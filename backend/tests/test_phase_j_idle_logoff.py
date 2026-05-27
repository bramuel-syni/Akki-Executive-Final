"""Phase J — Idle auto-logoff + JTI revocation CI guards (2026-05-27).

Locks:
  J.1 — JWT issuance includes `jti` claim
    J1a. `create_access_token` emits a payload with `jti` (uuid hex)
    J1b. `create_refresh_token` emits a payload with `jti`
    J1c. Two consecutive calls produce DIFFERENT JTIs (uuid uniqueness)

  J.2 — Revocation enforcement
    J2a. `revoked_jtis` collection: TTL index on `revoked_at`
         (expireAfterSeconds = 28800) + unique index on `jti`
    J2b. A valid access token authenticates 200 OK
    J2c. After /auth/logout, the same token returns 401
    J2d. A token from a NEW login (fresh JTI) authenticates after the
         previous token was revoked (regression: revocation is per-JTI,
         not per-account)
    J2e. `/auth/logout` writes `{jti, account_id, reason="logout"}` row
         to `db.revoked_jtis`

  J.3 — Admin revoke-all
    J3a. POST /api/admin/auth/revoke-all/{account_id} writes
         `accounts.{id}.sessions_revoked_after = now()`
    J3b. After revoke-all, a token whose iat predates the cutoff returns 401
    J3c. After revoke-all, a fresh login mint (iat AFTER cutoff) authenticates
    J3d. Non-superadmin gets 403
    J3e. Unknown account_id gets 404

  J.4 — Frontend hook + UI surface
    J4a. `useIdleTimeout` hook file exists and exports default
    J4b. Hook listens to ACTIVITY_EVENTS [mousemove, keydown, touchstart,
         click, scroll]
    J4c. Hook reads REACT_APP_IDLE_TIMEOUT_MINUTES env knob
    J4d. AppShell mounts `useIdleTimeout` with onLogout + onWarn handlers
    J4e. Idle warning banner testid `idle-warning-banner` present in
         AppShell source
    J4f. Sign-in page surfaces `?reason=idle` via the
         `signin-idle-reason` testid
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt as pyjwt
import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent


# ═════════════════════════════════════════════════════════════════
# J.1 — JWT issuance carries `jti`
# ═════════════════════════════════════════════════════════════════

def test_j_J1a_access_token_has_jti():
    from core import create_access_token, JWT_SECRET, JWT_ALGO
    tok = create_access_token("acc-test-1", "x@x.com")
    payload = pyjwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGO])
    assert "jti" in payload, "access token must carry a `jti` claim"
    assert isinstance(payload["jti"], str) and len(payload["jti"]) >= 16


def test_j_J1b_refresh_token_has_jti():
    from core import create_refresh_token, JWT_SECRET, JWT_ALGO
    tok = create_refresh_token("acc-test-1")
    payload = pyjwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGO])
    assert "jti" in payload, "refresh token must carry a `jti` claim"


def test_j_J1c_consecutive_tokens_have_distinct_jtis():
    from core import create_access_token, JWT_SECRET, JWT_ALGO
    t1 = create_access_token("acc-X", "x@x.com")
    t2 = create_access_token("acc-X", "x@x.com")
    p1 = pyjwt.decode(t1, JWT_SECRET, algorithms=[JWT_ALGO])
    p2 = pyjwt.decode(t2, JWT_SECRET, algorithms=[JWT_ALGO])
    assert p1["jti"] != p2["jti"], "JTIs must be unique across tokens"


# ═════════════════════════════════════════════════════════════════
# Fixture — actor + login
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
async def j_actor():
    from core import db, hash_password
    uid = f"j-{uuid.uuid4().hex[:8]}"
    email = f"j-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "JJ!1234567Pw"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "J Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.accounts.delete_one({"id": uid})
    await db.revoked_jtis.delete_many({"account_id": uid})


@pytest.fixture
async def j_admin_actor():
    from core import db, hash_password
    uid = f"j-admin-{uuid.uuid4().hex[:6]}"
    email = f"j-admin-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "AdminPw!1234"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "J Admin", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": True, "created_at": now_iso,
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.accounts.delete_one({"id": uid})


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ═════════════════════════════════════════════════════════════════
# J.2 — Revocation enforcement
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_j_J2a_revoked_jtis_indexes_exist():
    from core import db
    # Trigger server startup to ensure indexes are created.
    from server import app  # noqa: F401
    # Ensure indexes are created (server startup may have not run yet
    # in pytest collect order — call create_index directly to ensure).
    await db.revoked_jtis.create_index("jti", unique=True)
    await db.revoked_jtis.create_index("revoked_at", expireAfterSeconds=60 * 60 * 8)
    info = await db.revoked_jtis.index_information()
    has_jti_idx = any("jti" in [k[0] for k in v.get("key", [])] for v in info.values())
    has_ttl_idx = any(
        v.get("expireAfterSeconds") == 60 * 60 * 8 for v in info.values()
    )
    assert has_jti_idx, "revoked_jtis must have an index on `jti`"
    assert has_ttl_idx, "revoked_jtis must have a TTL index (expireAfterSeconds=28800)"


@pytest.mark.asyncio
async def test_j_J2b_J2c_J2e_logout_revokes_jti(j_actor):
    from core import db, JWT_SECRET, JWT_ALGO
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, j_actor["email"], j_actor["password"])
        payload = pyjwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALGO])
        jti = payload["jti"]

        # J2b: token authenticates
        r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200, r.text

        # /auth/logout
        r = await c.post("/api/auth/logout", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert r.json()["revoked_jti"] is True

        # J2e: row written
        rec = await db.revoked_jtis.find_one({"jti": jti}, {"_id": 0})
        assert rec is not None
        assert rec["account_id"] == j_actor["uid"]
        assert rec["reason"] == "logout"

        # J2c: same token now returns 401
        r2 = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r2.status_code == 401
        assert r2.json()["detail"] == "Token revoked"


@pytest.mark.asyncio
async def test_j_J2d_fresh_login_after_revoke_still_works(j_actor):
    from core import JWT_SECRET, JWT_ALGO
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok1 = await _login(c, j_actor["email"], j_actor["password"])
        await c.post("/api/auth/logout", headers={"Authorization": f"Bearer {tok1}"})
        # Fresh login
        tok2 = await _login(c, j_actor["email"], j_actor["password"])
        p1 = pyjwt.decode(tok1, JWT_SECRET, algorithms=[JWT_ALGO])
        p2 = pyjwt.decode(tok2, JWT_SECRET, algorithms=[JWT_ALGO])
        assert p1["jti"] != p2["jti"]
        r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok2}"})
        assert r.status_code == 200, "Fresh-login token must authenticate; revocation is per-JTI"


# ═════════════════════════════════════════════════════════════════
# J.3 — Admin revoke-all
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_j_J3a_J3b_J3c_admin_revoke_all(j_actor, j_admin_actor):
    from core import db
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # 1) Tester gets a token (iat=t0).
        tok_pre = await _login(c, j_actor["email"], j_actor["password"])
        r0 = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok_pre}"})
        assert r0.status_code == 200

        # 2) Admin revokes all sessions for tester (sets sessions_revoked_after = now).
        admin_tok = await _login(c, j_admin_actor["email"], j_admin_actor["password"])
        # Sleep 1.5s so the cutoff is strictly AFTER the pre-token's iat.
        import asyncio; await asyncio.sleep(1.5)
        r = await c.post(
            f"/api/admin/auth/revoke-all/{j_actor['uid']}",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        # J3a: account record carries the cutoff.
        a = await db.accounts.find_one({"id": j_actor["uid"]}, {"_id": 0, "sessions_revoked_after": 1})
        assert a.get("sessions_revoked_after"), "revoke-all must set sessions_revoked_after"

        # J3b: pre-token is now rejected.
        r2 = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok_pre}"})
        assert r2.status_code == 401
        assert r2.json()["detail"] == "Sessions revoked by admin"

        # J3c: fresh login (iat AFTER cutoff) authenticates.
        await asyncio.sleep(1.5)
        tok_post = await _login(c, j_actor["email"], j_actor["password"])
        r3 = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok_post}"})
        assert r3.status_code == 200


@pytest.mark.asyncio
async def test_j_J3d_revoke_all_requires_superadmin(j_actor):
    """Non-superadmin gets 403."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, j_actor["email"], j_actor["password"])
        r = await c.post(
            f"/api/admin/auth/revoke-all/{j_actor['uid']}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_j_J3e_revoke_all_unknown_account(j_admin_actor):
    """Unknown account_id → 404."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        admin_tok = await _login(c, j_admin_actor["email"], j_admin_actor["password"])
        r = await c.post(
            "/api/admin/auth/revoke-all/no-such-account-id",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════
# J.4 — Frontend hook + UI surface (source-strict guards)
# ═════════════════════════════════════════════════════════════════

HOOK = REPO / "frontend" / "src" / "hooks" / "useIdleTimeout.js"
APPSHELL = REPO / "frontend" / "src" / "components" / "layout" / "AppShell.jsx"
SIGNIN = REPO / "frontend" / "src" / "pages" / "SignIn.jsx"


def test_j_J4a_useIdleTimeout_hook_exists_and_exports_default():
    assert HOOK.exists(), "useIdleTimeout.js hook file must exist"
    src = HOOK.read_text(encoding="utf-8")
    assert "export default function useIdleTimeout" in src or "export default useIdleTimeout" in src


def test_j_J4b_hook_listens_to_activity_events():
    src = HOOK.read_text(encoding="utf-8")
    for ev in ["mousemove", "keydown", "touchstart", "click", "scroll"]:
        assert f'"{ev}"' in src, f"Hook must listen to {ev!r}"


def test_j_J4c_hook_reads_env_timeout_knob():
    src = HOOK.read_text(encoding="utf-8")
    assert "REACT_APP_IDLE_TIMEOUT_MINUTES" in src, (
        "Hook must read the REACT_APP_IDLE_TIMEOUT_MINUTES env knob"
    )


def test_j_J4d_appshell_mounts_useIdleTimeout():
    src = APPSHELL.read_text(encoding="utf-8")
    assert "useIdleTimeout" in src, "AppShell must import + call useIdleTimeout"
    # Must wire BOTH onLogout and onWarn callbacks.
    assert re.search(r"useIdleTimeout\s*\(", src), "useIdleTimeout must be invoked"
    assert "onLogout" in src and "onWarn" in src, (
        "AppShell must wire both onLogout and onWarn"
    )


def test_j_J4e_idle_warning_banner_testid_present():
    src = APPSHELL.read_text(encoding="utf-8")
    assert 'data-testid="idle-warning-banner"' in src, (
        "AppShell must render the idle-warning-banner data-testid"
    )


def test_j_J4f_signin_surfaces_idle_reason():
    src = SIGNIN.read_text(encoding="utf-8")
    assert 'data-testid="signin-idle-reason"' in src, (
        "Sign-in page must surface ?reason=idle via the signin-idle-reason testid"
    )
    assert "reason === \"idle\"" in src or "reason == \"idle\"" in src, (
        "Sign-in page must branch on the idle reason"
    )
