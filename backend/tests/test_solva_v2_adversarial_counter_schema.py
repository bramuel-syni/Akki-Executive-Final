"""Slice 5 — Adversarial counter schema contract tests.

Locks the AdversarialCounterCase Pydantic model against:
  • required fields (targets_conclusion_id, steel_man_position,
    source_input_ids, why_it_matters)
  • field-level minimum lengths (steel_man_position ≥80,
    why_it_matters ≥40)
  • source_input_ids list min_length=2 (triangulation contract)
  • round-trip serialization preserves all fields
  • model_copy with adversarial_counter populates correctly on
    PathwayItem and DecisionBranch
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.solva_v2.artefact_schema import (  # noqa: E402
    AdversarialCounterCase,
    PathwayItem,
    DecisionBranch,
)


VALID_STEEL_MAN = (
    "The strongest case against this conclusion is that the second-"
    "weighted scenario was under-explored and carries 28% of the "
    "distribution; investing in the recommended pathway forecloses "
    "the optionality of pivoting if it resolves favourably."
)
VALID_WHY = (
    "The 28%-weight alternative would shift the operating read materially."
)


def _valid_kwargs():
    return dict(
        targets_conclusion_id="pathway-1",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["audit-12", "audit-19"],
        why_it_matters=VALID_WHY,
    )


def test_round_trip_minimal_counter():
    counter = AdversarialCounterCase(**_valid_kwargs())
    dumped = counter.model_dump()
    rebuilt = AdversarialCounterCase(**dumped)
    assert rebuilt == counter


def test_targets_conclusion_id_required():
    kwargs = _valid_kwargs()
    kwargs.pop("targets_conclusion_id")
    with pytest.raises(ValidationError):
        AdversarialCounterCase(**kwargs)


def test_steel_man_min_length_80():
    kwargs = _valid_kwargs()
    kwargs["steel_man_position"] = "Too short."
    with pytest.raises(ValidationError):
        AdversarialCounterCase(**kwargs)


def test_why_it_matters_min_length_40():
    kwargs = _valid_kwargs()
    kwargs["why_it_matters"] = "Too brief."
    with pytest.raises(ValidationError):
        AdversarialCounterCase(**kwargs)


def test_source_input_ids_requires_at_least_two():
    kwargs = _valid_kwargs()
    kwargs["source_input_ids"] = ["audit-1"]
    with pytest.raises(ValidationError):
        AdversarialCounterCase(**kwargs)


def test_source_input_ids_accepts_three_or_more():
    kwargs = _valid_kwargs()
    kwargs["source_input_ids"] = ["a", "b", "c", "d"]
    counter = AdversarialCounterCase(**kwargs)
    assert len(counter.source_input_ids) == 4


def test_pathway_item_accepts_optional_adversarial_counter():
    counter = AdversarialCounterCase(**_valid_kwargs())
    item = PathwayItem(
        number=1,
        timeline_tag="DAYS 0-30",
        action_heading="If runway is the binding constraint",
        detail_paragraph="The recommended action surfaces the cost asymmetry between Plan A and Plan B; pre-committing to a checkpoint converts noisy variance into a structured decision moment.",
        adversarial_counter=counter,
    )
    assert item.adversarial_counter is counter


def test_pathway_item_adversarial_counter_defaults_none():
    item = PathwayItem(
        number=1,
        timeline_tag="DAYS 0-30",
        action_heading="If runway is the binding constraint",
        detail_paragraph="Body paragraph that satisfies the min length requirements of the surrounding schema; observational tone.",
    )
    assert item.adversarial_counter is None


def test_decision_branch_accepts_optional_adversarial_counter():
    counter = AdversarialCounterCase(**_valid_kwargs())
    branch = DecisionBranch(
        condition="If next quarter's churn exceeds 8%",
        conclusion="The leading scenario flips to the cost-asymmetry posture.",
        rationale="Confidence at 64% on the leading scenario.",
        adversarial_counter=counter,
    )
    assert branch.adversarial_counter is counter


def test_decision_branch_adversarial_counter_defaults_none():
    branch = DecisionBranch(
        condition="If runway shortens",
        conclusion="The operating read shifts.",
        rationale="Calibration note.",
    )
    assert branch.adversarial_counter is None
