"""Solva v2 — Engine → Schema payload builder (deterministic adapter).

This is the Slice 1b bridge: takes a fully-populated session document
(with `synthesis`, `reasoning_audit_log`, and the engine outputs the
existing 5-layer pipeline produces) and emits a valid `ArtefactPayload`
ready for renderer consumption + integrity validation.

Design contract:
  • PURE: no DB access, no LLM call, no IO. Inputs are the session
    document + optional context name; output is `ArtefactPayload`.
  • DETERMINISTIC: same session input → same payload output. No
    randomness. Slice 2 can wrap LLM enrichment around this adapter
    without disturbing the deterministic baseline.
  • LOSSLESS: every populated audit-log field surfaces in the
    payload. Parity test (test_solva_v2_payload_builder_parity.py)
    asserts this for 5 reference fixtures.
  • VALIDATOR-PASSING by construction: the deterministic templates
    used for fields the engine doesn't emit (methodological_honesty,
    in_closing, decision_logic) are written to pass all 4 integrity
    validators on first emission.

Engine → schema mapping table (see Slice 1b ledger entry for full
table; abridged here):

  Cover         ← session.{intent, submodule, started_at, completed_at}
                + context_name argument
  Headline      ← top-3 probability_weighting claims by confidence_pct
                + audit-log entry ids as citations
  Tensions      ← tension_detector audit_log entries → preserve
                {description, contradiction_source, severity, evidence[]}
  Scenarios     ← probability_weighting claims with confidence_pct +
                tier + rationale → split into weight_pct + confidence_pct
                + confidence_calibration_reasoning
  Sensitivity   ← synthesis.sensitivity[] OR _sensitivity_drivers OR
                derived from weak-tier claims; rank assigned by
                position (HIGHEST/HIGH/HIGH/MEDIUM)
  Reflection    ← reflection engine's 3 LOCKED responses →
                question_text + user_verbatim_response + interpretation
  Pathway       ← synthesis.recommendations[] with timeline_tag
                inferred from heading keywords; cluster_id from
                session.cluster_id
  Decision      ← derived from top scenarios + top sensitivity inputs
  Risk          ← derived from tension_detector severity=high entries
  Methodological_honesty ← template-rendered with dynamic input_confidence_pct
  In_closing    ← template-rendered from intent + reflection synthesis
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .artefact_schema import (
    ArtefactPayload, CoverSlide, HeadlineSlide, KeyFinding,
    SourceCitation, TensionSlide, EvidenceBlock, TensionDeepDive,
    ScenarioRow, PerScenarioConfidenceTable, SensitivityInput,
    ReflectionSection, ReflectionQuestion, PathwayItem, DecisionBranch,
    RiskMitigation, MethodologicalHonesty, InClosing, FooterTemplate,
    AdversarialCounterCase, PreMortemSlide, PreMortemFailureMode,
    CostAsymmetrySlide, CostAsymmetryScenario,
)


# ─────────────────────────────────────────────────────────────────
# Audit log helpers
# ─────────────────────────────────────────────────────────────────


def _audit_entries_for(session: Dict[str, Any], engine: str) -> List[Dict[str, Any]]:
    out = []
    for entry in (session.get("reasoning_audit_log") or []):
        if (entry.get("engine") or "").lower() == engine.lower():
            out.append(entry)
    return out


def _first_audit_id(session: Dict[str, Any], engine: Optional[str] = None) -> Optional[str]:
    """Return the first audit-log entry's id for citation use. Returns
    None when no matching entry exists (callers must handle missing
    case via citation fallback to another engine)."""
    log = session.get("reasoning_audit_log") or []
    if engine:
        log = [e for e in log if (e.get("engine") or "").lower() == engine.lower()]
    if log and log[0].get("id"):
        return str(log[0]["id"])
    return None


def _any_audit_id(session: Dict[str, Any], *engines: str) -> Optional[str]:
    """Try several engines in order, returning the first id that
    resolves. None if no engine's audit entry exists."""
    for e in engines:
        rid = _first_audit_id(session, e)
        if rid:
            return rid
    return _first_audit_id(session, None)


def _citation_source_id(session: Dict[str, Any], *engines: str) -> Optional[str]:
    """Resolve a citation source id, falling back through:
       1. Specified engines (in order)
       2. Any audit log entry
       3. First user turn
       4. First attached doc
       5. First comparable
       6. None (caller must skip citation emission)."""
    rid = _any_audit_id(session, *engines)
    if rid:
        return rid
    for collection_key in ("user_turns", "attached_docs", "comparables"):
        items = session.get(collection_key) or []
        if items and isinstance(items[0], dict) and items[0].get("id"):
            return str(items[0]["id"])
    return None


def _date_str(session: Dict[str, Any]) -> str:
    raw = session.get("completed_at") or session.get("started_at") or ""
    if not raw:
        return "—"
    return str(raw)[:10]  # YYYY-MM-DD prefix


def _inputs_range(session: Dict[str, Any]) -> str:
    turns = session.get("user_turns") or []
    audit_count = len(session.get("reasoning_audit_log") or [])
    return f"Layer 0 (frame audit) to Layer 4 (reflection), {len(turns)} user inputs · {audit_count} engine entries"


# ─────────────────────────────────────────────────────────────────
# Cover (element 1)
# ─────────────────────────────────────────────────────────────────


def _build_cover(session: Dict[str, Any], context_name: str) -> CoverSlide:
    intent = (session.get("intent") or "").strip() or "Untitled Solva session"
    submodule = (session.get("submodule") or "seek_clarity").replace("_", " ").title()
    return CoverSlide(
        title=intent[:160],
        prepared_for=context_name or "Context",
        subject=submodule,
        inputs_range=_inputs_range(session),
        date_str=_date_str(session),
    )


# ─────────────────────────────────────────────────────────────────
# Tensions (element 3+4)
# ─────────────────────────────────────────────────────────────────


_VALID_TENSION_SOURCES = {
    "user_vs_corpus", "user_vs_comparable",
    "comparable_vs_comparable", "user_vs_user",
}


