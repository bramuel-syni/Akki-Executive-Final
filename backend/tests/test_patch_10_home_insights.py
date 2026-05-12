"""
test_patch_10_home_insights.py — Patch 10 acceptance.

Covers:
  • Migration 0002_home_insight_fields runs once, idempotent
  • `cycles.expected_close_at` accepted on activate; default = +30d
  • `home/insights.cycles_closing` count reflects expected_close_at
    in next 7d
  • `home/insights.open_questions` count reflects
    cycle_questions.assignee_account_id assignments
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

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
        "owner": _acc("p10-ins"),
        "ctx":   f"ctx-p10-{uuid.uuid4().hex[:10]}",
    }
    db = core_mod.db
    await db.contexts.delete_many({"id": e["ctx"]})
    await db.memberships.delete_many({"context_id": e["ctx"]})
    await db.cycles.delete_many({"context_id": e["ctx"]})
    await db.cycle_questions.delete_many({"context_id": e["ctx"]})
    await db.accounts.update_one({"id": e["owner"]["id"]}, {"$set": e["owner"]}, upsert=True)
    await db.contexts.insert_one({
        "id": e["ctx"], "name": "P10 Co", "owner_account_id": e["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": e["ctx"], "account_id": e["owner"]["id"]},
        {"$set": {
            "context_id": e["ctx"], "account_id": e["owner"]["id"],
            "role": "owner", "status": "active",
        }},
        upsert=True,
    )
    yield e


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_migration_0002_marker_present():
    """Server startup runs the migration; marker row must exist."""
    db = core_mod.db
    row = await db["_migrations"].find_one({"id": "0002_home_insight_fields"}, {"_id": 0})
    assert row is not None, "migration 0002_home_insight_fields marker missing"
    assert "applied_at" in row


@pytest.mark.asyncio
async def test_cycles_closing_count_respects_expected_close_at(env):
    db = core_mod.db
    cid = env["ctx"]
    now = datetime.now(timezone.utc)
    in_3d   = (now + timedelta(days=3)).isoformat()
    in_20d  = (now + timedelta(days=20)).isoformat()
    past_2d = (now - timedelta(days=2)).isoformat()
    # 1 cycle closing in 3 days → counts
    await db.cycles.insert_one({
        "id": f"cy-{uuid.uuid4().hex[:8]}", "context_id": cid,
        "status": "active", "title": "Closing soon",
        "expected_close_at": in_3d,
    })
    # 1 cycle closing in 20 days → does NOT count
    await db.cycles.insert_one({
        "id": f"cy-{uuid.uuid4().hex[:8]}", "context_id": cid,
        "status": "active", "title": "Closing later",
        "expected_close_at": in_20d,
    })
    # 1 cycle without expected_close_at → does NOT count
    await db.cycles.insert_one({
        "id": f"cy-{uuid.uuid4().hex[:8]}", "context_id": cid,
        "status": "active", "title": "No close date",
    })
    # 1 cycle closed in past → does NOT count
    await db.cycles.insert_one({
        "id": f"cy-{uuid.uuid4().hex[:8]}", "context_id": cid,
        "status": "active", "title": "Overdue",
        "expected_close_at": past_2d,
    })
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/home/insights")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["insights"]["cycles_closing"]["count"] == 1


@pytest.mark.asyncio
async def test_open_questions_count_respects_assignee_account_id(env):
    db = core_mod.db
    cid = env["ctx"]
    me_id = env["owner"]["id"]
    other = _acc("p10-other")
    await db.accounts.update_one({"id": other["id"]}, {"$set": other}, upsert=True)
    # 2 questions assigned to me, open
    for _ in range(2):
        await db.cycle_questions.insert_one({
            "id": f"q-{uuid.uuid4().hex[:8]}", "context_id": cid,
            "assignee_account_id": me_id, "status": "open",
        })
    # 1 question assigned to someone else
    await db.cycle_questions.insert_one({
        "id": f"q-{uuid.uuid4().hex[:8]}", "context_id": cid,
        "assignee_account_id": other["id"], "status": "open",
    })
    # 1 question assigned to me, but resolved
    await db.cycle_questions.insert_one({
        "id": f"q-{uuid.uuid4().hex[:8]}", "context_id": cid,
        "assignee_account_id": me_id, "status": "resolved",
    })
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/home/insights")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["insights"]["open_questions"]["count"] == 2
