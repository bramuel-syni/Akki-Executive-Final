"""Solva v2 — Phase 15.0 POC package.

Single sub-module scope for 15.0: Seek Clarity. Gated behind
`account.solva_v2_poc=true`. v1 Solva (routers/solva_engine.py,
`db.solve_sessions`) remains untouched.

The POC proves two architectural primitives:
  1. reasoning_audit_log — per-engine per-turn audit trail on a session.
  2. 5-tier grounding contract — every assertive sentence in the synthesis
     output carries a `[T:<tier>]` marker; the parser is the contract.

Layer flow for Seek Clarity:
    framing  -> grounding  -> synthesis  -> reflection

    - framing:     standard-tier LLM turn; refusal stub + validator-placeholder
                   audit entries.
    - grounding:   triangulation (real, reads db.solve_comparables) + 
                   candidate_generation (stub). No LLM call in this layer.
    - synthesis:   LLM primary call; output MUST satisfy the grounding contract
                   (up to 2 retries); independent-family validator runs; 
                   probability_weighting stub passes claims through.
    - reflection:  Layer 4 placeholder (Phase 15.3 replaces this).

Reuse, not reinvention:
  - backend/services/synisense/pipeline.py   runs on every LLM input
  - backend/llm_service.py                   tiered call + validator
  - backend/llm_tier_quota.py                existing surface='solve_v2' budget
  - backend/solve_clusters_seed.py           12-cluster taxonomy (shared with v1)
  - backend/solve_comparables_seed.py        27 curated comparables (shared)
"""
from .grounding_contract import (
    TIER_NAMES,
    TIER_SET,
    GROUNDING_CONTRACT_PROMPT,
    parse,
    summarise_tier_distribution,
    input_hash,
    ParseResult,
    Claim,
)
from .llm_adapter import (
    shielded_call,
    synthetic_audit_entry,
    validator_call,
    record_retry,
    SHIELD_BYPASS_REASONS,
)
from .state_machine import (
    LAYERS,
    next_layer,
    can_post_turn,
    assert_can_post_turn,
    is_terminal,
    InvalidLayerTransition,
    GROUNDING_REQUIRED_ENGINES,
    TERMINAL_LAYER,
)

__all__ = [
    "TIER_NAMES",
    "TIER_SET",
    "GROUNDING_CONTRACT_PROMPT",
    "parse",
    "summarise_tier_distribution",
    "input_hash",
    "ParseResult",
    "Claim",
    "shielded_call",
    "synthetic_audit_entry",
    "validator_call",
    "record_retry",
    "SHIELD_BYPASS_REASONS",
    "LAYERS",
    "next_layer",
    "can_post_turn",
    "assert_can_post_turn",
    "is_terminal",
    "InvalidLayerTransition",
    "GROUNDING_REQUIRED_ENGINES",
    "TERMINAL_LAYER",
]
