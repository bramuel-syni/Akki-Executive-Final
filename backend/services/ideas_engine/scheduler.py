"""Phase P5.15 — Weekly digest scheduler.

Cron-driven idempotent weekly sweep that proactively generates one
`IdeasDigest` per active tenant per ISO-week. Lazy-on-GET in the
router still works (and is the user-experience fallback when the
sweep hasn't yet run for an account); the scheduler simply warms
the cache so a Monday-morning visitor lands on a ready digest
instead of triggering a 200-300 ms synthesis on first hit.

Idempotency contract:
  * Per `(account_id, week_iso, digest_version)` — already enforced
    by the router's `find_one` precheck + the audit-log row append.
  * The scheduler MUST NOT generate a second row for a tenant in
    the same week, even across multiple sweep runs (e.g. a
    sweep retry after partial failure).
  * The scheduler MUST NOT generate digests for dormant tenants
    (no documents indexed in the recent corpus window) — those
    return an empty digest with all 4 lenses dropped, which is
    write-amplification with no value.

Trigger choice: Monday 07:00 UTC. The previous week (last Sunday
23:59 UTC) is the cut-off for "what landed last week"; running at
07:00 Monday gives the synthesizer access to the freshest
indexed corpus while still landing the digest before the typical
9-10am local workday in EAT / WET / CET.

Concurrency: in-process APScheduler matches the existing pattern
(`chat_retention_daily`, `cohort_expiry_reminder_daily`,
`influence_digest_weekly`). Single-replica deploys only at this
LOC scale; the Mongo-lock variant (see
`services.synisense.engine.scheduler_lock`) is the future-mode
when Ideas goes multi-replica.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from .schema import IdeasDigest
from .synthesizer import synthesize_digest, week_iso_for
from .preferences import get_or_default_preferences

logger = logging.getLogger(__name__)

# The active-account window — sweep ignores tenants whose corpus
# hasn't seen any document activity in this many days. Same window
# the synthesizer uses internally (90 days) so a tenant that the
# synthesizer would treat as "empty corpus" is silently skipped
# rather than written as a zero-card row.
DEFAULT_ACTIVE_WINDOW_DAYS = 90


async def _account_has_recent_corpus(db, *, account_id: str, days: int) -> bool:
    """True iff at least one document in this tenant has an
    `updated_at` or `created_at` within the last `days`. Uses the
    sparse Mongo index on `(account_id, updated_at)` if available;
    otherwise falls back to a plain scan with a `$limit: 1`."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    doc = await db.documents.find_one(
        {
            "account_id": account_id,
            "$or": [
                {"updated_at": {"$gte": cutoff}},
                {"created_at": {"$gte": cutoff}},
            ],
        },
        {"_id": 0, "id": 1},
    )
    return doc is not None


