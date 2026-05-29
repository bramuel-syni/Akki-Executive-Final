"""Solva v2 — Slice 4 (2026-05-29) Bias Inventory frontend render.

Source-strict guards on `BiasInventorySlide.jsx`:
  • Locked DOM contract (data-solva-v2-slide=true + kind="bias_inventory"
    + slide-state attribute + footer)
  • Likelihood pill opacity steps inside the Wave 4.2.followup.2 allowlist
  • Observational copy (no theatricality drift; no imperatives)
  • Per-bias machine-readable testid via data-solva-v2-bias-name
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SLIDE = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "slides" / "BiasInventorySlide.jsx"
ORCH = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaArtefactV2.jsx"


def test_bias_slide_file_exists():
    assert SLIDE.is_file()


def test_bias_slide_passes_correct_kind_to_shell():
    src = SLIDE.read_text(encoding="utf-8")
    assert 'kind="bias_inventory"' in src


def test_bias_slide_threads_slide_state():
    """Per Slice 3b contract — every slide forwards slideState to
    SlideShell so the loading→ready transition fires for the new
    bias_inventory slide too."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "slideState," in src
    assert "slideState={slideState}" in src


def test_bias_slide_emits_locked_testids():
    src = SLIDE.read_text(encoding="utf-8")
    for tid in (
        "solva-v2-bias-inventory-title",
        "solva-v2-bias-inventory-list",
    ):
        assert f'data-testid="{tid}"' in src


def test_bias_slide_carries_per_bias_machine_id_attribute():
    """Each bias card must carry `data-solva-v2-bias-name={bias_name}`
    so tests can probe by canonical id (machine-readable) regardless
    of the human-readable display name."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "data-solva-v2-bias-name={b.bias_name}" in src
    assert "data-solva-v2-bias-likelihood={b.likelihood}" in src


def test_likelihood_pills_use_allowlisted_opacity_steps():
    """Wave 4.2.followup.2 — opacity steps must be inside the allowlist
    {5,10,15,20,25,30,40,50,60,70,75,80,90,95,100}. The likelihood
    pill maps high → /30, medium → /20, low → /10. All three are in
    the allowlist."""
    src = SLIDE.read_text(encoding="utf-8")
    # Positive evidence
    assert "bg-ned-purple/30" in src
    assert "bg-ned-purple/20" in src
    assert "bg-ned-purple/10" in src
    # Negative — invalid steps must NOT appear
    bad = re.findall(r"bg-ned-purple/(\d+)", src)
    allowed = {5,10,15,20,25,30,40,50,60,70,75,80,90,95,100}
    invalid = [int(n) for n in bad if int(n) not in allowed]
    assert not invalid, f"Invalid Tailwind opacity steps: {invalid}"


def test_no_hex_var_with_opacity_modifier():
    """Wave 4.2.followup.2 — `bg-[var(--ned-purple)]/N` silently fails."""
    src = SLIDE.read_text(encoding="utf-8")
    assert not re.search(r"bg-\[var\(--ned-purple\)\]/\d+", src)
    assert not re.search(r"border-\[var\(--ned-purple\)\]/\d+", src)


def test_bias_slide_does_not_theatricalise():
    """Observational copy lock — same forbidden-phrase pattern as the
    SSE step-description validator. Bias inventory has higher
    theatricality risk than other slides because biases are an
    inherently psychological topic; the visual must stay grounded."""
    src = SLIDE.read_text(encoding="utf-8")
    forbidden = (
        "thinking deeply", "pondering", "looking deeply",
        "let me", "would you like", "you should", "you must",
        "intuiting", "channeling", "sensing the", "hidden truths",
    )
    lower = src.lower()
    for needle in forbidden:
        assert needle not in lower, f"Bias slide must not contain {needle!r}."


def test_orchestrator_wires_bias_inventory_between_reflection_and_pathway():
    """The bias inventory slide MUST sit AFTER reflection and BEFORE
    pathway in the deck order — per the Slice 4 narrative arc: founder
    reflects → see bias landscape → move to recommendations."""
    src = ORCH.read_text(encoding="utf-8")
    refl_idx = src.find('kind: "reflection"')
    bias_idx = src.find('kind: "bias_inventory"')
    pathway_idx = src.find('kind: "pathway"')
    assert refl_idx > 0 and bias_idx > 0 and pathway_idx > 0
    assert refl_idx < bias_idx < pathway_idx, (
        "Order must be reflection → bias_inventory → pathway. "
        f"Got refl={refl_idx} bias={bias_idx} path={pathway_idx}."
    )


def test_orchestrator_imports_bias_inventory_slide():
    src = ORCH.read_text(encoding="utf-8")
    assert "import BiasInventorySlide" in src
    assert "<BiasInventorySlide" in src
