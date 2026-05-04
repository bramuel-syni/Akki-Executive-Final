"""Solva v2 — production reasoning surface (post Phase A cutover).

Solva v2 is the **only** Solva. The legacy `account.solva_v2_poc`
account flag was retired in Phase A; v1 POST endpoints have been
removed (see `routers/solva_engine.py` for the read-only forensic
GET surface that survives). This package owns the four sub-modules,
the layered state machine, the grounding contract, and the strict
LLM adapter that fronts every model call on this surface.

Four sub-modules (`submodules.py`):
    seek_clarity         — diagnose first; one layer at a time.
    develop_strategy     — diagnosis → testable, owner-assignable recommendation.
    simulate_hypothesis  — adds a `hypothesis` layer + tension detector.
    get_perspective      — persona-led ("See Another Perspective").
                           Persona REQUIRED at intake; cannot be skipped.

Layer flow (`state_machine.py`):
    framing -> grounding -> synthesis -> reflection            (default)
    framing -> grounding -> hypothesis -> synthesis -> reflection
                                                              (simulate_hypothesis)

`next_layer()` is a pure function gated by per-layer required engines
plus minimum user-turn counts. Transitions are deterministic — no
LLM is involved in deciding what layer to render next.

Reasoning audit log (`reasoning_audit_log[]` on every session) carries
one row per engine per turn: engine name, version, input/output hashes,
shield_required flag, latency, and (for LLM-touching engines) the
provider, tier_requested, tier_served, and the synisense_run_id from
`db.synisense_runs`. The log is the audit chain — it is what
governance export emits and what the Reasoning Drawer renders.

Engines (`engines/`):
    candidate_generation@1.0  — pre-grounding candidate set.
    triangulation@1.0         — reads `db.solve_comparables` (shared with v1).
    probability_weighting@1.0 — confidence_pct + interval per claim.
    refusal@1.1               — soft refusal step (see also `guardrails.py`).
    reflection@1.0            — three locked questions at terminal layer.
    tension_detector@1.0      — auto-fires inside simulate_hypothesis.
    llm_adapter_proxy         — deprecation shim; do not import.

Policy / guards:
    guardrails.py        — refusal ladder (continue|soft_block|hard_block|
                           therapy_redirect). Pure deterministic policy.
    opinion_filter.py    — no-opinion principle scan over synthesis text.
    grounding_contract.py — 5-tier markers; up to 2 retries on synthesis.
    llm_adapter.py       — strict shielded_call wrapping Synisense + tier
                           routing + optional independent-family validator.

Reuse, not reinvention:
    backend/services/synisense/pipeline.py   runs on every LLM input
    backend/llm_service.py                    tiered call + validator
    backend/llm_tier_quota.py                 per-account surface budget
    backend/solve_clusters_seed.py            12-cluster taxonomy (shared with v1)
    backend/solve_comparables_seed.py         27 curated comparables (shared)
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
