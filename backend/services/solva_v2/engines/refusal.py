"""Solva v2 — refusal engine (STUB, Phase 15.0).

Contract (15.3): check the user text against a jailbreak ladder (soft -> hard
block) and therapy-redirect heuristic. For POC, always returns {block: false}.

    run(*, user_text, context) -> {output: {block, reason, ladder_level}, audit}
"""
from __future__ import annotations

import time as _time
from typing import Any, Dict, Optional

ENGINE = "refusal"
ENGINE_VERSION = "refusal@0.1-stub"


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    user_text: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from .llm_adapter_proxy import synthetic_audit_entry

    t0 = _time.monotonic()
    output = {
        "stub": True,
        "block": False,
        "reason": None,
        "ladder_level": None,  # 15.3 introduces {soft, hard, therapy_redirect}
        "user_text_length": len(user_text or ""),
    }
    latency_ms = int((_time.monotonic() - t0) * 1000)
    audit_entry = await synthetic_audit_entry(
        engine=ENGINE,
        layer=layer,
        turn_id=turn_id,
        output={"stub": True, "block": False, "user_text_length": len(user_text or "")},
        tier_labels=[],
        engine_version=ENGINE_VERSION,
        latency_ms=latency_ms,
        shield_required=False,
        shield_bypassed_reason="placeholder_stub",
    )
    return {"output": output, "audit_entry": audit_entry}
