"""Solva v2 — probability_weighting engine (STUB, Phase 15.0).

Takes parsed claims from the grounding contract parser and returns them
unchanged. In Phase 15.1 this engine will assign confidence_band and
confidence_pct to each claim. For 15.0 both stay null.

Contract (15.1):
    run(*, claims) -> {output: {claims: [claim-with-confidence, ...]}, audit}
"""
from __future__ import annotations

import time as _time
from typing import Any, Dict, List

ENGINE = "probability_weighting"
ENGINE_VERSION = "probability_weighting@0.1-stub"


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    claims: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from .llm_adapter_proxy import synthetic_audit_entry

    t0 = _time.monotonic()
    # Pass-through: claims come in with confidence_band=None, confidence_pct=None;
    # we just echo them. 15.1 replaces this.
    weighted: List[Dict[str, Any]] = []
    for c in claims:
        d = dict(c) if isinstance(c, dict) else {"text": str(c), "tier": "domain_prior"}
        d.setdefault("confidence_band", None)
        d.setdefault("confidence_pct", None)
        weighted.append(d)
    latency_ms = int((_time.monotonic() - t0) * 1000)

    output = {
        "stub": True,
        "claim_count": len(weighted),
        "claims": weighted,
    }
    audit_entry = await synthetic_audit_entry(
        engine=ENGINE,
        layer=layer,
        turn_id=turn_id,
        output={"stub": True, "claim_count": len(weighted)},
        tier_labels=sorted({c.get("tier") for c in weighted if isinstance(c, dict) and c.get("tier")}),
        engine_version=ENGINE_VERSION,
        latency_ms=latency_ms,
        shield_required=False,
        shield_bypassed_reason="placeholder_stub",
    )
    return {"output": output, "audit_entry": audit_entry}
