"""Solva v2 sub-module registry (Phase 15.2).

Four sub-modules share the orchestrator, the four real engines, the
grounding contract, and the validator. Each sub-module owns:
  - a `framing_voice` (one-line system-prompt header)
  - a `synthesis_voice` (system-prompt header for synthesis)
  - optional layer hooks (e.g. simulate_hypothesis adds a hypothesis layer)
  - optional output post-processing (e.g. develop_strategy emits
    recommendations[] alongside claims[])

The orchestrator dispatches by `session.submodule` string. Backwards
compat: missing/None submodule → seek_clarity (15.1 default).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

SUBMODULE_NAMES = (
    "seek_clarity", "develop_strategy", "simulate_hypothesis", "get_perspective",
)


def _seek_clarity_voice(layer: str) -> str:
    return (
        "You are AKKI Solva \u2014 a structured-pause facilitator for board-grade "
        "problems. Sub-module: SEEK CLARITY. You walk the user one layer at a "
        "time and ask the questions a sharp counterpart would ask. You DIAGNOSE; "
        "you do not prescribe."
    )


def _develop_strategy_voice(layer: str) -> str:
    if layer == "synthesis":
        return (
            "You are AKKI Solva \u2014 sub-module: DEVELOP STRATEGY. Your job at "
            "this layer is to RECOMMEND a course of action grounded in the "
            "established diagnosis. Where Seek Clarity stops at the question, "
            "Develop Strategy answers it: state 2\u20134 specific recommendations "
            "with their evidence tier markers and a confidence band. Each "
            "recommendation should be testable, owner-assignable, and "
            "timeline-bounded."
        )
    return (
        "You are AKKI Solva \u2014 sub-module: DEVELOP STRATEGY. You are working "
        "toward an actionable recommendation. At this layer, surface the levers "
        "available and the constraints that bound them."
    )


def _simulate_hypothesis_voice(layer: str) -> str:
    if layer == "hypothesis":
        return (
            "You are AKKI Solva \u2014 sub-module: SIMULATE HYPOTHESIS. At this "
            "layer you expand the user's hypothesis into 2\u20133 plausible "
            "scenarios, each with second-order effects (what changes downstream, "
            "who is affected, what evidence would confirm vs falsify). Surface "
            "tensions between scenarios explicitly. Do NOT pick the winner yet \u2014 "
            "that is synthesis's job."
        )
    if layer == "synthesis":
        return (
            "You are AKKI Solva \u2014 sub-module: SIMULATE HYPOTHESIS. You have "
            "the scenarios from the hypothesis layer and the tensions detected "
            "between them. Pick the most defensible scenario and explain why, "
            "acknowledging the tensions explicitly (e.g. 'Note the tension "
            "between user assumption A and comparable C\u2026'). State the "
            "diagnosis with tier markers as usual."
        )
    return (
        "You are AKKI Solva \u2014 sub-module: SIMULATE HYPOTHESIS. You are working "
        "toward picking the most defensible scenario for a 'what-if' question."
    )


def _get_perspective_voice(layer: str, persona: str = "") -> str:
    persona = (persona or "").strip() or "a fellow non-executive director"
    if layer == "synthesis":
        return (
            f"You are AKKI Solva \u2014 sub-module: GET PERSPECTIVE. Synthesis "
            f"is written IN THE VOICE of: {persona}. Use first-person where "
            f"natural. Stay grounded \u2014 tier markers still required \u2014 but "
            f"adopt the diction, priorities, and challenge style of the persona. "
            f"Do not break character. The validator will independently judge "
            f"whether the diagnosis is sound regardless of voice."
        )
    return (
        "You are AKKI Solva \u2014 sub-module: GET PERSPECTIVE. You are gathering "
        "what the chosen persona would prioritise. Probe accordingly."
    )


def voice_for(submodule: str, layer: str, persona: Optional[str] = None) -> str:
    """Return the system-prompt voice header for a (submodule, layer) pair.

    Backwards compat: unknown / None submodule falls back to seek_clarity.
    """
    if submodule == "develop_strategy":
        return _develop_strategy_voice(layer)
    if submodule == "simulate_hypothesis":
        return _simulate_hypothesis_voice(layer)
    if submodule == "get_perspective":
        return _get_perspective_voice(layer, persona or "")
    return _seek_clarity_voice(layer)


def parse_recommendations_from_synthesis(text: str) -> List[Dict[str, Any]]:
    """Phase 15.2 \u2014 develop_strategy synthesis post-processing.

    Walks the synthesis text and pulls out lines starting with
    'Recommendation N:' / numbered bullets / markdown-bolded variants.
    Returns a list of `{text, ordinal}` dicts. Confidence bands are
    populated by the probability_weighting engine downstream \u2014 this
    function only extracts the textual recommendations.

    Phase B.1 (2026-05-10) \u2014 the regex now accepts the markdown-bold
    forms the synthesis layer actually emits in production:
      **Recommendation 1:** ...
      **Recommendation:** ...
      __Recommendation 1:__ ...
    The previous form `[*\\-]\\s+` only caught single-asterisk bullets
    and matched zero of the bolded \"**Recommendation N:**\" lines real
    Solva sessions produce, leaving `synthesis.recommendations = []`
    on every develop_strategy artefact.
    """
    import re

    if not text:
        return []
    out: List[Dict[str, Any]] = []
    lines = text.splitlines()
    current: List[str] = []
    ordinal = 0
    # Match any of:
    #   "Recommendation: ...", "Recommendation 1: ...", "Recommendation 2 \u2014 ..."
    #   "1) ...", "1. ..."
    # Optionally preceded by:
    #   - markdown bullet (* or -) + space
    #   - markdown bold (** or __) which may also wrap the ": " (e.g.
    #     "**Recommendation 1:**" \u2014 trailing ** stripped from group 1).
    pattern = re.compile(
        r"^\s*(?:[*\-]\s+)?"                   # optional bullet
        r"(?:\*\*|__)?\s*"                     # optional opening bold
        r"(?:Recommendation\s*\d*\s*[:\u2014]" # "Recommendation 1:" or em-dash variant
        r"|\d+[\.\)]\s+)"                      # OR numeric list "1." / "1)"
        r"(?:\*\*|__)?\s*"                     # optional closing bold (e.g. **Rec 1:**)
        r"(.*)$",
        re.IGNORECASE,
    )
    # Strip a trailing markdown-bold pair from the captured tail (handles
    # the "**Recommendation 1:** body **trailing**" rare case).
    strip_trailing_bold = re.compile(r"\*\*\s*$|__\s*$")

    def flush():
        nonlocal current, ordinal
        if current:
            ordinal += 1
            joined = " ".join(current).strip()
            joined = strip_trailing_bold.sub("", joined).strip()
            out.append({"ordinal": ordinal, "text": joined})
            current = []

    for line in lines:
        m = pattern.match(line)
        if m:
            flush()
            current = [m.group(1).strip()]
        elif line.strip() and current:
            current.append(line.strip())
        else:
            flush()
    flush()
    return out


def expects_recommendations(submodule: str) -> bool:
    return submodule == "develop_strategy"


def expects_hypothesis_layer(submodule: str) -> bool:
    return submodule == "simulate_hypothesis"


def expects_persona_at_intake(submodule: str) -> bool:
    return submodule == "get_perspective"


__all__ = [
    "SUBMODULE_NAMES",
    "voice_for",
    "parse_recommendations_from_synthesis",
    "expects_recommendations",
    "expects_hypothesis_layer",
    "expects_persona_at_intake",
]
