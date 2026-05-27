"""Phase R.1 (2026-05-27) — Admin cohort invite endpoints.

Superadmin-gated invite issuance + listing for the founding cohort.
R.1 only logs the welcome email; R.2 (2026-05-27) wired the actual
SendGrid send with a [FOUNDER:] placeholder guard.

Endpoints:
  POST /api/admin/cohort/invites           — issue a magic-link invite
       ?send=0   to skip the welcome-email send (default: send)
       ?preview=1 to render+return the welcome email body without
                  creating the invite (folds in the R.2.1 backlog feature)
  GET  /api/admin/cohort/invites           — list invites (filterable by cohort_tag, status)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account
from services.cohort.magic_link import (
    gen_magic_token, COHORT_INVITE_TTL_DAYS, COHORT_TRIAL_DEFAULT_DAYS,
)
from services.cohort.welcome_email import (
    build_welcome_html, assert_no_founder_placeholder, send_welcome_email_async,
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
    background_tasks: BackgroundTasks,
    send: int = Query(default=1, ge=0, le=1),
    preview: int = Query(default=0, ge=0, le=1),
    actor: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    now = _now()
    expires_at = now + timedelta(days=COHORT_INVITE_TTL_DAYS)
    trial_end_at = now + timedelta(days=body.trial_length_days)

    token = gen_magic_token()
    base = _public_base(request)
    magic_link_url = f"{base}/api/auth/magic/{token}"

    invite_id = uuid.uuid4().hex

    # Phase R.2 (2026-05-27) — Welcome email payload (shape locked at R.1).
    welcome_payload = {
        "event":           "cohort_welcome_pending",
        "to":              body.email.lower(),
        "template_id":     "cohort_welcome_v1",
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

    # Build the rendered email body. The same body is used for both
    # `?preview=1` (return without creating) and the actual send path.
    rendered = build_welcome_html(welcome_payload["dynamic_template_data"])

    # Phase R.2 (2026-05-27) — MANDATORY server-side guard. Refuses to
    # SEND if any `[FOUNDER:` placeholder is still in the body. The
    # guard fires ONLY on actual send (send=1). `?preview=1` and
    # `?send=0` deliberately bypass the guard so founders can iterate
    # on copy (preview) or run consume-flow tests without spamming
    # founders (send=0).
    if send == 1 and preview != 1:
        assert_no_founder_placeholder(rendered)

    if preview == 1:
        # Folds in the R.2.1 backlog feature — show the rendered body
        # WITHOUT creating an invite row or sending. The admin can
        # iterate on copy this way before going live.
        return {
            "preview": True,
            "subject": rendered["subject"],
            "html": rendered["html"],
            "text": rendered["text"],
            "dynamic_template_data": welcome_payload["dynamic_template_data"],
            "magic_link_url": magic_link_url,
        }

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

    if send == 1:
        # Fire-and-forget SendGrid via BackgroundTasks. The send
        # function NEVER raises — failures emit `cohort_welcome_failed`
        # log lines that the admin can review + re-send manually.
        background_tasks.add_task(
            send_welcome_email_async,
            rendered=rendered,
            to_email=body.email.lower(),
            invite_id=invite_id,
            cohort_tag=body.cohort_tag,
        )
        log.info("cohort_welcome_dispatched: %s", {
            **welcome_payload, "event": "cohort_welcome_dispatched",
        })
        # Phase R.3 (2026-05-27) — emit cohort.welcome.dispatched feature event.
        try:
            from services.cohort.feature_events import (
                emit_feature_event, COHORT_WELCOME_DISPATCHED,
            )
            await emit_feature_event(
                event_type=COHORT_WELCOME_DISPATCHED,
                account_id=actor["id"],
                cohort_tag=body.cohort_tag,
                payload={"invite_id": invite_id, "to": body.email.lower()},
            )
        except Exception:
            pass
    else:
        # Admin chose to skip the email. Log as `cohort_welcome_skipped`
        # so audit can distinguish from a real send.
        log.info("cohort_welcome_skipped: %s", {
            **welcome_payload, "event": "cohort_welcome_skipped",
        })

    return {
        "invite_id":      invite_id,
        "magic_link_url": magic_link_url,
        "expires_at":     row["expires_at"],
        "trial_end_at":   trial_end_at.isoformat(),
        "welcome_email_dispatched": bool(send == 1),
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



# ═════════════════════════════════════════════════════════════════════
# GET /api/admin/cohort/funnel — Phase R.3 funnel aggregator
# ═════════════════════════════════════════════════════════════════════
@router.get("/funnel")
async def cohort_funnel(
    cohort_tag: Optional[str] = Query(default=None),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Aggregate `db.feature_events` into a flat funnel.

    Returns counts per event_type, scoped to a cohort_tag (if given)
    or over all events otherwise. The aggregation runs the full
    collection (TTL-trimmed to 90 days); R.5 cohort console will
    layer time-window filters on top.

    Output shape (locked):
      {
        "cohort_tag":   <str or null>,
        "events_by_type": { "<event_type>": <count>, ... },
        "unique_accounts_by_type": { "<event_type>": <count>, ... },
        "total_events": <int>,
        "as_of":        <iso8601>,
      }
    """
    from services.cohort.feature_events import KNOWN_EVENT_TYPES

    match_stage: Dict[str, Any] = {}
    if cohort_tag:
        match_stage["cohort_tag"] = cohort_tag

    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},
        {"$group": {
            "_id": "$event_type",
            "count": {"$sum": 1},
            "accounts": {"$addToSet": "$account_id"},
        }},
    ]
    counts: Dict[str, int] = {ev: 0 for ev in KNOWN_EVENT_TYPES}
    unique: Dict[str, int] = {ev: 0 for ev in KNOWN_EVENT_TYPES}
    total = 0
    async for row in db.feature_events.aggregate(pipeline):
        ev = row["_id"]
        counts[ev] = int(row.get("count") or 0)
        unique[ev] = len([a for a in row.get("accounts", []) if a])
        total += counts[ev]

    return {
        "cohort_tag": cohort_tag,
        "events_by_type": counts,
        "unique_accounts_by_type": unique,
        "total_events": total,
        "as_of": _now().isoformat(),
    }
