"""Slice 5 — Adversarial counter integrity validator tests.

Locks `adversarial_counter_evidence_grounded`:
  • each adversarial_counter (on pathway items + decision branches)
    must cite ≥2 source_input_ids resolving to audit-log entries,
    user turns, OR coarse layer tags.
  • imperative phrasings in steel_man_position / why_it_matters are
    blocked.
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
    AdversarialCounterCase,
)
from services.solva_v2.integrity_validators import (  # noqa: E402
    adversarial_counter_evidence_grounded,
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


def _pre_mortem():
    return PreMortemSlide(
        failure_modes=[
            PreMortemFailureMode(
                failure_kind="data_signal_misread",
                failure_narrative=(
                    "The pathway anchors on a single dominant read; if "
                    "the underlying signal is cohort-specific the "
                    "pathway commits to a misread that surfaces only "
                    "after the timeline closes."
                ),
                triggering_signals=["Signal reverts at next intake"],
                source_input_ids=["audit-1"],
            ),
        ],
    )


def _payload(pathway, decision_logic):
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
                KeyFinding(number=i, paragraph_text=f"Finding {i} paragraph long enough.",
                           source_citations=[SourceCitation(source_kind="user_turn",
                                                            source_input_id="audit-1",
                                                            excerpt="Quote.")])
                for i in (1, 2, 3)
            ],
        ),
        scenarios=[
            ScenarioRow(
                label="Scenario A", description="Description.",
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
        pathway=pathway,
        decision_logic=decision_logic,
        risk_mitigation=[],
        methodological_honesty=MethodologicalHonesty(
            what_report_is="Report-is paragraph at locked min length.",
            what_report_is_not="Report-is-not paragraph at locked length.",
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
        pre_mortem=_pre_mortem(),
        per_scenario_confidence_table=PerScenarioConfidenceTable(),
    )


VALID_STEEL_MAN = (
    "The strongest case against this conclusion is that the second-"
    "weighted scenario was under-explored and carries 28% of the "
    "distribution; investing forecloses the pivot optionality."
)
VALID_WHY = (
    "The 28%-weight alternative would shift the operating read materially."
)


def _pathway_item(counter):
    return PathwayItem(
        number=1,
        timeline_tag="DAYS 0-30",
        action_heading="If runway is the binding constraint",
        detail_paragraph=(
            "The recommended action surfaces the cost asymmetry between "
            "Plan A and Plan B; pre-committing to a checkpoint converts "
            "noisy variance into structured decision moments."
        ),
        adversarial_counter=counter,
    )


def _branch(counter):
    return DecisionBranch(
        condition="If next quarter's churn exceeds 8%",
        conclusion="The leading scenario flips toward the cost-asymmetry posture.",
        rationale="Confidence at 64% on the leading scenario.",
        adversarial_counter=counter,
    )


# ─────────────────────────────────────────────────────────────────
# resolvability — ≥2 ids must resolve
# ─────────────────────────────────────────────────────────────────


def test_passes_when_pathway_counter_cites_two_real_audit_ids():
    counter = AdversarialCounterCase(
        targets_conclusion_id="pathway-1",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["audit-1", "audit-2"],
        why_it_matters=VALID_WHY,
    )
    p = _payload([_pathway_item(counter)], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert offs == []


def test_passes_when_counter_cites_coarse_layer_tags():
    counter = AdversarialCounterCase(
        targets_conclusion_id="pathway-1",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["L2", "L3"],
        why_it_matters=VALID_WHY,
    )
    p = _payload([_pathway_item(counter)], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert offs == []


def test_blocks_when_only_one_id_resolves():
    counter = AdversarialCounterCase(
        targets_conclusion_id="pathway-1",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["audit-1", "garbage-id"],
        why_it_matters=VALID_WHY,
    )
    p = _payload([_pathway_item(counter)], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert len(offs) == 1
    o = offs[0]
    assert o.severity == "block"
    assert "1 resolved source" in o.message
    assert "pathway[0].adversarial_counter" in o.location


def test_blocks_when_zero_ids_resolve():
    counter = AdversarialCounterCase(
        targets_conclusion_id="decision-0",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["bogus-1", "bogus-2"],
        why_it_matters=VALID_WHY,
    )
    p = _payload([], [_branch(counter)])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert any("0 resolved source" in o.message for o in offs)


def test_passes_with_no_counter_attached():
    p = _payload([_pathway_item(None)], [_branch(None)])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert offs == []


# ─────────────────────────────────────────────────────────────────
# imperative phrasing — blocked in steel_man + why_it_matters
# ─────────────────────────────────────────────────────────────────


def test_blocks_imperative_in_steel_man():
    counter = AdversarialCounterCase(
        targets_conclusion_id="pathway-1",
        steel_man_position=(
            "You should consider that the second-weighted scenario was "
            "under-explored and carries 28% of the distribution."
        ),
        source_input_ids=["L2", "L3"],
        why_it_matters=VALID_WHY,
    )
    p = _payload([_pathway_item(counter)], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert any("Imperative" in o.message for o in offs)


def test_blocks_imperative_in_why_it_matters():
    counter = AdversarialCounterCase(
        targets_conclusion_id="pathway-1",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["L2", "L3"],
        why_it_matters="You must address the 28%-weight alternative immediately.",
    )
    p = _payload([_pathway_item(counter)], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert any("Imperative" in o.message for o in offs)


def test_decision_branch_counter_resolution_checked():
    counter = AdversarialCounterCase(
        targets_conclusion_id="decision-0",
        steel_man_position=VALID_STEEL_MAN,
        source_input_ids=["bogus-x", "bogus-y"],
        why_it_matters=VALID_WHY,
    )
    p = _payload([], [_branch(counter)])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert any("decision_logic[0]" in o.location for o in offs)


def test_observational_steel_man_passes_validator():
    counter = AdversarialCounterCase(
        targets_conclusion_id="pathway-1",
        steel_man_position=(
            "The strongest case against this conclusion is that the "
            "evidence supports a continuum where the binary trigger "
            "would fire noisily; the if-clause may be too narrow."
        ),
        source_input_ids=["L2", "L3"],
        why_it_matters=(
            "Branch logic that ignores intermediate evidence states "
            "converts smooth signal into discrete action."
        ),
    )
    p = _payload([_pathway_item(counter)], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert offs == []


def test_payload_with_no_pathway_or_branches_passes():
    p = _payload([], [])
    offs = adversarial_counter_evidence_grounded(p, _audit_session())
    assert offs == []
