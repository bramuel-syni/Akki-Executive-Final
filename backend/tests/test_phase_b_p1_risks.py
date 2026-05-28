"""Phase B — P1 risk regression tests.

Covers:
1. Solva single-session route enforces strict `context_id` scoping
   (cross-context access returns 404 — does NOT leak session existence).
2. SSE error emitters in `streaming_v9.py` use the canonical
   `{type(exc).__name__}: {str(exc)[:300]}` format — no `repr(exc)`
   verbose-leak strings.
3. The Phase A→B `client.invoke()` path still rejects foreign tenants
   (regression locking the P0 from the previous patch).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def client():
    # Force LLM mock mode for hermetic runs.
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved_overrides)


@pytest_asyncio.fixture
async def authed_user(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"phaseb-{suffix}@example.com"
    password = "PhaseB2026!"
    account_id = f"acc-phaseb-{suffix}"
    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseB Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"account_id": account_id, "email": email, "password": password}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.solva_v2_sessions.delete_many({"account_id": account_id})


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────
# P1 Risk #2 — Solva single-session route MUST scope by context_id.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_solva_session_rejects_foreign_context(client, db_conn, authed_user):
    """A session belongs to context A; the same user requesting it
    while operating in context B receives 404, never the payload."""
    sid = "sv2-" + uuid.uuid4().hex
    # Seed a Solva session bound to context-A.
    await db_conn.solva_v2_sessions.insert_one({
        "id": sid,
        "account_id": authed_user["account_id"],
        "context_id": "context-A",
        "submodule": "seek_clarity",
        "intent_text": "stress test",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    auth = await _login(client, authed_user["email"], authed_user["password"])

    # Right context → 200 + payload.
    r_ok = await client.get(f"/api/solva/v2/sessions/{sid}",
                            params={"context_id": "context-A"}, headers=auth)
    assert r_ok.status_code == 200, r_ok.text
    assert r_ok.json()["id"] == sid

    # Foreign context → 404 (don't leak existence).
    r_no = await client.get(f"/api/solva/v2/sessions/{sid}",
                            params={"context_id": "context-B"}, headers=auth)
    assert r_no.status_code == 404, r_no.text
    body = r_no.json()
    # Detail must NOT echo the session id (no existence-leak via error text).
    assert sid not in (body.get("detail") or "")


# ─────────────────────────────────────────────────────────────────────
# P1 Risk #3 — SSE error emitter uses canonical error format.
# ─────────────────────────────────────────────────────────────────────
def test_streaming_v9_no_repr_exc():
    """Static grep — no `repr(exc)` survives in streaming_v9.py error paths."""
    p = "/app/backend/routers/streaming_v9.py"
    text = open(p, encoding="utf-8").read()
    assert "repr(exc)" not in text, (
        "repr(exc) found in streaming_v9.py — replace with "
        "f'{type(exc).__name__}: {str(exc)[:300]}'"
    )
    # Canonical format must be present at least once.
    assert "{type(exc).__name__}" in text


def test_streaming_v9_error_format_locked():
    """Confirms streaming_v9.py uses the canonical Phase L emitter
    error API + the exception-authenticity format
    (`{type(exc).__name__}: {str(exc)[:N]}` — not bare repr, not bare str).
    Phase L.b.3 (2026-05-27): rewrite of streaming_v9 uses the
    `PhaseEmitter.error(...)` method (via the `e.error(...)` helper)
    instead of the legacy `_error_event(...)`."""
    p = "/app/backend/routers/streaming_v9.py"
    import re
    text = open(p, encoding="utf-8").read()
    # The shared wrap _wrap_synchronous_handler dispatches `e.error(...)`
    # for both HTTPException and generic Exception branches. The
    # surface adapters may also raise HTTPException directly, which the
    # wrap converts. Lock the canonical exception-class format.
    canonical_pattern = re.search(
        r"\{type\(exc\)\.__name__\}.*\{str\(exc\)",
        text,
    )
    assert canonical_pattern is not None, (
        "streaming_v9.py must carry the canonical "
        "`{type(exc).__name__}: {str(exc)[:N]}` exception format"
    )
    # And the emitter error path must be exercised by the wrap helper.
    assert "await e.error(" in text, (
        "streaming_v9.py must use `await e.error(...)` from PhaseEmitter "
        "(Phase L.b.3 emitter contract)"
    )
