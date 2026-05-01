"""Cycle config — Phase 2 (Advisory 6).

Per-context cycle phase configuration powering the Cycle Strip on Home
and `/app/cycle`. A context gets a 6-phase default lazily on first GET;
owner/admin can rename, reorder, change durations, advance the cycle,
or reset back to defaults.

Schema (`db.cycle_configs`):
    {
      _id, context_id, phases: [{id, name, order, default_duration_days}],
      current_phase_id, cycle_started_at (iso str), updated_at (iso str),
      schema_version: 1
    }

History (`db.cycle_history`) is initialised by the advance-wrap path so
v2 can render previous-cycle summaries; v1 only reads the current cycle.

See `/app/docs/ux-advisories-v1.md` Cycle section for the binding rules.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, write_audit, require_context_membership

router = APIRouter(prefix="/api")

CYCLE_CONFIG_SCHEMA_VERSION = 1

DEFAULT_PHASES: List[Dict[str, Any]] = [
    {"id": "pack_arriving", "name": "Pack arriving", "order": 0, "default_duration_days": 3},
    {"id": "reading_week",  "name": "Reading week",  "order": 1, "default_duration_days": 7},
    {"id": "pre_board",     "name": "Pre-board",     "order": 2, "default_duration_days": 2},
    {"id": "meeting",       "name": "Meeting",       "order": 3, "default_duration_days": 1},
    {"id": "minutes",       "name": "Minutes",       "order": 4, "default_duration_days": 5},
    {"id": "follow_up",     "name": "Follow-up",     "order": 5, "default_duration_days": 14},
]
DEFAULT_PHASE_IDS = {p["id"] for p in DEFAULT_PHASES}
DEFAULT_FIRST_PHASE_ID = DEFAULT_PHASES[0]["id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _ensure_index() -> None:
    """Idempotent index creation (called on first router hit)."""
    try:
        await db.cycle_configs.create_index("context_id", unique=True)
    except Exception:  # noqa: BLE001
        pass


def _slug_id(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (name or "phase").strip().lower()).strip("_") or "phase"
    suffix = hashlib.sha1(f"{name}|{uuid.uuid4().hex}".encode("utf-8")).hexdigest()[:6]
    return f"{base}_{suffix}"


def _serialise(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    return out


def _strip_owner(ctx_dict: Dict[str, Any]) -> bool:
    """Convenience: are we the context owner / admin in this membership?"""
    return ctx_dict.get("context", {}).get("owner_account_id") == ctx_dict.get("account", {}).get("id") \
        or ctx_dict.get("membership", {}).get("sub_role") == "admin"


async def _load_or_create_default(context_id: str) -> Dict[str, Any]:
    """Lazy-create the 6-phase default config when the context has none."""
    existing = await db.cycle_configs.find_one({"context_id": context_id})
    if existing:
        return existing
    doc = {
        "context_id": context_id,
        "phases": [dict(p) for p in DEFAULT_PHASES],
        "current_phase_id": DEFAULT_FIRST_PHASE_ID,
        "cycle_started_at": iso(now()),
        "updated_at": iso(now()),
        "schema_version": CYCLE_CONFIG_SCHEMA_VERSION,
    }
    await db.cycle_configs.insert_one(doc)
    return doc


def _validate_phases(payload_phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Coerce + validate the incoming phases array.

    Rules:
      * non-empty list
      * each entry has a name (1..60 chars) and a default_duration_days (>=0)
      * IDs are unique. Default IDs (pack_arriving, etc.) are preserved
        when name+order match; new phases get an auto-generated id.
      * order is contiguous, 0..N-1.
    """
    if not isinstance(payload_phases, list) or not payload_phases:
        raise HTTPException(status_code=400, detail="At least one phase is required.")

    cleaned: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for idx, raw in enumerate(payload_phases):
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail=f"Phase #{idx} is not an object.")
        name = (raw.get("name") or "").strip()
        if not name or len(name) > 60:
            raise HTTPException(status_code=400, detail=f"Phase #{idx}: name must be 1..60 chars.")
        try:
            duration = int(raw.get("default_duration_days", 0))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Phase #{idx}: default_duration_days must be an integer.")
        if duration < 0 or duration > 365:
            raise HTTPException(status_code=400, detail=f"Phase #{idx}: default_duration_days must be 0..365.")
        pid = (raw.get("id") or "").strip() or _slug_id(name)
        if pid in seen_ids:
            raise HTTPException(status_code=400, detail=f"Phase id '{pid}' is duplicated.")
        seen_ids.add(pid)
        cleaned.append({
            "id": pid,
            "name": name,
            "order": idx,
            "default_duration_days": duration,
        })
    return cleaned


