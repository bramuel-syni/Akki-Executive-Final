"""Phase J — Generative Sandbox MVP routes (unauthenticated, public).

Endpoints under `/api/sandbox-gen`:
  POST   /sessions                   — accept form answers, enqueue gen
  GET    /sessions/{sid}             — poll for status + artefacts
  DELETE /sessions/{sid}             — manual purge

The existing `/api/sandbox/*` namespace belongs to the legacy guided
tour (SandboxV2) — we deliberately mount under `/api/sandbox-gen` to
avoid namespace collision and to keep observability clean.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sandbox-gen", tags=["sandbox_generation"])


class FormPayload(BaseModel):
    name: str = Field(..., max_length=80)
    role: str = Field(...)
    role_other: str = Field("", max_length=120)
    org_type: str = Field(...)
    org_type_other: str = Field("", max_length=120)
    org_size: str = Field(...)
    situation: str = Field("", max_length=1500)
    emphasis: list[str] = Field(default_factory=list)
    email: str = Field("", max_length=200)


@router.post("/sessions")
async def post_session(payload: FormPayload, request: Request, background: BackgroundTasks) -> Dict[str, Any]:
    """Create a sandbox session and enqueue the generation job.
    Returns immediately with `{session_id, status}`."""
    from services.sandbox_generation import (
        validate_form_answers,
        create_session,
        fulfil_session,
    )

    form = payload.model_dump()
    ok, reason = validate_form_answers(form)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    # IP hash (best-effort) — first 16 hex of sha256.
    fwd = request.headers.get("x-forwarded-for", "")
    ip = (fwd.split(",")[0] if fwd else (request.client.host if request.client else "")).strip()
    ip_hash = hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()[:16]

    sid = await create_session(form, ip_hash=ip_hash)
    background.add_task(fulfil_session, sid)
    return {"session_id": sid, "status": "generating"}


@router.get("/sessions/{sid}")
async def get_session(sid: str) -> Dict[str, Any]:
    from core import db
    doc = await db.sandbox_sessions.find_one({"id": sid})
    if not doc:
        raise HTTPException(status_code=404, detail="session not found or expired")
    return {
        "id": doc["id"],
        "status": doc.get("status", "generating"),
        "form_answers": doc.get("form_answers"),
        "artefacts": doc.get("artefacts"),
        "meta": doc.get("meta"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


@router.delete("/sessions/{sid}")
async def delete_session(sid: str) -> Dict[str, Any]:
    from core import db
    res = await db.sandbox_sessions.delete_one({"id": sid})
    return {"ok": True, "deleted": res.deleted_count}
