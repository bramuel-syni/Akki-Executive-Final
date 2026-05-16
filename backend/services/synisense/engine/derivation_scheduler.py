"""Synisense Engine — derivation scheduler (Phase F, 2026-05-16).

Two entry points:

  * `run_startup_backfill()` — invoked from `server.py` startup. Runs
    one derivation pass for the admin tenant + every account that has
    activity in the last 90 days. Cheap: each rule's queries are
    short-circuited by `_tenant_context_ids` when the tenant has no
    contexts.

  * `run_hourly_pass()` — invoked by APScheduler. Same body, but the
    name expresses its scheduling cadence in caller log entries.

Both are deliberately tiny — the per-tenant logic lives in
`signal_derivation.py`. This module is the orchestration shim
between FastAPI lifespan / APScheduler and the derivation engine.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from core import db

from services.synisense.engine.signal_derivation import derive_for_tenant

log = logging.getLogger("synisense.engine.scheduler")


async def _active_tenant_ids(lookback_days: int = 90) -> List[str]:
    """Tenants who've shown ANY activity in the lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    seen: Dict[str, bool] = {}
    # Activity-marker collections.
    for coll, ts_field in (
        ("chat_messages", "created_at"),
        ("solva_phase_d_sessions", "created_at"),
        ("documents", "created_at"),
        ("cycles", "updated_at"),
    ):
        try:
            cursor = db[coll].find(
                {ts_field: {"$gte": cutoff}},
                {"_id": 0, "account_id": 1, "owner_account_id": 1},
            ).limit(500)
            async for row in cursor:
                aid = row.get("account_id") or row.get("owner_account_id")
                if aid:
                    seen[str(aid)] = True
        except Exception as exc:  # noqa: BLE001
            log.info(
                "synisense.scheduler: skipping %s (%s)",
                coll, type(exc).__name__,
            )
    return list(seen.keys())


async def run_startup_backfill() -> Dict[str, int]:
    """One-time pass on app startup. Idempotent."""
    tenant_ids = await _active_tenant_ids(lookback_days=90)
    log.info(
        "synisense.scheduler: startup backfill for %d active tenants",
        len(tenant_ids),
    )
    totals: Dict[str, int] = {}
    for tid in tenant_ids:
        counts = await derive_for_tenant(tid)
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
    return totals


async def run_hourly_pass() -> Dict[str, int]:
    """Hourly cron entry point — same body, different log line."""
    tenant_ids = await _active_tenant_ids(lookback_days=30)
    log.info(
        "synisense.scheduler: hourly pass for %d active tenants",
        len(tenant_ids),
    )
    totals: Dict[str, int] = {}
    for tid in tenant_ids:
        counts = await derive_for_tenant(tid)
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
    return totals
