"""Sandbox conversion KPI — superadmin-only analytics for the Q5 objective
loop.

Surfaces the data the user feedback doc explicitly asked us to capture:
"we use this to measure later whether AKKI delivered on it."

Endpoints:
  GET /api/admin/sandbox/kpi  — aggregate view across sandbox + seeded
                                 contexts. Per-sector conversion +
                                 objective-delivery breakdown.
  GET /api/admin/sandbox/objectives — full list of captured objectives,
                                       most recent first, paginated.

Restricted to `accounts.is_superadmin == true`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core import db, get_current_account

router = APIRouter(prefix="/api/admin")


def _require_superadmin(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    return current


def _flatten_meta(ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the metadata branch (sandbox or seeded) that carries the
    objective + check, or None if neither is populated."""
    meta = ctx.get("sandbox_metadata") or ctx.get("seeded_metadata")
    if not meta or not (meta.get("objective") or "").strip():
        return None
    return meta


@router.get("/sandbox/kpi")
async def sandbox_kpi(_: Dict[str, Any] = Depends(_require_superadmin)):
    """Aggregate KPIs across every context that captured a Q5 objective.

    Returns:
        {
          "totals": {
            "with_objective": int,
            "answered": int,
            "yes": int, "partial": int, "no": int, "skipped": int,
            "answer_rate_pct": float,        # answered / (with_objective_eligible)
            "delivery_rate_pct": float,      # yes / answered
          },
          "by_sector": [
            {"sector": str, "with_objective": int, "yes": int, "partial": int,
             "no": int, "skipped": int, "answered": int,
             "delivery_rate_pct": float},
            ...
          ]
        }
    """
    cursor = db.contexts.find(
        {
            "$or": [
                {"sandbox_metadata.objective": {"$exists": True, "$ne": None}},
                {"seeded_metadata.objective":  {"$exists": True, "$ne": None}},
            ],
        },
        {
            "_id": 0, "id": 1, "type": 1,
            "sandbox_metadata.objective": 1,
            "sandbox_metadata.objective_check": 1,
            "sandbox_metadata.intake_inputs.sector": 1,
            "seeded_metadata.objective": 1,
            "seeded_metadata.objective_check": 1,
            "seeded_metadata.intake_inputs.sector": 1,
        },
    )

    by_sector: Dict[str, Dict[str, Any]] = {}
    totals = {
        "with_objective": 0, "answered": 0,
        "yes": 0, "partial": 0, "no": 0, "skipped": 0,
    }

    async for ctx in cursor:
        meta = _flatten_meta(ctx)
        if not meta:
            continue
        sector = ((meta.get("intake_inputs") or {}).get("sector")) or "unknown"
        if sector not in by_sector:
            by_sector[sector] = {
                "sector": sector, "with_objective": 0,
                "yes": 0, "partial": 0, "no": 0, "skipped": 0,
                "answered": 0,
            }

        totals["with_objective"] += 1
        by_sector[sector]["with_objective"] += 1

        check = meta.get("objective_check") or {}
        if check.get("dismissed"):
            totals["skipped"] += 1
            by_sector[sector]["skipped"] += 1
        elif check.get("answered_at"):
            ans = (check.get("answer") or "").lower()
            if ans in ("yes", "partial", "no"):
                totals["answered"] += 1
                totals[ans] += 1
                by_sector[sector]["answered"] += 1
                by_sector[sector][ans] += 1

    def _delivery_rate(b: Dict[str, Any]) -> float:
        return round((b["yes"] / b["answered"] * 100), 1) if b["answered"] > 0 else 0.0

    sectors_out = []
    for s in by_sector.values():
        s = {**s, "delivery_rate_pct": _delivery_rate(s)}
        sectors_out.append(s)
    sectors_out.sort(key=lambda x: x["with_objective"], reverse=True)

    answer_rate = (
        round((totals["answered"] / totals["with_objective"] * 100), 1)
        if totals["with_objective"] > 0 else 0.0
    )
    delivery_rate = (
        round((totals["yes"] / totals["answered"] * 100), 1)
        if totals["answered"] > 0 else 0.0
    )

    return {
        "totals": {
            **totals,
            "answer_rate_pct": answer_rate,
            "delivery_rate_pct": delivery_rate,
        },
        "by_sector": sectors_out,
    }


@router.get("/sandbox/objectives")
async def sandbox_objectives_list(
    _: Dict[str, Any] = Depends(_require_superadmin),
    limit: int = 50,
    sector: Optional[str] = None,
    answer: Optional[str] = None,
):
    """Most-recent-first list of captured objectives, with answer + note.

    Optional query params:
      sector — filter by intake sector
      answer — filter by 'yes' | 'partial' | 'no' | 'skipped' | 'pending'
    """
    cursor = db.contexts.find(
        {
            "$or": [
                {"sandbox_metadata.objective": {"$exists": True, "$ne": None}},
                {"seeded_metadata.objective":  {"$exists": True, "$ne": None}},
            ],
        },
        {
            "_id": 0, "id": 1, "name": 1, "type": 1, "created_at": 1,
            "sandbox_metadata": 1, "seeded_metadata": 1,
        },
    ).sort("created_at", -1)

    rows: List[Dict[str, Any]] = []
    async for ctx in cursor:
        meta = _flatten_meta(ctx)
        if not meta:
            continue
        s = ((meta.get("intake_inputs") or {}).get("sector")) or "unknown"
        if sector and s != sector:
            continue
        check = meta.get("objective_check") or {}
        if check.get("dismissed"):
            ans_label = "skipped"
        elif check.get("answered_at"):
            ans_label = (check.get("answer") or "").lower()
        else:
            ans_label = "pending"
        if answer and ans_label != answer:
            continue
        rows.append({
            "context_id": ctx["id"],
            "company_name": ctx.get("name"),
            "context_type": ctx.get("type"),
            "sector": s,
            "objective": meta.get("objective"),
            "generated_at": meta.get("generated_at"),
            "answer": ans_label,
            "answered_at": check.get("answered_at"),
            "note": check.get("note"),
        })
        if len(rows) >= limit:
            break
    return {"items": rows, "count": len(rows)}
