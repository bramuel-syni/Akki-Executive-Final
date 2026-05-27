"""Phase I.5 (2026-05-27) — One-shot backfill for `asker_role`.

Iterates all `cycle_questions` documents where `asker_role` is absent
or None. For each, derives the bucket via
`services.open_questions.asker_role_map.derive_asker_role` and writes
the result.

Idempotent: re-running after a successful pass is a no-op because the
match filter `{asker_role: {$in: [None, missing]}}` skips already-set
rows.

Counts logged:
  • Total scanned
  • Per-bucket (board / ceo / team)
  • Resolved via membership lookup
  • Defaulted to 'team' due to missing asked_by_account_id (E2=a)
  • Defaulted to 'team' due to membership not found

Run from `/app/backend`:
    python -m scripts.backfill_asker_role
Or via supervisor / cron once at deploy time.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

# Allow running as `python scripts/backfill_asker_role.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db  # noqa: E402
from services.open_questions.asker_role_map import (  # noqa: E402
    ASKER_ROLE_TEAM, derive_asker_role,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("backfill_asker_role")


async def main() -> dict:
    q = {"$or": [{"asker_role": {"$exists": False}}, {"asker_role": None}]}
    total = await db.cycle_questions.count_documents(q)
    log.info("scanning %d cycle_questions without asker_role", total)

    counter = Counter()
    no_asker = 0
    no_membership = 0
    cursor = db.cycle_questions.find(
        q, {"_id": 0, "id": 1, "context_id": 1, "asked_by_account_id": 1},
    )
    async for doc in cursor:
        qid = doc["id"]
        cid = doc["context_id"]
        asker = doc.get("asked_by_account_id")
        if not asker:
            no_asker += 1
            bucket = ASKER_ROLE_TEAM
        else:
            # derive_asker_role does its own membership lookup +
            # never raises.
            bucket = await derive_asker_role(asker, cid)
            if bucket == ASKER_ROLE_TEAM:
                # Distinguish "defaulted because no membership" from
                # legit team-bucket members. Confirm with an explicit
                # secondary lookup (cheap; one-shot script).
                m = await db.memberships.find_one(
                    {"account_id": asker, "context_id": cid},
                    {"_id": 0, "role": 1},
                )
                if not m:
                    no_membership += 1
        await db.cycle_questions.update_one(
            {"id": qid, "context_id": cid}, {"$set": {"asker_role": bucket}},
        )
        counter[bucket] += 1

    log.info(
        "backfill complete | total=%d | board=%d ceo=%d team=%d | "
        "no_asker=%d no_membership=%d",
        total, counter["board"], counter["ceo"], counter["team"],
        no_asker, no_membership,
    )
    return {
        "total": total,
        "board": counter["board"],
        "ceo":   counter["ceo"],
        "team":  counter["team"],
        "no_asker": no_asker,
        "no_membership": no_membership,
    }


if __name__ == "__main__":
    asyncio.run(main())
