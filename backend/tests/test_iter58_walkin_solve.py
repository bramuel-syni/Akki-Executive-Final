"""Iter58 — backend tests for /api/walkin and /api/solve."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://akki-executive.preview.emergentagent.com").rstrip("/")
EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"
CTX_ID = "fb4df969-3f17-4279-bf78-f07bb9e29650"
DECK_ID = "4fde929d-d9ae-433d-8cc9-bf60fda6eacd"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    return s


# -------- /api/solve --------
class TestSolve:
    def test_get_interest_me_submitted(self, session):
        r = session.get(f"{BASE_URL}/api/solve/interest/me")
        assert r.status_code == 200
        d = r.json()
        # Bramuel previously submitted per main agent
        assert "submitted" in d
        if d["submitted"]:
            assert "interest" in d
            assert d["interest"].get("account_email") == EMAIL

    def test_post_interest_creates_record(self, session):
        r = session.post(f"{BASE_URL}/api/solve/interest", json={"use_case": "TEST_iter58 board NED workflow", "role": "NED"})
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d.get("ok") is True
        assert isinstance(d.get("id"), str) and len(d["id"]) > 8

    def test_get_interest_me_after_post(self, session):
        r = session.get(f"{BASE_URL}/api/solve/interest/me")
        assert r.status_code == 200
        d = r.json()
        assert d["submitted"] is True
        assert d["interest"]["account_email"] == EMAIL

    def test_interest_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/solve/interest", json={})
        assert r.status_code in (401, 403)


# -------- /api/walkin --------
class TestWalkinDeck:
    def test_walkin_deck_cached_first_call(self, session):
        # Deck already has cached walkin per main agent
        r = session.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["ok"] is True
        wq = d["walkin_question"]
        assert "id" in wq and "body" in wq
        assert len(wq["body"]) <= 300
        assert "model" in wq
        assert "generated_at" in wq
        assert "generated_by" in wq

    def test_walkin_deck_idempotent_cached(self, session):
        r1 = session.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID})
        r2 = session.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID})
        assert r1.status_code == 200 and r2.status_code == 200
        # Second call should be cached:true with same id
        d2 = r2.json()
        assert d2.get("cached") is True
        assert d2["walkin_question"]["id"] == r1.json()["walkin_question"]["id"]

    def test_walkin_regenerate_changes_id(self, session):
        before = session.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID}).json()
        time.sleep(0.5)
        r = session.post(f"{BASE_URL}/api/walkin/regenerate", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID})
        assert r.status_code == 200, r.text[:300]
        after = r.json()
        assert after.get("cached") is False
        assert after["walkin_question"]["id"] != before["walkin_question"]["id"]


class TestWalkinValidation:
    def test_invalid_kind_422(self, session):
        r = session.post(f"{BASE_URL}/api/walkin", json={"kind": "garbage", "artefact_id": "x" * 6, "context_id": CTX_ID})
        assert r.status_code == 422

    def test_artefact_not_found_404(self, session):
        r = session.post(f"{BASE_URL}/api/walkin", json={"kind": "brief", "artefact_id": "nonexistent_brief_id_xx", "context_id": CTX_ID})
        assert r.status_code == 404

    def test_not_member_403(self, session):
        # Use a context the user is unlikely a member of
        r = session.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": "00000000-0000-0000-0000-000000000000"})
        # Could be 404 (artefact not found in that ctx) or 403 — both acceptable
        assert r.status_code in (403, 404)

    def test_walkin_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID})
        assert r.status_code in (401, 403)


class TestWalkinPersistence:
    def test_walkin_persisted_on_deck(self, session):
        # Trigger walkin
        r = session.post(f"{BASE_URL}/api/walkin", json={"kind": "deck", "artefact_id": DECK_ID, "context_id": CTX_ID})
        assert r.status_code == 200
        wq_id = r.json()["walkin_question"]["id"]
        # Fetch the deck and verify walkin_question is on artefact
        deck_resp = session.get(f"{BASE_URL}/api/contexts/{CTX_ID}/decks/{DECK_ID}")
        if deck_resp.status_code == 200:
            deck = deck_resp.json()
            assert deck.get("walkin_question", {}).get("id") == wq_id, "walkin_question not persisted on deck"
        else:
            pytest.skip(f"Cannot fetch deck endpoint: {deck_resp.status_code}")
