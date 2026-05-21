"""FastAPI router — Synisense Shield (Phase A).

Exposes `POST /api/v1/shield/llm/invoke`.

Auth model:
- JWT bearer (existing `get_current_account` from `core`).
- `tenant_id` from the body MUST equal the authenticated account_id,
  EXCEPT for `test.*` purposes which accept arbitrary tenants (so the
  smoke test fixture works as written). Logged in the close-out.

Error handling:
- The four Synisense exception classes map to their canonical HTTP
  status codes. Bodies follow the `ErrorEnvelope` shape with
  `{error_class, message, audit_id?}`.
- The error `message` uses the canonical `{type(exc).__name__}:
  {str(exc)[:300]}` format per the Chunk 3 authenticity rule.

OpenAPI:
- All four responses are declared so `/api/openapi.json` carries the
  full Phase A contract.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from core import get_current_account
from services.synisense.exceptions import (
    AuthDenied, GovernanceRefused, PurposeInvalid, ServiceUnavailable,
    SynisenseError, format_error,
)
from services.synisense.models import (
    ErrorEnvelope, ShieldInvokeRequest, ShieldInvokeResponse,
)
from services.synisense.shield import (
    audit_log, deidentifier, llm_router, purpose_validator,
    reidentifier, trust_receipt,
)

log = logging.getLogger("synisense.routers.shield")

router = APIRouter(prefix="/api/v1/shield", tags=["synisense-shield"])


def _err_response(exc: SynisenseError, audit_id: str | None = None) -> JSONResponse:
    envelope = ErrorEnvelope(
        error_class=exc.class_name,
        message=format_error(exc),
        audit_id=audit_id,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())


@router.post(
    "/llm/invoke",
    response_model=ShieldInvokeResponse,
    responses={
        401: {"model": ErrorEnvelope, "description": "AUTH_DENIED"},
        422: {"model": ErrorEnvelope, "description": "PURPOSE_INVALID"},
        451: {"model": ErrorEnvelope, "description": "GOVERNANCE_REFUSED"},
        503: {"model": ErrorEnvelope, "description": "SERVICE_UNAVAILABLE"},
    },
    summary="De-id → LLM → re-id → Trust Receipt",
)
async def invoke(
    body: ShieldInvokeRequest,
    request: Request,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    started = time.perf_counter()
    audit_id = "aud-" + uuid.uuid4().hex
    receipt_id = "rcp-" + uuid.uuid4().hex

    # ── Auth boundary ──
    # SECURITY (Phase A, P0 fix 2026-05-13): tenant_id in the body
    # MUST equal the authenticated account_id for EVERY purpose,
    # including `test.*` purposes. There is no longer a test-purpose
    # bypass — the previous exemption allowed user A to forge receipts
    # for user B by passing `tenant_id=B`. The check now mirrors the
    # Engine routes (signals/query, subscriptions) exactly.
    purpose = body.purpose
    if body.tenant_id != current["id"]:
        return _err_response(
            AuthDenied(
                f"tenant_id '{body.tenant_id}' does not match account_id '{current['id']}'"
            ),
            audit_id=None,
        )

    # ── Purpose validation ──
    try:
        purpose_validator.validate_purpose(purpose, internal_caller=False)
    except PurposeInvalid as exc:
        return _err_response(exc, audit_id=None)

    # ── De-identification ──
    try:
        de_id = await deidentifier.deidentify(body.content, tenant_id=body.tenant_id)
    except ServiceUnavailable as exc:
        return _err_response(exc, audit_id=audit_id)
    except Exception as exc:  # noqa: BLE001 — fail-closed catch-all.
        return _err_response(
            ServiceUnavailable(
                f"de-id pipeline failed: {type(exc).__name__}: {str(exc)[:200]}"
            ),
            audit_id=audit_id,
        )

    # ── Outbound LLM call ──
    try:
        llm_text, provider, model, usage = await llm_router.invoke_with_metering(
            de_id.redacted_text, model_preference=body.model_preference,
        )
    except ServiceUnavailable as exc:
        return _err_response(exc, audit_id=audit_id)

    # ── Re-identification ──
    response_text = reidentifier.reidentify(llm_text, de_id.token_map)
    latency_ms = int((time.perf_counter() - started) * 1000)

    # ── Audit + Trust Receipt ──
    timestamp = datetime.now(timezone.utc).isoformat()
    request_hash = trust_receipt.hash_payload(body.content)
    response_hash = trust_receipt.hash_payload(response_text)

    # Chunk 18 (Track 4 item 2, 2026-05-21) — token-accurate metering.
    # Same selection rule as `services.synisense.shield.client.invoke`:
    # prefer the provider SDK usage payload; estimate via char/4 if
    # missing. The audit row records `metering_method` + `actual_cost_usd`
    # so reviewers can opt out of estimated rows for billing-critical
    # queries.
    if usage and usage.get("method") == "exact":
        tokens_in = int(usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("output_tokens") or 0)
        metering_method = "exact"
    else:
        tokens_in = audit_log.estimate_tokens(body.content)
        tokens_out = audit_log.estimate_tokens(response_text)
        metering_method = "estimated"
    actual_cost_usd = audit_log.compute_cost_usd(
        provider=provider, model=model,
        tokens_in=tokens_in, tokens_out=tokens_out,
    )

    try:
        await audit_log.write_audit(
            audit_id=audit_id, tenant_id=body.tenant_id,
            consumer_id=body.consumer_id, user_id=body.user_id,
            purpose=purpose, timestamp=timestamp,
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
            receipt_id=receipt_id, audit_id=audit_id, tenant_id=body.tenant_id,
            consumer_id=body.consumer_id, purpose=purpose, timestamp=timestamp,
            llm_provider=provider, llm_model=model,
            de_id_summary=de_id.de_id_summary,
            dilution_score=de_id.dilution_score,
            exposure_reduction_score=de_id.exposure_reduction_score,
            request_hash=request_hash, response_hash=response_hash,
        )
        await audit_log.write_receipt(receipt)
    except Exception as exc:  # noqa: BLE001 — audit MUST succeed.
        return _err_response(
            ServiceUnavailable(
                f"audit log write failed: {type(exc).__name__}: {str(exc)[:200]}"
            ),
            audit_id=audit_id,
        )

    return ShieldInvokeResponse(
        response=response_text, trust_receipt=receipt, audit_id=audit_id,
    )


@router.get(
    "/audit/{audit_id}",
    responses={
        401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope},
    },
    summary="Retrieve an audit row by audit_id (own tenant only).",
)
async def get_audit(
    audit_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    # Tenant-scoped retrieval — caller can only see their own audit rows
    # (or, in test mode with `test.*` purposes, rows tagged with their
    # account_id OR an explicit `tenant_id` they pass via header). For
    # Phase A we trust the authenticated principal as the tenant.
    row = await audit_log.find_audit(audit_id, tenant_id=current["id"])
    if not row:
        raise HTTPException(status_code=404, detail="audit not found")
    return row


@router.get(
    "/receipt/{audit_id}",
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
    summary="Retrieve a trust receipt by audit_id (own tenant only).",
)
async def get_receipt(
    audit_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Any:
    receipt = await audit_log.find_receipt(audit_id, tenant_id=current["id"])
    if not receipt:
        raise HTTPException(status_code=404, detail="receipt not found")
    return receipt
