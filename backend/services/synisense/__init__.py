"""Synisense — in-house de-identification pipeline.

Phase 12.1 ships the engine end-to-end with a stable public API.
Phase A (Phase 12.3 close) — `shield_payload`-shape adapter exposed
here so legacy LLM-touching surfaces (chat, briefings, decks, etc.)
can migrate off the in-process regex shield without refactoring their
rehydrate flow. The adapter calls the three-layer pipeline in dryrun
mode and returns the (redacted_text, shield_map_dict) tuple shape.

Public entry points:
    pipeline.run(...)           — async, persisting; full data contract.
    pipeline.dryrun(...)        — async, non-persisting; same contract.
    shield_payload_async(...)   — async adapter returning the legacy
                                  (text, {token: original}) tuple shape.
    shielding_report(...)       — UI-friendly bucket counts.
    rehydrate(...)              — pure-python token → original substitution.
    encryption.unshield(...)    — server-internal reversal of a shield_map_id.
"""
from .pipeline import run, dryrun, get_perf_snapshot, get_status_snapshot
from .encryption import unshield, MasterKeyMissing
from .adapter import shield_payload_async, shielding_report, rehydrate

__all__ = [
    "run", "dryrun", "unshield",
    "get_perf_snapshot", "get_status_snapshot",
    "shield_payload_async", "shielding_report", "rehydrate",
    "MasterKeyMissing",
]
