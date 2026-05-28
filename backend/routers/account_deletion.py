"""Phase X (2026-02 fork-resume) — Self-service account deletion.

GDPR-class flow with 30-day soft-delete grace window.

Lifecycle:
    active                  → POST /api/me/delete-account
    pending_deletion        → POST /api/me/delete-account/cancel
                                (or auto hard-delete after 30d via
                                 POST /api/admin/users/process-deletions)

States added to `accounts.status`:
    "pending_deletion"  — user requested deletion; still able to log in
                          and cancel during the grace window.

New `accounts` fields stamped on request:
    deletion_requested_at   — ISO timestamp
    deletion_scheduled_for  — ISO timestamp 30 days in the future

Cascading hard-delete (admin-driven) wipes the account plus:
    memberships, cycle_questions, recent_views, feature_events,
    cohort_invites, cohort_special_asks, contexts owned by this account,
    documents/tasks/objectives/projects scoped to those contexts.

Out of scope (filed as Phase X.followup.1):
    - Per-user data export before delete
    - Legal-hold override
    - Undo after grace expiry
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import db, get_current_account


log = logging.getLogger(__name__)


GRACE_DAYS = 30  # locked product decision

# Cascade target collections — touched in process_deletion. Order is
# safest leaves-first to minimise dangling references at any
# midpoint failure.
_OWNED_BY_ACCOUNT_COLLECTIONS = (
    "memberships",
    "cycle_questions",
    "recent_views",
    "feature_events",
    "cohort_invites",
    "cohort_special_asks",
    "user_calendar_credentials",
    "revoked_jtis",
)

# Collections whose rows reference `context_id` — wiped when the
# owner_account_id's contexts are wiped.
_OWNED_BY_CONTEXT_COLLECTIONS = (
    "documents",
    "tasks_initiatives",
    "objectives",
    "projects",
    "signals",
    "events",
    "extractions_log",
)


router = APIRouter(prefix="/api", tags=["account-deletion"])


# ─────────────────────────────────────────────────────────────────
# Helpers (also used by tests)
# ─────────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _schedule_deletion(account_id: str) -> Dict[str, str]:
    """Stamp the soft-delete fields. Idempotent — re-running keeps
    the originally-stamped schedule (so the user can't postpone by
    re-submitting). Returns the stamped timestamps."""
    existing = await db.accounts.find_one(
        {"id": account_id}, {"_id": 0, "status": 1, "deletion_scheduled_for": 1, "deletion_requested_at": 1},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Account not found.")
    if existing.get("status") == "pending_deletion" and existing.get("deletion_scheduled_for"):
        # Already scheduled — return the existing schedule unchanged.
        return {
            "deletion_requested_at":   existing["deletion_requested_at"],
            "deletion_scheduled_for":  existing["deletion_scheduled_for"],
        }
    now = _now_utc()
    sched = now + timedelta(days=GRACE_DAYS)
    requested_iso = _iso(now)
    scheduled_iso = _iso(sched)
    await db.accounts.update_one(
        {"id": account_id},
        {"$set": {
            "status":                  "pending_deletion",
            "deletion_requested_at":   requested_iso,
            "deletion_scheduled_for":  scheduled_iso,
        }},
    )
    return {
        "deletion_requested_at":  requested_iso,
        "deletion_scheduled_for": scheduled_iso,
    }


async def _cancel_deletion(account_id: str) -> Dict[str, Any]:
    res = await db.accounts.update_one(
        {"id": account_id, "status": "pending_deletion"},
        {"$set":   {"status": "active"},
         "$unset": {"deletion_requested_at": "", "deletion_scheduled_for": ""}},
    )
    if res.modified_count == 0:
        # Either not pending, or no row.
        existing = await db.accounts.find_one({"id": account_id}, {"_id": 0, "status": 1})
        if not existing:
            raise HTTPException(status_code=404, detail="Account not found.")
        raise HTTPException(status_code=400, detail="Account is not pending deletion.")
    return {"ok": True}


async def _cascade_hard_delete(account_id: str) -> Dict[str, int]:
    """Wipe the account row + every collection that references it.

    Returns a counts dict for the caller to log.
    """
    counts: Dict[str, int] = {}
    # Step 1 — find contexts OWNED by this account so we can wipe
    # their data too.
    owned_ctx_cursor = db.contexts.find({"owner_account_id": account_id}, {"_id": 0, "id": 1})
    owned_ctx_ids: List[str] = [r["id"] async for r in owned_ctx_cursor]
    counts["owned_contexts"] = len(owned_ctx_ids)

    # Step 2 — wipe context-scoped data for those owned contexts.
    if owned_ctx_ids:
        for coll in _OWNED_BY_CONTEXT_COLLECTIONS:
            r = await db[coll].delete_many({"context_id": {"$in": owned_ctx_ids}})
            counts[f"{coll}_by_owned_ctx"] = r.deleted_count
        # Wipe ALL memberships of the owned contexts (other members
        # lose access since the org no longer exists).
        r_mem = await db.memberships.delete_many({"context_id": {"$in": owned_ctx_ids}})
        counts["memberships_by_owned_ctx"] = r_mem.deleted_count
        # Wipe the contexts themselves.
        r = await db.contexts.delete_many({"id": {"$in": owned_ctx_ids}})
        counts["contexts"] = r.deleted_count

    # Step 3 — wipe account-scoped collections.
    for coll in _OWNED_BY_ACCOUNT_COLLECTIONS:
        if coll == "memberships":
            r = await db.memberships.delete_many({"account_id": account_id})
        elif coll in ("feature_events", "recent_views"):
            r = await db[coll].delete_many({"account_id": account_id})
        elif coll == "cohort_invites":
            r = await db.cohort_invites.delete_many({"consumed_by_account_id": account_id})
        elif coll == "cohort_special_asks":
            r = await db.cohort_special_asks.delete_many({"account_id": account_id})
        elif coll == "user_calendar_credentials":
            r = await db.user_calendar_credentials.delete_many({"user_id": account_id})
        elif coll == "revoked_jtis":
            r = await db.revoked_jtis.delete_many({"account_id": account_id})
        else:
            r = await db[coll].delete_many({"account_id": account_id})
        counts[coll] = r.deleted_count

    # Step 4 — wipe the account row last.
    r = await db.accounts.delete_one({"id": account_id})
    counts["account"] = r.deleted_count
    return counts


# ─────────────────────────────────────────────────────────────────
# Self-service endpoints
# ─────────────────────────────────────────────────────────────────


class DeleteAccountRequest(BaseModel):
    confirm: str  # must equal user's email — defensive against accidental clicks


@router.post("/me/delete-account")
async def request_account_deletion(
    body: DeleteAccountRequest,
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Request soft-delete with a 30-day grace window.

    The caller MUST submit their own email in `confirm` — defensive
    second-step to prevent muscle-memory mis-clicks. The endpoint
    returns the scheduled hard-delete timestamp so the UI can
    display the cooling-off period.
    """
    if (body.confirm or "").strip().lower() != (account.get("email") or "").strip().lower():
        raise HTTPException(status_code=400, detail="confirm must equal your email.")
    if account.get("is_superadmin"):
        # Defensive — last-superadmin lockout. If the founder needs
        # to delete their own account, they downgrade themselves first.
        raise HTTPException(
            status_code=400,
            detail="Superadmin accounts cannot self-delete. Downgrade first.",
        )
    sched = await _schedule_deletion(account["id"])
    return {
        "ok": True,
        "status": "pending_deletion",
        "grace_days": GRACE_DAYS,
        **sched,
    }


