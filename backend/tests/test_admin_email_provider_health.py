"""Health-ping endpoint wire + live tests — 2026-05-26.

Covers:
  * Wire: router file exists + endpoint + admin gate + audit row
  * Live: 401 for unauthenticated · 403 for non-admin · 200 with
    expected shape for superadmin · env-var configured booleans
    accurate · Basic-Auth missing → warning surfaced · audit row
    written.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
ADMIN_ROUTER = REPO / "backend" / "routers" / "admin_email_provider.py"


# ── Wire ─────────────────────────────────────────────────────────
def test_health_router_file_exists_and_defines_endpoint():
    src = ADMIN_ROUTER.read_text("utf-8")
    assert '@router.get("/email-provider/health")' in src
    assert "async def email_provider_health" in src
    # Admin gate.
    assert "_require_admin" in src
    assert 'is_superadmin' in src
    # Audit row.
    assert "admin.email_provider.health_check" in src
    # Never logs secret values — we assert no env var key is included
    # via `body[<KEY>] = os.environ[<KEY>]` etc.
    assert "SENDGRID_API_KEY" in src   # named — fine
    # But never expose the API key in the response body.
    # We use the variable `sendgrid_key` internally and only return
    # a configured-boolean elsewhere.
    assert '"sendgrid_key":' not in src
    assert '"api_key":' not in src


def test_health_router_is_registered_in_server():
    src = (REPO / "backend" / "server.py").read_text("utf-8")
    assert "from routers import admin_email_provider as admin_email_provider_router" in src
    assert "app.include_router(admin_email_provider_router.router)" in src


# ── Fixtures ──────────────────────────────────────────────────────
@pytest.fixture
async def admin_actor():
    """Seed a superadmin account + login token."""
    from core import db, hash_password
    uid = f"test-admin-{uuid.uuid4().hex[:8]}"
    email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password(pw),
        "name": "Admin", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.audit_log.delete_many({"account_id": uid})
    await db.accounts.delete_one({"id": uid})


@pytest.fixture
async def regular_actor():
    """Seed a non-admin account."""
    from core import db, hash_password
    uid = f"test-reg-{uuid.uuid4().hex[:8]}"
    email = f"reg-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    await db.accounts.insert_one({
        "id": uid, "email": email,
        "password_hash": hash_password(pw),
        "name": "Reg", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.accounts.delete_one({"id": uid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    body = r.json()
    tok = body.get("access_token") or body.get("token")
    return {"Authorization": f"Bearer {tok}"}


# ── Live ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_health_unauthenticated_returns_401():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/admin/email-provider/health")
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_health_non_admin_returns_403(regular_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, regular_actor)
        r = await c.get("/api/admin/email-provider/health", headers=hdr)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_health_admin_returns_200_with_expected_shape(admin_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, admin_actor)
        r = await c.get("/api/admin/email-provider/health", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    # Required top-level keys.
    for k in (
        "active_provider", "from_email_configured",
        "inbound_domain_configured", "basic_auth_configured",
        "outbound_smoke", "inbound_parse", "warnings",
    ):
        assert k in body, f"missing key {k!r} in {body}"
    # Active provider — one of 3 values.
    assert body["active_provider"] in ("sendgrid", "resend", "none")
    # Outbound smoke shape.
    smoke = body["outbound_smoke"]
    assert "ok" in smoke and isinstance(smoke["ok"], bool)
    assert "sandbox_mode" in smoke
    # Inbound parse shape.
    ipp = body["inbound_parse"]
    assert ipp["webhook_path"] == "/api/inbound/sendgrid"
    assert "ready" in ipp and isinstance(ipp["ready"], bool)
    assert "route_mounted" in ipp and isinstance(ipp["route_mounted"], bool)
    # Inbound route IS mounted (we just hit the app).
    assert ipp["route_mounted"] is True
    # Warnings is always a list.
    assert isinstance(body["warnings"], list)


@pytest.mark.asyncio
async def test_health_reports_correct_env_configured_booleans(admin_actor, monkeypatch):
    """Set + clear env vars and confirm the booleans flip in the
    response."""
    from server import app  # noqa: F401
    # Force a CLEAR state.
    for k in (
        "SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL", "SENDGRID_INBOUND_DOMAIN",
        "SENDGRID_INBOUND_AUTH_USERNAME", "SENDGRID_INBOUND_AUTH_PASSWORD",
        "RESEND_API_KEY", "EMAIL_PROVIDER",
    ):
        monkeypatch.delenv(k, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, admin_actor)
        r = await c.get("/api/admin/email-provider/health", headers=hdr)
    body = r.json()
    assert body["active_provider"] == "none"
    assert body["from_email_configured"] is False
    assert body["inbound_domain_configured"] is False
    assert body["basic_auth_configured"] is False

    # Now set the from-email + inbound-domain (but not the API key)
    # and confirm the booleans flip while provider stays `none`.
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SENDGRID_INBOUND_DOMAIN", "inbound.example.com")
    monkeypatch.setenv("SENDGRID_INBOUND_AUTH_USERNAME", "sg-u")
    monkeypatch.setenv("SENDGRID_INBOUND_AUTH_PASSWORD", "sg-p")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, admin_actor)
        r = await c.get("/api/admin/email-provider/health", headers=hdr)
    body = r.json()
    assert body["active_provider"] == "none"   # still no API key
    assert body["from_email_configured"] is True
    assert body["inbound_domain_configured"] is True
    assert body["basic_auth_configured"] is True


@pytest.mark.asyncio
async def test_health_warns_when_basic_auth_missing(admin_actor, monkeypatch):
    """When SendGrid is wired with inbound domain but Basic Auth is
    NOT configured, the warnings array surfaces the recommendation."""
    from server import app  # noqa: F401
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake-key-for-warning-check")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SENDGRID_INBOUND_DOMAIN", "inbound.example.com")
    monkeypatch.delenv("SENDGRID_INBOUND_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("SENDGRID_INBOUND_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, admin_actor)
        r = await c.get("/api/admin/email-provider/health", headers=hdr)
    body = r.json()
    assert body["active_provider"] == "sendgrid"
    assert body["basic_auth_configured"] is False
    # Warning explicitly mentions Basic Auth.
    assert any("Basic Auth not configured" in w for w in body["warnings"]), body["warnings"]


@pytest.mark.asyncio
async def test_health_writes_audit_row_without_secrets(admin_actor):
    from server import app  # noqa: F401
    from core import db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, admin_actor)
        await c.get("/api/admin/email-provider/health", headers=hdr)
    row = await db.audit_log.find_one({
        "account_id": admin_actor["uid"],
        "action":     "admin.email_provider.health_check",
    })
    assert row is not None
    # Audit metadata never contains the API key value.
    md = row.get("metadata") or {}
    for v in md.values():
        if isinstance(v, str):
            assert "SG." not in v, f"audit row leaked SendGrid key: {v!r}"
    assert "provider" in md
    assert "warnings_count" in md
    assert "outbound_ok" in md


# ── Env scaffolding ─────────────────────────────────────────────
def test_env_example_file_exists_with_sendgrid_block():
    p = REPO / "backend" / ".env.example"
    assert p.exists(), ".env.example missing"
    txt = p.read_text("utf-8")
    for key in (
        "SENDGRID_API_KEY",
        "SENDGRID_FROM_EMAIL",
        "SENDGRID_INBOUND_DOMAIN",
        "SENDGRID_INBOUND_AUTH_USERNAME",
        "SENDGRID_INBOUND_AUTH_PASSWORD",
    ):
        assert f"{key}=" in txt, f"missing {key} in .env.example"
    # Legacy Postmark vars commented out.
    assert "# POSTMARK_API_KEY=" in txt
    assert "# POSTMARK_WEBHOOK_SECRET=" in txt


def test_local_env_file_contains_sendgrid_slots():
    p = REPO / "backend" / ".env"
    assert p.exists(), "/app/backend/.env missing"
    txt = p.read_text("utf-8")
    for key in (
        "SENDGRID_API_KEY",
        "SENDGRID_FROM_EMAIL",
        "SENDGRID_INBOUND_DOMAIN",
        "SENDGRID_INBOUND_AUTH_USERNAME",
        "SENDGRID_INBOUND_AUTH_PASSWORD",
    ):
        # Key must appear (value may be empty — operator fills it).
        assert f"{key}=" in txt, f"missing {key} slot in local .env"


# ── DEPLOY_READINESS doc presence ───────────────────────────────
def test_deploy_readiness_has_user_facing_runbook():
    p = REPO / "memory" / "sprints" / "DEPLOY_READINESS.md"
    txt = p.read_text("utf-8")
    assert "User-facing setup runbook" in txt
    # 3 mechanisms for setting env vars covered.
    assert "Emergent secrets panel" in txt
    assert "VS Code" in txt or "vscode" in txt.lower()
    assert "terminal" in txt.lower()
    # Health-ping curl example present.
    assert "/api/admin/email-provider/health" in txt
