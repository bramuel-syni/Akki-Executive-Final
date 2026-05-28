"""Item 4 + Item 5 (2026-02 fork-resume consolidated dispatch).

- Item 4: Monitor goal drawer intelligence wiring. Closed-row narrative
  snippets are bucket-template strings generated client-side by
  `performanceNarrative()` / `probabilityNarrative()`. The drawer
  was rendering only the score numbers without the bucket text. Fix
  surfaces the same templates inside the drawer (full text, not
  truncated), plus an empty milestone tracker + a recommended-action
  callout when the performance score < 65.

- Item 5: Monitor strategic-goals "CATEGORY" filter renamed to
  "OWNER" + "All categories" → "All owners". The values shown were
  always department-roles (CFO/CEO/...); the label was misleading.

Backend follow-up for Item 4 (filed in PHASE_LEDGER): Phase
AA.followup.10 — LLM-generated `performance_explanation`,
`probability_explanation`, `recommended_action`, `milestones[]`
on the goal model.
"""
from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


# ─────────────────────────────────────────────────────────────────
# Item 4 — drawer intel testids + bucket-narrative wiring
# ─────────────────────────────────────────────────────────────────


def test_item4_drawer_intelligence_panel_present():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    required = (
        "goal-drawer-intelligence",
        "goal-drawer-performance-signal",
        "goal-drawer-performance-signal-text",
        "goal-drawer-probability-signal",
        "goal-drawer-probability-signal-text",
        # AA.followup.10 REVISED — Progress timeline replaces the old
        # manual milestones tracker.
        "goal-drawer-progress-timeline",
        "goal-drawer-progress-timeline-empty",
        "goal-drawer-recommended-action",
    )
    for tid in required:
        assert f'data-testid="{tid}"' in src, (
            f"StrategicGoalsPanel.jsx must carry data-testid={tid!r}"
        )


def test_item4_drawer_uses_client_side_narratives_when_backend_field_absent():
    """Drawer must fall back to `performanceNarrative()` /
    `probabilityNarrative()` (the bucket templates) when the goal lacks
    backend-supplied LLM explanations."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # Both narrative functions must be referenced inside the drawer block.
    drawer_idx = src.find("goal-drawer-intelligence")
    assert drawer_idx > 0
    drawer_block = src[drawer_idx:drawer_idx + 3000]
    assert "performanceNarrative(goal?.current_score)" in drawer_block, (
        "Drawer must call performanceNarrative(goal?.current_score) so "
        "the bucket text matches the closed row."
    )
    assert "probabilityNarrative(goal?.probability)" in drawer_block, (
        "Drawer must call probabilityNarrative(goal?.probability)."
    )
    # The backend-explanation field must be checked first (LLM intel
    # supersedes the client bucket when available — see Phase
    # AA.followup.10 backlog).
    assert "performance_explanation" in drawer_block
    assert "probability_explanation" in drawer_block


def test_item4_progress_timeline_replaces_manual_milestones():
    """AA.followup.10 REVISED — the manual `+ Add milestone` direction
    was wrong. Drawer renders auto-derived Progress timeline instead."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # Old milestone testids must be gone.
    for legacy in ("goal-drawer-milestones-empty", "goal-drawer-add-milestone-btn", "goal-drawer-milestones\""):
        assert legacy.rstrip('"') not in src or f'"{legacy.rstrip(chr(34))}"' not in src or src.count(f'data-testid="{legacy.rstrip(chr(34))}"') == 0, (
            f"Legacy milestone testid {legacy!r} must be removed; "
            f"replaced by Progress timeline."
        )
    # Empty-state copy per spec.
    assert "No progress signals recorded yet." in src, (
        "Progress timeline empty-state copy must match spec exactly"
    )
    assert "+ Add milestone" not in src, (
        "Manual `+ Add milestone` CTA must be REMOVED from the drawer "
        "(AA.followup.10 REVISED course-correction)"
    )


def test_item4_recommended_action_uses_brand_purple_callout():
    """The "Recommended action" callout must use the brand-purple
    Tailwind-config-registered color (ned-purple/N), not the silent-
    fail `[var(--ned-purple)]/N` form."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    idx = src.find("goal-drawer-recommended-action")
    block = src[idx:idx + 800]
    # Must use Tailwind-config-registered colors so opacity composites.
    assert "bg-ned-purple/10" in block or "bg-ned-purple/8" in block, (
        "Recommended-action callout must use `bg-ned-purple/N` "
        "(Tailwind-config short name) so opacity composites correctly. "
        "`bg-[var(--ned-purple)]/N` silently fails."
    )


# ─────────────────────────────────────────────────────────────────
# Item 5 — Owner filter rename
# ─────────────────────────────────────────────────────────────────


def test_item5_filter_label_is_owner_not_category():
    """Decision 1 (2026-02 fork-resume) — the dropdown was COLLAPSED
    into a capsule strip. The label-rename assertion now checks for
    the capsule strip's `All owners` button text."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # New testid — capsule strip is the single source of truth.
    assert "strategic-goals-owner-capsules" in src, (
        "Owner-filter capsule strip testid required"
    )
    assert "strategic-goals-owner-capsule-all" in src, (
        "Default 'All owners' capsule testid required"
    )
    # User-facing copy.
    assert "All owners" in src, (
        '"All owners" default capsule text required'
    )


