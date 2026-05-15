"""Synisense Phase A — service config.

Holds:
- `SYNISENSE_MASTER_SECRET` resolution (env var, with dev fallback + STARTUP WARNING)
- Allow-listed purposes (initial Phase A set)
- Latency budgets
- Environment flag for dev-only routes

The structure here is locked by the user-approved Phase A brief. No
runtime config changes; settings are read once at import time.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Set

log = logging.getLogger("synisense.config")

# ─────────────────────────────────────────────────────────────────────
# Master secret resolution.
#
# Production MUST set SYNISENSE_MASTER_SECRET to a stable, high-entropy
# value (at least 32 bytes of base64 / hex). Per-tenant HMAC keys are
# derived via HKDF from this master secret with `tenant_id` as the
# info parameter (see `shield/trust_receipt.py`).
#
# If the env var is missing we generate a dev-only ephemeral secret and
# log a STARTUP WARNING in caps. Restarts will rotate the dev secret
# and invalidate every receipt signed with the previous one — which is
# the whole point of warning loudly.
# ─────────────────────────────────────────────────────────────────────
_DEV_FALLBACK_GENERATED = False


def _resolve_master_secret() -> bytes:
    global _DEV_FALLBACK_GENERATED
    raw = os.environ.get("SYNISENSE_MASTER_SECRET", "").strip()
    if raw:
        return raw.encode("utf-8")
    _DEV_FALLBACK_GENERATED = True
    dev_secret = secrets.token_bytes(32)
    log.warning(
        "*** STARTUP WARNING *** SYNISENSE_MASTER_SECRET ENV VAR IS NOT SET. "
        "USING AN EPHEMERAL DEV-ONLY SECRET. ALL TRUST RECEIPT SIGNATURES "
        "WILL BE INVALIDATED ON RESTART. DO NOT SHIP THIS CONFIGURATION "
        "TO PRODUCTION."
    )
    return dev_secret


MASTER_SECRET: bytes = _resolve_master_secret()


def is_dev_fallback_active() -> bool:
    """Test/admin probe — True iff the master secret came from the
    dev fallback (env var absent)."""
    return _DEV_FALLBACK_GENERATED


# ─────────────────────────────────────────────────────────────────────
# Allow-listed purposes (Phase A initial set).
#
# Purposes are namespaced by consumer + intent (e.g. `chat.standard_response`,
# `solva.layer_0.frame_audit`). Wildcards are supported via trailing
# `.*` (matches any depth). Internal purposes (`synisense.*`) are blocked
# at the HTTP boundary — only in-process code can invoke them.
#
# Phase A keeps the catalogue minimal — Phase B will extend it as call
# sites are migrated.
# ─────────────────────────────────────────────────────────────────────
ALLOWED_PURPOSES: Set[str] = {
    # Test-only.
    "test.smoke",
    "test.*",
    # Phase B will add: chat.*, solva.*, work_studio.*, etc.
    # NOTE: `synisense.shield.internal.ner` REMOVED — Phase A switched
    # the NER pass from cloud-LLM to local spaCy + tenant dictionary,
    # so there is no longer an internal LLM-NER call site to allow-list.
}

# Purposes that may NEVER be invoked from external HTTP callers — only
# from in-process code that flips the `internal_caller=True` flag in
# the validator.
INTERNAL_ONLY_PURPOSE_PREFIXES: tuple = ("synisense.",)

# ─────────────────────────────────────────────────────────────────────
# Latency budgets (informational — surfaced in metrics).
#
# Regex pass <5ms, LLM-NER <2000ms, full Shield invoke median <300ms
# overhead (LLM provider call is excluded from the overhead measure).
# ─────────────────────────────────────────────────────────────────────
LATENCY_BUDGET_REGEX_MS: int = 5
LATENCY_BUDGET_LLM_NER_MS: int = 2000
LATENCY_BUDGET_SHIELD_TOTAL_MS: int = 300

# ─────────────────────────────────────────────────────────────────────
# Environment — gates dev-only routes such as /engine/admin/reseed.
# ─────────────────────────────────────────────────────────────────────
ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development").lower()


def is_production() -> bool:
    return ENVIRONMENT == "production"
