"""Single-voice invariant enforcement.

`scan_for_internal_artefacts(text)` scans a user-facing string for
language that should only appear in INTERNAL reasoning artefacts.
Any hit returned is a SingleVoiceViolation — a leak of audit / FAR
/ candidate-set vocabulary into user-visible content. CI test
`test_solva_phase_d_single_voice_invariant.py` runs this scan on every
voice-tier output and on the Solva session GET response payload.
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
    # Phase D fix bundle 2026-05-16 — invalidation_condition + FAR
    # sensitivity-flag vocabulary, and Shield re-id placeholders.
    "invalidation_condition",
    "the lead reading shifts",
    "FAR.dimensions",
    "far.dimensions",
    "routing_decision",
    "[[ent_",
    "[[ENT_",
]


@dataclass
class SingleVoiceViolation:
    term: str
    snippet: str
    position: int


def scan_for_internal_artefacts(text: str) -> List[SingleVoiceViolation]:
    """Return one SingleVoiceViolation per internal-artefact hit found
    in `text`. Empty list = clean."""
    if not text:
        return []
    out: List[SingleVoiceViolation] = []
    for term in INTERNAL_ARTEFACT_TERMS:
        # Case-insensitive search. Use plain str.find loop so we catch
        # all occurrences with positions.
        haystack = text.lower()
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
    return out
