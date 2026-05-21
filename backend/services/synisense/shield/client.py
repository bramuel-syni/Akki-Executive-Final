"""Synisense Shield — in-process Python client (Phase A).

Phase B will migrate every direct LLM call site in `/app/backend/` to
this client. For Phase A we only ship the surface so the unit tests
can exercise it; no production call sites are migrated yet.

Usage from inside the FastAPI process:

    from services.synisense.shield.client import invoke as shield_invoke
    result = await shield_invoke(
        purpose="solva.layer_0.frame_audit",
        content=raw_text,
        tenant_id=account_id,
        consumer_id="solva",
        user_id=account_id,
        model_preference="analytical",
    )
    response_text = result["response"]
    trust_receipt = result["trust_receipt"]
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from services.synisense.shield import (
    audit_log,
    deidentifier,
    llm_router,
    purpose_validator,
    reidentifier,
    trust_receipt,
)


async def invoke(
    *,
    purpose: str,
    content: str,
    tenant_id: str,
    consumer_id: str,
    user_id: str,
    model_preference: Literal["analytical", "generative", "balanced"] = "balanced",
    internal_caller: bool = False,
) -> Dict[str, Any]:
    """Run the full Shield pipeline. Returns
    `{response, trust_receipt, audit_id}`. Raises one of the four
    SynisenseError subclasses on rejection / failure."""
    import time
    purpose_validator.validate_purpose(purpose, internal_caller=internal_caller)

    started = time.perf_counter()
    de_id = await deidentifier.deidentify(content, tenant_id=tenant_id)
    llm_text, provider, model = await llm_router.invoke(
        de_id.redacted_text, model_preference=model_preference,
    )
    response_text = reidentifier.reidentify(llm_text, de_id.token_map)
    latency_ms = int((time.perf_counter() - started) * 1000)

    audit_id = "aud-" + uuid.uuid4().hex
    receipt_id = "rcp-" + uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()
    request_hash = trust_receipt.hash_payload(content)
    response_hash = trust_receipt.hash_payload(response_text)

    # Chunk 18 (Track 4 item 2, 2026-05-21) — token-accurate metering.
    # The non-streaming `llm_router.invoke()` path uses
    # `emergentintegrations.LlmChat.send_message()` which returns a
    # string-only response with no usage payload. We therefore record
    # estimated token counts (char/4 approximation) and flag the
    # `metering_method` as "estimated" so downstream metering queries
    # can opt out of these rows for billing-critical paths. The
    # streaming path (`shield/streaming.py`) captures usage exactly
    # from provider SDK responses and writes its own audit with
    # `metering_method="exact"`.
    #
    # When the router returned a mock provider (e.g. SYNISENSE_LLM_MODE
    # is "mock" or the SDK is unavailable), we still record the
    # estimate so retention metrics are continuous, but flag it as
    # "estimated" — the same as any non-streaming live call.
    tokens_in = audit_log.estimate_tokens(content)
    tokens_out = audit_log.estimate_tokens(response_text)

    await audit_log.write_audit(
        audit_id=audit_id, tenant_id=tenant_id, consumer_id=consumer_id,
        user_id=user_id, purpose=purpose, timestamp=timestamp,
        de_id_summary=de_id.de_id_summary,
        dilution_score=de_id.dilution_score,
        exposure_reduction_score=de_id.exposure_reduction_score,
        llm_provider=provider, llm_model=model,
        request_hash=request_hash, response_hash=response_hash,
        outcome="success", latency_ms=latency_ms,
        tokens_in=tokens_in, tokens_out=tokens_out,
        metering_method="estimated",
    )
    receipt = trust_receipt.build_trust_receipt(
        receipt_id=receipt_id, audit_id=audit_id, tenant_id=tenant_id,
        consumer_id=consumer_id, purpose=purpose, timestamp=timestamp,
        llm_provider=provider, llm_model=model,
        de_id_summary=de_id.de_id_summary,
        dilution_score=de_id.dilution_score,
        exposure_reduction_score=de_id.exposure_reduction_score,
        request_hash=request_hash, response_hash=response_hash,
    )
    await audit_log.write_receipt(receipt)
    return {
        "response": response_text,
        "trust_receipt": receipt,
        "audit_id": audit_id,
    }
