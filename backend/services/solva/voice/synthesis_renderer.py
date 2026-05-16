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

CRITICAL invariant: NO Shield de-identification placeholders (any
family — `[[ENT_*]]`, `[[DATE_*]]`, `[[MONEY_*]]`, `[[ORG_*]]`,
`[[PERSON_*]]`, etc.) reach user-visible prose. Stripped by
`_strip_entity_placeholders` before assembly AND as a final
defensive pass.

CRITICAL invariant: NO standalone all-caps macro names (`DIAGNOSE`,
`EVIDENCE`, `OBSERVE`, `DECIDE`, `CANDIDATES`, `SCENARIOS`, etc.)
appear as user-visible section headers. Stripped by
`_strip_macro_names` whenever they appear outside plain English
usage.

Phase D fix bundle v1 + v2 (2026-05-16):
  - `carry_forward_caveats` removed from the rendered output entirely.
  - Placeholder regex broadened from `[[ENT_*_NNN]]` only to the
    FAMILY-WIDE pattern `[[<UPPER>_<digits>]]`.
  - Macro-name stripper added — catches LLM-hallucinated section
    headers like `DIAGNOSE` / `EVIDENCE`.
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

# Family-wide Shield de-identification placeholder pattern. Catches
# `[[ENT_*_NNN]]`, `[[DATE_NNN]]`, `[[MONEY_NNN]]`, `[[ORG_NNN]]`,
# `[[NAME_NNN]]`, `[[PERSON_NNN]]`, `[[EMAIL_NNN]]`, `[[PHONE_E164_NNN]]`,
# `[[IBAN_NNN]]`, `[[ACCOUNT_NUM_NNN]]`, `[[IP_NNN]]`, `[[URL_NNN]]`,
# `[[GPE_NNN]]`, `[[PRODUCT_NNN]]`, `[[NORP_NNN]]`, `[[FAC_NNN]]`,
# `[[EVENT_NNN]]`, `[[LAW_NNN]]` and any future Shield identifier
# categories. Format: `[[<UPPERCASE>_<digits>]]` — the leading letter
# must be uppercase, any number of `[A-Z_]` chars, then `_<digits>]]`.
# Phase D fix bundle v2 (2026-05-16) — was previously ENT-only.
_PLACEHOLDER_RE = re.compile(r"\[\[[A-Z][A-Z_]*_\d+\]\]")

# Single-word all-caps macro names that occasionally leak from prompt
# templates or LLM hallucination. Stripped only when they appear in a
# "header-ish" context — standalone on a line, or preceded/followed by
# punctuation. Plain English usage like "Yes, that diagnosis matches"
# is unaffected (DIAGNOSE all-caps, not lowercase).
_MACRO_NAMES = (
    "DIAGNOSE", "OBSERVE", "DECIDE", "EVIDENCE", "CANDIDATES",
    "FRAMING", "SYNTHESIS", "REFUSAL", "SCENARIOS", "TENSION", "TENSIONS",
    "RECOMMENDATION", "RECOMMENDATIONS", "LAYER", "REFLECTION",
    "PROBABILITY", "TRIANGULATION", "WEIGHTING",
)
# Boundary chars before/after — line break, start/end of string, or
# punctuation. The pattern asserts the macro isn't part of a longer
# word.
_MACRO_NAME_RE = re.compile(
    r"(?:^|(?<=[\s\.\,\;\:\!\?\(\[\u2014\u2013\-]))"
    rf"(?:{'|'.join(_MACRO_NAMES)})"
    r"(?=$|[\s\.\,\;\:\!\?\)\]\u2014\u2013\-])",
)


def _strip_entity_placeholders(text: str) -> Tuple[str, int]:
    """Strip any Shield de-identification placeholder (any family).
    Returns the cleaned text + a count of how many placeholders were
    stripped. The count is a structural signal — if non-zero, the
    upstream re-identifier silently failed to resolve them OR the
    LLM hallucinated tokens not present in the de-id map."""
    if not text:
        return "", 0
    n = len(_PLACEHOLDER_RE.findall(text))
    cleaned = _PLACEHOLDER_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:.-")
    return cleaned, n


def _strip_macro_names(text: str) -> str:
    """Strip standalone all-caps macro names (`DIAGNOSE`, `EVIDENCE`,
    etc.) that LLMs occasionally emit as section headers. Plain
    English usage is unaffected — the regex requires word boundaries
    AND that no lowercase letters follow."""
    if not text:
        return ""
    cleaned = _MACRO_NAME_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:.-")
    return cleaned


def _sanitize_internal_string(text: str) -> str:
    """Strip reasoning-tier artefact vocabulary from a string that
    might originate from an LLM response. Preserves the substantive
    content; removes the engineering scaffolding."""
    if not text:
        return ""
    t, _ = _strip_entity_placeholders(text)
    t = _strip_macro_names(t)
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
    tension_activation: Optional[Dict[str, Any]] = None,
) -> str:
    """Compose the Layer 3 user-visible synthesis.

    Editorial cadence — orientation, lead scenario with weight +
    interval, two alternates, surfaced tension, sensitivity driver,
    close. `carry_forward_caveats` is accepted for API back-compat
    but IGNORED — those are FAR-internal sensitivity flags.

    Phase E Sub-task C (2026-05-16): when `tension_activation.activated`
    is True AND `synthesis_variant=="tension_flagged"`, the prose opens
    with an EXPLICIT acknowledgement of the contested read instead of
    the neutral "Here is where I've landed." This keeps the
    disagreement visible to the user.

    Contract: returned string contains ZERO `[[ENT_` substrings and
    ZERO `invalidation_condition`-style copy. Locked by
    `test_synthesis_contains_no_entity_placeholders` and
    `test_synthesis_contains_no_invalidation_phrases`.
    """
    out: List[str] = []
    tension_flagged = bool(
        (tension_activation or {}).get("activated")
        and (tension_activation or {}).get("synthesis_variant") == "tension_flagged"
    )
    if tension_flagged:
        out.append(
            "Two readings are pulling against each other here, and I'm "
            "going to keep that visible rather than smooth it over."
        )
    else:
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

    # Final defensive scrub — strip any placeholders (any family) AND
    # all-caps macro headers that snuck through (e.g. inside scenario
    # descriptions the LLM hallucinated tokens for). Phase D fix
    # bundle v2 — was previously ENT-only and missed macro names.
    body = "\n".join(out).strip()
    body, _ = _strip_entity_placeholders(body)
    body = _strip_macro_names(body)
    return body
