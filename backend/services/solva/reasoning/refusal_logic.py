"""Refusal Logic — Solva Phase D.

Pure-rule deterministic engine. No LLM call here. Triggered before the
probability weighting engine; if refusal fires, weighting is SKIPPED
and the voice tier emits the refusal coach-voice template.

Triggers (per brief §4.7):
  1. Insufficient evidence — candidate set has fewer than 3 candidates
     with non-zero evidence_requirement.
  2. Contradictory evidence at scale — ≥2 critical divergences from
     triangulation_engine.
  3. FAR insufficient verdict not resolved — Layer 0 said insufficient
     AND Layer 1/2 conversation did not surface missing dimensions.
  4. Out-of-scope situation — situation_class == 'other_strategic' AND
     confidence < 0.5.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .frame_audit_engine import FrameAuditOutput
from .triangulation_engine import TriangulationOutput


class RefusalReason(str, Enum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONTRADICTORY_EVIDENCE_AT_SCALE = "contradictory_evidence_at_scale"
    FAR_INSUFFICIENT_UNRESOLVED = "far_insufficient_unresolved"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass
class RefusalDecision:
    should_refuse: bool
    reason: Optional[RefusalReason] = None
    detail: str = ""
    candidates_to_surface: Optional[List[Dict[str, Any]]] = None


def evaluate_refusal(
    *,
    far: Optional[FrameAuditOutput],
    triangulation: Optional[TriangulationOutput],
    candidates: List[Dict[str, Any]],
    situation_class: str,
    situation_class_confidence: float,
    layer_2_resolved_missing_dimensions: bool,
) -> RefusalDecision:
    # Rule 1 — insufficient evidence.
    grounded = [
        c for c in candidates
        if (c.get("evidence_requirement") or "").strip()
        and float(c.get("weight", 0.0)) > 0.05
    ]
    if len(grounded) < 3:
        return RefusalDecision(
            should_refuse=True,
            reason=RefusalReason.INSUFFICIENT_EVIDENCE,
            detail=(
                f"Only {len(grounded)} of {len(candidates)} candidates have "
                "non-trivial evidence requirements."
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
        # Multi-material divergences also disqualify.
        material = [d for d in triangulation.divergences if d.severity in ("material", "critical")]
        if len(material) >= 4:
            return RefusalDecision(
                should_refuse=True,
                reason=RefusalReason.CONTRADICTORY_EVIDENCE_AT_SCALE,
                detail=f"{len(material)} material/critical divergences across candidates.",
                candidates_to_surface=candidates,
            )

    # Rule 3 — FAR insufficient verdict not resolved.
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

    return RefusalDecision(should_refuse=False)
