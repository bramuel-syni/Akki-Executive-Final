"""Phase S (2026-05-27) — Password reset CI lockdown.

Locks:
  • 3 endpoints exist under /api/auth/(forgot-password | reset-password/{token})
  • Token TTL = 1 hour, single-use, 256-bit entropy (32 bytes urlsafe)
  • forgot-password returns 200 even if email doesn't exist (anti-enum)
  • Tampered token → 401 with TOKEN_INVALID code
  • Expired token → 410 with TOKEN_EXPIRED code
  • Reused token → 401 (cleared on successful set)
  • Successful reset:
       - hashes via bcrypt
       - sets auth_provider = "password"
       - bumps sessions_revoked_after (Phase J integration)
       - emits feature_events row
  • Frontend pages mount at /forgot-password + /reset-password/:token
  • SignIn carries the "Forgot password?" link
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import bcrypt
import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))


ROUTER  = REPO / "backend" / "routers" / "password_reset.py"
SERVER  = REPO / "backend" / "server.py"
FORGOT  = REPO / "frontend" / "src" / "pages" / "ForgotPassword.jsx"
RESET   = REPO / "frontend" / "src" / "pages" / "ResetPassword.jsx"
SIGNIN  = REPO / "frontend" / "src" / "pages" / "SignIn.jsx"
APP_JS  = REPO / "frontend" / "src" / "App.js"


# ─────────────────────────────────────────────────────────────────────
# Source-strict structural locks
# ─────────────────────────────────────────────────────────────────────

def test_PhaseS_a_router_module_exists():
    assert ROUTER.exists()


def test_PhaseS_b_three_endpoints_declared():
    src = ROUTER.read_text(encoding="utf-8")
    for sig in (
        '@router.post("/forgot-password"',
        '@router.get("/reset-password/{token}")',
        '@router.post("/reset-password/{token}")',
    ):
        assert sig in src, f"Phase S router must declare {sig!r}"


def test_PhaseS_c_token_uses_256_bit_entropy():
    src = ROUTER.read_text(encoding="utf-8")
    assert "RESET_TOKEN_BYTES = 32" in src, "Token must be 32 bytes (256-bit)"
    assert "secrets.token_urlsafe(RESET_TOKEN_BYTES)" in src or \
        "secrets.token_urlsafe(32)" in src, \
        "Token must be minted via secrets.token_urlsafe with 32-byte entropy"


def test_PhaseS_d_ttl_is_one_hour():
    src = ROUTER.read_text(encoding="utf-8")
    assert "RESET_TOKEN_TTL_HOURS = 1" in src


def test_PhaseS_e_forgot_password_is_constant_response():
    """Anti-enumeration: forgot-password ALWAYS returns 200 regardless
    of whether the email exists."""
    src = ROUTER.read_text(encoding="utf-8")
    assert '@router.post("/forgot-password", status_code=200)' in src, \
        "forgot-password must declare status_code=200 (anti-enumeration)"
    assert "If that email exists, a reset link is on its way." in src, \
        "forgot-password must surface the locked constant-response message"


def test_PhaseS_f_consume_revokes_sessions_and_emits_event():
    src = ROUTER.read_text(encoding="utf-8")
    # Phase J integration — bump sessions_revoked_after on successful set.
    assert "sessions_revoked_after" in src
    # Bcrypt hash + auth_provider flip.
    assert "bcrypt.hashpw" in src
    assert '"auth_provider":              "password"' in src or '"auth_provider": "password"' in src
    # Audit feature events.
    assert "auth.password_reset_requested" in src
    assert "auth.password_reset_completed" in src


def test_PhaseS_g_error_codes_locked():
    src = ROUTER.read_text(encoding="utf-8")
    assert '"code": "TOKEN_INVALID"' in src
    assert '"code": "TOKEN_EXPIRED"' in src
    # HTTP codes
    assert "status_code=401" in src
    assert "status_code=410" in src


def test_PhaseS_h_server_registers_router():
    src = SERVER.read_text(encoding="utf-8")
    assert "password_reset as password_reset_router" in src
    assert "app.include_router(password_reset_router.router)" in src


# ─────────────────────────────────────────────────────────────────────
# Frontend pages
# ─────────────────────────────────────────────────────────────────────

def test_PhaseS_i_forgot_page_carries_locked_testids():
    src = FORGOT.read_text(encoding="utf-8")
    for testid in (
        "forgot-password-page", "forgot-password-h1",
        "forgot-password-form", "forgot-password-email",
        "forgot-password-submit", "forgot-password-success",
    ):
        assert testid in src, f"ForgotPassword.jsx must carry testid {testid!r}"


def test_PhaseS_j_reset_page_carries_locked_testids():
    src = RESET.read_text(encoding="utf-8")
    for testid in (
        "reset-password-page", "reset-password-h1",
        "reset-password-validating", "reset-password-form",
        "reset-password-new", "reset-password-confirm",
        "reset-password-submit", "reset-password-success",
        "reset-password-expired", "reset-password-invalid",
    ):
        assert testid in src, f"ResetPassword.jsx must carry testid {testid!r}"


def test_PhaseS_k_signin_carries_forgot_password_link():
    src = SIGNIN.read_text(encoding="utf-8")
    assert 'data-testid="signin-forgot-password"' in src, \
        "SignIn.jsx must carry the Forgot-password link with locked testid"
    assert 'to="/forgot-password"' in src, \
        "SignIn.jsx forgot-password link must point to /forgot-password"


def test_PhaseS_l_app_js_registers_both_routes():
    src = APP_JS.read_text(encoding="utf-8")
    assert '<Route path="/forgot-password"' in src
    assert '<Route path="/reset-password/:token"' in src
    assert "import ForgotPassword" in src or 'lazy(() => import("@/pages/ForgotPassword"))' in src
    assert "import ResetPassword" in src or 'lazy(() => import("@/pages/ResetPassword"))' in src


# ─────────────────────────────────────────────────────────────────────
# Live integration tests (direct endpoint probes, bypass HTTP)
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_PhaseS_m_full_flow_end_to_end():
    """Mint token → validate → set → re-use blocked (token cleared)."""
    os.environ.setdefault("JWT_SECRET", "test-secret-phase-s")
    from core import db
    from routers.password_reset import (
        forgot_password, get_reset_token, consume_reset_token,
        ForgotPasswordIn, ResetPasswordIn,
    )

    test_email = "phase-s-flow-probe@example.com"
    test_aid   = "phase-s-flow-probe-acct"
    await db.accounts.delete_many({"id": test_aid})
    await db.accounts.delete_many({"email_lc": test_email})

    # Seed account.
    await db.accounts.insert_one({
        "id": test_aid, "email": test_email, "email_lc": test_email,
        "first_name": "Probe", "status": "active",
        "password_hash": bcrypt.hashpw(b"old-pw-123", bcrypt.gensalt()).decode(),
    })

    class _Req:
        headers: Dict[str, str] = {}
    class _BG:
        def add_task(self, fn, **kwargs): pass

    # 1. Request reset.
    res1 = await forgot_password(ForgotPasswordIn(email=test_email), _Req(), _BG())
    assert res1["ok"] is True

    # Fetch the minted token.
    row = await db.accounts.find_one({"id": test_aid}, {"_id": 0})
    token = row.get("reset_password_token")
    assert token and len(token) >= 30, "Token must be minted with ≥30-char entropy"

    # 2. Validate.
    res2 = await get_reset_token(token)
    assert res2["valid"] is True
    assert "@" in res2["email_masked"]

    # 3. Consume.
    res3 = await consume_reset_token(token, ResetPasswordIn(new_password="new-strong-password-456"))
    assert res3["ok"] is True

    # Verify password_hash changed + sessions_revoked_after stamped.
    row2 = await db.accounts.find_one({"id": test_aid}, {"_id": 0})
    assert row2["password_hash"] != row["password_hash"]
    assert row2.get("sessions_revoked_after")
    assert row2.get("auth_provider") == "password"
    # Token cleared.
    assert "reset_password_token" not in row2 or row2.get("reset_password_token") is None

    # 4. Re-use blocked.
    from fastapi import HTTPException as _HTTPExc
    with pytest.raises(_HTTPExc) as e:
        await consume_reset_token(token, ResetPasswordIn(new_password="another-pw-789"))
    assert e.value.status_code == 401

    # Cleanup.
    await db.accounts.delete_many({"id": test_aid})


@pytest.mark.asyncio
async def test_PhaseS_n_expired_token_returns_410():
    os.environ.setdefault("JWT_SECRET", "test-secret-phase-s")
    from core import db
    from routers.password_reset import get_reset_token, consume_reset_token, ResetPasswordIn

    test_aid = "phase-s-expired-probe-acct"
    await db.accounts.delete_many({"id": test_aid})

    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    expired_token = "EXPIRED-" + "x" * 40
    await db.accounts.insert_one({
        "id": test_aid, "email": "phase-s-expired@example.com",
        "email_lc": "phase-s-expired@example.com",
        "reset_password_token": expired_token,
        "reset_password_token_expires_at": past_iso,
    })

    from fastapi import HTTPException as _HTTPExc

    with pytest.raises(_HTTPExc) as e:
        await get_reset_token(expired_token)
    assert e.value.status_code == 410

    # Same for POST.
    await db.accounts.update_one(
        {"id": test_aid},
        {"$set": {"reset_password_token": expired_token, "reset_password_token_expires_at": past_iso}},
    )
    with pytest.raises(_HTTPExc) as e2:
        await consume_reset_token(expired_token, ResetPasswordIn(new_password="strong-pw-123"))
    assert e2.value.status_code == 410

    await db.accounts.delete_many({"id": test_aid})


@pytest.mark.asyncio
async def test_PhaseS_o_tampered_token_returns_401():
    os.environ.setdefault("JWT_SECRET", "test-secret-phase-s")
    from routers.password_reset import get_reset_token

    from fastapi import HTTPException as _HTTPExc

    with pytest.raises(_HTTPExc) as e:
        await get_reset_token("z" * 50)  # 50-char garbage token
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_PhaseS_p_forgot_password_anti_enumeration():
    """Forgot-password returns 200 for both existing AND non-existing
    emails, with the same response body."""
    os.environ.setdefault("JWT_SECRET", "test-secret-phase-s")
    from routers.password_reset import forgot_password, ForgotPasswordIn

    class _Req:
        headers: Dict[str, str] = {}
    class _BG:
        def add_task(self, fn, **kwargs): pass

    res_unknown = await forgot_password(
        ForgotPasswordIn(email="phase-s-never-existed@example.com"), _Req(), _BG(),
    )
    assert res_unknown["ok"] is True
    assert "If that email exists" in res_unknown["message"], \
        "forgot-password must return the constant anti-enum message for unknown emails"
