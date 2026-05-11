"""Cycle lifecycle helpers — shared between routers/cycles.py and the
write-guard used by routers/cycle_manager.py.

The `cycles` collection is the new master after the multi-cycle pivot.
Existing cycle-scoped collections (`cycle_agendas`, `cycle_team`,
`cycle_contributions`, `cycle_followups`) carry `cycle_id` = the
`cycles.id`. The migration in `migrations/0001_multi_cycle.py` backfills
existing rows so the legacy single-cycle data appears as one Active
cycle.

Status lifecycle: draft → active → completed.
  • Draft     — created by user, not yet visible to contributors.
  • Active    — visible to contributors, mutable, counts toward stats.
  • Completed — read-only. Only compilation re-download is permitted.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core import db


CYCLE_STATUSES: Tuple[str, ...] = ("draft", "active", "completed")


async def get_cycle_or_404(context_id: str, cycle_id: str) -> Dict[str, Any]:
    row = await db.cycles.find_one(
        {"id": cycle_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cycle not found.")
    return row


async def require_cycle_writable(
    context_id: str, cycle_id: str,
) -> Optional[Dict[str, Any]]:
    """Reject mutations on completed cycles with 409. Returns the cycle
    row so the caller can reuse it. Returns None silently if no cycle
    row exists yet (legacy/pre-migration data path)."""
    cycle = await db.cycles.find_one(
        {"id": cycle_id, "context_id": context_id},
        {"_id": 0},
    )
    if not cycle:
        return None
    if (cycle.get("status") or "draft") == "completed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "cycle_completed",
                "message": (
                    "This cycle is closed and read-only. Re-open by creating "
                    "a new cycle. Compilation re-download remains available "
                    "from the Compilation tab."
                ),
            },
        )
    return cycle


async def resolve_implicit_cycle_id(
    context_id: str, supplied_cycle_id: Optional[str] = None,
) -> Optional[str]:
    """Legacy-compat resolver for the singleton `/cycle/*` endpoints.

    Rules:
      • If caller supplied a cycle_id → validate it belongs to context.
      • Else if exactly one active cycle exists → use it.
      • Else if no cycles exist → return None (the caller's
        `_get_or_init_agenda` path auto-creates).
      • Else (multiple cycles, none supplied) → 400.

    NOTE: Draft cycles are NOT auto-resolved because users may have
    several Drafts in flight; ambiguity must be resolved by the caller.
    """
    if supplied_cycle_id:
        cycle = await db.cycles.find_one(
            {"id": supplied_cycle_id, "context_id": context_id},
            {"_id": 0, "id": 1, "status": 1},
        )
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found.")
        return supplied_cycle_id

    active_cursor = db.cycles.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1},
    ).limit(2)
    actives = await active_cursor.to_list(2)
    if len(actives) == 1:
        return actives[0]["id"]
    if len(actives) == 0:
        return None
    raise HTTPException(
        status_code=400,
        detail={
            "code": "cycle_id_required",
            "message": (
                "This context has multiple active cycles. Pass "
                "?cycle_id=… on the request to disambiguate."
            ),
        },
    )


async def compute_cycle_counts(cycle_id: str) -> Dict[str, int]:
    """Cheap rollup used on cycle list cards."""
    agenda = await db.cycle_agendas.find_one(
        {"id": cycle_id}, {"_id": 0, "items": 1},
    )
    agenda_count = len((agenda or {}).get("items") or [])
    contributor_count = await db.cycle_team.count_documents({
        "agenda_id": cycle_id, "status": "active",
    })
    return {
        "agenda_count": int(agenda_count),
        "contributor_count": int(contributor_count),
    }


async def compute_readiness_score(cycle_id: str) -> Optional[int]:
    """Average of contribution readiness scores 0..100 for the cycle.
    Returns None if no contributions are scored yet (so the card can
    render 'Not yet scored')."""
    contribs = await db.cycle_contributions.find(
        {"agenda_id": cycle_id, "scores.readiness": {"$exists": True}},
        {"_id": 0, "scores": 1},
    ).to_list(500)
    vals: List[int] = []
    for c in contribs:
        v = (c.get("scores") or {}).get("readiness")
        if isinstance(v, (int, float)):
            vals.append(int(v))
    if not vals:
        return None
    return int(round(sum(vals) / len(vals)))
