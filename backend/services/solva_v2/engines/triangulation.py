"""Solva v2 — triangulation engine (REAL, Phase 15.0).

Reads db.solve_comparables. Selection order (same logic as v1
_pick_comparables in routers/solva_engine.py:944): same cluster + sector_tag
match -> same cluster + sector_tag='any' -> same cluster + any sector. Caps at
limit=3 to keep the synthesis prompt sharp.

The engine itself does NOT call an LLM. It is a DB query + structured output.
It still writes a reasoning_audit_log entry because every engine invocation is
audited.
"""
from __future__ import annotations

import logging
import time as _time
from typing import Any, Dict, List, Optional

from core import db

logger = logging.getLogger("akki.solva_v2.triangulation")

ENGINE = "triangulation"
ENGINE_VERSION = "triangulation@1.0"


async def run(
    *,
    session: Dict[str, Any],
    turn_id: str,
    layer: str,
    cluster_id: str,
    sector_tag: Optional[str] = None,
    limit: int = 3,
) -> Dict[str, Any]:
    """Return `{output, audit_entry}` where output.comparables is the
    anonymised list of diagnoses to feed into synthesis prompts."""
    from .llm_adapter_proxy import synthetic_audit_entry  # local alias

    t0 = _time.monotonic()
    comparables: List[Dict[str, Any]] = []
    seen: set = set()

    async def _take(filter_q: Dict[str, Any]) -> None:
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
            comparables.append(c)
            if len(comparables) >= limit:
                return

    if sector_tag:
        await _take({"cluster_id": cluster_id, "sector_tag": sector_tag})
    if len(comparables) < limit:
        await _take({"cluster_id": cluster_id, "sector_tag": "any"})
    if len(comparables) < limit:
        await _take({"cluster_id": cluster_id})
    comparables = comparables[:limit]

    latency_ms = int((_time.monotonic() - t0) * 1000)

    output = {
        "cluster_id": cluster_id,
        "sector_tag": sector_tag or "",
        "comparable_count": len(comparables),
        "comparable_ids": [c["id"] for c in comparables],
        "comparables": comparables,
    }
    audit_entry = await synthetic_audit_entry(
        engine=ENGINE,
        layer=layer,
        turn_id=turn_id,
        output={k: v for k, v in output.items() if k != "comparables"},
        tier_labels=["comparable"],
        engine_version=ENGINE_VERSION,
        latency_ms=latency_ms,
        shield_required=False,
        shield_bypassed_reason="deterministic_only",
    )
    return {"output": output, "audit_entry": audit_entry}


def format_for_prompt(comparables: List[Dict[str, Any]]) -> str:
    """Format comparables into the block fed into the synthesis system prompt.
    Mirrors v1 phrasing so behavioural continuity with Solva v1 is preserved."""
    if not comparables:
        return ""
    lines: List[str] = []
    for c in comparables:
        lines.append(
            f"- {c.get('diagnosis_summary','').strip()}\n"
            f"  Worked: {c.get('what_worked','').strip()}\n"
            f"  Didn't: {c.get('what_didnt','').strip()}"
        )
    return (
        "\n\nCURATED COMPARABLES (anonymised, real boards). When useful, "
        "reference them inline as 'A comparable mid-cap bank\u2026' or "
        "'In one industrials case\u2026'. Do NOT name companies. Do not list "
        "all of them \u2014 pick at most one or two that genuinely sharpen "
        "the diagnosis. If none apply, ignore.\n"
        + "\n".join(lines)
    )
