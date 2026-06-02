"""C1-revised Phase A (2026-02) — First-login password-set gate.

Enforces that any account explicitly marked `has_set_password: False`
must set a password before they can perform state-changing API calls.
The gate is bypassed for legacy accounts where the field is missing,
null, or true — only the strict-bool `False` triggers it.

Design parity with `services/session_timeout.py`:
  • Same JWT extraction shape (`Authorization: Bearer` OR
    `access_token` cookie).
  • Bypass list is path-prefix based.
  • GET / HEAD / OPTIONS pass through — the gate only intervenes on
    POST / PUT / PATCH / DELETE so a gated user can navigate read-only
    surfaces while resolving the gate.
  • Returns 428 (Precondition Required) with a structured body
    `{detail: {code: "password_set_required", message: "…",
              set_password_url: "/auth/set-password"}}` so the SPA can
    redirect.

Why a middleware instead of a per-route dependency?
  • Per-route would mean touching every state-changing endpoint in
    the codebase — at ~80 routers, that's both an audit burden and
    impossible to keep in sync. Centralising the check matches how
    `SessionTimeoutMiddleware` and `CSRFMiddleware` already work and
    gives a single source of truth.

Toggle: `FIRST_LOGIN_PASSWORD_GATE_DISABLED=1` to disable entirely
(incident response — matches the escape-hatch shape of CSRF and
SessionTimeout).
"""
from __future__ import annotations

import logging
import os
from typing import Callable

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


log = logging.getLogger(__name__)


# Path PREFIXES that are exempt from the gate. The auth-entry/exit
# routes MUST be reachable so a gated user can:
#   • re-authenticate (login, refresh, logout)
#   • mint CSRF
#   • exchange a magic-link / OAuth code
#   • set a password via the new endpoint
#   • reset a forgotten password (the existing flow is separate; it
#     ends in a fully-set password so the gate naturally drops).
_BYPASS_PREFIXES: tuple[str, ...] = (
    "/api/csrf",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/register",
    "/api/auth/me",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/set-password",
    "/api/auth/magic",
    "/api/auth/magic-link",
    "/api/auth/oauth",
)


class FirstLoginPasswordSetGateMiddleware(BaseHTTPMiddleware):
    """Block state-changing routes for accounts with
    `has_set_password === False`."""

    NON_IDEMPOTENT = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if os.environ.get("FIRST_LOGIN_PASSWORD_GATE_DISABLED", "0").strip() == "1":
            return await call_next(request)

        if request.method not in self.NON_IDEMPOTENT:
            return await call_next(request)

        path = request.url.path or ""
        for prefix in _BYPASS_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        token = self._extract(request)
        if not token:
            return await call_next(request)

        from core import JWT_SECRET, JWT_ALGO, db
        try:
            claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        except Exception:  # noqa: BLE001
            return await call_next(request)

        sub = claims.get("sub")
        if not sub:
            return await call_next(request)

        acc = await db.accounts.find_one(
            {"id": sub},
            {"_id": 0, "has_set_password": 1},
        )
        if not acc:
            return await call_next(request)

        # Legacy bypass — only strict-bool `False` triggers the gate.
        # null, missing, or True all pass through.
        if acc.get("has_set_password", None) is False:
            return JSONResponse(
                status_code=428,
                content={"detail": {
                    "code":             "password_set_required",
                    "message":          "Set a password to continue.",
                    "set_password_url": "/auth/set-password",
                }},
            )

        return await call_next(request)

    @staticmethod
    def _extract(request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip() or None
        return request.cookies.get("access_token") or None
