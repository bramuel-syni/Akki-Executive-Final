"""Phase P4.B (2026-02) — Admin cohort approve / decline / hold actions.

Distinct from the older `admin_cohort.py` (R.1 invite issuance) — this
module operates on the `cohort_applications` collection (the funnel
side), where the older one operates on `cohort_invites` (the direct
admin-initiated channel).

Endpoints (all CSRF + MFA-gated):
  POST /api/admin/cohort/applications/{id}/approve
  POST /api/admin/cohort/applications/{id}/decline
  POST /api/admin/cohort/applications/{id}/hold
  GET  /api/admin/cohort/applications      — list, newest first
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.cohort_email import send_approval, send_decline
from routers.cohort_magic_link import _mint_token, _hash_token, TTL_DAYS


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/cohort/applications", tags=["admin-cohort-applications"])


VALID_STATUSES = ("submitted", "received", "held", "declined", "approved", "approved_redeemed")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _require_admin_with_mfa(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    import os as _os
    grace = {e.strip().lower() for e in (_os.environ.get("MFA_ADMIN_GRACE_EMAILS", "admin@akki.ai")).split(",") if e.strip()}
    if (current.get("email") or "").lower() not in grace and not current.get("mfa_enabled"):
        raise HTTPException(status_code=428, detail={
            "code": "mfa_enrolment_required",
            "message": "Enrol MFA before approving / declining applications.",
            "enrol_url": "/app/security",
        })
    return current


async def _record_action(
    *, application_id: str, action: str,
    actor_admin_id: str, prev_status: str, new_status: str,
) -> None:
    await db.cohort_application_audit.insert_one({
        "id":             _uuid.uuid4().hex,
        "application_id": application_id,
        "action":         action,
        "actor_admin_id": actor_admin_id,
        "prev_status":    prev_status,
        "new_status":     new_status,
        "timestamp":      _now_iso(),
    })


async def _load_app_or_404(application_id: str) -> Dict[str, Any]:
    app_row = await db.cohort_applications.find_one({"id": application_id}, {"_id": 0})
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")
    return app_row


class _ActionIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/{application_id}/approve")
async def approve_application(
    application_id: str,
    body: _ActionIn,
    request: Request,
    admin: Dict[str, Any] = Depends(_require_admin_with_mfa),
):
    app_row = await _load_app_or_404(application_id)
    prev_status = app_row.get("status", "received")

    # Invalidate any prior unconsumed links.
    await db.cohort_magic_links.update_many(
        {"application_id": application_id, "consumed_at": None},
        {"$set": {"consumed_at": _now_iso(), "consumed_reason": "superseded"}},
    )

    raw = _mint_token()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(days=TTL_DAYS)
    await db.cohort_magic_links.insert_one({
        "id":             _uuid.uuid4().hex,
        "application_id": application_id,
        "token_hash":     _hash_token(raw),
        "issued_at":      issued_at.isoformat(),
        "expires_at":     expires_at.isoformat(),
        "consumed_at":    None,
        "consumed_by_user_id": None,
        "issued_by":      admin.get("id"),
    })

    await db.cohort_applications.update_one(
        {"id": application_id},
        {"$set": {
            "status":      "approved",
            "approved_at": issued_at.isoformat(),
            "approved_by": admin.get("id"),
            "admin_note":  body.note,
        }},
    )
    await _record_action(
        application_id=application_id, action="approve",
        actor_admin_id=admin.get("id"), prev_status=prev_status, new_status="approved",
    )

    # Build the magic-link URL using public base from env or request origin.
    import os as _os
    public_base = (_os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
    if not public_base:
        public_base = (request.headers.get("origin") or "").rstrip("/")
    magic_url = f"{public_base}/welcome/{raw}" if public_base else f"/welcome/{raw}"

    email_result = send_approval(
        to_email=app_row["email"],
        first_name=app_row.get("name"),
        magic_link=magic_url,
    )
    return {
        "ok":             True,
        "application_id": application_id,
        "status":         "approved",
        "magic_url":      magic_url,
        "expires_at":     expires_at.isoformat(),
        "email":          email_result,
    }


@router.post("/{application_id}/decline")
async def decline_application(
    application_id: str,
    body: _ActionIn,
    request: Request,
    admin: Dict[str, Any] = Depends(_require_admin_with_mfa),
):
    app_row = await _load_app_or_404(application_id)
    prev_status = app_row.get("status", "received")

    await db.cohort_magic_links.update_many(
        {"application_id": application_id, "consumed_at": None},
        {"$set": {"consumed_at": _now_iso(), "consumed_reason": "declined"}},
    )

    await db.cohort_applications.update_one(
        {"id": application_id},
        {"$set": {
            "status":      "declined",
            "declined_at": _now_iso(),
            "declined_by": admin.get("id"),
            "admin_note":  body.note,
        }},
    )
    await _record_action(
        application_id=application_id, action="decline",
        actor_admin_id=admin.get("id"), prev_status=prev_status, new_status="declined",
    )

    # Phase P5.7.6 (2026-02) — door-back URL in the decline email.
    # The `?from={application_id}` query param lets the waitlist
    # endpoint correlate door-back signups to their originating
    # application for cohort-level analytics; the param is optional
    # and discarded if the recipient strips it.
    import os as _os
    public_base = (_os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
    if not public_base:
        public_base = (request.headers.get("origin") or "").rstrip("/")
    waitlist_url = (
        f"{public_base}/waitlist?from={application_id}"
        if public_base else f"/waitlist?from={application_id}"
    )
    email_result = send_decline(
        to_email=app_row["email"],
        first_name=app_row.get("name"),
        waitlist_url=waitlist_url,
    )
    return {
        "ok":             True,
        "application_id": application_id,
        "status":         "declined",
        "email":          email_result,
    }


@router.post("/{application_id}/hold")
async def hold_application(
    application_id: str,
    body: _ActionIn,
    admin: Dict[str, Any] = Depends(_require_admin_with_mfa),
):
    app_row = await _load_app_or_404(application_id)
    prev_status = app_row.get("status", "received")
    await db.cohort_applications.update_one(
        {"id": application_id},
        {"$set": {
            "status":     "held",
            "held_at":    _now_iso(),
            "held_by":    admin.get("id"),
            "admin_note": body.note,
        }},
    )
    await _record_action(
        application_id=application_id, action="hold",
        actor_admin_id=admin.get("id"), prev_status=prev_status, new_status="held",
    )
    return {
        "ok":             True,
        "application_id": application_id,
        "status":         "held",
    }


@router.get("")
async def list_applications(
    status: Optional[str] = None,
    admin: Dict[str, Any] = Depends(_require_admin_with_mfa),
):
    """List cohort applications with optional status filter, newest first."""
    query: Dict[str, Any] = {}
    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query["status"] = status
    cursor = db.cohort_applications.find(query, {"_id": 0}).sort("created_at", -1).limit(500)
    items = await cursor.to_list(length=500)
    return {"items": items, "total": len(items)}
