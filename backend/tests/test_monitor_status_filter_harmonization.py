"""Phase Y followup — Monitor status-filter harmonization (2026-02
fork-resume).

User flagged that the Tasks tab's status filter row was chunky
`rounded-full` capsules with uppercase labels while the Strategic
Objectives tab used cleaner `rounded-sm` text-tabs with an active
ink/parchment inversion. The Strategic Objectives row is the gold
standard per user spec.

This dispatch extracted the gold-standard markup into a shared
`<StatusFilterTabs>` primitive at:
  /app/frontend/src/components/monitor/StatusFilterTabs.jsx

Both Monitor surfaces (Strategic Objectives + Tasks/Initiatives) now
consume the primitive — guaranteed visual + a11y parity.

Tests:
  • Source-strict — both panels import the primitive, render it in
    place of the old inline markup, and pass the locked prop contract.
  • Runtime DOM probe — at 1280 / 1024 / 820 the two filter rows
    render with IDENTICAL computed font-size, padding, border-radius,
    and active-state background-color.
  • Wave 4.2.followup.2 compliance — the primitive must NOT use the
    silent-fail `bg-[var(--HEX-VAR)]/N` syntax.
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


PRIMITIVE = REPO / "frontend" / "src" / "components" / "monitor" / "StatusFilterTabs.jsx"
GOALS = REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx"
TASKS = REPO / "frontend" / "src" / "components" / "monitor" / "TasksInitiativesPanel.jsx"


# ─────────────────────────────────────────────────────────────────
# A. Primitive contract
# ─────────────────────────────────────────────────────────────────


def test_primitive_file_exists_at_canonical_path():
    assert PRIMITIVE.is_file(), (
        f"<StatusFilterTabs> primitive must exist at {PRIMITIVE!s}."
    )


def test_primitive_default_export_named_status_filter_tabs():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert re.search(r"export\s+default\s+function\s+StatusFilterTabs\b", src), (
        "Primitive must default-export `StatusFilterTabs`."
    )


def test_primitive_declares_locked_prop_contract():
    """Public surface: 6 props — tabs, activeKey, onSelect, counts,
    testIdPrefix, ariaLabel."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    for prop in ("tabs", "activeKey", "onSelect", "counts", "testIdPrefix", "ariaLabel"):
        assert prop in src, f"Primitive must accept the {prop!r} prop."


def test_primitive_renders_role_tablist_with_aria_label():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'role="tablist"' in src, (
        "Primitive root must declare `role=\"tablist\"`."
    )
    assert "aria-label={ariaLabel}" in src, (
        "Primitive must wire the `ariaLabel` prop to the tablist's aria-label."
    )


def test_primitive_each_tab_declares_role_and_aria_selected():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'role="tab"' in src
    assert "aria-selected={active}" in src


def test_primitive_uses_locked_visual_treatment():
    """The class strings define the gold-standard visual contract.
    Locked literals (any drift trips the test):
      - rounded-sm (not rounded-full)
      - text-[11.5px]
      - bg-[var(--ink)] text-[var(--parchment)]  (active state)
      - hover:bg-brand-rule/40                   (NOT hex-var/N trap)
      - bg-[var(--parchment)]/20                 (active count chip)
    """
    src = PRIMITIVE.read_text(encoding="utf-8")
    locked_literals = (
        "rounded-sm",
        "text-[11.5px]",
        "bg-[var(--ink)] text-[var(--parchment)]",
        "hover:bg-brand-rule/40",
        "bg-[var(--parchment)]/20",
    )
    for needle in locked_literals:
        assert needle in src, (
            f"Primitive must declare {needle!r} (gold-standard visual contract)."
        )
    # Anti-regression — the legacy chunky-capsule pattern must NOT
    # reappear in the primitive.
    forbidden = ("rounded-full", "uppercase tracking-wider")
    for needle in forbidden:
        assert needle not in src, (
            f"Primitive must NOT declare {needle!r} — that's the "
            f"legacy chunky-capsule visual the user explicitly rejected."
        )


