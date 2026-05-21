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

Phase F Sub-task D adds:

`GET /api/admin/synisense/billing?window_days=7|30&context_id={cid}`

Per-consumer + per-purpose USD-estimate roll-up using the code-
controlled `services/synisense/pricing.py` cost table. ILLUSTRATIVE
only — not invoiced; the UI marks every figure as "estimated".

Superadmin only — uses the existing `is_superadmin` flag on the
account record.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account
from services.synisense.pricing import (
    DEFAULT_FLAT_USD_PER_CALL, PROVIDER_MODEL_PRICING, flat_cost_for,
)


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
    cutoff_iso = cutoff.isoformat()
    # The audit log stores its row timestamp as an ISO string in
    # `timestamp` (no `created_at`). ISO-8601 strings sort
    # lexicographically the same as their datetime equivalents, so
    # a `$gte` against the cutoff's ISO form is correct.
    cursor = db.synisense_audit_log.find(
        {"timestamp": {"$gte": cutoff_iso}},
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


# ─────────────────────────────────────────────────────────────────────
# Phase F Sub-task D — per-tenant Shield billing ESTIMATE surface.
# ─────────────────────────────────────────────────────────────────────
@router.get("/billing")
async def billing_estimate(
    window_days: int = Query(default=7, ge=1, le=30),
    context_id: Optional[str] = Query(default=None),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Compose a per-consumer + per-purpose USD-estimate roll-up.

    Numbers are ILLUSTRATIVE — derived from a code-controlled price
    table (`services/synisense/pricing.py`). No tokens are recorded
    on the Shield audit log yet; the table emits a flat-per-call
    USD value per (provider, model) pair. The frontend MUST label
    this surface "estimated" prominently.

    Filters:
      - `window_days`: 1..30. Audit rows since `now − window_days`.
      - `context_id`: optional. If supplied, narrows the audit query
        to consumers whose audit rows carry this context_id field.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    cutoff_iso = cutoff.isoformat()
    query: Dict[str, Any] = {"timestamp": {"$gte": cutoff_iso}}
    if context_id:
        query["context_id"] = context_id

    cursor = db.synisense_audit_log.find(query, {"_id": 0}).limit(50000)
    rows = await cursor.to_list(length=50000)

    per_consumer: Dict[str, Dict[str, Any]] = {}
    per_purpose: Dict[str, Dict[str, Any]] = {}
    grand_total = 0.0

    for r in rows:
        consumer = r.get("consumer_id") or "unknown"
        purpose = r.get("purpose") or "unknown"
        provider = r.get("llm_provider") or ""
        model = r.get("llm_model") or ""
        unit = flat_cost_for(provider, model)
        grand_total += unit

        c = per_consumer.setdefault(consumer, {
            "consumer_id": consumer, "call_count": 0,
            "estimated_usd": 0.0, "providers": {},
        })
        c["call_count"] += 1
        c["estimated_usd"] += unit
        prov_label = f"{provider}/{model}" if provider and model else "unknown"
        c["providers"][prov_label] = c["providers"].get(prov_label, 0) + 1

        p = per_purpose.setdefault(purpose, {
            "purpose": purpose, "call_count": 0,
            "estimated_usd": 0.0,
        })
        p["call_count"] += 1
        p["estimated_usd"] += unit

    consumers = sorted(
        ({**v, "estimated_usd": round(v["estimated_usd"], 4)}
         for v in per_consumer.values()),
        key=lambda c: -c["estimated_usd"],
    )
    purposes = sorted(
        ({**v, "estimated_usd": round(v["estimated_usd"], 4)}
         for v in per_purpose.values()),
        key=lambda p: -p["estimated_usd"],
    )[:25]

    return {
        "window_days": window_days,
        "context_id": context_id,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "total_calls": len(rows),
        "estimated_total_usd": round(grand_total, 4),
        "per_consumer": consumers,
        "top_purposes_by_cost": purposes,
        "is_illustrative": True,
        "estimate_notes": (
            "Per-call flat USD estimates derived from a code-controlled "
            "table (services/synisense/pricing.py). Not invoiced. "
            "Token-accurate pricing requires Phase G+ metering."
        ),
        "pricing_table_signature": _pricing_signature(),
    }


def _pricing_signature() -> Dict[str, Any]:
    """A short fingerprint of the live pricing table so bank QA can
    detect if the table changed between two snapshots."""
    return {
        "entry_count": len(PROVIDER_MODEL_PRICING),
        "default_flat_usd_per_call": DEFAULT_FLAT_USD_PER_CALL,
        "providers": sorted({p for (p, _m) in PROVIDER_MODEL_PRICING}),
    }



# ─────────────────────────────────────────────────────────────────────
# Chunk 19 C19-005 — Admin cron health endpoint.
#
# Reads the `scheduler_runs` heartbeat collection (created in Chunk 18
# `services/synisense/engine/scheduler_lock.py`) and surfaces the most
# recent run per `job_id`. Bank-QA reviewers expect evidence that
# scheduled work actually runs — this endpoint is the single read for
# that evidence, no cross-referencing required.
# ─────────────────────────────────────────────────────────────────────
@router.get("/cron-health")
async def cron_health(
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> List[Dict[str, Any]]:
    """Latest scheduler heartbeat row per registered job.

    Returns a list ordered by `last_run_at` desc:
      [
        {
          "job_id": "synisense_engine_hourly",
          "last_run_at": "2026-05-21T19:00:00.123456+00:00",
          "status": "ok" | "failed",
          "duration_ms": 1530,
          "summary": {...rule-family counts...},
          "hour_bucket": "20260521-19",
          "replica_id": "agent-env-...-3fca028d",
          "error": null | "RuntimeError: ...",
        },
        ...
      ]

    Empty list when no scheduled work has run yet (e.g. fresh deploy
    pre-top-of-hour). The shape stays the same across job types so a
    single read covers every cron the platform owns today.
    """
    pipeline = [
        {"$sort": {"started_at": -1}},
        {"$group": {
            "_id": "$job_id",
            "doc": {"$first": "$$ROOT"},
        }},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"started_at": -1}},
    ]
    out: List[Dict[str, Any]] = []
    async for row in db.scheduler_runs.aggregate(pipeline):
        started = row.get("started_at")
        hour_bucket = None
        try:
            if isinstance(started, datetime):
                hour_bucket = started.strftime("%Y%m%d-%H")
        except Exception:  # noqa: BLE001
            hour_bucket = None
        out.append({
            "job_id": row.get("job_id"),
            "last_run_at": started.isoformat() if isinstance(started, datetime) else started,
            "status": row.get("status"),
            "duration_ms": row.get("duration_ms"),
            "summary": row.get("summary") or {},
            "hour_bucket": hour_bucket,
            "replica_id": row.get("replica_id"),
            "error": row.get("error"),
        })
    return out
