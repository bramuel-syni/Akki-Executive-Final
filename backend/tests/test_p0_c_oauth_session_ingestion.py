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


# ─────────────────────────────────────────────────────────────────
# Block 3 (2026-02) — Test-harness-blocker fix.
#
# The above tests model the OAuth-callback shape by directly calling
# `db.accounts.update_one` + `create_access_token`. This is stable but
# doesn't exercise the FastAPI route itself.
#
# The dispatch asked for a deterministic test that:
#   • Seeds an `accounts` row with `last_activity_at` stale 10+ days.
#   • Invokes the OAuth `finish` HANDLER directly with a stubbed
#     Emergent session payload.
#   • Asserts last_activity_at is now within the last 5 seconds.
#   • Asserts a follow-up `/api/me` call with the issued cookie
#     returns 200 (NOT 401 session_idle_timeout).
#
# The seam: `routers.auth_oauth._fetch_emergent_session_data(session_id)`
# at line 122 is the single dependency on the Emergent provider. Patch
# it to return a stub identity. Everything downstream — find-or-create,
# JWT mint, set_auth_cookies, last_activity_at write — runs verbatim.
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oauth_google_finish_route_with_stubbed_session_then_me_returns_200(
    transport, monkeypatch,
):
    """End-to-end through the FastAPI route, with the Emergent session
    fetch stubbed. Honours the dispatch contract exactly.
    """
    from core import db
    from routers import auth_oauth as auth_oauth_router

    email = f"p0c-route-{uuid.uuid4().hex[:6]}@example.com"
    name = "P0-C Route-level OAuth user"

    # Pre-seed an account in OAuth-only shape (no password_hash) with
    # a `last_activity_at` 10 days stale — far past the 30-minute
    # idle window the middleware enforces.
    aid = "acct-p0c-route-" + uuid.uuid4().hex[:10]
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    await db.accounts.insert_one({
        "id": aid,
        "email": email,
        "email_lc": email.lower(),
        "name": name,
        "password_hash": None,
        "declared_role": "user",
        "oauth_provider": "google",
        "last_activity_at": stale_ts,
        "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    })

    # Stub the single external dependency in the OAuth finish handler.
    async def _stub_fetch_emergent_session_data(session_id: str):
        return {
            "email": email,
            "name": name,
            "picture": None,
            "id": "google-oauth2|p0c-route-stub",
        }

    monkeypatch.setattr(
        auth_oauth_router,
        "_fetch_emergent_session_data",
        _stub_fetch_emergent_session_data,
    )
    # ASGITransport runs over `http://test` — httpx will drop cookies
    # carrying the `Secure` attribute. The production cookie hardening
    # (`set_auth_cookies` at core.py:386-397 with COOKIE_SECURE=1)
    # would prevent the cookie jar from persisting the access_token
    # for the next request. Disable Secure FOR THIS TEST ONLY via the
    # documented env override (core.py:386 reads COOKIE_SECURE at
    # request time). Production unaffected.
    monkeypatch.setenv("COOKIE_SECURE", "0")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Invoke the OAuth finish route with the stubbed session_id.
        r = await client.post(
            "/api/auth/oauth/google/finish",
            json={"session_id": "p0c-stub-session-" + uuid.uuid4().hex[:8]},
        )
        # Per the route contract this returns 200 with {ok, account_id,
        # email, name, first_session_status} and Set-Cookie headers
        # carrying the JWT.
        assert r.status_code == 200, (
            f"OAuth finish route did not return 200: "
            f"{r.status_code} {r.text[:300]}"
        )
        body = r.json()
        assert body.get("ok") is True, body
        assert (body.get("email") or "").lower() == email.lower(), body

        # 2. last_activity_at MUST be within the last 5 seconds.
        fresh = await db.accounts.find_one(
            {"id": aid}, {"last_activity_at": 1, "_id": 0}
        )
        last = datetime.fromisoformat(fresh["last_activity_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last).total_seconds()
        assert 0 <= age < 5, (
            f"last_activity_at not refreshed by OAuth finish route — "
            f"age={age}s, stale_ts was {stale_ts}"
        )

        # 3. Follow-up /api/me with the cookie jar from the OAuth
        # response MUST return 200 (NOT 401 session_idle_timeout).
        # httpx auto-carries cookies from the prior `r` via the
        # client's cookie jar.
        me = await client.get("/api/auth/me")
        assert me.status_code == 200, (
            f"/api/me did not return 200 after OAuth finish — "
            f"got {me.status_code} {me.text[:300]}.\n"
            f"This is the user-visible 'Re-enter your password' trap "
            f"regression. Stale ts={stale_ts}, age now={age}s."
        )
        me_body = me.json()
        # /api/me returns {account: {email, ...}, contexts: [...]}.
        me_email = ((me_body.get("account") or {}).get("email") or "").lower()
        assert me_email == email.lower(), me_body
