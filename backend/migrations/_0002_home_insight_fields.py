"""Migration 0002 — Home v2 insight schema fields.

Idempotent. Runs once per server startup, gated by `_migrations` marker
`{"id": "0002_home_insight_fields"}`.

Adds two schema affordances that power the Home 2 leading-insight cards:

  1. `cycles.expected_close_at`           — ISO date or null. Optional on
     existing rows; existing rows are LEFT as null (we don't auto-fill —
     the count just won't include cycles without a close date, which is
     correct behaviour per Patch 10 spec).

  2. `cycle_questions.assignee_account_id` — account id or null. Optional
     on existing rows; existing rows are LEFT as null.

This migration is purely schema-documentation + index. There is no
in-place data rewrite. Indexes added:

  - `cycles(context_id, expected_close_at)` for the `cycles_closing` count
  - `cycle_questions(context_id, assignee_account_id, status)` for the
    `open_questions` count
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from core import db, iso, now

MIGRATION_ID = "0002_home_insight_fields"
logger = logging.getLogger("akki.migration.0002_home_insight_fields")


async def _already_applied() -> bool:
    row = await db["_migrations"].find_one(
        {"id": MIGRATION_ID}, {"_id": 0, "applied_at": 1},
    )
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


async def run() -> Dict[str, Any]:
    if await _already_applied():
        return {"applied": False, "reason": "already_applied"}

    stats: Dict[str, int] = {
        "cycles_seen": 0,
        "questions_seen": 0,
    }

    # Diagnostic counts so the marker carries an audit trail.
    stats["cycles_seen"] = await db.cycles.count_documents({})
    stats["questions_seen"] = await db.cycle_questions.count_documents({})

    # Add indexes (idempotent — Mongo no-ops when the index already exists).
    await db.cycles.create_index(
        [("context_id", 1), ("expected_close_at", 1)],
        name="ix_cycles_expected_close_at",
    )
    await db.cycle_questions.create_index(
        [("context_id", 1), ("assignee_account_id", 1), ("status", 1)],
        name="ix_cycle_questions_assignee",
    )
    stats["indexes_created"] = 2

    await _mark_applied(stats)
    logger.info(
        "migration 0002_home_insight_fields applied: %s",
        {k: v for k, v in stats.items() if v},
    )
    return {"applied": True, "stats": stats}
