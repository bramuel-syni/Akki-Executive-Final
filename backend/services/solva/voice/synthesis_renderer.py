"""Synthesis renderer — converts internal reasoning artefacts into
coach-voice user-facing prose.

This is the ONE place where Layer 3 user content is produced. The
function consumes the (internal) probability weighting output +
triangulation divergences + carry-forward caveats and renders an
editorial-cadence synthesis paragraph.

CRITICAL invariant: NO internal artefact terminology (FAR, candidate,
triangulation, frame audit, scenario weight, dimension, etc.) appears
in the output. Locked by `voice.invariants.scan_for_internal_artefacts`.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# Strip layer references and Markdown field labels from any string
# that originated in the reasoning tier before it reaches the user.
_LAYER_REF_RE = re.compile(r"\b(layer[\s_]?[0-9]+|in the layer\s+[0-9]+)\b", re.I)
_MARKDOWN_LABEL_RE = re.compile(r"\*{2}[^*]{1,40}\*{2}\s*:?\s*", re.I)
_LEADING_LABEL_RE = re.compile(r"^\s*[A-Z][a-z]+(\s+[A-Za-z]+){0,2}\s*:\s+", re.I)
_INTERNAL_TERMS_RE = re.compile(
    r"\b(frame audit|candidate set|triangulation result|audit_?id|"
    r"dimension score|calibration version|synisense audit)\b",
    re.I,
)


def _sanitize_internal_string(text: str) -> str:
    """Strip reasoning-tier artefact vocabulary from a string that
    might originate from an LLM response. Preserves the substantive
    content; removes the engineering scaffolding."""
    if not text:
        return ""
    t = _MARKDOWN_LABEL_RE.sub("", text)
    t = _LAYER_REF_RE.sub("the framing", t)
    t = _INTERNAL_TERMS_RE.sub("the read", t)
    # Drop a leading "Word:" label like "Description: ...".
    t = _LEADING_LABEL_RE.sub("", t)
    # Collapse repeated whitespace.
    t = re.sub(r"\s+", " ", t).strip(" -.:;")
    return t


def _pct(weight: float) -> str:
    return f"{int(round(weight * 100))}%"


def _interval(low: float, high: float) -> str:
    return f"{int(round(low * 100))}–{int(round(high * 100))}%"


def render_acknowledgement(
    *, sub_module: str, framing_text: str
) -> str:
    """Short coach-voice acknowledgement before Layer 1 opens.

    Single-sentence reflection of the user's framing. Empathetic and
    restrained per brief §5.2.
    """
    if not framing_text:
        return "I've read what you've brought. Let's start here."
    snippet = (framing_text or "").strip()
    # Use the first 90 chars as a hint that lands as recognition,
    # not paraphrase (paraphrasing is fragile and feels patronising).
    if len(snippet) > 90:
        snippet = snippet[:87].rstrip(",;:- ") + "…"
    return (
        f"You've brought something that's sitting with weight — \"{snippet}\". "
        "Let's open it."
    )


def render_synthesis(
    *,
    sub_module: str,
    scenarios: List[Dict[str, Any]],
    sensitivity_drivers: List[Dict[str, Any]],
    surfaced_tensions: List[Dict[str, Any]],
    carry_forward_caveats: List[str],
    evidence_trace: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Compose the Layer 3 user-visible synthesis.

    Editorial cadence — one orientation sentence, two short bodies,
    one closing diagnosis sentence. Probability + interval shown per
    leading scenario. Tensions and caveats render as conditional
    clauses, not as enumerated lists with audit vocabulary.
    """
    out: List[str] = []
    # Orientation.
    out.append("Here is where I've landed.")
    out.append("")

    # Lead scenario.
    if scenarios:
        lead = max(scenarios, key=lambda s: float(s.get("weight", 0)))
        weight_str = _pct(float(lead.get("weight", 0)))
        ci_str = _interval(
            float(lead.get("confidence_interval_low", 0)),
            float(lead.get("confidence_interval_high", 1)),
        )
        lead_desc = _sanitize_internal_string(str(lead.get("description", "")))
        out.append(
            f"The reading that holds up best is this: {lead_desc}. "
            f"I'd put that at around {weight_str} ({ci_str})."
        )
        # Two alternates.
        alts = sorted(
            (s for s in scenarios if s.get("id") != lead.get("id")),
            key=lambda s: -float(s.get("weight", 0)),
        )[:2]
        if alts:
            alt_lines = []
            for a in alts:
                w = _pct(float(a.get("weight", 0)))
                ci = _interval(
                    float(a.get("confidence_interval_low", 0)),
                    float(a.get("confidence_interval_high", 1)),
                )
                a_desc = _sanitize_internal_string(str(a.get("description", "")))
                alt_lines.append(
                    f"There is also the reading that {a_desc} — about {w} ({ci})."
                )
            out.append(" ".join(alt_lines))
    else:
        out.append("The picture you've drawn is unsettled enough that I'm not going to put numbers on it.")

    out.append("")

    # Surfaced tensions — sanitized.
    if surfaced_tensions:
        ten_desc = _sanitize_internal_string(
            str(surfaced_tensions[0].get("description", ""))
        )
        if ten_desc:
            out.append(f"There is a piece of this worth naming: {ten_desc}")

    # Sensitivity drivers — render only the top one, in plain language.
    if sensitivity_drivers:
        d_desc = _sanitize_internal_string(
            str(sensitivity_drivers[0].get("description", ""))
        )
        if d_desc:
            out.append(f"What would change this read most is fresh signal from {d_desc}")

    # Carry-forward caveats render as conditional close.
    if carry_forward_caveats:
        cf = _sanitize_internal_string(str(carry_forward_caveats[0]))
        if cf:
            out.append(f"If {cf}, the lead reading shifts.")

    # Closing.
    out.append("")
    out.append("That's the position I'd hold to. Push back wherever it doesn't sit right.")
    return "\n".join(out).strip()
