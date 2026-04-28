"""Admin · LLM spend telemetry.

Surfaces aggregate deep-tier (Opus) usage per surface and per account so
the team can keep an eye on cost before opening Enterprise customers. The
data already exists in `llm_deep_usage`; this router just rolls it up.

Estimated unit cost (USD): Opus 4.x averages ~$0.045 per generation in our
typical prompt sizes. Configurable via env.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account
from llm_tier_quota import DEFAULT_QUOTAS, quota_for

router = APIRouter(prefix="/api/admin/llm", tags=["admin", "llm"])


def _est_unit_cost_usd() -> float:
    try:
        return float(os.environ.get("AKKI_DEEP_UNIT_COST_USD", "0.045"))
    except ValueError:
        return 0.045


async def _require_superadmin(account: Dict[str, Any] = Depends(get_current_account)) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return account


@router.get("/spend")
async def llm_spend(
    days: int = Query(30, ge=1, le=365),
    account: Dict[str, Any] = Depends(_require_superadmin),
):
    """Roll up the last N days of deep-tier calls.

    Returns:
        {
          window_days: int,
          totals: {calls, est_cost_usd, active_accounts, surfaces_used},
          today_utc: "YYYY-MM-DD",
          by_surface: [{surface, calls, est_cost_usd, accounts, default_limit}],
          by_account_top: [{account_id, email, name, calls, est_cost_usd, top_surface}],
          by_day: [{day, calls, est_cost_usd}],
          unit_cost_usd: float,
        }
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days - 1)
    cutoff_day = cutoff_dt.strftime("%Y-%m-%d")
    unit_cost = _est_unit_cost_usd()

    # Pull rows in window. Collection is small (one-row-per-user-per-surface-per-day).
    rows: List[Dict[str, Any]] = await db.llm_deep_usage.find(
        {"day_utc": {"$gte": cutoff_day}},
        {"_id": 0, "account_id": 1, "surface": 1, "day_utc": 1, "count": 1,
         "first_used_at": 1, "last_used_at": 1},
    ).to_list(length=20000)

    total_calls = sum(r.get("count", 0) or 0 for r in rows)
    active_account_ids = {r["account_id"] for r in rows}

    # Per-surface roll-up
    surface_acc: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        s = r.get("surface", "unknown")
        if s not in surface_acc:
            surface_acc[s] = {"surface": s, "calls": 0, "accounts": set()}
        surface_acc[s]["calls"] += r.get("count", 0) or 0
        surface_acc[s]["accounts"].add(r["account_id"])
    by_surface = []
    for s, d in surface_acc.items():
        by_surface.append({
            "surface": s,
            "calls": d["calls"],
            "accounts": len(d["accounts"]),
            "est_cost_usd": round(d["calls"] * unit_cost, 2),
            "default_limit": quota_for(s),
        })
    by_surface.sort(key=lambda x: x["calls"], reverse=True)

    # Per-account roll-up (top 20)
    acc_acc: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        aid = r["account_id"]
        if aid not in acc_acc:
            acc_acc[aid] = {"account_id": aid, "calls": 0, "by_surface": {}}
        acc_acc[aid]["calls"] += r.get("count", 0) or 0
        s = r.get("surface", "unknown")
        acc_acc[aid]["by_surface"][s] = acc_acc[aid]["by_surface"].get(s, 0) + (r.get("count", 0) or 0)

    # Hydrate with email/name from accounts collection.
    aids = list(acc_acc.keys())
    accounts = []
    if aids:
        accounts = await db.accounts.find(
            {"id": {"$in": aids}},
            {"_id": 0, "id": 1, "email": 1, "name": 1},
        ).to_list(length=len(aids))
    a_by_id = {a["id"]: a for a in accounts}

    by_account_top = []
    for aid, d in acc_acc.items():
        acct = a_by_id.get(aid, {})
        top_surface = (
            sorted(d["by_surface"].items(), key=lambda x: x[1], reverse=True)[0][0]
            if d["by_surface"] else None
        )
        by_account_top.append({
            "account_id": aid,
            "email": acct.get("email") or "(unknown)",
            "name": acct.get("name") or "",
            "calls": d["calls"],
            "est_cost_usd": round(d["calls"] * unit_cost, 2),
            "top_surface": top_surface,
        })
    by_account_top.sort(key=lambda x: x["calls"], reverse=True)
    by_account_top = by_account_top[:20]

    # Per-day roll-up (sparse — only days with activity).
    day_acc: Dict[str, int] = {}
    for r in rows:
        day_acc[r["day_utc"]] = day_acc.get(r["day_utc"], 0) + (r.get("count", 0) or 0)
    by_day = sorted(
        [
            {"day": d, "calls": c, "est_cost_usd": round(c * unit_cost, 2)}
            for d, c in day_acc.items()
        ],
        key=lambda x: x["day"],
    )

    return {
        "window_days": days,
        "today_utc": today,
        "totals": {
            "calls": total_calls,
            "est_cost_usd": round(total_calls * unit_cost, 2),
            "active_accounts": len(active_account_ids),
            "surfaces_used": len(surface_acc),
        },
        "by_surface": by_surface,
        "by_account_top": by_account_top,
        "by_day": by_day,
        "unit_cost_usd": unit_cost,
        "default_quotas": dict(DEFAULT_QUOTAS),
    }
