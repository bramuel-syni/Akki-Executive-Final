"""Capture the 7 H3 Trust Center screenshots.

Run::

    python3 /app/backend/scripts/capture_h3_screenshots.py
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

from playwright.async_api import async_playwright

with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.strip().split("=", 1)[1]
            break

OUT = Path("/app/memory/screenshots/h3")
OUT.mkdir(parents=True, exist_ok=True)

LOGIN_EMAIL = "bramuel@syni.ai"
LOGIN_PASSWORD = "Bramuel2026!"
# A real existing chat with PAN-containing turns.
PRIMARY_CHAT_ID = "9b4c6148-1414-419c-95da-01980e957d2d"
PRIMARY_MID = "c16c6874-5fc5-4076-91c7-03b43881363e"


async def _login(page):
    await page.goto(f"{BASE_URL}/signin", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
    await page.fill('[data-testid="signin-email-input"]', LOGIN_EMAIL)
    await page.fill('[data-testid="signin-password-input"]', LOGIN_PASSWORD)
    await page.click('[data-testid="signin-submit-btn"]')
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2500)


async def shot_01_topbar(pw):
    """Top bar showing the Trust Center entry between Documents and the
    workspace pill."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(f"{BASE_URL}/app", wait_until="networkidle")
        await page.wait_for_timeout(3500)
        # Wait until the topbar's Trust Center button is in the DOM.
        try:
            await page.wait_for_selector(
                '[data-testid="topbar-trust-center-btn"]', timeout=8000,
            )
        except Exception:
            pass
        # Crop to the top bar — clipping by viewport height.
        await page.screenshot(
            path=str(OUT / "01_topbar_entry.png"),
            clip={"x": 0, "y": 0, "width": 1440, "height": 110},
        )
        print(f"OK: {OUT / '01_topbar_entry.png'}")
    finally:
        await browser.close()


async def shot_02_this_session(pw):
    """Full "This session" view — promise + counters + caveats + turns."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={PRIMARY_CHAT_ID}",
            wait_until="networkidle",
        )
        await page.wait_for_selector('[data-testid="tc-session-view"]', timeout=10000)
        await page.wait_for_timeout(2000)
        await page.screenshot(
            path=str(OUT / "02_this_session_view.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '02_this_session_view.png'}")
    finally:
        await browser.close()


async def shot_03_drilldown(pw):
    """Drill-down panel expanded — 4-row evidence comparison."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 1100})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={PRIMARY_CHAT_ID}",
            wait_until="networkidle",
        )
        await page.wait_for_selector('[data-testid="tc-turn-open-btn"]', timeout=10000)
        await page.locator('[data-testid="tc-turn-open-btn"]').first.click()
        await page.wait_for_selector('[data-testid="tc-drilldown-panel"]', timeout=8000)
        await page.wait_for_timeout(2000)
        # Scroll the drilldown into view + screenshot.
        await page.locator('[data-testid="tc-drilldown-panel"]').scroll_into_view_if_needed()
        await page.wait_for_timeout(800)
        await page.screenshot(
            path=str(OUT / "03_drilldown_panel.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '03_drilldown_panel.png'}")
    finally:
        await browser.close()


async def shot_04_all_activity(pw):
    """The cross-conversation activity view."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 1100})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(f"{BASE_URL}/app/trust-center", wait_until="networkidle")
        await page.wait_for_selector('[data-testid="tc-activity-view"]', timeout=10000)
        await page.wait_for_timeout(2500)
        await page.screenshot(
            path=str(OUT / "04_all_activity_view.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '04_all_activity_view.png'}")
    finally:
        await browser.close()


async def shot_05_standards_footer(pw):
    """The standards-aligned footer block — crop to the bottom strip."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={PRIMARY_CHAT_ID}",
            wait_until="networkidle",
        )
        await page.wait_for_selector('[data-testid="tc-standards-footer"]', timeout=8000)
        await page.locator('[data-testid="tc-standards-footer"]').scroll_into_view_if_needed()
        await page.wait_for_timeout(1000)
        box = await page.locator('[data-testid="tc-standards-footer"]').bounding_box()
        if box:
            await page.screenshot(
                path=str(OUT / "05_standards_footer.png"),
                clip={
                    "x": max(0, box["x"] - 30),
                    "y": max(0, box["y"] - 30),
                    "width": min(1440, box["width"] + 60),
                    "height": box["height"] + 50,
                },
            )
        else:
            await page.screenshot(path=str(OUT / "05_standards_footer.png"))
        print(f"OK: {OUT / '05_standards_footer.png'}")
    finally:
        await browser.close()


