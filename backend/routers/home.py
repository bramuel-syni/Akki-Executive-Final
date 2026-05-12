"""
routers/home.py — Patch 3 Home v2 backend support.

Endpoints:
  • GET  /api/me/recent-views
  • POST /api/me/recent-views
  • GET  /api/contexts/{cid}/home/insights
  • GET  /api/contexts/{cid}/home/whats-new?since=…

Collections:
  • user_recent_views     — { id, account_id, surface_path, label, context_id?, last_visited_at }
  • user_context_visits   — { id, account_id, context_id, last_visited_at }

All counts are deterministic. No LLM call.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso as _iso, now as _now, get_current_account, require_context_membership


router = APIRouter(prefix="/api")


# -----------------------------------------------------------------------------
# Recent views
# -----------------------------------------------------------------------------
class RecentViewIn(BaseModel):
    surface_path: str = Field(..., min_length=1, max_length=300)
    label: str = Field(..., min_length=1, max_length=160)
    context_id: Optional[str] = None


@router.post("/me/recent-views")
async def post_recent_view(
    body: RecentViewIn,
    me: Dict[str, Any] = Depends(get_current_account),
):
    now = _now()
    # Upsert keyed on (account_id, surface_path) so reloads don't bloat the feed.
    await db.user_recent_views.update_one(
        {"account_id": me["id"], "surface_path": body.surface_path},
        {
            "$set": {
                "account_id": me["id"],
                "surface_path": body.surface_path,
                "label": body.label,
                "context_id": body.context_id,
                "last_visited_at": _iso(now),
            },
            "$setOnInsert": {"id": str(uuid.uuid4())},
        },
        upsert=True,
    )
    return {"ok": True}


@router.get("/me/recent-views")
async def get_recent_views(
    limit: int = 3,
    me: Dict[str, Any] = Depends(get_current_account),
):
    limit = max(1, min(20, int(limit or 3)))
    rows = await (
        db.user_recent_views
        .find({"account_id": me["id"]}, {"_id": 0})
        .sort("last_visited_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return {"items": rows}


# -----------------------------------------------------------------------------
# Context visit tracking (used by Home 2 to compute since-last-visit feeds)
# -----------------------------------------------------------------------------
async def _bump_visit(account_id: str, context_id: str) -> str:
    """Record the visit, returning the PREVIOUS visit timestamp (or empty)."""
    now_iso = _iso(_now())
    prev = await db.user_context_visits.find_one(
        {"account_id": account_id, "context_id": context_id},
        {"_id": 0, "last_visited_at": 1},
    )
    prev_ts = (prev or {}).get("last_visited_at") or ""
    await db.user_context_visits.update_one(
        {"account_id": account_id, "context_id": context_id},
        {
            "$set": {
                "account_id": account_id,
                "context_id": context_id,
                "last_visited_at": now_iso,
            },
            "$setOnInsert": {"id": str(uuid.uuid4())},
        },
        upsert=True,
    )
    return prev_ts


# -----------------------------------------------------------------------------
# Home 2 — insight counts (one shot)
# -----------------------------------------------------------------------------
async def _count_compile_ready(context_id: str) -> int:
    """Cycles with readiness >= 80 and status == active."""
    return await db.cycles.count_documents({
        "context_id": context_id,
        "status": "active",
        "readiness_pct": {"$gte": 80},
    })


async def _count_pulse_critical(context_id: str) -> int:
    return await db.signals.count_documents({
        "context_id": context_id,
        "severity": "critical",
        "state": {"$in": ["open", "new", "active", None]},
    })


async def _count_solva_waiting(context_id: str, account_id: str) -> int:
    """Solva session drafts assigned to me."""
    return await db.solva_sessions.count_documents({
        "context_id": context_id,
        "owner_account_id": account_id,
        "status": "draft",
    })


async def _count_signoffs_needed(context_id: str, account_id: str) -> int:
    """NED assignments pending acceptance for me + report sign-offs."""
    n_assign = await db.cycle_assignments.count_documents({
        "context_id": context_id,
        "assigned_to_account_id": account_id,
        "state": "pending",
    })
    return n_assign


async def _count_cycles_closing_this_week(context_id: str) -> int:
    """Active cycles whose expected close lands in the next 7 days."""
    in_week = (_now() + timedelta(days=7)).isoformat()
    return await db.cycles.count_documents({
        "context_id": context_id,
        "status": "active",
        "$and": [
            {"expected_close_at": {"$lte": in_week}},
            {"expected_close_at": {"$ne": None}},
        ],
    })


async def _count_new_documents_since(context_id: str, since_iso: str, account_id: str) -> int:
    """Documents created in this context since `since_iso` by others."""
    if not since_iso:
        return 0
    return await db.documents.count_documents({
        "context_id": context_id,
        "created_at": {"$gt": since_iso},
        "uploaded_by_account_id": {"$ne": account_id},
    })


async def _count_open_questions(context_id: str, account_id: str) -> int:
    """NED questions assigned to the user that are unanswered."""
    return await db.cycle_questions.count_documents({
        "context_id": context_id,
        "assignee_account_id": account_id,
        "status": {"$in": ["open", "pending"]},
    })


@router.get("/contexts/{context_id}/home/insights")
async def home_insights(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Returns 7 leading-insight counts for the active context in one shot.
    Side-effect: records the visit so the next "What's new" query has
    an anchor timestamp."""
    me = ctx["account"]
    prev_visit = await _bump_visit(me["id"], context_id)

    compile_ready = await _count_compile_ready(context_id)
    pulse_critical = await _count_pulse_critical(context_id)
    solva_waiting = await _count_solva_waiting(context_id, me["id"])
    signoffs_needed = await _count_signoffs_needed(context_id, me["id"])
    cycles_closing = await _count_cycles_closing_this_week(context_id)
    new_documents = await _count_new_documents_since(context_id, prev_visit, me["id"])
    open_questions = await _count_open_questions(context_id, me["id"])

    return {
        "context_id": context_id,
        "previous_visit_at": prev_visit or None,
        "insights": {
            "compile_ready":   {"count": compile_ready,   "key": "compile_ready"},
            "pulse_critical":  {"count": pulse_critical,  "key": "pulse_critical"},
            "solva_waiting":   {"count": solva_waiting,   "key": "solva_waiting"},
            "signoffs_needed": {"count": signoffs_needed, "key": "signoffs_needed"},
            "cycles_closing":  {"count": cycles_closing,  "key": "cycles_closing"},
            "new_documents":   {"count": new_documents,   "key": "new_documents"},
            "open_questions":  {"count": open_questions,  "key": "open_questions"},
        },
    }


