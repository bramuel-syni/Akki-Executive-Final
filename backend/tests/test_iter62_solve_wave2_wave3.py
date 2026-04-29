"""Iter62 — AKKI Solve Wave 2 (Handoff trio) + Wave 3 (Triangulation v2).

Backend tests:
  - GET    /api/solve/clusters                              regression: 12 clusters
  - POST   /api/solve/sessions                              start + Surface primer
  - POST   /api/solve/sessions/{sid}/turn x4                Surface→Depth→Synthesis→Lock-in
  - synthesis turn returns synthesis.comparables[]>=2 with required fields
  - POST   /api/solve/sessions/{sid}/handoff/brief          creates briefing, idempotent
  - POST   /api/solve/sessions/{sid}/handoff/decks          creates deck_outlines, idempotent
  - POST   /api/solve/sessions/{sid}/handoff/cycle          inserts 1-3 questions, idempotent
  - GET    /api/solve/sessions/{sid}/handoffs               lists handoffs
  - 409 on incomplete session, 403 on non-member context
  - Free monthly grant (pro_tier=true): first uses free grant, second falls back
"""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

USER_EMAIL = "bramuel@syni.ai"
USER_PASSWORD = "TestBramuel2026!"
TULI_NED_CTX = "fb4df969-3f17-4279-bf78-f07bb9e29650"


# ------------------------------------------------------------------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def user_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": USER_EMAIL, "password": USER_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"User login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _complete_session(api, tok, cluster_id="revenue_underperformance",
                      intent="TEST_iter62 wave2 - revenue is missing and pricing seems off in Q3",
                      pro_tier=False):
    """Helper: start a session and walk through all 4 phases."""
    r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(tok),
                 json={"cluster_id": cluster_id, "intent": intent, "pro_tier": pro_tier},
                 timeout=120)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    last = None
    for msg in [
        "TEST_iter62 surface reply - we missed Q3 revenue by 12pct, mostly in SME segment.",
        "TEST_iter62 depth reply - root cause may be onboarding friction we shipped in Q2.",
        "TEST_iter62 synthesis reply - we need to triangulate against comparable boards.",
        "TEST_iter62 lockin reply - decide a fix path, watch SME activation, walk-in CFO question.",
    ]:
        r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/turn",
                     headers=_h(tok), json={"user_text": msg}, timeout=240)
        assert r.status_code == 200, f"turn failed: {r.text}"
        last = r.json()
    assert last["status"] == "completed", f"expected completed, got {last['status']}"
    return sid, last


