"""Single-voice invariant enforcement.

`scan_for_internal_artefacts(text)` scans a user-facing string for
language that should only appear in INTERNAL reasoning artefacts.
Any hit returned is a SingleVoiceViolation — a leak of audit / FAR
/ candidate-set vocabulary into user-visible content. CI test
`test_solva_phase_d_single_voice_invariant.py` runs this scan on every
voice-tier output and on the Solva session GET response payload.

Phase D fix bundle v2 (2026-05-16):
  - Family-wide Shield placeholder detection — was previously
    `[[ENT_*]]` only; now catches `[[<UPPER>_<digits>]]` for ALL
    Shield identifier families (DATE, MONEY, ORG, PERSON, EMAIL,
    PHONE_E164, IBAN, ACCOUNT_NUM, IP, URL, GPE, PRODUCT, NORP, FAC,
    EVENT, LAW, and any future categories).
  - Macro-name detection — catches LLM-emitted section headers like
    `DIAGNOSE`, `EVIDENCE`, `OBSERVE` when they appear standalone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


# Internal artefact vocabulary — these terms are STRICTLY internal.
# Any of them appearing in a user-visible string is a leak.
INTERNAL_ARTEFACT_TERMS: List[str] = [
    "frame audit record",
    "far record",
    "far verdict",
    "candidate set",
    "candidate_set",
    "triangulation result",
    "triangulation_result",
    "dimension score",
    "calibration version",
    "synisense audit",
    "audit_id",
    "audit id",
    "shield refusal",
    "shield_refusal",
    "orchestration_audit",
    "orchestration audit",
    "tier_distribution",
    "tier distribution",
    "scenario weight",
    "probability weighting",
    "entailment classification",
    "claim extraction",
    "exposure_reduction",
    "dilution_score",
    "synisense_run",
    "FAR ",                 # capitalised acronym (FAR Verdict, FAR Dimensions)
    "FAR.",
    "FAR:",
    "FAR field",
    "Frame Audit Record",
    "Frame Audit Engine",
    # User's screenshot leak — the deterministic frame_audit summary
    # legacy "a couple of pieces are thin" copy.
    "a couple of pieces are thin",
    "several structural pieces are missing",
    "your framing is workable",
    # Phase D fix bundle v1 2026-05-16 — invalidation_condition + FAR
    # sensitivity-flag vocabulary, and Shield re-id placeholders.
    "invalidation_condition",
    "the lead reading shifts",
    "FAR.dimensions",
    "far.dimensions",
    "routing_decision",
    # Family-wide Shield placeholder substring guards (v2 2026-05-16).
    "[[ent_",
    "[[ENT_",
    "[[date_",
    "[[DATE_",
    "[[money_",
    "[[MONEY_",
    "[[org_",
    "[[ORG_",
    "[[person_",
    "[[PERSON_",
    "[[email_",
    "[[EMAIL_",
    "[[phone_",
    "[[PHONE_",
    "[[iban_",
    "[[IBAN_",
    "[[account_",
    "[[ACCOUNT_",
    "[[ip_",
    "[[IP_",
    "[[url_",
    "[[URL_",
    "[[gpe_",
    "[[GPE_",
    "[[product_",
    "[[PRODUCT_",
    "[[norp_",
    "[[NORP_",
    "[[fac_",
    "[[FAC_",
    "[[event_",
    "[[EVENT_",
    "[[law_",
    "[[LAW_",
    "[[name_",
    "[[NAME_",
]


# Family-wide placeholder regex — catches ANY [[<UPPER>_<digits>]]
# token regardless of family. Used in addition to the substring list
# above so the scanner catches placeholder categories we haven't yet
# enumerated (forward-compat with Shield's evolving taxonomy).
_PLACEHOLDER_PATTERN_RE = re.compile(r"\[\[[A-Z][A-Z_]*_\d+\]\]")


# Single-word all-caps macro names. Detected only when they appear as
# standalone tokens (header-ish context) — not when they're part of
# plain English prose.
_MACRO_NAMES = (
    "DIAGNOSE", "OBSERVE", "DECIDE", "EVIDENCE", "CANDIDATES",
    "FRAMING", "SYNTHESIS", "REFUSAL", "SCENARIOS", "TENSION",
    "TENSIONS", "RECOMMENDATION", "RECOMMENDATIONS", "LAYER",
    "REFLECTION", "PROBABILITY", "TRIANGULATION", "WEIGHTING",
)
_MACRO_NAME_RE = re.compile(
    r"(?:^|(?<=[\s\.\,\;\:\!\?\(\[\u2014\u2013\-]))"
    rf"(?:{'|'.join(_MACRO_NAMES)})"
    r"(?=$|[\s\.\,\;\:\!\?\)\]\u2014\u2013\-])",
)


@dataclass
class SingleVoiceViolation:
    term: str
    snippet: str
    position: int


def scan_for_internal_artefacts(text: str) -> List[SingleVoiceViolation]:
    """Return one SingleVoiceViolation per internal-artefact hit found
    in `text`. Empty list = clean.

    Three passes:
      (1) Substring list (case-insensitive) — known internal vocabulary.
      (2) Family-wide placeholder regex — catches any
          `[[<UPPER>_<digits>]]` token Shield could emit.
      (3) Macro-name regex — catches standalone all-caps section headers.
    """
    if not text:
        return []
    out: List[SingleVoiceViolation] = []

    # Pass 1: substring list.
    haystack = text.lower()
    for term in INTERNAL_ARTEFACT_TERMS:
        needle = term.lower()
        start = 0
        while True:
            idx = haystack.find(needle, start)
            if idx < 0:
                break
            ctx_start = max(0, idx - 20)
            ctx_end = min(len(text), idx + len(term) + 20)
            out.append(SingleVoiceViolation(
                term=term,
                snippet=text[ctx_start:ctx_end],
                position=idx,
            ))
            start = idx + len(needle)

    # Pass 2: family-wide placeholder regex.
    for m in _PLACEHOLDER_PATTERN_RE.finditer(text):
        ctx_start = max(0, m.start() - 20)
        ctx_end = min(len(text), m.end() + 20)
        out.append(SingleVoiceViolation(
            term=m.group(0),
            snippet=text[ctx_start:ctx_end],
            position=m.start(),
        ))

    # Pass 3: macro-name regex.
    for m in _MACRO_NAME_RE.finditer(text):
        ctx_start = max(0, m.start() - 20)
        ctx_end = min(len(text), m.end() + 20)
        out.append(SingleVoiceViolation(
            term=m.group(0),
            snippet=text[ctx_start:ctx_end],
            position=m.start(),
        ))

    return out
