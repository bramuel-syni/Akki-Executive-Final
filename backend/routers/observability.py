"""Phase ZZ.4 (2026-02 fork-resume v2) — Reasoning velocity aggregate.

`GET /api/observability/reasoning_velocity?window=7d|30d`

Source: existing `solva_v2_sessions` collection (status="completed",
completed_at within window). Per-session duration derived from
started_at → completed_at. Per-engine median latency_ms derived from
the embedded `reasoning_audit_log[]` rows. No new collections, no new
event schema.

Returned shape (consumed by Trust Center > Reasoning):
  {
    "window": "7d",
    "session_count": int,
    "slide_count": int,           # session_count * 16 (locked deck size)
    "avg_ms_per_slide": float,
    "p50_ms": float,
    "p95_ms": float,
    "slowest_slide_kind": {"kind": str, "median_ms": float} | None,
    "fastest_slide_kind": {"kind": str, "median_ms": float} | None,
  }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from core import db, get_current_account

router = APIRouter(prefix="/api/observability", tags=["observability"])

LOCKED_SLIDE_COUNT = 16


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round(pct * (len(sorted_vals) - 1)))))
    return float(sorted_vals[k])


@router.get("/reasoning_velocity")
async def reasoning_velocity(
    window: str = Query("7d", pattern="^(7d|30d)$"),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    days = 7 if window == "7d" else 30
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sessions = await db.solva_v2_sessions.find(
        {"account_id": current["id"], "status": "completed",
         "completed_at": {"$gte": cutoff}},
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
