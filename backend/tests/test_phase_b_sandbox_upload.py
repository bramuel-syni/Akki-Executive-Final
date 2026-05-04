"""Phase B sandbox hotfix — upload regression test.

Drives a real, end-to-end sandbox journey including the conversion-moment
upload that broke at the Phase A → Phase B handover:

    POST /api/sandbox/generate
    poll GET /api/sandbox/generate/{sid}/status until ready
    POST /api/contexts/{cid}/documents (multipart PDF)
    GET  /api/contexts/{cid}/documents/{did}    (queryable)

Test fails LOUDLY if the upload returns 503 (ClamAV unreachable) or 500
(MinIO unreachable). That's the point — it's a tripwire on the dev-pod
posture documented in `docs/RUNBOOKS/DEV_POD_CAVEATS.md`:

    - ALLOW_UNSAFE_UPLOADS=true     (until clamd is in the image — Phase G)
    - STORAGE_BACKEND=local         (until minio is in the image — Phase G)

If anyone flips ALLOW_UNSAFE_UPLOADS back to false without first standing
ClamAV up, this test will turn red and the sandbox conversion moment will
turn red along with it. Same for STORAGE_BACKEND=s3 without MinIO.
"""
from __future__ import annotations

import io
import os
import sys
import time
from typing import Any, Dict

import pytest
import requests

sys.path.insert(0, "/app/backend")

# Default to the local uvicorn process; override with AKKI_BACKEND_URL
# in CI if the test suite is pointed at a deployed preview.
BASE_URL = os.environ.get("AKKI_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
TIMEOUT = 30


def _make_pdf_bytes() -> bytes:
    """Synthesize a minimal valid PDF in-memory. We avoid reportlab here
    so the test has no extra dependencies even if reportlab is removed
    from requirements later."""
    # Hand-rolled minimum-viable PDF — single page with a couple of
    # text strings. Enough that the documents extractor produces a
    # `extracted` status (it falls through to a no-op extractor for
    # very small PDFs but still returns 200).
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"5 0 obj << /Length 70 >> stream\n"
        b"BT /F1 12 Tf 72 750 Td (AKKI sandbox upload regression test.) Tj ET\n"
        b"endstream endobj\n"
        b"xref\n0 6\n0000000000 65535 f\n"
        b"0000000010 00000 n\n0000000053 00000 n\n"
        b"0000000098 00000 n\n0000000185 00000 n\n"
        b"0000000245 00000 n\n"
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n368\n%%EOF\n"
    )
    return body


@pytest.fixture(scope="module")
def sandbox_session() -> Dict[str, Any]:
    """Spin up a fresh sandbox session, return access_token + context_id.

    Module-scoped so we only pay the seed cost once across the cases
    below. Skips with a clear message if the backend isn't reachable —
    matches how every other integration test in this corpus behaves.
    """
    payload = {
        "company_name": "PhaseBSandboxUploadProbe",
        "sector": "saas",
        "role": "executive",
        "region": "east_africa",
        "objective": "Verify the conversion-moment upload survives Phase A.",
    }
    try:
        r = requests.post(
            f"{BASE_URL}/api/sandbox/generate", json=payload, timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Backend not reachable at {BASE_URL}: {e}")

    assert r.status_code == 200, (r.status_code, r.text[:400])
    data = r.json()
    sid = data["session_id"]
    assert sid

    # Poll until ready (background seed completes in ~2-3s).
    deadline = time.time() + 30
    last_status = None
    while time.time() < deadline:
        rs = requests.get(
            f"{BASE_URL}/api/sandbox/generate/{sid}/status", timeout=TIMEOUT,
        )
        last_status = rs.json()
        if last_status.get("status") == "ready":
            break
        if last_status.get("status") == "error":
            pytest.fail(f"Sandbox seed failed: {last_status}")
        time.sleep(0.5)
    else:
        pytest.fail(f"Sandbox didn't reach 'ready' in 30s — last={last_status}")

    assert last_status.get("access_token"), "No access_token on ready"
    assert last_status.get("context_id"), "No context_id on ready"
    return last_status


# ---------------------------------------------------------------------------
# A.1 — POST /api/sandbox/generate succeeds and yields a session.
# (Already proven by the fixture, but keep an explicit case so the failure
# point is unambiguous when this lights up red.)
# ---------------------------------------------------------------------------
def test_sandbox_generate_returns_session(sandbox_session):
    assert sandbox_session.get("ready") is True
    assert sandbox_session["context_id"]
    assert sandbox_session["access_token"]


# ---------------------------------------------------------------------------
# A.2 — Stage 11 (the conversion moment): POST /contexts/{cid}/documents
# must accept the prospect's PDF. This is the call that returned 503
# (ClamAV unreachable) and then 500 (MinIO unreachable) before the
# Phase B sandbox hotfix. If anyone reverts the env, this test fails.
# ---------------------------------------------------------------------------
def test_sandbox_upload_succeeds_with_dev_bypass(sandbox_session):
    cid = sandbox_session["context_id"]
    token = sandbox_session["access_token"]
    pdf = _make_pdf_bytes()
    files = {"file": ("regression.pdf", io.BytesIO(pdf), "application/pdf")}
    data = {
        "display_name": "Phase B regression upload",
        "description": "Driven by tests/test_phase_b_sandbox_upload.py",
        "data_trust": "mixed",
    }
    r = requests.post(
        f"{BASE_URL}/api/contexts/{cid}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files=files, data=data, timeout=TIMEOUT,
    )

    # The two specific failure modes this test exists to catch.
    if r.status_code == 503:
        try:
            body = r.json()
        except ValueError:
            body = r.text
        pytest.fail(
            "Sandbox upload returned HTTP 503 — virus scanner offline. "
            "If ClamAV is not in this container, ALLOW_UNSAFE_UPLOADS "
            "must be 'true' in backend/.env until Phase G installs the "
            f"binary. Body: {body}"
        )
    if r.status_code == 500:
        pytest.fail(
            "Sandbox upload returned HTTP 500 — typically a storage "
            "backend issue (MinIO unreachable). If MinIO is not in "
            "this container, STORAGE_BACKEND must be 'local' in "
            f"backend/.env until Phase G installs the binary. Body: {r.text[:400]}"
        )
    assert r.status_code == 200, (r.status_code, r.text[:400])
    out = r.json()
    assert out.get("id"), out
    # Document must be queryable immediately after upload (the
    # `status:'extracted'` contract that SandboxPackDrop.jsx reads).
    sandbox_session["_uploaded_doc_id"] = out["id"]
    assert out.get("status") in ("extracted", "queued"), out


# ---------------------------------------------------------------------------
# A.3 — The doc is queryable via the standard documents GET. This is
# what QuickResults.jsx fetches to render its "AKKI just read <name>"
# header on the conversion landing page.
# ---------------------------------------------------------------------------
def test_uploaded_sandbox_doc_is_queryable(sandbox_session):
    cid = sandbox_session["context_id"]
    did = sandbox_session.get("_uploaded_doc_id")
    if not did:
        pytest.skip("Upload test didn't run / didn't capture doc id")
    token = sandbox_session["access_token"]
    r = requests.get(
        f"{BASE_URL}/api/contexts/{cid}/documents/{did}",
        headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT,
    )
    assert r.status_code == 200, (r.status_code, r.text[:400])
    doc = r.json()
    assert doc["id"] == did
    # Sandbox uploads carry `data_trust='mixed'` per SandboxPackDrop.jsx.
    assert doc.get("data_trust") in ("mixed", "trusted", "untrusted"), doc
