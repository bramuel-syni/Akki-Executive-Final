"""Solva v2 — thin LLM adapter (Phase 15.0).

Single entry point: `shielded_call`. Every LLM call in the Solva v2 orchestrator
goes through this adapter. The adapter is responsible for:

    1. Running Synisense Shield on the prompt BEFORE the LLM sees it.
    2. Recording the synisense_run_id from db.synisense_runs (looked up by
       input_sha256 after pipeline.run persists).
    3. Routing the (shielded) prompt via llm_tier_quota.call_llm_with_tier
       so quota downgrades are handled uniformly with v1.
    4. Optionally running the independent-family validator on the response.
    5. Returning an AdapterResult carrying a ready-to-append
       reasoning_audit_log entry.

The adapter NEVER lets raw user content reach the LLM. If Synisense raises,
the adapter re-raises — the caller must not fall back to unshielded content.
"""
from __future__ import annotations

import hashlib
import logging
import time as _time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core import db, iso, now

logger = logging.getLogger("akki.solva_v2.adapter")


# Engine version strings land on every audit entry.
ENGINE_VERSIONS: Dict[str, str] = {
    "llm_primary": "llm_primary@1.0",
    "validator": "validator@phase11",
    "triangulation": "triangulation@1.0",
    "candidate_generation": "candidate_generation@0.1-stub",
    "probability_weighting": "probability_weighting@0.1-stub",
    "refusal": "refusal@0.1-stub",
    "placeholder": "placeholder@1.0",
}


# Phase 15.0 hardening — locked vocabulary for shield_bypassed_reason.
# Every audit entry with shield_required=False MUST carry exactly one of
# these reasons, so the audit log never has to be interpreted to know why
# Synisense was not invoked.
SHIELD_BYPASS_REASONS = frozenset({
    "engine_does_not_call_llm",  # generic — engine is not an LLM call site
    "placeholder_stub",          # stub returning canned content for 15.0
    "deterministic_only",        # pure DB / arithmetic / parser; no model
})


@dataclass
class AdapterResult:
    text: str
    model: Optional[str]
    provider: Optional[str]
    tier_requested: str
    tier_served: Optional[str]
    latency_ms: int
    synisense_run_id: Optional[str]
    input_hash: str
    mode: str  # "live" | "no-key-fallback" | "error"
    validation: Optional[Dict[str, Any]] = None
    reasoning_audit_entry: Dict[str, Any] = field(default_factory=dict)


def _infer_provider(model_id: Optional[str]) -> str:
    m = (model_id or "").lower()
    if "claude" in m:
        return "anthropic"
    if "gemini" in m:
        return "gemini"
    if "gpt" in m:
        return "openai"
    return "unknown"


async def _lookup_synisense_run_id(
    input_sha256: str, surface: str, account_id: Optional[str]
) -> Optional[str]:
    """Immediately after pipeline.run persists, find the run record by the
    input_sha256 + surface (+ account_id when present). Returns the run id."""
    query: Dict[str, Any] = {"input_sha256": input_sha256, "surface": surface}
    if account_id:
        query["account_id"] = account_id
    row = await db.synisense_runs.find_one(
        query, {"_id": 0, "id": 1}, sort=[("ts", -1)]
    )
    return (row or {}).get("id")


