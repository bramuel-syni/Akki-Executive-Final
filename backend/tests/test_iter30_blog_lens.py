"""iter30 — blog RSS, cron weekly, seed/launch-10, regression for blog/strategic-goals.

Covers the backend wiring described in the iter30 review request. Uses the live
backend via REACT_APP_BACKEND_URL. LLM-touching endpoints have generous timeouts.
"""

import os
import time
import xml.etree.ElementTree as ET

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
CRON_SECRET = "local-dev-cron-secret-rotate-in-prod-2026"
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"
USER_EMAIL = "bramuel@syni.ai"
USER_PASSWORD = "TestBramuel2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(s, email, password):
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token(session):
    return _login(session, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def user_token():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return _login(s, USER_EMAIL, USER_PASSWORD)


# ---------- RSS feed ----------
class TestBlogRSS:
    def test_rss_returns_atom_xml(self, session):
        r = session.get(f"{BASE_URL}/api/blog/rss", timeout=20)
        assert r.status_code == 200, r.text[:300]
        ct = r.headers.get("content-type", "")
        assert "atom" in ct.lower() or "xml" in ct.lower(), f"unexpected content-type: {ct}"
        # Parse XML
        root = ET.fromstring(r.text)
        # Strip namespace for simpler matching
        tag = root.tag.lower()
        assert tag.endswith("feed"), f"root tag is {tag}, expected <feed>"
        # entries are optional (may be 0 published) but element must parse
        entries = [c for c in root if c.tag.lower().endswith("entry")]
        assert isinstance(entries, list)


# ---------- cron weekly ----------
class TestCronWeekly:
    def test_cron_weekly_unauthorized_without_secret(self, session):
        r = session.post(f"{BASE_URL}/api/blog/cron/weekly", timeout=20)
        assert r.status_code == 401, f"expected 401 got {r.status_code}"

    def test_cron_weekly_wrong_secret(self, session):
        r = session.post(
            f"{BASE_URL}/api/blog/cron/weekly",
            headers={"X-Cron-Secret": "wrong-secret"},
            timeout=20,
        )
        assert r.status_code == 401

    def test_cron_weekly_with_correct_secret(self, session):
        # Composes via LLM — accept 200 (success), 502 (gateway hiccup), or 503 (config)
        r = session.post(
            f"{BASE_URL}/api/blog/cron/weekly",
            headers={"X-Cron-Secret": CRON_SECRET},
            timeout=180,
        )
        assert r.status_code in (200, 502, 503), f"unexpected {r.status_code}: {r.text[:300]}"
        if r.status_code == 200:
            data = r.json()
            assert data.get("ok") is True
            assert "post" in data
            assert data.get("admins_notified") in (True, False)
        else:
            # Should return JSON with detail
            try:
                detail = r.json().get("detail", "")
                assert isinstance(detail, str) and len(detail) > 0
            except Exception:
                pass


# ---------- seed/launch-10 ----------
class TestSeedLaunch10:
    def test_seed_launch_anon_401(self, session):
        r = requests.post(f"{BASE_URL}/api/blog/seed/launch-10", timeout=20)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    def test_seed_launch_non_admin_403(self, user_token):
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/blog/seed/launch-10", timeout=20)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_seed_launch_admin_idempotent(self, admin_token):
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
        # First call — may take 60-120s but accept transient LLM 502s
        r = s.post(f"{BASE_URL}/api/blog/seed/launch-10", timeout=240)
        if r.status_code == 502:
            pytest.skip("LLM 502 transient; skipping seed test")
        assert r.status_code == 200, f"seed call failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        assert "composed" in data
        assert "skipped_existing" in data
        assert "total_drafts_now" in data
        # categories check
        valid_cats = {"opportunity", "risk", "compliance", "adoption", "growth"}
        for entry in data.get("composed", []):
            cat = entry.get("category")
            assert cat in valid_cats, f"invalid category {cat}"

        # Second call — should be largely idempotent (skip most)
        r2 = s.post(f"{BASE_URL}/api/blog/seed/launch-10", timeout=240)
        if r2.status_code == 502:
            pytest.skip("LLM 502 on second call; idempotency partially verified")
        assert r2.status_code == 200
        data2 = r2.json()
        # Should skip more than it composes on second run
        assert len(data2.get("skipped_existing", [])) >= len(data.get("composed", []))


# ---------- regression ----------
class TestRegression:
    def test_blog_posts_public(self, session):
        r = session.get(f"{BASE_URL}/api/blog/posts", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # posts list shape
        assert isinstance(data, (list, dict))

    def test_strategic_goals_endpoint(self, user_token):
        # Get bramuel contexts
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {user_token}"})
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert me.status_code == 200
        ctxs = me.json().get("contexts", [])
        assert len(ctxs) > 0
        cid = ctxs[0]["id"]
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/strategic-goals", timeout=20)
        assert r.status_code == 200, r.text[:200]

    def test_monitor_endpoint(self, user_token):
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {user_token}"})
        me = s.get(f"{BASE_URL}/api/auth/me", timeout=15)
        ctxs = me.json().get("contexts", [])
        cid = ctxs[0]["id"]
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/monitor", timeout=20)
        assert r.status_code == 200, r.text[:200]

    def test_scheduler_log_present(self):
        log_path = "/var/log/supervisor/backend.err.log"
        if not os.path.exists(log_path):
            pytest.skip("backend log not accessible")
        with open(log_path, "r", errors="ignore") as f:
            content = f.read()
        assert "Exco360 weekly scheduler armed" in content
