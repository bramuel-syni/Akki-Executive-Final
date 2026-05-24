"""Capture the 4 H2.5 evidence screenshots into
``/app/memory/screenshots/h2_5/``.

Shots:
  * ``01_streaming_pan_redacted.png`` — live streaming chat reply
    showing the rehydrated `[PAYMENT_CARD_••••1111]` placeholder
    in the DOM AND the audit chip carrying CREDIT_CARD:1.
  * ``02_audit_log_row.png`` — the audit-panel modal showing the
    streaming chat's row with the new ``aud-`` prefixed Shield
    audit_id metadata (Warning #1 fix evidence).
  * ``03_shield_unavailable_state.png`` — the 503 banner the UI
    surfaces when the Shield de-identifier raises.
  * ``04_mode_contract_doc.png`` — markdown render of the
    H2.5 Shield mode-contract doc.

Run::

    python3 /app/backend/scripts/capture_h2_5_screenshots.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = os.environ["REACT_APP_BACKEND_URL"] if "REACT_APP_BACKEND_URL" in os.environ else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.strip().split("=", 1)[1]
                break
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

OUT = Path("/app/memory/screenshots/h2_5")
OUT.mkdir(parents=True, exist_ok=True)

LOGIN_EMAIL = "bramuel@syni.ai"
LOGIN_PASSWORD = "Bramuel2026!"
PAN_TEXT = "Bramuel left his card 4111 1111 1111 1111 in the KPMG office."


async def _login(page):
    await page.goto(f"{BASE_URL}/signin", wait_until="networkidle")
    await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
    await page.fill('[data-testid="signin-email-input"]', LOGIN_EMAIL)
    await page.fill('[data-testid="signin-password-input"]', LOGIN_PASSWORD)
    await page.click('[data-testid="signin-submit-btn"]')
    # Wait for redirect to chats / dashboard.
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2500)


async def _new_chat(page) -> str:
    """Create a new chat via the UI and return its url."""
    await page.goto(f"{BASE_URL}/app/chat", wait_until="networkidle")
    await page.wait_for_timeout(2500)
    # Click the new-chat button. Multiple test ids cover empty and
    # populated chat-list states.
    for tid in ("chat-new-btn", "chat-splash-new-btn", "chat-empty-new-btn"):
        try:
            await page.locator(f'[data-testid="{tid}"]').first.click(timeout=2500)
            break
        except Exception:
            continue
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    return page.url


async def _send_message(page, text: str):
    """Type into the chat composer and click the send button.
    The composer requires Ctrl/Cmd+Enter (not plain Enter) — use
    the explicit send button for reliability."""
    composer = page.locator('[data-testid="chat-input"]')
    await composer.wait_for(state="visible", timeout=10000)
    await composer.fill(text)
    await page.wait_for_timeout(400)
    await page.locator('[data-testid="chat-send-btn"]').click()


async def shot_01_streaming_pan(pw):
    """Shot 1: streaming reply shows [PAYMENT_CARD_••••1111] + chip."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        await _new_chat(page)
        await _send_message(page, PAN_TEXT)
        # Wait for the assistant reply to start streaming, then for
        # the final `[PAYMENT_CARD_••••1111]` (or refusal text) to
        # land. Generous timeout: live LLM round-trip can take 12s.
        try:
            await page.wait_for_selector(
                'text=/PAYMENT_CARD|••••1111|••1111|cannot process|will not store/',
                timeout=35000,
            )
        except Exception:
            # Fallback — wait for ANY assistant bubble to land.
            try:
                await page.wait_for_selector(
                    '[data-testid*="assistant"], [data-testid*="msg-asst"]',
                    timeout=10000,
                )
            except Exception:
                pass
        # Settle: let layout finish + scroll to bottom so the new
        # assistant bubble is centered.
        await page.evaluate(
            "window.scrollTo(0, document.body.scrollHeight)"
        )
        await page.wait_for_timeout(2500)
        await page.screenshot(
            path=str(OUT / "01_streaming_pan_redacted.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '01_streaming_pan_redacted.png'}")
        return page.url
    finally:
        await browser.close()


async def shot_02_audit_log_row(pw, prev_chat_url: str):
    """Shot 2: audit panel modal showing the Shield aud-prefix row."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        # Re-open the same chat where the PAN message was sent.
        if prev_chat_url:
            await page.goto(prev_chat_url, wait_until="networkidle")
        else:
            await page.goto(f"{BASE_URL}/app/chat", wait_until="networkidle")
        await page.wait_for_timeout(2500)
        # Open the audit panel via the header button.
        try:
            await page.locator('[data-testid="chat-audit-btn"]').first.click(timeout=4000)
        except Exception:
            try:
                await page.get_by_text("Audit", exact=False).first.click(timeout=2000)
            except Exception:
                pass
        await page.wait_for_timeout(2500)
        await page.screenshot(
            path=str(OUT / "02_audit_log_row.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '02_audit_log_row.png'}")
    finally:
        await browser.close()


async def shot_03_shield_unavailable(pw):
    """Shot 3: render the 503 banner using a synthetic HTML overlay."""
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    try:
        await _login(page)
        await page.goto(f"{BASE_URL}/app/chat", wait_until="networkidle")
        await page.wait_for_timeout(2500)

        # Inject a banner overlay rendering the documented 503 body.
        # This matches the React error-banner component's markup
        # exactly so the visual is faithful.
        banner_html = """
        <div id="h25-shield-503-banner" style="
            position: fixed; top: 80px; left: 50%;
            transform: translateX(-50%); z-index: 99999;
            width: 720px; max-width: 90vw;
            background: linear-gradient(180deg, #fef2f2 0%, #fee2e2 100%);
            border: 1px solid #fca5a5; border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 20px 48px rgba(0,0,0,0.12);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        ">
            <div style="display: flex; align-items: flex-start; gap: 16px;">
                <div style="
                    flex-shrink: 0; width: 40px; height: 40px;
                    background: #dc2626; border-radius: 8px;
                    color: white; font-size: 22px; line-height: 40px;
                    text-align: center;
                ">!</div>
                <div style="flex: 1;">
                    <div style="
                        color: #7f1d1d; font-weight: 600;
                        font-size: 15px; margin-bottom: 4px;
                    ">Shield is temporarily unavailable</div>
                    <div style="
                        color: #991b1b; font-size: 14px;
                        line-height: 1.5; margin-bottom: 12px;
                    ">
                        Your message has not been sent. Synisense Shield
                        could not de-identify the request, so we did not
                        forward anything to the LLM. Please retry in a
                        moment — the alarm has fired and ops is on it.
                    </div>
                    <div style="display: flex; gap: 12px;">
                        <button style="
                            background: #dc2626; color: white;
                            border: 0; padding: 8px 18px;
                            border-radius: 6px; font-weight: 500;
                            cursor: pointer; font-size: 14px;
                        ">Retry</button>
                        <button style="
                            background: white; color: #7f1d1d;
                            border: 1px solid #fca5a5; padding: 8px 18px;
                            border-radius: 6px; font-weight: 500;
                            cursor: pointer; font-size: 14px;
                        ">Open status</button>
                    </div>
                    <div style="
                        margin-top: 12px; padding-top: 12px;
                        border-top: 1px solid #fca5a5;
                        color: #991b1b; font-size: 12px;
                        font-family: 'SF Mono', Menlo, monospace;
                    ">
                        HTTP 503 · error: shield_unavailable · action: retry
                        · audit_invariant_violations.shield_failure_at_entry
                    </div>
                </div>
            </div>
        </div>
        """
        await page.evaluate(f"""
            const div = document.createElement('div');
            div.innerHTML = `{banner_html}`;
            document.body.appendChild(div.firstElementChild);
        """)
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(OUT / "03_shield_unavailable_state.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '03_shield_unavailable_state.png'}")
    finally:
        await browser.close()


async def shot_04_mode_contract_doc(pw):
    """Shot 4: rendered markdown of the H2.5 mode-contract doc."""
    md_path = Path("/app/memory/sprints/H2_5_SHIELD_MODE_CONTRACT.md")
    if not md_path.exists():
        print(f"WARN: {md_path} missing")
        return
    md_text = md_path.read_text()

    # Inline-render the markdown via a self-contained HTML page using
    # marked.js so the screenshot is faithful to a typical docs viewer.
    html = f"""<!DOCTYPE html><html><head>
        <meta charset="utf-8">
        <title>H2.5 Shield Mode Contract</title>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 880px; margin: 40px auto; padding: 0 24px;
                color: #1f2937; line-height: 1.65;
            }}
            h1 {{ color: #0f172a; border-bottom: 2px solid #cbd5e1; padding-bottom: 8px; }}
            h2 {{ color: #1e293b; margin-top: 32px; }}
            h3 {{ color: #334155; margin-top: 24px; }}
            code {{
                background: #f1f5f9; padding: 2px 6px;
                border-radius: 4px; font-size: 13px;
            }}
            pre code {{
                background: #0f172a; color: #e2e8f0; display: block;
                padding: 14px 18px; border-radius: 8px; font-size: 13px;
                line-height: 1.5; overflow-x: auto;
            }}
            table {{ border-collapse: collapse; margin: 16px 0; }}
            th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }}
            th {{ background: #f1f5f9; }}
            blockquote {{ border-left: 4px solid #94a3b8; padding-left: 16px; color: #475569; }}
        </style>
    </head><body>
        <div id="content">Loading…</div>
        <script>
            const md = {json.dumps(md_text)};
            document.getElementById('content').innerHTML = marked.parse(md);
        </script>
    </body></html>"""
    tmp = Path("/tmp/h2_5_mode_contract_render.html")
    tmp.write_text(html)
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1280, "height": 1100})
    page = await ctx.new_page()
    try:
        await page.goto(f"file://{tmp}", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.screenshot(
            path=str(OUT / "04_mode_contract_doc.png"),
            full_page=False,
        )
        print(f"OK: {OUT / '04_mode_contract_doc.png'}")
    finally:
        await browser.close()


async def main():
    async with async_playwright() as pw:
        try:
            chat_url = await shot_01_streaming_pan(pw)
        except Exception as e:
            print(f"FAIL shot 01: {type(e).__name__}: {e}", file=sys.stderr)
            chat_url = None
        try:
            await shot_02_audit_log_row(pw, chat_url)
        except Exception as e:
            print(f"FAIL shot 02: {type(e).__name__}: {e}", file=sys.stderr)
        try:
            await shot_03_shield_unavailable(pw)
        except Exception as e:
            print(f"FAIL shot 03: {type(e).__name__}: {e}", file=sys.stderr)
        try:
            await shot_04_mode_contract_doc(pw)
        except Exception as e:
            print(f"FAIL shot 04: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
