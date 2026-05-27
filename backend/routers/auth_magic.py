"""Phase R.1 (2026-05-27) — Magic-link consume endpoint.

`GET /api/auth/magic/{token}` validates + atomically consumes the invite
row, creates or upgrades the account, mints a first-class JWT (Phase J
JTI revocation + idle-logoff apply), and 302-redirects to /app/.

Negative paths:
  Token not in DB        → 410 link_not_found
  Token already consumed → 410 link_already_used
  Token past expires_at  → 410 link_expired
  Per-IP rate limit hit  → 429 rate_limited

Race condition: double-click → two simultaneous GETs. The atomic
`find_one_and_update({status: "pending"}, ...)` in MongoDB guarantees
first-writer-wins. The second request gets None back from the update
(no document matched the filter — status is already "consumed") and
returns 410.

Test-only hook: `?json=1` query param suppresses the 302 redirect and
returns a JSON success payload instead. Used by the curl-based test
suite so we don't have to chase redirects. Production clients never
pass this param; the frontend uses the natural 302 path.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from core import (
    db, create_access_token, create_refresh_token, set_auth_cookies,
)


log = logging.getLogger("akki.cohort.magic")
router = APIRouter(prefix="/api/auth", tags=["auth-magic"])


# ─────────────────────────────────────────────────────────────────────
# Rate limiting (Q-g from playbook outcome). Per-IP, in-memory, 10
# requests / 5 minutes. Token entropy is 256 bits so brute-force is
# computationally impossible; this guards against bot scanning that
# would otherwise generate noise in the logs.
# ─────────────────────────────────────────────────────────────────────
_RATE_WINDOW_S = 5 * 60
_RATE_LIMIT = 10
_recent: Dict[str, Deque[float]] = defaultdict(deque)


def _check_rate_limit(ip: str) -> bool:
    now_ts = time.time()
    bucket = _recent[ip]
    while bucket and now_ts - bucket[0] > _RATE_WINDOW_S:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        return False
    bucket.append(now_ts)
    return True


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _public_base(request: Request) -> str:
    from_env = (
        os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
    )
    if from_env:
        return from_env.rstrip("/")
    return f"{request.url.scheme}://{request.url.netloc}"


def _is_expired(iso_str: str) -> bool:
    try:
        exp = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp < _now()
    except Exception:
        return True  # malformed → treat as expired (defense-in-depth)


# ═════════════════════════════════════════════════════════════════════
# GET /api/auth/magic/{token} — consume a cohort invite
# ═════════════════════════════════════════════════════════════════════
@router.get("/magic/{token}")
async def consume_magic_link(
    token: str,
    request: Request,
    json_mode: int = Query(default=0, alias="json"),
):
    ip = _client_ip(request)
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail={"error": "rate_limited"})

    # 1. Look up the invite. No HMAC verification (Option B per playbook
    #    outcome) — the 256-bit entropy of `secrets.token_urlsafe(32)` IS
    #    the validity check.
    pre = await db.cohort_invites.find_one(
        {"magic_link_token": token},
        {"_id": 0},
    )
    if not pre:
        # Tampered or never-issued token. Q-d acceptance test expects
        # 410 link_not_found per the user's locked override.
        raise HTTPException(status_code=410, detail={"error": "link_not_found"})

    # 2. Already-consumed? → 410 (don't even peek at expiry).
    if pre.get("consumed_at"):
        raise HTTPException(status_code=410, detail={
            "error":       "link_already_used",
            "invite_id":   pre["id"],
            "consumed_at": pre["consumed_at"],
        })

    # 3. Expired?
    if _is_expired(pre["expires_at"]):
        raise HTTPException(status_code=410, detail={
            "error":     "link_expired",
            "expires_at": pre["expires_at"],
        })

    # 4. ATOMIC SINGLE-USE FLIP FIRST. We claim the invite before
    #    touching the accounts collection so racing requests can't both
    #    succeed and end up double-inserting on the email_1 unique
    #    index. The `consumed_by_account_id` is filled in step 6 once
    #    we know which account_id won.
    email = pre["email"]
    trial_start = _now()
    trial_end = trial_start + timedelta(days=pre["trial_length_days"])

    claim = await db.cohort_invites.find_one_and_update(
        {"magic_link_token": token, "status": "pending", "consumed_at": None},
        {"$set": {
            "status":      "consumed",
            "consumed_at": _now_iso(),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    if not claim:
        # We lost the race to another concurrent request. The other
        # one will create/upgrade the account; we just report 410.
        post = await db.cohort_invites.find_one(
            {"magic_link_token": token},
            {"_id": 0, "id": 1, "consumed_at": 1},
        ) or {}
        raise HTTPException(status_code=410, detail={
            "error":       "link_already_used",
            "invite_id":   post.get("id"),
            "consumed_at": post.get("consumed_at"),
        })

    # 5. Resolve OR create the account. Email is lowercased throughout.
    account = await db.accounts.find_one({"email": email}, {"_id": 0})
    if account:
        # UPGRADE branch (Risk #6): stamp trial fields on top of the
        # existing row. Do NOT reset first_session.status; do NOT bump
        # sessions_revoked_after; do NOT change password_hash. If
        # first_name / logo_name were already set, the invite values
        # win only when the existing value is null (don't overwrite
        # user-set names).
        update_fields = {
            "trial_start_at":           trial_start.isoformat(),
            "trial_end_at":             trial_end.isoformat(),
            "trial_status":             "active_trial",
            "cohort_tag":               pre["cohort_tag"],
            "grandfathered_price_locked": False,
        }
        if not account.get("first_name") and pre.get("first_name"):
            update_fields["first_name"] = pre["first_name"]
        if not account.get("logo_name") and pre.get("logo_name"):
            update_fields["logo_name"] = pre["logo_name"]
        await db.accounts.update_one(
            {"id": account["id"]},
            {"$set": update_fields},
        )
        account_id = account["id"]
    else:
        # NEW account (passwordless). declared_role=null; first_session
        # starts at "intake" so the standard FirstSessionGuard bounces
        # them to the 4-step wizard (Q1=(a) per locked decision).
        account_id = uuid.uuid4().hex
        await db.accounts.insert_one({
            "id":              account_id,
            "email":           email,
            "password_hash":   None,                  # passwordless — magic-link only
            "name":            pre.get("first_name") or email.split("@")[0],
            "declared_role":   None,                  # Q2 — wizard collects
            "mfa_enabled":     False,
            "is_superadmin":   False,
            "first_session":   {"status": "intake"},
            "preferences":     {},
            "trial_start_at":  trial_start.isoformat(),
            "trial_end_at":    trial_end.isoformat(),
            "trial_status":    "active_trial",
            "cohort_tag":      pre["cohort_tag"],
            "grandfathered_price_locked": False,
            "first_name":      pre.get("first_name"),
            "logo_name":       pre.get("logo_name"),
            "created_at":      _now_iso(),
        })

    # 6. Stamp the winning account_id back onto the claimed invite row.
    await db.cohort_invites.update_one(
        {"id": claim["id"]},
        {"$set": {"consumed_by_account_id": account_id}},
    )

    # 6. Mint a first-class JWT — Phase J JTI revocation + idle logoff
    #    apply uniformly (Q-e per playbook outcome).
    access = create_access_token(account_id, email)
    refresh = create_refresh_token(account_id)

    # 7. Return path: 302 redirect to /app/ with cookies set (production
    #    flow), OR JSON success (test mode `?json=1`).
    if json_mode:
        resp = Response(content=None, status_code=200, media_type="application/json")
        set_auth_cookies(resp, access, refresh)
        # Bodyless 200 isn't useful for testing — write a JSON payload.
        from fastapi.responses import JSONResponse
        body = {
            "ok":              True,
            "account_id":      account_id,
            "email":           email,
            "trial_status":    "active_trial",
            "trial_end_at":    trial_end.isoformat(),
            "cohort_tag":      pre["cohort_tag"],
            "invite_id":       claim["id"],
            "access_token":    access,
        }
        json_resp = JSONResponse(content=body)
        set_auth_cookies(json_resp, access, refresh)
        return json_resp

    # Production path — 302 to /app/. The frontend's AuthContext will
    # call /api/auth/me on mount (with the just-set httponly cookie)
    # and resolve the session.
    base = _public_base(request)
    redirect_url = f"{base}/app/" if base else "/app/"
    resp = RedirectResponse(url=redirect_url, status_code=302)
    set_auth_cookies(resp, access, refresh)
    return resp
