"""Solva v2 — four reasoning engines (Phase 15.0).

One real, three stubs. All four share a common interface — async `run(...)`
returning `{output, audit_entry}` — so 15.1 can replace the three stubs in
place without touching the orchestrator.

Engine inventory:
    triangulation          REAL   wraps db.solve_comparables lookup
    candidate_generation   STUB   deterministic placeholder, domain_prior tier
    probability_weighting  STUB   pass-through (no confidence weighting)
    refusal                STUB   always returns {block: false}
"""
from . import triangulation, candidate_generation, probability_weighting, refusal

__all__ = [
    "triangulation",
    "candidate_generation",
    "probability_weighting",
    "refusal",
]
