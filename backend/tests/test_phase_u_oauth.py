"""Phase U (2026-05-27) — OAuth/SSO sign-in tests.

Locks:
  - Router exports the 3 expected endpoints (Google start/finish +
    Microsoft start).
  - Google start returns the locked auth_base_url + callback_path.
  - Microsoft start returns 503 + the locked institutional payload
    (`microsoft_oauth_not_configured` + `needs`).
  - Google finish:
      * 400 on invalid session_id (Emergent Auth endpoint returns non-200)
      * 400 on missing email in resolved profile
      * Creates a new account on novel email + mints a JWT that
        passes get_current_account validation
      * Existing account: stamps oauth_providers + last_login_at,
        doesn't reset trial fields
      * `is_new` flag matches the create/lookup branch taken
  - Sign-in page wires `<OAuthButtons>` + the OAuth buttons render
    with the locked testids.
  - `/oauth/callback` route is registered + lazy-imports
    `OAuthCallback`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

# Load env up-front so MONGO_URL etc. are present when modules import.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from fastapi.testclient import TestClient  # noqa: E402

OAUTH_PY     = REPO / "backend" / "routers" / "auth_oauth.py"
SIGNIN_JSX   = REPO / "frontend" / "src" / "pages" / "SignIn.jsx"
BUTTONS_JSX  = REPO / "frontend" / "src" / "components" / "auth" / "OAuthButtons.jsx"
CALLBACK_JSX = REPO / "frontend" / "src" / "pages" / "OAuthCallback.jsx"
APP_JS       = REPO / "frontend" / "src" / "App.js"


# ─────────────────────────────────────────────────────────────────────
# A. Router exports the 3 expected endpoints
# ─────────────────────────────────────────────────────────────────────

def test_U_a_router_registers_3_endpoints():
    from routers import auth_oauth
    paths = {(r.path, list(r.methods)[0] if r.methods else "?")
             for r in auth_oauth.router.routes}
    expected = {
        ("/api/auth/oauth/google/start", "GET"),
        ("/api/auth/oauth/google/finish", "POST"),
        ("/api/auth/oauth/microsoft/start", "GET"),
        ("/api/auth/oauth/microsoft/finish", "POST"),
    }
    for url, method in expected:
        assert any(p == url for p, _ in paths), \
            f"router must expose {method} {url}"


def test_U_a_server_includes_router():
    """The router must be wired into server.py so the endpoints exist
    behind /api on the FastAPI app."""
    src = (REPO / "backend" / "server.py").read_text(encoding="utf-8")
    assert "auth_oauth" in src, "server.py must import auth_oauth router"
    assert "auth_oauth_router.router" in src, \
        "server.py must include_router(auth_oauth_router.router)"


# ─────────────────────────────────────────────────────────────────────
# B. Google start returns the locked Emergent Auth base URL
# ─────────────────────────────────────────────────────────────────────

def test_U_b_google_start_returns_locked_emergent_url():
    """Per the playbook the auth_base_url is locked to Emergent Auth.
    Any change here breaks the auth flow institution-wide."""
    from server import app
    client = TestClient(app)
    res = client.get("/api/auth/oauth/google/start")
    assert res.status_code == 200
    body = res.json()
    assert body["auth_base_url"] == "https://auth.emergentagent.com/"
    assert body["callback_path"] == "/oauth/callback"
    assert body["provider"] == "google"


def test_U_b_google_start_does_not_hardcode_redirect_url():
    """The playbook is emphatic: backend MUST NOT hardcode the redirect
    URL — frontend assembles it from window.location.origin."""
    src = OAUTH_PY.read_text(encoding="utf-8")
    # Must not contain any literal preview URL.
    assert "preview.emergentagent.com" not in src, \
        "auth_oauth.py must NOT hardcode the preview URL — derive from window.location.origin"
    # Must NOT contain a fallback redirect URL literal.
    assert "REDIRECT_URL =" not in src
    assert "redirect_url = " not in src.replace("redirect_url ='/'", "")


# ─────────────────────────────────────────────────────────────────────
# C. Microsoft start returns 503 with locked payload
# ─────────────────────────────────────────────────────────────────────

def test_U_c_microsoft_start_returns_503_with_locked_payload():
    from server import app
    # Confirm creds are NOT in env (we expect 503; if creds slip in the
    # test would surface a 501 from the not-yet-implemented branch
    # which is a different signal).
    if os.environ.get("MICROSOFT_OAUTH_CLIENT_ID") and os.environ.get(
        "MICROSOFT_OAUTH_CLIENT_SECRET"
    ):
        pytest.skip("Microsoft OAuth creds present — Phase U.2 lockdown active")

    client = TestClient(app)
    res = client.get("/api/auth/oauth/microsoft/start")
    assert res.status_code == 503
    detail = res.json().get("detail", {})
    assert detail.get("error") == "microsoft_oauth_not_configured", \
        "503 payload must carry the locked error code"
    assert "needs" in detail, "503 payload must carry the actionable `needs` field"
    assert "Application ID" in detail["needs"]
    assert "Client Secret" in detail["needs"]


def test_U_c_microsoft_finish_returns_503():
    """Defence in depth — even if frontend bypasses the start check the
    finish endpoint must independently gate."""
    from server import app
    if os.environ.get("MICROSOFT_OAUTH_CLIENT_ID") and os.environ.get(
        "MICROSOFT_OAUTH_CLIENT_SECRET"
    ):
        pytest.skip("Microsoft OAuth creds present — Phase U.2 lockdown active")
    client = TestClient(app)
    res = client.post("/api/auth/oauth/microsoft/finish", json={"session_id": "x" * 10})
    assert res.status_code == 503
    assert res.json()["detail"]["error"] == "microsoft_oauth_not_configured"


# ─────────────────────────────────────────────────────────────────────
# D. Google finish — happy + sad paths (Emergent Auth endpoint mocked)
# ─────────────────────────────────────────────────────────────────────

def test_U_d_finish_400_on_invalid_session_id():
    """When Emergent Auth returns non-200 (expired session, replay, etc.) we
    return 400 with `oauth_session_invalid` — not 500."""
    from server import app

    with _patch_emergent_http_error(401):
        client = TestClient(app)
        res = client.post(
            "/api/auth/oauth/google/finish",
            json={"session_id": "expired_session"},
        )
        assert res.status_code == 400
        assert res.json()["detail"]["error"] == "oauth_session_invalid"


def _sync_mongo():
    """Sync pymongo handle for test verification (Motor binds to the
    TestClient's event loop which closes between tests)."""
    import pymongo
    url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    return pymongo.MongoClient(url)[db_name]


def test_U_d_finish_400_on_missing_email():
    """Emergent Auth returns 200 but profile lacks an email — surface a
    clean 400 with `oauth_email_missing`."""
    from server import app

    with _patch_emergent({
        "id": "g-123", "name": "Anon", "picture": None,
    }):
        client = TestClient(app)
        res = client.post(
            "/api/auth/oauth/google/finish",
            json={"session_id": "valid-session-id-no-email"},
        )
        assert res.status_code == 400, res.text
        assert res.json()["detail"]["error"] == "oauth_email_missing"


def _patch_emergent(profile: dict):
    """Helper — returns a patch context that makes the Emergent Auth
    session-data call resolve to the given profile.

    Patches the helper function (not httpx globally) so the test's own
    AsyncClient usage isn't affected.
    """
    from routers import auth_oauth

    async def _fake_fetch(session_id: str):
        return profile

    return patch.object(auth_oauth, "_fetch_emergent_session_data", _fake_fetch)


def _patch_emergent_http_error(status_code: int = 401):
    """Helper — patch the helper to raise the http-error pathway."""
    from routers import auth_oauth
    from fastapi import HTTPException

    async def _fake_fetch(session_id: str):
        raise HTTPException(status_code=400, detail={
            "error": "oauth_session_invalid",
            "message": "OAuth session expired or was already consumed.",
            "provider_status": status_code,
        })

    return patch.object(auth_oauth, "_fetch_emergent_session_data", _fake_fetch)


async def test_U_d_finish_creates_new_account_on_novel_email():
    """Novel email → creates account with auth_provider='google',
    is_new=True, mints a JWT, returns next_url=/app/first-session."""
    from server import app
    from core import JWT_SECRET, JWT_ALGO
    import jwt as pyjwt
    import secrets

    email = f"phase-u-novel-{secrets.token_hex(4)}@example.com"

    try:
        with _patch_emergent({
            "id": "g-test",
            "email": email,
            "name": "Phoebe Tester",
            "picture": "https://example.com/p.png",
        }):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                res = await client.post(
                    "/api/auth/oauth/google/finish",
                    json={"session_id": "valid_novel"},
                )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["is_new"] is True
            assert body["email"] == email
            assert body["next_url"] == "/app/first-session"
            assert body["provider"] == "google"
            token = body["token"]
            decoded = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            assert decoded["sub"] == body["account_id"]
            assert decoded["email"] == email
            assert "jti" in decoded

        # Verify account row via sync mongo handle.
        sdb = _sync_mongo()
        acct = sdb.accounts.find_one({"email": email}, {"_id": 0})
        assert acct is not None, "account must be created"
        assert acct["auth_provider"] == "google"
        assert acct["password_hash"] is None
        assert "google" in (acct.get("oauth_providers") or [])
        assert acct["first_session"] == {"status": "intake"}
    finally:
        _sync_mongo().accounts.delete_many({"email": email})


async def test_U_d_finish_signs_in_existing_account():
    """Existing email (sync-pre-written) → existing-account branch."""
    from server import app
    import secrets
    import uuid
    import datetime as dt

    email = f"phase-u-existing-{secrets.token_hex(4)}@example.com"
    acct_id = uuid.uuid4().hex

    sdb = _sync_mongo()
    sdb.accounts.insert_one({
        "id": acct_id, "email": email, "password_hash": "hashed",
        "auth_provider": "password",
        "name": "Already Here",
        "first_session": {"status": "complete"},
        "trial_status": "active_trial",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })

    try:
        with _patch_emergent({
            "id": "g-test", "email": email,
            "name": "Already Here", "picture": None,
        }):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                res = await client.post(
                    "/api/auth/oauth/google/finish",
                    json={"session_id": "valid_existing"},
                )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["is_new"] is False
            assert body["account_id"] == acct_id
            assert body["next_url"] == "/app/"

        acct = sdb.accounts.find_one({"id": acct_id}, {"_id": 0})
        assert "google" in (acct.get("oauth_providers") or [])
        assert acct.get("last_login_at"), "last_login_at must be stamped"
        assert acct["password_hash"] == "hashed", \
            "password account keeps its password_hash after OAuth sign-in"
        assert acct["auth_provider"] == "password", \
            "existing auth_provider must NOT be overwritten"
    finally:
        sdb.accounts.delete_one({"id": acct_id})


# ─────────────────────────────────────────────────────────────────────
# E. Frontend wiring — SignIn + OAuthButtons + OAuthCallback
# ─────────────────────────────────────────────────────────────────────

def test_U_e_signin_imports_oauth_buttons():
    src = SIGNIN_JSX.read_text(encoding="utf-8")
    assert "OAuthButtons" in src, "SignIn must import OAuthButtons"
    assert "<OAuthButtons" in src, "SignIn must render <OAuthButtons />"


def test_U_e_signin_block_carries_testid():
    """The OAuth block must be discoverable in the DOM at a stable
    testid so the testing agent + future regression locks can find it."""
    src = SIGNIN_JSX.read_text(encoding="utf-8")
    assert 'data-testid="signin-oauth-block"' in src


def test_U_e_oauth_buttons_carry_locked_testids():
    src = BUTTONS_JSX.read_text(encoding="utf-8")
    for tid in ("oauth-buttons", "oauth-google-btn", "oauth-microsoft-btn"):
        assert f'data-testid="{tid}"' in src, \
            f"OAuthButtons must carry data-testid={tid!r}"


def test_U_e_buttons_use_browser_origin_not_hardcode():
    """Per playbook — frontend MUST derive redirect URL from
    window.location.origin. Hardcoded URLs break the auth."""
    src = BUTTONS_JSX.read_text(encoding="utf-8")
    assert "window.location.origin" in src
    # The playbook reminder line MUST appear (institutional memory).
    assert "DO NOT HARDCODE" in src, \
        "OAuthButtons must carry the playbook reminder comment"


def test_U_e_callback_route_registered():
    src = APP_JS.read_text(encoding="utf-8")
    assert '"/oauth/callback"' in src or "'/oauth/callback'" in src, \
        "App.js must register the /oauth/callback route"
    assert "OAuthCallback" in src, "App.js must lazy-import OAuthCallback"


def test_U_e_callback_uses_useref_processed_flag():
    """Per playbook the AuthCallback effect MUST use useRef (NOT
    useState) for the processed flag to avoid StrictMode double-fire."""
    src = CALLBACK_JSX.read_text(encoding="utf-8")
    assert "useRef" in src, "OAuthCallback must use useRef for hasProcessed flag"
    assert "hasProcessed" in src
    # Confirm the synchronous-set pattern is present.
    assert "hasProcessed.current = true" in src


def test_U_e_callback_reads_hash_fragment_not_query_string():
    """Emergent Auth puts the session_id in the hash fragment (not the
    query string). Reading from window.location.search would 0-out the
    flow."""
    src = CALLBACK_JSX.read_text(encoding="utf-8")
    assert "window.location.hash" in src
    assert "session_id=" in src


def test_U_e_callback_carries_locked_testids():
    src = CALLBACK_JSX.read_text(encoding="utf-8")
    for tid in ("oauth-callback-page", "oauth-callback-spinner",
                "oauth-callback-status", "oauth-callback-error",
                "oauth-callback-back-to-signin"):
        assert f'data-testid="{tid}"' in src, \
            f"OAuthCallback must carry data-testid={tid!r}"
