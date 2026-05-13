"""Chunk 1 — P0 Solva cross-account leakage regression tests (WS-R16).

Locks the privacy fix applied 2026-05-13 to
`GET /api/solva/v2/sessions` so it cannot silently regress.

Bug summary
-----------
Pre-fix the endpoint filtered by `account_id` only. A user with active
memberships in multiple workspace contexts (companies / boards) saw
Solva sessions from EVERY context they belonged to, mixed into the
Generate-Brief-from-Solva picker. That violated AKKI's data-segregation
promise — a tester on a workspace they had never used Solva on still
saw sessions from their other workspaces.

Tests in this file
------------------
* `test_list_sessions_requires_context_id` — 422 when omitted.
* `test_list_sessions_rejects_non_member_context` — 403 when caller
  is not an active member of the requested context.
* `test_list_sessions_strictly_scopes_to_context` — the canonical
  isolation test: two contexts, one session each, must surface only
  the requested context's session.
* `test_list_sessions_excludes_orphan_context_id_rows` — sessions
  whose stored `context_id` is null / missing must NOT leak under
  any context_id filter (defense-in-depth for legacy data).

The fixtures use the live FastAPI app + the local Mongo through the
shared test_client pattern other tests use.
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


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def two_context_user(db_conn):
    """Create a fresh user with two active memberships + one Solva
    session per context. Returns dict {email, password, ctx_a, ctx_b,
    session_a_id, session_b_id}. Tears down everything at the end."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk1-leak-{suffix}@example.com"
    password = "Chunk1Leak2026!"
    account_id = f"acc-{suffix}"
    ctx_a = f"ctxA-{suffix}"
    ctx_b = f"ctxB-{suffix}"
    session_a = f"sessA-{suffix}"
    session_b = f"sessB-{suffix}"
    now = _iso()

    # bcrypt the password via the same path the real signup uses.
    from core import hash_password
    pw_hash = hash_password(password)

    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": pw_hash,
        "name": "Chunk1 Leak Probe", "role": "executive",
        "created_at": now, "default_context_id": ctx_a,
        "session_version": 0, "verified": True,
    })
    for cid in (ctx_a, ctx_b):
        await db_conn.contexts.insert_one({
            "id": cid, "name": f"Probe Ctx {cid[-1].upper()}",
            "type": "executive_personal", "status": "active",
            "owner_account_id": account_id, "created_at": now,
        })
        await db_conn.memberships.insert_one({
            "id": f"mem-{uuid.uuid4()}", "context_id": cid,
            "account_id": account_id, "status": "active",
            "role": "executive", "sub_role": "admin",
            "joined_at": now,
        })

    for sid, cid, intent in (
        (session_a, ctx_a, f"CTX-A-INTENT-{suffix}"),
        (session_b, ctx_b, f"CTX-B-INTENT-{suffix}"),
    ):
        await db_conn.solva_v2_sessions.insert_one({
            "id": sid, "account_id": account_id, "context_id": cid,
            "version": 2, "intent": intent, "status": "completed",
            "submodule": "drive", "started_at": now, "updated_at": now,
            "completed_at": now, "layer": "synthesis", "layer_index": 3,
        })

    yield {
        "email": email, "password": password, "account_id": account_id,
        "ctx_a": ctx_a, "ctx_b": ctx_b,
        "session_a_id": session_a, "session_b_id": session_b,
    }

    await db_conn.solva_v2_sessions.delete_many({"account_id": account_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.contexts.delete_many({"owner_account_id": account_id})
    await db_conn.accounts.delete_one({"id": account_id})


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_list_sessions_requires_context_id(client, two_context_user):
    """The picker MUST send `context_id`. Missing → 422."""
    token = await _login(client, two_context_user["email"], two_context_user["password"])
    r = await client.get(
        "/api/solva/v2/sessions",
        params={"status": "completed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, (
        f"expected 422 when context_id is omitted, got {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_list_sessions_rejects_non_member_context(client, two_context_user):
    """Caller passing a context_id they're not a member of → 403."""
    token = await _login(client, two_context_user["email"], two_context_user["password"])
    r = await client.get(
        "/api/solva/v2/sessions",
        params={"status": "completed", "context_id": "context-that-does-not-belong-to-caller"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, (
        f"expected 403 when caller is not a member of context_id, got {r.status_code}: {r.text}"
    )


@pytest.mark.asyncio
async def test_list_sessions_strictly_scopes_to_context(client, two_context_user):
    """The canonical leakage check: each context must see ONLY its own session."""
    token = await _login(client, two_context_user["email"], two_context_user["password"])

    # Context A
    ra = await client.get(
        "/api/solva/v2/sessions",
        params={"status": "completed", "context_id": two_context_user["ctx_a"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ra.status_code == 200, ra.text
    ids_a = {it["id"] for it in ra.json().get("items", [])}
    assert two_context_user["session_a_id"] in ids_a, "Context A's own session must surface"
    assert two_context_user["session_b_id"] not in ids_a, (
        "CROSS-CONTEXT LEAK: Context A's response included Context B's session"
    )

    # Context B
    rb = await client.get(
        "/api/solva/v2/sessions",
        params={"status": "completed", "context_id": two_context_user["ctx_b"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rb.status_code == 200, rb.text
    ids_b = {it["id"] for it in rb.json().get("items", [])}
    assert two_context_user["session_b_id"] in ids_b, "Context B's own session must surface"
    assert two_context_user["session_a_id"] not in ids_b, (
        "CROSS-CONTEXT LEAK: Context B's response included Context A's session"
    )


@pytest.mark.asyncio
async def test_list_sessions_excludes_orphan_context_id_rows(client, two_context_user, db_conn):
    """Legacy / orphan sessions with null `context_id` must NEVER leak.

    Defense-in-depth: even if old data lacks `context_id`, the strict
    `context_id` filter on the Mongo query means it cannot surface
    under any caller's request.
    """
    suffix = uuid.uuid4().hex[:8]
    orphan_id = f"orphan-{suffix}"
    await db_conn.solva_v2_sessions.insert_one({
        "id": orphan_id, "account_id": two_context_user["account_id"],
        "context_id": None,  # the orphan condition
        "version": 2, "intent": f"ORPHAN-{suffix}", "status": "completed",
        "submodule": "drive", "started_at": _iso(), "updated_at": _iso(),
        "completed_at": _iso(), "layer": "synthesis", "layer_index": 3,
    })
    try:
        token = await _login(client, two_context_user["email"], two_context_user["password"])
        for cid in (two_context_user["ctx_a"], two_context_user["ctx_b"]):
            r = await client.get(
                "/api/solva/v2/sessions",
                params={"status": "completed", "context_id": cid},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            ids = {it["id"] for it in r.json().get("items", [])}
            assert orphan_id not in ids, (
                "ORPHAN LEAK: a session with null `context_id` surfaced under a real context filter"
            )
    finally:
        await db_conn.solva_v2_sessions.delete_one({"id": orphan_id})
