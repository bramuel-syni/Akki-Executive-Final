"""Phase P3.3 (2026-02) — MFA enrolment, verification, recovery codes.

Replaces the earlier `/api/auth/mfa/setup` + `/api/auth/mfa/verify`
endpoints with a more complete flow:

  - POST /api/auth/mfa/enroll/start   → start enrolment (otpauth URL + QR)
  - POST /api/auth/mfa/enroll/confirm → confirm 6-digit code, generate recovery codes
  - POST /api/auth/mfa/verify         → verify 6-digit code on login (or recovery code)
  - POST /api/auth/mfa/disable        → disable MFA (requires password re-auth)
  - POST /api/auth/mfa/recovery/regenerate → regenerate recovery codes (requires fresh TOTP code)

Storage on `accounts`:
  - `mfa_enabled` (bool)
  - `mfa_secret` (str, base32 TOTP secret — encrypted-at-rest via MongoDB at rest if available)
  - `mfa_secret_pending` (str, set during enrolment, removed on confirm/cancel)
  - `mfa_recovery_codes` (list[str], each a bcrypt hash of a single-use recovery code)
  - `mfa_failed_attempts` (int, lifetime counter; resets on success)
  - `mfa_locked_until` (str ISO timestamp; admin-clearable)

Lock policy: 5 consecutive failed `/verify` codes within a 15-min
window → account is MFA-locked for 15 min. The lock is distinct from
the per-route rate limit (which sits in front of this check).

Recovery codes: 10 single-use, 12-character codes formatted as
`XXXX-XXXX-XXXX` for human transcription. Stored as bcrypt hashes;
the raw codes are returned exactly once at enrolment + regeneration.

Voice-clean: every user-facing copy line passes voice_lint.py.
"""
from __future__ import annotations

import base64
import io
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from core import (
    APP_NAME, db, get_current_account,
    create_access_token, create_refresh_token,
    set_auth_cookies, hash_password, verify_password,
)
from services.rate_limit import rate_limit


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/mfa", tags=["mfa"])


# ─── Tunables ────────────────────────────────────────────────────────
MFA_LOCK_AFTER_FAILED = 5
MFA_LOCK_WINDOW_MINUTES = 15
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_LENGTH = 12  # 12 chars (3 groups of 4)
RECOVERY_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> List[str]:
    """Return `count` codes formatted XXXX-XXXX-XXXX (A-Z + 0-9)."""
    out = []
    for _ in range(count):
        raw = "".join(secrets.choice(RECOVERY_CODE_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH))
        out.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return out


def _hash_recovery_codes(codes: List[str]) -> List[str]:
    return [bcrypt.hashpw(c.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for c in codes]


async def _is_locked(account: Dict[str, Any]) -> bool:
    locked_until = account.get("mfa_locked_until")
    if not locked_until:
        return False
    try:
        ts = datetime.fromisoformat(locked_until)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return _now() < ts
    except Exception:  # noqa: BLE001
        return False


async def _record_failed(account_id: str) -> None:
    """Bump the failed counter; lock the account on the 5th consecutive failure."""
    acc = await db.accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        return
    failed = int(acc.get("mfa_failed_attempts", 0)) + 1
    update: Dict[str, Any] = {"mfa_failed_attempts": failed}
    if failed >= MFA_LOCK_AFTER_FAILED:
        lock_until = _now() + timedelta(minutes=MFA_LOCK_WINDOW_MINUTES)
        update["mfa_locked_until"] = lock_until.isoformat()
        update["mfa_failed_attempts"] = 0   # reset counter for the next window
        try:
            await db.feature_events.insert_one({
                "account_id":  account_id,
                "event_type":  "auth.mfa.locked",
                "occurred_at": _now().isoformat(),
                "payload":     {"lock_minutes": MFA_LOCK_WINDOW_MINUTES},
            })
        except Exception:  # noqa: BLE001
            log.warning("MFA — failed to emit lock event", exc_info=True)
    await db.accounts.update_one({"id": account_id}, {"$set": update})


async def _record_success(account_id: str) -> None:
    await db.accounts.update_one(
        {"id": account_id},
        {"$set": {"mfa_failed_attempts": 0}, "$unset": {"mfa_locked_until": ""}},
    )


# ─── Schemas ─────────────────────────────────────────────────────────
class MFAConfirmIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MFAVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=14)  # accept TOTP or recovery


class MFADisableIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


# ─── Endpoints ───────────────────────────────────────────────────────
@router.post("/enroll/start")
async def enroll_start(
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Mint a fresh TOTP secret + return the QR data URL. Idempotent —
    calling again rotates the pending secret. Confirm must happen
    before the secret becomes active."""
    secret = pyotp.random_base32()
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current["email"], issuer_name=APP_NAME,
    )
    img = qrcode.make(otpauth)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"mfa_secret_pending": secret}},
    )
    return {
        "otpauth_url": otpauth,
        "qr_data_url": qr_data_url,
        "secret":      secret,
    }


@router.post("/enroll/confirm")
async def enroll_confirm(
    body: MFAConfirmIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Confirm enrolment with a 6-digit TOTP code. Returns the 10
    recovery codes ONCE — they will not be retrievable afterwards."""
    pending = current.get("mfa_secret_pending")
    if not pending:
        raise HTTPException(
            status_code=400,
            detail={"code": "MFA_NOT_PENDING", "message": "Start enrolment before confirming."},
        )
    totp = pyotp.TOTP(pending)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=400,
            detail={"code": "MFA_CODE_INVALID", "message": "That passcode did not match. Try the next one."},
        )

    recovery_codes = _generate_recovery_codes()
    hashed_codes = _hash_recovery_codes(recovery_codes)

    await db.accounts.update_one(
        {"id": current["id"]},
        {
            "$set": {
                "mfa_enabled":        True,
                "mfa_secret":         pending,
                "mfa_recovery_codes": hashed_codes,
                "mfa_enrolled_at":    _now().isoformat(),
                "mfa_failed_attempts": 0,
            },
            "$unset": {"mfa_secret_pending": "", "mfa_locked_until": ""},
        },
    )
    try:
        await db.feature_events.insert_one({
            "account_id":  current["id"],
            "event_type":  "auth.mfa.enrolled",
            "occurred_at": _now().isoformat(),
        })
    except Exception:  # noqa: BLE001
        log.warning("MFA — failed to emit enrol event", exc_info=True)

    return {
        "ok":              True,
        "mfa_enabled":     True,
        "recovery_codes":  recovery_codes,   # ⚠ shown once
        "code_count":      len(recovery_codes),
    }


