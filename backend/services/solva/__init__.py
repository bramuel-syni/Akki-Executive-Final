"""Solva — Phase D production reasoning module.

Phase D (2026-05-13) — 5-layer state machine + 7 reasoning models +
Shield-routed LLM gateway + voice tier. Sits ALONGSIDE the legacy
`services/solva_v2/` package which continues to serve the existing UI
routes. New context-scoped routes at `/api/contexts/{cid}/solva/v2/*`
consume this package; new sessions write to the `solva_phase_d_sessions`
Mongo collection.

Architecture (per /app/memory/briefs/SOLVA.md):

    Presentation tier  — owned by the frontend (single voice — coach)
    Orchestration tier — services/solva/orchestration/ + voice/
    Reasoning tier     — services/solva/reasoning/ (Shield-routed)

Single-voice invariant: ONLY `voice/question_bank.py` +
`voice/synthesis_renderer.py` + `voice/refusal_voice.py` produce
user-facing strings. Reasoning model outputs (FAR, candidate sets,
triangulation results, scenario weights) are INTERNAL — never rendered
as user content. Locked by
`tests/test_solva_phase_d_single_voice_invariant.py`.

Tenant scoping: every Mongo query AND every Shield invoke carries
`tenant_id = account_id` AND `context_id` from the route binding.
"""
from .schemas import (
    SUB_MODULES,
    LAYER_STATES,
    TERMINAL_STATES,
    LAYER_SEQUENCE,
    SolvaPhaseDSession,
    OrchestrationEntry,
    Layer0Record,
    Layer1Record,
    Layer2Record,
    Layer3Record,
    Layer4Record,
    SolvaSessionStatus,
    SUB_MODULE_TO_OPENING_KEY,
)

__all__ = [
    "SUB_MODULES",
    "LAYER_STATES",
    "TERMINAL_STATES",
    "LAYER_SEQUENCE",
    "SolvaPhaseDSession",
    "OrchestrationEntry",
    "Layer0Record",
    "Layer1Record",
    "Layer2Record",
    "Layer3Record",
    "Layer4Record",
    "SolvaSessionStatus",
    "SUB_MODULE_TO_OPENING_KEY",
]
