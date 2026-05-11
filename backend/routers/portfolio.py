"""Portfolio state endpoint (HOME sprint, 2026-05-12).

`GET /api/me/portfolio` — one row per active membership the calling
account holds, hydrated with role + cycle state + at-risk-goal count +
pending-followup count + unread-signals count + last activity.

Privacy Wall: every state query is filtered by exactly one
`context_id`. There is no cross-context aggregation in this endpoint.

Caching: an in-memory dict, keyed by `(account_id, context_id)`, holds
the per-row payload for 30 seconds. The cache is process-local — fine
for a single backend pod; if we scale out we'll move to Redis. The
30-second TTL is short enough that "stale state" is never confusing for
the user (they'd refresh anyway).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from core import db, get_current_account

logger = logging.getLogger("akki.portfolio")
router = APIRouter(prefix="/api")

# In-memory TTL cache. Key: (account_id, context_id). Value: (payload, expires_at).
_PORTFOLIO_CACHE: Dict[str, Dict[str, Any]] = {}
_TTL_SECONDS = 30.0


def _cache_key(account_id: str, context_id: str) -> str:
    return f"{account_id}::{context_id}"


def _cache_get(account_id: str, context_id: str) -> Optional[Dict[str, Any]]:
    row = _PORTFOLIO_CACHE.get(_cache_key(account_id, context_id))
    if row and row["expires_at"] > time.time():
        return row["payload"]
    return None


def _cache_put(account_id: str, context_id: str, payload: Dict[str, Any]) -> None:
    _PORTFOLIO_CACHE[_cache_key(account_id, context_id)] = {
        "payload": payload,
        "expires_at": time.time() + _TTL_SECONDS,
    }


# ─── State helpers ─────────────────────────────────────────────────────
async def _cycle_state(context_id: str) -> Dict[str, Any]:
    """Read latest active row from `db.cycle_agendas` and derive a tiny
    state dict the Home cards can render directly. Falls through to
    `no_cycle` if nothing is active."""
    agenda = await db.cycle_agendas.find_one(
        {"context_id": context_id, "status": "active"},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    if not agenda:
        return {"status": "no_cycle", "ship_in_days": None, "act_label": "Setup"}

    # Derive position in the four-stage cycle (setup → team → contributions →
    # scoring → followups → ship). We use the existence of related rows as the
    # signal, not a single state field — robust to schema drift.
    has_team = bool(await db.cycle_team_members.find_one({"context_id": context_id}))
    has_contribs = bool(await db.cycle_contributions.find_one({"context_id": context_id}))
    has_scored = bool(
        await db.cycle_contributions.find_one(
            {"context_id": context_id, "scores": {"$ne": None}}
        )
    )
    pending_followups = await db.cycle_followups.count_documents(
        {"context_id": context_id, "status": "pending"}
    )

    # Stage labelling, calm-fast voice.
    if not has_team:
        return {"status": "setup", "ship_in_days": None, "act_label": "Build team"}
    if not has_contribs:
        return {"status": "run", "ship_in_days": None, "act_label": "Gather contributions"}
    if not has_scored:
        return {"status": "run", "ship_in_days": None, "act_label": "Score readiness"}
    if pending_followups > 0:
        return {"status": "run", "ship_in_days": None, "act_label": f"Approve {pending_followups} follow-up{'s' if pending_followups != 1 else ''}"}
    return {"status": "ship", "ship_in_days": None, "act_label": "Compile pack"}


async def _goals_at_risk_count(context_id: str) -> int:
    return await db.signals.count_documents(
        {
            "context_id": context_id,
            "category": "goal_risk",
            "confidence": {"$gt": 0.6},
            "state": {"$ne": "archived"},
        }
    )


async def _pending_followups_count(context_id: str) -> int:
    return await db.cycle_followups.count_documents(
        {"context_id": context_id, "status": "pending"}
    )


async def _unread_signals_count(context_id: str) -> int:
    # Active signals not yet bookmarked or resolved.
    return await db.signals.count_documents(
        {
            "context_id": context_id,
            "$or": [
                {"state": "active"},
                {"state": {"$exists": False}, "status": {"$in": ["active", None]}},
            ],
        }
    )


async def _last_active_at(context_id: str, account_id: str) -> Optional[str]:
    candidates: List[Optional[str]] = []
    chat_msg = await db.chat_messages.find_one(
        {"context_id": context_id, "account_id": account_id},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)],
    )
    if chat_msg and chat_msg.get("created_at"):
        candidates.append(chat_msg["created_at"])
    solva_sess = await db.solva_v2_sessions.find_one(
        {"context_id": context_id, "account_id": account_id},
        {"_id": 0, "updated_at": 1, "created_at": 1},
        sort=[("updated_at", -1)],
    )
    if solva_sess:
        candidates.append(solva_sess.get("updated_at") or solva_sess.get("created_at"))
    cycle_contrib = await db.cycle_contributions.find_one(
        {"context_id": context_id, "created_by_account_id": account_id},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)],
    )
    if cycle_contrib and cycle_contrib.get("created_at"):
        candidates.append(cycle_contrib["created_at"])
    valid = [c for c in candidates if c]
    return max(valid) if valid else None


async def _exco_membership_summary(context_id: str, account_id: str) -> Dict[str, Any]:
    """Tells the home card whether this account belongs to any active
    ExCo team in this context (for the role kicker append rule)."""
    teams = await db.exco_teams.find(
        {
            "context_id": context_id,
            "status": "active",
            "member_account_ids": account_id,
        },
        {"_id": 0, "id": 1, "name": 1},
    ).to_list(length=8)
    return {"team_count": len(teams), "team_names": [t["name"] for t in teams]}


# ─── Route ─────────────────────────────────────────────────────────────
@router.get("/me/portfolio")
async def me_portfolio(current: Dict[str, Any] = Depends(get_current_account)):
    """One row per active membership the calling account holds."""
    account_id = current["id"]
    memberships = await db.memberships.find(
        {"account_id": account_id, "status": "active"},
        {"_id": 0},
    ).to_list(length=64)
    if not memberships:
        return {"items": []}

    context_ids = [m["context_id"] for m in memberships]
    contexts = await db.contexts.find(
        {"id": {"$in": context_ids}}, {"_id": 0, "id": 1, "name": 1}
    ).to_list(length=len(context_ids))
    ctx_by_id = {c["id"]: c for c in contexts}

    items: List[Dict[str, Any]] = []
    for m in memberships:
        cid = m["context_id"]
        ctx = ctx_by_id.get(cid)
        if not ctx:
            continue
        cached = _cache_get(account_id, cid)
        if cached:
            items.append(
                {
                    **cached,
                    # role/sub-role come from the membership row, never cached.
                    "role": m.get("role"),
                    "sub_role": m.get("sub_role"),
                }
            )
            continue
        state = {
            "cycle": await _cycle_state(cid),
            "goals_at_risk_count": await _goals_at_risk_count(cid),
            "pending_followups_count": await _pending_followups_count(cid),
            "unread_signals_count": await _unread_signals_count(cid),
            "last_active_at": await _last_active_at(cid, account_id),
            "exco": await _exco_membership_summary(cid, account_id),
        }
        payload = {
            "context_id": cid,
            "context_name": ctx.get("name", "Untitled"),
            "state": state,
        }
        _cache_put(account_id, cid, payload)
        items.append(
            {
                **payload,
                "role": m.get("role"),
                "sub_role": m.get("sub_role"),
            }
        )
    return {"items": items}
