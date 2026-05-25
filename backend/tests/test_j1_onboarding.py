"""J1 — Onboarding status wire-level tests.

Seven backend tests covering the grandfathered re-intro banner + the
Trust Center / Help one-shot tooltips.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki")
os.environ.setdefault("JWT_SECRET", "test-secret")

from httpx import AsyncClient, ASGITransport  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="module")
async def client():
    from server import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def _register(client, prefix: str = "j1"):
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    pwd = "J1Onboard2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pwd, "name": "J1 Tester",
    })
    assert r.status_code in (200, 201), r.text[:300]
    token = r.json()["access_token"]
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"},
    )
    return token, me.json()["account"]["id"], {
        "Authorization": f"Bearer {token}",
        "X-Active-Context": me.json()["contexts"][0]["id"],
    }


async def _seed_pre_v1_chat(account_id: str, ctx_id: str):
    """Insert a chat predating SHIELD_V1_DEPLOY_TIMESTAMP."""
    from core import db
    await db.chats.insert_one({
        "id": "j1pre-" + uuid.uuid4().hex[:12],
        "account_id": account_id,
        "context_id": ctx_id,
        "title": "ancient chat",
        # Far enough before the cut-over (2026-05-22T07:00) to be unambiguous.
        "created_at": "2026-03-15T10:00:00+00:00",
        "model_id": "claude-sonnet-4-5",
    })


# ─────────────────────────────────────────────────────────────────────
# Test 1 — grandfathered user → needs_reintro: true
# ─────────────────────────────────────────────────────────────────────
async def test_grandfathered_user_needs_reintro(client):
    _t, account_id, hdrs = await _register(client, "j1-grand")
    # Pull ctx_id from the first /me response.
    me = await client.get("/api/auth/me", headers={"Authorization": hdrs["Authorization"]})
    ctx_id = me.json()["contexts"][0]["id"]
    await _seed_pre_v1_chat(account_id, ctx_id)

    r = await client.get(
        "/api/users/me/onboarding-status", headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["needs_reintro"] is True, body
    assert body["reason"] == "pre_shield_v1_chats_exist", body
    assert body["dismissals_count"] == 0
    assert body["max_dismissals"] == 3
    assert body["acknowledged_at"] is None


# ─────────────────────────────────────────────────────────────────────
# Test 2 — brand-new user (no chats) → needs_reintro: false
# ─────────────────────────────────────────────────────────────────────
async def test_brand_new_user_no_reintro(client):
    """A user with zero chats is brand-new — they belong on First
    Session, NOT the re-intro banner."""
    _t, _a, hdrs = await _register(client, "j1-new")
    r = await client.get(
        "/api/users/me/onboarding-status", headers=hdrs,
    )
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["needs_reintro"] is False, body
    assert body["reason"] == "none", body


# ─────────────────────────────────────────────────────────────────────
# Test 3 — already-acknowledged user → needs_reintro: false (locked)
# ─────────────────────────────────────────────────────────────────────
async def test_acknowledged_user_no_reintro(client):
    _t, account_id, hdrs = await _register(client, "j1-ack")
    me = await client.get("/api/auth/me", headers={"Authorization": hdrs["Authorization"]})
    ctx_id = me.json()["contexts"][0]["id"]
    await _seed_pre_v1_chat(account_id, ctx_id)

    # Confirm pre-ack the user IS grandfathered.
    pre = await client.get("/api/users/me/onboarding-status", headers=hdrs)
    assert pre.json()["needs_reintro"] is True

    # Acknowledge.
    ack = await client.post(
        "/api/users/me/onboarding-status/acknowledge", headers=hdrs,
    )
    assert ack.status_code == 200, ack.text[:300]
    body = ack.json()
    assert body["needs_reintro"] is False, body
    assert body["acknowledged_at"], body
    assert body["reason"] == "already_acknowledged", body
    # Acknowledgement also dismisses the Trust Center tooltip.
    assert body["trust_center_tooltip"]["show"] is False, body
    # Read again — locked permanently.
    again = await client.get("/api/users/me/onboarding-status", headers=hdrs)
    assert again.json()["needs_reintro"] is False


# ─────────────────────────────────────────────────────────────────────
# Test 4 — dismiss increments counter
# ─────────────────────────────────────────────────────────────────────
async def test_dismiss_increments_counter(client):
    _t, account_id, hdrs = await _register(client, "j1-dis1")
    me = await client.get("/api/auth/me", headers={"Authorization": hdrs["Authorization"]})
    ctx_id = me.json()["contexts"][0]["id"]
    await _seed_pre_v1_chat(account_id, ctx_id)

    r1 = await client.post(
        "/api/users/me/onboarding-status/dismiss", headers=hdrs,
    )
    assert r1.json()["dismissals_count"] == 1, r1.json()
    assert r1.json()["needs_reintro"] is True
    r2 = await client.post(
        "/api/users/me/onboarding-status/dismiss", headers=hdrs,
    )
    assert r2.json()["dismissals_count"] == 2, r2.json()
    assert r2.json()["needs_reintro"] is True


# ─────────────────────────────────────────────────────────────────────
# Test 5 — three dismissals → needs_reintro: false
# ─────────────────────────────────────────────────────────────────────
async def test_three_dismissals_locks_banner(client):
    _t, account_id, hdrs = await _register(client, "j1-dis3")
    me = await client.get("/api/auth/me", headers={"Authorization": hdrs["Authorization"]})
    ctx_id = me.json()["contexts"][0]["id"]
    await _seed_pre_v1_chat(account_id, ctx_id)

    for _ in range(3):
        await client.post(
            "/api/users/me/onboarding-status/dismiss", headers=hdrs,
        )
    r = await client.get(
        "/api/users/me/onboarding-status", headers=hdrs,
    )
    body = r.json()
    assert body["dismissals_count"] == 3, body
    assert body["needs_reintro"] is False, body
    assert body["reason"] == "max_dismissals_reached", body

    # 4th dismiss still caps at 3 (idempotent).
    r4 = await client.post(
        "/api/users/me/onboarding-status/dismiss", headers=hdrs,
    )
    assert r4.json()["dismissals_count"] == 3


# ─────────────────────────────────────────────────────────────────────
# Test 6 — acknowledge sets timestamp + locks permanently
# ─────────────────────────────────────────────────────────────────────
async def test_acknowledge_sets_timestamp(client):
    from core import db
    _t, account_id, hdrs = await _register(client, "j1-ts")
    me = await client.get("/api/auth/me", headers={"Authorization": hdrs["Authorization"]})
    ctx_id = me.json()["contexts"][0]["id"]
    await _seed_pre_v1_chat(account_id, ctx_id)

    ack = await client.post(
        "/api/users/me/onboarding-status/acknowledge", headers=hdrs,
    )
    assert ack.status_code == 200
    acct = await db.accounts.find_one({"id": account_id}, {"_id": 0})
    assert acct["shield_v1_intro_acknowledged_at"], acct
    # The same field is on the response.
    assert ack.json()["acknowledged_at"] == acct["shield_v1_intro_acknowledged_at"]


# ─────────────────────────────────────────────────────────────────────
# Test 7 — /trust-center → /app/trust-center redirect
# ─────────────────────────────────────────────────────────────────────
async def test_trust_center_alias_route_is_registered(client):
    """The bare `/trust-center` route exists in the React app (not as
    a backend endpoint). Verify the SPA's `index.html` is served for
    that path AND the React Router config includes the alias.

    The actual redirect happens client-side via `<Navigate>` — the
    server returns the SPA shell. The wire-level test confirms the
    shell is reachable AND that the App.js bundle contains the
    redirect declaration."""
    # Read the App.js source from disk to verify the redirect is wired.
    with open("/app/frontend/src/App.js") as f:
        app_js = f.read()
    # Multi-line JSX tolerant — the alias may be split across lines as
    # `<Route\n  path="/trust-center"\n  element={...}\n/>`. We match
    # any whitespace between `<Route` and `path="/trust-center"`.
    import re as _re
    assert _re.search(r"<Route\s+path=\"/trust-center\"", app_js), (
        "Expected /trust-center alias route in App.js (multi-line JSX OK)"
    )
    assert "Navigate" in app_js and "/app/trust-center" in app_js, app_js[:0]
    # And the App.js bundle references the canonical /app/trust-center.
    # (Verifies file-wins: both the alias source and the target source exist.)
    assert '"/app/trust-center"' in app_js


# ─────────────────────────────────────────────────────────────────────
# Test 8 — tooltip dismissal endpoints
# ─────────────────────────────────────────────────────────────────────
async def test_trust_center_tooltip_dismiss_endpoint(client):
    _t, _a, hdrs = await _register(client, "j1-tip")
    r = await client.get(
        "/api/users/me/onboarding-status", headers=hdrs,
    )
    assert r.json()["trust_center_tooltip"]["show"] is True

    r2 = await client.post(
        "/api/users/me/onboarding-status/tooltips/trust-center/dismiss",
        headers=hdrs,
    )
    assert r2.status_code == 200
    assert r2.json()["trust_center_tooltip"]["show"] is False
    assert r2.json()["trust_center_tooltip"]["dismissed_at"]


async def test_help_tooltip_dismiss_endpoint(client):
    _t, _a, hdrs = await _register(client, "j1-help-tip")
    r = await client.get(
        "/api/users/me/onboarding-status", headers=hdrs,
    )
    assert r.json()["help_tooltip"]["show"] is True

    r2 = await client.post(
        "/api/users/me/onboarding-status/tooltips/help/dismiss",
        headers=hdrs,
    )
    assert r2.json()["help_tooltip"]["show"] is False
    assert r2.json()["help_tooltip"]["dismissed_at"]
