"""Solva v2 Slice 1 — Integrity validator tests.

Each of the 4 validators is exercised in both pass and fail modes,
plus the composite `validate_artefact()` runner.
"""
from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from services.solva_v2.artefact_schema import (  # noqa: E402
    ArtefactPayload, CoverSlide, HeadlineSlide, KeyFinding,
    SourceCitation, TensionSlide, EvidenceBlock, ScenarioRow,
    PerScenarioConfidenceTable, SensitivityInput, ReflectionSection,
    ReflectionQuestion, PathwayItem, DecisionBranch, RiskMitigation,
    MethodologicalHonesty, InClosing, FooterTemplate,
)
from services.solva_v2.integrity_validators import (  # noqa: E402
    citation_lint, confidence_calibration_audit,
    refuse_to_decide_enforcement, methodological_honesty_present,
    validate_artefact, ValidationResult,
)


_SESSION_STUB = {
    "id": "sess-1",
    "reasoning_audit_log": [
        {"id": "audit-1", "engine": "grounding", "input": "x", "output": "y"},
        {"id": "audit-2", "engine": "triangulation", "input": "x", "output": "y"},
    ],
    "user_turns": [
        {"id": "q-1", "layer": "framing", "text": "Should we shut down consumer?"},
    ],
    "attached_docs": [{"id": "doc-1", "name": "cohort_data.pdf"}],
    "comparables": [{"id": "comp-1", "name": "Comparable Co"}],
}


def _citation(source_id: str = "audit-1", kind: str = "audit_log", layer: str = "grounding") -> SourceCitation:
    return SourceCitation(
        source_input_id=source_id, source_kind=kind, excerpt="excerpt", source_layer=layer,
    )


def _baseline_payload(**overrides) -> ArtefactPayload:
    """Build a clean baseline that PASSES all 4 validators. Tests
    introduce a single defect via overrides + assert the right
    validator catches it."""
    payload = ArtefactPayload(
        session_id="sess-1",
        cover=CoverSlide(
            title="Should we shut down the consumer channel?",
            prepared_for="Gobeba", subject="Develop Strategy",
            inputs_range="L1-L5, 12 inputs", date_str="2026-02-18",
        ),
        headline=HeadlineSlide(key_findings=[
            KeyFinding(number=1, paragraph_text="The cohort signal is strong.",
                       source_citations=[_citation()]),
            KeyFinding(number=2, paragraph_text="The pricing gap is consistent.",
                       source_citations=[_citation()]),
            KeyFinding(number=3, paragraph_text="Framing is incomplete.",
                       source_citations=[_citation()]),
        ]),
        tensions=[
            TensionSlide(
                number="01", title="Channel framing", prevailing_framing="Consumer is the future.",
                evidence_block=EvidenceBlock(user_quote="q", source_layer_question_id="q-1", source_layer="framing"),
                implication="The framing rests on optimism not borne out.",
                severity="high", contradiction_source="user_vs_corpus",
            ),
        ],
        scenarios=[
            ScenarioRow(
                label="Restructure to B2B-only", description="Discontinue consumer focus.",
                weight_pct=40, confidence_pct=55,
                supporting_evidence=[_citation()],
                confidence_calibration_reasoning="Single-source signal; confidence moderate.",
                tier="comparable",
            ),
        ],
        sensitivity_inputs=[
            SensitivityInput(
                rank="HIGHEST",
                input_description="Q1 pipeline conversion",
                impact_explanation="Pipeline outcome shifts the B2B weighting.",
                cluster_weight_shift_mechanic="could move cluster from forty to sixty",
                affected_cluster_id="cluster-channel",
            ),
        ],
        reflection_section=ReflectionSection(questions=[
            ReflectionQuestion(question_text="What could be wrong?", diagnostic_interpretation="Optimistic on unit economics."),
            ReflectionQuestion(question_text="What would change in 30 days?", diagnostic_interpretation="Q1 data shifts read."),
            ReflectionQuestion(question_text="First sign to watch?", diagnostic_interpretation="CAC trend."),
        ]),
        pathway=[
            PathwayItem(
                number=1, timeline_tag="DAYS 0-30", follows_from_cluster_id="cluster-channel",
                action_heading="If pipeline conversion holds → restructure is supported",
                detail_paragraph=(
                    "The evidence supports investigating the B2B pipeline carry. "
                    "If conversion holds above the threshold, the read strengthens."
                ),
            ),
        ],
        decision_logic=[
            DecisionBranch(
                condition="If conversion ≥ threshold",
                conclusion="Restructure becomes the higher-weight scenario.",
                rationale="Conversion at that level closes the margin gap.",
            ),
        ],
        risk_mitigation=[
            RiskMitigation(risk="Signal may be cohort-specific.", mitigation="Pull cohort-stratified retention."),
        ],
        methodological_honesty=MethodologicalHonesty(
            what_report_is="A Solva diagnostic — Layer 0 frame audit through Layer 4 reflection — synthesizing your inputs with the comparable corpus.",
            what_report_is_not="Not a decision; a structured weighting of scenarios for your judgement.",
            provisional_nature_paragraph="Every weight is provisional. Q1 data will shift the read materially.",
            input_confidence_pct=65,
            not_sole_basis_paragraph="This synthesis should not be the sole basis for any strategic commitment.",
        ),
        in_closing=InClosing(
            reframing_paragraph="The original question framed the choice as binary; the evidence supports a third path.",
            key_findings_recap=["Cohort retention strong"],
            final_statement="The pathway is conditional. Q1 data resolves the weighting.",
        ),
        footer_template=FooterTemplate(),
        per_scenario_confidence_table=PerScenarioConfidenceTable(),
    )
    # Apply overrides via .model_copy(update=...)
    if overrides:
        return payload.model_copy(update=overrides)
    return payload


