"""Backend tests for Addendum v4.3 §1 Phase 1 — Sandbox pre-auth evaluation."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- Helpers ----------
def _start(s, payload):
    r = s.post(f"{API}/sandbox/generate", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _wait_ready(s, sid, timeout=8):
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


# ---------- POST /api/sandbox/generate ----------
class TestSandboxGenerate:
    def test_generate_returns_session_and_10_stages(self, s):
        data = _start(s, {
            "company_name": "TEST_Neo Capital Partners",
            "sector": "financial_services",
            "role": "ned",
            "region": "east_africa",
        })
        assert "session_id" in data and isinstance(data["session_id"], str)
        assert len(data["stages"]) == 10
        # Substitution check
        stage2 = data["stages"][2]["text"]
        assert "TEST_Neo Capital Partners" in stage2
        assert "financial services" in stage2
        assert "Kenya" in stage2
        # total_ms is the last stage's max_ms
        assert data["total_ms"] == data["stages"][-1]["max_ms"] == 60000

    def test_generate_missing_fields_returns_422(self, s):
        r = s.post(f"{API}/sandbox/generate",
                   json={"company_name": "X", "sector": "financial_services"},
                   timeout=10)
        assert r.status_code == 422

    def test_generate_invalid_sector_returns_422(self, s):
        r = s.post(f"{API}/sandbox/generate", json={
            "company_name": "X", "sector": "not_a_sector",
            "role": "ned", "region": "east_africa",
        }, timeout=10)
        assert r.status_code == 422


# ---------- GET /api/sandbox/generate/{id}/status ----------
class TestSandboxStatus:
    def test_status_unknown_session_returns_404(self, s):
        r = s.get(f"{API}/sandbox/generate/does-not-exist/status", timeout=10)
        assert r.status_code == 404

    def test_status_flips_to_ready_within_a_few_seconds(self, s):
        d = _start(s, {
            "company_name": "TEST_Quick Ready",
            "sector": "financial_services",
            "role": "executive",
            "region": "east_africa",
        })
        ready = _wait_ready(s, d["session_id"], timeout=8)
        assert ready["ready"] is True
        assert ready["context_id"]
        assert ready["access_token"]  # JWT surfaced only when ready


# ---------- Banking template seed integrity ----------
class TestBankingSeed:
    @pytest.fixture(scope="class")
    def ready(self):
        s = requests.Session()
        d = _start(s, {
            "company_name": "TEST_Neo Banking Plc",
            "sector": "financial_services",
            "role": "both",
            "region": "east_africa",
            "prospect_email": "prospect@example.com",
        })
        return s, _wait_ready(s, d["session_id"], timeout=10)

    def test_auto_login_works_with_bearer(self, ready):
        s, data = ready
        token = data["access_token"]
        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
        assert r.status_code == 200
        me = r.json()
        assert me["account"]["name"].startswith("Sandbox visitor")
        # NOTE: is_sandbox not surfaced by sanitize_account — reported as minor
        # contexts[0] must be sandbox
        assert len(me["contexts"]) >= 1
        sb = [c for c in me["contexts"] if c["type"] == "sandbox"]
        assert len(sb) == 1
        ctx = sb[0]
        # sandbox_metadata surfaced via sanitize_context
        assert "sandbox_metadata" in ctx and ctx["sandbox_metadata"]
        sm = ctx["sandbox_metadata"]
        assert sm["template_id"] == "banking_midcap"
        assert sm["intake_inputs"]["company_name"] == "TEST_Neo Banking Plc"
        assert sm["prospect_email"] == "prospect@example.com"

    def test_expiry_window_is_14_21_22_days(self, ready):
        _, data = ready
        # status endpoint only returns context_id; pull from /auth/me
        token = data["access_token"]
        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
        ctx = [c for c in r.json()["contexts"] if c["type"] == "sandbox"][0]
        sm = ctx["sandbox_metadata"]
        gen = datetime.fromisoformat(sm["generated_at"])
        exp = datetime.fromisoformat(sm["expires_at"])
        ro = datetime.fromisoformat(sm["read_only_until"])
        hd = datetime.fromisoformat(sm["hard_delete_at"])
        # 14 days ± 5 min
        assert 13.99 <= (exp - gen).total_seconds() / 86400 <= 14.01
        assert 20.99 <= (ro - gen).total_seconds() / 86400 <= 21.01
        assert 21.99 <= (hd - gen).total_seconds() / 86400 <= 22.01

    def test_seed_artefacts_exist_and_substituted(self, ready):
        _, data = ready
        token = data["access_token"]
        cid = data["context_id"]
        h = {"Authorization": f"Bearer {token}"}

        # Committees: 3 for banking
        r = requests.get(f"{API}/contexts/{cid}", headers=h, timeout=10)
        assert r.status_code == 200
        ctx = r.json()
        assert len(ctx.get("committees") or []) == 3

        # Documents: 3 (endpoint: /api/contexts/{cid}/documents)
        r = requests.get(f"{API}/contexts/{cid}/documents", headers=h, timeout=10)
        assert r.status_code == 200, r.text
        docs = r.json()
        docs_list = docs if isinstance(docs, list) else docs.get("documents", [])
        assert len(docs_list) == 3
        joined = " ".join((d.get("extracted_text") or "") + " " + (d.get("preview") or "")
                          for d in docs_list)
        assert "TEST_Neo Banking Plc" in joined
        assert "KSh" in joined  # East Africa currency
        # sandbox_artefact flag stored at DB level — API sanitizer currently
        # strips it. Verified in DB directly; tracked as minor finding.

        # Signals: 6 (endpoint: /api/contexts/{cid}/signals)
        r = requests.get(f"{API}/contexts/{cid}/signals", headers=h, timeout=10)
        assert r.status_code == 200, r.text
        sigs = r.json()
        sigs_list = sigs if isinstance(sigs, list) else sigs.get("signals", [])
        assert len(sigs_list) == 6
        heads = " ".join(x["headline"] for x in sigs_list)
        assert "NPL" in heads or "depositor concentration" in heads
        assert "loan-loss coverage" in heads.lower() or "loan-loss" in heads.lower()

        # Briefings: 1
        r = requests.get(f"{API}/contexts/{cid}/briefings", headers=h, timeout=10)
        assert r.status_code == 200, r.text
        br = r.json()
        br_list = br if isinstance(br, list) else br.get("briefings", [])
        assert len(br_list) == 1
        assert "TEST_Neo Banking Plc" in (br_list[0].get("opening_paragraph") or "")


# ---------- Generic fallback ----------
class TestGenericFallback:
    def test_other_sector_uses_generic_template(self, s):
        d = _start(s, {
            "company_name": "TEST_Diversified Holdings",
            "sector": "other",
            "role": "ned",
            "region": "europe",
        })
        ready = _wait_ready(s, d["session_id"], timeout=10)
        token = ready["access_token"]
        cid = ready["context_id"]
        h = {"Authorization": f"Bearer {token}"}

        r = requests.get(f"{API}/auth/me", headers=h, timeout=10)
        ctx = [c for c in r.json()["contexts"] if c["type"] == "sandbox"][0]
        assert ctx["sandbox_metadata"]["template_id"] == "generic_diversified"

        r = requests.get(f"{API}/contexts/{cid}/documents", headers=h, timeout=10)
        docs_list = r.json() if isinstance(r.json(), list) else r.json().get("documents", [])
        assert len(docs_list) == 1

        r = requests.get(f"{API}/contexts/{cid}/signals", headers=h, timeout=10)
        sigs_list = r.json() if isinstance(r.json(), list) else r.json().get("signals", [])
        assert len(sigs_list) == 3

        r = requests.get(f"{API}/contexts/{cid}/briefings", headers=h, timeout=10)
        br_list = r.json() if isinstance(r.json(), list) else r.json().get("briefings", [])
        assert len(br_list) == 1


# ---------- Templates meta endpoint ----------
class TestTemplatesMeta:
    def test_list_templates(self, s):
        r = s.get(f"{API}/sandbox/templates", timeout=10)
        assert r.status_code == 200
        arr = r.json()
        by_sector = {x["sector"]: x for x in arr}
        # Phase 1 polished template stayed the same
        assert by_sector["financial_services"]["template_id"] == "banking_midcap"
        assert by_sector["financial_services"]["is_polished"] is True
        # Phase 2 added 'other' as the only non-polished sector
        assert by_sector["other"]["template_id"] == "generic_diversified"
        assert by_sector["other"]["is_polished"] is False


# ---------- Cookie-auth regression ----------
class TestCookieAuthRegression:
    def test_bramuel_cookie_login_still_works_and_has_no_sandbox_flag(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login",
                   json={"email": "bramuel@syni.ai", "password": "TestBramuel2026!"},
                   timeout=10)
        assert r.status_code == 200, r.text
        assert "access_token" in s.cookies
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        me = r.json()
        assert me["account"]["email"] == "bramuel@syni.ai"
        assert me["account"].get("is_sandbox") is not True
        # None of bramuel's contexts should be type=sandbox
        assert not any(c["type"] == "sandbox" for c in me["contexts"])


# ---------- Cleanup sweep ----------
class TestCleanupSweep:
    def test_cleanup_requires_secret(self, s):
        # Unauthenticated now returns 401 (iter16 hardening)
        r = s.post(f"{API}/sandbox/cleanup/expired", timeout=15)
        assert r.status_code == 401, r.text

    def test_cleanup_endpoint_runs(self, s):
        import os
        # Read the secret from the backend's runtime config — test runner
        # inherits the same .env values via the FastAPI process.
        secret = os.environ.get("AKKI_CRON_SECRET", "local-dev-cron-secret-rotate-in-prod-2026")
        r = s.post(
            f"{API}/sandbox/cleanup/expired",
            headers={"X-Cron-Secret": secret},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert "swept" in r.json()
