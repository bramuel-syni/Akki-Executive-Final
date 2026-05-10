"""Signal action KPI — superadmin-only Act-on heatmap.

Surfaces which recommendation labels get picked across signals so we can
read which next-steps actually feel actionable to executives vs. which sit
in the dropdown unloved. Companion to /api/admin/sandbox/kpi.

Endpoints:
  GET /api/admin/signals/action-heatmap
      Aggregate counts grouped by (bucket, recommendation_label).
      Includes share recipient totals for context.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from core import db, get_current_account

router = APIRouter(prefix="/api/admin")


def _require_superadmin(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    return current


@router.get("/signals/action-heatmap")
async def signal_action_heatmap(_: Dict[str, Any] = Depends(_require_superadmin)):
    """Return per-bucket, per-recommendation pick counts plus share totals.

    Shape:
        {
          "by_bucket": [
            {"bucket": "risk", "acted": 12, "shared": 7,
             "recommendations": [
                {"label": "...", "picks": 8},
                {"label": "...", "picks": 3},
                {"label": "...", "picks": 1}]},
            ...
          ],
          "totals": {"acted": int, "shared": int, "share_recipients": int},
          "recent_actions": [{...}, ... 25],
        }
    """
    cursor = db.signal_actions.find({}, {"_id": 0}).sort("created_at", -1)
    actions: List[Dict[str, Any]] = [a async for a in cursor]

    # Pull each action's signal so we can group by recommendation bucket
    # (the bucket lives only on the signal, not on the action doc).
    signal_ids = list({a["signal_id"] for a in actions if a.get("signal_id")})
    sig_cursor = db.signals.find(
        {"id": {"$in": signal_ids}},
        {"_id": 0, "id": 1, "headline": 1, "tone": 1, "kind": 1,
         "signal_type": 1, "category": 1},
    )
    sig_meta: Dict[str, Dict[str, Any]] = {s["id"]: s async for s in sig_cursor}

    # Inline bucket classifier — kept identical to the one in
    # routers/signal_actions.py so the heatmap groups things the same
    # way the dropdown serves them.
    def _classify(sig: Dict[str, Any]) -> str:
        for k in ("kind", "tone", "signal_type", "category"):
            v = (sig.get(k) or "").lower()
            if v in {"risk", "opportunity", "gap", "neutral"}:
                return v
        head = (sig.get("headline") or "").lower()
        if any(w in head for w in ("risk", "exposure", "breach", "loss", "default", "fraud")):
            return "risk"
        if any(w in head for w in ("opportunity", "growth", "win", "expand", "upside", "tail-wind")):
            return "opportunity"
        if any(w in head for w in ("gap", "missing", "unclear", "no data", "undisclosed")):
            return "gap"
        return "neutral"

    # Per-bucket roll-up
    by_bucket_dict: Dict[str, Dict[str, Any]] = {}
    total_acted = 0
    total_shared = 0
    share_recipients: set = set()
    for a in actions:
        sig = sig_meta.get(a.get("signal_id") or "") or {}
        bucket = _classify(sig)
        b = by_bucket_dict.setdefault(bucket, {
            "bucket": bucket, "acted": 0, "shared": 0, "_recs": {},
        })
        if a["action_type"] == "acted":
            b["acted"] += 1
            total_acted += 1
            label = a.get("recommendation_label") or "(custom — composer)"
            b["_recs"][label] = b["_recs"].get(label, 0) + 1
        elif a["action_type"] == "shared":
            b["shared"] += 1
            total_shared += 1
            for r in (a.get("recipients") or []):
                share_recipients.add(r)

    # Materialise recommendations sorted by picks desc
    by_bucket: List[Dict[str, Any]] = []
    for b in by_bucket_dict.values():
        recs = sorted(
            ({"label": k, "picks": v} for k, v in b["_recs"].items()),
            key=lambda x: x["picks"], reverse=True,
        )
        by_bucket.append({
            "bucket":           b["bucket"],
            "acted":            b["acted"],
            "shared":           b["shared"],
            "recommendations":  recs,
        })
    by_bucket.sort(key=lambda x: x["acted"] + x["shared"], reverse=True)

    # Recent slice for the right-hand timeline (light annotation only).
    # Phase E.0.1 — drop signal_headline + actor_email cross-tenant.
    # Bucket label is the only signal-derived field shipped here;
    # headline is content-class per privacy_wall._DENY_SIGNALS.
    recent: List[Dict[str, Any]] = []
    for a in actions[:25]:
        sig = sig_meta.get(a.get("signal_id") or "") or {}
        recent.append({
            "id": a["id"],
            "signal_id": a["signal_id"],
            "bucket": _classify(sig),
            "action_type": a["action_type"],
            "recommendation_label": a.get("recommendation_label"),
            "recipients_count": len(a.get("recipients") or []),
            "created_at": a.get("created_at"),
        })

    return {
        "by_bucket": by_bucket,
        "totals": {
            "acted": total_acted,
            "shared": total_shared,
            "share_recipients": len(share_recipients),
        },
        "recent_actions": recent,
    }
