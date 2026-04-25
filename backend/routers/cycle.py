"""§12 Reporting Cycle (iter18 redesign).

Reframed governance posture: AKKI is the objective third party in the
conversation. The executive (or her EA) reviews and approves a checklist
that AKKI prepared; AKKI then *does* send and *does* collect responses,
acting under the principal's name (`AKKI for <Executive Name>`). The
executive's job is to gate, not to do secretarial work.

This module ships Phase 1 of the redesign:
  - Question Bank (per-context, persistent, seeded from past briefings)
  - Reportees CRUD (extends membership but tracked in its own collection
    for cycle-specific metadata that doesn't belong on memberships)
  - Reporting Checklist generation (LLM-tailored per reportee)
  - Approve & Dispatch (AKKI sends via Resend, with mailto fallback)
  - Submissions inbox + reply ingestion stub

Multi-tier compilation (CFO → CEO → Board) is reserved for Phase 3.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    get_current_account, require_context_membership,
)
from email_service import (
    configured as resend_configured,
    send_email, render_checklist_email_html,
)
from llm_service import call_llm as llm_call_llm, parse_json_response

logger = logging.getLogger("akki.cycle")

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

QuestionCategory = Literal[
    "audit", "risk", "operational", "strategic",
    "people", "financial", "regulatory", "general",
]
QuestionStatus = Literal["open", "answered", "retired"]


class QuestionIn(BaseModel):
    text: str = Field(min_length=8, max_length=400)
    category: QuestionCategory = "general"
    source: Optional[str] = Field(default=None, max_length=300)
    committee_id: Optional[str] = None


class QuestionPatch(BaseModel):
    text: Optional[str] = Field(default=None, min_length=8, max_length=400)
    category: Optional[QuestionCategory] = None
    status: Optional[QuestionStatus] = None
    committee_id: Optional[str] = None


class ReporteeIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    title: str = Field(min_length=2, max_length=120)
    areas: List[QuestionCategory] = Field(default_factory=list)


class ChecklistGenerateIn(BaseModel):
    cycle_name: str = Field(min_length=3, max_length=120,
                            description="e.g. 'Q2 2026 board pack' or 'May management report'")
    deadline_date: str = Field(min_length=4, max_length=40,
                               description="Human-readable, e.g. '15 May 2026'")
    reportee_ids: Optional[List[str]] = Field(
        default=None,
        description="Subset to draft for; None = every active reportee",
    )


class ChecklistEdit(BaseModel):
    questions: List[Dict[str, Any]]
    note_to_reportee: Optional[str] = Field(default=None, max_length=600)


class DispatchIn(BaseModel):
    checklist_ids: List[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Question Bank
# ---------------------------------------------------------------------------

@router.get("/contexts/{context_id}/questions")
async def list_questions(
    context_id: str,
    status: Optional[str] = None,
    category: Optional[str] = None,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id}
    if status:
        q["status"] = status
    if category:
        q["category"] = category
    cursor = db.questions.find(q, {"_id": 0}).sort("created_at", -1).limit(500)
    return {"questions": await cursor.to_list(length=500)}


@router.post("/contexts/{context_id}/questions")
async def add_question(
    context_id: str,
    body: QuestionIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    qid = str(uuid.uuid4())
    rec = {
        "id": qid,
        "context_id": context_id,
        "text": body.text.strip(),
        "category": body.category,
        "source": body.source or "added by executive",
        "committee_id": body.committee_id,
        "status": "open",
        "times_asked": 0,
        "last_asked_at": None,
        "created_by": current["id"],
        "created_at": _iso(_now()),
    }
    await db.questions.insert_one(rec.copy())
    await write_audit(context_id, current["id"], "question.added", "question", qid, {"text": body.text[:80]})
    return {k: v for k, v in rec.items() if k != "_id"}


@router.patch("/contexts/{context_id}/questions/{qid}")
async def patch_question(
    context_id: str,
    qid: str,
    body: QuestionPatch,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    update = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    res = await db.questions.update_one(
        {"id": qid, "context_id": context_id}, {"$set": update}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Question not found.")
    await write_audit(context_id, current["id"], "question.patched", "question", qid, update)
    rec = await db.questions.find_one({"id": qid, "context_id": context_id}, {"_id": 0})
    return rec


@router.post("/contexts/{context_id}/questions/seed-from-briefings")
async def seed_questions_from_briefings(
    context_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Pull 'questions to take into the room' from every briefing in this
    context and persist them as open questions. Idempotent — dedupes by text."""
    existing = await db.questions.find(
        {"context_id": context_id}, {"_id": 0, "text": 1},
    ).to_list(length=2000)
    existing_set = {(q.get("text") or "").strip().lower() for q in existing}

    cursor = db.briefings.find({"context_id": context_id}, {"_id": 0, "id": 1, "items": 1})
    added = 0
    async for b in cursor:
        for item in (b.get("items") or []):
            for q_text in (item.get("questions_to_ask") or []):
                norm = (q_text or "").strip()
                if not norm or norm.lower() in existing_set:
                    continue
                cat = "general"
                low = norm.lower()
                if any(k in low for k in ("audit", "internal control", "compliance")):
                    cat = "audit"
                elif any(k in low for k in ("risk", "exposure", "concentration")):
                    cat = "risk"
                elif any(k in low for k in ("regulator", "fca", "cbk", "pra")):
                    cat = "regulatory"
                elif any(k in low for k in ("liquidity", "capital", "cash", "loan")):
                    cat = "financial"
                elif any(k in low for k in ("strategy", "growth", "expansion")):
                    cat = "strategic"
                rec = {
                    "id": str(uuid.uuid4()),
                    "context_id": context_id,
                    "text": norm[:400],
                    "category": cat,
                    "source": f"briefing/{b['id'][:8]}",
                    "committee_id": item.get("committee_id"),
                    "status": "open",
                    "times_asked": 0,
                    "last_asked_at": None,
                    "created_by": current["id"],
                    "created_at": _iso(_now()),
                }
                await db.questions.insert_one(rec.copy())
                existing_set.add(norm.lower())
                added += 1
    return {"seeded": added}


