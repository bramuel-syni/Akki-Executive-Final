"""Phase I.4.a — Events system, manual entry only (2026-05-27).

CRUD endpoints for the `events` collection (new). Backs the Events
surface at `/app/events` and the Company Home Card 5 ("Upcoming
events") wiring.

Out-of-scope (deferred to later I.4 sub-phases):
  • Doc extraction (I.4.b) — LLM scans board packs for events
  • Calendar sync (I.4.c) — Google/Outlook OAuth
  • Recurring events / reminders / notifications
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, get_current_account


router = APIRouter(prefix="/api", tags=["events"])


_EVENT_TYPES = {"board_meeting", "audit_review", "briefing", "deadline", "other"}


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
    me: Dict[str, Any] = Depends(get_current_account),
) -> EventsList:
    await _assert_member(me["id"], cid)
    q: Dict[str, Any] = {
        "context_id": cid,
        "deleted_at": None,
    }
    if upcoming:
        q["start_at"] = {"$gte": _iso(_now())}
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
