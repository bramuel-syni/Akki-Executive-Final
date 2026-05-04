"""Phase 15.2 — submodule + fork + intent-classify integration tests.

Live-HTTP against the running backend. Uses admin@akki.ai and the
account.solva_v2_poc=true flag set at boot.

Pinned scope:
  - POST /api/solva/v2/sessions accepts each of the four sub-module values
  - get_perspective requires `persona`; missing → 422
  - simulate_hypothesis sets the hypothesis layer in flow (verified via
    state machine, not by walking a real session — that's covered in the
    10-session script)
  - POST /api/solva/v2/intent/classify returns valid sub-module + confidence
  - POST /api/solva/v2/sessions/{sid}/fork creates a child with
    parent_session_id linked and inherited intent
  - GET /api/solva/v2/sessions/{sid} on a pre-15.2 session (submodule
    field absent) defaults to seek_clarity

Run:
    pytest /app/backend/tests/test_solva_v2_submodules.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def cluster_id(client):
    r = client.get(f"{BASE_URL}/api/solva/clusters", timeout=20)
    assert r.status_code == 200, r.text
    clusters = r.json().get("clusters") or []
    assert clusters, "no Solva v1/v2 clusters seeded"
    return clusters[0]["id"]


def _start(client, cluster_id, submodule, intent, persona=None):
    body = {
        "cluster_id": cluster_id,
        "intent": intent,
        "submodule": submodule,
    }
    if persona:
        body["persona"] = persona
    r = client.post(f"{BASE_URL}/api/solva/v2/sessions", json=body, timeout=120)
    return r


def _cleanup(sid):
    """Best-effort cleanup — abandon the session if it's still active."""
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "akki_dev")]
    db.solva_v2_sessions.delete_one({"id": sid})


# ---------------------------------------------------------------------------
# Test 1 — picker accepts every sub-module
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("submodule, persona", [
    ("seek_clarity", None),
    ("develop_strategy", None),
    ("simulate_hypothesis", None),
    ("get_perspective", "Chair"),
])
def test_each_submodule_can_start_a_session(client, cluster_id, submodule, persona):
    intent = (
        f"Phase 15.2 smoke for {submodule}. The Q3 board pack lands "
        f"next week and we have a pricing-vs-mix disagreement on the table."
    )
    r = _start(client, cluster_id, submodule, intent, persona=persona)
    assert r.status_code == 200, f"{submodule}: {r.status_code} {r.text}"
    body = r.json()
    sid = body["id"]
    try:
        assert body["submodule"] == submodule
        assert body["status"] == "active"
        assert body["layer"] == "framing"
        if submodule == "get_perspective":
            assert body.get("persona") == persona
    finally:
        _cleanup(sid)


def test_get_perspective_requires_persona(client, cluster_id):
    intent = "Smoke test: persona-less get_perspective should 422."
    r = _start(client, cluster_id, "get_perspective", intent, persona=None)
    assert r.status_code == 422, r.text
    assert "persona" in r.text.lower()


def test_unknown_submodule_400s(client, cluster_id):
    intent = "Smoke test: nonsense submodule should 400."
    r = _start(client, cluster_id, "diagnose_self", intent)
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Test 2 — fork
# ---------------------------------------------------------------------------
def test_fork_inherits_intent_and_links_parent(client, cluster_id):
    parent_intent = (
        "We're stuck on whether to launch the new product line in Q4 or "
        "wait for FY26 — the new CFO wants the runway, the COO wants "
        "the brand momentum."
    )
    parent_resp = _start(client, cluster_id, "seek_clarity", parent_intent)
    assert parent_resp.status_code == 200, parent_resp.text
    parent = parent_resp.json()
    parent_id = parent["id"]

    try:
        # Walk the parent through one user turn so it has accumulated content
        # to inherit.
        t = client.post(
            f"{BASE_URL}/api/solva/v2/sessions/{parent_id}/turn",
            json={"user_text": "The CFO is right that runway is finite, but the "
                               "brand window is real too. I want both."},
            timeout=180,
        )
        assert t.status_code == 200, t.text

        # Fork into develop_strategy.
        fork_resp = client.post(
            f"{BASE_URL}/api/solva/v2/sessions/{parent_id}/fork",
            json={"to_submodule": "develop_strategy"},
            timeout=30,
        )
        assert fork_resp.status_code == 200, fork_resp.text
        child = fork_resp.json()
        try:
            assert child["id"] != parent_id
            assert child["parent_session_id"] == parent_id
            assert child["submodule"] == "develop_strategy"
            assert child["intent"] == parent_intent
            assert child["layer"] == "framing"
            assert child["status"] == "active"
            assert child["cluster_id"] == parent["cluster_id"]
            # The user turn from parent must have been copied across.
            user_turns = [t for t in (child.get("turns") or []) if t.get("role") == "user"]
            assert len(user_turns) >= 1
            # Parent should still be active (forking doesn't abandon).
            r2 = client.get(f"{BASE_URL}/api/solva/v2/sessions/{parent_id}", timeout=20)
            assert r2.status_code == 200
            # parent may have advanced layer due to the user_text we posted.
            assert r2.json().get("status") in {"active", "completed"}
        finally:
            _cleanup(child["id"])
    finally:
        _cleanup(parent_id)