# ─────────────────────────────────────────────────────────────────
# Validator 1 — citation_lint
# ─────────────────────────────────────────────────────────────────


def test_citation_lint_passes_on_baseline():
    offenders = citation_lint(_baseline_payload(), _SESSION_STUB)
    assert offenders == []


def test_citation_lint_flags_numerical_claim_without_citation():
    payload = _baseline_payload(headline=HeadlineSlide(key_findings=[
        KeyFinding(number=1, paragraph_text="Retention dropped 27% in Q3.",
                   source_citations=[]),
        KeyFinding(number=2, paragraph_text="x", source_citations=[_citation()]),
        KeyFinding(number=3, paragraph_text="x", source_citations=[_citation()]),
    ]))
    offenders = citation_lint(payload, _SESSION_STUB)
    assert offenders
    assert any("headline.key_findings[0]" in o.location for o in offenders)
    assert any("27%" in o.message for o in offenders)


def test_citation_lint_flags_unknown_source_id():
    payload = _baseline_payload(headline=HeadlineSlide(key_findings=[
        KeyFinding(number=1, paragraph_text="Retention dropped 27% in Q3.",
                   source_citations=[_citation("ghost-id-not-in-log")]),
        KeyFinding(number=2, paragraph_text="x", source_citations=[_citation()]),
        KeyFinding(number=3, paragraph_text="x", source_citations=[_citation()]),
    ]))
    offenders = citation_lint(payload, _SESSION_STUB)
    assert any("unknown source ids" in o.message for o in offenders)


# ─────────────────────────────────────────────────────────────────
# Validator 2 — confidence_calibration_audit
# ─────────────────────────────────────────────────────────────────


def test_calibration_passes_on_low_confidence_single_source():
    """confidence_pct=55 (< 70) → single source acceptable."""
    payload = _baseline_payload()
    assert payload.scenarios[0].confidence_pct == 55
    offenders = confidence_calibration_audit(payload, _SESSION_STUB)
    assert offenders == []


def test_calibration_flags_high_confidence_single_source():
    payload = _baseline_payload()
    payload.scenarios[0].confidence_pct = 80  # crank above threshold
    offenders = confidence_calibration_audit(payload, _SESSION_STUB)
    assert offenders
    assert any("only 1 supporting_evidence" in o.message for o in offenders)


