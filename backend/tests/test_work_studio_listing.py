"""Work Studio listing — search + status filter behavior tests.

Cycle Manager Feel pass (Patch 1 of 4): the existing
`GET /api/contexts/{cid}/briefings/aggregates` endpoint now accepts
ListingShell-shaped query params (q / status / sort / page / page_size)
and returns counts_by_status + total + pagination metadata.
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


def _acc(prefix):
    uid = uuid.uuid4().hex[:10]
    return {"id": f"{prefix}-{uid}", "email": f"{prefix}-{uid}@example.com",
            "display_name": prefix.title(), "name": prefix.title()}


@pytest.fixture(scope="module")
def env():
    return {
        "owner": _acc("wsl-owner"),
        "ctx": f"ctx-wsl-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.boardpacks.delete_many({"context_id": cid})
    await db.documents.delete_many({"context_id": cid})
    await db.work_studio_briefs.delete_many({"context_id": cid})
    # Belt-and-braces — the brief ids below are fixed test values, so
    # leftover rows from a prior run could pollute the lifecycle join.
    await db.work_studio_briefs.delete_many({"id": {"$in": ["brf_c", "brf_s"]}})
    await db.boardpacks.delete_many({"id": {"$in": ["bp_draft", "bp_in_progress", "bp_compiled", "bp_shipped"]}})
    await db.accounts.update_one({"id": env["owner"]["id"]}, {"$set": env["owner"]}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "WSL Co",
        "owner_account_id": env["owner"]["id"], "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid, "account_id": env["owner"]["id"],
            "role": "executive", "sub_role": "admin", "status": "active",
        }},
        upsert=True,
    )

    # Seed four boardpacks in four lifecycle statuses:
    #  - bp_draft       (no docs, status=draft)        → "draft"
    #  - bp_in_progress (1 doc, no brief_id)           → "in_progress"
    #  - bp_compiled    (has brief_id, no shipped)     → "compiled"
    #  - bp_shipped     (has brief_id, brief shipped)  → "shipped"
    base = {
        "context_id": cid, "account_id": env["owner"]["id"],
        "cycle_label": "Q1 2026", "meeting_date": "2026-02-15T00:00:00Z",
    }
    await db.boardpacks.insert_many([
        {**base, "id": "bp_draft", "title": "Alpha Draft Pack",
         "document_ids": [], "status": "draft",
         "created_at": "2026-02-01T00:00:00Z"},
        {**base, "id": "bp_in_progress", "title": "Beta In-Progress Pack",
         "document_ids": ["doc1"], "status": "active",
         "created_at": "2026-02-05T00:00:00Z"},
        {**base, "id": "bp_compiled", "title": "Gamma Compiled Pack",
         "document_ids": ["doc2"], "status": "active", "brief_id": "brf_c",
         "created_at": "2026-02-10T00:00:00Z"},
        {**base, "id": "bp_shipped", "title": "Delta Shipped Pack",
         "document_ids": ["doc3"], "status": "active", "brief_id": "brf_s",
         "created_at": "2026-02-12T00:00:00Z"},
    ])
    # Brief rows so the lifecycle derivation can join.
    await db.work_studio_briefs.insert_many([
        {"id": "brf_c", "context_id": cid, "account_id": env["owner"]["id"],
         "source_type": "test_wsl", "source_id": "bp_compiled",
         "title": "Gamma", "active_revision_id": "r1", "revision_count": 1,
         "board_status": "draft", "created_at": "2026-02-10T00:00:00Z",
         "updated_at": "2026-02-10T00:00:00Z"},
        {"id": "brf_s", "context_id": cid, "account_id": env["owner"]["id"],
         "source_type": "test_wsl", "source_id": "bp_shipped",
         "title": "Delta", "active_revision_id": "r2", "revision_count": 1,
         "board_status": "shipped", "created_at": "2026-02-12T00:00:00Z",
         "updated_at": "2026-02-12T00:00:00Z"},
    ])


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


URL = lambda cid: f"/api/contexts/{cid}/briefings/aggregates?kind=cycle_board_pack"


@pytest.mark.asyncio
async def test_listing_returns_pagination_envelope(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(URL(env["ctx"]))
    assert r.status_code == 200, r.text
    b = r.json()
    # New envelope keys present
    for k in ("items", "total", "page", "page_size", "total_pages",
              "counts_by_status", "q", "status", "sort"):
        assert k in b, f"missing key {k!r} in response"
    # Counts by status reflect the four seeded rows.
    cbs = b["counts_by_status"]
    assert cbs["all"] >= 4
    assert cbs["draft"] >= 1
    assert cbs["in_progress"] >= 1
    assert cbs["compiled"] >= 1
    assert cbs["shipped"] >= 1


@pytest.mark.asyncio
async def test_listing_search_filters_by_name(env):
    """Test 1 — search behavior. `q=delta` returns only the row whose
    name contains 'delta' (case-insensitive)."""
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"{URL(env['ctx'])}&q=delta")
    assert r.status_code == 200, r.text
    b = r.json()
    names = [it["name"] for it in b["items"]]
    assert all("delta" in n.lower() for n in names), names
    assert any("Delta Shipped Pack" == n for n in names)
    # Search doesn't change the counts_by_status (they're pre-filter).
    assert b["counts_by_status"]["all"] >= 4


@pytest.mark.asyncio
async def test_listing_status_filter(env):
    """Test 2 — status filter behavior. Each status filter returns
    only the rows in that lifecycle bucket."""
    _auth(env["owner"])
    async with _client() as c:
        for st, expected_substr in (
            ("draft", "Draft"),
            ("in_progress", "In-Progress"),
            ("compiled", "Compiled"),
            ("shipped", "Shipped"),
        ):
            r = await c.get(f"{URL(env['ctx'])}&status={st}")
            assert r.status_code == 200, r.text
            b = r.json()
            assert b["status"] == st
            statuses = {it["status"] for it in b["items"]}
            assert statuses == {st}, f"status={st} got mixed: {statuses}"
            # The seeded row name carries the substring.
            assert any(expected_substr.lower() in it["name"].lower() for it in b["items"])


@pytest.mark.asyncio
async def test_listing_sort_alpha(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"{URL(env['ctx'])}&sort=alpha&page_size=20")
    names = [it["name"] for it in r.json()["items"]]
    assert names == sorted(names, key=str.lower)


@pytest.mark.asyncio
async def test_listing_pagination(env):
    _auth(env["owner"])
    async with _client() as c:
        # Page 1 of 2 with page_size=2 over 4 rows.
        r1 = await c.get(f"{URL(env['ctx'])}&page=1&page_size=2&sort=alpha")
        r2 = await c.get(f"{URL(env['ctx'])}&page=2&page_size=2&sort=alpha")
    b1, b2 = r1.json(), r2.json()
    assert b1["page"] == 1 and b2["page"] == 2
    assert len(b1["items"]) == 2 and len(b2["items"]) == 2
    assert b1["total"] >= 4 and b2["total"] == b1["total"]
    # Items are disjoint.
    id1 = {it["id"] for it in b1["items"]}
    id2 = {it["id"] for it in b2["items"]}
    assert id1.isdisjoint(id2)


@pytest.mark.asyncio
async def test_listing_rejects_invalid_status(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"{URL(env['ctx'])}&status=bogus")
    assert r.status_code == 422, r.text
