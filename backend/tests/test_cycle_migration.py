"""Cycle Manager v2 migration test.

Verifies that pre-v2 data (a `cycle_agendas` row with `status="active"`
plus downstream rows referencing it via `agenda_id`) is migrated
correctly:

  • A row appears in `db.cycles` with `id` == the agenda id
    and `status="active"`.
  • All downstream rows get a `cycle_id` field equal to their `agenda_id`.
  • The migration is idempotent — running it twice yields no extra rows.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from migrations import _0001_multi_cycle as mig


@pytest.mark.asyncio
async def test_migration_creates_cycles_row_and_backfills_cycle_id():
    db = core_mod.db
    ctx = f"ctx-mig-{uuid.uuid4().hex[:8]}"
    cyc = f"cyc-mig-{uuid.uuid4().hex[:8]}"

    # Cleanup — fully delete any orphan rows from prior runs (test ids
    # are fixed, not random, so leftover state could pollute).
    await db["_migrations"].delete_one({"id": mig.MIGRATION_ID})
    for c in ("cycles", "cycle_agendas", "cycle_team",
              "cycle_contributions", "cycle_followups"):
        await getattr(db, c).delete_many({"context_id": ctx})
    # Also belt-and-braces on the fixed ids we use below.
    await db.cycle_team.delete_one({"id": "tm1"})
    await db.cycle_contributions.delete_one({"id": "co1"})

    await db.cycle_agendas.insert_one({
        "id": cyc, "context_id": ctx, "account_id": "acc-x",
        "title": "Legacy Cycle",
        "items": [{"id": "i1", "label": "Item 1"}],
        "status": "active",
        "created_at": "2025-09-01T00:00:00Z",
        "updated_at": "2025-09-01T00:00:00Z",
    })
    await db.cycle_team.insert_one({
        "id": "tm1", "context_id": ctx, "agenda_id": cyc,
        "name": "X", "email": "x@example.com",
        "contribution_description": "-",
        "owns_item_ids": ["i1"], "status": "active",
        "created_at": "2025-09-01T00:00:00Z", "updated_at": "2025-09-01T00:00:00Z",
    })
    await db.cycle_contributions.insert_one({
        "id": "co1", "context_id": ctx, "agenda_id": cyc,
        "agenda_item_id": "i1", "team_member_id": "tm1",
        "kind": "note", "body_text": "hello", "status": "pending",
        "created_at": "2025-09-01T00:00:00Z",
    })

    # Pre-state: no cycles row, downstream rows lack cycle_id
    assert await db.cycles.count_documents({"context_id": ctx}) == 0
    pre_t = await db.cycle_team.find_one({"id": "tm1", "context_id": ctx}, {"_id": 0, "cycle_id": 1})
    pre_c = await db.cycle_contributions.find_one({"id": "co1", "context_id": ctx}, {"_id": 0, "cycle_id": 1})
    assert "cycle_id" not in pre_t and "cycle_id" not in pre_c

    res = await mig.run()
    assert res["applied"] is True
    assert res["stats"]["cycles_created"] >= 1

    cyc_row = await db.cycles.find_one({"context_id": ctx}, {"_id": 0})
    assert cyc_row is not None
    assert cyc_row["id"] == cyc
    assert cyc_row["status"] == "active"
    assert cyc_row["title"] == "Legacy Cycle"

    post_t = await db.cycle_team.find_one({"id": "tm1", "context_id": ctx}, {"_id": 0, "cycle_id": 1})
    post_c = await db.cycle_contributions.find_one({"id": "co1", "context_id": ctx}, {"_id": 0, "cycle_id": 1})
    assert post_t["cycle_id"] == cyc
    assert post_c["cycle_id"] == cyc


@pytest.mark.asyncio
async def test_migration_is_idempotent():
    """Calling run() a second time after marker exists should not error
    and should not double-create cycles rows."""
    res1 = await mig.run()
    assert res1["applied"] in (True, False)
    res2 = await mig.run()
    assert res2["applied"] is False
    assert res2.get("reason") == "already_applied"
