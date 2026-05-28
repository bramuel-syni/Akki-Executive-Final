"""AA.followup.5 (2026-02) — owner-role retrofit migration.

Reconciles legacy `owner_role` values across the `tasks_initiatives`
collection (and any future collections that store the field) with the
canonical AA-slice-1 `TIOwnerRole` enum:

    ("CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER")  + None

What this script does:
    1. Discovers all rows in `tasks_initiatives` (and `objectives` /
       `projects` for safety) that carry a non-null `owner_role`.
    2. For each row, uppercases the value and remaps legacy synonyms:
         - "CCO" → "OTHER"
         - "Audit Committee" / "Risk Committee" / any non-canonical
           string → "OTHER"
    3. Idempotent: a second run is a no-op (all values already in the
       canonical set are skipped).
    4. Dry-run by default. Pass `--apply` to actually persist updates.

Usage:
    python -m backend.scripts.migrate_aa_followup_5_owner_roles            # dry-run
    python -m backend.scripts.migrate_aa_followup_5_owner_roles --apply    # persist
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient


# Match the AA-slice-1 TIOwnerRole enum (do not change without also
# bumping `routers/tasks_initiatives.py::TIOwnerRole`).
CANONICAL_TOKENS: tuple[str, ...] = (
    "CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER",
)
_CANONICAL_SET = set(CANONICAL_TOKENS)

# Legacy synonyms that map to specific canonical tokens. Anything not
# in this dict and not already canonical falls back to "OTHER".
_LEGACY_REMAP: Dict[str, str] = {
    "CCO": "OTHER",
    "AUDIT COMMITTEE": "OTHER",
    "RISK COMMITTEE": "OTHER",
}


def _canonicalize(raw: Optional[str]) -> Optional[str]:
    """Return the canonical token for `raw`, or None if the input is
    None / empty. Anything we can't map cleanly collapses to "OTHER"."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    upper = s.upper()
    if upper in _CANONICAL_SET:
        return upper
    if upper in _LEGACY_REMAP:
        return _LEGACY_REMAP[upper]
    return "OTHER"


# Collections that may store a stored `owner_role` field. (monitor_v2
# objectives/projects derive owner_role at $lookup time from
# accounts.declared_role and don't store it — but defensively include
# them in case any data has been backfilled.)
TARGET_COLLECTIONS: tuple[str, ...] = (
    "tasks_initiatives",
    "objectives",
    "projects",
)


async def run(apply_changes: bool) -> Dict[str, Dict[str, int]]:
    """Walk each target collection, compute the would-be updates, and
    print a per-collection summary. With --apply, writes the updates.

    Returns a dict shaped:
        {
          "tasks_initiatives": {
            "scanned": 42, "already_canonical": 38, "remapped": 4, "noop": 0
          }, ...
        }
    """
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("ERROR: MONGO_URL and DB_NAME must be set in env.")
        sys.exit(2)
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    summary: Dict[str, Dict[str, int]] = {}

    for coll_name in TARGET_COLLECTIONS:
        coll = db[coll_name]
        scanned = 0
        already_canonical = 0
        remapped = 0
        cursor = coll.find(
            {"owner_role": {"$exists": True, "$ne": None}},
            {"_id": 0, "id": 1, "owner_role": 1},
        )
        async for row in cursor:
            scanned += 1
            raw = row.get("owner_role")
            new = _canonicalize(raw)
            if new == raw:
                already_canonical += 1
                continue
            remapped += 1
            print(
                f"  [{coll_name}] id={row.get('id')!r}  "
                f"{raw!r:>20} → {new!r}"
            )
            if apply_changes:
                await coll.update_one(
                    {"id": row.get("id")},
                    {"$set": {"owner_role": new}},
                )

        summary[coll_name] = {
            "scanned": scanned,
            "already_canonical": already_canonical,
            "remapped": remapped,
        }
        print(
            f"[{coll_name}] scanned={scanned}  "
            f"already_canonical={already_canonical}  "
            f"remapped={remapped}"
        )

    client.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist updates. Without this flag the script is a "
        "dry-run (prints what would change but writes nothing).",
    )
    args = parser.parse_args()
    print(
        f"AA.followup.5 owner-role retrofit migration — "
        f"{'APPLY' if args.apply else 'DRY-RUN'} mode\n"
    )
    asyncio.run(run(apply_changes=args.apply))
    print("\nDone.")


if __name__ == "__main__":
    main()