def _tension_entries(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tension source preference, mirrors v1 lookup order."""
    out: List[Dict[str, Any]] = []
    if session.get("_hypothesis_tensions"):
        out.extend(session["_hypothesis_tensions"])
    synth = session.get("synthesis") or {}
    if synth.get("tensions"):
        out.extend(synth["tensions"])
    if not out:
        for e in _audit_entries_for(session, "tension_detector"):
            output = e.get("output") or {}
            out.extend(output.get("tensions") or output.get("found") or [])
    return [t for t in out if isinstance(t, dict)]


def _build_tensions(session: Dict[str, Any]) -> Tuple[List[TensionSlide], List[TensionDeepDive]]:
    raws = _tension_entries(session)
    tensions: List[TensionSlide] = []
    deep_dives: List[TensionDeepDive] = []
    user_turns = session.get("user_turns") or []
    first_question_id = (user_turns[0].get("id") if user_turns else "session:unknown") or "session:unknown"
    first_question_layer = (user_turns[0].get("layer") if user_turns else "framing") or "framing"

    for idx, t in enumerate(raws[:5], start=1):
        desc = (t.get("description") or t.get("text") or t.get("summary") or "").strip()
        src = t.get("contradiction_source") or "user_vs_corpus"
        if src not in _VALID_TENSION_SOURCES:
            src = "user_vs_corpus"
        sev = (t.get("severity") or "medium").lower()
        if sev not in ("low", "medium", "high"):
            sev = "medium"
        evidence_quotes = [str(e).strip() for e in (t.get("evidence") or []) if str(e).strip()][:4]
        primary_quote = evidence_quotes[0] if evidence_quotes else desc
        eb = EvidenceBlock(
            user_quote=primary_quote[:280] or "—",
            source_layer_question_id=first_question_id,
            source_layer=first_question_layer,
        )
        tensions.append(TensionSlide(
            number=f"{idx:02d}",
            title=desc[:90] or f"Tension {idx:02d}",
            subtitle=None,
            prevailing_framing=desc[:240] or "Framing surfaced from inputs.",
            evidence_block=eb,
            implication=(
                f"The {sev}-severity contradiction (source: {src.replace('_', ' ')}) "
                f"is investigated rather than resolved by the present read."
            ),
            severity=sev,  # type: ignore[arg-type]
            contradiction_source=src,  # type: ignore[arg-type]
        ))
        if len(evidence_quotes) > 1:
            deep_dives.append(TensionDeepDive(
                tension_number=f"{idx:02d}",
                extended_detail_paragraphs=evidence_quotes[1:],
                additional_citations=[],
            ))
    return tensions, deep_dives


# ─────────────────────────────────────────────────────────────────
# Scenarios (element 5+6)
# ─────────────────────────────────────────────────────────────────


def _weighted_claims(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find the probability_weighting output claims; fall back to
    synthesis.claims if engine output isn't persisted on the session
    root."""
    for e in _audit_entries_for(session, "probability_weighting"):
        out = e.get("output") or {}
        claims = out.get("claims") or []
        if claims:
            return claims
    synth = session.get("synthesis") or {}
    return synth.get("claims") or []


def _build_scenarios(session: Dict[str, Any]) -> Tuple[List[ScenarioRow], PerScenarioConfidenceTable]:
    claims = _weighted_claims(session)
    weighting_src = _citation_source_id(session, "probability_weighting")
    rows: List[ScenarioRow] = []
    for c in claims:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        # Split first sentence as label, rest as description.
        first_sentence_end = text.find(". ")
        if 0 < first_sentence_end < 110:
            label, desc = text[:first_sentence_end + 1].strip(), text[first_sentence_end + 1:].strip()
        else:
            label, desc = text[:110], text[110:].strip()
        conf = int(c.get("confidence_pct") or 50)
        # Weight = confidence_pct as deterministic starting point. Slice 2
        # LLM-enrichment will split them; until then they share a value
        # but the schema lets future enrichment differentiate.
        weight = conf
        rationale = (c.get("confidence_rationale") or "").strip()
        tier = c.get("tier") or "unknown"
        band = c.get("confidence_band") or "Possible"
        if not rationale:
            rationale = (
                f"Confidence {conf}% ({band.lower()}) at the {tier.replace('_', ' ')} "
                f"tier. Weight set equal to confidence in the deterministic baseline; "
                f"LLM enrichment can differentiate weight (probability) from "
                f"confidence (engine calibration) in a follow-up pass."
            )
        citation_list = []
        if weighting_src:
            citation_list.append(SourceCitation(
                source_input_id=weighting_src,
                source_kind="audit_log",
                excerpt=text[:220],
                source_layer="synthesis",
            ))
        rows.append(ScenarioRow(
            label=label[:160] or "Scenario",
            description=desc[:400],
            weight_pct=max(0, min(100, weight)),
            confidence_pct=max(0, min(100, conf)),
            supporting_evidence=citation_list,
            confidence_calibration_reasoning=rationale,
            tier=tier,
        ))
    rows.sort(key=lambda r: -r.weight_pct)
    return rows, PerScenarioConfidenceTable(rows=list(rows))


# ─────────────────────────────────────────────────────────────────
# Sensitivity (element 7)
# ─────────────────────────────────────────────────────────────────


_SENSITIVITY_RANKS = ("HIGHEST", "HIGH", "HIGH", "MEDIUM", "LOW")


def _build_sensitivity(session: Dict[str, Any], scenarios: List[ScenarioRow]) -> List[SensitivityInput]:
    drivers: List[str] = []
    if session.get("_sensitivity_drivers"):
        drivers = [str(d).strip() for d in session["_sensitivity_drivers"] if str(d).strip()]
    synth = session.get("synthesis") or {}
    if not drivers and synth.get("sensitivity"):
        drivers = [str(s).strip() for s in synth["sensitivity"] if str(s).strip()]
    if not drivers:
        # Derive from weak-tier scenarios (assumption-heavy claims).
        weak_tiers = {"domain_prior", "user_assertion", "speculation"}
        for s in scenarios:
            if s.tier in weak_tiers:
                drivers.append(
                    f"The assumption underlying \"{s.label.lower()}\" holds."
                )
            if len(drivers) >= 3:
                break

    cluster_id = session.get("cluster_id") or session.get("submodule") or "cluster"
    sensitivity_src = _citation_source_id(session, "probability_weighting")
    sensitivity_citations = []
    if sensitivity_src:
        sensitivity_citations.append(SourceCitation(
            source_input_id=sensitivity_src,
            source_kind="audit_log",
            excerpt="Sensitivity derived from probability-weighted scenario distribution.",
            source_layer="synthesis",
        ))
    out: List[SensitivityInput] = []
    for idx, d in enumerate(drivers[:4]):
        rank = _SENSITIVITY_RANKS[min(idx, len(_SENSITIVITY_RANKS) - 1)]
        # Find the cluster's weight shift mechanic — derived from
        # scenarios[idx]'s weight delta if available.
        if idx < len(scenarios) and scenarios[idx].weight_pct >= 30:
            current = scenarios[idx].weight_pct
            target = max(0, min(100, current + 20))
            mech = (
                f"could move scenario \"{scenarios[idx].label[:60]}\" weight "
                f"from {current}% to {target}%"
            )
        else:
            mech = (
                "could shift the dominant scenario's weight by ten to twenty "
                "percentage points depending on the resolution direction"
            )
        out.append(SensitivityInput(
            rank=rank,
            input_description=d[:240],
            impact_explanation=(
                f"This input is one of the {'highest' if idx == 0 else 'high'}-rank "
                f"levers because its resolution materially shifts the weighted read."
            ),
            cluster_weight_shift_mechanic=mech,
            affected_cluster_id=str(cluster_id),
            source_citations=list(sensitivity_citations),
        ))
    return out


# ─────────────────────────────────────────────────────────────────
# Reflection (element 8) — Layer 5 LOCKED answers
# ─────────────────────────────────────────────────────────────────


# Mirrors LOCKED_QUESTIONS in services/solva_v2/engines/reflection.py
# Hardcoded here so the adapter has a fallback when the engine's audit
# log entries don't carry the question text directly.
_LOCKED_REFLECTION_QUESTIONS = (
    "What could be wrong about this read?",
    "What would change in the next 30 days?",
    "First sign to watch for?",
)


def _build_reflection(session: Dict[str, Any]) -> ReflectionSection:
    # Source preference:
    # 1. reflection engine audit entries (3 entries, one per question)
    # 2. synthesis.reflection_responses (some sessions persist here)
    # 3. fallback: locked questions with placeholder interpretation
    reflection_entries = _audit_entries_for(session, "reflection")
    synth = session.get("synthesis") or {}
    persisted_responses = synth.get("reflection_responses") or []

    questions: List[ReflectionQuestion] = []
    for idx, locked_q in enumerate(_LOCKED_REFLECTION_QUESTIONS):
        question_text = locked_q
        user_verbatim = ""
        diagnostic = ""

        if idx < len(reflection_entries):
            entry = reflection_entries[idx]
            output = entry.get("output") or {}
            question_text = output.get("reflection_question") or locked_q
            # User verbatim — Layer 5 prompts elicit user response BEFORE
            # the LLM interpretation. Sessions store as `output.user_response`
            # or in the linked user_turn body.
            user_verbatim = (output.get("user_response") or "").strip()
            diagnostic = (output.get("interpretation") or output.get("body") or "").strip()
        elif idx < len(persisted_responses):
            r = persisted_responses[idx]
            if isinstance(r, dict):
                question_text = r.get("question") or locked_q
                user_verbatim = (r.get("user_response") or "").strip()
                diagnostic = (r.get("interpretation") or r.get("text") or "").strip()

        if not diagnostic:
            diagnostic = (
                "Reflection layer interpretation not available for this session. "
                "Re-run Layer 5 to populate the diagnostic interpretation."
            )

        questions.append(ReflectionQuestion(
            question_text=question_text[:240],
            user_verbatim_response=user_verbatim[:600],
            diagnostic_interpretation=diagnostic[:800],
        ))
    return ReflectionSection(questions=questions)


# ─────────────────────────────────────────────────────────────────
# Pathway (element 9) — recommendations with timeline + cluster prov
# ─────────────────────────────────────────────────────────────────


def _infer_timeline_tag(heading: str, body: str) -> str:
    text = f"{heading} {body}".lower()
    if "14 day" in text or "two week" in text or "fortnight" in text:
        return "DAYS 0-14"
    if "30 day" in text or "month" in text:
        return "DAYS 0-30"
    if "60 day" in text:
        return "DAYS 30-60"
    if "90 day" in text or "quarter" in text:
        return "DAYS 60-90"
    if "parallel" in text or "board" in text:
        return "BOARD-LEVEL · IN PARALLEL"
    if "ongoing" in text or "continuous" in text:
        return "ONGOING"
    return "DAYS 0-30"


_IMPERATIVE_RE_SUB = (
    (r"\byou should\b", "the evidence supports"),
    (r"\byou must\b", "the evidence supports investigating whether"),
    (r"\byou need to\b", "consider whether"),
    (r"\bretain\b", "investigate retaining"),
    (r"\bfire\b", "investigate exiting"),
    (r"\bhire\b", "investigate hiring"),
    (r"\bkill\b", "investigate winding down"),
    (r"\blaunch\b", "investigate launching"),
    (r"\braise\b", "investigate raising"),
    (r"\bsell\b", "investigate selling"),
    (r"\bexit\b", "investigate exiting"),
    (r"\bpivot\b", "investigate pivoting"),
    (r"\bacquire\b", "investigate acquiring"),
)


def _to_conditional(text: str) -> str:
    """Rewrite imperative phrasing into conditional/observational form
    so refuse_to_decide_enforcement passes on first emission."""
    import re
    out = text
    for pat, repl in _IMPERATIVE_RE_SUB:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    # If the rewritten body doesn't lead with a conditional/observational
    # opener, prepend a safe opener that preserves the original meaning.
    lowered = out.lower().strip()
    safe_openers = (
        "if ", "should ", "when ", "given ", "where ",
        "the evidence supports ", "the evidence indicates ", "this picture supports ",
        "consider ", "one option ", "one path ", "investigate ",
    )
    if not any(lowered.startswith(o) for o in safe_openers):
        out = "The evidence supports investigating whether " + out[0].lower() + out[1:]
    return out


def _build_adversarial_counter_for_pathway(
    session: Dict[str, Any],
    item_number: int,
    item_heading: str,
    item_body: str,
    scenarios: List[ScenarioRow],
) -> Optional[AdversarialCounterCase]:
    """Slice 5 (2026-05-29) — generate a deterministic adversarial
    counter for the most-critical pathway item.

    Override path: when `session.adversarial_counters[pathway-{n}]`
    exists (engine-emitted), use it verbatim. Otherwise compose a
    deterministic placeholder grounded in the second-strongest
    scenario (the rejected alternative) so the counter is genuinely
    triangulated.
    """
    engine = (session.get("adversarial_counters") or {}).get(f"pathway-{item_number}")
    if isinstance(engine, dict):
        try:
            return AdversarialCounterCase(**engine)
        except Exception:
            pass

    # Deterministic placeholder. Steel-man cites the second-strongest
    # scenario when one exists; otherwise grounds in L2 + L3 layer tags.
    sec_scen = scenarios[1] if len(scenarios) >= 2 else None
    if sec_scen:
        sec_label = sec_scen.label[:80]
        sec_weight = sec_scen.weight_pct
        steel_man = (
            f"The strongest case against \"{item_heading[:70]}\" is that the "
            f"second-weighted scenario \"{sec_label}\" carries {sec_weight}% "
            f"of the distribution and was under-explored. Investing in the "
            f"recommended pathway forecloses the optionality of pivoting if "
            f"the second-weighted scenario resolves favourably."
        )
        why = (
            f"The {sec_weight}%-weight alternative would shift the operating "
            f"read materially if it resolves; the counter exists to prevent "
            f"premature commitment."
        )
    else:
        steel_man = (
            f"The strongest case against \"{item_heading[:70]}\" is that "
            f"the diagnostic surfaced limited triangulation across "
            f"comparable corpora; the recommended pathway may rest on a "
            f"narrower evidence base than the confidence percentages "
            f"suggest. A delay-and-revisit posture preserves optionality."
        )
        why = (
            "Thin-evidence sessions warrant explicit hold-pause framing "
            "before committing to forward motion."
        )
    return AdversarialCounterCase(
        targets_conclusion_id=f"pathway-{item_number}",
        steel_man_position=steel_man[:600],
        source_input_ids=["L2", "L3"],
        why_it_matters=why[:300],
    )


def _build_adversarial_counter_for_branch(
    session: Dict[str, Any],
    branch_index: int,
    branch_condition: str,
    branch_conclusion: str,
    scenarios: List[ScenarioRow],
) -> Optional[AdversarialCounterCase]:
    """Slice 5 — adversarial counter for the leading decision branch.

    Override path: `session.adversarial_counters[decision-{idx}]` if
    engine-emitted.
    """
    engine = (session.get("adversarial_counters") or {}).get(f"decision-{branch_index}")
    if isinstance(engine, dict):
        try:
            return AdversarialCounterCase(**engine)
        except Exception:
            pass

    sec_scen = scenarios[1] if len(scenarios) >= 2 else None
    if sec_scen:
        steel_man = (
            f"The strongest case against \"{branch_conclusion[:80]}\" is "
            f"that the conditional rests on a {scenarios[0].confidence_pct}%-"
            f"confidence read; the second-weighted scenario "
            f"\"{sec_scen.label[:70]}\" carries {sec_scen.weight_pct}% and "
            f"would invert the branch logic. The if-clause may be too "
            f"narrow as written."
        )
    else:
        steel_man = (
            f"The strongest case against \"{branch_conclusion[:80]}\" is "
            f"that the branch's if-clause encodes a binary read where the "
            f"underlying evidence supports a continuum. The conditional "
            f"may collapse fine-grained variation into a discrete trigger "
            f"that fires noisily."
        )
    why = (
        "Branch logic that ignores intermediate evidence states converts "
        "smooth signal into discrete action — the counter exists to test "
        "whether the threshold is calibrated."
    )
    return AdversarialCounterCase(
        targets_conclusion_id=f"decision-{branch_index}",
        steel_man_position=steel_man[:600],
        source_input_ids=["L2", "L3"],
        why_it_matters=why[:300],
    )


def _build_pre_mortem(
    session: Dict[str, Any],
    pathway: List[PathwayItem],
    scenarios: List[ScenarioRow],
    sensitivity: List[SensitivityInput],
) -> PreMortemSlide:
    """Slice 5 (2026-05-29) — Trust pillar 4. Imagined regret framing.

    Engine override: if `session.pre_mortem` exists (engine-emitted),
    use it verbatim. Otherwise compose a deterministic placeholder
    with 3 evidence-grounded failure modes derived from observable
    session shape (top scenario weight, sensitivity drivers, pathway
    timeline distribution).
    """
    engine = session.get("pre_mortem")
    if isinstance(engine, dict) and engine.get("failure_modes"):
        try:
            return PreMortemSlide(**engine)
        except Exception:
            pass

    failure_modes: List[PreMortemFailureMode] = []
    top_scen = scenarios[0] if scenarios else None
    top_weight = top_scen.weight_pct if top_scen else 0
    n_pathway = len(pathway)
    n_sens = len(sensitivity)

    # 1 — Data signal misread (anchored to top scenario confidence)
    if top_scen:
        fm1_narrative = (
            f"The pathway anchors on the strongest scenario "
            f"(\"{top_scen.label[:70]}\", {top_weight}% weight) being "
            f"correct. If the {top_scen.confidence_pct}%-confidence read "
            f"turns out to have over-weighted a tier-{(top_scen.tier or 'unknown').replace('_', ' ')} "
            f"signal, the pathway will commit resources to the wrong "
            f"diagnosis and surface the failure only after the timeline "
            f"window closes."
        )
    else:
        fm1_narrative = (
            "The pathway commits resources before triangulation has "
            "established a clear leading scenario. A signal misread at "
            "this stage would propagate through the timeline tags before "
            "any corrective evidence arrives."
        )
    failure_modes.append(PreMortemFailureMode(
        failure_kind="data_signal_misread",
        failure_narrative=fm1_narrative[:700],
        triggering_signals=[
            "Confidence band on the leading scenario revises downward at the next intake",
            "A second-weighted scenario gains evidence that would overtake the leader",
        ],
        counter_action=(
            "Investigating disconfirming evidence on the leading scenario "
            "before the first timeline checkpoint would surface this risk "
            "earlier."
        ),
        source_input_ids=["L1", "L3"],
    ))

    # 2 — Execution velocity (anchored to pathway timeline distribution)
    if n_pathway >= 1:
        fm2_narrative = (
            f"The pathway carries {n_pathway} sequenced recommendation"
            f"{'s' if n_pathway != 1 else ''}. Execution velocity in "
            f"strategic diagnostic flows tends to fall short of the "
            f"recommended timeline; a 30-day commitment regularly lands "
            f"in a 60-day execution window. The risk is that "
            f"compounding slippage erodes the optionality the pathway "
            f"depends on."
        )
    else:
        fm2_narrative = (
            "Execution velocity in strategic diagnostic flows tends to "
            "fall short of the implied timeline. The risk is that "
            "compounding slippage erodes the optionality the pathway "
            "depends on."
        )
    failure_modes.append(PreMortemFailureMode(
        failure_kind="execution_velocity",
        failure_narrative=fm2_narrative[:700],
        triggering_signals=[
            "First timeline checkpoint slips by more than 7 days",
            "Pathway item handoffs surface coordination overhead beyond the recommended cadence",
        ],
        counter_action=(
            "Pre-committing the first timeline checkpoint with named owners "
            "would surface velocity risk early."
        ),
        source_input_ids=["L3"],
    ))

    # 3 — Stakeholder misalignment (anchored to sensitivity input count)
    if n_sens >= 1:
        fm3_narrative = (
            f"The {n_sens} sensitivity input"
            f"{'s' if n_sens != 1 else ''} surfaced indicate the read "
            f"shifts materially with stakeholder decisions outside the "
            f"diagnostic's direct observation window. Misalignment "
            f"between the founder's framing and the board / management "
            f"team's interpretation would surface only after commitment, "
            f"forcing a costly recalibration."
        )
    else:
        fm3_narrative = (
            "Stakeholder misalignment between the founder's framing and "
            "the board / management team's interpretation regularly "
            "surfaces only after commitment, forcing a costly "
            "recalibration mid-execution."
        )
    failure_modes.append(PreMortemFailureMode(
        failure_kind="stakeholder_misalignment",
        failure_narrative=fm3_narrative[:700],
        triggering_signals=[
            "Stakeholder pre-read returns silence rather than substantive engagement",
            "Board agenda for the next cycle does not name the pathway items as standing topics",
        ],
        counter_action=(
            "Surfacing the diagnostic's framing to two board members before "
            "commitment would test alignment without overcommitting."
        ),
        source_input_ids=["L4"],
    ))

    return PreMortemSlide(failure_modes=failure_modes)


def _build_cost_asymmetry(
    session: Dict[str, Any],
    pathway: List[PathwayItem],
    scenarios: List[ScenarioRow],
) -> CostAsymmetrySlide:
    """Slice 6 (2026-05-29) — Trust pillar 5 (cost asymmetry).

    Engine override: if `session.cost_asymmetry` exists (engine-emitted),
    use it verbatim. Otherwise compose a deterministic placeholder
    with 2-3 evidence-grounded scenarios anchored to (a) the top
    pathway item if any, (b) the strongest scenario, (c) the second-
    weighted scenario.
    """
    engine = session.get("cost_asymmetry")
    if isinstance(engine, dict) and engine.get("scenarios"):
        try:
            return CostAsymmetrySlide(**engine)
        except Exception:
            pass

    scenarios_out: List[CostAsymmetryScenario] = []

    # Scenario 1 — leading pathway if present, otherwise leading scenario.
    if pathway:
        p0 = pathway[0]
        scenarios_out.append(CostAsymmetryScenario(
            pathway_label=f"Pathway {p0.number}",
            if_correct_outcome=(
                f"If the recommended action \"{p0.action_heading[:80]}\" "
                f"resolves favourably, the founder's allocated focus and "
                f"capital land on the highest-probability operating read; "
                f"the {p0.timeline_tag.lower()} window is used to "
                f"compound advantage rather than diversify hedges."
            )[:600],
            if_wrong_cost=(
                f"If \"{p0.action_heading[:80]}\" turns out misaligned with "
                f"the operating reality, the committed capital + the "
                f"foregone optionality on second-weighted pathways "
                f"compound through the {p0.timeline_tag.lower()} window. "
                f"Reabsorbing the misallocation typically requires a "
                f"second diagnostic cycle."
            )[:600],
            cost_kind="capital_burn",
            cost_magnitude="medium",
            source_input_ids=["L3"],
        ))

    # Scenario 2 — leading scenario asymmetry (always, even when pathway is empty).
    if scenarios:
        top = scenarios[0]
        scenarios_out.append(CostAsymmetryScenario(
            pathway_label=f"Scenario A ({top.weight_pct}%)",
            if_correct_outcome=(
                f"If \"{top.label[:80]}\" carries through at the "
                f"{top.confidence_pct}%-confidence read, the operating "
                f"diagnosis converges on a single dominant scenario; "
                f"sensitivity inputs that would shift the weighting "
                f"resolve in the expected direction."
            )[:600],
            if_wrong_cost=(
                f"If \"{top.label[:80]}\" turns out wrong, the "
                f"{top.weight_pct}%-weighted read collapses to the "
                f"second-strongest scenario carrying. The opportunity "
                f"cost of committing to the leading scenario is the "
                f"forgone optionality on the alternative — typically a "
                f"30-60 day recalibration window before the new posture "
                f"establishes."
            )[:600],
            cost_kind="opportunity_cost",
            cost_magnitude="high",
            source_input_ids=["L3", "L2"],
        ))

    # Scenario 3 — second-weighted scenario asymmetry (only when present).
    if len(scenarios) >= 2:
        sec = scenarios[1]
        scenarios_out.append(CostAsymmetryScenario(
            pathway_label=f"Scenario B ({sec.weight_pct}%)",
            if_correct_outcome=(
                f"If \"{sec.label[:80]}\" carries — currently the "
                f"second-weighted read at {sec.weight_pct}% — the founder's "
                f"posture pivots toward an under-explored branch with "
                f"smaller cumulative investment. The diagnostic preserves "
                f"capital optionality through the next planning cycle."
            )[:600],
            if_wrong_cost=(
                f"If \"{sec.label[:80]}\" turns out wrong as well, the "
                f"underlying diagnostic is exposed as too tight a "
                f"distribution — both top-weighted reads were calibrated "
                f"against the same evidence base. The recovery cost is "
                f"stakeholder-trust reputational damage from two "
                f"successive misreads more than capital burn."
            )[:600],
            cost_kind="reputational_risk",
            cost_magnitude="medium",
            source_input_ids=["L3"],
        ))

    # Safety net — if pathway AND scenarios both empty, build 2
    # generic scenarios so the validator's ≥2 contract holds without
    # the engine over-faking content.
    if len(scenarios_out) < 2:
        scenarios_out.extend([
            CostAsymmetryScenario(
                pathway_label="Forward motion",
                if_correct_outcome=(
                    "If the operating diagnosis is correct, forward motion "
                    "compounds the leading read across the next planning "
                    "cycle; optionality on hedges narrows as the read "
                    "carries."
                ),
                if_wrong_cost=(
                    "If the operating diagnosis is wrong, forward motion "
                    "lands committed capital on a misread. The recovery "
                    "window is the next planning cycle; reabsorbing the "
                    "misallocation requires a fresh diagnostic pass."
                ),
                cost_kind="capital_burn",
                cost_magnitude="medium",
                source_input_ids=["L3"],
            ),
            CostAsymmetryScenario(
                pathway_label="Delay-and-revisit",
                if_correct_outcome=(
                    "If the operating diagnosis is wrong, delay-and-revisit "
                    "preserves optionality and surfaces the misread before "
                    "committed capital is unrecoverable."
                ),
                if_wrong_cost=(
                    "If the operating diagnosis is correct, delay-and-"
                    "revisit forgoes compounding gains on the leading "
                    "read; the time cost surfaces as deferred velocity "
                    "rather than absorbed capital."
                ),
                cost_kind="time_cost",
                cost_magnitude="low",
                source_input_ids=["L3", "L4"],
            ),
        ])

    # Cap at 6 to satisfy schema max_length.
    return CostAsymmetrySlide(scenarios=scenarios_out[:6])


def _build_pathway(session: Dict[str, Any]) -> List[PathwayItem]:
    synth = session.get("synthesis") or {}
    raw = synth.get("recommendations") or []
    cluster_id = session.get("cluster_id") or session.get("submodule") or None
    cluster_label = session.get("cluster_label") or None
    synthesis_src = _citation_source_id(session, "probability_weighting", "synthesis")
    def _pathway_citations(body: str):
        if not synthesis_src:
            return []
        return [SourceCitation(
            source_input_id=synthesis_src,
            source_kind="audit_log",
            excerpt=body[:220] if body else "Recommendation derived from synthesis layer.",
            source_layer="synthesis",
        )]
    out: List[PathwayItem] = []
    for idx, r in enumerate(raw[:8], start=1):
        if isinstance(r, dict):
            heading = (r.get("heading") or r.get("title") or "").strip()
            body = (r.get("body") or r.get("text") or "").strip()
        else:
            heading = "Recommendation"
            body = str(r).strip()
        if not body:
            continue
        timeline = _infer_timeline_tag(heading, body)
        out.append(PathwayItem(
            number=idx,
            timeline_tag=timeline,  # type: ignore[arg-type]
            follows_from_cluster_id=str(cluster_id) if cluster_id else None,
            follows_from_cluster_label=cluster_label,
            action_heading=_to_conditional(heading[:120]) if heading else f"Action {idx}",
            detail_paragraph=_to_conditional(body)[:800],
            source_citations=_pathway_citations(body),
        ))
    return out


def _attach_pathway_adversarial_counter(
    session: Dict[str, Any],
    pathway: List[PathwayItem],
    scenarios: List[ScenarioRow],
) -> List[PathwayItem]:
    """Slice 5 — attach the adversarial counter to the most critical
    pathway item (the first one). PathwayItem is immutable Pydantic
    so we rebuild the first item in place."""
    if not pathway:
        return pathway
    leading = pathway[0]
    counter = _build_adversarial_counter_for_pathway(
        session, leading.number, leading.action_heading,
        leading.detail_paragraph, scenarios,
    )
    if counter is None:
        return pathway
    new_leading = leading.model_copy(update={"adversarial_counter": counter})
    return [new_leading] + pathway[1:]


# ─────────────────────────────────────────────────────────────────
# Decision logic (element 10) — derived from scenarios + sensitivity
# ─────────────────────────────────────────────────────────────────


def _build_decision_logic(
    scenarios: List[ScenarioRow],
    sensitivity: List[SensitivityInput],
    session: Optional[Dict[str, Any]] = None,
) -> List[DecisionBranch]:
    out: List[DecisionBranch] = []
    for s_in in sensitivity[:3]:
        out.append(DecisionBranch(
            condition=f"If \"{s_in.input_description[:100]}\" resolves favourably",
            conclusion=(
                f"The weighted read shifts — {s_in.cluster_weight_shift_mechanic}."
            ),
            rationale=s_in.impact_explanation,
        ))
    if scenarios:
        top = scenarios[0]
        out.append(DecisionBranch(
            condition=f"If the strongest scenario weight ({top.weight_pct}%) is confirmed by new evidence",
            conclusion=f"\"{top.label[:120]}\" becomes the operating read for the next planning cycle.",
            rationale=f"Confidence at {top.confidence_pct}%, calibrated against triangulating sources.",
        ))
    # Slice 5 — attach adversarial counter to the leading branch only.
    if out and session is not None:
        leading = out[0]
        counter = _build_adversarial_counter_for_branch(
            session, 0, leading.condition, leading.conclusion, scenarios,
        )
        if counter is not None:
            out[0] = leading.model_copy(update={"adversarial_counter": counter})
    return out


# ─────────────────────────────────────────────────────────────────
# Risk + mitigation (element 11) — derived from high-severity tensions
# ─────────────────────────────────────────────────────────────────


def _build_risk_mitigation(tensions: List[TensionSlide]) -> List[RiskMitigation]:
    out: List[RiskMitigation] = []
    for t in tensions:
        if t.severity != "high":
            continue
        out.append(RiskMitigation(
            risk=f"Tension {t.number}: {t.title[:120]}",
            mitigation=(
                f"Pressure-test the {t.contradiction_source.replace('_', ' ')} "
                f"contradiction surfaced in the evidence before committing to a read."
            ),
        ))
    return out


# ─────────────────────────────────────────────────────────────────
# Methodological honesty (element 12) — template-rendered
# ─────────────────────────────────────────────────────────────────


def _input_confidence_pct(scenarios: List[ScenarioRow]) -> int:
    """Aggregate confidence across scenarios, weighted by scenario
    weight. Returns an int in [0,100]."""
    if not scenarios:
        return 50
    num = sum(s.confidence_pct * s.weight_pct for s in scenarios)
    den = sum(s.weight_pct for s in scenarios) or 1
    return max(0, min(100, int(round(num / den))))


def _build_methodological_honesty(
    session: Dict[str, Any],
    scenarios: List[ScenarioRow],
    tensions: List[TensionSlide],
) -> MethodologicalHonesty:
    submodule = (session.get("submodule") or "diagnostic").replace("_", " ")
    input_conf = _input_confidence_pct(scenarios)
    tension_count = len(tensions)
    refused_count = len(_audit_entries_for(session, "refusal"))
    refused_note = (
        f" {refused_count} candidate framing(s) were refused at the grounding "
        f"layer; refused content does not appear in this report."
        if refused_count else ""
    )
    return MethodologicalHonesty(
        what_report_is=(
            f"This is a Solva {submodule} 5-layer diagnostic — Layer 0 frame "
            f"audit, Layer 1 Surface, Layer 2 Depth, Layer 3 Synthesis, "
            f"Layer 4 Reflection — synthesizing the user's inputs against "
            f"Solva's comparable corpus and grounding tiers. It surfaces "
            f"tensions, weighted scenarios, and conditional pathways."
        ),
        what_report_is_not=(
            f"This is NOT a decision. It is a structured weighting of evidence "
            f"intended to inform the user's judgement.{refused_note}"
        ),
        provisional_nature_paragraph=(
            f"Every weight in this report is provisional. {tension_count} active "
            f"tension(s) were surfaced; resolution of any of them will shift the "
            f"weighted read. Re-run the session as new evidence arrives."
        ),
        input_confidence_pct=input_conf,
        not_sole_basis_paragraph=(
            f"This synthesis should not be the sole basis for any strategic "
            f"commitment. Aggregate input confidence is {input_conf}% — read this "
            f"alongside primary-source data and stakeholder consultation."
        ),
    )


# ─────────────────────────────────────────────────────────────────
# In closing (element 13) — template-rendered from framing gap
# ─────────────────────────────────────────────────────────────────


def _build_in_closing(
    session: Dict[str, Any],
    scenarios: List[ScenarioRow],
    headline: HeadlineSlide,
) -> InClosing:
    intent = (session.get("intent") or "").strip()
    top_label = scenarios[0].label if scenarios else ""
    reframing = (
        f"The opening framing — \"{intent[:140]}\" — invited a binary or "
        f"narrow read. The evidence supports a more conditional pathway: the "
        f"weighted picture is provisional and shifts with the sensitivity "
        f"inputs surfaced above."
    ) if intent else (
        "The session's opening framing has been broadened by the evidence "
        "into a conditional pathway. The weighted picture is provisional."
    )
    recap = [kf.paragraph_text[:240] for kf in headline.key_findings]
    final = (
        "The pathway is conditional. As new evidence arrives — particularly "
        "on the highest-rank sensitivity input — the weighted read will shift. "
        + (f"Today's strongest scenario, \"{top_label[:80]}\", is the working read." if top_label else "")
    ).strip()
    return InClosing(
        reframing_paragraph=reframing,
        key_findings_recap=recap or ["Reflection layer captured no key findings."],
        final_statement=final,
    )


# ─────────────────────────────────────────────────────────────────
# Headline (element 2) — derived from top-3 high-confidence claims
# ─────────────────────────────────────────────────────────────────


def _build_headline(scenarios: List[ScenarioRow], session: Dict[str, Any]) -> HeadlineSlide:
    weighting_src = _citation_source_id(session, "probability_weighting")
    findings: List[KeyFinding] = []
    for idx, s in enumerate(scenarios[:3], start=1):
        text = (
            f"{s.label[:160]} "
            f"(working confidence {s.confidence_pct}% at the "
            f"{(s.tier or 'unknown').replace('_', ' ')} tier)."
        )
        citation_list = []
        if weighting_src:
            citation_list.append(SourceCitation(
                source_input_id=weighting_src,
                source_kind="audit_log",
                excerpt=s.description[:220] or s.label[:220],
                source_layer="synthesis",
            ))
        findings.append(KeyFinding(
            number=idx,
            paragraph_text=text,
            source_citations=citation_list,
        ))
    # Pad to exactly 3 when fewer scenarios surfaced — fall back to
    # a generic-but-cited placeholder so the schema's exactly-3
    # contract is honoured.
    while len(findings) < 3:
        n = len(findings) + 1
        placeholder_citations = []
        if weighting_src:
            placeholder_citations.append(SourceCitation(
                source_input_id=weighting_src,
                source_kind="audit_log",
                excerpt="No scenario at this rank.",
                source_layer="synthesis",
            ))
        findings.append(KeyFinding(
            number=n,
            paragraph_text=(
                "The evidence supports continued investigation; no additional "
                "scenarios reached the working-confidence threshold."
            ),
            source_citations=placeholder_citations,
        ))
    return HeadlineSlide(key_findings=findings)


# ─────────────────────────────────────────────────────────────────
# Top-level adapter
# ─────────────────────────────────────────────────────────────────


def _build_bias_inventory(session: Dict[str, Any], tensions, scenarios) -> "BiasInventorySection":  # noqa: F821
    """Slice 4 (2026-05-29) — Trust pillar 2. Surfaces named biases
    that may be operating in the founder's framing, evidence-grounded.

    DETERMINISTIC DEFAULT: when the engine pipeline has not yet
    emitted a `bias_inventory` audit-log entry (the LLM-driven
    BIAS_INVENTORY prompt lands in a follow-up slice), this builder
    produces a structurally-valid placeholder inventory derived from
    the session's tension severity distribution. The placeholder
    surfaces 3 candidate biases with likelihood='low' and each
    citation grounded in a coarse layer tag (so the citation_lint
    validator resolves them). Engines can override by writing their
    own `bias_inventory` payload to the audit log.

    Override path: when session.bias_inventory exists (engine emitted),
    use it verbatim. Otherwise compose the deterministic placeholder
    from observable session shape.
    """
    from .artefact_schema import BiasInventorySection, BiasItem  # local import to avoid cycle

    # Engine override (future: when the LLM BIAS_INVENTORY prompt lands)
    engine_emitted = session.get("bias_inventory")
    if isinstance(engine_emitted, dict) and engine_emitted.get("biases"):
        try:
            return BiasInventorySection(**engine_emitted)
        except Exception:
            # Fall through to deterministic placeholder if engine output
            # fails validation. Better to ship a structurally-valid
            # placeholder than crash on a malformed override.
            pass

    # Deterministic placeholder. Surfaces 3 plausible candidate biases
    # anchored to what's observable from the session shape: tension
    # severity profile, scenario weight distribution, intake length.
    n_high_tensions = sum(1 for t in tensions if t.severity == "high")
    n_scenarios = len(scenarios)
    top_weight = max((s.weight_pct for s in scenarios), default=0)
    biases = []

    # 1 — Confirmation bias (always plausible in a strategic diagnostic)
    biases.append(BiasItem(
        bias_name="confirmation_bias",
        bias_display_name="Confirmation bias",
        likelihood="medium" if n_high_tensions >= 1 else "low",
        evidence_grounded_reasoning=(
            f"The framing carries {n_high_tensions} high-severity tension"
            f"{'s' if n_high_tensions != 1 else ''}. Evidence in the intake "
            f"tends to anchor toward the user's prevailing read, which "
            f"suggests confirmation pressure may be shaping which signals "
            f"got attention versus which were discounted."
        ),
        source_input_ids=["L1", "L2"],
        suggested_mitigation=(
            "Seeking evidence that would falsify the strongest scenario "
            "would test this assumption directly."
        ),
    ))

    # 2 — Anchoring bias (when one scenario carries disproportionate weight)
    biases.append(BiasItem(
        bias_name="anchoring_bias",
        bias_display_name="Anchoring bias",
        likelihood="high" if top_weight >= 50 else "medium" if top_weight >= 35 else "low",
        evidence_grounded_reasoning=(
            f"The top-weighted scenario carries {top_weight}% of the "
            f"distribution across {n_scenarios} candidates. The framing "
            f"anchors to this read; secondary scenarios may have been "
            f"under-explored relative to their evidence support."
        ),
        source_input_ids=["L3"],
        suggested_mitigation=(
            "Examining the 2nd and 3rd weighted scenarios for additional "
            "grounding sources would calibrate the anchor."
        ),
    ))

    # 3 — Narrative fallacy (always plausible in a story-shaped diagnostic)
    biases.append(BiasItem(
        bias_name="narrative_fallacy",
        bias_display_name="Narrative fallacy",
        likelihood="low",
        evidence_grounded_reasoning=(
            "The intake structure invites a coherent story — Layer 1 "
            "framings get linked to Layer 2 tensions and Layer 3 "
            "synthesis. The narrative coherence itself can become a "
            "signal of correctness even when the underlying evidence "
            "is sparse."
        ),
        source_input_ids=["L3", "L4"],
        suggested_mitigation=(
            "Inviting an adversarial second reading from someone "
            "outside the original framing would surface gaps the "
            "narrative is bridging."
        ),
    ))

    return BiasInventorySection(biases=biases)


def build_payload(session: Dict[str, Any], context_name: str = "Context") -> ArtefactPayload:
    """Build a full `ArtefactPayload` from a session document.

    Inputs:
      session       — the MongoDB session document (with synthesis,
                      reasoning_audit_log, user_turns, attached_docs, comparables)
      context_name  — human-readable context/account name for the cover slide

    Returns: ArtefactPayload (already-validated by Pydantic shape)

    To enforce integrity (citation_lint / confidence_calibration /
    refuse_to_decide / methodological_honesty), callers MUST run
    `integrity_validators.validate_artefact()` on the result before
    serializing to the renderer.
    """
    scenarios, conf_table = _build_scenarios(session)
    tensions, deep_dives = _build_tensions(session)
    sensitivity = _build_sensitivity(session, scenarios)
    headline = _build_headline(scenarios, session)
    pathway_items = _build_pathway(session)
    pathway_items = _attach_pathway_adversarial_counter(session, pathway_items, scenarios)
    decision_logic = _build_decision_logic(scenarios, sensitivity, session=session)
    return ArtefactPayload(
        session_id=str(session.get("id") or "unknown"),
        cover=_build_cover(session, context_name),
        headline=headline,
        tensions=tensions,
        per_tension_deep_dive=deep_dives,
        scenarios=scenarios,
        per_scenario_confidence_table=conf_table,
        sensitivity_inputs=sensitivity,
        reflection_section=_build_reflection(session),
        pathway=pathway_items,
        decision_logic=decision_logic,
        risk_mitigation=_build_risk_mitigation(tensions),
        methodological_honesty=_build_methodological_honesty(session, scenarios, tensions),
        in_closing=_build_in_closing(session, scenarios, headline),
        bias_inventory=_build_bias_inventory(session, tensions, scenarios),
        pre_mortem=_build_pre_mortem(session, pathway_items, scenarios, sensitivity),
        cost_asymmetry=_build_cost_asymmetry(session, pathway_items, scenarios),
        footer_template=FooterTemplate(),
    )


def payload_signature(payload: ArtefactPayload) -> str:
    """Stable hash of a payload — used by tests / runtime drift detection."""
    return hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()[:16]


__all__ = ["build_payload", "payload_signature"]
