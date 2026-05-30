"""Phase V (2026-05-27) — Admin user CRUD portal.

Superadmin-gated CRUD over the `accounts` collection. Closes the W7
stock-take #1 PARTIAL gap (the cohort console only lets the founder
INVITE users, not directly create / suspend / restore / export them).

Endpoints (all `/api/admin/users` prefixed, all `_require_superadmin`-gated):

  GET    /api/admin/users                    — paginated list + filters
  POST   /api/admin/users                    — create user manually
  GET    /api/admin/users/{id}               — single user detail
  POST   /api/admin/users/{id}/suspend       — flip status → suspended
  POST   /api/admin/users/{id}/restore       — flip status → active
  GET    /api/admin/users/{id}/timeline      — telemetry timeline
                                                (event_type + timestamp ONLY,
                                                 NO payload content)
  GET    /api/admin/users/export.csv         — CSV of the filtered list

Auth integration (W7 #4 data-safety promise):
  The `/timeline` endpoint returns ONLY the operational metadata of
  each `feature_events` row (`id`, `event_type`, `occurred_at`,
  `surface`, `account_id`) — NEVER the `payload` field which may
  contain user-typed content (chat messages, doc bodies, LLM
  responses). The CI guard `test_phase_v_timeline_strips_payload`
  enforces this invariant.

Suspend semantics:
  `account.status = 'suspended'` triggers a 401 in `get_current_account`
  (see `backend/core.py` Phase V block) so ALL auth-gated routes bounce
  immediately. Restore flips it back to 'active'.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


# ─────────────────────────────────────────────────────────────────────
# Auth gate (mirrors admin_cohort.py pattern)
# ─────────────────────────────────────────────────────────────────────

async def _require_superadmin(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    return account


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────

class UserCreateIn(BaseModel):
    email:        EmailStr
    first_name:   Optional[str] = Field(default=None, max_length=120)
    logo_name:    Optional[str] = Field(default=None, max_length=200)
    role:         Optional[str] = Field(default=None, max_length=80)  # declared_role
    cohort_tag:   Optional[str] = Field(default=None, max_length=120)
    initial_password: Optional[str] = Field(default=None, min_length=10, max_length=200)
    """If `initial_password` is left blank, the account is minted
    passwordless — the user can hit the magic-link or password-reset
    flow to set their own."""


class UserListItem(BaseModel):
    id:               str
    email:            str
    first_name:       Optional[str] = None
    logo_name:        Optional[str] = None
    declared_role:    Optional[str] = None
    cohort_tag:       Optional[str] = None
    trial_status:     Optional[str] = None
    status:           str = "active"
    is_superadmin:    bool = False
    last_login_at:    Optional[str] = None
    created_at:       Optional[str] = None
    auth_provider:    Optional[str] = None


# ─────────────────────────────────────────────────────────────────────
# Sanitiser
# ─────────────────────────────────────────────────────────────────────

# Fields stripped from outbound payloads — NEVER expose these to the
# admin UI even though it's a privileged surface (defence in depth).
SENSITIVE_FIELDS = {
    "_id",
    "password_hash",
    "magic_link_token",
    "reset_password_token",
    "sessions_revoked_after",  # Phase J internal
}

# Fields shown in the list view — explicit allowlist.
LIST_FIELDS = {
    "id", "email", "first_name", "logo_name", "declared_role",
    "cohort_tag", "trial_status", "status", "is_superadmin",
    "last_login_at", "created_at", "auth_provider",
}


def _sanitize_for_list(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: row.get(k) for k in LIST_FIELDS}
    # Default `status` to "active" if missing (legacy rows).
    if not out.get("status"):
        out["status"] = "active"
    return out


# ─────────────────────────────────────────────────────────────────────
# GET /api/admin/users — paginated list
# ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_users(
    request: Request,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
    sort: str = Query(default="created_at", regex="^(created_at|last_login_at|cohort_tag|email)$"),
    order: str = Query(default="desc", regex="^(asc|desc)$"),
    cohort_tag: Optional[str] = Query(default=None),
    trial_status: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, regex="^(active|suspended)$"),
    q: Optional[str] = Query(default=None, max_length=200),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    """Paginated list of all users with filters + sort.

    Filters compose with AND; `q` is a case-insensitive substring
    match over email + first_name + logo_name.
    """
    query: Dict[str, Any] = {}
    if cohort_tag:
        query["cohort_tag"] = cohort_tag
    if trial_status:
        query["trial_status"] = trial_status
    if role:
        query["declared_role"] = role
    if status:
        query["status"] = status
    if q:
        # Case-insensitive substring on 3 string fields. Escape regex
        # special chars so the user can't trigger a ReDoS.
        rx = re.escape(q)
        query["$or"] = [
            {"email":      {"$regex": rx, "$options": "i"}},
            {"first_name": {"$regex": rx, "$options": "i"}},
            {"logo_name":  {"$regex": rx, "$options": "i"}},
        ]

    sort_dir = -1 if order == "desc" else 1
    total = await db.accounts.count_documents(query)
    cursor = (
        db.accounts.find(query, {"_id": 0})
        .sort(sort, sort_dir)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    rows = [_sanitize_for_list(r) async for r in cursor]
    return {
        "items":     rows,
        "page":      page,
        "page_size": page_size,
        "total":     total,
        "has_more":  (page * page_size) < total,
    }


# ─────────────────────────────────────────────────────────────────────
# POST /api/admin/users — create user
# ─────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_user(
    body: UserCreateIn,
    request: Request,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    """Create a new account manually (NOT via magic-link).

    If `initial_password` is provided, the account is password-able
    from day 1; otherwise the account is passwordless and the user
    must hit the magic-link or password-reset flow to set their own.
    """
    # Uniqueness check (the existing `email_lc` unique index on
    # accounts handles the race; this gives a friendlier 409).
    existing = await db.accounts.find_one(
        {"email_lc": body.email.lower()}, {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    account_id = secrets.token_urlsafe(16)
    now = _now_iso()

    doc: Dict[str, Any] = {
        "id":             account_id,
        "email":          body.email,
        "email_lc":       body.email.lower(),
        "first_name":     body.first_name,
        "logo_name":      body.logo_name,
        "declared_role":  body.role,
        "cohort_tag":     body.cohort_tag,
        "status":         "active",
        "is_superadmin":  False,
        "created_at":     now,
        "first_session":  {"status": "intake"},  # exec must complete the wizard
    }

    if body.initial_password:
        doc["password_hash"] = bcrypt.hashpw(
            body.initial_password.encode("utf-8"), bcrypt.gensalt(),
        ).decode("utf-8")
        doc["auth_provider"] = "password"
    else:
        # Passwordless. The user can set a password later via the
        # forgot-password flow (Phase S) or magic-link consume (R.1).
        doc["auth_provider"] = "passwordless"

    await db.accounts.insert_one(doc)

    # Emit a feature_events row so the action is auditable in the
    # cohort console drill-down. Operational metadata ONLY (no PII
    # content beyond the email-as-identity which the user-facing
    # admin already sees in the list view).
    try:
        await db.feature_events.insert_one({
            "account_id": account_id,
            "event_type": "admin.user.created",
            "occurred_at": now,
            "payload":    {"created_by": _admin.get("id"), "auth_provider": doc["auth_provider"]},
        })
    except Exception:  # noqa: BLE001
        log.warning("Phase V — failed to emit admin.user.created event", exc_info=True)

    return _sanitize_for_list(doc)


# ─────────────────────────────────────────────────────────────────────
# GET /api/admin/users/{id}
# ─────────────────────────────────────────────────────────────────────

@router.get("/export.csv")
async def export_users_csv(
    request: Request,
    cohort_tag: Optional[str] = Query(default=None),
    trial_status: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, regex="^(active|suspended)$"),
    q: Optional[str] = Query(default=None, max_length=200),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    """CSV download of the filtered user list (no pagination — caps at 10k).

    Columns mirror the `LIST_FIELDS` allowlist so the CSV never
    surfaces sensitive fields (password_hash, magic_link_token, etc.).
    """
    query: Dict[str, Any] = {}
    if cohort_tag:
        query["cohort_tag"] = cohort_tag
    if trial_status:
        query["trial_status"] = trial_status
    if role:
        query["declared_role"] = role
    if status:
        query["status"] = status
    if q:
        rx = re.escape(q)
        query["$or"] = [
            {"email":      {"$regex": rx, "$options": "i"}},
            {"first_name": {"$regex": rx, "$options": "i"}},
            {"logo_name":  {"$regex": rx, "$options": "i"}},
        ]

    buf = io.StringIO()
    columns = [
        "id", "email", "first_name", "logo_name", "declared_role",
        "cohort_tag", "trial_status", "status", "is_superadmin",
        "last_login_at", "created_at", "auth_provider",
    ]
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()

    cursor = db.accounts.find(query, {"_id": 0}).limit(10_000)
    async for row in cursor:
        clean = _sanitize_for_list(row)
        # Coerce booleans/None to CSV-friendly strings.
        for col in columns:
            v = clean.get(col)
            if isinstance(v, bool):
                clean[col] = "true" if v else "false"
            elif v is None:
                clean[col] = ""
        writer.writerow(clean)

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="akki-users-{_now_iso()[:10]}.csv"',
        },
    )


@router.get("/{user_id}")
async def get_user(
    user_id: str, request: Request,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    row = await db.accounts.find_one({"id": user_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _sanitize_for_list(row)


# ─────────────────────────────────────────────────────────────────────
# POST /api/admin/users/{id}/suspend & /restore
# ─────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/suspend")
async def suspend_user(
    user_id: str, request: Request,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    """Flip account status → suspended. All auth-gated requests for
    this account will 401 with `ACCOUNT_SUSPENDED` from
    `get_current_account` (see `backend/core.py` Phase V block)."""
    # Phase V safety: the superadmin CAN'T accidentally suspend
    # themselves out (locks them out of the portal entirely).
    if user_id == _admin.get("id"):
        raise HTTPException(status_code=400, detail="Cannot suspend yourself")

    now = _now_iso()
    res = await db.accounts.update_one(
        {"id": user_id},
        {"$set": {"status": "suspended", "suspended_at": now}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        await db.feature_events.insert_one({
            "account_id": user_id,
            "event_type": "admin.user.suspended",
            "occurred_at": now,
            "payload":    {"suspended_by": _admin.get("id")},
        })
    except Exception:  # noqa: BLE001
        log.warning("Phase V — failed to emit admin.user.suspended event", exc_info=True)
    return {"ok": True, "user_id": user_id, "status": "suspended", "suspended_at": now}


@router.post("/{user_id}/restore")
async def restore_user(
    user_id: str, request: Request,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    now = _now_iso()
    res = await db.accounts.update_one(
        {"id": user_id},
        {"$set": {"status": "active"}, "$unset": {"suspended_at": ""}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        await db.feature_events.insert_one({
            "account_id": user_id,
            "event_type": "admin.user.restored",
            "occurred_at": now,
            "payload":    {"restored_by": _admin.get("id")},
        })
    except Exception:  # noqa: BLE001
        log.warning("Phase V — failed to emit admin.user.restored event", exc_info=True)
    return {"ok": True, "user_id": user_id, "status": "active"}


# ─────────────────────────────────────────────────────────────────────
# POST /api/admin/users/{id}/force-reset-password — Phase P2 B.6
# Mint a reset-password token on behalf of the target user and return
# the consumable reset URL. The superadmin can copy the URL into a
# direct message to the user OR rely on the SendGrid email path (when
# SENDGRID_FROM is configured) to deliver it.
# ─────────────────────────────────────────────────────────────────────

class ForceResetIn(BaseModel):
    send_email: bool = Field(default=True)


@router.post("/{user_id}/force-reset-password")
async def force_reset_password(
    user_id: str,
    body: ForceResetIn,
    request: Request,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    """Admin-triggered password reset. Generates a single-use reset
    token (mirrors Phase S `password_reset.py` semantics: 256-bit
    URL-safe, 1-hour TTL, single-use). Returns the reset URL so the
    superadmin can deliver it out-of-band if email is not configured.

    Audit row written. Body schema:
        { "send_email": true }   # default
    """
    from datetime import timedelta as _td
    import secrets as _secrets

    user = await db.accounts.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = _secrets.token_urlsafe(32)
    issued_at = datetime.now(timezone.utc)
    expires_at = (issued_at + _td(hours=1)).isoformat()

    await db.accounts.update_one(
        {"id": user_id},
        {"$set": {
            "reset_password_token":            token,
            "reset_password_token_expires_at": expires_at,
        }},
    )

    # Best-effort reset-URL composition using APP_PUBLIC_URL when set;
    # falls back to the request's Origin header for dev parity.
    import os as _os
    public_base = (_os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
    if not public_base:
        public_base = (request.headers.get("origin") or "").rstrip("/")
    reset_url = (
        f"{public_base}/reset-password/{token}" if public_base
        else f"/reset-password/{token}"
    )

    # If the user has SendGrid configured AND send_email is requested,
    # fire the existing password-reset email body via the shared helper.
    email_dispatched = False
    if body.send_email:
        try:
            from routers.password_reset import (
                _render_reset_email, _send_reset_email_async,
            )
            rendered = _render_reset_email(
                first_name=(user.get("first_name") or ""),
                email=user["email"],
                reset_url=reset_url,
            )
            # Sync function — call inline (the SendGrid SDK is sync and
            # the helper never raises).
            _send_reset_email_async(to_email=user["email"], rendered=rendered)
            email_dispatched = True
        except Exception:  # noqa: BLE001
            log.warning("B.6 — force-reset email send raised; URL still returned", exc_info=True)

    try:
        await db.feature_events.insert_one({
            "account_id":  user_id,
            "event_type":  "admin.user.password_force_reset",
            "occurred_at": issued_at.isoformat(),
            "payload":     {
                "triggered_by":     _admin.get("id"),
                "email_dispatched": email_dispatched,
            },
        })
    except Exception:  # noqa: BLE001
        log.warning("B.6 — failed to emit force-reset event", exc_info=True)

    return {
        "ok":               True,
        "user_id":          user_id,
        "email":            user["email"],
        "reset_url":        reset_url,
        "expires_at":       expires_at,
        "email_dispatched": email_dispatched,
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/admin/users/{id}/timeline — telemetry (NO payload content)
# ─────────────────────────────────────────────────────────────────────

# Fields exposed from each feature_events row. Notably ABSENT:
# `payload` (may contain user-typed content like chat messages, doc
# bodies, LLM responses). The W7 stock-take #4 promise is "the
# superadmin sees WHAT the user did, not what they typed."
TIMELINE_FIELDS = ("id", "event_type", "occurred_at", "surface", "account_id")


@router.get("/{user_id}/timeline")
async def user_timeline(
    user_id: str, request: Request,
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=100, ge=1, le=500),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
):
    """Per-user activity timeline drawn from `feature_events`.

    **Data-safety contract:** the response strips the `payload` field
    from every row. The superadmin sees the event TYPE + WHEN — never
    the user-typed content of that event. This invariant is locked
    by `test_phase_v_timeline_strips_payload` and surfaces in the W7
    stock-take #4 verdict.
    """
    # Confirm the user exists first; 404 if not.
    user = await db.accounts.find_one({"id": user_id}, {"_id": 0, "id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = {"account_id": user_id}
    total = await db.feature_events.count_documents(query)
    cursor = (
        db.feature_events.find(query, {"_id": 0})
        .sort("occurred_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items: List[Dict[str, Any]] = []
    async for row in cursor:
        # Explicit allowlist projection — defence in depth even though
        # we use a Mongo projection too (in case future code stops
        # excluding _id, payload still won't leak).
        items.append({k: row.get(k) for k in TIMELINE_FIELDS})
    return {
        "items":     items,
        "page":      page,
        "page_size": page_size,
        "total":     total,
        "has_more":  (page * page_size) < total,
    }
