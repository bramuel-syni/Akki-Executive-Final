"""Solva v2 — tension detector engine (Phase 15.2).

Auto-activates inside the Simulate Hypothesis sub-module at the
`hypothesis` layer, BEFORE synthesis. Detects contradictions between:
  - user_vs_corpus           (user assertion contradicts their own corpus)
  - user_vs_comparable       (user assertion contradicts a comparable)
  - comparable_vs_comparable (two comparables disagree)
  - user_vs_user             (user contradicts themselves within session)

HARD INVARIANT (decision #7, single-context only):
    All inputs MUST share the same session_id. The engine asserts this
    explicitly before any LLM call — cross-session input raises
    CrossSessionTensionInputError immediately.

Output shape:
    {
      "tensions": [
        {
          "id": "<uuid>",
          "description": "...one-sentence description...",
          "contradiction_source": "user_vs_comparable",
          "severity": "low|medium|high",
          "evidence": ["...short quoted snippet...", ...]
        }, ...
      ],
      "tension_count": N,
    }
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

log = logging.getLogger("akki.solva_v2.engines.tension_detector")

SURFACE = "solve_v2.tension_detector"
ENGINE_VERSION = "tension_detector@1.0"

VALID_SOURCES = (
    "user_vs_corpus", "user_vs_comparable",
    "comparable_vs_comparable", "user_vs_user",
)
VALID_SEVERITIES = ("low", "medium", "high")


class CrossSessionTensionInputError(Exception):
    """Raised when the detector is fed inputs from more than one session.

    Decision #7: tension detection is single-context only. Cross-context
    detection is blocked behind Phase 14 (Privacy Wall).
    """


def _assert_single_session(session_id: str, *input_lists: List[Dict[str, Any]]) -> None:
    """Hard guard: every input record must carry session_id == session_id.

    Inputs without a session_id field are accepted (they're inline content,
    e.g. user turn text), but any input record that DECLARES a session_id
    must declare THE session_id.
    """
    for input_list in input_lists:
        for record in (input_list or []):
            decl = record.get("session_id") if isinstance(record, dict) else None
            if decl is not None and decl != session_id:
                raise CrossSessionTensionInputError(
                    f"tension_detector refused cross-session input: "
                    f"expected session_id={session_id!r}, got {decl!r}. "
                    f"(Decision #7 \u2014 single-context only.)"
                )


TENSION_PROMPT_TEMPLATE = """You are the tension detector for AKKI Solva. Your job is
to find pairs of statements that contradict each other.

Rules:
- Only flag REAL contradictions, not stylistic differences.
- Each tension must cite its two sources from the INPUT below.
- Classify each tension by source:
    user_vs_corpus, user_vs_comparable, comparable_vs_comparable, user_vs_user
- Severity: low (cosmetic), medium (material), high (load-bearing on diagnosis).
- If you find no real tensions, return {{"tensions": []}}.
- Output STRICT JSON. No prose.

INPUT:
SESSION INTENT:
{intent}

USER TURNS (most recent first, max 6):
{user_turns}

COMPARABLES (from triangulation):
{comparables}

CANDIDATE HYPOTHESES (from candidate_generation):
{candidates}

Return JSON of the form:
{{"tensions": [{{"description": "...", "contradiction_source": "<one_of_4>",
  "severity": "<low|medium|high>", "evidence": ["...", "..."]}}]}}
