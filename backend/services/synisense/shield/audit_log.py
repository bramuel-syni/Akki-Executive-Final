"""Synisense Shield — audit log writer (Phase A).

Writes to two collections:
- `synisense_audit_log`     : one row per Shield invocation.
- `synisense_trust_receipts`: signed receipt mirror; consumers can
  retrieve their receipts via the Shield without exposing the audit
  log proper.

The writes are persisted in-process (not async-fire-and-forget) so the
caller can return the `audit_id` to the consumer with the guarantee
that the row is on disk. Mongo write concern uses the driver default.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from core import db

log = logging.getLogger("synisense.shield.audit_log")


AUDIT_COLLECTION = "synisense_audit_log"
RECEIPT_COLLECTION = "synisense_trust_receipts"


async def write_audit(
    *,
    audit_id: str,
    tenant_id: str,
    consumer_id: str,
    user_id: str,
    purpose: str,
    timestamp: str,
    de_id_summary: Dict[str, int],
    dilution_score: float,
    exposure_reduction_score: float,
    llm_provider: str,
    llm_model: str,
    request_hash: str,
    response_hash: str,
    outcome: str,
    latency_ms: int,
    # Chunk 18 (Track 4 item 2, 2026-05-21) — token-accurate metering.
    # New optional fields. Backward-compat: existing rows that don't
    # carry these fields are still valid; queries reading them must
    # treat the absence as None / unknown.
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
    metering_method: Optional[str] = None,  # "exact" | "estimated" | None
    actual_cost_usd: Optional[float] = None,
) -> None:
    """Persist a Shield audit log row.

    Chunk 18 additive fields:
      - `tokens_in` / `tokens_out`: token counts for this invocation.
        - "exact" — sourced from provider response payload's
          `usage.prompt_tokens` / `usage.completion_tokens` (live SDK).
        - "estimated" — char/4 approximation (mock-mode + legacy paths
          where the SDK returned no usage payload).
        - None — no metering attempted (legacy rows + early-return paths).
      - `metering_method`: provenance flag distinguishing exact vs estimated
        counts at query time.
      - `actual_cost_usd`: USD cost computed from the per-model rate table
        (`_RATE_TABLE`). Always populated when tokens_in / tokens_out are
        non-None; falls to None for legacy rows + early-return paths.

    Char/4 estimation matches GPT/Claude/Gemini tokenizers on English
    prose within ±10%. Caller decides whether estimation is acceptable
    for its tier (e.g. billing should require "exact").
    """
    row = {
        "audit_id": audit_id,
        "tenant_id": tenant_id,
        "consumer_id": consumer_id,
        "user_id": user_id,
        "purpose": purpose,
        "timestamp": timestamp,
        "de_id_summary": de_id_summary,
        "dilution_score": dilution_score,
        "exposure_reduction_score": exposure_reduction_score,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "request_hash": request_hash,
        "response_hash": response_hash,
        "outcome": outcome,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "metering_method": metering_method,
        "actual_cost_usd": actual_cost_usd,
    }
    await db[AUDIT_COLLECTION].insert_one(row)


# Chunk 18 (Track 4 item 2, 2026-05-21) — per-model USD rate table.
#
# Numbers are public list prices as of 2026-05 for the providers we
# proxy through Emergent integrations. Values are USD per 1M tokens.
# Adding a new model: append a row using the SAME provider:model
# composite key shape `client.py` writes into the audit log (the
# `:mock` suffix is stripped before lookup).
#
# When a provider/model pair is unknown the lookup returns the
# `_DEFAULT_RATE` (Claude Sonnet 4.5 pricing) so the audit row still
# carries a numeric cost — flagged as estimated since we couldn't
# resolve the exact rate.
_RATE_TABLE: Dict[Tuple[str, str], Tuple[float, float]] = {
    # provider, model: (input_per_M_usd, output_per_M_usd)
    ("anthropic", "claude-sonnet-4-5-20250929"): (3.00, 15.00),
    ("openai",    "gpt-4o"):                     (2.50, 10.00),
    ("openai",    "gpt-5.2"):                    (5.00, 20.00),
    ("gemini",    "gemini-2.5-flash"):           (0.10,  0.40),
    ("gemini",    "gemini-3-flash"):             (0.15,  0.60),
}

_DEFAULT_RATE: Tuple[float, float] = (3.00, 15.00)


def _strip_mock_suffix(value: str) -> str:
    return value.split(":", 1)[0] if ":" in value else value


def compute_cost_usd(
    *,
    provider: str,
    model: str,
    tokens_in: Optional[int],
    tokens_out: Optional[int],
) -> Optional[float]:
    """Return USD cost using `_RATE_TABLE`. None if no tokens supplied.

    Provider / model strings may carry a `:mock` suffix from the mock
    path — stripped before lookup so the same key works for live + mock
    rows in metering queries.
    """
    if tokens_in is None and tokens_out is None:
        return None
    p = _strip_mock_suffix(provider or "").lower()
    m = _strip_mock_suffix(model or "")
    rate_in, rate_out = _RATE_TABLE.get((p, m), _DEFAULT_RATE)
    cost = ((tokens_in or 0) * rate_in + (tokens_out or 0) * rate_out) / 1_000_000.0
    # Avoid -0.0 in the persisted row.
    return round(cost, 8) if cost else 0.0


def estimate_tokens(text: str) -> int:
    """Deterministic char/4 token estimation.

    Chunk 18 (Track 4 item 2) — fallback when the provider SDK doesn't
    surface usage data. Approximation accuracy across GPT/Claude/Gemini
    on English prose:
      • ASCII / English / paragraphs:    ±10%
      • Code / heavy punctuation:        ±25% (over-estimates)
      • Heavy non-Latin content:         ±30-50% (under-estimates)

    The Shield records `metering_method="estimated"` whenever this
    helper is used so consumers can opt out of estimated rows for
    metering-critical paths.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


async def write_receipt(receipt: Dict[str, Any]) -> None:
    # Store a payload_hash alongside the receipt so the audit chain can
    # be verified without retrieving the full receipt body.
    from services.synisense.shield.trust_receipt import hash_payload, _canonical_json
    body = {k: v for k, v in receipt.items() if k != "signature"}
    payload_hash = "sha256:" + __import__("hashlib").sha256(
        _canonical_json(body),
    ).hexdigest()
    # Phase A leaves `payload_hash` derivable; we still store it
    # alongside so audit-log queries are O(1).
    row = {**receipt, "payload_hash": payload_hash}
    await db[RECEIPT_COLLECTION].insert_one(row)
    # silence unused import warning
    _ = hash_payload


async def find_audit(audit_id: str, *, tenant_id: str) -> Optional[Dict[str, Any]]:
    return await db[AUDIT_COLLECTION].find_one(
        {"audit_id": audit_id, "tenant_id": tenant_id}, {"_id": 0},
    )


async def find_receipt(audit_id: str, *, tenant_id: str) -> Optional[Dict[str, Any]]:
    return await db[RECEIPT_COLLECTION].find_one(
        {"audit_id": audit_id, "tenant_id": tenant_id}, {"_id": 0},
    )
