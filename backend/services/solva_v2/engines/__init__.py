"""Solva v2 — reasoning engines (Phase 15.0 → 15.2).

All engines share a common interface — async `run(...)` returning
`{output, audit_entry}` (refusal returns `audit_entry`,
candidate_generation / probability_weighting return `audit_entries[]` as
they support a retry pass) — so the orchestrator can invoke any engine
the same way.

Engine inventory:
    triangulation          REAL  wraps db.solve_comparables lookup
    candidate_generation   REAL  Phase 15.1 — multi-candidate framings
    probability_weighting  REAL  Phase 15.1 — confidence bands per claim
    refusal                REAL  Phase 15.1 — clean / jailbreak / oos classifier
    tension_detector       REAL  Phase 15.2 — single-session contradiction finder
                                  (auto-activates inside Simulate Hypothesis)
"""
from . import (  # noqa: F401
    triangulation, candidate_generation, probability_weighting, refusal,
    tension_detector,
)

__all__ = [
    "triangulation",
    "candidate_generation",
    "probability_weighting",
    "refusal",
    "tension_detector",
]
