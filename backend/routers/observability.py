"""Phase ZZ.4 (2026-02 fork-resume v2) — Reasoning velocity aggregate.

Authenticated `GET /api/observability/reasoning_velocity` and the M.3
public mirror `GET /api/public/observability/reasoning_velocity` share
the same Mongo aggregation via `_velocity_for_account()`. The public
route restricts to `window=30d`, caches results for 5 minutes, and
does NOT require auth.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from core import db, get_current_account
from services.rate_limit import rate_limit

router = APIRouter(prefix="/api/observability", tags=["observability"])
public_router = APIRouter(prefix="/api/public/observability", tags=["public-observability"])

LOCKED_SLIDE_COUNT = 16
PUBLIC_CACHE_TTL_SECONDS = 300  # M.3 — 5-minute cache for the public mirror.
_public_cache: Dict[str, Any] = {"expires_at": 0.0, "payload": None}


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round(pct * (len(sorted_vals) - 1)))))
    return float(sorted_vals[k])


async def _velocity_aggregate(filter_q: Dict[str, Any], window: str) -> Dict[str, Any]:
    """Aggregate over solva_v2_sessions matching `filter_q`. Returns the
    locked ZZ.4 shape (session_count, slide_count, avg/p50/p95 ms,
    slowest/fastest engine kind+median)."""
    sessions = await db.solva_v2_sessions.find(
        filter_q,
        {"_id": 0, "started_at": 1, "completed_at": 1, "reasoning_audit_log": 1},
    ).to_list(length=None)
    per_session_ms_per_slide: List[float] = []
    engine_latencies: Dict[str, List[float]] = {}
    for s in sessions:
        try:
            t0 = datetime.fromisoformat(s["started_at"].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(s["completed_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        dur_ms = max(0.0, (t1 - t0).total_seconds() * 1000.0)
        per_session_ms_per_slide.append(dur_ms / LOCKED_SLIDE_COUNT)
        for row in (s.get("reasoning_audit_log") or []):
            eng = row.get("engine") or "unknown"
            lat = row.get("latency_ms")
            if isinstance(lat, (int, float)) and lat >= 0:
                engine_latencies.setdefault(eng, []).append(float(lat))
    per_session_ms_per_slide.sort()
    avg_ms = (sum(per_session_ms_per_slide) / len(per_session_ms_per_slide)
              if per_session_ms_per_slide else 0.0)
    engine_medians = {k: float(median(v)) for k, v in engine_latencies.items() if v}
    slowest: Optional[Dict[str, Any]] = None
    fastest: Optional[Dict[str, Any]] = None
    if engine_medians:
        sk = max(engine_medians, key=engine_medians.get)
        fk = min(engine_medians, key=engine_medians.get)
        slowest = {"kind": sk, "median_ms": engine_medians[sk]}
        fastest = {"kind": fk, "median_ms": engine_medians[fk]}
    return {
        "window": window,
        "session_count": len(sessions),
        "slide_count": len(sessions) * LOCKED_SLIDE_COUNT,
        "avg_ms_per_slide": avg_ms,
        "p50_ms": _percentile(per_session_ms_per_slide, 0.50) * LOCKED_SLIDE_COUNT,
        "p95_ms": _percentile(per_session_ms_per_slide, 0.95) * LOCKED_SLIDE_COUNT,
        "slowest_slide_kind": slowest,
        "fastest_slide_kind": fastest,
    }


@router.get("/reasoning_velocity")
async def reasoning_velocity(
    window: str = Query("7d", pattern="^(7d|30d)$"),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    days = 7 if window == "7d" else 30
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return await _velocity_aggregate(
        {"account_id": current["id"], "status": "completed",
         "completed_at": {"$gte": cutoff}},
        window,
    )


# ─────────────────────────────────────────────────────────────────────
# M.3 (2026-02) — Public mirror for prospects on /trust. No auth.
# 30-day window only. Aggregates across ALL accounts. 5-minute cache.
# ─────────────────────────────────────────────────────────────────────
@public_router.get("/reasoning_velocity")
async def public_reasoning_velocity(
    window: str = Query("30d", pattern="^30d$"),
    _rl: None = Depends(rate_limit("public_tile")),
) -> Dict[str, Any]:
    now = time.time()
    if _public_cache["payload"] and _public_cache["expires_at"] > now:
        return _public_cache["payload"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    payload = await _velocity_aggregate(
        {"status": "completed", "completed_at": {"$gte": cutoff}},
        window,
    )
    _public_cache["payload"] = payload
    _public_cache["expires_at"] = now + PUBLIC_CACHE_TTL_SECONDS
    return payload
