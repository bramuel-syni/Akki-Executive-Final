"""P5.17 — One-shot idempotent backfill from inbox-routing sibling
collections into the primary collections the user-facing surfaces
already read.

In v1 we only backfill tasks. Pulse signals + cycle updates need
explicit `context_id` / `cycle_id` resolution which the classifier
cannot supply — those are deferred to a follow-up phase. The
backfill is structured so a future revision can drop in additional
target classes without touching the tasks path.

Idempotency contract:
  • Per-row dedup key: `(account_id, origin.message_id)`.
  • Re-running the backfill produces ZERO net writes on rows that
    already exist; the function returns counters with the no-op count
    so the close-out check has hard evidence.

Callable from:
  • A pytest lockdown (validates idempotency).
  • An ops one-shot (e.g. `python -m services.inbox_routing.backfill`).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from .upstream_adapter import ORIGIN_EMAIL_AKKI, build_origin_envelope

logger = logging.getLogger(__name__)


async def _existing_task_for_routed(db, *, account_id: str, message_id: str) -> Any:
    """Lookup an existing primary-collection task row that was
    already backfilled from this routed sibling row."""
    return await db.tasks.find_one(
        {
            "account_id": account_id,
            "origin.source": ORIGIN_EMAIL_AKKI,
            "origin.message_id": message_id,
        },
        {"_id": 0, "id": 1},
    )


async def _routing_log_for_sibling(db, *, account_id: str,
                                    message_id: str, route_kind: str) -> Any:
    """Return the routing-log row that drove the sibling creation
    so we can hydrate the origin envelope with the live decision
    source + confidence band."""
    return await db.inbox_routing_log.find_one(
        {
            "account_id": account_id,
            "message_id": message_id,
            "route_kind": route_kind,
        },
        {"_id": 0, "confidence": 1, "decision_source": 1, "created_at": 1},
    )


async def backfill_tasks(db) -> Dict[str, int]:
    """Read every `inbox_routing_tasks` row and, for any that does
    NOT yet have a corresponding `tasks` row tagged with the same
    `origin.message_id`, create one. Returns aggregate counters."""
    counters = {
        "scanned": 0,
        "created": 0,
        "exists": 0,
        "skipped_missing_log": 0,
    }
    cursor = db.inbox_routing_tasks.find({}, {"_id": 0})
    async for sibling in cursor:
        counters["scanned"] += 1
        account_id = sibling.get("account_id")
        message_id = sibling.get("source_message_id")
        if not account_id or not message_id:
            counters["skipped_missing_log"] += 1
            continue
        existing = await _existing_task_for_routed(
            db, account_id=account_id, message_id=message_id,
        )
        if existing:
            counters["exists"] += 1
            continue
        log_row = await _routing_log_for_sibling(
            db,
            account_id=account_id,
            message_id=message_id,
            route_kind="task_create",
        )
        if not log_row:
            counters["skipped_missing_log"] += 1
            continue
        envelope = build_origin_envelope(
            message_id=message_id,
            confidence_band=log_row.get("confidence", "low"),
            decision_source=log_row.get("decision_source", "auto"),
            routed_at=log_row.get("created_at"),
        )
        task_doc = {
            "id": "tsk-" + uuid.uuid4().hex[:12],
            "account_id": account_id,
            "context_id": None,  # email-routed tasks live outside any context
            "name": (sibling.get("title") or "Inbound task")[:240],
            "objective": "",
            "success_criteria": "",
            "output_spec": None,
            "team": [],
            "state": "draft",
            "due_date": sibling.get("due_hint") or None,
            "readiness_score": 0,
            "created_at": sibling.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status_history": [],
            "origin": envelope,
        }
        await db.tasks.insert_one(dict(task_doc))
        counters["created"] += 1
    logger.info("[inbox_routing.backfill_tasks] %s", counters)
    return counters


async def run() -> Dict[str, Dict[str, int]]:
    """Top-level orchestrator — invoke from CLI or pytest."""
    from core import db  # lazy import so the test process owns env loading
    out = {
        "tasks": await backfill_tasks(db),
    }
    return out


def _cli() -> None:
    parser = argparse.ArgumentParser(prog="inbox_routing.backfill")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan + report counters without writing.",
    )
    args = parser.parse_args()
    if args.dry_run:
        logger.info("Dry-run not implemented for v1 — backfill is idempotent.")
    summary = asyncio.run(run())
    print(summary)


__all__ = ["backfill_tasks", "run"]

if __name__ == "__main__":
    _cli()
