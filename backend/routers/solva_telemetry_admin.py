"""Phase D.2 admin telemetry endpoints (2026-05-26).

Surfaces the question-key-emission frequency aggregated from
`db.solva_key_emissions`. Used by analytics dashboards / bank-content
maintenance to see which keys are over-emitted (or never emitted) and
where to invest in more variants.

Auth-gated: superadmin / owner only — same gate as
`/api/synisense/engine` admin endpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account


router = APIRouter(prefix="/api/admin/solva", tags=["admin", "solva", "telemetry"])


def _require_admin(current: Dict[str, Any]) -> None:
    """Phase D.2 telemetry endpoints require admin / superadmin.
    Matches the canonical gate used by `routers/admin_shield_backfill.py`
    — `current["is_superadmin"]` is the production-admin marker on
    `admin@akki.ai`. Falls through to the older role/tier checks for
    test-fixture accounts and to support per-tenant admins where
    membership.sub_role == "admin".
    """
    if current.get("is_superadmin"):
        return
    role = (current.get("role") or "").lower()
    tier = (current.get("tier") or "").lower()
    if role in {"superadmin", "owner", "admin"}:
        return
    if tier in {"superadmin", "admin"}:
        return
    raise HTTPException(
        status_code=403,
        detail="Solva telemetry endpoints require admin role.",
    )


@router.get("/key-usage")
async def get_key_usage(
    since: Optional[str] = Query(
        default=None,
        description="ISO-8601 timestamp. Only emissions at-or-after this "
                    "moment are counted. Omit for all-time.",
    ),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Return a sorted list `[{key, count}]` of question-key emission
    frequencies, descending. Useful for bank-content maintenance:
    keys with high emission counts but only one variant (the generic
    fallback) are the priority for variant expansion."""
    _require_admin(current)
    match: Dict[str, Any] = {}
    if since:
        try:
            datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="`since` must be a valid ISO timestamp.") from None
        match["emitted_at"] = {"$gte": since}
    pipeline: List[Dict[str, Any]] = []
    if match:
        pipeline.append({"$match": match})
    pipeline.extend([
        {"$group": {"_id": "$question_key", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
    ])
    rows = await db.solva_key_emissions.aggregate(pipeline).to_list(length=500)
    return {
        "since": since,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_keys": len(rows),
        "items": rows,
    }


@router.get("/variant-coverage")
async def get_variant_coverage(
    user_id: Optional[str] = Query(
        default=None,
        description="Account id to inspect. Omit to report bank-level "
                    "coverage across all users (still admin-only).",
    ),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Companion endpoint: returns `[{question_key, variants_seen, total_in_bank}]`
    so analytics can spot users approaching cycle-complete on a key.
    When called without `user_id` returns global per-key coverage
    aggregated across all users."""
    _require_admin(current)
    from services.solva.voice.question_bank import _resolve_variants

    match: Dict[str, Any] = {}
    if user_id:
        match["user_id"] = user_id
    # Distinct (user_id, question_key, variant_label) rows ARE the seen-set.
    pipeline: List[Dict[str, Any]] = []
    if match:
        pipeline.append({"$match": match})
    pipeline.append({
        "$group": {
            "_id": {"user_id": "$user_id", "question_key": "$question_key"},
            "variants_seen": {"$addToSet": "$variant_label"},
        },
    })
    rows = await db.solva_variant_seen.aggregate(pipeline).to_list(length=2000)
    out: List[Dict[str, Any]] = []
    for r in rows:
        key = r["_id"]["question_key"]
        total_in_bank = len(_resolve_variants(key))
        out.append({
            "user_id":       r["_id"]["user_id"],
            "question_key":  key,
            "variants_seen": sorted(r.get("variants_seen") or []),
            "seen_count":    len(r.get("variants_seen") or []),
            "total_in_bank": total_in_bank,
            "cycle_complete": len(r.get("variants_seen") or []) >= total_in_bank > 0,
        })
    # Sort by cycle-complete first, then by user.
    out.sort(key=lambda x: (not x["cycle_complete"], x["user_id"], x["question_key"]))
    return {
        "user_id_filter": user_id,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "items":          out,
    }
