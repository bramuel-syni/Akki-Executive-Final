"""Phase M.3 — briefings → boardpacks rename + schema enrichment.

Idempotent. Safe to re-run on dev / staging / prod.

Steps:
  1. Rename collection `briefings` → `boardpacks` (preserves indexes).
  2. Add the boardpack schema fields to every row, deriving them from
     existing fields where possible:
        commentary                 ← body (existing per-doc commentary
                                     becomes the boardpack-level
                                     commentary; legacy body field stays
                                     intact as `body_legacy` for trace)
        commentary_synisense_version ← synisense_version
        cycle_id                   ← null (existing rows have no cycle FK)
        cycle_label                ← "Uncycled · " + created_at month/year
        document_ids               ← []  (existing rows have no doc list)
  3. Create the (context_id, cycle_id) compound index — sparse so the
     null-cycle existing rows don't trip it.

The legacy `briefings.{briefing_id}` URL keeps working — the new
`boardpack.py` router keeps a `/api/contexts/{cid}/briefings/...`
backward-compat alias for 30 days (M.3 spec).
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


async def main() -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    db_name = os.environ["DB_NAME"]

    print("─" * 72)
    print(" Phase M.3 — briefings → boardpacks migration")
    print("─" * 72)
    existing = set(await db.list_collection_names())

    if "briefings" in existing and "boardpacks" not in existing:
        n = await db.boardpacks.count_documents({})
        await client.admin.command(
            "renameCollection",
            f"{db_name}.briefings",
            to=f"{db_name}.boardpacks",
        )
        print(f"  ✚ renamed briefings → boardpacks  ({n} rows)")
    elif "boardpacks" in existing and "briefings" in existing:
        # Both present — merge briefings into boardpacks then drop.
        docs = [d async for d in db.boardpacks.find({})]
        if docs:
            try:
                await db.boardpacks.insert_many(docs, ordered=False)
            except Exception as e:  # noqa: BLE001
                print(f"    (insert_many partial: {str(e)[:80]})")
        await db.boardpacks.drop()
        print(f"  ↺ merged briefings ({len(docs)}) into boardpacks; dropped briefings")
    elif "boardpacks" in existing:
        print(f"  ↺ boardpacks already exists ({await db.boardpacks.count_documents({})} rows)")
    else:
        print(f"  ⊘ neither briefings nor boardpacks present — empty DB")

    # 2. Enrich rows that don't yet carry the M.3 schema fields.
    n_to_enrich = await db.boardpacks.count_documents({"commentary": {"$exists": False}})
    print(f"  enriching {n_to_enrich} rows with M.3 schema fields...")
    enriched = 0
    async for row in db.boardpacks.find(
        {"commentary": {"$exists": False}},
        {"_id": 0, "id": 1, "body": 1, "body_redacted": 1,
         "synisense_version": 1, "created_at": 1, "title": 1},
    ):
        created_at = row.get("created_at") or ""
        # "Uncycled · 2026-04" cadence. Falls back to "Uncycled" when
        # created_at is missing.
        try:
            label_suffix = created_at[:7] if created_at else ""
        except Exception:  # noqa: BLE001
            label_suffix = ""
        cycle_label = f"Uncycled · {label_suffix}" if label_suffix else "Uncycled"

        update = {
            "commentary": row.get("body") or "",
            "commentary_redacted": row.get("body_redacted") or "",
            "commentary_synisense_version": row.get("synisense_version", 0),
            "cycle_id": None,
            "cycle_label": cycle_label,
            "document_ids": [],
            "schema_version": 1,
        }
        await db.boardpacks.update_one({"id": row["id"]}, {"$set": update})
        enriched += 1
    print(f"  ✚ enriched {enriched} rows with M.3 schema fields")

    # 3. Indexes
    await db.boardpacks.create_index(
        [("context_id", 1), ("cycle_id", 1)],
        sparse=True,
    )
    await db.boardpacks.create_index([("context_id", 1), ("created_at", -1)])
    print("  ✚ indexes ensured: (context_id, cycle_id) sparse, (context_id, created_at desc)")

    print("─" * 72)
    print("✅ M.3 migration complete.")
    print(f"   boardpacks total rows: {await db.boardpacks.count_documents({})}")
    print("─" * 72)
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