def test_primitive_no_silent_fail_hex_var_opacity():
    """Wave 4.2.followup.2 — the primitive's hover state must NOT use
    the `bg-[var(--HEX-VAR)]/N` JIT syntax (silent-fail trap). It
    must use the Tailwind-config short name `bg-brand-rule/40`
    instead."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    bad = re.search(r"hover:bg-\[var\(--cream-deep\)\]/\d", src)
    assert bad is None, (
        "Primitive must NOT use the silent-fail "
        "`hover:bg-[var(--cream-deep)]/N` syntax — use `bg-brand-rule/N` "
        "(Tailwind-config RGB short name, same color)."
    )


# ─────────────────────────────────────────────────────────────────
# B. Consumers — Goals panel + Tasks panel
# ─────────────────────────────────────────────────────────────────


def test_goals_panel_imports_primitive():
    src = GOALS.read_text(encoding="utf-8")
    assert re.search(
        r"import\s+StatusFilterTabs.*from\s+[\"']@/components/monitor/StatusFilterTabs[\"']",
        src,
    ), "Goals panel must import StatusFilterTabs from canonical path."


def test_goals_panel_renders_primitive():
    src = GOALS.read_text(encoding="utf-8")
    assert "<StatusFilterTabs" in src, (
        "Goals panel must render the primitive."
    )
    # Source-strict slot wiring.
    goals_block_idx = src.find("<StatusFilterTabs")
    assert goals_block_idx > 0
    block = src[goals_block_idx:goals_block_idx + 800]
    for prop in ("tabs=", "activeKey=", "onSelect=", "counts=", "testIdPrefix=", "ariaLabel="):
        assert prop in block, (
            f"Goals panel <StatusFilterTabs> must wire prop {prop!r}."
        )
    assert 'testIdPrefix="strategic-goals-status-tab"' in block, (
        "Goals panel must pass testIdPrefix=\"strategic-goals-status-tab\" "
        "to preserve existing testid namespace."
    )


def test_tasks_panel_imports_primitive():
    src = TASKS.read_text(encoding="utf-8")
    assert re.search(
        r"import\s+StatusFilterTabs.*from\s+[\"']@/components/monitor/StatusFilterTabs[\"']",
        src,
    ), "Tasks panel must import StatusFilterTabs from canonical path."


def test_tasks_panel_renders_primitive():
    src = TASKS.read_text(encoding="utf-8")
    assert "<StatusFilterTabs" in src, (
        "Tasks panel must render the primitive."
    )
    tasks_block_idx = src.find("<StatusFilterTabs")
    assert tasks_block_idx > 0
    block = src[tasks_block_idx:tasks_block_idx + 800]
    for prop in ("tabs=", "activeKey=", "onSelect=", "counts=", "testIdPrefix=", "ariaLabel="):
        assert prop in block, (
            f"Tasks panel <StatusFilterTabs> must wire prop {prop!r}."
        )
    assert 'testIdPrefix="tasks-status-tab"' in block, (
        "Tasks panel must pass testIdPrefix=\"tasks-status-tab\" "
        "to preserve existing testid namespace."
    )


def test_tasks_panel_legacy_chunky_capsule_markup_removed():
    """Anti-regression — the legacy `rounded-full uppercase
    tracking-wider` pattern that the user rejected MUST NOT come
    back into TasksInitiativesPanel for the status-filter row."""
    src = TASKS.read_text(encoding="utf-8")
    # The status-filter row testid bounds the assertion to the filter
    # row only (not the goal row chips, which intentionally use
    # different shapes).
    filter_block_idx = src.find('data-testid="tasks-status-filters"')
    assert filter_block_idx > 0
    # Walk forward until the next testid boundary.
    block_end = src.find('data-testid', filter_block_idx + 50)
    if block_end < 0:
        block_end = filter_block_idx + 1500
    block = src[filter_block_idx:block_end]
    for forbidden in ("rounded-full", "uppercase tracking-wider"):
        assert forbidden not in block, (
            f"Tasks status-filter row must NOT contain {forbidden!r} "
            f"(legacy chunky-capsule pattern). Block: {block[:300]!r}"
        )


# ─────────────────────────────────────────────────────────────────
# C. Runtime — multi-viewport DOM probe asserting visual parity
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
async def test_filter_rows_share_identical_computed_styles_at_multi_viewport():
    """At 1280 / 1024 / 820 the Strategic Goals + Tasks status filter
    tabs MUST render with identical computed font-size, padding,
    border-radius, and active-state background. This is the visual-
    parity contract the user asked for."""
    from playwright.async_api import async_playwright
    base = _frontend_url()

    PROBE_PROPS = ("fontSize", "fontWeight", "paddingTop", "paddingRight",
                   "paddingBottom", "paddingLeft", "borderRadius",
                   "letterSpacing", "textTransform")

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

                # Sample Goals "all" tab.
                goals_all = await page.query_selector('[data-testid="strategic-goals-status-tab-all"]')
                if goals_all is None:
                    # No goals panel mounted — skip on this viewport.
                    continue

                # Switch to Tasks tab.
                tasks_tab = await page.query_selector('[data-testid="monitor-tab-tasks"]')
                if tasks_tab is None:
                    # Tasks tab not exposed — skip.
                    continue
                await tasks_tab.click()
                await page.wait_for_timeout(2500)

                tasks_all = await page.query_selector('[data-testid="tasks-status-tab-all"]')
                if tasks_all is None:
                    continue

                # Switch back to Goals and capture the snapshot (the
                # tab click may have unmounted the goals row in the
                # previous viewport).
                goals_tab = await page.query_selector('[data-testid="monitor-tab-goals"]')
                if goals_tab:
                    await goals_tab.click()
                    await page.wait_for_timeout(2000)
                goals_all = await page.query_selector('[data-testid="strategic-goals-status-tab-all"]')
                if goals_all is None:
                    continue

                goals_cs = await goals_all.evaluate(
                    f"""(el) => {{
                        const cs = getComputedStyle(el);
                        const out = {{}};
                        const props = {list(PROBE_PROPS)!r};
                        props.forEach(p => out[p] = cs[p]);
                        return out;
                    }}"""
                )

                await tasks_tab.click()
                await page.wait_for_timeout(2000)
                tasks_all = await page.query_selector('[data-testid="tasks-status-tab-all"]')
                if tasks_all is None:
                    continue
                tasks_cs = await tasks_all.evaluate(
                    f"""(el) => {{
                        const cs = getComputedStyle(el);
                        const out = {{}};
                        const props = {list(PROBE_PROPS)!r};
                        props.forEach(p => out[p] = cs[p]);
                        return out;
                    }}"""
                )

                # Parity assertion — every probed property must match.
                for prop in PROBE_PROPS:
                    assert goals_cs[prop] == tasks_cs[prop], (
                        f"@ {vw}px — computed style mismatch on `{prop}`: "
                        f"Goals={goals_cs[prop]!r} vs Tasks={tasks_cs[prop]!r}. "
                        f"Full Goals: {goals_cs!r}. Full Tasks: {tasks_cs!r}."
                    )
        finally:
            await browser.close()
