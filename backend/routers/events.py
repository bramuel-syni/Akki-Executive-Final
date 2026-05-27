"""Phase I.4.a — Events system, manual entry (2026-05-27).
Phase I.4.b — Doc-extraction LLM scan (2026-05-27).

CRUD endpoints for the `events` collection (new in I.4.a). Backs the
Events surface at `/app/events` and the Company Home Card 5 ("Upcoming
events") wiring.

I.4.b extends this with a single LLM-extraction endpoint that scans
uploaded board packs / briefings / cycle compilations / strategy docs
and stages extracted events as `status="draft"`. The user then
confirms / rejects from the new "Extracted" tab in the Events page.

Out-of-scope (deferred to later I.4 sub-phases):
  • I.4.c — calendar sync (Google/Outlook OAuth)
  • Recurring events / reminders / notifications
  • Cross-document deduplication
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, get_current_account


router = APIRouter(prefix="/api", tags=["events"])

log = logging.getLogger(__name__)


_EVENT_TYPES = {"board_meeting", "audit_review", "briefing", "deadline", "other"}

# I.4.b (2026-05-27) — doc_type values that trigger AUTO-extraction on
# upload. Endpoint itself is callable on ANY document — this is just
# the auto-trigger gate. Decided 2026-05-27 (E1: option b): wider net
# for "magical" auto-extraction value, no real downside.
_AUTO_EXTRACT_DOC_TYPES = {
    "Board pack",
    "briefing",
    "cycle_compilation",
    "strategy_document",
}

# Extraction confidence floor. Items below this are discarded.
_MIN_CONFIDENCE = 0.6

# Pass-2 date-window guards (decided 2026-05-27, E3 confirm).
_PAST_GRACE_DAYS = 7
_FUTURE_HORIZON_MONTHS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso_or_400(s: str, field: str) -> str:
    """Validate the input is an ISO-parseable datetime; return its
    canonical ISO form (we store strings to stay symmetric with the
    rest of the codebase which uses ISO strings everywhere)."""
    if not isinstance(s, str) or not s:
        raise HTTPException(status_code=422, detail=f"`{field}` is required")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=422, detail=f"`{field}` is not a valid ISO datetime")
    return _iso(dt)


# -----------------------------------------------------------------------------
# Membership guard
# -----------------------------------------------------------------------------

async def _assert_member(account_id: str, context_id: str) -> None:
    m = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id, "status": "active"},
        {"_id": 0, "account_id": 1},
    )
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this context")


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class EventIn(BaseModel):
    title:    str = Field(..., min_length=1, max_length=200)
    type:     str = Field(..., min_length=1, max_length=40)
    start_at: str = Field(..., min_length=1)
    end_at:   Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    notes:    Optional[str] = Field(None, max_length=2000)


class EventPatch(BaseModel):
    title:    Optional[str] = Field(None, min_length=1, max_length=200)
    type:     Optional[str] = Field(None, min_length=1, max_length=40)
    start_at: Optional[str] = None
    end_at:   Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    notes:    Optional[str] = Field(None, max_length=2000)
    # I.4.b — allow confirming a draft via PATCH (status: "draft" → "confirmed").
    status:   Optional[str] = None


class EventOut(BaseModel):
    id:        str
    context_id: str
    title:     str
    type:      str
    start_at:  str
    end_at:    Optional[str]
    location:  Optional[str]
    notes:     Optional[str]
    source:    str
    source_ref: Optional[str]
    created_by_account_id: str
    created_at: str
    updated_at: str
    # I.4.b — extraction fields. Optional/None for manual entries.
    status:     Optional[str] = None     # "draft" | "confirmed" | None (absent = confirmed)
    confidence: Optional[float] = None
    extracted_at: Optional[str] = None
    extracted_by: Optional[str] = None


class EventsList(BaseModel):
    items: List[EventOut]
    total: int


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/contexts/{cid}/events", response_model=EventOut)
async def create_event(
    cid: str,
    body: EventIn,
    me: Dict[str, Any] = Depends(get_current_account),
) -> EventOut:
    await _assert_member(me["id"], cid)
    if body.type not in _EVENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid type. One of: {sorted(_EVENT_TYPES)}")
    start_iso = _parse_iso_or_400(body.start_at, "start_at")
    end_iso = _parse_iso_or_400(body.end_at, "end_at") if body.end_at else None
    now_iso = _iso(_now())
    doc = {
        "id":         str(uuid.uuid4()),
        "context_id": cid,
        "title":      body.title.strip(),
        "type":       body.type,
        "start_at":   start_iso,
        "end_at":     end_iso,
        "location":   (body.location or None),
        "notes":      (body.notes or None),
        "source":     "manual",
        "source_ref": None,
        "created_by_account_id": me["id"],
        "created_at": now_iso,
        "updated_at": now_iso,
        "deleted_at": None,
    }
    await db.events.insert_one(dict(doc))
    return EventOut(**{k: v for k, v in doc.items() if k != "deleted_at"})


@router.get("/contexts/{cid}/events", response_model=EventsList)
async def list_events(
    cid: str,
    upcoming: bool = Query(True),
    limit:    int  = Query(50, ge=1, le=100),
    status:   Optional[str] = Query(None),
    me: Dict[str, Any] = Depends(get_current_account),
) -> EventsList:
    """List events for a context.

    `status` filter (I.4.b):
      • None (default) → all non-deleted events (mirrors I.4.a behavior)
      • "draft"        → only extracted drafts awaiting user confirm/reject
      • "confirmed"    → confirmed events ONLY (absence-default included
        via `$ne:"draft"`; manual events without a status count)
    """
    await _assert_member(me["id"], cid)
    q: Dict[str, Any] = {
        "context_id": cid,
        "deleted_at": None,
    }
    if upcoming:
        q["start_at"] = {"$gte": _iso(_now())}
    if status == "draft":
        q["status"] = "draft"
    elif status == "confirmed":
        # Absence-default: events without a `status` field are implicitly
        # confirmed (per E2 decision 2026-05-27). `$ne:"draft"` covers
        # both literal "confirmed" AND absent-field.
        q["status"] = {"$ne": "draft"}
    cursor = (
        db.events.find(q, {"_id": 0, "deleted_at": 0})
        .sort("start_at", 1)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)
    total = await db.events.count_documents(q)
    return EventsList(items=[EventOut(**d) for d in items], total=total)


@router.get("/contexts/{cid}/events/{event_id}", response_model=EventOut)
async def get_event(
    cid: str,
    event_id: str,
    me: Dict[str, Any] = Depends(get_current_account),
) -> EventOut:
    await _assert_member(me["id"], cid)
    row = await db.events.find_one(
        {"id": event_id, "context_id": cid, "deleted_at": None},
        {"_id": 0, "deleted_at": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventOut(**row)


@router.patch("/contexts/{cid}/events/{event_id}", response_model=EventOut)
async def update_event(
    cid: str,
    event_id: str,
    body: EventPatch,
    me: Dict[str, Any] = Depends(get_current_account),
) -> EventOut:
    await _assert_member(me["id"], cid)
    updates: Dict[str, Any] = {}
    if body.title is not None:    updates["title"] = body.title.strip()
    if body.type is not None:
        if body.type not in _EVENT_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid type. One of: {sorted(_EVENT_TYPES)}")
        updates["type"] = body.type
    if body.start_at is not None: updates["start_at"] = _parse_iso_or_400(body.start_at, "start_at")
    if body.end_at is not None:   updates["end_at"]   = _parse_iso_or_400(body.end_at, "end_at") if body.end_at else None
    if body.location is not None: updates["location"] = body.location or None
    if body.notes is not None:    updates["notes"]    = body.notes or None
    if body.status is not None:
        # I.4.b — only "confirmed" can be set via PATCH (promotes a
        # draft); "draft" is server-set only (extraction endpoint).
        if body.status != "confirmed":
            raise HTTPException(
                status_code=422,
                detail="status can only be set to 'confirmed' via PATCH (drafts are server-created)",
            )
        updates["status"] = "confirmed"
    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update")
    updates["updated_at"] = _iso(_now())

    res = await db.events.find_one_and_update(
        {"id": event_id, "context_id": cid, "deleted_at": None},
        {"$set": updates},
        projection={"_id": 0, "deleted_at": 0},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventOut(**res)


@router.delete("/contexts/{cid}/events/{event_id}")
async def delete_event(
    cid: str,
    event_id: str,
    me: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    await _assert_member(me["id"], cid)
    res = await db.events.update_one(
        {"id": event_id, "context_id": cid, "deleted_at": None},
        {"$set": {"deleted_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"ok": True, "deleted_id": event_id}



# -----------------------------------------------------------------------------
# Phase I.4.b — Doc-extraction LLM scan (2026-05-27)
# -----------------------------------------------------------------------------

class ExtractEventsOut(BaseModel):
    extracted:           List[Dict[str, Any]]
    persisted_draft_ids: List[str]
    discarded:           Dict[str, int]   # {"low_confidence": int, "out_of_window": int}


def _coerce_extracted_iso(s: Any) -> Optional[str]:
    """LLM-returned dates can be partial ('2026-06-15', '2026-06-15T14:00')
    OR natural-language ('15 June 2026') OR bracket-wrapped by the
    Synisense de-identifier ('[15 June 2026]'). Coerce to a full ISO
    datetime; return None if unparseable."""
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip()
    # Synisense de-id may surround dates with brackets; strip if balanced.
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1].strip()
    if not s:
        return None
    # Date-only → assume 09:00 local-naive (then UTC)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        s = s + "T09:00:00"
    # First try strict ISO
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        # Fallback to dateutil for natural-language ("15 June 2026").
        try:
            from dateutil import parser as _dateutil_parser
            dt = _dateutil_parser.parse(s, fuzzy=True, default=datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0))
        except Exception:
            return None
    # If naive, treat as UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _map_extracted_type(t: Any) -> str:
    """Coerce extracted `type` to the I.4.a 5-value taxonomy."""
    if not isinstance(t, str):
        return "other"
    t = t.strip().lower().replace(" ", "_").replace("-", "_")
    if t in _EVENT_TYPES:
        return t
    # Friendly aliases the LLM might produce.
    aliases = {
        "board_meeting": {"board", "agm", "annual_general_meeting", "board_session", "meeting"},
        "audit_review":  {"audit", "auditing", "audit_committee", "audit_meeting", "committee_meeting", "committee_review"},
        "briefing":      {"brief", "pre_briefing", "exec_briefing", "executive_briefing"},
        "deadline":      {"due_date", "submission", "due", "filing_deadline", "year_end", "year_end_review", "cut_off", "cutoff"},
    }
    for canonical, alts in aliases.items():
        if t in alts:
            return canonical
    return "other"


def _within_window(start_iso: str) -> bool:
    """Pass-2 guard: discard events <7d past OR >24mo future (E3 confirm)."""
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except Exception:
        return False
    now = _now()
    if dt < now - timedelta(days=_PAST_GRACE_DAYS):
        return False
    # ≈24 months = 730 days
    if dt > now + timedelta(days=_FUTURE_HORIZON_MONTHS * 30 + 30):
        return False
    return True


_EXTRACTION_SYSTEM_PROMPT = (
    "You are AKKI's structured-extraction model. Strict JSON only. "
    "Never invent events that are not in the source text. If no events "
    "are present, return an empty list."
)


def _build_extraction_user_prompt(doc_name: str, doc_text: str) -> str:
    """Build the verbatim extractor prompt. Truncated to first 12 000 chars
    of the doc text (same convention as `prepare.py::extract_minutes`)."""
    return (
        "You are reading a board document for an executive who needs to "
        "know the upcoming events that this document references. Scan the "
        "text and extract every time-bound event you can find: board "
        "meetings, committee reviews, audits, briefings, regulatory "
        "deadlines, AGMs, year-end reviews, submission cut-offs, training "
        "dates, etc. Be precise. Do NOT invent events that aren't in the "
        "source text.\n\n"
        f"DOCUMENT TITLE: {doc_name}\n\n"
        "DOCUMENT TEXT (truncated to first 12 000 chars):\n"
        f"{doc_text[:12000]}\n\n"
        "Return STRICT JSON ONLY with this exact shape:\n"
        '{"events": [\n'
        '  {\n'
        '    "title": "<<short event title, ≤120 chars>>",\n'
        '    "type":  "<<one of: board_meeting | audit_review | briefing | deadline | other>>",\n'
        '    "start_at": "<<ISO datetime YYYY-MM-DDTHH:MM or just YYYY-MM-DD>>",\n'
        '    "end_at":   "<<ISO datetime or null>>",\n'
        '    "location": "<<location string or null>>",\n'
        '    "notes":    "<<brief context, ≤200 chars, or null>>",\n'
        '    "confidence": <<float 0.0-1.0 — how confident you are this is a real event from the doc>>\n'
        '  }\n'
        ']}\n'
        "If no events are present, return {\"events\": []}."
    )


async def _extract_and_persist(
    cid: str,
    doc_id: str,
    actor_id: str,
) -> ExtractEventsOut:
    """Core extraction routine. Reads doc text, calls the shielded LLM
    gateway, parses + filters + persists drafts, idempotent on prior
    drafts for the same `(cid, doc_id)`."""
    doc = await db.documents.find_one(
        {"id": doc_id, "context_id": cid},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
         "extracted_text": 1, "doc_type": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found in this context")
    text = (doc.get("extracted_text") or "").strip()
    if len(text) < 80:
        # Match the prepare.py::extract_minutes precedent — caller can
        # interpret as "doc has no readable text".
        raise HTTPException(status_code=400, detail="Document has no readable text to extract from.")

    doc_name = doc.get("name") or doc.get("original_filename") or "Document"
    user_prompt = _build_extraction_user_prompt(doc_name, text)

    # Single LLM call via the existing shielded gateway. `tier="standard"`
    # routes to Claude Sonnet 4.5 — same precedent as
    # `prepare.py::extract_minutes` which is the canonical structured-
    # extraction pattern in this codebase. Faster `tier="fast"`
    # (Gemini 2.5 Flash) was tried first but exceeds the 20s gateway
    # timeout for structured extraction prompts of this size.
    try:
        from llm_service import call_llm
        llm_out = await call_llm(
            module="events_extract",
            user_query=user_prompt,
            system_override=_EXTRACTION_SYSTEM_PROMPT,
            response_format="json",
            tier="standard",
            purpose="documents.events_extract",
            session_context={"context_id": cid},
        )
    except Exception as e:
        log.warning("[events.extract] LLM gateway failed for doc %s: %s", doc_id, e)
        raise HTTPException(status_code=502, detail=f"Extractor unavailable: {e}") from e

    from helpers.llm_json import safe_parse_json
    parsed, raw_str = safe_parse_json(llm_out.get("response") or "{}")
    if not isinstance(parsed, dict):
        parsed = {}
    raw_events = parsed.get("events") or []
    if not isinstance(raw_events, list):
        raw_events = []

    # Diagnostic line (INFO so first prod incidents have it for free;
    # truncates the raw response head to 200 chars — no PII leak risk
    # since Shield has already de-identified the input).
    log.info(
        "[events.extract] doc=%s mode=%s raw=%d kept_pre_filter=%d head=%r",
        doc_id, llm_out.get("mode"), len(raw_events),
        sum(1 for e in raw_events if isinstance(e, dict) and e.get("title")),
        (raw_str or "")[:200],
    )

    discarded = {"low_confidence": 0, "out_of_window": 0, "malformed": 0}
    extracted_clean: List[Dict[str, Any]] = []
    for ev in raw_events:
        if not isinstance(ev, dict):
            discarded["malformed"] += 1
            continue
        title = (ev.get("title") or "").strip()
        if not title:
            discarded["malformed"] += 1
            continue
        start_iso = _coerce_extracted_iso(ev.get("start_at"))
        if not start_iso:
            discarded["malformed"] += 1
            continue
        try:
            conf = float(ev.get("confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf < _MIN_CONFIDENCE:
            discarded["low_confidence"] += 1
            continue
        if not _within_window(start_iso):
            discarded["out_of_window"] += 1
            continue
        end_iso = _coerce_extracted_iso(ev.get("end_at")) if ev.get("end_at") else None
        extracted_clean.append({
            "title":      title[:200],
            "type":       _map_extracted_type(ev.get("type")),
            "start_at":   start_iso,
            "end_at":     end_iso,
            "location":   (str(ev.get("location"))[:200].strip() if ev.get("location") else None),
            "notes":      (str(ev.get("notes"))[:2000].strip() if ev.get("notes") else None),
            "confidence": max(0.0, min(1.0, conf)),
        })

    # Idempotency (E4 confirm): delete prior DRAFT rows for this
    # `(context_id, doc_id, source="doc_extraction", status="draft")`
    # before persisting new ones. Confirmed events untouched.
    # Soft-deleted (rejected) events stay rejected — we explicitly
    # exclude `deleted_at: None` from the wipe, so they don't resurrect.
    await db.events.delete_many({
        "context_id": cid,
        "source": "doc_extraction",
        "source_ref": doc_id,
        "status": "draft",
        "deleted_at": None,
    })

    now_iso = _iso(_now())
    persisted_ids: List[str] = []
    for clean in extracted_clean:
        new_id = str(uuid.uuid4())
        await db.events.insert_one({
            "id":         new_id,
            "context_id": cid,
            "title":      clean["title"],
            "type":       clean["type"],
            "start_at":   clean["start_at"],
            "end_at":     clean["end_at"],
            "location":   clean["location"],
            "notes":      clean["notes"],
            "source":     "doc_extraction",
            "source_ref": doc_id,
            "status":     "draft",
            "confidence": clean["confidence"],
            "extracted_at": now_iso,
            "extracted_by": "akki_extractor",
            "created_by_account_id": actor_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "deleted_at": None,
        })
        persisted_ids.append(new_id)

    return ExtractEventsOut(
        extracted=extracted_clean,
        persisted_draft_ids=persisted_ids,
        discarded=discarded,
    )


@router.post(
    "/contexts/{cid}/documents/{doc_id}/extract-events",
    response_model=ExtractEventsOut,
)
async def extract_events_from_document(
    cid: str,
    doc_id: str,
    me: Dict[str, Any] = Depends(get_current_account),
) -> ExtractEventsOut:
    """Phase I.4.b — LLM-extract time-bound events from a document.

    Returns the cleaned + filtered extractions and persists each as
    `status="draft"`. User reviews / confirms / rejects from the
    Events page Extracted tab.

    Idempotent on `(context_id, doc_id, source="doc_extraction",
    status="draft")` — re-running on the same doc replaces prior
    drafts; confirmed + rejected events are untouched.

    Callable on ANY document the caller has access to; the
    background auto-trigger on document upload is gated by an
    allowlist of `doc_type` values (see `_AUTO_EXTRACT_DOC_TYPES`).
    """
    await _assert_member(me["id"], cid)
    return await _extract_and_persist(cid=cid, doc_id=doc_id, actor_id=me["id"])


async def auto_extract_after_upload(cid: str, doc_id: str, doc_type: Optional[str], actor_id: str) -> None:
    """Background-task hook for `documents.upload_document`. Best-effort:
    failures are logged and swallowed, NEVER block the upload response.

    Only runs if `doc_type` is in the allowlist (decided 2026-05-27 E1=b).
    """
    if not doc_type or doc_type not in _AUTO_EXTRACT_DOC_TYPES:
        return
    try:
        result = await _extract_and_persist(cid=cid, doc_id=doc_id, actor_id=actor_id)
        log.info(
            "[events.auto_extract] doc=%s persisted=%d discarded=%s",
            doc_id, len(result.persisted_draft_ids), result.discarded,
        )
    except HTTPException as e:
        # 400 (no text) / 404 (deleted between upload and BG task) — log + swallow.
        log.info("[events.auto_extract] doc=%s skipped: %s", doc_id, e.detail)
    except Exception as e:  # noqa: BLE001
        log.warning("[events.auto_extract] doc=%s failed: %s", doc_id, e)
