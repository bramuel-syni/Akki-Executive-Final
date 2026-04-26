"""§13 Plays — choreography over existing surfaces.

A Play is a named, staged workflow that composes existing AKKI features
(Cycle, Reports, Schedule, Monitors, Submissions, etc.) into a coherent
journey for the executive. Plays are *invitational* and *editorial* —
they hold AKKI's cadence: quiet, trust-first, pause-and-resume, no
progress bars, no checklists, no celebrations.

Slice 1 ships the Play shell + the Board Pack Play (6 stages):
    1. Setting the cycle      — wire to the existing recurring schedule
    2. Where the gaps are     — Submissions inbox view
    3. Consolidation          — composes the report from submissions
    4. Your review            — opens the existing Report editor
    5. Distribution           — sends up the existing review chain
    6. Done                   — outcome card, lingers 7 days on Home

The persisted shape of a Play instance is intentionally generic so the
shell + Stages panel + Home chip render every Play the same way; only
the per-stage front-end components differ.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    get_current_account, require_context_membership,
)

logger = logging.getLogger("akki.plays")
router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Play definitions — data, not code.
# ---------------------------------------------------------------------------
# Each stage carries an editorial transition phrase that fades in over the
# stage name when the executive arrives at it. No imperatives ("Click next!"),
# no progress strings ("Stage 2 of 6"). Just observations.

BOARD_PACK_PLAY: Dict[str, Any] = {
    "type": "board_pack",
    "name": "Board Pack Play",
    "audience": "executive",
    "outcome": "A board pack you've reviewed and committed to.",
    "trigger_hint": "Run when the next board cycle is on the horizon.",
    "stages": [
        {
            "idx": 0, "key": "setting_cycle",
            "name": "Setting the cycle",
            "transition": "Start here. Decide the cadence and who reports.",
        },
        {
            "idx": 1, "key": "gaps",
            "name": "Where the gaps are",
            "transition": "Your team's submissions are in. Time to look at what's there.",
        },
        {
            "idx": 2, "key": "consolidation",
            "name": "Consolidation",
            "transition": "AKKI is reading what your team sent.",
        },
        {
            "idx": 3, "key": "review",
            "name": "Your review",
            "transition": "The draft is yours. Edit. Accept. Or rewrite.",
        },
        {
            "idx": 4, "key": "distribution",
            "name": "Distribution",
            "transition": "Send it up the chain when you're ready.",
        },
        {
            "idx": 5, "key": "done",
            "name": "Done",
            "transition": "Committed. Distributed.",
        },
    ],
}

# Stub definitions for the remaining 5 Plays — names + audiences only so the
# library can show them as "coming soon" without code paths. We'll fill them
# in slice-by-slice.
_PLAY_STUBS = [
    ("monthly_performance", "Monthly Performance Play", "executive",
     "A read on where you stand and what deserves attention."),
    ("team_reporting", "Team Reporting Play", "executive",
     "Set a reporting rhythm with your team and watch it land."),
    ("pre_board", "Pre-Board Play", "ned",
     "Walk into the meeting having read the pack the way a chair would."),
    ("cross_board_pulse", "Cross-Board Pulse Play", "ned",
     "What AKKI is seeing across your boards, and what to do about it."),
    ("open_threads", "Open Threads Play", "ned",
     "Every loose end from the last meeting, and your follow-ups."),
]

PLAY_LIBRARY: Dict[str, Dict[str, Any]] = {
    BOARD_PACK_PLAY["type"]: BOARD_PACK_PLAY,
}
for ptype, name, aud, outcome in _PLAY_STUBS:
    PLAY_LIBRARY[ptype] = {
        "type": ptype, "name": name, "audience": aud,
        "outcome": outcome, "stages": [], "available": False,
    }
PLAY_LIBRARY[BOARD_PACK_PLAY["type"]]["available"] = True


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

PlayStatus = Literal["active", "paused", "completed", "exited"]


class StartPlayIn(BaseModel):
    play_type: str = Field(min_length=2, max_length=64)


class JumpStageIn(BaseModel):
    stage_idx: int = Field(ge=0, le=20)
    confirm: bool = Field(default=False,
                          description="Required when jumping forward past the current stage.")


class StageStateUpdate(BaseModel):
    """Generic per-stage state patch — keys are stage-specific, the shell
    doesn't care. Examples: {schedule_id}, {report_id}, {submission_count}."""
    state: Dict[str, Any]


