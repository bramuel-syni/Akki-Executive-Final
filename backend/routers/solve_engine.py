"""AKKI Solve · 4-phase session engine.

Iter61 Wave 1 — the framework execution. Each Solve session walks the user
through Surface → Depth → Synthesis → Lock-in, posting one user turn and
one Solve turn per phase. The session is persisted on every turn so save &
resume is trivial.

Tiering (per iter58 user direction):
  - FREE accounts get Sonnet (`tier=standard`) for synthesis.
  - PRO accounts get Opus (`tier=deep`) for synthesis, charged against
    a SEPARATE per-day budget surface (`solve` in llm_deep_usage) so it
    doesn't compete with Decks/Brief budgets.

Triangulation v1 — evolutionary build (per iter58). At Synthesis we look
up the active cluster's `comparable_diagnoses` from the cluster doc; if
absent, we ask the LLM to surface 2 plausible comparables in-prompt. The
real curated comparable corpus lands in Wave 3.

Endpoints:
  GET  /api/solve/clusters
  POST /api/solve/sessions                                start a session
  GET  /api/solve/sessions                                list user's sessions
  GET  /api/solve/sessions/{sid}                          fetch one
  POST /api/solve/sessions/{sid}/turn                     post user input + advance phase
  POST /api/solve/sessions/{sid}/regenerate-current       redo current phase reply
  POST /api/solve/sessions/{sid}/restart                  start fresh session (clones cluster + intent)
  POST /api/solve/sessions/{sid}/abandon                  mark abandoned (won't show in resume)
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now

logger = logging.getLogger("akki.solve.engine")

router = APIRouter(prefix="/api/solve", tags=["solve"])


PHASES: List[str] = ["surface", "depth", "synthesis", "lockin"]


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------
class StartIn(BaseModel):
    cluster_id: str = Field(min_length=2, max_length=80)
    intent: str = Field(min_length=20, max_length=1200)
    context_id: Optional[str] = None  # optional: link to a NED/Exec context
    pro_tier: bool = False  # client requests deep synthesis (Opus)


class TurnIn(BaseModel):
    user_text: str = Field(min_length=2, max_length=4000)


# ---------------------------------------------------------------------------
# Tiering helper
# ---------------------------------------------------------------------------
async def _user_is_pro(account: Dict[str, Any]) -> bool:
    """True if the account has the Pro flag (paid). For now the flag is
    `account.solve_pro` — promote to a proper subscription record in Wave 2."""
    return bool(account.get("solve_pro"))


# ---------------------------------------------------------------------------
# Cluster lookup
# ---------------------------------------------------------------------------
@router.get("/clusters")
async def list_clusters(account: Dict[str, Any] = Depends(get_current_account)):
    rows = await db.solve_clusters.find({}, {"_id": 0}).to_list(length=50)
    return {"clusters": rows, "count": len(rows)}


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------
@router.post("/sessions")
async def start_session(body: StartIn, account: Dict[str, Any] = Depends(get_current_account)):
    cluster = await db.solve_clusters.find_one({"id": body.cluster_id}, {"_id": 0})
    if not cluster:
        raise HTTPException(status_code=404, detail="Unknown cluster.")

    session_id = str(uuid.uuid4())
    is_pro_request = body.pro_tier and await _user_is_pro(account)

    rec = {
        "id": session_id,
        "account_id": account["id"],
        "context_id": body.context_id,
        "cluster_id": body.cluster_id,
        "cluster_label": cluster.get("label"),
        "intent": body.intent.strip(),
        "phase": PHASES[0],
        "phase_index": 0,
        "status": "active",
        "pro_tier": is_pro_request,
        "turns": [],
        "synthesis": None,
        "lockin": None,
        "started_at": iso(now()),
        "updated_at": iso(now()),
        "completed_at": None,
    }
    await db.solve_sessions.insert_one(rec)

    # Generate Surface phase opening immediately so user lands on a primed
    # session, not an empty one.
    primer = await _generate_phase_response(rec, cluster, "surface", is_first=True)
    await _append_turn(session_id, role="solve", text=primer["text"], phase="surface",
                       model=primer.get("model"), tier=primer.get("tier"))
    rec["turns"].append({
        "id": str(uuid.uuid4()),
        "role": "solve",
        "phase": "surface",
        "text": primer["text"],
        "model": primer.get("model"),
        "tier": primer.get("tier"),
        "created_at": iso(now()),
    })
    rec.pop("_id", None)
    return rec


@router.get("/sessions")
async def list_my_sessions(
    status: Optional[str] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    q: Dict[str, Any] = {"account_id": account["id"]}
    if status:
        q["status"] = status
    rows = await db.solve_sessions.find(
        q,
        {"_id": 0, "id": 1, "cluster_id": 1, "cluster_label": 1, "intent": 1,
         "phase": 1, "phase_index": 1, "status": 1, "pro_tier": 1,
         "started_at": 1, "updated_at": 1, "completed_at": 1},
    ).sort("updated_at", -1).to_list(length=100)
    return {"items": rows, "count": len(rows)}


@router.get("/sessions/{sid}")
async def get_session(sid: str, account: Dict[str, Any] = Depends(get_current_account)):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    return rec


@router.post("/sessions/{sid}/turn")
async def post_turn(
    sid: str,
    body: TurnIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    if rec.get("status") != "active":
        raise HTTPException(status_code=409, detail=f"Session is {rec['status']}.")

    cluster = await db.solve_clusters.find_one({"id": rec["cluster_id"]}, {"_id": 0})
    if not cluster:
        raise HTTPException(status_code=410, detail="Cluster has been removed.")

    current_phase = rec["phase"]

    # Append user turn
    user_turn = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "phase": current_phase,
        "text": body.user_text.strip(),
        "created_at": iso(now()),
    }
    await _append_turn(sid, role="user", text=body.user_text.strip(), phase=current_phase)
    rec["turns"].append(user_turn)

    # Decide whether to advance: each phase takes one user reply then Solve
    # responds and advances.
    advance_to = _next_phase(current_phase)

    # Generate Solve response for the current phase
    response = await _generate_phase_response(rec, cluster, current_phase)
    solve_turn = {
        "id": str(uuid.uuid4()),
        "role": "solve",
        "phase": current_phase,
        "text": response["text"],
        "model": response.get("model"),
        "tier": response.get("tier"),
        "created_at": iso(now()),
    }
    await _append_turn(sid, role="solve", text=response["text"], phase=current_phase,
                       model=response.get("model"), tier=response.get("tier"))
    rec["turns"].append(solve_turn)

    update_fields: Dict[str, Any] = {"updated_at": iso(now())}

    # If we just produced synthesis or lockin output, persist a structured copy.
    if current_phase == "synthesis":
        update_fields["synthesis"] = {
            "body": response["text"],
            "model": response.get("model"),
            "tier": response.get("tier"),
            "comparables": response.get("comparables", []),
            "generated_at": iso(now()),
        }
        rec["synthesis"] = update_fields["synthesis"]
    elif current_phase == "lockin":
        update_fields["lockin"] = {
            "body": response["text"],
            "model": response.get("model"),
            "tier": response.get("tier"),
            "generated_at": iso(now()),
        }
        rec["lockin"] = update_fields["lockin"]

    if advance_to is None:
        # We were on lockin; complete the session.
        update_fields["status"] = "completed"
        update_fields["completed_at"] = iso(now())
        rec["status"] = "completed"
        rec["completed_at"] = update_fields["completed_at"]
    else:
        update_fields["phase"] = advance_to
        update_fields["phase_index"] = PHASES.index(advance_to)
        rec["phase"] = advance_to
        rec["phase_index"] = update_fields["phase_index"]

    await db.solve_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$set": update_fields},
    )

    rec.pop("_id", None)
    return rec


@router.post("/sessions/{sid}/restart")
async def restart_session(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Per iter58 user direction: users get BOTH continue-where-they-were
    AND start-over options. Restart clones the cluster + intent into a new
    session, abandons the old one, and primes Surface afresh."""
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.solve_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$set": {"status": "abandoned",
                  "abandoned_reason": "restarted",
                  "updated_at": iso(now())}},
    )
    # Reuse the start_session path
    new = await start_session(
        StartIn(
            cluster_id=rec["cluster_id"],
            intent=rec["intent"],
            context_id=rec.get("context_id"),
            pro_tier=rec.get("pro_tier", False),
        ),
        account,
    )
    return new


