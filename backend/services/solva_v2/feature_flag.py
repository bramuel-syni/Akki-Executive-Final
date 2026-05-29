"""Solva v2 — Feature flag helper.

The v2 build ships behind a two-layer flag so v1 stays functionally
identical until v2 fully ships:

  Layer 1 — env: SOLVA_V2_ENABLED ∈ {true, false, 1, 0, yes, no}
            Default: false (v1 surface unchanged).

  Layer 2 — per-account override: `account.feature_flags.solva_v2`
            (True / False / missing). When present, overrides env.

  Truth table:
    env=false, account=None  →  False  (v1 surface)
    env=false, account=True  →  True   (per-account opt-in)
    env=true,  account=None  →  True   (global rollout)
    env=true,  account=False →  False  (per-account opt-out — kill switch)

Callers: `solva_v2_enabled_for(account)`. Account is the loaded account
dict from `auth.current_account()` or equivalent. The helper tolerates
None / missing `feature_flags` keys gracefully.

NEVER read the env var directly elsewhere — always go through this
helper so the truth table is enforced consistently.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional


_TRUE_TOKENS = {"true", "1", "yes", "y", "on"}


def _env_default() -> bool:
    """Read SOLVA_V2_ENABLED at call-time so test pytest fixtures
    that monkeypatch the env are picked up."""
    raw = os.environ.get("SOLVA_V2_ENABLED", "false")
    return str(raw).strip().lower() in _TRUE_TOKENS


def solva_v2_enabled_for(account: Optional[Dict[str, Any]]) -> bool:
    """Return True iff Solva v2 artefact rendering is enabled for this
    account.

    Per-account override (when present) ALWAYS wins over the env
    default. Missing account, missing `feature_flags`, missing
    `solva_v2` key — all fall through to the env default.
    """
    if account is not None and isinstance(account, dict):
        flags = account.get("feature_flags")
        if isinstance(flags, dict) and "solva_v2" in flags:
            value = flags["solva_v2"]
            if isinstance(value, bool):
                return value
            # String form fallback ("true"/"false" stored in DB)
            return str(value).strip().lower() in _TRUE_TOKENS
    return _env_default()


__all__ = ["solva_v2_enabled_for"]
