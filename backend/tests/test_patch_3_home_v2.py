"""
test_patch_3_home_v2.py — Patch 3 Home v2 backend acceptance.
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
        "owner": _acc("p3-home"),
        "ctx": f"ctx-p3-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.accounts.update_one({"id": env["owner"]["id"]}, {"$set": env["owner"]}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "P3 Co", "owner_account_id": env["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid, "account_id": env["owner"]["id"],
            "role": "owner", "status": "active",
        }},
        upsert=True,
    )


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_home_insights_returns_all_7_keys(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{env['ctx']}/home/insights")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "insights" in body
    keys = set(body["insights"].keys())
    expected = {
        "compile_ready", "pulse_critical", "solva_waiting",
        "signoffs_needed", "cycles_closing", "new_documents",
        "open_questions",
    }
    assert keys == expected
    for k, v in body["insights"].items():
        assert "count" in v
        assert isinstance(v["count"], int)
        assert v["count"] >= 0


@pytest.mark.asyncio
async def test_home_insights_records_visit_and_returns_previous_visit(env):
    _auth(env["owner"])
    async with _client() as c:
        r1 = await c.get(f"/api/contexts/{env['ctx']}/home/insights")
        ts1 = r1.json()["previous_visit_at"]
        r2 = await c.get(f"/api/contexts/{env['ctx']}/home/insights")
    # On the second call, previous_visit_at must now be populated.
    assert r2.json()["previous_visit_at"] is not None


@pytest.mark.asyncio
async def test_whats_new_returns_envelope(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{env['ctx']}/home/whats-new")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_recent_views_round_trip(env):
    _auth(env["owner"])
    async with _client() as c:
        post = await c.post("/api/me/recent-views", json={
            "surface_path": "/app/work-studio",
            "label": "Work Studio",
            "context_id": env["ctx"],
        })
        assert post.status_code == 200, post.text
        get = await c.get("/api/me/recent-views", params={"limit": 5})
    assert get.status_code == 200, get.text
    body = get.json()
    paths = [it["surface_path"] for it in body["items"]]
    assert "/app/work-studio" in paths
