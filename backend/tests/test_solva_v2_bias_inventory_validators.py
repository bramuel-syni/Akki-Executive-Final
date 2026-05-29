"""Solva v2 — Slice 4 (2026-05-29) Bias Inventory integrity validators.

Locks the 3 new validators added in Slice 4:
  • bias_inventory_present     → block if biases list is empty / missing
  • bias_inventory_citation_lint → block if any source_input_id doesn't
                                   resolve to a real audit-log id, user
                                   turn id, or coarse layer tag
  • bias_evidence_observational  → block on imperative phrasing in
                                   evidence_grounded_reasoning OR
                                   suggested_mitigation
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
    CostAsymmetrySlide, CostAsymmetryScenario,
)
from services.solva_v2.integrity_validators import (  # noqa: E402
    bias_inventory_present, bias_inventory_citation_lint,
    bias_evidence_observational,
)


# Minimal fixture shared across tests
def _payload(biases):
    return ArtefactPayload(
        session_id="test-sid",
        schema_version="solva.v2.artefact.1.0",
        cover=CoverSlide(
            title="X", prepared_for="Y", subject="Z",
            inputs_range="Layer 0 to Layer 4, 5 inputs",
            date_str="2026-05-29",
        ),
        headline=HeadlineSlide(
            intro_copy="Intro intro intro intro intro intro intro intro intro.",
            key_findings=[
                KeyFinding(number=1, paragraph_text="Finding one paragraph here is long enough.",
                           source_citations=[SourceCitation(source_kind="user_turn", source_input_id="audit-1", excerpt="Quote.")]),
                KeyFinding(number=2, paragraph_text="Finding two paragraph here is long enough.",
                           source_citations=[SourceCitation(source_kind="user_turn", source_input_id="audit-1", excerpt="Quote.")]),
                KeyFinding(number=3, paragraph_text="Finding three paragraph here is long enough.",
                           source_citations=[SourceCitation(source_kind="user_turn", source_input_id="audit-1", excerpt="Quote.")]),
            ],
        ),
        scenarios=[
            ScenarioRow(
                label="Scenario A",
                description="Description.",
                weight_pct=40, confidence_pct=50,
                tier="domain_prior",
                confidence_calibration_reasoning="The reasoning is grounded in the corpus.",
            ),
        ],
        sensitivity_inputs=[],
        reflection_section=ReflectionSection(
            title="Reflection", intro_copy="Intro.",
            questions=[
                ReflectionQuestion(question_text="Q1?", diagnostic_interpretation="Interp."),
                ReflectionQuestion(question_text="Q2?", diagnostic_interpretation="Interp."),
                ReflectionQuestion(question_text="Q3?", diagnostic_interpretation="Interp."),
            ],
        ),
        pathway=[],
        decision_logic=[],
        risk_mitigation=[],
        methodological_honesty=MethodologicalHonesty(
            what_report_is="Report intro that is at least the locked-min length to pass.",
            what_report_is_not="Report-not intro that is at least the locked-min length to pass.",
            provisional_nature_paragraph="Provisional paragraph at length.",
            input_confidence_pct=50,
            not_sole_basis_paragraph="Not sole basis paragraph at length.",
        ),
        in_closing=InClosing(
            reframing_paragraph="Reframing paragraph that is long.",
            key_findings_recap=["A"],
            final_statement="Final statement of length.",
        ),
        bias_inventory=BiasInventorySection(biases=biases),
        pre_mortem=PreMortemSlide(
            failure_modes=[
                PreMortemFailureMode(
                    failure_kind="data_signal_misread",
                    failure_narrative=(
                        "The pathway anchors on a single dominant read; if "
                        "the underlying signal is cohort-specific, the "
                        "recommended pathway commits to a misread that "
                        "surfaces only after the timeline closes."
                    ),
                    triggering_signals=["Signal reverts at next intake"],
                    source_input_ids=["audit-1"],
                ),
            ],
        ),
        cost_asymmetry=CostAsymmetrySlide(
            scenarios=[
                CostAsymmetryScenario(
                    pathway_label="Pathway 1",
                    if_correct_outcome=(
                        "If the leading pathway resolves favourably, the "
                        "operating read converges; sensitivity inputs hold."
                    ),
                    if_wrong_cost=(
                        "If the leading pathway turns out misaligned, "
                        "committed capital lands on a misread; recovery "
                        "absorbs the next cycle."
                    ),
                    cost_kind="capital_burn",
                    cost_magnitude="medium",
                    source_input_ids=["audit-1"],
                ),
                CostAsymmetryScenario(
                    pathway_label="Pathway 2",
                    if_correct_outcome=(
                        "If the alternative pathway resolves favourably, "
                        "the founder preserves optionality across the next "
                        "cycle with lower committed capital."
                    ),
                    if_wrong_cost=(
                        "If the alternative pathway turns out wrong, the "
                        "diagnostic is exposed as too tightly calibrated; "
                        "stakeholder trust absorbs the recovery cost."
                    ),
                    cost_kind="opportunity_cost",
                    cost_magnitude="low",
                    source_input_ids=["audit-1"],
                ),
            ],
        ),
        per_scenario_confidence_table=PerScenarioConfidenceTable(),
    )


def _audit_session():
    return {
        "reasoning_audit_log": [
            {"id": "audit-1", "layer": "framing"},
            {"id": "audit-2", "layer": "synthesis"},
        ],
        "user_turns": [{"id": "turn-1"}],
    }


# ─────────────────────────────────────────────────────────────────
# bias_inventory_present
# ─────────────────────────────────────────────────────────────────


def test_present_passes_when_biases_carry_one_entry():
    p = _payload([_minimal_bias()])
    offs = bias_inventory_present(p, _audit_session())
    assert offs == []


def _minimal_bias(**overrides):
    base = dict(
        bias_name="confirmation_bias",
        bias_display_name="Confirmation bias",
        likelihood="low",
        evidence_grounded_reasoning=(
            "The framing anchors on the prevailing read; secondary signals "
            "got short treatment in the intake."
        ),
        source_input_ids=["audit-1"],
    )
    base.update(overrides)
    return BiasItem(**base)


# ─────────────────────────────────────────────────────────────────
# bias_inventory_citation_lint
# ─────────────────────────────────────────────────────────────────


def test_citation_lint_passes_with_resolvable_audit_id():
    p = _payload([_minimal_bias(source_input_ids=["audit-1"])])
    offs = bias_inventory_citation_lint(p, _audit_session())
    assert offs == []


def test_citation_lint_passes_with_coarse_layer_tag():
    """Coarse layer tags (L0..L4 + canonical names + legacy names) are
    accepted — engines can cite 'the Layer 3 synthesis output' rather
    than a specific audit entry id."""
    for tag in ("L0", "L3", "frame_audit", "synthesis", "framing"):
        p = _payload([_minimal_bias(source_input_ids=[tag])])
        offs = bias_inventory_citation_lint(p, _audit_session())
        assert offs == [], f"tag={tag!r} should resolve"


def test_citation_lint_blocks_unresolved_id():
    p = _payload([_minimal_bias(source_input_ids=["does-not-exist"])])
    offs = bias_inventory_citation_lint(p, _audit_session())
    assert any(o.severity == "block" for o in offs)
    assert any("does-not-exist" in o.message for o in offs)


# ─────────────────────────────────────────────────────────────────
# bias_evidence_observational
# ─────────────────────────────────────────────────────────────────


def test_observational_passes_on_observational_reasoning():
    """The default reasoning ('The framing anchors on the prevailing
    read; secondary signals got short treatment in the intake.')
    starts with 'the framing' which is in the observational opener
    allowlist."""
    p = _payload([_minimal_bias()])
    offs = bias_evidence_observational(p, _audit_session())
    assert offs == []


def test_observational_blocks_imperative_reasoning():
    """If evidence_grounded_reasoning starts with 'You should focus...'
    or contains imperative phrasing, the validator blocks."""
    p = _payload([_minimal_bias(
        evidence_grounded_reasoning=(
            "You should look at the cohort retention more carefully — "
            "you must reconsider the framing."
        ),
    )])
    offs = bias_evidence_observational(p, _audit_session())
    assert any(o.severity == "block" for o in offs)


def test_observational_blocks_imperative_mitigation():
    p = _payload([_minimal_bias(
        suggested_mitigation="You should examine the secondary signals.",
    )])
    offs = bias_evidence_observational(p, _audit_session())
    assert any(o.severity == "block" for o in offs)
    assert any("suggested_mitigation" in o.location for o in offs)


def test_observational_passes_on_observational_mitigation():
    """Mitigation starting with 'Seeking', 'Testing', 'Consulting',
    'Inviting', 'Asking', 'Examining' passes."""
    for opener in ("Seeking", "Testing", "Consulting", "Inviting", "Asking", "Examining"):
        p = _payload([_minimal_bias(
            suggested_mitigation=f"{opener} additional grounding sources would calibrate the read.",
        )])
        offs = bias_evidence_observational(p, _audit_session())
        assert offs == [], f"opener={opener!r} should pass"
