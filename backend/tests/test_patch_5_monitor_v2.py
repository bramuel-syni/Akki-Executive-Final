"""
test_patch_5_monitor_v2.py — Patch 5 Monitor v2 backend acceptance.
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
        "owner": _acc("p5-mon"),
        "ctx": f"ctx-p5-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.objectives.delete_many({"context_id": cid})
    await db.projects.delete_many({"context_id": cid})
    await db.accounts.update_one({"id": env["owner"]["id"]}, {"$set": env["owner"]}, upsert=True)
    await db.contexts.insert_one({"id": cid, "name": "P5 Co", "owner_account_id": env["owner"]["id"], "type": "executive_enterprise"})
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
async def test_objectives_crud(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        # CREATE
        r = await c.post(f"/api/contexts/{cid}/monitor/objective", json={
            "title": "Q4 ROI lift", "rag_status": "amber", "score": 62,
        })
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        # GET
        r = await c.get(f"/api/contexts/{cid}/monitor/objective/{rid}")
        assert r.status_code == 200, r.text
        # LIST
        r = await c.get(f"/api/contexts/{cid}/monitor/objective")
        assert r.status_code == 200, r.text
        assert r.json()["total"] >= 1
        # PATCH
        r = await c.patch(f"/api/contexts/{cid}/monitor/objective/{rid}", json={"score": 75})
        assert r.status_code == 200, r.text
        assert r.json()["score"] == 75
        # SOFT DELETE
        r = await c.delete(f"/api/contexts/{cid}/monitor/objective/{rid}")
        assert r.status_code == 200, r.text
        # LIST again — soft-deleted item must NOT appear
        r = await c.get(f"/api/contexts/{cid}/monitor/objective")
        assert all(it["id"] != rid for it in r.json()["items"])


@pytest.mark.asyncio
async def test_projects_crud(env):
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        r = await c.post(f"/api/contexts/{cid}/monitor/project", json={
            "title": "Implement new CRM",
            "rag_status": "green",
            "score": 88,
            "trend": "up",
        })
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        r = await c.get(f"/api/contexts/{cid}/monitor/project/{rid}")
        assert r.status_code == 200
        # RAG filter must respect amber/red/green/all
        r = await c.get(f"/api/contexts/{cid}/monitor/project", params={"status": "green"})
        assert r.status_code == 200
        assert any(it["id"] == rid for it in r.json()["items"])


@pytest.mark.asyncio
async def test_auto_suggest_endpoints(env):
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/monitor/auto-suggest-objectives")
        assert r.status_code == 200, r.text
        assert "items" in r.json()
        r = await c.get(f"/api/contexts/{cid}/monitor/auto-suggest-projects")
        assert r.status_code == 200, r.text
        assert "items" in r.json()
