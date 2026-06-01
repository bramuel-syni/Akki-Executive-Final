"""P5.20 — Default-inbox cycle scaffolding lockdown.

Coverage:
  • New default-inbox cycle gets agenda + team seed in the same call.
  • Re-running the singleton getter does NOT duplicate the seeds
    (idempotent on agenda items + team members).
  • Backward-compat migration `backfill_default_inbox_cycles`
    creates seeds on pre-P5.20 cycles, idempotent on second run.
  • `inbox_routing_log` carries the `seed_action` audit rows only
    when seeding actually fired (not on no-op re-runs).
  • Cycle agenda endpoint returns `is_default_inbox_cycle: true`
    for the auto-scaffolded cycle and `false` for user cycles.
  • Existing user-curated cycles unaffected.
  • Voice-lint clean on the seed copy.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from services.inbox_routing import (
    backfill_default_inbox_cycles,
    get_or_create_default_inbox_context,
    get_or_create_default_inbox_cycle,
)


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _csrf_login(client: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    r = await client.get("/api/csrf")
    return {"Authorization": f"Bearer {token}",
            "X-CSRF-Token": r.json()["csrf_token"]}


async def _ensure_test_account(db, *, email: str) -> Dict[str, Any]:
    from core import hash_password
    acct = await db.accounts.find_one({"email": email}, {"_id": 0})
    if not acct:
        acct = {
            "id": "acct-p520-" + uuid.uuid4().hex[:10],
            "email": email, "name": "P5.20 test account",
            "password_hash": hash_password("P520Test!"),
            "declared_role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.accounts.insert_one(dict(acct))
    return acct


# ── New default-inbox cycle is seeded with agenda + member ───────


@pytest.mark.asyncio
async def test_new_default_inbox_cycle_carries_agenda_and_team_seeds():
    from core import db
    acct = await _ensure_test_account(db, email=f"seed-{uuid.uuid4().hex[:6]}@p520.example.com")
    ctx = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    cyc = await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    # Agenda row exists with the seed item.
    agenda = await db.agendas.find_one({"id": cyc["id"]}, {"_id": 0})
    assert agenda is not None
    seed_items = [it for it in (agenda.get("items") or [])
                  if it.get("is_default_inbox_item")]
    assert len(seed_items) == 1, agenda
    assert seed_items[0]["label"] == "Inbound from Email Akki"
    # Team member row exists with the primary admin.
    team_row = await db.cycle_team.find_one(
        {"cycle_id": cyc["id"], "account_id": acct["id"],
         "is_default_inbox_seed": True}, {"_id": 0},
    )
    assert team_row is not None


@pytest.mark.asyncio
async def test_get_or_create_default_inbox_cycle_is_idempotent_on_seeds():
    """Two consecutive calls must NOT duplicate agenda items or
    team rows."""
    from core import db
    acct = await _ensure_test_account(db, email=f"idem-{uuid.uuid4().hex[:6]}@p520.example.com")
    ctx = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    a = await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    b = await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    assert a["id"] == b["id"]
    # Exactly one seed agenda item.
    agenda = await db.agendas.find_one({"id": a["id"]}, {"_id": 0})
    seeds = [it for it in (agenda.get("items") or [])
             if it.get("is_default_inbox_item")]
    assert len(seeds) == 1, seeds
    # Exactly one team member row for this account.
    team_count = await db.cycle_team.count_documents(
        {"cycle_id": a["id"], "account_id": acct["id"]},
    )
    assert team_count == 1


# ── Audit-log seed_action entries ────────────────────────────────


@pytest.mark.asyncio
async def test_seed_writes_audit_rows_on_first_call_only():
    """First call writes 2 audit rows (agenda + member);
    second call writes 0."""
    from core import db
    acct = await _ensure_test_account(db, email=f"audit-{uuid.uuid4().hex[:6]}@p520.example.com")
    ctx = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    before = await db.inbox_routing_log.count_documents(
        {"account_id": acct["id"], "route_kind": "default_cycle_seed"},
    )
    await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    after = await db.inbox_routing_log.count_documents(
        {"account_id": acct["id"], "route_kind": "default_cycle_seed"},
    )
    assert after - before == 2, (
        f"First call must write 2 seed_action rows: before={before} after={after}"
    )
    # Second call → no new rows.
    await get_or_create_default_inbox_cycle(
        db, account_id=acct["id"], context_id=ctx["id"],
    )
    after2 = await db.inbox_routing_log.count_documents(
        {"account_id": acct["id"], "route_kind": "default_cycle_seed"},
    )
    # negative-leak: idempotent re-run MUST NOT write seed audit rows.
    assert after2 == after, (
        f"Second call leaked seed audit rows: before={after} after={after2}"
    )


# ── Backward-compat migration ────────────────────────────────────


@pytest.mark.asyncio
async def test_backfill_default_inbox_cycles_seeds_pre_p520_cycles():
    """Seed: insert a default-inbox cycle directly into Mongo
    WITHOUT the agenda/team scaffolding (simulating a pre-P5.20
    state). Run the backfill, assert the seeds land."""
    from core import db
    acct = await _ensure_test_account(db, email=f"bc-{uuid.uuid4().hex[:6]}@p520.example.com")
    ctx = await get_or_create_default_inbox_context(db, account_id=acct["id"])
    # Insert a NAKED default-inbox cycle (no agenda, no team).
    cyc_id = "cyc-pre-p520-" + uuid.uuid4().hex[:10]
    await db.cycles.insert_one({
        "id": cyc_id, "context_id": ctx["id"], "account_id": acct["id"],
        "name": "Naked pre-P5.20 cycle", "status": "open",
        "is_default_inbox_cycle": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    # Assert there's no agenda or team rows for this cycle yet.
    assert await db.agendas.find_one({"id": cyc_id}) is None
    assert await db.cycle_team.find_one({"cycle_id": cyc_id}) is None

    # Run backfill.
    first = await backfill_default_inbox_cycles(db)
    assert first["scanned"] >= 1
    assert first["agenda_seeded"] >= 1
    assert first["member_seeded"] >= 1
    # Agenda + team now exist.
    assert await db.agendas.find_one({"id": cyc_id}) is not None
    assert await db.cycle_team.find_one({"cycle_id": cyc_id}) is not None

    # Run again → zero net new seeds.
    second = await backfill_default_inbox_cycles(db)
    # negative-leak: backfill re-run MUST NOT seed already-seeded cycles.
    assert second["scanned"] == first["scanned"]
    assert second["agenda_seeded"] == 0
    assert second["member_seeded"] == 0


# ── Endpoint surface: is_default_inbox_cycle on /cycle/agenda ────


@pytest.mark.asyncio
async def test_agenda_endpoint_surfaces_default_inbox_flag(transport):
    """The agenda endpoint must surface `is_default_inbox_cycle: true`
    for default-inbox cycles so the FE wizard can skip team/agenda
    authoring steps."""
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    ctx = await get_or_create_default_inbox_context(db, account_id=admin["id"])
    cyc = await get_or_create_default_inbox_cycle(
        db, account_id=admin["id"], context_id=ctx["id"],
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get(
            f"/api/contexts/{ctx['id']}/cycle/agenda?cycle_id={cyc['id']}",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["is_default_inbox_cycle"] is True


@pytest.mark.asyncio
async def test_agenda_endpoint_returns_false_for_user_cycles(transport):
    """Existing user-curated cycles MUST report `is_default_inbox_cycle:
    false` so they continue to render through the full wizard."""
    from core import db
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0})
    # Pick a NON-default cycle. If there's one already in the dev DB
    # this is a no-op; otherwise we insert a minimal one for the assertion.
    user_cyc = await db.cycles.find_one(
        {"is_default_inbox_cycle": {"$ne": True}}, {"_id": 0, "id": 1, "context_id": 1},
    )
    if not user_cyc:
        cyc_id = "cyc-user-" + uuid.uuid4().hex[:8]
        ctx_id = "ctx-user-" + uuid.uuid4().hex[:8]
        await db.contexts.insert_one({
            "id": ctx_id, "account_id": admin["id"], "name": "user ctx",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.cycles.insert_one({
            "id": cyc_id, "context_id": ctx_id, "account_id": admin["id"],
            "name": "User cycle", "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Membership for admin in this context.
        await db.memberships.insert_one({
            "id": "mem-test-" + uuid.uuid4().hex[:8],
            "context_id": ctx_id, "account_id": admin["id"],
            "status": "active", "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        user_cyc = {"id": cyc_id, "context_id": ctx_id}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.get(
            f"/api/contexts/{user_cyc['context_id']}/cycle/agenda?cycle_id={user_cyc['id']}",
            headers=headers,
        )
        # 200 (admin has membership or owns the context) or 403
        # (admin isn't a member of a random tenant ctx). Either way
        # the flag MUST be false on success.
        if r.status_code == 200:
            assert r.json().get("is_default_inbox_cycle") is False


# ── Voice-lint + source-strict ───────────────────────────────────


def test_default_inbox_seed_copy_voice_lint_clean():
    """Seed copy must not carry banned vocabulary."""
    src = Path("/app/backend/services/inbox_routing/context_resolver.py").read_text(encoding="utf-8")
    banned = ["seamless", "AI-powered", "transform", "harness", "leverage"]
    for bad in banned:
        assert re.search(re.escape(bad), src, re.IGNORECASE) is None, bad
    # Lock the actual seed strings against accidental drift.
    assert '"Inbound from Email Akki"' in src
    assert '"Routed contributions from email arrive here for triage."' in src


def test_p5_20_audit_log_marker_in_source():
    src = Path("/app/backend/services/inbox_routing/context_resolver.py").read_text(encoding="utf-8")
    assert '"default_cycle_agenda"' in src
    assert '"default_cycle_member"' in src
    assert '"classifier_version": "p5.20.0"' in src
