"""Solva v2 — candidate generation engine (REAL, Phase 15.1).

Runs between framing and grounding. Generates 2-4 candidate diagnostic
framings of the user's intent, each as a one-sentence hypothesis. Each
candidate carries a tentative_tier_hint so downstream layers can route
evidence-gathering: hint='comparable' keeps triangulation honest;
hint='domain_prior'/'speculation' tells synthesis where weight will fall.

LLM call routed via the shielded adapter at sub-surface
`solve_v2.candidate_generation`. After generation, a single validator pass
checks that the candidates are distinct, non-trivial, and responsive to the
user's intent. One retry on rejection; second rejection surfaces a
structured error.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("akki.solva_v2.candidate_generation")

ENGINE = "candidate_generation"
ENGINE_VERSION = "candidate_generation@1.0"
SURFACE = "solve_v2.candidate_generation"

SYSTEM_PROMPT = (
    "You are AKKI Solva's candidate-framing engine. Given a user's intent on "
    "a board-grade question, your job is to surface 2-4 distinct framings "
    "that the synthesis layer will weigh.\n\n"
    "Each framing must be:\n"
    "  - One sentence, declarative, no hedging.\n"
    "  - Genuinely distinct \u2014 not paraphrases of each other.\n"
    "  - Responsive to the user's intent, not generic boardroom platitudes.\n"
    "  - Tagged with tentative_tier_hint, one of: corpus, comparable, "
    "domain_prior, speculation. The hint says where you expect the\n"
    "    grounding for that framing to come from.\n\n"
    "Return STRICT JSON, schema:\n"
    "  {\n"
    "    \"candidates\": [\n"
    "      {\"hypothesis\": \"...\", \"tentative_tier_hint\": \"comparable\"},\n"
    "      ...\n"
    "    ]\n"
    "  }\n"
    "No prose outside the JSON. Do not invent tier names.\n"
)

VALID_HINTS = {"corpus", "comparable", "domain_prior", "speculation"}

MAX_RETRIES = 1  # one retry on validator rejection

_JSON_BLOCK_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.DOTALL)


def _parse_candidates(text: str) -> List[Dict[str, Any]]:
    """Best-effort JSON extraction. Tolerates fenced ``` blocks."""
    if not text:
        return []
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    # First try strict JSON, fall back to regex match.
    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(cleaned)
    except Exception:
        m = _JSON_BLOCK_RE.search(cleaned)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None
    if not isinstance(parsed, dict):
        return []
    cands = parsed.get("candidates")
    if not isinstance(cands, list):
        return []
    out: List[Dict[str, Any]] = []
    for c in cands:
        if not isinstance(c, dict):
            continue
        hyp = (c.get("hypothesis") or "").strip()
        hint = (c.get("tentative_tier_hint") or "").strip()
        if not hyp:
            continue
        if hint not in VALID_HINTS:
            hint = "domain_prior"  # safe fallback; validator will catch shape issues
        out.append({
            "id": str(uuid.uuid4()),
            "hypothesis": hyp,
            "tentative_tier_hint": hint,
        })
    return out


def _candidates_distinct(candidates: List[Dict[str, Any]]) -> bool:
    seen: set = set()
    for c in candidates:
        key = re.sub(r"\s+", " ", (c.get("hypothesis") or "").lower()).strip()
        if not key or key in seen:
            return False
        seen.add(key)
    return True


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    intent: str,
    cluster: Dict[str, Any],
    comparables: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate candidate framings via shielded LLM call. Validator pass.

    Returns {output: {candidates: [...]}, audit_entry: {...}, audit_extras: [...]}
    where audit_extras carries any retry attempts so the orchestrator can
    append the full picture.
    """
    from .llm_adapter_proxy import shielded_call, synthetic_audit_entry

    user_query = (
        f"User intent:\n{intent}\n\n"
        f"Cluster: {cluster.get('label', '?')}\n"
        "Generate 2-4 distinct candidate framings now. Strict JSON only."
    )

    audit_entries: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    last_validator_verdict: Optional[str] = None

    for attempt in range(MAX_RETRIES + 1):
        result = await shielded_call(
            engine=ENGINE,
            layer=layer,
            turn_id=turn_id,
            prompt=user_query,
            system_override=SYSTEM_PROMPT,
            tier="standard",
            surface=SURFACE,
            account_id=session.get("account_id"),
            session_id=session["id"],
            context_id=session.get("context_id"),
            engine_version=ENGINE_VERSION,
            extra_output={"attempt": attempt + 1},
        )
        audit_entries.append(result.reasoning_audit_entry)

        candidates = _parse_candidates(result.text)
        # Lightweight validator: distinctness + count bounds + responsiveness
        # via word overlap with the intent.
        distinct = _candidates_distinct(candidates)
        in_bounds = 2 <= len(candidates) <= 4
        intent_words = {w.lower() for w in re.findall(r"\w+", intent or "") if len(w) > 3}
        responsive = True
        if intent_words:
            for c in candidates:
                cand_words = {w.lower() for w in re.findall(r"\w+", c["hypothesis"]) if len(w) > 3}
                if not (cand_words & intent_words):
                    responsive = False
                    break

        verdict = "accepted" if (distinct and in_bounds and responsive) else "rejected"
        last_validator_verdict = verdict
        audit_entries[-1]["output"]["validator_verdict"] = verdict
        audit_entries[-1]["output"]["distinct"] = distinct
        audit_entries[-1]["output"]["in_bounds"] = in_bounds
        audit_entries[-1]["output"]["responsive"] = responsive
        audit_entries[-1]["output"]["candidate_count"] = len(candidates)

        if verdict == "accepted":
            audit_entries[-1]["tier_labels"] = sorted({c["tentative_tier_hint"] for c in candidates})
            break
        # Otherwise retry with stronger framing
        user_query = (
            user_query
            + "\n\nYour previous attempt was rejected by the validator. "
            "Issues: "
            + (", ".join(
                (["non-distinct"] if not distinct else [])
                + (["count out of bounds (must be 2-4)"] if not in_bounds else [])
                + (["not responsive to the user intent"] if not responsive else [])
            ) or "unspecified")
            + ". Re-emit. Strict JSON only."
        )

    if last_validator_verdict != "accepted":
        return {
            "violation": True,
            "reason": "candidate_generation_validator_rejected",
            "last_attempt_count": len(candidates),
            "audit_entries": audit_entries,
        }

    output = {"candidates": candidates, "candidate_count": len(candidates)}
    return {
        "violation": False,
        "output": output,
        "audit_entries": audit_entries,
    }
