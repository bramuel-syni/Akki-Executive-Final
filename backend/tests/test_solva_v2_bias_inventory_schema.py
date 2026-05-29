"""Solva v2 — Slice 4 (2026-05-29) Bias Inventory schema lock.

Locks the BiasItem + BiasInventorySection Pydantic shapes:
  • bias_name / bias_display_name required + non-empty
  • likelihood ∈ {high, medium, low}
  • evidence_grounded_reasoning ≥ 40 chars
  • source_input_ids ≥ 1 entry
  • biases list 1..6 entries
  • suggested_mitigation optional
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from services.solva_v2.artefact_schema import (  # noqa: E402
    BiasInventorySection, BiasItem,
)


def _bias(**overrides):
    base = dict(
        bias_name="confirmation_bias",
        bias_display_name="Confirmation bias",
        likelihood="medium",
        evidence_grounded_reasoning=(
            "The framing anchors strongly on the cohort retention story; "
            "secondary signals from pricing got short treatment."
        ),
        source_input_ids=["audit-1"],
        suggested_mitigation=(
            "Seeking evidence that would falsify the framing would test "
            "this assumption."
        ),
    )
    base.update(overrides)
    return BiasItem(**base)


def test_minimal_bias_round_trips():
    b = _bias()
    assert b.bias_name == "confirmation_bias"
    assert b.likelihood == "medium"
    d = b.model_dump()
    assert d["bias_display_name"] == "Confirmation bias"
    assert d["source_input_ids"] == ["audit-1"]


@pytest.mark.parametrize("likelihood", ["high", "medium", "low"])
def test_likelihood_accepts_locked_values(likelihood):
    b = _bias(likelihood=likelihood)
    assert b.likelihood == likelihood


def test_likelihood_rejects_other_values():
    with pytest.raises(ValidationError):
        _bias(likelihood="extreme")
    with pytest.raises(ValidationError):
        _bias(likelihood="")


def test_evidence_reasoning_min_length_40_chars():
    """Slice 4 contract — reasoning must be substantive (≥40 chars)
    so the LLM can't ship a one-word excuse."""
    with pytest.raises(ValidationError):
        _bias(evidence_grounded_reasoning="short")
    # 40 chars exactly should pass.
    text = "x" * 40
    b = _bias(evidence_grounded_reasoning=text)
    assert len(b.evidence_grounded_reasoning) == 40


def test_source_input_ids_min_one_required():
    with pytest.raises(ValidationError):
        _bias(source_input_ids=[])


def test_suggested_mitigation_optional():
    b = _bias(suggested_mitigation=None)
    assert b.suggested_mitigation is None


def test_bias_inventory_min_one_max_six():
    """Locked range. 0 biases → bug (Trust pillar 2 = always present).
    >6 → noise; the founder can't usefully read more than 6 named
    biases per artefact."""
    with pytest.raises(ValidationError):
        BiasInventorySection(biases=[])
    seven = [_bias(bias_name=f"b_{i}", bias_display_name=f"Bias {i}") for i in range(7)]
    with pytest.raises(ValidationError):
        BiasInventorySection(biases=seven)
    valid = BiasInventorySection(biases=[_bias()])
    assert len(valid.biases) == 1


def test_intro_copy_has_default():
    """Default intro_copy is set so engines can populate biases without
    needing to author the slide framing."""
    s = BiasInventorySection(biases=[_bias()])
    assert "bias" in s.intro_copy.lower()
