"""Slice 5 — Pre-mortem integrity validator tests.

Locks two new validators:
  • pre_mortem_present              → block if pre_mortem missing or
                                       failure_modes empty
  • pre_mortem_failure_evidence_grounded → block on unresolved source_ids,
                                       imperative phrasings, or non-
                                       observational counter_action openers
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from services.solva_v2.artefact_schema import (  # noqa: E402
    ArtefactPayload, CoverSlide, HeadlineSlide, KeyFinding,
    SourceCitation, ScenarioRow, PerScenarioConfidenceTable,
    SensitivityInput, ReflectionSection, ReflectionQuestion,
    PathwayItem, DecisionBranch, RiskMitigation,
    MethodologicalHonesty, InClosing,
    BiasInventorySection, BiasItem, FooterTemplate,
    PreMortemSlide, PreMortemFailureMode,
)
from services.solva_v2.integrity_validators import (  # noqa: E402
    pre_mortem_present, pre_mortem_failure_evidence_grounded,
)


def _audit_session():
    return {
        "reasoning_audit_log": [
            {"id": "audit-1", "layer": "framing"},
            {"id": "audit-2", "layer": "synthesis"},
        ],
        "user_turns": [{"id": "turn-1"}],
    }


def _bias():
    return BiasItem(
        bias_name="confirmation_bias",
        bias_display_name="Confirmation bias",
        likelihood="low",
        evidence_grounded_reasoning=(
            "The framing anchors on the prevailing read; secondary "
            "signals got short treatment in the intake."
        ),
        source_input_ids=["audit-1"],
    )


VALID_NARRATIVE = (
    "The pathway anchors on the cohort retention signal being the "
    "dominant read; if the signal turns out cohort-specific, the "
    "recommended pathway commits resources to a misread that surfaces "
    "only after the timeline window closes."
)


def _failure(**overrides):
    base = dict(
        failure_kind="data_signal_misread",
        failure_narrative=VALID_NARRATIVE,
        triggering_signals=["Cohort retention reverts to baseline"],
        source_input_ids=["audit-1"],
    )
    base.update(overrides)
    return PreMortemFailureMode(**base)


def _payload(pre_mortem_obj):
    return ArtefactPayload(
        session_id="test-sid",
        schema_version="solva.v2.artefact.1.0",
        cover=CoverSlide(
            title="X", prepared_for="Y", subject="Z",
            inputs_range="Layer 0 to Layer 4, 5 inputs",
            date_str="2026-05-29",
        ),
        headline=HeadlineSlide(
            intro_copy="Intro intro intro intro intro intro intro intro.",
            key_findings=[
                KeyFinding(number=i, paragraph_text=f"Finding {i} long enough.",
                           source_citations=[SourceCitation(source_kind="user_turn",
                                                            source_input_id="audit-1",
                                                            excerpt="Quote.")])
                for i in (1, 2, 3)
            ],
        ),
        scenarios=[
            ScenarioRow(
                label="A", description="D.",
                weight_pct=40, confidence_pct=50, tier="domain_prior",
                confidence_calibration_reasoning="Reasoning grounded in corpus.",
            ),
        ],
        sensitivity_inputs=[],
        reflection_section=ReflectionSection(
            title="R", intro_copy="Intro.",
            questions=[
                ReflectionQuestion(question_text="Q1?", diagnostic_interpretation="I."),
                ReflectionQuestion(question_text="Q2?", diagnostic_interpretation="I."),
                ReflectionQuestion(question_text="Q3?", diagnostic_interpretation="I."),
            ],
        ),
        pathway=[],
        decision_logic=[],
        risk_mitigation=[],
        methodological_honesty=MethodologicalHonesty(
            what_report_is="Report-is paragraph long enough.",
            what_report_is_not="Report-is-not paragraph long enough.",
            provisional_nature_paragraph="Provisional paragraph at length.",
            input_confidence_pct=50,
            not_sole_basis_paragraph="Not-sole-basis paragraph long enough.",
        ),
        in_closing=InClosing(
            reframing_paragraph="Reframing paragraph long enough.",
            key_findings_recap=["A"],
            final_statement="Final statement long enough.",
        ),
        bias_inventory=BiasInventorySection(biases=[_bias()]),
        pre_mortem=pre_mortem_obj,
        per_scenario_confidence_table=PerScenarioConfidenceTable(),
    )


# ─────────────────────────────────────────────────────────────────
# pre_mortem_present
# ─────────────────────────────────────────────────────────────────


def test_present_passes_when_one_failure_mode_carried():
    p = _payload(PreMortemSlide(failure_modes=[_failure()]))
    offs = pre_mortem_present(p, _audit_session())
    assert offs == []


def test_present_passes_for_multiple_failure_modes():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(),
        _failure(failure_kind="execution_velocity"),
        _failure(failure_kind="stakeholder_misalignment"),
    ]))
    offs = pre_mortem_present(p, _audit_session())
    assert offs == []


# ─────────────────────────────────────────────────────────────────
# pre_mortem_failure_evidence_grounded — citation resolution
# ─────────────────────────────────────────────────────────────────


def test_evidence_passes_for_resolved_audit_id():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(source_input_ids=["audit-1"]),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert offs == []


def test_evidence_passes_for_coarse_layer_tag():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(source_input_ids=["L3"]),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert offs == []


def test_evidence_blocks_unresolved_id():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(source_input_ids=["bogus-id"]),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert len(offs) == 1
    assert offs[0].severity == "block"
    assert "unresolved source" in offs[0].message


# ─────────────────────────────────────────────────────────────────
# observational counter_action opener
# ─────────────────────────────────────────────────────────────────


def test_observational_counter_action_passes():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(counter_action=(
            "Investigating cohort-stratified retention before committing "
            "would surface this risk earlier."
        )),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert offs == []


def test_imperative_counter_action_blocked():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(counter_action=(
            "You should investigate cohort-stratified retention before "
            "committing the pathway."
        )),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert any("counter_action" in o.location for o in offs)


def test_observational_opener_monitoring_passes():
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(counter_action=(
            "Monitoring the leading-indicator cadence weekly would "
            "surface this risk earlier."
        )),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert offs == []


def test_imperative_failure_narrative_blocked():
    bad = (
        "You must address the cohort retention drift immediately or the "
        "pathway will fail by quarter-end. The signal is too weak to be "
        "ignored across the upcoming planning cycle."
    )
    p = _payload(PreMortemSlide(failure_modes=[
        _failure(failure_narrative=bad),
    ]))
    offs = pre_mortem_failure_evidence_grounded(p, _audit_session())
    assert any("Imperative" in o.message for o in offs)
