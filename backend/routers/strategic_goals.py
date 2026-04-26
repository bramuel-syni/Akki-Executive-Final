"""Strategic Goals — board-level KPIs tracked against a strategic document.

The Monitor surface displays each function's strategic goals (e.g. "Migrate
to new ERP by Dec 2026", "Grow revenue to $50M by 2026") with current score,
target value, owner department, and probability of success.

The data model:
  • strategic_goals collection — one row per goal
  • Goals are EITHER manually entered, or extracted from an uploaded strategic
    document via LLM parse (`POST .../extract` referencing a documents.id).
  • Goals are tagged to a department (cfo|coo|commercial|ceo|board) so the
    Monitor surface can show only function-relevant rows.

Schema
------
{
  id, context_id, title, description, department, owner_name,
  target_metric, target_value, target_date,         # the "by Dec 2026"
  current_value, current_score (0-100), probability (0-100),
  status: "on_track" | "at_risk" | "off_track" | "achieved" | "abandoned",
  source_doc_id?, source_doc_name?,                  # provenance
  created_at, updated_at
}
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, conint

from core import db, now as _now, iso as _iso, write_audit, require_context_membership
from llm_service import call_llm, parse_json_response

logger = logging.getLogger("akki.strategic_goals")
router = APIRouter(prefix="/api")


Department = Literal["ceo", "cfo", "coo", "commercial", "board"]
Status = Literal["on_track", "at_risk", "off_track", "achieved", "abandoned"]


def sanitize(g: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in g.items() if k != "_id"}


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class GoalIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=600)
    department: Department = "ceo"
    owner_name: Optional[str] = Field(default=None, max_length=120)
    target_metric: Optional[str] = Field(default=None, max_length=160)
    target_value: Optional[str] = Field(default=None, max_length=120)
    target_date: Optional[str] = Field(default=None, max_length=40)
    current_value: Optional[str] = Field(default=None, max_length=120)
    current_score: Optional[conint(ge=0, le=100)] = None
    probability: Optional[conint(ge=0, le=100)] = None
    status: Status = "on_track"


class GoalPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=600)
    department: Optional[Department] = None
    owner_name: Optional[str] = Field(default=None, max_length=120)
    target_metric: Optional[str] = Field(default=None, max_length=160)
    target_value: Optional[str] = Field(default=None, max_length=120)
    target_date: Optional[str] = Field(default=None, max_length=40)
    current_value: Optional[str] = Field(default=None, max_length=120)
    current_score: Optional[conint(ge=0, le=100)] = None
    probability: Optional[conint(ge=0, le=100)] = None
    status: Optional[Status] = None


class ExtractFromDocIn(BaseModel):
    doc_id: str
    replace_existing: bool = False


# -----------------------------------------------------------------------------
# CRUD
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/strategic-goals")
async def list_goals(
    context_id: str,
    department: Optional[str] = None,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """List all goals on this context. Optional `department` filter restricts
    to a single function (cfo|coo|commercial|ceo|board)."""
    q: Dict[str, Any] = {"context_id": context_id}
    if department:
        q["department"] = department
    goals = await db.strategic_goals.find(q, {"_id": 0}).sort("target_date", 1).to_list(200)
    return {"goals": [sanitize(g) for g in goals]}


@router.post("/contexts/{context_id}/strategic-goals")
async def create_goal(
    context_id: str, body: GoalIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    now_iso = _iso(_now())
    goal = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        **body.dict(),
        "score_history": (
            [{"score": body.current_score, "recorded_at": now_iso}]
            if body.current_score is not None else []
        ),
        "created_at": now_iso,
        "updated_at": now_iso,
        "created_by": ctx["account"]["id"],
    }
    await db.strategic_goals.insert_one(goal)
    goal.pop("_id", None)
    await write_audit(context_id, ctx["account"]["id"], "strategic_goal.created", "strategic_goal", goal["id"],
                      {"title": goal["title"], "department": goal["department"]})
    return sanitize(goal)


@router.patch("/contexts/{context_id}/strategic-goals/{goal_id}")
async def update_goal(
    context_id: str, goal_id: str, body: GoalPatch,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        existing = await db.strategic_goals.find_one(
            {"id": goal_id, "context_id": context_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Goal not found")
        return sanitize(existing)

    existing = await db.strategic_goals.find_one(
        {"id": goal_id, "context_id": context_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Goal not found")

    now_iso = _iso(_now())
    updates["updated_at"] = now_iso

    # If the score moved, append a history point and cap at 12 entries.
    push_history = None
    if "current_score" in updates and updates["current_score"] != existing.get("current_score"):
        history = list(existing.get("score_history") or [])
        history.append({"score": updates["current_score"], "recorded_at": now_iso})
        # Cap at 12 trailing points (one per "week" of board cadence).
        history = history[-12:]
        push_history = history

    set_payload: Dict[str, Any] = {**updates}
    if push_history is not None:
        set_payload["score_history"] = push_history

    await db.strategic_goals.update_one(
        {"id": goal_id, "context_id": context_id}, {"$set": set_payload},
    )
    await write_audit(context_id, ctx["account"]["id"], "strategic_goal.updated", "strategic_goal", goal_id, updates)
    fresh = await db.strategic_goals.find_one({"id": goal_id}, {"_id": 0})
    return sanitize(fresh)


@router.delete("/contexts/{context_id}/strategic-goals/{goal_id}")
async def delete_goal(
    context_id: str, goal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.strategic_goals.delete_one({"id": goal_id, "context_id": context_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    await write_audit(context_id, ctx["account"]["id"], "strategic_goal.deleted", "strategic_goal", goal_id, {})
    return {"ok": True}


# -----------------------------------------------------------------------------
# Extract from document
# -----------------------------------------------------------------------------
@router.post("/contexts/{context_id}/strategic-goals/extract")
async def extract_from_document(
    context_id: str, body: ExtractFromDocIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Reads the document's extracted_text and asks Claude to return board-level
    strategic goals as a structured array, then upserts them."""
    doc = await db.documents.find_one(
        {"id": body.doc_id, "context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "name": 1, "extracted_text": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    text = (doc.get("extracted_text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Document has no extracted text to read.")

    sample = text[:18_000]
    prompt = (
        "You are reading a company's strategic plan or board pack. Extract the "
        "board-level strategic goals being tracked. Each goal must be measurable "
        "and tied to a date or deadline. Tag each to ONE department: ceo, cfo, "
        "coo, commercial, or board.\n\n"
        "Return STRICT JSON ONLY:\n"
        "{\"goals\": [{"
        "\"title\": \"<<concise <=120 char goal title>>\", "
        "\"description\": \"<<<=300 char detail>>\", "
        "\"department\": \"<<ceo|cfo|coo|commercial|board>>\", "
        "\"target_metric\": \"<<what's measured, e.g. Annual recurring revenue>>\", "
        "\"target_value\": \"<<the target, e.g. $50M | 99.5% uptime | Dec 2026>>\", "
        "\"target_date\": \"<<deadline as YYYY-MM or 'Q4 2026'>>\", "
        "\"owner_name\": \"<<role title or person, e.g. CFO|VP Engineering>>\", "
        "\"current_value\": \"<<best estimate of current state from the doc, blank if unknown>>\", "
        "\"current_score\": <<0-100 integer best-effort progress, 0 if unknown>>, "
        "\"probability\": <<0-100 integer best-effort confidence in hitting target>>, "
        "\"status\": \"<<on_track|at_risk|off_track|achieved>>\""
        "}, ...]}\n\n"
        "Rules: 5–12 goals max. Skip operational metrics. Only items the BOARD "
        "would track. Do NOT invent specific numeric targets — leave blank if the "
        "doc doesn't say. Use 'on_track' as default status when uncertain.\n\n"
        f"Document title: {doc.get('name')}\n\nText:\n{sample}"
    )

    out = await call_llm(
        module="strategic_goals.extract",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"strat-{context_id}-{body.doc_id}"},
        data_trust={"overall": "trusted"},
        response_format="json",
    )
    parsed = parse_json_response(out.get("response", ""))
    raw_goals = parsed.get("goals") if isinstance(parsed, dict) else None
    if not isinstance(raw_goals, list):
        raise HTTPException(status_code=502, detail=f"LLM returned no parseable goals. Mode={out.get('mode')}.")

    if body.replace_existing:
        await db.strategic_goals.delete_many({"context_id": context_id})

    valid_departments = {"ceo", "cfo", "coo", "commercial", "board"}
    valid_status = {"on_track", "at_risk", "off_track", "achieved", "abandoned"}
    inserted: List[Dict[str, Any]] = []
    now_iso = _iso(_now())
    for raw in raw_goals[:20]:
        if not isinstance(raw, dict) or not raw.get("title"):
            continue
        dept = (raw.get("department") or "ceo").lower()
        if dept not in valid_departments:
            dept = "ceo"
        status = (raw.get("status") or "on_track").lower()
        if status not in valid_status:
            status = "on_track"
        score_seed = _safe_int(raw.get("current_score"))
        goal = {
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "title": str(raw.get("title"))[:180],
            "description": (str(raw.get("description") or "")[:600]) or None,
            "department": dept,
            "owner_name": (str(raw.get("owner_name") or "")[:120]) or None,
            "target_metric": (str(raw.get("target_metric") or "")[:160]) or None,
            "target_value": (str(raw.get("target_value") or "")[:120]) or None,
            "target_date": (str(raw.get("target_date") or "")[:40]) or None,
            "current_value": (str(raw.get("current_value") or "")[:120]) or None,
            "current_score": score_seed,
            "probability": _safe_int(raw.get("probability")),
            "status": status,
            "score_history": (
                [{"score": score_seed, "recorded_at": now_iso}]
                if score_seed is not None else []
            ),
            "source_doc_id": doc["id"],
            "source_doc_name": doc.get("name"),
            "created_at": now_iso,
            "updated_at": now_iso,
            "created_by": ctx["account"]["id"],
        }
        await db.strategic_goals.insert_one(goal)
        goal.pop("_id", None)
        inserted.append(goal)

    await write_audit(context_id, ctx["account"]["id"], "strategic_goal.extracted", "document", doc["id"],
                      {"goals_inserted": len(inserted), "replace_existing": body.replace_existing})
    return {"inserted": [sanitize(g) for g in inserted], "count": len(inserted), "mode": out.get("mode")}


def _safe_int(v: Any) -> Optional[int]:
    try:
        n = int(v)
        if 0 <= n <= 100:
            return n
    except (TypeError, ValueError):
        pass
    return None
