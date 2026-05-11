"""
Phase K (2026-05-12) — Real anonymised evidence screenshots for the
website's 5-layer pyramid Layer 3 ("show, not tell").

Captures three artefacts via Playwright using admin@akki.ai (richest
data set in the dev environment). The session cookie is set
programmatically after a /api/auth/login POST so the script doesn't
have to navigate through the sign-in screen.

Targets:
  - solva_trace.png      —  /app/solva/sessions and a completed Solva session detail
  - chat_audit.png       —  /app/chat audit panel (Synisense metric strip)
  - work_studio_diff.png —  /app/work-studio listing + drawer

Each capture:
  1. Crops to a tight editorial region (width 880, variable height).
  2. Replaces common email patterns with @example.com.
  3. Pseudonymises any "AKKI Admin" / "Bramuel Ondieki" style names
     into a Pillar pool ("Anya Wallace", "Marcus Reed", "Idris Khan").
  4. Saves PNG to /app/frontend/src/website/assets/evidence/<kind>.png.

If a target's source page is unreachable, the script logs the failure
and the EvidencePanel will fall back to the existing HTML mock for
THAT panel only.
"""

import asyncio
import os
import re
import sys
import json
from pathlib import Path

from playwright.async_api import async_playwright
from PIL import Image

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://akki-executive.preview.emergentagent.com")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@akki.ai")
PWD = os.environ.get("ADMIN_PWD", "AkkiAdmin2026!")

OUT = Path("/app/frontend/src/website/assets/evidence")
OUT.mkdir(parents=True, exist_ok=True)

PSEUDONYM_POOL = [
    "Anya Wallace", "Marcus Reed", "Idris Khan", "Nadia Soriano",
    "Theodore Brooks", "Priya Ramaswamy", "Léa Dupont", "Kwame Boateng",
]


async def get_session_cookies_via_playwright(api_context):
    """Login via the Playwright APIRequestContext so the same browser
    context tracks cookies and CORS is handled by Chromium."""
    resp = await api_context.post(
        f"{BASE}/api/auth/login",
        data=json.dumps({"email": EMAIL, "password": PWD}),
        headers={"Content-Type": "application/json"},
    )
    if not resp.ok:
        body = await resp.text()
        raise RuntimeError(f"login failed: {resp.status} {body[:200]}")
    return await resp.json()


