"""Company Home — Phase I.2 data wiring (2026-05-27).

Two endpoints powering the active-context home surface
(`pages/CompanyHome.jsx`):

  GET /api/me/company-home/readiness?context_id={cid}
    → {"readiness_percent": int|null, "open_task_count": int}

  GET /api/me/company-home/attention?context_id={cid}
    → {
        "drafts":    {"count": int, "subtext": str, "oldest_days": int|null},
        "reports":   {"count": int, "subtext": str},
        "pulse":     {"count": int, "subtext": str, "critical": int, "opportunities": int},
        "questions": {"count": int, "subtext": str},
        "events":    {"count": 0, "subtext": "No events scheduled"}
      }

Both are cached in-process for 60s per (account, context).

Out-of-scope (deferred to I.4/I.5):
  • Events count + subtext (I.4 ships the events collection).
  • Asker-role decomposition on the Open Questions card (I.5).
  • Top-signals rail chips (I.3).
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import db, get_current_account


router = APIRouter(prefix="/api", tags=["company-home"])


_CACHE_TTL_S = 60.0
# key = (account_id, context_id, "readiness"|"attention")
_CACHE: Dict[Tuple[str, str, str], Tuple[float, Dict[str, Any]]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# -----------------------------------------------------------------------------
# Membership guard
# -----------------------------------------------------------------------------

async def _assert_member(account_id: str, context_id: str) -> None:
    """Make sure the caller belongs to this context. We don't return
    the membership doc — just gate access."""
    m = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id, "status": "active"},
        {"_id": 0, "account_id": 1},
    )
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this context")


# -----------------------------------------------------------------------------
# Readiness
# -----------------------------------------------------------------------------

class ReadinessOut(BaseModel):
    readiness_percent: Optional[int]
    open_task_count: int


@router.get("/me/company-home/readiness", response_model=ReadinessOut)
async def readiness(
    context_id: str = Query(..., min_length=4, max_length=120),
    me: Dict[str, Any] = Depends(get_current_account),
) -> ReadinessOut:
    """Weighted-average task readiness across open tasks for the
    active context. `state='active'` is the only "open" task state in
    this codebase (verified 2026-05-27 — DB distinct produces
    ['active','closed']). Drafts also qualify as open if the team
    introduces that state later — `$nin: ['closed']` is the future-
    safe filter, but for now `'active'` is exhaustive."""
    cid = context_id
    await _assert_member(me["id"], cid)

    cached = _CACHE.get((me["id"], cid, "readiness"))
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_S:
        return ReadinessOut(**cached[1])

    # Aggregate the average readiness_score across open tasks.
    pipeline = [
        {"$match": {
            "context_id": cid,
            "state": {"$nin": ["closed", "archived"]},
        }},
        {"$group": {
            "_id": None,
            "avg": {"$avg": "$readiness_score"},
            "n":   {"$sum": 1},
        }},
    ]
    cursor = db.tasks.aggregate(pipeline)
    row = await cursor.to_list(length=1)

    if not row or row[0].get("n", 0) == 0:
        out = {"readiness_percent": None, "open_task_count": 0}
    else:
        avg = row[0]["avg"] or 0
        out = {
            "readiness_percent": int(round(avg)),
            "open_task_count": int(row[0]["n"]),
        }

    _CACHE[(me["id"], cid, "readiness")] = (time.monotonic(), out)
    return ReadinessOut(**out)


# -----------------------------------------------------------------------------
# Attention cards
# -----------------------------------------------------------------------------

class CardDrafts(BaseModel):
    count: int
    subtext: str
    oldest_days: Optional[int] = None


class CardReports(BaseModel):
    count: int
    subtext: str


class CardPulse(BaseModel):
    count: int
    subtext: str
    critical: int
    opportunities: int


class CardQuestions(BaseModel):
    count: int
    subtext: str


class CardEvents(BaseModel):
    count: int
    subtext: str


class AttentionOut(BaseModel):
    drafts:    CardDrafts
    reports:   CardReports
    pulse:     CardPulse
    questions: CardQuestions
    events:    CardEvents


async def _build_drafts(cid: str) -> CardDrafts:
    """Drafts ready for review are rows in `ned_followups` and
    `cycle_followups` carrying `status='draft'`. (Verified 2026-05-27:
    the codebase uses `draft` as the ready-for-review status — there's
    no separate `ready_for_review` value in the wild; `send_skipped`
    means user-dismissed, NOT pending.) We aggregate the count + the
    age of the oldest waiting draft so the subtext can switch from
    "Nothing waiting." to "Send today · Oldest waiting Nd" to
    "{N} waiting · Send to keep momentum."""
    ned_q    = {"context_id": cid, "status": "draft"}
    cycle_q  = {"context_id": cid, "status": "draft"}

    ned_count   = await db.ned_followups.count_documents(ned_q)
    cycle_count = await db.cycle_followups.count_documents(cycle_q)
    count = ned_count + cycle_count

    if count == 0:
        return CardDrafts(count=0, subtext="Nothing waiting.", oldest_days=None)

    # Find the oldest waiting draft across both collections.
    oldest_iso: Optional[str] = None
    ned_oldest = await db.ned_followups.find_one(
        ned_q, {"_id": 0, "created_at": 1}, sort=[("created_at", 1)],
    )
    cycle_oldest = await db.cycle_followups.find_one(
        cycle_q, {"_id": 0, "created_at": 1}, sort=[("created_at", 1)],
    )
    for src in (ned_oldest, cycle_oldest):
        if not src:
            continue
        ts = src.get("created_at")
        if not ts:
            continue
        if oldest_iso is None or ts < oldest_iso:
            oldest_iso = ts

    oldest_days = None
    if oldest_iso:
        try:
            o = datetime.fromisoformat(oldest_iso.replace("Z", "+00:00"))
            oldest_days = int((_now() - o).total_seconds() / 86400)
        except Exception:
            oldest_days = None

    if oldest_days is not None and oldest_days > 3:
        subtext = f"Send today · Oldest waiting {oldest_days}d"
    else:
        subtext = f"{count} waiting · Send to keep momentum"
    return CardDrafts(count=count, subtext=subtext, oldest_days=oldest_days)


