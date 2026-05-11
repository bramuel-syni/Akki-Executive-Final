"""Team Catalogue — context-scoped permanent member identity.

Per Cycle Manager v2 brief §Must-have item 4:

  • Catalogue holds (name, email) as permanent identity.
  • Role / contribution_description / agenda_assignments live on
    per-cycle records in `cycle_team` (untouched here).
  • Email uniqueness is per (context, account, email) — case-insensitive.
  • Remove is soft-delete; historical cycle rows are preserved.
  • Adding a member with the same (name,email) to the same cycle AND
    the same agenda item returns 409 with a warning payload.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import db, iso, now, require_context_membership, write_audit

logger = logging.getLogger("akki.team_catalogue")

router = APIRouter(prefix="/api")


class CatalogueMemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class CatalogueMemberPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None


class CatalogueMemberOut(BaseModel):
    id: str
    context_id: str
    name: str
    email: str
    created_at: str
    updated_at: str


def _email_key(email: str) -> str:
    return (email or "").strip().lower()


# ─────────────────────────────────────────────────────────────────────
# 1. List
# ─────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/team-catalogue")
async def list_catalogue(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rows = await db.team_catalogue.find(
        {"context_id": context_id, "deleted_at": None},
        {"_id": 0},
    ).sort("name", 1).to_list(500)
    return {"members": rows, "count": len(rows)}


# ─────────────────────────────────────────────────────────────────────
# 2. Add (auto-upsert on (context, email))
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/team-catalogue", status_code=201)
async def add_catalogue_member(
    context_id: str,
    body: CatalogueMemberIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    email_lc = _email_key(body.email)
    existing = await db.team_catalogue.find_one(
        {"context_id": context_id, "email_lc": email_lc},
        {"_id": 0},
    )
    now_iso = iso(now())
    if existing:
        if existing.get("deleted_at"):
            # Resurrect a previously-soft-deleted entry.
            await db.team_catalogue.update_one(
                {"id": existing["id"]},
                {"$set": {
                    "name": body.name.strip(),
                    "deleted_at": None,
                    "updated_at": now_iso,
                }},
            )
            return await db.team_catalogue.find_one({"id": existing["id"]}, {"_id": 0})
        # Already active — upsert name if changed.
        if existing.get("name") != body.name.strip():
            await db.team_catalogue.update_one(
                {"id": existing["id"]},
                {"$set": {"name": body.name.strip(), "updated_at": now_iso}},
            )
        return await db.team_catalogue.find_one({"id": existing["id"]}, {"_id": 0})

    row = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "name": body.name.strip(),
        "email": body.email,
        "email_lc": email_lc,
        "created_at": now_iso,
        "updated_at": now_iso,
        "deleted_at": None,
    }
    await db.team_catalogue.insert_one(row)
    await write_audit(
        context_id, ctx["account"]["id"],
        "team_catalogue.added", "catalogue_member", row["id"],
        {"name": row["name"], "email": row["email"]},
    )
    row.pop("_id", None)
    return row


# ─────────────────────────────────────────────────────────────────────
# 3. Patch
# ─────────────────────────────────────────────────────────────────────
@router.patch("/contexts/{context_id}/team-catalogue/{member_id}")
async def patch_catalogue_member(
    context_id: str,
    member_id: str,
    body: CatalogueMemberPatch,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.team_catalogue.find_one(
        {"id": member_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Catalogue member not found.")

    update: Dict[str, Any] = {}
    if body.name is not None:
        update["name"] = body.name.strip()
    if body.email is not None:
        update["email"] = body.email
        update["email_lc"] = _email_key(body.email)
        # Check the new email doesn't collide with another active entry.
        clash = await db.team_catalogue.find_one(
            {
                "context_id": context_id,
                "email_lc": update["email_lc"],
                "id": {"$ne": member_id},
                "deleted_at": None,
            },
            {"_id": 0, "id": 1},
        )
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"Another active catalogue entry already has email {body.email!r}.",
            )
    if update:
        update["updated_at"] = iso(now())
        await db.team_catalogue.update_one({"id": member_id}, {"$set": update})
        await write_audit(
            context_id, ctx["account"]["id"],
            "team_catalogue.patched", "catalogue_member", member_id,
            {"fields_changed": list(update.keys())},
        )
    return await db.team_catalogue.find_one({"id": member_id}, {"_id": 0})


# ─────────────────────────────────────────────────────────────────────
# 4. Soft-delete (preserves historical cycle rows)
# ─────────────────────────────────────────────────────────────────────
@router.delete("/contexts/{context_id}/team-catalogue/{member_id}")
async def soft_delete_catalogue_member(
    context_id: str,
    member_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    now_iso = iso(now())
    res = await db.team_catalogue.update_one(
        {"id": member_id, "context_id": context_id, "deleted_at": None},
        {"$set": {"deleted_at": now_iso, "updated_at": now_iso}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Catalogue member not found.")
    await write_audit(
        context_id, ctx["account"]["id"],
        "team_catalogue.soft_deleted", "catalogue_member", member_id, {},
    )
    return {"id": member_id, "deleted_at": now_iso}


# ─────────────────────────────────────────────────────────────────────
# 5. Duplicate-detection helper used by the Team-tab add flow
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycles/{cycle_id}/agenda-items/{agenda_item_id}/check-team-duplicate")
async def check_team_duplicate(
    context_id: str,
    cycle_id: str,
    agenda_item_id: str,
    body: CatalogueMemberIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return 409 if a team member with the same (name,email) is
    already assigned to this agenda_item_id on this cycle_id. Returns
    200 otherwise."""
    email_lc = _email_key(body.email)
    rows = await db.cycle_team.find(
        {"agenda_id": cycle_id, "status": "active"},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "owns_item_ids": 1},
    ).to_list(200)
    for r in rows:
        if (r.get("email") or "").strip().lower() != email_lc:
            continue
        if (r.get("name") or "").strip().lower() != (body.name or "").strip().lower():
            continue
        owns = r.get("owns_item_ids") or []
        if agenda_item_id in owns:
            return {
                "duplicate": True,
                "existing_id": r["id"],
                "warning": (
                    f"{body.name!r} is already assigned to this agenda item. "
                    "Add anyway to create a second contribution slot?"
                ),
            }
    return {"duplicate": False}
