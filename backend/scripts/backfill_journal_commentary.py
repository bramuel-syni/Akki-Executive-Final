"""backfill_journal_commentary.py — Phase 1.

Walks `db.documents`, generates `journal_commentary` for every eligible
row through the SAME shared service the live lazy-on-click endpoint
uses (`document_commentary_service.generate_journal_commentary`). The
backfill therefore:

  * runs Synisense Shield on every generated commentary with
    `surface="journal_commentary"` (one row in `synisense_runs` per
    backfilled doc);
  * is idempotent — already-generated docs come back as `cached`
    and are not re-charged to the LLM bill;
  * is resumable — interrupting and re-running picks up where it left
    off because the only persistent state is the `journal_commentary`
    field on each row;
  * is throttled — `--sleep-ms` between docs (default 750ms) keeps the
    universal LLM key from rate-limiting under burst;
  * logs progress every 10 docs.

Invocation:
    python3 backend/scripts/backfill_journal_commentary.py
    python3 backend/scripts/backfill_journal_commentary.py --limit 50
    python3 backend/scripts/backfill_journal_commentary.py --sleep-ms 250
    python3 backend/scripts/backfill_journal_commentary.py --refresh   # force re-gen

Also called in-process by `POST /api/admin/journal/backfill`.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# When run as a standalone script, make sure the backend module dir is
# on sys.path so the ad-hoc imports (`core`, `document_commentary_service`)
# resolve. When called from inside the live FastAPI process via the
# admin endpoint this is a no-op because backend/ is already on the path.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Backend uses python-dotenv at import time of `core` — load .env explicitly
# so a fresh shell session works without the supervisor environment.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(_BACKEND_DIR / ".env")

from core import db  # noqa: E402  (must come after load_dotenv)
from document_commentary_service import (  # noqa: E402
    CommentaryGenerationError,
    generate_journal_commentary,
    is_eligible,
)

logger = logging.getLogger("akki.backfill.journal")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def _resolve_actor_account_id() -> str:
    """The audit log + Synisense run require an account id. We attribute
    the backfill to the bootstrap superadmin (`admin@akki.ai`) — that
    matches the convention of every other server-side cron in this
    codebase (e.g. retention sweep, paragraph anchors)."""
    a = await db.accounts.find_one(
        {"is_superadmin": True}, {"_id": 0, "id": 1, "email": 1},
        sort=[("created_at", 1)],
    )
    if not a:
        raise RuntimeError(
            "No superadmin account found — cannot attribute backfill audit. "
            "Boot the server first so `admin@akki.ai` is seeded.",
        )
    return a["id"]


async def run_backfill(
    *,
    limit: Optional[int] = None,
    sleep_ms: int = 750,
    refresh: bool = False,
    actor_account_id: Optional[str] = None,
    concurrency: int = 1,
) -> Dict[str, Any]:
    """Run the backfill. Returns a summary dict.

    Parameters
    ----------
    concurrency
        How many docs to generate in parallel. Default 1 (strict serial).
        Bumping to 3-4 cuts wall-clock dramatically because each doc's
        Synisense LLM fallback layer fires 5-10 Gemini calls in a tight
        burst and the Claude commentary call is ~20s; running 3 in
        parallel still keeps total in-flight LLM-gateway calls under the
        documented `SYNISENSE_LLM_FALLBACK_CONCURRENCY=5` ceiling per
        doc plus a handful of Claude streams. The throttle (`sleep_ms`)
        is applied between *batches* of `concurrency` docs.

    Returns
    -------
    {
        "total_docs": int,             # rows in db.documents
        "eligible": int,               # rows that pass is_eligible() pre-flight
        "generated": int,              # successfully generated this run
        "skipped": dict[str, int],     # reason -> count
        "failed": list[dict],          # [{doc_id, error}]
        "elapsed_seconds": float,
        "actor_account_id": str,
        "concurrency": int,
    }
    """
    started = time.monotonic()
    actor = actor_account_id or await _resolve_actor_account_id()

    total = await db.documents.count_documents({})

    # Pre-flight pass for eligibility. We materialise this list so the
    # progress log is meaningful and the throttle is predictable. Lean
    # projection — only the fields we actually consult during eligibility
    # plus the few generation needs.
    proj = {
        "_id": 0, "id": 1, "context_id": 1, "name": 1, "title": 1,
        "extracted_text": 1, "status": 1, "sensitivity_band": 1,
        "journal_commentary": 1, "journal_commentary_synisense_version": 1,
        "journal_commentary_generated_at": 1, "doc_kind": 1, "doc_type": 1,
    }

    if refresh:
        cursor = db.documents.find({}, proj)
    else:
        cursor = db.documents.find(
            {"$or": [
                {"journal_commentary": {"$exists": False}},
                {"journal_commentary": ""},
                {"journal_commentary": None},
            ]},
            proj,
        )

    candidates = []
    async for d in cursor:
        if limit and len(candidates) >= limit:
            break
        candidates.append(d)

    summary: Dict[str, Any] = {
        "total_docs": total,
        "eligible": 0,
        "generated": 0,
        "skipped": {},
        "failed": [],
        "elapsed_seconds": 0.0,
        "actor_account_id": actor,
        "concurrency": concurrency,
    }

    logger.info(
        "Backfill start — total=%d candidates=%d refresh=%s sleep_ms=%d concurrency=%d actor=%s",
        total, len(candidates), refresh, sleep_ms, concurrency, actor,
    )

    # Serial pre-flight skip pass — cheap, no LLM, no concurrency needed.
    work: list[Dict[str, Any]] = []
    for d in candidates:
        skip_reason = await is_eligible(d) if not refresh else None
        if skip_reason and skip_reason != "already_cached":
            summary["skipped"][skip_reason] = summary["skipped"].get(skip_reason, 0) + 1
            continue
        summary["eligible"] += 1
        work.append(d)

    # ─── Generation pass — bounded concurrency batches ───────────────
    async def _one(doc: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = doc["id"]
        try:
            res = await generate_journal_commentary(
                doc=doc,
                account_id=actor,
                refresh=refresh,
                record_audit=True,
            )
            return {"doc_id": doc_id, "ok": True, "res": res}
        except CommentaryGenerationError as exc:
            return {"doc_id": doc_id, "ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001  defensive
            logger.exception("[%s] unexpected backfill error", doc_id)
            return {"doc_id": doc_id, "ok": False, "error": f"unexpected: {exc}"}

    processed = 0
    for batch_start in range(0, len(work), concurrency):
        batch = work[batch_start:batch_start + concurrency]
        results = await asyncio.gather(*[_one(d) for d in batch])
        for r in results:
            processed += 1
            if not r["ok"]:
                summary["failed"].append({"doc_id": r["doc_id"], "error": r["error"]})
                logger.warning("[%s] failed: %s", r["doc_id"], r["error"])
                continue
            res = r["res"]
            if res["status"] == "generated":
                summary["generated"] += 1
            elif res["status"] == "cached":
                summary["skipped"]["already_cached"] = (
                    summary["skipped"].get("already_cached", 0) + 1
                )
            elif res["status"] == "skipped":
                reason = res["reason"]
                summary["skipped"][reason] = summary["skipped"].get(reason, 0) + 1

            if processed % 10 == 0:
                logger.info(
                    "Progress %d/%d — generated=%d skipped=%d failed=%d",
                    processed, len(work), summary["generated"],
                    sum(summary["skipped"].values()), len(summary["failed"]),
                )

        # Throttle between *batches*, not between individual docs.
        if sleep_ms > 0:
            await asyncio.sleep(sleep_ms / 1000.0)

    summary["elapsed_seconds"] = round(time.monotonic() - started, 2)
    logger.info(
        "Backfill done — total=%d eligible=%d generated=%d skipped=%d failed=%d elapsed=%.2fs",
        summary["total_docs"], summary["eligible"], summary["generated"],
        sum(summary["skipped"].values()), len(summary["failed"]),
        summary["elapsed_seconds"],
    )
    return summary


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 1 — Document Journal commentary backfill")
    p.add_argument("--limit", type=int, default=None,
                   help="Stop after N candidates (default: no cap).")
    p.add_argument("--sleep-ms", type=int, default=750,
                   help="Sleep between batches in milliseconds (default: 750).")
    p.add_argument("--refresh", action="store_true",
                   help="Force re-generation even on already-cached docs.")
    p.add_argument("--concurrency", type=int, default=1,
                   help="Docs to generate in parallel per batch (default: 1).")
    return p.parse_args()


async def _main() -> int:
    args = _parse_args()
    summary = await run_backfill(
        limit=args.limit,
        sleep_ms=args.sleep_ms,
        refresh=args.refresh,
        concurrency=args.concurrency,
    )
    import json
    print(json.dumps(summary, indent=2, default=str))
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
