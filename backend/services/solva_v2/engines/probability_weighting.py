"""Solva v2 — probability weighting engine (REAL, Phase 15.1).

Takes the parsed claims[] from the grounding-contract parser and assigns
confidence_pct (0-100) + confidence_band (Unlikely/Possible/Likely/
High-conviction) to each. Single LLM call at standard tier, sub-surface
`solve_v2.probability_weighting`.

Band vocabulary is locked:
    confidence_pct in [0, 35)   -> "Unlikely"
    confidence_pct in [35, 55)  -> "Possible"
    confidence_pct in [55, 75)  -> "Likely"
    confidence_pct in [75, 100] -> "High-conviction"

Invariants enforced after the LLM call:
    every corpus|comparable claim must have confidence_pct >= 35
    every speculation claim must have confidence_pct <= 75

Violations trigger one retry. Second failure logs the mis-calibration in the
audit log but does not block the session — 15.3 styles flagged claims.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("akki.solva_v2.probability_weighting")

ENGINE = "probability_weighting"
ENGINE_VERSION = "probability_weighting@1.0"
SURFACE = "solve_v2.probability_weighting"

MAX_RETRIES = 1

BAND_BREAKPOINTS = [
    (0,  35,  "Unlikely"),
    (35, 55,  "Possible"),
    (55, 75,  "Likely"),
    (75, 101, "High-conviction"),
]

SYSTEM_PROMPT = (
    "You are AKKI Solva's probability-weighting engine. You receive a list "
    "of claims drawn from a synthesis. Each claim already carries a grounding "
    "tier (corpus / comparable / domain_prior / user_assertion / speculation). "
    "Your job is to rate, per claim, how likely it is to be true given the "
    "available evidence.\n\n"
    "OUTPUT contract (strict): a JSON object with key 'ratings', a list one "
    "entry per claim in the SAME ORDER you received them. Each entry has:\n"
    "  - confidence_pct (integer 0-100)\n"
    "  - rationale (one short sentence)\n\n"
    "Rules:\n"
    "  - Use the comparables provided when weighting comparable-tiered claims.\n"
    "  - Speculation-tiered claims should NOT exceed 75.\n"
    "  - Corpus or comparable claims should NOT score below 35 unless the "
    "evidence visibly contradicts them.\n"
    "  - Do NOT add hedging language to rationales beyond the four band "
    "vocabulary words.\n"
    "  - Return JSON only. No prose outside the JSON.\n"
)

_JSON_BLOCK_RE = re.compile(r"\{(?:[^{}]|\{[^{}]*\})*\}", re.DOTALL)


def _band_for(pct: int) -> str:
    for lo, hi, name in BAND_BREAKPOINTS:
        if lo <= pct < hi:
            return name
    return "Possible"  # safety fallback


def _parse_ratings(text: str, expected_count: int) -> Optional[List[Dict[str, Any]]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    parsed: Any = None
    try:
        parsed = json.loads(cleaned)
    except Exception:
        m = _JSON_BLOCK_RE.search(cleaned)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                return None
    if not isinstance(parsed, dict):
        return None
    ratings = parsed.get("ratings")
    if not isinstance(ratings, list) or len(ratings) != expected_count:
        return None
    out: List[Dict[str, Any]] = []
    for r in ratings:
        if not isinstance(r, dict):
            return None
        try:
            pct = int(r.get("confidence_pct"))
        except (TypeError, ValueError):
            return None
        pct = max(0, min(100, pct))
        out.append({
            "confidence_pct": pct,
            "confidence_band": _band_for(pct),
            "rationale": str(r.get("rationale") or "")[:280],
        })
    return out


def _check_invariants(
    claims: List[Dict[str, Any]], ratings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    for i, (c, r) in enumerate(zip(claims, ratings)):
        tier = (c or {}).get("tier")
        pct = r["confidence_pct"]
        if tier in ("corpus", "comparable") and pct < 35:
            violations.append({
                "index": i, "tier": tier, "pct": pct,
                "rule": "corpus_or_comparable_must_be_>=_35",
            })
        elif tier == "speculation" and pct > 75:
            violations.append({
                "index": i, "tier": tier, "pct": pct,
                "rule": "speculation_must_be_<=_75",
            })
    return {"valid": len(violations) == 0, "violations": violations}


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    claims: List[Dict[str, Any]],
    comparables: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Rate every claim. Return updated claims + audit entries."""
    from .llm_adapter_proxy import shielded_call

    if not claims:
        return {"output": {"claims": [], "violations": []}, "audit_entries": []}

    claim_block_lines = []
    for i, c in enumerate(claims):
        claim_block_lines.append(
            f"{i + 1}. [{c.get('tier', '?')}] {c.get('text', '').strip()}"
        )
    claim_block = "\n".join(claim_block_lines)
    comp_block = ""
    if comparables:
        comp_lines = []
        for c in comparables:
            comp_lines.append(
                f"  - {(c.get('diagnosis_summary') or '').strip()}"
            )
        comp_block = ("\n\nComparables for this cluster:\n" + "\n".join(comp_lines))

    base_prompt = (
        "Claims to rate (in order):\n"
        + claim_block
        + comp_block
        + "\n\nReturn the ratings JSON now."
    )

    audit_entries: List[Dict[str, Any]] = []
    final_ratings: Optional[List[Dict[str, Any]]] = None
    invariant_check: Dict[str, Any] = {"valid": False, "violations": []}
    user_query = base_prompt
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
            extra_output={"attempt": attempt + 1, "claim_count": len(claims)},
        )
        audit_entries.append(result.reasoning_audit_entry)
        ratings = _parse_ratings(result.text, len(claims))
        if not ratings:
            audit_entries[-1]["output"]["parse_failed"] = True
            user_query = base_prompt + (
                "\n\nYour previous response failed to parse as the expected JSON. "
                "Re-emit strict JSON, one rating per claim, same order."
            )
            continue
        invariant_check = _check_invariants(claims, ratings)
        audit_entries[-1]["output"]["invariant_valid"] = invariant_check["valid"]
        audit_entries[-1]["output"]["invariant_violations"] = invariant_check["violations"]
        if invariant_check["valid"]:
            final_ratings = ratings
            audit_entries[-1]["tier_labels"] = sorted({c.get("tier") for c in claims if (c or {}).get("tier")})
            break
        # Mismatch — retry once with explicit fix instruction
        user_query = base_prompt + (
            "\n\nYour previous ratings violated tier invariants: "
            + json.dumps(invariant_check["violations"])
            + ". Re-rate. Return JSON only."
        )
        # Keep ratings from this attempt as a fallback if the retry also fails
        final_ratings = ratings

    # If still mis-calibrated after MAX_RETRIES, persist what we have but
    # keep invariant_violations on the audit — 15.3 will style flagged claims.
    weighted_claims: List[Dict[str, Any]] = []
    if final_ratings is None:
        # No usable ratings at all — fall back to neutral mid-band so the
        # session still completes; flag all claims in the audit.
        for c in claims:
            d = dict(c)
            d["confidence_pct"] = 50
            d["confidence_band"] = "Possible"
            d["confidence_rationale"] = "Auto-calibrated: probability_weighting failed to parse twice."
            weighted_claims.append(d)
    else:
        for c, r in zip(claims, final_ratings):
            d = dict(c)
            d["confidence_pct"] = r["confidence_pct"]
            d["confidence_band"] = r["confidence_band"]
            d["confidence_rationale"] = r.get("rationale") or ""
            weighted_claims.append(d)

    output = {
        "claims": weighted_claims,
        "violations": invariant_check.get("violations", []),
        "invariant_valid": invariant_check.get("valid", False),
    }
    return {"output": output, "audit_entries": audit_entries}
