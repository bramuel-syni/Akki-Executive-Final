"""C1-revised Phase A (2026-02) — First-login password-set lockdown.

Coverage:
  • `accounts.has_set_password` field semantics on each entry path:
      - Register (form signup)              → True
      - Direct magic-link consume (cohort)  → False  (no password set)
      - WelcomePage consume mode=password   → True
      - WelcomePage consume on existing acc → True (rotates password)
      - OAuth NEW google account            → False
      - OAuth NEW microsoft account         → False
  • Middleware gating shape:
      - Legacy missing                      → POST passes
      - Strict-bool None (legacy null)      → POST passes
      - Strict-bool True                    → POST passes
      - Strict-bool False                   → POST 428
  • Allowlist semantics:
      - GET passes regardless of flag
      - `/api/auth/set-password` POST passes regardless of flag
      - `/api/auth/me` GET passes regardless of flag
  • `/api/auth/set-password` happy path + idempotency
  • `sanitize_account` surfaces the field (True/False only — legacy
    lean response when missing).

No mocks of business logic. The only stub allowed is the SendGrid
outbound transport seam (none exercised here — pure DB + middleware
+ endpoint shape).
"""
from __future__ import annotations

import uuid
from pathlib import Path

import bcrypt
import pytest
from httpx import AsyncClient, ASGITransport

import server
from core import db


REPO = Path(__file__).resolve().parent.parent.parent
BE   = REPO / "backend"

MIDDLEWARE = BE / "services" / "first_login_password_set.py"
AUTH_ROUTER = BE / "routers" / "auth.py"
CORE_PY = BE / "core.py"
MAGIC_ROUTER = BE / "routers" / "auth_magic.py"
COHORT_MAGIC_ROUTER = BE / "routers" / "cohort_magic_link.py"
OAUTH_ROUTER = BE / "routers" / "auth_oauth.py"
SERVER_PY = BE / "server.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict wire-up
# ═════════════════════════════════════════════════════════════════════
def test_c1a_middleware_file_exists():
    assert MIDDLEWARE.exists()
    src = _read(MIDDLEWARE)
    assert "class FirstLoginPasswordSetGateMiddleware" in src
    assert "has_set_password" in src
    assert "password_set_required" in src
    # Allowlist must include the bypass paths needed for the gated
    # user to recover.
    for p in (
        "/api/csrf",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/refresh",
        "/api/auth/set-password",
        "/api/auth/magic",
        "/api/auth/oauth",
    ):
        assert p in src, p


def test_c1a_middleware_wired_in_server_py():
    src = _read(SERVER_PY)
    assert "FirstLoginPasswordSetGateMiddleware" in src
    assert "from services.first_login_password_set" in src


def test_c1a_set_password_endpoint_exists():
    src = _read(AUTH_ROUTER)
    assert '@router.post("/auth/set-password")' in src
    assert "async def set_password(" in src
    assert "has_set_password" in src
    assert "SetPasswordIn" in src


def test_c1a_sanitize_account_surfaces_flag():
    src = _read(CORE_PY)
    # Only the strict-bool True/False values surface — null/missing
    # stays lean.
    assert 'a.get("has_set_password") is False' in src
    assert 'a.get("has_set_password") is True' in src


def test_c1a_cohort_magic_link_consume_writes_flag():
    src = _read(COHORT_MAGIC_ROUTER)
    assert "has_set_password" in src
    # Password mode sets to True.
    assert '"has_set_password": True' in src
    # Password-mode insert path also sets the field (could be True or
    # False depending on body.mode).
    assert "password_set" in src


def test_c1a_direct_magic_consume_writes_flag_false():
    src = _read(MAGIC_ROUTER)
    assert '"has_set_password": False' in src


def test_c1a_oauth_new_account_writes_flag_false():
    src = _read(OAUTH_ROUTER)
    # Both Google + Microsoft new-account paths.
    assert src.count('"has_set_password": False') >= 2


# ═════════════════════════════════════════════════════════════════════
# Wire-level — middleware behaviour
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
def app():
    return server.app


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


async def _seed_account(*, email: str, has_set_password) -> str:
    """has_set_password may be False, None, True, or omitted (use the
    sentinel ``...`` to omit). Returns the account id."""
    await db.accounts.delete_many({"email": email})
    acc_id = uuid.uuid4().hex
    doc: dict = {
        "id":            acc_id,
        "email":         email,
        "email_lc":      email,
        "password_hash": _hash("TempPass2026!"),
        "name":          "C1A Test",
        "declared_role": "executive",
        "mfa_enabled":   False,
        "is_superadmin": False,
        # `skipped` so FirstSessionGuard doesn't redirect; that's a
        # separate flow.
        "first_session": {"status": "skipped"},
        "created_at":    "2026-02-01T00:00:00+00:00",
    }
    if has_set_password is not Ellipsis:
        doc["has_set_password"] = has_set_password
    await db.accounts.insert_one(doc)
    return acc_id


