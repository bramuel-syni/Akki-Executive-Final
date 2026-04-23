"""Sub-committees on a context — list, add, rename, delete."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, require_context_membership, write_audit

router = APIRouter(prefix="/api")


class CommitteeIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    your_role: Optional[str] = Field(default=None, max_length=40)  # chair | member | observer


def _slug(name: str) -> str:
    base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    return base or f"committee-{uuid.uuid4().hex[:6]}"


@router.get("/contexts/{context_id}/committees")
async def list_committees(ctx: Dict[str, Any] = Depends(require_context_membership())):
    c = ctx["context"]
    return c.get("committees") or []


@router.post("/contexts/{context_id}/committees")
async def add_committee(
    body: CommitteeIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    context_id = ctx["context"]["id"]
    existing: List[Dict[str, Any]] = list(ctx["context"].get("committees") or [])
    new_id = _slug(body.name)
    # Ensure unique id
    ids = {cm.get("id") for cm in existing}
    while new_id in ids:
        new_id = f"{_slug(body.name)}-{uuid.uuid4().hex[:4]}"
    committee = {"id": new_id, "name": body.name, "your_role": body.your_role or "member"}
    existing.append(committee)
    await db.contexts.update_one({"id": context_id}, {"$set": {"committees": existing}})
    await write_audit(
        context_id, ctx["account"]["id"], "committee.created", "committee", new_id,
        {"name": body.name},
    )
    return committee


@router.patch("/contexts/{context_id}/committees/{committee_id}")
async def update_committee(
    committee_id: str,
    body: CommitteeIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    context_id = ctx["context"]["id"]
    existing: List[Dict[str, Any]] = list(ctx["context"].get("committees") or [])
    target = next((cm for cm in existing if cm.get("id") == committee_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Committee not found")
    target["name"] = body.name
    if body.your_role is not None:
        target["your_role"] = body.your_role
    await db.contexts.update_one({"id": context_id}, {"$set": {"committees": existing}})
    await write_audit(
        context_id, ctx["account"]["id"], "committee.updated", "committee", committee_id, {},
    )
    return target


@router.delete("/contexts/{context_id}/committees/{committee_id}")
async def delete_committee(
    committee_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    context_id = ctx["context"]["id"]
    existing: List[Dict[str, Any]] = list(ctx["context"].get("committees") or [])
    remaining = [cm for cm in existing if cm.get("id") != committee_id]
    if len(remaining) == len(existing):
        raise HTTPException(status_code=404, detail="Committee not found")
    await db.contexts.update_one({"id": context_id}, {"$set": {"committees": remaining}})
    # Unset committee_id on any artefact that referenced it so nothing goes dangling.
    await db.signals.update_many(
        {"context_id": context_id, "committee_id": committee_id},
        {"$unset": {"committee_id": ""}},
    )
    await db.briefings.update_many(
        {"context_id": context_id, "committee_id": committee_id},
        {"$unset": {"committee_id": ""}},
    )
    await db.documents.update_many(
        {"context_id": context_id, "committee_id": committee_id},
        {"$unset": {"committee_id": ""}},
    )
    await write_audit(
        context_id, ctx["account"]["id"], "committee.deleted", "committee", committee_id, {},
    )
    return {"ok": True}
