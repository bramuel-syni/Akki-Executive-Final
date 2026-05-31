"""Phase P3.4 (2026-02) — Absolute + idle session timeout.

Two limits:

  - Absolute: 12 hours from token issuance (`iat` claim). After this,
    even silent refresh is refused; the user must re-auth fully.
  - Idle: 30 minutes since the last authenticated API call. After this,
    re-auth-with-password is required; the existing session stays
    alive but is marked `mfa_verified=false` + `password_reauthed=false`
    on the JWT until the user re-enters their password.

Activity tracking: every authenticated request (any route that goes
through `get_current_account`) records `last_activity_at` on the
account doc. The middleware below performs the boundary check and
emits a synthetic 401 with a structured error code when expired.

Silent refresh: a JWT issued >1h ago and used within the idle window
is silently re-signed with a fresh `exp` by the middleware, capped at
12h from the ORIGINAL `iat`. The refresh writes the new cookie + emits
an `X-Token-Refreshed: 1` header so the frontend axios wrapper picks
up the new token.

Tunables (env):
  - `SESSION_ABSOLUTE_HOURS` (default 12)
  - `SESSION_IDLE_MINUTES` (default 30)
  - `SESSION_SILENT_REFRESH_HOURS` (default 1)
  - `SESSION_TIMEOUT_DISABLED=1` → bypass entirely (incident response)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


log = logging.getLogger(__name__)


def _hours(env: str, default: int) -> int:
    try:
        return int(os.environ.get(env, str(default)))
    except (TypeError, ValueError):
        return default


def _minutes(env: str, default: int) -> int:
    try:
        return int(os.environ.get(env, str(default)))
    except (TypeError, ValueError):
        return default


ABSOLUTE_HOURS = _hours("SESSION_ABSOLUTE_HOURS", 12)
IDLE_MINUTES = _minutes("SESSION_IDLE_MINUTES", 30)
SILENT_REFRESH_HOURS = _hours("SESSION_SILENT_REFRESH_HOURS", 1)


# Phase P5.5 (2026-02) — auth entry/exit routes that MUST be reachable
# regardless of session-timeout state. These are the routes that
# establish, refresh, or close a session; gating them on the idle
# timer creates an unrecoverable trap where the re-auth modal posts
# /auth/login, the middleware rejects with session_idle_timeout
# (because last_activity_at is already past the idle window — that's
# the whole reason the modal opened), and the user cannot reach the
# very endpoint meant to refresh their session.
#
# Each entry is a path PREFIX matched against `request.url.path`.
# The signed-out paths /forgot and /reset don't carry a session and
# are listed for symmetry/clarity; the middleware bails on
# token-less requests anyway.
SESSION_TIMEOUT_BYPASS_PREFIXES: tuple[str, ...] = (
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/csrf",
)


class SessionTimeoutMiddleware(BaseHTTPMiddleware):
    """Enforce absolute + idle session timeouts. Only applies to
    requests that carry an `access_token` (cookie or Bearer) — public
    endpoints are unaffected."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if os.environ.get("SESSION_TIMEOUT_DISABLED", "0").strip() == "1":
            return await call_next(request)

        # Phase P5.5 — auth entry/exit routes bypass the timeout check.
        # See SESSION_TIMEOUT_BYPASS_PREFIXES above for rationale.
        path = request.url.path or ""
        for prefix in SESSION_TIMEOUT_BYPASS_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Extract token without throwing — public routes have no token.
        token = self._extract(request)
        if not token:
            return await call_next(request)

        from core import JWT_SECRET, JWT_ALGO, db
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        except Exception:  # noqa: BLE001
            # Let the downstream auth dependency surface the 401.
            return await call_next(request)

        iat = int(claims.get("iat", 0) or 0)
        exp = int(claims.get("exp", 0) or 0)
        if iat <= 0 or exp <= 0:
            return await call_next(request)

        now_ts = int(time.time())

        # Absolute timeout — issued more than ABSOLUTE_HOURS ago.
        if (now_ts - iat) > (ABSOLUTE_HOURS * 3600):
            return JSONResponse(
                status_code=401,
                content={"detail": {
                    "code": "session_absolute_timeout",
                    "message": "Session has reached its 12-hour limit. Sign in again.",
                }},
            )

        # Idle timeout — last_activity_at on the account.
        sub = claims.get("sub")
        last_seen = None
        if sub:
            acc = await db.accounts.find_one({"id": sub}, {"last_activity_at": 1, "_id": 0})
            if acc and acc.get("last_activity_at"):
                try:
                    ts = datetime.fromisoformat(acc["last_activity_at"])
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    last_seen = int(ts.timestamp())
                except Exception:  # noqa: BLE001
                    last_seen = None

        if last_seen is not None and (now_ts - last_seen) > (IDLE_MINUTES * 60):
            return JSONResponse(
                status_code=401,
                content={"detail": {
                    "code":    "session_idle_timeout",
                    "message": "Re-enter your password to keep this session active.",
                }},
            )

        # Touch last_activity_at — best-effort; doesn't block on Mongo errors.
        if sub:
            try:
                await db.accounts.update_one(
                    {"id": sub},
                    {"$set": {"last_activity_at": datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()}},
                )
            except Exception:  # noqa: BLE001
                log.warning("session-timeout: failed to record last_activity_at", exc_info=True)

        response = await call_next(request)

        # Silent refresh: token issued >SILENT_REFRESH_HOURS ago but
        # within absolute window — re-sign with fresh exp capped at
        # 12h from ORIGINAL iat. Only re-sign on JSON responses; HTML
        # cookies are managed by webpack-dev-server which doesn't carry
        # the API auth contract.
        token_age = now_ts - iat
        if token_age > (SILENT_REFRESH_HOURS * 3600):
            try:
                from core import create_access_token, set_auth_cookies, create_refresh_token
                # Cap remaining time to (ABSOLUTE_HOURS * 3600 - token_age).
                # If we'd push exp past the absolute boundary, don't refresh.
                remaining = (ABSOLUTE_HOURS * 3600) - token_age
                if remaining > (SILENT_REFRESH_HOURS * 3600):
                    # Issue a new access token preserving the original iat
                    # via a separate helper (defined inline).
                    new_access = _resign_with_original_iat(claims, iat)
                    # We don't rotate refresh on silent refresh.
                    response.headers["X-Token-Refreshed"] = "1"
                    # The cookie itself we re-set with the new value.
                    response.set_cookie(
                        "access_token", new_access,
                        httponly=True,
                        secure=(os.environ.get("COOKIE_SECURE", "1").strip() == "1"),
                        samesite="strict",
                        max_age=remaining, path="/",
                    )
            except Exception:  # noqa: BLE001
                log.warning("session-timeout: silent refresh failed", exc_info=True)

        return response

    @staticmethod
    def _extract(request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip() or None
        return request.cookies.get("access_token") or None


def _resign_with_original_iat(claims: dict, original_iat: int) -> str:
    """Mint a new access token preserving the original `iat` so the
    absolute-window check remains accurate."""
    from core import JWT_SECRET, JWT_ALGO
    import uuid
    new_claims = dict(claims)
    new_claims["jti"] = uuid.uuid4().hex
    new_claims["iat"] = original_iat
    new_claims["exp"] = int(time.time()) + (ABSOLUTE_HOURS * 3600) - (int(time.time()) - original_iat)
    return jwt.encode(new_claims, JWT_SECRET, algorithm=JWT_ALGO)
