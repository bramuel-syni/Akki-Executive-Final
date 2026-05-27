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


# -----------------------------------------------------------------------------
# Phase I.3 — Top Signals rail (2026-05-27)
# -----------------------------------------------------------------------------

class TopSignalItem(BaseModel):
    id:        str
    title:     str
    subtitle:  str
    severity:  Optional[str]   # "critical" | "warning" | "info" | None
    timestamp: Optional[str]
    deep_link: str


class TopSignalsOut(BaseModel):
    chip:            str
    items:           list[TopSignalItem]
    total_available: int


# Severity sort weight (critical highest). null/info treated as info-tier.
_SEVERITY_WEIGHT = {
    "critical": 0,
    "warning":  1,
    "info":     2,
    None:       2,
}


def _sort_by_severity_then_recency(items: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Tier 1: severity weight ascending. Tier 2: timestamp descending."""
    def _k(it):
        sev = _SEVERITY_WEIGHT.get(it.get("severity"), 2)
        # Negate timestamp string by inverting Unix sort — we want desc.
        # Using empty-string fallback so missing timestamps drop to bottom.
        ts = it.get("timestamp") or ""
        return (sev, _invert_ts(ts))
    return sorted(items, key=_k)


def _invert_ts(ts: str) -> str:
    """Helper for descending-timestamp sort under ascending tuple compare.
    ISO timestamps invert lexicographically by char-replacing every digit
    against its `9 - d` complement. Cheap and stable for sort."""
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in ts)


# ─── Chip: pulse ─────────────────────────────────────────────────
async def _build_pulse_items(cid: str, limit: int) -> tuple[list[Dict[str, Any]], int]:
    """Recent pulse signals. Type drives severity: risk/gap → critical,
    opportunity → info, unknown → warning. Limit `limit` after the
    severity-then-recency sort."""
    total = await db.signals.count_documents({"context_id": cid})
    cursor = db.signals.find(
        {"context_id": cid},
        {"_id": 0, "id": 1, "headline": 1, "summary": 1,
         "type": 1, "created_at": 1},
    ).sort("created_at", -1).limit(max(limit * 3, 30))
    raw = await cursor.to_list(length=max(limit * 3, 30))

    items = []
    for s in raw:
        kind = (s.get("type") or "").lower()
        if kind in ("risk", "gap"):
            sev = "critical"
        elif kind == "opportunity":
            sev = "info"
        else:
            sev = "warning"
        items.append({
            "id":        f"signal:{s['id']}",
            "title":     s.get("headline") or "(no headline)",
            "subtitle":  (s.get("summary") or "")[:140],
            "severity":  sev,
            "timestamp": s.get("created_at"),
            "deep_link": f"/app/pulse?signal_id={s['id']}&context_id={cid}",
        })
    items = _sort_by_severity_then_recency(items)[:limit]
    return items, total


# ─── Chip: monitor ───────────────────────────────────────────────
async def _build_monitor_items(cid: str, limit: int) -> tuple[list[Dict[str, Any]], int]:
    """Union: checklists (status=active) + submissions (status in
    {pending_approval, dispatched}) + reports (status in {draft,
    in_review}). Reuses the live `/api/contexts/{cid}/monitor` query
    logic. Sort: updated_at desc (severity=null on all)."""
    over_fetch = max(limit * 3, 30)

    ck_cursor = db.checklists.find(
        {"context_id": cid, "status": "active"},
        {"_id": 0, "id": 1, "name": 1, "title": 1,
         "updated_at": 1, "created_at": 1, "status": 1},
    ).sort("updated_at", -1).limit(over_fetch)
    sb_cursor = db.submissions.find(
        {"context_id": cid, "status": {"$in": ["pending_approval", "dispatched"]}},
        {"_id": 0, "id": 1, "subject": 1, "title": 1,
         "updated_at": 1, "created_at": 1, "status": 1},
    ).sort("updated_at", -1).limit(over_fetch)
    rp_cursor = db.reports.find(
        {"context_id": cid, "status": {"$in": ["draft", "in_review"]}},
        {"_id": 0, "id": 1, "title": 1,
         "updated_at": 1, "created_at": 1, "status": 1},
    ).sort("updated_at", -1).limit(over_fetch)

    checklists  = await ck_cursor.to_list(length=over_fetch)
    submissions = await sb_cursor.to_list(length=over_fetch)
    reports     = await rp_cursor.to_list(length=over_fetch)

    total_avail = len(checklists) + len(submissions) + len(reports)

    items = []
    for ck in checklists:
        items.append({
            "id":        f"checklist:{ck['id']}",
            "title":     ck.get("name") or ck.get("title") or "(checklist)",
            "subtitle":  "Checklist · Active",
            "severity":  None,
            "timestamp": ck.get("updated_at") or ck.get("created_at"),
            "deep_link": f"/app/monitor?context_id={cid}&focus=checklist:{ck['id']}",
        })
    for sb in submissions:
        st = (sb.get("status") or "").replace("_", " ").capitalize()
        items.append({
            "id":        f"submission:{sb['id']}",
            "title":     sb.get("subject") or sb.get("title") or "(submission)",
            "subtitle":  f"Submission · {st}",
            "severity":  None,
            "timestamp": sb.get("updated_at") or sb.get("created_at"),
            "deep_link": f"/app/monitor?context_id={cid}&focus=submission:{sb['id']}",
        })
    for rp in reports:
        st = (rp.get("status") or "").replace("_", " ").capitalize()
        items.append({
            "id":        f"report:{rp['id']}",
            "title":     rp.get("title") or "(report)",
            "subtitle":  f"Report · {st}",
            "severity":  None,
            "timestamp": rp.get("updated_at") or rp.get("created_at"),
            "deep_link": f"/app/monitor?context_id={cid}&focus=report:{rp['id']}",
        })

    # Sort union by updated_at desc, since severity is null across.
    items.sort(key=lambda it: it.get("timestamp") or "", reverse=True)
    return items[:limit], total_avail


# ─── Chip: documents ─────────────────────────────────────────────
async def _build_document_items(cid: str, limit: int) -> tuple[list[Dict[str, Any]], int]:
    """All documents for this context, sorted by `updated_at` desc
    (fall back to `created_at` if `updated_at` is missing). Severity
    is always null — documents aren't graded."""
    total = await db.documents.count_documents({"context_id": cid})
    cursor = db.documents.find(
        {"context_id": cid},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
         "description": 1, "doc_type": 1,
         "updated_at": 1, "created_at": 1},
    ).sort([("updated_at", -1), ("created_at", -1)]).limit(limit)
    raw = await cursor.to_list(length=limit)

    items = []
    for d in raw:
        title = d.get("name") or d.get("original_filename") or "(document)"
        kind  = d.get("doc_type") or "Document"
        items.append({
            "id":        f"document:{d['id']}",
            "title":     title,
            "subtitle":  kind,
            "severity":  None,
            "timestamp": d.get("updated_at") or d.get("created_at"),
            "deep_link": f"/app/work-studio?doc_id={d['id']}&context_id={cid}",
        })
    return items, total


