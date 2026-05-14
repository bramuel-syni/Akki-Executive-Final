"""Chunk 6.5-REVISED — backend regression tests for new endpoints.

This chunk's frontend rewrites (Tasks A, B, C, E) are exercised by
render-smoke. Only **Task D** introduces a new backend endpoint:
`GET /api/contexts/{cid}/document-journal/recent`. These tests cover
its contract.

Coverage:
1. Returns up to `limit` items (default 5), newest-first.
2. Caps `limit` at 25.
3. Floors `limit` at 1 (negative / zero → 1).
4. Scoped strictly by `context_id` (no cross-context leakage).
5. Empty workspace returns `[]` with `count=0`.
6. Response excludes `_id` (MongoDB ObjectId is never serialised).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


def _iso(offset_minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_conn():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest_asyncio.fixture
async def seeded(db_conn):
    """Seed 1 account + 2 contexts (active + foreign) and N=8 documents
    in the active context, 2 in the foreign one. Newest-first ordering
    is verifiable from the `created_at` offsets."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk65-doc-recent-{suffix}@example.com"
    password = "Chunk65DocRecent2026!"
    aid = f"acc-c65d-{suffix}"
    cid = f"ctx-c65d-{suffix}"
    foreign_cid = f"ctx-c65d-foreign-{suffix}"
    now = _iso()

    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid, "email": email, "password_hash": hash_password(password),
        "name": "Chunk 6.5-rev probe", "role": "executive", "created_at": now,
        "default_context_id": cid, "session_version": 0, "verified": True,
    })
    for ctx_id in (cid, foreign_cid):
        await db_conn.contexts.insert_one({
            "id": ctx_id, "name": f"Ctx-{ctx_id[-4:]}", "type": "executive_personal",
            "status": "active", "owner_account_id": aid if ctx_id == cid else "someone-else",
            "created_at": now,
        })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": cid, "account_id": aid,
        "status": "active", "role": "executive", "sub_role": "admin", "joined_at": now,
    })

    # Active context — 8 documents, staggered timestamps so newest-first
    # ordering is observable.
    active_ids: list[str] = []
    for idx in range(8):
        d_id = f"doc-c65d-{idx:02d}-{uuid.uuid4().hex[:6]}"
        active_ids.append(d_id)
        await db_conn.documents.insert_one({
            "id": d_id, "context_id": cid, "account_id": aid,
            "name": f"Active doc {idx:02d}",
            "doc_kind": "uploaded" if idx % 2 == 0 else "generated",
            "doc_type": "pdf",
            "status": "ready", "size": 1024,
            "mime": "application/pdf",
            "preview": f"Preview for doc {idx:02d}",
            "created_at": _iso(offset_minutes=-idx),   # smaller idx = newer
            "updated_at": _iso(offset_minutes=-idx),
        })

    # Foreign context — 2 documents. We verify they DO NOT leak.
    for idx in range(2):
        await db_conn.documents.insert_one({
            "id": f"doc-foreign-{idx}-{uuid.uuid4().hex[:6]}",
            "context_id": foreign_cid, "account_id": "someone-else",
            "name": f"Foreign doc {idx}", "doc_kind": "uploaded", "doc_type": "pdf",
            "status": "ready", "size": 1024, "mime": "application/pdf",
            "preview": "", "created_at": now, "updated_at": now,
        })

    yield {
        "email": email, "password": password,
        "account_id": aid, "context_id": cid, "foreign_context_id": foreign_cid,
        "active_doc_ids_newest_first": active_ids,
    }

    await db_conn.documents.delete_many({"context_id": {"$in": [cid, foreign_cid]}})
    await db_conn.memberships.delete_many({"account_id": aid})
    await db_conn.contexts.delete_many({"id": {"$in": [cid, foreign_cid]}})
    await db_conn.accounts.delete_one({"id": aid})


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ───────────────────────────────────────────────────────────────────────
# Task D — GET /document-journal/recent
# ───────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_recent_default_limit_returns_5_newest(client, seeded):
    """Default `limit=5` → 5 items, newest-first."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 5
    assert body["limit"] == 5
    assert len(body["items"]) == 5
    # Newest-first — the 5 most-recently-created (lowest offset) doc ids.
    returned_ids = [it["id"] for it in body["items"]]
    expected = seeded["active_doc_ids_newest_first"][:5]
    assert returned_ids == expected


@pytest.mark.asyncio
async def test_recent_limit_param_honoured(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert body["limit"] == 3


@pytest.mark.asyncio
async def test_recent_limit_capped_at_25(client, seeded):
    """An over-large `limit` is silently clamped to 25 (defensive)."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 200},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 25
    # The active context only has 8 documents, so we get 8 back.
    assert body["count"] == 8


@pytest.mark.asyncio
async def test_recent_limit_floored_at_1(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 1
    assert body["count"] == 1


@pytest.mark.asyncio
async def test_recent_strictly_scoped_by_context(client, seeded, db_conn):
    """Defence-in-depth — must NOT return foreign-context docs."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 25},
    )
    assert r.status_code == 200
    returned_ids = {it["id"] for it in r.json()["items"]}
    # None of the foreign-context doc ids may appear.
    foreign = await db_conn.documents.find(
        {"context_id": seeded["foreign_context_id"]}, {"_id": 0, "id": 1},
    ).to_list(10)
    foreign_ids = {f["id"] for f in foreign}
    assert returned_ids.isdisjoint(foreign_ids), (
        f"Cross-context leakage: {returned_ids & foreign_ids}"
    )


@pytest.mark.asyncio
async def test_recent_empty_workspace_returns_empty(client, seeded, db_conn):
    """An empty workspace returns count=0 + items=[]."""
    token = await _login(client, seeded["email"], seeded["password"])
    # Wipe the active context's docs.
    await db_conn.documents.delete_many({"context_id": seeded["context_id"]})
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_recent_response_excludes_mongo_objectid(client, seeded):
    """MongoDB ObjectIds are never serialised — none of the items
    should carry `_id`."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    for it in r.json()["items"]:
        assert "_id" not in it


@pytest.mark.asyncio
async def test_recent_foreign_context_returns_403(client, seeded):
    """Trying to read a context the user isn't a member of returns 403."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['foreign_context_id']}/document-journal/recent",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
