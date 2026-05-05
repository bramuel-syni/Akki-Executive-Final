"""Phase M.2 — Document Journal source_channel backfill.

Idempotent. Adds `source_channel` to every existing document row,
deriving it from the doc's existing fields:

  • Documents whose `source` already matches one of the canonical
    channels (`upload`, `inbound_email`, `share`, `sandbox`,
    `strategic_pack_v1`) are tagged accordingly.
  • Documents with `inbound_message_id` or `inbound_queue_id` → "inbound_email".
  • Documents with `share_id` → "share".
  • Documents whose context has type "sandbox" → "sandbox".
  • Everything else → "upload".

The strategic-pack docs (Phase L) keep their `source = "strategic_pack_v1"`
and gain `source_channel = "upload"` (they were ingested via the seed
script, which is logically an upload-class operation).

Usage:
    python3 backend/scripts/migrate_phase_m2_source_channel.py
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

    print("─" * 64)
    print(" Phase M.2 — source_channel backfill on documents")
    print("─" * 64)

    n_total = await db.documents.count_documents({})
    n_to_backfill = await db.documents.count_documents(
        {"source_channel": {"$exists": False}},
    )
    print(f"  documents total:           {n_total}")
    print(f"  needing source_channel:    {n_to_backfill}")

    counts = {"upload": 0, "inbound_email": 0, "share": 0, "sandbox": 0}
    async for d in db.documents.find(
        {"source_channel": {"$exists": False}},
        {"_id": 0, "id": 1, "context_id": 1, "inbound_message_id": 1,
         "inbound_queue_id": 1, "share_id": 1, "source": 1},
    ):
        if d.get("inbound_message_id") or d.get("inbound_queue_id"):
            channel = "inbound_email"
        elif d.get("share_id"):
            channel = "share"
        else:
            ctx = await db.contexts.find_one(
                {"id": d.get("context_id")}, {"_id": 0, "type": 1},
            )
            if ctx and ctx.get("type") == "sandbox":
                channel = "sandbox"
            else:
                channel = "upload"
        counts[channel] += 1
        await db.documents.update_one(
            {"id": d["id"]}, {"$set": {"source_channel": channel}},
        )

    print("─" * 64)
    print(f"  upload:        {counts['upload']}")
    print(f"  inbound_email: {counts['inbound_email']}")
    print(f"  share:         {counts['share']}")
    print(f"  sandbox:       {counts['sandbox']}")
    print("─" * 64)

    # Index: query pattern is `(context_id, created_at desc)` for the
    # journal listing — already exists from server.py boot. Add a sparse
    # index on source_channel for the "filter by inbound" facet.
    await db.documents.create_index([("context_id", 1), ("source_channel", 1)])
    print("  ✚ index ensured: (context_id, source_channel)")

    print("─" * 64)
    print("✅ M.2 backfill complete.")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
