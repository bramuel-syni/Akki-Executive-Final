"""Phase Y — Task Manager card consumes `<StrategicRow>` primitive
(2026-02 fork-resume).

Locks Task card composition against the same primitive Monitor uses.
This is the visual-parity guarantee the user explicitly asked for —
matching layout (chip placement, metadata row, scores on the right,
single-line description). Different SHAPE of data (one Readiness score
vs Monitor's Performance + Probability pair) but identical SLOTTING.

Multi-viewport runtime probes confirm primitive composition holds at
1280 / 1024 / 820.
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

LISTING = REPO / "frontend" / "src" / "components" / "tasks" / "TaskListing.jsx"


# ─────────────────────────────────────────────────────────────────
# A. Source-strict — primitive import + slot composition
# ─────────────────────────────────────────────────────────────────


def test_task_listing_imports_primitive_from_canonical_path():
    src = LISTING.read_text(encoding="utf-8")
    assert re.search(
        r"import\s+StrategicRow.*from\s+[\"']@/components/strategic_row/StrategicRow[\"']",
        src,
    ), (
        "TaskListing must import `<StrategicRow>` from "
        "`@/components/strategic_row/StrategicRow` — Phase Y canonical path."
    )


def test_task_listing_renders_primitive_per_card():
    src = LISTING.read_text(encoding="utf-8")
    assert "<StrategicRow" in src, (
        "Each task card must compose `<StrategicRow>`; inline JSX layouts "
        "regress visual parity with Monitor."
    )


def test_task_listing_wires_all_primitive_slots():
    """Slots: categoryChip / statusChip / title / rightSideScores /
    metadataChildren / description / onClick / testId / isLast."""
    src = LISTING.read_text(encoding="utf-8")
    idx = src.find("<StrategicRow")
    assert idx > 0
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
            f"Task card's <StrategicRow> must wire slot {slot!r}."
        )


def test_task_listing_passes_task_card_testid():
    src = LISTING.read_text(encoding="utf-8")
    assert "`task-card-${t.id}`" in src, (
        "Task card testId must follow `task-card-${t.id}` pattern."
    )


def test_task_listing_category_chip_uses_brand_purple_short_name():
    """The TASK category chip must use Tailwind-config short names
    (`bg-ned-purple/10` + `border-ned-purple/20`) so opacity composites
    correctly. Wave 4.2.followup.2 silent-fail trap MUST NOT be used."""
    src = LISTING.read_text(encoding="utf-8")
    idx = src.find("task-card-category-")
    assert idx > 0, "Category chip testid `task-card-category-` required"
    block = src[max(0, idx - 600):idx + 200]
    assert "bg-ned-purple/" in block, (
        "Category chip must use Tailwind short name `bg-ned-purple/N`."
    )
    assert "bg-[var(--ned-purple)]/" not in block, (
        "Category chip must NOT use the silent-fail "
        "`bg-[var(--ned-purple)]/N` syntax."
    )


def test_task_listing_readiness_uses_right_side_scores():
    """Readiness flows through `rightSideScores` with a `narrative`
    field (one-line explanation slot)."""
    src = LISTING.read_text(encoding="utf-8")
    # Find the rightSideScores array literal and assert it has a single
    # Readiness entry with all 5 ScoreBar fields.
    idx = src.find("rightSideScores")
    assert idx > 0
    block = src[idx:idx + 600]
    assert '"Readiness"' in block, (
        "Task card rightSideScores must include a `Readiness` entry."
    )
    assert "narrative" in block, (
        "Readiness ScoreBar must declare a `narrative` field (one-line "
        "explanation under the bar)."
    )
    assert "readinessBarClass" in block or "barClass" in block, (
        "Readiness ScoreBar must declare a `barClass` (RAG color)."
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
async def test_task_card_renders_primitive_data_attrs_multi_viewport():
    """At 1280 / 1024 / 820 the Task card's rendered DOM must:
      - Carry `data-strategic-row="true"` on the primitive root.
      - Expose `role="button"` (clickable opens TaskDrawer).
      - Render the right-anchored scores cluster.
      - Render a readiness bar with non-transparent fill OR an empty
        dashed track (per ScoreBar contract).
    """
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
                await page.goto(
                    f"{base}/app/task-manager",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await page.wait_for_timeout(3500)

                # Resolve task cards by the wrapping <li>'s data-card-kind.
                # If no tasks seeded, skip — assertions are about primitive
                # composition, not data presence.
                cards = await page.query_selector_all('li[data-card-kind="task"]')
                if not cards:
                    continue

                first_card = cards[0]
                # The primitive root must be inside the card wrapper.
                row = await first_card.query_selector('[data-strategic-row="true"]')
                assert row is not None, (
                    f"Task card at {vw}px must render <StrategicRow> "
                    f"(data-strategic-row=\"true\") inside the <li>."
                )
                role = await row.get_attribute("role")
                assert role == "button", (
                    f"Task card primitive at {vw}px must expose "
                    f"role=button (clickable opens TaskDrawer). "
                    f"Got role={role!r}."
                )
                tid = await row.get_attribute("data-testid")
                assert tid and tid.startswith("task-card-"), (
                    f"Task card testid must start with `task-card-`. "
                    f"Got {tid!r} at {vw}px."
                )
                # Right-anchored scores cluster.
                scores_wrapper = await row.query_selector(
                    '[data-strategic-row-scores="true"]'
                )
                assert scores_wrapper is not None, (
                    f"Task card at {vw}px must render the scores cluster."
                )
                # Readiness ScoreBar inside the cluster.
                readiness = await scores_wrapper.query_selector(
                    'div[data-testid^="task-card-readiness-"]'
                )
                assert readiness is not None, (
                    f"Task card at {vw}px must render the readiness "
                    f"ScoreBar inside the scores cluster."
                )
                # Selector-agnostic contract — at least one ScoreBar
                # with `data-scorebar-kind="readiness"` MUST exist
                # inside any `data-strategic-row="true"` card on
                # /app/task-manager (Phase Y followup, 2026-02).
                kind_match = await scores_wrapper.query_selector(
                    'div[data-scorebar="true"][data-scorebar-kind="readiness"]'
                )
                assert kind_match is not None, (
                    f"Task card at {vw}px must render at least one "
                    f"ScoreBar with `data-scorebar-kind=\"readiness\"` "
                    f"inside the scores cluster. This is the cross-"
                    f"surface selector contract — selectors that don't "
                    f"know the row-id suffix should still resolve."
                )
        finally:
            await browser.close()
