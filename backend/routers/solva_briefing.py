"""Solva briefing-deck state — Phase D.1 (2026-05-26).

Per-(user, area) state for the pre-conversation 4-slide briefing deck.

Collection: `solva_briefing_state`. Shape (one row per user × area):
    {
      "user_id": str,
      "area":    str,    # one of SOLVA_AREAS (see frontend canonical list)
      "visit_count": int,
      "suppressed": bool,
      "suppressed_at": ISO8601 str | None,
      "updated_at": ISO8601 str,
    }

Endpoints:
    GET  /api/solva/briefing/state?area={area}
    POST /api/solva/briefing/state          body: {area, action}

Where `action` is one of:
    - "increment"  — bump visit_count by 1. Used on deck OPEN. Idempotent
                     only in that re-opening the deck always increments;
                     callers must call this exactly once per deck open.
    - "suppress"   — set suppressed=True + stamp suppressed_at.
    - "unsuppress" — clear suppression (used by the `(i)` reopen path
                     if a future feature wants to also clear; not used
                     in current frontend but kept for completeness).

Area names match the verbatim slugs in
`frontend/src/data/solva-briefings.js`:
    seek-clarity, test-hypothesis, develop-strategy, different-perspective

Note: the SUBMODULE name the rest of Solva uses is different (see
HOME_CLEANUP_LOG.md "D.2 — Solva question-logic audit" for the mapping).
This router stores the FRONTEND area slug verbatim so the
briefing-deck UX is decoupled from the backend submodule rename.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, get_current_account

router = APIRouter(prefix="/api/solva/briefing", tags=["solva_briefing"])

# Allowed area slugs — match frontend SOLVA_AREAS keys verbatim.
_ALLOWED_AREAS = frozenset({
    "seek-clarity",
    "test-hypothesis",
    "develop-strategy",
    "different-perspective",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_area(area: str) -> str:
    if area not in _ALLOWED_AREAS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown area '{area}' — must be one of {sorted(_ALLOWED_AREAS)}",
        )
    return area


@router.get("/state")
async def get_state(
    area: str = Query(...),
    me=Depends(get_current_account),
):
    """Return current visit_count + suppressed for (user, area).

    Side-effect-free; safe to call on every deck render."""
    area = _validate_area(area)
    doc = await db.solva_briefing_state.find_one(
        {"user_id": me["id"], "area": area},
        {"_id": 0, "visit_count": 1, "suppressed": 1, "suppressed_at": 1},
    )
    if not doc:
        return {
            "area": area,
            "visit_count": 0,
            "suppressed": False,
            "suppressed_at": None,
        }
    return {
        "area": area,
        "visit_count": int(doc.get("visit_count") or 0),
        "suppressed": bool(doc.get("suppressed") or False),
        "suppressed_at": doc.get("suppressed_at"),
    }


class _PostBody(BaseModel):
    area: str = Field(...)
    action: Literal["increment", "suppress", "unsuppress"] = Field(...)


@router.post("/state")
async def mutate_state(
    body: _PostBody,
    me=Depends(get_current_account),
):
    """Mutate (user, area) state. Idempotent within a single deck open
    only for `suppress` / `unsuppress`; `increment` always bumps.

    Returns the post-mutation snapshot in the same shape as
    GET /state so the frontend can short-circuit without re-fetching."""
    area = _validate_area(body.area)
    now = _now_iso()

    if body.action == "increment":
        await db.solva_briefing_state.update_one(
            {"user_id": me["id"], "area": area},
            {
                "$inc": {"visit_count": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "user_id": me["id"],
                    "area": area,
                    "suppressed": False,
                    "suppressed_at": None,
                },
            },
            upsert=True,
        )
    elif body.action == "suppress":
        await db.solva_briefing_state.update_one(
            {"user_id": me["id"], "area": area},
            {
                "$set": {
                    "suppressed": True,
                    "suppressed_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": me["id"],
                    "area": area,
                    "visit_count": 0,
                },
            },
            upsert=True,
        )
    else:  # unsuppress
        await db.solva_briefing_state.update_one(
            {"user_id": me["id"], "area": area},
            {
                "$set": {
                    "suppressed": False,
                    "suppressed_at": None,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": me["id"],
                    "area": area,
                    "visit_count": 0,
                },
            },
            upsert=True,
        )

    # Return current state.
    doc = await db.solva_briefing_state.find_one(
        {"user_id": me["id"], "area": area},
        {"_id": 0, "visit_count": 1, "suppressed": 1, "suppressed_at": 1},
    )
    return {
        "area": area,
        "visit_count": int(doc.get("visit_count") or 0),
        "suppressed": bool(doc.get("suppressed") or False),
        "suppressed_at": doc.get("suppressed_at"),
    }
