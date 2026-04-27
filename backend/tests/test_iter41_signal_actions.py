"""Iter41 backend tests — Signal action recommendations + tracking.

Covers:
  GET  /api/contexts/{cid}/signals/{sid}/recommendations
  POST /api/contexts/{cid}/signals/{sid}/actions  (acted | shared)
  GET  /api/contexts/{cid}/signals/{sid}/actions  (summary aggregation)
  Tenancy: 404 on signal not in ctx; 422 on invalid action_type.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
USER = {"email": "bramuel@syni.ai", "password": "TestBramuel2026!"}
TULI_CTX = "fb4df969-3f17-4279-bf78-f07bb9e29650"


def _login(payload):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:120]}")
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def client():
    return _login(USER)


@pytest.fixture(scope="module")
def signal_id(client):
    """Find a real signal in the Tuli ctx to exercise endpoints against."""
    r = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals?limit=5")
    if r.status_code != 200:
        pytest.skip(f"Cannot list signals: {r.status_code}")
    items = r.json() if isinstance(r.json(), list) else r.json().get("signals", [])
    if not items:
        pytest.skip("No signals available in Tuli ctx")
    return items[0]["id"]


# ---------------------------------------------------------------------------
# 1. Recommendations endpoint — shape + bucket inference
# ---------------------------------------------------------------------------
class TestRecommendations:
    def test_recommendations_shape(self, client, signal_id):
        r = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/recommendations")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "bucket" in d and "recommendations" in d
        assert d["bucket"] in ("risk", "opportunity", "gap", "neutral")
        assert isinstance(d["recommendations"], list)
        assert len(d["recommendations"]) == 3
        for rec in d["recommendations"]:
            assert "label" in rec and "note" in rec
            assert isinstance(rec["label"], str) and len(rec["label"]) > 0
            assert isinstance(rec["note"], str) and len(rec["note"]) > 0

    def test_recommendations_404_for_unknown_signal(self, client):
        bogus = f"unknown-{uuid.uuid4().hex[:8]}"
        r = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{bogus}/recommendations")
        assert r.status_code == 404

    def test_bucket_inference_per_known_buckets(self, client, signal_id):
        """Across signals, we should see at least the neutral bucket
        produced for the seeded ubora signals (no headline). Sanity check
        that the bucket list is one of the four valid buckets."""
        r = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/recommendations")
        assert r.json()["bucket"] in {"risk", "opportunity", "gap", "neutral"}


# ---------------------------------------------------------------------------
# 2. Action logging — POST + GET aggregation
# ---------------------------------------------------------------------------
class TestActionLogging:
    def test_acted_resolves_label_from_idx(self, client, signal_id):
        # Use index 1 to log; server should resolve label from templates
        r = client.post(
            f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions",
            json={"action_type": "acted", "recommendation_idx": 1, "note": "TEST_iter41 acted"},
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["action_type"] == "acted"
        assert doc["recommendation_idx"] == 1
        assert doc["recommendation_label"]  # resolved server-side
        assert doc["note"] == "TEST_iter41 acted"

        # Verify summary picks this up
        sr = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions")
        assert sr.status_code == 200
        s = sr.json()["summary"]
        assert s["acted"] is True
        assert s["last_acted_label"] == doc["recommendation_label"]
        assert s["last_acted_at"]

    def test_shared_unique_recipient_count(self, client, signal_id):
        # Share twice with overlapping recipients — count should de-dupe
        before = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions").json()["summary"]
        baseline_recipients = set(before.get("shared_with") or [])

        unique_a = f"test_iter41_a_{uuid.uuid4().hex[:6]}@example.com"
        unique_b = f"test_iter41_b_{uuid.uuid4().hex[:6]}@example.com"

        r1 = client.post(
            f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions",
            json={"action_type": "shared", "recipients": [unique_a, unique_b]},
        )
        assert r1.status_code == 200
        # Share again to same recipient_a only — should not double count
        r2 = client.post(
            f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions",
            json={"action_type": "shared", "recipients": [unique_a]},
        )
        assert r2.status_code == 200

        sr = client.get(f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions").json()
        s = sr["summary"]
        # Both new recipients should be present, count went up by exactly 2 (unique)
        assert unique_a in s["shared_with"]
        assert unique_b in s["shared_with"]
        new_unique = set(s["shared_with"]) - baseline_recipients
        assert {unique_a, unique_b}.issubset(new_unique)
        assert s["shared_count"] == len(set(s["shared_with"]))

    def test_invalid_action_type_422(self, client, signal_id):
        r = client.post(
            f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions",
            json={"action_type": "deleted"},
        )
        assert r.status_code == 422

    def test_note_max_length(self, client, signal_id):
        r = client.post(
            f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{signal_id}/actions",
            json={"action_type": "acted", "recommendation_idx": 0, "note": "x" * 601},
        )
        assert r.status_code == 422

    def test_action_404_for_unknown_signal(self, client):
        bogus = f"unknown-{uuid.uuid4().hex[:8]}"
        r = client.post(
            f"{BASE_URL}/api/contexts/{TULI_CTX}/signals/{bogus}/actions",
            json={"action_type": "acted", "recommendation_idx": 0},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3. Tenancy — bogus context id should 401/403 (not 200)
# ---------------------------------------------------------------------------
class TestTenancy:
    def test_unknown_context_blocked(self, client, signal_id):
        bogus_ctx = uuid.uuid4().hex
        r = client.get(f"{BASE_URL}/api/contexts/{bogus_ctx}/signals/{signal_id}/recommendations")
        assert r.status_code in (401, 403, 404)
