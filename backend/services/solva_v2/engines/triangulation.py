"""Solva v2 — triangulation engine (REAL, Phase 15.1).

Reads db.solve_comparables. Selection priority:
    1. cluster_id + sector_tag exact match    -> priority_match='sector_match'
    2. cluster_id + sector_tag='any'          -> priority_match='cluster_any'
    3. cluster_id + any sector                -> priority_match='cluster'

Each returned comparable carries `priority_match` so the synthesis prompt
can weight tighter matches more heavily. Caps at limit=3.

No LLM call; no Synisense (the only inputs are cluster_id + sector_tag,
not user content). Audit entry is shield_required=False, deterministic_only.

When zero comparables match (the cluster has no curated entries OR the seed
is empty), the engine returns an empty list with output.empty_reason='no_match'
and the synthesis layer must handle the zero-comparable case gracefully
(tier-label heavier on domain_prior and speculation).
"""
from __future__ import annotations

import logging
import time as _time
from typing import Any, Dict, List, Optional

from core import db

logger = logging.getLogger("akki.solva_v2.triangulation")

ENGINE = "triangulation"
ENGINE_VERSION = "triangulation@1.0"
SURFACE = "solve_v2.triangulation"  # used in the audit input_hash basis


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    cluster_id: str,
    sector_tag: Optional[str] = None,
    limit: int = 3,
) -> Dict[str, Any]:
    from .llm_adapter_proxy import synthetic_audit_entry

    t0 = _time.monotonic()
    comparables: List[Dict[str, Any]] = []
    seen: set = set()

    async def _take(filter_q: Dict[str, Any], priority_match: str) -> None:
        async for c in db.solve_comparables.find(
            filter_q,
            {
                "_id": 0,
                "id": 1,
                "cluster_id": 1,
                "sector_tag": 1,
                "scale_tag": 1,
                "diagnosis_summary": 1,
                "what_worked": 1,
                "what_didnt": 1,
            },
        ):
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            c["priority_match"] = priority_match
            comparables.append(c)
            if len(comparables) >= limit:
                return

    if sector_tag:
        await _take({"cluster_id": cluster_id, "sector_tag": sector_tag}, "sector_match")
    if len(comparables) < limit:
        await _take({"cluster_id": cluster_id, "sector_tag": "any"}, "cluster_any")
    if len(comparables) < limit:
        await _take({"cluster_id": cluster_id}, "cluster")
    comparables = comparables[:limit]

    latency_ms = int((_time.monotonic() - t0) * 1000)
    empty_reason = "no_match" if not comparables else None

    output = {
        "cluster_id": cluster_id,
        "sector_tag": sector_tag or "",
        "comparable_count": len(comparables),
        "comparable_ids": [c["id"] for c in comparables],
        "comparables": comparables,
        "empty_reason": empty_reason,
    }
    audit_entry = await synthetic_audit_entry(
        engine=ENGINE,
        layer=layer,
        turn_id=turn_id,
        output={k: v for k, v in output.items() if k != "comparables"},
        tier_labels=["comparable"] if comparables else [],
        engine_version=ENGINE_VERSION,
        latency_ms=latency_ms,
        shield_required=False,
        shield_bypassed_reason="deterministic_only",
    )
    return {"output": output, "audit_entry": audit_entry}


def format_for_prompt(comparables: List[Dict[str, Any]]) -> str:
    """Format comparables for inclusion in the synthesis system prompt.

    Phase 15.1: include priority_match so the model can weight tight
    sector-matches more heavily than cluster-only matches.
    """
    if not comparables:
        return (
            "\n\nNO CURATED COMPARABLES match this cluster + sector. Lean on "
            "domain_prior / speculation tier labels and acknowledge the "
            "absence of comparable evidence in your diagnosis.\n"
        )
    lines: List[str] = []
    for c in comparables:
        weight = {
            "sector_match": "strong",
            "cluster_any": "medium",
            "cluster": "loose",
        }.get(c.get("priority_match", "cluster"), "loose")
        lines.append(
            f"- [{weight} match] {(c.get('diagnosis_summary') or '').strip()}\n"
            f"  Worked: {(c.get('what_worked') or '').strip()}\n"
            f"  Didn't: {(c.get('what_didnt') or '').strip()}"
        )
    return (
        "\n\nCURATED COMPARABLES (anonymised, real boards). Reference inline "
        "as 'A comparable mid-cap bank\u2026' or 'In one industrials case\u2026'. "
        "Do NOT name companies. Pick at most one or two that genuinely "
        "sharpen the diagnosis. Strong matches are worth more weight than "
        "loose ones; if all matches are loose, lean on domain_prior tier.\n"
        + "\n".join(lines)
    )
