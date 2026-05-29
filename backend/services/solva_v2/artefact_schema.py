"""Solva v2 — Artefact payload schema (Pydantic).

This is the structured contract between Solva's 5-layer reasoning engine
and the slide-paginated artefact renderer that will ship in Slice 2.
Every element the reference deck demonstrates is modelled here.

Schema completeness — 15 elements:

  1. cover                          — method tag + title + subject + method
  2. headline                       — 3 numbered key findings w/ citations
  3. tensions[]                     — 01/02/03 framing→evidence→implication
  4. per_tension_deep_dive[]        — extended per-tension detail
  5. scenarios[]                    — weight % + confidence % + evidence
  6. per_scenario_confidence_table  — table form of scenarios
  7. sensitivity_inputs[]           — HIGHEST/HIGH/HIGH rank + cluster shift
  8. reflection_section             — Layer 5 verbatim Q&A + interpretation
  9. pathway[]                      — sequenced recs w/ timeline + cluster prov
 10. decision_logic[]               — if/then branches
 11. risk_mitigation[]              — risk + mitigation pairs
 12. methodological_honesty         — what report IS / IS NOT + provisional
 13. in_closing                     — reframing + recap + final
 14. footer_template                — per-slide footer string template
 15. (cover.method_tag carries the "SOLVA · SESSION OUTPUT · CONFIDENTIAL"
      treatment; not a separate element but the canonical slide marker.)

This module is PURE — no DB, no LLM, no IO. It defines models only.

Integrity contract: every Pydantic model carries source-of-truth
annotations in field docstrings. Adapters (Slice 1b) populate these
from the audit log. Validators (`integrity_validators.py`) enforce
citation + confidence + refuse-to-decide rules at serialization time.
"""
from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────────
# Shared sub-types
# ─────────────────────────────────────────────────────────────────


SensitivityRank = Literal["HIGHEST", "HIGH", "MEDIUM", "LOW"]
TimelineTag = Literal[
    "DAYS 0-30",
    "DAYS 0-14",
    "DAYS 15-30",
    "DAYS 30-60",
    "DAYS 60-90",
    "BOARD-LEVEL · IN PARALLEL",
    "ONGOING",
]
TensionSource = Literal[
    "user_vs_corpus",
    "user_vs_comparable",
    "comparable_vs_comparable",
    "user_vs_user",
]


class SourceCitation(BaseModel):
    """A pointer into the session's audit log / source corpus.

    Every numerical claim and every confidence assertion must resolve
    to one of these. Validators check that `source_input_id` exists in
    the session's audit log."""
    source_input_id: str = Field(..., description="Audit log entry id OR user turn id OR comparable id")
    source_kind: Literal["user_turn", "audit_log", "comparable", "attached_doc", "corpus"]
    excerpt: str = Field(..., min_length=1, description="Verbatim snippet supporting the citation")
    source_layer: Optional[str] = Field(None, description="Solva audit-log layer tag emitted by the engine that produced the cited entry (e.g. framing/grounding/hypothesis/synthesis/reflection — see services/solva_v2/engines/* for the canonical emitter set).")


# ─────────────────────────────────────────────────────────────────
# Element 1 — Cover slide
# ─────────────────────────────────────────────────────────────────


class CoverSlide(BaseModel):
    method_tag: str = Field(
        default="SOLVA · SESSION OUTPUT · CONFIDENTIAL",
        description="Canonical method banner — appears on cover slide",
    )
    title: str = Field(..., min_length=1, description="The session's framing one-liner")
    prepared_for: str = Field(..., min_length=1, description="Context / account display name")
    subject: str = Field(..., min_length=1, description="Submodule label, e.g. 'Develop Strategy'")
    method: str = Field(
        default="Solva 5-layer pass — frame audit · surface · depth · synthesis · reflection",
        description="Method one-liner",
    )
    inputs_range: str = Field(..., description="e.g. 'Layer 0 (frame audit) to Layer 4 (reflection), 12 user inputs'")
    date_str: str = Field(..., description="Session completion date as 'YYYY-MM-DD'")


# ─────────────────────────────────────────────────────────────────
# Element 2 — Headline slide
# ─────────────────────────────────────────────────────────────────