async def shot_06_plaintext_modal(pw):
    """Plaintext modal opened with the audit-logged notice visible."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 1100})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={PRIMARY_CHAT_ID}",
            wait_until="networkidle",
        )
        await page.wait_for_selector('[data-testid="tc-turn-open-btn"]', timeout=10000)
        await page.locator('[data-testid="tc-turn-open-btn"]').first.click()
        await page.wait_for_selector('[data-testid="tc-view-raw-input-btn"]', timeout=8000)
        await page.locator('[data-testid="tc-view-raw-input-btn"]').click()
        await page.wait_for_selector('[data-testid="tc-plaintext-modal"]', timeout=8000)
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(OUT / "06_plaintext_audit_log.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '06_plaintext_audit_log.png'}")
    finally:
        await browser.close()


async def shot_07_pre_shield_v1(pw):
    """Empty state when "This session" loads for a pre-Shield-v1.x chat.

    Uses a chat row created via API with synisense_audit_ids=[] so the
    backend returns shield_status=pre_shield_v1. Requires direct Mongo
    insert (the existing chats endpoint sets up Shield instrumentation
    eagerly), so we shell out to Python."""
    import subprocess
    # Insert a pre-shield chat for this run.
    pre_id = "preview-pre-" + uuid.uuid4().hex[:10]
    insert_script = (
        "import asyncio\n"
        "from dotenv import load_dotenv; load_dotenv('/app/backend/.env')\n"
        "from core import db\n"
        "async def main():\n"
        f"    me = await db.accounts.find_one({{'email': '{LOGIN_EMAIL}'}}, {{'_id': 0}})\n"
        f"    ctx = await db.memberships.find_one({{'account_id': me['id'], 'status': 'active'}}, {{'_id': 0}})\n"
        "    await db.chats.insert_one({\n"
        f"        'id': '{pre_id}',\n"
        "        'account_id': me['id'],\n"
        "        'context_id': ctx['context_id'],\n"
        "        'title': 'Pre-Shield-v1.x conversation (legacy)',\n"
        "        'model_id': 'claude-sonnet-4-5',\n"
        "        'synisense_audit_ids': [],\n"
        "    })\n"
        f"    print('inserted {pre_id}')\n"
        "asyncio.run(main())"
    )
    subprocess.run(
        ["python3", "-c", insert_script], cwd="/app/backend", check=True,
    )

    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={pre_id}",
            wait_until="networkidle",
        )
        await page.wait_for_selector('[data-testid="tc-session-pre-shield-empty"]', timeout=8000)
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(OUT / "07_pre_shield_v1_state.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '07_pre_shield_v1_state.png'}")
    finally:
        await browser.close()


async def main():
    async with async_playwright() as pw:
        for name, fn in [
            ("01", shot_01_topbar),
            ("02", shot_02_this_session),
            ("03", shot_03_drilldown),
            ("04", shot_04_all_activity),
            ("05", shot_05_standards_footer),
            ("06", shot_06_plaintext_modal),
            ("07", shot_07_pre_shield_v1),
        ]:
            try:
                await fn(pw)
            except Exception as e:
                print(f"FAIL {name}: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
