"""iter33: backend tests for
  - POST /api/contexts/{cid}/documents/{did}/summary  (cache, refresh, 400, 404)
  - POST /api/contexts/{cid}/reports/compose  (new optional `description` field)
  - GET  /api/contexts/{cid}/documents/{did}  (now includes akki_summary)
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"

# Tuli CFO executive context (per review request)
CTX_ID = "2ceb9fde-a202-4891-adb1-ecf47dfe2258"
DOC_ID = "a90b82e3-3fa9-4a26-be0c-d63bdfc51909"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return s


# ---------- AKKI doc summary ----------
class TestDocumentSummary:
    def test_summary_first_call_returns_payload(self, session: requests.Session):
        # Force fresh so this test is independent of state
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC_ID}/summary?refresh=true",
            timeout=180,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert isinstance(data.get("tldr"), str) and data["tldr"], "tldr missing/empty"
        assert isinstance(data.get("highlights"), list) and len(data["highlights"]) >= 1
        assert isinstance(data.get("questions"), list) and len(data["questions"]) >= 1
        assert "mode" in data
        assert "generated_at" in data
        # cap enforcement
        assert len(data["highlights"]) <= 7
        assert len(data["questions"]) <= 3

    def test_summary_cache_hit_is_fast_and_identical(self, session: requests.Session):
        # First call (no refresh) — should hit cache from previous test
        t0 = time.monotonic()
        r1 = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC_ID}/summary",
            timeout=30,
        )
        elapsed = time.monotonic() - t0
        assert r1.status_code == 200
        d1 = r1.json()
        # Cache hit should be <5s (no LLM burn). Real LLM is 30-60s.
        assert elapsed < 10, f"expected cache hit but took {elapsed:.1f}s"
        assert d1.get("generated_at"), "cached payload missing generated_at"

        # Second call same — confirm idempotent
        r2 = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC_ID}/summary",
            timeout=15,
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["tldr"] == d1["tldr"]
        assert d2["generated_at"] == d1["generated_at"]

    def test_summary_404_when_doc_missing(self, session: requests.Session):
        bogus = str(uuid.uuid4())
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{bogus}/summary",
            timeout=15,
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text[:200]}"

    def test_get_document_includes_akki_summary(self, session: requests.Session):
        """After the summary cache exists, GET doc should surface akki_summary."""
        r = session.get(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{DOC_ID}",
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        data = r.json()
        assert "akki_summary" in data, "akki_summary should be present on the doc after generation"
        s = data["akki_summary"]
        assert s.get("tldr")
        assert isinstance(s.get("highlights"), list)


# ---------- Reports compose with description ----------
class TestComposeReportDescription:
    def _payload(self, description=None):
        body = {
            "cycle_name": f"TEST_iter33_compose_{uuid.uuid4().hex[:6]}",
            "title": "TEST iter33 compose report description field",
            "chain": [
                {"name": "TEST Reviewer", "title": "CEO", "email": "test_iter33_reviewer@example.com"},
            ],
        }
        if description is not None:
            body["description"] = description
        return body

    def test_compose_accepts_description_and_surfaces_in_body(self, session: requests.Session):
        desc = "Audit-committee deep-dive on revenue recognition with Q3 vs Q2 deltas."
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/reports/compose",
            json=self._payload(description=desc),
            timeout=120,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("id"), "report id missing"
        # description echoed on the report record
        assert data.get("description") == desc
        # Surfaced at top of body as 'What the author asked for'
        body_md = data.get("body") or ""
        assert "What the author asked for" in body_md, (
            f"expected 'What the author asked for' header in body. got: {body_md[:400]}"
        )
        assert desc in body_md, "description text should appear in body"

    def test_compose_without_description_still_succeeds(self, session: requests.Session):
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/reports/compose",
            json=self._payload(description=None),
            timeout=120,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("id")
        # description either absent or null
        assert not data.get("description")
        body_md = data.get("body") or ""
        assert "What the author asked for" not in body_md, (
            "header should not appear when no description provided"
        )

    def test_compose_description_too_long_rejected(self, session: requests.Session):
        too_long = "x" * 4001
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/reports/compose",
            json=self._payload(description=too_long),
            timeout=30,
        )
        assert r.status_code == 422, f"expected 422 validation, got {r.status_code}"