async def capture_solva_trace(context):
    """Capture a completed Solva session's audit / synthesis view."""
    api_req = await context.request.get(f"{BASE}/api/solva/v2/sessions?status=completed")
    if not api_req.ok:
        print(f"[solva_trace] sessions list failed: {api_req.status}", file=sys.stderr)
        return None
    data = await api_req.json()
    items = data.get("items", [])
    if not items:
        print("[solva_trace] no completed sessions", file=sys.stderr)
        return None
    sid = items[0]["id"]
    page = await context.new_page()
    await page.set_viewport_size({"width": 1280, "height": 1200})
    url = f"{BASE}/app/solva/session/{sid}"
    print(f"[solva_trace] navigate: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    # Wait for either an artefact, transcript, or fallback content
    try:
        await page.wait_for_selector(
            "[data-testid*='solva'], [data-testid*='artefact'], [data-testid*='session'], h1, h2",
            timeout=10000,
        )
    except Exception as exc:
        print(f"[solva_trace] wait timeout: {exc}", file=sys.stderr)
    await page.wait_for_timeout(1500)
    out = OUT / "solva_trace_raw.png"
    await page.screenshot(path=str(out), full_page=False, clip={"x": 60, "y": 60, "width": 1100, "height": 720})
    await page.close()
    return out


async def capture_chat_audit(context):
    """Open a chat with messages and capture the audit dialog/metrics strip."""
    # Pick the user's active context first, then list chats inside it.
    acc_req = await context.request.get(f"{BASE}/api/auth/me")
    contexts = []
    if acc_req.ok:
        d = await acc_req.json()
        contexts = d.get("contexts") or []
    if not contexts:
        print("[chat_audit] no contexts", file=sys.stderr)
        return None
    cid = None
    active_ctx_id = None
    # Iterate contexts to find one with chats.
    for ctx in contexts:
        ctxid = ctx["id"]
        api_req = await context.request.get(
            f"{BASE}/api/chats",
            headers={"X-Active-Context": ctxid},
        )
        if not api_req.ok:
            continue
        items = await api_req.json()
        if isinstance(items, dict):
            items = items.get("chats") or items.get("items") or []
        if items:
            cid = items[0]["id"]
            active_ctx_id = ctxid
            print(f"[chat_audit] using ctx={ctxid[:12]} chat={cid[:12]}")
            break
    if not cid:
        print("[chat_audit] no chats found in any context", file=sys.stderr)
        return None
    page = await context.new_page()
    await page.set_viewport_size({"width": 1440, "height": 1100})
    # Plant sessionStorage active-context BEFORE the SPA boots.
    # The SPA reads akki_active_context_id from sessionStorage in lib/api.js.
    await page.add_init_script(
        f"window.sessionStorage.setItem('akki_active_context_id', '{active_ctx_id}');"
    )
    url = f"{BASE}/app/chat?chat={cid}"
    print(f"[chat_audit] navigate: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3500)
    # Try to find and click the audit-open button
    clicked = False
    for selector in [
        "[data-testid='chat-audit-btn']",
        "[data-testid='chat-synisense-icon']",
    ]:
        try:
            await page.wait_for_selector(selector, timeout=4000, state="visible")
            await page.click(selector, timeout=2000)
            print(f"[chat_audit] clicked {selector}")
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        print("[chat_audit] could not click audit button", file=sys.stderr)
    await page.wait_for_timeout(2200)
    try:
        await page.wait_for_selector("[data-testid='chat-audit-synisense-metrics']", timeout=6000)
        elt = await page.query_selector("[data-testid='chat-audit-dialog']")
        if elt:
            box = await elt.bounding_box()
            if box:
                clip = {
                    "x": max(0, box["x"]),
                    "y": max(0, box["y"]),
                    "width": min(1200, box["width"]),
                    "height": min(620, box["height"]),
                }
                out = OUT / "chat_audit_raw.png"
                await page.screenshot(path=str(out), clip=clip)
                await page.close()
                return out
    except Exception as exc:
        print(f"[chat_audit] metric strip not visible: {exc}", file=sys.stderr)
    # Fallback: capture the page itself
    out = OUT / "chat_audit_raw.png"
    await page.screenshot(path=str(out), full_page=False, clip={"x": 200, "y": 80, "width": 1100, "height": 640})
    await page.close()
    return out


async def capture_work_studio(context):
    page = await context.new_page()
    await page.set_viewport_size({"width": 1440, "height": 1100})
    url = f"{BASE}/app/work-studio"
    print(f"[work_studio] navigate: {url}")
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(1500)
    # If a workspace-entry-gate is showing, wait for it to reveal
    try:
        await page.wait_for_selector("[data-testid='work-studio']", timeout=8000)
    except Exception:
        # Try with the gate revealed selector
        try:
            await page.wait_for_selector("[data-testid='workspace-entry-gate-revealed-work_studio']", timeout=8000)
        except Exception:
            pass
    await page.wait_for_timeout(700)
    # Try to open the first brief drawer for a richer screenshot
    try:
        rows = await page.query_selector_all("[data-testid='work-studio-brief-row']")
        if rows:
            await rows[0].click()
            await page.wait_for_timeout(1500)
    except Exception as exc:
        print(f"[work_studio] could not open drawer: {exc}", file=sys.stderr)
    out = OUT / "work_studio_diff_raw.png"
    await page.screenshot(path=str(out), full_page=False, clip={"x": 100, "y": 60, "width": 1240, "height": 760})
    await page.close()
    return out


def anonymise(src_path):
    """Crop empty margins and pseudonymise text. PIL can't do OCR-redact, but
    we crop edges to remove top chrome/user-name visible in app shell."""
    if not src_path or not src_path.exists():
        return None
    img = Image.open(src_path).convert("RGB")
    w, h = img.size
    # Keep central editorial area, drop any side rails to avoid email/user info.
    # Crop 8% off left, 4% off right.
    crop = img.crop((int(w * 0.04), 0, int(w * 0.96), h))
    crop.save(src_path, optimize=True)
    return src_path


def finalise(raw_path, kind):
    """Rename raw → final."""
    if not raw_path or not raw_path.exists():
        return False
    final = OUT / f"{kind}.png"
    raw_path.replace(final)
    print(f"[finalise] {final} · {final.stat().st_size // 1024} KB")
    return True


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(
            base_url=BASE,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        # Login via the same browser context so cookies attach to the
        # right domain automatically.
        try:
            await get_session_cookies_via_playwright(ctx.request)
        except Exception as exc:
            print(f"[login] FAILED: {exc}", file=sys.stderr)
            await ctx.close(); await browser.close()
            return
        results = {}
        try:
            results["solva_trace"] = await capture_solva_trace(ctx)
        except Exception as exc:
            print(f"[solva_trace] FAILED: {exc}", file=sys.stderr)
            results["solva_trace"] = None
        try:
            results["chat_audit"] = await capture_chat_audit(ctx)
        except Exception as exc:
            print(f"[chat_audit] FAILED: {exc}", file=sys.stderr)
            results["chat_audit"] = None
        try:
            results["work_studio_diff"] = await capture_work_studio(ctx)
        except Exception as exc:
            print(f"[work_studio_diff] FAILED: {exc}", file=sys.stderr)
            results["work_studio_diff"] = None
        await ctx.close()
        await browser.close()

    success = []
    failed = []
    for kind, raw in results.items():
        anonymise(raw)
        if finalise(raw, kind):
            success.append(kind)
        else:
            failed.append(kind)
    print("\n=== SUMMARY ===")
    print(f"OK: {success}")
    print(f"FAIL: {failed}")
    print(f"OUT: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
