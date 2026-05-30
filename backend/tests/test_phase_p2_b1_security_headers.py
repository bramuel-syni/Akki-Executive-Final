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


def test_b1_csp_present_on_json_too():
    """Phase P2.1-1 — CSP must ride on every response (API + HTML).
    The original B.1 ship gated CSP to HTML only; tester correctly
    flagged this as a P2.1-1 fail. CSP is now unconditional on the
    backend."""
    r = _run(_get("/api/health/composite"))
    csp = r.headers.get("Content-Security-Policy")
    assert csp, "CSP must be present on JSON API responses (P2.1-1 lockdown)"
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_b1_html_shell_headers_via_live_probe():
    """Phase P2.1-1 — the HTML shell (served by webpack-dev-server /
    Express, NOT FastAPI) must also carry all 7 headers + CSP. This is
    enforced by craco.config.js's setupMiddlewares hook. We probe the
    live preview URL because we can't drive Express from FastAPI's
    TestClient.

    Skipped if REACT_APP_BACKEND_URL is unreachable.
    """
    import subprocess

    base = ""
    fe_env = REPO / "frontend" / ".env"
    if fe_env.exists():
        for line in fe_env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                base = line.split("=", 1)[1].strip()
                break
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured; skipping live-shell probe")

    proc = subprocess.run(
        ["curl", "-sI", "--max-time", "10", f"{base}/"],
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        pytest.skip(f"live preview not reachable: {proc.stderr[:200]}")

    headers = proc.stdout.lower()
    required = [
        "strict-transport-security",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
        "x-permitted-cross-domain-policies",
        "content-security-policy",
    ]
    missing = [h for h in required if h not in headers]
    assert not missing, (
        f"HTML root missing security headers: {missing}\n"
        f"Full curl -I output:\n{proc.stdout}"
    )
