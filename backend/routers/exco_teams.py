"""ExCo teams (HOME sprint, 2026-05-12).

ExCo is a *grouping function* within a context, not a role. Owners and
admins of a context can create one or more ExCo teams, each holding a
subset of the context's existing members. Surfaces using teams:

  - Home Executive renders an `ExcoTeamsCard` listing the teams the
    current user belongs to, with management actions for admins.
  - Cycle Manager (future) — assign agenda items to a specific team.
  - Work Studio (future) — share a brief with a team.

Audit policy: every mutation writes one row to `db.audit_log`. Reads do
NOT write audit rows. Cross-context queries are impossible by route
shape (`/api/contexts/{cid}/exco-teams`) and enforced by
`require_context_membership`.

Privacy: hydration only exposes member display-name + role; raw email
is never returned. The owner of an ExCo team is the account that
created it; that account is preserved even if the creator leaves the
team (so audit trail stays intact).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db,
    now as _now,
    iso as _iso,
    write_audit,
    require_context_membership,
)

logger = logging.getLogger("akki.exco_teams")
router = APIRouter(prefix="/api")


# -----------------------------------------------------------------------------
# Pydantic schemas
# -----------------------------------------------------------------------------
ExcoStatus = Literal["active", "archived"]


class ExcoCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=600)
    member_account_ids: List[str] = Field(default_factory=list, max_length=64)


class ExcoUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=600)
    status: Optional[ExcoStatus] = None


class ExcoAddMemberIn(BaseModel):
    account_id: str


class ExcoMember(BaseModel):
    account_id: str
    name: str
    role: str
    sub_role: Optional[str] = None


class ExcoTeamOut(BaseModel):
    id: str
    context_id: str
    name: str
    description: Optional[str] = None
    member_account_ids: List[str]
    members: Optional[List[ExcoMember]] = None
    created_by: str
    created_at: str
    updated_at: str
    status: ExcoStatus
    my_role: Optional[Literal["creator", "member", "outside"]] = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _is_admin_or_owner(ctx: Dict[str, Any], membership: Dict[str, Any], account_id: str) -> bool:
    return ctx.get("owner_account_id") == account_id or membership.get("sub_role") == "admin"


async def _validate_members_in_context(context_id: str, account_ids: List[str]) -> None:
    if not account_ids:
        return
    deduped = list({a for a in account_ids if isinstance(a, str)})
    if len(deduped) != len(account_ids):
        raise HTTPException(status_code=400, detail="Duplicate member account ids")
    cursor = db.memberships.find(
        {
            "context_id": context_id,
            "account_id": {"$in": deduped},
            "status": "active",
        },
        {"_id": 0, "account_id": 1},
    )
    found_ids = {m["account_id"] for m in await cursor.to_list(length=len(deduped))}
    missing = [a for a in deduped if a not in found_ids]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Members not active in this context: {','.join(missing[:5])}",
        )


async def _hydrate_team(team: Dict[str, Any], current_account_id: str) -> Dict[str, Any]:
    """Build the response payload: enrich with member display + my_role.
    NEVER returns raw email."""
    member_ids = team.get("member_account_ids") or []
    members: List[Dict[str, Any]] = []
    if member_ids:
        # Look up display name + context membership for each member.
        accounts = await db.accounts.find(
            {"id": {"$in": member_ids}},
            {"_id": 0, "id": 1, "display_name": 1, "name": 1, "email": 1},
        ).to_list(length=len(member_ids))
        acc_by_id = {a["id"]: a for a in accounts}
        memberships = await db.memberships.find(
            {"context_id": team["context_id"], "account_id": {"$in": member_ids}},
            {"_id": 0, "account_id": 1, "role": 1, "sub_role": 1},
        ).to_list(length=len(member_ids))
        mem_by_id = {m["account_id"]: m for m in memberships}
        for aid in member_ids:
            acc = acc_by_id.get(aid, {})
            mem = mem_by_id.get(aid, {})
            display = acc.get("display_name") or acc.get("name") or "Anonymous"
            members.append(
                {
                    "account_id": aid,
                    "name": display,
                    "role": mem.get("role") or "member",
                    "sub_role": mem.get("sub_role"),
                }
            )
    my_role: str = "outside"
    if team.get("created_by") == current_account_id:
        my_role = "creator"
    elif current_account_id in member_ids:
        my_role = "member"
    return {
        "id": team["id"],
        "context_id": team["context_id"],
        "name": team["name"],
        "description": team.get("description"),
        "member_account_ids": list(member_ids),
        "members": members,
        "created_by": team["created_by"],
        "created_at": team["created_at"],
        "updated_at": team["updated_at"],
        "status": team["status"],
        "my_role": my_role,
    }


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@router.post("/contexts/{context_id}/exco-teams", response_model=ExcoTeamOut, status_code=201)
async def create_exco_team(
    context_id: str,
    body: ExcoCreateIn,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    account_id = bundle["account"]["id"]
    if not _is_admin_or_owner(bundle["context"], bundle["membership"], account_id):
        raise HTTPException(status_code=403, detail="Only owners and admins can create ExCo teams")
    await _validate_members_in_context(context_id, body.member_account_ids)
    team = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "name": body.name.strip(),
        "description": (body.description or "").strip() or None,
        "member_account_ids": list({a for a in body.member_account_ids}),
        "created_by": account_id,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
        "status": "active",
    }
    await db.exco_teams.insert_one(team)
    await write_audit(
        context_id, account_id,
        "exco.created", "exco_team", team["id"],
        {"name": team["name"], "member_count": len(team["member_account_ids"])},
    )
    return await _hydrate_team(team, account_id)


@router.get("/contexts/{context_id}/exco-teams", response_model=List[ExcoTeamOut])
async def list_exco_teams(
    context_id: str,
    include_archived: bool = False,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    account_id = bundle["account"]["id"]
    query: Dict[str, Any] = {"context_id": context_id}
    if not include_archived:
        query["status"] = "active"
    teams = await db.exco_teams.find(query, {"_id": 0}).sort("created_at", -1).to_list(length=100)
    out: List[Dict[str, Any]] = []
    for t in teams:
        out.append(await _hydrate_team(t, account_id))
    return out


@router.get("/contexts/{context_id}/exco-teams/{team_id}", response_model=ExcoTeamOut)
async def get_exco_team(
    context_id: str,
    team_id: str,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    account_id = bundle["account"]["id"]
    team = await db.exco_teams.find_one({"id": team_id, "context_id": context_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="ExCo team not found")
    return await _hydrate_team(team, account_id)


@router.patch("/contexts/{context_id}/exco-teams/{team_id}", response_model=ExcoTeamOut)
async def update_exco_team(
    context_id: str,
    team_id: str,
    body: ExcoUpdateIn,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    account_id = bundle["account"]["id"]
    if not _is_admin_or_owner(bundle["context"], bundle["membership"], account_id):
        raise HTTPException(status_code=403, detail="Only owners and admins can modify ExCo teams")
    team = await db.exco_teams.find_one({"id": team_id, "context_id": context_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="ExCo team not found")
    updates: Dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.description is not None:
        updates["description"] = body.description.strip() or None
    if body.status is not None:
        updates["status"] = body.status
    if not updates:
        return await _hydrate_team(team, account_id)
    updates["updated_at"] = _iso(_now())
    await db.exco_teams.update_one({"id": team_id}, {"$set": updates})
    event = "exco.archived" if updates.get("status") == "archived" else "exco.updated"
    await write_audit(context_id, account_id, event, "exco_team", team_id, updates)
    refreshed = await db.exco_teams.find_one({"id": team_id}, {"_id": 0})
    return await _hydrate_team(refreshed, account_id)


@router.post("/contexts/{context_id}/exco-teams/{team_id}/members", response_model=ExcoTeamOut)
async def add_exco_member(
    context_id: str,
    team_id: str,
    body: ExcoAddMemberIn,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    account_id = bundle["account"]["id"]
    if not _is_admin_or_owner(bundle["context"], bundle["membership"], account_id):
        raise HTTPException(status_code=403, detail="Only owners and admins can add ExCo members")
    team = await db.exco_teams.find_one({"id": team_id, "context_id": context_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="ExCo team not found")
    if body.account_id in (team.get("member_account_ids") or []):
        return await _hydrate_team(team, account_id)
    await _validate_members_in_context(context_id, [body.account_id])
    await db.exco_teams.update_one(
        {"id": team_id},
        {
            "$addToSet": {"member_account_ids": body.account_id},
            "$set": {"updated_at": _iso(_now())},
        },
    )
    await write_audit(
        context_id, account_id, "exco.member_added", "exco_team", team_id,
        {"member": body.account_id},
    )
    refreshed = await db.exco_teams.find_one({"id": team_id}, {"_id": 0})
    return await _hydrate_team(refreshed, account_id)


@router.delete("/contexts/{context_id}/exco-teams/{team_id}/members/{member_id}", response_model=ExcoTeamOut)
async def remove_exco_member(
    context_id: str,
    team_id: str,
    member_id: str,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    account_id = bundle["account"]["id"]
    if not _is_admin_or_owner(bundle["context"], bundle["membership"], account_id):
        raise HTTPException(status_code=403, detail="Only owners and admins can remove ExCo members")
    team = await db.exco_teams.find_one({"id": team_id, "context_id": context_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="ExCo team not found")
    if member_id not in (team.get("member_account_ids") or []):
        return await _hydrate_team(team, account_id)
    await db.exco_teams.update_one(
        {"id": team_id},
        {
            "$pull": {"member_account_ids": member_id},
            "$set": {"updated_at": _iso(_now())},
        },
    )
    await write_audit(
        context_id, account_id, "exco.member_removed", "exco_team", team_id,
        {"member": member_id},
    )
    refreshed = await db.exco_teams.find_one({"id": team_id}, {"_id": 0})
    return await _hydrate_team(refreshed, account_id)


@router.delete("/contexts/{context_id}/exco-teams/{team_id}", response_model=ExcoTeamOut)
async def archive_exco_team(
    context_id: str,
    team_id: str,
    bundle: Dict[str, Any] = Depends(require_context_membership()),
):
    """Soft delete — sets status='archived'. Never hard-deletes."""
    account_id = bundle["account"]["id"]
    if not _is_admin_or_owner(bundle["context"], bundle["membership"], account_id):
        raise HTTPException(status_code=403, detail="Only owners and admins can archive ExCo teams")
    team = await db.exco_teams.find_one({"id": team_id, "context_id": context_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="ExCo team not found")
    if team.get("status") == "archived":
        return await _hydrate_team(team, account_id)
    await db.exco_teams.update_one(
        {"id": team_id},
        {"$set": {"status": "archived", "updated_at": _iso(_now())}},
    )
    await write_audit(
        context_id, account_id, "exco.archived", "exco_team", team_id, {},
    )
    refreshed = await db.exco_teams.find_one({"id": team_id}, {"_id": 0})
    return await _hydrate_team(refreshed, account_id)


# -----------------------------------------------------------------------------
# Index creation hook (idempotent — called by app startup).
# -----------------------------------------------------------------------------
async def ensure_exco_indexes() -> None:
    """Create the indexes the HOME sprint specifies:
    unique (id), compound (context_id, status), compound (context_id, members)."""
    coll = db.exco_teams
    await coll.create_index("id", unique=True)
    await coll.create_index([("context_id", 1), ("status", 1)])
    await coll.create_index([("context_id", 1), ("member_account_ids", 1)])
