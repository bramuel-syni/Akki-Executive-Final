"""
Phase K (2026-05-12) — K6 perf measurement.

Headless-Chromium / Playwright in-container measurement of the
production CRA build. Records:
  - LCP   (Largest Contentful Paint)
  - INP-ish (we report event delays as a proxy — true INP needs user gestures)
  - CLS   (Cumulative Layout Shift)
  - TTI proxy (DOMContentLoaded + loadEventEnd from PerformanceNavigationTiming)
  - Total page weight (sum of all resource transfer sizes)

Container caveat: headless-Chromium running in a Kubernetes pod does
not reflect a real user's network or device. Numbers are INDICATIVE,
not the production figure. The real production figure must be
measured from a real device under the deployed CDN.
"""
import asyncio
import json
import time
from playwright.async_api import async_playwright

URL = "http://localhost:3001/"


async def measure():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()
        weights = {"count": 0, "bytes": 0, "biggest": []}

        async def on_response(resp):
            try:
                hdrs = await resp.all_headers()
                cl = hdrs.get("content-length")
                if cl:
                    n = int(cl)
                    weights["count"] += 1
                    weights["bytes"] += n
                    weights["biggest"].append((n, resp.url[:90]))
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        # Inject LCP + CLS observers BEFORE navigation
        await page.add_init_script(
            """
            window.__perf = { lcp: 0, cls: 0, longTaskMs: 0 };
            new PerformanceObserver((list) => {
              for (const e of list.getEntries()) {
                window.__perf.lcp = Math.max(window.__perf.lcp, e.renderTime || e.loadTime || e.startTime);
              }
            }).observe({ type: 'largest-contentful-paint', buffered: true });
            new PerformanceObserver((list) => {
              for (const e of list.getEntries()) {
                if (!e.hadRecentInput) window.__perf.cls += e.value;
              }
            }).observe({ type: 'layout-shift', buffered: true });
            try {
              new PerformanceObserver((list) => {
                for (const e of list.getEntries()) {
                  window.__perf.longTaskMs += e.duration;
                }
              }).observe({ type: 'longtask', buffered: true });
            } catch {}
            """
        )

        t0 = time.time()
        await page.goto(URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3500)
        elapsed = time.time() - t0

        m = await page.evaluate(
            """() => {
                const nav = performance.getEntriesByType('navigation')[0] || {};
                const paints = performance.getEntriesByType('paint').reduce((a,p) => (a[p.name]=p.startTime, a), {});
                return {
                    lcp: Math.round(window.__perf.lcp),
                    cls: +window.__perf.cls.toFixed(4),
                    longTaskMs: Math.round(window.__perf.longTaskMs),
                    dcl: Math.round(nav.domContentLoadedEventEnd || 0),
                    load: Math.round(nav.loadEventEnd || 0),
                    fcp: Math.round(paints['first-contentful-paint'] || 0),
                    fp:  Math.round(paints['first-paint'] || 0),
                };
            }"""
        )
        await ctx.close()
        await browser.close()

    weights["biggest"].sort(reverse=True)
    weights["biggest"] = weights["biggest"][:8]

    print(json.dumps({
        "url": URL,
        "wall_seconds": round(elapsed, 2),
        "metrics": {
            "lcp_ms": m["lcp"],
            "cls": m["cls"],
            "long_task_total_ms": m["longTaskMs"],
            "fcp_ms": m["fcp"],
            "first_paint_ms": m["fp"],
            "dom_content_loaded_ms": m["dcl"],
            "load_event_end_ms": m["load"],
        },
        "weight": {
            "total_bytes": weights["bytes"],
            "total_kb": round(weights["bytes"] / 1024, 1),
            "resources_counted": weights["count"],
            "biggest": [{"bytes": n, "url": u} for n, u in weights["biggest"]],
        },
        "budget": {
            "lcp_target_ms": 1500,
            "cls_target": 0.10,
            "page_weight_target_kb_landing": 500,
            "page_weight_target_kb_with_screenshots": 1024,
            "tti_target_ms": 2000,
        },
        "caveat": "Container-headless run. Indicative only — production figure must come from a real device under the deployed CDN.",
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(measure())
