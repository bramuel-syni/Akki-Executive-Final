"""Phase R.1.followup (2026-02 fork-resume) — Invite Founder CTA + modal
in Cohort Console.

Locks:
    1. CohortConsole header carries the Invite Founder CTA
    2. InviteFounderModal component exists with required testids
    3. Modal posts to /api/admin/cohort/invites (backend already wired)
    4. Live Playwright probe at 1280 — CTA opens modal + validates
       required fields
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# A. Source-strict — CTA + modal wired correctly
# ─────────────────────────────────────────────────────────────────


def test_invite_founder_cta_present_in_cohort_console():
    src = (REPO / "frontend" / "src" / "pages" / "admin" / "CohortConsole.jsx").read_text(encoding="utf-8")
    assert "cohort-console-invite-founder-btn" in src, (
        "CohortConsole.jsx must carry the Invite Founder CTA testid"
    )
    assert "InviteFounderModal" in src, (
        "CohortConsole.jsx must import + mount InviteFounderModal"
    )
    assert "Invite founder" in src, "CTA label must read 'Invite founder'"


def test_invite_founder_modal_component_exists_with_testids():
    p = REPO / "frontend" / "src" / "pages" / "admin" / "InviteFounderModal.jsx"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    required = (
        "invite-founder-modal",
        "invite-founder-email-input",
        "invite-founder-firstname-input",
        "invite-founder-tag-select",
        "invite-founder-trial-days-input",
        "invite-founder-submit-btn",
        "invite-founder-cancel-btn",
        "invite-founder-inline-error",
        "/admin/cohort/invites",
    )
    for needle in required:
        assert needle in src, f"InviteFounderModal.jsx must carry {needle!r}"


def test_invite_founder_modal_cta_uses_brand_purple():
    """Per spec — top-right brand-purple CTA."""
    src = (REPO / "frontend" / "src" / "pages" / "admin" / "CohortConsole.jsx").read_text(encoding="utf-8")
    # The CTA block must reference the brand-purple token.
    cta_idx = src.find("cohort-console-invite-founder-btn")
    assert cta_idx > 0
    cta_block = src[cta_idx:cta_idx + 500]
    assert "var(--ned-purple)" in cta_block, (
        "Invite Founder CTA must use the brand-purple token"
    )


# ─────────────────────────────────────────────────────────────────
# B. Backend wiring intact — POST /api/admin/cohort/invites
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_founder_backend_endpoint_accepts_modal_payload():
    """The exact payload shape the modal sends must POST cleanly."""
    from httpx import AsyncClient, ASGITransport
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    async def _fake_admin():
        return {"id": "admin-r1-fu", "email": "admin@example.com", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_admin
    invite_id = None
    test_email = f"r1fu-{uuid.uuid4().hex[:6]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            payload = {
                "email":              test_email,
                "cohort_tag":         "r1-followup-test",
                "trial_length_days":  14,
                "first_name":         "Test",
            }
            # send=0 to avoid SendGrid sandbox hits in CI.
            r = await c.post("/api/admin/cohort/invites?send=0", json=payload)
            assert r.status_code == 200, r.text
            data = r.json()
            assert "invite_id" in data
            assert "magic_link_url" in data
            assert "expires_at" in data
            invite_id = data["invite_id"]
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        if invite_id:
            await db.cohort_invites.delete_one({"id": invite_id})


# ─────────────────────────────────────────────────────────────────
# C. Live Playwright probe — CTA opens modal at 1280
# ─────────────────────────────────────────────────────────────────


pytestmark_runtime = pytest.mark.runtime_playwright


try:
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


def _frontend_url() -> str:
    for ln in (REPO / "frontend" / ".env").read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


@pytest.mark.skipif(not HAVE_PW, reason="Playwright not installed")
@pytest.mark.runtime_playwright
@pytest.mark.asyncio
async def test_invite_founder_live_cta_opens_modal_at_1280():
    from playwright.async_api import async_playwright
    base = _frontend_url()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            await page.goto(f"{base}/signin", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
            await page.fill('[data-testid="signin-email-input"]', "admin@akki.ai")
            await page.fill('[data-testid="signin-password-input"]', "AkkiAdmin2026!")
            await page.click('[data-testid="signin-form"] button[type="submit"]')
            await page.wait_for_timeout(3000)

            await page.goto(
                f"{base}/app/admin/cohort",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_selector(
                '[data-testid="cohort-console-invite-founder-btn"]',
                timeout=15000,
            )
            cta = await page.query_selector('[data-testid="cohort-console-invite-founder-btn"]')
            assert cta is not None, "CTA must mount"
            await cta.click()
            await page.wait_for_selector(
                '[data-testid="invite-founder-modal"]',
                timeout=10000,
            )
            modal = await page.query_selector('[data-testid="invite-founder-modal"]')
            assert modal is not None
            email_input = await page.query_selector('[data-testid="invite-founder-email-input"]')
            tag_select = await page.query_selector('[data-testid="invite-founder-tag-select"]')
            submit_btn = await page.query_selector('[data-testid="invite-founder-submit-btn"]')
            assert email_input is not None
            assert tag_select is not None
            assert submit_btn is not None
        finally:
            await browser.close()