@router.post("/verify")
async def verify(
    body: MFAVerifyIn,
    response: Response,
    current: Dict[str, Any] = Depends(get_current_account),
    _rl: None = Depends(rate_limit("auth_login")),
):
    """Verify a TOTP code OR a recovery code. Issues fresh auth tokens
    on success (so the post-login JWT carries an `mfa_verified` claim)."""
    if not current.get("mfa_enabled"):
        raise HTTPException(
            status_code=400,
            detail={"code": "MFA_NOT_ENABLED", "message": "MFA is not enabled on this account."},
        )

    if await _is_locked(current):
        raise HTTPException(
            status_code=429,
            detail={
                "code":    "MFA_LOCKED",
                "message": "Too many wrong passcodes. Try again in a few minutes.",
            },
        )

    code = body.code.strip().upper().replace(" ", "")

    # Try TOTP first (6 digits).
    ok = False
    used_recovery_idx: Optional[int] = None
    if len(code.replace("-", "")) <= 8:
        try:
            ok = pyotp.TOTP(current["mfa_secret"]).verify(code, valid_window=1)
        except Exception:  # noqa: BLE001
            ok = False

    # Try recovery code (14 chars including dashes).
    if not ok:
        hashed = current.get("mfa_recovery_codes") or []
        for i, h in enumerate(hashed):
            try:
                if bcrypt.checkpw(code.encode("utf-8"), h.encode("utf-8")):
                    ok = True
                    used_recovery_idx = i
                    break
            except Exception:  # noqa: BLE001
                continue

    if not ok:
        await _record_failed(current["id"])
        raise HTTPException(
            status_code=401,
            detail={"code": "MFA_CODE_INVALID", "message": "That passcode did not match."},
        )

    await _record_success(current["id"])

    # Burn the recovery code if one was used.
    if used_recovery_idx is not None:
        hashed = current.get("mfa_recovery_codes") or []
        hashed.pop(used_recovery_idx)
        await db.accounts.update_one(
            {"id": current["id"]},
            {"$set": {"mfa_recovery_codes": hashed}},
        )

    # Issue fresh tokens carrying `mfa_verified=true`.
    access = create_access_token(current["id"], current["email"], mfa_verified=True)
    refresh = create_refresh_token(current["id"])
    set_auth_cookies(response, access, refresh)
    try:
        await db.feature_events.insert_one({
            "account_id":  current["id"],
            "event_type":  "auth.mfa.verified",
            "occurred_at": _now().isoformat(),
            "payload":     {"used_recovery": used_recovery_idx is not None},
        })
    except Exception:  # noqa: BLE001
        log.warning("MFA — failed to emit verify event", exc_info=True)

    return {
        "ok":           True,
        "mfa_verified": True,
        "access_token": access,
        "recovery_codes_remaining": len((await db.accounts.find_one({"id": current["id"]}, {"_id": 0}) or {}).get("mfa_recovery_codes") or []),
    }


@router.post("/disable")
async def disable(
    body: MFADisableIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Disable MFA. Requires the user to re-prove the password (defense
    against a stolen but unlocked session)."""
    stored = current.get("password_hash")
    if not stored or not verify_password(body.password, stored):
        raise HTTPException(
            status_code=401,
            detail={"code": "PASSWORD_INVALID", "message": "Password did not match."},
        )
    await db.accounts.update_one(
        {"id": current["id"]},
        {
            "$set": {"mfa_enabled": False},
            "$unset": {
                "mfa_secret": "",
                "mfa_secret_pending": "",
                "mfa_recovery_codes": "",
                "mfa_locked_until": "",
            },
        },
    )
    try:
        await db.feature_events.insert_one({
            "account_id":  current["id"],
            "event_type":  "auth.mfa.disabled",
            "occurred_at": _now().isoformat(),
        })
    except Exception:  # noqa: BLE001
        log.warning("MFA — failed to emit disable event", exc_info=True)
    return {"ok": True, "mfa_enabled": False}


@router.post("/recovery/regenerate")
async def regenerate_recovery(
    body: MFAConfirmIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Regenerate the 10 recovery codes. Requires a fresh TOTP code to
    prove the user has the authenticator app (defense against burning
    everyone's recovery codes from a compromised session)."""
    if not current.get("mfa_enabled"):
        raise HTTPException(
            status_code=400,
            detail={"code": "MFA_NOT_ENABLED", "message": "MFA is not enabled on this account."},
        )
    totp = pyotp.TOTP(current["mfa_secret"])
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=400,
            detail={"code": "MFA_CODE_INVALID", "message": "That passcode did not match. Try the next one."},
        )
    recovery_codes = _generate_recovery_codes()
    hashed = _hash_recovery_codes(recovery_codes)
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"mfa_recovery_codes": hashed, "mfa_recovery_regenerated_at": _now().isoformat()}},
    )
    return {"ok": True, "recovery_codes": recovery_codes, "code_count": len(recovery_codes)}


@router.get("/status")
async def status(current: Dict[str, Any] = Depends(get_current_account)):
    """Lightweight status endpoint for the frontend to render the
    Account → Security panel."""
    return {
        "mfa_enabled":     bool(current.get("mfa_enabled")),
        "enrolled_at":     current.get("mfa_enrolled_at"),
        "recovery_codes_remaining": len(current.get("mfa_recovery_codes") or []),
        "locked":          await _is_locked(current),
    }
