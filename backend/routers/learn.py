"""M9 — Learn: on-demand research LLM endpoint."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm, parse_json_response
from core import get_current_account, db

router = APIRouter(prefix="/api")


class LearnResearchIn(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    context_id: Optional[str] = Field(default=None, description="Active context id — used to weight the research to the user's sector/jurisdiction.")


def _personalisation_clause(ctx: Optional[Dict[str, Any]]) -> str:
    """Compose a short personalisation paragraph based on the user's active
    context. Returns '' if no usable signals are present. This is what turns a
    generic governance article into e.g. a Kenyan-banking-flavoured one."""
    if not ctx:
        return ""
    bits = []
    sector = (ctx.get("sector") or ctx.get("industry") or "").strip()
    jurisdiction = (ctx.get("jurisdiction") or "").strip()
    name = (ctx.get("name") or "").strip()
    ctype = (ctx.get("type") or "").strip()
    if sector:
        bits.append(f"sector: {sector}")
    if jurisdiction:
        bits.append(f"jurisdiction: {jurisdiction}")
    if ctype:
        bits.append(f"board type: {ctype.replace('_', ' ')}")
    if not bits:
        return ""
    lead = (
        f"The reader serves on '{name}'. Weight the piece to their situation: "
        if name
        else "Weight the piece to the reader's situation: "
    )
    return (
        lead
        + "; ".join(bits)
        + ". Where a regulator is mentioned, name the one that actually supervises this "
          "jurisdiction (e.g. CBK/CMA for Kenya, FCA/PRA for the UK, SEC/OCC for the US, "
          "SARB/FSCA for South Africa, CBN/SEC for Nigeria, MAS for Singapore, EBA/ECB for EU). "
          "Where statistics are invoked, prefer figures from sources that cover this region. "
          "If the topic has no regional variation, say so plainly rather than inventing local colour."
    )


@router.post("/learn/research")
async def learn_research(
    body: LearnResearchIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Synthesise a short governance-framed article on any topic the user asks
    about. When `context_id` is supplied and the user is a member of that
    context, the LLM is asked to weight the piece to that context's sector
    and jurisdiction — so a Kenyan NED researching 'vendor AI oversight'
    gets CBK-flavoured sources, not generic SEC ones."""
    ctx = None
    if body.context_id:
        # Best-effort: only personalise if the user is actually a member
        membership = await db.memberships.find_one(
            {"context_id": body.context_id, "account_id": current["id"]},
            {"_id": 0, "context_id": 1},
        )
        if membership:
            ctx = await db.contexts.find_one(
                {"id": body.context_id},
                {"_id": 0, "name": 1, "sector": 1, "industry": 1, "jurisdiction": 1, "type": 1},
            )
    personalisation = _personalisation_clause(ctx)
    header = (
        f"A non-executive director or senior executive has asked for a short, board-ready "
        f"briefing on this topic:\n\n    « {body.topic} »\n\n"
    )
    if personalisation:
        header += personalisation + "\n\n"
    prompt = header + (
        "Write a piece they can read in 5–7 minutes. Serious, specific, no hype. Write "
        "as a colleague with governance experience — not as a tool. Do not preamble.\n\n"
        "Return JSON:\n"
        '{\n'
        '  "title": "<= 80 chars, declarative",\n'
        '  "kicker": "e.g. Governance · 6 min read",\n'
        '  "topic": "slug (governance|frameworks|sector-banking|foundations|regulation|risk|vendor|leadership|strategy|custom)",\n'
        '  "summary": "one sentence distilling the insight",\n'
        '  "body": "4-7 paragraphs. Specific. Numerate where relevant. Name regulators, frameworks, authorities.",\n'
        '  "questions_to_ask": ["3-4 sharp questions a NED should put to management"],\n'
        '  "source_name": "the authoritative body whose material informed this",\n'
        '  "source_url": "best-effort primary-source URL. Must be plausible."\n'
        "}\n"
    )
    llm_out = await llm_call_llm(
        module="learn-research",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"learn-{current['id']}"},
        data_trust={"overall": "trusted"},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict) or not parsed.get("body"):
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not produce an article. Mode={llm_out.get('mode')}.",
        )
    return {
        "id": f"ad-hoc-{uuid.uuid4().hex[:8]}",
        "title": (parsed.get("title") or body.topic)[:120],
        "kicker": (parsed.get("kicker") or "Research · on-demand")[:80],
        "topic": (parsed.get("topic") or "custom")[:40],
        "audience": ["ned", "executive"],
        "source_name": (parsed.get("source_name") or "AKKI synthesis")[:120],
        "source_url": (parsed.get("source_url") or "")[:500],
        "summary": (parsed.get("summary") or "")[:400],
        "body": (parsed.get("body") or "")[:6000],
        "questions_to_ask": (parsed.get("questions_to_ask") or [])[:6],
        "generated": True,
        "personalised": bool(personalisation),
        "personalisation_from": {
            "sector": (ctx or {}).get("sector") or (ctx or {}).get("industry"),
            "jurisdiction": (ctx or {}).get("jurisdiction"),
        } if personalisation else None,
        "mode": llm_out.get("mode"),
    }
