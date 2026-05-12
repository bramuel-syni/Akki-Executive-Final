"""
routers/questions.py — Patch 14.

CRUD-lite for `cycle_questions`. Used by the Home 2 `open_questions`
insight card destination + the new Questions UI surface.

Endpoints:
  GET    /api/me/questions?status=open|answered|all&page=&page_size=
  GET    /api/contexts/{cid}/cycles/{cycle_id}/questions
  POST   /api/contexts/{cid}/cycles/{cycle_id}/questions
  GET    /api/contexts/{cid}/questions/{question_id}
  POST   /api/contexts/{cid}/questions/{question_id}/answer

Schema for db.cycle_questions:
  {
    id, context_id, cycle_id, agenda_item_id?,
    text, asked_by_account_id, asked_at,
    assignee_account_id, status: open|answered|resolved,
    answer_text?, answered_at?, answered_by_account_id?,
    history: [],
  }
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, iso as _iso, now as _now, get_current_account, require_context_membership


router = APIRouter(prefix="/api")


_STATUS = ("open", "answered", "resolved", "pending")


class QuestionIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    assignee_account_id: Optional[str] = None
    agenda_item_id: Optional[str] = None


class AnswerIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


def _strip(rec: Dict[str, Any]) -> Dict[str, Any]:
    rec = dict(rec)
    rec.pop("_id", None)
    return rec


# -----------------------------------------------------------------------------
# Cross-context: questions assigned to ME
# -----------------------------------------------------------------------------
@router.get("/me/questions")
async def my_questions(
    status: str = "open",
    page: int = 1,
    page_size: int = 10,
    me: Dict[str, Any] = Depends(get_current_account),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(50, int(page_size or 10)))
    q: Dict[str, Any] = {"assignee_account_id": me["id"]}
    if status and status != "all":
        if status in ("open", "pending"):
            q["status"] = {"$in": ["open", "pending"]}
        elif status in _STATUS:
            q["status"] = status
        else:
            raise HTTPException(status_code=400, detail="Unknown status.")
    total = await db.cycle_questions.count_documents(q)
    cursor = (
        db.cycle_questions.find(q, {"_id": 0})
        .sort("asked_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_strip(r) async for r in cursor]
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


# -----------------------------------------------------------------------------
# Context-scoped: list, create, detail, answer
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/cycles/{cycle_id}/questions")
async def list_cycle_questions(
    context_id: str,
    cycle_id: str,
    status: Optional[str] = None,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id, "cycle_id": cycle_id}
    if status and status != "all":
        if status not in _STATUS:
            raise HTTPException(status_code=400, detail="Unknown status.")
        q["status"] = status
    rows = await db.cycle_questions.find(q, {"_id": 0}).sort("asked_at", -1).to_list(200)
    return {"items": [_strip(r) for r in rows], "total": len(rows)}


@router.post("/contexts/{context_id}/cycles/{cycle_id}/questions")
async def raise_question(
    context_id: str,
    cycle_id: str,
    body: QuestionIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    me = ctx["account"]
    now_iso = _iso(_now())
    rec: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "cycle_id": cycle_id,
        "agenda_item_id": body.agenda_item_id,
        "text": body.text.strip(),
        "asked_by_account_id": me["id"],
        "asked_at": now_iso,
        "assignee_account_id": body.assignee_account_id,
        "status": "open",
        "history": [{
            "ts": now_iso, "kind": "raised",
            "actor_id": me["id"],
            "note": f"Raised{' to ' + body.assignee_account_id if body.assignee_account_id else ' (unassigned)'}.",
        }],
    }
    await db.cycle_questions.insert_one(rec.copy())
    return _strip(rec)


@router.get("/contexts/{context_id}/questions/{question_id}")
async def get_question(
    context_id: str,
    question_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rec = await db.cycle_questions.find_one(
        {"id": question_id, "context_id": context_id},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Question not found.")
    return _strip(rec)


@router.post("/contexts/{context_id}/questions/{question_id}/answer")
async def answer_question(
    context_id: str,
    question_id: str,
    body: AnswerIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    me = ctx["account"]
    rec = await db.cycle_questions.find_one(
        {"id": question_id, "context_id": context_id},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Question not found.")
    now_iso = _iso(_now())
    history = rec.get("history") or []
    history.append({
        "ts": now_iso, "kind": "answered",
        "actor_id": me["id"], "note": body.text.strip()[:500],
    })
    await db.cycle_questions.update_one(
        {"id": question_id, "context_id": context_id},
        {"$set": {
            "answer_text": body.text.strip(),
            "answered_at": now_iso,
            "answered_by_account_id": me["id"],
            "status": "answered",
            "history": history,
        }},
    )
    rec2 = await db.cycle_questions.find_one(
        {"id": question_id, "context_id": context_id}, {"_id": 0},
    )
    return _strip(rec2)
