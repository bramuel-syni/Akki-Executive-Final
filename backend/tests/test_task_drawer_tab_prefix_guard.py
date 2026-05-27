"""TaskDrawer tab-prefix collision CI guard — 2026-05-26.

Runtime DOM assertion: on a real TaskManager page with an open
TaskDrawer, exactly **5** elements match `[data-testid^="task-drawer-tab-"]`.

This catches the regression class where a child element (e.g., a
tab body) reuses the `task-drawer-tab-*` prefix and inflates the
count in strict tester walkthroughs.

Marked `runtime_playwright` so fast CI can skip it. Run with:
    pytest -m runtime_playwright

Or unconditional:
    pytest tests/test_task_drawer_tab_prefix_guard.py
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest


pytestmark = pytest.mark.runtime_playwright


REPO = Path(__file__).resolve().parent.parent.parent


def _frontend_url() -> str:
    env = REPO / "frontend" / ".env"
    for ln in env.read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


# Skip cleanly when Playwright isn't installed.
try:
    from playwright.async_api import async_playwright   # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


@pytest.mark.skipif(not HAVE_PW, reason="playwright not installed")
@pytest.mark.asyncio
async def test_task_drawer_exactly_five_tab_testids():
    """Open TaskDrawer on the seeded `E2E-Drawer-Test` task and
    assert exactly 5 `[data-testid^="task-drawer-tab-"]` elements."""
    from playwright.async_api import async_playwright
    from core import db

    # Confirm the seed task exists; tester-friendly skip if missing.
    juli = await db.accounts.find_one({"email": "juliusaopio@gmail.com"})
    if not juli:
        pytest.skip("juliusaopio@gmail.com seed account missing")
    task = await db.tasks.find_one({
        "account_id": juli["id"], "name": "E2E-Drawer-Test", "state": "active",
    })
    if not task:
        pytest.skip("E2E-Drawer-Test task not seeded; run seed_e2e_drawer_test.py")

    base = _frontend_url()
    pw_password = os.environ.get("E2E_PASSWORD") or "Julius@Akki!2026-Exec"

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"chromium browser not available: {e!s}"[:200])
        ctx = await browser.new_context(viewport={"width": 1920, "height": 800})
        page = await ctx.new_page()
        # Login
        await page.goto(f"{base}/app", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)
        await page.locator('input[type="email"]').first.fill("juliusaopio@gmail.com")
        await page.locator('input[type="password"]').first.fill(pw_password)
        await page.locator('button:has-text("Sign in")').first.click(force=True)
        await page.wait_for_timeout(4000)
        # Open task manager + click seed card
        await page.goto(f"{base}/app/task-manager", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)
        card = page.locator('[data-card-kind="task"]:has-text("E2E-Drawer-Test")').first
        assert await card.count() > 0, "Seed task card not rendered"
        await card.click(force=True)
        await page.wait_for_timeout(2500)
        # Count tab prefix matches.
        tab_count = await page.locator('[data-testid^="task-drawer-tab-"]').count()
        # Also assert each panel renders distinctly under the new prefix.
        panel_count = await page.locator('[data-testid^="task-drawer-panel-"]').count()
        await browser.close()

    assert tab_count == 5, (
        f"[data-testid^='task-drawer-tab-'] count = {tab_count}, expected 5. "
        "Prefix collision regression — a child element is reusing the "
        "`task-drawer-tab-*` namespace. Rename to `task-drawer-panel-<id>`."
    )
    # Only the active panel is rendered at a time (tabs lazy-render).
    assert panel_count >= 1, (
        f"[data-testid^='task-drawer-panel-'] count = {panel_count}, "
        "expected at least 1 (the active tab's panel)."
    )
