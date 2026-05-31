"""Phase P5.6 — Production CSRF cross-origin block regression.

The bug: production deploy was serving a SPA bundle whose API_BASE
was baked to `https://akki-executive.emergent.host/api`. When loaded
from `https://akki.syni.ai`, every API call was cross-origin. The
CSRF cookie minted via `GET /api/csrf` landed on the
`akki-executive.emergent.host` cookie jar; the subsequent
`POST /api/auth/login` was a cross-site POST so SameSite=Lax
suppressed the cookie. The backend's CSRF middleware saw no cookie
and returned 403 `csrf_token_missing` — the exact error the user
hit on sign-in.

Two backend-side invariants we lock here:

  1. The `/api/csrf` Set-Cookie must NOT pin a hardcoded `Domain`
     attribute (e.g. `Domain=.preview.emergentagent.com`). The
     cookie must be host-only so it follows the request's host —
     equally compatible with preview, production, custom domains
     and local dev.
  2. The cookie attributes are exactly the set required for the
     double-submit pattern: `Path=/`, `SameSite=Lax`, `Secure`,
     non-HttpOnly (so the SPA JS can read it for the X-CSRF-Token
     header).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _csrf_setcookie_header(scheme: str = "http") -> str:
    """Fetch the /api/csrf Set-Cookie header. Pass scheme='https' to
    drive the request-scheme conditional that controls the Secure
    flag (matches what the ingress sends in preview / production via
    x-forwarded-proto)."""
    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            headers = {}
            if scheme == "https":
                headers["x-forwarded-proto"] = "https"
            r = await ac.get("/api/csrf", headers=headers)
            assert r.status_code == 200, r.text
            return r.headers.get("set-cookie", "")
    return _run(_do())


def test_p5_6_csrf_cookie_has_no_pinned_domain():
    """Set-Cookie MUST NOT carry a `Domain=` attribute. A pinned
    domain (e.g. Domain=.preview.emergentagent.com) would prevent
    the cookie from following the request to production / custom
    domains, making the CSRF double-submit unrecoverable there."""
    header = _csrf_setcookie_header().lower()
    # Iterate every attribute; assert none is `domain=...`. (Cookie
    # values may legitimately CONTAIN the word "domain" but the
    # attribute syntax is `; domain=...`.)
    parts = [p.strip() for p in header.split(";")]
    pinned = [p for p in parts if p.startswith("domain=")]
    assert not pinned, (
        f"csrf cookie must be host-only — found pinned domain attr: {pinned}; "
        f"full header: {header}"
    )


def test_p5_6_csrf_cookie_is_double_submit_shape():
    """Cookie must be Path=/, SameSite=Lax (or stricter on local-only
    deploys), Secure (when served over HTTPS — the prod / preview
    contract), and NOT HttpOnly so the SPA can read it."""
    header = _csrf_setcookie_header(scheme="https").lower()
    parts = [p.strip() for p in header.split(";")]
    assert "path=/" in parts, f"missing Path=/: {header}"
    samesite = next((p for p in parts if p.startswith("samesite=")), None)
    assert samesite is not None, f"missing SameSite attr: {header}"
    assert samesite.split("=", 1)[1] in ("lax", "strict"), (
        f"SameSite must be Lax or Strict for double-submit: {samesite}"
    )
    # `secure` attribute (no value) — required when served over HTTPS.
    assert "secure" in parts, f"missing Secure on HTTPS request: {header}"
    # MUST be readable by JS — no HttpOnly.
    assert "httponly" not in parts, (
        f"CSRF cookie must NOT be HttpOnly (the SPA reads it to attach "
        f"the X-CSRF-Token header). Found HttpOnly. Header: {header}"
    )


def test_p5_6_csrf_cookie_drops_secure_on_plain_http():
    """Loopback dev / health-check probes hit the endpoint over HTTP.
    The Secure flag must NOT be set in that case, otherwise the
    cookie won't be persisted by the client and the SPA breaks on
    `npm start` or any non-TLS environment."""
    header = _csrf_setcookie_header(scheme="http").lower()
    parts = [p.strip() for p in header.split(";")]
    assert "secure" not in parts, (
        f"Secure flag must not be set on plain HTTP responses; "
        f"header: {header}"
    )


def test_p5_6_csrf_cookie_name_and_value_present():
    """The cookie is named `csrf_token` and the same value appears
    in the JSON body, so the SPA can compare cookie ↔ header
    (the double-submit invariant)."""
    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.get("/api/csrf")
    r = _run(_do())
    assert r.status_code == 200
    setcookie = r.headers.get("set-cookie", "")
    # The cookie name is the first key=value pair before the ; attrs.
    head = setcookie.split(";", 1)[0]
    assert head.startswith("csrf_token="), f"cookie name must be csrf_token, got: {head}"
    cookie_value = head.split("=", 1)[1]
    body = r.json()
    assert body.get("csrf_token") == cookie_value, (
        "double-submit invariant broken: cookie value != JSON body value"
    )
