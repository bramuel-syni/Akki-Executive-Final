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
import re as _re
import uuid
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Module-level regex + month dict so we don't recompile on every list call.
# (Lifted out of `list_goals` per code review iter48.)
# ---------------------------------------------------------------------------
_TARGET_DATE_ISO = _re.compile(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?$")
_TARGET_DATE_QUARTER = _re.compile(r"^q([1-4])\s+(\d{4})$")
_TARGET_DATE_MONTH = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
    "nov": "11", "dec": "12",
}


def _target_date_sort_key(raw: Optional[str]) -> str:
    """Coerce a varied target_date string to a sortable YYYY-MM-DD key.

    Inputs we honour: "2026-12", "2026-12-31", "Q4 2026", "Dec 2026".
    Anything else (or None) sorts to the bottom via "9999-99-99".
    """
    if not raw:
        return "9999-99-99"
    s = str(raw).strip().lower()
    m = _TARGET_DATE_ISO.match(s)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), (m.group(3) or "01").zfill(2)
        return f"{y}-{mo}-{d}"
    m = _TARGET_DATE_QUARTER.match(s)
    if m:
        q_num = int(m.group(1))
        return f"{m.group(2)}-{q_num * 3:02d}-30"
    for short, num in _TARGET_DATE_MONTH.items():
        mm = _re.match(rf"^{short}[a-z]*\s+(\d{{4}})$", s)
        if mm:
            return f"{mm.group(1)}-{num}-15"
    return "9999-99-99"

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, conint

from core import db, now as _now, iso as _iso, write_audit, require_context_membership
from llm_service import call_llm, parse_json_response

logger = logging.getLogger("akki.strategic_goals")
router = APIRouter(prefix="/api")


Department = Literal["ceo", "cfo", "coo", "commercial", "board"]
Status = Literal["on_track", "at_risk", "off_track", "achieved", "abandoned"]
# Iter40 — strategic goal categorisation (top-row marker on the card).
# Six executive-language categories that map to the typical goal
# vocabulary on a board pack. Defaults to "operations" when AKKI can't
# infer the right one from the source document.
Category = Literal["revenue", "customer", "product", "people", "operations", "compliance"]


def sanitize(g: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in g.items() if k != "_id"}


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class GoalIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=600)
    department: Department = "ceo"
    category: Category = "operations"
    initiatives_count: conint(ge=0, le=99) = 0
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
    category: Optional[Category] = None
    initiatives_count: Optional[conint(ge=0, le=99)] = None
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
    goals = await db.strategic_goals.find(q, {"_id": 0}).to_list(200)
    goals.sort(key=lambda g: (_target_date_sort_key(g.get("target_date")), g.get("title", "")))
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
        **body.model_dump(),
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
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
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
        "coo, commercial, or board. Tag each to ONE category: revenue, customer, "
        "product, people, operations, or compliance. Estimate the number of "
        "ACTIVE INITIATIVES rolling up to the goal (0 if the doc doesn't say).\n\n"
        "Return STRICT JSON ONLY:\n"
        "{\"goals\": [{"
        "\"title\": \"<<concise <=120 char goal title>>\", "
        "\"description\": \"<<<=300 char detail>>\", "
        "\"department\": \"<<ceo|cfo|coo|commercial|board>>\", "
        "\"category\": \"<<revenue|customer|product|people|operations|compliance>>\", "
        "\"initiatives_count\": <<0-99 integer count of active initiatives>>, "
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
        "doc doesn't say. Use 'on_track' as default status when uncertain. "
        "Use 'operations' as default category when uncertain.\n\n"
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
    valid_categories = {"revenue", "customer", "product", "people", "operations", "compliance"}
    valid_status = {"on_track", "at_risk", "off_track", "achieved", "abandoned"}
    inserted: List[Dict[str, Any]] = []
    now_iso = _iso(_now())
    for raw in raw_goals[:20]:
        if not isinstance(raw, dict) or not raw.get("title"):
            continue
        dept = (raw.get("department") or "ceo").lower()
        if dept not in valid_departments:
            dept = "ceo"
        cat = (raw.get("category") or "operations").lower()
        if cat not in valid_categories:
            cat = "operations"
        status = (raw.get("status") or "on_track").lower()
        if status not in valid_status:
            status = "on_track"
        score_seed = _safe_int(raw.get("current_score"))
        # Initiatives — clamp 0..99 to match schema. _safe_int caps at 100
        # which is fine; we floor at 0 for safety.
        try:
            ic = int(raw.get("initiatives_count") or 0)
        except (TypeError, ValueError):
            ic = 0
        ic = max(0, min(99, ic))
        goal = {
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "title": str(raw.get("title"))[:180],
            "description": (str(raw.get("description") or "")[:600]) or None,
            "department": dept,
            "category": cat,
            "initiatives_count": ic,
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
