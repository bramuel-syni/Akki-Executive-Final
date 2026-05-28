"""Wave 4.2.followup.2 — Multi-page runtime audit for silent-fail
brand-purple capsules (2026-02 fork-resume reply dispatch · followup #2).

Audit logic at each page (UPDATED 2026-02 to triage hover-only design
patterns):
  1. Find every element whose `class` contains any brand-purple
     utility — broad selector matching tester's exact query.
  2. For each match, parse the class string into:
       - resting purple tokens (e.g. `bg-ned-purple/10`)
       - hover-only purple tokens (e.g. `hover:bg-brand-rule/30`,
         `focus:bg-brand-rule/40`)
  3. Element classified as:
       - REAL BUG: has resting purple tokens BUT computed
         backgroundColor is transparent or grey. Indicates a token
         the Tailwind compiler dropped (e.g. invalid opacity step
         like `/8` `/6` `/18` — Wave 4.2.followup.2 silent-fail trap).
       - HOVER-ONLY (whitelisted): only hover/focus/active variants
         carry the purple bg; resting transparent is the design.
       - OK: resting purple token + opaque computed background.
  4. Assert REAL_BUG count is zero across all 5 surveyed pages.

Pages surveyed:
  - /app/monitor
  - /app/work-studio
  - /app/task-manager
  - /app/admin/tenants
  - /app/admin/extractions
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


try:
    from playwright.async_api import async_playwright  # noqa: F401
    _HAVE_PW = True
except Exception:  # noqa: BLE001
    _HAVE_PW = False


def _frontend_url() -> str:
    for ln in (REPO / "frontend" / ".env").read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


# JS audit — returns the structured offender list per page with the
# hover-only-vs-resting triage applied. Tester's broader selector
# (`[class*="bg-brand-"], [class*="bg-ned-purple"], [class*="bg-[var(--ned-purple)]"]`)
# matches both pseudo-state utilities AND resting utilities; the JS
# below parses the class string into the two buckets so the audit
# only flags REAL BUGS.
_AUDIT_SCRIPT = r"""
() => {
  const sel = '[class*="bg-brand-"], [class*="bg-ned-purple"], [class*="bg-[var(--ned-purple)]"]';
  const els = document.querySelectorAll(sel);
  const out = [];
  const purpleBgRe = /(?:^|:)bg-(?:brand-[a-z]+|ned-purple|\[var\(--ned-purple\)\])(?:\/\d+)?$/;
  const pseudoRe = /^(?:hover|focus|active|group-hover|peer-hover|focus-visible|focus-within|disabled):/;

  els.forEach((el) => {
    const cls = el.getAttribute('class') || '';
    const tokens = cls.split(/\s+/);
    const purpleTokens = tokens.filter(t => purpleBgRe.test(t));
    if (purpleTokens.length === 0) return;
    const restingPurple = purpleTokens.filter(t => !pseudoRe.test(t));
    const hoverOnlyPurple = purpleTokens.filter(t => pseudoRe.test(t));
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor;
    const isTransparent = (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent');

    // Grey detection — rgb(r,g,b) where r ≈ g ≈ b and not near-white.
    let isGrey = false;
    const m = bg.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (m) {
      const r = +m[1], g = +m[2], b = +m[3];
      const isNeutral = Math.abs(r - g) <= 8 && Math.abs(g - b) <= 8 && Math.abs(r - b) <= 8;
      const isPaperTone = r >= 220;
      isGrey = isNeutral && !isPaperTone && r >= 50 && r <= 180;
    }

    // Classification:
    //  - REAL_BUG: has resting purple token(s) yet renders transparent/grey
    //  - HOVER_ONLY: only pseudo-state purple tokens; resting transparent OK
    //  - OK: resting purple token(s) AND opaque non-grey bg
    let verdict;
    if (restingPurple.length === 0 && hoverOnlyPurple.length > 0) {
      verdict = 'HOVER_ONLY';
    } else if (restingPurple.length > 0 && (isTransparent || isGrey)) {
      verdict = 'REAL_BUG';
    } else {
      verdict = 'OK';
    }

    out.push({
      verdict: verdict,
      tag: el.tagName.toLowerCase(),
      testid: el.getAttribute('data-testid') || null,
      restingPurple: restingPurple,
      hoverOnlyPurple: hoverOnlyPurple,
      bg: bg,
      outerHTMLSnippet: el.outerHTML.substring(0, 220),
    });
  });
  return out;
}
"""


_PAGES = (
    ("/app/monitor",            "Monitor"),
    ("/app/work-studio",        "WorkStudio"),
    ("/app/task-manager",       "TaskManager"),
    ("/app/admin/tenants",      "AdminTenants"),
    ("/app/admin/extractions",  "AdminExtractions"),
)


@pytest.mark.runtime_playwright
@pytest.mark.skipif(not _HAVE_PW, reason="Playwright not installed")
@pytest.mark.asyncio
async def test_no_silent_fail_purple_capsules_across_surveyed_pages():
    """Live audit — at 1280, every element with a brand-purple capsule
    class is classified as REAL_BUG / HOVER_ONLY / OK. The assertion
    locks REAL_BUG count == 0 across all 5 surveyed pages.

    Surfaces a structured offender table in the failure message when
    any REAL_BUGs are found — for fast triage. HOVER_ONLY matches are
    whitelisted by design (ghost-button patterns where the brand-
    purple class is the hover/focus variant, not the resting bg)."""
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
            await page.wait_for_timeout(3500)

            structured_report = []
            for url, name in _PAGES:
                await page.goto(f"{base}{url}", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)
                results = await page.evaluate(_AUDIT_SCRIPT)
                bugs = [r for r in results if r["verdict"] == "REAL_BUG"]
                hover_only = [r for r in results if r["verdict"] == "HOVER_ONLY"]
                ok = [r for r in results if r["verdict"] == "OK"]
                structured_report.append({
                    "page": name, "url": url,
                    "real_bugs": bugs,
                    "hover_only_count": len(hover_only),
                    "ok_count": len(ok),
                })

            total_bugs = sum(len(p["real_bugs"]) for p in structured_report)
            if total_bugs > 0:
                lines = ["", "Wave 4.2.followup.2 REAL BUGS detected:"]
                for p in structured_report:
                    if p["real_bugs"]:
                        lines.append(
                            f"\n  [{p['page']}] {p['url']}: "
                            f"{len(p['real_bugs'])} REAL_BUG "
                            f"({p['hover_only_count']} hover-only whitelisted, "
                            f"{p['ok_count']} OK)"
                        )
                        for o in p["real_bugs"][:10]:
                            lines.append(
                                f"    - tag={o['tag']} testid={o['testid']} "
                                f"bg={o['bg']} "
                                f"resting={o['restingPurple']} "
                                f"html={o['outerHTMLSnippet']!r}"
                            )
                pytest.fail("\n".join(lines))

            # Affirmative: every page surveyed AND classification ran.
            assert len(structured_report) == len(_PAGES), (
                f"Audit must cover all {len(_PAGES)} pages; surveyed "
                f"{len(structured_report)}."
            )
        finally:
            await browser.close()
