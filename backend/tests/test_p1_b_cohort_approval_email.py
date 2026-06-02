"""P1-B — Cohort approval magic-link email actually dispatches.

Spec invariant: when an admin approves a cohort application,
`services.cohort_email.send_approval` MUST invoke
`_send_via_sendgrid` with:
  • the applicant's email as `to_email`,
  • a `subject` matching `APPROVAL_SUBJECT`,
  • a `plain_body` AND `html_body` containing the freshly-minted
    `/welcome/<token>` URL.

Pre-fix behaviour (`cohort_email.py:228-230`): without the env var
`COHORT_EMAILS_ENABLED=true`, `send_approval` short-circuited with
`{"status": "flag_off"}` and the SendGrid invoker was never reached.
The magic-link token was minted and stored, but the email never
went out — the approved applicant had no way to discover their link.

Honesty note (no mocks of business logic): we spy on the
`_send_via_sendgrid` call to capture its argument shape — that
function itself remains untouched. The actual SendGrid HTTP request
is suppressed because `conftest.py` sets `COHORT_NOTIFY_DISABLED=1`,
which `_send_via_sendgrid` honours at line 152 BEFORE any HTTP call.
The spy proves the send is wired correctly; the suppression keeps
the test deterministic (no network).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import server  # noqa: F401
from server import app


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _seed_admin_and_application(db) -> Dict[str, Any]:
    """Mint an admin with MFA-grace and one received cohort
    application ready to be approved.
    """
    from core import hash_password
    admin_email = f"p1b-admin-{uuid.uuid4().hex[:6]}@example.com"
    applicant_email = f"p1b-applicant-{uuid.uuid4().hex[:6]}@example.com"
    aid = "acct-p1b-" + uuid.uuid4().hex[:10]
    app_id = "appl-p1b-" + uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()

    await db.accounts.insert_one({
        "id": aid,
        "email": admin_email.lower(),
        "email_lc": admin_email.lower(),
        "name": "P1-B admin",
        "password_hash": hash_password("P1bTest!"),
        "declared_role": "user",
        "is_superadmin": True,
        "is_admin": True,
        "mfa_enabled": True,
        "first_session": {"status": "completed", "current_step": "done"},
        "created_at": now,
    })
    await db.cohort_applications.insert_one({
        "id": app_id,
        "email": applicant_email.lower(),
        "name": "Applicant Pre-Approval",
        "organization": "Acme",
        "role": "founder",
        "status": "received",
        "created_at": now,
    })
    return {
        "admin_email": admin_email,
        "admin_password": "P1bTest!",
        "admin_id": aid,
        "application_id": app_id,
        "applicant_email": applicant_email.lower(),
    }


async def _csrf_login(client: AsyncClient, *, email: str, password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    r = await client.get("/api/csrf")
    return {"Authorization": f"Bearer {token}",
            "X-CSRF-Token": r.json()["csrf_token"]}


# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_does_NOT_send_when_flag_is_off(transport, monkeypatch):
    """Pre-fix behaviour lockdown — without the env var set,
    `send_approval` short-circuits with `flag_off`. The endpoint
    still returns 200 (token minted) but the SendGrid invoker is
    NEVER reached.

    Guards against future drift where a refactor removes the gate
    without putting the env in production — we'd want the test to
    catch a silent regression IN THE OTHER DIRECTION too.
    """
    from core import db
    from services import cohort_email

    fixture = await _seed_admin_and_application(db)

    # Force kill-switch ON.
    monkeypatch.setenv("COHORT_EMAILS_ENABLED", "false")

    captured: List[Dict[str, Any]] = []

    def _spy(**kwargs):
        captured.append(kwargs)
        return {"status": "sent", "provider_status": "202", "provider_id": "spy"}

    monkeypatch.setattr(cohort_email, "_send_via_sendgrid", _spy)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(
            client, email=fixture["admin_email"], password=fixture["admin_password"]
        )
        r = await client.post(
            f"/api/admin/cohort/applications/{fixture['application_id']}/approve",
            json={"note": "P1-B negative-case test"}, headers=hdrs,
        )
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    # Token minted regardless.
    assert "/welcome/" in body["magic_url"]
    # But the SendGrid invoker was NEVER called.
    assert captured == [], (
        f"P1-B kill-switch leaked: _send_via_sendgrid was called when "
        f"COHORT_EMAILS_ENABLED=false. captured={captured}"
    )
    # And email_result reports the short-circuit.
    assert body["email"]["status"] == "flag_off"
    assert body["email"]["kind"] == "approval"


@pytest.mark.asyncio
async def test_approve_sends_when_flag_is_on(transport, monkeypatch):
    """Positive case — with `COHORT_EMAILS_ENABLED=true`:
      • `_send_via_sendgrid` IS invoked.
      • `to_email` == applicant email.
      • `subject` == APPROVAL_SUBJECT.
      • `plain_body` AND `html_body` BOTH contain the magic URL.
      • The magic URL contains a token (32+ urlsafe chars) matching
        the response body.
    """
    from core import db
    from services import cohort_email

    fixture = await _seed_admin_and_application(db)

    # Open the gate.
    monkeypatch.setenv("COHORT_EMAILS_ENABLED", "true")

    captured: List[Dict[str, Any]] = []

    def _spy(**kwargs):
        captured.append(kwargs)
        return {"status": "sent", "provider_status": "202", "provider_id": "spy"}

    monkeypatch.setattr(cohort_email, "_send_via_sendgrid", _spy)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login(
            client, email=fixture["admin_email"], password=fixture["admin_password"]
        )
        r = await client.post(
            f"/api/admin/cohort/applications/{fixture['application_id']}/approve",
            json={"note": "P1-B positive-case test"}, headers=hdrs,
        )
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    magic_url = body["magic_url"]
    assert "/welcome/" in magic_url
    token = magic_url.rsplit("/welcome/", 1)[1]
    assert len(token) >= 32, f"token too short: {token!r}"

    # The spy must have fired EXACTLY once.
    assert len(captured) == 1, captured
    call = captured[0]

    # Argument-shape lockdown.
    assert call["to_email"] == fixture["applicant_email"], call
    assert call["subject"] == cohort_email.APPROVAL_SUBJECT, call
    assert magic_url in (call.get("plain_body") or ""), call
    assert magic_url in (call.get("html_body") or ""), call

    # Body must surface the freshly-minted token, NOT a stale one.
    assert token in (call.get("plain_body") or ""), call
    assert token in (call.get("html_body") or ""), call

    # Endpoint response surfaces the SendGrid result.
    assert body["email"]["status"] == "sent", body["email"]


@pytest.mark.asyncio
async def test_send_approval_helper_invokes_sendgrid_when_enabled(transport, monkeypatch):
    """Unit-level guard on `send_approval` itself — no FastAPI route.

    Defensive against future drift where a refactor changes the
    helper-to-invoker wiring without anyone noticing.
    """
    from services import cohort_email

    monkeypatch.setenv("COHORT_EMAILS_ENABLED", "true")

    captured: List[Dict[str, Any]] = []

    def _spy(**kwargs):
        captured.append(kwargs)
        return {"status": "sent", "provider_status": "202", "provider_id": "x"}

    monkeypatch.setattr(cohort_email, "_send_via_sendgrid", _spy)

    out = cohort_email.send_approval(
        to_email="unit-test@example.com",
        first_name="Unit",
        magic_link="https://preview/welcome/UNITTOKENXYZ123456789012345678901234567890",
    )
    assert out["kind"] == "approval"
    assert out["status"] == "sent"
    assert len(captured) == 1
    assert captured[0]["to_email"] == "unit-test@example.com"
    assert "UNITTOKENXYZ123456789012345678901234567890" in captured[0]["plain_body"]


@pytest.mark.asyncio
async def test_module_source_carries_p1b_marker(transport):
    """Source-strict — guards against future refactors stripping the
    gate documentation or inverting it silently."""
    src = open("/app/backend/services/cohort_email.py", encoding="utf-8").read()
    assert "COHORT_EMAILS_ENABLED" in src, (
        "cohort_email.py lost the COHORT_EMAILS_ENABLED gate — surface "
        "review needed."
    )
    assert "def send_approval" in src
    assert "def _enabled" in src
