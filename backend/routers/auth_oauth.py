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
    # Phase P5.3 (2026-02) — when set, the Google OAuth finish consumes
    # the cohort magic link before issuing the session. Frontend passes
    # this through from /welcome/{token}'s "Continue with Google" CTA.
    magic_link_token: Optional[str] = Field(default=None, max_length=400)


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
    existing = await db.accounts.find_one({"email_lc": email}, {"_id": 0})
    if not existing:
        # Fallback for accounts created before the email_lc invariant.
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
            "email_lc":        email,
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

    # P0-C (2026-02) — Refresh `last_activity_at` on the account doc.
    # Mirrors the password-login fix at `routers/auth.py:126-135`
    # (Phase P5.5). Without this, the FIRST authenticated API call
    # after a Google OAuth finish trips SessionTimeoutMiddleware's
    # idle check against a stale `last_activity_at` from a prior
    # session, returning 401 `session_idle_timeout` even though the
    # session was just minted — surfacing as the user-visible "Re-enter
    # your password to keep this session active" toast and a forced
    # password modal that an OAuth-only user has no password for.
    await db.accounts.update_one(
        {"id": account_id},
        {"$set": {"last_activity_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Phase P5.3 (2026-02) — consume the cohort magic link if supplied.
    # If invalid/expired/consumed, fail the OAuth finish rather than
    # silently signing the user in via a non-cohort path.
    mlt = (body.magic_link_token or "").strip()
    magic_link_consumed = False
    if mlt:
        from routers.cohort_magic_link import _find_link_record
        row = await _find_link_record(mlt)
        if not row:
            raise HTTPException(status_code=410, detail={
                "code":    "magic_link_invalid_or_consumed",
                "message": "This invite link is no longer valid.",
            })
        await db.cohort_magic_links.update_one(
            {"id": row["id"]},
            {"$set": {
                "consumed_at":         _iso(_now()),
                "consumed_by_user_id": account_id,
            }},
        )
        await db.cohort_applications.update_one(
            {"id": row["application_id"]},
            {"$set": {
                "status":     "approved_redeemed",
                "redeemed_at": _iso(_now()),
                "redeemed_by": account_id,
            }},
        )
        await db.accounts.update_one(
            {"id": account_id},
            {"$set": {"cohort_application_id": row["application_id"]}},
        )
        magic_link_consumed = True

    return {
        "ok":           True,
        "token":        access,             # frontend stores in localStorage too
        "account_id":   account_id,
        "email":        email,
        "is_new":       is_new,
        "next_url":     next_url,
        "provider":     "google",
        "magic_link_consumed": magic_link_consumed,
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
# Microsoft Identity Platform — Phase U.2 (2026-02 dispatch 20)
#
# Direct OAuth flow (Microsoft is not behind Emergent Managed Auth).
# Mirrors the URL-building, state-validation, and code-exchange pattern
# from `oauth_google.py` (Calendar OAuth), adapted to the v2.0 multi-
# tenant Microsoft Identity Platform.
#
# Endpoints:
#   GET /api/auth/oauth/microsoft/start    → {authorize_url}
#   GET /api/auth/oauth/microsoft/callback → 302 → /app/
#
# Scopes: openid profile email User.Read offline_access
# Multi-tenant: uses /common/oauth2/v2.0/{authorize,token}
# Audit logs: microsoft_oauth_login_initiated | _success | _failure
#   — log session/state/error codes; NEVER log secret or raw tokens.
# ─────────────────────────────────────────────────────────────────────
MICROSOFT_CLIENT_ID_VAR = "MICROSOFT_OAUTH_CLIENT_ID"
MICROSOFT_CLIENT_SECRET_VAR = "MICROSOFT_OAUTH_CLIENT_SECRET"
MICROSOFT_REDIRECT_URI_VAR = "MICROSOFT_OAUTH_REDIRECT_URI"
MICROSOFT_POST_LOGIN_REDIRECT_VAR = "MICROSOFT_OAUTH_POST_LOGIN_REDIRECT"

_MS_AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_MS_SCOPES = ["openid", "profile", "email", "User.Read", "offline_access"]
_MS_STATE_TTL_SECONDS = 10 * 60


def _microsoft_configured() -> bool:
    return bool(os.environ.get(MICROSOFT_CLIENT_ID_VAR)) and bool(
        os.environ.get(MICROSOFT_CLIENT_SECRET_VAR)
    )


def _ms_client_id() -> str:
    v = (os.environ.get(MICROSOFT_CLIENT_ID_VAR) or "").strip()
    if not v:
        raise HTTPException(status_code=503, detail={
            "error": "microsoft_oauth_not_configured",
            "needs": "user-provided Application ID + Client Secret",
            "env_vars_required": [MICROSOFT_CLIENT_ID_VAR, MICROSOFT_CLIENT_SECRET_VAR],
        })
    return v


def _ms_client_secret() -> str:
    v = (os.environ.get(MICROSOFT_CLIENT_SECRET_VAR) or "").strip()
    if not v:
        raise HTTPException(status_code=503, detail={
            "error": "microsoft_oauth_not_configured",
        })
    return v


def _ms_redirect_uri() -> str:
    v = (os.environ.get(MICROSOFT_REDIRECT_URI_VAR) or "").strip()
    if not v:
        raise HTTPException(status_code=503, detail={
            "error": "microsoft_oauth_redirect_uri_missing",
            "needs": "MICROSOFT_OAUTH_REDIRECT_URI in backend/.env",
        })
    return v


def _ms_post_login_redirect() -> str:
    return (os.environ.get(MICROSOFT_POST_LOGIN_REDIRECT_VAR) or "/app/").strip()


def _ms_sign_state(payload: Dict[str, Any]) -> str:
    """JWT-sign the OAuth state. Reuses the app-wide JWT_SECRET so the
    same revocation story applies."""
    import jwt
    from core import JWT_SECRET
    body = {**payload, "exp": int(_now().timestamp()) + _MS_STATE_TTL_SECONDS}
    return jwt.encode(body, JWT_SECRET, algorithm="HS256")


def _ms_verify_state(token: str) -> Dict[str, Any]:
    import jwt
    from core import JWT_SECRET
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={
            "error": "microsoft_oauth_state_invalid",
            "reason": str(e)[:120],
        }) from e


# Phase P2 A.2 (2026-02) — PKCE (RFC 7636) for Microsoft OAuth.
# We generate a high-entropy `code_verifier` per /start, derive the
# S256 challenge that goes on the authorize URL, and persist the
# verifier in Mongo keyed by the state JWT's `sid` claim. On
# /callback we look it up and send it to the token endpoint.
def _ms_pkce_verifier() -> str:
    """RFC 7636 §4.1 — 43-128 char unreserved-set string. 64 bytes of
    randomness, base64url-encoded, no padding."""
    import secrets, base64
    return base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")


def _ms_pkce_challenge(verifier: str) -> str:
    """RFC 7636 §4.2 — S256 challenge = base64url(sha256(verifier))."""
    import hashlib, base64
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def _ms_pkce_store(sid: str, verifier: str) -> None:
    """Persist the verifier so /callback can retrieve it. TTL matches
    the state JWT (10 min). Uses Mongo `oauth_pkce_verifiers` with a
    TTL index on `expires_at` (created on first write below)."""
    from server import db
    expires = int(_now().timestamp()) + _MS_STATE_TTL_SECONDS
    await db.oauth_pkce_verifiers.update_one(
        {"sid": sid, "provider": "microsoft"},
        {"$set": {
            "sid": sid, "provider": "microsoft",
            "code_verifier": verifier,
            "expires_at": expires,
        }},
        upsert=True,
    )


async def _ms_pkce_consume(sid: str) -> Optional[str]:
    """One-shot fetch + delete the verifier. Returns None if the state
    has already been consumed (replay protection) or has expired."""
    from server import db
    rec = await db.oauth_pkce_verifiers.find_one_and_delete(
        {"sid": sid, "provider": "microsoft"},
    )
    if not rec:
        return None
    if int(rec.get("expires_at", 0)) < int(_now().timestamp()):
        return None
    return rec.get("code_verifier")


def _ms_audit(action: str, **fields: Any) -> None:
    """Log a Microsoft OAuth audit event. Caller MUST NOT pass the
    secret or raw tokens — only stable IDs + error codes."""
    sanitised = {k: v for k, v in fields.items() if k not in {
        "secret", "client_secret", "access_token", "id_token", "refresh_token",
    }}
    log.info("microsoft_oauth_%s: %s", action, sanitised)


@router.get("/microsoft/start")
async def oauth_microsoft_start(
    request: Request,
    magic_link_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Stage-1: returns the Microsoft authorize URL. Frontend redirects
    the browser there; Microsoft bounces back to /microsoft/callback.

    Probe mode: pass `?probe=1` to avoid burning a state token + audit
    entry on a configuration check. Returns just `{configured: true}`
    when the provider is wired.

    Phase P5.3 (2026-02) — `magic_link_token` is packed into the state
    JWT as the `mlt` claim. On the /microsoft/callback round-trip the
    state-verified `mlt` drives the cohort magic-link consume so the
    OAuth sign-in counts as a single-use redemption of the same
    invite the applicant received in their approval email."""
    if not _microsoft_configured():
        raise HTTPException(status_code=503, detail={
            "error": "microsoft_oauth_not_configured",
            "needs": "user-provided Application ID + Client Secret",
            "env_vars_required": [
                MICROSOFT_CLIENT_ID_VAR, MICROSOFT_CLIENT_SECRET_VAR,
            ],
        })
    # Probe mode — frontend availability check; no PKCE/state burn.
    if request.query_params.get("probe") == "1":
        return {"configured": True, "provider": "microsoft"}
    session_id = uuid.uuid4().hex
    state_claims: Dict[str, Any] = {"sid": session_id, "kind": "ms_signin"}
    mlt = (magic_link_token or "").strip()
    if mlt:
        # Cap the length defensively — the token is base64url(32 bytes)
        # so ~43 chars; reject anything pathological that would inflate
        # the state JWT or pass through to a downstream lookup.
        if len(mlt) > 200:
            raise HTTPException(status_code=400, detail={
                "error": "magic_link_token_too_long",
            })
        state_claims["mlt"] = mlt
    state = _ms_sign_state(state_claims)
    nonce = uuid.uuid4().hex
    # Phase P2 A.2 — PKCE: derive a fresh verifier + S256 challenge and
    # persist the verifier keyed by sid for the /callback round trip.
    code_verifier = _ms_pkce_verifier()
    code_challenge = _ms_pkce_challenge(code_verifier)
    await _ms_pkce_store(session_id, code_verifier)
    from urllib.parse import urlencode
    qs = urlencode({
        "client_id": _ms_client_id(),
        "response_type": "code",
        "redirect_uri": _ms_redirect_uri(),
        "response_mode": "query",
        "scope": " ".join(_MS_SCOPES),
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    authorize_url = f"{_MS_AUTHORIZE_URL}?{qs}"
    _ms_audit("login_initiated", session_id=session_id, client_id=_ms_client_id(), pkce="S256")
    return {
        "authorize_url": authorize_url,
        "provider": "microsoft",
    }


async def _ms_exchange_code(code: str, code_verifier: Optional[str] = None) -> Dict[str, Any]:
    """Exchange auth code for tokens at the Microsoft v2.0 token endpoint.

    Phase P2 A.2 — PKCE: when a `code_verifier` is supplied, it is sent
    alongside the code (RFC 7636). Microsoft requires this when the
    `/authorize` request included a `code_challenge`.
    """
    payload = {
        "client_id": _ms_client_id(),
        "client_secret": _ms_client_secret(),
        "code": code,
        "redirect_uri": _ms_redirect_uri(),
        "grant_type": "authorization_code",
        "scope": " ".join(_MS_SCOPES),
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_MS_TOKEN_URL, data=payload)
    if r.status_code != 200:
        body_preview = r.text[:200]
        raise HTTPException(status_code=502, detail={
            "error": "microsoft_token_exchange_failed",
            "provider_status": r.status_code,
            "provider_body_preview": body_preview,
        })
    return r.json()


def _ms_decode_id_token(id_token: str) -> Dict[str, Any]:
    """Validate the ID-token signature against Microsoft JWKS + decode claims.

    Multi-tenant tolerance: the issuer is `https://login.microsoftonline.com/{tid}/v2.0`
    where `{tid}` varies per tenant. We accept any tenant (consistent
    with the `/common` authorize endpoint) but enforce signature + aud +
    expiry validation."""
    import jwt
    from jwt import PyJWKClient
    try:
        jwk_client = PyJWKClient(_MS_JWKS_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(
            id_token, signing_key, algorithms=["RS256"],
            audience=_ms_client_id(),
            options={"verify_iss": False},  # multi-tenant — issuer varies
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail={
            "error": "microsoft_id_token_invalid",
            "reason": str(e)[:160],
        }) from e
    iss = claims.get("iss") or ""
    if not iss.startswith("https://login.microsoftonline.com/"):
        raise HTTPException(status_code=400, detail={
            "error": "microsoft_id_token_issuer_invalid",
            "iss": iss[:120],
        })
    return claims


@router.get("/microsoft/callback")
async def oauth_microsoft_callback(
    response: Response,
    code: Optional[str] = None, state: Optional[str] = None,
    error: Optional[str] = None, error_description: Optional[str] = None,
):
    """Stage-2: Microsoft redirected back with `code` + `state`. Exchange
    the code, validate the ID token, upsert the account, mint JWT, set
    cookies, redirect to the post-login landing."""
    from fastapi.responses import RedirectResponse
    if error:
        _ms_audit("login_failure", error=error, error_description=(error_description or "")[:160])
        return RedirectResponse(url=f"/sign-in?oauth_error={error}", status_code=302)
    if not code or not state:
        _ms_audit("login_failure", error="missing_code_or_state")
        raise HTTPException(status_code=400, detail={
            "error": "microsoft_oauth_missing_code_or_state",
        })
    state_payload = _ms_verify_state(state)
    session_id = state_payload.get("sid") or "unknown"
    if not _microsoft_configured():
        raise HTTPException(status_code=503, detail={"error": "microsoft_oauth_not_configured"})
    # Phase P2 A.2 — PKCE: consume the verifier stored at /start.
    code_verifier = await _ms_pkce_consume(session_id)
    if not code_verifier:
        _ms_audit("login_failure", session_id=session_id, error="pkce_verifier_missing_or_expired")
        raise HTTPException(status_code=400, detail={
            "error": "microsoft_oauth_pkce_state_invalid",
            "reason": "code_verifier missing or expired (replay or >10min round trip)",
        })
    try:
        tokens = await _ms_exchange_code(code, code_verifier=code_verifier)
    except HTTPException as e:
        _ms_audit("login_failure", session_id=session_id,
                  error=(e.detail or {}).get("error", "token_exchange_failed"))
        raise

    id_token = tokens.get("id_token") or ""
    if not id_token:
        _ms_audit("login_failure", session_id=session_id, error="no_id_token")
        raise HTTPException(status_code=502, detail={"error": "microsoft_no_id_token"})

    claims = _ms_decode_id_token(id_token)
    email = (claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    name = (claims.get("name") or "").strip()
    oid = (claims.get("oid") or "").strip()
    tid = (claims.get("tid") or "").strip()
    if not email or "@" not in email:
        _ms_audit("login_failure", session_id=session_id, error="email_missing", oid=oid, tid=tid)
        raise HTTPException(status_code=400, detail={
            "error": "oauth_email_missing",
            "message": "Microsoft did not return an email/UPN.",
        })

    # Find-or-create account — same pattern as the Google sign-in finish path.
    existing = await db.accounts.find_one({"email_lc": email}, {"_id": 0})
    if not existing:
        existing = await db.accounts.find_one({"email": email}, {"_id": 0})
    is_new = existing is None
    trial_start = _now()
    trial_end = trial_start + timedelta(days=TRIAL_LENGTH_DAYS)
    if existing:
        account_id = existing["id"]
        update_fields: Dict[str, Any] = {"last_login_at": _iso(trial_start)}
        providers_used = list(existing.get("oauth_providers") or [])
        if "microsoft" not in providers_used:
            providers_used.append("microsoft")
            update_fields["oauth_providers"] = providers_used
        if not existing.get("auth_provider") and not existing.get("password_hash"):
            update_fields["auth_provider"] = "microsoft"
        if not existing.get("name") and name:
            update_fields["name"] = name
        if not existing.get("first_name") and name:
            update_fields["first_name"] = name.split()[0]
        if oid and not existing.get("microsoft_oid"):
            update_fields["microsoft_oid"] = oid
        await db.accounts.update_one({"id": account_id}, {"$set": update_fields})
        next_url = _ms_post_login_redirect()
    else:
        account_id = uuid.uuid4().hex
        first_name = (name.split()[0] if name else email.split("@")[0])
        await db.accounts.insert_one({
            "id":              account_id,
            "email":           email,
            "email_lc":        email,
            "password_hash":   None,
            "auth_provider":   "microsoft",
            "oauth_providers": ["microsoft"],
            "microsoft_oid":   oid or None,
            "name":            name or email.split("@")[0],
            "first_name":      first_name,
            "picture":         None,
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

    try:
        from services.cohort.feature_events import emit_feature_event, ACCOUNT_SIGNED_UP
        if is_new:
            await emit_feature_event(
                event_type=ACCOUNT_SIGNED_UP, account_id=account_id, cohort_tag=None,
                payload={"email": email, "via": "oauth_microsoft", "tid": tid},
            )
    except Exception:
        log.exception("oauth microsoft: feature_event emit failed (non-fatal)")

    access = create_access_token(account_id, email)
    refresh = create_refresh_token(account_id)
    redirect_resp = RedirectResponse(url=next_url, status_code=302)
    set_auth_cookies(redirect_resp, access, refresh)

    # P0-C (2026-02) — Refresh `last_activity_at`. See the matching
    # comment on the Google finish handler above. Same trap, same
    # fix — without this, the Microsoft OAuth callback redirects to
    # /app and the very next authenticated API call returns 401
    # `session_idle_timeout` against the stale-from-prior-session
    # `last_activity_at`, triggering the re-auth modal.
    await db.accounts.update_one(
        {"id": account_id},
        {"$set": {"last_activity_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Phase P5.3 (2026-02) — cohort magic-link consume.
    # When the OAuth start packed `mlt` (magic_link_token) into the
    # state JWT, complete the cohort consume here before returning the
    # session. If the token is invalid/expired/already-consumed we
    # FAIL the callback rather than silently signing the user in —
    # the cohort gate must hold.
    mlt = (state_payload.get("mlt") or "").strip()
    if mlt:
        try:
            from routers.cohort_magic_link import _find_link_record
            row = await _find_link_record(mlt)
            if not row:
                _ms_audit("login_failure", session_id=session_id, error="magic_link_invalid_or_consumed")
                return RedirectResponse(
                    url="/welcome/" + mlt + "?oauth_error=consumed",
                    status_code=302,
                )
            # Mark consumed + link the account to the application.
            await db.cohort_magic_links.update_one(
                {"id": row["id"]},
                {"$set": {
                    "consumed_at":         _iso(_now()),
                    "consumed_by_user_id": account_id,
                }},
            )
            await db.cohort_applications.update_one(
                {"id": row["application_id"]},
                {"$set": {
                    "status":     "approved_redeemed",
                    "redeemed_at": _iso(_now()),
                    "redeemed_by": account_id,
                }},
            )
            await db.accounts.update_one(
                {"id": account_id},
                {"$set": {"cohort_application_id": row["application_id"]}},
            )
            _ms_audit("magic_link_consumed", session_id=session_id,
                      account_id=account_id, application_id=row["application_id"])
        except Exception as _mlt_err:  # noqa: BLE001
            log.warning("oauth microsoft: magic-link consume failed err=%s", str(_mlt_err)[:200])
            _ms_audit("login_failure", session_id=session_id, error="magic_link_consume_error")

    _ms_audit(
        "login_success",
        session_id=session_id, account_id=account_id,
        oid=oid, tid=tid, is_new=is_new,
    )
    return redirect_resp


@router.post("/microsoft/finish")
async def oauth_microsoft_finish(body: FinishIn) -> Dict[str, Any]:
    """Legacy POST endpoint — kept for parity with the Google /finish
    pattern. Phase U.2 uses the GET /microsoft/callback redirect flow
    instead (Microsoft Identity Platform native), so this returns 410
    pointing callers at the canonical entry point."""
    raise HTTPException(status_code=410, detail={
        "error": "microsoft_oauth_use_callback_redirect",
        "message": "Phase U.2 uses GET /microsoft/callback. Initiate via /microsoft/start.",
    })
