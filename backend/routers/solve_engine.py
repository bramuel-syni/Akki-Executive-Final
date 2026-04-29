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
# Tiering helper — Solve Pro is bundled into the existing Pro plan so users
# get one decision (subscribe to Pro $29) rather than a separate Solve fee.
# Legacy/manual `solve_pro` flag still honoured. Free users get one deep
# Synthesis grant per UTC month so they can taste it before subscribing.
# ---------------------------------------------------------------------------
def _now_month_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _user_is_pro(account: Dict[str, Any]) -> bool:
    plan = (account.get("plan") or "free").lower()
    return plan in ("pro", "team") or bool(account.get("solve_pro"))


async def _consume_free_grant(account_id: str) -> Dict[str, Any]:
    """Atomically claim this user's monthly free deep-synthesis grant.
    Returns {"allowed": bool, "remaining_this_month": 0|1}. Each free user
    gets exactly 1 deep synthesis per month (cheap taste-test)."""
    month = _now_month_utc()
    key = {"account_id": account_id, "month_utc": month}
    iso_now = iso(now())
    try:
        await db.solve_free_grants.insert_one({
            **key, "count": 1, "first_used_at": iso_now, "last_used_at": iso_now,
        })
        return {"allowed": True, "remaining_this_month": 0}
    except Exception:  # noqa: BLE001 — duplicate key = already claimed
        return {"allowed": False, "remaining_this_month": 0}


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
    is_pro_account = await _user_is_pro(account)
    # Record both the user's request AND whether their account is on the Pro
    # plan. Synthesis time will decide whether to consume the Pro quota or
    # fall back to the monthly free grant.
    pro_tier_requested = bool(body.pro_tier)

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
        "pro_tier": pro_tier_requested,
        "pro_account": is_pro_account,
        "turns": [],
        "synthesis": None,
        "lockin": None,
        "handoffs": [],
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
            "free_grant_used": response.get("free_grant_used", False),
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
# Wave 2 — Handoff trio. From a completed Solve session, push the synthesis
# + lock-in into the user's existing artefacts:
#
#   1. Brief    — creates a briefing-shaped doc whose opening_paragraph is the
#                  synthesis and whose items[] are the lock-in commitments.
#   2. Decks    — seeds a Decks outline with intent = synthesis + lock-in.
#                  The user then commits the deep-tier render via the existing
#                  decks pipeline.
#   3. Cycle    — seeds the synthesis into the Question Bank as 1-3 questions
#                  derived from the lock-in's "Walk in with" line, so the
#                  diagnosis becomes a board-room follow-up.
#
# All three are idempotent within a session — subsequent calls return the
# previously-created artefact_id rather than spawning duplicates.
# ---------------------------------------------------------------------------
class HandoffBriefIn(BaseModel):
    context_id: str = Field(min_length=8, max_length=80)
    title: Optional[str] = Field(default=None, max_length=120)


class HandoffDecksIn(BaseModel):
    context_id: str = Field(min_length=8, max_length=80)
    audience: Optional[str] = Field(default=None, max_length=120)


class HandoffCycleIn(BaseModel):
    context_id: str = Field(min_length=8, max_length=80)


def _require_completed_session(rec: Dict[str, Any]) -> None:
    if not rec.get("synthesis") or not rec.get("lockin"):
        raise HTTPException(
            status_code=409,
            detail="Solve session must reach Synthesis and Lock-in before handoff.",
        )


