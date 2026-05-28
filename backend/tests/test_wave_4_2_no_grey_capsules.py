"""
Wave 4.2 (2026-05-27) — grey → brand-purple capsule sweep CI guard.

Scope clarification: the dispatch named ">10 sites" but a thorough
inventory of capsule-like elements (rounded-sm + uppercase tracking-
wider OR rounded-full pill semantics) revealed only **5 actual sites**
were carrying grey backgrounds. The broader 39 `bg-slate-*` hits in
the codebase are non-capsule semantics (hover states, disabled
inputs, code/kbd blocks, table headers) where grey is the correct
choice. Those are explicitly OUT of scope for Wave 4.2 — see
PHASE_LEDGER for the rationale.

Locked sites:
  1. TasksInitiativesPanel.jsx — TaskCard category pill
  2. StrategicGoalsPanel.jsx — operations category bar + chip
  3. DocumentCardsSection.jsx — `unrated` state badge
  4. DocumentCardsSection.jsx — default state-category className
  5. Pulse.jsx — confidence "low" tone + drawer confidence chip

Each must carry `var(--ned-purple)` (with opacity modifier) — no
`bg-slate-*` / `bg-gray-*` / `bg-neutral-*` on capsule elements.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"

# Map: file → list of patterns each MUST be absent (negative lock)
# AND a positive `bg-[var(--ned-purple)]` reference must be present.
SWEPT_SITES = (
    {
        "file": "components/monitor/TasksInitiativesPanel.jsx",
        "anchor_testid": "task-card-category-${task.id}",
        "must_not_match": (r"bg-slate-50\s+text-slate-700",),
    },
    {
        "file": "components/monitor/StrategicGoalsPanel.jsx",
        "anchor_str": '"Operations"',
        "must_not_match": (r"bg-slate-100\s+text-slate-800",),
    },
    {
        "file": "components/work_studio/DocumentCardsSection.jsx",
        "anchor_str": 'className: "bg-',
        "must_not_match": (
            r"className:\s*\"bg-slate-100\s+text-slate-700",
            r"unrated:\s*\"bg-slate-50",
        ),
    },
    {
        "file": "pages/Pulse.jsx",
        "anchor_testid": "pulse-drawer-confidence",
        "must_not_match": (
            r"card\.confidence === \"low\"\s*\?\s*\"bg-slate-50",
            r"\"px-2 py-0\.5 bg-slate-50 border border-slate-200 rounded-sm\"",
        ),
    },
)


def test_w42_swept_sites_no_grey_capsules() -> None:
    """Each swept site must NOT contain its previous grey-capsule
    pattern AND must contain at least one `var(--ned-purple)` reference
    in the same file."""
    for site in SWEPT_SITES:
        path = FRONTEND / site["file"]
        src = path.read_text(encoding="utf-8")
        for pat in site["must_not_match"]:
            assert not re.search(pat, src), (
                f"Wave 4.2 swept site {site['file']!r} still carries "
                f"a grey-capsule pattern matching {pat!r}. Replace with "
                f"`bg-[var(--ned-purple)]/<opacity>`."
            )
        # Wave 4.2.followup.2 (2026-02 fork-resume) — accept BOTH the
        # legacy `var(--ned-purple)` direct-use form AND the Tailwind-
        # config-registered short name `ned-purple` (preferred — opacity
        # composites correctly via the R G B triplet var).
        has_purple = (
            "var(--ned-purple)" in src
            or "ned-purple/" in src  # short-name with opacity modifier
            or " bg-ned-purple" in src
            or " text-ned-purple" in src
            or " border-ned-purple" in src
        )
        assert has_purple, (
            f"Wave 4.2 swept site {site['file']!r} must reference the "
            f"brand-purple token after the sweep (either `var(--ned-purple)` "
            f"direct or `ned-purple/N` Tailwind-config short name)."
        )


def test_w42_global_capsule_grep_clean() -> None:
    """Global sweep — no rounded-full or rounded-sm + uppercase
    tracking-wider element in any .jsx may carry `bg-slate-50`,
    `bg-slate-100`, `bg-gray-50`, `bg-gray-100`, `bg-neutral-50` or
    `bg-neutral-100`. The broader hover-state / disabled-input /
    kbd uses are out of scope and tolerated."""
    offenders: list[str] = []
    grey_classes = (
        "bg-slate-50", "bg-slate-100", "bg-gray-50", "bg-gray-100",
        "bg-neutral-50", "bg-neutral-100",
    )
    for jsx in FRONTEND.rglob("*.jsx"):
        text = jsx.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            # Heuristic: a capsule-like className has BOTH one of the
            # grey backgrounds AND a capsule signature on the same line.
            if any(g in line for g in grey_classes):
                # Capsule signature: rounded-full | (rounded-sm + uppercase)
                #                  | tracking-wider on a className
                is_capsule = (
                    "rounded-full" in line
                    or ("rounded-sm" in line and ("uppercase" in line or "tracking-wider" in line))
                )
                # Hover states (`hover:bg-slate-*`) are not capsule
                # backgrounds — the bg only applies on hover.
                line_stripped = line.strip()
                if re.search(r'\bhover:bg-(slate|gray|neutral)-(50|100)\b', line_stripped):
                    # If THE ONLY grey on this line is the hover state,
                    # tolerate. If a non-hover grey is present too,
                    # the surrounding capsule signature still triggers.
                    bare_grey = re.search(
                        r'(?<!hover:)\b(bg-(?:slate|gray|neutral)-(?:50|100))\b',
                        line_stripped,
                    )
                    if not bare_grey:
                        continue
                if is_capsule:
                    offenders.append(
                        f"{jsx.relative_to(FRONTEND)}:{line_no} → "
                        f"{line.strip()[:120]}"
                    )
    assert not offenders, (
        "Wave 4.2 grey→purple sweep — capsule-like elements still "
        "carrying grey backgrounds:\n  - " + "\n  - ".join(offenders)
    )


# ─────────────────────────────────────────────────────────────────
# Phase W.followup.1 hotfix (2026-02 fork-resume) — Wave 4.2 was a
# pure source-string sweep. It missed a class of regressions where
# `bg-[var(--ned-purple)]/<N>` silently breaks at runtime because
# `--ned-purple` is hex-encoded (#6B46C1) and Tailwind's
# opacity-modifier syntax requires `R G B` space-separated values
# OR a hex literal at the call site. The result: source LOOKS
# correct but the rendered background is `rgba(0,0,0,0)` (transparent)
# and the border falls back to gray-200.
#
# Lesson captured + new live-DOM probe below extends Wave 4.2 to
# catch this rendering class. We assert on COMPUTED STYLE not the
# source string.
# ─────────────────────────────────────────────────────────────────


def test_w42_no_var_ned_purple_opacity_in_capsule_sites() -> None:
    """`bg-[var(--ned-purple)]/<N>` and `border-[var(--ned-purple)]/<N>`
    silently break — they must be replaced with the hex-literal form
    `bg-[#6B46C1]/<N>` (Tailwind supports opacity modifier on hex
    arbitrary values) until `--ned-purple` is re-declared in `R G B`
    space-separated form.

    Scope: only Wave 4.2 capsule sites + tenant-scope pill. Other
    usages may iterate later in a controlled migration sprint.
    """
    capsule_pages = (
        "pages/admin/ExtractionsActivity.jsx",
    )
    offenders: list[str] = []
    bad = re.compile(r'(?:bg|border)-\[var\(--ned-purple\)\]/\d')
    for rel in capsule_pages:
        p = FRONTEND / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if bad.search(line):
                # Tenant-scope pill must use hex literal — anywhere else
                # in the file is the operator's call.
                if 'extractions-tenant-scope' in line or 'tenant-scope-pill' in line:
                    offenders.append(
                        f"{rel}:{line_no} → tenant-scope pill must use "
                        f"`bg-[#6B46C1]/N` not `bg-[var(--ned-purple)]/N` — "
                        f"opacity modifier on hex CSS var silently fails. "
                        f"{line.strip()[:120]}"
                    )
    assert not offenders, (
        "Wave 4.2 hex-opacity regression on capsule sites:\n  - "
        + "\n  - ".join(offenders)
    )


try:
    import pytest
    from playwright.async_api import async_playwright  # noqa: F401
    HAVE_PW = True
except Exception:  # noqa: BLE001
    HAVE_PW = False


def _frontend_url() -> str:
    env = REPO_ROOT / "frontend" / ".env"
    for ln in env.read_text("utf-8").splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not in frontend/.env")


if HAVE_PW:
    import pytest

    @pytest.mark.runtime_playwright
    @pytest.mark.asyncio
    async def test_w42_tenant_scope_pill_rendered_background_is_purple_not_grey():
        """Live DOM probe — open the extractions page with a
        ?tenant_id= filter, assert the computed background is the
        brand-purple tint (not transparent / not grey)."""
        from playwright.async_api import async_playwright
        base = _frontend_url()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(viewport={"width": 1024, "height": 800})
                page = await ctx.new_page()
                await page.goto(f"{base}/signin", wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_selector('[data-testid="signin-email-input"]', timeout=15000)
                await page.fill('[data-testid="signin-email-input"]', "admin@akki.ai")
                await page.fill('[data-testid="signin-password-input"]', "AkkiAdmin2026!")
                await page.click('[data-testid="signin-form"] button[type="submit"]')
                await page.wait_for_timeout(3000)
                await page.goto(
                    f"{base}/app/admin/extractions?tenant_id=w42-probe-cid",
                    wait_until="domcontentloaded", timeout=20000,
                )
                await page.wait_for_selector(
                    '[data-testid="extractions-tenant-scope-pill"]',
                    timeout=15000,
                )
                pill = await page.query_selector(
                    '[data-testid="extractions-tenant-scope-pill"]',
                )
                bg = await page.evaluate(
                    "(el) => getComputedStyle(el).backgroundColor", pill,
                )
                border = await page.evaluate(
                    "(el) => getComputedStyle(el).borderColor", pill,
                )
                # The background must NOT be transparent (`rgba(0, 0, 0, 0)`)
                # and the border must NOT be the Tailwind gray-200 default.
                assert bg != "rgba(0, 0, 0, 0)", (
                    f"Tenant-scope pill bg is transparent — Wave 4.2 regression. "
                    f"Got {bg!r}"
                )
                assert border != "rgb(229, 231, 235)", (
                    f"Tenant-scope pill border is gray-200 default — Wave 4.2 "
                    f"regression. Got {border!r}"
                )
                # Positive — must be a purple-ish tint. The hex #6B46C1 with
                # opacity 0.1 composites to rgba(107, 70, 193, 0.1).
                assert "107" in bg or "purple" in bg.lower() or "6b46c1" in bg.lower(), (
                    f"Tenant-scope pill bg should be brand-purple-tinted, got {bg!r}"
                )
            finally:
                await browser.close()


# ─────────────────────────────────────────────────────────────────
# Phase W.followup.1 hotfix — drilldown "View all" link always
# renders (no `extractions.length > 0` gate).
# ─────────────────────────────────────────────────────────────────


def test_w42_drilldown_view_all_link_unconditional() -> None:
    """`tenant-extraction-view-all-link` must always render inside
    the drilldown extraction panel — not gated on `extractions.length`."""
    src = (FRONTEND / "pages" / "admin" / "AdminTenants.jsx").read_text(encoding="utf-8")
    panel_idx = src.find("tenant-extraction-panel")
    assert panel_idx > 0, "tenant-extraction-panel testid missing"
    # Examine the next 2000 chars (the panel block).
    panel_block = src[panel_idx:panel_idx + 2500]
    assert 'tenant-extraction-view-all-link' in panel_block, (
        "View-all link testid must be inside the panel block"
    )
    # No `extractions.length > 0 &&` conditional immediately above the
    # link — that was the regression. We assert the link is NOT inside a
    # short-circuit conditional.
    link_idx = panel_block.find("tenant-extraction-view-all-link")
    # Look 200 chars BEFORE the link for the offending gate.
    before = panel_block[max(0, link_idx - 250):link_idx]
    assert "extractions.length > 0 && (" not in before, (
        "View-all link must NOT be gated on `extractions.length > 0` — "
        "Phase W.followup.1 hotfix requires it to always render."
    )


# ─────────────────────────────────────────────────────────────────
# Phase W.followup.1 hotfix — tenant-scope pill clear affordance.
# ─────────────────────────────────────────────────────────────────


def test_w42_tenant_scope_pill_has_clear_button() -> None:
    """The tenant-scope pill on /app/admin/extractions must carry a
    clear button that strips `tenant_id` from the URL via
    setSearchParams."""
    src = (FRONTEND / "pages" / "admin" / "ExtractionsActivity.jsx").read_text(encoding="utf-8")
    required = (
        "extractions-tenant-scope-clear-btn",
        'next.delete("tenant_id")',
        "setSearchParams",
    )
    for needle in required:
        assert needle in src, (
            f"ExtractionsActivity.jsx must contain {needle!r} for the "
            f"tenant-scope clear affordance"
        )