"""


def _safe_json_load(raw: str) -> Optional[Dict[str, Any]]:
    """Strip code fences and parse JSON. Returns None on failure."""
    if not raw:
        return None
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: locate the first {...} blob
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _normalise_tension(t: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate + normalise a single tension dict from the LLM response."""
    if not isinstance(t, dict):
        return None
    desc = (t.get("description") or "").strip()
    if not desc:
        return None
    src = (t.get("contradiction_source") or "").strip()
    if src not in VALID_SOURCES:
        # Best-effort fallback: classify as user_vs_comparable since that's
        # the most common case during simulate_hypothesis.
        src = "user_vs_comparable"
    sev = (t.get("severity") or "").strip().lower()
    if sev not in VALID_SEVERITIES:
        sev = "medium"
    evidence = t.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = [str(evidence)]
    evidence = [str(e).strip()[:280] for e in evidence if str(e).strip()][:4]
    return {
        "id": str(uuid.uuid4()),
        "description": desc[:400],
        "contradiction_source": src,
        "severity": sev,
        "evidence": evidence,
    }


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    user_turns: List[Dict[str, Any]],
    triangulation_output: Optional[Dict[str, Any]] = None,
    candidate_hypotheses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run the tension detector on the active session's content.

    Returns:
      {
        "output": {"tensions": [...], "tension_count": N},
        "audit_entry": <single audit entry to append>,
      }

    Raises:
      CrossSessionTensionInputError: if any input declares a session_id
        that doesn't match session['id']. Decision #7 hard rule.
    """
    sid = session["id"]
    comparables = (triangulation_output or {}).get("comparables") or []
    candidates = candidate_hypotheses or []

    # ----- HARD GUARD — single-session inputs only -------------------------
    _assert_single_session(sid, user_turns, comparables, candidates)

    # ----- prompt assembly ------------------------------------------------
    intent = (session.get("intent") or "").strip()[:1200]

    user_turns_text = "\n".join(
        f"  - {(t.get('text') or '').strip()[:300]}"
        for t in (list(reversed(user_turns or []))[:6])
        if t.get("role") == "user"
    ) or "  (no user turns)"

    comparables_text = "\n".join(
        f"  - {(c.get('label') or c.get('id') or '?')}: "
        f"{((c.get('thesis') or c.get('summary') or '')[:240])}"
        for c in comparables[:6]
    ) or "  (none)"

    candidates_text = "\n".join(
        f"  - [{c.get('tentative_tier_hint') or 'unknown'}] "
        f"{(c.get('hypothesis') or '')[:240]}"
        for c in candidates[:6]
    ) or "  (none)"

    user_prompt = TENSION_PROMPT_TEMPLATE.format(
        intent=intent,
        user_turns=user_turns_text,
        comparables=comparables_text,
        candidates=candidates_text,
    )

    # ----- shielded LLM call ---------------------------------------------
    # Imported inside the function so test stubs that monkeypatch
    # services.solva_v2.engines.llm_adapter_proxy.shielded_call are picked
    # up at call time. (candidate_generation uses the same pattern.)
    from .llm_adapter_proxy import shielded_call
    SYSTEM_PROMPT = "You are the AKKI Solva tension detector. Output strict JSON."
    result = await shielded_call(
        engine="tension_detector",
        layer="hypothesis",
        turn_id=turn_id,
        prompt=user_prompt,
        system_override=SYSTEM_PROMPT,
        tier="fast",
        surface=SURFACE,
        account_id=session.get("account_id"),
        session_id=session["id"],
        context_id=session.get("context_id"),
        engine_version=ENGINE_VERSION,
    )
    raw_text = result.text or ""
    audit = result.reasoning_audit_entry

    parsed = _safe_json_load(raw_text)
    raw_tensions = ((parsed or {}).get("tensions") or []) if isinstance(parsed, dict) else []
    tensions: List[Dict[str, Any]] = []
    for t in raw_tensions:
        norm = _normalise_tension(t)
        if norm is not None:
            tensions.append(norm)

    output = {
        "tensions": tensions,
        "tension_count": len(tensions),
        "sources_distribution": _sources_distribution(tensions),
    }
    # Persist parsed output on the audit entry so the orchestrator + the
    # synthesis prompt downstream can read it from the audit log.
    audit["output"]["tensions"] = tensions
    audit["output"]["tension_count"] = len(tensions)
    audit["output"]["sources_distribution"] = output["sources_distribution"]
    return {"output": output, "audit_entry": audit}


def _sources_distribution(tensions: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for t in tensions:
        k = t.get("contradiction_source") or "unknown"
        out[k] = out.get(k, 0) + 1
    return out


__all__ = [
    "run",
    "SURFACE",
    "ENGINE_VERSION",
    "CrossSessionTensionInputError",
    "VALID_SOURCES",
    "VALID_SEVERITIES",
]
