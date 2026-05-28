"""Phase U (2026-05-27) — OAuth/SSO sign-in (Google + Microsoft).

Per the integration_playbook_expert_v2 brief — uses Emergent Auth for
Google (zero-config, browser-derived redirect URL). The Microsoft
route returns a locked 503 payload until creds arrive (Phase U.2).

Architecture decision:
  Emergent Auth resolves the identity → we mint OUR OWN JWT using the
  existing `core.create_access_token` / `create_refresh_token`
  helpers. This keeps Phase J's JTI revocation + idle-logoff contract
  uniform across magic-link, password, and OAuth sign-in paths.

Endpoints:
  GET  /api/auth/oauth/google/start
       Returns {redirect_url, callback_path}. Frontend builds the
       final URL using `window.location.origin + callback_path`.
  POST /api/auth/oauth/google/finish
       Body {session_id}. Backend calls Emergent's session-data
       endpoint, finds-or-creates the account
       (`auth_provider="google"`, `password_hash=None`), mints JWT +
       sets cookies + returns `{token, account, is_new, next_url}`.
  POST /api/auth/oauth/microsoft/start
       Returns 503 + locked payload {error: "microsoft_oauth_not_configured"}.

Negative paths handled:
  Invalid / expired session_id     → 400 oauth_session_invalid
  Emergent Auth endpoint unreachable → 502 oauth_provider_unreachable
  Missing email in profile         → 400 oauth_email_missing
  Account exists with different
    auth_provider (password)       → 200 (signs in — passwordless
                                      flag is purely informational)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import (
    db, create_access_token, create_refresh_token, set_auth_cookies,
)


log = logging.getLogger("akki.auth.oauth")
router = APIRouter(prefix="/api/auth/oauth", tags=["auth-oauth"])


# ─────────────────────────────────────────────────────────────────────
# Emergent Auth constants — locked per playbook
# ─────────────────────────────────────────────────────────────────────
EMERGENT_AUTH_URL = "https://auth.emergentagent.com/"
EMERGENT_SESSION_DATA_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)
# Frontend will tack this onto window.location.origin and pass it as
# the `redirect` query param. The Emergent Auth auth flow redirects back to
# `{origin}{OAUTH_CALLBACK_PATH}#session_id=<random>`.
OAUTH_CALLBACK_PATH = "/oauth/callback"
TRIAL_LENGTH_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ─────────────────────────────────────────────────────────────────────
# Google — start (returns the Emergent Auth redirect base)
# ─────────────────────────────────────────────────────────────────────
@router.get("/google/start")
async def oauth_google_start() -> Dict[str, Any]:
    """Return the Emergent Auth base URL + callback path.

    Per the playbook the redirect URL MUST be derived on the client
    from `window.location.origin` (NEVER hardcoded on the backend),
    so this endpoint just returns the building blocks and the
    frontend assembles the final URL.

    REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR
    REDIRECT URLS — THIS BREAKS THE AUTH.
    """
    return {
        "auth_base_url": EMERGENT_AUTH_URL,
        "callback_path": OAUTH_CALLBACK_PATH,
        "provider": "google",
    }


# ─────────────────────────────────────────────────────────────────────
# Google — finish (exchange session_id → mint our JWT)
# ─────────────────────────────────────────────────────────────────────
class FinishIn(BaseModel):
    session_id: str = Field(min_length=4, max_length=512)


@router.post("/google/finish")
async def oauth_google_finish(
    body: FinishIn, response: Response,
) -> Dict[str, Any]:
    """Exchange the Emergent Auth session_id for the user identity, then
    find-or-create the account + mint our JWT.

    The frontend POSTs `{session_id}` AFTER the browser lands at
    `/oauth/callback#session_id=<random>`. The hash fragment never
    leaves the browser — the frontend explicitly forwards the value
    here.
    """
    # 1. Resolve the identity via Emergent's session-data endpoint.
    profile = await _fetch_emergent_session_data(body.session_id)

    # 2. Extract + validate the email.
    email = (profile.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={
            "error": "oauth_email_missing",
            "message": "OAuth provider did not return an email address.",
        })

    name = (profile.get("name") or "").strip()
    picture = (profile.get("picture") or "").strip() or None

    # 3. Find-or-create the account (matching the magic-link upgrade
    #    pattern from auth_magic.py — preserve any existing
    #    user-set fields).
    existing = await db.accounts.find_one({"email": email}, {"_id": 0})
    is_new = existing is None
    trial_start = _now()
    trial_end = trial_start + timedelta(days=TRIAL_LENGTH_DAYS)

    if existing:
        account_id = existing["id"]
        update_fields: Dict[str, Any] = {
            # Stamp last_login + remember the OAuth provider used.
            # Don't overwrite an existing auth_provider if the
            # account already has one set (a password account that
            # then signs in via Google keeps `auth_provider`
            # unchanged but gains an `oauth_providers` array).
            "last_login_at": _iso(trial_start),
        }
        # Track which providers the account has used for sign-in.
        providers_used: list[str] = list(existing.get("oauth_providers") or [])
        if "google" not in providers_used:
            providers_used.append("google")
            update_fields["oauth_providers"] = providers_used
        # If the account has no auth_provider AND no password_hash,
        # this is a fresh provision via OAuth — stamp it as such.
        if not existing.get("auth_provider") and not existing.get("password_hash"):
            update_fields["auth_provider"] = "google"
        # If name was empty, fill it in from the Google profile.
        if not existing.get("name") and name:
            update_fields["name"] = name
        if not existing.get("first_name") and name:
            update_fields["first_name"] = name.split()[0]
        if picture and not existing.get("picture"):
            update_fields["picture"] = picture
        await db.accounts.update_one(
            {"id": account_id}, {"$set": update_fields},
        )
        next_url = "/app/"
    else:
        # New passwordless account. `first_session.status = "intake"`
        # so the FirstSessionGuard bounces them to the 4-step wizard
        # (mirrors magic-link first-session path).
        account_id = uuid.uuid4().hex
        first_name = (name.split()[0] if name else email.split("@")[0])
        await db.accounts.insert_one({
            "id":              account_id,
            "email":           email,
            "password_hash":   None,                  # passwordless — OAuth only
            "auth_provider":   "google",
            "oauth_providers": ["google"],
            "name":            name or email.split("@")[0],
            "first_name":      first_name,
            "picture":         picture,
            "declared_role":   None,
            "mfa_enabled":     False,
            "is_superadmin":   False,
            "first_session":   {"status": "intake"},
            "preferences":     {},
            "trial_start_at":  _iso(trial_start),
            "trial_end_at":    _iso(trial_end),
            "trial_status":    "active_trial",
            "cohort_tag":      None,
            "created_at":      _iso(trial_start),
            "last_login_at":   _iso(trial_start),
        })
        next_url = "/app/first-session"

    # 4. Best-effort feature event emit (mirrors magic-link path).
    try:
        from services.cohort.feature_events import (
            emit_feature_event,
            ACCOUNT_SIGNED_UP,
        )
        if is_new:
            await emit_feature_event(
                event_type=ACCOUNT_SIGNED_UP,
                account_id=account_id,
                cohort_tag=None,
                payload={"email": email, "via": "oauth_google"},
            )
    except Exception:
        # emit_feature_event is documented as never-raising, but
        # belt-and-braces here.
        log.exception("oauth google: feature_event emit failed (non-fatal)")

    # 5. Mint our first-class JWT. Phase J JTI revocation +
    #    idle-logoff apply uniformly.
    access = create_access_token(account_id, email)
    refresh = create_refresh_token(account_id)
    set_auth_cookies(response, access, refresh)

    return {
        "ok":           True,
        "token":        access,             # frontend stores in localStorage too
        "account_id":   account_id,
        "email":        email,
        "is_new":       is_new,
        "next_url":     next_url,
        "provider":     "google",
    }


async def _fetch_emergent_session_data(session_id: str) -> Dict[str, Any]:
    """Call Emergent Auth's session-data endpoint.

    Returns the user profile dict on success. Raises HTTPException on
    any failure path (invalid id, network error, malformed response).
    """
    headers = {"X-Session-ID": session_id, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(EMERGENT_SESSION_DATA_URL, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("oauth google: emergent session-data network error: %s", exc)
        raise HTTPException(status_code=502, detail={
            "error": "oauth_provider_unreachable",
            "message": "Could not reach the OAuth identity provider.",
        }) from exc

    if res.status_code != 200:
        log.info("oauth google: emergent session-data returned %d", res.status_code)
        raise HTTPException(status_code=400, detail={
            "error": "oauth_session_invalid",
            "message": "OAuth session expired or was already consumed.",
            "provider_status": res.status_code,
        })

    try:
        return res.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={
            "error": "oauth_provider_malformed",
            "message": "OAuth provider returned a malformed response.",
        }) from exc


# ─────────────────────────────────────────────────────────────────────
# Microsoft — 503 mock until creds arrive
# ─────────────────────────────────────────────────────────────────────
MICROSOFT_CLIENT_ID_VAR = "MICROSOFT_OAUTH_CLIENT_ID"
MICROSOFT_CLIENT_SECRET_VAR = "MICROSOFT_OAUTH_CLIENT_SECRET"


def _microsoft_configured() -> bool:
    return bool(os.environ.get(MICROSOFT_CLIENT_ID_VAR)) and bool(
        os.environ.get(MICROSOFT_CLIENT_SECRET_VAR)
    )


@router.get("/microsoft/start")
async def oauth_microsoft_start() -> Dict[str, Any]:
    """Locked 503 mock — surfaces a clear actionable message to the
    frontend until Microsoft Graph credentials arrive in backend/.env.

    The exact response payload is institutionally locked (Phase U
    dispatch spec): `{"error": "microsoft_oauth_not_configured",
    "needs": "user-provided Application ID + Client Secret"}`. Future
    Phase U.2 implementation will replace this body with a real
    Microsoft Identity authorize URL.
    """
    if not _microsoft_configured():
        raise HTTPException(status_code=503, detail={
            "error": "microsoft_oauth_not_configured",
            "needs": "user-provided Application ID + Client Secret",
            "env_vars_required": [
                MICROSOFT_CLIENT_ID_VAR,
                MICROSOFT_CLIENT_SECRET_VAR,
            ],
        })
    # Future: real Microsoft Identity authorize URL.
    raise HTTPException(status_code=501, detail={
        "error": "microsoft_oauth_not_yet_implemented",
        "message": "Microsoft credentials are present but Phase U.2 has not shipped.",
    })


@router.post("/microsoft/finish")
async def oauth_microsoft_finish(body: FinishIn) -> Dict[str, Any]:
    # Same gate — let frontend's button-disabled state catch this
    # first, but defence in depth on the backend.
    if not _microsoft_configured():
        raise HTTPException(status_code=503, detail={
            "error": "microsoft_oauth_not_configured",
            "needs": "user-provided Application ID + Client Secret",
        })
    raise HTTPException(status_code=501, detail={
        "error": "microsoft_oauth_not_yet_implemented",
    })
