"""Solva v2 — Phase 15.3 Reflection layer.

Three locked questions that close every Solva session. Each question gets
its own LLM-generated 1–3 sentence response, tier-marked per the existing
grounding contract, validator-checked, and emitted as a separate audit
entry under engine='reflection'.

Locked questions (per Phase 15.3 decision #14):
  1. What could be wrong about this diagnosis?
  2. What would change the answer in 30 days?
  3. What is the first sign you should watch for?

Each response uses the same shielded LLM adapter as synthesis,
sub-surface `solve_v2.reflection`, tier=fast (cheap; the questions are
narrow and the synthesis already did the heavy lifting). Each response
is parsed for tier markers; we do not retry on contract failure here —
a single attempt is enough because the reflection prompt is highly
constrained. If a response fails parsing it is recorded with
`grounding_accepted=False` in the audit entry but the layer continues.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("akki.solva_v2.reflection")

ENGINE = "reflection"
ENGINE_VERSION = "reflection@1.0"
SURFACE = "solve_v2.reflection"

LOCKED_QUESTIONS: List[str] = [
    "What could be wrong about this diagnosis?",
    "What would change the answer in 30 days?",
    "What is the first sign you should watch for?",
]


def build_system_prompt(intent: str, synthesis_body: str) -> str:
    return (
        "You are AKKI Solva at the REFLECTION layer. The diagnosis has "
        "already been written. Your job is to answer ONE focused reflection "
        "question about it in 1–3 sentences, no more.\n\n"
        f"Original intent: {intent}\n\n"
        f"Diagnosis (synthesis body, already validator-passed):\n"
        f"---\n{synthesis_body}\n---\n\n"
        "OUTPUT RULES:\n"
        "  * 1 to 3 sentences total.\n"
        "  * Every assertive sentence MUST end with exactly one tier marker "
        "in square brackets, e.g. '… [T:corpus]', '… [T:comparable]', "
        "'… [T:domain_prior]', '… [T:user_assertion]', '… [T:speculation]'.\n"
        "  * Pick the tier that honestly describes where the claim is grounded:\n"
        "      corpus           — anchored in the user's own documents (rare here).\n"
        "      comparable       — anchored in a named comparable diagnosis.\n"
        "      domain_prior     — anchored in widely-held domain knowledge.\n"
        "      user_assertion   — re-stating what the user said.\n"
        "      speculation      — your judgement, not directly grounded.\n"
        "  * Be honest. Reflection is the place where speculation is "
        "    welcome — name it as such.\n"
        "  * Do NOT repeat the diagnosis. Address the reflection question only.\n"
    )


async def run_one(
    *,
    session: Dict[str, Any],
    turn_id: str,
    question: str,
    question_index: int,
    intent: str,
    synthesis_body: str,
    account_id: str,
) -> Dict[str, Any]:
    """Run ONE reflection question. Returns audit entry + parsed result."""
    from ..llm_adapter import shielded_call
    from ..grounding_contract import parse, summarise_tier_distribution

    sys_prompt = build_system_prompt(intent, synthesis_body)
    user_prompt = (
        f"Reflection question #{question_index + 1} of 3:\n"
        f"  {question}\n\n"
        "Answer the question now in 1–3 sentences. Tag every assertive "
        "sentence with exactly one tier marker."
    )
    result = await shielded_call(
        engine=ENGINE,
        layer="reflection",
        turn_id=turn_id,
        prompt=user_prompt,
        system_override=sys_prompt,
        tier="fast",
        surface=SURFACE,
        account_id=account_id,
        session_id=session["id"],
        context_id=session.get("context_id"),
        engine_version=ENGINE_VERSION,
        run_validator=False,
        extra_output={
            "reflection_question_index": question_index,
            "reflection_question": question,
        },
    )
    parsed = parse(result.text)
    audit = result.reasoning_audit_entry
    audit["output"]["reflection_question"] = question
    audit["output"]["reflection_question_index"] = question_index
    audit["output"]["grounding_accepted"] = bool(parsed.valid)
    audit["output"]["claim_count"] = len(parsed.claims)
    audit["output"]["untagged_count"] = len(parsed.untagged_sentences)
    audit["output"]["malformed_count"] = len(parsed.malformed_markers)
    audit["tier_labels"] = sorted({c.tier for c in parsed.claims})

    return {
        "audit_entry": audit,
        "question": question,
        "question_index": question_index,
        "raw_text": result.text,
        "stripped_text": parsed.stripped_text,
        "claims": [c.to_dict() for c in parsed.claims],
        "tier_distribution": summarise_tier_distribution(parsed.claims),
        "grounding_accepted": parsed.valid,
        "model": result.model,
        "tier": result.tier_served,
    }


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    intent: str,
    synthesis_body: str,
    account_id: str,
) -> Dict[str, Any]:
    """Run all three reflection questions in sequence.

    Returns:
      {
        "responses": [ {question, question_index, raw_text, stripped_text,
                        claims, tier_distribution, grounding_accepted}, ... ],
        "audit_entries": [audit, audit, audit],
        "body": "...stitched user-visible text...",
        "model": last_model_seen,
        "tier": last_tier_seen,
      }
    """
    audit_entries: List[Dict[str, Any]] = []
    responses: List[Dict[str, Any]] = []
    last_model = None
    last_tier = None
    for idx, q in enumerate(LOCKED_QUESTIONS):
        r = await run_one(
            session=session,
            turn_id=turn_id,
            question=q,
            question_index=idx,
            intent=intent,
            synthesis_body=synthesis_body,
            account_id=account_id,
        )
        audit_entries.append(r["audit_entry"])
        responses.append({k: v for k, v in r.items() if k != "audit_entry"})
        last_model = r["model"]
        last_tier = r["tier"]

    # Stitched body for the user-facing turn message.
    body_parts = []
    for r in responses:
        body_parts.append(f"**{r['question']}**")
        body_parts.append(r["raw_text"].strip())
        body_parts.append("")
    body = "\n".join(body_parts).strip()

    return {
        "responses": responses,
        "audit_entries": audit_entries,
        "body": body,
        "model": last_model,
        "tier": last_tier,
    }


__all__ = [
    "ENGINE", "ENGINE_VERSION", "SURFACE",
    "LOCKED_QUESTIONS", "build_system_prompt",
    "run_one", "run",
]
