"""Phase P4.C (2026-02) — Cohort magic-link issuance + redemption.

Single-use, 14-day expiry. Token shape: 32 random bytes, base64url
encoded. Only the bcrypt hash is stored in Mongo; the raw token is
returned exactly once (to the admin's approve response).

Endpoints:
  - POST /api/auth/magic-link/issue   (admin, CSRF, MFA-gated)
  - GET  /api/auth/magic-link/preview/{token}  (public)
  - POST /api/auth/magic-link/consume (public; CSRF)

Storage: `cohort_magic_links` collection. See README in /app/memory/sprints/P4_cohort_live_wire.md.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import (
    APP_NAME, db, get_current_account,
    create_access_token, create_refresh_token,
    set_auth_cookies, hash_password,
    sanitize_account, provision_default_context, sanitize_context,
)


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/magic-link", tags=["cohort-magic-link"])

TOKEN_BYTES = 32        # 256 bits of entropy
TTL_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mint_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _hash_token(token: str) -> str:
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_token(token: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(token.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


async def _find_link_record(token: str) -> Optional[Dict[str, Any]]:
    """Look up the magic-link row by hash match. We compare in
    Python because bcrypt salts are per-hash; can't index on hash.

    Trade-off: O(n) per probe — acceptable for cohort scale (low
    hundreds of links/year). When this scales out we'll add an
    HMAC-prefixed lookup column.
    """
    # Filter to unconsumed, unexpired rows first to keep the scan tiny.
    cursor = db.cohort_magic_links.find(
        {"consumed_at": None, "expires_at": {"$gte": _now().isoformat()}},
        {"_id": 0},
    )
    async for row in cursor:
        if _verify_token(token, row["token_hash"]):
            return row
    return None


async def _find_consumed_or_expired(token: str) -> Optional[Dict[str, Any]]:
    """Look up consumed / expired rows so we can return a precise
    410 Gone with the right narrative."""
    cursor = db.cohort_magic_links.find({}, {"_id": 0})
    async for row in cursor:
        if _verify_token(token, row["token_hash"]):
            return row
    return None


# ─── Schemas ─────────────────────────────────────────────────────────
class IssueIn(BaseModel):
    application_id: str = Field(min_length=1, max_length=120)


class ConsumeIn(BaseModel):
    token: str = Field(min_length=1, max_length=400)
    mode:  str = Field(pattern="^(password|google|microsoft)$")
    password:     Optional[str] = Field(default=None, min_length=10, max_length=200)
    oauth_code:   Optional[str] = Field(default=None, max_length=2000)


# ─── /issue (admin) ──────────────────────────────────────────────────
async def _require_admin(current: Dict[str, Any] = Depends(get_current_account)) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    # P3.3 MFA gate (grace bypass honoured for admin@akki.ai via env).
    import os as _os
    grace = {e.strip().lower() for e in (_os.environ.get("MFA_ADMIN_GRACE_EMAILS", "admin@akki.ai")).split(",") if e.strip()}
    if (current.get("email") or "").lower() not in grace and not current.get("mfa_enabled"):
        raise HTTPException(status_code=428, detail={
            "code": "mfa_enrolment_required",
            "message": "Enrol MFA before issuing magic links.",
            "enrol_url": "/app/security",
        })
    return current


@router.post("/issue")
async def issue_magic_link(
    body: IssueIn,
    admin: Dict[str, Any] = Depends(_require_admin),
):
    """Admin-only. Idempotent per-application — second call invalidates
    the prior token. Returns `{token, expires_at}` so the caller (the
    /approve action) can embed the raw token in the approval email."""
    app_row = await db.cohort_applications.find_one(
        {"id": body.application_id}, {"_id": 0},
    )
    if not app_row:
        raise HTTPException(status_code=404, detail="Application not found")

    # Invalidate any prior unconsumed links for this application.
    await db.cohort_magic_links.update_many(
        {"application_id": body.application_id, "consumed_at": None},
        {"$set": {"consumed_at": _now().isoformat(),
                  "consumed_reason": "superseded"}},
    )

    raw = _mint_token()
    now = _now()
    expires_at = now + timedelta(days=TTL_DAYS)
    row = {
        "id":            uuid.uuid4().hex,
        "application_id": body.application_id,
        "token_hash":    _hash_token(raw),
        "issued_at":     now.isoformat(),
        "expires_at":    expires_at.isoformat(),
        "consumed_at":   None,
        "consumed_by_user_id": None,
        "issued_by":     admin.get("id"),
    }
    await db.cohort_magic_links.insert_one(dict(row))

    try:
        await db.feature_events.insert_one({
            "account_id":  admin.get("id"),
            "event_type":  "cohort.magic_link.issued",
            "occurred_at": now.isoformat(),
            "payload":     {"application_id": body.application_id},
        })
    except Exception:  # noqa: BLE001
        log.warning("magic_link: failed to emit issued event", exc_info=True)

    return {
        "token":      raw,
        "expires_at": expires_at.isoformat(),
    }


# ─── /preview (public) ───────────────────────────────────────────────
@router.get("/preview/{token}")
async def preview_magic_link(token: str):
    row = await _find_link_record(token)
    if row:
        app_row = await db.cohort_applications.find_one(
            {"id": row["application_id"]}, {"_id": 0},
        )
        if not app_row:
            raise HTTPException(status_code=404, detail={"code": "application_missing"})
        first_name = (app_row.get("name") or "").split()[0] if app_row.get("name") else ""
        return {
            "first_name":   first_name,
            "organisation": app_row.get("organisation") or "",
            "expires_at":   row["expires_at"],
        }
    # Already consumed or expired? Distinguish for the UI narrative.
    fallback = await _find_consumed_or_expired(token)
    if fallback:
        # Determine consumed vs expired.
        if fallback.get("consumed_at"):
            raise HTTPException(status_code=410, detail={"code": "consumed"})
        expires_at = fallback.get("expires_at", "")
        try:
            ts = datetime.fromisoformat(expires_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if _now() > ts:
                raise HTTPException(status_code=410, detail={"code": "expired"})
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=410, detail={"code": "consumed"})
    raise HTTPException(status_code=404, detail={"code": "not_found"})


# ─── /consume (public) ───────────────────────────────────────────────
@router.post("/consume")
async def consume_magic_link(body: ConsumeIn, response: Response):
    row = await _find_link_record(body.token)
    if not row:
        raise HTTPException(status_code=410, detail={"code": "invalid_or_consumed"})

    app_row = await db.cohort_applications.find_one(
        {"id": row["application_id"]}, {"_id": 0},
    )
    if not app_row:
        raise HTTPException(status_code=404, detail={"code": "application_missing"})

    email = (app_row.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail={"code": "application_missing_email"})

    if body.mode == "password":
        if not body.password:
            raise HTTPException(status_code=400, detail={"code": "password_required"})
    elif body.mode in ("google", "microsoft"):
        # OAuth modes consume the token AFTER OAuth callback completes;
        # the callback should re-issue this consume with mode=password
        # impossible. For now we accept mode here only when oauth_code
        # was already validated upstream — out-of-scope to validate the
        # OAuth code in this endpoint (the existing
        # routers/auth_oauth.py callback handles that and links the
        # account, then calls this endpoint internally). For the
        # frontend "Continue with Google/Microsoft" buttons, we'll
        # generate the OAuth URL with `?magic_link_token={token}` and
        # complete consume inside the OAuth callback.
        raise HTTPException(
            status_code=400,
            detail={
                "code": "oauth_consume_via_callback",
                "message": "OAuth-mode consume happens inside the OAuth callback flow.",
            },
        )

    # Look up or create the account.
    acc = await db.accounts.find_one({"email_lc": email}, {"_id": 0})
    new_account = False
    if not acc:
        from core import iso, now as _core_now
        acc_id = uuid.uuid4().hex
        acc = {
            "id":            acc_id,
            "email":         email,
            "email_lc":      email,
            "first_name":    (app_row.get("name") or "").split()[0] if app_row.get("name") else "",
            "last_name":     " ".join((app_row.get("name") or "").split()[1:]) if app_row.get("name") else "",
            "status":        "active",
            "is_superadmin": False,
            "auth_provider": "password",
            "password_hash": hash_password(body.password) if body.mode == "password" else None,
            "created_at":    iso(_core_now()),
            "cohort_application_id": row["application_id"],
        }
        await db.accounts.insert_one(dict(acc))
        new_account = True
    else:
        # Existing account — set/refresh password if password mode.
        if body.mode == "password":
            await db.accounts.update_one(
                {"id": acc["id"]},
                {"$set": {
                    "password_hash": hash_password(body.password),
                    "auth_provider": "password",
                    "cohort_application_id": row["application_id"],
                }},
            )
            acc["password_hash"] = hash_password(body.password)

    # Mark the link consumed.
    await db.cohort_magic_links.update_one(
        {"id": row["id"]},
        {"$set": {
            "consumed_at":          _now().isoformat(),
            "consumed_by_user_id":  acc["id"],
        }},
    )
    # Update the application status to mark redemption (terminal — admin can still
    # touch via separate endpoint, out-of-scope here).
    await db.cohort_applications.update_one(
        {"id": row["application_id"]},
        {"$set": {
            "status":             "approved_redeemed",
            "redeemed_at":        _now().isoformat(),
            "redeemed_by":        acc["id"],
        }},
    )

    # Default workspace for fresh accounts.
    if new_account:
        try:
            await provision_default_context(acc)
        except Exception:  # noqa: BLE001
            log.warning("magic_link: failed to provision default context", exc_info=True)

    # Mint session.
    access = create_access_token(acc["id"], acc["email"])
    refresh = create_refresh_token(acc["id"])
    set_auth_cookies(response, access, refresh)

    try:
        await db.feature_events.insert_one({
            "account_id":  acc["id"],
            "event_type":  "cohort.magic_link.consumed",
            "occurred_at": _now().isoformat(),
            "payload":     {
                "application_id": row["application_id"],
                "mode":           body.mode,
                "new_account":    new_account,
            },
        })
    except Exception:  # noqa: BLE001
        log.warning("magic_link: failed to emit consumed event", exc_info=True)

    return {
        "ok":            True,
        "access_token":  access,
        "account":       sanitize_account(acc),
        "new_account":   new_account,
        "redirect":      "/app/work-studio",
    }
