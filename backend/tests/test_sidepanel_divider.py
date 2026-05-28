"""Item 6 redo + gap-fix (2026-02 fork-resume) — sign-in-style
hairline divider on Work Studio / Task Manager / Home (CompanyHome
active-context state).

Gold-standard reference: SignIn.jsx:73 — `border-r border-[var(--rule)]`
on the LEFT column. For interior surfaces with both a top horizontal
nav rule and a bottom trust-footer rule, the divider must touch BOTH
rules with zero pixel gap, forming clean T-junctions.

Implementation:
  - AppShell.jsx — back-slot wrapper uses `empty:hidden empty:p-0` to
    collapse to 0px when BackButton self-hides.
  - BackButton.jsx — `TOP_LEVEL_ROUTES` extended to include `/app`,
    `/app/work-studio`, `/app/task-manager` so the back-slot collapses.
  - Each page wrapper carries `relative flex-1` so the absolute-positioned
    divider can use `top:0 bottom:0` and span the full vertical extent
    of the wrapper, which itself spans top-rule → bottom-rule.
  - The divider is an absolute `<div w-px bg-[var(--rule)]>` positioned
    at the column boundary via `style={{ right: 'calc(rail + gap + pad)' }}`.

Previous failure modes captured for PHASE_LEDGER:
  1. (May): `<div w-px bg self-stretch>` between columns → cropped to
     right-rail card-stack height because flexbox sibling stretch only
     stretches to the longest sibling, not to the parent height.
  2. (Feb redo v1): `border-r` on listing column → divider only spanned
     the column's content height, leaving a 51px gap at top (back-slot
     BackButton row) and arbitrary gap at bottom.
  3. (Feb redo v2 — current): `absolute top:0 bottom:0` inside `flex-1
     relative` page wrapper → zero gap at top and bottom.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


pytestmark = pytest.mark.runtime_playwright


try:
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


def _frontend_url() -> str:
    for ln in (REPO / "frontend" / ".env").read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


SURFACES = (
    ("/app/task-manager", "task-manager-vertical-divider"),
    ("/app/work-studio",  "work-studio-vertical-divider"),
    ("/app",              "company-home-vertical-divider"),
)


# ─────────────────────────────────────────────────────────────────
# A. Source-strict — no opacity-modifier syntax on the rule token
#    (Wave 4.2.followup.2 silent-fail trap)
# ─────────────────────────────────────────────────────────────────


def test_no_hex_opacity_modifier_on_rule_token():
    import re
    bad = re.compile(r'(bg|border|text|ring)-\[var\(--rule\)\]/\d')
    offenders = []
    for rel in (
        "pages/TaskManager.jsx", "pages/WorkStudio.jsx",
        "pages/ContextPortfolio.jsx", "pages/CompanyHome.jsx",
    ):
        src = (REPO / "frontend" / "src" / rel).read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            if bad.search(line):
                offenders.append(f"{rel}:{n} → {line.strip()[:120]}")
    assert not offenders, (
        "Wave 4.2.followup.2 silent-fail trap re-introduced:\n  - "
        + "\n  - ".join(offenders)
    )


def test_appshell_back_slot_uses_empty_hidden():
    """The back-slot wrapper must collapse to 0px when BackButton
    self-hides — required for the divider top to flush against the
    top horizontal nav rule."""
    src = (REPO / "frontend" / "src" / "components" / "layout" / "AppShell.jsx").read_text(encoding="utf-8")
    idx = src.find('data-testid="appshell-back-slot"')
    assert idx > 0
    block = src[max(0, idx - 250):idx + 50]
    assert "empty:hidden" in block, (
        "back-slot wrapper must include `empty:hidden` so it collapses "
        "when BackButton returns null"
    )


def test_backbutton_top_level_routes_include_divider_surfaces():
    src = (REPO / "frontend" / "src" / "components" / "layout" / "BackButton.jsx").read_text(encoding="utf-8")
    for route in ('"/app"', '"/app/work-studio"', '"/app/task-manager"'):
        assert route in src, (
            f"BackButton TOP_LEVEL_ROUTES must include {route} so the "
            f"back-slot collapses on the 4 divider surfaces"
        )


# ─────────────────────────────────────────────────────────────────
# B. Runtime — gap precision against horizontal rules
# ─────────────────────────────────────────────────────────────────


async def _sign_in_reference(page, base):
    await page.goto(f"{base}/signin", wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
    await page.wait_for_timeout(1200)
    aside = await page.query_selector('aside.border-r')
    assert aside is not None, "Sign-in reference aside.border-r not found"
    return {
        "border_right_color": await page.evaluate("(el) => getComputedStyle(el).borderRightColor", aside),
    }


async def _login_admin(page, base):
    await page.fill('[data-testid="signin-email-input"]', "admin@akki.ai")
    await page.fill('[data-testid="signin-password-input"]', "AkkiAdmin2026!")
    await page.click('[data-testid="signin-form"] button[type="submit"]')
    await page.wait_for_timeout(3500)


@pytest.mark.skipif(not HAVE_PW, reason="Playwright not installed")
@pytest.mark.asyncio
async def test_divider_flush_against_horizontal_rules_at_1280_and_1024():
    """For each surface at 1280 and 1024:
      - divider.top === nav_rule.bottom (within 1px)
      - divider.bottom === footer.top    (within 1px)
      - divider.color matches sign-in's --rule color
    At 820:
      - divider.width === 0 (display:none / hidden)
    """
    from playwright.async_api import async_playwright
    base = _frontend_url()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()

            ref = await _sign_in_reference(page, base)
            await _login_admin(page, base)

            for vw, vh in ((1280, 900), (1024, 800)):
                for path, divider_tid in SURFACES:
                    await page.set_viewport_size({"width": vw, "height": vh})
                    await page.goto(f"{base}{path}", wait_until="networkidle", timeout=30000)
                    await page.wait_for_selector(
                        f'[data-testid="{divider_tid}"]', timeout=20000,
                    )
                    await page.wait_for_timeout(3000)

                    measurements = await page.evaluate(f"""() => {{
                        const div = document.querySelector('[data-testid="{divider_tid}"]');
                        if (!div) return null;
                        const dr = div.getBoundingClientRect();
                        // Top horizontal rule = the secondary nav row whose
                        // bottom border is the top-rule. It sits at top ~64-128
                        // (sticky behind the primary nav).
                        let nav_rule_bottom = null;
                        const navs = document.querySelectorAll('nav, [class*="h-[64px]"]');
                        for (const el of navs) {{
                            const r = el.getBoundingClientRect();
                            if (r.height >= 60 && r.height <= 80 && r.top >= 50 && r.top <= 150) {{
                                nav_rule_bottom = r.bottom;
                                break;
                            }}
                        }}
                        // Bottom horizontal rule = the trust-footer's top border.
                        let footer_top = null;
                        const footers = document.querySelectorAll('footer, [class*="border-t"]');
                        for (const el of footers) {{
                            const cls = el.className || '';
                            if (typeof cls === 'string' && cls.includes('border-t') && !cls.includes('border-t-0')) {{
                                const r = el.getBoundingClientRect();
                                if (footer_top === null || r.top > footer_top) {{
                                    footer_top = r.top;
                                }}
                            }}
                        }}
                        return {{
                            divider: {{
                                top: dr.top, bottom: dr.bottom,
                                width: dr.width, height: dr.height,
                                color: getComputedStyle(div).backgroundColor,
                            }},
                            nav_rule_bottom: nav_rule_bottom,
                            footer_top: footer_top,
                        }};
                    }}""")

                    assert measurements is not None, f"{path} @ {vw}: divider missing"

                    d = measurements["divider"]
                    nrb = measurements["nav_rule_bottom"]
                    ft = measurements["footer_top"]

                    assert d["width"] == 1, (
                        f"{path} @ {vw}px — divider width must be 1px; got {d['width']}"
                    )

                    # Color must match sign-in's --rule token (both use
                    # the same CSS var; the background-color of our
                    # divider should match sign-in's border-right-color).
                    assert d["color"] == ref["border_right_color"], (
                        f"{path} @ {vw}px — divider color {d['color']!r} != "
                        f"sign-in's {ref['border_right_color']!r}"
                    )

                    # Top gap — divider.top must equal nav_rule.bottom (±1px).
                    assert nrb is not None, f"{path} @ {vw}: no nav rule detected"
                    top_gap = d["top"] - nrb
                    assert abs(top_gap) <= 1, (
                        f"{path} @ {vw}px — divider top is {top_gap:.1f}px "
                        f"away from nav rule bottom (must be ≤1px). divider.top="
                        f"{d['top']:.1f}, nav_rule.bottom={nrb:.1f}"
                    )

                    # Bottom gap — divider.bottom must equal footer.top (±1px).
                    assert ft is not None, f"{path} @ {vw}: no footer detected"
                    bottom_gap = ft - d["bottom"]
                    assert abs(bottom_gap) <= 1, (
                        f"{path} @ {vw}px — divider bottom is {bottom_gap:.1f}px "
                        f"away from footer top (must be ≤1px). divider.bottom="
                        f"{d['bottom']:.1f}, footer.top={ft:.1f}"
                    )

            # ── 820 — divider hidden.
            for path, divider_tid in SURFACES:
                await page.set_viewport_size({"width": 820, "height": 900})
                await page.goto(f"{base}{path}", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                d = await page.query_selector(f'[data-testid="{divider_tid}"]')
                if d is None:
                    # Element may be absent at narrow viewports — that's fine.
                    continue
                box = await d.bounding_box()
                if box is not None:
                    assert box.get("width", 0) == 0, (
                        f"{path} @ 820 — divider must be hidden; "
                        f"got width={box.get('width')}"
                    )
        finally:
            await browser.close()
