"""Contexts, memberships, invitations, context objects, presets, accounts/me.

Everything "account-level + context-level" CRUD that doesn't belong in a
domain router. Moved out of server.py without behavioural changes.
"""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    get_current_account, require_context_membership,
    sanitize_account, sanitize_context,
)

logger = logging.getLogger("akki.contexts")

router = APIRouter(prefix="/api")


ContextType = Literal[
    "ned_personal", "ned_sponsored", "executive_personal", "executive_enterprise"
]
MembershipRole = Literal["ned", "executive", "reportee"]
AccountRole = Literal["ned", "executive", "dual", "undeclared"]


# -----------------------------------------------------------------------------
# Pydantic schemas
# -----------------------------------------------------------------------------
class ContextCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: ContextType = "executive_personal"
    industry: Optional[str] = None
    jurisdiction: Optional[str] = None
    sector: Optional[str] = None


class ContextRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ContextObjectIn(BaseModel):
    industry: Optional[str] = None
    sector: Optional[str] = None
    jurisdiction: Optional[str] = None
    role: Optional[MembershipRole] = None
    answers: Dict[str, Any] = Field(default_factory=dict)
    step: int = 0
    completed: bool = False


class AccountUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    declared_role: Optional[AccountRole] = None
    preferences: Optional[Dict[str, Any]] = None


class SetDefaultContextIn(BaseModel):
    context_id: str


class InvitationIn(BaseModel):
    email: EmailStr
    role: MembershipRole = "executive"
    sub_role: Optional[str] = None


# -----------------------------------------------------------------------------
# Account-level (me, default-context, consent, leave)
# -----------------------------------------------------------------------------
@router.patch("/accounts/me")
async def update_account(
    body: AccountUpdateIn, current: Dict[str, Any] = Depends(get_current_account)
):
    updates: Dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.declared_role is not None:
        updates["declared_role"] = body.declared_role
    if body.preferences is not None:
        merged = {**(current.get("preferences") or {}), **body.preferences}
        updates["preferences"] = merged
    if not updates:
        return {"account": sanitize_account(current)}
    await db.accounts.update_one({"id": current["id"]}, {"$set": updates})
    await write_audit(None, current["id"], "account.updated", "account", current["id"], updates)
    refreshed = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return {"account": sanitize_account(refreshed)}


@router.post("/accounts/me/default-context")
async def set_default_context(
    body: SetDefaultContextIn, current: Dict[str, Any] = Depends(get_current_account)
):
    mem = await db.memberships.find_one(
        {"context_id": body.context_id, "account_id": current["id"], "status": "active"}
    )
    if not mem:
        raise HTTPException(status_code=404, detail="You are not a member of that context")
    await db.accounts.update_one(
        {"id": current["id"]}, {"$set": {"default_context_id": body.context_id}}
    )
    refreshed = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return {"account": sanitize_account(refreshed)}


