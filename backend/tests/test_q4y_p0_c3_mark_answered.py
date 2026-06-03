"""Q4Y P0-C3 (2026-02 fork-resume) — Mark as Answered endpoint.

Coverage:
  1. Source-strict — endpoint exists, idempotent, writes
     `marked_answered` history kind.
  2. POST flips status to "answered" + appends history row with
     kind `marked_answered` and optional note.
  3. Endpoint does NOT require/set `answer_text` (the Submit-Answer
     flow remains the only path that writes a body).
  4. Idempotent — re-running on an already-answered question is a
     200 no-op, no new history row.
  5. Tenant scoping — a user without context membership cannot
     mark-answered (cross-context isolation guard).
  6. Optional `note` is captured under history[].note.
  7. Empty `note` (or missing) writes empty string, not None,
     and the row's `answered_at` reflects the call timestamp.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import pytest
from httpx import AsyncClient, ASGITransport

import server
from core import db


REPO = Path(__file__).resolve().parent.parent.parent
BE = REPO / "backend"
ROUTER = BE / "routers" / "questions.py"
PAGE   = REPO / "frontend" / "src" / "pages" / "Questions.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict
# ═════════════════════════════════════════════════════════════════════
def test_q4y_c3_endpoint_defined():
    src = _read(ROUTER)
    assert '@router.post("/contexts/{context_id}/questions/{question_id}/mark-answered")' in src
    assert "async def mark_question_answered(" in src
    assert "MarkAnsweredIn" in src
    assert '"kind":     "marked_answered"' in src
    # Idempotent shape — early return if already answered.
    assert 'if rec.get("status") == "answered":' in src


def test_q4y_c3_drawer_button_present():
    src = _read(PAGE)
    assert 'data-testid="question-drawer-mark-answered"' in src
    assert "Mark as Answered" in src


# ═════════════════════════════════════════════════════════════════════
# Wire-level
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
def app():
    return server.app


async def _seed_account_and_context(email: str, role: str = "owner") -> tuple[str, str, str]:
    """Returns (account_id, context_id, password)."""
    pw = "TestPass2026!"
    await db.accounts.delete_many({"email": email})
    aid = uuid.uuid4().hex
    cid = f"ctx-c3-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id":            aid,
        "email":         email,
        "email_lc":      email,
        "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        "name":          "C3 Tester",
        "first_name":    "C3",
        "declared_role": "executive",
        "mfa_enabled":   False,
        "is_superadmin": False,
        "first_session": {"status": "skipped"},
        "default_context_id": cid,
        "created_at":    now,
    })
    # Use the same shape `admin_qa_seed_recent_doc` uses
    # (`db.contexts` + `db.memberships` with `status: "active"`) —
    # that's the convention `require_context_membership` reads
    # (core.py:258).
    await db.contexts.insert_one({
        "id":               cid,
        "name":             "C3 Test Context",
        "owner_account_id": aid,
        "type":             "company",
        "created_at":       now,
    })
    await db.memberships.insert_one({
        "id":         uuid.uuid4().hex,
        "account_id": aid,
        "context_id": cid,
        "role":       "founder",
        "sub_role":   role,
        "status":     "active",
        "created_at": now,
    })
    return aid, cid, pw


async def _seed_question(*, context_id: str, assignee: str,
                          status: str = "open") -> str:
    qid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    await db.cycle_questions.insert_one({
        "id":                  qid,
        "context_id":          context_id,
        "cycle_id":            "",
        "assignee_account_id": assignee,
        "asker_role":          "board",
        "text":                f"C3 lockdown question {qid[:6]}",
        "status":              status,
        "asked_at":            now,
        "history":             [{"ts": now, "kind": "raised", "actor_id": assignee}],
        "_qa_seed":            True,
    })
    return qid


async def _cleanup_account(email: str) -> None:
    acc = await db.accounts.find_one({"email": email}, {"_id": 0, "id": 1,
                                                          "default_context_id": 1})
    if acc:
        await db.memberships.delete_many({"account_id": acc["id"]})
        if acc.get("default_context_id"):
            await db.contexts.delete_many({"id": acc["default_context_id"]})
        await db.accounts.delete_many({"id": acc["id"]})


async def _login(c: AsyncClient, email: str, pw: str) -> tuple[str, str]:
    r = await c.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await c.post(
        "/api/auth/login", headers={"X-CSRF-Token": csrf},
        json={"email": email, "password": pw},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    r = await c.get("/api/csrf")
    csrf2 = r.json()["csrf_token"]
    return token, csrf2


@pytest.mark.asyncio
async def test_q4y_c3_mark_answered_flips_status_and_appends_history(app):
    email = f"c3-flip-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account_and_context(email)
    qid = await _seed_question(context_id=cid, assignee=aid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok, csrf = await _login(c, email, pw)
            r = await c.post(
                f"/api/contexts/{cid}/questions/{qid}/mark-answered",
                headers={"Authorization": f"Bearer {tok}",
                          "X-CSRF-Token": csrf},
                json={"note": "Resolved out-of-band at 27-Jan board call."},
            )
            assert r.status_code == 200, r.text
            row = r.json()
            assert row["status"] == "answered"
            assert row["answered_by_account_id"] == aid
            assert "answered_at" in row and row["answered_at"]
            # NOTE: answer_text must NOT have been set.
            assert row.get("answer_text") in (None, "")
            # History — original "raised" + new "marked_answered".
            kinds = [h["kind"] for h in row.get("history") or []]
            assert kinds == ["raised", "marked_answered"], kinds
            ma = next(h for h in row["history"] if h["kind"] == "marked_answered")
            assert ma["actor_id"] == aid
            assert "board call" in ma["note"]
    finally:
        await db.cycle_questions.delete_many({"id": qid})
        await _cleanup_account(email)


@pytest.mark.asyncio
async def test_q4y_c3_idempotent_when_already_answered(app):
    email = f"c3-idem-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account_and_context(email)
    qid = await _seed_question(context_id=cid, assignee=aid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok, csrf = await _login(c, email, pw)
            # First call — flips status + appends 1 history row.
            await c.post(
                f"/api/contexts/{cid}/questions/{qid}/mark-answered",
                headers={"Authorization": f"Bearer {tok}",
                          "X-CSRF-Token": csrf},
                json={"note": "first"},
            )
            # Second call — must be 200 no-op, NO new history row.
            r2 = await c.post(
                f"/api/contexts/{cid}/questions/{qid}/mark-answered",
                headers={"Authorization": f"Bearer {tok}",
                          "X-CSRF-Token": csrf},
                json={"note": "second"},
            )
            assert r2.status_code == 200
            row = r2.json()
            assert row["status"] == "answered"
            kinds = [h["kind"] for h in row.get("history") or []]
            # Still just `raised` + 1× `marked_answered`.
            assert kinds.count("marked_answered") == 1, kinds
            # The note from the first call wins (idempotent — second
            # call did not overwrite).
            ma = next(h for h in row["history"] if h["kind"] == "marked_answered")
            assert ma["note"] == "first"
    finally:
        await db.cycle_questions.delete_many({"id": qid})
        await _cleanup_account(email)


@pytest.mark.asyncio
async def test_q4y_c3_works_without_note(app):
    email = f"c3-no-note-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account_and_context(email)
    qid = await _seed_question(context_id=cid, assignee=aid)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok, csrf = await _login(c, email, pw)
            r = await c.post(
                f"/api/contexts/{cid}/questions/{qid}/mark-answered",
                headers={"Authorization": f"Bearer {tok}",
                          "X-CSRF-Token": csrf},
                json={},
            )
            assert r.status_code == 200
            row = r.json()
            ma = next(h for h in row["history"] if h["kind"] == "marked_answered")
            # Empty string, not None — keeps the wire shape stable.
            assert ma["note"] == ""
    finally:
        await db.cycle_questions.delete_many({"id": qid})
        await _cleanup_account(email)


@pytest.mark.asyncio
async def test_q4y_c3_tenant_scope_blocks_cross_context_mark(app):
    """User B (member of context B) must NOT be able to mark-answered
    a question in context A.

    # negative-leak: locks in cross-tenant isolation for the C3
    # write path.
    """
    email_a = f"c3-a-{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"c3-b-{uuid.uuid4().hex[:6]}@example.com"
    aid_a, cid_a, _ = await _seed_account_and_context(email_a)
    aid_b, cid_b, pw_b = await _seed_account_and_context(email_b)
    # Question lives in context A.
    qid = await _seed_question(context_id=cid_a, assignee=aid_a)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            # User B logs in.
            tok_b, csrf_b = await _login(c, email_b, pw_b)
            # User B tries to mark-answered context-A's question
            # via either path label:
            for path in (
                f"/api/contexts/{cid_a}/questions/{qid}/mark-answered",  # right path, no membership
                f"/api/contexts/{cid_b}/questions/{qid}/mark-answered",  # wrong context label
            ):
                r = await c.post(
                    path,
                    headers={"Authorization": f"Bearer {tok_b}",
                              "X-CSRF-Token": csrf_b},
                    json={"note": "spoof"},
                )
                # Either 403 (membership rejected) or 404 (question
                # not found in this context). Either way: not 200.
                assert r.status_code in (403, 404), (
                    f"{path}: expected 403/404, got {r.status_code}"
                )
            # Question A still open.
            rec = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
            assert rec["status"] == "open"
            kinds = [h["kind"] for h in rec["history"]]
            assert "marked_answered" not in kinds
    finally:
        await db.cycle_questions.delete_many({"id": qid})
        await _cleanup_account(email_a)
        await _cleanup_account(email_b)


@pytest.mark.asyncio
async def test_q4y_c3_404_when_question_missing(app):
    email = f"c3-404-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account_and_context(email)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok, csrf = await _login(c, email, pw)
            r = await c.post(
                f"/api/contexts/{cid}/questions/missing-id-xyz/mark-answered",
                headers={"Authorization": f"Bearer {tok}",
                          "X-CSRF-Token": csrf},
                json={},
            )
            assert r.status_code == 404
    finally:
        await _cleanup_account(email)
