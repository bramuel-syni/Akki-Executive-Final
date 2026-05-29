"""Solva v2 — Slice 2b contract guard: locked 13-kind inventory.

THE FAILURE THIS TEST EXISTS TO CATCH

The prior Slice 2b close-out claimed the 13-kind contract was met
but the rendered DOM showed:
  - 5 missing kinds (tensions_overview / per_tension / per_scenario_table /
    pathway / risk_mitigation) — because they were skipped when the
    payload arc data was empty
  - 2 unexpected kinds (`section_divider` polluting the enum;
    `per_scenario_confidence_table` was the wrong name)

This test locks the contract at THREE layers:

  1. Source-strict (the orchestrator composes a slides[] entry per
     kind UNCONDITIONALLY — no `.length > 0` gates)
  2. Per-slide-template (every component passes the locked kind enum
     value to SlideShell)
  3. Optional runtime — if E1_SMOKE_URL is set, walks the rendered
     DOM at 1280 and asserts every kind in the enum is present ≥1
     and no kind appears outside the enum.

LOCKED ENUM (13 kinds, frozen)

    LOCKED_KINDS = {
        "cover", "headline",
        "tensions_overview", "per_tension",
        "scenarios_overview", "per_scenario_table", "sensitivity",
        "reflection",
        "pathway", "decision_logic", "risk_mitigation",
        "methodological_honesty", "in_closing",
    }

Section dividers are NOT slides — they have their own attribute
`data-solva-v2-section-divider="true"`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
V2_DIR = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2"
ORCH = V2_DIR / "SolvaArtefactV2.jsx"
SLIDES = V2_DIR / "slides"


LOCKED_KINDS = frozenset({
    "cover",
    "headline",
    "tensions_overview",
    "per_tension",
    "scenarios_overview",
    "per_scenario_table",
    "sensitivity",
    "reflection",
    "bias_inventory",
    "pathway",
    "decision_logic",
    "risk_mitigation",
    "methodological_honesty",
    "in_closing",
})


# ─────────────────────────────────────────────────────────────────
# A. Source-strict: orchestrator composes all 13 unconditionally
# ─────────────────────────────────────────────────────────────────


def test_orchestrator_composes_every_locked_kind():
    """The orchestrator MUST push a slides[] entry with each of the
    13 locked kinds. This contract is independent of payload data —
    an empty arc surfaces as a slide with empty-state copy, NOT as a
    missing slide."""
    raw = ORCH.read_text(encoding="utf-8")
    src = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    src = re.sub(r"//[^\n]*", "", src)
    missing = [k for k in LOCKED_KINDS if f'kind: "{k}"' not in src]
    assert not missing, (
        "Orchestrator missing locked kinds: "
        + ", ".join(sorted(missing))
        + ".\nEvery one of the 13 locked kinds must compose a slides[] entry."
    )


def test_orchestrator_only_uses_locked_kinds_plus_section_divider():
    """The orchestrator MUST NOT introduce kinds outside the locked
    enum (besides the section_divider helper)."""
    raw = ORCH.read_text(encoding="utf-8")
    src = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    src = re.sub(r"//[^\n]*", "", src)
    found = set(re.findall(r'kind:\s*"([a-z_]+)"', src))
    allowed = LOCKED_KINDS | {"section_divider"}
    extras = found - allowed
    assert not extras, (
        "Orchestrator uses unexpected kinds: "
        + ", ".join(sorted(extras))
        + f"\nAllowed: {sorted(allowed)}"
    )


def test_orchestrator_renders_kinds_unconditionally():
    """No locked kind may be gated behind a single `.length > 0`
    conditional with no `else` fallback. The orchestrator's
    `composeSlides()` must surface every locked kind every time so
    the rendered kind inventory is consistent across sessions.

    Heuristic: a kind is unconditional if EITHER
      (a) it appears outside any `if (...) { ... }` block at the
          composeSlides function's top level, OR
      (b) it appears in BOTH branches of an `if (X.length > 0) { ... }
          else { ... }` pattern (count ≥ 2 push sites).

    A kind that appears EXACTLY ONCE and is enclosed in a `.length`
    -gated if-block with no else branch is the violation.
    """
    raw = ORCH.read_text(encoding="utf-8")
    src = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    src = re.sub(r"//[^\n]*", "", src)
    lines = src.splitlines()

    offenders = []
    for kind in LOCKED_KINDS:
        push_lines = [i for i, ln in enumerate(lines) if f'kind: "{kind}"' in ln]
        if not push_lines:
            offenders.append(f"kind={kind!r}: never pushed in composeSlides()")
            continue
        # Rule (b): ≥ 2 push sites → assume if/else fallback covers it.
        if len(push_lines) >= 2:
            continue
        # Rule (a): exactly 1 push site — verify it's NOT inside a
        # `.length`-gated `if` block.
        i = push_lines[0]
        depth = 0
        gated = False
        for j in range(i, max(0, i - 80), -1):
            text = lines[j]
            depth += text.count("}") - text.count("{")
            if depth < 0:
                # Found the enclosing block opener. Look 4 lines above
                # for the matching `if` / `} else` head.
                for k in range(j, max(0, j - 4), -1):
                    head = lines[k].lstrip()
                    if head.startswith("if (") or head.startswith("if("):
                        if ".length" in head:
                            gated = True
                        break
                    if head.startswith("} else") or head.startswith("else"):
                        # We're inside an else branch — count as
                        # unconditional fallback.
                        gated = False
                        break
                break
        if gated:
            offenders.append(
                f"kind={kind!r}: exactly 1 push site, gated by a `.length` if-block "
                f"with no else-fallback (line {i+1})."
            )
    assert not offenders, "Conditional-only kinds detected:\n  " + "\n  ".join(offenders)


# ─────────────────────────────────────────────────────────────────
# B. Per-template strictness — kind enum lock
# ─────────────────────────────────────────────────────────────────


KIND_PER_TEMPLATE = {
    "CoverSlide.jsx":                  "cover",
    "HeadlineSlide.jsx":               "headline",
    "TensionsOverviewSlide.jsx":       "tensions_overview",
    "PerTensionSlide.jsx":             "per_tension",
    "ScenariosOverviewSlide.jsx":      "scenarios_overview",
    "PerScenarioConfidenceTable.jsx":  "per_scenario_table",
    "SensitivitySlide.jsx":            "sensitivity",
    "ReflectionSlide.jsx":             "reflection",
    "BiasInventorySlide.jsx":          "bias_inventory",
    "PathwaySlide.jsx":                "pathway",
    "DecisionLogicSlide.jsx":          "decision_logic",
    "RiskMitigationSlide.jsx":         "risk_mitigation",
    "MethodologicalHonestySlide.jsx":  "methodological_honesty",
    "InClosingSlide.jsx":              "in_closing",
}


def test_every_template_passes_locked_kind_value():
    """Each slide component MUST pass the EXACT locked kind enum
    value to SlideShell — not the file name, not the Pydantic field
    name, not a shortened variant."""
    for filename, locked_kind in KIND_PER_TEMPLATE.items():
        src = (SLIDES / filename).read_text(encoding="utf-8")
        match = re.search(r'kind="([^"]+)"', src)
        assert match, f"{filename}: must pass a `kind=` prop to SlideShell."
        assert match.group(1) == locked_kind, (
            f"{filename}: passes kind={match.group(1)!r}, "
            f"locked enum value is {locked_kind!r}."
        )


# ─────────────────────────────────────────────────────────────────
# C. Section dividers must NOT pollute the kind inventory
# ─────────────────────────────────────────────────────────────────


def test_section_divider_carries_no_slide_kind_attribute():
    """SectionDivider is a visual separator, not a slide. It MUST
    NOT carry the `data-solva-v2-slide-kind` data-attribute."""
    raw = (V2_DIR / "SectionDivider.jsx").read_text(encoding="utf-8")
    # Strip comments so docstring references don't trip the guard.
    code = re.sub(r"/\*[\s\S]*?\*/", "", raw)
    code = re.sub(r"//[^\n]*", "", code)
    assert "data-solva-v2-slide-kind" not in code
    assert 'data-solva-v2-slide="true"' not in code
    assert 'data-solva-v2-section-divider="true"' in code


# ─────────────────────────────────────────────────────────────────
# D. Optional runtime — walks the rendered DOM at 1280
# ─────────────────────────────────────────────────────────────────


SMOKE_URL = os.environ.get("E1_SMOKE_URL") or os.environ.get("SOLVA_V2_SMOKE_URL")


@pytest.mark.skipif(not SMOKE_URL, reason="Set E1_SMOKE_URL=<authed-preview>/app/solva/session/<sid> to run.")
def test_runtime_kind_inventory_matches_locked_enum():
    """Live Playwright probe — navigates to the smoke URL (which
    must already include an authenticated session reaching ARTEFACT
    state) and verifies the rendered DOM:
      • Every locked kind appears ≥1 time
      • No kind appears outside the locked enum
      • No `data-solva-v2-slide` attribute appears with a missing or
        empty kind value
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:  # noqa: BLE001
        pytest.skip("Playwright not installed in this environment.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            page = ctx.new_page()
            page.goto(SMOKE_URL, wait_until="networkidle")
            page.wait_for_selector('[data-testid="solva-v2-artefact-root"]', timeout=30_000)
            inventory = page.evaluate(
                """() => {
                    const out = {};
                    document.querySelectorAll('[data-solva-v2-slide-kind]').forEach(el => {
                        const k = el.getAttribute('data-solva-v2-slide-kind') || '';
                        out[k] = (out[k] || 0) + 1;
                    });
                    return out;
                }"""
            )
            ctx.close()
        finally:
            browser.close()

    found = set(inventory.keys())
    missing = LOCKED_KINDS - found
    extras = found - LOCKED_KINDS
    assert not missing, f"Runtime DOM missing locked kinds: {sorted(missing)}\nInventory: {inventory}"
    assert not extras, f"Runtime DOM contains kinds outside locked enum: {sorted(extras)}\nInventory: {inventory}"
    # And no slide may have an empty kind attribute.
    assert "" not in found, "A slide rendered with an empty data-solva-v2-slide-kind."
