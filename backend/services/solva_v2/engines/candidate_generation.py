"""Solva v2 — candidate_generation engine (STUB, Phase 15.0).

Returns a deterministic placeholder tagged `domain_prior`. Interface matches
what 15.1 will implement: given the user intent + cluster + any triangulation
output, emit candidate framings / hypotheses the synthesis layer can weigh.

Contract (for 15.1 compatibility):
    async def run(*, session, turn_id, layer, intent, cluster, comparables) ->
        {output: {candidates: [{text, rationale, tier}, ...]},
         audit_entry: {...}}
"""
from __future__ import annotations

import time as _time
from typing import Any, Dict, List, Optional

ENGINE = "candidate_generation"
ENGINE_VERSION = "candidate_generation@0.1-stub"


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    intent: str,
    cluster: Dict[str, Any],
    comparables: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Stub: return a single deterministic candidate tagged domain_prior.

    Real 15.1 version generates 2-3 candidate framings via a standard-tier
    LLM call, each with rationale and tier suggestion. Keeps the interface
    stable.
    """
    from .llm_adapter_proxy import synthetic_audit_entry

    t0 = _time.monotonic()
    candidates: List[Dict[str, Any]] = [
        {
            "text": "Stub candidate framing: " + (cluster.get("label") or "cluster"),
            "rationale": "15.0 stub output — replace in Phase 15.1.",
            "tier": "domain_prior",
        }
    ]
    latency_ms = int((_time.monotonic() - t0) * 1000)

    output = {
        "stub": True,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    audit_entry = await synthetic_audit_entry(
        engine=ENGINE,
        layer=layer,
        turn_id=turn_id,
        output={"stub": True, "candidate_count": len(candidates)},
        tier_labels=["domain_prior"],
        engine_version=ENGINE_VERSION,
        latency_ms=latency_ms,
        shield_required=False,
        shield_bypassed_reason="placeholder_stub",
    )
    return {"output": output, "audit_entry": audit_entry}
