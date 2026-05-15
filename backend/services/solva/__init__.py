"""Solva v2 pipeline (Phase D) — package marker.

New canonical Solva architecture: 5-layer state machine + 7 reasoning
modules + coach-voice renderer. Every LLM call routes through Synisense
Shield with its declared `solva.layer_*` purpose. Single-voice
invariant enforced by `voice.invariants`.

The legacy implementation in `routers/solva_v2.py` (1990-3020) stays
operational; new sessions created via `routers/solva_v2_contexts.py`
flow through this pipeline.
"""
