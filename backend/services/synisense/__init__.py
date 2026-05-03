"""Synisense — in-house de-identification pipeline.

Phase 12.1 ships the engine end-to-end with a stable public API. Surface
wiring (chat, ingest, Studio, Solve, public-read) is Phase 12.2.

Public entry points:
    pipeline.run(...) — async, returns the locked data contract dict.
    pipeline.dryrun(...) — same as run() but never persists.
    encryption.unshield(shield_map_id, ...) — server-internal reversal.
"""
from .pipeline import run, dryrun, get_perf_snapshot, get_status_snapshot
from .encryption import unshield, MasterKeyMissing

__all__ = [
    "run", "dryrun", "unshield",
    "get_perf_snapshot", "get_status_snapshot",
    "MasterKeyMissing",
]
