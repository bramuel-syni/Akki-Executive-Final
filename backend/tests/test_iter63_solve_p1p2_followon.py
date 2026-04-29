"""Iter63 — AKKI Solve P1+P2 follow-on items.

Backend coverage:
  - GET  /api/solve/pro-status                          shape + values for free-grant-claimed user
  - GET  /api/solve/sessions/{sid}/export.pdf           valid PDF + Content-Disposition + 404/409
  - POST /api/solve/sessions/{sid}/handoff/cycle        LLM-polished questions (no verbatim
                                                        "How do we hold ourselves to:" prefix), 1-3 entries, idempotent
  - _consume_free_grant race-safety                     5+ concurrent calls converge to exactly
                                                        one allowed=True; no duplicate docs
  - Regression                                          iter62 endpoints still respond OK
"""
import asyncio
import os
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

USER_EMAIL = "bramuel@syni.ai"
USER_PASSWORD = "TestBramuel2026!"
TULI_NED_CTX = "fb4df969-3f17-4279-bf78-f07bb9e29650"

# Pre-existing completed session w/ Brief+Decks+Cycle handoffs (per iter62 fixture)
PRE_EXISTING_SID = "caf60a32-ea4a-419c-bba7-164178b8ad30"


# ------------------------------------------------------------------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def user_token(api):
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"User login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _complete_session(api, tok, cluster_id="revenue_underperformance",
                      intent="TEST_iter63 follow-on - revenue missed and pricing weakened in Q4"):
    r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(tok),
                 json={"cluster_id": cluster_id, "intent": intent, "pro_tier": False},
                 timeout=120)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    last = None
    for msg in [
        "TEST_iter63 surface - missed Q4 revenue ~10pct, concentrated in SME segment.",
        "TEST_iter63 depth - underlying issue is onboarding friction added by the Q2 redesign.",
        "TEST_iter63 synthesis - need to triangulate against comparable boards on activation drop.",
        "TEST_iter63 lockin - decide a remediation owner, watch SME activation rate, walk-in CFO question.",
    ]:
        r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/turn",
                     headers=_h(tok), json={"user_text": msg}, timeout=240)
        assert r.status_code == 200, f"turn failed: {r.text}"
        last = r.json()
    assert last["status"] == "completed"
    return sid, last


