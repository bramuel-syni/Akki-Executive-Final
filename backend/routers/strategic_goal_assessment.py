"""Strategic Goals — "Update Goal" assessment endpoint (Chunk 12, 2026-05-21).

QA-2026-05-16-049 — Strategic-goal drawer rewrite. Replaces the
"Edit this goal" CTA with "Update Goal", which:
  1. Searches the user's documents + signals scoped to the goal.
  2. If relevant material is found, Akki invokes Shield with purpose
     `monitor.strategic_goal.update_assessment` and parses the
     response into structured updates for `current_score`,
     `probability`, and `status`.
  3. Persists the new values + a timestamp + an audit ID.
  4. If no relevant material is found, returns a structured
     `{no_data: True, message: <verbatim>}` payload. Status/score/
     probability are NEVER mutated on the no-data path.

Reuses the patterns established in
`routers/monitor_status_assessment.py` (Chunk 7 / QA-047 fix-pass):
  • engine signals + recent docs gathered first
  • Shield call short-circuited when neither source has content
  • LLM-returned status="not_started" with empty supporting_*_ids
    treated as the no-data path
  • locked verbatim copy on no-data response

The legacy POST /strategic-goals/{id} (manual edit) is left intact
in `routers/strategic_goals.py` — the QA spec wants the EDIT BUTTON
removed from the drawer, not the underlying endpoint (admin/migration
paths may still need it). Frontend hides every manual-edit affordance.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core import db, iso as _iso, now as _now, require_context_membership
from services.synisense.engine.signal_seeder import SIGNAL_COLLECTION
from services.synisense.shield.client import invoke as shield_invoke

log = logging.getLogger("strategic_goal_assessment")

router = APIRouter(prefix="/api")


_STATUS = ("on_track", "at_risk", "off_track", "achieved", "abandoned")


# Verbatim copy from `qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-049`.
_NO_DATA_MESSAGE = (
    "No additional information found for this goal. Please upload a "
    "document with updated performance data so Akki can reassess."
)


class StrategicGoalUpdateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    note: Optional[str] = None


async def _gather_engine_signals(
    tenant_id: str, context_id: str,
) -> List[Dict[str, Any]]:
    cursor = db[SIGNAL_COLLECTION].find(
        {
            "tenant_id": tenant_id,
            "signal_type": {"$in": [
                "anomaly_flag", "compliance_trigger",
                "operational_health", "churn_risk",
            ]},
            "$or": [{"context_id": context_id}, {"context_id": None}],
        },
        {"_id": 0},
    ).sort([("created_at", -1)]).limit(12)
    return [s async for s in cursor]


async def _gather_recent_docs(
    context_id: str, account_id: str,
) -> List[Dict[str, Any]]:
    cursor = db.documents.find(
        {"context_id": context_id, "account_id": account_id},
        {"_id": 0, "id": 1, "name": 1, "summary": 1,
         "extracted_text": 1, "created_at": 1},
    ).sort([("created_at", -1)]).limit(5)
    return [d async for d in cursor]


def _format_update_prompt(
    *, goal: Dict[str, Any],
    signals: List[Dict[str, Any]], docs: List[Dict[str, Any]],
) -> str:
    """Compose the structured prompt sent to Shield.

    The LLM is asked for a constrained JSON shape with `relevant`,
    `current_score`, `probability`, `status`,
    `supporting_signal_ids`, `supporting_doc_ids`, `rationale`. If
    the relevant flag is false OR the supporting_*_ids are both
    empty, we treat it as the no-data path.
    """
    goal_block = (
        f"Title: {goal.get('title')}\n"
        f"Department: {goal.get('department')}\n"
        f"Description: {goal.get('description') or '(none)'}\n"
        f"Target: {goal.get('target_value') or '—'} {goal.get('target_metric') or ''}\n"
        f"Target date: {goal.get('target_date') or '—'}\n"
        f"Current performance score: {goal.get('current_score')}\n"
        f"Current probability: {goal.get('probability')}\n"
        f"Current status: {goal.get('status')}"
    )
    sig_block = ""
    if signals:
        sig_lines = [
            f"  • [{s.get('signal_id') or s.get('id')}] {s.get('signal_type')} — "
            f"{(s.get('headline') or s.get('payload', {}).get('label') or '')[:160]}"
            for s in signals
        ]
        sig_block = "Recent engine signals:\n" + "\n".join(sig_lines)
    else:
        sig_block = "Recent engine signals: (none)"
    doc_block = ""
    if docs:
        doc_lines = [
            f"  • [{d['id']}] {d.get('name') or '(untitled)'} — "
            f"{(d.get('summary') or (d.get('extracted_text') or '')[:240])}"
            for d in docs
        ]
        doc_block = "Recent documents:\n" + "\n".join(doc_lines)
    else:
        doc_block = "Recent documents: (none)"
    return f"""You are Akki, assessing a strategic goal.

