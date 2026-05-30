"""Phase P2 A.2 — Microsoft OAuth PKCE tests.

Asserts:
  1. `/microsoft/start` returns an authorize_url carrying both
     `code_challenge=...` and `code_challenge_method=S256` query params.
  2. The S256 challenge is the SHA-256 of the stored verifier
     (RFC 7636 §4.2 round-trip).
  3. The verifier is persisted in Mongo keyed by sid.
  4. `_ms_exchange_code` includes `code_verifier` in the token-exchange
     POST when one is supplied (mocked httpx).
  5. `/microsoft/callback` invokes `_ms_pkce_consume` and rejects with
     `microsoft_oauth_pkce_state_invalid` when no verifier exists.
  6. End-user response shape from `/microsoft/start` is unchanged
     (still `{authorize_url, provider}` — no extra leaked fields).

Live MS endpoints are NEVER hit — token exchange + JWKS are mocked.

P2 A.2 quality bar — every test must pass under file-level pytest.
The test file uses `httpx.AsyncClient` + `ASGITransport` driven by the
session-scoped event loop in conftest.py, which keeps Motor's async
client bound to a single loop for the lifetime of the suite. (The
previous module-level `TestClient(app)` pattern spawned a fresh
asyncio loop per request and broke Motor on the 2nd hit — see the
`RuntimeError: Event loop is closed` trace in the iter1 fork
handoff.)
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


_BASE = "http://testserver"


@pytest.fixture(autouse=True)
def _clean_pkce_collection():
    """Phase P2 A.2 — each test starts with an empty PKCE-verifier
    collection so verifiers minted by one test don't bleed into the
    invariant assertions of the next."""
    import pymongo
    _db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    _db.oauth_pkce_verifiers.delete_many({"provider": "microsoft"})
    yield
    _db.oauth_pkce_verifiers.delete_many({"provider": "microsoft"})


async def _async_get(path: str, **kwargs):
    """One-shot AsyncClient GET driven by the session event loop."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE) as ac:
        return await ac.get(path, **kwargs)


def _run(coro):
    """Run an awaitable on the session event loop (defined in conftest.py)."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _authorize_url_params(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


@pytest.mark.parametrize("path", ["/api/auth/oauth/microsoft/start"])
def test_a2_start_returns_code_challenge_S256(path):
    """The authorize_url carries the PKCE challenge + method on every
    non-probe /start call."""
    r = _run(_async_get(path))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "authorize_url" in data
    assert data.get("provider") == "microsoft"
    params = _authorize_url_params(data["authorize_url"])
    assert "code_challenge" in params, "PKCE code_challenge must be on authorize_url"
    assert params.get("code_challenge_method") == "S256", "Method must be S256"
    # Challenge is base64url(sha256(verifier)) — 43 chars.
    assert 43 <= len(params["code_challenge"]) <= 128


def test_a2_start_response_shape_unchanged():
    """End-user shape is still {authorize_url, provider} — no
    verifier / sid / pkce metadata leaked."""
    r = _run(_async_get("/api/auth/oauth/microsoft/start"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) == {"authorize_url", "provider"}


def test_a2_probe_returns_minimal_shape():
    """Probe mode skips PKCE generation entirely."""
    r = _run(_async_get("/api/auth/oauth/microsoft/start?probe=1"))
    assert r.status_code == 200
    data = r.json()
    assert data == {"configured": True, "provider": "microsoft"}


def test_a2_pkce_verifier_persisted_in_mongo():
    """After /start, the verifier MUST be in oauth_pkce_verifiers
    keyed by the sid encoded in the state JWT."""
    r = _run(_async_get("/api/auth/oauth/microsoft/start"))
    assert r.status_code == 200, r.text
    params = _authorize_url_params(r.json()["authorize_url"])
    state = params["state"]
    challenge = params["code_challenge"]
    # Decode state JWT to recover sid.
    import jwt as _jwt
    from core import JWT_SECRET
    claims = _jwt.decode(state, JWT_SECRET, algorithms=["HS256"])
    sid = claims["sid"]
    # Pull the stored verifier and verify the S256 round-trip.
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rec = db.oauth_pkce_verifiers.find_one(
        {"sid": sid, "provider": "microsoft"}, {"_id": 0},
    )
    assert rec, f"No PKCE verifier persisted for sid={sid!r}"
    verifier = rec["code_verifier"]
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    assert derived == challenge, "S256(verifier) MUST equal the published challenge"


def test_a2_pkce_verifier_helpers_round_trip():
    """Pure-function round-trip — verifier → challenge → S256 match."""
    from routers.auth_oauth import _ms_pkce_verifier, _ms_pkce_challenge
    v = _ms_pkce_verifier()
    assert 43 <= len(v) <= 128
    c = _ms_pkce_challenge(v)
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(v.encode()).digest()
    ).rstrip(b"=").decode()
    assert c == derived


def test_a2_exchange_code_sends_code_verifier():
    """_ms_exchange_code MUST include `code_verifier` in the POST body
    when one is provided."""
    from routers import auth_oauth as ao

    captured = {}

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"id_token": "fake", "access_token": "fake"}

    class _FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def post(self, url, data=None):
            captured["url"] = url
            captured["data"] = data
            return _FakeResp()

    with patch.object(ao, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = lambda *a, **kw: _FakeClient()
        _run(ao._ms_exchange_code("FAKE_CODE", code_verifier="FAKE_VERIFIER_12345"))
    assert captured["data"]["code_verifier"] == "FAKE_VERIFIER_12345"
    assert captured["data"]["code"] == "FAKE_CODE"
    assert captured["data"]["grant_type"] == "authorization_code"


def test_a2_callback_rejects_when_verifier_missing():
    """A callback whose state has no corresponding verifier in Mongo
    must reject with microsoft_oauth_pkce_state_invalid (replay or
    expiry protection)."""
    # Forge a valid-shape state JWT pointing at a sid that was never
    # written to oauth_pkce_verifiers.
    import jwt as _jwt
    from core import JWT_SECRET
    from routers.auth_oauth import _MS_STATE_TTL_SECONDS
    import time
    fake_state = _jwt.encode(
        {"sid": "never-stored", "kind": "ms_signin",
         "exp": int(time.time()) + _MS_STATE_TTL_SECONDS},
        JWT_SECRET, algorithm="HS256",
    )
    r = _run(_async_get(
        f"/api/auth/oauth/microsoft/callback?code=FAKE_CODE&state={fake_state}",
        follow_redirects=False,
    ))
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "microsoft_oauth_pkce_state_invalid"
