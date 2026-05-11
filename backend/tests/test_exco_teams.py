"""Tests for ExCo teams router (HOME sprint, 2026-05-12).

Coverage matches the sprint brief acceptance:
  - Owner can create ExCo with valid members
  - Non-admin member cannot create ExCo (403)
  - Adding a member who isn't in the context is rejected (400)
  - Cross-context request to another context's ExCo team returns 404 / 403
  - Audit row written on every action

Pattern: async tests using httpx.AsyncClient + ASGITransport so Motor
and the test runner share an event loop. Auth is monkey-patched via
FastAPI dependency_overrides.
"""
from __future__ import annotations

import asyncio
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


def _new_acc(suffix: str) -> dict:
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"acc-{suffix}-{uid}",
        "email": f"{suffix}-{uid}@example.com",
        "display_name": f"{suffix.title()} Account",
    }


@pytest.fixture(scope="module")
def env():
    return {
        "ctx_id": f"ctx-{uuid.uuid4().hex[:10]}",
        "owner": _new_acc("owner"),
        "admin": _new_acc("admin"),
        "member": _new_acc("member"),
        "outsider": _new_acc("outside"),
        "team_id": None,
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx_id"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.exco_teams.delete_many({"context_id": cid})
    await db.audit_log.delete_many({"context_id": cid})
    for a in (env["owner"], env["admin"], env["member"], env["outsider"]):
        await db.accounts.update_one({"id": a["id"]}, {"$set": a}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "Test Ctx",
        "owner_account_id": env["owner"]["id"],
        "type": "executive_personal",
    })
    for acc, role, sub in [
        (env["owner"], "executive", "admin"),
        (env["admin"], "executive", "admin"),
        (env["member"], "executive", None),
    ]:
        await db.memberships.update_one(
            {"context_id": cid, "account_id": acc["id"]},
            {"$set": {
                "context_id": cid, "account_id": acc["id"],
                "role": role, "sub_role": sub, "status": "active",
            }},
            upsert=True,
        )


def _override_auth(account: dict):
    async def _override():
        return account
    app.dependency_overrides[core_mod.get_current_account] = _override


def _client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ─── Tests ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_owner_can_create_exco_team(env):
    await _seed(env)
    _override_auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_id']}/exco-teams",
            json={
                "name": "Senior Leadership Team",
                "description": "Weekly leadership",
                "member_account_ids": [env["member"]["id"], env["admin"]["id"]],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == "Senior Leadership Team"
        assert body["status"] == "active"
        assert set(body["member_account_ids"]) == {env["member"]["id"], env["admin"]["id"]}
        assert body["my_role"] == "creator"
    env["team_id"] = body["id"]
    aud = await core_mod.db.audit_log.find_one(
        {"context_id": env["ctx_id"], "action": "exco.created", "resource_id": body["id"]},
    )
    assert aud is not None


@pytest.mark.asyncio
async def test_non_admin_cannot_create_exco_team(env):
    _override_auth(env["member"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_id']}/exco-teams",
            json={"name": "Unauthorised", "member_account_ids": [env["admin"]["id"]]},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_adding_member_not_in_context_is_rejected(env):
    _override_auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_id']}/exco-teams",
            json={"name": "With Outsider", "member_account_ids": [env["outsider"]["id"]]},
        )
        assert r.status_code == 400, r.text
        if env["team_id"]:
            r2 = await cli.post(
                f"/api/contexts/{env['ctx_id']}/exco-teams/{env['team_id']}/members",
                json={"account_id": env["outsider"]["id"]},
            )
            assert r2.status_code == 400


@pytest.mark.asyncio
async def test_cross_context_team_returns_404_or_403(env):
    """Asking for a team that belongs to a DIFFERENT context:
       - via the foreign context where caller is not a member → 403
       - via caller's own context where the team doesn't exist → 404
    """
    other_cid = f"ctx-{uuid.uuid4().hex[:10]}"
    other_acc = env["outsider"]
    await core_mod.db.contexts.insert_one({
        "id": other_cid, "name": "Other Ctx",
        "owner_account_id": other_acc["id"], "type": "executive_personal",
    })
    await core_mod.db.memberships.insert_one({
        "context_id": other_cid, "account_id": other_acc["id"],
        "role": "executive", "sub_role": "admin", "status": "active",
    })
    other_team_id = f"team-{uuid.uuid4().hex[:10]}"
    await core_mod.db.exco_teams.insert_one({
        "id": other_team_id, "context_id": other_cid,
        "name": "Other Team", "member_account_ids": [other_acc["id"]],
        "created_by": other_acc["id"], "status": "active",
        "created_at": "2026-05-12T00:00:00", "updated_at": "2026-05-12T00:00:00",
    })
    _override_auth(env["owner"])
    async with _client() as cli:
        r = await cli.get(f"/api/contexts/{other_cid}/exco-teams/{other_team_id}")
        assert r.status_code == 403, r.text
        r2 = await cli.get(f"/api/contexts/{env['ctx_id']}/exco-teams/{other_team_id}")
        assert r2.status_code == 404, r2.text
    await core_mod.db.exco_teams.delete_many({"context_id": other_cid})
    await core_mod.db.memberships.delete_many({"context_id": other_cid})
    await core_mod.db.contexts.delete_many({"id": other_cid})


@pytest.mark.asyncio
async def test_add_remove_member_writes_audit(env):
    assert env["team_id"], "ordering: create test must run first"
    _override_auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_id']}/exco-teams/{env['team_id']}/members",
            json={"account_id": env["owner"]["id"]},
        )
        assert r.status_code == 200, r.text
        assert env["owner"]["id"] in r.json()["member_account_ids"]
    add_aud = await core_mod.db.audit_log.find_one(
        {"action": "exco.member_added", "resource_id": env["team_id"]},
        sort=[("created_at", -1)],
    )
    assert add_aud is not None and add_aud["metadata"]["member"] == env["owner"]["id"]
    async with _client() as cli:
        r2 = await cli.delete(
            f"/api/contexts/{env['ctx_id']}/exco-teams/{env['team_id']}/members/{env['member']['id']}",
        )
        assert r2.status_code == 200, r2.text
        assert env["member"]["id"] not in r2.json()["member_account_ids"]
    rem_aud = await core_mod.db.audit_log.find_one(
        {"action": "exco.member_removed", "resource_id": env["team_id"]},
        sort=[("created_at", -1)],
    )
    assert rem_aud is not None


@pytest.mark.asyncio
async def test_archive_writes_audit_and_is_soft_delete(env):
    assert env["team_id"]
    _override_auth(env["owner"])
    async with _client() as cli:
        r = await cli.delete(f"/api/contexts/{env['ctx_id']}/exco-teams/{env['team_id']}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "archived"
    aud = await core_mod.db.audit_log.find_one(
        {"action": "exco.archived", "resource_id": env["team_id"]},
    )
    assert aud is not None
    surviving = await core_mod.db.exco_teams.find_one({"id": env["team_id"]})
    assert surviving is not None
    assert surviving["status"] == "archived"
    # Cleanup at module-end (best effort)
    await core_mod.db.exco_teams.delete_many({"context_id": env["ctx_id"]})
    await core_mod.db.audit_log.delete_many({"context_id": env["ctx_id"]})
    await core_mod.db.memberships.delete_many({"context_id": env["ctx_id"]})
    await core_mod.db.contexts.delete_many({"id": env["ctx_id"]})
    app.dependency_overrides.clear()
