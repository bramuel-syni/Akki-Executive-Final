"""Simulate — qualitative 1y / 3y scenario planning on top of a Context Object.

Takes a hypothesis (free-text) plus optional signals to ground against, and
asks the LLM to produce Best / Base / Stress trajectories with a watchlist of
3 early-warning indicators the board should track.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm, parse_json_response
from core import (
    db, now, iso, write_audit, require_context_membership,
    gather_context_object, docs_overall_trust,
)

router = APIRouter(prefix="/api")


class SimulateIn(BaseModel):
    hypothesis: str = Field(min_length=10, max_length=800)
    horizon: str = Field(default="1y3y", pattern=r"^(1y|3y|1y3y)$")
    signal_ids: Optional[List[str]] = None  # Optional — ground against specific signals
    committee_id: Optional[str] = Field(default=None, max_length=80)


def _build_prompt(
    *,
    context_name: str,
    role: str,
    context_object: Optional[Dict[str, Any]],
    hypothesis: str,
    horizon: str,
    signals_summary: str,
) -> str:
    horizon_line = {
        "1y":   "one-year trajectory",
        "3y":   "three-year trajectory",
        "1y3y": "one-year AND three-year trajectories",
    }.get(horizon, "trajectory")

    return (
        f"You are AKKI, an experienced adviser writing for a senior "
        f"{'non-executive director' if role == 'ned' else 'executive'} on the {context_name} board. "
        f"Write in the serious, specific, no-hype voice of a board paper.\n\n"
        f"Produce a qualitative {horizon_line} for this hypothesis the director is stress-testing:\n"
        f"    « {hypothesis} »\n\n"
        f"{signals_summary}\n\n"
        f"Return JSON only, no preamble:\n"
        f"{{\n"
        f'  "title": "<= 90 chars declarative title capturing the hypothesis",\n'
        f'  "one_year": {{ "best": "1 paragraph", "base": "1 paragraph", "stress": "1 paragraph" }},\n'
        f'  "three_year": {{ "best": "1 paragraph", "base": "1 paragraph", "stress": "1 paragraph" }},\n'
        f'  "watchlist": [\n'
        f'    {{ "indicator": "what to watch (e.g. \'90-day loan arrears rate\')", "early_warning": "threshold that should trigger escalation", "committee": "Audit|Risk|Remuneration|Nominations|ESG|Full board" }},\n'
        f'    {{ ... }},\n'
        f'    {{ ... }}\n'
        f'  ],\n'
        f'  "assumptions": ["2–4 load-bearing assumptions — be specific"],\n'
        f'  "question_for_management": "the single sharpest question the board should put to management in light of this"\n'
        f"}}\n\n"
        f"Rules:\n"
        f"  - Each paragraph 2–4 sentences. No bullets inside a paragraph.\n"
        f"  - Ground in the Context Object if it's informative; otherwise say so plainly.\n"
        f"  - If the horizon is only 1y or only 3y, return the OTHER as null.\n"
    )


@router.post("/contexts/{context_id}/simulate")
async def simulate(
    body: SimulateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    context_name = ctx["context"]["name"]

    my_membership = await db.memberships.find_one(
        {"context_id": context_id, "account_id": ctx["account"]["id"], "status": "active"},
        {"_id": 0, "role": 1},
    )
    my_role = (my_membership or {}).get("role") or "executive"

    # Optional signals grounding
    signals: List[Dict[str, Any]] = []
    if body.signal_ids:
        signals = await db.signals.find(
            {"context_id": context_id, "id": {"$in": body.signal_ids}, "status": "active"},
            {"_id": 0, "id": 1, "type": 1, "headline": 1, "confidence": 1, "sources": 1},
        ).to_list(8)

    signals_summary = ""
    if signals:
        lines = []
        for s in signals:
            lines.append(
                f"  - [{s.get('type','signal')} · {s.get('confidence','medium')} confidence] "
                f"{s.get('headline','')}"
            )
        signals_summary = "Active signals to consider in your reasoning:\n" + "\n".join(lines)

    ctx_obj = await gather_context_object(context_id)
    prompt = _build_prompt(
        context_name=context_name,
        role=my_role,
        context_object=ctx_obj,
        hypothesis=body.hypothesis,
        horizon=body.horizon,
        signals_summary=signals_summary,
    )
    llm_out = await llm_call_llm(
        module="simulate",
        user_query=prompt,
        context_object=ctx_obj,
        session_context={"session_id": f"simulate-{context_id}"},
        data_trust={"overall": "mixed"},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not return a valid simulation. Mode={llm_out.get('mode')}.",
        )

    sim_id = str(uuid.uuid4())
    created_at = iso(now())
    doc = {
        "id": sim_id,
        "context_id": context_id,
        "context_name": context_name,
        "committee_id": body.committee_id,
        "created_by": ctx["account"]["id"],
        "created_at": created_at,
        "hypothesis": body.hypothesis,
        "horizon": body.horizon,
        "role": my_role,
        "title": (parsed.get("title") or f"{context_name} — scenario")[:120],
        "one_year": parsed.get("one_year") if body.horizon in ("1y", "1y3y") else None,
        "three_year": parsed.get("three_year") if body.horizon in ("3y", "1y3y") else None,
        "watchlist": (parsed.get("watchlist") or [])[:6],
        "assumptions": (parsed.get("assumptions") or [])[:6],
        "question_for_management": (parsed.get("question_for_management") or "")[:600],
        "signal_ids": body.signal_ids or [],
        "mode": llm_out.get("mode"),
        "shielding_masked": llm_out.get("shielding", {}).get("identifiers_masked", 0),
        "shielding": llm_out.get("shielding", {}),
        "status": "active",
    }
    await db.simulations.insert_one(doc)
    await write_audit(
        context_id, ctx["account"]["id"], "simulation.created", "simulation", sim_id,
        {"horizon": body.horizon, "mode": llm_out.get("mode")},
    )
    out = dict(doc)
    out.pop("_id", None)
    return out


@router.get("/contexts/{context_id}/simulations")
async def list_simulations(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 50,
    committee_id: Optional[str] = None,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"], "status": "active"}
    if committee_id:
        q["committee_id"] = committee_id
    rows = await db.simulations.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows


@router.get("/contexts/{context_id}/simulations/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    doc = await db.simulations.find_one(
        {"id": simulation_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return doc


@router.delete("/contexts/{context_id}/simulations/{simulation_id}")
async def archive_simulation(
    simulation_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.simulations.update_one(
        {"id": simulation_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"$set": {"status": "archived", "archived_at": iso(now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Simulation not found")
    await write_audit(
        ctx["context"]["id"], ctx["account"]["id"], "simulation.archived", "simulation",
        simulation_id, {},
    )
    return {"ok": True}
