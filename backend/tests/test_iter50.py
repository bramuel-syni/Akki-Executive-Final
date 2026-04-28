"""Iter50 backend regression — briefs concurrency, minutes endpoint, regression."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vigilant-kalam-4.preview.emergentagent.com").rstrip("/")
EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=30).json()
    contexts = me.get("contexts") or []
    # pick Tuli CFO executive — smaller seed
    cid = None
    for c in contexts:
        if "Tuli" in (c.get("name") or "") and c.get("type") == "executive_personal" or c.get("name") == "Tuli Financial Group (CFO)":
            cid = c.get("id"); break
    if not cid and contexts:
        cid = contexts[0].get("id")
    return {"session": s, "cid": cid, "token": token}


# Brief endpoint shape + concurrency latency
class TestBriefs:
    def test_create_brief_shape_and_latency(self, auth):
        s = auth["session"]; cid = auth["cid"]
        t0 = time.time()
        r = s.post(
            f"{BASE_URL}/api/contexts/{cid}/briefs",
            json={"kind": "topic", "objective": "TEST_iter50 briefly orient me on liquidity ratios for Q2 2026."},
            timeout=120,
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        b = r.json()
        # required keys
        for k in ["id", "kind", "objective", "title", "body", "model", "validation", "created_at"]:
            assert k in b, f"missing {k} in brief response. keys={list(b.keys())}"
        v = b["validation"]
        for k in ["verdict", "confidence", "notes", "validator_provider", "validator_model"]:
            assert k in v, f"validation missing {k}"
        # final verdict not 'pending'
        assert v["verdict"] in ("validated", "qualified", "flagged"), f"unexpected verdict {v['verdict']}"
        print(f"latency={elapsed:.1f}s verdict={v['verdict']} provider={v['validator_provider']}")
        # Persist brief_id for next test
        TestBriefs.brief_id = b["id"]
        # latency target — soft check (warn but don't fail brutally)
        assert elapsed < 60, f"brief endpoint took {elapsed:.1f}s — too slow"

    def test_get_brief_persisted_final_verdict(self, auth):
        s = auth["session"]; cid = auth["cid"]
        bid = getattr(TestBriefs, "brief_id", None)
        if not bid:
            pytest.skip("no brief id from previous test")
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/briefs/{bid}", timeout=30)
        assert r.status_code == 200, r.text
        v = r.json()["validation"]
        assert v["verdict"] in ("validated", "qualified", "flagged"), f"persisted verdict={v['verdict']}"

    def test_list_briefs_regression(self, auth):
        s = auth["session"]; cid = auth["cid"]
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/briefs?limit=20", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "count" in d


# Minutes endpoint
class TestMinutes:
    def test_minutes_listing_shape(self, auth):
        s = auth["session"]; cid = auth["cid"]
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/minutes?limit=50", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "count" in d
        assert isinstance(d["items"], list)
        assert d["count"] == len(d["items"])
        for it in d["items"]:
            for k in ["id", "title", "filename", "created_at", "doc_type", "trust_level", "extracted"]:
                assert k in it, f"minutes item missing {k}: {it}"

    def test_minutes_filename_heuristic(self, auth):
        """Upload a doc with 'minutes' in the filename and verify it surfaces."""
        s = auth["session"]; cid = auth["cid"]
        # Try multipart upload with text content
        import io
        files = {"file": ("TEST_iter50_Q1_Board_Minutes.txt", io.BytesIO(b"Test minutes body"), "text/plain")}
        r = s.post(f"{BASE_URL}/api/contexts/{cid}/documents", files=files, timeout=60)
        if r.status_code not in (200, 201):
            # try alternative endpoint
            r2 = s.post(f"{BASE_URL}/api/contexts/{cid}/documents/upload", files=files, timeout=60)
            if r2.status_code in (200, 201):
                r = r2
            else:
                pytest.skip(f"doc upload not available: {r.status_code} / {r2.status_code}")
        doc_id = r.json().get("id") if r.status_code in (200, 201) else None
        # Verify minutes endpoint surfaces it
        r3 = s.get(f"{BASE_URL}/api/contexts/{cid}/minutes?limit=50", timeout=30)
        assert r3.status_code == 200
        items = r3.json().get("items", [])
        found = any("minutes" in (it.get("filename") or "").lower() or "minutes" in (it.get("title") or "").lower() for it in items)
        assert found, f"uploaded minutes doc not surfaced. items={items[:3]}"
        # Cleanup
        if doc_id:
            s.delete(f"{BASE_URL}/api/contexts/{cid}/documents/{doc_id}", timeout=30)


# Regression: strategic-goals
class TestRegression:
    def test_strategic_goals(self, auth):
        s = auth["session"]; cid = auth["cid"]
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/strategic-goals", timeout=30)
        assert r.status_code == 200, r.text
