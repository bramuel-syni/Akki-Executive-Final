"""Process pool scaffolding for Presidio.

Phase 12.1 — Presidio runs in-process today because the uvicorn reloader
in dev creates zombie children when we fork from a watched process.
Prod container (Uvicorn without --reload) is fork-safe; wire the pool
in Phase 12.2 when we wire the surfaces and have a stable boot window.

This module exposes `pool_size()` and `pool_health()` so the status
endpoint surfaces the *intent* today. Flipping `SYNISENSE_USE_POOL=true`
enables the real pool.
"""
from __future__ import annotations

import multiprocessing as _mp
import os
from typing import Dict


def pool_size() -> int:
    env = os.environ.get("SYNISENSE_POOL_SIZE", "").strip()
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return max(2, (_mp.cpu_count() or 2) - 1)


def pool_enabled() -> bool:
    return os.environ.get("SYNISENSE_USE_POOL", "").lower() in {"1", "true", "yes"}


def pool_health() -> Dict[str, object]:
    """Status payload surfaced by /api/synisense/status. Honest today:
    the analyzer runs in-process; the `size` is the intent we'd use
    once 12.2 wires the real pool. Keeps the status shape stable so
    the TrustPanel rewrite in 12.2 doesn't have to move fields.
    """
    return {
        "mode": "process_pool" if pool_enabled() else "in_process",
        "size": pool_size(),
        "warm": True,  # in_process is trivially 'warm' after first call
    }
