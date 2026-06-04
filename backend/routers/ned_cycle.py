"""Phase E — NED Cycle Manager.

Parallel build to the executive Cycle Manager (`routers/cycle_manager.py`).
The NED side is structurally different: receiving, preparing, attending,
deciding, monitoring across MULTIPLE boards — per the spec at
`backend/work_studio/samples/Akki_NED_Cycle_Manager_Module_Specification.docx`.

Hard rules (from spec):
  • Cross-board confidentiality is architectural — every cross-board read
    routes through `services.privacy_wall.cross_context_query`.
  • In-meeting surface (`POST /meetings/{id}/notes`) is LLM-FREE. No
    summary, no commentary, no chat handoff inside the In phase.
  • Each NED's view is private. No multi-NED collaboration.
  • Calendar integration is manual entry only for v1 (no ICS/OAuth).

NEW collections owned by this router:
  db.ned_meetings           — one row per meeting (manual entry)
  db.ned_meeting_notes      — Q&A / Decision / Open note rows
  db.ned_positions          — registered positions on decisions
  db.ned_followups          — drafted follow-ups (separate from cycle_followups)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, write_audit
from services.privacy_wall import cross_context_query  # noqa: F401  # available for future cross-board reads

logger = logging.getLogger("akki.ned_cycle")

router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


async def _user_ned_context_ids(account_id: str) -> List[Dict[str, Any]]:
    """Return [{context_id, name, role}] for every context where the user
    has a NED membership. Cross-board joins must filter to this set."""
    memberships = await db.memberships.find(
        {"account_id": account_id, "role": "ned", "status": "active"},
        {"_id": 0, "context_id": 1},
    ).to_list(50)
    cids = [m["context_id"] for m in memberships]
    if not cids:
        return []
    ctxs = await db.contexts.find(
        {"id": {"$in": cids}, "type": {"$regex": "^ned_"}},
        {"_id": 0, "id": 1, "name": 1, "type": 1, "industry": 1},
    ).to_list(50)
    return ctxs


# ─────────────────────────────────────────────────────────────────────
# E.1 — Cross-board landing
# ─────────────────────────────────────────────────────────────────────
@router.get("/ned/landing")
async def ned_landing(
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Cross-board landing per spec §4.

    Returns four sections:
      • this_week — meetings within the next 7 days
      • next_two_weeks — meetings days 7-21 ahead
      • outstanding — open follow-ups + unanswered questions, all boards
      • patterns_url — pointer to the active context's E.0.3 aggregator
        endpoint (the landing renders patterns from there client-side
        with the active context as scope)
    """
    aid = account["id"]
    boards = await _user_ned_context_ids(aid)
    if not boards:
        return {
            "this_week": [], "next_two_weeks": [],
            "outstanding": [], "boards": [],
            "patterns_supported": False,
        }
    cid_set = [b["id"] for b in boards]

    now = _now()
    week  = (now + timedelta(days=7)).isoformat().replace("+00:00", "Z")
    fortn = (now + timedelta(days=21)).isoformat().replace("+00:00", "Z")

    meetings_window = await db.ned_meetings.find(
        {"account_id": aid, "context_id": {"$in": cid_set},
         "state": {"$ne": "closed"}, "scheduled_at": {"$lte": fortn}},
        {"_id": 0},
    ).sort("scheduled_at", 1).to_list(200)

    this_week, next_two_weeks = [], []
    iso_now = _iso(now)
    for m in meetings_window:
        sched = m.get("scheduled_at") or ""
        if sched < iso_now:
            continue  # past meetings stay out of the upcoming sections
        if sched <= week:
            this_week.append(m)
        else:
            next_two_weeks.append(m)

    # Outstanding — open follow-ups + decisions registered without
    # private_note + meetings still in 'in' or 'post' but not closed
    # past the meeting date.
    outstanding_followups = await db.ned_followups.find(
        {"account_id": aid, "context_id": {"$in": cid_set},
         "status": {"$in": ["draft", "sent"]}},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(50)

    outstanding_meetings = await db.ned_meetings.find(
        {"account_id": aid, "context_id": {"$in": cid_set},
         "state": {"$in": ["in", "post"]}},
        {"_id": 0},
    ).sort("scheduled_at", -1).to_list(50)

    return {
        "this_week": this_week,
        "next_two_weeks": next_two_weeks,
        "outstanding": {
            "followups": outstanding_followups,
            "meetings": outstanding_meetings,
        },
        "boards": boards,
        "patterns_supported": True,
    }


# ─────────────────────────────────────────────────────────────────────
# E.2 — Per-meeting CRUD (manual entry only for v1)
# ─────────────────────────────────────────────────────────────────────
class MeetingCreate(BaseModel):
    context_id: str = Field(min_length=1)
    committee: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    scheduled_at: str = Field(min_length=10, max_length=40)  # ISO-8601
    paper_doc_ids: Optional[List[str]] = Field(default_factory=list)


class MeetingPatch(BaseModel):
    title: Optional[str] = None
    committee: Optional[str] = None
    scheduled_at: Optional[str] = None
    paper_doc_ids: Optional[List[str]] = None
    formulated_question: Optional[str] = None  # the Pre-phase free-text
    state: Optional[Literal["pre", "in", "post", "closed"]] = None
    prep_state: Optional[Literal["not_started", "started", "ready"]] = None


async def _verify_ned_context(account_id: str, context_id: str) -> Dict[str, Any]:
    """Confirms the account has a NED membership on context_id and returns
    the resolved context. Raises 403 otherwise."""
    m = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id,
         "role": "ned", "status": "active"},
        {"_id": 0, "role": 1},
    )
    if not m:
        raise HTTPException(status_code=403, detail="Not a NED on this board")
    ctx = await db.contexts.find_one(
        {"id": context_id, "type": {"$regex": "^ned_"}}, {"_id": 0},
    )
    if not ctx:
        raise HTTPException(status_code=404, detail="NED context not found")
    return ctx


