"""Solva v2 — LLM prompt strings for fields not deterministically derivable
from existing engine outputs.

Solva borrows STRUCTURE from the upstream canonical methodology
(verbatim-quote evidence, probability-weighted scenarios, sensitivity
analysis, methodological honesty, decision logic, sequenced
recommendations with cluster derivation). The IDENTITY is Solva's own.
Every prompt below names the diagnostic as a "Solva diagnostic" — never
the upstream brand. The reasoning shape is the Solva 5-layer pass:

    Layer 0 — Frame Audit (FAR)
    Layer 1 — Surface (candidate generation)
    Layer 2 — Depth   (triangulation + tension detection)
    Layer 3 — Synthesis (the diagnosis paragraph)
    Layer 4 — Reflection (3 fixed reflection questions)

Slice 1b ships the DETERMINISTIC `payload_builder` that emits a valid
payload from existing engine outputs alone. This module supplies the
prompt CONSTANTS the LLM-enrichment layer (wired in Slice 2) will use
to upgrade individual fields above the deterministic baseline:

  • headline.key_findings           — LLM-crafted (vs deterministic
                                      "top-3 by confidence")
  • scenarios[].weight_pct          — separate from confidence_pct
                                      (deterministic baseline sets
                                      weight = confidence; LLM splits)
  • sensitivity_inputs[].cluster_weight_shift_mechanic
                                    — explicit "from Y% to Z%" copy
  • decision_logic[]                — narrative if/then beyond the
                                      deterministic template
  • in_closing.reframing_paragraph  — narrative reframing beyond the
                                      deterministic template
  • methodological_honesty          — narrative beyond the deterministic
                                      template (template-rendered today)

Each prompt is a PURE constant — no formatting code lives here. The
caller layer (Slice 2 runner) substitutes session-specific variables
via .format() / str.format_map() before invoking the LLM.

Discipline: every prompt embeds the integrity-validator constraints
inline so the LLM produces output that passes validation on FIRST
emission. The `compose_retry_prompt()` helper wraps the original
prompt with the `revision_hint_bundle()` from the validator's
`ValidationResult` when a first attempt fails — max 1 retry per
Trust pillar 3.

NEVER add an alternative phrasing that would let the LLM bypass
integrity. The point of the prompts is to make the validator-passing
output the path of least resistance.
"""
from __future__ import annotations

from typing import Optional


# ─────────────────────────────────────────────────────────────────
# Shared constraint preamble — appended to every v2 prompt
# ─────────────────────────────────────────────────────────────────


CONSTRAINT_PREAMBLE = """\
INTEGRITY CONSTRAINTS — these are non-negotiable. The output you produce
will be rejected by automated validators if any of these are violated:

1. CITATION: every numerical claim (percentages, counts, time spans,
   monetary amounts) MUST cite a `source_input_id` that resolves to an
   entry in the session's audit log, user turns, attached documents, or
   comparable corpus. NEVER emit a number without naming its source.

2. CONFIDENCE TRIANGULATION: any confidence_pct ≥ 70 MUST name ≥ 2
   INDEPENDENT triangulating evidence sources in the supporting_evidence
   list AND explain the triangulation in `confidence_calibration_reasoning`.
   Independence = different `source_kind` (user_turn vs corpus vs comparable
   vs attached_doc) OR different `source_layer` (framing vs grounding vs
   synthesis vs reflection). Two citations from the same kind+layer is
   NOT triangulation — it is echo.

3. REFUSE-TO-DECIDE: NEVER state a directive in recommendation copy. Use
   ONLY:
     • Conditional framing: "If <data outcome> → then <strategic conclusion>"
     • Observational framing: "The evidence supports investigating X"
     • Provisional framing: "One option worth pressure-testing is Y"
   NEVER use: "you should", "you must", "retain X", "fire Y", "kill Z",
   "pivot to W". Solva surfaces conditional pathways; the user decides.

4. METHODOLOGICAL HONESTY: every report MUST include a substantive
   (≥ 1 sentence per sub-section) statement of what the report IS, what
   it IS NOT, its provisional nature, and the input confidence percentage.
"""


# ─────────────────────────────────────────────────────────────────
# 1 — Headline (exactly 3 key findings)
# ─────────────────────────────────────────────────────────────────


