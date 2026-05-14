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


# ═════════════════════════════════════════════════════════════════════
# Task F — Monitor owner-role tabs (Chunk 6.5-REVISED, 2026-05-13)
#
# Backend changes under test:
#   - GET /contexts/{cid}/monitor/owner-roles            (NEW endpoint)
#   - GET /contexts/{cid}/monitor/{kind}                 (pipeline refactor)
# Both rely on a $lookup of `db.accounts` against `owner_account_id`
# to project `declared_role` as `owner_role` on each item.
# ═════════════════════════════════════════════════════════════════════
@pytest_asyncio.fixture
async def f_seeded(db_conn):
    """Seed an account + 2 contexts (active + foreign) + a small set of
    monitor_objectives and monitor_projects covering several declared
    roles, a null-owner item, and a canonical-but-uncommon role
    (Audit Committee) so the canonicalisation paths get exercised."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk65f-{suffix}@example.com"
    password = "Chunk65F2026!"
    aid = f"acc-c65f-{suffix}"
    cid = f"ctx-c65f-{suffix}"
    foreign_cid = f"ctx-c65f-foreign-{suffix}"
    now = _iso()

    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid, "email": email, "password_hash": hash_password(password),
        "name": "F probe", "role": "executive", "declared_role": "executive",
        "created_at": now, "default_context_id": cid,
        "session_version": 0, "verified": True,
    })
    for ctx_id in (cid, foreign_cid):
        await db_conn.contexts.insert_one({
            "id": ctx_id, "name": f"Ctx-{ctx_id[-4:]}", "type": "executive_personal",
            "status": "active", "owner_account_id": aid if ctx_id == cid else "someone-else",
            "created_at": now,
        })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": cid, "account_id": aid,
        "status": "active", "role": "executive", "sub_role": "admin",
        "joined_at": now,
    })

    # Seed owner accounts spanning a few canonical roles + one
    # non-canonical + one no-role. (`declared_role` in this codebase is
    # usually lowercase — verify the case-insensitive canonical match.)
    owner_accounts = [
        ("acc-ceo-" + suffix, "ceo"),
        ("acc-cfo-" + suffix, "CFO"),
        ("acc-coo-" + suffix, "Coo"),
        ("acc-audit-" + suffix, "Audit Committee"),
        ("acc-unknown-" + suffix, "investor_relations"),   # non-canonical → Other
        ("acc-noroll-" + suffix, None),                    # null declared_role → Other
    ]
    for oa_id, role in owner_accounts:
        await db_conn.accounts.insert_one({
            "id": oa_id, "email": f"{oa_id}@x.com", "password_hash": "x",
            "name": oa_id, "role": "executive",
            **({"declared_role": role} if role is not None else {}),
            "created_at": now, "session_version": 0, "verified": True,
        })

    # Seed objectives + projects in the active context.
    objectives = [
        ("obj-1",  "acc-ceo-" + suffix),
        ("obj-2",  "acc-ceo-" + suffix),
        ("obj-3",  "acc-cfo-" + suffix),
        ("obj-4",  "acc-coo-" + suffix),
        ("obj-5",  "acc-audit-" + suffix),
        ("obj-6",  "acc-unknown-" + suffix),  # Other
        ("obj-7",  "acc-noroll-" + suffix),   # Other (null declared_role)
        ("obj-8",  None),                     # Other (no owner_account_id)
    ]
    for oid, oa_id in objectives:
        await db_conn.objectives.insert_one({
            "id": f"{oid}-{suffix}", "context_id": cid,
            "title": f"Objective {oid}",
            "rag_status": "green", "score": 80, "trend": "flat", "source": "manual",
            "owner_account_id": oa_id, "created_at": now, "updated_at": now,
        })

    projects = [
        ("proj-1", "acc-ceo-" + suffix),
        ("proj-2", "acc-cfo-" + suffix),
    ]
    for pid, oa_id in projects:
        await db_conn.projects.insert_one({
            "id": f"{pid}-{suffix}", "context_id": cid,
            "title": f"Project {pid}",
            "rag_status": "amber", "score": 50, "trend": "flat", "source": "manual",
            "owner_account_id": oa_id, "created_at": now, "updated_at": now,
        })

    # One foreign-context objective so the cross-context isolation test
    # has something it can verify NOT to leak.
    await db_conn.objectives.insert_one({
        "id": f"obj-foreign-{suffix}", "context_id": foreign_cid,
        "title": "Foreign objective",
        "rag_status": "green", "score": 60, "trend": "flat", "source": "manual",
        "owner_account_id": "acc-ceo-" + suffix, "created_at": now, "updated_at": now,
    })

    yield {
        "email": email, "password": password,
        "account_id": aid, "context_id": cid, "foreign_context_id": foreign_cid,
        "suffix": suffix,
    }

    sx = suffix
    await db_conn.objectives.delete_many({"context_id": {"$in": [cid, foreign_cid]}})
    await db_conn.projects.delete_many({"context_id": cid})
    await db_conn.accounts.delete_many({"id": {"$regex": f"-{sx}$"}})
    await db_conn.memberships.delete_many({"account_id": aid})
    await db_conn.contexts.delete_many({"id": {"$in": [cid, foreign_cid]}})


@pytest.mark.asyncio
async def test_owner_roles_returns_canonical_with_counts(client, f_seeded):
    """The owner-roles endpoint returns canonical labels (case-corrected),
    in the locked product order, with item counts (objectives + projects
    summed). Items with null owner_account_id and non-canonical roles
    all bucket into 'Other'."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/owner-roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # 8 objectives + 2 projects = 10 total items in the active context.
    assert body["total"] == 10
    role_to_count = {row["role"]: row["count"] for row in body["roles"]}
    # CEO: 2 obj + 1 proj = 3 (canonicalised from lowercase 'ceo').
    assert role_to_count.get("CEO") == 3
    # CFO: 1 obj + 1 proj = 2.
    assert role_to_count.get("CFO") == 2
    # COO: 1 obj (case-insensitive match on 'Coo').
    assert role_to_count.get("COO") == 1
    # Audit Committee: 1 obj.
    assert role_to_count.get("Audit Committee") == 1
    # Other = 3 (investor_relations + null declared_role + null owner_account_id).
    assert role_to_count.get("Other") == 3
    # Canonical order preserved; "Other" emitted last.
    role_order = [row["role"] for row in body["roles"]]
    canonical_order = ["CEO", "CFO", "COO", "Audit Committee", "Other"]
    assert role_order == canonical_order


