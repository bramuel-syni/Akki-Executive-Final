"""Solva v2 Slice 1b — Payload builder parity tests.

Five seeded audit-log fixtures cover the engine output shapes a real
Solva session produces. Each fixture exercises a different combination
of engine outputs so the lossless-mapping contract is exhaustively
verified.

For each fixture, the test asserts:
  • Every populated audit-log field that should surface in the payload
    DOES surface (no silent drops).
  • The composed payload passes ALL 4 integrity validators on first
    emission (the deterministic adapter is validator-passing by
    construction).
  • Stable payload signature — re-running the adapter against the same
    fixture produces an identical signature (determinism).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from services.solva_v2.payload_builder import build_payload, payload_signature  # noqa: E402
from services.solva_v2.integrity_validators import validate_artefact  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Fixture factory — builds 5 distinct seeded sessions
# ─────────────────────────────────────────────────────────────────


def _seeded_session(name: str) -> Dict[str, Any]:
    """Return one of 5 seeded session shapes."""
    base = {
        "id": f"sess-{name}",
        "account_id": "acct-test",
        "context_id": "ctx-test",
        "intent": "Should we shut down the consumer channel?",
        "submodule": "develop_strategy",
        "cluster_id": "cluster-channel",
        "cluster_label": "Channel Strategy",
        "started_at": "2026-02-18T09:00:00Z",
        "completed_at": "2026-02-18T10:24:00Z",
        "user_turns": [
            {"id": "turn-1", "layer": "framing", "text": "We're losing on every consumer transaction."},
            {"id": "turn-2", "layer": "grounding", "text": "But the B2B pipeline is uncertain."},
            {"id": "turn-3", "layer": "synthesis", "text": "Margin matters more than scale."},
        ],
        "attached_docs": [
            {"id": "doc-1", "name": "cohort_data.pdf"},
        ],
        "comparables": [
            {"id": "comp-1", "name": "Comparable A", "diagnosis_summary": "Pivoted to B2B with margin uplift."},
            {"id": "comp-2", "name": "Comparable B", "diagnosis_summary": "Hybrid model failed; consumer ate the margin."},
        ],
    }

    if name == "all_engines":
        # Full session — every engine has fired.
        base["reasoning_audit_log"] = [
            {"id": "audit-1", "engine": "triangulation", "output": {"cluster_id": "cluster-channel"}},
            {"id": "audit-2", "engine": "candidate_generation", "output": {"hypotheses": ["B2B refocus", "Hybrid"]}},
            {"id": "audit-3", "engine": "tension_detector", "output": {"tensions": [
                {"description": "Framing as binary vs evidence supporting third path.",
                 "contradiction_source": "user_vs_corpus", "severity": "high",
                 "evidence": ["We're losing on every consumer transaction.", "Cohort A retention strong."]},
                {"description": "Pricing gap consistent across two comparables.",
                 "contradiction_source": "comparable_vs_comparable", "severity": "medium",
                 "evidence": ["Comparable A pivoted to B2B."]},
            ]}},
            {"id": "audit-4", "engine": "probability_weighting", "output": {
                "claims": [
                    {"text": "Restructure into B2B-only with margin focus. The pivot would discontinue consumer.",
                     "tier": "corpus", "confidence_pct": 55, "confidence_band": "Likely",
                     "confidence_rationale": "Two comparables triangulate the read."},
                    {"text": "Hybrid model preserving both channels. Both margins narrow but each carries the other.",
                     "tier": "comparable", "confidence_pct": 30, "confidence_band": "Possible",
                     "confidence_rationale": "Comparable B's failure is a counter-signal."},
                    {"text": "Status quo: consumer-led growth continues. Volume eventually offsets margin pressure.",
                     "tier": "user_assertion", "confidence_pct": 15, "confidence_band": "Speculative",
                     "confidence_rationale": "Only user assertion supports this; no corpus signal."},
                ]
            }},
            {"id": "audit-5", "engine": "reflection", "output": {
                "reflection_question": "What could be wrong about this read?",
                "reflection_question_index": 0,
                "user_response": "We may be overweighting the cohort retention signal.",
                "interpretation": "The user identifies a calibration risk in the corpus signal.",
            }},
            {"id": "audit-6", "engine": "reflection", "output": {
                "reflection_question": "What would change in the next 30 days?",
                "reflection_question_index": 1,
                "user_response": "Q1 B2B pipeline conversion data lands mid-March.",
                "interpretation": "Pipeline data is the highest-rank sensitivity input.",
            }},
            {"id": "audit-7", "engine": "reflection", "output": {
                "reflection_question": "First sign to watch for?",
                "reflection_question_index": 2,
                "user_response": "Consumer CAC trend month-over-month.",
                "interpretation": "CAC trajectory will indicate channel-margin direction.",
            }},
        ]
        base["synthesis"] = {
            "body": "## Diagnosis\n\nThe weighted read supports a conditional channel restructure.",
            "recommendations": [
                {"heading": "Pressure-test B2B pipeline conversion in next 14 days",
                 "body": "You should investigate whether Q1 pipeline conversion exceeds 15%."},
                {"heading": "Pull cohort-stratified retention data",
                 "body": "Should pressure-test whether the retention signal is cohort-specific or channel-wide."},
            ],
        }
    elif name == "minimal_engines":
        # Only probability_weighting + minimal recommendations.
        base["reasoning_audit_log"] = [
            {"id": "audit-1", "engine": "probability_weighting", "output": {
                "claims": [
                    {"text": "Working hypothesis: channel restructure.", "tier": "comparable",
                     "confidence_pct": 50, "confidence_band": "Possible",
                     "confidence_rationale": "Single comparable supports this."},
                ]
            }},
        ]
        base["synthesis"] = {
            "body": "Brief diagnosis only.",
            "recommendations": [],
        }
    elif name == "no_tensions":
        # All engines fired except tension_detector.
        base["reasoning_audit_log"] = [
            {"id": "audit-1", "engine": "probability_weighting", "output": {
                "claims": [
                    {"text": "Scenario A.", "tier": "corpus", "confidence_pct": 60, "confidence_band": "Likely",
                     "confidence_rationale": "Corpus signal."},
                    {"text": "Scenario B.", "tier": "comparable", "confidence_pct": 35, "confidence_band": "Possible",
                     "confidence_rationale": "Comparable signal."},
                ]
            }},
        ]
        base["synthesis"] = {
            "body": "No tensions surfaced this session.",
            "recommendations": [],
        }
    elif name == "high_severity_tensions":
        # Multiple high-severity tensions exercise risk_mitigation derivation.
        base["reasoning_audit_log"] = [
            {"id": "audit-1", "engine": "tension_detector", "output": {"tensions": [
                {"description": "High-severity tension 1", "contradiction_source": "user_vs_corpus",
                 "severity": "high", "evidence": ["Quote 1", "Quote 2"]},
                {"description": "High-severity tension 2", "contradiction_source": "user_vs_user",
                 "severity": "high", "evidence": ["Quote 3"]},
            ]}},
            {"id": "audit-2", "engine": "probability_weighting", "output": {
                "claims": [
                    {"text": "Single scenario.", "tier": "comparable", "confidence_pct": 50, "confidence_band": "Possible",
                     "confidence_rationale": "Single comparable."},
                ]
            }},
        ]
        base["synthesis"] = {"body": "x", "recommendations": []}
    elif name == "imperative_recs":
        # Recommendations with imperative phrasing — verify the
        # adapter's _to_conditional() rewriter passes refuse_to_decide_enforcement.
        base["reasoning_audit_log"] = [
            {"id": "audit-1", "engine": "probability_weighting", "output": {
                "claims": [
                    {"text": "Restructure scenario.", "tier": "corpus", "confidence_pct": 50, "confidence_band": "Possible",
                     "confidence_rationale": "Corpus signal."},
                ]
            }},
        ]
        base["synthesis"] = {
            "body": "x",
            "recommendations": [
                {"heading": "Fire the consumer channel head",
                 "body": "You should kill the consumer channel and pivot to B2B."},
                {"heading": "Retain the founding team",
                 "body": "You must retain the founding pricing team during the pivot."},
            ],
        }
    return base


# ─────────────────────────────────────────────────────────────────
# A. Per-fixture parity assertions
# ─────────────────────────────────────────────────────────────────


_FIXTURE_NAMES = ("all_engines", "minimal_engines", "no_tensions",
                  "high_severity_tensions", "imperative_recs")


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_payload_builder_returns_valid_payload(fixture_name):
    session = _seeded_session(fixture_name)
    payload = build_payload(session, context_name="Gobeba")
    assert payload.session_id == f"sess-{fixture_name}"
    assert payload.schema_version == "solva.v2.artefact.1.0"
    # All 15 elements at least present (some may be empty lists).
    assert payload.cover is not None
    assert payload.headline is not None
    assert len(payload.headline.key_findings) == 3       # exactly-3 contract
    assert len(payload.reflection_section.questions) == 3
    assert payload.methodological_honesty is not None
    assert payload.in_closing is not None


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_payload_passes_integrity_validators(fixture_name):
    """Deterministic adapter must produce validator-passing output on
    FIRST emission for every fixture — no retry needed."""
    session = _seeded_session(fixture_name)
    payload = build_payload(session, context_name="Gobeba")
    result = validate_artefact(payload, session)
    assert result.ok, (
        f"Fixture {fixture_name!r} payload failed validators:\n"
        + result.revision_hint_bundle()
    )


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_payload_signature_is_deterministic(fixture_name):
    """Same session → same signature. Critical for drift detection."""
    session = _seeded_session(fixture_name)
    p1 = build_payload(session, context_name="Gobeba")
    p2 = build_payload(session, context_name="Gobeba")
    assert payload_signature(p1) == payload_signature(p2)


# ─────────────────────────────────────────────────────────────────
# B. Engine field → schema destination — no silent drops
# ─────────────────────────────────────────────────────────────────


def test_tension_severity_preserved():
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    assert payload.tensions
    # First tension was severity=high in the fixture.
    assert payload.tensions[0].severity == "high"
    # Risk mitigation gets exactly the high-severity tensions.
    assert len(payload.risk_mitigation) == 1  # only 1 high-severity tension


def test_tension_contradiction_source_preserved():
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    # Two tensions in fixture: user_vs_corpus + comparable_vs_comparable.
    sources = {t.contradiction_source for t in payload.tensions}
    assert "user_vs_corpus" in sources
    assert "comparable_vs_comparable" in sources


def test_tension_evidence_quotes_preserved():
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    # First tension had 2 evidence quotes — the first appears in
    # evidence_block, the second appears in per_tension_deep_dive.
    first_tension = payload.tensions[0]
    assert "consumer transaction" in first_tension.evidence_block.user_quote.lower()
    deep_dive = next((d for d in payload.per_tension_deep_dive
                      if d.tension_number == first_tension.number), None)
    assert deep_dive is not None, "Second evidence quote must surface in deep dive"
    assert "cohort a retention" in " ".join(deep_dive.extended_detail_paragraphs).lower()


def test_reflection_locked_questions_preserved_verbatim():
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    qs = payload.reflection_section.questions
    assert qs[0].question_text.startswith("What could be wrong")
    assert qs[1].question_text.startswith("What would change")
    assert qs[2].question_text.startswith("First sign")
    # Verbatim user responses preserved.
    assert "overweighting the cohort retention signal" in qs[0].user_verbatim_response
    assert "Q1 B2B pipeline conversion data" in qs[1].user_verbatim_response
    assert "Consumer CAC trend" in qs[2].user_verbatim_response


def test_claim_tier_surfaces_in_scenario_calibration():
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    scenarios = payload.scenarios
    assert scenarios
    # Each scenario's calibration reasoning mentions the tier OR the
    # confidence rationale that originally carried the tier.
    tiers_seen = {s.tier for s in scenarios}
    assert "corpus" in tiers_seen
    assert "comparable" in tiers_seen
    assert "user_assertion" in tiers_seen


def test_cluster_id_surfaces_in_pathway():
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    assert payload.pathway
    for p in payload.pathway:
        assert p.follows_from_cluster_id == "cluster-channel"
        assert p.follows_from_cluster_label == "Channel Strategy"


def test_recommendations_imperative_phrasing_rewritten():
    """The `imperative_recs` fixture has pathway items with 'fire',
    'kill', 'must', 'you should'. The _to_conditional() rewrite must
    pass refuse_to_decide_enforcement on first emission."""
    session = _seeded_session("imperative_recs")
    payload = build_payload(session, context_name="Gobeba")
    result = validate_artefact(payload, session)
    assert result.ok, (
        "Imperative phrasing rewrite failed:\n" + result.revision_hint_bundle()
    )
    # Sanity check — the rewritten output should no longer contain
    # imperative trigger phrases.
    joined = " ".join(p.detail_paragraph for p in payload.pathway).lower()
    assert "you should" not in joined
    assert "you must" not in joined


def test_input_confidence_pct_is_weighted_aggregate():
    """methodological_honesty.input_confidence_pct = sum(conf * weight) /
    sum(weight). Verify with the all_engines fixture (3 claims)."""
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    # Claims: 55+30+15 (conf=weight in deterministic baseline)
    # weighted_avg = (55*55 + 30*30 + 15*15) / (55+30+15) = 4150/100 = 41.5
    # Rounded: 42
    assert 40 <= payload.methodological_honesty.input_confidence_pct <= 45


def test_refused_count_surfaces_in_methodological_honesty():
    """When refusal engine fires, the count must be named in the
    what_report_is_not paragraph."""
    session = _seeded_session("all_engines")
    # Inject a refusal audit entry.
    session["reasoning_audit_log"].append({
        "id": "audit-refused-1", "engine": "refusal",
        "output": {"refused": True, "reason": "out_of_scope"},
    })
    payload = build_payload(session, context_name="Gobeba")
    assert "1 candidate framing" in payload.methodological_honesty.what_report_is_not


def test_audit_log_entry_count_in_inputs_range():
    """cover.inputs_range surfaces both user_turns count + audit entries."""
    session = _seeded_session("all_engines")
    payload = build_payload(session, context_name="Gobeba")
    assert "3 user inputs" in payload.cover.inputs_range
    assert "7 engine entries" in payload.cover.inputs_range


# ─────────────────────────────────────────────────────────────────
# C. Adapter handles partial sessions without crashing
# ─────────────────────────────────────────────────────────────────


def test_no_engine_outputs_still_produces_valid_shape():
    """Edge case — session with only intent/submodule, no engines fired."""
    session = {
        "id": "sess-empty",
        "intent": "What should we do?",
        "submodule": "seek_clarity",
        "started_at": "2026-02-18T09:00:00Z",
        "user_turns": [],
        "reasoning_audit_log": [],
    }
    payload = build_payload(session, context_name="Empty Co")
    # Schema shape contract holds even with empty engine outputs.
    assert payload.session_id == "sess-empty"
    assert len(payload.headline.key_findings) == 3  # padded to exactly 3
    assert len(payload.reflection_section.questions) == 3
