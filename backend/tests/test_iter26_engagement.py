"""Iter 26 — Agenda Evolution + Document Engagement (read receipts, share, linked).

Covers the two new routers introduced in this batch:
  • /api/contexts/{cid}/agenda-evolution
  • /api/contexts/{cid}/documents/{doc_id}/{view, share, engagement}
"""
import os
import pytest
import requests

def _read_react_url():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_react_url()).rstrip("/")
assert BASE_URL.startswith("http"), f"BASE_URL not configured: {BASE_URL!r}"
CTX_ID = "2ceb9fde-a202-4891-adb1-ecf47dfe2258"  # Tuli CFO (Bramuel exec)

OWNER = {"email": "bramuel@syni.ai", "password": "TestBramuel2026!"}
OTHER = {"email": "admin@akki.ai", "password": "AkkiAdmin2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def owner_session():
    return _login(OWNER)


@pytest.fixture(scope="module")
def doc_id(owner_session):
    r = owner_session.get(f"{BASE_URL}/api/contexts/{CTX_ID}/documents", timeout=20)
    assert r.status_code == 200
    docs = r.json()
    if not docs:
        pytest.skip("No documents seeded in Tuli CFO context")
    return docs[0]["id"]


# ------------------- Agenda Evolution -------------------
class TestAgendaEvolution:
    def test_get_agenda_evolution_shape(self, owner_session):
        r = owner_session.get(f"{BASE_URL}/api/contexts/{CTX_ID}/agenda-evolution", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "last_meeting" in data
        assert "since_then" in data
        assert "next_up" in data
        assert isinstance(data["since_then"], list)

    def test_agenda_evolution_unauth(self):
        r = requests.get(f"{BASE_URL}/api/contexts/{CTX_ID}/agenda-evolution", timeout=20)
        assert r.status_code in (401, 403)


# ------------------- Document Engagement -------------------
class TestDocumentEngagement:
    def test_view_record_and_dedupe(self, owner_session, doc_id):
        url = f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{doc_id}/view"
        r1 = owner_session.post(url, timeout=20)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1.get("ok") is True
        # Second call same day should dedupe
        r2 = owner_session.post(url, timeout=20)
        assert r2.status_code == 200
        assert r2.json().get("deduped") is True

    def test_view_unauth_blocked(self, doc_id):
        r = requests.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{doc_id}/view", timeout=20
        )
        assert r.status_code in (401, 403)

    def test_view_invalid_doc(self, owner_session):
        r = owner_session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/non-existent-id/view", timeout=20
        )
        assert r.status_code == 404

    def test_share_record(self, owner_session, doc_id):
        r = owner_session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{doc_id}/share",
            json={
                "to_email": "TEST_share@example.com",
                "to_name": "Test Recipient",
                "message": "FYI from iter26 test",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec.get("shared_with_email") == "TEST_share@example.com"
        assert rec.get("doc_id") == doc_id
        assert "id" in rec

    def test_share_invalid_email(self, owner_session, doc_id):
        r = owner_session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{doc_id}/share",
            json={"to_email": "not-an-email"},
            timeout=20,
        )
        assert r.status_code == 422

    def test_engagement_summary_excludes_owner(self, owner_session, doc_id):
        r = owner_session.get(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{doc_id}/engagement", timeout=20
        )
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("view_count", "unique_readers", "readers", "share_count",
                  "shares", "linked_count", "linked_documents"):
            assert k in data, f"missing key {k}"
        # Owner views should not count as unique readers
        owner_emails = [r.get("email") for r in data["readers"]]
        assert OWNER["email"] not in owner_emails, "owner should be excluded from readers"
        # Share recorded earlier should be visible
        assert data["share_count"] >= 1
        emails = [s["shared_with_email"] for s in data["shares"]]
        assert "TEST_share@example.com" in emails

    def test_engagement_unauth_blocked(self, doc_id):
        r = requests.get(
            f"{BASE_URL}/api/contexts/{CTX_ID}/documents/{doc_id}/engagement", timeout=20
        )
        assert r.status_code in (401, 403)
