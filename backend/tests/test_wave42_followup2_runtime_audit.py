"""Wave 4.2.followup.2 — Multi-page runtime audit for silent-fail
brand-purple capsules (2026-02 fork-resume reply dispatch).

Issue 4 from the e1_tester cross-surface pass was SUSPECTED but not
captured in structured form. This audit runs the structured probe
in CI so the next regression is caught immediately.

Audit logic at each page:
  1. Find every element whose `class` attribute contains a brand-
     purple capsule pattern (`bg-ned-purple/N`, `bg-[var(--ned-purple)]`,
     `bg-brand-*`, or `bg-[var(--brand-*)]`).
  2. For each match, read `getComputedStyle(el).backgroundColor`.
  3. Flag as OFFENDER if the computed background is `rgba(0,0,0,0)`
     (transparent) — that's the silent-fail trap symptom — OR any
     `rgb(slate-*)` / grey value when the class promised purple.
  4. Assert the offender count is zero across all 5 surveyed pages.

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


# JS audit — returns the structured offender list per page.
_AUDIT_SCRIPT = r"""
() => {
  const purplePatterns = [
    /\bbg-ned-purple\/\d+\b/,
    /\bbg-\[var\(--ned-purple\)\]/,
    /\bbg-brand-/,
    /\bbg-\[var\(--brand-/,
  ];
  const matched = [];
  const all = document.querySelectorAll('[class]');
  all.forEach((el) => {
    const cls = el.getAttribute('class') || '';
    const hasPurple = purplePatterns.some(p => p.test(cls));
    if (!hasPurple) return;
    const cs = getComputedStyle(el);
    const bg = cs.backgroundColor;
    // Offender criteria:
    //   1. Computed bg === rgba(0,0,0,0) → silent-fail trap symptom
    //   2. Computed bg matches a slate/grey value → token drift
    const isTransparent = (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent');
    // Grey detection — rough match for the slate-* palette
    // (rgb(100,116,139) ish range).
    let isGrey = false;
    const m = bg.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (m) {
      const r = +m[1], g = +m[2], b = +m[3];
      // Pure grey: r ≈ g ≈ b AND not within the purple/cream/parchment
      // brand range. Tolerance: 8 units. Filter out white/cream tints.
      const isNeutral = Math.abs(r - g) <= 8 && Math.abs(g - b) <= 8 && Math.abs(r - b) <= 8;
      const isPaperTone = r >= 220;  // parchment-ish / cream
      isGrey = isNeutral && !isPaperTone && r >= 50 && r <= 180;
    }
    if (!isTransparent && !isGrey) return;
    matched.push({
      tag: el.tagName.toLowerCase(),
      testid: el.getAttribute('data-testid') || null,
      classes: cls.substring(0, 200),
      bg: bg,
      reason: isTransparent ? 'transparent' : 'grey-drift',
    });
  });
  return matched;
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
    class must render with a non-transparent, non-grey background.
    Any offender indicates a Wave 4.2.followup.2 silent-fail trap
    (`bg-[var(--HEX-TOKEN)]/N` syntax) OR a token-drift regression.

    Surfaces the structured offender table in the assertion message
    when any offenders are found — for fast triage."""
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
                offenders = await page.evaluate(_AUDIT_SCRIPT)
                structured_report.append({"page": name, "url": url, "offenders": offenders})

            total = sum(len(p["offenders"]) for p in structured_report)
            if total > 0:
                # Render structured table in assertion failure.
                lines = ["", "Wave 4.2.followup.2 silent-fail offenders detected:"]
                for p in structured_report:
                    if p["offenders"]:
                        lines.append(f"\n  [{p['page']}] {p['url']}: {len(p['offenders'])} offenders")
                        for o in p["offenders"][:10]:
                            lines.append(
                                f"    - tag={o['tag']} testid={o['testid']} "
                                f"reason={o['reason']} bg={o['bg']} "
                                f"classes={o['classes'][:120]}"
                            )
                pytest.fail("\n".join(lines))

            # Assert all-clean signal explicitly so a passing test
            # reads as "audit ran across all 5 pages and found 0
            # offenders" not "test was vacuously skipped".
            assert len(structured_report) == len(_PAGES), (
                f"Audit must cover all {len(_PAGES)} pages; surveyed "
                f"{len(structured_report)}."
            )
        finally:
            await browser.close()
