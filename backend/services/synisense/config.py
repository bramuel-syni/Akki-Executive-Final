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
    # NOTE: `synisense.shield.internal.ner` REMOVED — Phase A switched
    # the NER pass from cloud-LLM to local spaCy + tenant dictionary,
    # so there is no longer an internal LLM-NER call site to allow-list.

    # ── Phase B — LLM Call Migration (2026-05-13) ──
    # Chat (Phase C will add the protective layer + audit panel)
    "chat.session.summarise",
    "chat.streaming.standard_response",
    "chat.standard_response",
    "chat.fm_a.hypothesis_detection",
    "chat.fm_b.claim_extraction",
    "chat.fm_c.consequence_classification",
    "chat.refusal.compose",
    "chat.*",

    # Solva (Phase D will rewrite the 5-layer pipeline; entry path
    # migrates here so docs-into-solva no longer 524s on a direct call)
    "solva.layer_0.frame_audit",
    "solva.layer_0.situation_classification",
    "solva.layer_1.candidate_generation",
    "solva.layer_2.triangulation.claim_extraction",
    "solva.layer_2.triangulation.entailment_classification",
    "solva.layer_2.tension_detection",
    "solva.layer_3.scenario_narrative_generation",
    "solva.layer_3.synthesis_rendering",
    "solva.refusal.compose",
    "solva.entry.frame_payload",
    "solva.*",

    # Work Studio
    "work_studio.brief.enhance",
    "work_studio.brief.seed",
    "work_studio.deck.generate",
    "work_studio.report.generate",
    "work_studio.minutes.enhance",
    "work_studio.compile.board_pack",
    "work_studio.sandbox.generate",
    "work_studio.*",

    # Document Journal
    "document_journal.commentary.generate",
    "document_journal.meta.generate",
    "document_journal.summary.generate",
    "document_journal.evolution_diff",
    "document_journal.signals.generate",
    "document_journal.add_to_cycle.prep",
    "document_journal.take_to_solva.prep",
    "document_journal.*",

    # Cycle Manager
    "cycle_manager.agenda.generate",
    "cycle_manager.briefing.aggregate",
    "cycle_manager.*",

    # Monitor (Phase F real-signal generation will exercise)
    "monitor.objective.status_assessment",
    "monitor.project.status_assessment",
    "monitor.strategic_goal.update",
    "monitor.*",

    # Pulse
    "pulse.signal.commentary",
    "pulse.*",

    # Generic gateway (legacy `call_llm` paths whose module string
    # doesn't fit a named purpose. Phase C will tighten by mapping
    # every gateway caller to a specific consumer prefix.)
    "akki.gateway.standard",

    # Ops / health probes (no PII)
    "health.ping",
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