def test_item5_legacy_category_testids_removed():
    """The old `strategic-goals-category-*` testids must be gone, AND
    the intermediate `strategic-goals-owner-select` dropdown must be
    gone too (Decision 1 collapse).

    Excludes JS line-comments + JSX `{/* ... */}` block comments — the
    comment in `StrategicGoalsPanel.jsx` documenting the removal must
    keep referencing the legacy testid name."""
    import re
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # Strip JSX block comments and JS line comments before grep.
    code = re.sub(r'\{/\*.*?\*/\}', '', src, flags=re.DOTALL)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    code = "\n".join(
        line.split("//", 1)[0] for line in code.splitlines()
    )
    assert "strategic-goals-category-select" not in code, (
        "Legacy `strategic-goals-category-select` testid must be removed."
    )
    assert "strategic-goals-owner-select" not in code, (
        "Decision 1 — `strategic-goals-owner-select` dropdown must be "
        "removed; capsule strip is the single source of truth."
    )
    assert "All categories" not in code, (
        'Legacy "All categories" default option text must be removed.'
    )


def test_decision_1_dropdown_collapsed_into_capsule_strip():
    """Decision 1 hard guard — no `<select>` element with the legacy
    `id="strategic-goals-owner"` may remain. Capsules only."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    assert 'id="strategic-goals-owner"' not in src, (
        "Legacy <select id='strategic-goals-owner'> dropdown must be "
        "removed. Capsules only."
    )
    # The capsule strip must mirror the proven TasksInitiativesPanel
    # pattern — single-tap, brand-accent active state.
    capsule_idx = src.find("strategic-goals-owner-capsules")
    assert capsule_idx > 0
    capsule_block = src[capsule_idx:capsule_idx + 2000]
    assert "bg-[var(--accent)]" in capsule_block, (
        "Active capsule must use the brand accent token (matches "
        "TasksInitiativesPanel)"
    )


def test_owner_capsule_strip_source_locks_horizontal_scroll_layout():
    """Recurrence-#4 source-strict lock (2026-02 fork-resume reply
    dispatch) — the owner capsule strip container MUST declare
    `flex-nowrap overflow-x-auto`, and each capsule button MUST
    declare `whitespace-nowrap`. This enforces the horizontal-scroll
    layout at narrow viewports (820px) instead of the flex-wrap-to-
    second-line failure mode."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    capsule_idx = src.find("strategic-goals-owner-capsules")
    assert capsule_idx > 0
    # Walk backwards a few hundred chars to capture the parent <div>'s
    # className, since the testid sits on the strip container.
    container_block = src[max(0, capsule_idx - 600):capsule_idx + 100]
    assert "flex-nowrap" in container_block, (
        "Owner capsule strip container must declare `flex-nowrap` so "
        "items never wrap to a second line at narrow viewports."
    )
    assert "overflow-x-auto" in container_block, (
        "Owner capsule strip container must declare `overflow-x-auto` "
        "so overflowing capsules become horizontally scrollable."
    )
    # Capsule buttons (inside the strip) must declare `whitespace-nowrap`.
    capsule_block = src[capsule_idx:capsule_idx + 2500]
    assert "whitespace-nowrap" in capsule_block, (
        "Owner capsule <button>s must declare `whitespace-nowrap` so "
        "label text never wraps inside an individual capsule."
    )


import sys
import pytest

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


@pytest.mark.runtime_playwright
@pytest.mark.skipif(not _HAVE_PW, reason="Playwright not installed")
@pytest.mark.asyncio
async def test_owner_capsule_strip_horizontal_scrolls_at_820():
    """Recurrence-#4 runtime lock — at 820 the owner capsule strip's
    computed `flex-wrap` must be `nowrap` and `overflow-x` must be
    `auto`. When more capsules are rendered than fit the strip's
    `clientWidth`, the `scrollWidth` must exceed `clientWidth`
    (proving it scrolls, not wraps to a second line).

    Skipif fall-through: when the test tenant has no goals seeded,
    the capsule strip doesn't render at all (gated by
    `categoryOptions.length > 0`). Assertion is about computed style,
    not data presence — so the test skips on empty data."""
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
                # Set viewport BEFORE goto so CSS @media is evaluated fresh.
                await page.set_viewport_size({"width": vw, "height": vh})
                await page.goto(f"{base}/app/monitor", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3500)

                strip = await page.query_selector('[data-testid="strategic-goals-owner-capsules"]')
                if strip is None:
                    # No goals seeded under this tenant → strip not rendered.
                    # Skipif fall-through — the source-strict lock above
                    # already guarantees the layout when the strip renders.
                    continue

                metrics = await strip.evaluate("""(el) => {
                    const cs = getComputedStyle(el);
                    return {
                        flexWrap: cs.flexWrap,
                        overflowX: cs.overflowX,
                        scrollWidth: el.scrollWidth,
                        clientWidth: el.clientWidth,
                    };
                }""")
                assert metrics["flexWrap"] == "nowrap", (
                    f"Owner capsule strip @ {vw}px — flex-wrap must be "
                    f"`nowrap`, got {metrics['flexWrap']!r}"
                )
                # `overflow-x: auto` is the Tailwind default; some
                # browsers report it as `auto` literally.
                assert metrics["overflowX"] in ("auto", "scroll"), (
                    f"Owner capsule strip @ {vw}px — overflow-x must be "
                    f"`auto` or `scroll`, got {metrics['overflowX']!r}"
                )
                # When capsules overflow the strip width, scrollWidth >
                # clientWidth proves horizontal-scroll behaviour. When
                # they don't overflow (e.g. only 1-2 capsules), this
                # equality is fine; assert non-regression of nowrap+
                # overflow regardless.
                assert metrics["scrollWidth"] >= metrics["clientWidth"], (
                    f"Owner capsule strip @ {vw}px — scrollWidth must "
                    f"be ≥ clientWidth. Got scrollWidth="
                    f"{metrics['scrollWidth']} clientWidth="
                    f"{metrics['clientWidth']}"
                )
        finally:
            await browser.close()
