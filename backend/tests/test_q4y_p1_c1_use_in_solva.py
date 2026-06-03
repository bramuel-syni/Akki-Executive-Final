"""Q4Y P1-C1 (2026-02 fork-resume) — "Use in Solva" CTA wiring.

Coverage:
  1. Source-strict — solva_v2 has the `kind == "question"` branch
     in `fetch_take_to_solva_seed`. The supported-kinds error message
     lists `question`. The seed comment block documents the new
     kind.
  2. Source-strict — `Questions.jsx` imports `takeToSolva` and the
     drawer renders a `question-drawer-use-in-solva` button calling
     it with kind="question".
  3. Seed returns `{seed_text, citation_label}` with the precise
     label format `"Question · {first 60 chars}…"`.
  4. Citation label trims correctly for short and long question
     text.
  5. 404 when the question doesn't exist.
  6. Membership guard — a user not on the question's context gets
     404 (no leak via the seed payload).

  No new chat/Solva flows. Reuses the existing
  `routers/solva_v2.py::fetch_take_to_solva_seed` resolver.
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


@pytest.fixture
def app():
    return server.app


async def _login(c: AsyncClient, email: str, pw: str) -> str:
    r = await c.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await c.post(
        "/api/auth/login", headers={"X-CSRF-Token": csrf},
        json={"email": email, "password": pw},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


REPO = Path(__file__).resolve().parent.parent.parent
BE = REPO / "backend"
SOLVA_ROUTER = BE / "routers" / "solva_v2.py"
PAGE = REPO / "frontend" / "src" / "pages" / "Questions.jsx"
HELPER = REPO / "frontend" / "src" / "lib" / "takeToSolva.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict
# ═════════════════════════════════════════════════════════════════════
def test_q4y_c1_solva_router_has_question_branch():
    src = _read(SOLVA_ROUTER)
    assert 'elif kind == "question":' in src
    assert 'cycle_questions.find_one(' in src
    # New citation_label format.
    assert '"Question · {snippet}"' in src
    # Question listed in the supported-kinds error message.
    assert "ned_meeting, question" in src
    # Documentation comment block updated.
    assert "Q4Y P1-C1" in src


def test_q4y_c1_drawer_button_calls_takeToSolva():
    page = _read(PAGE)
    helper = _read(HELPER)
    assert 'data-testid="question-drawer-use-in-solva"' in page
    assert 'takeToSolva({ navigate, kind: "question", id: row.id })' in page
    assert "Use in Solva" in page
    # Helper is the canonical Pulse pattern.
    assert "/app/solva/session/new" in helper


# ═════════════════════════════════════════════════════════════════════
# Wire-level — direct call into fetch_take_to_solva_seed
# ═════════════════════════════════════════════════════════════════════
async def _seed(email: str, has_membership: bool) -> tuple[str, str, str]:
    pw = "TestPass2026!"
    await db.accounts.delete_many({"email": email})
    aid = uuid.uuid4().hex
    cid = f"ctx-c1-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id": aid, "email": email, "email_lc": email,
        "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        "name": "C1 Tester", "declared_role": "executive",
        "mfa_enabled": False, "is_superadmin": False,
        "first_session": {"status": "skipped"},
        "default_context_id": cid,
        "created_at": now,
    })
    if has_membership:
        await db.contexts.insert_one({
            "id": cid, "name": "C1 Test Context",
            "owner_account_id": aid, "type": "company", "created_at": now,
        })
        await db.memberships.insert_one({
            "id": uuid.uuid4().hex, "account_id": aid, "context_id": cid,
            "role": "founder", "sub_role": "owner",
            "status": "active", "created_at": now,
        })
    return aid, cid, pw


async def _seed_question(*, context_id: str, assignee: str, text: str) -> str:
    qid = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    await db.cycle_questions.insert_one({
        "id": qid, "context_id": context_id, "cycle_id": "",
        "assignee_account_id": assignee,
        "asker_role": "board",
        "text": text, "status": "open", "asked_at": now,
        "history": [{"ts": now, "kind": "raised", "actor_id": assignee}],
        "_qa_seed": True,
    })
    return qid


async def _cleanup(email: str, qids: list[str]) -> None:
    acc = await db.accounts.find_one({"email": email}, {"_id": 0, "id": 1,
                                                          "default_context_id": 1})
    if acc:
        await db.memberships.delete_many({"account_id": acc["id"]})
        if acc.get("default_context_id"):
            await db.contexts.delete_many({"id": acc["default_context_id"]})
        await db.accounts.delete_many({"id": acc["id"]})
    if qids:
        await db.cycle_questions.delete_many({"id": {"$in": qids}})


@pytest.mark.asyncio
async def test_q4y_c1_seed_returns_question_payload_short_text(app):
    email = f"c1-short-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed(email, has_membership=True)
    qid = await _seed_question(
        context_id=cid, assignee=aid,
        text="Short Q text.",
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            r = await c.get(
                "/api/solva/v2/seed",
                params={"kind": "question", "id": qid},
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 200, r.text
            seed = r.json()
            assert seed["seed_text"] == "Short Q text."
            assert seed["citation_label"] == "Question · Short Q text."
    finally:
        await _cleanup(email, [qid])


@pytest.mark.asyncio
async def test_q4y_c1_seed_returns_question_payload_long_text(app):
    email = f"c1-long-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed(email, has_membership=True)
    long_text = (
        "What is the runway under stress scenario B "
        "given the new capital allocation policy and the most "
        "recent forecast revisions?"
    )
    qid = await _seed_question(context_id=cid, assignee=aid, text=long_text)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            r = await c.get(
                "/api/solva/v2/seed",
                params={"kind": "question", "id": qid},
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 200, r.text
            seed = r.json()
            prefix = "Question · "
            assert seed["citation_label"].startswith(prefix)
            snippet = seed["citation_label"][len(prefix):]
            assert snippet.endswith("…"), snippet
            body = snippet.rstrip("…").rstrip()
            assert body == long_text[:60].rstrip()
    finally:
        await _cleanup(email, [qid])


@pytest.mark.asyncio
async def test_q4y_c1_seed_404_when_question_missing(app):
    email = f"c1-404-{uuid.uuid4().hex[:6]}@example.com"
    aid, _, pw = await _seed(email, has_membership=True)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            r = await c.get(
                "/api/solva/v2/seed",
                params={"kind": "question", "id": "bogus-id-xyz"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 404
    finally:
        await _cleanup(email, [])


@pytest.mark.asyncio
async def test_q4y_c1_seed_404_when_no_membership(app):
    """Cross-tenant guard — caller has no membership on the
    question's context. Resolver returns 404 (NOT the seed data)
    so context-A's question text doesn't leak via this path.

    # negative-leak: locks in tenant isolation for the C1 seed.
    """
    email_a = f"c1a-{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"c1b-{uuid.uuid4().hex[:6]}@example.com"
    aid_a, cid_a, _    = await _seed(email_a, has_membership=True)
    aid_b, _,    pw_b = await _seed(email_b, has_membership=False)
    qid = await _seed_question(
        context_id=cid_a, assignee=aid_a, text="Secret context-A query.",
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok_b = await _login(c, email_b, pw_b)
            r = await c.get(
                "/api/solva/v2/seed",
                params={"kind": "question", "id": qid},
                headers={"Authorization": f"Bearer {tok_b}"},
            )
            assert r.status_code == 404
            # Seed payload not leaked in the detail message.
            assert "Secret context-A query" not in r.text
    finally:
        await _cleanup(email_a, [qid])
        await _cleanup(email_b, [])
