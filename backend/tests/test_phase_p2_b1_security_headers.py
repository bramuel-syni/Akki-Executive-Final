"""Phase P2 B.1 — Security headers middleware lockdown.

Asserts every response carries the baseline defence-in-depth headers
listed in `services/security_headers.py`. CSP is gated to HTML
responses; the other headers ride on every response.

Uses AsyncClient + ASGITransport driven by the session event loop
(conftest.py) so it co-exists cleanly with the PKCE Motor-bound tests
in the same pytest invocation.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _get(path: str, headers=None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        return await ac.get(path, headers=headers)


def test_b1_baseline_headers_on_json_response():
    r = _run(_get("/api/health/composite"))
    assert r.status_code == 200
    # JSON responses carry every header EXCEPT CSP (gated to HTML).
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in r.headers.get("Permissions-Policy", "")
    assert r.headers.get("X-Permitted-Cross-Domain-Policies") == "none"


def test_b1_hsts_set_on_https_forwarded():
    """HSTS only emits when the request is HTTPS (via x-forwarded-proto)."""
    r = _run(_get(
        "/api/health/composite",
        headers={"x-forwarded-proto": "https"},
    ))
    assert r.status_code == 200
    hsts = r.headers.get("Strict-Transport-Security")
    assert hsts and "max-age=" in hsts and "includeSubDomains" in hsts


def test_b1_hsts_absent_on_plain_http():
    r = _run(_get("/api/health/composite"))
    # AsyncClient default scheme is http → HSTS must NOT appear.
    assert r.headers.get("Strict-Transport-Security") is None
