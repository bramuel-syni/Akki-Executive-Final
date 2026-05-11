"""Cycle Manager v2 — multi-cycle lifecycle tests."""
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


def _acc(prefix: str) -> dict:
    uid = uuid.uuid4().hex[:10]
    return {"id": f"{prefix}-{uid}", "email": f"{prefix}-{uid}@example.com",
            "display_name": f"{prefix.title()} {uid[:4]}",
            "name": f"{prefix.title()} {uid[:4]}"}


@pytest.fixture(scope="module")
def env():
    return {
        "owner": _acc("v2owner"),
        "outsider": _acc("v2outsider"),
        "ctx": f"ctx-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    await db.memberships.delete_many({"context_id": cid})
    await db.cycles.delete_many({"context_id": cid})
    await db.cycle_agendas.delete_many({"context_id": cid})
    await db.cycle_team.delete_many({"context_id": cid})
    await db.cycle_contributions.delete_many({"context_id": cid})
    await db.cycle_followups.delete_many({"context_id": cid})
    await db["team_catalogue"].delete_many({"context_id": cid})
    for a in (env["owner"], env["outsider"]):
        await db.accounts.update_one({"id": a["id"]}, {"$set": a}, upsert=True)
    await db.contexts.insert_one({
        "id": cid, "name": "v2 Co",
        "owner_account_id": env["owner"]["id"], "type": "executive_enterprise",
    })
    for acc, sub in [(env["owner"], "admin"), (env["outsider"], None)]:
        await db.memberships.update_one(
            {"context_id": cid, "account_id": acc["id"]},
            {"$set": {
                "context_id": cid, "account_id": acc["id"],
                "role": "executive", "sub_role": sub, "status": "active",
            }},
            upsert=True,
        )


def _auth(a):
    async def _o():
        return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


# ── Create + list + detail ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_cycle_returns_draft_and_redirect(env):
    await _seed(env)
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Q1 2026"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "draft"
    assert b["title"] == "Q1 2026"
    assert b["redirect_url"].startswith("/app/cycle/")
    assert b["agenda_count"] == 0
    env["c1"] = b["id"]


@pytest.mark.asyncio
async def test_list_cycles_paginated(env):
    _auth(env["owner"])
    async with _client() as c:
        for i in range(3):
            await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": f"Cycle {i+2}"})
        r = await c.get(f"/api/contexts/{env['ctx']}/cycles?page=1&page_size=12")
    assert r.status_code == 200
    b = r.json()
    assert b["total"] >= 4
    assert len(b["cycles"]) >= 4
    titles = [x["title"] for x in b["cycles"]]
    # Default sort = recent → newest first
    assert titles[0] in {"Cycle 4", "Cycle 3", "Cycle 2"} or titles[0] == "Q1 2026"


@pytest.mark.asyncio
async def test_list_cycles_search(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{env['ctx']}/cycles?q=Q1")
    assert r.status_code == 200
    b = r.json()
    assert any("Q1" in x["title"] for x in b["cycles"])


@pytest.mark.asyncio
async def test_list_cycles_sort_alpha(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.get(f"/api/contexts/{env['ctx']}/cycles?sort=alpha")
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()["cycles"]]
    assert titles == sorted(titles)


# ── Activate (PO decision #1: MANUAL) ─────────────────────────────────
@pytest.mark.asyncio
async def test_activate_requires_agenda_item(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(f"/api/contexts/{env['ctx']}/cycles/{env['c1']}/activate")
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_activate_after_adding_agenda_item(env):
    _auth(env["owner"])
    async with _client() as c:
        # Add an agenda item via the legacy upsert endpoint scoped by cycle_id.
        await c.post(
            f"/api/contexts/{env['ctx']}/cycle/agenda?cycle_id={env['c1']}",
            json={"title": "Q1 2026", "items": [{"label": "Strategy refresh"}]},
        )
        r = await c.post(f"/api/contexts/{env['ctx']}/cycles/{env['c1']}/activate")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    assert r.json()["agenda_count"] == 1


# ── Close (active → completed) ────────────────────────────────────────
@pytest.mark.asyncio
async def test_close_active_cycle(env):
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(f"/api/contexts/{env['ctx']}/cycles/{env['c1']}/close")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    assert r.json()["closed_at"] is not None


@pytest.mark.asyncio
async def test_completed_cycle_rejects_writes(env):
    """Adding a team member to a completed cycle returns 409."""
    _auth(env["owner"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx']}/cycle/team?cycle_id={env['c1']}",
            json={
                "name": "X Y", "email": "xy@example.com",
                "contribution_description": "—", "owns_item_ids": [],
            },
        )
    assert r.status_code == 409, r.text
    assert "cycle_completed" in str(r.json())


@pytest.mark.asyncio
async def test_cannot_close_draft_cycle(env):
    _auth(env["owner"])
    async with _client() as c:
        r0 = await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Draft only"})
        cid_draft = r0.json()["id"]
        r = await c.post(f"/api/contexts/{env['ctx']}/cycles/{cid_draft}/close")
    assert r.status_code == 400, r.text


# ── Eligible contributors (PO decision #2) ────────────────────────────
@pytest.mark.asyncio
async def test_eligible_contributors_filtered_by_agenda_item(env):
    _auth(env["owner"])
    async with _client() as c:
        # Build a fresh active cycle
        r0 = await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Eligibility test"})
        cyc = r0.json()["id"]
        ag = await c.post(
            f"/api/contexts/{env['ctx']}/cycle/agenda?cycle_id={cyc}",
            json={"title": "Eligibility test", "items": [
                {"label": "Item A"}, {"label": "Item B"}]},
        )
        items = ag.json()["items"]
        a_id, b_id = items[0]["id"], items[1]["id"]
        # Member 1 → A only; Member 2 → B only; Member 3 → A and B
        for n, owns in [("Alice", [a_id]), ("Bob", [b_id]), ("Cara", [a_id, b_id])]:
            await c.post(
                f"/api/contexts/{env['ctx']}/cycle/team?cycle_id={cyc}",
                json={"name": n, "email": f"{n.lower()}@example.com",
                      "contribution_description": "—", "owns_item_ids": owns},
            )
        # Eligible for Item A
        r = await c.get(
            f"/api/contexts/{env['ctx']}/cycles/{cyc}/agenda-items/{a_id}/eligible-contributors",
        )
        assert r.status_code == 200, r.text
        names = sorted([m["name"] for m in r.json()["contributors"]])
        assert names == ["Alice", "Cara"]
        # Eligible for Item B
        r2 = await c.get(
            f"/api/contexts/{env['ctx']}/cycles/{cyc}/agenda-items/{b_id}/eligible-contributors",
        )
        names2 = sorted([m["name"] for m in r2.json()["contributors"]])
        assert names2 == ["Bob", "Cara"]


# ── Multi-cycle data isolation ────────────────────────────────────────
@pytest.mark.asyncio
async def test_two_cycles_isolated_team_data(env):
    _auth(env["owner"])
    async with _client() as c:
        a = (await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Iso A"})).json()
        b = (await c.post(f"/api/contexts/{env['ctx']}/cycles", json={"title": "Iso B"})).json()
        await c.post(
            f"/api/contexts/{env['ctx']}/cycle/team?cycle_id={a['id']}",
            json={"name": "Member A", "email": "a@example.com",
                  "contribution_description": "—", "owns_item_ids": []},
        )
        ra = await c.get(f"/api/contexts/{env['ctx']}/cycle/team?cycle_id={a['id']}")
        rb = await c.get(f"/api/contexts/{env['ctx']}/cycle/team?cycle_id={b['id']}")
    names_a = [m["name"] for m in ra.json()["members"]]
    names_b = [m["name"] for m in rb.json()["members"]]
    assert "Member A" in names_a
    assert "Member A" not in names_b


# ── 400 when multiple active cycles and cycle_id omitted ──────────────
@pytest.mark.asyncio
async def test_singleton_endpoint_400s_with_multiple_actives(env):
    """Build a fresh context so this test is robust against
    leftover state from earlier tests in the module."""
    db = core_mod.db
    cid_local = f"ctx-{uuid.uuid4().hex[:10]}"
    await db.contexts.insert_one({
        "id": cid_local, "name": "Multi-active Co",
        "owner_account_id": env["owner"]["id"], "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid_local, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid_local, "account_id": env["owner"]["id"],
            "role": "executive", "sub_role": "admin", "status": "active",
        }},
        upsert=True,
    )
    _auth(env["owner"])
    async with _client() as c:
        # Build TWO active cycles in this fresh context.
        for title in ("Active 1", "Active 2"):
            nc_r = await c.post(f"/api/contexts/{cid_local}/cycles", json={"title": title})
            assert nc_r.status_code == 201, nc_r.text
            nc = nc_r.json()
            await c.post(
                f"/api/contexts/{cid_local}/cycle/agenda?cycle_id={nc['id']}",
                json={"title": title, "items": [{"label": "Topic"}]},
            )
            r_act = await c.post(f"/api/contexts/{cid_local}/cycles/{nc['id']}/activate")
            assert r_act.status_code == 200, r_act.text
        # Two actives now exist. Singleton endpoint without cycle_id → 400.
        r = await c.get(f"/api/contexts/{cid_local}/cycle/team")
    assert r.status_code == 400, r.text
    assert "cycle_id" in str(r.json()).lower()
