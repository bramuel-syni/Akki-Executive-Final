"""AKKI Solva v1 — read-only forensic surface; POSTs retired in Phase A cleanup.

Phase A (post-15.3.5) closes the v1 retirement: every write/turn/handoff
endpoint has been removed. Only GET endpoints survive, and only because
historical v1 sessions still need to be inspectable for governance and
forensic comparison:

  GET /api/solva/clusters                         cluster taxonomy (shared with v2)
  GET /api/solva/pro-status                       legacy plan-affordance probe
  GET /api/solva/sessions                         list user's v1 sessions
  GET /api/solva/sessions/{sid}                   read one v1 session
  GET /api/solva/sessions/{sid}/handoffs          list v1 handoffs
  GET /api/solva/sessions/{sid}/export.pdf        v1 session PDF export

Mongo collections (`solve_sessions`, `solve_clusters`, `solve_comparables`,
`solve_handoffs`, `solve_free_grants`) retain their `solve_` names by
design — renaming a collection is a data-migration risk for zero user
benefit. New work lives under `routers/solva_v2.py`.

The v1 POST surface (start, turn, restart, abandon, handoff/{brief|
decks|cycle}) was decommissioned with HTTP 410 in Phase 15.3.5 and
fully removed in Phase A. Routes now 404 for any v1 POST. Callers must
target `/api/solva/v2/*`.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core import db, get_current_account, iso, now

logger = logging.getLogger("akki.solva.engine")

router = APIRouter(prefix="/api/solva", tags=["solva"])


# ---------------------------------------------------------------------------
# Tiering helper — preserved because GET /pro-status still answers it.
# ---------------------------------------------------------------------------
def _now_month_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _user_is_pro(account: Dict[str, Any]) -> bool:
    """Phase 10 — read the plan LIVE from the DB.

    The product review flagged that a cached `account` dict can hold a
    stale plan when a webhook has just upgraded/downgraded mid-session.
    Every Solva entry-point that makes a tier decision goes through this
    helper.
    """
    aid = account.get("id") if isinstance(account, dict) else None
    if aid:
        fresh = await db.accounts.find_one(
            {"id": aid}, {"_id": 0, "plan": 1, "solve_pro": 1, "subscription_status": 1},
        )
    else:
        fresh = None
    src = fresh if fresh is not None else account
    plan = (src.get("plan") or "free").lower()
    sub_status = (src.get("subscription_status") or "").lower()
    if plan in ("pro", "team") and sub_status in ("", "active", "trialing"):
        return True
    return bool(src.get("solve_pro"))


# ---------------------------------------------------------------------------
# Cluster lookup (read-only)
# ---------------------------------------------------------------------------
@router.get("/clusters")
async def list_clusters(account: Dict[str, Any] = Depends(get_current_account)):
    rows = await db.solve_clusters.find({}, {"_id": 0}).to_list(length=50)
    return {"clusters": rows, "count": len(rows)}


@router.get("/pro-status")
async def get_pro_status(account: Dict[str, Any] = Depends(get_current_account)):
    """Live plan-affordance probe. Solva v2 reads the same values via
    its own helper; this endpoint exists for legacy clients."""
    is_pro = await _user_is_pro(account)
    month = _now_month_utc()
    grant = await db.solve_free_grants.find_one(
        {"account_id": account["id"], "month_utc": month},
        {"_id": 0, "count": 1},
    )
    grant_used = bool(grant and (grant.get("count") or 0) >= 1)
    return {
        "is_pro": is_pro,
        "plan": (account.get("plan") or "free").lower(),
        "free_grant": {
            "claimed_this_month": grant_used,
            "month_utc": month,
            "remaining": 0 if grant_used or is_pro else 1,
        },
    }


# ---------------------------------------------------------------------------
# Session reads — forensic only. Writes live under /api/solva/v2.
# ---------------------------------------------------------------------------
@router.get("/sessions")
async def list_my_sessions(
    status: Optional[str] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    q: Dict[str, Any] = {"account_id": account["id"]}
    if status:
        q["status"] = status
    rows = await db.solve_sessions.find(
        q,
        {"_id": 0, "id": 1, "cluster_id": 1, "cluster_label": 1, "intent": 1,
         "phase": 1, "phase_index": 1, "status": 1, "pro_tier": 1,
         "started_at": 1, "updated_at": 1, "completed_at": 1},
    ).sort("updated_at", -1).to_list(length=100)
    return {"items": rows, "count": len(rows)}


@router.get("/sessions/{sid}")
async def get_session(sid: str, account: Dict[str, Any] = Depends(get_current_account)):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    return rec


@router.get("/sessions/{sid}/handoffs")
async def list_session_handoffs(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0, "id": 1}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    rows = await db.solve_handoffs.find(
        {"session_id": sid}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=20)
    return {"items": rows, "count": len(rows)}


@router.get("/sessions/{sid}/export.pdf")
async def export_session_pdf(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not rec.get("synthesis") and not rec.get("lockin"):
        raise HTTPException(
            status_code=409,
            detail="Solva session has no synthesis to export — finish at least one phase first.",
        )
    from solve_pdf import render_solve_pdf
    pdf_bytes = render_solve_pdf(rec)
    safe_name = "".join(
        ch for ch in (rec.get("intent") or "solva")[:60]
        if ch.isalnum() or ch in (" -_")
    ).strip().replace(" ", "_") or "solva"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="akki_solva_{safe_name}.pdf"'},
    )
