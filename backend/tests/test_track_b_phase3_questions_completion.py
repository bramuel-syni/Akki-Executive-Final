"""Track B Phase B3 — Open Questions feature completion lockdowns.

R4 (≤10 tests). Coverage:

  1. Share endpoint: 200 + history audit kind=shared + recipient list
  2. Reopen endpoint: Answered → Open + history kind=reopened
  3. Reopen idempotent on already-open Q that was previously closed
  4. Reopen guard: never-closed Q → 400
  5. Link-response: writes response_doc_id + history kind=response_linked
  6. Link-response cross-context blocked: 404 when doc not in same context
  7. History array surfaces ALL state changes chronologically
  8. Empty state verbatim copy + Go to Document CTA wired
  9. Cross-tenant: viewer cannot reach admin's question via any new endpoint
 10. Q4Y regression: mark-answered still flips status
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app

REPO = Path("/app")
FRONTEND = REPO / "frontend" / "src"


@pytest.fixture
def transport():
    return ASGITransport(app=app)


async def _csrf_login(ac: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await ac.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await ac.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token
    r = await ac.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_question_via_admin_qa(ac: AsyncClient, headers: Dict[str, str], *,
                                       account_id: str, context_id: str,
                                       status: str = "open") -> str:
    """Seed a cycle_question row directly via Mongo for deterministic
    state. Uses the same shape the existing harness uses."""
    from datetime import datetime, timezone
    from core import db
    qid = "q-" + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    row: Dict[str, Any] = {
        "id":         qid,
        "context_id": context_id,
        "asker_account_id": account_id,
        "asker_role": "executive",
        "text":       f"Lockdown question {qid[-6:]}",
        "status":     status,
        "asked_at":   now,
        "history":    [{"ts": now, "kind": "raised", "actor_id": account_id}],
    }
    if status == "answered":
        row["answered_at"] = now
        row["history"].append({"ts": now, "kind": "marked_answered", "actor_id": account_id})
    await db.cycle_questions.insert_one(row)
    return qid


async def _membership_for_admin(ac: AsyncClient, headers: Dict[str, str], context_id: str) -> str:
    """The new endpoints sit behind `require_context_membership` which
    reads from `db.memberships` and requires `status='active'` (per
    `core.py:258`). Seed accordingly."""
    from core import db
    me = await ac.get("/api/auth/me", headers=headers)
    aid = me.json()["account"]["id"]
    await db.contexts.update_one(
        {"id": context_id},
        {"$setOnInsert": {
            "id": context_id, "name": f"ctx {context_id[-6:]}",
            "kind": "company",
        }},
        upsert=True,
    )
    await db.memberships.update_one(
        {"account_id": aid, "context_id": context_id},
        {"$set": {
            "account_id": aid, "context_id": context_id,
            "role": "owner", "status": "active", "sub_role": "admin",
        }},
        upsert=True,
    )
    return aid


# ─── Test 1 — Share endpoint ────────────────────────────────────


@pytest.mark.asyncio
async def test_share_records_audit_with_recipients(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-sh-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(ac, admin, account_id=aid, context_id=ctx)
        r = await ac.post(
            f"/api/contexts/{ctx}/questions/{qid}/share",
            json={"recipient_emails": ["lead@x.com", "ned@y.com"],
                  "message": "Reviewing this for next week."},
            headers=admin,
        )
        assert r.status_code == 200, r.text
        rec = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        history = rec["history"]
        share_row = next((h for h in history if h["kind"] == "shared"), None)
        assert share_row is not None
        assert share_row["payload"]["recipients"] == ["lead@x.com", "ned@y.com"]
        assert "next week" in (share_row["payload"]["message"] or "")


# ─── Tests 2 + 3 + 4 — Reopen happy + idempotent + guard ───────


@pytest.mark.asyncio
async def test_reopen_answered_to_open(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-ro-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(
            ac, admin, account_id=aid, context_id=ctx, status="answered",
        )
        r = await ac.post(f"/api/contexts/{ctx}/questions/{qid}/reopen", headers=admin)
        assert r.status_code == 200
        rec = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        assert rec["status"] == "open"
        assert "answered_at" not in rec
        assert any(h["kind"] == "reopened" for h in rec["history"])


@pytest.mark.asyncio
async def test_reopen_idempotent_on_already_open_after_close(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-roi-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(
            ac, admin, account_id=aid, context_id=ctx, status="answered",
        )
        await ac.post(f"/api/contexts/{ctx}/questions/{qid}/reopen", headers=admin)
        before = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        n_reopens_before = sum(1 for h in before["history"] if h["kind"] == "reopened")
        # Second call should be a no-op — Q already open.
        r = await ac.post(f"/api/contexts/{ctx}/questions/{qid}/reopen", headers=admin)
        assert r.status_code == 200
        after = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        n_reopens_after = sum(1 for h in after["history"] if h["kind"] == "reopened")
        assert n_reopens_after == n_reopens_before


@pytest.mark.asyncio
async def test_reopen_guard_never_closed_returns_400(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-rog-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(
            ac, admin, account_id=aid, context_id=ctx, status="open",
        )
        r = await ac.post(f"/api/contexts/{ctx}/questions/{qid}/reopen", headers=admin)
        assert r.status_code == 400
        assert "never closed" in r.text.lower()


# ─── Test 5 — Link response document ────────────────────────────


@pytest.mark.asyncio
async def test_link_response_writes_doc_id_and_audit(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-lr-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        # Seed a doc in the same context.
        doc_id = "doc-" + uuid.uuid4().hex[:12]
        await db.documents.insert_one({
            "id": doc_id, "context_id": ctx, "account_id": aid,
            "filename": "Response.pdf", "title": "Q3 board response",
            "created_at": "2026-06-04T00:00:00Z",
        })
        qid = await _seed_question_via_admin_qa(ac, admin, account_id=aid, context_id=ctx)
        r = await ac.post(
            f"/api/contexts/{ctx}/questions/{qid}/link-response",
            json={"document_id": doc_id}, headers=admin,
        )
        assert r.status_code == 200, r.text
        rec = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        assert rec["response_doc_id"] == doc_id
        assert any(h["kind"] == "response_linked" for h in rec["history"])


# ─── Test 6 — Link cross-context blocked ───────────────────────


@pytest.mark.asyncio
async def test_link_response_cross_context_blocked(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx_a = "tbp3-cxA-" + uuid.uuid4().hex[:6]
        ctx_b = "tbp3-cxB-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx_a)
        await _membership_for_admin(ac, admin, ctx_b)
        # Doc lives in ctx_b; question is in ctx_a → must 404.
        doc_id = "doc-" + uuid.uuid4().hex[:12]
        await db.documents.insert_one({
            "id": doc_id, "context_id": ctx_b, "account_id": aid,
            "filename": "x.pdf", "title": "Other context doc",
        })
        qid = await _seed_question_via_admin_qa(
            ac, admin, account_id=aid, context_id=ctx_a,
        )
        r = await ac.post(
            f"/api/contexts/{ctx_a}/questions/{qid}/link-response",
            json={"document_id": doc_id}, headers=admin,
        )
        assert r.status_code == 404


# ─── Test 7 — History array ordering ───────────────────────────


@pytest.mark.asyncio
async def test_history_ordering_across_all_actions(transport):
    from core import db
    import asyncio
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-h-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(ac, admin, account_id=aid, context_id=ctx)
        # raised → marked_answered → reopened → shared → response_linked
        await ac.post(f"/api/contexts/{ctx}/questions/{qid}/mark-answered",
                      json={}, headers=admin)
        await asyncio.sleep(0.005)
        await ac.post(f"/api/contexts/{ctx}/questions/{qid}/reopen", headers=admin)
        await asyncio.sleep(0.005)
        await ac.post(f"/api/contexts/{ctx}/questions/{qid}/share",
                      json={"recipient_emails": ["x@y.com"]}, headers=admin)
        doc_id = "doc-" + uuid.uuid4().hex[:12]
        await db.documents.insert_one({
            "id": doc_id, "context_id": ctx, "account_id": aid,
            "title": "Reply.pdf",
        })
        await ac.post(f"/api/contexts/{ctx}/questions/{qid}/link-response",
                      json={"document_id": doc_id}, headers=admin)
        rec = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        kinds_in_order = [h["kind"] for h in rec["history"]]
        assert "raised" in kinds_in_order
        assert "marked_answered" in kinds_in_order
        assert "reopened" in kinds_in_order
        assert "shared" in kinds_in_order
        assert "response_linked" in kinds_in_order
        # The five new actions appear after `raised` in order.
        idx = {k: kinds_in_order.index(k) for k in
               ("raised", "marked_answered", "reopened", "shared", "response_linked")}
        assert idx["raised"] < idx["marked_answered"]
        assert idx["marked_answered"] < idx["reopened"]
        assert idx["reopened"] < idx["shared"]
        assert idx["shared"] < idx["response_linked"]


# ─── Test 8 — Empty state verbatim copy ────────────────────────


def test_empty_state_carries_verbatim_qa_copy_and_go_to_document_cta():
    """G23 verbatim copy from Doc 3 paragraph 26 must appear on the
    Questions page empty state for non-answered filter."""
    src = (FRONTEND / "pages" / "Questions.jsx").read_text(encoding="utf-8")
    assert "You have not generated any questions yet. Go to a document to generate questions." in src, (
        "Questions.jsx empty state missing the verbatim QA copy."
    )
    assert 'data-testid="questions-empty-go-to-document"' in src
    assert 'navigate("/app/documents")' in src
    # Old Z2.4 CTA "Run Solva on a document" must be GONE from empty state.
    assert "Run Solva on a document" not in src or "questions-empty-run-solva" not in src


# ─── Test 9 — Cross-tenant guard on every new endpoint ─────────


@pytest.mark.asyncio
async def test_cross_tenant_blocked_on_all_new_endpoints(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-tn-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(
            ac, admin, account_id=aid, context_id=ctx, status="answered",
        )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        viewer = await _csrf_login(ac, "viewer@akki.ai", "Viewer2026!")
        for path, payload in (
            (f"/api/contexts/{ctx}/questions/{qid}/share",
             {"recipient_emails": ["x@y.com"]}),
            (f"/api/contexts/{ctx}/questions/{qid}/reopen", None),
            (f"/api/contexts/{ctx}/questions/{qid}/link-response",
             {"document_id": "doc-x"}),
        ):
            r = await (
                ac.post(path, headers=viewer)
                if payload is None
                else ac.post(path, json=payload, headers=viewer)
            )
            assert r.status_code in (403, 404), (
                f"tenant leak on {path}: viewer got {r.status_code}: {r.text[:200]}"
            )


# ─── Test 10 — Mark-answered regression ────────────────────────


@pytest.mark.asyncio
async def test_mark_answered_still_works(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "tbp3-mr-" + uuid.uuid4().hex[:6]
        aid = await _membership_for_admin(ac, admin, ctx)
        qid = await _seed_question_via_admin_qa(ac, admin, account_id=aid, context_id=ctx)
        r = await ac.post(
            f"/api/contexts/{ctx}/questions/{qid}/mark-answered",
            json={}, headers=admin,
        )
        assert r.status_code == 200
        rec = await db.cycle_questions.find_one({"id": qid}, {"_id": 0})
        assert rec["status"] == "answered"
        assert any(h["kind"] == "marked_answered" for h in rec["history"])