HEADLINE_PROMPT = """\
You are composing the 'If you read nothing else, read this' slide for a
Solva diagnostic.

INPUTS:
  • Session framing (intent): {intent}
  • Top-weighted scenarios (top 5): {top_scenarios_json}
  • Surfaced tensions: {tensions_json}
  • Audit log id roster: {audit_id_roster}

TASK:
Produce EXACTLY 3 key findings (no more, no less). Each finding must:
  • Be 1-3 sentences, written as observational synthesis (not directive).
  • Carry at least one `source_citation` resolving to an audit log id
    from the roster above.
  • Synthesize signal across BOTH scenarios AND tensions where possible.

OUTPUT: strict JSON array of 3 objects, each shaped:
  {{
    "number": <1|2|3>,
    "paragraph_text": "<the 1-3 sentence finding>",
    "source_citations": [
      {{
        "source_input_id": "<from audit log roster>",
        "source_kind": "audit_log|user_turn|comparable|attached_doc|corpus",
        "excerpt": "<verbatim or near-verbatim snippet from the source>",
        "source_layer": "framing|grounding|hypothesis|synthesis|reflection"
      }}
    ]
  }}

""" + CONSTRAINT_PREAMBLE


# ─────────────────────────────────────────────────────────────────
# 2 — Scenarios with weight/confidence split
# ─────────────────────────────────────────────────────────────────


SCENARIOS_WEIGHT_SPLIT_PROMPT = """\
You are refining the probability-weighted scenarios for a Solva diagnostic.

The probability_weighting engine has produced raw `confidence_pct` values
for each scenario. Your job is to split this single value into TWO
distinct fields:

  • `weight_pct`     — probability that this scenario describes reality
  • `confidence_pct` — engine's calibrated certainty about that probability

These can diverge: a scenario with weight 30% and confidence 80% means
"we are 80% sure this scenario has a 30% chance of being true."

INPUTS:
  • Raw scenarios with single confidence_pct: {raw_scenarios_json}
  • Audit log id roster: {audit_id_roster}

TASK:
Emit JSON array, same length as input. Each item shaped:
  {{
    "label": "<from input>",
    "description": "<from input>",
    "weight_pct": <0-100, the probability this scenario obtains>,
    "confidence_pct": <0-100, certainty about the weight>,
    "supporting_evidence": [
      {{ source_input_id, source_kind, excerpt, source_layer }}
      // ≥ 2 entries with DIFFERENT source_kind OR source_layer
      // when confidence_pct >= 70
    ],
    "confidence_calibration_reasoning": "<1-2 sentences naming the
      triangulating sources by name>",
    "tier": "<from input>"
  }}

Weights across the array do NOT need to sum to 100 (scenarios are
independent reads, not partition probabilities). But each weight_pct
and confidence_pct must be defensible from the supporting_evidence cited.

""" + CONSTRAINT_PREAMBLE


# ─────────────────────────────────────────────────────────────────
# 3 — Sensitivity cluster-shift explicit copy
# ─────────────────────────────────────────────────────────────────


SENSITIVITY_CLUSTER_SHIFT_PROMPT = """\
You are writing explicit cluster-weight-shift copy for sensitivity inputs
in a Solva diagnostic.

For each sensitivity input, the user must SEE in writing how much the
weighted picture shifts if that input resolves one way vs the other.
The deterministic baseline uses generic ±20 pp copy; you will replace
this with a specific, defensible mechanic per input.

INPUTS:
  • Sensitivity inputs (rank + description): {sensitivity_inputs_json}
  • Current scenario weights: {scenario_weights_json}
  • Audit log id roster: {audit_id_roster}

TASK:
For each sensitivity input, return JSON shaped:
  {{
    "rank": "<from input>",
    "input_description": "<from input>",
    "impact_explanation": "<1-2 sentences explaining the lever>",
    "cluster_weight_shift_mechanic": "<explicit 'could move scenario X
       weight from Y% to Z%' or 'could move cluster A from Y% to Z%' copy,
       grounded in the current weights above>",
    "affected_cluster_id": "<cluster id from session>"
  }}

The shift mechanic MUST name a specific scenario or cluster AND specific
percentage points. Vague copy ("could shift the read significantly") will
be rejected by the validator.

""" + CONSTRAINT_PREAMBLE


# ─────────────────────────────────────────────────────────────────
# 4 — Decision logic (narrative if/then beyond deterministic)
# ─────────────────────────────────────────────────────────────────


DECISION_LOGIC_PROMPT = """\
You are composing the Decision Logic slide for a Solva diagnostic.

The slide is a sequence of if/then branches that map specific data
outcomes to strategic conclusions. The branches connect sensitivity
inputs (the levers) to scenarios (the weighted reads) by way of
observational consequence.

INPUTS:
  • Scenarios with weights: {scenarios_json}
  • Sensitivity inputs: {sensitivity_inputs_json}
  • Audit log id roster: {audit_id_roster}

TASK:
Produce 3-5 if/then branches. Each branch shaped:
  {{
    "condition": "If <specific observable data outcome>",
    "conclusion": "<observational consequence — what the weighted read
       supports under this condition. NOT a directive.>",
    "rationale": "<1-2 sentences naming the evidence linkage>"
  }}

Conditions should be testable (specific metrics, time windows, or
observable thresholds). Conclusions are observational ("the read shifts
toward X", "the weighted picture supports Y"). NEVER imperative.

""" + CONSTRAINT_PREAMBLE