# ─── Regression: 12 clusters ──────────────────────────────────────
class TestClusters:
    def test_12_clusters(self, api, user_token):
        r = api.get(f"{BASE_URL}/api/solve/clusters", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("count") == 12
        assert len(data["clusters"]) == 12


# ─── Wave 1 + Wave 3: full walkthrough + comparables corpus ────────
class TestSessionWalkthroughAndComparables:
    @pytest.fixture(scope="class")
    def completed(self, api, user_token):
        sid, last = _complete_session(api, user_token)
        yield sid, last
        # cleanup is done via abandon helper (session already completed; leave as completed)

    def test_session_completes_to_lockin(self, completed):
        sid, last = completed
        assert last["phase"] in ("lockin", "completed", "synthesis")
        assert last["status"] == "completed"
        assert last.get("synthesis", {}).get("body")
        assert last.get("lockin", {}).get("body")

    def test_synthesis_has_comparables_v2(self, completed):
        """Wave 3 — synthesis.comparables[] must include >=2 curated entries
        with diagnosis_summary, what_worked, what_didnt fields."""
        _, last = completed
        comparables = (last.get("synthesis") or {}).get("comparables", [])
        assert isinstance(comparables, list), "synthesis.comparables must be a list"
        assert len(comparables) >= 2, f"expected >=2 comparables, got {len(comparables)}"
        for c in comparables[:2]:
            assert c.get("diagnosis_summary"), f"missing diagnosis_summary: {c}"
            assert c.get("what_worked"), f"missing what_worked: {c}"
            assert c.get("what_didnt"), f"missing what_didnt: {c}"
            # sector_tag/scale_tag are part of the new corpus shape
            assert "sector_tag" in c
            assert "scale_tag" in c


# ─── Wave 2: Handoff trio (idempotent) ─────────────────────────────
class TestHandoffs:
    @pytest.fixture(scope="class")
    def completed_sid(self, api, user_token):
        sid, _ = _complete_session(api, user_token,
                                   cluster_id="ceo_succession",
                                   intent="TEST_iter62 handoff - succession plan looks shaky for our COO promotion")
        return sid

    def test_handoff_brief_creates_and_idempotent(self, api, user_token, completed_sid):
        r1 = api.post(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/brief",
                      headers=_h(user_token),
                      json={"context_id": TULI_NED_CTX, "title": "TEST_iter62 brief"},
                      timeout=60)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1.get("already_exists") is False
        b1 = d1.get("briefing")
        assert b1 and b1.get("id")
        assert b1.get("opening_paragraph"), "briefing must have opening_paragraph (synthesis)"
        # items split into Decide/Watch/Walk-in (best-effort) or fallback summary
        assert isinstance(b1.get("items"), list) and len(b1["items"]) >= 1
        assert b1.get("solve_session_id") == completed_sid

        # Idempotent: 2nd call returns already_exists=true with same id
        r2 = api.post(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/brief",
                      headers=_h(user_token),
                      json={"context_id": TULI_NED_CTX}, timeout=60)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2.get("already_exists") is True
        assert d2["briefing"]["id"] == b1["id"]

    def test_handoff_decks_creates_and_idempotent(self, api, user_token, completed_sid):
        r1 = api.post(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/decks",
                      headers=_h(user_token),
                      json={"context_id": TULI_NED_CTX, "audience": "TEST audience"},
                      timeout=60)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1.get("already_exists") is False
        assert d1.get("outline", {}).get("id")

        r2 = api.post(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/decks",
                      headers=_h(user_token),
                      json={"context_id": TULI_NED_CTX}, timeout=60)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2.get("already_exists") is True
        assert d2["outline"]["id"] == d1["outline"]["id"]

    def test_handoff_cycle_creates_questions_and_idempotent(self, api, user_token, completed_sid):
        r1 = api.post(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/cycle",
                      headers=_h(user_token),
                      json={"context_id": TULI_NED_CTX}, timeout=60)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1.get("already_exists") is False
        qs1 = d1.get("questions", [])
        assert isinstance(qs1, list) and 1 <= len(qs1) <= 3, f"expected 1-3 questions, got {len(qs1)}"
        for q in qs1:
            # Each question should be tagged with the solve session id
            assert q.get("solve_session_id") == completed_sid or \
                   completed_sid in str(q), f"question missing solve_session_id tag: {q}"

        r2 = api.post(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoff/cycle",
                      headers=_h(user_token),
                      json={"context_id": TULI_NED_CTX}, timeout=60)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        assert d2.get("already_exists") is True
        # Question count should not grow on second call
        qs2 = d2.get("questions", [])
        assert len(qs2) == len(qs1)

    def test_list_session_handoffs(self, api, user_token, completed_sid):
        r = api.get(f"{BASE_URL}/api/solve/sessions/{completed_sid}/handoffs",
                    headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should accept either {handoffs:[...]} or {items:[...]}
        rows = data.get("handoffs") or data.get("items") or []
        assert isinstance(rows, list)
        targets = {r.get("target") for r in rows}
        assert {"brief", "decks", "cycle"}.issubset(targets), \
            f"expected all 3 handoffs, got {targets}"


# ─── Reject: incomplete session (409) ─────────────────────────────
class TestHandoffRejections:
    def test_handoff_on_incomplete_session_409(self, api, user_token):
        # Start a session but do not complete
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": "strategy_drift",
                           "intent": "TEST_iter62 incomplete session for 409 test"},
                     timeout=120)
        assert r.status_code == 200
        sid = r.json()["id"]

        for path in ("brief", "decks", "cycle"):
            r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/handoff/{path}",
                         headers=_h(user_token),
                         json={"context_id": TULI_NED_CTX}, timeout=30)
            assert r.status_code == 409, \
                f"{path} should reject incomplete: got {r.status_code} {r.text[:200]}"

        # cleanup
        api.post(f"{BASE_URL}/api/solve/sessions/{sid}/abandon",
                 headers=_h(user_token), timeout=30)

    def test_handoff_non_member_context_403(self, api, user_token):
        # Complete a session, then try handoff to a fake context
        sid, _ = _complete_session(api, user_token,
                                   cluster_id="risk_blindspot",
                                   intent="TEST_iter62 403 non-member context attempt for handoff")
        bogus_ctx = "00000000-0000-0000-0000-000000000bad"
        for path in ("brief", "decks", "cycle"):
            r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/handoff/{path}",
                         headers=_h(user_token),
                         json={"context_id": bogus_ctx}, timeout=30)
            # Either 403 (non-member) or 404 (context doesn't exist) is acceptable for safety
            assert r.status_code in (403, 404), \
                f"{path} should reject non-member: got {r.status_code} {r.text[:200]}"


