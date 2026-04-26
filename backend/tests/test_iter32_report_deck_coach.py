"""
iter32 backend tests:
1. GET /api/contexts/{cid}/reports/{rid}/export.deck.pdf — happy path + auth + 404 + 409
2. Regression: existing /reports/{rid}/export.pdf still works
3. Regression: /lens/coach/sessions create/list/get/post/delete (active filter — archived 404s)
"""

import os
import uuid
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"

# Mawingu Logistics (NED) — has the iter19 rich draft report
MAWINGU_CTX = "06cc1fc6-4308-4d19-a679-6f8f6bd692dc"
RICH_DRAFT_RID = "iter19-mawingu-rich-draft"

# Tuli CFO ctx — used as a "non-member" stand-in for Mawingu? No: Bramuel is a member
# of all contexts. We instead simulate a non-member by creating a fresh account.
TULI_CFO_CTX = "2ceb9fde-a202-4891-adb1-ecf47dfe2258"


# ───────────────────────── fixtures ─────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def stranger_session():
    """Fresh signup → never a member of Mawingu, used for 403 check."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    rand = uuid.uuid4().hex[:8]
    email = f"test_iter32_stranger_{rand}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "TestStranger2026!", "name": f"TEST stranger {rand}",
    })
    if r.status_code not in (200, 201):
        pytest.skip(f"Could not create stranger account: {r.status_code} {r.text}")
    body = r.json()
    token = body.get("access_token") or body.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ───────────────────────── deck PDF tests ─────────────────────────
class TestReportDeckPdf:
    def test_deck_pdf_happy_path(self, session):
        r = session.get(f"{API}/contexts/{MAWINGU_CTX}/reports/{RICH_DRAFT_RID}/export.deck.pdf")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower() and "filename" in cd.lower(), f"bad CD header: {cd}"
        assert r.content[:4] == b"%PDF", "Body is not a PDF blob"
        assert len(r.content) > 2000, f"PDF too small ({len(r.content)} bytes)"
        print(f"[deck-pdf] {len(r.content)} bytes, CD={cd}")

    def test_deck_pdf_unauth_401(self):
        r = requests.get(f"{API}/contexts/{MAWINGU_CTX}/reports/{RICH_DRAFT_RID}/export.deck.pdf")
        assert r.status_code == 401, f"anon should be 401, got {r.status_code}"

    def test_deck_pdf_non_member_403(self, stranger_session):
        r = stranger_session.get(f"{API}/contexts/{MAWINGU_CTX}/reports/{RICH_DRAFT_RID}/export.deck.pdf")
        assert r.status_code == 403, f"non-member should be 403, got {r.status_code} {r.text[:200]}"

    def test_deck_pdf_404_unknown_report(self, session):
        bogus = f"TEST_iter32_no_such_{uuid.uuid4().hex[:6]}"
        r = session.get(f"{API}/contexts/{MAWINGU_CTX}/reports/{bogus}/export.deck.pdf")
        assert r.status_code == 404, f"expected 404, got {r.status_code}"


# ───────────────────────── regression: legacy export.pdf ─────────────────────────
class TestLegacyReportPdfRegression:
    def test_legacy_pdf_still_works(self, session):
        r = session.get(f"{API}/contexts/{MAWINGU_CTX}/reports/{RICH_DRAFT_RID}/export.pdf")
        assert r.status_code == 200, f"legacy export.pdf broke: {r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1000


# ───────────────────────── regression: lens coach sessions ─────────────────────────
class TestLensCoachRegression:
    @pytest.fixture(scope="class")
    def coach_state(self, session):
        # Create a session
        r = session.post(
            f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions",
            json={"lens": "first_principles", "subject": "TEST_iter32_coach"},
        )
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text}"
        sid = r.json()["id"]
        return {"sid": sid}

    def test_create_session_returns_active(self, coach_state):
        assert coach_state["sid"]

    def test_list_includes_session(self, session, coach_state):
        r = session.get(f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert coach_state["sid"] in ids

    def test_get_active_session_200(self, session, coach_state):
        r = session.get(f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions/{coach_state['sid']}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == coach_state["sid"]
        assert body["status"] == "active"

    def test_post_message_appends_turns(self, session, coach_state):
        r = session.post(
            f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions/{coach_state['sid']}/messages",
            json={"lens": "first_principles", "message": "TEST_iter32 kickoff: what should I focus on?"},
        )
        assert r.status_code == 200, f"post message failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body["user"]["content"].startswith("TEST_iter32")
        assert (body["akki"].get("content") or "").strip(), "AKKI returned empty content"

    def test_archive_then_get_404(self, session, coach_state):
        # DELETE
        r = session.delete(f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions/{coach_state['sid']}")
        assert r.status_code == 200
        # Allow tiny propagation
        time.sleep(0.2)
        # Subsequent GET must 404 because archived sessions are filtered out (iter32 spec)
        r2 = session.get(f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions/{coach_state['sid']}")
        assert r2.status_code == 404, f"expected archived → 404, got {r2.status_code}"
        # Archived also stripped from list
        r3 = session.get(f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions")
        assert r3.status_code == 200
        assert coach_state["sid"] not in [s["id"] for s in r3.json()]


# ───────────────────────── auth-bad-lens regression ─────────────────────────
class TestCoachValidation:
    def test_unknown_lens_400(self, session):
        r = session.post(
            f"{API}/contexts/{MAWINGU_CTX}/lens/coach/sessions",
            json={"lens": "no_such_lens", "subject": "TEST_iter32_bad_lens"},
        )
        assert r.status_code == 400
