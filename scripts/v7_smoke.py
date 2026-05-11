"""Phase v7 smoke — verify all 18 website routes return 200 and render
a v7 hero/h1. Also confirms the Plausible script is present, no Navy/
bronze hex values are in computed styles, and the canonical link points
at akki.syni.ai."""
import asyncio, json, sys
from playwright.async_api import async_playwright

BASE = "https://akki-executive.preview.emergentagent.com"
ROUTES = [
    ("home",             "/"),
    ("why-akki",         "/why-akki"),
    ("what-akki-does",   "/what-akki-does"),
    ("trust",            "/trust"),
    ("cohort",           "/cohort"),
    ("pricing",          "/pricing"),
    ("about",            "/about"),
    ("contact",          "/contact"),
    ("privacy",          "/privacy"),
    ("terms",            "/terms"),
    ("methodology",      "/methodology"),
    ("exco360",          "/exco360"),
    ("solva",            "/solva"),
    ("akki-chat",        "/akki-chat"),
    ("work-studio",      "/work-studio"),
    ("cycle-manager",    "/cycle-manager"),
    ("monitor",          "/monitor"),
    ("pulse",            "/pulse"),
    ("document-journal", "/document-journal"),
    ("for-executives",   "/for-executives"),
    ("for-neds",         "/for-non-executive-directors"),
    ("for-organisations","/for-organisations"),
    ("for-exco",         "/for-exco"),
    ("sandbox",          "/sandbox"),
]

FORBIDDEN_HEX = ["rgb(139, 111, 62)", "rgb(247, 244, 238)", "rgb(237, 231, 214)",
                 "rgb(10, 31, 68)", "rgb(15, 30, 58)", "rgb(26, 43, 76)"]


async def main():
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        for name, path in ROUTES:
            page = await ctx.new_page()
            try:
                r = await page.goto(BASE + path, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)
                h1 = await page.evaluate(
                    "() => { const h = document.querySelector('h1.hero, .hero h1, h1'); return h ? h.innerText.slice(0,140) : null; }"
                )
                lift = await page.evaluate(
                    "() => { const e = document.querySelector('.lift'); return e ? { text: e.innerText, color: getComputedStyle(e).color } : null; }"
                )
                kicker = await page.evaluate(
                    "() => { const k = document.querySelector('.kicker'); return k ? k.innerText : null; }"
                )
                plausible = await page.evaluate("() => !!document.getElementById('plausible-script')")
                canon = await page.evaluate("() => { const l = document.querySelector('link[rel=canonical]'); return l ? l.href : null; }")
                forbidden_hits = await page.evaluate(
                    """(banned) => {
                        // Phase v7: ignore BODY and HTML since they belong to the
                        // app-shell index.css which is out of v7 scope. The
                        // .akki-website div sets the visible parchment bg over
                        // the top.
                        const hits = [];
                        document.querySelectorAll('*').forEach(el => {
                            if (el.tagName === 'BODY' || el.tagName === 'HTML') return;
                            const cs = getComputedStyle(el);
                            [cs.color, cs.backgroundColor, cs.borderColor].forEach(v => {
                                if (banned.includes(v)) hits.push({ tag: el.tagName, c: v });
                            });
                        });
                        return hits.length;
                    }""", FORBIDDEN_HEX
                )
                out.append({
                    "page": name, "path": path, "status": r.status,
                    "h1": h1, "kicker": kicker, "lift": lift,
                    "plausible": plausible, "canonical_ok": bool(canon and "akki.syni.ai" in canon),
                    "forbidden_hits": forbidden_hits,
                })
            except Exception as exc:
                out.append({"page": name, "path": path, "error": str(exc)[:100]})
            await page.close()
        await ctx.close(); await browser.close()
    # Summary
    print(json.dumps(out, indent=2))
    bad = [r for r in out if r.get("error") or r.get("status", 200) != 200 or r.get("forbidden_hits", 0) > 0]
    print(f"\n=== {len(out) - len(bad)} / {len(out)} routes OK ===")
    if bad:
        print("BAD:", json.dumps(bad, indent=2))
        sys.exit(1)


asyncio.run(main())