def test_calibration_passes_on_high_confidence_with_two_independent_sources():
    payload = _baseline_payload()
    payload.scenarios[0].confidence_pct = 80
    payload.scenarios[0].supporting_evidence = [
        _citation("audit-1", kind="audit_log", layer="grounding"),
        _citation("comp-1", kind="comparable", layer="grounding"),
    ]
    payload.scenarios[0].confidence_calibration_reasoning = (
        "Confidence high because the audit-log signal at grounding and the "
        "comparable corpus entry both surface the same trend independently."
    )
    offenders = confidence_calibration_audit(payload, _SESSION_STUB)
    assert offenders == []


def test_calibration_flags_two_sources_same_kind_and_layer():
    """Two citations from the same source_kind + layer is NOT independent."""
    payload = _baseline_payload()
    payload.scenarios[0].confidence_pct = 75
    payload.scenarios[0].supporting_evidence = [
        _citation("audit-1", kind="audit_log", layer="grounding"),
        _citation("audit-2", kind="audit_log", layer="grounding"),
    ]
    offenders = confidence_calibration_audit(payload, _SESSION_STUB)
    assert any("not independent" in o.message for o in offenders)


# ─────────────────────────────────────────────────────────────────
# Validator 3 — refuse_to_decide_enforcement
# ─────────────────────────────────────────────────────────────────


def test_refuse_to_decide_passes_on_conditional_phrasing():
    offenders = refuse_to_decide_enforcement(_baseline_payload(), _SESSION_STUB)
    assert offenders == []


def test_refuse_to_decide_flags_imperative_phrasing():
    payload = _baseline_payload()
    payload.pathway[0].detail_paragraph = (
        "You should fire the consumer channel head and pivot the entire org."
    )
    offenders = refuse_to_decide_enforcement(payload, _SESSION_STUB)
    assert offenders
    assert any("Imperative phrasing" in o.message for o in offenders)


def test_refuse_to_decide_flags_must_kill_phrasing():
    payload = _baseline_payload()
    payload.pathway[0].action_heading = "Kill the consumer channel immediately"
    offenders = refuse_to_decide_enforcement(payload, _SESSION_STUB)
    assert offenders


def test_refuse_to_decide_allows_observational_phrasing():
    payload = _baseline_payload()
    payload.pathway[0].detail_paragraph = (
        "The evidence supports investigating whether the channel restructure "
        "follows from the pricing-gap signal observed in the corpus."
    )
    offenders = refuse_to_decide_enforcement(payload, _SESSION_STUB)
    assert offenders == []


# ─────────────────────────────────────────────────────────────────
# Validator 4 — methodological_honesty_present
# ─────────────────────────────────────────────────────────────────


def test_methodological_honesty_passes_on_baseline():
    offenders = methodological_honesty_present(_baseline_payload(), _SESSION_STUB)
    assert offenders == []


def test_methodological_honesty_flags_short_paragraphs():
    payload = _baseline_payload()
    payload.methodological_honesty.what_report_is = "Diagnostic."  # < 40 chars
    offenders = methodological_honesty_present(payload, _SESSION_STUB)
    assert offenders
    assert any("what_report_is" in o.location for o in offenders)


# ─────────────────────────────────────────────────────────────────
# Composite runner
# ─────────────────────────────────────────────────────────────────


def test_composite_validate_artefact_ok_on_baseline():
    result: ValidationResult = validate_artefact(_baseline_payload(), _SESSION_STUB)
    assert result.ok
    assert result.offenders == []


def test_composite_validate_artefact_blocks_on_imperative():
    payload = _baseline_payload()
    payload.pathway[0].detail_paragraph = "You must fire the consumer team."
    result = validate_artefact(payload, _SESSION_STUB)
    assert not result.ok
    assert len(result.blocking) >= 1


def test_revision_hint_bundle_includes_hints_for_each_offender():
    payload = _baseline_payload()
    payload.pathway[0].detail_paragraph = "You should kill the channel."
    payload.scenarios[0].confidence_pct = 90  # high w/ single src → calibration fail
    result = validate_artefact(payload, _SESSION_STUB)
    assert not result.ok
    bundle = result.revision_hint_bundle()
    assert "refuse_to_decide_enforcement" in bundle
    assert "confidence_calibration_audit" in bundle
