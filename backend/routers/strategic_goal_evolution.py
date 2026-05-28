"""AA.followup.10 (REVISED, 2026-02 fork-resume) — Goal evolution signal feed.

Course-correction on the original AA.followup.10 milestone direction.
The drawer's Progress timeline is OBSERVATIONAL (auto-derived), not
manually managed. This module aggregates existing time-series events
for a single strategic goal into one chronologically-sorted feed.

Sources (no new tables — uses existing collections):
    - `strategic_goals.score_history[]`  → performance score deltas
    - `audit_log`                        → strategic_goal.updated /
                                            strategic_goal.assessed
                                            entries scoped to the goal
    - `documents`                        → docs linked to the goal
                                            (created_at = upload event)
    - `extractions_log`                  → LLM re-extraction runs
                                            on goal-linked docs

Endpoint:

    GET /api/contexts/{cid}/strategic-goals/{gid}/evolution

Response shape:

    {
        "goal_id":   str,
        "context_id": str,
        "events": [
            {
                "id":        str,           # opaque stable id
                "kind":      "score_delta" | "doc_upload" | "ai_reassessment" | "status_change",
                "at":        str (iso),
                "delta":     {              # only for score_delta
                    "metric":   "performance" | "probability",
                    "from":     int,
                    "to":       int,
                    "direction": "up" | "down" | "flat",
                },
                "trigger":   str (one-liner human description),
                "doc_id":    str | null,    # related document if any
                "doc_title": str | null,
            },
            ...
        ]
    }
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core import db, get_current_account


log = logging.getLogger(__name__)


router = APIRouter(prefix="/api/contexts", tags=["strategic-goal-evolution"])


def _stable_id(*parts: Any) -> str:
    """Deterministic id for a derived event so the same event always
    renders with the same key (helpful for the frontend's expand-
    detail state)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return h[:16]


def _direction(prev: Optional[int], curr: int) -> str:
    if prev is None:
        return "flat"
    if curr > prev:
        return "up"
    if curr < prev:
        return "down"
    return "flat"


@router.get("/{context_id}/strategic-goals/{goal_id}/evolution")
async def goal_evolution(
    context_id: str,
    goal_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Aggregate every time-series signal for one goal into a single
    chronological feed."""
    goal = await db.strategic_goals.find_one(
        {"id": goal_id, "context_id": context_id}, {"_id": 0},
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")

    events: List[Dict[str, Any]] = []

    # ── 1. Score deltas from `score_history[]` (performance score).
    prev: Optional[int] = None
    for h in (goal.get("score_history") or []):
        score = int(h.get("score", 0))
        at = h.get("recorded_at") or h.get("at")
        if at is None:
            continue
        events.append({
            "id":      _stable_id(goal_id, "score_delta", at),
            "kind":    "score_delta",
            "at":      at,
            "delta":   {
                "metric":    "performance",
                "from":      prev if prev is not None else score,
                "to":        score,
                "direction": _direction(prev, score),
            },
            "trigger": (
                f"Performance reassessed to {score}%"
                if prev is None or _direction(prev, score) == "flat"
                else f"Performance moved {prev}% → {score}%"
            ),
            "doc_id":    None,
            "doc_title": None,
        })
        prev = score

    # ── 2. Documents linked to this goal (uploads).
    linked_doc_cursor = db.documents.find(
        {
            "context_id": context_id,
            "linked_objective_id": goal_id,
            "deleted_at": {"$exists": False},
        },
        {"_id": 0, "id": 1, "title": 1, "created_at": 1, "category": 1},
    ).sort("created_at", 1)
    linked_docs: List[Dict[str, Any]] = []
    async for d in linked_doc_cursor:
        if not d.get("created_at"):
            continue
        linked_docs.append(d)
        events.append({
            "id":        _stable_id(goal_id, "doc_upload", d["id"]),
            "kind":      "doc_upload",
            "at":        d["created_at"],
            "delta":     None,
            "trigger":   f"New {d.get('category') or 'document'} uploaded: {d.get('title') or '(untitled)'}",
            "doc_id":    d["id"],
            "doc_title": d.get("title"),
        })

    # ── 3. AI reassessments — extractions_log rows on goal-linked docs.
    if linked_docs:
        doc_ids = [d["id"] for d in linked_docs]
        ext_cursor = db.extractions_log.find(
            {"document_id": {"$in": doc_ids}, "context_id": context_id},
            {"_id": 0},
        ).sort("created_at", 1)
        async for ext in ext_cursor:
            if not ext.get("created_at"):
                continue
            doc_id = ext.get("document_id")
            doc = next((d for d in linked_docs if d["id"] == doc_id), {})
            count = int(ext.get("count", 0))
            failures = int(ext.get("failures", 0))
            events.append({
                "id":        _stable_id(goal_id, "ai_reassessment", ext.get("id") or ext.get("created_at")),
                "kind":      "ai_reassessment",
                "at":        ext["created_at"],
                "delta":     None,
                "trigger": (
                    f"AKKI re-evaluated this goal "
                    f"({count} signal{'s' if count != 1 else ''}{', ' + str(failures) + ' failed' if failures else ''})"
                ),
                "doc_id":    doc_id,
                "doc_title": doc.get("title"),
            })

    # ── 4. Status changes — read from audit_log scoped to this goal.
    audit_cursor = db.audit_log.find(
        {
            "context_id": context_id,
            "subject_type": "strategic_goal",
            "subject_id":   goal_id,
            "action":       {"$in": ["strategic_goal.updated", "strategic_goal.assessed"]},
        },
        {"_id": 0},
    ).sort("created_at", 1)
    async for a in audit_cursor:
        diff = (a.get("payload") or {}) if isinstance(a.get("payload"), dict) else {}
        if "status" not in diff:
            continue
        events.append({
            "id":        _stable_id(goal_id, "status_change", a.get("id") or a.get("created_at")),
            "kind":      "status_change",
            "at":        a.get("created_at"),
            "delta":     None,
            "trigger":   f"Status changed to {diff.get('status')}",
            "doc_id":    None,
            "doc_title": None,
        })

    # Sort chronologically (oldest → newest); frontend may reverse.
    events.sort(key=lambda e: e.get("at") or "")

    return {
        "goal_id":    goal_id,
        "context_id": context_id,
        "events":     events,
    }