# ─── Pro-status endpoint ───────────────────────────────────────────
class TestProStatus:
    def test_pro_status_shape(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/pro-status",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        # Required top-level keys
        assert "is_pro" in body and isinstance(body["is_pro"], bool)
        assert "plan" in body and isinstance(body["plan"], str)
        assert "free_grant" in body
        fg = body["free_grant"]
        assert isinstance(fg.get("claimed_this_month"), bool)
        assert isinstance(fg.get("month_utc"), str) and len(fg["month_utc"]) == 7
        assert fg.get("remaining") in (0, 1)

    def test_pro_status_bramuel_grant_already_claimed(self, api, user_token):
        """Bramuel's free grant for current UTC month was consumed in iter62."""
        r = api.get(f"{BASE_URL}/api/solve/pro-status",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        body = r.json()
        # Bramuel is on free plan
        assert body["is_pro"] is False, f"expected free user, got plan={body['plan']}"
        # Grant was already claimed in iter62 — should still be true this UTC month
        assert body["free_grant"]["claimed_this_month"] is True, \
            "expected claimed_this_month=True for Bramuel (consumed in iter62)"
        assert body["free_grant"]["remaining"] == 0


# ─── PDF export endpoint ───────────────────────────────────────────
class TestPdfExport:
    def test_pdf_404_on_unknown_session(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/sessions/iter63-unknown-sid-xyz/export.pdf",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 404

    def test_pdf_409_on_incomplete_session(self, api, user_token):
        # Start a session but DON'T walk it through any phases
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={
                         "cluster_id": "revenue_underperformance",
                         "intent": "TEST_iter63 pdf 409 - empty session, no synthesis yet, intentionally abandoned",
                         "pro_tier": False,
                     },
                     timeout=60)
        assert r.status_code == 200
        sid = r.json()["id"]
        try:
            pr = api.get(f"{BASE_URL}/api/solve/sessions/{sid}/export.pdf",
                         headers=_h(user_token), timeout=30)
            assert pr.status_code == 409, f"expected 409 incomplete, got {pr.status_code}: {pr.text[:200]}"
        finally:
            api.post(f"{BASE_URL}/api/solve/sessions/{sid}/abandon",
                     headers=_h(user_token), timeout=30)

    def test_pdf_export_pre_existing_session(self, api, user_token):
        """Use the pre-existing iter62 completed session w/ synthesis."""
        # First confirm session exists for this user
        check = api.get(f"{BASE_URL}/api/solve/sessions/{PRE_EXISTING_SID}",
                        headers=_h(user_token), timeout=30)
        if check.status_code != 200:
            pytest.skip(f"Pre-existing session not visible: {check.status_code}")

        r = api.get(f"{BASE_URL}/api/solve/sessions/{PRE_EXISTING_SID}/export.pdf",
                    headers=_h(user_token), timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf"), \
            f"content-type mismatch: {r.headers.get('content-type')}"
        cd = r.headers.get("content-disposition", "")
        assert "inline" in cd.lower(), f"expected inline disposition, got {cd}"
        assert "filename=" in cd.lower(), f"expected filename in disposition: {cd}"
        body = r.content
        assert body.startswith(b"%PDF"), f"not a PDF, first 8 bytes: {body[:8]!r}"
        assert len(body) >= 1500, f"PDF suspiciously small: {len(body)} bytes"
        assert len(body) <= 200_000, f"PDF unexpectedly large: {len(body)} bytes"


# ─── LLM-polished cycle handoff questions ──────────────────────────
class TestCycleHandoffPolish:
    @pytest.fixture(scope="class")
    def completed_sid(self, api, user_token):
        sid, _ = _complete_session(
            api, user_token,
            intent="TEST_iter63 cycle polish - SME activation has dropped 18pct since Q2 redesign",
        )
        yield sid

    def test_cycle_handoff_questions_polished(self, api, user_token, completed_sid):
        r = api.post(
            f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/cycle",
            headers=_h(user_token),
            json={"context_id": TULI_NED_CTX},
            timeout=60,
        )
        assert r.status_code == 200, r.text[:400]
        body = r.json()
        assert body.get("already_exists") is False
        qs = body.get("questions") or []
        assert 1 <= len(qs) <= 3, f"expected 1-3 questions, got {len(qs)}"
        for q in qs:
            assert q.get("text"), q
            assert q.get("solve_session_id") == completed_sid
            assert q.get("context_id") == TULI_NED_CTX
        # Polish assertion — texts should NOT all be the verbatim
        # "How do we hold ourselves to:" deterministic fallback prefix.
        # At least one question should be free of that prefix (LLM polished).
        prefixed = [q for q in qs if q["text"].startswith("How do we hold ourselves to")]
        assert len(prefixed) < len(qs), \
            f"all questions look like verbatim fallback, no LLM polish: {[q['text'] for q in qs]}"

    def test_cycle_handoff_idempotent(self, api, user_token, completed_sid):
        r = api.post(
            f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/cycle",
            headers=_h(user_token),
            json={"context_id": TULI_NED_CTX},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("already_exists") is True
        assert body.get("handoff_id")
        # Returns prior questions
        assert isinstance(body.get("questions"), list)


# ─── Free-grant race safety ────────────────────────────────────────
class TestFreeGrantRaceSafety:
    """Hammer _consume_free_grant directly via Mongo helpers; assert
    exactly one allowed=True across N concurrent calls and exactly one
    document exists for the (account, month) pair."""

    def test_atomic_find_one_and_update_converges(self):
        # Direct DB probe — bypass HTTP. Use a fresh synthetic account_id
        # so we don't disturb Bramuel's already-claimed grant.
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"motor not available: {e}")
        import sys
        sys.path.insert(0, "/app/backend")
        from routers.solve_engine import _consume_free_grant, _now_month_utc  # type: ignore

        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        assert mongo_url and db_name, "MONGO_URL/DB_NAME missing"

        synthetic_account = f"TEST_iter63_race_{int(time.time()*1000)}"
        month = None

        async def runner():
            nonlocal month
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            month = _now_month_utc()
            # Pre-clean (in case of leftover)
            await db.solve_free_grants.delete_many(
                {"account_id": synthetic_account, "month_utc": month}
            )
            try:
                # Fire 8 concurrent claims
                results = await asyncio.gather(
                    *[_consume_free_grant(synthetic_account) for _ in range(8)]
                )
                allowed_count = sum(1 for r in results if r.get("allowed"))
                denied_count = sum(1 for r in results if not r.get("allowed"))
                docs = await db.solve_free_grants.count_documents(
                    {"account_id": synthetic_account, "month_utc": month}
                )
                final = await db.solve_free_grants.find_one(
                    {"account_id": synthetic_account, "month_utc": month},
                    {"_id": 0, "count": 1},
                )
                return allowed_count, denied_count, docs, (final or {}).get("count", 0)
            finally:
                await db.solve_free_grants.delete_many(
                    {"account_id": synthetic_account, "month_utc": month}
                )
                client.close()

        loop = asyncio.new_event_loop()
        try:
            allowed, denied, docs, final_count = loop.run_until_complete(runner())
        finally:
            loop.close()

        assert allowed == 1, f"expected exactly 1 allowed, got {allowed}"
        assert denied == 7, f"expected 7 denied, got {denied}"
        assert docs == 1, f"expected exactly 1 grant doc, got {docs}"
        assert final_count == 8, f"expected count to converge to 8 (each call $inc), got {final_count}"


# ─── Regression: iter62 endpoints still up ─────────────────────────
class TestIter62Regression:
    def test_clusters_endpoint_still_12(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/clusters", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        assert r.json().get("count") == 12

    def test_sessions_list_endpoint(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        body = r.json()
        # Wave 2 introduced this list — keys vary; just check it returns dict/list cleanly
        assert isinstance(body, (dict, list))

    def test_pre_existing_session_handoffs_list(self, api, user_token):
        check = api.get(f"{BASE_URL}/api/solve/sessions/{PRE_EXISTING_SID}",
                        headers=_h(user_token), timeout=30)
        if check.status_code != 200:
            pytest.skip("Pre-existing session not accessible to current user")
        r = api.get(f"{BASE_URL}/api/solve/sessions/{PRE_EXISTING_SID}/handoffs",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        items = r.json().get("items") or []
        targets = {item.get("target") for item in items}
        # Per agent context, the pre-existing session has at least Brief + Cycle
        # (Decks may or may not be present depending on iter62 fixture state)
        assert {"brief", "cycle"}.issubset(targets), \
            f"expected brief+cycle in handoffs, got {targets}"
