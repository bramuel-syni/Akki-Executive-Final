"""
test_patch_2b1_kinds.py — Patch 2B.1 backend acceptance.

Verifies that briefings/aggregates accepts the three new kinds added
in Patch 2B.1 (`deck`, `report`, `briefing`) with well-formed empty
envelopes when no rows exist.

Auth uses the same dependency-override pattern as
test_work_studio_listing.py.
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
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": prefix.title(),
        "name": prefix.title(),
    }


@pytest.fixture(scope="module")
def env():
    return {
        "owner": _acc("p2b1-owner"),
        "ctx": f"ctx-p2b1-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.accounts.update_one(
        {"id": env["owner"]["id"]}, {"$set": env["owner"]}, upsert=True
    )
    await db.contexts.insert_one({
        "id": cid,
        "name": "P2B1 Co",
        "owner_account_id": env["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid,
            "account_id": env["owner"]["id"],
            "role": "owner",
            "status": "active",
        }},
        upsert=True,
    )


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_aggregates_kind_deck_returns_200_empty(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{env['ctx']}/briefings/aggregates",
            params={"kind": "deck", "page": 1, "page_size": 5},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "deck"
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total_pages"] == 1
    assert "counts_by_status" in body


@pytest.mark.asyncio
async def test_aggregates_kind_report_returns_200_empty(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{env['ctx']}/briefings/aggregates",
            params={"kind": "report", "page": 1, "page_size": 5},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "report"
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_aggregates_kind_briefing_returns_200_empty(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{env['ctx']}/briefings/aggregates",
            params={"kind": "briefing", "page": 1, "page_size": 5},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "briefing"
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_aggregates_unknown_kind_rejected(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{env['ctx']}/briefings/aggregates",
            params={"kind": "not_a_real_kind"},
        )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_aggregates_kind_deck_returns_row_after_create(env):
    """Direct DB insert into db.decks → row surfaces in kind=deck listing."""
    db = core_mod.db
    cid = env["ctx"]
    deck_id = f"deck-p2b1-{uuid.uuid4().hex[:8]}"
    await db.decks.insert_one({
        "id": deck_id,
        "context_id": cid,
        "title": "P2B1 Deck Smoke",
        "status": "draft",
        "slides": [{"id": "s1"}, {"id": "s2"}],
        "created_at": "2026-05-12T00:00:00+00:00",
        "updated_at": "2026-05-12T00:00:00+00:00",
    })
    try:
        _auth(env["owner"])
        async with _client() as c:
            r = await c.get(
                f"/api/contexts/{cid}/briefings/aggregates",
                params={"kind": "deck", "page": 1, "page_size": 5},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        names = [it["name"] for it in body["items"]]
        assert "P2B1 Deck Smoke" in names
        # Schema parity: row carries the same fields the cycle kinds use.
        row = next(it for it in body["items"] if it["name"] == "P2B1 Deck Smoke")
        for k in ("id", "kind", "name", "meeting_date", "document_count",
                  "contributor_count", "status", "created_at"):
            assert k in row, f"missing key {k!r}"
        assert row["kind"] == "deck"
        assert row["status"] == "draft"
        assert row["document_count"] == 2  # mirrors slide count
    finally:
        await db.decks.delete_one({"id": deck_id})