GOAL CONTEXT
{goal_block}

EVIDENCE
{sig_block}

{doc_block}

TASK
Determine whether the evidence contains material relevant to THIS
goal. If yes, return updated values. If no, set relevant=false and
leave score/probability/status unchanged.

Respond with ONLY a single JSON object, no prose, no markdown:
{{
  "relevant": true | false,
  "current_score": <int 0-100 or null>,
  "probability": <int 0-100 or null>,
  "status": "on_track" | "at_risk" | "off_track" | "achieved" | "abandoned" | null,
  "supporting_signal_ids": ["..."],
  "supporting_doc_ids": ["..."],
  "rationale": "<one or two sentences explaining the update OR why nothing relevant was found>"
}}

When `relevant` is false, set current_score / probability / status to
null AND leave supporting_*_ids empty. Never invent IDs that are not
in the evidence above.
"""


def _parse_update_response(raw: str) -> Dict[str, Any]:
    """Parse the Shield response into a typed update dict.

    Defensive: tolerates the LLM wrapping the JSON in a ```json fence
    OR adding leading/trailing prose. Falls back to a no-data shape
    on any parse failure.
    """
    if not raw:
        return {"relevant": False, "rationale": "Shield returned empty response."}
    body = raw.strip()
    # Strip ```json … ``` fences.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, re.S)
    if fenced:
        body = fenced.group(1)
    # First {...} candidate.
    obj_match = re.search(r"\{.*\}", body, re.S)
    if not obj_match:
        return {"relevant": False, "rationale": "No JSON found in response."}
    try:
        parsed = json.loads(obj_match.group(0))
    except json.JSONDecodeError:
        return {"relevant": False, "rationale": "JSON parse failed."}
    # Validate / normalise.
    relevant = bool(parsed.get("relevant"))
    status = parsed.get("status")
    if status not in _STATUS:
        status = None
    def _ci(v):
        try:
            n = int(v)
            return n if 0 <= n <= 100 else None
        except (TypeError, ValueError):
            return None
    return {
        "relevant": relevant,
        "current_score": _ci(parsed.get("current_score")),
        "probability": _ci(parsed.get("probability")),
        "status": status,
        "supporting_signal_ids": [s for s in (parsed.get("supporting_signal_ids") or []) if isinstance(s, str)],
        "supporting_doc_ids": [d for d in (parsed.get("supporting_doc_ids") or []) if isinstance(d, str)],
        "rationale": (parsed.get("rationale") or "")[:600],
    }


@router.post("/contexts/{context_id}/strategic-goals/{goal_id}/update")
async def update_strategic_goal(
    context_id: str,
    goal_id: str,
    body: StrategicGoalUpdateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Akki-driven strategic-goal reassessment.

    QA-2026-05-16-049 — replaces the manual "Edit this goal" flow.
    Returns shapes:
      • Success path:
        {goal_id, kind: "strategic_goal", updated: True,
         status, current_score, probability,
         last_akki_update: {assessed_at, audit_id, rationale, ...}}
      • No-data path (no relevant evidence OR LLM said relevant=false):
        {goal_id, kind: "strategic_goal", updated: False,
         no_data: True, message: <verbatim spec copy>,
         last_akki_update: {assessed_at, audit_id, rationale, ...}}

    QA-2026-05-16-048 — RBAC defence-in-depth carries over: NED
    accounts cannot trigger this (read-only on strategic goals).
    """
    if (ctx["account"].get("declared_role") or "").lower() == "ned":
        raise HTTPException(
            status_code=403,
            detail="Strategic goal updates are an Executive-only action. "
                   "NED users have read-only access to strategic goals.",
        )
    account = ctx["account"]
    goal = await db.strategic_goals.find_one(
        {"id": goal_id, "context_id": context_id,
         "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Strategic goal not found.")

    signals = await _gather_engine_signals(
        tenant_id=account["id"], context_id=context_id,
    )
    docs = await _gather_recent_docs(
        context_id=context_id, account_id=account["id"],
    )

    # Short-circuit when there's literally no evidence at all in the
    # context — don't burn a Shield call on a guaranteed no-data
    # outcome.
    if not signals and not docs:
        last = {
            "audit_id": None,
            "assessed_at": _iso(_now()),
            "no_data": True,
            "rationale": "No documents or engine signals available in this context.",
            "supporting_signal_ids": [],
            "supporting_doc_ids": [],
        }
        await db.strategic_goals.update_one(
            {"id": goal_id, "context_id": context_id},
            {"$set": {
                "last_akki_update": last,
                "updated_at": _iso(_now()),
            }},
        )
        return {
            "goal_id": goal_id,
            "kind": "strategic_goal",
            "updated": False,
            "no_data": True,
            "message": _NO_DATA_MESSAGE,
            "last_akki_update": last,
        }

    purpose = "monitor.strategic_goal.update_assessment"
    prompt = _format_update_prompt(goal=goal, signals=signals, docs=docs)

    shield_result = await shield_invoke(
        purpose=purpose,
        content=prompt,
        tenant_id=account["id"],
        consumer_id="monitor",
        user_id=account["id"],
        model_preference="analytical",
        internal_caller=True,
    )

    parsed = _parse_update_response(shield_result.get("response") or "")

    # No-data path #2: LLM signalled relevant=false OR all supporting
    # IDs are empty. Don't mutate score/probability/status — only
    # record the timestamp + audit_id so the drawer can show
    # "Akki last checked: <ts>".
    if (not parsed.get("relevant")) or (
        not parsed.get("supporting_signal_ids")
        and not parsed.get("supporting_doc_ids")
    ):
        last = {
            "audit_id": shield_result.get("audit_id"),
            "assessed_at": _iso(_now()),
            "no_data": True,
            "rationale": parsed.get("rationale") or "",
            "supporting_signal_ids": [],
            "supporting_doc_ids": [],
        }
        await db.strategic_goals.update_one(
            {"id": goal_id, "context_id": context_id},
            {"$set": {
                "last_akki_update": last,
                "updated_at": _iso(_now()),
            }},
        )
        return {
            "goal_id": goal_id,
            "kind": "strategic_goal",
            "updated": False,
            "no_data": True,
            "message": _NO_DATA_MESSAGE,
            "last_akki_update": last,
        }

    # Success path — apply the LLM's updates. Score, probability, and
    # status only change when the LLM returned a non-null value;
    # absence means "no change".
    set_doc: Dict[str, Any] = {"updated_at": _iso(_now())}
    if parsed["current_score"] is not None:
        set_doc["current_score"] = parsed["current_score"]
        # Append to score_history for the drawer timeline.
        await db.strategic_goals.update_one(
            {"id": goal_id, "context_id": context_id},
            {"$push": {"score_history": {
                "recorded_at": _iso(_now()),
                "score": parsed["current_score"],
                "note": (parsed.get("rationale") or "")[:160],
                "source": "akki_update",
            }}},
        )
    if parsed["probability"] is not None:
        set_doc["probability"] = parsed["probability"]
    if parsed["status"] is not None:
        set_doc["status"] = parsed["status"]
    last = {
        "audit_id": shield_result.get("audit_id"),
        "assessed_at": _iso(_now()),
        "no_data": False,
        "rationale": parsed.get("rationale") or "",
        "supporting_signal_ids": parsed.get("supporting_signal_ids") or [],
        "supporting_doc_ids": parsed.get("supporting_doc_ids") or [],
        "applied_changes": {
            k: v for k, v in {
                "current_score": parsed["current_score"],
                "probability": parsed["probability"],
                "status": parsed["status"],
            }.items() if v is not None
        },
    }
    set_doc["last_akki_update"] = last
    await db.strategic_goals.update_one(
        {"id": goal_id, "context_id": context_id},
        {"$set": set_doc},
    )

    # Refetch to return the post-update shape.
    updated = await db.strategic_goals.find_one(
        {"id": goal_id, "context_id": context_id},
        {"_id": 0},
    )
    return {
        "goal_id": goal_id,
        "kind": "strategic_goal",
        "updated": True,
        "no_data": False,
        "current_score": updated.get("current_score"),
        "probability": updated.get("probability"),
        "status": updated.get("status"),
        "last_akki_update": last,
    }
