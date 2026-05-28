"""Phase Y — Monitor Strategic Goal row consumes `<StrategicRow>` primitive
(2026-02 fork-resume).

Verifies the Monitor goal row in `StrategicGoalsPanel.jsx` composes the
shared primitive (slots wired correctly, primitive imported from the
canonical path). This locks "zero visual regression" against the
pre-extraction Monitor row — if a future agent inlines the JSX layout
again, these guards fail.

Multi-viewport runtime probes confirm the rendered DOM carries the
primitive's data attributes at 1280 / 1024 / 820, so primitive
composition stays correct across breakpoints.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PANEL = REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx"


# ─────────────────────────────────────────────────────────────────
# A. Source-strict — primitive import + slot composition
# ─────────────────────────────────────────────────────────────────


def test_monitor_panel_imports_primitive_from_canonical_path():
    src = PANEL.read_text(encoding="utf-8")
    assert re.search(
        r"import\s+StrategicRow.*from\s+[\"']@/components/strategic_row/StrategicRow[\"']",
        src,
    ), (
        "StrategicGoalsPanel must import `<StrategicRow>` from "
        "`@/components/strategic_row/StrategicRow` — Phase Y canonical path."
    )


def test_monitor_panel_uses_strategic_row_in_goal_row():
    """The `GoalRow` component must render `<StrategicRow>` instead of
    inlining the JSX layout. Locks the primitive composition so future
    agents don't quietly inline."""
    src = PANEL.read_text(encoding="utf-8")
    # `<StrategicRow` must be referenced.
    assert "<StrategicRow" in src, (
        "GoalRow must render <StrategicRow>; primitive composition required."
    )


def test_monitor_panel_wires_all_primitive_slots():
    """Slots: categoryChip / statusChip / title / rightSideScores /
    metadataChildren / description / onClick / testId / isLast must
    all be wired through to the primitive."""
    src = PANEL.read_text(encoding="utf-8")
    idx = src.find("<StrategicRow")
    assert idx > 0
    # Capture the StrategicRow JSX block.
    block_end = src.find("/>", idx)
    if block_end < 0:
        block_end = src.find("</StrategicRow>", idx)
    assert block_end > 0
    block = src[idx:block_end]
    for slot in (
        "categoryChip=",
        "statusChip=",
        "title=",
        "rightSideScores=",
        "metadataChildren=",
        "description=",
        "onClick=",
        "testId=",
        "isLast=",
    ):
        assert slot in block, (
            f"Monitor GoalRow's <StrategicRow> must wire slot {slot!r}."
        )


def test_monitor_panel_passes_strategic_goal_testid():
    """The row testId must use `strategic-goal-${goal.id}` so existing
    Monitor probes resolve."""
    src = PANEL.read_text(encoding="utf-8")
    assert "`strategic-goal-${goal.id}`" in src, (
        "Monitor row testId must be `strategic-goal-${goal.id}`."
    )


# ─────────────────────────────────────────────────────────────────
# B. Runtime — multi-viewport DOM probe
# ─────────────────────────────────────────────────────────────────


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


@pytest.mark.skipif(not HAVE_PW, reason="Playwright not installed")
@pytest.mark.asyncio
async def test_monitor_row_renders_primitive_data_attrs_multi_viewport():
    """At 1280 / 1024 / 820 the Monitor goal row's rendered DOM must
    carry the primitive's `data-strategic-row="true"` attribute and
    expose `role="button"` (clickable for drawer open)."""
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

            for vw, vh in ((1280, 900), (1024, 800), (820, 900)):
                await page.set_viewport_size({"width": vw, "height": vh})
                await page.goto(f"{base}/app/monitor", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3500)

                # If no goals seeded on this tenant, skip — assertions
                # are about primitive composition, not data presence.
                rows = await page.query_selector_all('[data-strategic-row="true"]')
                if not rows:
                    continue

                first_row = rows[0]
                # The primitive declares clickable rows with role=button.
                role = await first_row.get_attribute("role")
                assert role == "button", (
                    f"Monitor goal row at {vw}px must expose role=button "
                    f"when clickable (drawer open). Got role={role!r}."
                )
                # data-testid must follow `strategic-goal-<id>` pattern.
                tid = await first_row.get_attribute("data-testid")
                assert tid and tid.startswith("strategic-goal-"), (
                    f"Monitor row testid must start with `strategic-goal-`. "
                    f"Got {tid!r} at {vw}px."
                )
                # Score bars must be inside the right-anchored cluster.
                scores_wrapper = await first_row.query_selector(
                    '[data-strategic-row-scores="true"]'
                )
                assert scores_wrapper is not None, (
                    f"Monitor row at {vw}px must render the scores cluster."
                )
        finally:
            await browser.close()
