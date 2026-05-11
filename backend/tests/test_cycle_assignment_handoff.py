"""Cycle Manager — assignment handoff full lifecycle tests.

Covers the five state transitions (submit / assign / inbox / accept / decline)
plus permissions, idempotency, cohort resolution, and audit emission.

Privacy-Wall negative tests live in test_cycle_assignment_privacy_wall.py.
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


def _acc(prefix: str) -> dict:
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": f"{prefix.title()} {uid[:4]}",
        "name": f"{prefix.title()} {uid[:4]}",
    }


@pytest.fixture(scope="module")
def env():
    return {
        "owner": _acc("owner"),
        "cos": _acc("cos"),       # chief_of_staff sub_role
        "exco": _acc("exco"),     # ExCo team member
        "outsider": _acc("nonexec"),
        "ned_a": _acc("neda"),
        "ned_b": _acc("nedb"),
        "ned_other": _acc("nedother"),
        "ctx_team_id": f"ctx-{uuid.uuid4().hex[:10]}",
        "ctx_individual_id": f"ctx-{uuid.uuid4().hex[:10]}",
        "ctx_board_id": f"ctx-{uuid.uuid4().hex[:10]}",
        "ctx_other_board_id": f"ctx-{uuid.uuid4().hex[:10]}",
        "cycle_id": f"cyc-{uuid.uuid4().hex[:10]}",
        "brief_id": f"brf-{uuid.uuid4().hex[:10]}",
        "individual_brief_id": f"brf-{uuid.uuid4().hex[:10]}",
        "cohort_id": f"chrt-{uuid.uuid4().hex[:10]}",
        "exco_team_id": f"exco-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    # Clean up any prior run
    for cid in (env["ctx_team_id"], env["ctx_individual_id"], env["ctx_board_id"], env["ctx_other_board_id"]):
        await db.contexts.delete_many({"id": cid})
        await db.memberships.delete_many({"context_id": cid})
        await db.cycle_assignments.delete_many({"context_id": cid})
        await db.work_studio_briefs.delete_many({"context_id": cid})
        await db.audit_log.delete_many({"context_id": cid})
        await db.exco_teams.delete_many({"context_id": cid})
        await db.cohorts.delete_many({"context_id": cid})
        await db.cycle_agendas.delete_many({"context_id": cid})
    await db.ned_packs.delete_many({"ned_id": {"$in": [env["ned_a"]["id"], env["ned_b"]["id"]]}})

    for a in (env["owner"], env["cos"], env["exco"], env["outsider"],
              env["ned_a"], env["ned_b"], env["ned_other"]):
        await db.accounts.update_one({"id": a["id"]}, {"$set": a}, upsert=True)

    # Team workspace
    await db.contexts.insert_one({
        "id": env["ctx_team_id"], "name": "Team Co",
        "owner_account_id": env["owner"]["id"], "type": "executive_enterprise",
    })
    for acc, role, sub in [
        (env["owner"], "executive", "admin"),
        (env["cos"], "executive", "chief_of_staff"),
        (env["exco"], "executive", None),
        (env["outsider"], "executive", None),
    ]:
        await db.memberships.update_one(
            {"context_id": env["ctx_team_id"], "account_id": acc["id"]},
            {"$set": {
                "context_id": env["ctx_team_id"], "account_id": acc["id"],
                "role": role, "sub_role": sub, "status": "active",
            }},
            upsert=True,
        )
    # ExCo team (gives `exco` user submit permission)
    await db.exco_teams.insert_one({
        "id": env["exco_team_id"], "context_id": env["ctx_team_id"],
        "name": "SLT", "member_account_ids": [env["exco"]["id"]],
        "created_by": env["owner"]["id"], "status": "active",
        "created_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z",
    })

    # Individual workspace (owner-only)
    await db.contexts.insert_one({
        "id": env["ctx_individual_id"], "name": "Solo Co",
        "owner_account_id": env["owner"]["id"], "type": "executive_personal",
    })
    await db.memberships.update_one(
        {"context_id": env["ctx_individual_id"], "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": env["ctx_individual_id"], "account_id": env["owner"]["id"],
            "role": "executive", "sub_role": "admin", "status": "active",
        }},
        upsert=True,
    )
    await db.memberships.update_one(
        {"context_id": env["ctx_individual_id"], "account_id": env["outsider"]["id"]},
        {"$set": {
            "context_id": env["ctx_individual_id"], "account_id": env["outsider"]["id"],
            "role": "executive", "sub_role": None, "status": "active",
        }},
        upsert=True,
    )

    # NED boards (used by inbox tests + ned membership lookups)
    await db.contexts.insert_one({
        "id": env["ctx_board_id"], "name": "Board A",
        "owner_account_id": env["ned_a"]["id"], "type": "ned_personal",
    })
    for ned in (env["ned_a"], env["ned_b"]):
        await db.memberships.update_one(
            {"context_id": env["ctx_board_id"], "account_id": ned["id"]},
            {"$set": {
                "context_id": env["ctx_board_id"], "account_id": ned["id"],
                "role": "ned", "status": "active",
            }},
            upsert=True,
        )
    await db.contexts.insert_one({
        "id": env["ctx_other_board_id"], "name": "Other Board",
        "owner_account_id": env["ned_other"]["id"], "type": "ned_personal",
    })
    await db.memberships.update_one(
        {"context_id": env["ctx_other_board_id"], "account_id": env["ned_other"]["id"]},
        {"$set": {
            "context_id": env["ctx_other_board_id"], "account_id": env["ned_other"]["id"],
            "role": "ned", "status": "active",
        }},
        upsert=True,
    )

    # Cohort that fans out to ned_a + ned_b
    await db.cohorts.insert_one({
        "id": env["cohort_id"], "context_id": env["ctx_team_id"],
        "label": "Audit Committee NEDs",
        "ned_account_ids": [env["ned_a"]["id"], env["ned_b"]["id"]],
        "status": "active",
    })

    # Cycle agenda (just enough for cycle_title resolution)
    await db.cycle_agendas.insert_one({
        "id": env["cycle_id"], "context_id": env["ctx_team_id"],
        "title": "Q1 2026 Board Cycle",
    })

    # Briefs (team-workspace + individual-workspace)
    for bid, cid in [(env["brief_id"], env["ctx_team_id"]),
                     (env["individual_brief_id"], env["ctx_individual_id"])]:
        await db.work_studio_briefs.insert_one({
            "id": bid, "context_id": cid,
            "account_id": env["owner"]["id"],
            "source_type": "test_seed", "source_id": bid,
            "title": "Q1 Reporting Brief", "subtitle": "Cycle compilation",
            "company_label": "Acme", "document_type": "Board Briefing",
            "active_revision_id": f"rev-{uuid.uuid4().hex[:8]}",
            "revision_count": 1,
            "board_status": "draft",
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-01T00:00:00Z",
        })


def _auth(account: dict):
    async def _override():
        return account
    app.dependency_overrides[core_mod.get_current_account] = _override


def _client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ── 1. Submit ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_owner_can_submit_brief_for_board_team_workspace(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/submit-for-board",
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["board_status"] == "submitted"
    assert body["submitter_account_id"] == env["owner"]["id"]
    # Brief row reflects new state
    brief = await core_mod.db.work_studio_briefs.find_one(
        {"id": env["brief_id"]}, {"_id": 0}
    )
    assert brief["board_status"] == "submitted"
    assert brief.get("submitted_at")
    # Audit row written
    aud = await core_mod.db.audit_log.find_one(
        {"action": "cycle.brief.submit_for_board", "resource_id": env["brief_id"]},
    )
    assert aud is not None and aud["metadata"]["workspace_kind"] == "team"
    assert aud["metadata"]["permission_reason"] == "owner"


@pytest.mark.asyncio
async def test_chief_of_staff_can_submit_in_team_workspace(env):
    # Re-set brief board_status so this test is independent
    await core_mod.db.work_studio_briefs.update_one(
        {"id": env["brief_id"]}, {"$set": {"board_status": "draft"}}
    )
    _auth(env["cos"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/submit-for-board",
        )
    assert r.status_code == 200, r.text
    aud = await core_mod.db.audit_log.find_one(
        {"action": "cycle.brief.submit_for_board", "resource_id": env["brief_id"]},
        sort=[("created_at", -1)],
    )
    assert aud["metadata"]["permission_reason"] == "team_chief_of_staff"


@pytest.mark.asyncio
async def test_exco_member_can_submit_in_team_workspace(env):
    await core_mod.db.work_studio_briefs.update_one(
        {"id": env["brief_id"]}, {"$set": {"board_status": "draft"}}
    )
    _auth(env["exco"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/submit-for-board",
        )
    assert r.status_code == 200, r.text
    aud = await core_mod.db.audit_log.find_one(
        {"action": "cycle.brief.submit_for_board", "resource_id": env["brief_id"]},
        sort=[("created_at", -1)],
    )
    assert aud["metadata"]["permission_reason"] == "team_exco_member"


@pytest.mark.asyncio
async def test_unprivileged_member_cannot_submit_team_workspace(env):
    _auth(env["outsider"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/submit-for-board",
        )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_individual_workspace_only_owner_can_submit(env):
    _auth(env["outsider"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_individual_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['individual_brief_id']}/submit-for-board",
        )
    assert r.status_code == 403, r.text
    _auth(env["owner"])
    async with _client() as cli:
        r2 = await cli.post(
            f"/api/contexts/{env['ctx_individual_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['individual_brief_id']}/submit-for-board",
        )
    assert r2.status_code == 200, r2.text


# ── 2. Assign ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_assign_requires_submitted_status(env):
    # Brief currently submitted (test 1). Make a fresh draft brief.
    fresh_bid = f"brf-{uuid.uuid4().hex[:10]}"
    await core_mod.db.work_studio_briefs.insert_one({
        "id": fresh_bid, "context_id": env["ctx_team_id"],
        "account_id": env["owner"]["id"],
        "source_type": "test_seed", "source_id": fresh_bid,
        "title": "Draft Only", "active_revision_id": "rev-x",
        "revision_count": 1, "board_status": "draft",
        "created_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z",
    })
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{fresh_bid}/assignments",
            json={"ned_ids": [env["ned_a"]["id"]]},
        )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_assign_rejects_both_ned_ids_and_cohort_id(env):
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/assignments",
            json={"ned_ids": [env["ned_a"]["id"]], "cohort_id": env["cohort_id"]},
        )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_assign_rejects_neither_ned_ids_nor_cohort_id(env):
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/assignments",
            json={"note": "missing both"},
        )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_assign_ned_ids_fan_out(env):
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/assignments",
            json={
                "ned_ids": [env["ned_a"]["id"], env["ned_b"]["id"]],
                "note": "Pre-read for Q1",
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["count"] == 2
    assert body["newly_created"] == 2
    statuses = {a["ned_id"]: a["status"] for a in body["assignments"]}
    assert statuses == {env["ned_a"]["id"]: "pending", env["ned_b"]["id"]: "pending"}


@pytest.mark.asyncio
async def test_assign_idempotent_on_repeat(env):
    """Calling assign again with the same ned_ids does NOT create
    duplicate rows. newly_created == 0 on the second call."""
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/assignments",
            json={"ned_ids": [env["ned_a"]["id"], env["ned_b"]["id"]]},
        )
    assert r.status_code == 201
    assert r.json()["newly_created"] == 0
    assert r.json()["count"] == 2


@pytest.mark.asyncio
async def test_assign_cohort_resolution(env):
    # Use a fresh brief so the cohort path is exercised cleanly.
    bid = f"brf-{uuid.uuid4().hex[:10]}"
    await core_mod.db.work_studio_briefs.insert_one({
        "id": bid, "context_id": env["ctx_team_id"],
        "account_id": env["owner"]["id"],
        "source_type": "test_seed", "source_id": bid,
        "title": "Cohort brief", "active_revision_id": "rev-c",
        "revision_count": 1, "board_status": "submitted",
        "submitted_at": "2026-02-02T00:00:00Z",
        "submitter_account_id": env["owner"]["id"],
        "submitted_cycle_id": env["cycle_id"],
        "created_at": "2026-02-02T00:00:00Z", "updated_at": "2026-02-02T00:00:00Z",
    })
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{bid}/assignments",
            json={"cohort_id": env["cohort_id"]},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["count"] == 2
    assert body["newly_created"] == 2
    # Each row carries the cohort_id + label snapshot
    for a in body["assignments"]:
        assert a["cohort_id"] == env["cohort_id"]
        assert a["cohort_label"] == "Audit Committee NEDs"


@pytest.mark.asyncio
async def test_assign_unprivileged_member_refused(env):
    _auth(env["outsider"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{env['brief_id']}/assignments",
            json={"ned_ids": [env["ned_a"]["id"]]},
        )
    assert r.status_code == 403, r.text


# ── 3. NED inbox ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ned_inbox_returns_only_whitelisted_fields(env):
    """Strict whitelist enforcement: items contain ONLY the fields
    declared on NedInboxItemOut. The privacy-wall test suite has more
    aggressive negative coverage; this is the positive contract."""
    _auth(env["ned_a"])
    async with _client() as cli:
        r = await cli.get("/api/ned/inbox/assignments")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 1
    allowed = {
        "assignment_id", "brief_id", "submitter_display_name",
        "cycle_title", "submitted_at", "cohort_label", "note", "status",
    }
    for item in body["items"]:
        extra = set(item.keys()) - allowed
        assert not extra, f"Inbox surfaced disallowed fields: {extra}"


@pytest.mark.asyncio
async def test_ned_inbox_scoped_to_authed_ned_only(env):
    _auth(env["ned_other"])
    async with _client() as cli:
        r = await cli.get("/api/ned/inbox/assignments")
    assert r.status_code == 200, r.text
    body = r.json()
    # ned_other never received assignments
    assert body["count"] == 0


# ── 4. Accept ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ned_accept_creates_ned_pack_and_marks_accepted(env):
    _auth(env["ned_a"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        assignment_id = inbox["items"][0]["assignment_id"]
        r = await cli.post(f"/api/ned/assignments/{assignment_id}/accept")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "accepted"
    # ned_packs row written, with ONLY whitelisted fields
    pack = await core_mod.db.ned_packs.find_one(
        {"assignment_id": assignment_id}, {"_id": 0},
    )
    assert pack is not None
    forbidden = {"agenda", "contributions", "scoring_rationale", "cycle_team",
                 "scores", "score_rationale", "agenda_internals"}
    assert not (set(pack.keys()) & forbidden), pack
    # brief board_status promoted to shipped on first accept
    brief = await core_mod.db.work_studio_briefs.find_one(
        {"id": env["brief_id"]}, {"_id": 0}
    )
    assert brief["board_status"] == "shipped"


@pytest.mark.asyncio
async def test_ned_accept_idempotent(env):
    _auth(env["ned_a"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        accepted = [i for i in inbox["items"] if i["status"] == "accepted"]
        assert accepted, "expected an already-accepted item"
        assignment_id = accepted[0]["assignment_id"]
        r = await cli.post(f"/api/ned/assignments/{assignment_id}/accept")
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_ned_cannot_accept_another_neds_assignment(env):
    _auth(env["ned_a"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        assignment_id = inbox["items"][0]["assignment_id"]
    # ned_other attempts to accept ned_a's assignment
    _auth(env["ned_other"])
    async with _client() as cli:
        r = await cli.post(f"/api/ned/assignments/{assignment_id}/accept")
    assert r.status_code == 404, r.text


# ── 5. Decline ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ned_can_decline_pending_assignment(env):
    _auth(env["ned_b"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        pending = [i for i in inbox["items"] if i["status"] == "pending"]
        assert pending, "expected at least one pending"
        assignment_id = pending[0]["assignment_id"]
        r = await cli.post(
            f"/api/ned/assignments/{assignment_id}/decline",
            json={"reason": "Conflict of interest"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "declined"


@pytest.mark.asyncio
async def test_ned_cannot_decline_after_accept(env):
    _auth(env["ned_a"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        accepted = [i for i in inbox["items"] if i["status"] == "accepted"]
        assert accepted
        r = await cli.post(
            f"/api/ned/assignments/{accepted[0]['assignment_id']}/decline",
            json={"reason": "n/a"},
        )
    assert r.status_code == 409, r.text


# ── 6. Cancel (creator-only, before NED accepts) ─────────────────────
@pytest.mark.asyncio
async def test_creator_can_cancel_pending(env):
    """Create a fresh brief + assignment, then cancel it."""
    bid = f"brf-{uuid.uuid4().hex[:10]}"
    await core_mod.db.work_studio_briefs.insert_one({
        "id": bid, "context_id": env["ctx_team_id"],
        "account_id": env["owner"]["id"],
        "source_type": "test_seed", "source_id": bid,
        "title": "Cancel test", "active_revision_id": "rev-x",
        "revision_count": 1, "board_status": "submitted",
        "submitted_at": "2026-02-02T00:00:00Z",
        "submitter_account_id": env["owner"]["id"],
        "created_at": "2026-02-02T00:00:00Z", "updated_at": "2026-02-02T00:00:00Z",
    })
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.post(
            f"/api/contexts/{env['ctx_team_id']}/cycles/{env['cycle_id']}"
            f"/briefs/{bid}/assignments",
            json={"ned_ids": [env["ned_a"]["id"]]},
        )
        assert r.status_code == 201
        aid = r.json()["assignments"][0]["id"]
        r2 = await cli.delete(
            f"/api/contexts/{env['ctx_team_id']}/cycle-assignments/{aid}",
        )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cannot_cancel_after_accept(env):
    _auth(env["ned_a"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        accepted = [i for i in inbox["items"] if i["status"] == "accepted"]
        aid = accepted[0]["assignment_id"]
    _auth(env["owner"])
    async with _client() as cli:
        r = await cli.delete(
            f"/api/contexts/{env['ctx_team_id']}/cycle-assignments/{aid}",
        )
    assert r.status_code == 409, r.text


# ── 7. Submitter rollup (Should-have surface) ─────────────────────────
@pytest.mark.asyncio
async def test_my_submitted_briefs_rollup(env):
    # The most-recent submitter of env["brief_id"] is `exco` (test #3).
    _auth(env["exco"])
    async with _client() as cli:
        r = await cli.get("/api/me/submitted-briefs")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] >= 1
    rollup_for = {b["id"]: b["assignment_rollup"] for b in body["briefs"]}
    target = rollup_for[env["brief_id"]]
    # At least one accepted + one declined recorded above
    assert target["accepted"] >= 1
    assert target["declined"] >= 1