# -----------------------------------------------------------------------------
# Home 2 — What's new since last visit
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/home/whats-new")
async def home_whats_new(
    context_id: str,
    since: Optional[str] = None,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Returns a chronological feed of context activity since `since`
    (ISO timestamp). If `since` is omitted, uses the user's previous
    recorded visit on this context."""
    me = ctx["account"]
    if not since:
        v = await db.user_context_visits.find_one(
            {"account_id": me["id"], "context_id": context_id},
            {"_id": 0, "last_visited_at": 1},
        )
        since = (v or {}).get("last_visited_at") or ""

    items: List[Dict[str, Any]] = []
    if since:
        # Cycle status changes — recently activated or completed.
        async for c in db.cycles.find(
            {"context_id": context_id, "updated_at": {"$gt": since}},
            {"_id": 0, "id": 1, "title": 1, "status": 1, "updated_at": 1},
        ):
            items.append({
                "kind": "cycle_status",
                "ts": c.get("updated_at"),
                "actor_id": None,
                "label": f"Cycle '{c.get('title','')}' → {c.get('status','—')}",
                "href": f"/app/cycle/{c.get('id')}",
            })

        # New documents.
        async for d in db.documents.find(
            {
                "context_id": context_id,
                "created_at": {"$gt": since},
                "uploaded_by_account_id": {"$ne": me["id"]},
            },
            {"_id": 0, "id": 1, "name": 1, "created_at": 1, "uploaded_by_account_id": 1},
        ).limit(20):
            items.append({
                "kind": "document_new",
                "ts": d.get("created_at"),
                "actor_id": d.get("uploaded_by_account_id"),
                "label": f"New document — {d.get('name','')}",
                "href": f"/app/documents/{d.get('id')}",
            })

        # Critical Pulse signals.
        async for s in db.signals.find(
            {
                "context_id": context_id,
                "severity": "critical",
                "created_at": {"$gt": since},
            },
            {"_id": 0, "id": 1, "title": 1, "created_at": 1},
        ).limit(10):
            items.append({
                "kind": "pulse_critical",
                "ts": s.get("created_at"),
                "actor_id": None,
                "label": f"Critical signal — {s.get('title','')}",
                "href": "/app/pulse",
            })

    # Sort newest first, cap at 10.
    items.sort(key=lambda r: r.get("ts") or "", reverse=True)
    items = items[:10]
    return {
        "context_id": context_id,
        "since": since or None,
        "items": items,
    }
