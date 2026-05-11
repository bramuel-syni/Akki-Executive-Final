"""Team Catalogue v2 — CRUD + duplicate detection."""
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
    return {"owner": _acc("cato"), "ctx": f"ctx-{uuid.uuid4().hex[:10]}"}


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db["team_catalogue"].delete_many({"context_id": cid})
    await db.accounts.update_one({"id": env["owner"]["id"]}, {"$set": env["owner"]}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "Cat Co",
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


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_add_lists_and_returns_member(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx']}/team-catalogue",
            json={"name": "Anna", "email": "ANNA@example.com"},
        )
        assert r.status_code == 201, r.text
        assert r.json()["email"] == "ANNA@example.com"
        assert r.json()["email_lc"] == "anna@example.com"
        env["member_id"] = r.json()["id"]
        r2 = await c.get(f"/api/contexts/{env['ctx']}/team-catalogue")
        assert r2.status_code == 200
        assert any(m["id"] == env["member_id"] for m in r2.json()["members"])


@pytest.mark.asyncio
async def test_add_with_same_email_returns_existing(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx']}/team-catalogue",
            json={"name": "Anna Renamed", "email": "anna@example.com"},
        )
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == env["member_id"]  # same row
    assert body["name"] == "Anna Renamed"  # name updated


@pytest.mark.asyncio
async def test_patch_email_collision_returns_409(env):
    _auth(env["owner"])
    async with _client() as c:
        r0 = await c.post(
            f"/api/contexts/{env['ctx']}/team-catalogue",
            json={"name": "Bob", "email": "bob@example.com"},
        )
        bob_id = r0.json()["id"]
        # Try to rename Bob to anna@example.com (Anna's email)
        r = await c.patch(
            f"/api/contexts/{env['ctx']}/team-catalogue/{bob_id}",
            json={"email": "anna@example.com"},
        )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list_keeps_row(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.delete(f"/api/contexts/{env['ctx']}/team-catalogue/{env['member_id']}")
        assert r.status_code == 200
        r2 = await c.get(f"/api/contexts/{env['ctx']}/team-catalogue")
        assert not any(m["id"] == env["member_id"] for m in r2.json()["members"])
    # Row still present in DB
    row = await core_mod.db["team_catalogue"].find_one({"id": env["member_id"]}, {"_id": 0})
    assert row is not None
    assert row.get("deleted_at") is not None


@pytest.mark.asyncio
async def test_resurrect_via_re_add_after_soft_delete(env):
    """Re-adding the same email after a soft-delete should resurrect the row,
    not 409."""
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx']}/team-catalogue",
            json={"name": "Anna Returns", "email": "anna@example.com"},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == env["member_id"]  # same row
    assert body.get("deleted_at") is None
    assert body["name"] == "Anna Returns"


@pytest.mark.asyncio
async def test_check_team_duplicate_warning(env):
    """Adding a member already assigned to an agenda item → 200 with duplicate=True."""
    _auth(env["owner"])
    async with _client() as c:
        # Set up a cycle + agenda + team member
        cyc = (await c.post(
            f"/api/contexts/{env['ctx']}/cycles",
            json={"title": "Dup test"},
        )).json()
        cyc_id = cyc["id"]
        ag = await c.post(
            f"/api/contexts/{env['ctx']}/cycle/agenda?cycle_id={cyc_id}",
            json={"title": "Dup test", "items": [{"label": "Topic 1"}]},
        )
        item_id = ag.json()["items"][0]["id"]
        await c.post(
            f"/api/contexts/{env['ctx']}/cycle/team?cycle_id={cyc_id}",
            json={"name": "Cara", "email": "cara@example.com",
                  "contribution_description": "—", "owns_item_ids": [item_id]},
        )
        # Check duplicate for Cara on the same item
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{cyc_id}/agenda-items/{item_id}/check-team-duplicate",
            json={"name": "Cara", "email": "cara@example.com"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["duplicate"] is True
    assert "warning" in r.json()
