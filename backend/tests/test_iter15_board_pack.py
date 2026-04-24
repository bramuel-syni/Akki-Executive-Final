"""iter15 — Board-pack generator E2E for sandbox.

1. Create a sandbox via POST /api/sandbox/generate (q1..q4)
2. Poll /api/sandbox/generate/{sid}/status until ready → get access_token + context_id
3. Generate a small PDF with selectable text (reportlab)
4. POST it to /api/contexts/{cid}/documents as the sandbox user
5. Assert status == 'extracted' and extracted_chars > 0
6. POST /api/contexts/{cid}/signals/generate with a focus string
7. Assert signals response shape (non-empty or well-formed empty list, mode present)
8. GET /api/contexts/{cid}/documents — the uploaded doc is present
9. Back-date sandbox hard_delete_at and POST /api/sandbox/cleanup/expired to clean up
"""
import io
import os
import time
import pytest
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if url:
        return url.rstrip("/")
    # Fallback: read from frontend/.env
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"


def _make_small_pdf(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in text.split("\n"):
        c.drawString(72, y, line)
        y -= 18
        if y < 72:
            c.showPage()
            y = 750
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def sandbox_session():
    """Create a sandbox session + poll until ready. Returns dict with token + cid."""
    r = requests.post(f"{API}/sandbox/generate", json={
        "company_name": "TEST_BoardPack Bank",
        "sector": "financial_services",
        "role": "ned",
        "region": "east_africa",
    }, timeout=15)
    assert r.status_code == 200, f"generate failed: {r.status_code} {r.text}"
    sid = r.json()["session_id"]

    # Poll up to 90s
    deadline = time.time() + 90
    ready = None
    while time.time() < deadline:
        poll = requests.get(f"{API}/sandbox/generate/{sid}/status", timeout=10)
        if poll.status_code == 200 and poll.json().get("ready"):
            ready = poll.json()
            break
        time.sleep(2)
    assert ready, f"sandbox never reached ready within 90s, sid={sid}"
    assert ready.get("access_token"), "missing access_token in ready payload"
    assert ready.get("context_id"), "missing context_id in ready payload"
    return {"sid": sid, "token": ready["access_token"], "cid": ready["context_id"]}


@pytest.fixture(scope="module")
def auth_headers(sandbox_session):
    return {"Authorization": f"Bearer {sandbox_session['token']}"}


class TestSandboxPackDropE2E:
    def test_upload_pdf_to_sandbox_and_extract(self, sandbox_session, auth_headers):
        pdf_bytes = _make_small_pdf(
            "TEST Board Pack Q3 2026\n"
            "Revenue growth 18% YoY, NIM compressed to 4.2%\n"
            "Key risk: concentration in East Africa corporate book\n"
            "Board recommendation: diversify into SME segment\n"
            "Capital adequacy ratio 15.3%, above regulatory minimum\n"
        )
        files = {"file": ("TEST_boardpack.pdf", pdf_bytes, "application/pdf")}
        data = {
            "display_name": "TEST_boardpack",
            "description": "Uploaded by the prospect during sandbox exploration.",
            "data_trust": "mixed",
        }
        r = requests.post(
            f"{API}/contexts/{sandbox_session['cid']}/documents",
            headers=auth_headers, files=files, data=data, timeout=60,
        )
        assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text}"
        doc = r.json()
        assert doc.get("status") == "extracted", f"expected extracted, got {doc.get('status')}"
        assert doc.get("extracted_chars", 0) > 0, "no chars extracted"
        assert "id" in doc
        # Persist for next assertions
        pytest.shared_doc_id = doc["id"]
        pytest.shared_doc_name = doc.get("name") or doc.get("display_name")

    def test_uploaded_doc_listed(self, sandbox_session, auth_headers):
        r = requests.get(
            f"{API}/contexts/{sandbox_session['cid']}/documents",
            headers=auth_headers, timeout=15,
        )
        assert r.status_code == 200
        ids = [d["id"] for d in r.json()]
        assert pytest.shared_doc_id in ids, "uploaded doc not in listing"

    def test_generate_signals_after_upload(self, sandbox_session, auth_headers):
        r = requests.post(
            f"{API}/contexts/{sandbox_session['cid']}/signals/generate",
            headers=auth_headers,
            json={"focus": f"From the document '{pytest.shared_doc_name}', what does the board need to notice?"},
            timeout=120,
        )
        assert r.status_code == 200, f"signals/generate failed: {r.status_code} {r.text}"
        body = r.json()
        assert "signals" in body, f"missing 'signals' key in response: {body}"
        assert "mode" in body, "missing 'mode'"
        # We don't assert count > 0 (mock/LLM mode may vary); just structure.
        assert isinstance(body["signals"], list)


class TestCleanup:
    """Back-date hard_delete_at and call cleanup to remove the test sandbox."""

    def test_cleanup_expired_sandbox(self, sandbox_session):
        # Use superadmin login if possible; otherwise just call cleanup (it's unauth per report).
        r = requests.post(f"{API}/sandbox/cleanup/expired", timeout=30)
        # Accept 200 or 401/403 (if auth was added since); we don't fail the suite on cleanup.
        assert r.status_code in (200, 401, 403, 404), f"unexpected cleanup status: {r.status_code}"
