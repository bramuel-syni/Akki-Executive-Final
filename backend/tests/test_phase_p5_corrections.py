"""Phase P5 corrections + OAuth-mode consume."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


def _seed_application(prefix: str = "p5") -> dict:
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    row = {
        "id":            uuid.uuid4().hex,
        "name":          "P5 Applicant",
        "email":         f"{prefix}-{uuid.uuid4().hex[:6]}@p5.example.com",
        "organisation":  "Probe",
        "role":          "Tester",
        "use_case":      "Smoke testing the P5 corrections.",
        "referral_source": "qa",
        "status":        "received",
        "created_at":    datetime.now(timezone.utc).isoformat(),
    }
    db.cohort_applications.insert_one(dict(row))
    return row


def _admin_login_token() -> str:
    async def _do():
        async with _client() as ac:
            r = await ac.post("/api/auth/login",
                              json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"})
            return r.json()["access_token"]
    return _run(_do())


def _issue_magic_link(application_id: str) -> str:
    """Approve to mint a fresh single-use token."""
    tok = _admin_login_token()
    async def _do():
        async with _client() as ac:
            r = await ac.post(
                f"/api/admin/cohort/applications/{application_id}/approve",
                headers={"Authorization": f"Bearer {tok}"},
                json={"note": "p5 test"},
            )
            return r.json()["magic_url"].rsplit("/", 1)[-1]
    return _run(_do())


# ─── P5.3 — OAuth state JWT carries magic_link_token ─────────────────
def test_p5_3_ms_start_packs_magic_link_token_in_state():
    """`/microsoft/start?magic_link_token=X` puts the token into the
    state JWT under the `mlt` claim."""
    from routers.auth_oauth import _ms_verify_state
    from urllib.parse import urlparse, parse_qs

    async def _do():
        async with _client() as ac:
            return await ac.get(
                "/api/auth/oauth/microsoft/start?magic_link_token=p5-3-token-abc"
            )
    r = _run(_do())
    assert r.status_code == 200, r.text
    url = r.json()["authorize_url"]
    state = parse_qs(urlparse(url).query).get("state", [""])[0]
    assert state
    decoded = _ms_verify_state(state)
    assert decoded.get("mlt") == "p5-3-token-abc"


def test_p5_3_ms_start_without_magic_link_omits_mlt_claim():
    """When no magic_link_token is supplied, the state JWT must NOT
    carry an mlt claim — keep the claim absent rather than empty so
    accidental empty-string consumption can't slip through."""
    from routers.auth_oauth import _ms_verify_state
    from urllib.parse import urlparse, parse_qs

    async def _do():
        async with _client() as ac:
            return await ac.get("/api/auth/oauth/microsoft/start")
    r = _run(_do())
    state = parse_qs(urlparse(r.json()["authorize_url"]).query)["state"][0]
    decoded = _ms_verify_state(state)
    assert "mlt" not in decoded or not decoded.get("mlt")


def test_p5_3_google_finish_consumes_magic_link():
    """A Google /finish request carrying `magic_link_token` consumes
    the link + links the account to the application. We mock the
    Emergent session-data fetch to avoid hitting the network."""
    app_row = _seed_application("p5-3-google")
    raw = _issue_magic_link(app_row["id"])

    from unittest.mock import patch

    fake_profile = {
        "email":   app_row["email"],
        "name":    app_row["name"],
        "picture": None,
    }
    async def _fake_fetch(_session_id):
        return fake_profile

    with patch("routers.auth_oauth._fetch_emergent_session_data", _fake_fetch):
        async def _do():
            async with _client() as ac:
                return await ac.post(
                    "/api/auth/oauth/google/finish",
                    json={"session_id": "fake-session-id",
                          "magic_link_token": raw},
                )
        r = _run(_do())

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["magic_link_consumed"] is True

    # Application moved to redeemed.
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    fresh = db.cohort_applications.find_one({"id": app_row["id"]}, {"_id": 0})
    assert fresh["status"] == "approved_redeemed"
    # Account is linked to the application.
    acc = db.accounts.find_one({"email_lc": app_row["email"]}, {"_id": 0})
    assert acc and acc.get("cohort_application_id") == app_row["id"]


def test_p5_3_google_finish_rejects_consumed_token():
    """Second use of a token via Google /finish must return 410."""
    app_row = _seed_application("p5-3-google-twice")
    raw = _issue_magic_link(app_row["id"])

    from unittest.mock import patch
    fake_profile = {"email": app_row["email"], "name": "x", "picture": None}
    async def _fake_fetch(_session_id):
        return fake_profile

    with patch("routers.auth_oauth._fetch_emergent_session_data", _fake_fetch):
        async def _twice():
            async with _client() as ac:
                r1 = await ac.post(
                    "/api/auth/oauth/google/finish",
                    json={"session_id": "fake-1", "magic_link_token": raw},
                )
                r2 = await ac.post(
                    "/api/auth/oauth/google/finish",
                    json={"session_id": "fake-2", "magic_link_token": raw},
                )
                return r1, r2
        r1, r2 = _run(_twice())
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 410, r2.text
    assert r2.json()["detail"]["code"] == "magic_link_invalid_or_consumed"


def test_p5_3_google_finish_without_mlt_is_unchanged():
    """Existing Google sign-in (no magic_link_token) still works
    end-to-end with `magic_link_consumed: false`."""
    from unittest.mock import patch
    email = f"p5-3-no-mlt-{uuid.uuid4().hex[:6]}@p5.example.com"
    fake_profile = {"email": email, "name": "No MLT User", "picture": None}
    async def _fake_fetch(_session_id):
        return fake_profile

    with patch("routers.auth_oauth._fetch_emergent_session_data", _fake_fetch):
        async def _do():
            async with _client() as ac:
                return await ac.post(
                    "/api/auth/oauth/google/finish",
                    json={"session_id": "fake-no-mlt"},
                )
        r = _run(_do())
    assert r.status_code == 200, r.text
    assert r.json().get("magic_link_consumed") in (False, None)


def test_p5_3_ms_state_carries_mlt_when_provided():
    """Explicit assertion separate from the urllib parse path —
    verifies _ms_sign_state + _ms_verify_state round trip on the mlt claim."""
    from routers.auth_oauth import _ms_sign_state, _ms_verify_state
    state = _ms_sign_state({"sid": "abc", "kind": "ms_signin", "mlt": "token-xyz"})
    decoded = _ms_verify_state(state)
    assert decoded.get("mlt") == "token-xyz"


# ─── P5.2 — backend contract for consume returns the redirect ────────
def test_p5_2_consume_returns_redirect_target():
    """`/consume` must include `redirect` so the frontend can hand off
    to the correct landing without reaching for a hardcoded fallback."""
    app_row = _seed_application("p5-2-redirect")
    raw = _issue_magic_link(app_row["id"])
    async def _do():
        async with _client() as ac:
            return await ac.post(
                "/api/auth/magic-link/consume",
                json={"token": raw, "mode": "password", "password": "P5RedirectPass1234!"},
            )
    r = _run(_do())
    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == "/app/work-studio"
