"""Phase 12.2 closeout BUG 2 — backfill migration.

Sets `synisense_version >= 1` on every existing briefing/deck/report
that has body content but was never run through Synisense. This
unblocks public-read sharing for artefacts that predate the Phase
12.2 wiring (or were created through paths that bypass
_persist_and_project, like decks.generate_deck).

The migration is idempotent and safe to re-run. Pass --dry-run first
to preview the changeset.

Strategy:
  - Find artefacts where `synisense_version` is unset OR < 1.
  - If `body_redacted` exists already (meaning Synisense did run via
    some now-historical path), just bump the version to 1.
  - Otherwise, RUN Synisense on the artefact's `body` (or
    opening_paragraph + items concatenation for briefings) and persist
    the redacted projection plus the version field.

Usage:
    cd /app/backend
    python scripts/backfill_synisense_version.py --dry-run    # preview
    python scripts/backfill_synisense_version.py              # apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient


def _flatten_briefing(art: Dict[str, Any]) -> str:
    """Briefings store `opening_paragraph` + `items[]` shape. Concatenate."""
    parts: List[str] = []
    if art.get("opening_paragraph"):
        parts.append(str(art["opening_paragraph"]))
    for it in art.get("items") or []:
        if it.get("title"):
            parts.append(str(it["title"]))
        if it.get("body"):
            parts.append(str(it["body"]))
        if it.get("why_it_matters"):
            parts.append(str(it["why_it_matters"]))
        for q in it.get("questions_for_management") or []:
            parts.append(str(q))
    return "\n\n".join(p for p in parts if (p or "").strip())


def _flatten_deck(art: Dict[str, Any]) -> str:
    """Decks store slides; concat the body_md fields."""
    parts: List[str] = []
    for s in art.get("slides") or []:
        if s.get("title"):
            parts.append(str(s["title"]))
        if s.get("body_md"):
            parts.append(str(s["body_md"]))
    return "\n\n".join(p for p in parts if (p or "").strip())


def _flatten_report(art: Dict[str, Any]) -> str:
    return str(art.get("body") or "")


_FLATTENERS = {
    "briefings": _flatten_briefing,
    "decks": _flatten_deck,
    "reports": _flatten_report,
}


async def _process_collection(
    db, coll_name: str, dry_run: bool,
) -> Dict[str, int]:
    from services.synisense import run as syn_run
    from services.synisense.pipeline import current_version

    flattener = _FLATTENERS[coll_name]
    stats = {"scanned": 0, "skipped": 0, "redacted": 0, "version_only_bumped": 0,
             "failed": 0}
    cursor = db[coll_name].find(
        {"$or": [
            {"synisense_version": {"$exists": False}},
            {"synisense_version": {"$lt": 1}},
            {"synisense_version": None},
        ]},
        {"_id": 0, "id": 1, "context_id": 1, "title": 1,
         "body": 1, "body_redacted": 1, "opening_paragraph": 1,
         "items": 1, "slides": 1, "synisense_version": 1},
    )
    async for art in cursor:
        stats["scanned"] += 1
        # Path 1: `body_redacted` already populated → just bump version.
        if art.get("body_redacted"):
            if not dry_run:
                await db[coll_name].update_one(
                    {"id": art["id"]},
                    {"$set": {"synisense_version": 1}},
                )
            stats["version_only_bumped"] += 1
            print(f"  [{coll_name}] bump {art['id'][:12]:>12}  '{(art.get('title') or '')[:60]}'")
            continue

        # Path 2: actually run Synisense on the artefact body.
        flat = flattener(art)
        if not (flat or "").strip():
            stats["skipped"] += 1
            continue
        try:
            out = await syn_run(
                text=flat,
                context_id=art.get("context_id") or "",
                surface={"briefings": "briefing",
                         "decks": "deck",
                         "reports": "report"}[coll_name],
                mode="redact",
            )
        except Exception as e:  # noqa: BLE001
            print(f"  [{coll_name}] FAIL {art['id'][:12]:>12}  ({e.__class__.__name__})")
            stats["failed"] += 1
            continue
        spans = out.get("spans") or []
        histogram: Dict[str, int] = {}
        for s in spans:
            t = s.get("entity_type") or "UNKNOWN"
            histogram[t] = histogram.get(t, 0) + 1
        update_set = {
            "body_redacted": out["redacted_text"],
            "synisense": {
                "spans": spans,
                "stats": out.get("stats") or {},
                "version": current_version(),
                "histogram": histogram,
                "computed_at": "backfill",
            },
            "synisense_version": 1,
        }
        if not dry_run:
            await db[coll_name].update_one({"id": art["id"]}, {"$set": update_set})
        stats["redacted"] += 1
        print(f"  [{coll_name}] redact {art['id'][:12]:>12}  '{(art.get('title') or '')[:50]}'  spans={len(spans)}")
    return stats


async def main(dry_run: bool):
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    print(f"\n=== Phase 12.2 backfill — synisense_version on existing artefacts ===")
    print(f"    DB: {os.environ['DB_NAME']}")
    print(f"    DRY RUN: {dry_run}")
    totals = {"scanned": 0, "skipped": 0, "redacted": 0,
              "version_only_bumped": 0, "failed": 0}
    for coll_name in ("briefings", "decks", "reports"):
        print(f"\n--- {coll_name} ---")
        s = await _process_collection(db, coll_name, dry_run)
        for k, v in s.items():
            totals[k] += v
        print(f"  totals[{coll_name}]: {s}")
    print(f"\n=== overall totals ===")
    for k, v in totals.items():
        print(f"  {k:>22}: {v}")
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Preview changes; do not write to Mongo.")
    args = p.parse_args()
    asyncio.run(main(args.dry_run))
