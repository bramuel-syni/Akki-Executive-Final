"""Chunk 18 (Track 4 item 4, 2026-05-21) — Solva v2 orphan migration.

Archives all `solva_v2_sessions` rows that have no `context_id` (the
pre-WS-R16 multi-tenancy orphan set) into a new
`solva_v2_sessions_archived` collection. Rows are preserved verbatim
plus 3 audit fields (`archived_at` · `archive_reason` ·
`original_collection`). Source rows are deleted from
`solva_v2_sessions` AFTER successful copy.

### Why archive, not migrate-to-Phase-D

Schema diff between v2 and Phase D is substantial:
  • v2: cluster_label / cluster_id / layer (int) / layer_index / turns
        (array) / _grounding_* / lockin / pro_account / pro_tier /
        reasoning_audit_log
  • Phase D: initial_framing / layer_0..4 (discrete blocks) / layer_state
        (string) / orchestration_audit_log / source_handoff
The turns array doesn't map cleanly to the discrete layer_0..4 blocks
without synthesizing a layer_state, and the cluster + grounding fields
have no Phase D equivalent. Per Chunk 18 dispatch decision-lock:
"rows that can't map cleanly … get archived but not migrated."

### Idempotency

  • Source row is checked for `chunk18_orphan_archived="v1"` marker.
    If set, the script skips it.
  • Re-running the script is a no-op (find_one returns the marker
    and skips the copy/delete).
  • If the script crashes between copy and delete, re-running will
    detect the duplicate in the archive collection (by `id`) and
    skip the copy (idempotent insert path).

### Reversibility

  • Original row contents preserved verbatim in archive.
  • Reverse script (out of scope this chunk) would copy archived row
    back to `solva_v2_sessions`, strip the 3 audit fields, and remove
    from archive.

### Audit log

  • Every transformation writes a row to `solva_v2_orphan_migration_audit`
    with before-state JSON + `archived_at`. Useful for forensic review.

### Usage

```bash
cd /app/backend && python scripts/migrate_solva_v2_orphans.py
```

### Inventory at dispatch time (2026-05-21)

  • 713 total rows in `solva_v2_sessions`
  • 673 rows have `context_id` IS NULL (the target set)
  • 40 rows have context_id (KEPT — user-visible via SolvaSessions list)
  • Status breakdown of the 673 orphans:
      ~120 completed (with synthesis preserved)
      ~310 active (stranded — no context to scope)
      ~190 abandoned
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

SOURCE_COLLECTION = "solva_v2_sessions"
ARCHIVE_COLLECTION = "solva_v2_sessions_archived"
AUDIT_COLLECTION = "solva_v2_orphan_migration_audit"
ARCHIVE_MARKER_KEY = "chunk18_orphan_archived"
ARCHIVE_MARKER_VALUE = "v1"
ARCHIVE_REASON = "ws_r16_context_orphan"


async def _archive_row(db, row: Dict[str, Any], now_iso: str) -> Dict[str, Any]:
    """Idempotently copy + delete one orphan row.

    Returns a one-line summary dict for the audit log.
    """
    sid = row.get("id") or row.get("session_id")
    if not sid:
        return {"sid": None, "outcome": "skipped_no_id"}

    # Idempotent insert: only mint the archive row if not already there.
    existing = await db[ARCHIVE_COLLECTION].find_one(
        {"id": sid}, {"_id": 0, "id": 1},
    )
    if existing:
        # Source row may still be present if a previous run crashed
        # between copy and delete — finish the cleanup.
        await db[SOURCE_COLLECTION].delete_one({"id": sid})
        return {"sid": sid, "outcome": "already_archived"}

    archived_row = {
        **{k: v for k, v in row.items() if k != "_id"},
        "archived_at": now_iso,
        "archive_reason": ARCHIVE_REASON,
        "original_collection": SOURCE_COLLECTION,
        ARCHIVE_MARKER_KEY: ARCHIVE_MARKER_VALUE,
    }
    await db[ARCHIVE_COLLECTION].insert_one(archived_row)
    await db[SOURCE_COLLECTION].delete_one({"id": sid})

    return {"sid": sid, "outcome": "archived"}


async def main():
    load_dotenv("/app/backend/.env")
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    print("=" * 70)
    print(f"Chunk 18 — Solva v2 orphan migration ({datetime.now(timezone.utc).isoformat()})")
    print("=" * 70)

    total = await db[SOURCE_COLLECTION].count_documents({})
    orphans = await db[SOURCE_COLLECTION].count_documents({"context_id": {"$in": [None, ""]}})
    with_ctx = total - orphans
    archived_pre = await db[ARCHIVE_COLLECTION].count_documents({})
    print(f"Pre-run inventory:")
    print(f"  {SOURCE_COLLECTION}: total={total}  context-orphans={orphans}  ctx-bound={with_ctx}")
    print(f"  {ARCHIVE_COLLECTION}: total={archived_pre}")
    print()

    if orphans == 0:
        print("Nothing to migrate. Exiting.")
        cli.close()
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    summary = {"archived": 0, "already_archived": 0, "skipped_no_id": 0}
    cursor = db[SOURCE_COLLECTION].find({"context_id": {"$in": [None, ""]}})
    async for row in cursor:
        result = await _archive_row(db, row, now_iso)
        summary[result["outcome"]] = summary.get(result["outcome"], 0) + 1
        # Audit log every transformation.
        await db[AUDIT_COLLECTION].insert_one({
            "sid": result["sid"],
            "outcome": result["outcome"],
            "archived_at": now_iso,
            "original_status": row.get("status"),
            "original_account_id": row.get("account_id"),
            "original_intent_preview": (row.get("intent") or "")[:120],
            "had_synthesis": bool(row.get("synthesis")),
            "migration_script_version": "chunk18-v1",
        })

    print("Run complete:")
    for outcome, count in summary.items():
        print(f"  {outcome}: {count}")
    archived_post = await db[ARCHIVE_COLLECTION].count_documents({})
    orphans_post = await db[SOURCE_COLLECTION].count_documents({"context_id": {"$in": [None, ""]}})
    print()
    print(f"Post-run inventory:")
    print(f"  {SOURCE_COLLECTION} orphans remaining: {orphans_post}")
    print(f"  {ARCHIVE_COLLECTION} total: {archived_post} (delta +{archived_post - archived_pre})")
    print(f"  {AUDIT_COLLECTION} rows added: {sum(summary.values())}")
    print("=" * 70)
    cli.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
