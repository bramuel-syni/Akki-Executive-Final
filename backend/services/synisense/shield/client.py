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


# ─────────────────────────────────────────────────────────────────────
# H2.5 (2026-05-24) — Streaming-aware Shield gateway.
# ─────────────────────────────────────────────────────────────────────
# `invoke()` above does the whole round-trip including the LLM call
# (via `llm_router.invoke_with_metering`). The chat streaming surface
# (`routers/chat.py:2390`) needs to drive the LLM round-trip itself
# via `stream_llm_direct`, so it can yield deltas to the SSE client.
# But it still needs the same Shield discipline:
#   1. De-identify the prompt BEFORE calling the LLM
#   2. Re-identify deltas as they arrive (via StreamingReidentifier)
#   3. Write the SAME audit row shape `invoke()` writes, so the Trust
#      Center / audit panel render the streaming turn identically to
#      a sync turn.
#
# `prepare_for_streaming` returns `(redacted_text, token_map,
# audit_finalizer)`. The caller streams the LLM, then awaits
# `audit_finalizer(response_text, provider, model, usage)` to mint
# the same row shape `invoke()` would.
async def prepare_for_streaming(
    *,
    purpose: str,
    content: str,
    tenant_id: str,
    consumer_id: str,
    user_id: str,
    internal_caller: bool = False,
):
    """De-identify `content` and return everything the caller needs
    to stream a Shield-equivalent turn.

    Returns:
        (redacted_text, token_map, finalize)

        redacted_text: str — what to send to `stream_llm_direct`.
        token_map:     dict — feed into `StreamingReidentifier(token_map)`
                       and call `.feed(delta)` / `.flush()` per chunk.
        finalize:      async callable. Caller invokes it AFTER the
                       stream completes:

            audit_id = await finalize(
                response_text=<rehydrated final reply>,
                provider="anthropic" | "openai" | "gemini",
                model="claude-...",
                usage={"input_tokens": .., "output_tokens": .., "method": ..} | None,
                outcome="success" | "stream_error",
            )

        On success this writes the same `synisense_audit_log` row
        + trust receipt that `invoke()` would write. The minted
        audit_id is returned so the caller can push it onto
        `chat.synisense_audit_ids[]`.

    Raises:
        Same Shield exceptions as `invoke()` (purpose_validator,
        de-id pipeline failures).
    """
    import time
    purpose_validator.validate_purpose(purpose, internal_caller=internal_caller)

    started = time.perf_counter()
    de_id = await deidentifier.deidentify(content, tenant_id=tenant_id)

    audit_id = "aud-" + uuid.uuid4().hex
    receipt_id = "rcp-" + uuid.uuid4().hex
    request_hash = trust_receipt.hash_payload(content)

    async def finalize(
        *,
        response_text: str,
        provider: str,
        model: str,
        usage: Dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> str:
        """Close the streaming round-trip — write the audit row +
        trust receipt. Returns the (already-minted) `audit_id`."""
        timestamp = datetime.now(timezone.utc).isoformat()
        latency_ms = int((time.perf_counter() - started) * 1000)
        response_hash = trust_receipt.hash_payload(response_text or "")

        if usage and usage.get("method") == "exact":
            tokens_in = int(usage.get("input_tokens") or 0)
            tokens_out = int(usage.get("output_tokens") or 0)
            metering_method = "exact"
        else:
            tokens_in = audit_log.estimate_tokens(content)
            tokens_out = audit_log.estimate_tokens(response_text or "")
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
            outcome=outcome, latency_ms=latency_ms,
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
        return audit_id

    return de_id.redacted_text, de_id.token_map, finalize