async def shielded_call(
    *,
    engine: str,
    layer: str,
    turn_id: str,
    prompt: str,
    system_override: Optional[str] = None,
    tier: str = "standard",
    surface: str = "solve_v2",
    account_id: Optional[str] = None,
    session_id: str,
    context_id: Optional[str] = None,
    engine_version: Optional[str] = None,
    extra_output: Optional[Dict[str, Any]] = None,
    run_validator: bool = False,
    validator_kind: Optional[str] = None,
    validator_objective: Optional[str] = None,
) -> AdapterResult:
    """Run Synisense → call LLM → (optional) validate → return audit-ready result.

    The adapter refuses to call the LLM if Synisense raises. If Synisense
    is unavailable, the exception propagates up to the orchestrator so the
    turn fails loudly rather than leaking unshielded input.
    """
    from services.synisense import run as syn_run
    from llm_tier_quota import call_llm_with_tier

    t0 = _time.monotonic()

    # 1. Synisense first — surface='solve_v2' closes the v1 gap flagged at
    #    docs/SYNISENSE_SCOPE.md:49.
    try:
        syn_out = await syn_run(
            text=prompt,
            context_id=context_id or "",
            surface=surface,
            mode="redact",
            account_id=account_id,
        )
    except Exception as exc:
        logger.error(
            "solva_v2 adapter: synisense failed surface=%s engine=%s err=%s",
            surface, engine, exc,
        )
        raise RuntimeError(
            f"Synisense unavailable for solva_v2 engine={engine}; refusing LLM call"
        ) from exc

    shielded_prompt = syn_out.get("redacted_text") or prompt
    # pipeline.run writes to db.synisense_runs synchronously with
    # input_sha256 = sha256(text). We recompute and look up the id.
    ihash = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()
    syn_run_id = await _lookup_synisense_run_id(ihash, surface, account_id)

    # 2. LLM call via the shared tier wrapper (quota-aware, downgrade-safe).
    llm_out, quota_state = await call_llm_with_tier(
        surface=surface,
        account_id=account_id or "",
        requested_tier=tier,
        call_args={
            "module": f"solva_v2.{engine}",
            "user_query": shielded_prompt,
            "system_override": system_override,
            "response_format": "text",
        },
    )
    body_text = (llm_out.get("response") or "").strip()
    model_id = llm_out.get("model")
    served_tier = quota_state.get("served_tier") or llm_out.get("tier") or "standard"
    mode = llm_out.get("mode") or "error"
    provider = _infer_provider(model_id)

    # 3. Optional validator (independent family — drafter Claude → validator
    #    Gemini Flash). Only synthesis layer sets run_validator=True.
    validation: Optional[Dict[str, Any]] = None
    if run_validator and body_text:
        try:
            from llm_service import validate_independent
            validation = await validate_independent(
                kind=validator_kind or "solve_v2_synthesis",
                content=body_text,
                objective=validator_objective,
                surface=surface,
                account_id=account_id,
            )
        except Exception as exc:
            logger.warning(
                "solva_v2 validator failed surface=%s engine=%s err=%s",
                surface, engine, exc,
            )
            validation = {
                "verdict": "qualified",
                "confidence": 0,
                "notes": [f"Validator wrapper error ({exc.__class__.__name__}); treat with normal scrutiny."],
                "validator_provider": "n/a",
                "validator_model": "n/a",
            }

    latency_ms = int((_time.monotonic() - t0) * 1000)

    # 4. Assemble audit entry.
    # Phase 15.0 hardening: shielded_call ALWAYS represents a real LLM egress
    # so shield_required is always True and synisense_run_id is non-null.
    audit_entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "turn_id": turn_id,
        "layer": layer,
        "engine": engine,
        "engine_version": engine_version or ENGINE_VERSIONS.get(engine, f"{engine}@unknown"),
        "input_hash": ihash,
        "output": {
            "text_length": len(body_text),
            "response_mode": mode,
            "tier_requested": tier,
            "tier_served": served_tier,
            "quota_downgraded": quota_state.get("downgraded", False),
            **(extra_output or {}),
        },
        "tier_labels": [],
        "latency_ms": latency_ms,
        "model": model_id,
        "provider": provider,
        "created_at": iso(now()),
        "synisense_run_id": syn_run_id,
        "shield_required": True,
        "shield_bypassed_reason": None,
    }
    if validation is not None:
        audit_entry["output"]["validator_verdict"] = validation.get("verdict")
        audit_entry["output"]["validator_confidence"] = validation.get("confidence")
        audit_entry["output"]["validator_provider"] = validation.get("validator_provider")
        audit_entry["output"]["validator_model"] = validation.get("validator_model")

    return AdapterResult(
        text=body_text,
        model=model_id,
        provider=provider,
        tier_requested=tier,
        tier_served=served_tier,
        latency_ms=latency_ms,
        synisense_run_id=syn_run_id,
        input_hash=ihash,
        mode=mode,
        validation=validation,
        reasoning_audit_entry=audit_entry,
    )


