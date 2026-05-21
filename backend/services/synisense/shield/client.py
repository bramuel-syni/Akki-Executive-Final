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
    llm_text, provider, model, usage = await llm_router.invoke_with_metering(
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
    # `llm_router.invoke_with_metering` returns `usage = {"input_tokens",
    # "output_tokens", "method": "exact"}` when the provider SDK
    # surfaced a usage payload (live `litellm.acompletion` path). On
    # mock-mode or any path where usage is empty we fall back to the
    # char/4 estimator. The audit row carries both the token counts
    # and the provenance flag so downstream metering queries can opt
    # out of estimated rows for billing-critical paths.
    if usage and usage.get("method") == "exact":
        tokens_in = int(usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("output_tokens") or 0)
        metering_method = "exact"
    else:
        tokens_in = audit_log.estimate_tokens(content)
        tokens_out = audit_log.estimate_tokens(response_text)
        metering_method = "estimated"
    actual_cost_usd = audit_log.compute_cost_usd(
        provider=provider, model=model,
        tokens_in=tokens_in, tokens_out=tokens_out,
    )

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
        metering_method=metering_method,
        actual_cost_usd=actual_cost_usd,
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