@router.post("/me/delete-account/cancel")
async def cancel_account_deletion(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Cancel a pending soft-delete. 400 if the account isn't
    pending deletion (idempotent caller protection)."""
    return await _cancel_deletion(account["id"])


# ─────────────────────────────────────────────────────────────────
# Admin endpoint — process expired soft-deletes
# ─────────────────────────────────────────────────────────────────


@router.post("/admin/users/process-deletions")
async def process_pending_deletions(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Hard-delete every account whose `deletion_scheduled_for` is in
    the past. Returns per-account cascade counts. Superadmin-only."""
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required.")
    now_iso = _iso(_now_utc())
    cursor = db.accounts.find(
        {
            "status": "pending_deletion",
            "deletion_scheduled_for": {"$lte": now_iso},
        },
        {"_id": 0, "id": 1, "email": 1},
    )
    targets = [r async for r in cursor]
    results: List[Dict[str, Any]] = []
    for t in targets:
        try:
            counts = await _cascade_hard_delete(t["id"])
            results.append({"account_id": t["id"], "email": t.get("email"), "counts": counts})
        except Exception as e:  # pragma: no cover
            log.exception("[phase-x] failed to hard-delete %s: %s", t.get("id"), e)
            results.append({"account_id": t["id"], "email": t.get("email"), "error": str(e)})
    return {"ok": True, "processed": len(targets), "results": results}
