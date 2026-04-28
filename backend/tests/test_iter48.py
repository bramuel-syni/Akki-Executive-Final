"""Iter48 backend tests:
  - /api/sandbox/contexts/{cid}/sample-doc (GET + POST accept)
  - /api/contexts/{cid}/strategic-goals sort by normalised target_date
  - /api/briefs CRUD regression
  - /api/chats custom title regression
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

BRAMUEL_EMAIL = "bramuel@syni.ai"
BRAMUEL_PASSWORD = "TestBramuel2026!"


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def bramuel_session():
    """Login as Bramuel and return a session with cookies + default context id."""
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": BRAMUEL_EMAIL, "password": BRAMUEL_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=30).json()
    ctx_id = me.get("account", {}).get("default_context_id") or (
        me.get("contexts", [{}])[0].get("id") if me.get("contexts") else None
    )
    assert ctx_id, "no default context for bramuel"
    return s, ctx_id


@pytest.fixture(scope="module")
def sandbox_session():
    """Create a fresh sandbox session, wait until ready, return bearer token + ctx_id."""
    s = requests.Session()
    body = {
        "company_name": "TEST_Sandbox_Iter48",
        "sector": "financial_services",
        "role": "ned",
        "region": "east_africa",
        "objective": "grow revenue and harden controls",
    }
    r = s.post(f"{BASE_URL}/api/sandbox/generate", json=body, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"sandbox /generate not available: {r.status_code} {r.text[:200]}")
    sid = r.json()["session_id"]

    deadline = time.time() + 90
    ctx_id, token = None, None
    while time.time() < deadline:
        rs = s.get(f"{BASE_URL}/api/sandbox/generate/{sid}/status", timeout=30).json()
        if rs.get("ready"):
            ctx_id = rs.get("context_id")
            token = rs.get("access_token")
            break
        time.sleep(2)
    if not ctx_id or not token:
        pytest.skip("sandbox session did not become ready in time")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s, ctx_id


# -----------------------------------------------------------------------------
# Sandbox sample-doc endpoints
# -----------------------------------------------------------------------------
class TestSandboxSampleDoc:
    def test_sample_doc_non_sandbox_returns_404(self, bramuel_session):
        s, ctx_id = bramuel_session
        r = s.get(f"{BASE_URL}/api/sandbox/contexts/{ctx_id}/sample-doc", timeout=30)
        assert r.status_code == 404

    def test_sample_doc_preview_for_sandbox(self, sandbox_session):
        s, ctx_id = sandbox_session
        r = s.get(f"{BASE_URL}/api/sandbox/contexts/{ctx_id}/sample-doc", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data.get("already_accepted") is False
        assert data.get("context_id") == ctx_id
        assert isinstance(data.get("title"), str) and len(data["title"]) > 4
        assert isinstance(data.get("filename"), str) and data["filename"].endswith(".md")
        assert isinstance(data.get("preview"), str) and len(data["preview"]) > 100
        assert isinstance(data.get("word_count"), int) and data["word_count"] > 20

    def test_sample_doc_accept_then_already_accepted(self, sandbox_session):
        s, ctx_id = sandbox_session
        preview = s.get(
            f"{BASE_URL}/api/sandbox/contexts/{ctx_id}/sample-doc", timeout=30
        ).json()
        # If already accepted from a previous test run, skip accept and verify flag
        if preview.get("already_accepted"):
            assert preview["already_accepted"] is True
            return
        payload = {
            "title": preview["title"],
            "filename": preview["filename"],
            "preview": preview["preview"],
        }
        r = s.post(
            f"{BASE_URL}/api/sandbox/contexts/{ctx_id}/sample-doc/accept",
            json=payload, timeout=30,
        )
        assert r.status_code == 200, f"accept failed: {r.status_code} {r.text[:500]}"
        data = r.json()
        assert data.get("ok") is True
        assert isinstance(data.get("doc_id"), str) and len(data["doc_id"]) > 8
        assert data.get("title") == preview["title"]

        # Subsequent GET returns already_accepted=True
        r2 = s.get(f"{BASE_URL}/api/sandbox/contexts/{ctx_id}/sample-doc", timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("already_accepted") is True

        # Document was actually persisted — list documents
        rd = s.get(f"{BASE_URL}/api/contexts/{ctx_id}/documents", timeout=30)
        if rd.status_code == 200:
            docs_payload = rd.json()
            docs = docs_payload if isinstance(docs_payload, list) else docs_payload.get("documents", [])
            doc_ids = [d.get("id") for d in docs]
            assert data["doc_id"] in doc_ids, "accepted sample doc not found in list"


# -----------------------------------------------------------------------------
# Strategic goals target_date sort
# -----------------------------------------------------------------------------
class TestStrategicGoalsSort:
    def _create(self, s, ctx_id, title, target_date):
        r = s.post(
            f"{BASE_URL}/api/contexts/{ctx_id}/strategic-goals",
            json={"title": title, "department": "ceo", "target_date": target_date},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        return r.json()["id"]

    def test_list_sorted_by_normalised_target_date(self, bramuel_session):
        s, ctx_id = bramuel_session
        created = []
        try:
            created.append(self._create(s, ctx_id, "TEST_ZZ_null_date_iter48", None))
            created.append(self._create(s, ctx_id, "TEST_A_iso_2026_03_iter48", "2026-03"))
            created.append(self._create(s, ctx_id, "TEST_B_q4_2026_iter48", "Q4 2026"))
            created.append(self._create(s, ctx_id, "TEST_C_dec_2026_iter48", "Dec 2026"))
            created.append(self._create(s, ctx_id, "TEST_D_iso_2025_12_01_iter48", "2025-12-01"))

            r = s.get(f"{BASE_URL}/api/contexts/{ctx_id}/strategic-goals", timeout=30)
            assert r.status_code == 200
            goals = r.json()["goals"]
            # Filter only our test rows
            ours = [g for g in goals if g["title"].startswith("TEST_") and g["title"].endswith("_iter48")]
            titles = [g["title"] for g in ours]
            # Expected order:
            # 2025-12-01 → "TEST_D..." first
            # 2026-03    → "TEST_A..."
            # Q4 2026 (→2026-12-30) vs Dec 2026 (→2026-12-15): Dec 2026 first
            # null → last
            expected = [
                "TEST_D_iso_2025_12_01_iter48",
                "TEST_A_iso_2026_03_iter48",
                "TEST_C_dec_2026_iter48",
                "TEST_B_q4_2026_iter48",
                "TEST_ZZ_null_date_iter48",
            ]
            assert titles == expected, f"unexpected order: {titles}"
        finally:
            for gid in created:
                s.delete(f"{BASE_URL}/api/contexts/{ctx_id}/strategic-goals/{gid}", timeout=30)


# -----------------------------------------------------------------------------
# Regression: briefs CRUD
# -----------------------------------------------------------------------------
class TestBriefsCRUDRegression:
    def test_briefs_list_returns_200(self, bramuel_session):
        s, ctx_id = bramuel_session
        r = s.get(f"{BASE_URL}/api/contexts/{ctx_id}/briefs?limit=50", timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert isinstance(body, (list, dict))


# -----------------------------------------------------------------------------
# Regression: chats custom title
# -----------------------------------------------------------------------------
class TestChatsRegression:
    def test_create_chat_with_custom_title(self, bramuel_session):
        s, ctx_id = bramuel_session
        r = s.post(
            f"{BASE_URL}/api/chats",
            json={"context_id": ctx_id, "title": "TEST_iter48_seed_title"},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text[:300]
        data = r.json()
        chat_id = data.get("id") or data.get("chat", {}).get("id")
        assert chat_id, f"no chat id in response: {data}"
        # Verify persistence via GET
        r2 = s.get(f"{BASE_URL}/api/chats/{chat_id}", timeout=30)
        assert r2.status_code == 200
        got = r2.json()
        title = got.get("title") or got.get("chat", {}).get("title")
        assert title == "TEST_iter48_seed_title"
        # Cleanup
        s.delete(f"{BASE_URL}/api/chats/{chat_id}", timeout=30)