async def sweep_account(
    db,
    *,
    account_id: str,
    user_id: Optional[str] = None,
    week_iso: Optional[str] = None,
    digest_version: str = "p5.15.0",
) -> Dict[str, Any]:
    """Per-tenant weekly sweep step. Returns a small structured
    result dict so the parent sweep can aggregate diagnostics.

    Idempotent: existing `(account_id, week_iso, digest_version)`
    row → no-op (`status="exists"`). No-corpus tenant → no-op
    (`status="skipped_no_corpus"`). Generated path persists the
    row + audit-log entry exactly like the router's lazy path.
    """
    user_id = user_id or account_id  # in this codebase account.id IS the user_id
    week_iso = week_iso or week_iso_for()

    existing = await db.ideas_digests.find_one(
        {"account_id": account_id, "week_iso": week_iso,
         "digest_version": digest_version},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {
            "account_id": account_id,
            "week_iso": week_iso,
            "status": "exists",
            "digest_id": existing.get("id"),
        }

    if not await _account_has_recent_corpus(
        db, account_id=account_id, days=DEFAULT_ACTIVE_WINDOW_DAYS,
    ):
        return {
            "account_id": account_id,
            "week_iso": week_iso,
            "status": "skipped_no_corpus",
        }

    prefs = await get_or_default_preferences(
        db, account_id=account_id, user_id=user_id,
    )
    digest: IdeasDigest = await synthesize_digest(
        db,
        account_id=account_id,
        user_id=user_id,
        week_iso=week_iso,
        lenses_enabled=prefs.lenses_enabled,
        custom_instructions=prefs.custom_instructions,
    )
    await db.ideas_digests.insert_one(digest.model_dump())
    await db.ideas_audit_log.insert_one({
        "digest_id": digest.id,
        "account_id": account_id,
        "user_id": user_id,
        "week_iso": digest.week_iso,
        "model_id": digest.model_id,
        "shield_invoke_id": digest.shield_invoke_id,
        "citation_count": digest.citation_count,
        "refuse_to_decide_pass_count": digest.refuse_to_decide_pass_count,
        "refuse_to_decide_fail_count": digest.refuse_to_decide_fail_count,
        "dropped_lenses": digest.dropped_lenses,
        "trigger": "scheduler_weekly",
        "generated_at": digest.generated_at,
    })
    return {
        "account_id": account_id,
        "week_iso": week_iso,
        "status": "generated",
        "digest_id": digest.id,
        "card_count": len(digest.cards),
        "dropped_lenses": digest.dropped_lenses,
    }


async def run_weekly_ideas_sweep(
    db, *, week_iso: Optional[str] = None, max_accounts: int = 200_000,
) -> Dict[str, Any]:
    """Iterate every account and call `sweep_account`. Returns
    aggregate counters for logging + audit. Designed to be
    callable from APScheduler cron AND from tests directly.

    `max_accounts` is a defensive cap to bound the sweep duration
    if the accounts collection ever explodes; the default 200 000
    sits well above today's footprint (production today ≈ 30, dev
    ≈ 23 500 mostly from past test pollution). Raise if needed; do
    NOT lower — silently capped sweeps regress the "we surface
    ideas for every active tenant" promise.

    No tenant order guarantee. Per-tenant errors are caught + counted
    (logged at WARNING) so a single broken corpus doesn't abort
    the entire sweep.
    """
    week_iso = week_iso or week_iso_for()
    cursor = db.accounts.find({}, {"_id": 0, "id": 1}).limit(max_accounts)
    counters: Dict[str, int] = {
        "scanned": 0,
        "generated": 0,
        "exists": 0,
        "skipped_no_corpus": 0,
        "errors": 0,
    }
    results: List[Dict[str, Any]] = []
    async for acct in cursor:
        account_id = acct.get("id")
        if not account_id:
            continue
        counters["scanned"] += 1
        try:
            out = await sweep_account(
                db, account_id=account_id, user_id=account_id,
                week_iso=week_iso,
            )
            counters[out["status"]] = counters.get(out["status"], 0) + 1
            results.append(out)
        except Exception as e:  # noqa: BLE001 — keep sweep moving
            counters["errors"] += 1
            logger.warning(
                "[ideas.scheduler] sweep failed for account_id=%s week_iso=%s: %s",
                account_id, week_iso, e,
            )
    summary = {
        "week_iso": week_iso,
        "counters": counters,
        # Trim sample to first 50 results to keep the log line bounded.
        "sample": results[:50],
    }
    logger.info("[ideas.scheduler] weekly sweep complete: %s",
                {"week_iso": week_iso, "counters": counters})
    return summary


def is_scheduler_disabled() -> bool:
    """Env override for tests + single-replica vs HA deploys.
    Setting `IDEAS_SCHEDULER_DISABLED=true` keeps the cron from
    arming at startup (the router lazy-path remains active so the
    UX doesn't regress)."""
    return os.environ.get("IDEAS_SCHEDULER_DISABLED", "false").strip().lower() == "true"


__all__ = [
    "DEFAULT_ACTIVE_WINDOW_DAYS",
    "is_scheduler_disabled",
    "run_weekly_ideas_sweep",
    "sweep_account",
]
