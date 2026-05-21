"""Chunk 18.5 (Track 4 item 4, 2026-05-21) — Solva legacy-orphan probe.

Read-only diagnostic. Prints the three Solva collection counts plus any
non-zero legacy orphan rows so operators can verify whether a
migration is actually needed.

Usage::

    cd /app/backend && python -m scripts.probe_solva_legacy_orphans

Result is also returned as a dict from `probe()` for programmatic use
(see `tests/test_qa_chunk_18_5.py::test_chunk18_5_solva_legacy_orphan_count_is_zero`).

Why this exists
===============
The Phase E soft-archive (`routers/solva_phase_e_polish.py`) flipped
the orphan source collection (`solva_sessions`) to soft-archived state.
Subsequent operational tasks have since cleared the collection
entirely on the live preview (`pending_orphans = archived_orphans = 0`).
Documenting this empty state means future agents don't re-investigate
phantom orphan counts (the original brief said 541, POST_REWRITE_RAMP
said 524 — both stale).

A dormant migration script lives next to this one
(`migrate_solva_legacy_to_phase_d.py`) for the day a future seed
accidentally re-introduces legacy rows.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


COLLECTIONS = (
    "solva_sessions",         # legacy (pre-Phase-D) — orphan SOURCE
    "solva_phase_d_sessions", # Phase D canonical — orphan DESTINATION
    "solva_v2_sessions",      # v2 orchestration runs — active path
)


async def probe(mongo_url: str = "", db_name: str = "") -> Dict[str, Any]:
    """Read-only count probe.

    Returns:
      {
        collection_name: {
            "total": int, "with_context": int, "without_context": int,
            "archived": int,
        },
        ...
        "summary": {"pending_orphans": int, "archived_orphans": int},
      }
    """
    mongo_url = mongo_url or os.environ["MONGO_URL"]
    db_name = db_name or os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    try:
        db = client[db_name]
        out: Dict[str, Any] = {}
        for col in COLLECTIONS:
            total = await db[col].count_documents({})
            with_ctx = await db[col].count_documents({
                "context_id": {"$exists": True, "$nin": [None, ""]},
            })
            without_ctx = await db[col].count_documents({
                "$or": [
                    {"context_id": {"$exists": False}},
                    {"context_id": None},
                    {"context_id": ""},
                ],
            })
            archived = await db[col].count_documents(
                {"archived_at": {"$exists": True}},
            )
            out[col] = {
                "total": total,
                "with_context": with_ctx,
                "without_context": without_ctx,
                "archived": archived,
            }
        # Phase E orphan definition: in `solva_sessions`, rows with no
        # context_id AND not already archived.
        pending = await db["solva_sessions"].count_documents({
            "$or": [
                {"context_id": {"$exists": False}},
                {"context_id": None},
                {"context_id": ""},
            ],
            "archived_at": {"$exists": False},
        })
        archived_orphans = await db["solva_sessions"].count_documents(
            {"archived_at": {"$exists": True}},
        )
        out["summary"] = {
            "pending_orphans": pending,
            "archived_orphans": archived_orphans,
            "migration_needed": pending > 0,
        }
        return out
    finally:
        client.close()


def _print_report(result: Dict[str, Any]) -> None:
    print("=" * 60)
    print("Solva legacy orphan probe (Chunk 18.5)")
    print("=" * 60)
    for col in COLLECTIONS:
        c = result[col]
        print(f"\n{col}:")
        print(f"  total           : {c['total']}")
        print(f"  with_context    : {c['with_context']}")
        print(f"  without_context : {c['without_context']}")
        print(f"  archived        : {c['archived']}")
    s = result["summary"]
    print("\n" + "-" * 60)
    print("Summary:")
    print(f"  pending_orphans   : {s['pending_orphans']}")
    print(f"  archived_orphans  : {s['archived_orphans']}")
    print(f"  migration_needed  : {s['migration_needed']}")
    print("-" * 60)


if __name__ == "__main__":
    result = asyncio.run(probe())
    _print_report(result)
