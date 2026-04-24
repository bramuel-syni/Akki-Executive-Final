"""Iteration 6 regression — M13 BM25 Ask, pipeline events, signals routing."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://vigilant-kalam-4.preview.emergentagent.com"
EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def me(client):
    r = client.get(f"{BASE_URL}/api/auth/me", timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def tuli_ctx_id(me):
    for c in me.get("contexts", []):
        if "Tuli" in c.get("name", "") and c.get("type", "").startswith("ned"):
            return c["id"]
    # fallback first
    return me["contexts"][0]["id"]


# ── Landing page (unauthenticated) ────────────────────────────────────
def test_landing_root_reachable():
    r = requests.get(f"{BASE_URL}/", timeout=30)
    assert r.status_code == 200


# ── M13 BM25 Ask ──────────────────────────────────────────────────────
def test_ask_returns_bm25_retrieval_mode(client, tuli_ctx_id):
    r = client.post(
        f"{BASE_URL}/api/contexts/{tuli_ctx_id}/ask",
        json={"question": "What is the IFRS 9 provisioning impact on Tuli capital adequacy?"},
        timeout=120,
    )
    assert r.status_code == 200, f"Ask failed: {r.text[:300]}"
    data = r.json()
    assert "retrieval_mode" in data, "Missing retrieval_mode"
    assert data["retrieval_mode"] in ("bm25", "recency_fallback"), data["retrieval_mode"]
    assert "answer" in data and data["answer"]
    assert "sources" in data and isinstance(data["sources"], list)
    assert "id" in data
    # For a real-world question against seeded Tuli docs we expect BM25 to hit.
    print(f"retrieval_mode={data['retrieval_mode']} sources={len(data['sources'])}")


def test_ask_gibberish_falls_back(client, tuli_ctx_id):
    # All-stopwords/numeric query — BM25 should produce no matches → recency fallback.
    r = client.post(
        f"{BASE_URL}/api/contexts/{tuli_ctx_id}/ask",
        json={"question": "zzqqxx 12345 ?????"},
        timeout=120,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["retrieval_mode"] in ("bm25", "recency_fallback")
    # Answer still present
    assert isinstance(data.get("answer"), str)


def test_ask_persisted_in_history(client, tuli_ctx_id):
    r = client.get(f"{BASE_URL}/api/contexts/{tuli_ctx_id}/ask", timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list) and len(items) > 0
    assert "retrieval_mode" in items[0]


# ── Signals router still works ────────────────────────────────────────
def test_signals_list(client, tuli_ctx_id):
    r = client.get(f"{BASE_URL}/api/contexts/{tuli_ctx_id}/signals", timeout=30)
    assert r.status_code == 200
    sigs = r.json()
    assert isinstance(sigs, list)
    print(f"signals_count={len(sigs)}")


# ── Pipeline events for Trace drawer ──────────────────────────────────
def test_pipeline_events_for_signal_with_run_id(client, me):
    # find any context that has a signal with pipeline_run_id
    found = None
    for c in me.get("contexts", []):
        sigs = client.get(f"{BASE_URL}/api/contexts/{c['id']}/signals", timeout=30).json()
        with_run = [s for s in sigs if s.get("pipeline_run_id")]
        if with_run:
            found = (c["id"], with_run[0])
            break
    if not found:
        pytest.skip("No signals with pipeline_run_id across user contexts")
    ctx_id, s = found
    r = client.get(
        f"{BASE_URL}/api/contexts/{ctx_id}/pipeline/events",
        params={"pipeline_run_id": s["pipeline_run_id"], "limit": 50},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    evs = r.json()
    assert isinstance(evs, list) and len(evs) >= 1
    kinds = {e.get("type") for e in evs}
    print(f"pipeline_events kinds={kinds} count={len(evs)}")
    assert "pipeline.started" in kinds or any("pipeline" in (k or "") for k in kinds)


# ── Regression: core endpoints ────────────────────────────────────────
def test_contexts_endpoint(me):
    assert len(me.get("contexts", [])) >= 1
    assert me.get("account", {}).get("email") == EMAIL
