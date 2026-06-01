"""P5.16 — Confidence calibration for inbox routing.

Calibrated bands derived from signal strength, NOT LLM-self-reported.
Same calibration philosophy as Solva v2 and the Ideas engine:

  • The classifier emits a *score* in [0.0, 1.0].
  • `calibrate_band()` maps the score to one of {low, medium, high}.
  • Thresholds are tuned conservatively: a high band requires
    multiple converging signals, not a single keyword hit.

Score ingredients (for the deterministic-v1 classifier in
`classifier.py`):

  • Keyword density        — how many route-kind tokens land in the
                             subject + first 200 body chars.
  • Subject prefix verb    — "Re:", "Fwd:", "Action required:" etc.
  • Sender tier            — is the sender already known in the tenant?
  • Routing result history — did the inbound pipeline already hint
                             a routing decision?
  • Length signal          — very short bodies degrade to low.
"""
from __future__ import annotations

from typing import Literal

ConfidenceBand = Literal["low", "medium", "high"]

# Locked thresholds — bumping these requires explicit phase memo.
# Calibration tuned so that:
#   • a single weak keyword hit → low (≤ 0.34)
#   • two converging signals (e.g. keyword + sender-tier match)
#     OR an explicit "task:" / "cycle:" prefix → medium
#   • three+ converging signals OR a structured subject prefix
#     (e.g. "ACTION REQUIRED:") → high
CONFIDENCE_THRESHOLDS: dict[ConfidenceBand, float] = {
    "low": 0.0,
    "medium": 0.35,
    "high": 0.70,
}


def calibrate_band(score: float) -> ConfidenceBand:
    """Map a score in [0.0, 1.0] to a calibrated band. Out-of-range
    inputs are clamped: negative → low, > 1.0 → high."""
    if score is None:
        return "low"
    if score >= CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    if score >= CONFIDENCE_THRESHOLDS["medium"]:
        return "medium"
    return "low"


__all__ = ["CONFIDENCE_THRESHOLDS", "calibrate_band"]