@router.post("/sessions/{sid}/abandon")
async def abandon_session(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0, "id": 1}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.solve_sessions.update_one(
        {"id": sid, "account_id": account["id"]},
        {"$set": {"status": "abandoned", "updated_at": iso(now())}},
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Phase response generator
# ---------------------------------------------------------------------------
def _next_phase(current: str) -> Optional[str]:
    try:
        i = PHASES.index(current)
    except ValueError:
        return None
    if i >= len(PHASES) - 1:
        return None
    return PHASES[i + 1]


async def _append_turn(sid: str, *, role: str, text: str, phase: str,
                       model: Optional[str] = None, tier: Optional[str] = None) -> None:
    turn = {
        "id": str(uuid.uuid4()),
        "role": role,
        "phase": phase,
        "text": text,
        "model": model,
        "tier": tier,
        "created_at": iso(now()),
    }
    await db.solve_sessions.update_one(
        {"id": sid},
        {"$push": {"turns": turn}, "$set": {"updated_at": iso(now())}},
    )


def _phase_system_prompt(cluster: Dict[str, Any], phase: str, intent: str) -> str:
    hint = (cluster.get("phase_hints") or {}).get(phase, "")
    banned = (cluster.get("banned_terms") or [])
    banned_block = ", ".join(banned) if banned else "(none specified)"
    return (
        "You are AKKI Solve — a structured-pause facilitator for board-grade "
        "problems. You walk users through four phases (Surface → Depth → "
        "Synthesis → Lock-in), one phase at a time. You do NOT lecture. You "
        "ask the questions a sharp counterpart would ask, and you do not move "
        "the user to the next phase prematurely.\n\n"
        f"CURRENT PHASE: {phase.upper()}.\n"
        f"PHASE INSTRUCTION: {hint}\n"
        f"USER INTENT: {intent}\n"
        f"CLUSTER: {cluster.get('label')}\n"
        f"BANNED TERMS (never use these): {banned_block}\n\n"
        "TONE: Calm, editorial, AKKI house style. Serif voice if you were "
        "speaking. No bullet stuffing unless the phase warrants it. No "
        "marketing language. No false certainty. Acknowledge the user's "
        "framing before pressing it.\n\n"
        "OUTPUT FORMAT:\n"
        "  - Surface phase: 2–3 short sentences asking the user to name "
        "the problem precisely. End with one specific question.\n"
        "  - Depth phase: 4–6 sentences pressure-testing the framing. "
        "Surface 1–2 contradictions or missing pieces. End with one "
        "question worth 10 minutes of the user's time.\n"
        "  - Synthesis phase: A 250–350 word diagnosis. Open with one "
        "orientation sentence. Two short paragraphs of analysis. Close "
        "with the diagnosis named in one sentence. If you reference "
        "comparable diagnoses, cite them as 'Comparable: <one line>'.\n"
        "  - Lock-in phase: Three commitments labelled 'Decide / Watch / "
        "Walk in with'. Each is one short sentence. End with one closing "
        "line.\n"
    )


async def _generate_phase_response(
    session: Dict[str, Any],
    cluster: Dict[str, Any],
    phase: str,
    is_first: bool = False,
) -> Dict[str, Any]:
    """Calls the LLM with the right tier for the user. Returns
    {text, model, tier, comparables}."""
    system_msg = _phase_system_prompt(cluster, phase, session["intent"])

    transcript_lines: List[str] = []
    for t in session.get("turns", []):
        prefix = "User" if t["role"] == "user" else "Solve"
        transcript_lines.append(f"{prefix} ({t.get('phase','?')}): {t.get('text','')}")
    transcript = "\n".join(transcript_lines) if transcript_lines else "(no prior turns)"

    if is_first:
        user_query = (
            f"The user just opened a Solve session.\n\n"
            f"Their intent: {session['intent']}\n\n"
            f"Open the SURFACE phase. Greet calmly, acknowledge what "
            f"they've named, then ask the first sharpening question."
        )
    else:
        user_query = (
            f"Conversation so far:\n{transcript}\n\n"
            f"Generate the {phase.upper()} response. Follow the OUTPUT "
            f"FORMAT for this phase precisely."
        )

    # Tier selection. Pro accounts get deep synthesis when the session
    # was started in Pro mode. Other phases (Surface, Depth, Lock-in)
    # always use standard — they're conversational, not heavy synthesis.
    tier = "standard"
    if phase == "synthesis" and session.get("pro_tier"):
        tier = "deep"

    if tier == "deep":
        # Use the existing deep-tier quota infra — Solve gets its own
        # surface so it doesn't compete with decks/brief budgets.
        from llm_tier_quota import call_llm_with_tier
        llm_out, quota_state = await call_llm_with_tier(
            surface="solve",
            account_id=session["account_id"],
            requested_tier="deep",
            call_args={
                "module": f"solve.{phase}",
                "user_query": user_query,
                "system_override": system_msg,
                "response_format": "text",
            },
        )
        body_text = (llm_out.get("response") or "").strip()
        model_id = llm_out.get("model")
        served_tier = llm_out.get("tier") or "standard"
    else:
        from llm_service import call_llm
        llm_out = await call_llm(
            module=f"solve.{phase}",
            user_query=user_query,
            system_override=system_msg,
            response_format="text",
            tier="standard",
        )
        body_text = (llm_out.get("response") or "").strip()
        model_id = llm_out.get("model")
        served_tier = llm_out.get("tier") or "standard"

    if not body_text:
        body_text = "(Solve returned an empty response — please try again.)"

    # Triangulation v1 — when this is the synthesis phase, attach any
    # `comparable_diagnoses` documented on the cluster. The LLM was already
    # primed to reference them in the body; this is just structured data
    # for the UI side panel.
    comparables: List[Dict[str, Any]] = []
    if phase == "synthesis":
        comparables = (cluster.get("comparable_diagnoses") or [])[:3]

    return {
        "text": body_text,
        "model": model_id,
        "tier": served_tier,
        "comparables": comparables,
    }
