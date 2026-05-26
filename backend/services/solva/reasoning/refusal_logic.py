"""Refusal Logic — Solva Phase D.

Pure-rule deterministic engine. No LLM call here. Invoked between
Layer 2 completion and Layer 3 synthesis; if refusal fires, weighting
is SKIPPED and the voice tier emits the refusal coach-voice template.

Triggers (per brief §4.7 + Phase D fix bundle 2026-05-16):
  1. INSUFFICIENT_EVIDENCE — fewer than 2 candidates with **non-trivial,
     non-fallback** support.
  2. CONTRADICTORY_EVIDENCE_AT_SCALE — ≥2 critical OR ≥4 material
     divergences from triangulation.
  3. FAR_INSUFFICIENT_UNRESOLVED — FAR said insufficient AND Layer 1/2
     answers DID NOT surface substantive missing dimensions
     (heuristic: combined Layer 1+2 answer text < 100 chars OR every
     answer is shorter than 12 chars).
  4. OUT_OF_SCOPE — situation_class == 'other_strategic' with
     confidence < 0.5.
  5. LOW_TRIANGULATION_CONSISTENCY — `triangulation.overall_consistency`
     < 0.4 (added 2026-05-16). Mean entailment too weak to justify a
     probability-weighted synthesis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .frame_audit_engine import FrameAuditOutput
from .triangulation_engine import TriangulationOutput


# Phase D fix-bundle thresholds — locked.
MIN_GROUNDED_CANDIDATES = 2
MIN_TRIANGULATION_CONSISTENCY = 0.4
MIN_RESOLVED_ANSWER_CHARS = 100
MIN_SUBSTANTIVE_ANSWER_CHARS = 12


# Known boilerplate evidence_requirement strings emitted by the
# `_fallback_candidates` path in candidate_generation.py. Candidates
# whose `evidence_requirement` is exactly one of these are SYNTHETIC,
# not user-anchored, and must not count toward Rule 1's grounded set.
_FALLBACK_BOILERPLATE_EVIDENCE = {
    "material or document referenced in the user's framing",
    "evidence from attached material or referenced source",
}


class RefusalReason(str, Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONTRADICTORY_EVIDENCE_AT_SCALE = "contradictory_evidence_at_scale"
    FAR_INSUFFICIENT_UNRESOLVED = "far_insufficient_unresolved"
    OUT_OF_SCOPE = "out_of_scope"
    LOW_TRIANGULATION_CONSISTENCY = "low_triangulation_consistency"


@dataclass
class RefusalDecision:
    should_refuse: bool
    reason: Optional[RefusalReason] = None
    detail: str = ""
    candidates_to_surface: Optional[List[Dict[str, Any]]] = None


def compute_layer_2_resolved(
    *,
    layer_1_answers: List[Dict[str, Any]],
    layer_2_answers: List[Dict[str, Any]],
) -> bool:
    """Heuristic: did Layer 1 + Layer 2 answers surface enough substance
    to lift an 'insufficient' FAR verdict?

    Three checks (ALL must pass — Phase D fix bundle v2 2026-05-16):
      - Combined answer text ≥ MIN_RESOLVED_ANSWER_CHARS chars.
      - At least 3 of the answers are ≥ MIN_SUBSTANTIVE_ANSWER_CHARS chars
        individually (catches the `["yes","no","dunno","maybe"]` pattern).
      - At least 2 of the answers contain at least one EVIDENCE MARKER:
        a digit, a named-document keyword (memo/deck/report/scorecard/
        dashboard/financials/minutes/email/letter/paper/forecast/model/
        analysis/dataset/log/spreadsheet), a date keyword (Q1/Q2/Q3/Q4/
        H1/H2/FY/year/month/week/days), or a financial unit
        ($/%/£/€/USD/EUR/GBP/bps/bn/m).

      The third check is the v2 addition. Without it, fluffy executive
      sentences like "I think we should consider doing something soon"
      pass the first two checks but carry no actual evidence the FAR
      could anchor against.
    """
    all_answers = list(layer_1_answers or []) + list(layer_2_answers or [])
    texts = [(a.get("text") or "").strip() for a in all_answers]
    total_chars = sum(len(t) for t in texts)
    substantive = sum(1 for t in texts if len(t) >= MIN_SUBSTANTIVE_ANSWER_CHARS)
    with_evidence = sum(1 for t in texts if _has_evidence_marker(t))
    return (
        total_chars >= MIN_RESOLVED_ANSWER_CHARS
        and substantive >= 3
        and with_evidence >= 2
    )


_EVIDENCE_DOC_RE = re.compile(
    r"\b(memo|deck|report|paper|brief(?:ing)?|forecast|model|analysis|"
    r"finding|study|scorecard|dashboard|minutes|email|letter|forecast|"
    r"dataset|log|spreadsheet|tracker|board|review|attached)\b",
    re.IGNORECASE,
)
_EVIDENCE_DATE_RE = re.compile(
    r"\b(q[1-4]|h[12]|fy\s*\d+|fy\d{2,4}|fiscal year|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"\d+\s*(?:days?|weeks?|months?|quarters?|years?))\b",
    re.IGNORECASE,
)
_EVIDENCE_DIGIT_RE = re.compile(r"\d")
_EVIDENCE_UNIT_RE = re.compile(
    r"\b(usd|eur|gbp|chf|jpy|inr|bps|basis points?|percent|"
    r"million|billion|bn|mn|m)\b",
    re.IGNORECASE,
)


def _has_evidence_marker(text: str) -> bool:
    if not text:
        return False
    if _EVIDENCE_DIGIT_RE.search(text):
        return True
    if _EVIDENCE_DOC_RE.search(text):
        return True
    if _EVIDENCE_DATE_RE.search(text):
        return True
    if _EVIDENCE_UNIT_RE.search(text):
        return True
    return False


def _candidate_is_grounded(c: Dict[str, Any]) -> bool:
    """True iff candidate appears to be user-anchored (not a synthetic
    fallback) AND carries non-trivial weight."""
    weight = float(c.get("weight", 0.0))
    if weight <= 0.05:
        return False
    evidence = (c.get("evidence_requirement") or "").strip().lower()
    if not evidence:
        return False
    if evidence in _FALLBACK_BOILERPLATE_EVIDENCE:
        return False
    if (c.get("source") or "") == "fallback_synthetic":
        return False
    if len(evidence) < 30:
        # Too short to be a real evidence requirement anchored to a user
        # document / memo / dataset.
        return False
    return True


def evaluate_refusal(
    *,
    far: Optional[FrameAuditOutput],
    triangulation: Optional[TriangulationOutput],
    candidates: List[Dict[str, Any]],
    situation_class: str,
    situation_class_confidence: float,
    layer_2_resolved_missing_dimensions: bool,
) -> RefusalDecision:
    # Rule 1 — insufficient evidence (tightened 2026-05-16: synthetic
    # fallback candidates do NOT count).
    grounded = [c for c in candidates if _candidate_is_grounded(c)]
    if len(grounded) < MIN_GROUNDED_CANDIDATES:
        return RefusalDecision(
            should_refuse=True,
            reason=RefusalReason.INSUFFICIENT_EVIDENCE,
            detail=(
                f"Only {len(grounded)} of {len(candidates)} candidates "
                "are user-anchored with non-trivial evidence requirements."
            ),
            candidates_to_surface=candidates,
        )

    # Rule 2 — contradictory evidence at scale.
    if triangulation:
        critical = [d for d in triangulation.divergences if d.severity == "critical"]
        if len(critical) >= 2:
            return RefusalDecision(
                should_refuse=True,
                reason=RefusalReason.CONTRADICTORY_EVIDENCE_AT_SCALE,
                detail=f"{len(critical)} critical divergences across candidates.",
                candidates_to_surface=candidates,
            )
        material = [d for d in triangulation.divergences if d.severity in ("material", "critical")]
        if len(material) >= 4:
            return RefusalDecision(
                should_refuse=True,
                reason=RefusalReason.CONTRADICTORY_EVIDENCE_AT_SCALE,
                detail=f"{len(material)} material/critical divergences across candidates.",
                candidates_to_surface=candidates,
            )

    # Rule 3 — FAR insufficient verdict not resolved by Layer 1/2.
    if far and far.verdict == "insufficient" and not layer_2_resolved_missing_dimensions:
        return RefusalDecision(
            should_refuse=True,
            reason=RefusalReason.FAR_INSUFFICIENT_UNRESOLVED,
            detail="Layer 0 verdict was insufficient; Layer 1/2 did not surface missing dimensions.",
            candidates_to_surface=candidates,
        )

    # Rule 4 — out-of-scope situation.
    if situation_class == "other_strategic" and situation_class_confidence < 0.5:
        return RefusalDecision(
            should_refuse=True,
            reason=RefusalReason.OUT_OF_SCOPE,
            detail="No canonical situation class matched above threshold.",
            candidates_to_surface=candidates,
        )

    # Rule 5 — low triangulation consistency (new 2026-05-16).
    if triangulation and float(triangulation.overall_consistency) < MIN_TRIANGULATION_CONSISTENCY:
        return RefusalDecision(
            should_refuse=True,
            reason=RefusalReason.LOW_TRIANGULATION_CONSISTENCY,
            detail=(
                f"Triangulation overall_consistency "
                f"{triangulation.overall_consistency:.2f} below threshold "
                f"{MIN_TRIANGULATION_CONSISTENCY}."
            ),
            candidates_to_surface=candidates,
        )

    return RefusalDecision(should_refuse=False)
