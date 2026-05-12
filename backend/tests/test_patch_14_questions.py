"""
test_patch_14_questions.py — Patch 14 backend acceptance.
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


@pytest.fixture
async def env():
    e = {
        "owner": _acc("p14-q-own"),
        "ned":   _acc("p14-q-ned"),
        "ctx":   f"ctx-p14-{uuid.uuid4().hex[:10]}",
        "cycle": f"cy-p14-{uuid.uuid4().hex[:10]}",
    }
    db = core_mod.db
    await db.contexts.delete_many({"id": e["ctx"]})
    await db.memberships.delete_many({"context_id": e["ctx"]})
    await db.cycle_questions.delete_many({"context_id": e["ctx"]})
    for k in ("owner", "ned"):
        await db.accounts.update_one({"id": e[k]["id"]}, {"$set": e[k]}, upsert=True)
    await db.contexts.insert_one({
        "id": e["ctx"], "name": "P14 Co", "owner_account_id": e["owner"]["id"],
        "type": "executive_enterprise",
    })
    for k, role in (("owner", "owner"), ("ned", "ned")):
        await db.memberships.update_one(
            {"context_id": e["ctx"], "account_id": e[k]["id"]},
            {"$set": {
                "context_id": e["ctx"], "account_id": e[k]["id"],
                "role": role, "status": "active",
            }},
            upsert=True,
        )
    await db.cycles.insert_one({
        "id": e["cycle"], "context_id": e["ctx"], "status": "active",
        "title": "P14 cycle",
    })
    yield e


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_raise_then_list_by_assignee_then_answer_flips_status(env):
    _auth(env["owner"])
    async with _client() as c:
        # 1. Raise — assigned to the NED
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{env['cycle']}/questions",
            json={
                "text": "How does the AI shield handle multi-tenant signals?",
                "assignee_account_id": env["ned"]["id"],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        qid = body["id"]
        assert body["status"] == "open"
        assert body["assignee_account_id"] == env["ned"]["id"]
        assert any(h["kind"] == "raised" for h in body["history"])

    # 2. List as the NED — should see the question
    _auth(env["ned"])
    async with _client() as c:
        r = await c.get("/api/me/questions", params={"status": "open"})
        assert r.status_code == 200, r.text
        ids = [it["id"] for it in r.json()["items"]]
        assert qid in ids

        # 3. Answer — flips status to answered
        r = await c.post(
            f"/api/contexts/{env['ctx']}/questions/{qid}/answer",
            json={"text": "Synisense Shield is per-context. No cross-tenant carry."},
        )
        assert r.status_code == 200, r.text
        answered = r.json()
        assert answered["status"] == "answered"
        assert answered["answer_text"].startswith("Synisense")
        assert answered["answered_by_account_id"] == env["ned"]["id"]

        # 4. List answered=true now includes it; list open=true excludes it
        ropen = await c.get("/api/me/questions", params={"status": "open"})
        rclosed = await c.get("/api/me/questions", params={"status": "answered"})
    open_ids = [it["id"] for it in ropen.json()["items"]]
    closed_ids = [it["id"] for it in rclosed.json()["items"]]
    assert qid not in open_ids
    assert qid in closed_ids


@pytest.mark.asyncio
async def test_list_by_cycle_scoped(env):
    _auth(env["owner"])
    async with _client() as c:
        await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{env['cycle']}/questions",
            json={"text": "Scoped one", "assignee_account_id": env["ned"]["id"]},
        )
        r = await c.get(
            f"/api/contexts/{env['ctx']}/cycles/{env['cycle']}/questions",
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_detail_404_when_cross_context(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{env['cycle']}/questions",
            json={"text": "Cross-context guard", "assignee_account_id": env["ned"]["id"]},
        )
        qid = r.json()["id"]
        # Same context — should resolve
        r2 = await c.get(f"/api/contexts/{env['ctx']}/questions/{qid}")
        assert r2.status_code == 200
        # Different context id — must 404
        r3 = await c.get(f"/api/contexts/some-other-ctx/questions/{qid}")
    assert r3.status_code == 404
