"""Solva v2 Slice 1 — Artefact schema serialization tests.

Schema completeness check: a minimum-viable payload covering all 15
elements serializes cleanly and round-trips through Pydantic's
.model_dump() / .model_validate() cycle.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from services.solva_v2.artefact_schema import (  # noqa: E402
    ArtefactPayload,
    CoverSlide,
    HeadlineSlide,
    KeyFinding,
    SourceCitation,
    TensionSlide,
    EvidenceBlock,
    TensionDeepDive,
    ScenarioRow,
    PerScenarioConfidenceTable,
    SensitivityInput,
    ReflectionSection,
    ReflectionQuestion,
    PathwayItem,
    DecisionBranch,
    RiskMitigation,
    MethodologicalHonesty,
    InClosing,
    BiasInventorySection,
    BiasItem,
    FooterTemplate,
)


def _minimal_citation(source_id: str = "audit-1") -> SourceCitation:
    return SourceCitation(
        source_input_id=source_id,
        source_kind="audit_log",
        excerpt="The user mentioned cohort retention dipped in Q3.",
        source_layer="grounding",
    )


def _minimal_payload() -> ArtefactPayload:
    """Construct a valid `ArtefactPayload` covering all 15 elements."""
    return ArtefactPayload(
        session_id="sess-test-1",
        cover=CoverSlide(
            title="Should we shut down the consumer channel?",
            prepared_for="Gobeba",
            subject="Develop Strategy",
            inputs_range="Layer 1 to Layer 5, 12 user inputs",
            date_str="2026-02-18",
        ),
        headline=HeadlineSlide(key_findings=[
            KeyFinding(number=1, paragraph_text="The cohort retention signal is strong.",
                       source_citations=[_minimal_citation()]),
            KeyFinding(number=2, paragraph_text="The pricing gap is consistent across two cohorts.",
                       source_citations=[_minimal_citation()]),
            KeyFinding(number=3, paragraph_text="The team's framing of the question is incomplete.",
                       source_citations=[_minimal_citation()]),
        ]),
        tensions=[
            TensionSlide(
                number="01", title="Channel framing vs unit economics",
                prevailing_framing="Consumer channel is the future.",
                evidence_block=EvidenceBlock(
                    user_quote="We can't keep losing on every transaction.",
                    source_layer_question_id="q-1",
                    source_layer="grounding",
                ),
                implication="The framing rests on growth optimism not borne out by the data.",
                severity="high",
                contradiction_source="user_vs_corpus",
            ),
        ],
        per_tension_deep_dive=[
            TensionDeepDive(
                tension_number="01",
                extended_detail_paragraphs=["Extended context for tension 01."],
                additional_citations=[_minimal_citation()],
            ),
        ],
        scenarios=[
            ScenarioRow(
                label="Channel restructures into B2B-only",
                description="Discontinue consumer; refocus margin into B2B.",
                weight_pct=40, confidence_pct=60,
                supporting_evidence=[_minimal_citation()],
                confidence_calibration_reasoning=(
                    "Confidence is moderate because only one evidence layer "
                    "(user_turn) supports this read so far."
                ),
                tier="comparable",
            ),
        ],
        per_scenario_confidence_table=PerScenarioConfidenceTable(rows=[]),
        sensitivity_inputs=[
            SensitivityInput(
                rank="HIGHEST",
                input_description="Whether next quarter's B2B pipeline materializes",
                impact_explanation="The B2B-only scenario weight depends on Q1 pipeline conversion.",
                cluster_weight_shift_mechanic="could move B2B-only from 40% to 60%",
                affected_cluster_id="cluster-channel",
            ),
        ],
        reflection_section=ReflectionSection(questions=[
            ReflectionQuestion(question_text="What could be wrong about this read?",
                               diagnostic_interpretation="The team's confidence in unit economics may be optimistic."),
            ReflectionQuestion(question_text="What would change in 30 days?",
                               diagnostic_interpretation="Q1 pipeline data will materially shift the weight."),
            ReflectionQuestion(question_text="First sign to watch?",
                               diagnostic_interpretation="Watch consumer CAC trend month-over-month."),
        ]),
        pathway=[
            PathwayItem(
                number=1, timeline_tag="DAYS 0-30",
                follows_from_cluster_id="cluster-channel",
                action_heading="If Q1 pipeline conversion falls below 15% → B2B refocus is supported.",
                detail_paragraph=(
                    "The evidence supports investigating whether the B2B pipeline "
                    "can carry the margin shortfall. If conversion holds above 15%, "
                    "the channel restructure becomes a stronger read."
                ),
            ),
        ],
        decision_logic=[
            DecisionBranch(
                condition="If Q1 pipeline conversion ≥ 15%",
                conclusion="The B2B-only restructure becomes the higher-weight scenario.",
                rationale="Conversion at that level closes the margin gap demonstrated in cohort data.",
            ),
        ],
        risk_mitigation=[
            RiskMitigation(
                risk="Cohort retention signal may be cohort-specific, not channel-wide.",
                mitigation="Pull cohort-stratified retention before committing to the read.",
            ),
        ],
        methodological_honesty=MethodologicalHonesty(
            what_report_is="This is a Solva diagnostic — Layer 0 frame audit through Layer 4 reflection — synthesizing your inputs and the comparable corpus.",
            what_report_is_not="This is not a decision. It is a structured weighting of scenarios for your judgement.",
            provisional_nature_paragraph="Every weight is provisional. Q1 data will shift the read materially.",
            input_confidence_pct=65,
            not_sole_basis_paragraph="This synthesis should not be the sole basis for any strategic commitment.",
        ),
        in_closing=InClosing(
            reframing_paragraph="The original question framed the choice as binary; the evidence supports a third path.",
            key_findings_recap=["Cohort retention strong", "Pricing gap consistent", "Framing incomplete"],
            final_statement="The pathway is conditional. Q1 data resolves the weighting.",
        ),
        bias_inventory=BiasInventorySection(
            biases=[
                BiasItem(
                    bias_name="confirmation_bias",
                    bias_display_name="Confirmation bias",
                    likelihood="medium",
                    evidence_grounded_reasoning=(
                        "The intake anchors strongly on the cohort retention story; "
                        "secondary signals from the pricing experiment got short "
                        "treatment in the framing."
                    ),
                    source_input_ids=["audit-1"],
                    suggested_mitigation=(
                        "Seeking evidence that would falsify the cohort retention "
                        "framing would test this assumption."
                    ),
                ),
            ],
        ),
        footer_template=FooterTemplate(),
    )


# ─────────────────────────────────────────────────────────────────
# A. Schema completeness
# ─────────────────────────────────────────────────────────────────


def test_minimal_payload_round_trips():
    """The minimum-viable payload must serialize + re-validate."""
    p = _minimal_payload()
    dumped = p.model_dump()
    restored = ArtefactPayload.model_validate(dumped)
    assert restored.session_id == p.session_id
    assert restored.schema_version == "solva.v2.artefact.1.0"


def test_all_15_elements_modelled():
    """Every element from the Slice 1 spec must be a populated field."""
    p = _minimal_payload()
    assert p.cover is not None                              # element 1
    assert p.headline is not None                           # element 2
    assert p.tensions and len(p.tensions) == 1              # element 3
    assert p.per_tension_deep_dive                          # element 4
    assert p.scenarios                                      # element 5
    assert p.per_scenario_confidence_table is not None      # element 6
    assert p.sensitivity_inputs                             # element 7
    assert p.reflection_section is not None                 # element 8
    assert p.pathway                                        # element 9
    assert p.decision_logic                                 # element 10
    assert p.risk_mitigation                                # element 11
    assert p.methodological_honesty is not None             # element 12
    assert p.in_closing is not None                         # element 13
    assert p.footer_template is not None                    # element 14
    # (element 15 = cover.method_tag, covered by element 1)


def test_cover_method_tag_default_value():
    p = _minimal_payload()
    assert p.cover.method_tag == "SOLVA · SESSION OUTPUT · CONFIDENTIAL"


def test_footer_template_default_value():
    p = _minimal_payload()
    assert "Solva Session Output" in p.footer_template.template
    assert "{context_name}" in p.footer_template.template
    assert "{n}" in p.footer_template.template
    assert "{total}" in p.footer_template.template


# ─────────────────────────────────────────────────────────────────
# B. Headline contract — exactly 3 numbered findings
# ─────────────────────────────────────────────────────────────────


def test_headline_must_have_exactly_three_findings():
    with pytest.raises(Exception):
        HeadlineSlide(key_findings=[
            KeyFinding(number=1, paragraph_text="only one", source_citations=[_minimal_citation()]),
        ])
    with pytest.raises(Exception):
        HeadlineSlide(key_findings=[
            KeyFinding(number=i, paragraph_text=f"f{i}", source_citations=[_minimal_citation()])
            for i in range(1, 5)
        ])


def test_key_finding_number_is_1_to_3():
    with pytest.raises(Exception):
        KeyFinding(number=0, paragraph_text="x", source_citations=[_minimal_citation()])
    with pytest.raises(Exception):
        KeyFinding(number=4, paragraph_text="x", source_citations=[_minimal_citation()])


# ─────────────────────────────────────────────────────────────────
# C. Tension contract — number pattern + contradiction source enum
# ─────────────────────────────────────────────────────────────────


def test_tension_number_must_be_two_digit_string():
    """Tension numbers display as '01', '02', '03' on the deck."""
    with pytest.raises(Exception):
        TensionSlide(
            number="1",   # wrong — needs '01'
            title="x", prevailing_framing="x",
            evidence_block=EvidenceBlock(user_quote="q", source_layer_question_id="q-1", source_layer="grounding"),
            implication="x", contradiction_source="user_vs_corpus",
        )


def test_tension_contradiction_source_enum():
    """Only the 4 specified sources are valid."""
    with pytest.raises(Exception):
        TensionSlide(
            number="01", title="x", prevailing_framing="x",
            evidence_block=EvidenceBlock(user_quote="q", source_layer_question_id="q-1", source_layer="grounding"),
            implication="x",
            contradiction_source="bogus_source",  # type: ignore[arg-type]
        )


# ─────────────────────────────────────────────────────────────────
# D. Scenarios — weight + confidence are independent fields
# ─────────────────────────────────────────────────────────────────


def test_scenario_weight_and_confidence_are_separate_fields():
    s = ScenarioRow(
        label="x", description="y",
        weight_pct=30, confidence_pct=80,
        supporting_evidence=[_minimal_citation(), _minimal_citation("audit-2")],
        confidence_calibration_reasoning="Two independent layers triangulate.",
    )
    assert s.weight_pct == 30
    assert s.confidence_pct == 80
    # Range gating
    with pytest.raises(Exception):
        ScenarioRow(label="x", weight_pct=101, confidence_pct=50,
                    supporting_evidence=[_minimal_citation()],
                    confidence_calibration_reasoning="x")


# ─────────────────────────────────────────────────────────────────
# E. Reflection contract — exactly 3 questions
# ─────────────────────────────────────────────────────────────────


def test_reflection_section_must_have_three_questions():
    with pytest.raises(Exception):
        ReflectionSection(questions=[
            ReflectionQuestion(question_text="q1", diagnostic_interpretation="i1"),
            ReflectionQuestion(question_text="q2", diagnostic_interpretation="i2"),
        ])


# ─────────────────────────────────────────────────────────────────
# F. Pathway — timeline_tag enum
# ─────────────────────────────────────────────────────────────────


def test_pathway_timeline_tag_enum_locked():
    with pytest.raises(Exception):
        PathwayItem(
            number=1, timeline_tag="WHENEVER",  # type: ignore[arg-type]
            action_heading="x", detail_paragraph="x",
        )


# ─────────────────────────────────────────────────────────────────
# G. Schema rejects extra fields (strict contract)
# ─────────────────────────────────────────────────────────────────


def test_root_payload_rejects_extra_fields():
    p = _minimal_payload()
    dumped = p.model_dump()
    dumped["bogus_extra_field"] = "x"
    with pytest.raises(Exception):
        ArtefactPayload.model_validate(dumped)
