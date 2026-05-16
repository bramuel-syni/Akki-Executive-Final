"""Phase E Sub-task D — Synisense observability dashboard endpoint.

`GET /api/admin/synisense/observability?window_days=7|30|90`

Returns aggregates over the last N days from `synisense_audit_log`:
  - Total Shield invokes per consumer (chat / solva / work_studio /
    document_journal / cycle_manager).
  - Per-consumer average dilution + exposure reduction scores.
  - Refusal rate per consumer (success vs governance_refused vs
    service_unavailable). The `outcome` field on each audit row is
    the source of truth.
  - Top 10 most-used purposes.
  - `reidentification_partial: true` rate.
  - Solva-specific: refusal_reason distribution.

Superadmin only — uses the existing `is_superadmin` flag on the
account record.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account


router = APIRouter(prefix="/api/admin/synisense", tags=["admin-synisense-observability"])


async def _require_superadmin(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return current


@router.get("/observability")
async def observability_snapshot(
    window_days: int = Query(default=7, ge=1, le=90),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    # Read all relevant audit rows since cutoff. Bounded by audit
    # collection size; if this grows beyond ~50k/day, switch to an
    # aggregation pipeline.
    cursor = db.synisense_audit_log.find(
        {"created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).limit(50000)
    rows = await cursor.to_list(length=50000)

    per_consumer: Dict[str, Dict[str, Any]] = {}
    purpose_counts: Dict[str, int] = {}
    reid_partial = 0
    solva_refusals: Dict[str, int] = {}

    for r in rows:
        consumer = r.get("consumer_id") or "unknown"
        outcome = r.get("outcome") or "success"
        bucket = per_consumer.setdefault(consumer, {
            "consumer_id": consumer,
            "total_invokes": 0,
            "successes": 0,
            "governance_refused": 0,
            "service_unavailable": 0,
            "exposure_reduction_sum": 0.0,
            "exposure_reduction_count": 0,
            "dilution_sum": 0.0,
            "dilution_count": 0,
        })
        bucket["total_invokes"] += 1
        if outcome == "success":
            bucket["successes"] += 1
        elif outcome == "governance_refused":
            bucket["governance_refused"] += 1
        elif outcome == "service_unavailable":
            bucket["service_unavailable"] += 1
        er = r.get("exposure_reduction_score")
        if isinstance(er, (int, float)):
            bucket["exposure_reduction_sum"] += er
            bucket["exposure_reduction_count"] += 1
        dl = r.get("dilution_score")
        if isinstance(dl, (int, float)):
            bucket["dilution_sum"] += dl
            bucket["dilution_count"] += 1

        purpose = r.get("purpose") or "unknown"
        purpose_counts[purpose] = purpose_counts.get(purpose, 0) + 1

        if r.get("reidentification_partial") is True:
            reid_partial += 1

        # Solva refusal reason distribution — pulled from the linked
        # session, NOT from the audit row (audit rows don't carry the
        # session's refusal reason). We approximate by checking purpose
        # prefix `solva.guardrails.*` — those audit rows fire the guard.
        if (r.get("purpose") or "").startswith("solva.guardrails."):
            tag = (r.get("purpose") or "").split(".")[-1]
            solva_refusals[tag] = solva_refusals.get(tag, 0) + 1

    # Compute averages.
    consumers = []
    for bucket in per_consumer.values():
        er_avg = (
            round(bucket["exposure_reduction_sum"] / bucket["exposure_reduction_count"], 1)
            if bucket["exposure_reduction_count"] else None
        )
        dl_avg = (
            round(bucket["dilution_sum"] / bucket["dilution_count"], 1)
            if bucket["dilution_count"] else None
        )
        total = bucket["total_invokes"]
        consumers.append({
            "consumer_id": bucket["consumer_id"],
            "total_invokes": total,
            "success_rate": round(bucket["successes"] / total, 3) if total else None,
            "refusal_rate": (
                round(bucket["governance_refused"] / total, 3) if total else None
            ),
            "unavailable_rate": (
                round(bucket["service_unavailable"] / total, 3) if total else None
            ),
            "average_exposure_reduction": er_avg,
            "average_dilution": dl_avg,
        })

    consumers.sort(key=lambda c: -c["total_invokes"])

    # Also pull Solva session refusal_reason distribution (Phase D
    # surface). Lookup from solva_phase_d_sessions where status is
    # `refused` or `blocked_hard`.
    sess_cursor = db.solva_phase_d_sessions.find(
        {"updated_at": {"$gte": cutoff}, "status": {"$in": ["refused", "blocked_hard"]}},
        {"_id": 0, "layer_3.refusal_reason": 1, "status": 1, "guardrail_primary_classifier": 1},
    ).limit(10000)
    refusal_reason_distribution: Dict[str, int] = {}
    async for s in sess_cursor:
        reason = (
            (s.get("layer_3") or {}).get("refusal_reason")
            or s.get("guardrail_primary_classifier")
            or "unknown"
        )
        refusal_reason_distribution[reason] = refusal_reason_distribution.get(reason, 0) + 1

    top_purposes = sorted(purpose_counts.items(), key=lambda kv: -kv[1])[:10]

    return {
        "window_days": window_days,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "total_invokes": len(rows),
        "per_consumer": consumers,
        "top_purposes": [{"purpose": p, "count": c} for p, c in top_purposes],
        "reidentification_partial_rate": (
            round(reid_partial / len(rows), 4) if rows else 0.0
        ),
        "guardrail_block_counts": solva_refusals,
        "solva_refusal_reasons": refusal_reason_distribution,
    }
