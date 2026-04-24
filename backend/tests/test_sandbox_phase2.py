"""Backend tests for Addendum v4.3 §1 Phase 2 — new sector templates +
email capture + sandbox→account conversion flow."""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _start(s, payload):
    r = s.post(f"{API}/sandbox/generate", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _wait_ready(s, sid, timeout=12):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = s.get(f"{API}/sandbox/generate/{sid}/status", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        if data["status"] == "ready":
            return data
        if data["status"] == "error":
            pytest.fail(f"Seed error: {data.get('error')}")
        time.sleep(0.3)
    pytest.fail("Sandbox did not become ready in time")


def _create_sandbox(sector, region="east_africa", role="ned", company=None):
    s = requests.Session()
    company = company or f"TEST_{sector}_{uuid.uuid4().hex[:6]}"
    d = _start(s, {
        "company_name": company,
        "sector": sector,
        "role": role,
        "region": region,
    })
    ready = _wait_ready(s, d["session_id"], timeout=12)
    return s, ready, company


# =============================================================================
# 1. Templates endpoint — all 8 sectors, is_polished flags
# =============================================================================
class TestTemplatesMeta:
    def test_all_8_sectors_present_and_polished(self):
        r = requests.get(f"{API}/sandbox/templates", timeout=10)
        assert r.status_code == 200
        arr = r.json()
        by_sector = {x["sector"]: x for x in arr}

        expected_polished = {
            "financial_services": "banking_midcap",
            "saas": "saas_growth",
            "logistics": "logistics_panafrican",
            "healthcare": "healthcare_provider",
            "manufacturing": "manufacturing_industrial",
            "retail": "retail_multicategory",
            "real_estate": "real_estate_developer",
        }
        for sector, tid in expected_polished.items():
            assert sector in by_sector, f"{sector} missing from templates"
            assert by_sector[sector]["template_id"] == tid, \
                f"{sector} → expected {tid}, got {by_sector[sector]['template_id']}"
            assert by_sector[sector]["is_polished"] is True, \
                f"{sector} should be is_polished=true"
            assert by_sector[sector]["label"], f"{sector} has empty label"

        # "other" remains the unpolished generic fallback
        assert by_sector["other"]["template_id"] == "generic_diversified"
        assert by_sector["other"]["is_polished"] is False


# =============================================================================
# 2. New sector templates — each resolves and seeds sector-specific signals
# =============================================================================
@pytest.mark.parametrize("sector,region,keyword", [
    ("saas",          "europe",          "net revenue retention"),
    ("logistics",     "east_africa",     "ERP"),
    ("healthcare",    "europe",          "readmission"),
    ("manufacturing", "east_africa",     "hedg"),
    ("retail",        "europe",          "Shrinkage"),
    ("real_estate",   "east_africa",     "Coast Gardens"),
])
class TestNewSectorTemplates:
    def test_polished_template_resolved(self, sector, region, keyword):
        s, ready, company = _create_sandbox(sector, region=region)
        token = ready["access_token"]
        cid = ready["context_id"]
        h = {"Authorization": f"Bearer {token}"}

        # /auth/me → template_id must be a polished sector id, not generic
        r = requests.get(f"{API}/auth/me", headers=h, timeout=10)
        ctx = [c for c in r.json()["contexts"] if c["type"] == "sandbox"][0]
        tid = ctx["sandbox_metadata"]["template_id"]
        assert tid != "generic_diversified", \
            f"{sector} resolved to generic template instead of polished"

        # At least 4 signals and company-name substitution in evidence
        r = requests.get(f"{API}/contexts/{cid}/signals", headers=h, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        sigs = data if isinstance(data, list) else data.get("signals", [])
        assert len(sigs) >= 4, f"{sector} produced only {len(sigs)} signals"

        # Sector-specific keyword in headlines
        heads = " ".join(x["headline"] for x in sigs)
        assert keyword.lower() in heads.lower(), \
            f"{sector}: expected '{keyword}' in signal headlines, got: {heads[:300]}"

        # Company-name substitution in at least one document/briefing
        r = requests.get(f"{API}/contexts/{cid}/documents", headers=h, timeout=10)
        data = r.json()
        docs = data if isinstance(data, list) else data.get("documents", [])
        joined_docs = " ".join(
            (d.get("extracted_text") or "") + " " + (d.get("preview") or "")
            for d in docs
        )
        assert company in joined_docs, \
            f"{sector} documents missing company_name substitution"

        # Residual {placeholder} markers should NOT leak
        assert "{company_name}" not in joined_docs
        assert "{currency}" not in joined_docs
        assert "{regulator}" not in joined_docs


# =============================================================================
# 3. Email capture endpoint
# =============================================================================
class TestCaptureEmail:
    def test_captures_email_and_queues_pickup(self):
        s, ready, _ = _create_sandbox("saas", region="europe")
        token = ready["access_token"]
        cid = ready["context_id"]
        h = {"Authorization": f"Bearer {token}"}

        r = requests.post(
            f"{API}/sandbox/contexts/{cid}/capture-email",
            json={"email": "TEST_prospect@example.com"},
            headers=h, timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Verify email persisted on context.sandbox_metadata.prospect_email
        r2 = requests.get(f"{API}/auth/me", headers=h, timeout=10)
        ctx = [c for c in r2.json()["contexts"] if c["id"] == cid][0]
        assert ctx["sandbox_metadata"].get("prospect_email") == "test_prospect@example.com"

    def test_invalid_email_rejected(self):
        s, ready, _ = _create_sandbox("retail", region="europe")
        token = ready["access_token"]
        cid = ready["context_id"]
        r = requests.post(
            f"{API}/sandbox/contexts/{cid}/capture-email",
            json={"email": "not-an-email"},
            headers={"Authorization": f"Bearer {token}"}, timeout=10,
        )
        assert r.status_code == 422

    def test_non_sandbox_context_returns_404(self):
        # Create sandbox A; try capture on random/non-existent cid while authed as A
        s, ready, _ = _create_sandbox("manufacturing")
        token = ready["access_token"]
        r = requests.post(
            f"{API}/sandbox/contexts/{uuid.uuid4()}/capture-email",
            json={"email": "x@example.com"},
            headers={"Authorization": f"Bearer {token}"}, timeout=10,
        )
        assert r.status_code == 404


# =============================================================================
# 4. Sandbox → account conversion
# =============================================================================
class TestSandboxConvert:
    def test_convert_flips_context_type_and_strips_sandbox(self):
        s, ready, _ = _create_sandbox("healthcare", role="executive")
        token = ready["access_token"]
        cid = ready["context_id"]
        h = {"Authorization": f"Bearer {token}"}

        new_email = f"TEST_convert_{uuid.uuid4().hex[:8]}@example.com".lower()
        payload = {
            "email": new_email,
            "password": "ConvertTest2026!",
            "name": "Converted User",
            "keep_sandbox": True,
        }
        r = requests.post(f"{API}/sandbox/convert", json=payload, headers=h, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["account"]["email"] == new_email
        assert body["account"]["name"] == "Converted User"
        assert body["contexts_kept"] >= 1
        assert body.get("access_token")

        # /auth/me with new bearer — context type flipped off sandbox
        new_token = body["access_token"]
        r2 = requests.get(f"{API}/auth/me",
                          headers={"Authorization": f"Bearer {new_token}"}, timeout=10)
        assert r2.status_code == 200
        me = r2.json()
        assert me["account"]["email"] == new_email
        assert me["account"].get("is_sandbox") is not True
        ctxs = me["contexts"]
        target = next((c for c in ctxs if c["id"] == cid), None)
        assert target is not None
        # executive role → executive_personal
        assert target["type"] == "executive_personal", \
            f"Expected executive_personal, got {target['type']}"
        assert target["sandbox_metadata"].get("converted_at")
        # expiry fields cleared
        assert target["sandbox_metadata"].get("expires_at") in (None, "")
        assert target["sandbox_metadata"].get("hard_delete_at") in (None, "")

    def test_convert_ned_role_flips_to_ned_personal(self):
        s, ready, _ = _create_sandbox("real_estate", role="ned")
        token = ready["access_token"]
        cid = ready["context_id"]
        new_email = f"TEST_ned_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/sandbox/convert", json={
            "email": new_email, "password": "ConvertTest2026!",
            "name": "Test NED", "keep_sandbox": True,
        }, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r.status_code == 200, r.text
        new_token = r.json()["access_token"]
        me = requests.get(f"{API}/auth/me",
                          headers={"Authorization": f"Bearer {new_token}"}, timeout=10).json()
        target = next((c for c in me["contexts"] if c["id"] == cid), None)
        assert target["type"] == "ned_personal"

    def test_duplicate_email_returns_409(self):
        s, ready, _ = _create_sandbox("retail")
        token = ready["access_token"]
        # bramuel@syni.ai is known seeded
        r = requests.post(f"{API}/sandbox/convert", json={
            "email": "bramuel@syni.ai", "password": "AnythingValid123!",
            "name": "Duplicate", "keep_sandbox": True,
        }, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r.status_code == 409

    def test_non_sandbox_caller_returns_400(self):
        # Login as bramuel (cookie auth, not a sandbox account)
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": "bramuel@syni.ai", "password": "TestBramuel2026!"},
                   timeout=10)
        assert r.status_code == 200, r.text
        r = s.post(f"{API}/sandbox/convert", json={
            "email": f"TEST_notused_{uuid.uuid4().hex[:8]}@example.com",
            "password": "ConvertTest2026!", "name": "X", "keep_sandbox": True,
        }, timeout=15)
        assert r.status_code == 400

    def test_keep_sandbox_false_deletes_context_and_artefacts(self):
        s, ready, _ = _create_sandbox("logistics", role="ned")
        token = ready["access_token"]
        cid = ready["context_id"]

        # Sanity: artefacts exist pre-delete
        h = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{API}/contexts/{cid}/signals", headers=h, timeout=10)
        data = r.json()
        sig_count = len(data if isinstance(data, list) else data.get("signals", []))
        assert sig_count >= 4

        new_email = f"TEST_drop_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/sandbox/convert", json={
            "email": new_email, "password": "ConvertTest2026!",
            "name": "Drop Sandbox", "keep_sandbox": False,
        }, headers=h, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["contexts_kept"] == 0

        # After deletion, /contexts/{cid} should 404 with the new token
        new_token = r.json()["access_token"]
        h2 = {"Authorization": f"Bearer {new_token}"}
        r_ctx = requests.get(f"{API}/contexts/{cid}", headers=h2, timeout=10)
        assert r_ctx.status_code in (403, 404), \
            f"Expected context gone, got {r_ctx.status_code}"

        # And the converted account should now have no sandbox contexts
        me = requests.get(f"{API}/auth/me", headers=h2, timeout=10).json()
        assert not any(c["type"] == "sandbox" for c in me["contexts"])
        assert not any(c["id"] == cid for c in me["contexts"])
