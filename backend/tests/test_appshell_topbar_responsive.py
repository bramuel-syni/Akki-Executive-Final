"""AppShell topbar responsive — Dispatch 2 (2026-05-29).

Locks the responsive behaviour applied to the global topbar's right-
cluster. Before this fix, the cluster carried ~1100px of intrinsic
width (Cmd+K search at 280px, Documents button, Trust Center button,
Help button, keyboard shortcuts button, MentionInbox, CycleContext
indicator, ContinueWithPill, account avatar) and pushed
`document.scrollWidth` to ~1280px even at vw=820.

Fix approach: hide secondary controls below the `lg` (1024px)
breakpoint. The mobile hamburger drawer (already `lg:hidden`) carries
Documents / Trust Center / Help into its menu, so no functionality is
lost — only the topbar surface adapts.

Source-strict layer is what CI runs. The optional Playwright runtime
layer probes the live preview at 1280/1024/820 when E1_SMOKE_URL +
the headless browser are available.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
APPSHELL = REPO / "frontend" / "src" / "components" / "layout" / "AppShell.jsx"


# ─────────────────────────────────────────────────────────────────
# A. Source-strict — responsive utility classes locked
# ─────────────────────────────────────────────────────────────────


def test_documents_button_hidden_below_xl():
    """Documents button hides at sub-1280 so the topbar fits at 1024
    and 820 (the `lg` breakpoint at 1024 was the previous attempt;
    pushed to `xl` because secondary controls re-appeared at exactly
    1024 and pushed scrollWidth back to 1172). The mobile drawer
    carries Document Journal navigation at sub-1280."""
    src = APPSHELL.read_text(encoding="utf-8")
    btn_idx = src.find('data-testid="topbar-documents-btn"')
    assert btn_idx > 0
    block = src[max(0, btn_idx - 800): btn_idx]
    assert "hidden xl:inline-flex" in block


def test_trust_center_button_wrapper_hidden_below_xl():
    """Trust Center button wrapper hides at sub-1280."""
    src = APPSHELL.read_text(encoding="utf-8")
    btn_idx = src.find('data-testid="topbar-trust-center-btn"')
    assert btn_idx > 0
    block = src[max(0, btn_idx - 800): btn_idx]
    assert 'className="relative hidden xl:block"' in block


def test_help_button_wrapper_hidden_below_xl():
    """Help button wrapper hides at sub-1280."""
    src = APPSHELL.read_text(encoding="utf-8")
    btn_idx = src.find('data-testid="topbar-help-btn"')
    assert btn_idx > 0
    block = src[max(0, btn_idx - 1200): btn_idx]
    matches = list(re.finditer(r'<div className="relative([^"]*)"', block))
    assert matches
    last_match = matches[-1]
    classes = last_match.group(1).strip()
    assert "hidden xl:block" in classes


def test_keyboard_shortcuts_button_promoted_to_xl_only():
    """The keyboard shortcuts button is power-user; hide below `xl`
    (1280). `?` keyboard shortcut still works."""
    src = APPSHELL.read_text(encoding="utf-8")
    btn_idx = src.find('data-testid="keyboard-help-btn"')
    assert btn_idx > 0
    block = src[max(0, btn_idx - 400): btn_idx + 400]
    assert "hidden xl:inline-flex" in block, (
        "Keyboard shortcuts button must promote from md to xl so it "
        "only renders ≥1280px."
    )
    # Sanity: the prior `hidden md:inline-flex` is gone for THIS button.
    # (Other md:inline-flex elements may still exist legitimately
    #  e.g. the search button.) Use a tighter window around the testid.
    assert "hidden md:inline-flex" not in block[: block.find('data-testid="keyboard-help-btn"')], (
        "Keyboard shortcuts button must no longer carry "
        "`hidden md:inline-flex` — promoted to xl in Dispatch 2."
    )


def test_search_button_narrows_progressively():
    """The Cmd+K search bar narrows from 340px → 280px → 200px as
    viewport shrinks. This gives the right-cluster headroom at sub-lg."""
    src = APPSHELL.read_text(encoding="utf-8")
    btn_idx = src.find('data-testid="cmdk-launch-btn"')
    assert btn_idx > 0
    block = src[max(0, btn_idx - 600): btn_idx]
    assert "md:w-[200px]" in block, "Search bar must be 200px at md."
    assert "lg:w-[280px]" in block, "Search bar must widen to 280px at lg."
    assert "xl:w-[340px]" in block, "Search bar must widen to 340px at xl."


def test_mobile_hamburger_still_renders_below_lg():
    """The existing mobile hamburger must still surface below lg so
    Documents / Trust Center / Help remain reachable from the drawer."""
    src = APPSHELL.read_text(encoding="utf-8")
    btn_idx = src.find('data-testid="mobile-nav-trigger"')
    assert btn_idx > 0
    block = src[max(0, btn_idx - 400): btn_idx + 200]
    assert "lg:hidden" in block, (
        "Mobile hamburger must keep `lg:hidden` so it surfaces at "
        "sub-1024 to carry the hidden topbar items into a drawer."
    )


# ─────────────────────────────────────────────────────────────────
# B. Optional Playwright runtime probe — sub-1024 scroll width
# ─────────────────────────────────────────────────────────────────


SMOKE_URL = os.environ.get("E1_SMOKE_URL") or os.environ.get("APPSHELL_SMOKE_URL")


@pytest.mark.skipif(
    not SMOKE_URL,
    reason="Set APPSHELL_SMOKE_URL=<authed-preview>/app to run.",
)
def test_runtime_no_horizontal_scroll_across_viewports_and_surfaces():
    """Live probe across 3 viewports × 3 surfaces (/app, /app/work-studio,
    /app/monitor). Asserts `document.scrollWidth ≤ viewport_width + 16px`
    (small scrollbar tolerance) at each combination."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        pytest.skip("Playwright not installed in this environment.")

    findings = {}
    surfaces = ["/app", "/app/work-studio", "/app/monitor"]
    viewports = [(1280, 800), (1024, 768), (820, 1180)]
    base_url = SMOKE_URL.rstrip("/").rsplit("/app", 1)[0]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for surface in surfaces:
                for vw, vh in viewports:
                    ctx = browser.new_context(viewport={"width": vw, "height": vh})
                    page = ctx.new_page()
                    page.goto(base_url + surface, wait_until="networkidle")
                    page.wait_for_timeout(800)
                    scroll_w = page.evaluate(
                        "() => document.documentElement.scrollWidth"
                    )
                    findings[(surface, vw)] = scroll_w
                    assert scroll_w <= vw + 16, (
                        f"Surface={surface!r}, vw={vw}: "
                        f"scrollWidth={scroll_w} > viewport+16. Topbar overflow."
                    )
                    ctx.close()
        finally:
            browser.close()
    assert findings