# ---------------------------------------------------------------------------
# Reportees
# ---------------------------------------------------------------------------

@router.get("/contexts/{context_id}/reportees")
async def list_reportees(
    context_id: str,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    cursor = db.reportees.find(
        {"context_id": context_id, "status": {"$ne": "removed"}},
        {"_id": 0},
    ).sort("created_at", 1)
    return {"reportees": await cursor.to_list(length=200)}


@router.post("/contexts/{context_id}/reportees")
async def add_reportee(
    context_id: str,
    body: ReporteeIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    rid = str(uuid.uuid4())
    rec = {
        "id": rid,
        "context_id": context_id,
        "name": body.name.strip(),
        "email": body.email.lower().strip(),
        "title": body.title.strip(),
        "areas": body.areas,
        "status": "active",
        "added_by": current["id"],
        "created_at": _iso(_now()),
    }
    await db.reportees.insert_one(rec.copy())
    await write_audit(context_id, current["id"], "reportee.added", "reportee", rid, {"email": body.email})
    return {k: v for k, v in rec.items() if k != "_id"}


@router.delete("/contexts/{context_id}/reportees/{rid}")
async def remove_reportee(
    context_id: str,
    rid: str,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.reportees.update_one(
        {"id": rid, "context_id": context_id},
        {"$set": {"status": "removed", "removed_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reportee not found.")
    await write_audit(context_id, current["id"], "reportee.removed", "reportee", rid, {})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Checklist generation + dispatch
# ---------------------------------------------------------------------------

ANTI_SPAM_DAYS = 14  # don't dispatch a fresh checklist to the same reportee within this window


async def _executive_name(account_id: str) -> str:
    acc = await db.accounts.find_one({"id": account_id}, {"_id": 0, "name": 1, "email": 1})
    return (acc or {}).get("name") or (acc or {}).get("email", "your executive").split("@")[0]


async def _draft_questions_for_reportee(
    *,
    reportee: Dict[str, Any],
    open_questions: List[Dict[str, Any]],
    cycle_name: str,
) -> List[Dict[str, Any]]:
    """Pick 4-7 questions from the open bank that align with this reportee's
    declared areas of ownership. Prefers higher-times-asked (recurring questions
    the board keeps coming back to) and recent additions. No LLM call needed —
    deterministic ranking keeps the pipeline cheap and auditable."""
    areas = set(reportee.get("areas") or [])
    scored: List[tuple] = []
    for q in open_questions:
        score = 0
        if q.get("category") in areas:
            score += 5
        if not areas and q.get("category") in {"financial", "operational", "general"}:
            score += 2  # default ownership for reportees with no declared areas
        score += min(int(q.get("times_asked") or 0), 3) * 2
        # newer questions get a small recency bias
        try:
            age = (_now() - datetime.fromisoformat((q.get("created_at") or "").replace("Z", "+00:00"))).days
            score += max(0, 5 - min(age, 5))
        except Exception:
            pass
        scored.append((score, q))
    scored.sort(key=lambda t: -t[0])
    picked = [q for _, q in scored[:6]]
    return [
        {
            "question_id": q["id"],
            "text": q["text"],
            "category": q.get("category", "general"),
            "times_asked": int(q.get("times_asked") or 0),
        }
        for q in picked
    ]


@router.post("/contexts/{context_id}/checklists/generate")
async def generate_checklists(
    context_id: str,
    body: ChecklistGenerateIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Compose a per-reportee checklist tailored from the open question bank.
    Returns drafts in `pending_approval` state — nothing is sent yet. The
    executive reviews/edits/approves them via /dispatch below."""
    # Pull all active reportees (or the requested subset)
    rep_query: Dict[str, Any] = {"context_id": context_id, "status": "active"}
    if body.reportee_ids:
        rep_query["id"] = {"$in": body.reportee_ids}
    reportees = await db.reportees.find(rep_query, {"_id": 0}).to_list(length=200)
    if not reportees:
        raise HTTPException(status_code=400, detail="No reportees configured for this context.")

    # Anti-spam: skip reportees who got a checklist in the last ANTI_SPAM_DAYS
    cutoff = _iso(_now() - timedelta(days=ANTI_SPAM_DAYS))
    recent = await db.checklists.find(
        {"context_id": context_id, "dispatched_at": {"$gte": cutoff}},
        {"_id": 0, "reportee_id": 1},
    ).to_list(length=500)
    recent_ids = {r["reportee_id"] for r in recent}

    open_qs = await db.questions.find(
        {"context_id": context_id, "status": "open"}, {"_id": 0},
    ).sort("created_at", -1).to_list(length=500)
    if not open_qs:
        raise HTTPException(
            status_code=400,
            detail="The Question Bank is empty. Seed it from past briefings first, or add a question manually.",
        )

    drafts: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for r in reportees:
        if r["id"] in recent_ids and (not body.reportee_ids or r["id"] not in body.reportee_ids):
            skipped.append({"reportee_id": r["id"], "name": r["name"], "reason": f"received a checklist within the last {ANTI_SPAM_DAYS} days"})
            continue
        questions = await _draft_questions_for_reportee(
            reportee=r, open_questions=open_qs, cycle_name=body.cycle_name,
        )
        if not questions:
            skipped.append({"reportee_id": r["id"], "name": r["name"], "reason": "no open questions match this reportee's areas"})
            continue
        cid = str(uuid.uuid4())
        rec = {
            "id": cid,
            "context_id": context_id,
            "reportee_id": r["id"],
            "reportee_name": r["name"],
            "reportee_email": r["email"],
            "cycle_name": body.cycle_name,
            "deadline_date": body.deadline_date,
            "questions": questions,
            "note_to_reportee": None,
            "status": "pending_approval",
            "submission_token": uuid.uuid4().hex,
            "executive_id": current["id"],
            "created_at": _iso(_now()),
            "dispatched_at": None,
            "responded_at": None,
        }
        await db.checklists.insert_one(rec.copy())
        drafts.append({k: v for k, v in rec.items() if k != "_id"})

    await write_audit(
        context_id, current["id"], "checklists.generated", "cycle", body.cycle_name,
        {"drafts": len(drafts), "skipped": len(skipped)},
    )
    return {"drafts": drafts, "skipped": skipped, "anti_spam_days": ANTI_SPAM_DAYS}


@router.get("/contexts/{context_id}/checklists")
async def list_checklists(
    context_id: str,
    status: Optional[str] = None,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id}
    if status:
        q["status"] = status
    cursor = db.checklists.find(q, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"checklists": await cursor.to_list(length=200)}


@router.patch("/contexts/{context_id}/checklists/{cid}")
async def edit_checklist(
    context_id: str,
    cid: str,
    body: ChecklistEdit,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Executive edits questions / adds a personal note before approving."""
    res = await db.checklists.update_one(
        {"id": cid, "context_id": context_id, "status": "pending_approval"},
        {"$set": {
            "questions": body.questions,
            "note_to_reportee": body.note_to_reportee,
            "edited_at": _iso(_now()),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Checklist not found or already dispatched.")
    return await db.checklists.find_one({"id": cid}, {"_id": 0})


def _frontend_origin() -> str:
    import os as _os
    return _os.environ.get("FRONTEND_URL", "https://akki.ai").rstrip("/")


@router.post("/contexts/{context_id}/checklists/dispatch")
async def dispatch_checklists(
    context_id: str,
    body: DispatchIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Executive approves and dispatches a batch of checklists. AKKI sends
    each via Resend (with mailto fallback if not configured), updates the
    Question Bank's `times_asked` + `last_asked_at`, and returns send results.

    Sender: 'AKKI for <Executive Name> <noreply@akki.ai>', reply-to is the
    executive's real email so reportee replies route back to her naturally.
    """
    exec_name = await _executive_name(current["id"])
    exec_email = (await db.accounts.find_one({"id": current["id"]}, {"_id": 0, "email": 1})).get("email")
    origin = _frontend_origin()

    sent: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    fallback_mailtos: List[Dict[str, Any]] = []

    for cid in body.checklist_ids:
        cl = await db.checklists.find_one(
            {"id": cid, "context_id": context_id, "status": "pending_approval"},
            {"_id": 0},
        )
        if not cl:
            failed.append({"checklist_id": cid, "error": "not pending"})
            continue
        submission_url = f"{origin}/respond/{cl['submission_token']}"
        html = render_checklist_email_html(
            executive_name=exec_name,
            reportee_name=cl["reportee_name"],
            cycle_name=cl["cycle_name"],
            deadline_date=cl["deadline_date"],
            questions=cl["questions"],
            submission_url=submission_url,
        )
        subject = f"AKKI for {exec_name}: {cl['cycle_name']} — your input"

        if resend_configured():
            res = await send_email(
                to=[cl["reportee_email"]],
                subject=subject,
                html=html,
                reply_to=exec_email,
                from_executive_name=exec_name,
                tags=[{"name": "kind", "value": "checklist"},
                      {"name": "context", "value": context_id[:24]}],
            )
            if res.get("ok"):
                await db.checklists.update_one(
                    {"id": cid},
                    {"$set": {
                        "status": "dispatched",
                        "dispatched_at": _iso(_now()),
                        "send_id": res.get("id"),
                        "send_mode": res.get("mode"),
                    }},
                )
                sent.append({"checklist_id": cid, "to": cl["reportee_email"], "send_id": res.get("id")})
                # Bump question bank counters
                qids = [q["question_id"] for q in cl["questions"] if q.get("question_id")]
                if qids:
                    await db.questions.update_many(
                        {"id": {"$in": qids}, "context_id": context_id},
                        {"$inc": {"times_asked": 1}, "$set": {"last_asked_at": _iso(_now())}},
                    )
            else:
                failed.append({"checklist_id": cid, "error": res.get("error", "send failed")})
        else:
            # Fallback: surface a mailto: URI so the executive can send manually
            from urllib.parse import quote
            body_lines = [f"Hi {cl['reportee_name']},", "",
                          f"{exec_name} would like your input on:", ""]
            for i, q in enumerate(cl["questions"], 1):
                body_lines.append(f"{i}. {q['text']}")
            body_lines += ["", f"Please respond by {cl['deadline_date']}.",
                           "", f"Submit on AKKI: {submission_url}", "", f"— AKKI for {exec_name}"]
            mailto = (
                f"mailto:{cl['reportee_email']}"
                f"?subject={quote(subject)}"
                f"&body={quote(chr(10).join(body_lines))}"
            )
            fallback_mailtos.append({
                "checklist_id": cid,
                "to": cl["reportee_email"],
                "mailto": mailto,
            })

    await write_audit(
        context_id, current["id"], "checklists.dispatched", "cycle",
        body.checklist_ids[0] if body.checklist_ids else "batch",
        {"sent": len(sent), "failed": len(failed), "fallback": len(fallback_mailtos)},
    )
    return {
        "sent": sent,
        "failed": failed,
        "fallback_mailtos": fallback_mailtos,
        "resend_configured": resend_configured(),
    }


# ---------------------------------------------------------------------------
# Submissions (reportee-side response)
# ---------------------------------------------------------------------------

class AnswerIn(BaseModel):
    question_id: Optional[str] = None
    question_text: Optional[str] = Field(default=None, max_length=400)
    answer: str = Field(default="", max_length=4000)


class SubmissionIn(BaseModel):
    answers: List[AnswerIn]
    notes: Optional[str] = Field(default=None, max_length=4000)


@router.get("/respond/{token}")
async def get_checklist_for_token(token: str):
    """Public — reportee fetches their own checklist via emailed link."""
    cl = await db.checklists.find_one({"submission_token": token}, {"_id": 0})
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found or has been revoked.")
    if cl.get("status") not in ("dispatched", "pending_approval"):
        raise HTTPException(status_code=410, detail="This checklist is no longer accepting responses.")
    return {
        "id": cl["id"],
        "cycle_name": cl["cycle_name"],
        "deadline_date": cl["deadline_date"],
        "reportee_name": cl["reportee_name"],
        "questions": cl["questions"],
        "note_to_reportee": cl.get("note_to_reportee"),
        "submitted": cl.get("status") == "responded",
    }


@router.post("/respond/{token}")
async def submit_response(token: str, body: SubmissionIn):
    cl = await db.checklists.find_one({"submission_token": token}, {"_id": 0})
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found.")
    if cl.get("status") not in ("dispatched", "pending_approval"):
        raise HTTPException(status_code=410, detail="This checklist is no longer accepting responses.")

    sub_id = str(uuid.uuid4())
    answers_raw = [a.model_dump() for a in body.answers]
    rec = {
        "id": sub_id,
        "context_id": cl["context_id"],
        "checklist_id": cl["id"],
        "reportee_id": cl["reportee_id"],
        "reportee_name": cl["reportee_name"],
        "reportee_email": cl["reportee_email"],
        "cycle_name": cl["cycle_name"],
        "answers": answers_raw,
        "notes": body.notes,
        "submitted_at": _iso(_now()),
    }
    await db.submissions.insert_one(rec.copy())
    await db.checklists.update_one(
        {"id": cl["id"]},
        {"$set": {"status": "responded", "responded_at": _iso(_now())}},
    )
    # Mark each answered question as 'answered' if not already
    for ans in answers_raw:
        qid = ans.get("question_id")
        if qid and (ans.get("answer") or "").strip():
            await db.questions.update_one(
                {"id": qid, "context_id": cl["context_id"], "status": "open"},
                {"$set": {"status": "answered", "answered_at": _iso(_now())}},
            )
    return {"ok": True, "submission_id": sub_id}


@router.get("/contexts/{context_id}/submissions")
async def list_submissions(
    context_id: str,
    cycle_name: Optional[str] = None,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id}
    if cycle_name:
        q["cycle_name"] = cycle_name
    cursor = db.submissions.find(q, {"_id": 0}).sort("submitted_at", -1).limit(500)
    return {"submissions": await cursor.to_list(length=500)}



# ---------------------------------------------------------------------------
# Reports (multi-tier review chain) — Phase 3
# ---------------------------------------------------------------------------
# A Report is the consolidated artefact a single tier of the chain composes
# from their reportees' submissions. Each Report carries a `chain[]` —
# successive reviewers in escalation order (e.g. CFO → CEO → Board). When the
# author finalises a tier, the next reviewer's account_id is flipped to
# `pending`. Reviewers can: edit body / add comments / approve & forward /
# send back. The receiving reviewer becomes the next-tier author and their
# act of sending up creates a new "envelope" entry on the chain.
#
# This is the smallest model that captures the user's described flow:
# "compilation to CFO, CFO approves, sent to CEO, CEO reviews, and approves,
#  sent to board".


ReviewerStatus = Literal["pending", "approved", "sent_back", "skipped"]
ReportStatus = Literal["draft", "in_review", "finalised", "withdrawn"]


class ReviewerIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=120,
                       description="e.g. 'CEO', 'Board chair', 'Audit committee chair'")


class ReportComposeIn(BaseModel):
    cycle_name: str = Field(min_length=3, max_length=120)
    title: str = Field(min_length=4, max_length=200)
    chain: List[ReviewerIn] = Field(
        min_length=1, max_length=5,
        description="Escalation order: first item = first reviewer after the author. "
                    "e.g. CFO author → chain = [CEO, Board chair].",
    )


class ReportPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=4, max_length=200)
    body: Optional[str] = Field(default=None, max_length=40000)
    note: Optional[str] = Field(default=None, max_length=2000,
                                description="A note from the current reviewer to the next tier or the author.")


class ReviewActionIn(BaseModel):
    action: Literal["approve", "send_back"]
    note: Optional[str] = Field(default=None, max_length=2000)


def _initial_chain(chain_in: List[ReviewerIn], author_id: str, author_name: str) -> List[Dict[str, Any]]:
    """Build the chain list with the author at position 0 (always approved
    on creation since they composed it) and reviewers in pending state.
    Position 1 is `pending`; everyone after is `pending` but blocked until
    the previous tier approves."""
    result: List[Dict[str, Any]] = [{
        "tier": 0,
        "role": "author",
        "name": author_name,
        "title": "Author",
        "email": None,
        "account_id": author_id,
        "status": "approved",
        "acted_at": _iso(_now()),
        "note": None,
    }]
    for i, r in enumerate(chain_in):
        result.append({
            "tier": i + 1,
            "role": "reviewer",
            "name": r.name.strip(),
            "title": r.title.strip(),
            "email": r.email.lower().strip(),
            "account_id": None,  # resolved on first review (lookup by email)
            "status": "pending" if i == 0 else "blocked",
            "acted_at": None,
            "note": None,
        })
    return result


def _current_reviewer_idx(chain: List[Dict[str, Any]]) -> Optional[int]:
    """Return index of the chain entry currently awaiting action, or None
    if the report is fully approved or withdrawn."""
    for i, entry in enumerate(chain):
        if entry.get("status") == "pending":
            return i
    return None


async def _consolidate_submissions_into_body(
    *, context_id: str, cycle_name: str
) -> str:
    """Pull every submission for this cycle and stitch them into a clean
    starting markdown body the author can edit. Cheap, deterministic — no
    LLM call needed for the v1; the LLM-polish path can come later."""
    subs = await db.submissions.find(
        {"context_id": context_id, "cycle_name": cycle_name},
        {"_id": 0},
    ).sort("reportee_name", 1).to_list(length=500)
    if not subs:
        return f"# {cycle_name}\n\n_No reportee submissions yet for this cycle._\n"
    lines: List[str] = [f"# {cycle_name}\n"]
    lines.append("## Inputs from your team\n")
    for s in subs:
        lines.append(f"### {s['reportee_name']}")
        for ans in (s.get("answers") or []):
            qt = ans.get("question_text") or ans.get("question_id") or "Untitled"
            lines.append(f"**{qt}**")
            lines.append(ans.get("answer", "_(no response)_") or "_(no response)_")
            lines.append("")
        if s.get("notes"):
            lines.append(f"_{s['reportee_name']}'s note: {s['notes']}_")
            lines.append("")
    lines.append("## Author's commentary\n")
    lines.append("_Add your synthesis above the team inputs before sending up the chain._")
    lines.append("")
    return "\n".join(lines)


@router.post("/contexts/{context_id}/reports/compose")
async def compose_report(
    context_id: str,
    body: ReportComposeIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Compose a draft report from this cycle's submissions and define the
    review chain. Report starts in `draft` — author can edit freely, nothing
    is sent up until they `send_up`."""
    author_name = await _executive_name(current["id"])
    initial_body = await _consolidate_submissions_into_body(
        context_id=context_id, cycle_name=body.cycle_name,
    )
    rid = str(uuid.uuid4())
    rec = {
        "id": rid,
        "context_id": context_id,
        "cycle_name": body.cycle_name,
        "title": body.title.strip(),
        "body": initial_body,
        "author_id": current["id"],
        "author_name": author_name,
        "status": "draft",
        "chain": _initial_chain(body.chain, current["id"], author_name),
        "events": [{
            "at": _iso(_now()),
            "actor_id": current["id"],
            "actor_name": author_name,
            "action": "composed",
            "note": None,
        }],
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    await db.reports.insert_one(rec.copy())
    await write_audit(context_id, current["id"], "report.composed", "report", rid,
                      {"cycle_name": body.cycle_name, "chain_len": len(rec["chain"]) - 1})
    return {k: v for k, v in rec.items() if k != "_id"}


@router.get("/contexts/{context_id}/reports")
async def list_reports(
    context_id: str,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    cursor = db.reports.find(
        {"context_id": context_id, "status": {"$ne": "withdrawn"}},
        {"_id": 0},
    ).sort("updated_at", -1).limit(200)
    return {"reports": await cursor.to_list(length=200)}


async def _resolve_report_access(
    *, context_id: str, rid: str, current: Dict[str, Any]
) -> Dict[str, Any]:
    """Gate for per-report endpoints (get/patch/send_up/review). Allows access
    if the caller is EITHER an active member of the context OR the email of
    the current pending reviewer matches the caller's email. This is the
    multi-tier flow's central insight: a reviewer (e.g. CEO) doesn't need to
    be a member of the upstream-author's board to act on the report — they
    only need to be the named reviewer on the chain. Returns the report dict.
    Raises 403/404 on rejection."""
    rec = await db.reports.find_one({"id": rid, "context_id": context_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Path 1: full context member — sees + acts on everything per usual rules
    membership = await db.memberships.find_one(
        {"account_id": current["id"], "context_id": context_id, "status": "active"},
        {"_id": 0, "role": 1},
    )
    if membership:
        return rec

    # Path 2: not a member, but is a named reviewer on this report's chain
    caller_email = (current.get("email") or "").lower()
    reviewer_emails = {
        (entry.get("email") or "").lower()
        for entry in (rec.get("chain") or [])
        if entry.get("email")
    }
    if caller_email and caller_email in reviewer_emails:
        return rec

    raise HTTPException(status_code=403, detail="Not authorised to access this report.")


@router.get("/contexts/{context_id}/reports/{rid}")
async def get_report(
    context_id: str,
    rid: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    return await _resolve_report_access(context_id=context_id, rid=rid, current=current)


@router.patch("/contexts/{context_id}/reports/{rid}")
async def patch_report(
    context_id: str,
    rid: str,
    body: ReportPatchIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Edit body/title. Author may edit while in `draft`; current reviewer may
    edit while `in_review`. Other tiers — even members — cannot edit, only read."""
    rec = await _resolve_report_access(context_id=context_id, rid=rid, current=current)

    idx = _current_reviewer_idx(rec.get("chain") or [])
    is_author = rec["author_id"] == current["id"] and rec["status"] == "draft"
    current_email = (current.get("email") or "").lower()
    is_current_reviewer = (
        idx is not None
        and rec["chain"][idx].get("email") == current_email
    )
    if not (is_author or is_current_reviewer):
        raise HTTPException(status_code=403, detail="Only the author (in draft) or the current reviewer can edit this report.")

    update = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "note" in update:
        # Notes attach to the chain at the current author/reviewer's position
        target_idx = idx if is_current_reviewer else 0
        rec["chain"][target_idx]["note"] = update.pop("note")[:2000]
        update["chain"] = rec["chain"]
    if not update:
        return rec
    update["updated_at"] = _iso(_now())
    await db.reports.update_one({"id": rid}, {"$set": update})
    return await db.reports.find_one({"id": rid}, {"_id": 0})


@router.post("/contexts/{context_id}/reports/{rid}/send_up")
async def send_report_up(
    context_id: str,
    rid: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Author flips draft → in_review. Notifies the next reviewer via Resend
    (or a mailto fallback if Resend is unconfigured). Each call advances the
    chain by one position when invoked by the current reviewer; sending from
    `draft` advances from author (tier 0) to first reviewer (tier 1)."""
    rec = await _resolve_report_access(context_id=context_id, rid=rid, current=current)
    if rec["status"] not in ("draft", "in_review"):
        raise HTTPException(status_code=409, detail=f"Report is {rec['status']}, cannot be sent up.")

    chain = rec["chain"]
    idx = _current_reviewer_idx(chain)
    if idx is None:
        raise HTTPException(status_code=409, detail="No pending reviewer in chain.")

    # Sanity: only the actual author or current reviewer can send up
    current_email = (current.get("email") or "").lower()
    can_send = (
        rec["status"] == "draft" and rec["author_id"] == current["id"]
    ) or (
        rec["status"] == "in_review" and chain[idx].get("email") == current_email
    )
    if not can_send:
        raise HTTPException(status_code=403, detail="Only the author (in draft) or the current reviewer can send this report up.")

    # Notify the *target* reviewer (chain[idx])
    target = chain[idx]
    sender_name = (await db.accounts.find_one({"id": current["id"]}, {"_id": 0, "name": 1, "email": 1})).get("name") or rec["author_name"]
    review_url = f"{_frontend_origin()}/app/cycle/reports/{rid}"
    subject = f"AKKI for {sender_name}: review request — {rec['title']}"
    html = f"""
<div style="font-family:Georgia,serif;color:#2A2622;background:#F7F3EA;padding:32px;">
  <div style="max-width:580px;margin:0 auto;background:#fff;border:1px solid #E8E0D0;padding:32px 36px;">
    <p style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#8B2E2B;margin:0 0 8px 0;font-weight:600;">AKKI · Review request</p>
    <h2 style="margin:0 0 16px 0;font-size:22px;font-weight:normal;color:#1a1a1a;line-height:1.3;">{rec['title']}</h2>
    <p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;">Hi {target['name']},</p>
    <p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;">
      <strong>{sender_name}</strong> has prepared the <strong>{rec['cycle_name']}</strong> report and asked AKKI to forward it to you for review as <em>{target['title']}</em>.
    </p>
    <p style="margin:0 0 22px 0;font-size:15px;line-height:1.6;">
      You can edit, add comments, then either approve and forward to the next reviewer, or send it back with notes.
    </p>
    <a href="{review_url}" style="display:inline-block;padding:11px 22px;background:#1A2B4C;color:#fff;text-decoration:none;font-family:-apple-system,sans-serif;font-size:14px;border-radius:4px;">Open report in AKKI</a>
    <p style="margin:18px 0 0 0;font-size:12px;color:#8b6f47;font-family:-apple-system,sans-serif;">AKKI never reads private replies sent outside its product surface.</p>
  </div>
</div>
"""
    if resend_configured():
        send_res = await send_email(
            to=[target["email"]],
            subject=subject,
            html=html,
            reply_to=(await db.accounts.find_one({"id": current["id"]}, {"_id": 0, "email": 1})).get("email"),
            from_executive_name=sender_name,
            tags=[{"name": "kind", "value": "report-review"},
                  {"name": "report_id", "value": rid[:24]}],
        )
    else:
        send_res = {"ok": False, "mode": "noop"}

    new_events = list(rec.get("events") or [])
    new_events.append({
        "at": _iso(_now()),
        "actor_id": current["id"],
        "actor_name": sender_name,
        "action": "sent_up",
        "to_email": target["email"],
        "to_name": target["name"],
        "note": None,
    })
    await db.reports.update_one(
        {"id": rid},
        {"$set": {
            "status": "in_review",
            "events": new_events,
            "updated_at": _iso(_now()),
            "current_reviewer_email": target["email"],
        }},
    )
    await write_audit(context_id, current["id"], "report.sent_up", "report", rid,
                      {"to": target["email"], "tier": target["tier"]})
    return {
        "ok": True,
        "to": target["email"],
        "send_id": send_res.get("id"),
        "send_mode": send_res.get("mode"),
        "review_url": review_url,
    }


@router.post("/contexts/{context_id}/reports/{rid}/review")
async def review_report(
    context_id: str,
    rid: str,
    body: ReviewActionIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Current reviewer approves or sends back. On approve, the next reviewer
    becomes pending; if there is no next reviewer, the report is finalised.
    On send_back, the entire chain rolls back to the author and they can
    revise + send up again."""
    rec = await _resolve_report_access(context_id=context_id, rid=rid, current=current)
    if rec["status"] != "in_review":
        raise HTTPException(status_code=409, detail=f"Report is {rec['status']}, cannot be reviewed.")

    chain = rec["chain"]
    idx = _current_reviewer_idx(chain)
    if idx is None:
        raise HTTPException(status_code=409, detail="No pending reviewer.")

    current_email = (current.get("email") or "").lower()
    if chain[idx].get("email") != current_email:
        raise HTTPException(status_code=403, detail="You are not the current reviewer.")

    chain[idx]["account_id"] = current["id"]
    chain[idx]["acted_at"] = _iso(_now())
    chain[idx]["note"] = (body.note or chain[idx].get("note") or "")[:2000] or None

    new_status = rec["status"]
    new_current_email = rec.get("current_reviewer_email")

    if body.action == "approve":
        chain[idx]["status"] = "approved"
        # Promote the next blocked tier to pending
        if idx + 1 < len(chain) and chain[idx + 1]["status"] == "blocked":
            chain[idx + 1]["status"] = "pending"
            new_current_email = chain[idx + 1]["email"]
        else:
            new_status = "finalised"
            new_current_email = None
    else:  # send_back
        chain[idx]["status"] = "sent_back"
        # Reset tiers ≥ idx (they all need redoing) — but keep history of acted_at/note
        for i in range(idx + 1, len(chain)):
            chain[i]["status"] = "blocked"
        new_status = "draft"  # author may revise + send up again
        new_current_email = None

    new_events = list(rec.get("events") or [])
    new_events.append({
        "at": _iso(_now()),
        "actor_id": current["id"],
        "actor_name": current.get("name") or current_email,
        "action": body.action,
        "tier": chain[idx]["tier"],
        "note": body.note,
    })
    await db.reports.update_one(
        {"id": rid},
        {"$set": {
            "chain": chain,
            "status": new_status,
            "events": new_events,
            "current_reviewer_email": new_current_email,
            "updated_at": _iso(_now()),
        }},
    )
    await write_audit(context_id, current["id"], f"report.{body.action}", "report", rid,
                      {"tier": chain[idx]["tier"], "new_status": new_status})
    return await db.reports.find_one({"id": rid}, {"_id": 0})


@router.get("/reports/inbox")
async def reports_inbox(
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Cross-context: every report in the platform where this user is the
    current pending reviewer. Powers the 'awaiting your review' Home card."""
    email = (current.get("email") or "").lower()
    if not email:
        return {"reports": []}
    cursor = db.reports.find(
        {"status": "in_review", "current_reviewer_email": email},
        {"_id": 0},
    ).sort("updated_at", -1).limit(50)
    return {"reports": await cursor.to_list(length=50)}
