"""Phase H.2 — Right-rail company list wiring — 2026-05-26.

Locks in the H.2 contract on top of the H.1 layout shell:

  T1.  Card root carries both `portfolio-card-<id>` (H.1) AND
       `rail-company-card-<id>` (H.2 stable alias).
  T2.  Card carries `data-rail-card-role` attribute = `ned` |
       `executive` for tab-filtering assertions.
  T3.  Tab labels include the live count (`NED · {n}` / `Executive · {n}`).
  T4.  Default tab = first non-empty (`nedList.length > 0 ? "ned" : "executive"`).
  T5.  Tab selection persisted under localStorage key
       `akki.portfolio.rail.tab`.
  T6.  Card click → calls `switchContext(c.id)` from AuthContext;
       does NOT manually navigate (switchContext owns navigation).
  T7.  + Add Company button routes to existing `/app/contexts/new` flow.
  T8.  Cards drop legacy SIGNALS/BRIEFINGS/DOCS inline metrics.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"
CONTEXT_PORTFOLIO = FE / "pages" / "ContextPortfolio.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. Stable rail-company-card testid ─────────────────────────
def test_h2_card_has_stable_rail_company_card_testid():
    src = _read(CONTEXT_PORTFOLIO)
    # H.2 stable alias for Playwright assertions.
    assert "rail-company-card-${c.id}" in src, (
        "CompanyCard must expose `rail-company-card-<id>` testid for "
        "H.2 Playwright assertions."
    )
    # H.1 back-compat testid retained.
    assert "portfolio-card-${c.id}" in src


# ── T2. data-rail-card-role attribute ───────────────────────────
def test_h2_card_carries_data_rail_card_role_attribute():
    src = _read(CONTEXT_PORTFOLIO)
    # Attribute used by tab-filtering live assertions.
    assert "data-rail-card-role=" in src
    assert 'c.type?.startsWith("ned") ? "ned" : "executive"' in src


def test_h2_card_carries_data_rail_card_id_attribute():
    """`data-rail-card-id={c.id}` lets the Playwright click flow
    target the actual button (since `rail-company-card-<id>` is a
    sr-only sentinel)."""
    src = _read(CONTEXT_PORTFOLIO)
    assert "data-rail-card-id={c.id}" in src


# ── T3. Tab labels include live counts ──────────────────────────
def test_h2_tab_labels_include_real_filtered_counts():
    src = _read(CONTEXT_PORTFOLIO)
    assert "NED · {nedList.length}" in src
    assert "Executive · {execList.length}" in src
    # The lists are computed via classifyRole().
    assert 'classifyRole(c) === "ned"' in src
    assert 'classifyRole(c) === "executive"' in src


# ── T4. Default tab = first non-empty ───────────────────────────
def test_h2_default_tab_resolution_prefers_first_non_empty():
    src = _read(CONTEXT_PORTFOLIO)
    # _initialTab helper checks persisted value first, falls back to
    # _firstNonEmpty().
    assert "const _initialTab" in src
    assert 'nedList.length > 0 ? "ned" : "executive"' in src


# ── T5. localStorage persistence ────────────────────────────────
def test_h2_tab_selection_persists_to_localstorage():
    src = _read(CONTEXT_PORTFOLIO)
    # Key matches spec.
    assert '"akki.portfolio.rail.tab"' in src
    # Read on init.
    assert "localStorage.getItem(" in src
    # Write on tab change via setTab wrapper.
    assert "localStorage.setItem(" in src
    # Wrapped in try/catch so private-mode / quota errors don't crash.
    setter_match = re.search(
        r"const setTab\s*=\s*\(next\)\s*=>\s*\{(.*?)\n\s{2}\};",
        src, flags=re.DOTALL,
    )
    assert setter_match, "setTab wrapper not found"
    assert "try" in setter_match.group(1) and "catch" in setter_match.group(1), (
        "setTab must wrap localStorage.setItem in try/catch."
    )


# ── T6. Card click → switchContext ──────────────────────────────
def test_h2_card_click_invokes_switch_context_only():
    src = _read(CONTEXT_PORTFOLIO)
    # openContext calls switchContext(cid).
    assert "switchContext(cid)" in src
    # Does NOT manually navigate("/app") — AuthContext.switchContext
    # owns navigation (sets window.location.href = "/app" on success).
    open_block = src.split("const openContext = (cid) => {")[1].split("};")[0]
    assert "navigate(\"/app\")" not in open_block and "navigate('/app')" not in open_block, (
        "openContext must not manually navigate('/app') — switchContext "
        "owns post-switch navigation."
    )


# ── T7. + Add Company routes to existing flow ───────────────────
def test_h2_add_company_button_routes_to_existing_flow():
    src = _read(CONTEXT_PORTFOLIO)
    # Reuses the same /app/contexts/new route used by Manage.jsx,
    # TenantSettings.jsx etc.
    assert (
        'navigate("/app/contexts/new")' in src
        or "navigate('/app/contexts/new')" in src
    ), "Add Company button must route to existing /app/contexts/new flow."


# ── T8. Calm-pass — no legacy inline metrics in card ────────────
def test_h2_card_drops_legacy_inline_metrics_row():
    src = _read(CONTEXT_PORTFOLIO)
    # Extract the CompanyCard function block.
    card_match = re.search(
        r"function CompanyCard\(.*?\}\s*\)\s*\{(.*?)\n\}\n",
        src, flags=re.DOTALL,
    )
    assert card_match
    card = card_match.group(1)
    # Legacy `SIGNALS | BRIEFINGS | DOCS` strings as JSX text content
    # are forbidden inside the card.
    for forbidden in (">Signals<", ">Briefings<", ">Docs<",
                      ">SIGNALS<", ">BRIEFINGS<", ">DOCS<"):
        assert forbidden not in card, (
            f"Calm-pass regression: legacy {forbidden!r} reappeared in "
            "CompanyCard. H.1 dropped these for the calm-inviting-feel."
        )