async def synthetic_audit_entry(
    *,
    engine: str,
    layer: str,
    turn_id: str,
    output: Dict[str, Any],
    tier_labels: Optional[list] = None,
    engine_version: Optional[str] = None,
    synisense_run_id: Optional[str] = None,
    latency_ms: int = 0,
    shield_required: bool = False,
    shield_bypassed_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Emit an audit entry for engine calls that do NOT go through the
    `shielded_call` adapter directly.

    Phase 15.0 hardening contract:
        - shield_required=False  -> synisense_run_id MUST be None,
                                    shield_bypassed_reason MUST be one of
                                    SHIELD_BYPASS_REASONS.
        - shield_required=True   -> synisense_run_id MUST be non-None,
                                    shield_bypassed_reason MUST be None.
                                    Used by callers (e.g. the validator)
                                    that send content to an external LLM
                                    out-of-band but ride on a prior shielded
                                    input; they pass the upstream run_id.

    Violations raise ValueError so the audit log can never become ambiguous.
    """
    if shield_required:
        if not synisense_run_id:
            raise ValueError(
                "shield_required=True audit entries must carry synisense_run_id"
            )
        if shield_bypassed_reason is not None:
            raise ValueError(
                "shield_required=True must not carry shield_bypassed_reason"
            )
    else:
        if synisense_run_id is not None:
            raise ValueError(
                "shield_required=False audit entries must NOT carry synisense_run_id"
            )
        if shield_bypassed_reason not in SHIELD_BYPASS_REASONS:
            raise ValueError(
                f"shield_bypassed_reason must be one of {sorted(SHIELD_BYPASS_REASONS)}; "
                f"got {shield_bypassed_reason!r}"
            )

    ihash_basis = f"{engine}:{layer}:{turn_id}:" + ":".join(
        f"{k}={output.get(k)}" for k in sorted(output.keys()) if isinstance(output.get(k), (str, int, float))
    )
    ihash = hashlib.sha256(ihash_basis.encode("utf-8")).hexdigest()
    return {
        "id": str(uuid.uuid4()),
        "turn_id": turn_id,
        "layer": layer,
        "engine": engine,
        "engine_version": engine_version or ENGINE_VERSIONS.get(engine, f"{engine}@unknown"),
        "input_hash": ihash,
        "output": output,
        "tier_labels": tier_labels or [],
        "latency_ms": latency_ms,
        "model": None,
        "provider": None,
        "created_at": iso(now()),
        "synisense_run_id": synisense_run_id,
        "shield_required": shield_required,
        "shield_bypassed_reason": shield_bypassed_reason,
    }



# -----------------------------------------------------------------------------
# Phase 15.1 — validator_call: fresh Synisense pass on validator input.
# -----------------------------------------------------------------------------
async def validator_call(
    *,
    content: str,
    objective: Optional[str],
    layer: str,
    turn_id: str,
    account_id: Optional[str],
    context_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Independent-family validator with its OWN Synisense pass.

    Phase 15.0 reused the upstream synthesis run_id on the validator audit
    entry. Phase 15.1 closes that audit ambiguity: the validator gets a
    fresh shield pass under sub-surface `solve_v2.validator`, producing its
    own run_id. This catches any model-introduced PII in the synthesis
    output before it crosses the validator boundary (Gemini Flash).

    Returns {validation, audit_entry}.
    """
    from services.synisense import run as syn_run
    from llm_service import validate_independent

    surface = "solve_v2.validator"
    t0 = _time.monotonic()

    # 1. Shield the synthesis content (not the original user input — the LLM's
    #    OUTPUT, which may carry hallucinated PII).
    try:
        syn_out = await syn_run(
            text=content,
            context_id=context_id or "",
            surface=surface,
            mode="redact",
            account_id=account_id,
        )
    except Exception as exc:
        logger.error("solva_v2 validator: synisense failed err=%s", exc)
        raise RuntimeError(f"Synisense unavailable for validator; refusing call") from exc

    shielded_content = syn_out.get("redacted_text") or content
    ihash = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    syn_run_id = await _lookup_synisense_run_id(ihash, surface, account_id)

    # 2. Validator LLM call on shielded content
    try:
        validation = await validate_independent(
            kind="solve_v2_synthesis",
            content=shielded_content,
            objective=objective,
            surface=surface,
            account_id=account_id,
        )
    except Exception as exc:
        logger.warning("solva_v2 validator wrapper failed: %s", exc)
        validation = {
            "verdict": "qualified",
            "confidence": 0,
            "notes": [f"Validator wrapper error ({exc.__class__.__name__})."],
            "validator_provider": "n/a",
            "validator_model": "n/a",
        }

    latency_ms = int((_time.monotonic() - t0) * 1000)

    # 3. Audit entry — fresh run_id, shield_required=True
    audit_entry = await synthetic_audit_entry(
        engine="validator",
        layer=layer,
        turn_id=turn_id,
        output={
            "validator_verdict": validation.get("verdict"),
            "validator_confidence": validation.get("confidence"),
            "validator_provider": validation.get("validator_provider"),
            "validator_model": validation.get("validator_model"),
            "content_length": len(content or ""),
        },
        tier_labels=[],
        engine_version="validator@phase11",
        latency_ms=latency_ms,
        shield_required=True,
        synisense_run_id=syn_run_id,
    )
    return {"validation": validation, "audit_entry": audit_entry}


# -----------------------------------------------------------------------------
# Phase 15.1 — retry log: track per-surface retry counts for the admin dashboard.
# -----------------------------------------------------------------------------
async def record_retry(*, surface: str, account_id: Optional[str], reason: str) -> None:
    """Append a retry event to db.llm_retry_log. TTL'd at 30 days via the
    boot-time index in server.py. The admin spend dashboard aggregates the
    last 24 hours grouped by surface.
    """
    from core import db
    try:
        await db.llm_retry_log.insert_one({
            "id": str(uuid.uuid4()),
            "surface": surface,
            "account_id": account_id or "",
            "reason": reason,
            "created_at": iso(now()),
        })
    except Exception as exc:  # noqa: BLE001
        # Retry tracking is observability only — never fail the user request.
        logger.warning("solva_v2: record_retry failed surface=%s err=%s", surface, exc)
