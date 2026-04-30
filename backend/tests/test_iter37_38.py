"""iter37+38 backend tests:
- Admin Health Dashboard (/api/admin/health/full)
- Influence Map digest (/api/contexts/{cid}/influence-map/digest)
- Weekly Digest cron (/api/cron/weekly-digest)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://akki-executive.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASS = "AkkiAdmin2026!"
USER_EMAIL = "bramuel@syni.ai"
USER_PASS = "TestBramuel2026!"
TULI_CFO_CTX = "2ceb9fde-a202-4891-adb1-ecf47dfe2258"
CRON_SECRET = "local-dev-cron-secret-rotate-in-prod-2026"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s, token


@pytest.fixture(scope="module")
def admin_session():
    s, _ = _login(ADMIN_EMAIL, ADMIN_PASS)
    return s


@pytest.fixture(scope="module")
def user_session():
    s, _ = _login(USER_EMAIL, USER_PASS)
    return s


# -------------------- Admin Health --------------------
class TestAdminHealth:
    def test_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/health/full", timeout=15)
        assert r.status_code == 401, f"expected 401 got {r.status_code} {r.text[:200]}"

    def test_regular_user_returns_403(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/admin/health/full", timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"
        assert "Superadmin" in r.text or "superadmin" in r.text.lower()

    def test_admin_full_grid(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/health/full", timeout=60)
        assert r.status_code == 200, f"got {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "overall" in body and body["overall"] in ("pass", "warn", "fail")
        checks = body.get("checks", {})
        for key in ("mongo", "llm", "resend", "stripe", "scheduler", "cron_secret"):
            assert key in checks, f"missing check {key}"
            assert "status" in checks[key]

        assert checks["mongo"]["status"] == "pass", f"mongo not pass: {checks['mongo']}"
        assert "latency_ms" in checks["mongo"]

        assert checks["llm"]["status"] in ("pass", "warn"), f"llm: {checks['llm']}"
        if checks["llm"]["status"] == "pass":
            assert "claude-haiku" in (checks["llm"].get("model") or "")

        # Scheduler must be pass with the two named jobs
        assert checks["scheduler"]["status"] == "pass", f"scheduler: {checks['scheduler']}"
        job_ids = {j["id"] for j in checks["scheduler"].get("jobs", [])}
        assert "exco360_weekly" in job_ids, f"missing exco360_weekly in {job_ids}"
        assert "influence_digest_weekly" in job_ids, f"missing influence_digest_weekly in {job_ids}"
        for j in checks["scheduler"]["jobs"]:
            if j["id"] in ("exco360_weekly", "influence_digest_weekly"):
                assert j.get("next_run_time"), f"no next_run_time for {j['id']}"

        assert checks["cron_secret"]["status"] == "pass", checks["cron_secret"]


# -------------------- Influence Map digest manual --------------------
class TestInfluenceDigest:
    def test_manual_digest_runs(self, user_session):
        r = user_session.post(
            f"{BASE_URL}/api/contexts/{TULI_CFO_CTX}/influence-map/digest",
            timeout=60,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "ok" in body
        assert "mode" in body
        assert "totals" in body
        # totals.edges may be 0 if no engagement; we just assert key presence
        assert isinstance(body["totals"], dict)


# -------------------- Cron weekly-digest --------------------
class TestCronWeeklyDigest:
    def test_wrong_secret_403(self):
        r = requests.post(
            f"{BASE_URL}/api/cron/weekly-digest",
            headers={"X-Cron-Secret": "wrong-secret"},
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"

    def test_no_secret_403(self):
        r = requests.post(f"{BASE_URL}/api/cron/weekly-digest", timeout=30)
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"

    def test_correct_secret_runs(self):
        r = requests.post(
            f"{BASE_URL}/api/cron/weekly-digest",
            headers={"X-Cron-Secret": CRON_SECRET},
            timeout=120,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text[:400]}"
        body = r.json()
        for k in ("sent", "skipped_no_engagement", "failed", "ran_at"):
            assert k in body, f"missing key {k} in {body}"
        assert isinstance(body["sent"], int)
        assert isinstance(body["failed"], int)
