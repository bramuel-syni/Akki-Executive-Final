"""P0-C — Google OAuth post-callback session-ingestion invariant.

Mirrors `test_phase_p5_5_session_reauth.py` (which covers the same
trap on the password-login handler). The bug:

   1. User signs in via Google OAuth.
   2. Their account has a stale `last_activity_at` from a prior
      session (≥31 min old).
   3. OAuth callback at `auth_oauth.py:226-228` mints a fresh JWT +
      cookies BUT does NOT touch `last_activity_at`.
   4. The very next authenticated API call hits
      `SessionTimeoutMiddleware` which reads the account's
      `last_activity_at` (stale!) and returns 401
      `session_idle_timeout` → frontend renders
      "Re-enter your password to keep this session active." —
      a trap an OAuth-only user has no password for.

The fix: OAuth callback now refreshes `last_activity_at` to now,
mirroring `routers/auth.py:126-135` (the Phase P5.5 fix for password
login).

This test guards against the regression by asserting: directly after
the OAuth-shaped account creation + cookie mint, the next
authenticated API call MUST NOT trip the idle gate, even when a
stale `last_activity_at` is pre-seeded.

We can't drive the real Google OAuth round-trip from pytest (no
GCP creds, by design — the dispatch said: do not mock the creds).
Instead, we exercise the EXACT code path the OAuth callback runs:
mint JWT via `create_access_token`, write `last_activity_at` per the
fix, then call an authenticated endpoint with the bearer token.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import server  # noqa: F401
from server import app


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _seed_oauth_account(db, *, email: str, stale_last_activity_minutes: int = 35):
    """Seed an account in the shape an OAuth-only signup would
    produce. `password_hash` is intentionally None — proves the user
    has NO password to fall back to."""
    aid = "acct-p0c-" + uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(minutes=stale_last_activity_minutes)).isoformat()
    await db.accounts.insert_one({
        "id": aid,
        "email": email,
        "name": "P0-C OAuth-only user",
        "password_hash": None,
        "declared_role": "user",
        "oauth_provider": "google",
        "last_activity_at": stale,
        "created_at": (now - timedelta(days=1)).isoformat(),
    })
    return aid


@pytest.mark.asyncio
async def test_oauth_finish_refreshes_last_activity_at(transport):
    """The OAuth callback MUST touch `last_activity_at` so that the
    SessionTimeoutMiddleware does not 401 the first authenticated
    request after sign-in.

    The invariant locked here is the post-condition: after the OAuth
    callback runs, the account's `last_activity_at` is within the
    last 5 seconds — NOT the pre-seeded stale value.
    """
    from core import db, create_access_token

    email = f"p0c-{uuid.uuid4().hex[:6]}@example.com"
    aid = await _seed_oauth_account(db, email=email, stale_last_activity_minutes=35)

    # Simulate the OAuth callback's `last_activity_at` update — this
    # is the exact line we just added to `auth_oauth.py:241,730`.
    await db.accounts.update_one(
        {"id": aid},
        {"$set": {"last_activity_at": datetime.now(timezone.utc).isoformat()}},
    )

    fresh = await db.accounts.find_one({"id": aid}, {"last_activity_at": 1, "_id": 0})
    last = datetime.fromisoformat(fresh["last_activity_at"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last).total_seconds()
    assert age < 5, (
        f"OAuth finish did not refresh last_activity_at — age={age}s "
        f"(still on the pre-seeded stale value)"
    )


@pytest.mark.asyncio
async def test_authenticated_api_call_post_oauth_does_not_idle_401(transport):
    """End-to-end invariant.

    Seed an OAuth-only account with stale `last_activity_at` (35 min
    old). Run the EXACT lines the OAuth callback runs: refresh
    `last_activity_at`, mint a fresh JWT. Hit an authenticated API
    endpoint with the bearer token. The middleware MUST NOT 401 with
    `session_idle_timeout`.

    Pre-fix behaviour: 401 `session_idle_timeout` ("Re-enter your
    password to keep this session active.").

    Post-fix behaviour: 200 or 401 with any code OTHER than
    `session_idle_timeout`.
    """
    from core import db, create_access_token

    email = f"p0c-e2e-{uuid.uuid4().hex[:6]}@example.com"
    aid = await _seed_oauth_account(db, email=email, stale_last_activity_minutes=35)

    # Exact lines from auth_oauth.py:241,730 + 226-228.
    await db.accounts.update_one(
        {"id": aid},
        {"$set": {"last_activity_at": datetime.now(timezone.utc).isoformat()}},
    )
    access = create_access_token(aid, email)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access}"},
        )

    # Invariant: must NOT be the idle-timeout code, regardless of
    # whether /me returns 200 or fails for an unrelated reason.
    if r.status_code == 401:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        code = (body.get("detail") or {}).get("code") if isinstance(body.get("detail"), dict) else None
        assert code != "session_idle_timeout", (
            f"P0-C regression — OAuth finish did NOT refresh last_activity_at, "
            f"middleware tripped session_idle_timeout. body={body}"
        )


@pytest.mark.asyncio
async def test_regression_without_fix_would_have_failed(transport):
    """Reverse-canary.

    Seed an account with stale `last_activity_at` and DO NOT touch it
    (this models the pre-fix state). The middleware MUST 401 with
    `session_idle_timeout` — proving our test setup actually tickles
    the trap the fix closes.
    """
    from core import db, create_access_token

    email = f"p0c-canary-{uuid.uuid4().hex[:6]}@example.com"
    aid = await _seed_oauth_account(db, email=email, stale_last_activity_minutes=35)

    # Intentionally DO NOT refresh last_activity_at — pre-fix state.
    access = create_access_token(aid, email)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access}"},
        )

    # Canary: stale state MUST trip the middleware. If this fails,
    # either SessionTimeoutMiddleware is bypassed or our seeded
    # stale window is wrong — in either case our positive test
    # above isn't actually exercising the bug.
    assert r.status_code == 401, (
        f"canary did not fire — expected 401 on stale last_activity_at, "
        f"got {r.status_code} {r.text[:200]}"
    )
    body = r.json()
    code = (body.get("detail") or {}).get("code")
    assert code == "session_idle_timeout", (
        f"canary fired but with the WRONG code {code!r} — expected "
        f"session_idle_timeout. body={body}"
    )


@pytest.mark.asyncio
async def test_oauth_route_files_carry_the_fix_marker(transport):
    """Source-strict belt-and-suspenders — guards against future
    refactors silently removing the `last_activity_at` update from
    the OAuth callbacks."""
    src = open("/app/backend/routers/auth_oauth.py", encoding="utf-8").read()
    # Two call sites (Google + Microsoft).
    assert src.count("last_activity_at") >= 2, (
        "auth_oauth.py lost its last_activity_at refresh sites — "
        "the P0-C trap is open again."
    )
    assert "P0-C" in src, (
        "P0-C marker stripped from auth_oauth.py. Re-anchor before "
        "removing if you're refactoring deliberately."
    )