class KeyFinding(BaseModel):
    number: int = Field(..., ge=1, le=3, description="1-indexed (1/2/3)")
    paragraph_text: str = Field(..., min_length=1)
    source_citations: List[SourceCitation] = Field(default_factory=list, description="Audit-log references — empty allowed at schema level, citation_lint validator enforces presence")


class HeadlineSlide(BaseModel):
    intro_copy: str = Field(
        default="If you read nothing else, read this.",
        description="The 'TL;DR' framing line",
    )
    key_findings: List[KeyFinding] = Field(..., min_length=3, max_length=3)


# ─────────────────────────────────────────────────────────────────
# Element 3 + 4 — Tensions + per-tension deep dives
# ─────────────────────────────────────────────────────────────────


class EvidenceBlock(BaseModel):
    """Verbatim user quote + the layer/question that elicited it."""
    user_quote: str = Field(..., min_length=1)
    source_layer_question_id: str = Field(..., description="Audit log id of the Q&A pair")
    source_layer: str = Field(..., description="framing/grounding/...")


class TensionSlide(BaseModel):
    number: str = Field(..., pattern=r"^\d{2}$", description="Display number — '01', '02', '03'")
    title: str = Field(..., min_length=1)
    subtitle: Optional[str] = None
    prevailing_framing: str = Field(..., min_length=1, description="The framing the user brought in")
    evidence_block: EvidenceBlock
    implication: str = Field(..., min_length=1)
    severity: Literal["low", "medium", "high"] = "medium"
    contradiction_source: TensionSource


class TensionDeepDive(BaseModel):
    tension_number: str = Field(..., pattern=r"^\d{2}$")
    extended_detail_paragraphs: List[str] = Field(default_factory=list, min_length=1)
    additional_citations: List[SourceCitation] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Element 5 + 6 — Scenarios + per-scenario confidence table
# ─────────────────────────────────────────────────────────────────


class ScenarioRow(BaseModel):
    label: str = Field(..., min_length=1)
    description: str = Field(default="", description="Optional 1-line elaboration")
    weight_pct: int = Field(..., ge=0, le=100, description="Probability weight in [0,100]")
    confidence_pct: int = Field(..., ge=0, le=100, description="Engine confidence in the weight")
    supporting_evidence: List[SourceCitation] = Field(default_factory=list, description="Audit-log references — empty allowed at schema level, citation_lint validator enforces presence")
    confidence_calibration_reasoning: str = Field(
        ..., min_length=1,
        description="Why this confidence_pct was assigned — names ≥2 triangulating sources for conf ≥ 70",
    )
    tier: Optional[str] = Field(None, description="grounding tier — corpus/comparable/...")


class PerScenarioConfidenceTable(BaseModel):
    """Tabular projection of scenarios[] for the dedicated confidence-
    table slide. Adapters typically populate this from `scenarios` —
    same data, different render."""
    rows: List[ScenarioRow] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Element 7 — Sensitivity
# ─────────────────────────────────────────────────────────────────


class SensitivityInput(BaseModel):
    rank: SensitivityRank
    input_description: str = Field(..., min_length=1)
    impact_explanation: str = Field(..., min_length=1)
    cluster_weight_shift_mechanic: str = Field(
        ..., min_length=1,
        description="e.g. 'could move cluster Operations from 35% to 50%'",
    )
    affected_cluster_id: Optional[str] = None
    source_citations: List[SourceCitation] = Field(
        default_factory=list,
        description="Citations supporting the numerical claims in shift_mechanic / impact_explanation",
    )


# ─────────────────────────────────────────────────────────────────
# Element 8 — Reflection (Layer 4 of the Solva 5-layer pass)
# ─────────────────────────────────────────────────────────────────


class ReflectionQuestion(BaseModel):
    question_text: str = Field(..., min_length=1)
    user_verbatim_response: str = Field(default="", description="Verbatim user response captured during Layer 4 Reflection.")
    diagnostic_interpretation: str = Field(
        ..., min_length=1,
        description="Engine's 1-3 sentence interpretation, tier-marked",
    )


