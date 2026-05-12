"""
routers/compilations.py — Patch 2B.2 Compilation Wizard backend.

Endpoints (all under /api/contexts/{cid}/work-studio/compilations):
  • POST   — create a compilation from the wizard Step 4 confirm.
  • GET    — list compilations for the active context.
  • GET /{id} — detail.

Collection: `compilations`
  {
    id, context_id, title, artefact_type, template_key,
    source_ids[], contributor_ids[], cadence_kind, cadence_payload,
    formats[], status, created_at, created_by, last_compiled_at?,
    agent_cycle_log: [],
  }

Indexes: (context_id, status, created_at DESC), (context_id, artefact_type)
— installed on startup in server.py.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from core import db, iso as _iso, now as _now, require_context_membership


router = APIRouter(prefix="/api")


# Constrain the wizard inputs to the locked product decisions.
_ARTEFACT_TYPES = ("board_pack", "minutes", "committee_pack", "deck", "report", "briefing")
_CADENCE_KINDS = ("one_off", "recurring", "scheduled")
_RECURRING_INTERVALS = ("weekly", "fortnightly", "monthly", "quarterly")
_FORMATS = ("docx", "pptx", "pdf")


class CadencePayload(BaseModel):
    """Free-form bag — the shape varies by `kind`:
    • one_off    — payload is empty.
    • recurring  — {"interval": "weekly|fortnightly|monthly|quarterly"}
    • scheduled  — {"scheduled_at": "<ISO date>"}
    """
    interval: Optional[str] = None
    scheduled_at: Optional[str] = None


class CompilationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    artefact_type: str
    template_key: str = Field(default="standard", min_length=1, max_length=80)
    source_ids: List[str] = Field(default_factory=list)
    contributor_ids: List[str] = Field(default_factory=list)
    cadence_kind: str
    cadence_payload: CadencePayload = Field(default_factory=CadencePayload)
    formats: List[str] = Field(default_factory=list)

    @validator("artefact_type")
    def _v_artefact(cls, v):
        if v not in _ARTEFACT_TYPES:
            raise ValueError(f"artefact_type must be one of {_ARTEFACT_TYPES}")
        return v

    @validator("cadence_kind")
    def _v_cadence(cls, v):
        if v not in _CADENCE_KINDS:
            raise ValueError(f"cadence_kind must be one of {_CADENCE_KINDS}")
        return v

    @validator("formats")
    def _v_formats(cls, v):
        # Patch 9+ correction — `formats` is OPTIONAL (default `[]`). When
        # present, every entry must be one of docx/pptx/pdf. An empty
        # list is valid — the wizard still produces a record; format
        # selection can land later via update.
        lower = [f.lower() for f in (v or [])]
        for f in lower:
            if f not in _FORMATS:
                raise ValueError(f"unknown format {f!r}; allowed: {_FORMATS}")
        return lower


def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo internals; rec must already exclude `_id`."""
    rec = dict(rec)
    rec.pop("_id", None)
    return rec


@router.post("/contexts/{context_id}/work-studio/compilations")
async def create_compilation(
    context_id: str,
    body: CompilationCreate,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    now = _now()
    rec: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "title": body.title.strip(),
        "artefact_type": body.artefact_type,
        "template_key": body.template_key,
        "source_ids": list(body.source_ids),
        "contributor_ids": list(body.contributor_ids),
        "cadence_kind": body.cadence_kind,
        "cadence_payload": body.cadence_payload.dict(exclude_none=True),
        "formats": body.formats,
        "status": "queued",
        "created_at": _iso(now),
        "created_by": ctx["account"]["id"],
        "agent_cycle_log": [
            {
                "ts": _iso(now),
                "actor_id": ctx["account"]["id"],
                "kind": "created",
                "note": "Wizard confirm — commissioned to Agent Cycle.",
            },
        ],
    }
    await db.compilations.insert_one(rec.copy())
    return _sanitize(rec)


@router.get("/contexts/{context_id}/work-studio/compilations")
async def list_compilations(
    context_id: str,
    status: Optional[str] = None,
    artefact_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id}
    if status:
        q["status"] = status
    if artefact_type:
        if artefact_type not in _ARTEFACT_TYPES:
            raise HTTPException(status_code=400, detail="Unknown artefact_type.")
        q["artefact_type"] = artefact_type
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    total = await db.compilations.count_documents(q)
    cursor = (
        db.compilations
        .find(q, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_sanitize(r) async for r in cursor]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/contexts/{context_id}/work-studio/compilations/{compilation_id}")
async def get_compilation(
    context_id: str,
    compilation_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rec = await db.compilations.find_one(
        {"id": compilation_id, "context_id": context_id},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Compilation not found.")
    return _sanitize(rec)
