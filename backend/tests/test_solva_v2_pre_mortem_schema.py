"""Slice 5 — Pre-mortem schema contract tests.

Locks the PreMortemSlide / PreMortemFailureMode Pydantic models
against the locked contract (≥1 failure mode required, locked
failure_kind enum, ≥80 char failure_narrative, ≥1 triggering signal,
≥1 source citation, optional counter_action).
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.solva_v2.artefact_schema import (  # noqa: E402
    PreMortemSlide,
    PreMortemFailureMode,
    ArtefactPayload,
)


VALID_NARRATIVE = (
    "The pathway anchors on the cohort retention signal being the "
    "dominant read; if the signal turns out cohort-specific, the "
    "recommended pathway commits resources to a misread that surfaces "
    "only after the timeline window closes."
)


def _valid_failure(**overrides):
    base = dict(
        failure_kind="data_signal_misread",
        failure_narrative=VALID_NARRATIVE,
        triggering_signals=["Cohort retention reverts to baseline"],
        source_input_ids=["audit-1"],
    )
    base.update(overrides)
    return PreMortemFailureMode(**base)


def test_minimal_pre_mortem_round_trips():
    slide = PreMortemSlide(failure_modes=[_valid_failure()])
    dumped = slide.model_dump()
    rebuilt = PreMortemSlide(**dumped)
    assert rebuilt == slide


def test_failure_kind_enum_locked():
    with pytest.raises(ValidationError):
        _valid_failure(failure_kind="freeform_label")


def test_failure_kind_accepts_each_locked_value():
    for kind in (
        "execution_velocity",
        "market_shift",
        "stakeholder_misalignment",
        "data_signal_misread",
        "capability_gap",
        "external_shock",
    ):
        fm = _valid_failure(failure_kind=kind)
        assert fm.failure_kind == kind


def test_failure_narrative_min_length_80():
    with pytest.raises(ValidationError):
        _valid_failure(failure_narrative="The pathway might fail.")


def test_triggering_signals_at_least_one():
    with pytest.raises(ValidationError):
        _valid_failure(triggering_signals=[])


def test_source_input_ids_at_least_one():
    with pytest.raises(ValidationError):
        _valid_failure(source_input_ids=[])


def test_counter_action_optional():
    fm = _valid_failure()
    assert fm.counter_action is None
    fm2 = _valid_failure(
        counter_action=(
            "Investigating cohort-stratified retention before committing "
            "would surface this risk earlier."
        )
    )
    assert fm2.counter_action.startswith("Investigating")


def test_failure_modes_min_length_one():
    with pytest.raises(ValidationError):
        PreMortemSlide(failure_modes=[])


def test_failure_modes_max_length_six():
    items = [_valid_failure() for _ in range(7)]
    with pytest.raises(ValidationError):
        PreMortemSlide(failure_modes=items)


def test_artefact_payload_requires_pre_mortem_field():
    """ArtefactPayload must declare `pre_mortem` as a required field."""
    fields = ArtefactPayload.model_fields
    assert "pre_mortem" in fields, "ArtefactPayload missing required pre_mortem field"
    # Required field has no default value
    assert fields["pre_mortem"].is_required(), "pre_mortem must be required"
