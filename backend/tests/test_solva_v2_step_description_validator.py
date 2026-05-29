"""Solva v2 — Slice 3a (2026-05-29) step-description validator.

The live reasoning ticker is the most exposed surface for theatricality
drift. Every step_description must be observational, grounded, and
imperative-free. This test suite locks the validator.
"""
from __future__ import annotations

import pytest

from services.solva_v2.stream_schema import (
    StepDescriptionValidationError,
    validate_step_description,
)


# ─────────────────────────────────────────────────────────────────
# PASS — observational, grounded
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "Layer 1 Surface — extracting 4 candidate framings",
    "Layer 2 Depth — triangulating tension 02 against Layer 1 Q4",
    "Layer 3 Synthesis — calibrating cluster A using 3 triangulating sources",
    "Layer 4 Reflection — composing diagnostic interpretation of question 2 of 3",
    "Layer 0 Frame Audit — gating the framing against the grounding contract",
    "Rendered Headline — 3 key findings carried up",
    "Auditing framing of subject 'Develop Strategy'",
    "Weighting 9 scenarios against the calibration ladder",
    "Ranking 3 sensitivity inputs by cluster-weight-shift mechanic",
    "Session complete — 5 layers, 13 slides rendered",
])
def test_observational_descriptions_pass(text):
    validate_step_description(text)  # no exception


# ─────────────────────────────────────────────────────────────────
# REJECT — theatrical / vague / imperative
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "Solva is thinking deeply about your situation",
    "Pondering the hidden tensions in your inputs",
    "Sensing the gaps in your framing",
    "Looking deeply at the evidence",
    "Searching for hidden patterns",
    "Channeling pattern recognition",
    "Let me think about this for a moment",
    "Let's look at the third scenario",
    "Hmm, an interesting tension",
    "Considering your unique situation deeply",
    "You should focus on Tension 02",
    "You must read the synthesis carefully",
    "Would you like to see the alternative scenario?",
    "Thinking about the implications",
])
def test_theatrical_or_imperative_descriptions_rejected(text):
    with pytest.raises(StepDescriptionValidationError):
        validate_step_description(text)


# ─────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────


def test_empty_description_rejected():
    with pytest.raises(StepDescriptionValidationError):
        validate_step_description("")
    with pytest.raises(StepDescriptionValidationError):
        validate_step_description("   ")


def test_overlong_description_rejected():
    text = "Layer 3 Synthesis — calibrating cluster A " + ("blah " * 100)
    with pytest.raises(StepDescriptionValidationError):
        validate_step_description(text)


def test_non_string_rejected():
    with pytest.raises(StepDescriptionValidationError):
        validate_step_description(None)  # type: ignore[arg-type]
    with pytest.raises(StepDescriptionValidationError):
        validate_step_description(42)  # type: ignore[arg-type]
