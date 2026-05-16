"""Synthesis renderer — converts internal reasoning artefacts into
coach-voice user-facing prose.

This is the ONE place where Layer 3 user content is produced. The
function consumes the (internal) probability weighting output +
surfaced tensions and renders an editorial-cadence synthesis
paragraph.

CRITICAL invariant: NO internal artefact terminology (FAR, candidate,
triangulation, frame audit, scenario weight, dimension, invalidation
condition, etc.) appears in the output. Locked by
`voice.invariants.scan_for_internal_artefacts`.

CRITICAL invariant: NO Shield de-identification placeholders
(`[[ENT_*_NNN]]`) reach user-visible prose. Stripped by
`_strip_entity_placeholders` before assembly.

Phase D fix bundle 2026-05-16:
  - `carry_forward_caveats` removed from the rendered output entirely.
    Those are FAR-internal sensitivity flags, not user prose. Synthesis
    derives only from weights + tensions + scenario descriptions.
  - `[[ENT_*]]` placeholders stripped from every input string before
    rendering — surfaced as a structural artefact (see `synthesis_had_unresolved_entities`).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Strip layer references and Markdown field labels from any string
# that originated in the reasoning tier before it reaches the user.
_LAYER_REF_RE = re.compile(r"\b(layer[\s_]?[0-9]+|in the layer\s+[0-9]+)\b", re.I)
_MARKDOWN_LABEL_RE = re.compile(r"\*{2}[^*]{1,40}\*{2}\s*:?\s*", re.I)
_LEADING_LABEL_RE = re.compile(r"^\s*[A-Z][a-z]+(\s+[A-Za-z]+){0,2}\s*:\s+", re.I)
_INTERNAL_TERMS_RE = re.compile(
    r"\b(frame audit|candidate set|triangulation result|audit_?id|"
    r"dimension score|calibration version|synisense audit|"
    r"invalidation_?condition|routing_?decision)\b",
    re.I,
)

# Shield de-identification placeholder pattern. Examples:
#   [[ENT_PERSON_001]]   [[ENT_MONEY_42]]   [[ENT_PROJECT_007]]
_ENT_PLACEHOLDER_RE = re.compile(r"\[\[ENT_[A-Z][A-Z_0-9]*_\d+\]\]")


def _strip_entity_placeholders(text: str) -> Tuple[str, int]:
    """Strip any Shield `[[ENT_*_NNN]]` placeholders. Returns the
    cleaned text + a count of how many placeholders were stripped.
    The count is a structural signal — if non-zero, the upstream
    LLM hallucinated entity tokens not present in the de-id map."""
    if not text:
        return "", 0
    n = len(_ENT_PLACEHOLDER_RE.findall(text))
    cleaned = _ENT_PLACEHOLDER_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:.-")
    return cleaned, n


def _sanitize_internal_string(text: str) -> str:
    """Strip reasoning-tier artefact vocabulary from a string that
    might originate from an LLM response. Preserves the substantive
    content; removes the engineering scaffolding."""
    if not text:
        return ""
    t, _ = _strip_entity_placeholders(text)
    t = _MARKDOWN_LABEL_RE.sub("", t)
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
    carry_forward_caveats: Optional[List[str]] = None,   # accepted but IGNORED
    evidence_trace: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Compose the Layer 3 user-visible synthesis.

    Editorial cadence — orientation, lead scenario with weight +
    interval, two alternates, surfaced tension, sensitivity driver,
    close. `carry_forward_caveats` is accepted for API back-compat
    but IGNORED — those are FAR-internal sensitivity flags.

    Contract: returned string contains ZERO `[[ENT_` substrings and
    ZERO `invalidation_condition`-style copy. Locked by
    `test_synthesis_contains_no_entity_placeholders` and
    `test_synthesis_contains_no_invalidation_phrases`.
    """
    out: List[str] = []
    out.append("Here is where I've landed.")
    out.append("")

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

    # NOTE: carry_forward_caveats deliberately NOT rendered (Phase D
    # fix bundle 2026-05-16). Those are FAR-internal invalidation
    # conditions; rendering them leaked engineering vocabulary into
    # user prose ("If no explicit decision the diagnosis would inform,
    # the lead reading shifts.").

    out.append("")
    out.append("That's the position I'd hold to. Push back wherever it doesn't sit right.")

    # Final defensive scrub — strip any entity placeholders that snuck
    # through (e.g. inside scenario descriptions the LLM hallucinated
    # tokens for). The post-strip count is logged structurally above
    # via _sanitize_internal_string.
    body = "\n".join(out).strip()
    body, _ = _strip_entity_placeholders(body)
    return body
