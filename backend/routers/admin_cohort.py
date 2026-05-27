"""Phase R.1 (2026-05-27) — Admin cohort invite endpoints.

Superadmin-gated invite issuance + listing for the founding cohort.
R.1 only logs the welcome email; R.2 will replace the log line with a
SendGrid send. The log line is already shaped as a SendGrid-ready dict
so R.2 is a near-zero refactor.

Endpoints:
  POST /api/admin/cohort/invites      — issue a magic-link invite
  GET  /api/admin/cohort/invites      — list invites (filterable by cohort_tag, status)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account
from services.cohort.magic_link import (
    gen_magic_token, COHORT_INVITE_TTL_DAYS, COHORT_TRIAL_DEFAULT_DAYS,
)


log = logging.getLogger("akki.cohort.admin")
router = APIRouter(prefix="/api/admin/cohort", tags=["admin-cohort"])


# Phase R.1 — Mirror the existing superadmin gate pattern from
# `admin_audit_invariant.py` and `admin_auth_events.py`. Don't extract
# to a shared helper this phase — the codebase has 3+ copies already
# and the refactor would touch unrelated files (OUT_OF_SCOPE).
async def _require_superadmin(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    return account


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _public_base(request: Request) -> str:
    """Where the magic-link URL points. Priority:
      1. `PUBLIC_BASE_URL` env var (set this in prod to lock the host).
      2. `REACT_APP_BACKEND_URL` env var (backend .env, if shared).
      3. The scheme + host of the current request — works in any env
         (preview, prod, staging) without explicit config.
    """
    from_env = (
        os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
    )
    if from_env:
        return from_env.rstrip("/")
    return f"{request.url.scheme}://{request.url.netloc}"


def _compute_status(row: Dict[str, Any]) -> str:
    """Compute the user-facing status from the DB row. The DB never
    stores "expired" — that's a function of the current time vs the
    persisted `expires_at`. R.5 cohort console will use this same
    function on read."""
    if row.get("consumed_at"):
        return "consumed"
    try:
        exp = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _now():
            return "expired"
    except Exception:
        pass
    return "pending"


def _sanitize_invite(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip the raw token from list responses — the admin only needs
    to see the magic_link_url once (at creation). Subsequent reads
    show the status + audit fields."""
    return {
        "id":                     row["id"],
        "email":                  row["email"],
        "cohort_tag":             row["cohort_tag"],
        "trial_length_days":      row["trial_length_days"],
        "first_name":             row.get("first_name"),
        "logo_name":              row.get("logo_name"),
        "issued_at":              row["issued_at"],
        "expires_at":             row["expires_at"],
        "consumed_at":            row.get("consumed_at"),
        "consumed_by_account_id": row.get("consumed_by_account_id"),
        "issued_by_account_id":   row.get("issued_by_account_id"),
        "status":                 _compute_status(row),
    }


# ═════════════════════════════════════════════════════════════════════
# POST /api/admin/cohort/invites — issue an invite
# ═════════════════════════════════════════════════════════════════════
class IssueInviteIn(BaseModel):
    email: EmailStr
    cohort_tag: str = Field(min_length=1, max_length=100)
    trial_length_days: int = Field(default=COHORT_TRIAL_DEFAULT_DAYS, ge=1, le=365)
    first_name: Optional[str] = Field(default=None, max_length=120)
    logo_name: Optional[str] = Field(default=None, max_length=200)


@router.post("/invites", status_code=200)
async def issue_invite(
    body: IssueInviteIn,
    request: Request,
    actor: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    now = _now()
    expires_at = now + timedelta(days=COHORT_INVITE_TTL_DAYS)
    trial_end_at = now + timedelta(days=body.trial_length_days)

    token = gen_magic_token()
    base = _public_base(request)
    magic_link_url = f"{base}/api/auth/magic/{token}"

    invite_id = uuid.uuid4().hex
    row = {
        "id":                     invite_id,
        "email":                  body.email.lower(),
        "cohort_tag":             body.cohort_tag,
        "trial_length_days":      body.trial_length_days,
        "first_name":             body.first_name,
        "logo_name":              body.logo_name,
        "magic_link_token":       token,
        "magic_link_url":         magic_link_url,
        "issued_at":              now.isoformat(),
        "expires_at":             expires_at.isoformat(),
        "consumed_at":            None,
        "consumed_by_account_id": None,
        "status":                 "pending",  # static field — never updated; use _compute_status() on read
        "issued_by_account_id":   actor["id"],
    }
    await db.cohort_invites.insert_one(row)

    # Phase R.2 stub — welcome email log line shaped as a SendGrid-ready dict.
    # When R.2 lands, wrap this dict in a SendGrid send call; the field
    # names already match SendGrid's `personalizations[].substitutions`
    # template variable convention.
    welcome_payload = {
        "event":           "cohort_welcome_pending",
        "to":              body.email.lower(),
        "template_id":     "cohort_welcome_v1",  # R.2 will replace with real template id
        "dynamic_template_data": {
            "first_name":   body.first_name or "there",
            "logo_name":    body.logo_name or "your team",
            "cohort_tag":   body.cohort_tag,
            "magic_link":   magic_link_url,
            "trial_length_days": body.trial_length_days,
            "trial_end_at": trial_end_at.isoformat(),
            "expires_at":   expires_at.isoformat(),
        },
        "invite_id":       invite_id,
    }
    log.info("cohort_welcome_pending: %s", welcome_payload)

    return {
        "invite_id":      invite_id,
        "magic_link_url": magic_link_url,
        "expires_at":     row["expires_at"],
        "trial_end_at":   trial_end_at.isoformat(),
    }


# ═════════════════════════════════════════════════════════════════════
# GET /api/admin/cohort/invites — list invites
# ═════════════════════════════════════════════════════════════════════
@router.get("/invites")
async def list_invites(
    cohort_tag: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, regex="^(pending|consumed|expired)$"),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if cohort_tag:
        q["cohort_tag"] = cohort_tag
    rows: List[Dict[str, Any]] = []
    async for r in db.cohort_invites.find(q, {"_id": 0, "magic_link_token": 0}).sort("issued_at", -1).limit(limit):
        sanitised = _sanitize_invite(r)
        if status and sanitised["status"] != status:
            continue
        rows.append(sanitised)
    return {"items": rows, "total": len(rows)}
