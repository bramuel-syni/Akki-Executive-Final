"""M14 — Lens Room.

Six structured frameworks that a board can ask AKKI to apply to any
signal, document, or hypothesis:

  1. First Principles      — strip to the irreducible facts, then rebuild
  2. Customer Obsession    — what does the customer actually experience?
  3. Systems Thinking      — second- and third-order effects
  4. Capital Discipline    — unit economics, IRR, opportunity cost
  5. Stakeholder Integration — employees, regulators, communities
  6. Organisational Culture — what must the team believe for this to work?

Each lens returns a 3-section output: OBSERVATION · IMPLICATION · ACTION —
plus the single question the board should put to management.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm, parse_json_response
from core import (
    db, now, iso, write_audit, require_context_membership,
    gather_context_object,
)

router = APIRouter(prefix="/api")


LENS_CATALOG = {
    "first_principles": {
        "name": "First Principles",
        "hint": "Strip the situation to the irreducible facts. Then rebuild the conclusion.",
    },
    "customer_obsession": {
        "name": "Customer Obsession",
        "hint": "Walk through what the customer actually experiences. Name friction honestly.",
    },
    "systems_thinking": {
        "name": "Systems Thinking",
        "hint": "Map second- and third-order effects. What does this feedback loop produce at steady state?",
    },
    "capital_discipline": {
        "name": "Capital Discipline",
        "hint": "Pressure-test the unit economics, IRR, payback, and opportunity cost. Be numerate.",
    },
    "stakeholder_integration": {
        "name": "Stakeholder Integration",
        "hint": "Who is affected beyond shareholders — employees, regulators, communities, vendors?",
    },
    "organisational_culture": {
        "name": "Organisational Culture",
        "hint": "What would the team have to believe and reward for this to actually work?",
    },
}


class LensRunIn(BaseModel):
    lens: str = Field(min_length=1, max_length=40)  # key of LENS_CATALOG
    subject: str = Field(min_length=10, max_length=1200)  # what to apply the lens to
    signal_id: Optional[str] = None
    committee_id: Optional[str] = Field(default=None, max_length=80)


@router.get("/lens/catalog")
async def lens_catalog():
    """Public-to-authenticated catalog of available lenses."""
    return [{"id": k, **v} for k, v in LENS_CATALOG.items()]


@router.post("/contexts/{context_id}/lens/run")
async def run_lens(
    body: LensRunIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    context_name = ctx["context"]["name"]

    lens_def = LENS_CATALOG.get(body.lens)
    if not lens_def:
        raise HTTPException(status_code=400, detail=f"Unknown lens '{body.lens}'.")

    # Optional signal grounding
    signal = None
    if body.signal_id:
        signal = await db.signals.find_one(
            {"id": body.signal_id, "context_id": context_id, "status": "active"},
            {"_id": 0, "id": 1, "type": 1, "headline": 1, "summary": 1, "sources": 1},
        )

    my_membership = await db.memberships.find_one(
        {"context_id": context_id, "account_id": ctx["account"]["id"], "status": "active"},
        {"_id": 0, "role": 1},
    )
    my_role = (my_membership or {}).get("role") or "executive"

    ctx_obj = await gather_context_object(context_id)

    sig_block = ""
    if signal:
        sig_block = (
            f"[SIGNAL YOU ARE EXAMINING THROUGH THIS LENS]\n"
            f"type: {signal.get('type','signal')}\n"
            f"headline: {signal.get('headline','')}\n"
            f"summary: {signal.get('summary','')}\n\n"
        )

    prompt = (
        f"You are AKKI, an adviser to a senior "
        f"{'non-executive director' if my_role == 'ned' else 'executive'} on the "
        f"{context_name} board. Apply the **{lens_def['name']}** lens to the "
        f"subject below. Hint: {lens_def['hint']}\n\n"
        f"[SUBJECT]\n« {body.subject} »\n\n"
        f"{sig_block}"
        f"Be serious, specific, numerate where you can. Avoid generic advice. Do "
        f"not preamble. Return JSON only:\n"
        f"{{\n"
        f'  "observation": "2–4 sentences — what the lens makes visible that is not otherwise visible.",\n'
        f'  "implication": "2–4 sentences — what it therefore means for governance / execution.",\n'
        f'  "action": "2–4 sentences — what the board or executive should now do, and by when.",\n'
        f'  "question_for_management": "the single sharpest question to raise at the next meeting",\n'
        f'  "confidence": "high|medium|low — how robust this reading is to the information at hand"\n'
        f"}}\n"
    )

    llm_out = await llm_call_llm(
        module="lens",
        user_query=prompt,
        context_object=ctx_obj,
        session_context={"session_id": f"lens-{context_id}"},
        data_trust={"overall": "mixed"},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not return a valid lens output. Mode={llm_out.get('mode')}.",
        )

    run_id = str(uuid.uuid4())
    created_at = iso(now())
    doc = {
        "id": run_id,
        "context_id": context_id,
        "context_name": context_name,
        "committee_id": body.committee_id,
        "lens": body.lens,
        "lens_name": lens_def["name"],
        "subject": body.subject,
        "signal_id": body.signal_id,
        "signal_snapshot": signal,
        "observation": (parsed.get("observation") or "")[:2000],
        "implication": (parsed.get("implication") or "")[:2000],
        "action": (parsed.get("action") or "")[:2000],
        "question_for_management": (parsed.get("question_for_management") or "")[:600],
        "confidence": parsed.get("confidence") if parsed.get("confidence") in ("high", "medium", "low") else "medium",
        "created_by": ctx["account"]["id"],
        "created_at": created_at,
        "role": my_role,
        "mode": llm_out.get("mode"),
        "shielding_masked": llm_out.get("shielding", {}).get("identifiers_masked", 0),
        "shielding": llm_out.get("shielding", {}),
        "status": "active",
    }
    await db.lens_runs.insert_one(doc)
    out = dict(doc)
    out.pop("_id", None)
    await write_audit(
        context_id, ctx["account"]["id"], "lens.run", "lens_run", run_id,
        {"lens": body.lens, "mode": llm_out.get("mode")},
    )
    return out


@router.get("/contexts/{context_id}/lens/runs")
async def list_lens_runs(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 50,
    lens: Optional[str] = None,
    committee_id: Optional[str] = None,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"], "status": "active"}
    if lens:
        q["lens"] = lens
    if committee_id:
        q["committee_id"] = committee_id
    rows = await db.lens_runs.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows


@router.get("/contexts/{context_id}/lens/runs/{run_id}")
async def get_lens_run(
    run_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    doc = await db.lens_runs.find_one(
        {"id": run_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Lens run not found")
    return doc


@router.delete("/contexts/{context_id}/lens/runs/{run_id}")
async def archive_lens_run(
    run_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.lens_runs.update_one(
        {"id": run_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"$set": {"status": "archived", "archived_at": iso(now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lens run not found")
    await write_audit(
        ctx["context"]["id"], ctx["account"]["id"], "lens.archived", "lens_run", run_id, {},
    )
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────
# Lens Coach — multi-turn chat through a chosen lens.
#
# A coaching session is a thread of messages where AKKI replies in the
# voice of the selected lens. The lens can be switched mid-thread; the
# next reply is generated through the new lens but the conversation
# history stays intact (so the user can compare framings).
# ─────────────────────────────────────────────────────────────────────────
class CoachStartIn(BaseModel):
    lens: str = Field(min_length=1, max_length=40)
    subject: str = Field(min_length=2, max_length=200)


class CoachMessageIn(BaseModel):
    lens: str = Field(min_length=1, max_length=40)
    message: str = Field(min_length=1, max_length=4000)


COACH_SYSTEM = (
    "You are AKKI, an executive thinking partner. The user has chosen a "
    "specific mental-model lens for this conversation. Reply in the voice "
    "and frame of that lens. Be concrete, ask sharp clarifying questions, "
    "challenge sloppy thinking, and refuse to give generic advice.\n\n"
    "Format: 1-3 short paragraphs. End with ONE question that pulls the "
    "user one step deeper. Never use bullet lists unless the user asks.\n\n"
    "Tell the user when their question is outside what this lens can see "
    "and suggest the lens that would see it better."
)


def _coach_prompt(lens_id: str, history: List[Dict[str, str]], next_message: str) -> str:
    lens = LENS_CATALOG.get(lens_id) or {"name": lens_id, "hint": ""}
    lines = [
        COACH_SYSTEM,
        "",
        f"Active lens: {lens['name']}",
        f"Lens posture: {lens['hint']}",
        "",
        "Conversation so far:",
    ]
    for m in history[-12:]:  # last 12 turns is plenty for coaching
        role = "USER" if m.get("role") == "user" else "AKKI"
        lines.append(f"{role}: {m.get('content', '').strip()}")
    lines.append("")
    lines.append(f"USER: {next_message.strip()}")
    lines.append(f"AKKI (through {lens['name']}):")
    return "\n".join(lines)


@router.post("/contexts/{context_id}/lens/coach/sessions")
async def start_coach_session(
    context_id: str,
    body: CoachStartIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if body.lens not in LENS_CATALOG:
        raise HTTPException(status_code=400, detail="Unknown lens")
    sid = str(uuid.uuid4())
    now_iso = iso(now())
    session = {
        "id": sid, "context_id": context_id,
        "subject": body.subject.strip(), "lens": body.lens,
        "messages": [],
        "owner_id": ctx["account"]["id"],
        "owner_name": ctx["account"].get("name") or ctx["account"]["email"],
        "status": "active",
        "created_at": now_iso, "updated_at": now_iso,
    }
    await db.lens_coach_sessions.insert_one(session.copy())
    session.pop("_id", None)
    return session


@router.get("/contexts/{context_id}/lens/coach/sessions")
async def list_coach_sessions(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    cursor = db.lens_coach_sessions.find(
        {"context_id": context_id, "owner_id": ctx["account"]["id"], "status": "active"},
        {"_id": 0},
    ).sort("updated_at", -1).limit(50)
    items = await cursor.to_list(50)
    # Strip messages on the index — list view shows previews only.
    for it in items:
        msgs = it.get("messages") or []
        it["last_message_preview"] = (msgs[-1].get("content") if msgs else "")[:160]
        it["message_count"] = len(msgs)
        it.pop("messages", None)
    return items


@router.get("/contexts/{context_id}/lens/coach/sessions/{sid}")
async def get_coach_session(
    context_id: str, sid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    s = await db.lens_coach_sessions.find_one(
        {"id": sid, "context_id": context_id, "owner_id": ctx["account"]["id"]},
        {"_id": 0},
    )
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.post("/contexts/{context_id}/lens/coach/sessions/{sid}/messages")
async def post_coach_message(
    context_id: str, sid: str,
    body: CoachMessageIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if body.lens not in LENS_CATALOG:
        raise HTTPException(status_code=400, detail="Unknown lens")
    s = await db.lens_coach_sessions.find_one(
        {"id": sid, "context_id": context_id, "owner_id": ctx["account"]["id"]},
        {"_id": 0},
    )
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    history = s.get("messages") or []
    prompt = _coach_prompt(body.lens, history, body.message)
    out = await llm_call_llm(
        module="lens.coach",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"lens-coach-{sid}"},
        data_trust={"overall": "trusted"},
    )
    reply_text = (out.get("response") or "").strip()
    if not reply_text:
        raise HTTPException(status_code=502, detail="The lens didn't return a reply.")

    now_iso = iso(now())
    user_turn = {"role": "user", "content": body.message.strip(), "lens": body.lens, "at": now_iso}
    akki_turn = {"role": "akki", "content": reply_text, "lens": body.lens, "at": now_iso, "mode": out.get("mode")}
    await db.lens_coach_sessions.update_one(
        {"id": sid},
        {
            "$push": {"messages": {"$each": [user_turn, akki_turn]}},
            "$set": {"lens": body.lens, "updated_at": now_iso},
        },
    )
    return {"user": user_turn, "akki": akki_turn}


@router.delete("/contexts/{context_id}/lens/coach/sessions/{sid}")
async def archive_coach_session(
    context_id: str, sid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.lens_coach_sessions.update_one(
        {"id": sid, "context_id": context_id, "owner_id": ctx["account"]["id"]},
        {"$set": {"status": "archived", "archived_at": iso(now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}
