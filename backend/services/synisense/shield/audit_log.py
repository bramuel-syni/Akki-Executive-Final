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
from typing import Any, Dict, Optional

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
) -> None:
    """Persist a Shield audit log row.

    Chunk 18 additive fields:
      - `tokens_in` / `tokens_out`: token counts for this invocation.
        - "exact" — sourced from provider response payload's
          `usage.input_tokens` / `output_tokens` (streaming path).
        - "estimated" — char/4 approximation (non-streaming path,
          since `emergentintegrations.LlmChat.send_message()` returns
          string only with no usage data).
        - None — no metering attempted (legacy rows + early-return paths).
      - `metering_method`: provenance flag distinguishing exact vs estimated
        counts at query time.

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
    }
    await db[AUDIT_COLLECTION].insert_one(row)


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
