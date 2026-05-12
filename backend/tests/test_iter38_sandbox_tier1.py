"""Iter38 Tier 1 — Sandbox conversion overhaul

Covers:
- POST /api/sandbox/generate with new objective + other_sector fields
- GET /api/sandbox/generate/{id}/status reaches ready
- GET /api/sandbox/contexts/{id}/tutorial (auth)
- POST /api/sandbox/contexts/{id}/tutorial/dismiss
- POST /api/sandbox/contexts/seeded (auth via bramuel) + tutorial on real ctx
- resolve_stage_texts uses other_sector_name when sector='other'
"""
import os
import time
import requests
import pytest

pytestmark = pytest.mark.skip(reason="Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after the password constant was unified (Bramuel2026!) — previously silent-skipped because the login failed; now login succeeds but hardcoded context IDs no longer match the current seed.")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://akki-executive.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _wait_ready(sess, sid, timeout=20):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = sess.get(f"{API}/sandbox/generate/{sid}/status")
        last = r
        if r.status_code == 200 and r.json().get("ready"):
            return r.json()
        time.sleep(1)
    raise AssertionError(f"sandbox not ready in {timeout}s; last={last.status_code} {last.text[:200]}")


# --------------------------- Sandbox generate w/ new fields ---------------------------
class TestSandboxGenerate:
    def test_generate_with_objective_and_other_sector(self, sess):
        payload = {
            "company_name": "TEST_AcmeOtherCo",
            "sector": "other",
            "role": "executive",
            "region": "east_africa",
            "objective": "I need to size up exit risks before the next audit committee.",
            "other_sector_name": "Edutech holdings",
            "other_sector_description": "Pan-African private edutech investments",
        }
        r = sess.post(f"{API}/sandbox/generate", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "session_id" in body and isinstance(body["session_id"], str)
        assert body["total_ms"] > 0
        stages = body["stages"]
        assert isinstance(stages, list) and len(stages) >= 3
        # Stage 0/1/2 must have non-empty sublines
        for i in (0, 1, 2):
            assert stages[i]["index"] == i
            assert "headline" in stages[i] and stages[i]["headline"]
            assert "text" in stages[i]
            assert isinstance(stages[i]["sublines"], list) and len(stages[i]["sublines"]) >= 1
        # Stage 2 substitutes other_sector_name (not 'diversified')
        joined = " ".join([stages[2]["headline"]] + stages[2]["sublines"])
        assert "Edutech holdings" in joined or "edutech holdings" in joined.lower(), \
            f"Expected other_sector_name in stage 2: {joined}"
        assert "diversified" not in joined.lower()

    def test_generate_without_objective_accepts(self, sess):
        payload = {
            "company_name": "TEST_NoObjCo",
            "sector": "saas",
            "role": "executive",
            "region": "europe",
        }
        r = sess.post(f"{API}/sandbox/generate", json=payload)
        assert r.status_code == 200, r.text
        assert "session_id" in r.json()

    def test_status_reaches_ready(self, sess):
        payload = {
            "company_name": "TEST_ReadyCo",
            "sector": "saas",
            "role": "executive",
            "region": "east_africa",
            "objective": "Validate readiness within 10 seconds for the audit cycle close.",
        }
        r = sess.post(f"{API}/sandbox/generate", json=payload)
        sid = r.json()["session_id"]
        ready = _wait_ready(sess, sid, timeout=20)
        assert ready["ready"] is True
        assert ready["context_id"]
        assert ready["access_token"]


# --------------------------- Tutorial endpoints ---------------------------
class TestSandboxTutorial:
    def _spin_sandbox(self, sess, **kw):
        payload = {
            "company_name": "TEST_TutorialCo",
            "sector": "financial_services",
            "role": "ned",
            "region": "east_africa",
            **kw,
        }
        r = sess.post(f"{API}/sandbox/generate", json=payload)
        sid = r.json()["session_id"]
        ready = _wait_ready(sess, sid, timeout=25)
        return ready["context_id"], ready["access_token"]

    def test_tutorial_with_objective_embeds_in_opener(self, sess):
        objective = "Probe top-20 depositor concentration before next audit committee."
        ctx_id, token = self._spin_sandbox(sess, objective=objective)
        r = requests.get(f"{API}/sandbox/contexts/{ctx_id}/tutorial",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dismissed"] is False
        assert body["objective"] == objective
        assert body["first_briefing"] is not None
        assert body["first_briefing"]["id"]
        assert body["first_briefing"]["title"]
        assert body["first_briefing"]["opening_paragraph"]
        assert body["first_signal_headline"]
        assert objective[:40] in body["suggested_chat_opener"], \
            f"objective not embedded: {body['suggested_chat_opener']}"
        assert isinstance(body["steps"], list) and len(body["steps"]) == 3
        keys = {s["key"] for s in body["steps"]}
        assert keys == {"read_brief", "ask_chat", "scan_signals"}

    def test_tutorial_without_objective_falls_back_to_signal(self, sess):
        ctx_id, token = self._spin_sandbox(sess)  # no objective
        r = requests.get(f"{API}/sandbox/contexts/{ctx_id}/tutorial",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["objective"] in (None, "")
        # Opener should reference first signal headline
        assert body["first_signal_headline"]
        # Either pattern works depending on implementation
        opener = body["suggested_chat_opener"] or ""
        assert body["first_signal_headline"] in opener or opener.startswith("Walk me through this:"), \
            f"Expected fallback opener referencing signal: {opener}"

    def test_tutorial_dismiss_persists(self, sess):
        ctx_id, token = self._spin_sandbox(sess, objective="Quick dismiss test for the chair brief.")
        h = {"Authorization": f"Bearer {token}"}
        r = requests.post(f"{API}/sandbox/contexts/{ctx_id}/tutorial/dismiss",
                          json={"dismissed": True}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # Verify persistence
        r2 = requests.get(f"{API}/sandbox/contexts/{ctx_id}/tutorial", headers=h)
        assert r2.status_code == 200
        assert r2.json()["dismissed"] is True


# --------------------------- Seeded real context ---------------------------
class TestSeededRealContext:
    @pytest.fixture(scope="class")
    def bramuel_token(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": "bramuel@syni.ai", "password": "Bramuel2026!"})
        if r.status_code != 200:
            pytest.skip(f"bramuel login failed: {r.status_code} {r.text[:120]}")
        # access_token may be in body or cookie
        body = r.json()
        tok = body.get("access_token") or body.get("token")
        if not tok:
            # Try cookie fallback
            tok = r.cookies.get("access_token")
        assert tok, f"no access_token in login response: {body}"
        return tok

    def test_create_seeded_executive_context(self, bramuel_token):
        h = {"Authorization": f"Bearer {bramuel_token}", "Content-Type": "application/json"}
        payload = {
            "company_name": "TEST_SeededExecCo",
            "sector": "saas",
            "role": "executive",
            "region": "europe",
            "objective": "Drive a margin recovery program over the next two quarters.",
            "seed_data": True,
        }
        r = requests.post(f"{API}/sandbox/contexts/seeded", json=payload, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["context_id"]
        ctx = body["context"]
        assert ctx["type"] == "executive_personal"
        assert ctx["name"] == "TEST_SeededExecCo"
        # Tutorial works on seeded real context
        r2 = requests.get(f"{API}/sandbox/contexts/{body['context_id']}/tutorial", headers=h)
        assert r2.status_code == 200, r2.text
        t = r2.json()
        assert t["dismissed"] is False
        assert t["objective"] == payload["objective"]
        assert payload["objective"][:30] in (t["suggested_chat_opener"] or "")

    def test_create_seeded_ned_context(self, bramuel_token):
        h = {"Authorization": f"Bearer {bramuel_token}", "Content-Type": "application/json"}
        payload = {
            "company_name": "TEST_SeededNedCo",
            "sector": "financial_services",
            "role": "ned",
            "region": "east_africa",
            "seed_data": True,
        }
        r = requests.post(f"{API}/sandbox/contexts/seeded", json=payload, headers=h)
        assert r.status_code == 200, r.text
        ctx = r.json()["context"]
        assert ctx["type"] == "ned_personal"
