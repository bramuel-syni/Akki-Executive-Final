"""Iter9 refactor smoke — confirms auth, contexts, documents, misc routers
all expose the paths they used to before the server.py refactor.
Hits public REACT_APP_BACKEND_URL; no mocks."""
import os
import io
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def me(session):
    r = session.get(f"{BASE_URL}/auth/me", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "account" in body and "contexts" in body
    assert len(body["contexts"]) >= 1
    return body


@pytest.fixture(scope="module")
def ctx_id(me):
    # Use Tuli Financial Group if present, else first context
    for c in me["contexts"]:
        if "Tuli" in c.get("name", ""):
            return c["id"]
    return me["contexts"][0]["id"]


# ----- misc router -----
def test_root_api():
    r = requests.get(f"{BASE_URL}/", timeout=15)
    assert r.status_code == 200


def test_health():
    r = requests.get(f"{BASE_URL}/health", timeout=15)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ----- auth router (register + me) -----
def test_register_new_account_then_me():
    s = requests.Session()
    unique = uuid.uuid4().hex[:10]
    email = f"TEST_iter9_{unique}@akki.ai"
    r = s.post(f"{BASE_URL}/auth/register",
               json={"email": email, "password": "TestPass2026!", "name": "TEST Iter9"},
               timeout=30)
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
    r2 = s.get(f"{BASE_URL}/auth/me", timeout=15)
    assert r2.status_code == 200
    body = r2.json()
    assert body["account"]["email"].lower() == email.lower()
    assert len(body["contexts"]) >= 1


def test_auth_me_existing(me):
    assert me["account"]["email"].lower() == EMAIL.lower()


# ----- contexts router -----
def test_get_context(session, ctx_id):
    r = session.get(f"{BASE_URL}/contexts/{ctx_id}", timeout=15)
    assert r.status_code == 200
    assert r.json()["id"] == ctx_id


def test_list_members(session, ctx_id):
    r = session.get(f"{BASE_URL}/contexts/{ctx_id}/members", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_invitations(session, ctx_id):
    r = session.get(f"{BASE_URL}/contexts/{ctx_id}/invitations", timeout=15)
    assert r.status_code == 200


# ----- documents router -----
def test_document_upload_list_download(session, ctx_id):
    payload = f"TEST iter9 refactor smoke {uuid.uuid4().hex[:6]}"
    files = {"file": ("TEST_iter9_smoke.txt", io.BytesIO(payload.encode()), "text/plain")}
    data = {"display_name": "TEST iter9 smoke", "data_trust": "trusted"}
    r = session.post(f"{BASE_URL}/contexts/{ctx_id}/documents", files=files, data=data, timeout=30)
    assert r.status_code in (200, 201), f"upload: {r.status_code} {r.text}"
    doc = r.json()
    assert doc["id"]
    # list
    r2 = session.get(f"{BASE_URL}/contexts/{ctx_id}/documents", timeout=15)
    assert r2.status_code == 200
    ids = [d["id"] for d in r2.json()]
    assert doc["id"] in ids
    # download
    r3 = session.get(f"{BASE_URL}/contexts/{ctx_id}/documents/{doc['id']}/download", timeout=15)
    assert r3.status_code == 200


# ----- signals_ask + briefings router shielding regression -----
def test_signals_generate_shielding(session, ctx_id):
    r = session.post(f"{BASE_URL}/contexts/{ctx_id}/signals/generate", json={"horizon": "30d"}, timeout=90)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    body = r.json()
    shielding = body.get("shielding")
    assert isinstance(shielding, dict), f"missing shielding dict, got keys={list(body.keys())}"
    assert "identifiers_masked" in shielding
    assert "by_category" in shielding
    assert "shielded_by" in shielding


def test_ask_shielding(session, ctx_id):
    r = session.post(f"{BASE_URL}/contexts/{ctx_id}/ask",
                     json={"question": "What are the top risks right now?"}, timeout=90)
    assert r.status_code == 200
    body = r.json()
    shielding = body.get("shielding")
    assert isinstance(shielding, dict)
    assert "by_category" in shielding


def test_briefing_shielding(session, ctx_id):
    r = session.post(f"{BASE_URL}/contexts/{ctx_id}/briefings",
                     json={"horizon": "weekly"}, timeout=90)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("shielding"), dict)
    assert "by_category" in body["shielding"]