def _parse_lockin_lines(lockin_body: str) -> Dict[str, str]:
    """Best-effort split of the lock-in body into Decide/Watch/Walk-in lines.
    Tolerates markdown bold (**Decide:** ...) and bullet prefixes."""
    out = {"decide": "", "watch": "", "walk_in": ""}
    if not lockin_body:
        return out
    for raw in lockin_body.splitlines():
        # strip leading bullet/markdown markers and trailing whitespace
        line = raw.strip()
        # peel off leading bullet markers
        line = line.lstrip(" \t-•·*")
        # peel off markdown bold marker
        if line.startswith("**"):
            line = line[2:]
        if not line:
            continue
        # find label vs body separator (colon or asterisks-then-colon)
        body = line
        label = ""
        if ":" in line:
            label, body = line.split(":", 1)
            # strip trailing markdown bold from label and leading from body
            label = label.rstrip("* ").strip().lower()
            body = body.lstrip("* ").strip()
        else:
            label = line[:20].lower()
            body = line
        if label.startswith("decide"):
            out["decide"] = body
        elif label.startswith("watch"):
            out["watch"] = body
        elif label.startswith("walk in") or label.startswith("walk-in"):
            out["walk_in"] = body
    return out


async def _record_handoff(sid: str, account_id: str, target: str,
                          artefact_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
    rec = {
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "account_id": account_id,
        "target": target,
        "artefact_id": artefact_id,
        "created_at": iso(now()),
        **(extra or {}),
    }
    await db.solve_handoffs.insert_one(rec)
    await db.solve_sessions.update_one(
        {"id": sid, "account_id": account_id},
        {"$push": {"handoffs": {"target": target, "artefact_id": artefact_id,
                                 "created_at": rec["created_at"]}},
         "$set": {"updated_at": iso(now())}},
    )


async def _ensure_membership(context_id: str, account_id: str) -> Dict[str, Any]:
    """Lightweight membership check — Solve handoffs require the user to be
    a member of the destination context."""
    ctx = await db.contexts.find_one({"id": context_id, "status": {"$ne": "archived"}}, {"_id": 0})
    if not ctx:
        raise HTTPException(status_code=404, detail="Destination context not found.")
    m = await db.memberships.find_one(
        {"context_id": context_id, "account_id": account_id, "status": "active"},
        {"_id": 0, "role": 1},
    )
    if not m:
        raise HTTPException(status_code=403, detail="You are not a member of that context.")
    return ctx


@router.post("/sessions/{sid}/handoff/brief")
async def handoff_brief(
    sid: str,
    body: HandoffBriefIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    _require_completed_session(rec)
    ctx = await _ensure_membership(body.context_id, account["id"])

    # Idempotency — return the existing handoff if one was already created.
    existing = await db.solve_handoffs.find_one(
        {"session_id": sid, "target": "brief"}, {"_id": 0}
    )
    if existing:
        prior = await db.briefings.find_one(
            {"id": existing["artefact_id"]}, {"_id": 0}
        )
        if prior:
            return {"already_exists": True, "briefing": prior, "handoff_id": existing["id"]}

    synthesis_body = (rec.get("synthesis") or {}).get("body") or ""
    lockin_body = (rec.get("lockin") or {}).get("body") or ""
    parsed = _parse_lockin_lines(lockin_body)

    items: List[Dict[str, Any]] = []
    for label, key in (("Decide", "decide"), ("Watch", "watch"), ("Walk in with", "walk_in")):
        text = parsed[key]
        if not text:
            continue
        items.append({
            "signal_id": f"solve-{rec['id'][:8]}-{key}",
            "signal_type": "solve_lockin",
            "signal_headline": label,
            "evidence": text[:1500],
            "question": "" if key != "walk_in" else text[:400],
            "sources": [],
        })
    if not items:
        # Lock-in didn't parse into Decide/Watch/Walk — store it verbatim
        items.append({
            "signal_id": f"solve-{rec['id'][:8]}-summary",
            "signal_type": "solve_lockin",
            "signal_headline": "Solve commitments",
            "evidence": lockin_body[:1500],
            "question": "",
            "sources": [],
        })

    briefing_id = str(uuid.uuid4())
    title = (body.title or f"Solve · {rec.get('cluster_label','Diagnosis')}")[:120]

    briefing = {
        "id": briefing_id,
        "context_id": body.context_id,
        "context_name": ctx.get("name"),
        "version": 1,
        "title": title,
        "role": "executive",
        "opening_paragraph": synthesis_body[:2500],
        "items": items,
        "closing_note": None,
        "source_doc_ids": [],
        "signal_ids": [],
        "data_trust": "low",
        "mode": "solve_handoff",
        "shielding_masked": 0,
        "shielding": {},
        "created_by": account["id"],
        "created_at": iso(now()),
        "status": "active",
        "solve_session_id": sid,
    }
    await db.briefings.insert_one(briefing)
    await _record_handoff(sid, account["id"], "brief", briefing_id,
                          {"context_id": body.context_id})
    briefing.pop("_id", None)
    return {"already_exists": False, "briefing": briefing,
            "handoff_id": (await db.solve_handoffs.find_one(
                {"session_id": sid, "target": "brief"}, {"_id": 0, "id": 1}
            ) or {}).get("id")}


@router.post("/sessions/{sid}/handoff/decks")
async def handoff_decks(
    sid: str,
    body: HandoffDecksIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    _require_completed_session(rec)
    await _ensure_membership(body.context_id, account["id"])

    existing = await db.solve_handoffs.find_one(
        {"session_id": sid, "target": "decks"}, {"_id": 0}
    )
    if existing:
        prior = await db.deck_outlines.find_one(
            {"id": existing["artefact_id"]}, {"_id": 0}
        )
        if prior:
            return {"already_exists": True, "outline": prior, "handoff_id": existing["id"]}

    synthesis_body = (rec.get("synthesis") or {}).get("body") or ""
    lockin_body = (rec.get("lockin") or {}).get("body") or ""

    # Compose a deck intent prompt that the existing decks pipeline will
    # turn into an outline + research_question. We package the synthesis
    # as the seed thesis and the lock-in as the action vector.
    intent_seed = (
        f"Build a board-grade deck that lands the diagnosis below as a "
        f"presentable narrative. Source thesis (Solve synthesis):\n\n"
        f"{synthesis_body[:1400]}\n\n"
        f"Action vector (Solve lock-in commitments):\n{lockin_body[:600]}"
    )[:600]  # decks Outline.intent has max_length=600

    # Skip the LLM and persist a draft outline directly. The user can refine
    # it inside Decks before committing the deep-tier render. This avoids
    # wasting a Decks-quota call on a Solve handoff that the user might not
    # actually render.
    outline_id = str(uuid.uuid4())
    outline = {
        "id": outline_id,
        "context_id": body.context_id,
        "intent": intent_seed,
        "audience": body.audience or "Board",
        "target_slides": 8,
        "research_question": (rec.get("intent") or "")[:400],
        "missing_context": [],
        "evidence_summary": {"docs": 0, "signals": 0, "briefs": 0},
        "slides": [
            {"title": "The diagnosis", "key_message": (synthesis_body[:300] or rec.get("intent",""))[:300]},
            {"title": "What worked / didn't (comparables)",
             "key_message": "Two anonymised comparable cases the diagnosis triangulates against."},
            {"title": "Decide", "key_message": _parse_lockin_lines(lockin_body)["decide"] or "What we are committing to."},
            {"title": "Watch", "key_message": _parse_lockin_lines(lockin_body)["watch"] or "What we are watching."},
            {"title": "Walk in with", "key_message": _parse_lockin_lines(lockin_body)["walk_in"] or "How we walk into the room."},
        ],
        "model": "solve_handoff",
        "tier": "standard",
        "created_by": account["id"],
        "created_at": iso(now()),
        "status": "draft",
        "iteration": 0,
        "parent_outline_id": None,
        "solve_session_id": sid,
    }
    await db.deck_outlines.insert_one(outline)
    await _record_handoff(sid, account["id"], "decks", outline_id,
                          {"context_id": body.context_id})
    outline.pop("_id", None)
    h = await db.solve_handoffs.find_one(
        {"session_id": sid, "target": "decks"}, {"_id": 0, "id": 1}
    )
    return {"already_exists": False, "outline": outline,
            "handoff_id": (h or {}).get("id")}


@router.post("/sessions/{sid}/handoff/cycle")
async def handoff_cycle(
    sid: str,
    body: HandoffCycleIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    _require_completed_session(rec)
    await _ensure_membership(body.context_id, account["id"])

    existing = await db.solve_handoffs.find_one(
        {"session_id": sid, "target": "cycle"}, {"_id": 0}
    )
    if existing:
        ids = existing.get("question_ids") or []
        prior_qs = await db.questions.find(
            {"id": {"$in": ids}}, {"_id": 0}
        ).to_list(length=10) if ids else []
        return {"already_exists": True, "questions": prior_qs, "handoff_id": existing["id"]}

    synthesis_body = (rec.get("synthesis") or {}).get("body") or ""
    lockin_body = (rec.get("lockin") or {}).get("body") or ""
    parsed = _parse_lockin_lines(lockin_body)

    # Compose 1-3 questions: the "Walk in with" line as the lead question,
    # plus optionally a Watch follow-up and a synthesis-derived probe.
    candidates: List[str] = []
    if parsed["walk_in"]:
        candidates.append(_to_question(parsed["walk_in"]))
    if parsed["watch"]:
        candidates.append(f"What would tell us the watch item is moving? Specifically: {parsed['watch']}")
    if parsed["decide"]:
        candidates.append(f"Have we decided: {parsed['decide']}? If not, what's blocking?")

    if not candidates:
        # Fall back to a generic probe derived from the synthesis lead sentence.
        first_sentence = next((s.strip() for s in synthesis_body.split(".") if s.strip()), rec.get("intent",""))
        candidates.append(f"Solve diagnosis: {first_sentence[:300]} — what's the board's next move?")

    questions: List[Dict[str, Any]] = []
    new_ids: List[str] = []
    for text in candidates[:3]:
        qid = str(uuid.uuid4())
        q = {
            "id": qid,
            "context_id": body.context_id,
            "text": text[:400],
            "category": "strategic",
            "source": f"AKKI Solve · {rec.get('cluster_label','session')}",
            "committee_id": None,
            "status": "open",
            "times_asked": 0,
            "last_asked_at": None,
            "created_by": account["id"],
            "created_at": iso(now()),
            "solve_session_id": sid,
        }
        await db.questions.insert_one(q.copy())
        q.pop("_id", None)
        questions.append(q)
        new_ids.append(qid)

    await _record_handoff(sid, account["id"], "cycle", new_ids[0] if new_ids else "",
                          {"context_id": body.context_id, "question_ids": new_ids})
    h = await db.solve_handoffs.find_one(
        {"session_id": sid, "target": "cycle"}, {"_id": 0, "id": 1}
    )
    return {"already_exists": False, "questions": questions,
            "handoff_id": (h or {}).get("id")}


def _to_question(line: str) -> str:
    """Normalise a lock-in line into a question form, gently."""
    line = line.strip().rstrip(".").rstrip(":")
    if line.endswith("?"):
        return line
    if line.lower().startswith(("how", "what", "why", "when", "who", "should", "is ", "are ", "do ", "does ")):
        return line + "?"
    return f"How do we hold ourselves to: {line}?"


@router.get("/sessions/{sid}/handoffs")
async def list_session_handoffs(
    sid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = await db.solve_sessions.find_one(
        {"id": sid, "account_id": account["id"]}, {"_id": 0, "id": 1}
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Session not found.")
    rows = await db.solve_handoffs.find(
        {"session_id": sid}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=20)
    return {"items": rows, "count": len(rows)}


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


async def _pick_comparables(cluster_id: str, sector_tag: Optional[str], limit: int = 3) -> List[Dict[str, Any]]:
    """Triangulation v2 — pick the closest comparables for a given cluster.

    Order of preference:
      1. Same cluster + matching sector_tag.
      2. Same cluster + sector_tag='any'.
      3. Same cluster + any sector.

    Curated comparables are anonymised (no real company names) and carry a
    'verdict' field (what worked / what didn't) so the prompt can ground the
    diagnosis in lived board experience rather than abstractions.
    """
    out: List[Dict[str, Any]] = []
    seen: set = set()

    async def _take(filter_q: Dict[str, Any]) -> None:
        async for c in db.solve_comparables.find(
            filter_q,
            {"_id": 0, "id": 1, "cluster_id": 1, "sector_tag": 1, "scale_tag": 1,
             "diagnosis_summary": 1, "what_worked": 1, "what_didnt": 1},
        ):
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            out.append(c)
            if len(out) >= limit:
                return

    if sector_tag:
        await _take({"cluster_id": cluster_id, "sector_tag": sector_tag})
    if len(out) < limit:
        await _take({"cluster_id": cluster_id, "sector_tag": "any"})
    if len(out) < limit:
        await _take({"cluster_id": cluster_id})
    return out[:limit]


def _phase_system_prompt(cluster: Dict[str, Any], phase: str, intent: str,
                         comparables: Optional[List[Dict[str, Any]]] = None) -> str:
    hint = (cluster.get("phase_hints") or {}).get(phase, "")
    banned = (cluster.get("banned_terms") or [])
    banned_block = ", ".join(banned) if banned else "(none specified)"

    comparable_block = ""
    if phase == "synthesis" and comparables:
        lines = []
        for c in comparables:
            lines.append(
                f"- {c.get('diagnosis_summary','').strip()}\n"
                f"  Worked: {c.get('what_worked','').strip()}\n"
                f"  Didn't: {c.get('what_didnt','').strip()}"
            )
        comparable_block = (
            "\n\nCURATED COMPARABLES (anonymised, real boards). When useful, "
            "reference them inline as 'A comparable mid-cap bank…' or "
            "'In one industrials case…'. Do NOT name companies. Do not list "
            "all of them — pick at most one or two that genuinely sharpen "
            "the diagnosis. If none apply, ignore.\n"
            + "\n".join(lines)
        )

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
        "line."
        + comparable_block
    )


async def _generate_phase_response(
    session: Dict[str, Any],
    cluster: Dict[str, Any],
    phase: str,
    is_first: bool = False,
) -> Dict[str, Any]:
    """Calls the LLM with the right tier for the user. Returns
    {text, model, tier, comparables, free_grant_used?, quota?}."""
    # Wave 3 — at synthesis, pick curated comparables for triangulation. We
    # use the session's context sector if available; otherwise we fall back
    # to cluster-level matches.
    comparables: List[Dict[str, Any]] = []
    sector_tag: Optional[str] = None
    if phase == "synthesis":
        ctx_id = session.get("context_id")
        if ctx_id:
            ctx_doc = await db.contexts.find_one(
                {"id": ctx_id}, {"_id": 0, "sector": 1, "industry": 1}
            )
            if ctx_doc:
                sector_tag = (ctx_doc.get("sector") or ctx_doc.get("industry") or "").lower() or None
        comparables = await _pick_comparables(cluster["id"], sector_tag, limit=3)

    system_msg = _phase_system_prompt(cluster, phase, session["intent"], comparables=comparables)

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

    # Tier resolution. Only synthesis can be deep. Pro accounts use the
    # paid `solve` quota; free accounts who requested Pro tier are granted
    # one deep synthesis per UTC month so they can taste it.
    tier = "standard"
    free_grant_used = False
    quota_state: Optional[Dict[str, Any]] = None

    if phase == "synthesis" and session.get("pro_tier"):
        if session.get("pro_account"):
            tier = "deep"
        else:
            grant = await _consume_free_grant(session["account_id"])
            if grant.get("allowed"):
                tier = "deep"
                free_grant_used = True

    if tier == "deep":
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
        if quota_state.get("downgraded"):
            served_tier = "standard"
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

    return {
        "text": body_text,
        "model": model_id,
        "tier": served_tier,
        "comparables": comparables,
        "free_grant_used": free_grant_used,
        "quota": quota_state,
    }
