"""Admin · Auth events panel.

Iter61 follow-up to the iter59/60 sandbox cookie-poisoning bug.
That bug existed in plain sight for a full release because the auth
dependency had no observability. This module adds:

  1. A lightweight middleware (auth_observability.py — sibling) that
     samples auth attempts at AKKI_AUTH_OBSERVE_RATE (default 0.01) and
     writes one row per sampled attempt to the `auth_events` collection.
  2. This admin endpoint that surfaces the rolled-up signals so ops can
     spot rising 401 rates BEFORE a user reports them.

Read-only. Superadmin-only. Same pattern as /admin/llm/spend.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account

router = APIRouter(prefix="/api/admin/auth", tags=["admin", "auth"])


async def _require_superadmin(account: Dict[str, Any] = Depends(get_current_account)) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return account


@router.get("/events")
async def auth_events(
    hours: int = Query(24, ge=1, le=720),
    account: Dict[str, Any] = Depends(_require_superadmin),
):
    """Roll up auth events from the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    rows = await db.auth_events.find(
        {"at": {"$gte": cutoff_iso}},
        {"_id": 0},
    ).sort("at", -1).to_list(length=10000)

    total = len(rows)
    success = sum(1 for r in rows if r.get("ok"))
    failure = total - success

    by_reason: Dict[str, int] = {}
    by_credential: Dict[str, int] = {}
    by_path: Dict[str, int] = {}
    dual_present = 0
    dual_mismatch = 0

    for r in rows:
        if not r.get("ok"):
            reason = r.get("reason") or "unknown"
            by_reason[reason] = by_reason.get(reason, 0) + 1
        creds = r.get("credentials") or []
        cred_key = "+".join(sorted(creds)) if creds else "none"
        by_credential[cred_key] = by_credential.get(cred_key, 0) + 1
        if len(creds) >= 2:
            dual_present += 1
            if r.get("dual_mismatch"):
                dual_mismatch += 1
        path = r.get("path") or "unknown"
        by_path[path] = by_path.get(path, 0) + 1

    return {
        "window_hours": hours,
        "sampled_events": total,
        "success": success,
        "failure": failure,
        "failure_rate_pct": round((failure / total) * 100, 1) if total else 0,
        "by_failure_reason": sorted(
            [{"reason": k, "count": v} for k, v in by_reason.items()],
            key=lambda x: x["count"], reverse=True,
        ),
        "by_credential": sorted(
            [{"credential": k, "count": v} for k, v in by_credential.items()],
            key=lambda x: x["count"], reverse=True,
        ),
        "top_paths": sorted(
            [{"path": k, "count": v} for k, v in by_path.items()],
            key=lambda x: x["count"], reverse=True,
        )[:20],
        "dual_credentials_seen": dual_present,
        "dual_credentials_mismatched": dual_mismatch,
        "recent": rows[:50],
    }



# Phase J (2026-05-27) — Admin kill-switch for stolen-credential scenarios.
# Marks the account so EVERY active access token issued before `now` is
# rejected by `get_current_account`. Implemented via a wildcard JTI row
# rather than enumerating individual JTIs (we don't track per-account JTI
# lists; the access-token TTL of 8h means the user's session will fully
# clear within that window even without intervention).
@router.post("/revoke-all/{account_id}")
async def revoke_all_sessions(
    account_id: str,
    actor: Dict[str, Any] = Depends(_require_superadmin),
):
    """Admin kill-switch — bumps `accounts.{id}.sessions_revoked_after`
    to now(). Tokens with `iat < sessions_revoked_after` are rejected.
    This is broader than the per-JTI blocklist but simpler — useful for
    "this user reports their account was compromised, kill everything"
    scenarios."""
    target = await db.accounts.find_one({"id": account_id}, {"_id": 0, "id": 1, "email": 1})
    if not target:
        raise HTTPException(status_code=404, detail="Account not found")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.accounts.update_one(
        {"id": account_id},
        {"$set": {"sessions_revoked_after": now_iso}},
    )
    return {
        "ok": True,
        "account_id": account_id,
        "email": target.get("email"),
        "revoked_at": now_iso,
        "actor_id": actor["id"],
    }
