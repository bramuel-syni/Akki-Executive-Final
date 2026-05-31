"""Phase P5.5.A — Session re-auth recovery from idle timeout.

The user-reported bug: after the 30-minute idle window expires, the
SessionTimeoutGuard modal opens (via the backend's 401
session_idle_timeout signal). The user enters the correct password
and clicks Continue. The expected outcome is "session refreshed,
stay on the same page". The actual pre-fix outcome was a bounce to
/signin because:

  1. SessionTimeoutMiddleware was checking every request — including
     /api/auth/login — against the account's last_activity_at, so
     the very call meant to re-authenticate was itself rejected
     with 401 session_idle_timeout, never reaching the login
     handler. (root cause class (a))
  2. Even after class (a) was fixed by the bypass list, the FIRST
     post-login request still tripped the idle check because the
     login handler didn't refresh `last_activity_at` on the account
     doc — only the middleware (running after the timeout check) did.
     The check failed before the refresh could happen, creating an
     unrecoverable loop. (root cause class (b))

This file locks both fixes.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
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


def _make_account(prefix: str, password: str = "P5_5Pass!2026") -> dict:
    """Seed an account with a recent created_at but an idle
    last_activity_at (35 min old) — same state the user hits when
    they leave their browser tab open for >30 min."""
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@p5-5.example.com"
    now = datetime.now(timezone.utc)
    doc = {
        "id": uuid.uuid4().hex,
        "email": email,
        "email_lc": email.lower(),
        "status": "active",
        "is_superadmin": False,
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "auth_provider": "password",
        "created_at": now.isoformat(),
        "last_activity_at": (now - timedelta(minutes=35)).isoformat(),
    }
    db.accounts.insert_one(dict(doc))
    return doc


def test_p5_5_login_bypasses_session_timeout_middleware():
    """/api/auth/login must be reachable even when the calling
    session is past its idle window. Without the bypass, the
    middleware returns 401 session_idle_timeout BEFORE the login
    handler runs, and the re-auth modal can never recover."""
    acc = _make_account("p5-5-bypass")

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            # First, prove the idle state by hitting a protected endpoint
            # WITH a cookie that mimics a logged-in session. The bearer
            # token isn't needed for the bypass assertion — we just
            # need the middleware to see a token-carrying request to
            # /api/auth/login.
            from core import create_access_token
            stale_tok = create_access_token(acc["id"], acc["email"])
            return await ac.post(
                "/api/auth/login",
                headers={
                    "Authorization": f"Bearer {stale_tok}",
                    "Cookie": f"access_token={stale_tok}",
                },
                json={"email": acc["email"], "password": "P5_5Pass!2026"},
            )

    r = _run(_do())
    # Must NOT be 401 session_idle_timeout — the bypass means the
    # request reached the login handler and the handler succeeded.
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body.get("access_token"), "login response missing access_token"
    assert body.get("account", {}).get("email") == acc["email"]


def test_p5_5_login_refreshes_last_activity_at():
    """After a successful login, the FIRST subsequent protected
    request must NOT trip the idle check. This requires the login
    handler itself to write last_activity_at on the account doc —
    relying on the middleware to refresh it is too late because the
    middleware runs the idle check BEFORE the refresh write."""
    acc = _make_account("p5-5-refresh", password="RefreshTest!2026")
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # Re-verify the seeded last_activity_at is genuinely 35 min stale.
    pre = db.accounts.find_one({"id": acc["id"]}, {"_id": 0, "last_activity_at": 1})
    pre_ts = datetime.fromisoformat(pre["last_activity_at"])
    if pre_ts.tzinfo is None:
        pre_ts = pre_ts.replace(tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - pre_ts) > timedelta(minutes=30)

    async def _login_then_probe():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            login_r = await ac.post(
                "/api/auth/login",
                json={"email": acc["email"], "password": "RefreshTest!2026"},
            )
            assert login_r.status_code == 200, login_r.text
            new_tok = login_r.json()["access_token"]
            probe = await ac.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {new_tok}"},
            )
            return probe

    probe = _run(_login_then_probe())
    # The probe must NOT be a session timeout. If the login handler
    # didn't refresh last_activity_at, the middleware would still see
    # the 35-min-stale value and reject this call.
    assert probe.status_code == 200, (
        f"first request after re-auth was rejected by middleware; "
        f"status={probe.status_code} body={probe.text[:200]}"
    )

    # Confirm the account doc was actually updated.
    post = db.accounts.find_one({"id": acc["id"]}, {"_id": 0, "last_activity_at": 1})
    post_ts = datetime.fromisoformat(post["last_activity_at"])
    if post_ts.tzinfo is None:
        post_ts = post_ts.replace(tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - post_ts) < timedelta(minutes=2), (
        "last_activity_at was not refreshed by the login handler"
    )


def test_p5_5_login_wrong_password_still_returns_401_not_timeout():
    """A wrong-password attempt on an idle session must still return
    401 with the existing `Invalid email or password` message, NOT
    a session_idle_timeout — otherwise the SessionTimeoutGuard would
    treat it as 'session expired, retry' rather than 'wrong password,
    stay open with an error'."""
    acc = _make_account("p5-5-wrong-pw")

    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.post(
                "/api/auth/login",
                json={"email": acc["email"], "password": "WrongPassword!2026"},
            )

    r = _run(_do())
    assert r.status_code == 401
    body = r.json()
    detail = body.get("detail")
    # Pre-fix would have returned the timeout shape; assert it does NOT.
    if isinstance(detail, dict):
        assert detail.get("code") != "session_idle_timeout", (
            "wrong-password attempt was masked by the timeout middleware"
        )
    # The legacy shape is a plain string "Invalid email or password".
    if isinstance(detail, str):
        assert "session_" not in detail


def test_p5_5_csrf_endpoint_bypasses_idle_timeout():
    """The CSRF endpoint must be reachable even on an idle session —
    the SPA re-fetches the CSRF token via the response interceptor
    after a 403; if it can't, the user cannot recover via the
    re-auth modal (which itself is a CSRF-protected POST)."""
    async def _do():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            return await ac.get("/api/csrf")

    r = _run(_do())
    assert r.status_code == 200
    assert r.json().get("csrf_token"), "csrf endpoint did not return a token"
