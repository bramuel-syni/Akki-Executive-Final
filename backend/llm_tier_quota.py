"""Deep-tier quota governance.

Opus 4.x is ~5× the cost of Sonnet on output tokens, so deep-tier calls are
metered per-account-per-day. Each surface declares a `surface` slug and a
daily limit; when a user is over quota we fall back to the standard tier
with a soft notice surfaced back to the UI in the call response.

Persistence: a single `llm_deep_usage` collection keyed on
`(account_id, surface, day_utc)` with `count: int`.

Reset: implicit — the day_utc key changes at 00:00 UTC. No cron needed.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core import db

logger = logging.getLogger("akki.deep_quota")

# Default daily budgets per surface (per user). Overridable via env using
# AKKI_DEEP_QUOTA_<surface_upper> e.g. AKKI_DEEP_QUOTA_DECK=5.
DEFAULT_QUOTAS: Dict[str, int] = {
    "brief":     10,   # Deep Brief (long-form narrative)
    "blog":       5,   # ExCo360 blog generation (admin)
    "deck":       3,   # Deck generation (when shipped)
    "chat":      30,   # Chat with Opus selected
    "validate":  20,   # High-stakes second-pass validation
    "minutes":    5,   # Minutes → narrative summary / Cycle dispatch
    "solve":      4,   # AKKI Solve · Pro tier deep synthesis (per session)
    "solve_v2":   4,   # Phase 15.0 POC — mirrors solve budget; aliases to
                       # AKKI_DEEP_QUOTA_SOLVE so no new env var is introduced.
}


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def quota_for(surface: str) -> int:
    """Look up the daily limit for a surface, env-overridable.

    Phase 15.0 aliasing: when surface=='solve_v2' and no explicit
    AKKI_DEEP_QUOTA_SOLVE_V2 is set, fall back to AKKI_DEEP_QUOTA_SOLVE so
    operators do not need a new env key for the POC.
    """
    key = f"AKKI_DEEP_QUOTA_{surface.upper()}"
    env = os.environ.get(key)
    if env:
        try:
            return max(0, int(env))
        except ValueError:
            pass
    # Phase 15.0 alias: solve_v2 falls back to solve env key
    if surface == "solve_v2":
        alias = os.environ.get("AKKI_DEEP_QUOTA_SOLVE")
        if alias:
            try:
                return max(0, int(alias))
            except ValueError:
                pass
    return DEFAULT_QUOTAS.get(surface, 5)


async def check_and_consume(account_id: str, surface: str) -> Dict[str, Any]:
    """Check whether the user is within their daily deep-tier budget for
    `surface` and atomically increment if so.

    Returns:
        {
          "allowed": bool,
          "remaining": int,
          "limit": int,
          "used": int,
          "surface": str,
          "reset_at": "<ISO of next 00:00 UTC>",
        }
    """
    limit = quota_for(surface)
    day = _today_utc()
    key = {"account_id": account_id, "surface": surface, "day_utc": day}

    if limit <= 0:
        return {
            "allowed": False, "remaining": 0, "limit": 0, "used": 0,
            "surface": surface, "reset_at": _next_midnight_iso(),
        }

    # Race-safe atomic check-and-consume.
    # Pass 1: increment IF count < limit AND a row already exists.
    nowiso = datetime.now(timezone.utc).isoformat()
    res = await db.llm_deep_usage.find_one_and_update(
        {**key, "count": {"$lt": limit}},
        {"$inc": {"count": 1}, "$set": {"last_used_at": nowiso}},
        return_document=True,
        projection={"_id": 0, "count": 1},
    )
    if res is not None:
        used_now = res.get("count", 1)
        return {
            "allowed": True,
            "remaining": max(0, limit - used_now),
            "limit": limit, "used": used_now,
            "surface": surface, "reset_at": _next_midnight_iso(),
        }

    # Pass 2: either no row yet (first call of the day) OR row already at cap.
    # Try to insert a fresh count=1 row; the unique index on (account_id, surface,
    # day_utc) makes this atomic — a duplicate-key error means a row already
    # exists, which (since pass 1 didn't match) must be at cap, so deny.
    try:
        await db.llm_deep_usage.insert_one({
            **key, "count": 1,
            "first_used_at": nowiso, "last_used_at": nowiso,
        })
        return {
            "allowed": True, "remaining": max(0, limit - 1),
            "limit": limit, "used": 1,
            "surface": surface, "reset_at": _next_midnight_iso(),
        }
    except Exception:  # noqa: BLE001 — DuplicateKeyError or any insert failure
        existing = await db.llm_deep_usage.find_one(key, {"_id": 0, "count": 1})
        used = (existing or {}).get("count", limit) or limit
        return {
            "allowed": False, "remaining": 0, "limit": limit, "used": used,
            "surface": surface, "reset_at": _next_midnight_iso(),
        }


async def peek(account_id: str, surface: Optional[str] = None) -> Dict[str, Any]:
    """Inspect today's deep-tier usage without consuming. If `surface` is
    None, returns a dict for every surface with a configured default."""
    day = _today_utc()
    if surface:
        row = await db.llm_deep_usage.find_one(
            {"account_id": account_id, "surface": surface, "day_utc": day},
            {"_id": 0, "count": 1},
        )
        used = (row or {}).get("count", 0) or 0
        limit = quota_for(surface)
        return {
            "surface": surface, "used": used, "limit": limit,
            "remaining": max(0, limit - used), "reset_at": _next_midnight_iso(),
        }
    # All surfaces.
    out = {}
    for s in DEFAULT_QUOTAS:
        out[s] = await peek(account_id, s)
    out["reset_at"] = _next_midnight_iso()
    return out


def _next_midnight_iso() -> str:
    now = datetime.now(timezone.utc)
    nxt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 86400s in a day; add one day's worth of seconds at most.
    from datetime import timedelta
    nxt += timedelta(days=1)
    return nxt.isoformat()


async def call_llm_with_tier(
    *,
    surface: str,
    account_id: str,
    requested_tier: str,
    call_args: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Convenience wrapper. Calls llm_service.call_llm with the requested
    tier if quota allows; otherwise downgrades to "standard" and surfaces
    a `quota` block on the result.

    Returns (llm_result, quota_state). The caller can decide whether to
    bubble the quota state to the API response.
    """
    from llm_service import call_llm

    quota_state: Dict[str, Any] = {
        "requested_tier": requested_tier,
        "served_tier": requested_tier,
        "surface": surface,
        "downgraded": False,
    }

    if requested_tier == "deep":
        budget = await check_and_consume(account_id, surface)
        quota_state.update(budget)
        if not budget["allowed"]:
            requested_tier = "standard"
            quota_state["served_tier"] = "standard"
            quota_state["downgraded"] = True

    result = await call_llm(**{**call_args, "tier": requested_tier})
    return result, quota_state
