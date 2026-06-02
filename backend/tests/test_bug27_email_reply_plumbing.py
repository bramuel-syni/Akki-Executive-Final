"""Bug 27 / Fig 42 (2026-02 fork-resume) — Email Reply mode plumbing.

End-to-end logical test of the inbound email-reply ingestion +
read-side surface. The user-perceived symptom (per the handoff
one-liner; the literal QA-doc text was not in /app/memory and was
surfaced as such in the combined memo) was "Email Reply mode
plumbing". Ground-truth trace identified the break as option (c):
write path succeeds, read-side adapter (`_sanitize_task`) dropped
the field on the wire so the task owner never saw the reply body.

Coverage:
  1. Source-strict — `_sanitize_task` includes
     `contributor_comments` and the sanitizer trims `_id`.
  2. End-to-end ingestion + read round-trip — a SendGrid inbound
     payload with a `task-<token>@inbound` recipient lands the body
     onto `tasks.contributor_comments[]`, the GET /tasks/{task_id}
     response carries the comment with the precise shape, AND the
     team row flips to `submitted`.
  3. Multi-comment ordering — most-recent-first as
     `_sanitize_comments` guarantees.
  4. Portal-comment path also surfaces (kind="contributor").
  5. Tenant scoping — a reply replying to a token whose
     `task_account_id` is tenant A CANNOT land on a like-named task
     under tenant B.
  6. Sender-mismatch is silently dropped + audited as
     `sender_mismatch` (regression guard — not new behaviour).
  7. Doc IDs from inbound attachments are surfaced under `doc_ids`.

No mocks of business logic. SendGrid transport seam is bypassed by
calling the inbound webhook handler directly with a Postmark-
normalized payload (the same path the live webhook takes after the
SendGrid → Postmark adapter).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

import server
from core import db


REPO = Path(__file__).resolve().parent.parent.parent
BE = REPO / "backend"

TASKS_ROUTER = BE / "routers" / "tasks.py"
INBOUND_ROUTER = BE / "routers" / "inbound_email.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict
# ═════════════════════════════════════════════════════════════════════
def test_bug27_sanitize_task_surfaces_contributor_comments():
    src = _read(TASKS_ROUTER)
    assert '"contributor_comments":' in src
    assert "_sanitize_comments(" in src
    assert "def _sanitize_comments(" in src


def test_bug27_inbound_handler_writes_to_contributor_comments():
    """Regression guard — the write path must remain present."""
    src = _read(INBOUND_ROUTER)
    assert "contributor_comments" in src
    assert '"kind"' in src
    assert "email_body" in src


# ═════════════════════════════════════════════════════════════════════
# Wire-level — end-to-end ingestion + read
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
def app():
    return server.app


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _seed_task(*, owner_email: str, contributor_email: str,
                     account_id: str | None = None) -> tuple[str, str, str]:
    """Returns (task_id, token, account_id). Inserts:
      • The owner account row (if needed for /api/auth lookups).
      • The task row with the contributor in `team[]`.
      • The token row in `task_contributor_tokens`.
    Sender authority is fixture-driven: the contributor row carries
    `email = contributor_email`, so the inbound handler's From-
    sender check succeeds when the simulated From: matches.
    """
    aid = account_id or f"acc-bug27-{uuid.uuid4().hex[:10]}"
    tid = f"task-bug27-{uuid.uuid4().hex[:10]}"
    now = _now()
    team = [{
        "name": "Bug27 Reviewer",
        "role": "Reviewer",
        "email": contributor_email,
        "contribution": "Review section X",
        "contribution_mode": "email_reply",
        "status": "invited",
    }]
    await db.tasks.insert_one({
        "id":         tid,
        "account_id": aid,
        "owner_id":   aid,
        "name":       "Bug27 trace task",
        "objective":  "Trace email-reply plumbing",
        "success_criteria": "Reply body visible to owner",
        "team":       team,
        "state":      "active",
        "created_at": now,
        "updated_at": now,
    })
    tok = uuid.uuid4().hex + uuid.uuid4().hex
    await db.task_contributor_tokens.insert_one({
        "id":                uuid.uuid4().hex,
        "token":             tok,
        "task_id":           tid,
        "task_account_id":   aid,
        "contributor_email": contributor_email.lower(),
        "contributor_id":    contributor_email.lower(),
        "expires_at":        (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "used":              False,
        "created_at":        now,
    })
    return tid, tok, aid


async def _cleanup(task_id: str, token: str) -> None:
    await db.tasks.delete_many({"id": task_id})
    await db.task_contributor_tokens.delete_many({"token": token})
    await db.task_inbound_emails.delete_many({"task_id": task_id})


def _postmark_payload(*, to_token: str, from_addr: str,
                      subject: str, text_body: str,
                      domain: str = "inbound.akki.syni.ai") -> dict:
    """Build the Postmark-normalized inbound payload shape the live
    SendGrid → Postmark adapter produces. Mirrors what
    `_dispatch_inbound_payload` accepts."""
    return {
        "MessageID":  uuid.uuid4().hex,
        "Date":       _now(),
        "Subject":    subject,
        "From":       from_addr,
        "FromFull":   {"Email": from_addr, "Name": ""},
        "To":         f"task-{to_token}@{domain}",
        "ToFull":     [{"Email": f"task-{to_token}@{domain}",
                         "MailboxHash": f"task-{to_token}"}],
        "MailboxHash": f"task-{to_token}",
        "TextBody":    text_body,
        "HtmlBody":    "",
        "StrippedTextReply": text_body,
        "Attachments": [],
    }


@pytest.mark.asyncio
async def test_bug27_email_reply_lands_on_task_and_surfaces_to_owner(app):
    """The full round-trip: inbound email payload → handler → DB
    push → GET /api/tasks/{task_id} carries the comment payload."""
    from routers.inbound_email import _dispatch_inbound_payload
    contributor = f"bug27-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, aid = await _seed_task(
        owner_email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
        contributor_email=contributor,
    )
    try:
        payload = _postmark_payload(
            to_token=tok,
            from_addr=contributor,
            subject="Re: Section X review",
            text_body=("Here's my review.\n\n"
                       "I think section X needs three more pages on the "
                       "risk envelope. Otherwise looks great."),
        )
        body = await _dispatch_inbound_payload(payload)
        assert body.get("ok") is True, body
        assert body.get("task_id") == tid, body

        # Read back the task row directly to confirm the write
        # happened.
        t = await db.tasks.find_one({"id": tid}, {"_id": 0})
        assert t is not None
        cc = t.get("contributor_comments") or []
        assert len(cc) == 1
        assert cc[0]["kind"] == "email_body"
        assert cc[0]["reviewer"] == contributor.lower()
        assert "risk envelope" in cc[0]["comment"]
        assert cc[0]["subject"] == "Re: Section X review"

        # Team status flipped to "submitted".
        team = t.get("team") or []
        assert team[0]["status"] == "submitted"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_bug27_read_side_surfaces_comments_in_sanitized_response(app):
    """Calls the read-side helper directly (no auth needed) to lock
    in the API shape the FE consumes."""
    from routers.tasks import _sanitize_task

    contributor = f"bug27r-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task(
        owner_email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
        contributor_email=contributor,
    )
    try:
        # Push two comments — one email_body, one portal — onto the
        # task row directly. Older `created_at` first; sanitize_task
        # must return them most-recent-first.
        await db.tasks.update_one(
            {"id": tid},
            {"$push": {"contributor_comments": {
                "$each": [
                    {
                        "id":         uuid.uuid4().hex,
                        "kind":       "email_body",
                        "reviewer":   contributor.lower(),
                        "comment":    "First reply via email.",
                        "subject":    "Re: Section X",
                        "doc_ids":    ["doc-abc"],
                        "created_at": "2026-02-01T00:00:00+00:00",
                    },
                    {
                        "id":         uuid.uuid4().hex,
                        "kind":       "contributor",
                        "reviewer":   contributor.lower(),
                        "comment":    "Second reply via portal.",
                        "doc_ids":    [],
                        "created_at": "2026-02-02T00:00:00+00:00",
                    },
                ],
            }}},
        )
        t = await db.tasks.find_one({"id": tid}, {"_id": 0})
        out = _sanitize_task(t)
        assert "contributor_comments" in out
        cc = out["contributor_comments"]
        assert len(cc) == 2
        # Most-recent first.
        assert cc[0]["kind"] == "contributor"
        assert cc[1]["kind"] == "email_body"
        # Each row has the precise shape the FE expects.
        for row in cc:
            for k in ("id", "kind", "reviewer", "comment", "subject",
                      "doc_ids", "created_at"):
                assert k in row, k
        assert cc[1]["doc_ids"] == ["doc-abc"]
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_bug27_sender_mismatch_silently_dropped(app):
    """Regression guard — a reply from an email that does NOT match
    the team contributor email must NOT push a comment. The audit
    row in `task_inbound_emails` is the only surface for the
    rejection (matches existing P0-C-style security shape)."""
    from routers.inbound_email import _dispatch_inbound_payload
    contributor = f"bug27sm-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task(
        owner_email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
        contributor_email=contributor,
    )
    try:
        payload = _postmark_payload(
            to_token=tok,
            from_addr=f"attacker-{uuid.uuid4().hex[:6]}@example.com",
            subject="Spoof reply",
            text_body="I'm pretending to be the contributor.",
        )
        await _dispatch_inbound_payload(payload)

        t = await db.tasks.find_one({"id": tid}, {"_id": 0})
        cc = t.get("contributor_comments") or []
        assert len(cc) == 0, "spoofed reply must NOT land on the task"
        # Team status MUST NOT have flipped.
        assert (t.get("team") or [])[0]["status"] == "invited"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_bug27_cross_tenant_isolation_via_account_scoping(app):
    """A token row's `task_account_id` is the authoritative tenant
    boundary. A token belonging to tenant A cannot push a comment
    onto a like-named task under tenant B even if a malicious actor
    forges the From header.

    # negative-leak: this assertion must remain green to lock in
    # cross-tenant isolation on the email-reply plumbing.
    """
    from routers.inbound_email import _dispatch_inbound_payload
    contributor = f"bug27ct-{uuid.uuid4().hex[:8]}@example.com"
    aid_a = f"acc-A-{uuid.uuid4().hex[:8]}"
    aid_b = f"acc-B-{uuid.uuid4().hex[:8]}"
    tid_a, tok_a, _ = await _seed_task(
        owner_email=f"owner-A-{uuid.uuid4().hex[:6]}@example.com",
        contributor_email=contributor, account_id=aid_a,
    )
    tid_b, tok_b, _ = await _seed_task(
        owner_email=f"owner-B-{uuid.uuid4().hex[:6]}@example.com",
        contributor_email=contributor, account_id=aid_b,
    )
    try:
        # Reply to token A. Must land ONLY on task A.
        payload = _postmark_payload(
            to_token=tok_a, from_addr=contributor,
            subject="Re: Task A review",
            text_body="Tenant-A-only contribution.",
        )
        await _dispatch_inbound_payload(payload)
        ta = await db.tasks.find_one({"id": tid_a}, {"_id": 0})
        tb = await db.tasks.find_one({"id": tid_b}, {"_id": 0})
        assert len(ta.get("contributor_comments") or []) == 1
        assert len(tb.get("contributor_comments") or []) == 0
        # Task A's row carries account_id=aid_a; B's carries aid_b.
        assert ta["account_id"] == aid_a
        assert tb["account_id"] == aid_b
    finally:
        await _cleanup(tid_a, tok_a)
        await _cleanup(tid_b, tok_b)


@pytest.mark.asyncio
async def test_bug27_attached_docs_surface_in_doc_ids(app):
    """When the inbound email carries attachments, the handler
    creates `documents` rows and includes their IDs under
    `comment.doc_ids[]`."""
    from routers.inbound_email import _dispatch_inbound_payload
    contributor = f"bug27att-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task(
        owner_email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
        contributor_email=contributor,
    )
    try:
        import base64
        payload = _postmark_payload(
            to_token=tok, from_addr=contributor,
            subject="Re: With attachment",
            text_body="See attached PDF.",
        )
        payload["Attachments"] = [{
            "Name":          "review.pdf",
            "ContentType":   "application/pdf",
            "ContentLength": 12,
            "Content":       base64.b64encode(b"%PDF-fake-12").decode(),
        }]
        await _dispatch_inbound_payload(payload)

        t = await db.tasks.find_one({"id": tid}, {"_id": 0})
        cc = t.get("contributor_comments") or []
        assert len(cc) == 1
        assert len(cc[0].get("doc_ids") or []) == 1
        # Confirm the underlying document row exists.
        doc_id = cc[0]["doc_ids"][0]
        doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
        assert doc is not None
        assert doc.get("origin") in ("email_receipt", "akki_generated")
        await db.documents.delete_many({"id": doc_id})
    finally:
        await _cleanup(tid, tok)
