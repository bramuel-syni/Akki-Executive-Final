"""Shield invoker — the SINGLE chokepoint for Solva Phase D LLM calls.

Every reasoning model in Phase D routes through this helper. It:
  1. Calls `services.synisense.shield.client.invoke()` with the declared
     `solva.layer_*` purpose.
  2. Captures the `audit_id` + `trust_receipt` returned by Shield.
  3. Appends the audit_id to the session's `synisense_audit_ids` array.
  4. Appends an `OrchestrationEntry` to the session's
     `orchestration_audit_log` (cross-references the audit_id).
  5. Returns the LLM response text to the caller.

If Shield raises, this helper re-raises — there is no fallback path that
bypasses Synisense. Solva treats Synisense unavailability as a normal
operating state per `briefs/SOLVA.md §9.5`.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.synisense.shield.client import invoke as shield_invoke


DEFAULT_CONSUMER_ID = "solva.phase_d"


@dataclass
class ShieldInvokeResult:
    response_text: str
    audit_id: str
    trust_receipt: Dict[str, Any]
    latency_ms: int
    orchestration_entry: Dict[str, Any]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def invoke_via_shield(
    *,
    purpose: str,
    prompt: str,
    tenant_id: str,
    user_id: str,
    layer: str,
    engine: str,
    engine_version: str,
    consumer_id: str = DEFAULT_CONSUMER_ID,
    model_preference: str = "balanced",
    input_hash: Optional[str] = None,
    output_summary: Optional[Dict[str, Any]] = None,
) -> ShieldInvokeResult:
    """Run a Shield-routed LLM call and prepare an audit entry for the
    caller to append to the session record.

    The caller is responsible for the Mongo $push (we do not own the
    session document here — keeps this helper testable without a db
    fixture).
    """
    started = time.perf_counter()
    result = await shield_invoke(
        purpose=purpose,
        content=prompt,
        tenant_id=tenant_id,
        consumer_id=consumer_id,
        user_id=user_id,
        model_preference=model_preference,  # type: ignore[arg-type]
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    audit_id = result["audit_id"]
    response = result["response"]
    trust_receipt = result["trust_receipt"]

    entry = {
        "id": "orch-" + uuid.uuid4().hex,
        "layer": layer,
        "engine": engine,
        "engine_version": engine_version,
        "timestamp": _now_iso(),
        "input_hash": input_hash,
        "output_summary": output_summary or {"response_length": len(response or "")},
        "synisense_audit_id": audit_id,
        "shield_required": True,
        "shield_bypass_reason": None,
        "latency_ms": latency_ms,
    }
    return ShieldInvokeResult(
        response_text=response,
        audit_id=audit_id,
        trust_receipt=trust_receipt,
        latency_ms=latency_ms,
        orchestration_entry=entry,
    )


def build_orchestration_entry_deterministic(
    *,
    layer: str,
    engine: str,
    engine_version: str,
    output_summary: Dict[str, Any],
    bypass_reason: str = "deterministic_only",
) -> Dict[str, Any]:
    """Build an orchestration log entry for a deterministic reasoning
    step (no LLM call). Used by the state machine, probability
    weighting, and refusal logic when they run pure-rule code paths.
    """
    return {
        "id": "orch-" + uuid.uuid4().hex,
        "layer": layer,
        "engine": engine,
        "engine_version": engine_version,
        "timestamp": _now_iso(),
        "input_hash": None,
        "output_summary": output_summary,
        "synisense_audit_id": None,
        "shield_required": False,
        "shield_bypass_reason": bypass_reason,
        "latency_ms": 0,
    }
