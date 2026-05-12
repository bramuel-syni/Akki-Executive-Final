"""Cycle Manager Feel pass (Patch 2 of 4) — backend tests.

Covers:
  • Extended cycle list envelope (counts_by_status, intel fields)
  • POST /cycles/{cid}/apply-template main_board
  • POST /quick-actions/{key}/clicked
  • GET  /quick-actions/order
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


def _acc(p):
    uid = uuid.uuid4().hex[:10]
    return {"id": f"{p}-{uid}", "email": f"{p}-{uid}@example.com",
            "display_name": p.title(), "name": p.title()}


@pytest.fixture(scope="module")
def env():
    return {
        "owner": _acc("feel-owner"),
        "outsider": _acc("feel-outsider"),
        "ctx": f"ctx-feel-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    for c in ("contexts", "memberships", "cycles", "cycle_agendas",
              "cycle_team", "cycle_contributions", "cycle_followups",
              "quick_action_usage", "team_catalogue"):
        await getattr(db, c).delete_many({"context_id": cid})
    for a in (env["owner"], env["outsider"]):
        await db.accounts.update_one({"id": a["id"]}, {"$set": a}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "Feel Co",
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
    # Seed 3 catalogue members so apply-template has something to copy.
    for i, (name, email) in enumerate([
        ("Alice Alpha",  "alice@example.com"),
        ("Bob Beta",     "bob@example.com"),
        ("Cara Gamma",   "cara@example.com"),
    ]):
        await db.team_catalogue.insert_one({
            "id": f"cat-{i}-{uuid.uuid4().hex[:6]}",
            "context_id": cid,
            "name": name, "email": email,
            "email_lc": email.lower(),
            "created_at": "2026-02-01T00:00:00Z",
            "updated_at": "2026-02-01T00:00:00Z",
            "deleted_at": None,
        })


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ── 1. Extended cycle list envelope ──────────────────────────────────
@pytest.mark.asyncio
async def test_cycle_list_envelope_carries_counts_by_status(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as c:
        # Make 2 draft + 1 active (after agenda+activate) + 0 completed.
        d1 = (await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Draft One"})).json()
        await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Draft Two"})
        await c.post(
            f"/api/contexts/{env['ctx']}/cycle/agenda?cycle_id={d1['id']}",
            json={"title": "Draft One", "items": [{"label": "Topic"}]},
        )
        await c.post(f"/api/contexts/{env['ctx']}/cycles/{d1['id']}/activate")
        r = await c.get(f"/api/contexts/{env['ctx']}/cycles")
    body = r.json()
    assert r.status_code == 200, r.text
    for k in ("counts_by_status", "total_pages"):
        assert k in body
    cbs = body["counts_by_status"]
    assert cbs["all"] >= 2
    assert cbs["draft"] >= 1
    assert cbs["active"] >= 1
    # Default page_size is now 10.
    assert body["page_size"] == 10


@pytest.mark.asyncio
async def test_cycle_list_rows_carry_intel_fields(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{env['ctx']}/cycles")
    cycles = r.json()["cycles"]
    assert len(cycles) >= 1
    for row in cycles:
        for k in ("agenda_count", "team_count", "readiness_pct",
                  "last_activity_at", "next_action_hint"):
            assert k in row, f"row missing {k!r}: {row}"


# ── 2. Apply template — Prepare for Main Board ───────────────────────
@pytest.mark.asyncio
async def test_apply_main_board_template(env):
    _auth(env["owner"])
    async with _client() as c:
        # Fresh draft cycle.
        cyc = (await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Main Board"})).json()
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{cyc['id']}/apply-template",
            json={"template_key": "main_board"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["agenda_items_added"] == 6
    assert body["team_members_added"] == 3
    # Agenda items in the canonical order.
    agenda = await core_mod.db.cycle_agendas.find_one({"id": cyc["id"]}, {"_id": 0, "items": 1})
    labels = [it["label"] for it in agenda["items"]]
    assert labels == [
        "Strategy review", "Financial performance", "Risk and compliance",
        "People and culture", "ExCo report", "Forward look",
    ]
    # Team rows seeded with empty role + "—" contribution_description.
    teams = await core_mod.db.cycle_team.find({"agenda_id": cyc["id"]}, {"_id": 0}).to_list(20)
    assert len(teams) == 3
    for t in teams:
        assert t["role"] is None
        assert t["contribution_description"] == "—"
        assert t["owns_item_ids"] == []
    # Cycle envelope reflects the new state on next read.
    detail = (await body["cycle"]["agenda_count"]) if False else body["cycle"]["agenda_count"]
    assert detail == 6
    assert body["cycle"]["team_count"] == 3
    env["tpl_cycle_id"] = cyc["id"]


@pytest.mark.asyncio
async def test_apply_template_idempotency_refuses_non_empty(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{env['tpl_cycle_id']}/apply-template",
            json={"template_key": "main_board"},
        )
    assert r.status_code == 409, r.text
    assert "cycle_not_empty" in str(r.json())


@pytest.mark.asyncio
async def test_apply_template_rejects_unknown_key(env):
    _auth(env["owner"])
    async with _client() as c:
        cyc = (await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "X"})).json()
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycles/{cyc['id']}/apply-template",
            json={"template_key": "bogus"},
        )
    assert r.status_code == 400, r.text


# ── 3. Quick Action telemetry ────────────────────────────────────────
@pytest.mark.asyncio
async def test_quick_action_click_increments_count(env):
    _auth(env["owner"])
    async with _client() as c:
        r1 = await c.post(f"/api/contexts/{env['ctx']}/quick-actions/main_board/clicked")
        r2 = await c.post(f"/api/contexts/{env['ctx']}/quick-actions/main_board/clicked")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["click_count"] == 1
    assert r2.json()["click_count"] == 2


@pytest.mark.asyncio
async def test_quick_action_rejects_unknown_key(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(f"/api/contexts/{env['ctx']}/quick-actions/bogus/clicked")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_quick_action_order_reflects_click_counts(env):
    """After clicking main_board twice and answer_questions once, the
    returned order is [main_board, answer_questions, project_proposal, fund_raising]."""
    _auth(env["owner"])
    async with _client() as c:
        # main_board already has 2 clicks from previous test.
        await c.post(f"/api/contexts/{env['ctx']}/quick-actions/answer_questions/clicked")
        r = await c.get(f"/api/contexts/{env['ctx']}/quick-actions/order")
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["order"] == [
        "main_board", "answer_questions", "project_proposal", "fund_raising",
    ]
    assert body["canonical"] == [
        "main_board", "answer_questions", "project_proposal", "fund_raising",
    ]


@pytest.mark.asyncio
async def test_quick_action_order_is_per_account(env):
    """Clicks by a different account do NOT affect another account's order."""
    # outsider is not a member; we make them a member quickly so the
    # require_context_membership passes.
    await core_mod.db.memberships.update_one(
        {"context_id": env["ctx"], "account_id": env["outsider"]["id"]},
        {"$set": {
            "context_id": env["ctx"], "account_id": env["outsider"]["id"],
            "role": "executive", "sub_role": None, "status": "active",
        }},
        upsert=True,
    )
    _auth(env["outsider"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{env['ctx']}/quick-actions/order")
    # Outsider has clicked nothing — falls back to canonical order.
    assert r.json()["order"] == [
        "main_board", "answer_questions", "project_proposal", "fund_raising",
    ]