async def _build_reports(cid: str) -> CardReports:
    """Reports ready to compile: open tasks (state=active in current
    codebase) with `readiness_score >= 80`."""
    q = {
        "context_id": cid,
        "state": {"$nin": ["closed", "archived"]},
        "readiness_score": {"$gte": 80},
    }
    count = await db.tasks.count_documents(q)
    subtext = "Nothing ready yet." if count == 0 else "All ≥80% · Commit now"
    return CardReports(count=count, subtext=subtext)


async def _build_pulse(cid: str) -> CardPulse:
    """Pulse signals created in last 7 days. No `severity`/`priority`
    field exists in the wild (verified 2026-05-27: `db.signals.distinct`
    both return []), so we fall back to `type`:
      • critical      ← type ∈ {risk, gap}
      • opportunities ← type == opportunity
    Brief allows fallback to plain `{N} new this week` when severity
    is absent — we use the type-based decomposition since it's
    deterministic and present."""
    since = (_now() - timedelta(days=7)).isoformat()
    q = {"context_id": cid, "created_at": {"$gte": since}}

    cursor = db.signals.aggregate([
        {"$match": q},
        {"$group": {"_id": "$type", "n": {"$sum": 1}}},
    ])
    rows = await cursor.to_list(length=None)
    by_type = {(r["_id"] or "unknown"): r["n"] for r in rows}

    critical = by_type.get("risk", 0) + by_type.get("gap", 0)
    opportunities = by_type.get("opportunity", 0)
    count = sum(by_type.values())

    if count == 0:
        subtext = "Nothing new this week."
    elif critical and opportunities:
        subtext = f"{critical} critical · {opportunities} opportunities"
    elif critical:
        unit = "signal" if critical == 1 else "signals"
        subtext = f"{critical} critical {unit}"
    else:
        unit = "opportunity" if opportunities == 1 else "opportunities"
        subtext = f"{opportunities} {unit}"

    return CardPulse(
        count=count, subtext=subtext,
        critical=critical, opportunities=opportunities,
    )


async def _build_questions(cid: str) -> CardQuestions:
    """Open `cycle_questions`. I.2 surfaces COUNT only — the asker-
    role decomposition ("X from board · Y from CEO · Z from team")
    lands in I.5 once the `asker_role` field is added to the
    cycle_questions schema. Do NOT pre-wire that here."""
    count = await db.cycle_questions.count_documents({
        "context_id": cid,
        "status": "open",
    })
    subtext = "Nothing open." if count == 0 else "Awaiting clarification"
    return CardQuestions(count=count, subtext=subtext)


def _build_events() -> CardEvents:
    """Hard-coded empty state — the events collection ships in
    Phase I.4. Do NOT fall back to `tasks.final_due_date` etc. The
    brief is explicit: "Card stays empty-state-only until I.4 wires
    the real events collection." """
    return CardEvents(count=0, subtext="No events scheduled")


@router.get("/me/company-home/attention", response_model=AttentionOut)
async def attention(
    context_id: str = Query(..., min_length=4, max_length=120),
    me: Dict[str, Any] = Depends(get_current_account),
) -> AttentionOut:
    cid = context_id
    await _assert_member(me["id"], cid)

    cached = _CACHE.get((me["id"], cid, "attention"))
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_S:
        return AttentionOut(**cached[1])

    drafts    = await _build_drafts(cid)
    reports   = await _build_reports(cid)
    pulse     = await _build_pulse(cid)
    questions = await _build_questions(cid)
    events    = _build_events()

    out = {
        "drafts":    drafts.model_dump(),
        "reports":   reports.model_dump(),
        "pulse":     pulse.model_dump(),
        "questions": questions.model_dump(),
        "events":    events.model_dump(),
    }
    _CACHE[(me["id"], cid, "attention")] = (time.monotonic(), out)
    return AttentionOut(**out)
