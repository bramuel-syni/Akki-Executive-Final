"""Admin QA hooks — test-harness endpoints for e1_tester.

All endpoints in this module are SUPER-ADMIN gated and use the same
MFA-grace shape as `admin_inbox.py`. They exist purely so e1_tester
(and human QA) can prepare deterministic state for the onboarding
and Continue-card flows without contaminating the user-visible
product surface. No new product feature is shipped here.

──────────────────────────────────────────────────────────────────
Endpoints
──────────────────────────────────────────────────────────────────

  POST /api/admin/qa/first-session/reset
       Body: { "account_email": "?" }  (optional — defaults to caller)
       Effect: writes `accounts.first_session = {status:"in_progress",
               current_step:"door", door_taken:null, intake: <preserved>}`
       Use case: e1_tester traverses 4 doors with a single admin; reset
       between clicks to land on the door step again.

  POST /api/admin/qa/seed/recent-doc
       Body: { "account_email": "?", "context_name": "?" }  (both optional)
       Effect: idempotently provisions
         • a context owned by the admin
         • a "QA seed document.pdf" inside it
         • a `user_recent_views` row scoped to that admin + doc
         such that the Home / Portfolio "Continue" card surfaces with
         a deep_link of `/app/work-studio?doc_id={doc}&context_id={cid}`.
       Use case: e1_tester verifies TC4 (Home Continue → Work Studio
       cross-context propagation) without the user manually opening
       a real doc first.

──────────────────────────────────────────────────────────────────
Both endpoints reuse the established super-admin guard
(`_require_super_admin_with_mfa` pattern from admin_inbox.py:75).
MFA-grace honours `MFA_ADMIN_GRACE_EMAILS` so `admin@akki.ai` works
without MFA in preview.
"""
from __future__ import annotations

import os as _os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account

router = APIRouter(prefix="/api/admin/qa", tags=["admin-qa"])


# ───────────────────────────────────────────────────────────────────


