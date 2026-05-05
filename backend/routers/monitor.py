"""§4 Monitor — role-adaptive mission-critical touchpoints.

The Monitor surface gives executives a "what should I be paying attention
to as a [CEO|CFO|COO|Commercial|NED] right now" view. It composes from
existing collections (signals, checklists, submissions, reports, briefings,
documents, document_views) without introducing a new model.

Function-aware filtering:
  • CEO        — cross-functional pulse (everything important)
  • CFO        — financial + audit + risk signals; financial-area reportees
  • COO        — operational signals; operational-area reportees
  • Commercial — strategic + opportunity + customer signals
  • NED        — cross-board reading: meetings approaching, open threads
  • Other      — generic executive view

Reportee area-of-ownership is matched fuzzily against role keywords so
the user doesn't have to tag reportees with a function — we pattern-match
on the area strings ("Audit", "Risk", "Sales", "Operations" …).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, require_context_membership

logger = logging.getLogger("akki.monitor")
router = APIRouter(prefix="/api")


# Function → category whitelist for signals + area keywords for reportees.
FUNCTION_FILTERS: Dict[str, Dict[str, List[str]]] = {
    "ceo": {
        "signal_categories": [],  # all
        "reportee_area_keywords": [],  # all
    },
    "cfo": {
        "signal_categories": ["financial", "risk", "audit", "regulatory"],
        "reportee_area_keywords": ["finance", "financial", "audit", "treasury", "tax", "risk", "compliance"],
    },
    "coo": {
        "signal_categories": ["operational", "people", "risk"],
        "reportee_area_keywords": ["operations", "operational", "people", "hr", "supply", "logistics", "delivery", "service"],
    },
    "commercial": {
        "signal_categories": ["strategic", "opportunity"],
        "reportee_area_keywords": ["sales", "commercial", "marketing", "customer", "growth", "revenue", "product"],
    },
    "ned": {
        "signal_categories": [],
        "reportee_area_keywords": [],
    },
    "other": {
        "signal_categories": [],
        "reportee_area_keywords": [],
    },
}


def _match_reportee(reportee: Dict[str, Any], keywords: List[str]) -> bool:
    if not keywords:
        return True
    haystack = " ".join([
        (reportee.get("title") or ""),
        " ".join(reportee.get("areas") or []),
    ]).lower()
    return any(k in haystack for k in keywords)


@router.get("/contexts/{context_id}/monitor")
async def get_monitor(
    context_id: str,
    function: str = Query("ceo", regex="^(ceo|cfo|coo|commercial|ned|other)$"),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Returns the role-adaptive Monitor payload."""
    filters = FUNCTION_FILTERS.get(function, FUNCTION_FILTERS["other"])
    cat_whitelist = filters["signal_categories"]
    area_keywords = filters["reportee_area_keywords"]

    # ── Signals (filtered by category whitelist if any)
    sig_q: Dict[str, Any] = {"context_id": context_id}
    if cat_whitelist:
        sig_q["category"] = {"$in": cat_whitelist}
    signals = await db.signals.find(sig_q, {"_id": 0}).sort("created_at", -1).to_list(50)

    high_signals = [s for s in signals if s.get("confidence") == "high"]
    risk_signals = [s for s in signals if s.get("type") == "risk"]
    opportunity_signals = [s for s in signals if s.get("type") == "opportunity"]

    # ── Cycle (reportees + outstanding)
    reportees_all = await db.reportees.find(
        {"context_id": context_id, "status": "active"}, {"_id": 0},
    ).to_list(200)
    reportees = [r for r in reportees_all if _match_reportee(r, area_keywords)]
    reportee_ids = {r["id"] for r in reportees}

    checklists = await db.checklists.find(
        {"context_id": context_id, "status": {"$in": ["dispatched", "pending_approval"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    if reportee_ids:
        checklists = [c for c in checklists if c.get("reportee_id") in reportee_ids]

    submissions = await db.submissions.find(
        {"context_id": context_id}, {"_id": 0},
    ).sort("received_at", -1).to_list(200)
    submitted_keys: set = set()
    for s in submissions:
        if s.get("reportee_id"):
            submitted_keys.add(s["reportee_id"])
        if s.get("checklist_id"):
            submitted_keys.add(s["checklist_id"])

    now = datetime.now(timezone.utc)
    overdue: List[Dict[str, Any]] = []
    awaiting_approval: List[Dict[str, Any]] = []
    in_flight: List[Dict[str, Any]] = []
    for c in checklists:
        if c.get("status") == "pending_approval":
            awaiting_approval.append(c)
            continue
        responded = (c.get("id") in submitted_keys) or (c.get("reportee_id") in submitted_keys)
        if responded:
            continue
        deadline_str = c.get("deadline_date") or ""
        try:
            dl = datetime.strptime(deadline_str, "%d %b %Y").replace(tzinfo=timezone.utc)
            if dl < now:
                overdue.append({**c, "_overdue_days": (now - dl).days})
                continue
        except (ValueError, TypeError):
            pass
        in_flight.append(c)

    # ── Reports awaiting your action (drafts + reviews where you're current)
    account_email = (ctx["account"].get("email") or "").lower()
    reports_pending: List[Dict[str, Any]] = []
    rep_cursor = db.reports.find(
        {"context_id": context_id, "status": {"$in": ["draft", "in_review"]}},
        {"_id": 0},
    ).sort("updated_at", -1)
    async for r in rep_cursor:
        if r.get("status") == "draft":
            if r.get("created_by") == ctx["account"]["id"]:
                reports_pending.append({"id": r["id"], "title": r.get("title"), "stage": "draft", "updated_at": r.get("updated_at")})
        elif r.get("status") == "in_review":
            chain = r.get("chain", []) or []
            current = next((t for t in chain if t.get("status") == "pending"), None)
            if current and (current.get("email") or "").lower() == account_email:
                reports_pending.append({
                    "id": r["id"], "title": r.get("title"), "stage": "review",
                    "updated_at": r.get("updated_at"),
                })

    # ── Briefings (recent)
    briefings = await db.boardpacks.find(
        {"context_id": context_id}, {"_id": 0, "items": 0},
    ).sort("created_at", -1).to_list(5)

    # ── Document engagement — your most-read docs in the last 30 days
    cutoff_30 = (now - timedelta(days=30)).isoformat()
    your_docs_cursor = db.documents.find(
        {"context_id": context_id, "uploaded_by": ctx["account"]["id"], "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "name": 1, "created_at": 1},
    ).sort("created_at", -1)
    your_docs: List[Dict[str, Any]] = []
    async for d in your_docs_cursor:
        views = await db.document_views.find(
            {"doc_id": d["id"], "viewed_at": {"$gte": cutoff_30}},
            {"_id": 0, "account_id": 1, "view_count": 1},
        ).to_list(500)
        unique = len({v["account_id"] for v in views if v.get("account_id") != ctx["account"]["id"]})
        if unique > 0:
            your_docs.append({"id": d["id"], "name": d.get("name"), "unique_readers": unique})
        if len(your_docs) >= 8:
            break

    # ── NED-specific: cross-board pulse (the active context's most-recent + counts)
    ned_extra: Optional[Dict[str, Any]] = None
    if function == "ned":
        # Open threads: unanswered comments mentioning the user across artefacts
        mentions = await db.mentions.find(
            {"target_account_id": ctx["account"]["id"], "read": False},
            {"_id": 0},
        ).sort("created_at", -1).to_list(20)
        ned_extra = {
            "open_threads": len(mentions),
            "recent_mentions": [{
                "preview": m.get("preview"),
                "context_id": m.get("context_id"),
                "created_at": m.get("created_at"),
            } for m in mentions[:5]],
        }

    return {
        "function": function,
        "as_of": now.isoformat(),
        "signals": {
            "total": len(signals),
            "high_confidence": len(high_signals),
            "risks": len(risk_signals),
            "opportunities": len(opportunity_signals),
            "top": [{
                "id": s["id"], "type": s.get("type"), "headline": s.get("headline"),
                "confidence": s.get("confidence"), "category": s.get("category"),
                "created_at": s.get("created_at"),
            } for s in signals[:5]],
        },
        "cycle": {
            "matched_reportees": len(reportees),
            "overdue": [{
                "id": c["id"], "reportee_name": c.get("reportee_name"),
                "cycle_name": c.get("cycle_name"), "deadline_date": c.get("deadline_date"),
                "overdue_days": c.get("_overdue_days", 0),
            } for c in overdue[:6]],
            "awaiting_approval": [{
                "id": c["id"], "reportee_name": c.get("reportee_name"),
                "cycle_name": c.get("cycle_name"), "questions_count": len(c.get("questions") or []),
            } for c in awaiting_approval[:6]],
            "in_flight": [{
                "id": c["id"], "reportee_name": c.get("reportee_name"),
                "cycle_name": c.get("cycle_name"), "deadline_date": c.get("deadline_date"),
            } for c in in_flight[:6]],
        },
        "reports_pending": reports_pending[:6],
        "briefings_recent": [{
            "id": b["id"], "title": b.get("title"), "version": b.get("version"),
            "created_at": b.get("created_at"),
        } for b in briefings],
        "document_engagement": your_docs,
        "ned": ned_extra,
    }