class ReflectionSection(BaseModel):
    title: str = Field(default="Reflection — what could be wrong, what would change, what to watch")
    intro_copy: str = Field(
        default="Three closing questions. Every diagnosis carries provisional weight.",
    )
    questions: List[ReflectionQuestion] = Field(..., min_length=3, max_length=3)


# ─────────────────────────────────────────────────────────────────
# Element 9 — Pathway / sequenced recommendations
# ─────────────────────────────────────────────────────────────────


class AdversarialCounterCase(BaseModel):
    """Slice 5 (2026-05-29) — Trust pillar 4 (adversarial debate).

    The strongest case AGAINST the targeted conclusion. Rendered as an
    inline callout block on the pathway slide's most critical
    recommendation AND on the decision_logic slide's leading branch.

    Locked constraints (enforced by Slice 5 integrity validators):
      • steel_man_position must be observational (≥80 chars), evidence-
        grounded, NEVER imperative.
      • source_input_ids has ≥2 entries (genuine triangulation, not a
        vague devil's advocate).
      • why_it_matters explains the operating significance of the
        counter-case (≥40 chars, observational).
    """
    targets_conclusion_id: str = Field(
        ...,
        min_length=1,
        description="Identifier linking the counter to the conclusion it targets — typically a pathway number ('pathway-1') or decision branch index ('decision-0')",
    )
    steel_man_position: str = Field(
        ..., min_length=80,
        description="The strongest plausible case against the targeted conclusion — observational, ≥80 chars, evidence-grounded",
    )
    source_input_ids: List[str] = Field(
        ..., min_length=2,
        description="≥2 audit-log / user-turn ids OR coarse layer tags (L0..L4) supporting the counter — triangulation contract",
    )
    why_it_matters: str = Field(
        ..., min_length=40,
        description="Why this counter-case is worth weighing — observational, ≥40 chars",
    )


class PathwayItem(BaseModel):
    number: int = Field(..., ge=1)
    timeline_tag: TimelineTag
    follows_from_cluster_id: Optional[str] = Field(
        None,
        description="Cluster id this recommendation derives from (provenance link)",
    )
    follows_from_cluster_label: Optional[str] = None
    action_heading: str = Field(..., min_length=1)
    detail_paragraph: str = Field(..., min_length=1)
    source_citations: List[SourceCitation] = Field(
        default_factory=list,
        description="Citations supporting any numerical claims in action_heading / detail_paragraph",
    )
    adversarial_counter: Optional[AdversarialCounterCase] = Field(
        None,
        description="Slice 5 — strongest case against this recommendation. Set on the most critical pathway item only.",
    )


# ─────────────────────────────────────────────────────────────────
# Element 10 — Decision logic
# ─────────────────────────────────────────────────────────────────


class DecisionBranch(BaseModel):
    condition: str = Field(..., min_length=1, description="If clause — 'If next quarter's churn rate exceeds X%'")
    conclusion: str = Field(..., min_length=1, description="Then clause — observational, not imperative")
    rationale: str = Field(..., min_length=1)
    adversarial_counter: Optional[AdversarialCounterCase] = Field(
        None,
        description="Slice 5 — strongest case against this branch's conclusion. Set on the leading branch only.",
    )


# ─────────────────────────────────────────────────────────────────
# Element 11 — Risk + mitigation
# ─────────────────────────────────────────────────────────────────


class RiskMitigation(BaseModel):
    risk: str = Field(..., min_length=1)
    mitigation: str = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────────────
# Element 12 — Methodological honesty
# ─────────────────────────────────────────────────────────────────


class MethodologicalHonesty(BaseModel):
    what_report_is: str = Field(..., min_length=1)
    what_report_is_not: str = Field(..., min_length=1)
    provisional_nature_paragraph: str = Field(..., min_length=1)
    input_confidence_pct: int = Field(..., ge=0, le=100)
    not_sole_basis_paragraph: str = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────────────
# Element 13 — In closing
# ─────────────────────────────────────────────────────────────────


class InClosing(BaseModel):
    reframing_paragraph: str = Field(..., min_length=1)
    key_findings_recap: List[str] = Field(default_factory=list, min_length=1)
    final_statement: str = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────────────
