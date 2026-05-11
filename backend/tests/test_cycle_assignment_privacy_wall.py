"""Privacy-Wall negative tests for Cycle Manager assignment handoff.

Hard rule from CYCLE_MANAGER_BRIEF.md §3.3: ANY write that copies
Exec-internal fields (cycle_agendas, cycle_contributions, cycle_team,
cycle_followups, scoring rationale, agenda internals) into NED
collections (ned_meetings, ned_meeting_notes, ned_positions,
ned_followups, ned_packs, ned_annotations) is a CI failure.

These tests prove that:

  1. The accept ingest path NEVER reads from cycle_agendas /
     cycle_contributions / cycle_team / cycle_followups (monkeypatched
     to raise on any access).
  2. The ned_packs row written by accept contains ONLY whitelisted fields.
  3. The NED inbox response surface exposes ONLY the strict whitelist —
     even if the underlying cycle_assignments row carries extra fields,
     they are NOT projected.
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


_ALLOWED_NED_INBOX_FIELDS = {
    "assignment_id", "brief_id", "submitter_display_name",
    "cycle_title", "submitted_at", "cohort_label", "note", "status",
}

# Fields from Exec-internal collections that MUST NOT appear in any
# row read by the NED side. The strings here are sentinel values that
# we plant in the source rows and then assert never re-surface.
_EXEC_INTERNAL_SENTINELS = {
    "EXEC_SCORING_RATIONALE_SENTINEL_FORBIDDEN",
    "EXEC_AGENDA_INTERNAL_SENTINEL_FORBIDDEN",
    "EXEC_CONTRIBUTION_BODY_SENTINEL_FORBIDDEN",
    "EXEC_TEAM_INTERNAL_SENTINEL_FORBIDDEN",
    "EXEC_FOLLOWUP_PRIVATE_SENTINEL_FORBIDDEN",
}

_EXEC_INTERNAL_NED_KEY_DENYLIST = {
    "agenda", "agenda_internals", "agenda_items",
    "contributions", "contribution_metadata",
    "scoring_rationale", "scores", "score_rationale",
    "cycle_team", "team_internal",
    "cycle_followups", "followups_private",
    "exec_internal", "exec_only",
}


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
        "ned": _acc("ned"),
        "ctx": f"ctx-{uuid.uuid4().hex[:10]}",
        "cycle_id": f"cyc-{uuid.uuid4().hex[:10]}",
        "brief_id": f"brf-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.cycle_assignments.delete_many({"context_id": cid})
    await db.work_studio_briefs.delete_many({"context_id": cid})
    await db.cycle_agendas.delete_many({"context_id": cid})
    await db.cycle_contributions.delete_many({"context_id": cid})
    await db.cycle_team.delete_many({"context_id": cid})
    await db.cycle_followups.delete_many({"context_id": cid})
    await db.ned_packs.delete_many({"ned_id": env["ned"]["id"]})
    await db.audit_log.delete_many({"context_id": cid})

    for a in (env["owner"], env["ned"]):
        await db.accounts.update_one({"id": a["id"]}, {"$set": a}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "Privacy Wall Test Co",
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
    # Plant Exec-internal collections WITH sentinel values that MUST
    # never re-surface on the NED side.
    await db.cycle_agendas.insert_one({
        "id": env["cycle_id"], "context_id": cid,
        "title": "Q1 Cycle",
        "items": [{
            "id": "item-1", "title": "Strategy refresh",
            "internal_note": "EXEC_AGENDA_INTERNAL_SENTINEL_FORBIDDEN",
        }],
        "internal_owner_only": "EXEC_AGENDA_INTERNAL_SENTINEL_FORBIDDEN",
    })
    await db.cycle_contributions.insert_one({
        "id": "c1", "context_id": cid, "agenda_id": env["cycle_id"],
        "body_text": "EXEC_CONTRIBUTION_BODY_SENTINEL_FORBIDDEN",
        "score_rationale": "EXEC_SCORING_RATIONALE_SENTINEL_FORBIDDEN",
        "scores": {"impact": 4},
    })
    await db.cycle_team.insert_one({
        "id": "t1", "context_id": cid, "agenda_id": env["cycle_id"],
        "name": "Internal Person",
        "contribution_description": "EXEC_TEAM_INTERNAL_SENTINEL_FORBIDDEN",
    })
    await db.cycle_followups.insert_one({
        "id": "f1", "context_id": cid, "agenda_id": env["cycle_id"],
        "draft_body": "EXEC_FOLLOWUP_PRIVATE_SENTINEL_FORBIDDEN",
    })

    # Submitted brief
    await db.work_studio_briefs.insert_one({
        "id": env["brief_id"], "context_id": cid,
        "account_id": env["owner"]["id"],
        "source_type": "test_seed", "source_id": env["brief_id"],
        "title": "Public-facing Brief Title",
        "subtitle": "Cycle compilation",
        "company_label": "Acme",
        "document_type": "Board Briefing",
        "active_revision_id": "rev-1",
        "revision_count": 1,
        "board_status": "submitted",
        "submitted_at": "2026-02-02T00:00:00Z",
        "submitter_account_id": env["owner"]["id"],
        "submitted_cycle_id": env["cycle_id"],
        "created_at": "2026-02-02T00:00:00Z",
        "updated_at": "2026-02-02T00:00:00Z",
    })


def _auth(account: dict):
    async def _override():
        return account
    app.dependency_overrides[core_mod.get_current_account] = _override


def _client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _walk_for_sentinels(obj, sentinels=_EXEC_INTERNAL_SENTINELS, path="$"):
    """Recursively assert no sentinel string appears as any value."""
    if isinstance(obj, str):
        for s in sentinels:
            assert s not in obj, (
                f"Privacy wall leak at {path}: sentinel {s!r} surfaced "
                f"in NED-facing string."
            )
    elif isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in _EXEC_INTERNAL_NED_KEY_DENYLIST, (
                f"Privacy wall leak at {path}.{k}: denylisted Exec-"
                f"internal key surfaced in NED-facing payload."
            )
            _walk_for_sentinels(v, sentinels, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_for_sentinels(v, sentinels, f"{path}[{i}]")


# ─── 1. Inbox response carries ONLY whitelisted fields, even if the
#       underlying row was polluted ───────────────────────────────────
@pytest.mark.asyncio
async def test_ned_inbox_strips_polluted_assignment_fields(env):
    await _seed(env)
    # Create an assignment row with deliberate Exec-internal pollution
    # — simulating a bad future write that violates the wall.
    polluted = {
        "id": str(uuid.uuid4()),
        "brief_id": env["brief_id"],
        "cycle_id": env["cycle_id"],
        "context_id": env["ctx"],
        "ned_id": env["ned"]["id"],
        "submitter_account_id": env["owner"]["id"],
        "submitter_display_name": "Owner Bob",
        "cycle_title": "Q1 Cycle",
        "submitted_at": "2026-02-02T00:00:00Z",
        "status": "pending",
        "created_at": "2026-02-02T00:00:00Z",
        "updated_at": "2026-02-02T00:00:00Z",
        "note": None, "cohort_id": None, "cohort_label": None,
        "accepted_at": None, "declined_at": None, "decline_reason": None,
        # Pollution ↓
        "agenda_internals": "EXEC_AGENDA_INTERNAL_SENTINEL_FORBIDDEN",
        "score_rationale": "EXEC_SCORING_RATIONALE_SENTINEL_FORBIDDEN",
        "exec_internal": {"contributions": ["EXEC_CONTRIBUTION_BODY_SENTINEL_FORBIDDEN"]},
        "cycle_team": "EXEC_TEAM_INTERNAL_SENTINEL_FORBIDDEN",
    }
    await core_mod.db.cycle_assignments.insert_one(polluted)
    _auth(env["ned"])
    async with _client() as cli:
        r = await cli.get("/api/ned/inbox/assignments")
    assert r.status_code == 200, r.text
    body = r.json()
    # Verify the polluted row was returned
    matching = [i for i in body["items"] if i["assignment_id"] == polluted["id"]]
    assert len(matching) == 1, "expected polluted assignment to appear"
    item = matching[0]
    # Field whitelist enforcement
    extra = set(item.keys()) - _ALLOWED_NED_INBOX_FIELDS
    assert not extra, f"Inbox leaked disallowed fields: {extra}"
    # Sentinel scan over the FULL response
    _walk_for_sentinels(body)


# ─── 2. Accept ingest path produces a ned_packs row free of Exec
#       internals — and only references the brief by id ──────────────
@pytest.mark.asyncio
async def test_accept_writes_minimal_ned_packs_row(env):
    """Accept must NOT copy agenda/contributions/team/followups into
    ned_packs. The row should reference the brief_id and nothing else
    that could contain Exec-internal content."""
    # Use the already-pending assignment from test #1
    _auth(env["ned"])
    async with _client() as cli:
        inbox = (await cli.get("/api/ned/inbox/assignments")).json()
        assignment_id = inbox["items"][0]["assignment_id"]
        r = await cli.post(f"/api/ned/assignments/{assignment_id}/accept")
    assert r.status_code == 200, r.text
    pack = await core_mod.db.ned_packs.find_one(
        {"assignment_id": assignment_id}, {"_id": 0},
    )
    assert pack is not None
    # Sentinel scan — no Exec-internal string survived ingest.
    _walk_for_sentinels(pack)
    # Strict-keys assertion — ned_packs row schema is locked.
    allowed_pack_keys = {
        "id", "ned_id", "assignment_id", "brief_id",
        "submitter_display_name", "cycle_title", "received_at",
    }
    extra = set(pack.keys()) - allowed_pack_keys
    assert not extra, f"ned_packs row carries disallowed keys: {extra}"


# ─── 3. Defensive guard: accept must NOT read cycle_agendas /
#       cycle_contributions / cycle_team / cycle_followups ─────────────
@pytest.mark.asyncio
async def test_accept_never_reads_exec_internal_collections(env, monkeypatch):
    """Patch find/find_one on the four Exec-internal collections to
    raise. If accept tries to touch any of them, the test fails — proof
    the ingest is genuinely independent of Exec-internal state."""
    # Fresh assignment + brief so we don't reuse already-accepted ids.
    bid = f"brf-{uuid.uuid4().hex[:10]}"
    await core_mod.db.work_studio_briefs.insert_one({
        "id": bid, "context_id": env["ctx"],
        "account_id": env["owner"]["id"],
        "source_type": "test_seed", "source_id": bid,
        "title": "Defensive guard brief",
        "active_revision_id": "rev-d", "revision_count": 1,
        "board_status": "submitted",
        "submitted_at": "2026-02-03T00:00:00Z",
        "submitter_account_id": env["owner"]["id"],
        "submitted_cycle_id": env["cycle_id"],
        "created_at": "2026-02-03T00:00:00Z",
        "updated_at": "2026-02-03T00:00:00Z",
    })
    aid = str(uuid.uuid4())
    await core_mod.db.cycle_assignments.insert_one({
        "id": aid, "brief_id": bid, "cycle_id": env["cycle_id"],
        "context_id": env["ctx"], "ned_id": env["ned"]["id"],
        "submitter_account_id": env["owner"]["id"],
        "submitter_display_name": "Owner Bob",
        "cycle_title": "Q1 Cycle",
        "submitted_at": "2026-02-03T00:00:00Z",
        "status": "pending",
        "created_at": "2026-02-03T00:00:00Z",
        "updated_at": "2026-02-03T00:00:00Z",
        "note": None, "cohort_id": None, "cohort_label": None,
        "accepted_at": None, "declined_at": None, "decline_reason": None,
    })

    def _raise(*a, **k):
        raise AssertionError(
            "Privacy wall violation: accept path read from an Exec-"
            "internal collection (cycle_agendas / cycle_contributions / "
            "cycle_team / cycle_followups)."
        )
    monkeypatch.setattr(core_mod.db.cycle_agendas, "find_one", _raise)
    monkeypatch.setattr(core_mod.db.cycle_agendas, "find", _raise)
    monkeypatch.setattr(core_mod.db.cycle_contributions, "find_one", _raise)
    monkeypatch.setattr(core_mod.db.cycle_contributions, "find", _raise)
    monkeypatch.setattr(core_mod.db.cycle_team, "find_one", _raise)
    monkeypatch.setattr(core_mod.db.cycle_team, "find", _raise)
    monkeypatch.setattr(core_mod.db.cycle_followups, "find_one", _raise)
    monkeypatch.setattr(core_mod.db.cycle_followups, "find", _raise)

    _auth(env["ned"])
    async with _client() as cli:
        r = await cli.post(f"/api/ned/assignments/{aid}/accept")
    assert r.status_code == 200, r.text
    # Defensive scan over the ned_packs row
    pack = await core_mod.db.ned_packs.find_one(
        {"assignment_id": aid}, {"_id": 0},
    )
    _walk_for_sentinels(pack)