async def _login_and_get_creds(client: AsyncClient, email: str):
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": csrf},
        json={"email": email, "password": "TempPass2026!"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    # Mint a fresh CSRF on the post-auth jar.
    r = await client.get("/api/csrf")
    csrf2 = r.json()["csrf_token"]
    return token, csrf2


@pytest.mark.asyncio
async def test_c1a_gate_blocks_post_when_flag_strict_false(app):
    email = f"c1a-block-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, csrf = await _login_and_get_creds(c, email)
        # /api/auth/declare-role is a state-changing route NOT in the
        # bypass list — must be 428.
        r = await c.post(
            "/api/auth/declare-role",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf},
            json={"declared_role": "executive"},
        )
        assert r.status_code == 428
        body = r.json()
        assert body["detail"]["code"] == "password_set_required"
        assert "set_password_url" in body["detail"]


@pytest.mark.asyncio
async def test_c1a_gate_allows_post_when_flag_is_true(app):
    email = f"c1a-true-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=True)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, csrf = await _login_and_get_creds(c, email)
        r = await c.post(
            "/api/auth/declare-role",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf},
            json={"declared_role": "executive"},
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_c1a_gate_allows_post_when_flag_is_null(app):
    email = f"c1a-null-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, csrf = await _login_and_get_creds(c, email)
        r = await c.post(
            "/api/auth/declare-role",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf},
            json={"declared_role": "executive"},
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_c1a_gate_allows_post_when_flag_missing(app):
    email = f"c1a-missing-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=Ellipsis)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, csrf = await _login_and_get_creds(c, email)
        r = await c.post(
            "/api/auth/declare-role",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf},
            json={"declared_role": "executive"},
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_c1a_gate_allows_get_when_flag_strict_false(app):
    """GET requests must always pass through so a gated user can
    navigate read-only surfaces while resolving the gate."""
    email = f"c1a-get-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, _csrf = await _login_and_get_creds(c, email)
        r = await c.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["account"]["has_set_password"] is False


@pytest.mark.asyncio
async def test_c1a_set_password_endpoint_flips_flag(app):
    email = f"c1a-set-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=False)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, csrf = await _login_and_get_creds(c, email)
        # 1. Set-password POST is in the allowlist, must succeed.
        r = await c.post(
            "/api/auth/set-password",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf},
            json={"password": "NewSecurePass2026!"},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["account"]["has_set_password"] is True
        # 2. The flag in DB flipped.
        acc = await db.accounts.find_one({"email": email}, {"_id": 0})
        assert acc["has_set_password"] is True
        # 3. The next state-changing POST passes (gate dropped).
        r2 = await c.get("/api/csrf")
        csrf3 = r2.json()["csrf_token"]
        r3 = await c.post(
            "/api/auth/declare-role",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf3},
            json={"declared_role": "executive"},
        )
        assert r3.status_code == 200


@pytest.mark.asyncio
async def test_c1a_set_password_idempotent_when_already_true(app):
    """Calling set-password while the flag is already True rotates
    the password (no error). This matches the existing reset-password
    flow shape."""
    email = f"c1a-idem-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=True)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, csrf = await _login_and_get_creds(c, email)
        r = await c.post(
            "/api/auth/set-password",
            headers={"Authorization": f"Bearer {token}",
                     "X-CSRF-Token": csrf},
            json={"password": "RotatedPass2026!"},
        )
        assert r.status_code == 200
        assert r.json()["account"]["has_set_password"] is True


@pytest.mark.asyncio
async def test_c1a_register_sets_flag_true(app):
    """Form signup → has_set_password=True so the gate never fires."""
    email = f"c1a-reg-{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        r = await c.get("/api/csrf")
        csrf = r.json()["csrf_token"]
        r = await c.post(
            "/api/auth/register",
            headers={"X-CSRF-Token": csrf},
            json={"email": email, "password": "SecurePass2026!",
                  "name": "Reg Test"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["account"]["has_set_password"] is True
        acc = await db.accounts.find_one({"email": email}, {"_id": 0})
        assert acc["has_set_password"] is True


@pytest.mark.asyncio
async def test_c1a_sanitize_account_omits_field_when_legacy_missing(app):
    email = f"c1a-lean-{uuid.uuid4().hex[:8]}@example.com"
    await _seed_account(email=email, has_set_password=Ellipsis)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        token, _ = await _login_and_get_creds(c, email)
        r = await c.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        acc = r.json()["account"]
        # Legacy missing → field absent on the wire.
        assert "has_set_password" not in acc