# Element 14 — Bias inventory (Slice 4, 2026-05-29) — Trust pillar 2
# ─────────────────────────────────────────────────────────────────
#
# Different from tensions: tensions are framing-vs-evidence contradictions
# explicit in the user's intake. Biases are SYSTEMATIC patterns of
# reasoning that may be coloring the user's interpretation — surfaced
# from evidence in the audit log + the user's verbatim responses, not
# from theatrical pattern-matching. Each named bias must cite ≥1
# source_input_id from the user's actual inputs.


BiasLikelihood = Literal["high", "medium", "low"]


class BiasItem(BaseModel):
    """One named bias entry in the inventory.

    Locked constraints (enforced by Slice 4 integrity validators):
      • bias_name is a snake_case canonical id (e.g. "confirmation_bias",
        "anchoring_bias", "sunk_cost_fallacy", "recency_bias",
        "narrative_fallacy", "availability_heuristic", "optimism_bias",
        "loss_aversion"). Machine-readable.
      • bias_display_name is the human-readable form (e.g. "Confirmation
        bias").
      • likelihood ∈ {high, medium, low}.
      • evidence_grounded_reasoning ≥40 chars, observational (no
        imperative phrasing — uses verbs like "indicates", "suggests",
        "the framing presents", NOT "you should").
      • source_input_ids carries ≥1 entries resolving to real
        audit-log / user-turn ids. Validator confirms resolution.
      • suggested_mitigation, if present, starts with an OBSERVATIONAL
        opener (Seeking / Testing / Consulting / Inviting / Asking)
        — NEVER an imperative ("You should", "You must", "Do X").
    """
    bias_name: str = Field(..., min_length=1, description="Snake_case canonical id")
    bias_display_name: str = Field(..., min_length=1, description="Human-readable form")
    likelihood: BiasLikelihood = Field(..., description="high / medium / low")
    evidence_grounded_reasoning: str = Field(
        ..., min_length=40,
        description="WHY this bias is likely operating, citing specific user inputs",
    )
    source_input_ids: List[str] = Field(
        ..., min_length=1,
        description="≥1 audit-log / user-turn ids that ground this assessment",
    )
    suggested_mitigation: Optional[str] = Field(
        None,
        description="Observational mitigation suggestion (Seeking..., Testing..., Consulting...). NEVER imperative.",
    )


class BiasInventorySection(BaseModel):
    """The Bias Inventory slide payload.

    Slice 4 ships this slide as REQUIRED on every artefact — bias
    inventory is Trust pillar 2 (per user direction). When the engine
    cannot surface any biases (low-evidence sessions), `biases` is
    still emitted with at least 1 entry — the engine's hardest call
    for which bias might be operating, with `likelihood: "low"`
    acknowledging the thin evidence. An empty `biases` list is a real
    bug (caught by the `bias_inventory_present` validator).
    """
    intro_copy: str = Field(
        default="What systematic patterns of reasoning may be shaping the framing. "
                "Each bias below cites the user inputs that triggered it.",
    )
    biases: List[BiasItem] = Field(..., min_length=1, max_length=6)


# ─────────────────────────────────────────────────────────────────
# Element 14b — Pre-mortem (Slice 5, 2026-05-29) — imagined regret
# ─────────────────────────────────────────────────────────────────
#
# "Imagine 12 months from now you regret this pathway. What was the
# most likely failure mode?" Each failure_mode names an evidence-
# grounded way the recommended pathway could fail, the early-warning
# signals that would surface it, and an observational counter-action
# that would shift the risk.


PreMortemFailureKind = Literal[
    "execution_velocity",
    "market_shift",
    "stakeholder_misalignment",
    "data_signal_misread",
    "capability_gap",
    "external_shock",
]


