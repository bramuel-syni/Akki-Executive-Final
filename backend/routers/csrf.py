"""Phase P3.1 (2026-02) — CSRF token mint endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from services.csrf import mint_csrf_token, set_csrf_cookie, CSRF_COOKIE_NAME


router = APIRouter(prefix="/api", tags=["csrf"])


@router.get("/csrf")
async def csrf(request: Request, response: Response):
    """Mint (or refresh) the per-session CSRF token. Idempotent — call
    on app boot, after sign-in, or whenever the existing cookie has
    expired. The frontend axios wrapper calls this before any
    state-changing request when its in-memory token cache is empty.

    The token is returned in the JSON body so clients without cookie
    access (mobile app builds, server-side rendering) can still pull
    it; the cookie is the primary delivery channel for browsers.
    """
    # Determine secure flag from request scheme so loopback dev gets
    # `secure=false` and the cookie still rides on HTTP.
    forwarded_proto = (
        request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    )
    is_https = request.url.scheme.lower() == "https" or forwarded_proto == "https"

    existing = request.cookies.get(CSRF_COOKIE_NAME, "").strip()
    # Re-issue every time so the token is always fresh. Cheap and
    # avoids stale-token edge cases.
    token = mint_csrf_token()
    set_csrf_cookie(response, token, secure=is_https)
    return {"csrf_token": token, "rotated": bool(existing and existing != token)}
