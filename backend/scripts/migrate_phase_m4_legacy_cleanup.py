"""Phase M.4 — legacy Mongo cleanup migration.

Idempotent. Safe to re-run on dev / staging / prod.

Renames the 6 `solve_*` collections (kept as-is for migration safety
through Phases A → L) to `solva_v1_*_archive` so they're visibly
read-only forensic stores. Also `$unset`s the partially-decommissioned
`solva_v2_poc` field from every account document.

`renameCollection` preserves all indexes — the underlying TTLs and
unique constraints stay intact.

Usage:
    python3 backend/scripts/migrate_phase_m4_legacy_cleanup.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

# Source → target renames. Order doesn't matter; renameCollection is
# atomic per-collection.
#
# `solve_clusters` and `solve_handoffs` are *alive* — Solva v2 reads
# both at runtime (cluster taxonomy + cycle handoff queue). They get
# renamed to canonical v2 names, not the `_archive` suffix.
# The other four are pure v1 forensic stores and move to `_archive`.
RENAMES: dict[str, str] = {
    # Live → canonical v2 names
    "solve_clusters":     "solva_clusters",
    "solve_handoffs":     "solva_handoffs",
    # V1-only → forensic archive
    "solve_comparables":  "solva_v1_comparables_archive",
    "solve_sessions":     "solva_v1_sessions_archive",
    "solve_free_grants":  "solva_v1_free_grants_archive",
    "solve_interest":     "solva_v1_interest_archive",
    # Recovery from an earlier intermediate state where the live
    # collections were renamed to `_archive` before the canonical
    # naming was picked. Idempotent: only fires if these still exist.
    "solva_v1_clusters_archive": "solva_clusters",
    "solva_v1_handoffs_archive": "solva_handoffs",
}


async def main() -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    db_name = os.environ["DB_NAME"]

    print("─" * 64)
    print(" Phase M.4 — legacy Mongo cleanup migration")
    print("─" * 64)
    # 1. Collection renames — re-read existing-collection list each
    #    iteration so we see the effects of prior renames in the same run.
    for src, dst in RENAMES.items():
        existing = set(await db.list_collection_names())
        if src in existing and dst not in existing:
            n = await db[src].count_documents({})
            await client.admin.command(
                "renameCollection",
                f"{db_name}.{src}",
                to=f"{db_name}.{dst}",
            )
            print(f"  ✚ renamed   {src:32} → {dst:32}  ({n} rows)")
        elif dst in existing and src not in existing:
            print(f"  ↺ already renamed:  {dst}")
        elif src in existing and dst in existing:
            # Both exist — merge src into dst and drop src.
            n_src = await db[src].count_documents({})
            n_dst = await db[dst].count_documents({})
            if n_src > 0:
                docs = [d async for d in db[src].find({})]
                if docs:
                    # Best-effort insert — ignore unique-index collisions
                    # (re-running the migration shouldn't fail because a
                    # row already exists in the destination).
                    try:
                        await db[dst].insert_many(docs, ordered=False)
                    except Exception as e:  # noqa: BLE001
                        print(f"    (insert_many partial: {str(e)[:80]})")
            await db[src].drop()
            print(f"  ↺ merged + dropped: {src} ({n_src}) → {dst} (was {n_dst})")
        else:
            print(f"  ⊘ neither present:  {src} / {dst}")

    # 2. $unset solva_v2_poc on accounts
    n_to_unset = await db.accounts.count_documents({"solva_v2_poc": {"$exists": True}})
    if n_to_unset:
        r = await db.accounts.update_many(
            {"solva_v2_poc": {"$exists": True}},
            {"$unset": {"solva_v2_poc": ""}},
        )
        print(f"  ✚ accounts.solva_v2_poc unset on {r.modified_count}/{n_to_unset} docs")
    else:
        print(f"  ↺ accounts.solva_v2_poc already absent on every account")

    print("─" * 64)
    print("✅ M.4 migration complete.")
    print("─" * 64)
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
