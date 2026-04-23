"""M9 — Learn: on-demand research LLM endpoint."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm, parse_json_response
from core import get_current_account

router = APIRouter(prefix="/api")


class LearnResearchIn(BaseModel):
    topic: str = Field(min_length=3, max_length=200)


@router.post("/learn/research")
async def learn_research(
    body: LearnResearchIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Synthesise a short governance-framed article on any topic the user asks about."""
    prompt = (
        f"A non-executive director or senior executive has asked for a short, board-ready "
        f"briefing on this topic:\n\n    « {body.topic} »\n\n"
        f"Write a piece they can read in 5–7 minutes. Serious, specific, no hype. Write "
        f"as a colleague with governance experience — not as a tool. Do not preamble.\n\n"
        f"Return JSON:\n"
        f'{{\n'
        f'  "title": "<= 80 chars, declarative",\n'
        f'  "kicker": "e.g. Governance · 6 min read",\n'
        f'  "topic": "slug (governance|frameworks|sector-banking|foundations|regulation|risk|vendor|leadership|strategy|custom)",\n'
        f'  "summary": "one sentence distilling the insight",\n'
        f'  "body": "4-7 paragraphs. Specific. Numerate where relevant. Name regulators, frameworks, authorities.",\n'
        f'  "questions_to_ask": ["3-4 sharp questions a NED should put to management"],\n'
        f'  "source_name": "the authoritative body whose material informed this",\n'
        f'  "source_url": "best-effort primary-source URL. Must be plausible."\n'
        f"}}\n"
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
        "mode": llm_out.get("mode"),
    }
