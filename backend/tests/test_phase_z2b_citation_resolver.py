"""Sprint Z.2.B — Scope A: citation realness resolver + validator
integration tests.

Covers:
  • CitationResolver embedded resolution
  • Coarse-layer tag whitelist resolution
  • DB-resolved id pass-through
  • Unresolved → "unresolved" strategy
  • Validators emit `citation_unverifiable` failure reason carrying the
    un-resolvable citation id
  • collect_citation_refs walks every section that carries citations
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from services.solva_v2.citation_resolver import (  # noqa: E402
    CitationResolver,
    COARSE_LAYER_TAGS,
    EMBEDDED_FIELDS_BY_KIND,
    build_embedded_index,
    collect_citation_refs,
)
from services.solva_v2.artefact_schema import (  # noqa: E402
    ArtefactPayload, CoverSlide, HeadlineSlide, KeyFinding,
    SourceCitation, ScenarioRow, PerScenarioConfidenceTable,
    ReflectionSection, ReflectionQuestion,
    MethodologicalHonesty, InClosing,
    BiasInventorySection, BiasItem,
    PreMortemSlide, PreMortemFailureMode,
    CostAsymmetrySlide, CostAsymmetryScenario,
)
from services.solva_v2.integrity_validators import (  # noqa: E402
    citation_lint, confidence_calibration_audit, validate_artefact,
)


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────


def _make_session(
    *,
    audit_ids=("a1", "a2", "a3"),
    user_turn_ids=("u1",),
    doc_ids=(),
    comparable_ids=(),
):
    return {
        "id": "test-session",
        "reasoning_audit_log": [
            {"id": i, "engine": "probability_weighting" if k == 0 else "tension_detector",
             "layer": "synthesis" if k == 0 else "surface"}
            for k, i in enumerate(audit_ids)
        ],
        "user_turns": [{"id": i, "layer": "framing"} for i in user_turn_ids],
        "attached_docs": [{"id": i, "title": f"Doc {i}"} for i in doc_ids],
        "comparables": [{"id": i, "title": f"Comp {i}"} for i in comparable_ids],
    }


def _make_minimal_payload(scenarios: List[ScenarioRow]) -> ArtefactPayload:
    """Build a minimal-but-schema-valid ArtefactPayload from the given
    scenarios. Bias inventory + pre-mortem + cost-asymmetry are filled
    with the minimum-valid stub forms so the schema accepts the
    payload."""
    methodological = MethodologicalHonesty(
        what_report_is=("A reasoning trace, not a recommendation. It surfaces "
                        "the weighted reading of the available evidence."),
        what_report_is_not=("This report is not a directive. It does not "
                            "instruct the founder on what to decide."),
        provisional_nature_paragraph=("Every claim here is provisional. "
                                      "Confidence and weight are the engine's "
                                      "calibrated reads, not certainties."),
        not_sole_basis_paragraph=("This report is one input to the "
                                  "decision-making process. Hold it next to "
                                  "the founder's situated judgement."),
        input_confidence_pct=60,
    )
    cover = CoverSlide(
        title="Test cover", prepared_for="Test ctx", subject="seek clarity",
        inputs_range="Layer 0 to Layer 4", date_str="2026-02-01",
    )
    headline = HeadlineSlide(
        key_findings=[
            KeyFinding(number=i, paragraph_text=f"Finding {i}.", source_citations=[])
            for i in (1, 2, 3)
        ],
    )
    bias = BiasInventorySection(
        biases=[
            BiasItem(
                bias_name="confirmation_bias",
                bias_display_name="Confirmation bias",
                likelihood="low",
                evidence_grounded_reasoning=(
                    "The framing indicates a preference for evidence "
                    "that supports the leading hypothesis; thin signal here."
                ),
                source_input_ids=["framing"],  # coarse tag — accepted
            ),
        ],
    )
    pre_mortem = PreMortemSlide(
        failure_modes=[
            PreMortemFailureMode(
                failure_kind="execution_velocity",
                failure_narrative=(
                    "Investigating the leading indicator earlier would shift this risk; "
                    "the pathway slips if the velocity assumption proves brittle."
                ),
                triggering_signals=["Velocity drop ≥10% week-over-week."],
                counter_action="Monitoring the velocity signal weekly.",
                source_input_ids=["synthesis"],
            ),
        ],
    )
    cost_asym = CostAsymmetrySlide(
        scenarios=[
            CostAsymmetryScenario(
                pathway_label="A",
                if_correct_outcome=(
                    "The evidence supports the leading pathway and the upside is "
                    "captured at the calibrated probability the engine surfaces."
                ),
                if_wrong_cost=(
                    "If wrong, the cost reabsorbed remains modest at the corpus tier "
                    "and the optionality loss is small enough to recover within a quarter."
                ),
                cost_magnitude="medium",
                cost_kind="opportunity_cost",
                source_input_ids=["synthesis"],
            ),
            CostAsymmetryScenario(
                pathway_label="B",
                if_correct_outcome=(
                    "The alternative pathway captures a different upside profile "
                    "anchored to a deeper-tier signal that the engine cross-reads."
                ),
                if_wrong_cost=(
                    "If wrong, the cost reabsorbed sits materially higher at the depth "
                    "tier and the time cost extends across two reporting periods."
                ),
                cost_magnitude="medium",
                cost_kind="time_cost",
                source_input_ids=["depth"],
            ),
        ],
    )
    reflection = ReflectionSection(
        questions=[
            ReflectionQuestion(
                question_text="What could be wrong about the leading scenario?",
                user_verbatim_response="The weighting tier may be wrong.",
                diagnostic_interpretation="The user names a real tier risk; held for tracking.",
            ),
            ReflectionQuestion(
                question_text="What would change your read?",
                user_verbatim_response="A clean churn signal from the corpus tier.",
                diagnostic_interpretation="A corpus-tier signal would re-weight scenarios.",
            ),
            ReflectionQuestion(
                question_text="What is worth watching for?",
                user_verbatim_response="The regulatory window in November.",
                diagnostic_interpretation="The November regulatory date is captured as a watch item.",
            ),
        ],
    )
    return ArtefactPayload(
        schema_version="solva.v2.artefact.1.0",
        session_id="test-session",
        cover=cover,
        headline=headline,
        tensions=[],
        per_tension_deep_dive=[],
        scenarios=scenarios,
        per_scenario_confidence_table=PerScenarioConfidenceTable(rows=list(scenarios)),
        sensitivity_inputs=[],
        reflection_section=reflection,
        pathway=[],
        decision_logic=[],
        risk_mitigation=[],
        methodological_honesty=methodological,
        in_closing=InClosing(
            reframing_paragraph="The user's framing is preserved verbatim in this trace.",
            key_findings_recap=["Finding 1.", "Finding 2."],
            final_statement="This trace anchors the next session.",
        ),
        bias_inventory=bias,
        pre_mortem=pre_mortem,
        cost_asymmetry=cost_asym,
    )


# ─────────────────────────────────────────────────────────────────
# CitationResolver core
# ─────────────────────────────────────────────────────────────────


def test_resolver_embedded_audit_log():
    s = _make_session()
    r = CitationResolver(s)
    out = r.resolve("a1", "audit_log")
    assert out.resolved is True
    assert out.strategy == "embedded_audit_log"


def test_resolver_embedded_user_turn():
    s = _make_session(user_turn_ids=("u-real",))
    r = CitationResolver(s)
    out = r.resolve("u-real", "user_turn")
    assert out.resolved is True
    assert out.strategy == "embedded_user_turn"


def test_resolver_coarse_layer_tag_accepted_regardless_of_kind():
    s = _make_session()
    r = CitationResolver(s)
    for tag in ("L0", "L4", "synthesis", "framing", "reflection", "depth"):
        out = r.resolve(tag, "audit_log")
        assert out.resolved is True, f"coarse tag {tag!r} must resolve"
        assert out.strategy == "coarse_layer_tag"


def test_resolver_unknown_id_returns_unresolved():
    s = _make_session()
    r = CitationResolver(s)
    out = r.resolve("not-a-real-id-12345", "audit_log")
    assert out.resolved is False
    assert out.strategy == "unresolved"


def test_resolver_empty_id_returns_unresolved_empty():
    s = _make_session()
    r = CitationResolver(s)
    out = r.resolve("", "audit_log")
    assert out.resolved is False
    assert "empty" in out.strategy


def test_resolver_db_resolved_id_pass_through():
    s = _make_session()
    r = CitationResolver(s, db_resolved_ids={
        "attached_doc": {"doc-from-db-only"},
    })
    out = r.resolve("doc-from-db-only", "attached_doc")
    assert out.resolved is True
    assert out.strategy == "db_attached_doc"


def test_resolver_kindless_sweep_matches_any_embedded_kind():
    s = _make_session(audit_ids=("audit-X",), user_turn_ids=("turn-Y",))
    r = CitationResolver(s)
    a = r.resolve("audit-X")
    assert a.resolved is True
    assert a.strategy == "embedded_audit_log"
    b = r.resolve("turn-Y")
    assert b.resolved is True
    assert b.strategy == "embedded_user_turn"


def test_build_embedded_index_shape():
    s = _make_session(audit_ids=("a",), user_turn_ids=("u",), doc_ids=("d",), comparable_ids=("c",))
    idx = build_embedded_index(s)
    for k in EMBEDDED_FIELDS_BY_KIND:
        assert k in idx
    assert idx["audit_log"] == {"a"}
    assert idx["user_turn"] == {"u"}
    assert idx["attached_doc"] == {"d"}
    assert idx["comparable"] == {"c"}


# ─────────────────────────────────────────────────────────────────
# Validator emits citation_unverifiable
# ─────────────────────────────────────────────────────────────────


def test_confidence_calibration_audit_emits_citation_unverifiable_on_fabricated_id():
    """A scenario whose supporting_evidence references a fabricated id
    (not in embedded arrays, not a coarse tag, not pre-resolved) must
    trip a `citation_unverifiable` blocking offender."""
    s = _make_session()
    scenarios = [
        ScenarioRow(
            label="Fabricated-citation scenario",
            description="Triangulation looks healthy on surface.",
            weight_pct=75,
            confidence_pct=75,
            supporting_evidence=[
                SourceCitation(
                    source_input_id="a1",  # real
                    source_kind="audit_log",
                    excerpt="real",
                    source_layer="synthesis",
                ),
                SourceCitation(
                    source_input_id="FABRICATED-DOES-NOT-EXIST-99",
                    source_kind="user_turn",
                    excerpt="fabricated",
                    source_layer="framing",
                ),
            ],
            confidence_calibration_reasoning=(
                "Triangulation across audit_log + user_turn — but one of the "
                "two cites a fabricated id. The resolver must catch this."
            ),
            tier="corpus",
        ),
    ]
    payload = _make_minimal_payload(scenarios)
    offenders = confidence_calibration_audit(payload, s)
    messages = [o.message for o in offenders]
    assert any("citation_unverifiable" in m for m in messages), (
        f"Expected citation_unverifiable; got {messages!r}"
    )
    assert any("FABRICATED-DOES-NOT-EXIST-99" in m for m in messages), (
        f"Unresolved id must be surfaced in the failure payload; "
        f"got {messages!r}"
    )


def test_confidence_calibration_clean_when_all_citations_real_and_independent():
    s = _make_session(audit_ids=("a1",), user_turn_ids=("u1",))
    scenarios = [
        ScenarioRow(
            label="Clean scenario",
            description="Two real, independent citations.",
            weight_pct=80,
            confidence_pct=80,
            supporting_evidence=[
                SourceCitation(source_input_id="a1", source_kind="audit_log",
                               excerpt="audit-log entry one", source_layer="synthesis"),
                SourceCitation(source_input_id="u1", source_kind="user_turn",
                               excerpt="user turn one", source_layer="framing"),
            ],
            confidence_calibration_reasoning=(
                "Triangulation succeeds: audit_log + user_turn from "
                "different layers (synthesis + framing)."
            ),
            tier="corpus",
        ),
    ]
    payload = _make_minimal_payload(scenarios)
    offenders = confidence_calibration_audit(payload, s)
    assert not offenders, f"Clean scenario should produce 0 offenders; got {offenders!r}"


def test_citation_lint_emits_citation_unverifiable_on_unknown_id():
    """citation_lint must surface `citation_unverifiable` for any
    SourceCitation whose id doesn't resolve, even if the field passes
    the numerical-claim test."""
    s = _make_session()
    scenarios = [
        ScenarioRow(
            label="Scenario with 15% claim",
            description="The 27% delta indicates a strong signal.",
            weight_pct=50,
            confidence_pct=50,  # under threshold so confidence_calibration_audit doesn't fire
            supporting_evidence=[
                SourceCitation(source_input_id="GHOST-ID", source_kind="audit_log",
                               excerpt="ghost", source_layer="synthesis"),
            ],
            confidence_calibration_reasoning="Low confidence; no triangulation needed.",
            tier="corpus",
        ),
    ]
    payload = _make_minimal_payload(scenarios)
    offenders = citation_lint(payload, s)
    messages = [o.message for o in offenders]
    assert any("citation_unverifiable" in m and "GHOST-ID" in m for m in messages), (
        f"Expected citation_unverifiable with GHOST-ID in message; got {messages!r}"
    )


def test_validate_artefact_threads_db_resolved_ids_through():
    """End-to-end: providing `db_resolved_ids` to validate_artefact
    must enable resolution of a citation that's NOT in embedded
    arrays."""
    s = _make_session()
    scenarios = [
        ScenarioRow(
            label="Scenario citing DB-only attached_doc",
            description="Doc-only citation alongside audit-log.",
            weight_pct=75,
            confidence_pct=75,
            supporting_evidence=[
                SourceCitation(source_input_id="a1", source_kind="audit_log",
                               excerpt="emb", source_layer="synthesis"),
                SourceCitation(source_input_id="cross-session-doc-xyz",
                               source_kind="attached_doc",
                               excerpt="cross-session doc",
                               source_layer="depth"),
            ],
            confidence_calibration_reasoning=(
                "audit_log + attached_doc from synthesis + depth layers — "
                "independent triangulation."
            ),
            tier="corpus",
        ),
    ]
    payload = _make_minimal_payload(scenarios)
    # Without DB pre-resolved set → citation_unverifiable fires.
    result_a = validate_artefact(payload, s)
    cites_unverif_a = [o for o in result_a.blocking
                       if "citation_unverifiable" in o.message
                       and "cross-session-doc-xyz" in o.message]
    assert cites_unverif_a, (
        "Without DB pre-resolved set, cross-session-doc-xyz must be unverifiable"
    )
    # WITH DB pre-resolved set → no citation_unverifiable for that id.
    result_b = validate_artefact(payload, s, db_resolved_ids={
        "attached_doc": {"cross-session-doc-xyz"},
    })
    blocking_msgs = [o.message for o in result_b.blocking]
    assert not any("cross-session-doc-xyz" in m and "citation_unverifiable" in m
                   for m in blocking_msgs), (
        f"With DB pre-resolved set, citation_unverifiable on cross-session-doc-xyz "
        f"must NOT fire; got: {blocking_msgs}"
    )


def test_collect_citation_refs_walks_every_section():
    """The async router prefetcher relies on collect_citation_refs
    walking every payload section that carries SourceCitation lists."""
    scenarios = [
        ScenarioRow(
            label="x", description="x", weight_pct=50, confidence_pct=50,
            supporting_evidence=[
                SourceCitation(source_input_id="scen-doc",
                               source_kind="attached_doc",
                               excerpt="x", source_layer="depth"),
            ],
            confidence_calibration_reasoning="low confidence — no triangulation",
            tier="corpus",
        ),
    ]
    payload = _make_minimal_payload(scenarios)
    payload.headline.key_findings[0].source_citations.append(
        SourceCitation(source_input_id="head-doc", source_kind="attached_doc",
                       excerpt="x", source_layer="depth")
    )
    refs = collect_citation_refs(payload)
    assert "scen-doc" in refs.get("attached_doc", set())
    assert "head-doc" in refs.get("attached_doc", set())
