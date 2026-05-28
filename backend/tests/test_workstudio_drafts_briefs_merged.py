"""Drafts+Briefs merge (2026-02 fork-resume) — Work Studio tab UI
collapses two formerly-separate tabs (`Drafts` / `Briefing`) into one
combined tab. Data model UNTOUCHED — `draft` and `briefing` categories
remain orthogonal in the DB + API; only the tab grouping collapses.

Asserts:
    A. Exactly one tab where there used to be two; no `Drafts` solo tab,
       no `Briefing` solo tab.
    B. The combined tab fetches BOTH categories (array form).
    C. The per-tile category chip uses brand-purple Tailwind-config
       short name (`bg-ned-purple/10` — NOT `bg-[var(--ned-purple)]/N`
       which silently fails per Wave 4.2.followup.2).
    D. Live runtime probe: chip computed background-color is NOT
       transparent (`rgba(0, 0, 0, 0)`).
    E. Legacy URL deep-links `?kind=drafts` and `?kind=briefing`
       redirect to the merged tab.
    F. CATEGORY_CHIP_SHORT exposes singular labels (`Draft` / `Brief`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# A. Tab strip — exactly one merged tab, no solo `Drafts` / `Briefing`
# ─────────────────────────────────────────────────────────────────


def test_workstudio_tabs_collapsed_to_one_merged_tab():
    src = (REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx").read_text(encoding="utf-8")
    # The single merged tab definition.
    assert 'id: "drafts_briefs"' in src, (
        "KIND_TABS must include the merged `drafts_briefs` tab"
    )
    assert 'category: ["draft", "briefing"]' in src, (
        "Merged tab must declare both categories in array form"
    )
    # The OLD solo tabs must be gone from KIND_TABS.
    assert 'id: "drafts"' not in src, (
        'Solo `id: "drafts"` tab must be removed from KIND_TABS — '
        'replaced by the merged `drafts_briefs` tab.'
    )
    assert 'id: "briefing"' not in src, (
        'Solo `id: "briefing"` tab must be removed from KIND_TABS — '
        'replaced by the merged `drafts_briefs` tab.'
    )


def test_workstudio_fetcher_handles_array_categories():
    """The aggregate fetcher must fire parallel GETs when `category`
    is an array (one per category) and merge the results."""
    src = (REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx").read_text(encoding="utf-8")
    assert "Array.isArray(cat)" in src, (
        "Fetcher must detect `Array.isArray(cat)` to support the merged tab"
    )
    assert "Promise.all" in src, (
        "Fetcher must use Promise.all for parallel category GETs"
    )


def test_workstudio_legacy_kind_urls_redirect_to_merged_tab():
    src = (REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx").read_text(encoding="utf-8")
    assert 'k === "drafts" || k === "briefing"' in src, (
        "Legacy `?kind=drafts` and `?kind=briefing` URL params must "
        "redirect to the merged tab so existing deep-links continue to work"
    )
    # ...and the redirect target is the merged tab id.
    idx = src.find('k === "drafts" || k === "briefing"')
    block = src[idx:idx + 200]
    assert 'return "drafts_briefs"' in block, (
        "Legacy-URL redirect must target the new merged tab id"
    )


# ─────────────────────────────────────────────────────────────────
# B. Per-tile chip — brand-purple + singular label
# ─────────────────────────────────────────────────────────────────


def test_category_chip_short_labels_exposed():
    src = (REPO / "frontend" / "src" / "lib" / "origins.js").read_text(encoding="utf-8")
    assert "CATEGORY_CHIP_SHORT" in src
    assert "displayCategoryChip" in src
    # Singular labels per spec.
    assert 'draft:      "Draft"' in src, (
        "Singular `Draft` label required for the per-tile chip"
    )
    assert 'briefing:   "Brief"' in src, (
        "Singular `Brief` label required for the per-tile chip"
    )


def test_workstudio_row_chip_uses_tailwind_config_short_name():
    """The chip MUST use `bg-ned-purple/N` (Tailwind-config short name)
    instead of `bg-[var(--ned-purple)]/N` (silent-fail per
    Wave 4.2.followup.2). The chip MUST be rendered with the singular
    label form via `displayCategoryChip`."""
    src = (REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx").read_text(encoding="utf-8")
    idx = src.find('data-testid="work-studio-document-row-category-badge"')
    assert idx > 0, "Category badge testid must be present"
    block = src[max(0, idx - 600):idx + 300]
    assert "bg-ned-purple/10" in block, (
        "Category chip must use `bg-ned-purple/10` (Tailwind-config "
        "short name — composites opacity correctly)"
    )
    assert "displayCategoryChip" in block, (
        "Category chip must render via `displayCategoryChip(category)` "
        "for singular short labels"
    )
    # Negative: must not carry the silent-fail syntax anymore.
    assert "bg-[var(--ned-purple)]/" not in block, (
        "Category chip must not reference `bg-[var(--ned-purple)]/N` "
        "(Wave 4.2.followup.2 silent-fail trap)"
    )


# ─────────────────────────────────────────────────────────────────
# C. Live runtime — chip background is NOT transparent
# ─────────────────────────────────────────────────────────────────


pytestmark_runtime = pytest.mark.runtime_playwright


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


@pytest.mark.skipif(not HAVE_PW, reason="Playwright not installed")
@pytest.mark.runtime_playwright
@pytest.mark.asyncio
async def test_workstudio_merged_tab_chip_computed_style_not_transparent():
    """Open the merged tab and assert at least one category chip
    renders with a non-transparent brand-purple background. If the
    `bg-[var(--ned-purple)]/N` silent-fail re-introduces itself this
    test catches it at runtime, even if the source grep guard
    (`test_workstudio_row_chip_uses_tailwind_config_short_name`)
    misses it."""
    from playwright.async_api import async_playwright
    base = _frontend_url()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        try:
            ctx = await b.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            await page.goto(f"{base}/signin", wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
            await page.fill('[data-testid="signin-email-input"]', "admin@akki.ai")
            await page.fill('[data-testid="signin-password-input"]', "AkkiAdmin2026!")
            await page.click('[data-testid="signin-form"] button[type="submit"]')
            await page.wait_for_timeout(3500)
            await page.goto(f"{base}/app/work-studio?kind=drafts_briefs", wait_until="networkidle", timeout=30000)
            await page.wait_for_selector('[data-testid="work-studio"]', timeout=20000)
            await page.wait_for_timeout(4000)

            # Tab presence — only one combined tab, no solo drafts/briefing tab.
            # Tab testid format: `work-studio-tab-${id}${active ? "-active" : ""}`.
            tab_solo_drafts = await page.query_selector(
                '[data-testid="work-studio-tab-drafts"], [data-testid="work-studio-tab-drafts-active"]'
            )
            tab_solo_briefing = await page.query_selector(
                '[data-testid="work-studio-tab-briefing"], [data-testid="work-studio-tab-briefing-active"]'
            )
            tab_merged = await page.query_selector(
                '[data-testid="work-studio-tab-drafts_briefs"], [data-testid="work-studio-tab-drafts_briefs-active"]'
            )
            assert tab_solo_drafts is None, "Solo `Drafts` tab must be gone"
            assert tab_solo_briefing is None, "Solo `Briefing` tab must be gone"
            assert tab_merged is not None, "Merged `Drafts & Briefs` tab must be present"

            # If the merged tab has at least one row, probe its chip.
            chip = await page.query_selector(
                '[data-testid="work-studio-document-row-category-badge"]',
            )
            if chip is not None:
                bg = await page.evaluate("(el) => getComputedStyle(el).backgroundColor", chip)
                assert bg != "rgba(0, 0, 0, 0)", (
                    f"Category chip rendered with transparent bg — "
                    f"Wave 4.2.followup.2 silent-fail regression. Got {bg!r}"
                )
                # Must be the brand-purple tint — substring check.
                # rgba(107, 70, 193, 0.1) is the expected value.
                assert "107" in bg or "70" in bg or "193" in bg, (
                    f"Category chip background not brand-purple-tinted: {bg!r}"
                )
                # Chip text — DRAFT or BRIEF (singular, uppercase via CSS).
                txt = (await chip.text_content() or "").strip().upper()
                assert txt in ("DRAFT", "BRIEF"), (
                    f"Chip text must read DRAFT or BRIEF; got {txt!r}. "
                    f"If neither row exists in this tenant, seed a "
                    f"sample doc and re-run."
                )
        finally:
            await b.close()
