"""Phase P2 B.4 (2026-02) — In-app password change for the logged-in user.

Endpoint:
  POST /api/auth/password/change
    body: { current_password, new_password }

Behaviour:
  - Verify `current_password` against the stored hash. 401 if wrong.
  - Hash the new password with bcrypt (gensalt) and store.
  - Bump `sessions_revoked_after = now()` so every other JTI issued
    before this moment is invalidated (Phase J integration).
  - Mint a fresh access token + refresh cookie for the CURRENT session
    so the user stays signed in on this device.
  - Audit row written to `feature_events` (no PII content — operational
    metadata only).
  - Reject if account uses passwordless / OAuth-only auth (no current
    password to verify against).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from core import (
    db, get_current_account,
    create_access_token, create_refresh_token,
    set_auth_cookies,
)
from services.rate_limit import rate_limit


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth-password-change"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password:     str = Field(min_length=10, max_length=200)


@router.post("/password/change")
async def change_password(
    body: PasswordChangeIn,
    response: Response,
    current: Dict[str, Any] = Depends(get_current_account),
    _rl: None = Depends(rate_limit("auth_pwchange")),
):
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400,
            detail={"code": "SAME_PASSWORD", "message": "New password must differ from current."},
        )

    stored = current.get("password_hash")
    if not stored:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PASSWORDLESS_ACCOUNT",
                "message": "This account uses passwordless sign-in. Set a password via the forgot-password flow.",
            },
        )

    # Verify current password.
    try:
        ok = bcrypt.checkpw(body.current_password.encode("utf-8"), stored.encode("utf-8"))
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        raise HTTPException(
            status_code=401,
            detail={"code": "CURRENT_PASSWORD_WRONG", "message": "Current password is incorrect."},
        )

    new_hash = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now_iso = _now_iso()

    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {
            "password_hash":          new_hash,
            "auth_provider":          "password",
            "password_reset_at":      now_iso,
            # Phase J — invalidate every JTI issued before this moment.
            "sessions_revoked_after": now_iso,
        }},
    )

    # Mint fresh tokens for the current session so the user stays
    # signed in on THIS device. Other devices' tokens fail at the JTI
    # / sessions_revoked_after check.
    access = create_access_token(current["id"], current["email"])
    refresh = create_refresh_token(current["id"])
    set_auth_cookies(response, access, refresh)

    try:
        await db.feature_events.insert_one({
            "account_id":  current["id"],
            "event_type":  "auth.password_changed_in_app",
            "occurred_at": now_iso,
        })
    except Exception:  # noqa: BLE001
        log.warning("B.4 — failed to emit auth.password_changed_in_app event", exc_info=True)

    return {
        "ok":           True,
        "access_token": access,
        "message":      "Password updated. Other devices have been signed out.",
    }