# ─────────────────────────────────────────────────────────────────
# 5 — In Closing reframing
# ─────────────────────────────────────────────────────────────────


IN_CLOSING_REFRAMING_PROMPT = """\
You are composing the In Closing slide for a Solva diagnostic.

This slide reframes the user's opening question (the user's Layer 1
Surface framing) in light of the Layer 3 Synthesis (the diagnosis) and
the Layer 4 Reflection responses. The reframing must surface the gap
between the question the user asked and the question the evidence
supports asking.

INPUTS:
  • Opening framing (intent, Layer 1 Surface): {intent}
  • Strongest scenario after weighting: {top_scenario_json}
  • Layer 4 Reflection responses: {reflection_responses_json}
  • Surfaced tensions: {tensions_json}

TASK:
Emit JSON shaped:
  {{
    "reframing_paragraph": "<2-3 sentences. Identify the gap between
       opening framing and what the evidence supports asking. Observational.>",
    "key_findings_recap": [<3 short strings summarizing the headline>],
    "final_statement": "<1-2 sentences. Conditional. Names the
       sensitivity that would shift the read. NEVER directive.>"
  }}

""" + CONSTRAINT_PREAMBLE


# ─────────────────────────────────────────────────────────────────
# 6 — Methodological honesty narrative
# ─────────────────────────────────────────────────────────────────


METHODOLOGICAL_HONESTY_PROMPT = """\
You are composing the Methodological Honesty slide for a Solva
diagnostic. This slide is required on every artefact.

INPUTS:
  • Aggregate input confidence (engine-computed): {input_confidence_pct}%
  • Number of active tensions: {tension_count}
  • Number of refused candidates: {refused_count}
  • Submodule (framing): {submodule}

TASK:
Emit JSON with FOUR sub-sections, each ≥ 1 sentence:
  {{
    "what_report_is": "<1-2 sentences naming what this report is — a
       diagnostic synthesis, not a decision>",
    "what_report_is_not": "<1-2 sentences naming what this report is
       NOT — naming the refused-candidate count when > 0>",
    "provisional_nature_paragraph": "<1-2 sentences acknowledging
       provisional nature, citing the active tensions>",
    "input_confidence_pct": <0-100>,
    "not_sole_basis_paragraph": "<1-2 sentences instructing the user to
       NOT treat this as a sole basis for strategic commitment>"
  }}

""" + CONSTRAINT_PREAMBLE


# ─────────────────────────────────────────────────────────────────
# Retry-prompt composer
# ─────────────────────────────────────────────────────────────────


def compose_retry_prompt(original_prompt: str, revision_hint_bundle: str) -> str:
    """Wrap the original prompt with a structured revision instruction
    derived from the validator's failed-attempt offenders.

    Slice 2 runner uses this once (max 1 retry per Trust pillar 3); if
    the retry also fails, the runner must surface a structured error
    upstream — NEVER silently bypass."""
    if not revision_hint_bundle:
        return original_prompt
    return (
        original_prompt
        + "\n\n--- RETRY ---\n"
        + revision_hint_bundle
        + "\n\nRe-emit the output addressing every revision hint above. "
        + "Output MUST pass all integrity validators on this second attempt."
    )


# ─────────────────────────────────────────────────────────────────
# Public roster — used by tests + the Slice 2 runner for discovery
# ─────────────────────────────────────────────────────────────────


V2_PROMPT_ROSTER = {
    "headline": HEADLINE_PROMPT,
    "scenarios_weight_split": SCENARIOS_WEIGHT_SPLIT_PROMPT,
    "sensitivity_cluster_shift": SENSITIVITY_CLUSTER_SHIFT_PROMPT,
    "decision_logic": DECISION_LOGIC_PROMPT,
    "in_closing": IN_CLOSING_REFRAMING_PROMPT,
    "methodological_honesty": METHODOLOGICAL_HONESTY_PROMPT,
}


def get_prompt(name: str) -> Optional[str]:
    """Lookup helper for the runner."""
    return V2_PROMPT_ROSTER.get(name)


__all__ = [
    "CONSTRAINT_PREAMBLE",
    "HEADLINE_PROMPT",
    "SCENARIOS_WEIGHT_SPLIT_PROMPT",
    "SENSITIVITY_CLUSTER_SHIFT_PROMPT",
    "DECISION_LOGIC_PROMPT",
    "IN_CLOSING_REFRAMING_PROMPT",
    "METHODOLOGICAL_HONESTY_PROMPT",
    "V2_PROMPT_ROSTER",
    "get_prompt",
    "compose_retry_prompt",
]