@router.post("/contexts/{context_id}/leave")
async def leave_context(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    ctx_id = ctx["context"]["id"]
    account_id = ctx["account"]["id"]
    if ctx["context"]["owner_account_id"] == account_id:
        raise HTTPException(status_code=400, detail="Context owner cannot leave — archive the context instead.")
    res = await db.memberships.update_one(
        {"context_id": ctx_id, "account_id": account_id, "status": "active"},
        {"$set": {"status": "left", "left_at": _iso(_now())}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Membership not found")
    if ctx["account"].get("default_context_id") == ctx_id:
        await db.accounts.update_one({"id": account_id}, {"$set": {"default_context_id": None}})
    await write_audit(ctx_id, account_id, "member.left", "account", account_id, {})
    return {"ok": True}


@router.get("/accounts/me/consent-decisions")
async def list_consent_decisions(current: Dict[str, Any] = Depends(get_current_account)):
    decisions = await db.consent_decisions.find(
        {"account_id": current["id"]}, {"_id": 0}
    ).sort("decided_at", -1).to_list(200)
    return decisions


# -----------------------------------------------------------------------------
# Industry presets (hardcoded reference data for M2 onboarding)
# -----------------------------------------------------------------------------
INDUSTRY_PRESETS = [
    {"id": "banking", "label": "Banking & Capital Markets", "sectors": ["Retail", "Corporate", "Investment", "Private"]},
    {"id": "insurance", "label": "Insurance", "sectors": ["Life", "General", "Health", "Reinsurance"]},
    {"id": "retail", "label": "Retail & Consumer", "sectors": ["Grocery", "Apparel", "Electronics", "Multi-category"]},
    {"id": "fintech", "label": "Fintech", "sectors": ["Payments", "Lending", "Wealth", "Infra"]},
    {"id": "telco", "label": "Telecommunications", "sectors": ["Mobile", "Broadband", "Enterprise"]},
    {"id": "energy", "label": "Energy & Utilities", "sectors": ["Oil & Gas", "Power", "Renewables", "Water"]},
    {"id": "healthcare", "label": "Healthcare & Pharma", "sectors": ["Provider", "Payor", "Pharma", "Devices"]},
    {"id": "logistics", "label": "Logistics & Transport", "sectors": ["Freight", "Passenger", "Last-mile"]},
    {"id": "mining", "label": "Mining & Resources", "sectors": ["Metals", "Commodities", "Services"]},
    {"id": "agriculture", "label": "Agriculture & Agribusiness", "sectors": ["Primary", "Processing", "Distribution"]},
    {"id": "manufacturing", "label": "Manufacturing", "sectors": ["FMCG", "Industrial", "Automotive"]},
    {"id": "public_sector", "label": "Public Sector / NGO", "sectors": ["Government", "Non-profit", "Multilateral"]},
]

JURISDICTION_PRESETS = [
    "Nigeria", "Kenya", "South Africa", "Ghana", "Egypt", "Morocco", "Ethiopia",
    "Tanzania", "Uganda", "Rwanda", "Pan-African", "Global",
]


@router.get("/presets/industries")
async def list_industries(_: Dict[str, Any] = Depends(get_current_account)):
    return INDUSTRY_PRESETS


@router.get("/presets/jurisdictions")
async def list_jurisdictions(_: Dict[str, Any] = Depends(get_current_account)):
    return JURISDICTION_PRESETS


# -----------------------------------------------------------------------------
# Context Object (versioned)
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/context-object")
async def get_context_object(ctx: Dict[str, Any] = Depends(require_context_membership())):
    latest = await db.context_objects.find_one(
        {"context_id": ctx["context"]["id"]}, {"_id": 0}, sort=[("version", -1)],
    )
    return latest


@router.post("/contexts/{context_id}/context-object")
async def upsert_context_object(
    body: ContextObjectIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    context_id = ctx["context"]["id"]
    account_id = ctx["account"]["id"]

    latest = await db.context_objects.find_one(
        {"context_id": context_id}, {"_id": 0}, sort=[("version", -1)]
    )
    new_version = (latest["version"] + 1) if latest else 1
    created_at = _iso(_now())
    doc = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "version": new_version,
        "industry": body.industry,
        "sector": body.sector,
        "jurisdiction": body.jurisdiction,
        "role": body.role,
        "answers": body.answers,
        "step": body.step,
        "completed": body.completed,
        "created_by": account_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    await db.context_objects.insert_one(doc)
    doc.pop("_id", None)

    ctx_updates: Dict[str, Any] = {
        "progress_state": {
            "onboarding_step": body.step,
            "onboarding_completed": body.completed,
            "context_object_version": new_version,
        },
    }
    if body.industry:
        ctx_updates["industry"] = body.industry
    if body.jurisdiction:
        ctx_updates["jurisdiction"] = body.jurisdiction
    if body.sector:
        ctx_updates["sector"] = body.sector
    await db.contexts.update_one({"id": context_id}, {"$set": ctx_updates})

    await write_audit(
        context_id, account_id,
        "context_object.saved" if body.completed else "context_object.progress",
        "context_object", doc["id"],
        {"version": new_version, "completed": body.completed, "step": body.step},
    )
    return doc


# -----------------------------------------------------------------------------
# Contexts CRUD
# -----------------------------------------------------------------------------
@router.post("/contexts")
async def create_context(body: ContextCreateIn, current: Dict[str, Any] = Depends(get_current_account)):
    ctx_id = str(uuid.uuid4())
    created_at = _iso(_now())
    ctx_doc = {
        "id": ctx_id,
        "name": body.name.strip(),
        "type": body.type,
        "industry": body.industry,
        "jurisdiction": body.jurisdiction,
        "sector": body.sector,
        "sponsoring_org_id": None,
        "owner_account_id": current["id"],
        "status": "active",
        "progress_state": {"onboarding_step": 0},
        "created_at": created_at,
    }
    await db.contexts.insert_one(ctx_doc)
    role: MembershipRole = "ned" if body.type.startswith("ned") else "executive"
    await db.memberships.insert_one(
        {
            "id": str(uuid.uuid4()),
            "account_id": current["id"],
            "context_id": ctx_id,
            "role": role,
            "sub_role": "admin",
            "provisioning": "personal",
            "data_ownership": "account",
            "status": "active",
            "created_at": created_at,
        }
    )
    await write_audit(ctx_id, current["id"], "context.created", "context", ctx_id, {"name": body.name, "type": body.type})
    ctx_doc.pop("_id", None)
    return sanitize_context(ctx_doc)


@router.get("/contexts/{context_id}")
async def get_context(ctx: Dict[str, Any] = Depends(require_context_membership())):
    out = sanitize_context(ctx["context"])
    out["my_role"] = ctx["membership"].get("role")
    out["my_sub_role"] = ctx["membership"].get("sub_role")
    out["provisioning"] = ctx["membership"].get("provisioning")
    out["data_ownership"] = ctx["membership"].get("data_ownership")
    return out


@router.patch("/contexts/{context_id}")
async def rename_context(
    context_id: str,
    body: ContextRenameIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    await db.contexts.update_one({"id": context_id}, {"$set": {"name": body.name.strip()}})
    await write_audit(context_id, ctx["account"]["id"], "context.renamed", "context", context_id, {"to": body.name})
    c = await db.contexts.find_one({"id": context_id}, {"_id": 0})
    return sanitize_context(c)


@router.delete("/contexts/{context_id}")
async def archive_context(
    context_id: str, ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True))
):
    await db.contexts.update_one({"id": context_id}, {"$set": {"status": "archived", "archived_at": _iso(_now())}})
    await write_audit(context_id, ctx["account"]["id"], "context.archived", "context", context_id, {})
    return {"ok": True, "status": "archived"}


# -----------------------------------------------------------------------------
# Members
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/members")
async def list_members(ctx: Dict[str, Any] = Depends(require_context_membership())):
    context_id = ctx["context"]["id"]
    memberships = await db.memberships.find(
        {"context_id": context_id, "status": "active"}, {"_id": 0}
    ).to_list(500)
    account_ids = [m["account_id"] for m in memberships]
    accounts = await db.accounts.find({"id": {"$in": account_ids}}, {"_id": 0}).to_list(500)
    by_id = {a["id"]: a for a in accounts}
    out = []
    for m in memberships:
        a = by_id.get(m["account_id"])
        if not a:
            continue
        out.append(
            {
                "account_id": a["id"],
                "email": a["email"],
                "name": a.get("name", ""),
                "role": m["role"],
                "sub_role": m.get("sub_role"),
                "provisioning": m.get("provisioning", "personal"),
                "joined_at": m.get("created_at"),
            }
        )
    return out


@router.delete("/contexts/{context_id}/members/{account_id}")
async def remove_member(
    context_id: str,
    account_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    if account_id == ctx["context"]["owner_account_id"]:
        raise HTTPException(status_code=400, detail="Cannot remove the context owner")
    res = await db.memberships.update_one(
        {"context_id": context_id, "account_id": account_id, "status": "active"},
        {"$set": {"status": "removed", "removed_at": _iso(_now())}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    await write_audit(context_id, ctx["account"]["id"], "member.removed", "account", account_id, {})
    return {"ok": True}


# -----------------------------------------------------------------------------
# Invitations (context-scoped)
# -----------------------------------------------------------------------------
@router.post("/contexts/{context_id}/invitations")
async def create_invitation(
    context_id: str,
    body: InvitationIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    email = body.email.lower().strip()
    existing_acc = await db.accounts.find_one({"email": email}, {"_id": 0})
    if existing_acc:
        existing_mem = await db.memberships.find_one(
            {"context_id": context_id, "account_id": existing_acc["id"], "status": "active"}
        )
        if existing_mem:
            raise HTTPException(status_code=409, detail="Account is already a member")
    existing_inv = await db.invitations.find_one(
        {"context_id": context_id, "email": email, "status": "pending"}
    )
    if existing_inv:
        raise HTTPException(status_code=409, detail="Invitation already pending for this email")

    token = secrets.token_urlsafe(32)
    inv = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "email": email,
        "role": body.role,
        "sub_role": body.sub_role,
        "token": token,
        "status": "pending",
        "invited_by": ctx["account"]["id"],
        "created_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(days=7)),
    }
    await db.invitations.insert_one(inv)

    frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
    accept_url = f"{frontend_url}/invite/{token}" if frontend_url else f"/invite/{token}"

    # Phase G3 (2026-05-11) — un-stub invitation email. Real Resend
    # send via the existing email_service wrapper. Wrapper returns
    # `mode ∈ {sent, noop, test_mode_restricted, error}` and NEVER
    # raises — so a Resend outage cannot fail the API call.
    try:
        from email_service import send_email
        inviter_name = ctx["account"].get("name") or ctx["account"].get("email") or "Akki"
        company_name = ctx["context"].get("name") or "an Akki workspace"
        subject = f"{inviter_name} invited you to {company_name} on Akki"
        text_body = (
            f"Hello,\n\n"
            f"{inviter_name} has invited you to join {company_name} on Akki "
            f"as a {body.role}.\n\n"
            f"Accept the invitation here:\n  {accept_url}\n\n"
            f"This invitation expires in 7 days.\n\n"
            f"If you weren't expecting this, you can ignore this email.\n\n"
            f"— Akki"
        )
        html_body = f"""
<div style="font-family: Georgia, serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #2A1B1D; background: #FAF7F2;">
  <h1 style="font-size: 24px; font-weight: bold; margin: 0 0 16px;">You've been invited to {company_name}</h1>
  <p style="font-size: 16px; line-height: 1.6; color: #2A1B1D; margin: 0 0 16px;">
    <strong>{inviter_name}</strong> has invited you to join <strong>{company_name}</strong> on Akki as a <strong>{body.role}</strong>.
  </p>
  <p style="margin: 24px 0;">
    <a href="{accept_url}" style="display: inline-block; background: #C25A38; color: #FAF7F2; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 2px;">
      Accept invitation
    </a>
  </p>
  <p style="font-size: 13px; color: #6B6B6B; margin: 24px 0 0;">
    This invitation expires in 7 days. If you weren't expecting it, you can ignore this email.
  </p>
  <p style="font-size: 13px; color: #6B6B6B; margin: 16px 0 0; border-top: 1px solid #D5C9B6; padding-top: 16px;">
    — Akki
  </p>
</div>
""".strip()
        email_result = await send_email(
            to=[email], subject=subject, html=html_body, text=text_body,
            tags=[{"name": "type", "value": "invitation"},
                  {"name": "context", "value": context_id}],
        )
        logger.info(
            "[invite-email] to=%s ctx=%s mode=%s id=%s",
            email, ctx["context"]["name"], email_result.get("mode"),
            email_result.get("id"),
        )
    except Exception as exc:  # noqa: BLE001 — never break invite flow
        logger.error("[invite-email] send failed err=%s — invite row was still created", exc)
        email_result = {"ok": False, "mode": "error", "id": None}

    await write_audit(
        context_id, ctx["account"]["id"], "member.invited", "invitation", inv["id"],
        {"email": email, "role": body.role},
    )
    return {
        "id": inv["id"],
        "email": email,
        "role": body.role,
        "status": "pending",
        "accept_url": accept_url,
        "expires_at": inv["expires_at"],
        "created_at": inv["created_at"],
    }


@router.get("/contexts/{context_id}/invitations")
async def list_invitations(ctx: Dict[str, Any] = Depends(require_context_membership())):
    invs = await db.invitations.find(
        {"context_id": ctx["context"]["id"], "status": "pending"}, {"_id": 0, "token": 0}
    ).to_list(200)
    return invs


@router.delete("/contexts/{context_id}/invitations/{invitation_id}")
async def revoke_invitation(
    context_id: str,
    invitation_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    res = await db.invitations.update_one(
        {"id": invitation_id, "context_id": context_id, "status": "pending"},
        {"$set": {"status": "revoked", "revoked_at": _iso(_now())}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Invitation not found")
    await write_audit(context_id, ctx["account"]["id"], "invitation.revoked", "invitation", invitation_id, {})
    return {"ok": True}


@router.get("/invitations/by-token/{token}")
async def preview_invitation(token: str):
    inv = await db.invitations.find_one({"token": token, "status": "pending"}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found or no longer valid")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < _now():
        raise HTTPException(status_code=410, detail="Invitation expired")
    ctx = await db.contexts.find_one({"id": inv["context_id"]}, {"_id": 0})
    return {
        "email": inv["email"],
        "role": inv["role"],
        "context_name": ctx["name"] if ctx else "Context",
        "context_type": ctx.get("type") if ctx else None,
    }


@router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str, current: Dict[str, Any] = Depends(get_current_account)
):
    inv = await db.invitations.find_one({"token": token, "status": "pending"}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not valid")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < _now():
        raise HTTPException(status_code=410, detail="Invitation expired")
    if current["email"].lower() != inv["email"].lower():
        raise HTTPException(
            status_code=403,
            detail=f"This invitation was sent to {inv['email']}. Sign in with that email to accept.",
        )
    existing = await db.memberships.find_one(
        {"context_id": inv["context_id"], "account_id": current["id"], "status": "active"}
    )
    if not existing:
        await db.memberships.insert_one(
            {
                "id": str(uuid.uuid4()),
                "account_id": current["id"],
                "context_id": inv["context_id"],
                "role": inv["role"],
                "sub_role": inv.get("sub_role"),
                "provisioning": "personal",
                "data_ownership": "account",
                "status": "active",
                "created_at": _iso(_now()),
            }
        )
    await db.invitations.update_one(
        {"id": inv["id"]}, {"$set": {"status": "accepted", "accepted_at": _iso(_now())}}
    )
    await write_audit(
        inv["context_id"], current["id"], "member.joined", "account", current["id"],
        {"role": inv["role"]},
    )
    ctx = await db.contexts.find_one({"id": inv["context_id"]}, {"_id": 0})
    return {"ok": True, "context": sanitize_context(ctx)}
