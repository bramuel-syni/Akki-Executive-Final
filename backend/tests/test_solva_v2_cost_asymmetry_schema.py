"""Slice 6 — Cost asymmetry schema contract tests.

Locks `CostAsymmetrySlide` / `CostAsymmetryScenario` against:
  • required fields (pathway_label, if_correct_outcome, if_wrong_cost,
    cost_kind, cost_magnitude, source_input_ids)
  • field-level min lengths (if_correct_outcome ≥80, if_wrong_cost ≥80)
  • locked cost_kind enum + cost_magnitude enum
  • slide-level min_length=2 (asymmetry requires ≥2 scenarios)
  • REQUIRED on the ArtefactPayload root
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.solva_v2.artefact_schema import (  # noqa: E402
    CostAsymmetrySlide,
    CostAsymmetryScenario,
    ArtefactPayload,
)


VALID_OUTCOME = (
    "If this pathway resolves favourably, the operating read converges "
    "on the leading scenario; sensitivity inputs hold across the cycle."
)
VALID_COST = (
    "If this pathway turns out misaligned, committed capital lands on a "
    "misread; recovery absorbs the next planning cycle."
)


def _valid_scenario(**overrides):
    base = dict(
        pathway_label="Pathway 1",
        if_correct_outcome=VALID_OUTCOME,
        if_wrong_cost=VALID_COST,
        cost_kind="capital_burn",
        cost_magnitude="medium",
        source_input_ids=["audit-1"],
    )
    base.update(overrides)
    return CostAsymmetryScenario(**base)


def test_minimal_cost_asymmetry_round_trips():
    slide = CostAsymmetrySlide(scenarios=[_valid_scenario(), _valid_scenario(pathway_label="Pathway 2")])
    dumped = slide.model_dump()
    rebuilt = CostAsymmetrySlide(**dumped)
    assert rebuilt == slide


def test_cost_kind_enum_locked():
    with pytest.raises(ValidationError):
        _valid_scenario(cost_kind="invented_kind")


def test_cost_kind_accepts_each_locked_value():
    for kind in (
        "capital_burn",
        "opportunity_cost",
        "reputational_risk",
        "optionality_loss",
        "time_cost",
        "stakeholder_trust",
    ):
        sc = _valid_scenario(cost_kind=kind)
        assert sc.cost_kind == kind


def test_cost_magnitude_enum_locked():
    with pytest.raises(ValidationError):
        _valid_scenario(cost_magnitude="extreme")
    for mag in ("low", "medium", "high"):
        sc = _valid_scenario(cost_magnitude=mag)
        assert sc.cost_magnitude == mag


def test_if_correct_min_length_80():
    with pytest.raises(ValidationError):
        _valid_scenario(if_correct_outcome="Too short.")


def test_if_wrong_min_length_80():
    with pytest.raises(ValidationError):
        _valid_scenario(if_wrong_cost="Too short.")


def test_source_input_ids_at_least_one():
    with pytest.raises(ValidationError):
        _valid_scenario(source_input_ids=[])


def test_scenarios_min_length_two():
    """The slide MUST carry ≥2 scenarios — you cannot have an
    'asymmetry' with one option."""
    with pytest.raises(ValidationError):
        CostAsymmetrySlide(scenarios=[_valid_scenario()])


def test_scenarios_max_length_six():
    items = [_valid_scenario() for _ in range(7)]
    with pytest.raises(ValidationError):
        CostAsymmetrySlide(scenarios=items)


def test_artefact_payload_requires_cost_asymmetry_field():
    """ArtefactPayload MUST declare `cost_asymmetry` as a required
    field — accidentally omitting it from a future builder version
    must fail at the Pydantic model level."""
    fields = ArtefactPayload.model_fields
    assert "cost_asymmetry" in fields
    assert fields["cost_asymmetry"].is_required()
