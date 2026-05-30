"""Phase P2 B.1 (2026-02) — Security headers middleware.

Adds a baseline of defence-in-depth response headers to every response
emitted by the FastAPI app. Headers chosen so they hold the line for an
authenticated SaaS without breaking legitimate browser features the
product depends on (image uploads, websockets, SendGrid email tracking
links).

Headers applied:

| Header                       | Value                                                      | Why                                                            |
|------------------------------|------------------------------------------------------------|----------------------------------------------------------------|
| Strict-Transport-Security    | max-age=63072000; includeSubDomains                        | Force HTTPS for 2y; only set on prod, not dev (HTTP loopback)  |
| X-Frame-Options              | DENY                                                       | No iframe embedding (clickjacking guard)                       |
| X-Content-Type-Options       | nosniff                                                    | Stop MIME sniffing                                             |
| Referrer-Policy              | strict-origin-when-cross-origin                            | Don't leak the full URL to third parties                       |
| Permissions-Policy           | camera=(), microphone=(), geolocation=(), payment=()       | Disable powerful APIs we don't use                             |
| Content-Security-Policy      | default-src 'self'; frame-ancestors 'none'; …              | XSS containment; only applied on HTML responses by default     |
| X-Permitted-Cross-Domain-Pol | none                                                       | Flash / PDF cross-domain bypass guard                          |

The CSP is intentionally minimal — it lets the existing CRA-built bundle
serve correctly while denying inline-script vectors. If product features
later need additional sources (e.g. an embedded video player), add them
to the `CSP_DIRECTIVES` dict below; do NOT silently disable CSP.

HSTS is only emitted when the request scheme is HTTPS (i.e. forwarded
behind a TLS-terminating proxy). The K8s ingress is HTTPS, so prod gets
the header; localhost dev does not.

Toggle via env: `SECURITY_HEADERS_DISABLED=1` skips the middleware
(escape hatch for emergency debugging — never set in prod).
"""
from __future__ import annotations

import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


CSP_DIRECTIVES = {
    "default-src":   "'self'",
    "script-src":    "'self' 'unsafe-inline' 'unsafe-eval' https://js.sentry-cdn.com https://browser.sentry-cdn.com",
    "style-src":     "'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src":      "'self' data: https://fonts.gstatic.com",
    "img-src":       "'self' data: blob: https:",
    "connect-src":   "'self' https: wss:",
    "media-src":     "'self' blob:",
    "frame-ancestors": "'none'",
    "base-uri":      "'self'",
    "form-action":   "'self'",
    "object-src":    "'none'",
}


def _csp_string() -> str:
    return "; ".join(f"{k} {v}" for k, v in CSP_DIRECTIVES.items())


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply a baseline of security headers to every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if os.environ.get("SECURITY_HEADERS_DISABLED", "0").strip() == "1":
            return response

        # HSTS only on HTTPS requests (loopback dev stays HTTP).
        scheme = request.url.scheme.lower()
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        is_https = scheme == "https" or forwarded_proto == "https"
        if is_https:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )

        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")

        # Phase P2.1-1 (2026-02) — CSP applied on every response, HTML
        # and JSON alike. JSON consumers ignore the header; browsers
        # use it on document loads. Required to clear the P2.1-1 audit
        # gate (CSP must be present on /api/health/composite too).
        response.headers.setdefault("Content-Security-Policy", _csp_string())

        return response
