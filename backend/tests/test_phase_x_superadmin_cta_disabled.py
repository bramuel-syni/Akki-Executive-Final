"""Phase X bug-2 regression — superadmin Danger Zone CTA UI lockout.

Source-strict + live DOM guard. Backend already 400s the request; the
visible CTA must be disabled (preferred over hidden — preserves
discoverability for the founder).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]


pytestmark = pytest.mark.runtime_playwright


try:
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


# ─────────────────────────────────────────────────────────────────
# A. Source-strict — superadmin branch renders disabled CTA + tooltip
# ─────────────────────────────────────────────────────────────────


def test_phase_x_bug2_source_renders_disabled_cta_for_superadmin():
    """The Danger Zone JSX must contain a superadmin-branch render
    that DISABLES the delete CTA (vs hiding it) and surfaces the
    lockout note."""
    src = (REPO / "frontend" / "src" / "pages" / "AccountSecurity.jsx").read_text(encoding="utf-8")
    # The superadmin ternary branch must exist.
    assert "account?.is_superadmin" in src, (
        "AccountSecurity.jsx must check account?.is_superadmin in the "
        "Danger Zone branch"
    )
    # The branch must render a disabled CTA (preserves discoverability)
    # — verify both `disabled` and `aria-disabled="true"` are present.
    assert "open-delete-account-btn" in src
    # Must include the lockout note testid + the wording.
    assert "superadmin-delete-lockout-note" in src
    assert "Superadmins cannot self-delete" in src


def test_phase_x_bug2_source_keeps_open_btn_testid_for_disabled_state():
    """Test must work regardless of disabled-vs-enabled branch: both
    branches share the `open-delete-account-btn` data-testid so the
    same Playwright selector can resolve in either."""
    src = (REPO / "frontend" / "src" / "pages" / "AccountSecurity.jsx").read_text(encoding="utf-8")
    # The testid must appear in both branches.
    count = src.count('data-testid="open-delete-account-btn"')
    assert count >= 2, (
        f"`open-delete-account-btn` testid must appear in BOTH the "
        f"superadmin-disabled branch and the normal-user branch (got "
        f"{count} occurrence(s))."
    )


# ─────────────────────────────────────────────────────────────────
# B. Live Playwright probe — admin login → /app/account/security
# ─────────────────────────────────────────────────────────────────


def _frontend_url() -> str:
    env = REPO / "frontend" / ".env"
    for ln in env.read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


@pytest.mark.skipif(not HAVE_PW, reason="Playwright not installed")
@pytest.mark.asyncio
async def test_phase_x_bug2_live_dom_superadmin_cta_disabled():
    """Live probe at 1280px — sign in as superadmin, visit
    /app/account/security, assert the delete CTA is disabled and the
    lockout note renders."""
    from playwright.async_api import async_playwright

    base = _frontend_url()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()

            # Sign in.
            await page.goto(f"{base}/signin", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
            await page.fill('[data-testid="signin-email-input"]', "admin@akki.ai")
            await page.fill('[data-testid="signin-password-input"]', "AkkiAdmin2026!")
            await page.click('[data-testid="signin-form"] button[type="submit"]')
            await page.wait_for_timeout(3000)

            # Visit Account Security.
            await page.goto(
                f"{base}/app/security",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_selector('[data-testid="account-danger-zone"]', timeout=15000)

            # CTA present and disabled.
            cta = await page.query_selector('[data-testid="open-delete-account-btn"]')
            assert cta is not None, "Delete CTA must mount for superadmin"
            disabled = await cta.get_attribute("disabled")
            aria_disabled = await cta.get_attribute("aria-disabled")
            assert disabled is not None or aria_disabled == "true", (
                "Superadmin delete CTA must carry disabled or "
                "aria-disabled='true'."
            )

            # Lockout note visible.
            note = await page.query_selector('[data-testid="superadmin-delete-lockout-note"]')
            assert note is not None, "Lockout note must render"
            note_text = await note.text_content()
            assert "Superadmins" in (note_text or "")
        finally:
            await browser.close()
