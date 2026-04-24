"""Iter10 backend smoke — Board deck export + shielding regression.

Exercises:
 - POST /api/auth/login (bramuel demo account)
 - GET  /api/contexts/{cid}/briefings    (expect at least 1 seeded briefing)
 - GET  /api/contexts/{cid}/briefings/{bid}/export?fmt=board_deck  (landscape %PDF, >2KB)
 - GET  /api/contexts/{cid}/briefings/{bid}/export?fmt=pdf         (backwards-compat)
 - GET  /api/contexts/{cid}/briefings/{bid}/export?fmt=docx        (backwards-compat)
 - GET  /api/contexts/{cid}/briefings/{bid}/export?fmt=xyz         (400)
 - POST /api/ask                                                   (shielding dict regression)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vigilant-kalam-4.preview.emergentagent.com").rstrip("/")
CTX_ID_TULI = "2ceb9fde-a202-4891-adb1-ecf47dfe2258"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "bramuel@syni.ai", "password": "TestBramuel2026!"},
               timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def briefing_id(session):
    r = session.get(f"{BASE_URL}/api/contexts/{CTX_ID_TULI}/briefings", timeout=30)
    assert r.status_code == 200, f"list briefings: {r.status_code} {r.text[:300]}"
    rows = r.json()
    if not rows:
        pytest.skip("No briefings seeded in Tuli context — cannot exercise export")
    return rows[0]["id"]


# ── Export format tests ────────────────────────────────────────────────────
class TestBriefingExports:

    def test_board_deck_pdf(self, session, briefing_id):
        r = session.get(
            f"{BASE_URL}/api/contexts/{CTX_ID_TULI}/briefings/{briefing_id}/export",
            params={"fmt": "board_deck"}, timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", f"not a PDF, got {r.content[:20]!r}"
        assert len(r.content) > 2048, f"deck pdf too small: {len(r.content)} bytes"
        cd = r.headers.get("content-disposition", "")
        assert "deck.pdf" in cd, f"content-disposition missing deck.pdf suffix: {cd}"

    def test_backwards_compat_pdf(self, session, briefing_id):
        r = session.get(
            f"{BASE_URL}/api/contexts/{CTX_ID_TULI}/briefings/{briefing_id}/export",
            params={"fmt": "pdf"}, timeout=60,
        )
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1024

    def test_backwards_compat_docx(self, session, briefing_id):
        r = session.get(
            f"{BASE_URL}/api/contexts/{CTX_ID_TULI}/briefings/{briefing_id}/export",
            params={"fmt": "docx"}, timeout=60,
        )
        assert r.status_code == 200
        # DOCX is a zip → starts with PK
        assert r.content[:2] == b"PK", f"not a docx/zip, got {r.content[:10]!r}"
        ct = r.headers.get("content-type", "")
        assert "officedocument" in ct or "wordprocessing" in ct

    def test_invalid_fmt_returns_400(self, session, briefing_id):
        r = session.get(
            f"{BASE_URL}/api/contexts/{CTX_ID_TULI}/briefings/{briefing_id}/export",
            params={"fmt": "xyz"}, timeout=30,
        )
        assert r.status_code == 400, f"expected 400 for fmt=xyz, got {r.status_code}: {r.text[:200]}"


# ── Shielding dict regression (Sprint 6) ──────────────────────────────────
class TestShieldingRegression:

    def test_ask_returns_shielding_dict(self, session):
        r = session.post(
            f"{BASE_URL}/api/contexts/{CTX_ID_TULI}/ask",
            json={"question": "What are the top risks?"},
            timeout=90,
        )
        assert r.status_code == 200, f"/ask failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "shielding" in body, "top-level shielding missing from /ask"
        sh = body["shielding"]
        assert isinstance(sh, dict), f"shielding must be dict, got {type(sh).__name__}"
        # common keys from Sprint 6 contract
        assert "identifiers_masked" in sh or "by_category" in sh or "shielded_by" in sh, \
            f"shielding dict missing expected keys: {list(sh.keys())}"
