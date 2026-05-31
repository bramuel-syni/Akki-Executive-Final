"""Phase P3.1 (2026-02) — CSRF protection (double-submit cookie + HMAC).

Strategy: double-submit cookie with HMAC-signed token.

  1. `GET /api/csrf` mints a token = `<random_nonce>.<hmac_sha256(secret, nonce)>`,
     sets it as a non-HttpOnly cookie `csrf_token` (SameSite=Lax,
     Secure=true on HTTPS). The frontend axios wrapper reads the
     cookie and sends the value back as the `X-CSRF-Token` header on
     every state-changing request.

  2. The middleware below intercepts every POST/PUT/PATCH/DELETE and:
     - lets allowlisted paths through (webhook receivers + the CSRF
       mint endpoint itself);
     - rejects 403 `csrf_token_missing` when either cookie or header
       is absent;
     - rejects 403 `csrf_token_invalid` when they don't match or the
       HMAC doesn't verify.

  3. SameSite=Lax on the CSRF cookie + HMAC verification mean a
     cross-origin attacker can neither read the cookie (Same-Origin
     Policy) nor forge a valid HMAC, and a same-origin attacker would
     have already broken the browser sandbox.

Test bypass: set `CSRF_TEST_BYPASS_HEADER=1` env to allow requests
that carry `X-CSRF-Test-Bypass: 1` to skip enforcement. Used by the
existing pytest suite — fork agents and CI runners that don't drive
the full SPA otherwise can't easily mint cookies. Production never
sets this env.
"""
from __future__ import annotations

import hmac
import hashlib
import logging
import os
import secrets
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


log = logging.getLogger(__name__)


CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TEST_BYPASS_HEADER = "X-CSRF-Test-Bypass"
CSRF_TOKEN_TTL_SECONDS = 24 * 3600  # 24 hours; refreshed by frontend on demand


# Endpoints exempt from CSRF (webhooks + OAuth callbacks + the mint
# endpoint itself). Match by exact path prefix.
_ALLOWLIST_PREFIXES = (
    "/api/csrf",
    "/api/billing/webhook/",           # Stripe webhooks (HMAC-signed by Stripe)
    "/api/auth/oauth/google/callback", # OAuth callbacks: state-param protected
    "/api/auth/oauth/microsoft/callback",
    # Phase P5.8.1 (2026-02) — SendGrid Inbound Parse webhook. Cannot
    # carry a CSRF token because it's an unattended POST from
    # SendGrid's edge. The endpoint itself is gated by Basic Auth
    # (`SENDGRID_INBOUND_AUTH_USERNAME` + `_PASSWORD`).
    "/api/inbound/sendgrid",
    # Phase P5.7.5 (2026-02) — SendGrid Event Webhook (delivery /
    # bounce / spam-report events). Cannot carry CSRF either; gated
    # by SendGrid's signed-event-webhook ECDSA signature when the
    # `SENDGRID_WEBHOOK_PUBLIC_KEY` env is set.
    "/api/cohort/email-events/sendgrid",
)


def _secret() -> bytes:
    """The CSRF HMAC secret — reuses the existing JWT secret so we
    don't introduce a new operator-managed key. If JWT_SECRET ever
    rotates, existing CSRF tokens become invalid (expected)."""
    from core import JWT_SECRET
    return JWT_SECRET.encode("utf-8")


def mint_csrf_token() -> str:
    """Return `<nonce>.<hmac>`. The nonce is 16 random bytes urlsafe
    base64-encoded; the hmac is the HMAC-SHA256 over `<nonce>.<issued_at>`
    keyed by the CSRF secret. The issued_at is encoded into the nonce
    portion so we can age the token off."""
    import base64
    nonce = secrets.token_urlsafe(16)
    issued_at = str(int(time.time()))
    body = f"{nonce}.{issued_at}"
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{body}.{sig_b64}"


def verify_csrf_token(token: str) -> bool:
    """Constant-time HMAC verification + age check."""
    if not token:
        return False
    try:
        nonce, issued_at_s, sig_b64 = token.split(".", 2)
        issued_at = int(issued_at_s)
        if (time.time() - issued_at) > CSRF_TOKEN_TTL_SECONDS:
            return False
        if (time.time() - issued_at) < -60:  # clock skew tolerance
            return False
        body = f"{nonce}.{issued_at_s}"
        import base64
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
        # Re-encode the provided sig and compare.
        provided = base64.urlsafe_b64decode(sig_b64 + "=" * (4 - len(sig_b64) % 4))
        return hmac.compare_digest(expected, provided)
    except Exception:  # noqa: BLE001
        return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """Enforce double-submit-cookie CSRF on every state-changing route
    that isn't in the allowlist."""

    NON_IDEMPOTENT = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in self.NON_IDEMPOTENT:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _ALLOWLIST_PREFIXES):
            return await call_next(request)

        # Test bypass — only honoured when the env switch is set.
        if os.environ.get("CSRF_TEST_BYPASS_HEADER", "0").strip() == "1":
            if request.headers.get(CSRF_TEST_BYPASS_HEADER, "").strip() == "1":
                return await call_next(request)

        # Disable escape hatch (incident response).
        if os.environ.get("CSRF_DISABLED", "0").strip() == "1":
            return await call_next(request)

        cookie_val = request.cookies.get(CSRF_COOKIE_NAME, "").strip()
        header_val = request.headers.get(CSRF_HEADER_NAME, "").strip()

        if not cookie_val or not header_val:
            return JSONResponse(
                status_code=403,
                content={"detail": {
                    "code": "csrf_token_missing",
                    "message": "CSRF token missing. Reload the page and retry.",
                }},
            )

        if not hmac.compare_digest(cookie_val, header_val):
            return JSONResponse(
                status_code=403,
                content={"detail": {
                    "code": "csrf_token_invalid",
                    "message": "CSRF token mismatch. Reload the page and retry.",
                }},
            )

        if not verify_csrf_token(cookie_val):
            return JSONResponse(
                status_code=403,
                content={"detail": {
                    "code": "csrf_token_invalid",
                    "message": "CSRF token invalid or expired. Reload the page and retry.",
                }},
            )

        return await call_next(request)


def set_csrf_cookie(response: Response, token: str, *, secure: bool = True) -> None:
    """Stamp the CSRF cookie. Lax SameSite so the cookie rides on
    same-site navigations (top-level GET) which is what the double-
    submit pattern needs."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,       # frontend JS reads it
        secure=secure,
        samesite="lax",
        max_age=CSRF_TOKEN_TTL_SECONDS,
        path="/",
    )
