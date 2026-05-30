"""Sprint Z.2.C — refuse_to_decide_enforcement production hardening tests.

User-mandated test cases: ≥6 production-realistic phrasings, ≥3 must
fire (true imperatives), ≥3 must NOT fire (observational text where
trigger verbs appear as nouns, in negated frames, hyphenated compounds,
or counterfactual `should have <pp>` constructions).

Scope:
  • Verbs-as-nouns (`partial pivot`, `exit horizon`, `sell pressure`)
  • Negated frames (`do not underwrite`, `did not decide`)
  • Hyphenated compounds (`cross-sell`, `buy-back`, `sell-off`)
  • Counterfactual `should have <past_participle>` constructions
  • Infinitive-in-subordinate-clause with negated main verb
  • True imperatives ("you need to ship", "fire the CFO", "raise prices")
  • Imperative bare-verb commands ("Pivot toward services", "Sell the
    asset before Q3.")
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from services.solva_v2.integrity_validators import (  # noqa: E402
    _IMPERATIVE_PATTERNS,
    _CONDITIONAL_OPENERS,
    _trigger_is_observational,
)


def _scan(text: str):
    """Mirror the validator's inner loop — return the first
    (matched_pattern, was_observational) tuple if a pattern fires, or
    None if the text is clean. Used to unit-test the hardening
    classifier in isolation."""
    normalised = text.lower().strip()
    if any(normalised.startswith(o) for o in _CONDITIONAL_OPENERS):
        return None
    for pat in _IMPERATIVE_PATTERNS:
        m = re.search(pat, normalised)
        if m:
            return (m.group(0), _trigger_is_observational(text, m))
    return None


# ─────────────────────────────────────────────────────────────────
# Must FIRE — true imperatives (Solva telling the user what to do)
# ─────────────────────────────────────────────────────────────────


def test_imperative_you_need_to_fires():
    """Direct user-addressing imperative."""
    text = (
        "The December regulator meeting creates a hard forcing function: "
        "you need to show either immediate capital action or a binding "
        "remediation plan."
    )
    result = _scan(text)
    assert result is not None
    matched, observational = result
    assert "you need to" in matched
    assert observational is False, (
        f"True imperative must fire (not observational); matched={matched!r}"
    )


def test_imperative_you_should_fires():
    """Direct user-addressing should."""
    text = "You should sell the underperforming segment before the Q3 close."
    result = _scan(text)
    assert result is not None
    matched, observational = result
    assert observational is False


def test_imperative_bare_verb_fires():
    """Bare-verb command — `Fire the CFO` after a conditional has
    passed → should fire. We deliberately use a sentence where the
    bare verb cannot be a noun (`Fire the CFO before Q3 close.`)."""
    text = "Fire the CFO before the Q3 board pack lands."
    result = _scan(text)
    assert result is not None
    matched, observational = result
    assert matched.lower() == "fire"
    assert observational is False


def test_imperative_raise_prices_fires():
    """Direct command — `Raise prices`."""
    text = "Raise prices by 15% in the next quarter."
    result = _scan(text)
    assert result is not None
    matched, observational = result
    assert observational is False, (
        f"Bare-imperative raise must fire; matched={matched!r}"
    )


def test_imperative_must_fires_on_user_subject():
    """`The board must approve` is a directive, not observational."""
    text = "The board must approve the resolution before the AGM."
    result = _scan(text)
    assert result is not None
    matched, observational = result
    # `must approve` matches the `\bmust\s+\w+` pattern.
    assert observational is False


# ─────────────────────────────────────────────────────────────────
# Must NOT FIRE — observational / nominal / counterfactual / negated
# ─────────────────────────────────────────────────────────────────


def test_observational_partial_pivot_does_not_fire():
    """`partial pivot` — `pivot` is a NOUN (modifier-noun)."""
    text = "Scenario B — partial pivot toward services revenue, capped at 15% of group capex."
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True, (
            f"`partial pivot` should classify as noun-form; got matched={matched!r}, obs={observational}"
        )


def test_observational_that_pivot_subject_does_not_fire():
    """`That pivot matters because...` — `pivot` is a NOUN subject."""
    text = (
        "That pivot matters, because accelerating capex usually signals "
        "growth or capacity constraint, while a buyback typically reads "
        "as defensive."
    )
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True


def test_observational_cross_sell_hyphenated_does_not_fire():
    """`cross-sell` — hyphenated compound noun."""
    text = (
        "The bolt-on deal's cross-sell math collapsed when someone "
        "finally asked about post-renewal churn."
    )
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True, (
            f"`cross-sell` must classify as hyphenated compound; matched={matched!r}"
        )


def test_observational_typical_do_not_underwrite_does_not_fire():
    """`institutional shareholders typically do not underwrite` —
    negation with non-user subject."""
    text = (
        "The tension arises because institutional shareholders typically "
        "do not underwrite execution risk when a credible alternative exists."
    )
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True, (
            f"`typically do not <verb>` with non-user subject must be observational; "
            f"matched={matched!r}"
        )


def test_observational_should_have_counterfactual_does_not_fire():
    """`should have triggered` — counterfactual past participle."""
    text = (
        "The audit findings should have triggered a pause; instead, "
        "they were filed without a board-pack escalation."
    )
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True, (
            f"`should have <past_participle>` is counterfactual; matched={matched!r}"
        )


def test_observational_exit_horizon_noun_modifier_does_not_fire():
    """`exit horizon` — `exit` as attributive noun modifying `horizon`."""
    text = (
        "The PE firm's internal-appointment push is almost certainly "
        "anchored to exit horizon, not to a sober read of the situation."
    )
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True, (
            f"`exit horizon` must classify as noun-modifier; matched={matched!r}"
        )


def test_observational_infinitive_subordinate_clause_negated_main_does_not_fire():
    """`to acquire that ambiguity doesn't resolve` — `acquire` is an
    infinitive in a subordinate clause whose main verb is negated."""
    text = (
        "Paying 14x (the likely closing number after negotiation) to "
        "acquire that ambiguity doesn't resolve concentration risk."
    )
    result = _scan(text)
    if result is not None:
        matched, observational = result
        assert observational is True, (
            f"infinitive-in-subordinate-clause with negated main verb must be "
            f"observational; matched={matched!r}"
        )


# ─────────────────────────────────────────────────────────────────
# Coverage assertion — at least 5 fire + 7 don't fire production cases
# ─────────────────────────────────────────────────────────────────


FIRE_CASES = [
    "You should sell the asset before the holidays.",
    "Fire the CFO before Q3 close.",
    "You need to launch the product in November.",
    "Raise prices by 15% next quarter.",
    "You must terminate the contract.",
]

DO_NOT_FIRE_CASES = [
    "Scenario B — partial pivot toward services revenue, capped at 15%.",
    "Institutional shareholders typically do not underwrite execution risk.",
    "The audit findings should have triggered a pause.",
    "The cross-sell math collapsed in month eleven.",
    "Paying 14x to acquire that ambiguity doesn't resolve concentration.",
    "Exit horizon dominates the PE firm's reasoning.",
    "Their sell-off was the dominant signal in the quarter.",
]


def test_fire_corpus_all_fire():
    """All FIRE_CASES must classify as imperatives (not observational)."""
    misses = []
    for s in FIRE_CASES:
        result = _scan(s)
        if result is None:
            misses.append((s, "NO MATCH"))
        else:
            matched, obs = result
            if obs:
                misses.append((s, f"classified observational on match {matched!r}"))
    assert not misses, f"FIRE_CASES must all fire as imperative; misses: {misses}"


def test_do_not_fire_corpus_all_pass():
    """All DO_NOT_FIRE_CASES must either not match any pattern OR
    classify as observational on whatever match is found."""
    misses = []
    for s in DO_NOT_FIRE_CASES:
        result = _scan(s)
        if result is None:
            continue  # clean — no pattern fired at all
        matched, obs = result
        if not obs:
            misses.append((s, f"true-imperative classification on match {matched!r}"))
    assert not misses, (
        f"DO_NOT_FIRE_CASES must classify observational; misses: {misses}"
    )


def test_coverage_minima_are_met():
    """Lock the coverage contract — at least 3 fire + 3 don't-fire
    cases must be exercised, per user dispatch spec."""
    assert len(FIRE_CASES) >= 3, "≥3 fire cases required"
    assert len(DO_NOT_FIRE_CASES) >= 3, "≥3 don't-fire cases required"


# ─────────────────────────────────────────────────────────────────
# End-to-end through refuse_to_decide_enforcement
# ─────────────────────────────────────────────────────────────────


def test_end_to_end_validator_fires_on_real_imperative_in_pathway():
    """The validator (not just the classifier) must still fire on a
    true imperative when wired into a real ArtefactPayload."""
    from services.solva_v2.artefact_schema import (
        ArtefactPayload, CoverSlide, HeadlineSlide, KeyFinding,
        ScenarioRow, PerScenarioConfidenceTable,
        SensitivityInput, ReflectionSection, ReflectionQuestion,
        PathwayItem, MethodologicalHonesty, InClosing,
        BiasInventorySection, BiasItem,
        PreMortemSlide, PreMortemFailureMode,
        CostAsymmetrySlide, CostAsymmetryScenario,
    )
    from services.solva_v2.integrity_validators import refuse_to_decide_enforcement

    methodological = MethodologicalHonesty(
        what_report_is="x" * 50, what_report_is_not="y" * 50,
        provisional_nature_paragraph="z" * 50, not_sole_basis_paragraph="w" * 50,
        input_confidence_pct=60,
    )
    payload = ArtefactPayload(
        schema_version="solva.v2.artefact.1.0",
        session_id="s",
        cover=CoverSlide(title="t", prepared_for="p", subject="s",
                         inputs_range="r", date_str="2026-02-01"),
        headline=HeadlineSlide(key_findings=[
            KeyFinding(number=i, paragraph_text="A clean sentence.", source_citations=[])
            for i in (1, 2, 3)
        ]),
        tensions=[], per_tension_deep_dive=[],
        scenarios=[
            ScenarioRow(label="x", description="x", weight_pct=50, confidence_pct=50,
                        confidence_calibration_reasoning="low conf, no triangulation",
                        tier="corpus")
        ],
        per_scenario_confidence_table=PerScenarioConfidenceTable(rows=[]),
        sensitivity_inputs=[],
        reflection_section=ReflectionSection(questions=[
            ReflectionQuestion(question_text="q1", diagnostic_interpretation="r1"),
            ReflectionQuestion(question_text="q2", diagnostic_interpretation="r2"),
            ReflectionQuestion(question_text="q3", diagnostic_interpretation="r3"),
        ]),
        pathway=[
            PathwayItem(
                number=1, timeline_tag="DAYS 0-30",
                action_heading="Take action",
                detail_paragraph=(
                    "You need to launch the product in November to capture the "
                    "regulatory window before it closes."
                ),
            ),
        ],
        decision_logic=[],
        risk_mitigation=[],
        methodological_honesty=methodological,
        in_closing=InClosing(reframing_paragraph="r", key_findings_recap=["a"],
                             final_statement="f"),
        bias_inventory=BiasInventorySection(biases=[
            BiasItem(bias_name="x", bias_display_name="X",
                    likelihood="low",
                    evidence_grounded_reasoning="The framing indicates a low-likelihood pattern of reasoning.",
                    source_input_ids=["framing"])
        ]),
        pre_mortem=PreMortemSlide(failure_modes=[
            PreMortemFailureMode(
                failure_kind="execution_velocity",
                failure_narrative=("Investigating the leading indicator earlier would shift this risk; "
                                  "the pathway slips if the velocity assumption proves brittle."),
                triggering_signals=["Velocity drop ≥10% week-over-week."],
                counter_action="Monitoring the velocity signal weekly.",
                source_input_ids=["synthesis"],
            )
        ]),
        cost_asymmetry=CostAsymmetrySlide(scenarios=[
            CostAsymmetryScenario(
                pathway_label="A",
                if_correct_outcome=("The evidence supports the leading pathway and the upside is "
                                    "captured at the calibrated probability the engine surfaces."),
                if_wrong_cost=("If wrong, the cost reabsorbed remains modest at the corpus tier and "
                              "the optionality loss is small enough to recover within a quarter."),
                cost_magnitude="medium", cost_kind="opportunity_cost",
                source_input_ids=["synthesis"],
            ),
            CostAsymmetryScenario(
                pathway_label="B",
                if_correct_outcome=("The alternative pathway captures a different upside profile "
                                    "anchored to a deeper-tier signal that the engine cross-reads."),
                if_wrong_cost=("If wrong, the cost reabsorbed sits materially higher at the depth tier "
                              "and the time cost extends across two reporting periods."),
                cost_magnitude="medium", cost_kind="time_cost",
                source_input_ids=["depth"],
            ),
        ]),
    )
    offenders = refuse_to_decide_enforcement(payload, {})
    assert any(o.location.startswith("pathway[0]") for o in offenders), (
        f"Validator must fire on the true imperative; offenders: {offenders!r}"
    )
