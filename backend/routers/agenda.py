"""§13.x Agenda Evolution — composes existing data into a 'last-meeting +
what's evolved since' narrative for the Home dashboard.

We do NOT introduce a new 'meetings' model. Instead, we treat the most
recent published report's cycle_name as the meeting label, and surface
what's happened since:

  • Submissions received since the meeting
  • Outstanding checklists past their deadline
  • Reports drafted/edited
  • Briefings published

Returns a flat narrative array the frontend can render as line items.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core import db, get_current_account, require_context_membership

logger = logging.getLogger("akki.agenda")
router = APIRouter(prefix="/api")


@router.get("/contexts/{context_id}/agenda-evolution")
async def get_agenda_evolution(
    context_id: str,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Returns:
        {
          "last_meeting": {
            "cycle_name": "Q1 2026 board pack",
            "happened_at": "2026-04-12T...",
            "report_title": "Q1 2026 management report",
            "agenda": ["Provisioning", "Capital", "Cyber"]   # best-effort
          } | None,
          "since_then": [
            {"actor": "Ruth Kamau", "verb": "answered", "object": "5 of 6 audit questions",
             "at": "2026-04-25T...", "tone": "positive"},
            ...
          ],
          "next_up": "Q2 2026 audit pack — 1 outstanding response"
        }
    """
    # Find the most recent committed/distributed report; that's "the last meeting".
    last_report = await db.reports.find_one(
        {"context_id": context_id, "status": {"$in": ["committed", "distributed", "completed", "approved"]}},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    # Fallback: the most recent draft report (so a fresh tenant still sees something
    # rather than a permanent empty state).
    if not last_report:
        last_report = await db.reports.find_one(
            {"context_id": context_id},
            {"_id": 0},
            sort=[("updated_at", -1)],
        )

    last_meeting = None
    happened_at: Optional[str] = None
    if last_report:
        # Derive a soft "agenda" — top 3 capitalised noun phrases from the body.
        body = (last_report.get("body") or "")
        words = [w.strip(",.()'\"") for w in body.split() if len(w) > 3]
        cap_words = [w for w in words if w[:1].isupper() and not w.isupper()]
        agenda: List[str] = []
        seen = set()
        for w in cap_words:
            lower = w.lower()
            if lower in seen or lower in {"the", "their", "this", "that", "these", "those"}:
                continue
            seen.add(lower)
            agenda.append(w)
            if len(agenda) >= 3:
                break
        happened_at = last_report.get("updated_at") or last_report.get("created_at")
        last_meeting = {
            "cycle_name": last_report.get("cycle_name") or "Last cycle",
            "happened_at": happened_at,
            "report_title": last_report.get("title"),
            "report_id": last_report.get("id"),
            "agenda": agenda or ["Performance", "Risk", "Strategy"],
        }

    # Compose the "since then" narrative — chronological evolution.
    since: List[Dict[str, Any]] = []

    # 1. Submissions received in the last 30 days (or since last meeting).
    cutoff = happened_at or "2020-01-01T00:00:00+00:00"
    sub_cursor = db.submissions.find(
        {"context_id": context_id, "received_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("received_at", -1).limit(10)
    async for s in sub_cursor:
        n = len(s.get("answers") or [])
        since.append({
            "actor": s.get("reportee_name") or "Reportee",
            "verb": "submitted",
            "object": f"{n} {('answer' if n == 1 else 'answers')} on {s.get('cycle_name', 'this cycle')}",
            "at": s.get("received_at"),
            "tone": "positive",
            "category": "inputs",  # Phase 15.3.5 — agenda 4-cluster
        })

    # 2. Outstanding checklists that are past deadline.
    now = datetime.now(timezone.utc)
    cl_cursor = db.checklists.find(
        {"context_id": context_id, "status": "dispatched"},
        {"_id": 0},
    ).sort("dispatched_at", -1).limit(20)
    submitted_keys = set()
    sub_lookup = db.submissions.find({"context_id": context_id}, {"_id": 0, "reportee_id": 1, "checklist_id": 1})
    async for s in sub_lookup:
        if s.get("checklist_id"):
            submitted_keys.add(s["checklist_id"])
        if s.get("reportee_id"):
            submitted_keys.add(s["reportee_id"])

    async for c in cl_cursor:
        if c.get("id") in submitted_keys or c.get("reportee_id") in submitted_keys:
            continue
        deadline_str = c.get("deadline_date") or ""
        try:
            dl = datetime.strptime(deadline_str, "%d %b %Y").replace(tzinfo=timezone.utc)
            if dl < now:
                since.append({
                    "actor": c.get("reportee_name") or "Reportee",
                    "verb": "is overdue",
                    "object": f"on {c.get('cycle_name', 'this cycle')} — due {deadline_str}",
                    "at": c.get("dispatched_at"),
                    "tone": "warning",
                    "category": "overdue",  # Phase 15.3.5 — agenda 4-cluster
                })
        except (ValueError, TypeError):
            pass

    # 3. Reports drafted in the period (excluding the last_meeting one).
    rep_cursor = db.reports.find(
        {"context_id": context_id, "updated_at": {"$gte": cutoff}, "status": {"$nin": ["committed", "distributed", "completed", "approved"]}},
        {"_id": 0},
    ).sort("updated_at", -1).limit(5)
    async for r in rep_cursor:
        if last_report and r.get("id") == last_report.get("id"):
            continue
        since.append({
            "actor": "AKKI",
            "verb": "drafted",
            "object": r.get("title") or "a report from your team's submissions",
            "at": r.get("updated_at"),
            "tone": "neutral",
            "category": "drafts",  # Phase 15.3.5 — agenda 4-cluster
        })

    # 4. Briefings published in the period.
    br_cursor = db.briefings.find(
        {"context_id": context_id, "status": {"$in": ["published", "active"]},
         "$or": [{"published_at": {"$gte": cutoff}}, {"created_at": {"$gte": cutoff}}]},
        {"_id": 0},
    ).sort("created_at", -1).limit(5)
    async for b in br_cursor:
        since.append({
            "actor": "AKKI",
            "verb": "published",
            "object": b.get("title") or "a briefing",
            "at": b.get("published_at") or b.get("created_at"),
            "tone": "neutral",
            "category": "publications",  # Phase 15.3.5 — agenda 4-cluster
        })

    # Phase 15.3.5 — sort most-recent-first and cap at 12 lines so the
    # 4-cluster card (Submissions · Overdue · Drafts · Publications) has
    # up to 3 items per category. Frontend caps each cluster to 3.
    since.sort(key=lambda x: x.get("at") or "", reverse=True)
    since = since[:12]

    # 5. "Next up" — the active checklist or workflow with the soonest deadline.
    next_up = None
    next_cl = await db.checklists.find_one(
        {"context_id": context_id, "status": "dispatched"},
        {"_id": 0},
        sort=[("deadline_date", 1)],
    )
    if next_cl:
        out = await db.checklists.count_documents({
            "context_id": context_id, "status": "dispatched",
            "cycle_name": next_cl.get("cycle_name"),
        })
        next_up = f"{next_cl.get('cycle_name', 'Next cycle')} — {out} response{'s' if out != 1 else ''} still expected"

    return {
        "last_meeting": last_meeting,
        "since_then": since,
        "next_up": next_up,
    }
