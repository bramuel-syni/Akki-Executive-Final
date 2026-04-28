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


@router.get("/decks/quality")
async def deck_quality(
    days: int = Query(30, ge=1, le=365),
    account: Dict[str, Any] = Depends(_require_superadmin),
):
    """Behaviour-monitoring view: how good are the decks AKKI is producing?

    Returns aggregate signals over the window so the team can spot
    deteriorating prompt quality or rising regen counts BEFORE budget gets
    burned.
    """
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days - 1)
    cutoff_iso = cutoff_dt.isoformat()

    rows: List[Dict[str, Any]] = await db.deck_telemetry.find(
        {"created_at": {"$gte": cutoff_iso}},
        {"_id": 0},
    ).to_list(length=5000)

    decks_count = len(rows)
    quality_scored = [r for r in rows if r.get("quality_score") is not None]
    avg_score = (
        round(sum(r["quality_score"] for r in quality_scored) / len(quality_scored), 1)
        if quality_scored else None
    )
    rated = [r for r in rows if r.get("user_rating")]
    thumbs_up = sum(1 for r in rated if r["user_rating"] == "up")
    thumbs_down = sum(1 for r in rated if r["user_rating"] == "down")
    satisfaction = (
        round(thumbs_up * 100 / len(rated), 0) if rated else None
    )

    # Outline approval rate — outlines created vs decks generated. A high
    # ratio means users are iterating outlines (good — saving deep budget).
    outline_total = await db.deck_outlines.count_documents(
        {"created_at": {"$gte": cutoff_iso}}
    )
    outline_approved = await db.deck_outlines.count_documents(
        {"created_at": {"$gte": cutoff_iso}, "approved": True}
    )
    iterations = [r.get("outline_iterations", 1) for r in rows]
    avg_iterations = (
        round(sum(iterations) / len(iterations), 2) if iterations else None
    )

    will_regen = sum(1 for r in rows if r.get("user_will_regenerate"))
    quality_recommends_regen = sum(1 for r in rows if r.get("quality_recommends_regen"))
    insufficient_ctx = sum(
        1 for r in rows if r.get("context_sufficiency") == "insufficient"
    )
    partial_ctx = sum(
        1 for r in rows if r.get("context_sufficiency") == "partial"
    )

    # Per-account quality alert: which users dropped below 55 on >=3 of last 5
    # decks? These are the ones to coach before they burn more budget.
    QUALITY_ALERT_THRESHOLD = 55
    QUALITY_ALERT_WINDOW = 5
    QUALITY_ALERT_HITS = 3

    by_account: Dict[str, List[Dict[str, Any]]] = {}
    for r in sorted(rows, key=lambda x: x.get("created_at") or "", reverse=True):
        if r.get("quality_score") is None:
            continue
        by_account.setdefault(r["account_id"], []).append(r)

    alerted_accounts: List[Dict[str, Any]] = []
    for aid, recs in by_account.items():
        last_n = recs[:QUALITY_ALERT_WINDOW]
        weak = [x for x in last_n if (x.get("quality_score") or 100) < QUALITY_ALERT_THRESHOLD]
        if len(weak) >= QUALITY_ALERT_HITS:
            acct = await db.accounts.find_one(
                {"id": aid}, {"_id": 0, "id": 1, "email": 1, "name": 1}
            )
            alerted_accounts.append({
                "account_id": aid,
                "email": (acct or {}).get("email") or "(unknown)",
                "name": (acct or {}).get("name") or "",
                "weak_count": len(weak),
                "window": len(last_n),
                "avg_score": round(sum(x["quality_score"] for x in last_n) / len(last_n), 1),
            })
    alerted_accounts.sort(key=lambda x: x["avg_score"])

    # Top regen reasons (the learning-loop signal).
    reasons_acc: Dict[str, int] = {}
    for r in rows:
        rr = r.get("user_regen_reason")
        if rr:
            reasons_acc[rr] = reasons_acc.get(rr, 0) + 1
    top_regen_reasons = sorted(
        [{"reason": k, "count": v} for k, v in reasons_acc.items()],
        key=lambda x: x["count"], reverse=True,
    )

    return {
        "window_days": days,
        "decks_generated": decks_count,
        "outlines_drafted": outline_total,
        "outline_to_deck_ratio": (
            round(outline_total / decks_count, 2) if decks_count else None
        ),
        "outlines_approved": outline_approved,
        "avg_outline_iterations": avg_iterations,
        "avg_quality_score": avg_score,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "satisfaction_pct": satisfaction,
        "user_will_regenerate_count": will_regen,
        "quality_recommends_regen_count": quality_recommends_regen,
        "insufficient_context_count": insufficient_ctx,
        "partial_context_count": partial_ctx,
        "alerted_accounts": alerted_accounts,
        "alert_threshold": QUALITY_ALERT_THRESHOLD,
        "alert_window": QUALITY_ALERT_WINDOW,
        "alert_min_hits": QUALITY_ALERT_HITS,
        "top_regen_reasons": top_regen_reasons,
    }