def _public_play(p: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo internals + project the play onto the contract the shell
    consumes (definition + instance state)."""
    definition = PLAY_LIBRARY.get(p["play_type"], {})
    return {
        "id": p["id"],
        "play_type": p["play_type"],
        "name": definition.get("name", p["play_type"]),
        "audience": definition.get("audience"),
        "outcome": definition.get("outcome"),
        "stages": definition.get("stages", []),
        "status": p["status"],
        "current_stage": p["current_stage"],
        "context_id": p["context_id"],
        "state": p.get("state") or {},
        "started_at": p.get("started_at"),
        "last_activity_at": p.get("last_activity_at"),
        "completed_at": p.get("completed_at"),
    }


# ---------------------------------------------------------------------------
# Library + listing
# ---------------------------------------------------------------------------

@router.get("/plays/library")
async def list_play_library():
    """Public — the executive can browse what's available even before
    starting one."""
    return {"plays": list(PLAY_LIBRARY.values())}


@router.get("/contexts/{context_id}/plays")
async def list_plays(
    context_id: str,
    status: Optional[str] = None,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id}
    if status:
        q["status"] = status
    cursor = db.plays.find(q, {"_id": 0}).sort("last_activity_at", -1).limit(50)
    rows = await cursor.to_list(length=50)
    return {"plays": [_public_play(p) for p in rows]}


@router.get("/contexts/{context_id}/plays/{play_id}")
async def get_play(
    context_id: str, play_id: str,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    return {"play": _public_play(p)}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@router.post("/contexts/{context_id}/plays")
async def start_play(
    context_id: str,
    body: StartPlayIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    definition = PLAY_LIBRARY.get(body.play_type)
    if not definition or not definition.get("available"):
        raise HTTPException(status_code=400, detail="Play not available yet.")

    # Idempotency: if there's already an active Play of this type for this
    # (context, account), return that one instead of creating a duplicate.
    existing = await db.plays.find_one(
        {"context_id": context_id, "account_id": current["id"],
         "play_type": body.play_type, "status": {"$in": ["active", "paused"]}},
        {"_id": 0},
    )
    if existing:
        return {"play": _public_play(existing), "resumed": True}

    rec = {
        "id": str(uuid.uuid4()),
        "play_type": body.play_type,
        "context_id": context_id,
        "account_id": current["id"],
        "status": "active",
        "current_stage": 0,
        "state": {},
        "started_at": _iso(_now()),
        "last_activity_at": _iso(_now()),
        "completed_at": None,
        "events": [{"at": _iso(_now()), "kind": "started", "stage": 0}],
    }
    await db.plays.insert_one(rec.copy())
    await write_audit(context_id, current["id"], "play.started", "play",
                      rec["id"], {"play_type": body.play_type})
    return {"play": _public_play(rec), "resumed": False}


async def _patch_play(play_id: str, context_id: str, patch: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    patch.setdefault("last_activity_at", _iso(_now()))
    await db.plays.update_one(
        {"id": play_id, "context_id": context_id},
        {"$set": patch, "$push": {"events": {**event, "at": _iso(_now())}}},
    )
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    return p


@router.post("/contexts/{context_id}/plays/{play_id}/advance")
async def advance_play(
    context_id: str, play_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    if p["status"] not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="Play is not advanceable.")
    definition = PLAY_LIBRARY.get(p["play_type"], {})
    stages = definition.get("stages", [])
    nxt = p["current_stage"] + 1
    patch: Dict[str, Any] = {"current_stage": nxt, "status": "active"}
    if nxt >= len(stages) - 1:
        # Last stage = 'done'; entering it completes the Play.
        patch["status"] = "completed"
        patch["completed_at"] = _iso(_now())
    p = await _patch_play(play_id, context_id, patch,
                          {"kind": "advanced", "stage": nxt})
    return {"play": _public_play(p)}


@router.post("/contexts/{context_id}/plays/{play_id}/jump")
async def jump_to_stage(
    context_id: str, play_id: str, body: JumpStageIn,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    definition = PLAY_LIBRARY.get(p["play_type"], {})
    stages = definition.get("stages", [])
    if body.stage_idx >= len(stages):
        raise HTTPException(status_code=400, detail="Stage out of range.")
    # Trust-first: backwards jumps are free; forward jumps require explicit confirm.
    if body.stage_idx > p["current_stage"] and not body.confirm:
        raise HTTPException(
            status_code=409,
            detail="Confirm required to jump ahead of your current stage.",
        )
    p = await _patch_play(play_id, context_id, {"current_stage": body.stage_idx, "status": "active"},
                          {"kind": "jumped", "stage": body.stage_idx, "confirmed": body.confirm})
    return {"play": _public_play(p)}


@router.post("/contexts/{context_id}/plays/{play_id}/pause")
async def pause_play(
    context_id: str, play_id: str,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    p = await _patch_play(play_id, context_id, {"status": "paused"},
                          {"kind": "paused", "stage": p["current_stage"]})
    return {"play": _public_play(p)}


@router.post("/contexts/{context_id}/plays/{play_id}/resume")
async def resume_play(
    context_id: str, play_id: str,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    p = await _patch_play(play_id, context_id, {"status": "active"},
                          {"kind": "resumed", "stage": p["current_stage"]})
    return {"play": _public_play(p)}


@router.post("/contexts/{context_id}/plays/{play_id}/exit")
async def exit_play(
    context_id: str, play_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    p = await _patch_play(play_id, context_id, {"status": "exited"},
                          {"kind": "exited", "stage": p["current_stage"]})
    await write_audit(context_id, current["id"], "play.exited", "play",
                      play_id, {"stage": p["current_stage"]})
    return {"play": _public_play(p)}


@router.patch("/contexts/{context_id}/plays/{play_id}/state")
async def patch_play_state(
    context_id: str, play_id: str, body: StageStateUpdate,
    membership: Dict[str, Any] = Depends(require_context_membership()),
):
    """Per-stage front-ends use this to persist their bindings — e.g. the
    Setting-the-cycle stage stores `schedule_id`, the Consolidation stage
    stores `report_id`. The shell never inspects these; they're opaque.

    Top-level keys are shallow-merged with the existing state. Stage state
    in Slice 1 is intentionally flat (one key per binding); we'll move to a
    proper deep-merge if a future Play needs nested per-stage state.
    """
    p = await db.plays.find_one({"id": play_id, "context_id": context_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Play not found.")
    merged = {**(p.get("state") or {}), **body.state}
    p = await _patch_play(play_id, context_id, {"state": merged},
                          {"kind": "state_patched", "keys": list(body.state.keys())})
    return {"play": _public_play(p)}