@pytest.mark.asyncio
async def test_owner_roles_strict_context_scope(client, f_seeded, db_conn):
    """Owner-role counts in context A must not include rows from
    context B."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/owner-roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    # The foreign-context objective is NOT counted; we know there's
    # 1 foreign objective, so the active-context total (10) wouldn't
    # include it (active total alone is 10; if it leaked it'd be 11).
    assert body["total"] == 10


@pytest.mark.asyncio
async def test_owner_roles_foreign_context_403(client, f_seeded):
    """Reading a foreign context returns 403."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['foreign_context_id']}/monitor/owner-roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_items_attaches_owner_role_via_lookup(client, f_seeded):
    """Each item returned by /monitor/{kind} carries an `owner_role`
    field projected from the linked account's `declared_role`.
    `null` for items whose owner_account_id is null OR the account
    has no declared_role."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/objective",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 50},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 8

    # Each item carries `owner_role`. The CEO-owned items carry "ceo"
    # (lowercase, as stored on the account row — the canonical
    # uppercasing is a frontend display concern).
    owner_roles = [it.get("owner_role") for it in items]
    assert "ceo" in owner_roles
    assert "CFO" in owner_roles or "cfo" in owner_roles
    # 3 items with null owner_role (non-canonical declared_role,
    # null declared_role, null owner_account_id).
    assert sum(1 for r in owner_roles if r is None) >= 1


@pytest.mark.asyncio
async def test_list_items_filters_by_owner_role_canonical(client, f_seeded):
    """`?owner_role=CEO` filters items to just those whose linked
    account has declared_role=CEO (case-insensitive)."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/objective",
        headers={"Authorization": f"Bearer {token}"},
        params={"owner_role": "CEO", "page_size": 50},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    # 2 CEO-owned objectives in the active context.
    assert len(items) == 2
    for it in items:
        assert (it.get("owner_role") or "").lower() == "ceo"


@pytest.mark.asyncio
async def test_list_items_filters_by_owner_role_other_sentinel(client, f_seeded):
    """`?owner_role=__other__` returns items whose owner_role is null OR
    not in the canonical list."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/objective",
        headers={"Authorization": f"Bearer {token}"},
        params={"owner_role": "__other__", "page_size": 50},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    # 3 "Other" objectives (investor_relations + null declared_role +
    # null owner_account_id).
    assert len(items) == 3


@pytest.mark.asyncio
async def test_list_items_null_owner_account_id_yields_null_role(client, f_seeded):
    """An objective with `owner_account_id=null` surfaces with
    `owner_role=null` (no $lookup match)."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/objective",
        headers={"Authorization": f"Bearer {token}"},
        params={"owner_role": "__other__", "page_size": 50},
    )
    assert r.status_code == 200
    # At least one of the "Other" objectives carries a null owner_role
    # (the one with owner_account_id=None — obj-8).
    others = r.json()["items"]
    assert any(it.get("owner_role") is None for it in others)


@pytest.mark.asyncio
async def test_list_items_intersect_owner_role_and_status(client, f_seeded, db_conn):
    """Owner-role filter combines cleanly with the RAG status filter
    (orthogonal filters intersect)."""
    token = await _login(client, f_seeded["email"], f_seeded["password"])
    # Set one of the CEO objectives to red so we can verify the
    # intersection narrows the result.
    suffix = f_seeded["suffix"]
    await db_conn.objectives.update_one(
        {"id": f"obj-1-{suffix}"},
        {"$set": {"rag_status": "red"}},
    )
    r = await client.get(
        f"/api/contexts/{f_seeded['context_id']}/monitor/objective",
        headers={"Authorization": f"Bearer {token}"},
        params={"owner_role": "CEO", "status": "red", "page_size": 50},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    # Exactly 1 item — the now-red CEO objective.
    assert len(items) == 1
    assert items[0]["rag_status"] == "red"
    assert (items[0].get("owner_role") or "").lower() == "ceo"
