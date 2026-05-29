"""Solva v2 — Slice 6 (2026-05-29) Cost asymmetry frontend render.

Source-strict guards on `CostAsymmetrySlide.jsx`:
  • Locked DOM contract (`data-solva-v2-slide-kind="cost_asymmetry"`,
    slideState forwarded, footer via SlideShell)
  • Per-scenario machine-readable id via `data-solva-v2-cost-kind` +
    `data-solva-v2-cost-scenario-index`
  • Wave 4.2.followup.2 allowlisted opacity on chips
  • Two-column "If correct / If wrong" layout per scenario
  • Slide mounted in orchestrator between decision_logic and risk_mitigation
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SLIDE = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "slides" / "CostAsymmetrySlide.jsx"
ORCH = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaArtefactV2.jsx"


def test_cost_asymmetry_slide_file_exists():
    assert SLIDE.is_file()


def test_cost_asymmetry_slide_passes_correct_kind_to_shell():
    src = SLIDE.read_text(encoding="utf-8")
    assert 'kind="cost_asymmetry"' in src


def test_cost_asymmetry_slide_threads_slide_state():
    """Per Slice 3b contract — every slide forwards slideState to
    SlideShell so the loading→ready transition fires for the new
    cost_asymmetry slide too."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "slideState," in src
    assert "slideState={slideState}" in src


def test_cost_asymmetry_slide_emits_locked_testids():
    src = SLIDE.read_text(encoding="utf-8")
    for tid in (
        "solva-v2-cost-asymmetry-title",
        "solva-v2-cost-asymmetry-list",
    ):
        assert f'data-testid="{tid}"' in src


def test_cost_asymmetry_slide_carries_per_scenario_machine_ids():
    """Each scenario card must carry a canonical id attribute so
    tests can address it by cost_kind (not by display order)."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "data-solva-v2-cost-kind={sc.cost_kind}" in src
    assert "data-solva-v2-cost-scenario-index={idx}" in src
    assert "data-solva-v2-cost-magnitude={sc.cost_magnitude}" in src


def test_chip_opacity_steps_inside_allowlist():
    """Wave 4.2.followup.2 — every bg-ned-purple/N + border-ned-purple/N
    opacity must be inside the locked allowlist."""
    src = SLIDE.read_text(encoding="utf-8")
    opacities = re.findall(r"ned-purple/(\d+)", src)
    assert opacities, "Expected at least one ned-purple/N reference"
    allowed = {5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100}
    for o in opacities:
        assert int(o) in allowed, (
            f"ned-purple/{o} is OUTSIDE Wave 4.2.followup.2 allowlist"
        )


def test_scenario_renders_if_correct_and_if_wrong_columns():
    """Two-column layout per scenario — both sides must render."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "solva-v2-cost-if-correct-${sc.cost_kind}" in src
    assert "solva-v2-cost-if-wrong-${sc.cost_kind}" in src
    assert "If correct →" in src
    assert "If wrong →" in src


def test_cost_asymmetry_slide_imports_into_orchestrator():
    """SolvaArtefactV2 must import + mount CostAsymmetrySlide so the
    new slide reaches the deck."""
    src = ORCH.read_text(encoding="utf-8")
    assert "import CostAsymmetrySlide" in src
    assert "<CostAsymmetrySlide" in src


def test_cost_asymmetry_positioned_between_decision_logic_and_risk_mitigation():
    """In composeSlides() the cost_asymmetry block must appear AFTER
    decision_logic and BEFORE risk_mitigation — the locked deck order."""
    src = ORCH.read_text(encoding="utf-8")
    decision_idx = src.find('kind: "decision_logic"')
    cost_idx = src.find('kind: "cost_asymmetry"')
    risk_idx = src.find('kind: "risk_mitigation"')
    assert decision_idx > 0
    assert cost_idx > 0
    assert risk_idx > 0
    assert decision_idx < cost_idx < risk_idx, (
        f"Deck order broken — decision_logic={decision_idx}, "
        f"cost_asymmetry={cost_idx}, risk_mitigation={risk_idx}"
    )


def test_no_imperative_phrasing_in_static_copy():
    """Static slide copy must read observationally — no 'You should /
    you must' phrasings even in the intro."""
    src = SLIDE.read_text(encoding="utf-8")
    forbidden = (
        "You should",
        "you should",
        "You must",
        "you must",
        "You need to",
        "you need to",
    )
    for f in forbidden:
        assert f not in src, f"Forbidden imperative {f!r} found in CostAsymmetrySlide.jsx"


def test_cost_kind_label_table_complete():
    """Each locked cost_kind from the Pydantic enum must have a
    human-readable label in the frontend label table — drift between
    the two means the chip would render a raw enum token instead of
    a polished label."""
    src = SLIDE.read_text(encoding="utf-8")
    for kind in (
        "capital_burn", "opportunity_cost", "reputational_risk",
        "optionality_loss", "time_cost", "stakeholder_trust",
    ):
        assert f"{kind}:" in src, (
            f"COST_KIND_LABEL table missing label for {kind!r}"
        )
