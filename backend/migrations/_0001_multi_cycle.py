"""Migration 0001 — Multi-cycle pivot.

Idempotent. Runs once per server startup, gated by the `_migrations`
collection marker `{"id": "0001_multi_cycle", "applied_at": iso}`.

Walks every distinct `context_id` in `cycle_agendas`. For each, creates
a row in the new `cycles` collection with the same id as the agenda
(preserves the existing FK chain for `cycle_team` / `cycle_contributions`
/ `cycle_followups` which all join via `agenda_id` = the cycle id).

Existing cycles are stamped as `status="active"` per PO decision #3.

Also backfills `cycle_id` field on every cycle-scoped row that
references an `agenda_id`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Set

from core import db, iso, now

MIGRATION_ID = "0001_multi_cycle"
logger = logging.getLogger("akki.migration.0001_multi_cycle")


async def _already_applied() -> bool:
    row = await db["_migrations"].find_one({"id": MIGRATION_ID}, {"_id": 0, "applied_at": 1})
    return bool(row)


async def _mark_applied(stats: Dict[str, int]) -> None:
    await db["_migrations"].update_one(
        {"id": MIGRATION_ID},
        {"$set": {
            "id": MIGRATION_ID,
            "applied_at": iso(now()),
            "stats": stats,
        }},
        upsert=True,
    )


async def _backfill_cycle_id_field(stats: Dict[str, int]) -> None:
    """Stamp `cycle_id` onto every cycle-scoped row that's missing it.

    For each row where `cycle_id` is absent, copy the value from
    `agenda_id` (the legacy join key) if present.
    """
    for coll in ("cycle_team", "cycle_contributions", "cycle_followups",
                 "cycle_compilations", "cycle_assignments"):
        c = getattr(db, coll)
        # Skip if collection has no rows at all (motor returns 0 quickly).
        if await c.count_documents({"cycle_id": {"$exists": False}}, limit=1) == 0:
            continue
        # Mongo update_many with $expr — but motor/pymongo doesn't support
        # `$expr` inside `$set` directly for copying a field, so use a
        # cursor loop. Bulk-batched.
        async for row in c.find(
            {"cycle_id": {"$exists": False}, "agenda_id": {"$exists": True}},
            {"_id": 1, "agenda_id": 1},
        ):
            await c.update_one(
                {"_id": row["_id"]},
                {"$set": {"cycle_id": row["agenda_id"]}},
            )
            stats[f"backfilled_{coll}"] = stats.get(f"backfilled_{coll}", 0) + 1


async def run() -> Dict[str, Any]:
    """Apply the migration. Idempotent.

    Returns a small stats dict for logging."""
    if await _already_applied():
        return {"applied": False, "reason": "already_applied"}

    stats: Dict[str, int] = {
        "cycles_created": 0,
        "contexts_scanned": 0,
    }

    # Gather every distinct context_id that already has cycle data.
    context_ids: Set[str] = set()
    for coll in ("cycle_agendas", "cycle_team", "cycle_contributions"):
        c = getattr(db, coll)
        async for r in c.find({}, {"_id": 0, "context_id": 1}):
            if r.get("context_id"):
                context_ids.add(r["context_id"])

    for cid in context_ids:
        stats["contexts_scanned"] += 1
        # Skip if this context already has a row in the new `cycles`
        # collection (defensive — should not happen on first run).
        existing = await db.cycles.count_documents({"context_id": cid})
        if existing > 0:
            continue

        agenda = await db.cycle_agendas.find_one(
            {"context_id": cid},
            {"_id": 0, "id": 1, "title": 1, "items": 1, "created_at": 1, "account_id": 1},
            sort=[("created_at", 1)],
        )
        if not agenda:
            # Context has cycle_team / contributions but no agenda?
            # Skip — we can't infer a cycle id reliably.
            continue
        cycle_id = agenda["id"]
        # Title preference: existing agenda title → first item label → "Cycle 1"
        title = (agenda.get("title") or "").strip()
        if not title:
            items = agenda.get("items") or []
            if items and isinstance(items, list):
                title = ((items[0] or {}).get("label") or "").strip()
        if not title:
            title = "Cycle 1"

        created_at = agenda.get("created_at") or iso(now())
        row = {
            "id": cycle_id,
            "context_id": cid,
            "account_id": agenda.get("account_id"),
            "title": title,
            "status": "active",
            "created_at": created_at,
            "activated_at": created_at,
            "closed_at": None,
            "migrated_from": "single_cycle_legacy",
        }
        await db.cycles.insert_one(row)
        stats["cycles_created"] += 1

    await _backfill_cycle_id_field(stats)

    await _mark_applied(stats)
    logger.info(
        "migration 0001_multi_cycle applied: %s",
        {k: v for k, v in stats.items() if v},
    )
    return {"applied": True, "stats": stats}