# ─── Free monthly grant on pro_tier=true (free account) ───────────
class TestFreeMonthlyGrant:
    """Bramuel is a free-plan account. First synthesis with pro_tier=true
    should consume the monthly free grant (free_grant_used=true, tier=deep).
    Second pro synthesis in same UTC month falls back to standard."""

    def _walk_until_synthesis(self, api, tok, intent, pro_tier=True):
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(tok),
                     json={"cluster_id": "performance_management",
                           "intent": intent, "pro_tier": pro_tier},
                     timeout=120)
        assert r.status_code == 200, r.text
        sess = r.json()
        sid = sess["id"]
        assert sess.get("pro_tier") is True, "pro_tier must be persisted on session"
        synthesis_turn = None
        # 3 turns: surface→depth→synthesis (synthesis turn is the 3rd user turn)
        for msg in [
            "TEST_iter62 grant - surface reply with the COO performance picture.",
            "TEST_iter62 grant - depth reply about the two-output gap and CEO accountability.",
            "TEST_iter62 grant - synthesis trigger reply asking for a diagnosis.",
        ]:
            r = api.post(f"{BASE_URL}/api/solve/sessions/{sid}/turn",
                         headers=_h(tok), json={"user_text": msg}, timeout=240)
            assert r.status_code == 200, r.text
            sess = r.json()
        synthesis_turn = sess
        return sid, synthesis_turn

    def test_pro_tier_persisted_on_session(self, api, user_token):
        r = api.post(f"{BASE_URL}/api/solve/sessions", headers=_h(user_token),
                     json={"cluster_id": "capital_allocation",
                           "intent": "TEST_iter62 pro_tier persist check on free account",
                           "pro_tier": True},
                     timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("pro_tier") is True
        api.post(f"{BASE_URL}/api/solve/sessions/{d['id']}/abandon",
                 headers=_h(user_token), timeout=30)

    @pytest.mark.slow
    def test_first_synthesis_consumes_grant_second_falls_back(self, api, user_token):
        """End-to-end: first pro synthesis this UTC month → free_grant_used=true
        and tier=deep. Second pro synthesis in same month → free_grant_used=false
        and tier falls back to standard.
        NOTE: If grant has already been claimed earlier this month
        (e.g. by a prior test run), first call already returns free_grant_used=false.
        We assert at least the SECOND call returns standard tier, and at most ONE
        of the two calls reports free_grant_used=true."""
        sid1, s1 = self._walk_until_synthesis(
            api, user_token,
            "TEST_iter62 grant call 1 - first pro synthesis attempt this month")
        synth1 = s1.get("synthesis") or {}
        used_first = bool(synth1.get("free_grant_used"))
        tier_first = synth1.get("tier")

        sid2, s2 = self._walk_until_synthesis(
            api, user_token,
            "TEST_iter62 grant call 2 - second pro synthesis attempt same month")
        synth2 = s2.get("synthesis") or {}
        used_second = bool(synth2.get("free_grant_used"))
        tier_second = synth2.get("tier")

        # At most one of the two should be free_grant_used=true
        assert not (used_first and used_second), \
            "Free grant should only be claimable once per month"
        # Second call definitely should not have free_grant_used and should be standard
        assert used_second is False, "Second pro synthesis must not consume grant"
        assert tier_second == "standard", \
            f"Second pro synthesis must fall back to standard, got tier={tier_second}"

        # If first claim happened, it must be tier=deep
        if used_first:
            assert tier_first == "deep", \
                f"First grant-consuming synthesis must be tier=deep, got {tier_first}"

        # Cleanup — complete or abandon both
        for sid in (sid1, sid2):
            api.post(f"{BASE_URL}/api/solve/sessions/{sid}/abandon",
                     headers=_h(user_token), timeout=30)
