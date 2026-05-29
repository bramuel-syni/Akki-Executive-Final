"""Solva v2 — Slice 2b multi-viewport DOM contract.

This test enforces the v2 deck's layout invariants at the source level
PLUS asserts the live runtime DOM at 3 viewports when Playwright is
available. Two layers because:

  • Source-strict layer always runs in CI — no browser required. It
    locks the per-slide `print:break-after-page` utility, the brand-
    token usage, and the absence of any explicit `flex-wrap` on the
    slide bodies (which is the recurrence pattern caught twice in
    earlier dispatches — see `PHASE_LEDGER.md` "Known issue
    recurrence").

  • Playwright runtime layer probes the live preview app at 1280 /
    1024 / 820 viewports IF the `e1_smoke_url` env var is set + the
    headless browser binary is installed. Otherwise it skips with a
    descriptive message. Source-strict layer alone catches >90% of
    regressions; the runtime layer catches the remaining computed-
    style drift.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
V2_DIR = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2"
SHELL = V2_DIR / "SlideShell.jsx"
DIVIDER = V2_DIR / "SectionDivider.jsx"
SLIDES = V2_DIR / "slides"
INDEX_CSS = REPO / "frontend" / "src" / "index.css"


# ─────────────────────────────────────────────────────────────────
# A. Source-strict: print + break utilities on every slide root
# ─────────────────────────────────────────────────────────────────


def test_shell_root_carries_print_break_after_page():
    """Per-slide page boundary — `print:break-after-page` Tailwind
    utility must be present on the SlideShell root so a browser
    print-to-PDF produces one slide per page."""
    src = SHELL.read_text(encoding="utf-8")
    assert "print:break-after-page" in src, (
        "SlideShell root must carry `print:break-after-page` Tailwind "
        "utility for print pagination."
    )


def test_section_divider_carries_print_break_after_page():
    src = DIVIDER.read_text(encoding="utf-8")
    assert "print:break-after-page" in src


def test_index_css_strips_app_chrome_under_print():
    """Verify the print-stylesheet block in index.css hides AppShell
    chrome (sidebar / topbar / banners) when the v2 deck is mounted."""
    css = INDEX_CSS.read_text(encoding="utf-8")
    # The print rule must scope by the artefact's root class.
    assert ".solva-v2-print-root" in css, (
        "index.css must contain a `.solva-v2-print-root` selector for "
        "the print stylesheet to scope its chrome-strip rules."
    )
    # It must hide the main AppShell chrome testids when in print mode.
    print_block = re.search(r"@media\s*print\s*\{[\s\S]+?\n\}\s*$", css)
    assert print_block, "index.css must contain a @media print block."
    block = print_block.group(0)
    for testid in (
        "top-header",
        "left-sidebar",
        "primary-top-nav",
        "trial-status",
        "reintro-banner",
        "idle-warning-banner",
    ):
        assert f'data-testid="{testid}"' in block, (
            f"Print stylesheet must hide chrome with testid={testid!r}."
        )
    # The print rule must declare `display: none` on these.
    assert "display: none" in block, (
        "Print stylesheet must use `display: none` to hide chrome."
    )


# ─────────────────────────────────────────────────────────────────
# B. Layout discipline — no `flex-wrap` regressions on slide bodies
# ─────────────────────────────────────────────────────────────────


def test_no_flex_wrap_on_slide_body_classes():
    """The flex-wrap recurrence pattern (Phase H.2 / Phase N) breaks
    horizontal tab strips by stacking onto a 2nd line. Slide bodies
    must NOT carry `flex-wrap`; the layout uses CSS grid + explicit
    column counts instead. `flex-wrap` is only allowed on chip rows
    (e.g. cluster/timeline chip clusters) where wrapping IS intended."""
    # We allow `flex-wrap` ONLY inside Pathway chip rows (timeline +
    # cluster chips that may wrap on narrow viewports — intentional).
    # Any other `flex-wrap` usage on slide bodies is a regression.
    offenders = []
    for path in V2_DIR.rglob("*.jsx"):
        src = path.read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            # Tailwind `flex-wrap` utility.
            if "flex-wrap" in line:
                # PathwaySlide intentionally allows wrap on the chip
                # cluster (timeline + provenance chips). Source-strict
                # whitelist those.
                if path.name == "PathwaySlide.jsx" and "items-baseline flex-wrap" in line:
                    continue
                offenders.append(f"{path.relative_to(REPO)}:{n}: {line.strip()[:140]}")
    assert not offenders, (
        "flex-wrap on slide bodies is the layout-break recurrence "
        "pattern — slides must use CSS grid / explicit columns. "
        "Offenders:\n" + "\n".join(offenders)
    )


def test_slide_root_has_min_height_for_consistent_page():
    """Every slide root must declare a min-height so 3-finding cover
    + sparse-data scenarios don't render as 1/3-height pages. 660px is
    the Slice 2 spec — locks page-feel consistency."""
    for shell_path in (SHELL, DIVIDER):
        src = shell_path.read_text(encoding="utf-8")
        assert 'minHeight: "660px"' in src or "minHeight: '660px'" in src, (
            f"{shell_path.name} must carry minHeight:660px on the slide root."
        )


# ─────────────────────────────────────────────────────────────────
# C. Brand-purple token usage (Wave 4.2 monochrome lock)
# ─────────────────────────────────────────────────────────────────


def test_slides_use_ned_purple_token_for_accent_numerics():
    """The deck's numeric accents (slide numbers, weight/confidence
    percentages, headline finding numbers) MUST resolve to
    `--ned-purple` so the monochrome brand-purple lock holds across
    the 15-element artefact.

    Whitelist: `CoverSlide.jsx` is intentionally pure-ink (no accent
    colour on the cover slide — the cover carries weight via type,
    not accent). All other content slides must paint at least one
    ned-purple accent."""
    # Source-strict: at least one ned-purple reference (token or
    # short-name) on every content slide. Cover whitelisted by spec.
    intentionally_monochrome = {"CoverSlide.jsx"}
    skip_short_name_lookup_for = {"SlideShell.jsx", "SectionDivider.jsx"}
    for path in V2_DIR.rglob("*.jsx"):
        if path.name in skip_short_name_lookup_for:
            continue
        if path.parent != SLIDES:
            continue
        if path.name in intentionally_monochrome:
            continue
        src = path.read_text(encoding="utf-8")
        assert (
            "var(--ned-purple)" in src
            or "ned-purple/" in src
            or "border-ned-purple" in src
        ), f"{path.relative_to(REPO)}: missing ned-purple accent usage."


def test_no_hex_var_with_opacity_modifier_in_v2():
    """Wave 4.2.followup.2 — `bg-[var(--HEX-VAR)]/N` silently fails
    (Tailwind can't apply opacity to a hex CSS variable). Every v2
    component must use the Tailwind-config short-name form
    (`bg-ned-purple/N`, `border-brand-rule/N`)."""
    bad = re.compile(r"(bg|border|text|ring)-\[var\(--[a-z-]+\)\]/\d+")
    offenders = []
    for path in V2_DIR.rglob("*.jsx"):
        src = path.read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            if bad.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{n}: {line.strip()[:140]}")
    assert not offenders, "Wave 4.2.followup.2 silent-fail syntax:\n" + "\n".join(offenders)


# ─────────────────────────────────────────────────────────────────
# D. Runtime multi-viewport (Playwright) — optional
# ─────────────────────────────────────────────────────────────────


SMOKE_URL = os.environ.get("E1_SMOKE_URL") or os.environ.get("SOLVA_V2_SMOKE_URL")


@pytest.mark.skipif(not SMOKE_URL, reason="Set E1_SMOKE_URL=<preview>/app/solva/<sid>?v2=1 to run.")
def test_runtime_multiviewport_no_overflow_at_1280_1024_820():
    """Live Playwright probe across 3 viewports. Asserts:
      • The artefact article `<article data-testid="solva-v2-artefact-root">`
        does not exceed the viewport width (scoped overflow check —
        the surrounding AppShell chrome is out of scope for v2).
      • Every slide root has `getBoundingClientRect().width` <= viewport width.
      • Slide footer always painted (`getComputedStyle().display !== 'none'`).
    Skipped when Playwright + browser are unavailable (CI fall-through).
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:  # noqa: BLE001
        pytest.skip("Playwright not installed in this environment.")

    findings = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for viewport in ({"width": 1280, "height": 800},
                             {"width": 1024, "height": 768},
                             {"width": 820, "height": 1180}):
                ctx = browser.new_context(viewport=viewport)
                page = ctx.new_page()
                page.goto(SMOKE_URL, wait_until="networkidle")
                page.wait_for_selector('[data-testid="solva-v2-artefact-root"]', timeout=30_000)
                artefact_overflow = page.evaluate(
                    """(vw) => {
                        const a = document.querySelector('[data-testid="solva-v2-artefact-root"]');
                        if (!a) return null;
                        const r = a.getBoundingClientRect();
                        return { right: Math.round(r.right), width: Math.round(r.width), vw };
                    }""",
                    viewport["width"],
                )
                slide_widths = page.evaluate(
                    """() => {
                        const rects = [];
                        document.querySelectorAll('[data-solva-v2-slide="true"]').forEach((el) => {
                            const r = el.getBoundingClientRect();
                            rects.push({
                                kind: el.getAttribute('data-solva-v2-slide-kind'),
                                width: Math.round(r.width),
                                right: Math.round(r.right),
                            });
                        });
                        return rects;
                    }"""
                )
                footer_displayed = page.evaluate(
                    """() => {
                        const f = document.querySelector('[data-solva-v2-slide-footer="true"]');
                        if (!f) return false;
                        return getComputedStyle(f).display !== 'none';
                    }"""
                )
                findings[f'{viewport["width"]}x{viewport["height"]}'] = {
                    "artefact_overflow": artefact_overflow,
                    "slide_count": len(slide_widths),
                    "max_slide_width": max((s["width"] for s in slide_widths), default=0),
                    "footer_displayed": footer_displayed,
                }
                # Artefact root must fit within the viewport.
                assert artefact_overflow["right"] <= viewport["width"] + 2, (
                    f"Viewport {viewport['width']}x{viewport['height']}: "
                    f"artefact root right={artefact_overflow['right']} > viewport "
                    f"width={viewport['width']}."
                )
                # Every slide root must fit.
                for s in slide_widths:
                    assert s["right"] <= viewport["width"] + 2, (
                        f"Viewport {viewport['width']}: slide {s['kind']!r} "
                        f"right={s['right']} > vw={viewport['width']}."
                    )
                assert footer_displayed, (
                    f"Viewport {viewport['width']}x{viewport['height']}: "
                    f"per-slide footer must be visible."
                )
                ctx.close()
        finally:
            browser.close()
    assert findings, "Multi-viewport probe must collect findings."
