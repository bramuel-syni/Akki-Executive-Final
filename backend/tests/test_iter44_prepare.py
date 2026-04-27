"""Iter44 Prepare router — on-demand briefs + signal-generation regression.

Covers:
 - GET  /api/prepare/brief-kinds                 (auth'd)
 - POST /api/contexts/{cid}/briefs
 - GET  /api/contexts/{cid}/briefs
 - GET  /api/contexts/{cid}/briefs/{bid}
 - DELETE /api/contexts/{cid}/briefs/{bid}
 - validation: unknown kind -> 422
 - regression: /signals/generate, /briefings reachable, /me/home/stream 200
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vigilant-kalam-4.preview.emergentagent.com").rstrip("/")
EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


@pytest.fixture(scope="module")
def cid(client):
    r = client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert r.status_code == 200
    ctxs = r.json().get("contexts") or []
    # Tuli NED ctx preferred for consistency with other iter reports
    preferred = "fb4df969-3f17-4279-bf78-f07bb9e29650"
    if any(c.get("id") == preferred for c in ctxs):
        return preferred
    assert ctxs, "no contexts"
    return ctxs[0]["id"]


class TestBriefKinds:
    def test_list_kinds(self, client):
        r = client.get(f"{BASE_URL}/api/prepare/brief-kinds", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "kinds" in data
        kinds = data["kinds"]
        assert isinstance(kinds, list) and len(kinds) == 5
        expected_ids = {"claim", "proposal", "topic", "period", "report"}
        assert {k["id"] for k in kinds} == expected_ids
        for k in kinds:
            assert k.get("label") and k.get("blurb")


class TestBriefCRUD:
    created_id = None

    def test_create_brief(self, client, cid):
        payload = {
            "kind": "topic",
            "objective": "TEST_iter44 — two-paragraph orientation on underwriting margin drift.",
        }
        r = client.post(f"{BASE_URL}/api/contexts/{cid}/briefs", json=payload, timeout=90)
        assert r.status_code == 200, f"create brief: {r.status_code} {r.text[:300]}"
        doc = r.json()
        for field in ("id", "kind", "objective", "title", "body", "validated", "created_at"):
            assert field in doc, f"missing field: {field}"
        assert doc["kind"] == "topic"
        assert doc["validated"] is True
        assert isinstance(doc["body"], str) and len(doc["body"].strip()) >= 40
        TestBriefCRUD.created_id = doc["id"]

    def test_list_briefs_contains_created(self, client, cid):
        assert TestBriefCRUD.created_id
        r = client.get(f"{BASE_URL}/api/contexts/{cid}/briefs?limit=20", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "count" in data
        ids = [x["id"] for x in data["items"]]
        assert TestBriefCRUD.created_id in ids
        # Sorted desc by created_at — first item should be the one we just made
        if data["items"]:
            assert data["items"][0]["id"] == TestBriefCRUD.created_id

    def test_get_brief(self, client, cid):
        bid = TestBriefCRUD.created_id
        r = client.get(f"{BASE_URL}/api/contexts/{cid}/briefs/{bid}", timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["id"] == bid

    def test_get_missing_returns_404(self, client, cid):
        r = client.get(f"{BASE_URL}/api/contexts/{cid}/briefs/{uuid.uuid4()}", timeout=20)
        assert r.status_code == 404

    def test_unknown_kind_422(self, client, cid):
        r = client.post(
            f"{BASE_URL}/api/contexts/{cid}/briefs",
            json={"kind": "not-a-kind", "objective": "Why is the sky blue and cloudy today?"},
            timeout=30,
        )
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text[:200]}"

    def test_delete_brief(self, client, cid):
        bid = TestBriefCRUD.created_id
        r = client.delete(f"{BASE_URL}/api/contexts/{cid}/briefs/{bid}", timeout=20)
        assert r.status_code == 200
        # Confirm 404 on re-fetch
        r2 = client.get(f"{BASE_URL}/api/contexts/{cid}/briefs/{bid}", timeout=20)
        assert r2.status_code == 404

    def test_delete_missing_returns_404(self, client, cid):
        r = client.delete(f"{BASE_URL}/api/contexts/{cid}/briefs/{uuid.uuid4()}", timeout=20)
        assert r.status_code == 404


class TestRegression:
    def test_signals_generate_reachable(self, client, cid):
        # Lightweight focus; we only care the endpoint is not broken.
        r = client.post(
            f"{BASE_URL}/api/contexts/{cid}/signals/generate",
            json={"focus": "[Risks the board should notice] TEST_iter44 smoke"},
            timeout=120,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"

    def test_signals_list(self, client, cid):
        r = client.get(f"{BASE_URL}/api/contexts/{cid}/signals?limit=5", timeout=20)
        assert r.status_code == 200

    def test_briefings_list(self, client, cid):
        r = client.get(f"{BASE_URL}/api/contexts/{cid}/briefings", timeout=20)
        assert r.status_code in (200, 204)

    def test_home_stream(self, client):
        r = client.get(f"{BASE_URL}/api/me/home/stream", timeout=20)
        # Accept 200 or 204 depending on empty stream
        assert r.status_code in (200, 204), f"{r.status_code} {r.text[:200]}"