_CHIP_BUILDERS = {
    "pulse":     _build_pulse_items,
    "monitor":   _build_monitor_items,
    "documents": _build_document_items,
}


@router.get("/me/company-home/top-signals", response_model=TopSignalsOut)
async def top_signals(
    context_id: str = Query(..., min_length=4, max_length=120),
    chip:       str = Query("pulse"),
    limit:      int = Query(10, ge=1, le=50),
    me: Dict[str, Any] = Depends(get_current_account),
) -> TopSignalsOut:
    """Right-rail Top Signals chip data feed. 60s cache per
    (account, context, chip). Severity sort applies on the Pulse
    chip; the Monitor + Documents chips have severity=null on every
    row and fall back to timestamp-desc sort."""
    cid = context_id
    chip_key = (chip or "").strip().lower()
    if chip_key not in _CHIP_BUILDERS:
        raise HTTPException(status_code=400, detail=f"Unknown chip: {chip!r}")

    await _assert_member(me["id"], cid)

    cache_key = (me["id"], cid, f"top-signals:{chip_key}:{limit}")
    cached = _CACHE.get(cache_key)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_S:
        return TopSignalsOut(**cached[1])

    builder = _CHIP_BUILDERS[chip_key]
    items, total = await builder(cid, limit)

    out = {
        "chip":            chip_key,
        "items":           items,
        "total_available": total,
    }
    _CACHE[cache_key] = (time.monotonic(), out)
    return TopSignalsOut(**out)
