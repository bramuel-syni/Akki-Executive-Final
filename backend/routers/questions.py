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

import re
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


# Q4Y P0-C3 (2026-02 fork-resume) — "Mark as Answered" without
# requiring an answer body. Optional `note` is captured in history
# as the `marked_answered` row. Idempotent.
class MarkAnsweredIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


# Q4Y P0-S1 (2026-02 fork-resume) — three sort keys mapped to
# (field, direction) tuples. Applied in BOTH list endpoints.
_SORT_KEYS = {
    "recent":             ("asked_at",    -1),
    "oldest":             ("asked_at",     1),
    "answered_at_desc":   ("answered_at", -1),
}


def _strip(rec: Dict[str, Any]) -> Dict[str, Any]:
    rec = dict(rec)
    rec.pop("_id", None)
    # Q4Y harness (2026-02) — strip the QA seed marker so it never
    # leaks to clients via either list endpoint or the mark-answered
    # round-trip.
    rec.pop("_qa_seed", None)
    return rec


# -----------------------------------------------------------------------------
# Cross-context: questions assigned to ME
# -----------------------------------------------------------------------------
@router.get("/me/questions")
async def my_questions(
    status: str = "open",
    page: int = 1,
    page_size: int = 10,
    asker_role: Optional[str] = None,
    # Q4Y P0-S1 (2026-02 fork-resume) — sort key. One of:
    #   recent | oldest | answered_at_desc
    # `recent` preserves the legacy default (sort by `asked_at` desc).
    sort: str = "recent",
    # Q4Y P1-F3 (2026-02 fork-resume) — server-side case-insensitive
    # text search. Escapes regex special characters defensively so
    # users can't inject regex syntax. ≤120 chars to bound the regex
    # cost.
    q: Optional[str] = Query(default=None, max_length=120),
    me: Dict[str, Any] = Depends(get_current_account),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(50, int(page_size or 10)))
    mongo_q: Dict[str, Any] = {"assignee_account_id": me["id"]}
    if status and status != "all":
        if status in ("open", "pending"):
            mongo_q["status"] = {"$in": ["open", "pending"]}
        elif status in _STATUS:
            mongo_q["status"] = status
        else:
            raise HTTPException(status_code=400, detail="Unknown status.")
    # Phase I.6 (2026-05-27) — `asker_role` filter param closes the loop
    # from CompanyHome Card 4 clickable subtext segments. Accepted
    # values match the I.5 bucket taxonomy: board / ceo / team. Any
    # other value returns 400.
    if asker_role:
        if asker_role not in ("board", "ceo", "team"):
            raise HTTPException(status_code=400, detail="Unknown asker_role.")
        mongo_q["asker_role"] = asker_role
    # Q4Y P1-F3 — server-side text search. Escapes regex special chars
    # so a question containing literal regex metachars still matches.
    q_text = (q or "").strip()
    if q_text:
        mongo_q["text"] = {"$regex": re.escape(q_text), "$options": "i"}
    # Q4Y P0-S1 — resolve sort key. Unknown keys raise 400 so callers
    # can't silently fall back to a different order.
    if sort not in _SORT_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sort. Use one of {sorted(_SORT_KEYS)}",
        )
    sort_field, sort_dir = _SORT_KEYS[sort]
    total = await db.cycle_questions.count_documents(mongo_q)
    cursor = (
        db.cycle_questions.find(mongo_q, {"_id": 0})
        .sort(sort_field, sort_dir)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_strip(r) async for r in cursor]
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "sort": sort,
    }


# -----------------------------------------------------------------------------
# Context-scoped: list, create, detail, answer
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/cycles/{cycle_id}/questions")
async def list_cycle_questions(
    context_id: str,
    cycle_id: str,
    status: Optional[str] = None,
    asker_role: Optional[str] = None,
    # Q4Y P0-S1 — same sort key contract as `/me/questions`.
    sort: str = "recent",
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id, "cycle_id": cycle_id}
    if status and status != "all":
        if status not in _STATUS:
            raise HTTPException(status_code=400, detail="Unknown status.")
        q["status"] = status
    # Phase I.6 (2026-05-27) — `asker_role` filter param (see note above).
    if asker_role:
        if asker_role not in ("board", "ceo", "team"):
            raise HTTPException(status_code=400, detail="Unknown asker_role.")
        q["asker_role"] = asker_role
    # Q4Y P0-S1 — resolve sort key. Unknown keys raise 400.
    if sort not in _SORT_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sort. Use one of {sorted(_SORT_KEYS)}",
        )
    sort_field, sort_dir = _SORT_KEYS[sort]
    rows = (
        await db.cycle_questions.find(q, {"_id": 0})
        .sort(sort_field, sort_dir)
        .to_list(200)
    )
    return {"items": [_strip(r) for r in rows], "total": len(rows), "sort": sort}


@router.post("/contexts/{context_id}/cycles/{cycle_id}/questions")
async def raise_question(
    context_id: str,
    cycle_id: str,
    body: QuestionIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    me = ctx["account"]
    now_iso = _iso(_now())
    # Phase I.5 (2026-05-27) — derive `asker_role` at insert time so
    # Card 4 decomposition is computed at read time without per-row
    # membership lookups. Memberships lookup is best-effort and
    # NEVER raises; defaults to "team" if anything goes wrong.
    from services.open_questions.asker_role_map import derive_asker_role
    asker_role = await derive_asker_role(me["id"], context_id)
    rec: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "cycle_id": cycle_id,
        "agenda_item_id": body.agenda_item_id,
        "text": body.text.strip(),
        "asked_by_account_id": me["id"],
        "asker_role": asker_role,
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



# -----------------------------------------------------------------------------
# Q4Y P0-C3 (2026-02 fork-resume) — "Mark as Answered" without
# requiring an answer body.
#
# Use case: the question was answered out-of-band (verbally, in a
# meeting, in another tool) and the assignee wants to clear it from
# their queue without inventing fake answer copy.
#
# Idempotent — calling on an already-answered question is a 200
# no-op that returns the current row unchanged. History row is
# appended ONLY on the first transition (or if the previous answer
# was empty and this call adds a note).
#
# Tenant scoping: uses the same `require_context_membership()`
# dependency as the rest of this router. A user without membership
# on the question's context gets a 403 before any read.
# -----------------------------------------------------------------------------
@router.post("/contexts/{context_id}/questions/{question_id}/mark-answered")
async def mark_question_answered(
    context_id: str,
    question_id: str,
    body: MarkAnsweredIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    me = ctx["account"]
    rec = await db.cycle_questions.find_one(
        {"id": question_id, "context_id": context_id},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Question not found.")

    # Idempotent — already answered: return current row unchanged.
    if rec.get("status") == "answered":
        return _strip(rec)

    now_iso = _iso(_now())
    history = list(rec.get("history") or [])
    history.append({
        "ts":       now_iso,
        "kind":     "marked_answered",
        "actor_id": me["id"],
        "note":     ((body.note or "").strip()[:500] if body.note else ""),
    })
    await db.cycle_questions.update_one(
        {"id": question_id, "context_id": context_id},
        {"$set": {
            # NOTE: we explicitly do NOT set `answer_text` — the
            # Submit-answer flow remains the only path that writes
            # a body. The drawer renders an empty-answer state with
            # the history line "Marked answered — {note?}".
            "answered_at":            now_iso,
            "answered_by_account_id": me["id"],
            "status":                 "answered",
            "history":                history,
        }},
    )
    rec2 = await db.cycle_questions.find_one(
        {"id": question_id, "context_id": context_id}, {"_id": 0},
    )
    return _strip(rec2)

