"""Cycle Manager v2 — multi-cycle master endpoints.

Routes:
  POST   /api/contexts/{cid}/cycles                — create draft
  GET    /api/contexts/{cid}/cycles                — paginated, search + sort
  GET    /api/contexts/{cid}/cycles/{cycle_id}     — detail + counts + readiness
  POST   /api/contexts/{cid}/cycles/{cycle_id}/activate
  POST   /api/contexts/{cid}/cycles/{cycle_id}/close

The `cycles` collection is the new master. `cycle_agendas` continues
to hold the items but is now keyed by `cycle_id` (= `cycle_agendas.id`).
See `services/cycle_lifecycle.py` for the shared helpers.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership, write_audit
from services.cycle_lifecycle import (
    CYCLE_STATUSES,
    compute_cycle_counts,
    compute_readiness_score,
    get_cycle_or_404,
)

logger = logging.getLogger("akki.cycles")

router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────
class CycleCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class CycleOut(BaseModel):
    id: str
    context_id: str
    title: str
    status: str
    created_at: str
    activated_at: Optional[str] = None
    closed_at: Optional[str] = None
    readiness_score: Optional[int] = None
    agenda_count: int = 0
    contributor_count: int = 0


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
async def _persist_agenda_shell(cycle_id: str, context_id: str, account_id: str, title: str) -> None:
    """Create the matching `cycle_agendas` row with the same id so the
    legacy single-cycle endpoints continue to resolve it. Idempotent."""
    existing = await db.cycle_agendas.find_one({"id": cycle_id}, {"_id": 0, "id": 1})
    if existing:
        return
    await db.cycle_agendas.insert_one({
        "id": cycle_id,
        "cycle_id": cycle_id,  # alias for new code paths
        "context_id": context_id,
        "account_id": account_id,
        "title": title,
        "items": [],
        "status": "active",  # legacy field — the new state lives on db.cycles
        "created_at": iso(now()),
        "updated_at": iso(now()),
    })


async def _hydrate_cycle(row: Dict[str, Any]) -> Dict[str, Any]:
    counts = await compute_cycle_counts(row["id"])
    readiness = await compute_readiness_score(row["id"])
    return {
        **row,
        "agenda_count": counts["agenda_count"],
        "contributor_count": counts["contributor_count"],
        "readiness_score": readiness,
    }


# ─────────────────────────────────────────────────────────────────────
# 1. Create
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles", status_code=201)
async def create_cycle(
    context_id: str,
    body: CycleCreateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    cycle_id = str(uuid.uuid4())
    title = body.title.strip()
    now_iso = iso(now())
    row = {
        "id": cycle_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "title": title,
        "status": "draft",
        "created_at": now_iso,
        "activated_at": None,
        "closed_at": None,
    }
    await db.cycles.insert_one(row)
    await _persist_agenda_shell(cycle_id, context_id, ctx["account"]["id"], title)
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.created", "cycle", cycle_id,
        {"title": title},
    )
    return {
        "id": cycle_id,
        "context_id": context_id,
        "title": title,
        "status": "draft",
        "created_at": now_iso,
        "activated_at": None,
        "closed_at": None,
        "readiness_score": None,
        "agenda_count": 0,
        "contributor_count": 0,
        "redirect_url": f"/app/cycle/{cycle_id}?tab=agenda",
    }


# ─────────────────────────────────────────────────────────────────────
# 2. List (paginated + searchable + sortable)
# ─────────────────────────────────────────────────────────────────────
_SORT_MAP = {
    "recent":  [("created_at", -1)],
    "oldest":  [("created_at", 1)],
    "alpha":   [("title", 1)],
    "status":  None,  # custom — active > draft > completed
}


@router.get("/contexts/{context_id}/cycles")
async def list_cycles(
    context_id: str,
    q: Optional[str] = Query(default=None, max_length=200),
    sort: str = Query(default="recent", pattern=r"^(recent|oldest|alpha|status)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=60),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    filt: Dict[str, Any] = {"context_id": context_id}
    if q:
        # Mongo regex on title — case-insensitive, escaped.
        filt["title"] = {"$regex": re.escape(q.strip()), "$options": "i"}

    total = await db.cycles.count_documents(filt)

    if sort == "status":
        # Custom server-side sort: active > draft > completed, then recency.
        cur = db.cycles.find(filt, {"_id": 0})
        rows = await cur.to_list(2000)
        order = {"active": 0, "draft": 1, "completed": 2}
        rows.sort(key=lambda r: (
            order.get((r.get("status") or "draft"), 3),
            -1 * (r.get("created_at") or "").__hash__()  # stable secondary
        ))
        # Secondary sort by created_at desc — re-sort with stable comparator.
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        rows.sort(key=lambda r: order.get((r.get("status") or "draft"), 3))
        rows = rows[(page - 1) * page_size : page * page_size]
    else:
        sort_spec = _SORT_MAP[sort]
        cur = db.cycles.find(filt, {"_id": 0}).sort(sort_spec)
        cur = cur.skip((page - 1) * page_size).limit(page_size)
        rows = await cur.to_list(page_size)

    cycles_out: List[Dict[str, Any]] = []
    for r in rows:
        cycles_out.append(await _hydrate_cycle(r))

    return {
        "cycles": cycles_out,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "sort": sort,
        "q": q or "",
    }


# ─────────────────────────────────────────────────────────────────────
# 3. Detail
# ─────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycles/{cycle_id}")
async def get_cycle(
    context_id: str,
    cycle_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await get_cycle_or_404(context_id, cycle_id)
    return await _hydrate_cycle(row)


# ─────────────────────────────────────────────────────────────────────
# 4. Activate (draft → active)
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles/{cycle_id}/activate")
async def activate_cycle(
    context_id: str,
    cycle_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await get_cycle_or_404(context_id, cycle_id)
    if (row.get("status") or "draft") == "completed":
        raise HTTPException(status_code=409, detail="Completed cycles cannot be re-activated.")
    if (row.get("status") or "draft") == "active":
        return await _hydrate_cycle(row)  # idempotent
    if not (row.get("title") or "").strip():
        raise HTTPException(status_code=400, detail="Cycle title is required to activate.")
    # Require at least one agenda item.
    agenda = await db.cycle_agendas.find_one({"id": cycle_id}, {"_id": 0, "items": 1})
    if not agenda or not (agenda.get("items") or []):
        raise HTTPException(
            status_code=400,
            detail="At least one agenda item is required to activate a cycle.",
        )
    now_iso = iso(now())
    await db.cycles.update_one(
        {"id": cycle_id, "context_id": context_id},
        {"$set": {"status": "active", "activated_at": now_iso}},
    )
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.activated", "cycle", cycle_id, {},
    )
    return await _hydrate_cycle(await get_cycle_or_404(context_id, cycle_id))


# ─────────────────────────────────────────────────────────────────────
# 5. Close (active → completed)
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles/{cycle_id}/close")
async def close_cycle(
    context_id: str,
    cycle_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await get_cycle_or_404(context_id, cycle_id)
    if (row.get("status") or "draft") == "completed":
        return await _hydrate_cycle(row)  # idempotent
    if (row.get("status") or "draft") == "draft":
        raise HTTPException(status_code=400, detail="Cannot close a draft cycle. Activate first.")
    now_iso = iso(now())
    readiness = await compute_readiness_score(cycle_id)
    await db.cycles.update_one(
        {"id": cycle_id, "context_id": context_id},
        {"$set": {
            "status": "completed",
            "closed_at": now_iso,
            "final_readiness_score": readiness,
        }},
    )
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.closed", "cycle", cycle_id,
        {"final_readiness_score": readiness},
    )
    return await _hydrate_cycle(await get_cycle_or_404(context_id, cycle_id))
