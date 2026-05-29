"""Solva v2 — Slice 5 (2026-05-29) Adversarial counter callout render.

Locks the inline callout block on PathwaySlide and DecisionLogicSlide
that surfaces when an `adversarial_counter` is attached:
  • Conditional render — the callout MUST NOT render unless the
    backing field is populated.
  • Locked DOM contract: data-testid + data-solva-v2-adversarial-counter
    attribute carrying the source slide kind.
  • Wave 4.2.followup.2 — bg-ned-purple/N opacity inside allowlist.
  • Locked human-readable label: 'Strongest case against this conclusion'.
  • 'Why it matters' inline label rendered alongside the steel-man.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATHWAY = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "slides" / "PathwaySlide.jsx"
DECISION = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "slides" / "DecisionLogicSlide.jsx"


def test_pathway_renders_adversarial_counter_callout():
    src = PATHWAY.read_text(encoding="utf-8")
    assert "p.adversarial_counter" in src
    assert 'data-solva-v2-adversarial-counter="pathway"' in src
    assert "Strongest case against this conclusion" in src


def test_decision_logic_renders_adversarial_counter_callout():
    src = DECISION.read_text(encoding="utf-8")
    assert "b.adversarial_counter" in src
    assert 'data-solva-v2-adversarial-counter="decision_logic"' in src
    assert "Strongest case against this conclusion" in src


def test_pathway_callout_uses_allowlisted_opacity():
    """Wave 4.2.followup.2 — the callout's brand-purple background and
    border opacity must be inside the locked opacity allowlist."""
    src = PATHWAY.read_text(encoding="utf-8")
    # Find the adversarial counter block (starts at the conditional render guard)
    block_match = re.search(
        r"p\.adversarial_counter\s*&&\s*\(.*?</div>\s*\)\s*}",
        src, re.DOTALL,
    )
    assert block_match, "Could not isolate pathway adversarial counter block"
    block = block_match.group(0)
    opacities = re.findall(r"ned-purple/(\d+)", block)
    assert opacities, "Expected at least one ned-purple/N usage in callout"
    allowed = {5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100}
    for o in opacities:
        assert int(o) in allowed, (
            f"ned-purple/{o} is OUTSIDE Wave 4.2.followup.2 allowlist in pathway callout"
        )


def test_decision_callout_uses_allowlisted_opacity():
    src = DECISION.read_text(encoding="utf-8")
    block_match = re.search(
        r"b\.adversarial_counter\s*&&\s*\(.*?</div>\s*\)\s*}",
        src, re.DOTALL,
    )
    assert block_match, "Could not isolate decision_logic adversarial counter block"
    block = block_match.group(0)
    opacities = re.findall(r"ned-purple/(\d+)", block)
    assert opacities, "Expected at least one ned-purple/N usage in decision callout"
    allowed = {5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100}
    for o in opacities:
        assert int(o) in allowed, (
            f"ned-purple/{o} is OUTSIDE Wave 4.2.followup.2 allowlist in decision callout"
        )


def test_pathway_callout_carries_per_pathway_testid():
    """Each callout must carry a per-recommendation testid so tests
    can address the leading-pathway counter directly."""
    src = PATHWAY.read_text(encoding="utf-8")
    assert "solva-v2-pathway-adversarial-${p.number || idx + 1}" in src


def test_decision_callout_carries_per_branch_testid():
    src = DECISION.read_text(encoding="utf-8")
    assert "solva-v2-decision-adversarial-${idx}" in src


def test_pathway_callout_renders_why_it_matters_block():
    src = PATHWAY.read_text(encoding="utf-8")
    assert "p.adversarial_counter.steel_man_position" in src
    assert "p.adversarial_counter.why_it_matters" in src
    assert "Why it matters ·" in src


def test_decision_callout_renders_why_it_matters_block():
    src = DECISION.read_text(encoding="utf-8")
    assert "b.adversarial_counter.steel_man_position" in src
    assert "b.adversarial_counter.why_it_matters" in src
    assert "Why it matters ·" in src


def test_callouts_use_conditional_render_guard():
    """The callout MUST NOT render unless the backing field is
    populated — empty payloads must not surface a phantom callout
    block."""
    pathway_src = PATHWAY.read_text(encoding="utf-8")
    decision_src = DECISION.read_text(encoding="utf-8")
    assert "p.adversarial_counter && (" in pathway_src
    assert "b.adversarial_counter && (" in decision_src


def test_callouts_use_observational_label_not_recommendation():
    """The label must read 'Strongest case against this conclusion'
    NOT 'You should consider' or 'Recommendation' — the steel-man
    counter is observational."""
    for path in (PATHWAY, DECISION):
        src = path.read_text(encoding="utf-8")
        # Anchor: locked human-readable label
        assert "Strongest case against this conclusion" in src
        # Banned imperatives in the callout copy
        for banned in ("You should consider", "We recommend", "You must"):
            assert banned not in src, (
                f"{banned!r} found in {path.name} — violates observational tone"
            )