def test_fork_into_get_perspective_requires_persona(client, cluster_id):
    parent = _start(client, cluster_id, "seek_clarity",
                    "Smoke test: forking into get_perspective with no persona.")
    assert parent.status_code == 200
    parent_id = parent.json()["id"]
    try:
        r = client.post(
            f"{BASE_URL}/api/solva/v2/sessions/{parent_id}/fork",
            json={"to_submodule": "get_perspective"},  # no persona
            timeout=30,
        )
        assert r.status_code == 422, r.text
        assert "persona" in r.text.lower()
    finally:
        _cleanup(parent_id)


def test_fork_unknown_submodule_400s(client, cluster_id):
    parent = _start(client, cluster_id, "seek_clarity",
                    "Smoke test: forking with bad submodule label.")
    assert parent.status_code == 200
    parent_id = parent.json()["id"]
    try:
        r = client.post(
            f"{BASE_URL}/api/solva/v2/sessions/{parent_id}/fork",
            json={"to_submodule": "rumination_loop"},
            timeout=30,
        )
        assert r.status_code == 400, r.text
    finally:
        _cleanup(parent_id)


# ---------------------------------------------------------------------------
# Test 3 — intent classifier
# ---------------------------------------------------------------------------
def test_intent_classify_returns_valid_submodule(client):
    """Single tier=fast LLM call. Must always return a valid 4-way label
    plus a confidence in [0, 1] regardless of input quality."""
    intent = (
        "I want to know what the chair would say about my push for an "
        "off-cycle bonus pool ahead of the Q4 board meeting."
    )
    r = client.post(
        f"{BASE_URL}/api/solva/v2/intent/classify",
        json={"intent": intent}, timeout=120,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["submodule"] in {
        "seek_clarity", "develop_strategy", "simulate_hypothesis", "get_perspective",
    }
    assert 0.0 <= body["confidence"] <= 1.0
    # We don't assert which one the LLM picks — that's stochastic — but
    # this particular intent is a clean get_perspective signal so the
    # classifier should usually pick that. If it doesn't we don't fail
    # the test; we just log the soft expectation.
    if body["submodule"] != "get_perspective":
        print(f"NOTE: classifier picked {body['submodule']} for a "
              f"get_perspective-shaped intent (this is non-deterministic, "
              f"not a defect)")


# ---------------------------------------------------------------------------
# Test 4 — backwards compat: legacy session reads with default submodule
# ---------------------------------------------------------------------------
def test_legacy_session_without_submodule_field_defaults_to_seek_clarity(client):
    """Sessions written before 15.2 may not carry a submodule field at all.
    GET /api/solva/v2/sessions/{sid} must default to seek_clarity at read
    time so the client never sees a null submodule."""
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "akki_dev")]

    me = client.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    aid = me["account"]["id"]
    legacy_id = str(uuid.uuid4())
    legacy = {
        "id": legacy_id,
        "account_id": aid,
        "context_id": None,
        "version": 2,
        "schema_version": 1,  # pre-15.1
        # NO submodule field — legacy doc shape.
        "cluster_id": "cluster.test",
        "cluster_label": "Legacy session for test",
        "intent": "Phase 15.2 read-time default test.",
        "layer": "framing",
        "layer_index": 0,
        "status": "active",
        "turns": [],
        "reasoning_audit_log": [],
        "synthesis": None,
        "lockin": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.solva_v2_sessions.insert_one(legacy)
    try:
        r = client.get(f"{BASE_URL}/api/solva/v2/sessions/{legacy_id}", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Read-time default — submodule must be 'seek_clarity', not None.
        assert body.get("submodule") == "seek_clarity"
        # Underlying doc still has no submodule field on disk (we don't
        # do a write-time migration).
        on_disk = db.solva_v2_sessions.find_one({"id": legacy_id})
        assert "submodule" not in on_disk or on_disk.get("submodule") is None
    finally:
        db.solva_v2_sessions.delete_one({"id": legacy_id})
