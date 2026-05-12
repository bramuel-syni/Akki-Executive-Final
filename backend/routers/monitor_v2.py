"""
routers/monitor_v2.py — Patch 5 Monitor v2 (Objectives & Projects).

CRUD endpoints under `/api/contexts/{cid}/monitor/...` for the new
`objectives` and `projects` collections, plus auto-suggest endpoints
that surface candidates from existing cycles + Solva sessions.

All RAG fields are deterministic. No LLM.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso as _iso, now as _now, require_context_membership


router = APIRouter(prefix="/api")


_RAG = ("red", "amber", "green")
_TREND = ("up", "flat", "down")
_SOURCE = ("auto", "manual", "hybrid")
_KIND = ("objective", "project")


def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    rec = dict(rec)
    rec.pop("_id", None)
    return rec


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class ObjectiveIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    owner_account_id: Optional[str] = None
    shared_with: List[str] = Field(default_factory=list)
    rag_status: Literal["red", "amber", "green"] = "green"
    score: int = Field(default=50, ge=0, le=100)
    trend: Literal["up", "flat", "down"] = "flat"
    source: Literal["auto", "manual", "hybrid"] = "manual"
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectIn(ObjectiveIn):
    objective_id: Optional[str] = None
    timeline_events: List[Dict[str, Any]] = Field(default_factory=list)


def _coll(kind: str):
    return db.objectives if kind == "objective" else db.projects


def _model(kind: str):
    return ObjectiveIn if kind == "objective" else ProjectIn


# -----------------------------------------------------------------------------
# Auto-suggest — surface candidate objectives/projects from existing data.
# (Declared BEFORE the generic /{kind} routes so FastAPI matches the
# specific paths first.)
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/monitor/auto-suggest-objectives")
async def auto_suggest_objectives(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Suggest objectives derived from active cycles and Solva sessions."""
    candidates: List[Dict[str, Any]] = []
    async for c in db.cycles.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "readiness_pct": 1},
    ).limit(20):
        readiness = c.get("readiness_pct") or 0
        rag = "green" if readiness >= 80 else "amber" if readiness >= 40 else "red"
        candidates.append({
            "kind": "objective",
            "source": "auto",
            "title": c.get("title") or "Untitled agenda",
            "source_refs": [{"kind": "cycle", "id": c["id"]}],
            "rag_status": rag,
            "score": readiness,
        })
    async for s in db.solva_sessions.find(
        {"context_id": context_id, "status": {"$in": ["complete", "draft"]}},
        {"_id": 0, "id": 1, "topic": 1, "status": 1},
    ).limit(10):
        if not s.get("topic"):
            continue
        candidates.append({
            "kind": "objective",
            "source": "auto",
            "title": f"Investigate: {s.get('topic')}",
            "source_refs": [{"kind": "solva_session", "id": s["id"]}],
            "rag_status": "amber",
            "score": 50,
        })
    return {"items": candidates}


@router.get("/contexts/{context_id}/monitor/auto-suggest-projects")
async def auto_suggest_projects(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Suggest projects from active cycles."""
    candidates: List[Dict[str, Any]] = []
    async for c in db.cycles.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "readiness_pct": 1},
    ).limit(20):
        readiness = c.get("readiness_pct") or 0
        rag = "green" if readiness >= 80 else "amber" if readiness >= 40 else "red"
        candidates.append({
            "kind": "project",
            "source": "auto",
            "title": c.get("title") or "Untitled agenda",
            "source_refs": [{"kind": "cycle", "id": c["id"]}],
            "rag_status": rag,
            "score": readiness,
        })
    return {"items": candidates}


# -----------------------------------------------------------------------------
# CRUD — shared shape across objectives and projects.
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/monitor/{kind}")
async def list_items(
    context_id: str,
    kind: str,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    page: int = 1,
    page_size: int = 5,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    page = max(1, int(page or 1))
    page_size = max(1, min(50, int(page_size or 5)))
    q: Dict[str, Any] = {"context_id": context_id, "deleted_at": {"$exists": False}}
    if status:
        if status not in _RAG and status != "all":
            raise HTTPException(status_code=400, detail="Unknown status.")
        if status != "all":
            q["rag_status"] = status
    if owner:
        q["owner_account_id"] = owner
    total = await _coll(kind).count_documents(q)
    cursor = (
        _coll(kind)
        .find(q, {"_id": 0})
        .sort("score", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_sanitize(r) async for r in cursor]
    return {
        "kind": kind,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@router.post("/contexts/{context_id}/monitor/{kind}")
async def create_item(
    context_id: str,
    kind: str,
    body: dict,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    parsed = _model(kind)(**body)
    now = _now()
    rec: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        **parsed.dict(),
    }
    await _coll(kind).insert_one(rec.copy())
    return _sanitize(rec)


@router.get("/contexts/{context_id}/monitor/{kind}/{rid}")
async def get_item(
    context_id: str,
    kind: str,
    rid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    rec = await _coll(kind).find_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Not found.")
    return _sanitize(rec)


@router.patch("/contexts/{context_id}/monitor/{kind}/{rid}")
async def update_item(
    context_id: str,
    kind: str,
    rid: str,
    body: dict,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    body.pop("id", None); body.pop("context_id", None); body.pop("_id", None)
    body["updated_at"] = _iso(_now())
    res = await _coll(kind).update_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"$set": body},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found.")
    rec = await _coll(kind).find_one({"id": rid, "context_id": context_id}, {"_id": 0})
    return _sanitize(rec)


@router.delete("/contexts/{context_id}/monitor/{kind}/{rid}")
async def delete_item(
    context_id: str,
    kind: str,
    rid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    res = await _coll(kind).update_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"$set": {"deleted_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found.")
    return {"ok": True}


# -----------------------------------------------------------------------------
# (Auto-suggest endpoints moved above the CRUD block so FastAPI matches
# their specific paths before the generic /{kind} pattern.)
# -----------------------------------------------------------------------------
