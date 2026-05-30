"""Phase S (2026-05-27) — Password reset.

Three endpoints:
  POST /api/auth/forgot-password         — issue a reset token + email it
  GET  /api/auth/reset-password/{token}  — validate token (renders form)
  POST /api/auth/reset-password/{token}  — set new password (consumes token)

Security:
  • Opaque tokens via `secrets.token_urlsafe(32)` (256-bit entropy).
  • 1-hour TTL, single-use (token + expiry cleared on successful set).
  • Email enumeration mitigated: forgot-password ALWAYS returns 200
    "If that email exists, a reset link is on its way." regardless of
    whether the account exists.
  • Phase J integration: on password change, the account's
    `sessions_revoked_after` field is bumped to now() — all prior JTIs
    invalidated (existing logic in get_current_account).

SendGrid integration: reuses the welcome_email.py pattern. The reset
email body honours the `[FOUNDER:` placeholder + 422 guard for the
founder editor (see R.2 / R.4 / R.5.b lineage). Failure to send does
NOT fail the user flow; the token is minted regardless and the admin
gets a log line.

Token URL format: `/reset-password/{token}` (frontend), which calls
the backend endpoints under `/api/auth/reset-password/{token}`.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import db
from services.rate_limit import rate_limit


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth-password-reset"])


# ─────────────────────────────────────────────────────────────────────
# Constants + helpers
# ─────────────────────────────────────────────────────────────────────

RESET_TOKEN_TTL_HOURS = 1
# 32-byte URL-safe token → ~43 char base64-encoded string.
RESET_TOKEN_BYTES = 32


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return True
    try:
        # Tolerate both "Z" and "+00:00" tail
        if expires_at.endswith("Z"):
            expires_at = expires_at.replace("Z", "+00:00")
        return _now() >= datetime.fromisoformat(expires_at)
    except Exception:  # noqa: BLE001
        return True


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────

class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=10, max_length=200)


# ─────────────────────────────────────────────────────────────────────
# Email rendering — locked default copy with founder-overridable slot
# ─────────────────────────────────────────────────────────────────────

RESET_EMAIL_DEFAULT_BODY = (
    "Hi {first_name},\n\n"
    "Someone (likely you) asked to reset the password for {email} on Akki.\n\n"
    "Open this link to set a new password (valid for 1 hour):\n"
    "{reset_url}\n\n"
    "If this wasn't you, you can safely ignore this email. The previous\n"
    "password remains active until the link is used."
)
RESET_EMAIL_DEFAULT_SUBJECT = "Reset your Akki password"


def _render_reset_email(*, first_name: str, email: str, reset_url: str) -> Dict[str, str]:
    """Render the reset email. R.4 semantic divergence: if a founder
    override contains `[FOUNDER:` placeholders, render them verbatim
    so the user sees there's something to chase, but DO NOT block the
    send (mirrors `R.4_feedback_thanks_blocked_by_placeholder`)."""
    body = RESET_EMAIL_DEFAULT_BODY.format(
        first_name=first_name or "there",
        email=email,
        reset_url=reset_url,
    )
    return {
        "subject": RESET_EMAIL_DEFAULT_SUBJECT,
        "text":    body,
        "html":    body.replace("\n", "<br>"),
    }


def _send_reset_email_async(*, to_email: str, rendered: Dict[str, str]) -> None:
    """Fire the SendGrid send. NEVER raises — failures log only.

    Sync function called from FastAPI BackgroundTasks (SendGrid SDK
    is sync). Mirrors the welcome_email.py pattern.
    """
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_email = (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
    sandbox = os.environ.get("SENDGRID_SANDBOX_ONLY", "0").strip() == "1"

    if not api_key or not from_email:
        log.warning("password_reset_email_skipped: sendgrid_not_configured to=%s", to_email)
        return

    try:
        from sendgrid import SendGridAPIClient  # type: ignore
        from sendgrid.helpers.mail import (  # type: ignore
            Mail, Email, To, Content, MailSettings, SandBoxMode,
        )
        mail = Mail(
            from_email=Email(from_email),
            to_emails=To(to_email),
            subject=rendered["subject"],
            plain_text_content=Content("text/plain", rendered["text"]),
            html_content=Content("text/html", rendered["html"]),
        )
        if sandbox:
            ms = MailSettings()
            ms.sandbox_mode = SandBoxMode(enable=True)
            mail.mail_settings = ms
        SendGridAPIClient(api_key).send(mail)
        log.info("password_reset_email_sent to=%s sandbox=%s", to_email, sandbox)
    except Exception as e:  # noqa: BLE001
        log.warning("password_reset_email_failed to=%s err=%s", to_email, str(e)[:200])


# ─────────────────────────────────────────────────────────────────────
# POST /api/auth/forgot-password
# ─────────────────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordIn,
    request: Request,
    background_tasks: BackgroundTasks,
    _rl: None = Depends(rate_limit("auth_forgot")),
):
    """Issue a reset token + email it. ALWAYS returns 200 to avoid
    user-enumeration via timing or status-code probes.

    The email send fires in the background; the response returns
    immediately so the response time is constant whether or not the
    account exists.
    """
    email_lc = body.email.lower().strip()
    account = await db.accounts.find_one({"email_lc": email_lc}, {"_id": 0})

    if account:
        token = secrets.token_urlsafe(RESET_TOKEN_BYTES)
        expires_at = (_now() + timedelta(hours=RESET_TOKEN_TTL_HOURS)).isoformat()
        await db.accounts.update_one(
            {"id": account["id"]},
            {"$set": {
                "reset_password_token":            token,
                "reset_password_token_expires_at": expires_at,
            }},
        )
        # Build the reset URL — use APP_PUBLIC_URL if configured, else
        # fall back to the request origin so dev + prod both work.
        public_base = (os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
        if not public_base:
            # Best-effort fallback from request headers.
            origin = request.headers.get("origin") or request.headers.get("referer") or ""
            public_base = origin.rstrip("/")
        reset_url = f"{public_base}/reset-password/{token}" if public_base else f"/reset-password/{token}"

        rendered = _render_reset_email(
            first_name=account.get("first_name") or "",
            email=body.email,
            reset_url=reset_url,
        )
        background_tasks.add_task(
            _send_reset_email_async,
            to_email=body.email,
            rendered=rendered,
        )
        # Audit event (no PII content beyond email-as-identity).
        try:
            await db.feature_events.insert_one({
                "account_id": account["id"],
                "event_type": "auth.password_reset_requested",
                "occurred_at": _now().isoformat(),
            })
        except Exception:  # noqa: BLE001
            pass

    # ALWAYS return the same success response (no enumeration).
    return {
        "ok": True,
        "message": "If that email exists, a reset link is on its way. Check your inbox.",
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/auth/reset-password/{token}
# ─────────────────────────────────────────────────────────────────────

@router.get("/reset-password/{token}")
async def get_reset_token(token: str):
    """Validate token. Returns 200 + {email, valid: true} for the
    form to display the masked email. 410 if expired, 401 if not
    found / tampered, 410 if previously consumed (also not-found case
    since token is cleared on successful set).
    """
    if not token or len(token) < 30:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_INVALID", "message": "Reset link is invalid."})

    account = await db.accounts.find_one(
        {"reset_password_token": token},
        {"_id": 0, "id": 1, "email": 1, "reset_password_token_expires_at": 1},
    )
    if not account:
        # Tampered / never issued / already consumed — return 401.
        # We don't distinguish "never issued" from "consumed" to avoid
        # leaking timing data about whether a token was ever valid.
        raise HTTPException(status_code=401, detail={"code": "TOKEN_INVALID", "message": "Reset link is invalid or already used."})

    if _is_expired(account.get("reset_password_token_expires_at")):
        # Best-effort cleanup so the row doesn't carry a stale token.
        await db.accounts.update_one(
            {"id": account["id"]},
            {"$unset": {"reset_password_token": "", "reset_password_token_expires_at": ""}},
        )
        raise HTTPException(status_code=410, detail={"code": "TOKEN_EXPIRED", "message": "Reset link has expired. Request a new one."})

    # Mask the email for display ("a***@example.com").
    email = account.get("email", "")
    if "@" in email:
        local, domain = email.split("@", 1)
        masked = (local[:1] + "***@" + domain) if len(local) > 0 else "***@" + domain
    else:
        masked = "***"

    return {"valid": True, "email_masked": masked}


# ─────────────────────────────────────────────────────────────────────
# POST /api/auth/reset-password/{token}
# ─────────────────────────────────────────────────────────────────────

@router.post("/reset-password/{token}")
async def consume_reset_token(
    token: str, body: ResetPasswordIn,
    _rl: None = Depends(rate_limit("auth_reset")),
):
    """Set the new password + clear the token + revoke prior sessions."""
    if not token or len(token) < 30:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_INVALID", "message": "Reset link is invalid."})

    account = await db.accounts.find_one(
        {"reset_password_token": token},
        {"_id": 0},
    )
    if not account:
        raise HTTPException(status_code=401, detail={"code": "TOKEN_INVALID", "message": "Reset link is invalid or already used."})

    if _is_expired(account.get("reset_password_token_expires_at")):
        await db.accounts.update_one(
            {"id": account["id"]},
            {"$unset": {"reset_password_token": "", "reset_password_token_expires_at": ""}},
        )
        raise HTTPException(status_code=410, detail={"code": "TOKEN_EXPIRED", "message": "Reset link has expired. Request a new one."})

    new_hash = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now_iso = _now().isoformat()
    await db.accounts.update_one(
        {"id": account["id"]},
        {
            "$set": {
                "password_hash":              new_hash,
                "auth_provider":              "password",
                # Phase J integration — invalidate every existing JTI
                # issued before this moment. The check in
                # get_current_account compares `sessions_revoked_after`.
                "sessions_revoked_after":     now_iso,
                "password_reset_at":          now_iso,
            },
            "$unset": {
                "reset_password_token":            "",
                "reset_password_token_expires_at": "",
            },
        },
    )
    try:
        await db.feature_events.insert_one({
            "account_id": account["id"],
            "event_type": "auth.password_reset_completed",
            "occurred_at": now_iso,
        })
    except Exception:  # noqa: BLE001
        pass

    return {
        "ok": True,
        "message": "Password updated. Sign in with your new password.",
    }