async def _require_super_admin_with_mfa(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Mirrors admin_inbox.py:75 — same gate semantics so anyone
    auditing the surface only has one shape to remember."""
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    grace = {
        e.strip().lower() for e in
        (_os.environ.get("MFA_ADMIN_GRACE_EMAILS", "admin@akki.ai")).split(",")
        if e.strip()
    }
    if (current.get("email") or "").lower() not in grace and not current.get("mfa_enabled"):
        raise HTTPException(status_code=428, detail={
            "code": "mfa_enrolment_required",
            "message": "Enrol MFA before using the QA hooks.",
            "enrol_url": "/app/security",
        })
    return current


async def _resolve_target_account(
    admin: Dict[str, Any], account_email: Optional[str]
) -> Dict[str, Any]:
    """Default to the caller. Allow overriding via account_email so
    e1_tester can reset a separate QA dummy account if needed."""
    if not account_email:
        return admin
    target = await db.accounts.find_one(
        {"email_lc": account_email.lower()}, {"_id": 0}
    )
    if not target:
        target = await db.accounts.find_one(
            {"email": account_email.lower()}, {"_id": 0}
        )
    if not target:
        raise HTTPException(status_code=404, detail={
            "code": "account_not_found",
            "message": f"No account matches email_lc={account_email.lower()!r}",
        })
    return target


# ───────────────────────────────────────────────────────────────────
# Block 1 — First-session reset
# ───────────────────────────────────────────────────────────────────


class FirstSessionResetIn(BaseModel):
    account_email: Optional[EmailStr] = Field(
        default=None,
        description=("Account to reset. Optional — defaults to the "
                     "caller's own account."),
    )


@router.post("/first-session/reset")
async def reset_first_session(
    body: FirstSessionResetIn,
    admin: Dict[str, Any] = Depends(_require_super_admin_with_mfa),
) -> Dict[str, Any]:
    """Reset the first-session state to `current_step="door"`.

    Idempotent: running it twice produces the same result. Preserves
    any prior `intake` payload so the user doesn't need to retype the
    intake answers — the goal is to land them back on the door step
    with their intake context intact.
    """
    target = await _resolve_target_account(admin, body.account_email)
    prior = target.get("first_session") or {}
    new_state = {
        "status": "in_progress",
        "current_step": "door",
        "door_taken": None,
        "intake": prior.get("intake") or {},
    }
    await db.accounts.update_one(
        {"id": target["id"]},
        {"$set": {"first_session": new_state}},
    )
    return {
        "ok": True,
        "account_id": target["id"],
        "email": target.get("email"),
        "first_session": new_state,
    }


# ───────────────────────────────────────────────────────────────────
# Block 2 — Recent-doc seed
# ───────────────────────────────────────────────────────────────────


class RecentDocSeedIn(BaseModel):
    account_email: Optional[EmailStr] = Field(
        default=None,
        description=("Account to receive the seeded doc. Optional — "
                     "defaults to the caller's own account."),
    )
    context_name: Optional[str] = Field(
        default=None, min_length=1, max_length=120,
        description=("Optional. Defaults to 'QA Continue-Card Context'."
                     " Reuses an existing context with this name if "
                     "the admin already owns one — idempotent."),
    )


@router.post("/seed/recent-doc")
async def seed_recent_doc(
    body: RecentDocSeedIn,
    admin: Dict[str, Any] = Depends(_require_super_admin_with_mfa),
) -> Dict[str, Any]:
    """Idempotently seed (context + doc + user_recent_views) so the
    Home / Portfolio "Continue" card has a row to render.

    Resulting deep_link shape — exact contract that ContextPortfolio
    + WorkStudio honour together:
        /app/work-studio?doc_id={doc_id}&context_id={context_id}
    """
    target = await _resolve_target_account(admin, body.account_email)
    ctx_name = body.context_name or "QA Continue-Card Context"
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Find-or-create the context (idempotent on name+owner).
    ctx = await db.contexts.find_one(
        {"owner_account_id": target["id"], "name": ctx_name},
        {"_id": 0},
    )
    created_context = False
    if not ctx:
        cid = "ctx-qa-recent-" + uuid.uuid4().hex[:10]
        ctx = {
            "id": cid,
            "name": ctx_name,
            "owner_account_id": target["id"],
            "type": "company",
            "created_at": now_iso,
        }
        await db.contexts.insert_one(dict(ctx))
        await db.memberships.insert_one({
            "id": "mem-qa-" + uuid.uuid4().hex[:10],
            "account_id": target["id"],
            "context_id": cid,
            "role": "founder", "sub_role": "owner",
            "status": "active", "created_at": now_iso,
        })
        created_context = True
    cid = ctx["id"]

    # 2. Find-or-create the seed document (idempotent on name+context).
    doc = await db.documents.find_one(
        {"context_id": cid, "name": "QA seed document.pdf"},
        {"_id": 0},
    )
    created_document = False
    if not doc:
        doc_id = "doc-qa-recent-" + uuid.uuid4().hex[:10]
        doc = {
            "id": doc_id,
            "context_id": cid,
            "name": "QA seed document.pdf",
            "doc_type": "Document",
            "original_filename": "QA seed document.pdf",
            "extracted_text": "QA seed document body (e1_tester fixture).",
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await db.documents.insert_one(dict(doc))
        created_document = True
    did = doc["id"]

    # 3. Upsert a fresh user_recent_views row so the Continue card
    #    surfaces this doc at the top of "where you left off".
    deep_link = f"/app/work-studio?doc_id={did}&context_id={cid}"
    await db.user_recent_views.update_one(
        {"account_id": target["id"], "artefact_id": did},
        {"$set": {
            "account_id":      target["id"],
            "context_id":      cid,
            "artefact_id":     did,
            "artefact_kind":   "document",
            "label":           doc["name"],
            "surface_path":    deep_link,
            "deep_link":       deep_link,
            "last_visited_at": now_iso,
            "updated_at":      now_iso,
        }},
        upsert=True,
    )

    return {
        "ok": True,
        "account_id": target["id"],
        "context_id": cid,
        "doc_id": did,
        "deep_link": deep_link,
        "created_context": created_context,
        "created_document": created_document,
    }