def _phase_window(config: Dict[str, Any], phase_id: str) -> Optional[Dict[str, str]]:
    """Compute the [start, end) window of the named phase relative to
    cycle_started_at + cumulative durations of prior phases."""
    started_iso = config.get("cycle_started_at")
    if not started_iso:
        return None
    try:
        started = datetime.fromisoformat(started_iso.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
    cursor = started
    for phase in sorted(config["phases"], key=lambda p: p["order"]):
        delta_days = int(phase.get("default_duration_days") or 0)
        end = cursor + _timedelta(days=delta_days)
        if phase["id"] == phase_id:
            return {"start": iso(cursor), "end": iso(end)}
        cursor = end
    return None


def _timedelta(days: int):
    from datetime import timedelta
    return timedelta(days=days)


# Phase id → list of (collection, time-field, optional-extra-filter, projection-fields).
PHASE_QUERY_MAP: Dict[str, List[Dict[str, Any]]] = {
    "pack_arriving": [
        {"key": "documents", "collection": "documents", "time": "created_at",
         "filter": {"status": {"$ne": "archived"}}, "fields": {"id": 1, "name": 1, "created_at": 1}},
    ],
    "reading_week": [
        {"key": "signals", "collection": "signals", "time": "created_at",
         "filter": {"status": "active"}, "fields": {"id": 1, "headline": 1, "created_at": 1}},
        {"key": "ask_messages", "collection": "ask_messages", "time": "created_at",
         "filter": {}, "fields": {"id": 1, "question": 1, "created_at": 1}},
    ],
    "pre_board": [
        {"key": "briefings", "collection": "briefings", "time": "created_at",
         "filter": {"status": "active"}, "fields": {"id": 1, "title": 1, "created_at": 1}},
        {"key": "decks", "collection": "decks", "time": "created_at",
         "filter": {"status": {"$ne": "archived"}}, "fields": {"id": 1, "title": 1, "created_at": 1}},
    ],
    "meeting": [
        {"key": "walkin", "collection": "walkin_sessions", "time": "created_at",
         "filter": {}, "fields": {"id": 1, "title": 1, "created_at": 1}},
    ],
    "minutes": [
        {"key": "documents", "collection": "documents", "time": "created_at",
         "filter": {"status": {"$ne": "archived"}, "$or": [
             {"doc_type": {"$regex": "minute", "$options": "i"}},
             {"minutes_extracted_at": {"$exists": True}},
         ]},
         "fields": {"id": 1, "name": 1, "created_at": 1}},
    ],
    "follow_up": [
        {"key": "reports", "collection": "reports", "time": "created_at",
         "filter": {"status": {"$ne": "archived"}}, "fields": {"id": 1, "title": 1, "created_at": 1}},
        {"key": "signal_actions", "collection": "signal_actions", "time": "created_at",
         "filter": {}, "fields": {"id": 1, "label": 1, "created_at": 1}},
    ],
}


# Mirror map: which phase IDs are referenced by which kind of artefact.
# Used by the delete-phase guard.
ARTEFACT_PHASE_REF_MAP = {
    "cycle_history": "phases",  # history records freeze the phases that were active
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PhaseIn(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=60)
    default_duration_days: int = Field(ge=0, le=365)


class CycleConfigUpdate(BaseModel):
    # `phases` is Optional at the schema level so the handler can return a
    # consistent 400-with-clean-message rather than FastAPI's auto-422 when
    # callers PUT only `{current_phase_id: "..."}`. The handler enforces
    # presence + validates contents below.
    phases: Optional[List[PhaseIn]] = None
    current_phase_id: str = Field(min_length=1, max_length=80)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/contexts/{context_id}/cycle-config")
async def get_cycle_config(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Read the cycle config; lazy-create the 6-phase default if missing."""
    await _ensure_index()
    cid = ctx["context"]["id"]
    cfg = await _load_or_create_default(cid)
    return _serialise(cfg)


@router.put("/contexts/{context_id}/cycle-config")
async def update_cycle_config(
    body: CycleConfigUpdate,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    """Owner/admin-only edit. Validates phase IDs unique, order contiguous,
    current_phase_id present in phases. 409 if a deleted phase still has
    artefacts referencing it via cycle_history."""
    cid = ctx["context"]["id"]
    existing = await _load_or_create_default(cid)

    if body.phases is None:
        raise HTTPException(
            status_code=400,
            detail="`phases` is required. Send the full phases array, even if you’re only changing current_phase_id.",
        )
    new_phases = _validate_phases([p.model_dump() for p in body.phases])
    new_ids = {p["id"] for p in new_phases}
    if body.current_phase_id not in new_ids:
        raise HTTPException(
            status_code=400,
            detail=f"current_phase_id '{body.current_phase_id}' is not in the phases list.",
        )

    # Detect phases that existed before but are being removed; if any are
    # referenced by cycle_history.phases, reject with 409.
    old_ids = {p["id"] for p in existing.get("phases", [])}
    removed = old_ids - new_ids
    if removed:
        # cycle_history is initialised lazily when advance wraps; v1 may have
        # zero records so this is usually a no-op.
        history_refs = await db.cycle_history.count_documents({
            "context_id": cid,
            "phases.id": {"$in": list(removed)},
        })
        if history_refs > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot remove phases referenced by historical cycles: {sorted(removed)}",
            )

    update = {
        "phases": new_phases,
        "current_phase_id": body.current_phase_id,
        "updated_at": iso(now()),
        "schema_version": CYCLE_CONFIG_SCHEMA_VERSION,
    }
    await db.cycle_configs.update_one({"context_id": cid}, {"$set": update})
    cfg = await db.cycle_configs.find_one({"context_id": cid})
    await write_audit(
        cid, ctx["account"]["id"], "cycle_config.update", "cycle_config", cid,
        {"phase_count": len(new_phases), "current_phase_id": body.current_phase_id},
    )
    return _serialise(cfg)


@router.post("/contexts/{context_id}/cycle-config/advance")
async def advance_cycle_phase(
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    """Move current_phase_id to the next phase by `order`. From the last
    phase wraps back to the first phase, snapshots the current cycle into
    `db.cycle_history` and resets cycle_started_at."""
    cid = ctx["context"]["id"]
    cfg = await _load_or_create_default(cid)
    phases_sorted = sorted(cfg["phases"], key=lambda p: p["order"])
    current_id = cfg["current_phase_id"]
    try:
        cur_idx = next(i for i, p in enumerate(phases_sorted) if p["id"] == current_id)
    except StopIteration:
        cur_idx = 0
    next_idx = cur_idx + 1
    wrapping = next_idx >= len(phases_sorted)
    if wrapping:
        # Snapshot the cycle that just finished into history.
        await db.cycle_history.insert_one({
            "context_id": cid,
            "started_at": cfg.get("cycle_started_at"),
            "ended_at": iso(now()),
            "phases": cfg["phases"],
            "schema_version": CYCLE_CONFIG_SCHEMA_VERSION,
        })
        next_phase_id = phases_sorted[0]["id"]
        new_started = iso(now())
    else:
        next_phase_id = phases_sorted[next_idx]["id"]
        new_started = cfg.get("cycle_started_at")

    update = {
        "current_phase_id": next_phase_id,
        "cycle_started_at": new_started,
        "updated_at": iso(now()),
    }
    await db.cycle_configs.update_one({"context_id": cid}, {"$set": update})
    await write_audit(
        cid, ctx["account"]["id"], "cycle_config.advance", "cycle_config", cid,
        {"from": current_id, "to": next_phase_id, "wrapped": wrapping},
    )
    cfg = await db.cycle_configs.find_one({"context_id": cid})
    return _serialise(cfg)


@router.post("/contexts/{context_id}/cycle-config/reset")
async def reset_cycle_config(
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    """Restore the 6-phase default. Hard-refuses (409) if any historical
    cycle references a non-default phase id, since restoring would orphan
    those references."""
    cid = ctx["context"]["id"]
    history_non_default = await db.cycle_history.count_documents({
        "context_id": cid,
        "phases.id": {"$nin": list(DEFAULT_PHASE_IDS)},
    })
    if history_non_default > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reset: {history_non_default} historical cycle(s) reference custom phases.",
        )
    update = {
        "phases": [dict(p) for p in DEFAULT_PHASES],
        "current_phase_id": DEFAULT_FIRST_PHASE_ID,
        "cycle_started_at": iso(now()),
        "updated_at": iso(now()),
        "schema_version": CYCLE_CONFIG_SCHEMA_VERSION,
    }
    await db.cycle_configs.update_one(
        {"context_id": cid}, {"$set": update}, upsert=True,
    )
    await write_audit(
        cid, ctx["account"]["id"], "cycle_config.reset", "cycle_config", cid, {},
    )
    cfg = await db.cycle_configs.find_one({"context_id": cid})
    return _serialise(cfg)


@router.get("/contexts/{context_id}/cycle-config/phases/{phase_id}/summary")
async def phase_summary(
    phase_id: str,
    cycle_offset: int = 0,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Artefact roll-up for a phase. v1 only supports cycle_offset=0
    (the current cycle); historical cycles return the placeholder shape."""
    cid = ctx["context"]["id"]
    cfg = await _load_or_create_default(cid)

    phase = next((p for p in cfg["phases"] if p["id"] == phase_id), None)
    if not phase:
        raise HTTPException(status_code=404, detail=f"Phase '{phase_id}' not in this context's config.")

    if cycle_offset != 0:
        return {
            "phase_id": phase_id,
            "phase_name": phase["name"],
            "cycle_offset": 0,
            "error": "Historical cycles not yet available.",
        }

    window = _phase_window(cfg, phase_id) or {"start": cfg.get("cycle_started_at"), "end": iso(now())}

    artefacts: Dict[str, Any] = {}
    queries = PHASE_QUERY_MAP.get(phase_id, [])
    for q in queries:
        coll = getattr(db, q["collection"])
        time_field = q["time"]
        match: Dict[str, Any] = {
            "context_id": cid,
            time_field: {"$gte": window["start"], "$lt": window["end"]},
        }
        match.update(q.get("filter", {}))
        try:
            count = await coll.count_documents(match)
        except Exception:  # noqa: BLE001
            count = 0
        try:
            recent_docs = await coll.find(match, q["fields"]).sort(time_field, -1).limit(5).to_list(5)
        except Exception:  # noqa: BLE001
            recent_docs = []
        # Strip any leaked _id (defensive — projection should already exclude it).
        for r in recent_docs:
            r.pop("_id", None)
        artefacts[q["key"]] = {"count": count, "recent": recent_docs}

    return {
        "phase_id": phase_id,
        "phase_name": phase["name"],
        "cycle_started_at": cfg.get("cycle_started_at"),
        "phase_window": window,
        "cycle_offset": 0,
        "artefacts": artefacts,
    }