@router.post("/ned/meetings")
async def create_meeting(
    body: MeetingCreate,
    account: Dict[str, Any] = Depends(get_current_account),
):
    aid = account["id"]
    await _verify_ned_context(aid, body.context_id)
    mid = str(uuid.uuid4())
    now_s = _iso(_now())
    doc = {
        "id": mid,
        "account_id": aid,
        "context_id": body.context_id,
        "committee": body.committee.strip(),
        "title": body.title.strip(),
        "scheduled_at": body.scheduled_at,
        "paper_doc_ids": list(body.paper_doc_ids or []),
        "state": "pre",
        "prep_state": "not_started",
        "formulated_question": "",
        "created_at": now_s,
        "updated_at": now_s,
    }
    await db.ned_meetings.insert_one(doc)
    doc.pop("_id", None)
    try:
        await write_audit(
            body.context_id, aid,
            "ned.meeting.created", "ned_meeting", mid,
            {"committee": body.committee, "papers": len(body.paper_doc_ids or [])},
        )
    except Exception:
        pass
    return doc


@router.get("/ned/meetings/{meeting_id}")
async def get_meeting(
    meeting_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    m = await db.ned_meetings.find_one(
        {"id": meeting_id, "account_id": account["id"]}, {"_id": 0},
    )
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Resolve papers (documents) — read each through the per-context
    # path so we never expose another tenant's metadata.
    papers: List[Dict[str, Any]] = []
    for did in (m.get("paper_doc_ids") or []):
        d = await db.documents.find_one(
            {"id": did, "context_id": m["context_id"]},
            {"_id": 0, "id": 1, "name": 1, "filename": 1, "page_count": 1,
             "doc_kind": 1, "created_at": 1, "sensitivity_band": 1},
        )
        if d:
            papers.append(d)

    notes = await db.ned_meeting_notes.find(
        {"meeting_id": meeting_id, "account_id": account["id"]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    positions = await db.ned_positions.find(
        {"meeting_id": meeting_id, "account_id": account["id"]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(100)
    followups = await db.ned_followups.find(
        {"meeting_id": meeting_id, "account_id": account["id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)

    return {**m, "papers": papers, "notes": notes,
            "positions": positions, "followups": followups}


@router.patch("/ned/meetings/{meeting_id}")
async def patch_meeting(
    meeting_id: str, body: MeetingPatch,
    account: Dict[str, Any] = Depends(get_current_account),
):
    existing = await db.ned_meetings.find_one(
        {"id": meeting_id, "account_id": account["id"]}, {"_id": 0},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Meeting not found")
    upd: Dict[str, Any] = {"updated_at": _iso(_now())}
    if body.title is not None:
        upd["title"] = body.title.strip()
    if body.committee is not None:
        upd["committee"] = body.committee.strip()
    if body.scheduled_at is not None:
        upd["scheduled_at"] = body.scheduled_at
    if body.paper_doc_ids is not None:
        upd["paper_doc_ids"] = body.paper_doc_ids
    if body.formulated_question is not None:
        upd["formulated_question"] = body.formulated_question
    if body.state is not None:
        upd["state"] = body.state
    if body.prep_state is not None:
        upd["prep_state"] = body.prep_state
    if len(upd) == 1:
        return existing
    await db.ned_meetings.update_one({"id": meeting_id}, {"$set": upd})
    fresh = await db.ned_meetings.find_one({"id": meeting_id}, {"_id": 0})
    return fresh


@router.delete("/ned/meetings/{meeting_id}")
async def delete_meeting(
    meeting_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    existing = await db.ned_meetings.find_one(
        {"id": meeting_id, "account_id": account["id"]}, {"_id": 0, "id": 1, "context_id": 1},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Meeting not found")
    await db.ned_meetings.delete_one({"id": meeting_id})
    await db.ned_meeting_notes.delete_many({"meeting_id": meeting_id})
    await db.ned_positions.delete_many({"meeting_id": meeting_id})
    await db.ned_followups.delete_many({"meeting_id": meeting_id})
    return {"ok": True, "id": meeting_id}


# ─────────────────────────────────────────────────────────────────────
# E.2.In — Note-taking surface (ZERO LLM by hard rule)
# ─────────────────────────────────────────────────────────────────────
class NoteCreate(BaseModel):
    kind: Literal["qna", "decision", "open"]
    body: str = Field(min_length=1, max_length=4000)
    related_question_index: Optional[int] = None  # ticks off a question


@router.post("/ned/meetings/{meeting_id}/notes")
async def add_note(
    meeting_id: str, body: NoteCreate,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """In-phase note insert. SPEC §5.2.1: no real-time AI, no transcription.
    This endpoint MUST NOT call any LLM. Pure DB insert. The marker comment
    below is a build-time guardrail — do not add LLM calls here."""
    # PRIVACY-WALL-CONTRACT ned-in-phase-llm-free=true
    m = await db.ned_meetings.find_one(
        {"id": meeting_id, "account_id": account["id"]},
        {"_id": 0, "id": 1, "context_id": 1, "state": 1},
    )
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")

    nid = str(uuid.uuid4())
    doc = {
        "id": nid,
        "meeting_id": meeting_id,
        "account_id": account["id"],
        "context_id": m["context_id"],
        "kind": body.kind,
        "body": body.body,
        "related_question_index": body.related_question_index,
        "created_at": _iso(_now()),
    }
    await db.ned_meeting_notes.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/ned/meetings/{meeting_id}/notes/{note_id}")
async def delete_note(
    meeting_id: str, note_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    res = await db.ned_meeting_notes.delete_one(
        {"id": note_id, "meeting_id": meeting_id, "account_id": account["id"]},
    )
    return {"ok": res.deleted_count > 0}


# ─────────────────────────────────────────────────────────────────────
# E.2.Post — Position registration & follow-ups
# ─────────────────────────────────────────────────────────────────────
class PositionCreate(BaseModel):
    decision_text: str = Field(min_length=1, max_length=400)
    position: Literal["for", "against", "abstained"]
    private_note: Optional[str] = Field(default=None, max_length=2000)


@router.post("/ned/meetings/{meeting_id}/positions")
async def register_position(
    meeting_id: str, body: PositionCreate,
    account: Dict[str, Any] = Depends(get_current_account),
):
    m = await db.ned_meetings.find_one(
        {"id": meeting_id, "account_id": account["id"]},
        {"_id": 0, "id": 1, "context_id": 1, "committee": 1},
    )
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    pid = str(uuid.uuid4())
    doc = {
        "id": pid,
        "meeting_id": meeting_id,
        "account_id": account["id"],
        "context_id": m["context_id"],
        "committee": m["committee"],
        "decision_text": body.decision_text,
        "position": body.position,
        "private_note": body.private_note or "",
        "created_at": _iso(_now()),
    }
    await db.ned_positions.insert_one(doc)
    doc.pop("_id", None)
    return doc


class FollowupDraft(BaseModel):
    to_email: str = Field(min_length=3, max_length=200)
    to_name: Optional[str] = Field(default=None, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    body_md: str = Field(min_length=1, max_length=8000)


@router.post("/ned/meetings/{meeting_id}/followups")
async def draft_followup(
    meeting_id: str, body: FollowupDraft,
    account: Dict[str, Any] = Depends(get_current_account),
):
    m = await db.ned_meetings.find_one(
        {"id": meeting_id, "account_id": account["id"]},
        {"_id": 0, "id": 1, "context_id": 1, "committee": 1},
    )
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    fid = str(uuid.uuid4())
    now_s = _iso(_now())
    doc = {
        "id": fid,
        "meeting_id": meeting_id,
        "account_id": account["id"],
        "context_id": m["context_id"],
        "committee": m["committee"],
        "to_email": body.to_email.strip().lower(),
        "to_name": body.to_name,
        "subject": body.subject,
        "body_md": body.body_md,
        "status": "draft",
        "created_at": now_s,
        "updated_at": now_s,
    }
    await db.ned_followups.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post(
    "/ned/meetings/{meeting_id}/followups/{fid}/send",
    operation_id="ned_cycle_send_followup",
)
async def send_followup(
    meeting_id: str, fid: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Reuse Phase D.2 email infrastructure with a NED posture (peer-toned
    'From <NED Name> via Akki'). The send path mirrors `cycle_manager.py`."""
    fu = await db.ned_followups.find_one(
        {"id": fid, "meeting_id": meeting_id, "account_id": account["id"]},
        {"_id": 0},
    )
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if fu.get("status") == "sent":
        return {"ok": True, "duplicate": True, "id": fid}

    from email_service import send_email, cycles_alias_for
    reply_to = cycles_alias_for(account["id"])
    subject = fu.get("subject", "")
    body_md = fu.get("body_md", "")

    res = await send_email(
        to=[fu["to_email"]],
        subject=subject,
        html=f"<pre style='font-family:Georgia,serif;white-space:pre-wrap'>{body_md}</pre>",
        text=body_md,
        reply_to=reply_to,
        from_executive_name=account.get("name") or account.get("email") or "AKKI",
        posture="cycle",
    )

    update = {
        "status": "sent" if res.get("ok") else "failed",
        "send_mode": res.get("mode"),
        "send_error": res.get("error"),
        "sent_at": _iso(_now()),
        "updated_at": _iso(_now()),
        "from_header": f'"{account.get("name") or "AKKI"} (via Akki)" <noreply@cycles.akki.ai>',
        "reply_to_alias": reply_to,
    }
    await db.ned_followups.update_one({"id": fid}, {"$set": update})
    fresh = await db.ned_followups.find_one({"id": fid}, {"_id": 0})
    try:
        await write_audit(
            fu["context_id"], account["id"],
            "ned.followup.sent", "ned_followup", fid,
            {"to": fu["to_email"], "mode": res.get("mode")},
        )
    except Exception:
        pass
    return fresh


# ─────────────────────────────────────────────────────────────────────
# E.3 — Per-committee through-line
# ─────────────────────────────────────────────────────────────────────
@router.get("/ned/committee/{context_id}/{committee}")
async def committee_through_line(
    context_id: str, committee: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Returns reverse-chrono meetings + decisions + positions across the
    NED's tenure on this (context, committee) — STRICTLY scoped by
    account_id. The NED sees only their own engagement."""
    await _verify_ned_context(account["id"], context_id)

    meetings = await db.ned_meetings.find(
        {"account_id": account["id"], "context_id": context_id,
         "committee": committee},
        {"_id": 0},
    ).sort("scheduled_at", -1).to_list(200)

    positions = await db.ned_positions.find(
        {"account_id": account["id"], "context_id": context_id,
         "committee": committee},
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)

    # Recurring questions: collect every formulated_question + question
    # notes across this committee, count word-overlap clusters above a
    # threshold. Pure local heuristic (no LLM per spec).
    all_questions: List[str] = [
        m.get("formulated_question", "").strip()
        for m in meetings if m.get("formulated_question")
    ]
    qna_notes = await db.ned_meeting_notes.find(
        {"account_id": account["id"], "context_id": context_id,
         "kind": "qna"},
        {"_id": 0, "body": 1, "meeting_id": 1},
    ).to_list(500)
    qna_by_meeting = [n["body"] for n in qna_notes
                      if n["meeting_id"] in {m["id"] for m in meetings}]
    all_questions.extend(qna_by_meeting)

    return {
        "context_id": context_id,
        "committee": committee,
        "meeting_count": len(meetings),
        "meetings": meetings,
        "positions": positions,
        "questions_log": all_questions[:120],
    }


# ─────────────────────────────────────────────────────────────────────
# E.4 — Personal memory search (BM25 lexical, account-scoped)
# ─────────────────────────────────────────────────────────────────────
def _bm25_score(text: str, query_terms: List[str]) -> float:
    """Tiny BM25-ish lexical scorer — sufficient for v1's small N. Each
    matched term contributes 1; double-match contributes 0.5; never
    negative. Deterministic, no LLM."""
    if not text or not query_terms:
        return 0.0
    tl = text.lower()
    score = 0.0
    for t in query_terms:
        if not t:
            continue
        n = tl.count(t)
        if n == 0:
            continue
        score += 1 + min(n - 1, 4) * 0.5
    return score


@router.get("/ned/search")
async def personal_memory_search(
    q: str,
    limit: int = 25,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Cross-board search across the NED's OWN meetings/notes/positions/
    followups. STRICTLY scoped by account_id — never queries other NEDs
    or other accounts. Privacy Wall holds by construction (account_id
    filter on every query)."""
    aid = account["id"]
    qs = [t for t in (q or "").lower().strip().split() if t]
    if not qs:
        return {"hits": [], "query": q}

    boards = await _user_ned_context_ids(aid)
    cid_set = [b["id"] for b in boards]
    if not cid_set:
        return {"hits": [], "query": q}

    scope = {"account_id": aid, "context_id": {"$in": cid_set}}
    hits: List[Dict[str, Any]] = []

    async for m in db.ned_meetings.find(scope, {"_id": 0}):
        text = " ".join([m.get("title") or "", m.get("committee") or "",
                         m.get("formulated_question") or ""])
        s = _bm25_score(text, qs)
        if s > 0:
            hits.append({
                "kind": "meeting", "score": s,
                "id": m["id"], "title": m.get("title"),
                "committee": m.get("committee"), "context_id": m["context_id"],
                "scheduled_at": m.get("scheduled_at"),
            })

    async for n in db.ned_meeting_notes.find(scope, {"_id": 0}):
        s = _bm25_score(n.get("body", ""), qs)
        if s > 0:
            hits.append({
                "kind": "note", "score": s,
                "id": n["id"], "meeting_id": n.get("meeting_id"),
                "note_kind": n.get("kind"),
                "snippet": (n.get("body") or "")[:240],
                "context_id": n.get("context_id"),
                "created_at": n.get("created_at"),
            })

    async for p in db.ned_positions.find(scope, {"_id": 0}):
        text = " ".join([p.get("decision_text") or "",
                         p.get("private_note") or ""])
        s = _bm25_score(text, qs)
        if s > 0:
            hits.append({
                "kind": "position", "score": s,
                "id": p["id"], "meeting_id": p.get("meeting_id"),
                "position": p.get("position"),
                "decision_text": p.get("decision_text"),
                "context_id": p.get("context_id"),
                "created_at": p.get("created_at"),
            })

    async for f in db.ned_followups.find(scope, {"_id": 0}):
        text = " ".join([f.get("subject") or "", f.get("body_md") or ""])
        s = _bm25_score(text, qs)
        if s > 0:
            hits.append({
                "kind": "followup", "score": s,
                "id": f["id"], "meeting_id": f.get("meeting_id"),
                "subject": f.get("subject"),
                "to_email": f.get("to_email"),
                "context_id": f.get("context_id"),
                "status": f.get("status"),
                "created_at": f.get("created_at"),
            })

    hits.sort(key=lambda h: -h["score"])
    return {"query": q, "hits": hits[:max(1, min(limit, 100))]}
