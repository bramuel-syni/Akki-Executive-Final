"""Chunk 18.5 (Track 4 item 4, 2026-05-21) — Solva legacy → Phase D
session migration script. DORMANT BY DESIGN.

Status on 2026-05-21: the source collection (`solva_sessions`) is
empty on the live preview per
`scripts/probe_solva_legacy_orphans.py`. This script ships
ready-to-run for the day a future seed accidentally re-introduces
legacy rows, and is exercised in tests via the dry-run path.

Contract
========
- Idempotent — source rows acquire a `legacy_to_phase_d_migrated_at`
  marker so re-runs skip already-migrated rows.
- Reversible — original source row is preserved in
  `solva_sessions_archived` BEFORE the destination row is written.
- Audited — every row writes one entry to `solva_migration_audit`
  with before-JSON + after-JSON + status (`migrated` / `archived_only`
  / `skipped`).
- Unmappable rows → archived only (not migrated). Count documented in
  the audit log.

Usage
=====
  Dry-run (NO writes; counts only):
      python -m scripts.migrate_solva_legacy_to_phase_d --dry-run

  Live:
      python -m scripts.migrate_solva_legacy_to_phase_d

Acceptance lock
===============
Per Chunk 18.5 dispatch: rows that can't map cleanly to Phase D
schema → archive but don't migrate. Required Phase D fields (per
`routers/solva_phase_d.py::COLLECTION`):
  - id (uuid)
  - account_id
  - context_id  ← if this is missing the row CANNOT migrate
  - status      ← legacy `state` mapped where possible
  - phase_d_started_at
  - layers (object)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient


SOURCE = "solva_sessions"
DEST = "solva_phase_d_sessions"
ARCHIVE = "solva_sessions_archived"
AUDIT = "solva_migration_audit"

MIGRATION_MARKER = "legacy_to_phase_d_migrated_at"


# Legacy `state` values → Phase D `status` mapping. Anything we don't
# explicitly know stays in `status: "unknown"` and the destination row
# carries a `legacy_state` field for forensic review.
_STATE_MAP = {
    "active": "active",
    "paused": "paused",
    "complete": "complete",
    "completed": "complete",
    "refused": "refused",
    "abandoned": "refused",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _try_map_to_phase_d(legacy: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Return (mappable, phase_d_row).

    Mappable iff the legacy row has account_id AND context_id (everything
    else can be defaulted). If unmappable, the second element is `{}`.
    """
    ctx = legacy.get("context_id")
    acc = legacy.get("account_id")
    if not ctx or not acc:
        return (False, {})
    legacy_state = (legacy.get("state") or legacy.get("status") or "").lower()
    status = _STATE_MAP.get(legacy_state, "unknown")
    phase_d = {
        "id": legacy.get("id") or f"phd-legacy-{uuid.uuid4().hex[:12]}",
        "account_id": acc,
        "context_id": ctx,
        "status": status,
        "legacy_state": legacy_state or None,
        "phase_d_started_at": legacy.get("started_at") or _now_iso(),
        "layers": legacy.get("layers") or {},
        "intent": legacy.get("intent") or legacy.get("title") or "",
        "migrated_from": SOURCE,
        "migrated_at": _now_iso(),
    }
    return (True, phase_d)


async def _archive_one(db, legacy: Dict[str, Any]) -> None:
    """Write the original legacy row to `solva_sessions_archived` so
    the migration is reversible. Idempotent on `id`."""
    snapshot = {**legacy, "archived_via": "legacy_to_phase_d_migration"}
    snapshot.pop("_id", None)
    await db[ARCHIVE].update_one(
        {"id": legacy.get("id")},
        {"$setOnInsert": snapshot},
        upsert=True,
    )


async def _audit(
    db, *,
    legacy_id: str, status: str,
    before: Dict[str, Any], after: Dict[str, Any] | None,
    reason: str | None = None,
) -> None:
    await db[AUDIT].insert_one({
        "legacy_id": legacy_id,
        "status": status,  # "migrated" | "archived_only" | "skipped"
        "reason": reason,
        "before": before,
        "after": after,
        "recorded_at": _now_iso(),
    })


async def migrate(*, dry_run: bool = False) -> Dict[str, Any]:
    """Walk every row in `solva_sessions` that lacks the migration
    marker; archive + (if mappable) migrate.

    Returns counters: `total`, `already_migrated`, `migrated`,
    `archived_only`, `skipped`.
    """
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    try:
        db = client[db_name]
        counters = {
            "total": 0, "already_migrated": 0,
            "migrated": 0, "archived_only": 0, "skipped": 0,
        }
        async for legacy in db[SOURCE].find({}):
            counters["total"] += 1
            legacy.pop("_id", None)
            if legacy.get(MIGRATION_MARKER):
                counters["already_migrated"] += 1
                continue

            mappable, phase_d = _try_map_to_phase_d(legacy)
            if dry_run:
                if mappable:
                    counters["migrated"] += 1
                else:
                    counters["archived_only"] += 1
                continue

            try:
                # Always archive first — reversible by design.
                await _archive_one(db, legacy)

                if mappable:
                    await db[DEST].update_one(
                        {"id": phase_d["id"]},
                        {"$setOnInsert": phase_d},
                        upsert=True,
                    )
                    await db[SOURCE].update_one(
                        {"id": legacy["id"]},
                        {"$set": {MIGRATION_MARKER: _now_iso()}},
                    )
                    await _audit(
                        db, legacy_id=legacy.get("id") or "(no-id)",
                        status="migrated", before=legacy, after=phase_d,
                    )
                    counters["migrated"] += 1
                else:
                    await db[SOURCE].update_one(
                        {"id": legacy.get("id")},
                        {"$set": {
                            MIGRATION_MARKER: _now_iso(),
                            "archived_only_at": _now_iso(),
                            "archived_only_reason": "missing required Phase D fields",
                        }},
                    )
                    await _audit(
                        db, legacy_id=legacy.get("id") or "(no-id)",
                        status="archived_only", before=legacy, after=None,
                        reason="missing account_id or context_id",
                    )
                    counters["archived_only"] += 1
            except Exception as exc:  # noqa: BLE001
                await _audit(
                    db, legacy_id=legacy.get("id") or "(no-id)",
                    status="skipped", before=legacy, after=None,
                    reason=f"{type(exc).__name__}: {str(exc)[:200]}",
                )
                counters["skipped"] += 1
        return counters
    finally:
        client.close()


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="count only; no writes")
    args = parser.parse_args()
    result = asyncio.run(migrate(dry_run=args.dry_run))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()
