"""Phase K final smoke — load the 5 app surfaces + 2 website surfaces,
record HTTP status + page title + visible primary heading. No Navy
should appear in any computed style for known wordmark elements."""
import asyncio, json
from playwright.async_api import async_playwright

BASE = "https://akki-executive.preview.emergentagent.com"
EMAIL = "admin@akki.ai"
PWD = "AkkiAdmin2026!"

PAGES = [
    ("home_marketing",     "/"),
    ("sandbox",            "/sandbox"),
    ("for_exco",           "/for-exco"),
    ("app_home",           "/app"),
    ("app_solva",          "/app/solva"),
    ("app_chat",           "/app/chat"),
    ("app_cycle",          "/app/cycle"),
    ("app_work_studio",    "/app/work-studio"),
    ("app_monitor",        "/app/monitor"),
]


async def main():
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(user_agent="Mozilla/5.0 PhaseK-Smoke")
        # Login
        r = await ctx.request.post(
            f"{BASE}/api/auth/login",
            data=json.dumps({"email": EMAIL, "password": PWD}),
            headers={"Content-Type": "application/json"},
        )
        if not r.ok:
            print("LOGIN_FAIL", r.status, await r.text())
            await browser.close(); return
        for name, path in PAGES:
            page = await ctx.new_page()
            # Plant active context for authed pages
            await page.add_init_script(
                "window.sessionStorage.setItem('akki_active_context_id', '6e488232-f39c-4cd0-83f9-c00d54a4f3df');"
            )
            try:
                resp = await page.goto(BASE + path, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1800)
                title = await page.title()
                # Sniff for Navy hex in any inline style
                navy_hits = await page.evaluate(
                    """() => {
                        const fp = ['#0a1f44', '#0f1e3a', '#1a2b4c', '#1e3a8a', '#172554'];
                        const hits = [];
                        document.querySelectorAll('*').forEach(el => {
                            const cs = getComputedStyle(el);
                            const cands = [cs.color, cs.backgroundColor, cs.borderColor];
                            cands.forEach(v => {
                                if (!v) return;
                                // computed RGB form — convert known Navy hexes to RGB strings
                                if (v === 'rgb(10, 31, 68)' || v === 'rgb(15, 30, 58)' || v === 'rgb(26, 43, 76)' || v === 'rgb(30, 58, 138)') {
                                    hits.push({tag: el.tagName, v});
                                }
                            });
                        });
                        return hits.length;
                    }"""
                )
                # Find any visible H1
                h1 = await page.evaluate(
                    "() => { const h = document.querySelector('h1'); return h ? h.innerText.slice(0,80) : null; }"
                )
                out.append({
                    "page": name, "path": path,
                    "status": resp.status if resp else None,
                    "title": title,
                    "h1": h1,
                    "navy_computed_styles": navy_hits,
                })
            except Exception as exc:
                out.append({"page": name, "path": path, "error": str(exc)[:120]})
            await page.close()
        await ctx.close(); await browser.close()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
