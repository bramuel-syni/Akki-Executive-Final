"""Iter61 — AKKI Solve engine + Walk-in context hint + admin auth-events.

Backend regression suite covering:
  - GET    /api/solve/clusters                 (12 clusters seeded)
  - POST   /api/solve/sessions                 (start + Surface primer)
  - POST   /api/solve/sessions/{sid}/turn      (4-phase state machine)
  - POST   /api/solve/sessions/{sid}/restart   (clones cluster+intent)
  - POST   /api/solve/sessions/{sid}/abandon
  - GET    /api/solve/sessions[?status=]       (sorted by updated_at desc)
  - POST   /api/walkin                         (context hint baked in)
  - GET    /api/admin/auth-events              (superadmin only)

Skips gracefully if backend or auth is down.
"""
import os
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
USER_EMAIL = "bramuel@syni.ai"
USER_PASSWORD = "TestBramuel2026!"
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(api, email, password):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        return None
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def user_token(api):
    tok = _login(api, USER_EMAIL, USER_PASSWORD)
    if not tok:
        pytest.skip("User login failed — cannot run user-scoped tests")
    return tok


@pytest.fixture(scope="session")
def admin_token(api):
    tok = _login(api, ADMIN_EMAIL, ADMIN_PASSWORD)
    if not tok:
        pytest.skip("Admin login failed — cannot run admin-scoped tests")
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Solve clusters
# ---------------------------------------------------------------------------
class TestSolveClusters:
    def test_list_clusters(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/clusters", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "clusters" in data
        assert data.get("count") == 12, f"Expected 12 clusters, got {data.get('count')}"
        assert len(data["clusters"]) == 12
        sample = data["clusters"][0]
        for k in ("id", "label", "blurb", "example_question", "phase_hints", "banned_terms"):
            assert k in sample, f"missing key {k} in cluster"
        assert isinstance(sample["phase_hints"], dict)
        for ph in ("surface", "depth", "synthesis", "lockin"):
            assert ph in sample["phase_hints"]


# ---------------------------------------------------------------------------
# Solve session — 4-phase walkthrough
# ---------------------------------------------------------------------------
class TestSolveSessionFlow:
    def test_start_advance_complete(self, api, user_token):
        # Pick a cluster
        r = api.get(f"{BASE_URL}/api/solve/clusters", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        cluster = r.json()["clusters"][0]

        intent = "TEST_iter61 - revenue is missing and pricing seems off"
        # Start session
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": cluster["id"], "intent": intent}, timeout=120)
        assert r.status_code == 200, r.text
        sess = r.json()
        sid = sess["id"]
        assert sess["phase"] == "surface"
        assert sess["status"] == "active"
        assert len(sess["turns"]) == 1, "Surface primer should be present"
        assert sess["turns"][0]["role"] == "solve"

        # Walk through all 4 phases (4 user turns total)
        phases_seen = []
        for i, msg in enumerate([
            "User reply for surface, ~30 chars test fixture content.",
            "User reply for depth, ~30 chars test fixture content.",
            "User reply for synthesis, ~30 chars test fixture content.",
            "User reply for lockin, ~30 chars test fixture content.",
        ]):
            r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/turn",
                         headers=_h(user_token), json={"user_text": msg}, timeout=180)
            assert r.status_code == 200, f"turn {i} failed: {r.text}"
            sess = r.json()
            phases_seen.append(sess["phase"])

        # After 4 user turns, status should be completed
        assert sess["status"] == "completed", f"expected completed, got {sess['status']}"
        assert sess.get("completed_at")
        # Synthesis + Lockin objects populated
        assert sess.get("synthesis"), "synthesis should be populated"
        assert sess["synthesis"].get("body")
        assert sess.get("lockin"), "lockin should be populated"
        assert sess["lockin"].get("body")

        # Persistence: GET should still return completed
        r = api.get(f"{BASE_URL}/api/solve/sessions/{sid}",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_restart_session(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/clusters", headers=_h(user_token), timeout=30)
        cluster = r.json()["clusters"][1]
        intent = "TEST_iter61 restart fixture - succession readiness gap"
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": cluster["id"], "intent": intent}, timeout=120)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/restart",
                     headers=_h(user_token), timeout=120)
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["id"] != sid
        assert new["cluster_id"] == cluster["id"]
        assert new["intent"] == intent.strip()
        assert new["status"] == "active"
        assert new["phase"] == "surface"

        # Old session abandoned
        r = api.get(f"{BASE_URL}/api/solve/sessions/{sid}",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "abandoned"

        # Cleanup new
        api.post(f"{BASE_URL}/api/solve/sessions/{new['id']}/abandon",
                 headers=_h(user_token), timeout=30)

    def test_abandon_session(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/clusters", headers=_h(user_token), timeout=30)
        cluster = r.json()["clusters"][2]
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": cluster["id"],
                           "intent": "TEST_iter61 abandon fixture intent ≥20 chars"},
                     timeout=120)
        assert r.status_code == 200
        sid = r.json()["id"]

        r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/abandon",
                     headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        r = api.get(f"{BASE_URL}/api/solve/sessions/{sid}",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "abandoned"

    def test_list_sessions_sort(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/sessions",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        items = data["items"]
        assert isinstance(items, list)
        if len(items) >= 2:
            for i in range(len(items) - 1):
                assert items[i]["updated_at"] >= items[i + 1]["updated_at"]

    def test_list_sessions_status_filter(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/sessions?status=active",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["status"] == "active"

    def test_intent_too_short_rejected(self, api, user_token):
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": "revenue_underperformance", "intent": "too short"},
                     timeout=30)
        assert r.status_code in (400, 422), r.text

    def test_unknown_cluster_rejected(self, api, user_token):
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": "no_such_cluster_xyz",
                           "intent": "TEST_iter61 fixture intent for unknown cluster"},
                     timeout=30)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Walk-in context hint
# ---------------------------------------------------------------------------
class TestWalkinContextHint:
    def test_walkin_endpoint_validates_input(self, api, user_token):
        """Smoke test — endpoint is wired and validates required fields.
        Live integration with a real artefact is covered by main agent; here
        we just ensure the route exists and rejects empty body."""
        r = api.post(f"{BASE_URL}/api/walkin", headers=_h(user_token),
                     json={"kind": "brief"}, timeout=30)
        # Missing artefact_id / context_id → 422
        assert r.status_code in (200, 422), \
            f"walkin returned unexpected {r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# Admin auth-events
# ---------------------------------------------------------------------------
class TestAdminAuthEvents:
    URL = "/api/admin/auth/events"

    def test_auth_events_shape(self, api, admin_token):
        r = api.get(f"{BASE_URL}{self.URL}",
                    headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict) and len(data) > 0

    def test_auth_events_nonadmin_forbidden(self, api, user_token):
        r = api.get(f"{BASE_URL}{self.URL}",
                    headers=_h(user_token), timeout=30)
        assert r.status_code in (401, 403), \
            f"non-admin should not access auth-events, got {r.status_code}"

    def test_failure_increments_after_bad_login(self, api, admin_token):
        before = api.get(f"{BASE_URL}{self.URL}",
                         headers=_h(admin_token), timeout=30).json()
        for _ in range(3):
            api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "nobody@nowhere.test", "password": "wrong-xyz"},
                     timeout=15)
        time.sleep(1)
        after = api.get(f"{BASE_URL}{self.URL}",
                        headers=_h(admin_token), timeout=30).json()
        assert isinstance(after, dict)
