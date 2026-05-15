"""Solva v2 reasoning modules (Phase D).

Seven reasoning modules — each calls Synisense Shield with its
declared `solva.layer_*` purpose (pre-declared in `ALLOWED_PURPOSES`
at Phase B). Every module returns a structured Pydantic v2 record.
NO module renders user-facing text; that's the voice renderer's job.

Module → purpose mapping:
  frame_audit_engine         → solva.layer_0.frame_audit
  situation_class_classifier → solva.layer_0.situation_classification
  candidate_generation       → solva.layer_1.candidate_generation
  triangulation_engine       → solva.layer_2.triangulation.{claim_extraction,
                                                            entailment_classification}
  tension_detection          → solva.layer_2.tension_detection
  probability_weighting      → solva.layer_3.scenario_narrative_generation
                              + solva.layer_3.synthesis_rendering
  refusal_logic              → no LLM (deterministic gate)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from services.solva.models import (
    CandidateRecord, FrameAuditRecord, Layer3Record, ScenarioRecord,
    SituationClass, SituationClassRecord, TensionRecord,
    TriangulationClaim,
)
from services.synisense.shield.client import invoke as shield_invoke

log = logging.getLogger("solva.reasoning")


# ─────────────────────────────────────────────────────────────────────
# JSON-blob parser shared across modules.
# ─────────────────────────────────────────────────────────────────────
def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    # Tolerate fenced ```json and prefix/suffix noise.
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def _shield_call(
    *, purpose: str, prompt: str, tenant_id: str, user_id: str,
    timeout_s: float = 20.0,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Routes through Shield, returns (parsed_json, audit_id). Returns
    (None, None) on any failure — caller decides fallback policy."""
    try:
        result = await asyncio.wait_for(
            shield_invoke(
                purpose=purpose, content=prompt,
                tenant_id=tenant_id, consumer_id="solva",
                user_id=user_id, model_preference="analytical",
                internal_caller=True,
            ),
            timeout=timeout_s,
        )
        return _parse_json(result.get("response") or ""), result.get("audit_id")
    except Exception as exc:  # noqa: BLE001
        log.warning("solva reasoning shield call failed: purpose=%s err=%s",
                    purpose, type(exc).__name__)
        return None, None


# ─────────────────────────────────────────────────────────────────────
# 1) Frame Audit Engine.
# ─────────────────────────────────────────────────────────────────────
_FRAME_AUDIT_PROMPT = """\
TASK: Read the user's INITIAL FRAMING below. Score it on three axes
(0.0 – 1.0). Then verdict: thick_enough / thin / refuse.

  framing_thickness_score : how specific is the framing? (vague, generic,
                            buzzword-laden → low; specific, anchored to
                            concrete artefact → high)
  evidence_density_score  : how much of the framing is supported by
                            session evidence vs unsupported claims?
  decision_stakes_score   : how consequential is this decision? (capital,
                            structural, strategic → high)

Also list any surfaced constraints and risk flags.

Verdict semantics:
  thick_enough → proceed to Layer 1 candidate generation.
  thin         → ask the user a clarification question (Layer 1 still runs,
                 but with a thin-framing flag).
  refuse       → evidence is so insufficient that proceeding would mean
                 fabricating analysis; trigger refusal voice.

INITIAL FRAMING:
{framing}

OUTPUT EXACTLY one JSON object, no prose, no markdown fence:
{{"framing_thickness_score": 0.0-1.0,
  "evidence_density_score":  0.0-1.0,
  "decision_stakes_score":   0.0-1.0,
  "has_specific_artefact":   true|false,
  "surfaced_constraints":    ["..."],
  "risk_flags":              ["..."],
  "verdict":                 "thick_enough"|"thin"|"refuse",
  "rationale":               "<= 240 chars, INTERNAL"}}
"""


