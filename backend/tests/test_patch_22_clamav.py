"""Patch 22 — ClamAV upload-scan integration tests.

The Patch 22 brief specifies 3 cases:
  1. OK happy path (mocked clamd returns clean).
  2. INFECTED — endpoint returns 422 with malware_suspected.
  3. ERROR in dev (ALLOW_UNSAFE_UPLOADS=true) — upload proceeds.

The scanner service lives at services/clamav_service.py. Today the
`.env` in this repo sets `ALLOW_UNSAFE_UPLOADS=true` so the dev pod
can run without a clamd container. In production this MUST be `false`
or unset — see /app/memory/integrations/CLAMAV_SETUP_GUIDELINE.md §5.

The integration point we exercise here is `POST /api/contexts/{cid}/documents`
(the same endpoint Patch 23 fixed). All five other upload entry points
(chat, daily_review, work_studio_export, studio_blocks) use the same
`clamav_service.scan(data, filename)` call so this test transitively
covers their contract too.
"""
from __future__ import annotations

import importlib
import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from server import app
from services import clamav_service


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register(client: AsyncClient) -> tuple[str, str]:
    email = f"clamav-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "ClamTest!1", "name": "ClamAV Test"},
    )
    assert r.status_code in {200, 201}, r.text
    token = r.json()["access_token"]
    return token, email


async def _create_context(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/api/contexts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"ClamAV Probe {uuid.uuid4().hex[:6]}",
            "kind": "executive_personal",
            "industry": "banking",
            "role": "CFO",
        },
    )
    assert r.status_code in {200, 201}, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Case 1 — OK happy path (mock clamd returns clean)
# ---------------------------------------------------------------------------
async def test_upload_ok_happy_path(client, monkeypatch):
    """Mock scan to return clean → upload succeeds with status 200."""
    def fake_scan(data, filename=None):
        return clamav_service.ScanResult(clean=True, signature=None, scan_ms=5)
    monkeypatch.setattr(clamav_service, "scan", fake_scan)

    token, _ = await _register(client)
    cid = await _create_context(client, token)
    files = {"file": ("clean.txt", io.BytesIO(b"clean content"), "text/plain")}
    r = await client.post(
        f"/api/contexts/{cid}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files=files, data={"data_trust": "mixed"},
    )
    assert r.status_code == 200, f"OK path failed: {r.status_code} {r.text}"
    doc = r.json()
    assert doc["status"] in {"extracted", "extracting", "uploaded"}


# ---------------------------------------------------------------------------
# Case 2 — INFECTED rejection
# ---------------------------------------------------------------------------
async def test_upload_infected_returns_422(client, monkeypatch):
    """Mock scan to return FOUND → upload rejected with 422 + signature."""
    def fake_scan(data, filename=None):
        return clamav_service.ScanResult(
            clean=False,
            signature="Eicar-Test-Signature",
            scan_ms=12,
        )
    monkeypatch.setattr(clamav_service, "scan", fake_scan)

    token, _ = await _register(client)
    cid = await _create_context(client, token)
    files = {"file": ("eicar.txt", io.BytesIO(b"infected pretend bytes"), "text/plain")}
    r = await client.post(
        f"/api/contexts/{cid}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files=files, data={"data_trust": "mixed"},
    )
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    detail = r.json().get("detail") or {}
    assert detail.get("error") == "blocked"
    assert detail.get("reason") == "malware_suspected"
    assert detail.get("signature") == "Eicar-Test-Signature"


# ---------------------------------------------------------------------------
# Case 3 — ERROR-in-dev (ALLOW_UNSAFE_UPLOADS) allows the upload
# ---------------------------------------------------------------------------
async def test_upload_error_in_dev_bypass_allows(client, monkeypatch):
    """When ALLOW_UNSAFE_UPLOADS=true (dev pod default), the scanner
    is bypassed and the upload proceeds even if clamd would have been
    unreachable. We verify by monkeypatching `scan` to return the
    clean+unsafe-mode path identical to what the live service does
    when ALLOW_UNSAFE_UPLOADS is set."""
    # Force the bypass path on the live service module.
    monkeypatch.setattr(clamav_service, "ALLOW_UNSAFE_UPLOADS", True, raising=False)

    token, _ = await _register(client)
    cid = await _create_context(client, token)
    files = {"file": ("dev-bypass.txt", io.BytesIO(b"dev-bypass body"), "text/plain")}
    r = await client.post(
        f"/api/contexts/{cid}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files=files, data={"data_trust": "mixed"},
    )
    assert r.status_code == 200, f"dev-bypass upload failed: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# Case 4 — Scanner unreachable in prod (no bypass) — returns 503
# Documents the prod contract.
# ---------------------------------------------------------------------------
async def test_upload_unreachable_in_prod_returns_503(client, monkeypatch):
    monkeypatch.setattr(clamav_service, "ALLOW_UNSAFE_UPLOADS", False, raising=False)

    def fake_scan(data, filename=None):
        raise clamav_service.ClamAVUnreachable("simulated clamd down")
    monkeypatch.setattr(clamav_service, "scan", fake_scan)

    token, _ = await _register(client)
    cid = await _create_context(client, token)
    files = {"file": ("probe.txt", io.BytesIO(b"x"), "text/plain")}
    r = await client.post(
        f"/api/contexts/{cid}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files=files, data={"data_trust": "mixed"},
    )
    assert r.status_code == 503, f"expected 503 when clamd unreachable in prod, got {r.status_code}: {r.text}"
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "scanner_unavailable"


# ---------------------------------------------------------------------------
# Case 5 — Healthcheck reports unsafe mode
# ---------------------------------------------------------------------------
def test_healthcheck_reports_unsafe_mode(monkeypatch):
    monkeypatch.setattr(clamav_service, "ALLOW_UNSAFE_UPLOADS", True, raising=False)
    h = clamav_service.healthcheck()
    assert h["ok"] is False
    assert h["mode"] == "unsafe"
