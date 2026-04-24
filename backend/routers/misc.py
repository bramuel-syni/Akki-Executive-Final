"""Miscellaneous endpoints: LLM probe, telemetry events, health, root."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm
from core import (
    db, now as _now, iso as _iso,
    get_current_account, require_context_membership, APP_NAME,
)

router = APIRouter(prefix="/api")


class LLMProbeIn(BaseModel):
    module: str
    query: str


class TelemetryEventIn(BaseModel):
    event_name: str
    event_version: str = "1.0"
    context_id: Optional[str] = None
    session_id: Optional[str] = None
    surface: Optional[str] = None  # home / workspace / highlights / ask / learn / settings
    properties: Dict[str, Any] = Field(default_factory=dict)


@router.post("/contexts/{context_id}/llm/probe")
async def llm_probe(
    context_id: str,
    body: LLMProbeIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    out = await llm_call_llm(
        module=body.module,
        user_query=body.query,
        context_object={"context_id": context_id, "context_type": ctx["context"].get("type")},
        session_context={"probe": True, "account_id": ctx["account"]["id"]},
        data_trust={"overall": "unrated"},
    )
    return out


@router.post("/events")
async def record_event(
    body: TelemetryEventIn, current: Dict[str, Any] = Depends(get_current_account)
):
    if body.context_id:
        mem = await db.memberships.find_one(
            {"context_id": body.context_id, "account_id": current["id"], "status": "active"}
        )
        if not mem:
            raise HTTPException(status_code=403, detail="Not a member of this context")
    created_at = _iso(_now())
    doc = {
        "id": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "event_name": body.event_name,
        "event_version": body.event_version,
        "context_id": body.context_id,
        "account_id": current["id"],
        "session_id": body.session_id,
        "surface": body.surface,
        "properties": body.properties,
        "occurred_at": created_at,
        "received_at": created_at,
    }
    await db.telemetry_events.insert_one(doc)
    return {"ok": True}


@router.get("/")
async def root():
    return {"app": APP_NAME, "status": "ok", "module": "M5", "brd_version": "3.0"}


@router.get("/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok", "db": "up"}
    except Exception as e:  # pragma: no cover
        return {"status": "degraded", "db": str(e)}
