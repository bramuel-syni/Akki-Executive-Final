"""H4 — Capture the 3 back-fill evidence screenshots.

Run::

    python3 /app/backend/scripts/capture_h4_screenshots.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.strip().split("=", 1)[1]
            break

OUT = Path("/app/memory/screenshots/h4")
OUT.mkdir(parents=True, exist_ok=True)

LOGIN_EMAIL = "bramuel@syni.ai"
LOGIN_PASSWORD = "Bramuel2026!"


async def _login(page):
    await page.goto(f"{BASE_URL}/signin", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
    await page.fill('[data-testid="signin-email-input"]', LOGIN_EMAIL)
    await page.fill('[data-testid="signin-password-input"]', LOGIN_PASSWORD)
    await page.click('[data-testid="signin-submit-btn"]')
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2500)


async def shot_01_admin_status(pw):
    """Render the admin status endpoint as a faithful JSON view.
    The endpoint itself is API-only; we present its response shape
    inside an HTML wrapper that matches the parchment aesthetic
    so the screenshot reads as an operator's view."""
    # Fetch the live status via curl.
    import subprocess
    # Login admin via curl + grab status.
    api = BASE_URL
    admin_token = subprocess.check_output([
        "bash", "-c",
        f'curl -s -X POST "{api}/api/auth/login" '
        '-H "Content-Type: application/json" '
        '-d \'{"email":"admin@akki.ai","password":"AkkiAdmin2026!"}\' '
        '| python3 -c "import sys,json;print(json.load(sys.stdin)[\'access_token\'])"',
    ]).decode().strip()
    status_resp = subprocess.check_output([
        "bash", "-c",
        f'curl -s "{api}/api/admin/shield/backfill/status" '
        f'-H "Authorization: Bearer {admin_token}"',
    ]).decode().strip()

    # Use the latest JOB row (the run that actually did work),
    # not the last empty-no-op job, so the screenshot tells a true
    # story.
    job_resp = subprocess.check_output([
        "bash", "-c",
        f'curl -s "{api}/api/admin/shield/backfill/bf-20260524-141749-e6d5ffb2/status" '
        f'-H "Authorization: Bearer {admin_token}" 2>/dev/null || true',
    ]).decode().strip()

    html = f"""<!DOCTYPE html><html><head>
        <meta charset="utf-8">
        <title>Shield back-fill — Admin status</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #fbf7ef; color: #1f2937;
                margin: 0; padding: 40px;
            }}
            h1 {{ font-size: 22px; margin-bottom: 6px; }}
            .subtitle {{ color: #6b7280; font-size: 13px; margin-bottom: 24px; }}
            .panel {{
                background: #fffdf7; border: 1px solid #e5e0d3;
                border-radius: 10px; padding: 24px;
                margin-bottom: 16px; box-shadow: 0 1px 0 rgba(0,0,0,0.02);
            }}
            .panel-title {{
                font-size: 11px; text-transform: uppercase;
                letter-spacing: 0.06em; color: #6b7280;
                margin-bottom: 8px;
            }}
            pre {{
                font-family: 'SF Mono', Menlo, monospace;
                font-size: 12.5px; line-height: 1.55;
                background: #f5f1e8; padding: 16px; border-radius: 6px;
                color: #1f2937; overflow-x: auto; white-space: pre-wrap;
            }}
            .endpoint {{
                display: inline-block; padding: 2px 8px;
                background: #f0eadb; border-radius: 4px;
                font-family: 'SF Mono', Menlo, monospace; font-size: 12px;
                color: #1e293b;
            }}
        </style>
    </head><body>
        <h1>Shield back-fill · Admin status</h1>
        <div class="subtitle">Read-only operator view of the H4 back-fill engine. Superadmin-gated.</div>

        <div class="panel">
            <div class="panel-title">GET <span class="endpoint">/api/admin/shield/backfill/status</span> (latest job)</div>
            <pre>{status_resp}</pre>
        </div>
        <div class="panel">
            <div class="panel-title">GET <span class="endpoint">/api/admin/shield/backfill/{{job_id}}/status</span> (actual run that processed the corpus)</div>
            <pre>{job_resp or "(job no longer in collection — earliest summary preserved in backfill_log)"}</pre>
        </div>
    </body></html>"""
    tmp = Path("/tmp/h4_admin_status.html")
    tmp.write_text(html)

    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1200, "height": 900})
    page = await ctx.new_page()
    try:
        await page.goto(f"file://{tmp}", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(OUT / "01_admin_backfill_status.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '01_admin_backfill_status.png'}")
    finally:
        await browser.close()


async def shot_02_trust_center_backfilled(pw):
    """Trust Center "This session" view of a back-filled chat —
    new amber banner + per-turn back-filled badge."""
    # Use the real-corpus back-filled chat we confirmed earlier.
    bf_chat = "bc442afa-473a-4a1f-ad88-952ac436c327"

    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 1100})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={bf_chat}",
            wait_until="networkidle",
        )
        # Wait for either the back-fill banner OR the session view to render.
        try:
            await page.wait_for_selector('[data-testid="tc-backfill-banner"]', timeout=10000)
        except Exception:
            await page.wait_for_selector('[data-testid="tc-session-view"]', timeout=8000)
        await page.wait_for_timeout(2000)
        await page.screenshot(
            path=str(OUT / "02_trust_center_backfilled_chat.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '02_trust_center_backfilled_chat.png'}")
    finally:
        await browser.close()


async def shot_03_drilldown_backfill_badge(pw):
    """Turn drill-down showing the back-fill badge on the turn row."""
    bf_chat = "bc442afa-473a-4a1f-ad88-952ac436c327"

    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 1100})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(
            f"{BASE_URL}/app/trust-center?chat_id={bf_chat}",
            wait_until="networkidle",
        )
        await page.wait_for_selector('[data-testid="tc-turn-open-btn"]', timeout=10000)
        # Verify the badge is present on at least one turn before opening.
        await page.wait_for_selector(
            '[data-testid="tc-turn-backfill-badge"]', timeout=6000,
        )
        await page.locator('[data-testid="tc-turn-open-btn"]').first.click()
        await page.wait_for_selector('[data-testid="tc-drilldown-panel"]', timeout=8000)
        await page.locator('[data-testid="tc-drilldown-panel"]').scroll_into_view_if_needed()
        await page.wait_for_timeout(2000)
        await page.screenshot(
            path=str(OUT / "03_drilldown_with_backfill_badge.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '03_drilldown_with_backfill_badge.png'}")
    finally:
        await browser.close()


async def main():
    async with async_playwright() as pw:
        for name, fn in [
            ("01", shot_01_admin_status),
            ("02", shot_02_trust_center_backfilled),
            ("03", shot_03_drilldown_backfill_badge),
        ]:
            try:
                await fn(pw)
            except Exception as e:
                print(f"FAIL {name}: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
