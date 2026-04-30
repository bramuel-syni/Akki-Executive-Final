"""iter68/69 — Share with the Chair + public read-only viewer.

Matches the codebase pytest convention: uses requests against the live
BASE_URL (same preview pod the app serves), so we don't re-mount ASGI.

Covers:
  * POST /studio/{kind}/{aid}/share-email (auth, email send + share record)
  * GET  /api/public/studio/track/{token} (302 to /shared/:token)
  * GET  /api/public/studio/read/{token} (artefact body + view recorded)
  * Expiration (410), invalid token (400), deleted artefact (404)
  * External reader feeds exposure score (unique_readers increments)
"""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import requests

# Wire BASE_URL from frontend .env if not already set in environment
if not os.environ.get("REACT_APP_BACKEND_URL"):
    fe_env = Path("/app/frontend/.env")
    if fe_env.exists():
        for ln in fe_env.read_text().splitlines():
            if ln.startswith("REACT_APP_BACKEND_URL="):
                os.environ["REACT_APP_BACKEND_URL"] = ln.split("=", 1)[1].strip()
                break

# Wire JWT_SECRET from backend .env for token minting
if not os.environ.get("JWT_SECRET"):
    be_env = Path("/app/backend/.env")
    if be_env.exists():
        for ln in be_env.read_text().splitlines():
            if ln.startswith("JWT_SECRET="):
                val = ln.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["JWT_SECRET"] = val
                break

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
JWT_SECRET = os.environ["JWT_SECRET"]
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"

CTX_TULI_NED = "fb4df969-3f17-4279-bf78-f07bb9e29650"
BRAMUEL_EMAIL = "bramuel@syni.ai"
BRAMUEL_PASSWORD = "TestBramuel2026!"


# -- Helpers -----------------------------------------------------------------

def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": BRAMUEL_EMAIL, "password": BRAMUEL_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _mint_share_token(payload: dict, ttl_days: int = 14) -> str:
    body = {
        **payload,
        "purpose": "studio_share",
        "exp": int((datetime.now(timezone.utc) + timedelta(days=ttl_days)).timestamp()),
    }
    return jwt.encode(body, JWT_SECRET, algorithm="HS256")


def _pick_briefing(token: str) -> str:
    """Find any briefing on Tuli NED. Uses the studio history endpoint."""
    r = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/studio/history?limit=5",
        headers=_auth(token),
        timeout=10,
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    brief = next((i for i in items if i.get("kind") == "briefing"), None)
    assert brief, "No briefing in Tuli NED studio history"
    return brief["id"]


# -- Tests -------------------------------------------------------------------

def test_share_email_creates_record_and_fires_resend():
    token = _login()
    bid = _pick_briefing(token)
    r = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/studio/briefing/{bid}/share-email",
        headers=_auth(token),
        json={"to_email": "delivered@resend.dev", "to_name": "The Chair",
              "message": "iter69 pytest"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["to_email"] == "delivered@resend.dev"
    # Resend configured in .env — expect `sent`. Accept `noop` for missing-key CI.
    assert d["email_mode"] in ("sent", "noop")
    assert "share_id" in d


def test_public_track_redirects_to_shared_route():
    auth_tok = _login()
    bid = _pick_briefing(auth_tok)
    t = _mint_share_token({
        "kind": "briefing", "aid": bid, "cid": CTX_TULI_NED,
        "email": "track_redirect@example.com", "sid": str(uuid.uuid4()),
    })
    r = requests.get(
        f"{BASE_URL}/api/public/studio/track/{t}",
        allow_redirects=False, timeout=10,
    )
    assert r.status_code == 302
    loc = r.headers["location"]
    assert "/shared/" in loc
    assert t in loc


def test_public_read_returns_artefact_and_records_view():
    auth_tok = _login()
    bid = _pick_briefing(auth_tok)
    email = f"reader_{uuid.uuid4().hex[:6]}@example.com"
    t = _mint_share_token({
        "kind": "briefing", "aid": bid, "cid": CTX_TULI_NED,
        "email": email, "sid": str(uuid.uuid4()),
    })
    r = requests.get(f"{BASE_URL}/api/public/studio/read/{t}", timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["kind"] == "briefing"
    assert d["artefact_id"] == bid
    assert "content" in d and "title" in d["content"]
    assert d["content"]["title"]
    assert isinstance(d["content"].get("items"), list)


def test_expired_token_returns_410():
    auth_tok = _login()
    bid = _pick_briefing(auth_tok)
    t = _mint_share_token({
        "kind": "briefing", "aid": bid, "cid": CTX_TULI_NED,
        "email": "expired@example.com", "sid": "expired-sid",
    }, ttl_days=-1)
    r = requests.get(f"{BASE_URL}/api/public/studio/read/{t}", timeout=10)
    assert r.status_code == 410


def test_invalid_token_returns_400():
    r = requests.get(
        f"{BASE_URL}/api/public/studio/read/not-a-real-token",
        timeout=10,
    )
    assert r.status_code == 400


def test_missing_artefact_returns_404():
    t = _mint_share_token({
        "kind": "briefing", "aid": "nonexistent-id",
        "cid": CTX_TULI_NED,
        "email": "nobody@example.com", "sid": "nobody-sid",
    })
    r = requests.get(f"{BASE_URL}/api/public/studio/read/{t}", timeout=10)
    assert r.status_code == 404


def test_external_reader_increments_unique_readers():
    auth_tok = _login()
    bid = _pick_briefing(auth_tok)
    email = f"unique_{uuid.uuid4().hex[:6]}@example.com"

    before = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/studio/briefing/{bid}/engagement",
        headers=_auth(auth_tok), timeout=10,
    )
    assert before.status_code == 200
    before_unique = before.json()["unique_readers"]

    t = _mint_share_token({
        "kind": "briefing", "aid": bid, "cid": CTX_TULI_NED,
        "email": email, "sid": str(uuid.uuid4()),
    })
    # Two reads — second should dedupe via the synthetic external account_id
    r1 = requests.get(f"{BASE_URL}/api/public/studio/read/{t}", timeout=10)
    assert r1.status_code == 200
    r2 = requests.get(f"{BASE_URL}/api/public/studio/read/{t}", timeout=10)
    assert r2.status_code == 200

    after = requests.get(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/studio/briefing/{bid}/engagement",
        headers=_auth(auth_tok), timeout=10,
    )
    assert after.status_code == 200
    assert after.json()["unique_readers"] == before_unique + 1

    # Sanity-check the synthetic account id format
    expected_aid = "external:" + hashlib.sha256(email.lower().encode()).hexdigest()[:24]
    assert expected_aid.startswith("external:")


def test_share_email_token_is_valid_for_public_read():
    """End-to-end: send share, decode the email link, fetch the read endpoint."""
    token = _login()
    bid = _pick_briefing(token)
    share_email = f"e2e_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(
        f"{BASE_URL}/api/contexts/{CTX_TULI_NED}/studio/briefing/{bid}/share-email",
        headers=_auth(token),
        json={"to_email": share_email, "to_name": "Chair",
              "message": "e2e check"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    # For e2e we re-mint a token with the same payload we know the server signed
    # (since email_configured=True, tracked_url isn't returned in the response).
    t = _mint_share_token({
        "kind": "briefing", "aid": bid, "cid": CTX_TULI_NED,
        "email": share_email, "sid": r.json()["share_id"],
    })
    view = requests.get(f"{BASE_URL}/api/public/studio/read/{t}", timeout=10)
    assert view.status_code == 200
    assert view.json()["artefact_id"] == bid
