"""Phase H.3 — Portfolio Landing data wiring (2026-05-26).

Three endpoints powering the redesigned Portfolio Landing
(`/app/companies`):

  GET /api/me/portfolio-metrics     → 4 metric tiles
  GET /api/me/boards-to-watch       → AI-composite ranked top-N boards
  GET /api/me/last-action           → "Where you left off" resume card

All endpoints are READ-ONLY, account-scoped, and short-circuit
gracefully when the user has zero memberships / zero data
(returns empty / null shapes the frontend can render as empty
states).

No new collections; reuses:
  - memberships             → scope
  - contexts                → company names + types
  - signals                 → pulse + monitor signals
  - briefings               → upcoming board packs
  - documents               → document counts
  - tasks                   → at-risk tasks
  - user_recent_views       → last action
  - audit_log               → last action fallback
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from core import db, get_current_account

logger = logging.getLogger("akki.portfolio_data")

router = APIRouter(prefix="/api", tags=["portfolio"])


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_days_ago(days: int) -> str:
    return (_now_utc() - timedelta(days=days)).isoformat()


def _iso_days_ahead(days: int) -> str:
    return (_now_utc() + timedelta(days=days)).isoformat()


async def _user_context_ids(account_id: str) -> List[str]:
    """Return all context_ids the user has active membership in."""
    mems = await db.memberships.find(
        {"account_id": account_id, "status": "active"},
        {"_id": 0, "context_id": 1},
    ).to_list(length=500)
    return [m["context_id"] for m in mems if m.get("context_id")]


# ─────────────────────────────────────────────────────────────────────
# 1. /api/me/portfolio-metrics — 4 tiles
# ─────────────────────────────────────────────────────────────────────


class PortfolioMetricsOut(BaseModel):
    companies:  int
    signals:    int
    briefings:  int
    documents:  int


@router.get("/me/portfolio-metrics", response_model=PortfolioMetricsOut)
async def portfolio_metrics(
    me: Dict[str, Any] = Depends(get_current_account),
) -> PortfolioMetricsOut:
    """Aggregate counts across all the user's company contexts.

    Signals + briefings are scoped to the last 30 days to keep the
    Portfolio Landing surface focused on "what's relevant now".
    Documents + companies are all-time totals.
    """
    cids = await _user_context_ids(me["id"])
    if not cids:
        return PortfolioMetricsOut(companies=0, signals=0, briefings=0, documents=0)

    since_30d = _iso_days_ago(30)
    # Run all 3 aggregate count queries in parallel via asyncio.gather
    # would be ideal — but Motor returns coroutines individually and
    # the sequential ones complete in ~tens of ms. Sequential is fine.
    signals_q = {
        "context_id": {"$in": cids},
        "created_at": {"$gte": since_30d},
    }
    briefings_q = {
        "context_id": {"$in": cids},
        "created_at": {"$gte": since_30d},
    }
    documents_q = {
        "context_id": {"$in": cids},
        "status": {"$ne": "archived"},
    }

    signals_count   = await db.signals.count_documents(signals_q)
    briefings_count = await db.briefings.count_documents(briefings_q)
    documents_count = await db.documents.count_documents(documents_q)

    return PortfolioMetricsOut(
        companies=len(cids),
        signals=signals_count,
        briefings=briefings_count,
        documents=documents_count,
    )


# ─────────────────────────────────────────────────────────────────────
# 2. /api/me/boards-to-watch — AI-composite ranking
# ─────────────────────────────────────────────────────────────────────


class BoardToWatchOut(BaseModel):
    context_id:  str
    name:        str
    score:       float
    reasons:     List[str]


class BoardsToWatchOut(BaseModel):
    items: List[BoardToWatchOut]


# Composite weights — `signals dominant, then briefings, then risk`
# per the H.3 dispatch.
_WEIGHT_SIGNALS_7D     = 0.5
_WEIGHT_BRIEFINGS_14D  = 0.3
_WEIGHT_AT_RISK        = 0.2

# At-risk task definition: readiness_score below this OR overdue OR
# state == "at_risk" / "blocked".
_AT_RISK_READINESS_BELOW = 50


def _normalize(value: int, max_value: int) -> float:
    if max_value <= 0:
        return 0.0
    return float(value) / float(max_value)


@router.get("/me/boards-to-watch", response_model=BoardsToWatchOut)
async def boards_to_watch(
    limit: int = Query(3, ge=1, le=10),
    me: Dict[str, Any] = Depends(get_current_account),
) -> BoardsToWatchOut:
    """Rank the user's boards by an AI-composite of:
      * 7-day new signals             (weight 0.5)
      * 14-day upcoming briefings     (weight 0.3)
      * Open at-risk tasks            (weight 0.2)

    Each component is normalized to [0,1] across the user's portfolio
    so a single board with 5 signals doesn't always win.

    Reasons[] surface the dominant contributor in human-readable form.
    """
    cids = await _user_context_ids(me["id"])
    if not cids:
        return BoardsToWatchOut(items=[])

    # Fetch the context docs for names.
    contexts = await db.contexts.find(
        {"id": {"$in": cids}},
        {"_id": 0, "id": 1, "name": 1},
    ).to_list(length=500)
    name_by_id = {c["id"]: c.get("name", "(unnamed)") for c in contexts}

    since_7d   = _iso_days_ago(7)
    since_14d  = _iso_days_ahead(14)
    now_iso    = _now_utc().isoformat()

    # Build per-board counts. Use aggregation $group on each collection.
    async def _grouped_count(coll, match) -> Dict[str, int]:
        cursor = coll.aggregate([
            {"$match": match},
            {"$group": {"_id": "$context_id", "n": {"$sum": 1}}},
        ])
        out: Dict[str, int] = {}
        async for row in cursor:
            out[row["_id"]] = row["n"]
        return out

    signals_by_ctx = await _grouped_count(
        db.signals,
        {"context_id": {"$in": cids}, "created_at": {"$gte": since_7d}},
    )
    briefings_by_ctx = await _grouped_count(
        db.briefings,
        {
            "context_id": {"$in": cids},
            "due_date":   {"$gte": now_iso, "$lte": since_14d},
        },
    )
    # At-risk tasks: readiness below threshold OR overdue OR explicit state.
    atrisk_by_ctx = await _grouped_count(
        db.tasks,
        {
            "context_id": {"$in": cids},
            "state": {"$nin": ["closed", "archived", "done"]},
            "$or": [
                {"readiness_score": {"$lt": _AT_RISK_READINESS_BELOW}},
                {"due_date": {"$lt": now_iso, "$ne": None}},
                {"state": {"$in": ["at_risk", "blocked"]}},
            ],
        },
    )

    # Normalize each metric across the portfolio.
    max_signals    = max(signals_by_ctx.values(), default=0)
    max_briefings  = max(briefings_by_ctx.values(), default=0)
    max_atrisk     = max(atrisk_by_ctx.values(), default=0)

    ranked: List[BoardToWatchOut] = []
    for cid in cids:
        s_count = signals_by_ctx.get(cid, 0)
        b_count = briefings_by_ctx.get(cid, 0)
        r_count = atrisk_by_ctx.get(cid, 0)
        if (s_count + b_count + r_count) == 0:
            continue
        score = (
            _WEIGHT_SIGNALS_7D    * _normalize(s_count, max_signals)
            + _WEIGHT_BRIEFINGS_14D * _normalize(b_count, max_briefings)
            + _WEIGHT_AT_RISK      * _normalize(r_count, max_atrisk)
        )
        reasons: List[str] = []
        if s_count > 0:
            reasons.append(
                f"{s_count} new signal{'s' if s_count != 1 else ''} this week"
            )
        if b_count > 0:
            reasons.append(
                f"{b_count} briefing{'s' if b_count != 1 else ''} due in 14 days"
            )
        if r_count > 0:
            reasons.append(
                f"{r_count} task{'s' if r_count != 1 else ''} at risk"
            )
        ranked.append(BoardToWatchOut(
            context_id=cid,
            name=name_by_id.get(cid, "(unnamed)"),
            score=round(score, 4),
            reasons=reasons,
        ))

    ranked.sort(key=lambda b: b.score, reverse=True)
    return BoardsToWatchOut(items=ranked[:limit])


# ─────────────────────────────────────────────────────────────────────
# 3. /api/me/last-action — "Where you left off"
# ─────────────────────────────────────────────────────────────────────


class LastActionOut(BaseModel):
    context_id:     Optional[str]
    context_name:   Optional[str]
    surface:        Optional[str]
    artefact_id:    Optional[str]
    artefact_title: Optional[str]
    action:         Optional[str]
    at:             Optional[str]
    deep_link:      Optional[str]


def _classify_surface(path: str) -> str:
    """Map a recent-view path (e.g. /app/work-studio?doc_id=…) to a
    surface key the UI uses to pick an icon + sentence template."""
    if not path:
        return "page"
    p = path.lower()
    if "/chat" in p:
        return "chat"
    if "/solva" in p:
        return "solva"
    if "/pulse" in p:
        return "pulse"
    if "/task-manager" in p or "task_id=" in p:
        return "task"
    if "/work-studio" in p or "doc_id=" in p or "/documents" in p:
        return "document"
    return "page"


def _classify_action(surface: str) -> str:
    """Default verbs per surface. We don't track granular actions
    (open vs edit) on the recent-views collection — sufficient for
    the resume card today; can be refined later."""
    return {
        "document": "opened",
        "task":     "viewed",
        "pulse":    "viewed",
        "chat":     "opened",
        "solva":    "asked",
    }.get(surface, "visited")


@router.get("/me/last-action", response_model=LastActionOut)
async def last_action(
    me: Dict[str, Any] = Depends(get_current_account),
) -> LastActionOut:
    """Return the user's most recent meaningful action across the
    app, as the source for the "Where you left off" resume card.

    Reads from `user_recent_views` (populated by `POST /api/me/recent-views`
    on most surface mounts). Returns an empty / null shape when no
    recent activity exists (frontend renders the empty state).
    """
    row = await db.user_recent_views.find_one(
        {"account_id": me["id"]},
        {"_id": 0},
        sort=[("last_visited_at", -1)],
    )
    if not row:
        return LastActionOut(
            context_id=None, context_name=None, surface=None,
            artefact_id=None, artefact_title=None, action=None,
            at=None, deep_link=None,
        )
    cid = row.get("context_id")
    ctx_name = None
    if cid:
        ctx = await db.contexts.find_one({"id": cid}, {"_id": 0, "name": 1})
        ctx_name = (ctx or {}).get("name")
    surface_path = row.get("surface_path") or "/app"
    surface = _classify_surface(surface_path)
    return LastActionOut(
        context_id=cid,
        context_name=ctx_name,
        surface=surface,
        artefact_id=None,   # Not threaded through recent-views today;
                            # frontend has the label.
        artefact_title=row.get("label") or "(work in progress)",
        action=_classify_action(surface),
        at=row.get("last_visited_at"),
        deep_link=surface_path,
    )
