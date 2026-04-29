"""Iter65 — Public sensitivity-demo + iter64 regression smoke."""
import os
import time
import pytest
import requests
from pathlib import Path

# Load REACT_APP_BACKEND_URL from frontend/.env if not in environment
if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe_env = Path("/app/frontend/.env")
    if fe_env.exists():
        for line in fe_env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()
                break

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
DEMO_URL = f"{BASE_URL}/api/public/studio/sensitivity-demo"


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ── Public demo endpoint ──────────────────────────────────────────────
class TestSensitivityDemo:
    def test_benign_text_scores_low(self, client):
        time.sleep(2)
        r = client.post(DEMO_URL, json={"text": "Quarterly cash flow update with normal opex commentary."})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "sensitivity" in data
        s = data["sensitivity"]
        for k in ("score", "classification", "label", "reasons"):
            assert k in s
        assert isinstance(s["reasons"], list)
        assert s["classification"] in ("public", "internal")
        assert s["score"] < 50
        assert data["input_chars"] == len(
            "Quarterly cash flow update with normal opex commentary."
        )

    def test_restricted_text_scores_high(self, client):
        time.sleep(2)
        text = (
            "Confidential M&A discussion: a £85m acquisition with regulator approval pending. "
            "Whistleblower allegation reported on the CEO transition; restructure planned."
        )
        r = client.post(DEMO_URL, json={"text": text})
        assert r.status_code == 200, r.text
        s = r.json()["sensitivity"]
        assert s["score"] >= 75, f"expected >=75, got {s}"
        assert s["classification"] == "restricted"
        assert len(s["reasons"]) >= 3

    def test_short_payload_rejected(self, client):
        time.sleep(2)
        r = client.post(DEMO_URL, json={"text": "hi"})
        assert r.status_code == 422

    def test_long_payload_rejected(self, client):
        time.sleep(2)
        r = client.post(DEMO_URL, json={"text": "x" * 4001})
        assert r.status_code == 422

    def test_rate_limit_burst(self, client):
        # Best-effort burst test. Behind k8s ingress, request.client.host
        # can vary per connection (multi-node ingress), so rate-limit may
        # be defeated for some hits. We accept that at least one 429 fires
        # within a 5-shot burst.
        time.sleep(2)
        codes = []
        for i in range(5):
            r = client.post(DEMO_URL, json={"text": f"Routine note {i}."})
            codes.append(r.status_code)
        assert 429 in codes, f"expected at least one 429 in burst, got {codes}"


# ── Iter64 regression — auth-required studio history endpoint reachable ─
class TestIter64Regression:
    """Smoke check: studio/history endpoint shape is still wired (auth gated)."""

    def test_studio_history_requires_auth(self, client):
        time.sleep(2)
        r = client.get(
            f"{BASE_URL}/api/contexts/fb4df969-3f17-4279-bf78-f07bb9e29650/studio/history"
        )
        # Without cookies this should 401/403, not 500
        assert r.status_code in (401, 403), f"expected auth-gate, got {r.status_code}"

    def test_login_works(self, client):
        r = client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "bramuel@syni.ai", "password": "TestBramuel2026!"},
        )
        assert r.status_code == 200, r.text
        assert "access_token" in r.json() or r.cookies.get("access_token")
