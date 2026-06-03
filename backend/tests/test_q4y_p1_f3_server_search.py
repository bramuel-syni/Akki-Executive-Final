"""Q4Y P1-F3 (2026-02 fork-resume) — Server-side `q` text search on
`GET /api/me/questions`.

Coverage:
  1. Source-strict — endpoint accepts `q` query param, uses
     `re.escape` to defang regex metacharacters, applies
     case-insensitive match.
  2. Case-insensitive hit — `q=RUNWAY` matches "runway" in body.
  3. Cross-page hit — a question on page 2 surfaces in page 1
     when `q` filters to it (regression vs. the legacy client-only
     filter that missed cross-page hits).
  4. Regex-injection defense — a question text containing literal
     regex metacharacters (`.`, `*`, `?`, `[`, `]`) is found by
     searching for the literal characters.
  5. Combines with status + asker_role filters (intersection
     applies cleanly).
  6. Tenant scoping — `q` only finds rows where
     `assignee_account_id == me` (legacy behaviour preserved; the
     /me endpoint is already account-scoped).
  7. `q=` empty / whitespace-only → no filter applied.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import pytest
from httpx import AsyncClient, ASGITransport

import server
from core import db


REPO = Path(__file__).resolve().parent.parent.parent
BE = REPO / "backend"
ROUTER = BE / "routers" / "questions.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict
# ═════════════════════════════════════════════════════════════════════
def test_q4y_f3_router_accepts_q_param_with_regex_escape():
    src = _read(ROUTER)
    assert 'q: Optional[str] = Query(default=None, max_length=120)' in src
    # Critical — re.escape() must be used to defuse regex metachars.
    assert 're.escape(q_text)' in src
    # Case-insensitive option.
    assert '"$options": "i"' in src


# ═════════════════════════════════════════════════════════════════════
# Wire-level
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
def app():
    return server.app


async def _seed_account(email: str) -> tuple[str, str, str]:
    pw = "TestPass2026!"
    await db.accounts.delete_many({"email": email})
    aid = uuid.uuid4().hex
    cid = f"ctx-f3-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id": aid, "email": email, "email_lc": email,
        "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        "name": "F3 Tester", "declared_role": "executive",
        "mfa_enabled": False, "is_superadmin": False,
        "first_session": {"status": "skipped"},
        "default_context_id": cid,
        "created_at": now,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "F3 Test Context",
        "owner_account_id": aid, "type": "company", "created_at": now,
    })
    await db.memberships.insert_one({
        "id": uuid.uuid4().hex, "account_id": aid, "context_id": cid,
        "role": "founder", "sub_role": "owner",
        "status": "active", "created_at": now,
    })
    return aid, cid, pw


async def _login(c: AsyncClient, email: str, pw: str) -> str:
    r = await c.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await c.post(
        "/api/auth/login", headers={"X-CSRF-Token": csrf},
        json={"email": email, "password": pw},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _seed_q(*, context_id: str, assignee: str, text: str,
                   status: str = "open", asker_role: str = "board",
                   asked_at: str | None = None) -> str:
    qid = uuid.uuid4().hex
    now = asked_at or datetime.now(timezone.utc).isoformat()
    await db.cycle_questions.insert_one({
        "id": qid, "context_id": context_id, "cycle_id": "",
        "assignee_account_id": assignee,
        "asker_role": asker_role,
        "text": text, "status": status, "asked_at": now,
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
async def test_q4y_f3_q_case_insensitive_hit(app):
    email = f"f3-case-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account(email)
    qids = []
    qids.append(await _seed_q(
        context_id=cid, assignee=aid,
        text="What is the runway under stress scenario B?",
    ))
    qids.append(await _seed_q(
        context_id=cid, assignee=aid,
        text="Has the board approved the new capital ratio?",
    ))
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            r = await c.get(
                "/api/me/questions",
                params={"q": "RUNWAY", "status": "all"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 200
            items = r.json()["items"]
            assert len(items) == 1
            assert "runway" in items[0]["text"].lower()
    finally:
        await _cleanup(email, qids)


@pytest.mark.asyncio
async def test_q4y_f3_q_finds_cross_page_hits(app):
    """A row that sits on page 2 must surface on page 1 when `q`
    narrows to it. This is the legacy bug — the old client-only
    filter only ran on the already-returned page."""
    email = f"f3-cross-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account(email)
    qids = []
    # 12 questions; the unique one is the OLDEST so on page 1 (sorted
    # by asked_at desc, "recent") it would be on page 2.
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(12):
        text = "decoy text never matching" if i != 0 else "PLATINUM RUNWAY token"
        qids.append(await _seed_q(
            context_id=cid, assignee=aid, text=text,
            asked_at=(base + timedelta(days=i)).isoformat(),
        ))
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            # Without `q`, page=1 (sorted desc) shows the most recent
            # 10 — does NOT include the OLDEST PLATINUM RUNWAY row.
            r1 = await c.get(
                "/api/me/questions",
                params={"status": "all", "page": 1, "page_size": 10},
                headers={"Authorization": f"Bearer {tok}"},
            )
            texts_p1 = [it["text"] for it in r1.json()["items"]]
            assert not any("PLATINUM" in t for t in texts_p1), (
                "fixture invalid: PLATINUM row landed on page 1 without filter"
            )
            # WITH `q=PLATINUM`, page=1 surfaces the cross-page hit.
            r2 = await c.get(
                "/api/me/questions",
                params={"status": "all", "page": 1, "page_size": 10,
                         "q": "PLATINUM"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            items = r2.json()["items"]
            assert len(items) == 1
            assert "PLATINUM RUNWAY" in items[0]["text"]
    finally:
        await _cleanup(email, qids)


@pytest.mark.asyncio
async def test_q4y_f3_regex_injection_defense(app):
    """A `q` value containing regex metacharacters must match the
    LITERAL characters, not the regex semantics. Specifically a
    `q="."` should NOT match every row."""
    email = f"f3-rx-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account(email)
    qids = []
    qids.append(await _seed_q(
        context_id=cid, assignee=aid,
        text="No metacharacters here",
    ))
    qids.append(await _seed_q(
        context_id=cid, assignee=aid,
        text="What [is] the (latest) snapshot?  And.then?",
    ))
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            # Bare "." should NOT match all rows (would in unescaped
            # regex); should only match rows literally containing ".".
            r = await c.get(
                "/api/me/questions",
                params={"q": ".", "status": "all"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            items = r.json()["items"]
            # Only the second row contains a literal period.
            assert len(items) == 1
            assert items[0]["text"] == "What [is] the (latest) snapshot?  And.then?"
            # Bare "[is]" should match its literal occurrence.
            r2 = await c.get(
                "/api/me/questions",
                params={"q": "[is]", "status": "all"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            items2 = r2.json()["items"]
            assert len(items2) == 1
            assert items2[0]["text"] == "What [is] the (latest) snapshot?  And.then?"
    finally:
        await _cleanup(email, qids)


@pytest.mark.asyncio
async def test_q4y_f3_combines_with_status_and_asker_role(app):
    email = f"f3-combo-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account(email)
    qids = []
    # Mix of statuses and asker_roles, all containing "alpha" so q
    # narrows them.
    qids.append(await _seed_q(context_id=cid, assignee=aid,
                                text="alpha board open", asker_role="board"))
    qids.append(await _seed_q(context_id=cid, assignee=aid,
                                text="alpha ceo open", asker_role="ceo"))
    qids.append(await _seed_q(context_id=cid, assignee=aid,
                                text="alpha board done", status="answered",
                                asker_role="board"))
    qids.append(await _seed_q(context_id=cid, assignee=aid,
                                text="no-match here", asker_role="board"))
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            r = await c.get(
                "/api/me/questions",
                params={"q": "alpha", "status": "open", "asker_role": "board"},
                headers={"Authorization": f"Bearer {tok}"},
            )
            items = r.json()["items"]
            assert len(items) == 1
            assert items[0]["text"] == "alpha board open"
    finally:
        await _cleanup(email, qids)


@pytest.mark.asyncio
async def test_q4y_f3_q_only_finds_my_questions(app):
    """The /me endpoint already filters by `assignee_account_id`.
    A user A's `q` query must NOT return user B's matching rows.

    # negative-leak: locks in tenant scoping on F3 + /me/questions.
    """
    email_a = f"f3-a-{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"f3-b-{uuid.uuid4().hex[:6]}@example.com"
    aid_a, cid_a, pw_a = await _seed_account(email_a)
    aid_b, cid_b, _    = await _seed_account(email_b)
    qids = []
    qids.append(await _seed_q(context_id=cid_b, assignee=aid_b,
                                text="ECHO B private question"))
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok_a = await _login(c, email_a, pw_a)
            r = await c.get(
                "/api/me/questions",
                params={"q": "ECHO", "status": "all"},
                headers={"Authorization": f"Bearer {tok_a}"},
            )
            items = r.json()["items"]
            assert items == [], (
                f"user A leaked user B's row: {items!r}"
            )
    finally:
        await _cleanup(email_a, [])
        await _cleanup(email_b, qids)


@pytest.mark.asyncio
async def test_q4y_f3_empty_q_does_not_filter(app):
    email = f"f3-empty-{uuid.uuid4().hex[:6]}@example.com"
    aid, cid, pw = await _seed_account(email)
    qids = []
    qids.append(await _seed_q(context_id=cid, assignee=aid, text="one"))
    qids.append(await _seed_q(context_id=cid, assignee=aid, text="two"))
    try:
        async with AsyncClient(transport=ASGITransport(app=app),
                                base_url="http://testserver") as c:
            tok = await _login(c, email, pw)
            for empty in ("", "   "):
                r = await c.get(
                    "/api/me/questions",
                    params={"q": empty, "status": "all"},
                    headers={"Authorization": f"Bearer {tok}"},
                )
                assert r.status_code == 200
                # Both rows present.
                assert len(r.json()["items"]) == 2
    finally:
        await _cleanup(email, qids)