class PreMortemFailureMode(BaseModel):
    """One imagined failure mode in the pre-mortem.

    Locked constraints (enforced by Slice 5 integrity validators):
      • failure_kind ∈ locked enum.
      • failure_narrative ≥80 chars, observational, evidence-grounded.
      • triggering_signals carries ≥1 concrete signal that would
        warn this failure mode is materializing.
      • counter_action, if present, starts with an observational
        opener (Investigating / Monitoring / Strengthening / Pre-
        committing / Surfacing) — NEVER an imperative.
      • source_input_ids carries ≥1 audit-log / user-turn / coarse
        layer tag.
    """
    failure_kind: PreMortemFailureKind = Field(
        ..., description="Locked taxonomy slot",
    )
    failure_narrative: str = Field(
        ..., min_length=80,
        description="Observational narrative of how the pathway fails — ≥80 chars, evidence-grounded",
    )
    triggering_signals: List[str] = Field(
        ..., min_length=1,
        description="≥1 concrete early-warning signals that would surface this failure",
    )
    counter_action: Optional[str] = Field(
        None,
        description="Observational counter-action (Investigating... / Monitoring... / Strengthening...). NEVER imperative.",
    )
    source_input_ids: List[str] = Field(
        ..., min_length=1,
        description="≥1 audit-log / user-turn ids OR coarse layer tags grounding this failure mode",
    )


class PreMortemSlide(BaseModel):
    """The Pre-mortem slide payload.

    Slice 5 ships this slide as REQUIRED on every artefact — pre-
    mortem is Trust pillar 4 (adversarial debate, imagined regret).
    Empty `failure_modes` is a real bug, not an observational outcome.
    """
    intro_copy: str = Field(
        default="Imagine twelve months from now you regret this pathway. "
                "What was the most likely failure mode?",
    )
    failure_modes: List[PreMortemFailureMode] = Field(
        ..., min_length=1, max_length=6,
        description="3-5 typical, 1-6 enforced. Each mode is evidence-grounded and observational.",
    )


# ─────────────────────────────────────────────────────────────────
# Element 15 — Per-slide footer template
# ─────────────────────────────────────────────────────────────────


class FooterTemplate(BaseModel):
    """The Jinja-style template a renderer interpolates per slide.

    Locked template — `{n}` / `{total}` / `{context_name}` substitution
    happens at render time."""
    template: str = Field(
        default="Solva Session Output · Confidential · {context_name} · {n} / {total}",
    )


# ─────────────────────────────────────────────────────────────────
# Root payload
# ─────────────────────────────────────────────────────────────────


class ArtefactPayload(BaseModel):
    """The full slide-payload contract. Renderers consume one
    `ArtefactPayload` per session. Adapter functions (in
    `payload_builder.py`, Slice 1b) build this from a session
    document."""
    model_config = ConfigDict(extra="forbid")

    session_id: str
    schema_version: str = Field(default="solva.v2.artefact.1.0")
    cover: CoverSlide
    headline: HeadlineSlide
    tensions: List[TensionSlide] = Field(default_factory=list)
    per_tension_deep_dive: List[TensionDeepDive] = Field(default_factory=list)
    scenarios: List[ScenarioRow] = Field(default_factory=list)
    per_scenario_confidence_table: PerScenarioConfidenceTable = Field(default_factory=PerScenarioConfidenceTable)
    sensitivity_inputs: List[SensitivityInput] = Field(default_factory=list)
    reflection_section: ReflectionSection
    pathway: List[PathwayItem] = Field(default_factory=list)
    decision_logic: List[DecisionBranch] = Field(default_factory=list)
    risk_mitigation: List[RiskMitigation] = Field(default_factory=list)
    methodological_honesty: MethodologicalHonesty
    in_closing: InClosing
    bias_inventory: BiasInventorySection
    pre_mortem: PreMortemSlide
    footer_template: FooterTemplate = Field(default_factory=FooterTemplate)


__all__ = [
    "ArtefactPayload",
    "CoverSlide",
    "HeadlineSlide",
    "KeyFinding",
    "TensionSlide",
    "TensionDeepDive",
    "EvidenceBlock",
    "ScenarioRow",
    "PerScenarioConfidenceTable",
    "SensitivityInput",
    "ReflectionSection",
    "ReflectionQuestion",
    "PathwayItem",
    "DecisionBranch",
    "RiskMitigation",
    "MethodologicalHonesty",
    "InClosing",
    "BiasInventorySection",
    "BiasItem",
    "BiasLikelihood",
    "AdversarialCounterCase",
    "PreMortemSlide",
    "PreMortemFailureMode",
    "PreMortemFailureKind",
    "FooterTemplate",
    "SourceCitation",
    "SensitivityRank",
    "TimelineTag",
    "TensionSource",
]
