"""Quick Action telemetry — Cycle Manager Feel pass (Patch 2 of 4).

Surfaces:
  POST /api/contexts/{cid}/quick-actions/{action_key}/clicked
  GET  /api/contexts/{cid}/quick-actions/order

The four canonical action keys (and stable default order, used as the
tiebreaker for never-clicked actions):

  1. main_board
  2. answer_questions
  3. project_proposal
  4. fund_raising

Storage: `db.quick_action_usage` — one row per
(context_id, account_id, action_key). Per-account counts.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import db, get_current_account, iso, now, require_context_membership

logger = logging.getLogger("akki.quick_actions")

router = APIRouter(prefix="/api")


CANONICAL_ACTION_KEYS: tuple = (
    "main_board",
    "answer_questions",
    "project_proposal",
    "fund_raising",
)


class QuickActionOrderOut(BaseModel):
    order: List[str]
    canonical: List[str]


def _validate_key(key: str) -> str:
    if key not in CANONICAL_ACTION_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown quick action key. Allowed: {', '.join(CANONICAL_ACTION_KEYS)}.",
        )
    return key


@router.post(
    "/contexts/{context_id}/quick-actions/{action_key}/clicked",
    status_code=200,
)
async def record_quick_action_click(
    context_id: str,
    action_key: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Increment click count for (context, account, action_key)."""
    key = _validate_key(action_key)
    now_iso = iso(now())
    res = await db.quick_action_usage.find_one_and_update(
        {
            "context_id": context_id,
            "account_id": ctx["account"]["id"],
            "action_key": key,
        },
        {
            "$inc": {"click_count": 1},
            "$set": {"last_used_at": now_iso},
            "$setOnInsert": {
                "context_id": context_id,
                "account_id": ctx["account"]["id"],
                "action_key": key,
                "created_at": now_iso,
            },
        },
        upsert=True,
        return_document=True,
    )
    return {
        "action_key": key,
        "click_count": (res or {}).get("click_count") or 1,
        "last_used_at": now_iso,
    }


@router.get(
    "/contexts/{context_id}/quick-actions/order",
    response_model=QuickActionOrderOut,
)
async def get_quick_action_order(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return the 4 canonical action keys ordered by per-account click
    count DESC, then last_used_at DESC, with the canonical default
    order as the stable tiebreaker for never-clicked keys."""
    rows = await db.quick_action_usage.find(
        {
            "context_id": context_id,
            "account_id": ctx["account"]["id"],
            "action_key": {"$in": list(CANONICAL_ACTION_KEYS)},
        },
        {"_id": 0, "action_key": 1, "click_count": 1, "last_used_at": 1},
    ).to_list(20)

    rank = {r["action_key"]: r for r in rows}
    default_rank = {k: i for i, k in enumerate(CANONICAL_ACTION_KEYS)}
    keys = list(CANONICAL_ACTION_KEYS)
    keys.sort(key=lambda k: (
        -(rank.get(k, {}).get("click_count") or 0),
        -(_iso_sort_key(rank.get(k, {}).get("last_used_at"))),
        default_rank[k],
    ))
    return QuickActionOrderOut(order=keys, canonical=list(CANONICAL_ACTION_KEYS))


def _iso_sort_key(iso_ts: str | None) -> int:
    """Convert ISO timestamp to a sortable integer (epoch microseconds).
    None → 0 (sorts last when used with descending negation)."""
    if not iso_ts:
        return 0
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).timestamp() * 1_000_000)
    except Exception:  # noqa: BLE001
        return 0
