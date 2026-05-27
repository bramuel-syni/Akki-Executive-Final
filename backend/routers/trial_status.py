"""Phase R.5.a (2026-05-27) — Trial-status read endpoint + early-access opt-in.

Surfaces the trial-day + trial-status the cohort console + frontend
day-counter banner / hard-lock router need:

  GET  /api/me/trial-status          — { trial_day, trial_status, trial_end_at,
                                          cohort_tag, locked: bool }
  POST /api/me/early-access-opt-in   — request to convert from cohort trial
                                          to early-access paid plan. The hard-locked
                                          frontend `/app/early-access-opt-in` page
                                          POSTs here.

The frontend uses `trial_status === "expired_hard_lock"` to force the
user into the `/app/early-access-opt-in` route. All other routes
short-circuit to the same page when the flag is set.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.cohort.console import (
    _compute_trial_status, TRIAL_SOFT_WARNING_DAY, TRIAL_HARD_LOCK_DAY,
    TRIAL_TOTAL_DAYS,
)


log = logging.getLogger("akki.cohort.trial_status")
router = APIRouter(prefix="/api/me", tags=["trial_status"])


# ─────────────────────────────────────────────────────────────────────
# GET /api/me/trial-status
# ─────────────────────────────────────────────────────────────────────
@router.get("/trial-status")
async def get_my_trial_status(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    trial_start_at = account.get("trial_start_at")
    trial_end_at   = account.get("trial_end_at")
    trial_status, day = _compute_trial_status(trial_start_at=trial_start_at)
    locked = (trial_status == "expired_hard_lock")
    return {
        "trial_day":            day,
        "trial_total_days":     TRIAL_TOTAL_DAYS,
        "trial_status":         trial_status,
        "trial_start_at":       trial_start_at,
        "trial_end_at":         trial_end_at,
        "cohort_tag":           account.get("cohort_tag"),
        "soft_warning_at_day":  TRIAL_SOFT_WARNING_DAY,
        "hard_lock_at_day":     TRIAL_HARD_LOCK_DAY,
        "locked":               locked,
    }


# ─────────────────────────────────────────────────────────────────────
# POST /api/me/early-access-opt-in
# ─────────────────────────────────────────────────────────────────────
class EarlyAccessIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=1000)


@router.post("/early-access-opt-in")
async def post_early_access_opt_in(
    body: EarlyAccessIn,
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Record the user's early-access opt-in request. Idempotent —
    a second submission updates `note` + `updated_at` but keeps the
    original `requested_at`. This is the ONLY endpoint a hard-locked
    user can hit (besides auth + this status read) until the founder
    converts them via the cohort console."""
    now_iso = datetime.now(timezone.utc).isoformat()
    existing = await db.early_access_optins.find_one(
        {"account_id": account["id"]}, {"_id": 0},
    )
    if existing:
        await db.early_access_optins.update_one(
            {"account_id": account["id"]},
            {"$set": {
                "note":       body.note,
                "updated_at": now_iso,
            }},
        )
        return {
            "ok": True, "status": "updated",
            "requested_at": existing.get("requested_at"),
            "updated_at": now_iso,
        }
    rec = {
        "id":            uuid.uuid4().hex,
        "account_id":    account["id"],
        "email":         account.get("email"),
        "cohort_tag":    account.get("cohort_tag"),
        "trial_start_at": account.get("trial_start_at"),
        "note":          body.note,
        "requested_at":  now_iso,
        "updated_at":    now_iso,
    }
    await db.early_access_optins.insert_one(rec)
    log.info("early_access_optin_requested: %s", {
        "account_id": account["id"], "email": account.get("email"),
        "cohort_tag": account.get("cohort_tag"),
    })
    return {"ok": True, "status": "recorded", "requested_at": now_iso}


# ─────────────────────────────────────────────────────────────────────
# Day-counter middleware-style guard — admin-helper view of any account
# (used by the cohort console drill-down)
# ─────────────────────────────────────────────────────────────────────
@router.get("/trial-status/by-account/{account_id}")
async def admin_get_trial_status(
    account_id: str,
    me: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not me.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    acct = await db.accounts.find_one({"id": account_id}, {"_id": 0})
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found.")
    trial_status, day = _compute_trial_status(trial_start_at=acct.get("trial_start_at"))
    return {
        "account_id":     account_id,
        "email":          acct.get("email"),
        "cohort_tag":     acct.get("cohort_tag"),
        "trial_day":      day,
        "trial_status":   trial_status,
        "trial_start_at": acct.get("trial_start_at"),
        "locked":         trial_status == "expired_hard_lock",
    }