async def frame_audit(
    *, framing: str, tenant_id: str, user_id: str,
) -> Tuple[Optional[FrameAuditRecord], Optional[str]]:
    parsed, audit_id = await _shield_call(
        purpose="solva.layer_0.frame_audit",
        prompt=_FRAME_AUDIT_PROMPT.format(framing=framing),
        tenant_id=tenant_id, user_id=user_id,
    )
    if not parsed:
        # Deterministic fallback so the pipeline still progresses.
        rec = FrameAuditRecord(
            framing_thickness_score=0.4,
            evidence_density_score=0.3,
            decision_stakes_score=0.5,
            has_specific_artefact=False,
            surfaced_constraints=[],
            risk_flags=["shield_unavailable"],
            verdict="thin",
            rationale="LLM unavailable; defaulted to thin verdict.",
        )
        return rec, audit_id
    try:
        rec = FrameAuditRecord(**parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("frame_audit parse failed: %s", type(exc).__name__)
        return None, audit_id
    return rec, audit_id


# ─────────────────────────────────────────────────────────────────────
# 2) Situation Class Classifier.
# ─────────────────────────────────────────────────────────────────────
_SITUATION_PROMPT = """\
TASK: Classify the user's framing into one of:
  decision_with_evidence     - decisional, has supporting material
  decision_without_evidence  - decisional, missing supporting material
  exploration                - open-ended discovery
  hypothesis_test            - "if X then Y" speculative test
  perspective_seeking        - asking for an opinion / second view
  out_of_scope               - not a strategic decision at all

FRAMING: {framing}

OUTPUT EXACTLY one JSON object:
{{"classification":"<one of above>","confidence":0.0-1.0,"rationale":"<= 240 chars"}}
"""


async def situation_classification(
    *, framing: str, tenant_id: str, user_id: str,
) -> Tuple[Optional[SituationClassRecord], Optional[str]]:
    parsed, audit_id = await _shield_call(
        purpose="solva.layer_0.situation_classification",
        prompt=_SITUATION_PROMPT.format(framing=framing),
        tenant_id=tenant_id, user_id=user_id,
    )
    if not parsed:
        rec = SituationClassRecord(
            classification="decision_without_evidence",
            confidence=0.4,
            rationale="LLM unavailable; defaulted.",
        )
        return rec, audit_id
    try:
        rec = SituationClassRecord(**parsed)
    except Exception:  # noqa: BLE001
        return None, audit_id
    return rec, audit_id


# ─────────────────────────────────────────────────────────────────────
# 3) Candidate Generation (Layer 1).
# ─────────────────────────────────────────────────────────────────────
_CANDIDATE_PROMPT = """\
TASK: Produce 3 DISTINCT candidate framings of the user's question.
Each candidate must represent a genuinely different angle (different
axis of consideration, NOT three rewordings of the same thought).

USER FRAMING:
{framing}

SUB-MODULE: {sub_module}

OUTPUT EXACTLY one JSON object:
{{"candidates":[
  {{"label":"<5-8 words>","description":"<= 240 chars","distinct_axis":"<what axis>"}},
  {{"label":"...","description":"...","distinct_axis":"..."}},
  {{"label":"...","description":"...","distinct_axis":"..."}}
]}}
"""


async def candidate_generation(
    *, framing: str, sub_module: str, tenant_id: str, user_id: str,
) -> Tuple[Optional[List[CandidateRecord]], Optional[str]]:
    parsed, audit_id = await _shield_call(
        purpose="solva.layer_1.candidate_generation",
        prompt=_CANDIDATE_PROMPT.format(framing=framing, sub_module=sub_module),
        tenant_id=tenant_id, user_id=user_id,
    )
    if not parsed:
        # Deterministic 3-candidate fallback so the state machine
        # doesn't stall.
        cs = [
            CandidateRecord(label="Strategic angle",
                            description="Consider this as a strategic positioning question.",
                            distinct_axis="positioning"),
            CandidateRecord(label="Operational angle",
                            description="Consider this as an execution / delivery question.",
                            distinct_axis="execution"),
            CandidateRecord(label="Stakeholder angle",
                            description="Consider this through the lens of key stakeholders.",
                            distinct_axis="stakeholders"),
        ]
        return cs, audit_id
    try:
        cs = [CandidateRecord(**c) for c in (parsed.get("candidates") or [])][:3]
    except Exception:  # noqa: BLE001
        return None, audit_id
    return cs if cs else None, audit_id


# ─────────────────────────────────────────────────────────────────────
# 4) Triangulation Engine (Layer 2) — 2 Shield calls.
# ─────────────────────────────────────────────────────────────────────
_CLAIM_EXTRACTION_PROMPT = """\
TASK: From the user's running framing + their answers below, extract
the load-bearing claims. For each, classify the source as:
  session_evidence  - explicitly grounded in the session materials
  general_practice  - industry/general-practice reference
  unknown           - unclear provenance

USER FRAMING:
{framing}

USER ANSWERS (Layer 1):
{answers}

OUTPUT EXACTLY one JSON object:
{{"claims":[
  {{"claim":"<short>","source_type":"session_evidence|general_practice|unknown",
    "confidence":0.0-1.0}},
  ...
]}}
At most 6 claims.
"""


_ENTAILMENT_PROMPT = """\
TASK: For each claim below, decide whether it SUPPORTS, CONTRADICTS,
or is TANGENTIAL to the load-bearing framing.

FRAMING: {framing}

CLAIMS:
{claims_json}

OUTPUT EXACTLY one JSON object:
{{"entailments":[
  {{"claim":"<verbatim>","entailment":"supports|contradicts|tangential"}},
  ...
]}}
"""


async def triangulation(
    *, framing: str, layer_1_answers: List[Dict[str, Any]],
    tenant_id: str, user_id: str,
) -> Tuple[List[TriangulationClaim], List[str]]:
    """Two-stage triangulation. Returns (claims, [audit_id_a, audit_id_b])."""
    answers_text = "\n".join(
        f"- Q: {a.get('question')}\n  A: {a.get('answer')}"
        for a in layer_1_answers
    )
    audit_ids: List[str] = []
    parsed_a, audit_id_a = await _shield_call(
        purpose="solva.layer_2.triangulation.claim_extraction",
        prompt=_CLAIM_EXTRACTION_PROMPT.format(framing=framing, answers=answers_text),
        tenant_id=tenant_id, user_id=user_id,
    )
    if audit_id_a:
        audit_ids.append(audit_id_a)
    claims_raw = (parsed_a or {}).get("claims") or []
    if not claims_raw:
        return [], audit_ids
    parsed_b, audit_id_b = await _shield_call(
        purpose="solva.layer_2.triangulation.entailment_classification",
        prompt=_ENTAILMENT_PROMPT.format(
            framing=framing,
            claims_json=json.dumps([{"claim": c.get("claim")} for c in claims_raw]),
        ),
        tenant_id=tenant_id, user_id=user_id,
    )
    if audit_id_b:
        audit_ids.append(audit_id_b)
    entailment_map = {
        e["claim"]: e["entailment"]
        for e in ((parsed_b or {}).get("entailments") or [])
        if e.get("claim")
    }
    out: List[TriangulationClaim] = []
    for c in claims_raw:
        try:
            out.append(TriangulationClaim(
                claim=c["claim"],
                source_type=c.get("source_type") or "unknown",
                entailment=entailment_map.get(c["claim"]) or "tangential",
                confidence=float(c.get("confidence") or 0.5),
            ))
        except Exception:  # noqa: BLE001
            continue
    return out, audit_ids


# ─────────────────────────────────────────────────────────────────────
# 5) Tension Detection (Layer 2) — basic; auto-activation is Phase E.
# ─────────────────────────────────────────────────────────────────────
_TENSION_PROMPT = """\
TASK: List up to 3 tensions or trade-offs implicit in the framing
and the user's answers below. A tension = "X and Y both matter but
cannot be fully satisfied together".

FRAMING: {framing}
ANSWERS: {answers}

OUTPUT EXACTLY one JSON object:
{{"tensions":[
  {{"axis":"<short>","severity":"low|medium|high","description":"<= 200 chars"}}
]}}
"""


async def tension_detection(
    *, framing: str, layer_1_answers: List[Dict[str, Any]],
    tenant_id: str, user_id: str,
) -> Tuple[List[TensionRecord], Optional[str]]:
    answers_text = "\n".join(
        f"Q: {a.get('question')} | A: {a.get('answer')}"
        for a in layer_1_answers
    )
    parsed, audit_id = await _shield_call(
        purpose="solva.layer_2.tension_detection",
        prompt=_TENSION_PROMPT.format(framing=framing, answers=answers_text),
        tenant_id=tenant_id, user_id=user_id,
    )
    if not parsed:
        return [], audit_id
    out: List[TensionRecord] = []
    for t in (parsed.get("tensions") or []):
        try:
            out.append(TensionRecord(**t))
        except Exception:  # noqa: BLE001
            continue
    return out, audit_id


# ─────────────────────────────────────────────────────────────────────
# 6) Probability Weighting + Synthesis (Layer 3) — 2 Shield calls.
# ─────────────────────────────────────────────────────────────────────
_SCENARIO_PROMPT = """\
TASK: Produce 3 scenarios that cover the plausible outcome space of
the user's decision. Probabilities MUST sum to ~1.0. Each scenario
needs an upside band, a downside band, a leading indicator (one
specific observable that would tell us we're in this scenario), and
a 2-3 sentence narrative in coach voice (empathetic, restrained,
conversational; no buzzwords).

FRAMING: {framing}
TRIANGULATION CLAIMS:
{claims}
TENSIONS:
{tensions}

OUTPUT EXACTLY one JSON object:
{{"scenarios":[
  {{"name":"<short>","probability":0.0-1.0,"upside_band":"<short>",
    "downside_band":"<short>","leading_indicator":"<short>",
    "narrative":"<= 360 chars in coach voice"}},
  ...
]}}
"""


_SYNTHESIS_PROMPT = """\
TASK: Write the coach-voice synthesis paragraph that closes this
reasoning session. ONE paragraph. 4-7 sentences. Coach voice:
empathetic, restrained, conversational. Anchor specific phrases in
the user's framing. Surface the load-bearing tension if there is one.
NEVER fabricate facts not in the inputs.

FRAMING: {framing}
SCENARIOS: {scenarios_json}
TRIANGULATION: {triangulation_json}

OUTPUT EXACTLY one JSON object:
{{"synthesis":"<the paragraph>",
  "evidence_trace":["<short bullet>","<short bullet>","<short bullet>"]}}

NO JSON inside the synthesis. NO field names. NO bullet points inside
the synthesis. NO opening "Let me synthesise" — just begin.
"""


async def probability_weighting_and_synthesis(
    *, framing: str, claims: List[TriangulationClaim],
    tensions: List[TensionRecord], tenant_id: str, user_id: str,
) -> Tuple[Optional[Layer3Record], List[str]]:
    audit_ids: List[str] = []
    parsed_a, audit_id_a = await _shield_call(
        purpose="solva.layer_3.scenario_narrative_generation",
        prompt=_SCENARIO_PROMPT.format(
            framing=framing,
            claims=json.dumps([c.model_dump() for c in claims]),
            tensions=json.dumps([t.model_dump() for t in tensions]),
        ),
        tenant_id=tenant_id, user_id=user_id,
    )
    if audit_id_a:
        audit_ids.append(audit_id_a)
    scenarios: List[ScenarioRecord] = []
    for s in ((parsed_a or {}).get("scenarios") or []):
        try:
            scenarios.append(ScenarioRecord(**s))
        except Exception:  # noqa: BLE001
            continue
    if not scenarios:
        return None, audit_ids

    parsed_b, audit_id_b = await _shield_call(
        purpose="solva.layer_3.synthesis_rendering",
        prompt=_SYNTHESIS_PROMPT.format(
            framing=framing,
            scenarios_json=json.dumps([s.model_dump() for s in scenarios]),
            triangulation_json=json.dumps([c.model_dump() for c in claims]),
        ),
        tenant_id=tenant_id, user_id=user_id,
    )
    if audit_id_b:
        audit_ids.append(audit_id_b)
    synth_text = (parsed_b or {}).get("synthesis") or ""
    if not synth_text or len(synth_text) < 80:
        # Deterministic coach-voice fallback synthesis built from
        # scenario narratives so the user still gets a closing paragraph.
        synth_text = (
            "Stepping back across what you've shared: " +
            " ".join(s.narrative for s in scenarios)[:600]
        )
    trace = (parsed_b or {}).get("evidence_trace") or []
    if not isinstance(trace, list):
        trace = []
    return Layer3Record(
        scenarios=scenarios,
        synthesis_paragraph=synth_text,
        evidence_trace=[str(t)[:200] for t in trace][:5],
    ), audit_ids


# ─────────────────────────────────────────────────────────────────────
# 7) Refusal Logic — deterministic gate (NO LLM).
# ─────────────────────────────────────────────────────────────────────
def should_refuse(
    *, frame_audit: FrameAuditRecord, situation: SituationClassRecord,
) -> Optional[str]:
    """Returns a refusal reason if Solva should REFUSE rather than
    proceed; None to continue. Deterministic — no LLM call (so no
    Shield audit row generated; refusal voice composition is its own
    Shield purpose called only if the user wants the refusal explained)."""
    if situation.classification == "out_of_scope":
        return "out_of_scope"
    if frame_audit.verdict == "refuse":
        return "evidence_insufficient"
    # Hard gate: both decision-stakes high AND evidence-density very low.
    if (frame_audit.decision_stakes_score >= 0.7
            and frame_audit.evidence_density_score < 0.2):
        return "high_stakes_low_evidence"
    return None
