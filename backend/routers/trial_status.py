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
from services.cohort.copy_overrides import (
    get_slot_override, SLOT_FIELDS, overlay_slot,
)
from services.cohort.special_ask import (
    SPECIAL_ASK_TRIGGER_DAY,
    get_or_mint_special_ask,
    get_special_ask,
    save_special_ask,
)
from services.cohort.feature_events import (
    emit_feature_event,
)


# Phase R.5.b.2 (2026-05-27) — `feature_events` constants. These are
# event-type strings the special-ask flow emits. NOT in the global
# `KNOWN_EVENT_TYPES` set yet — added below at import time so the
# funnel aggregator surfaces them.
SPECIAL_ASK_SURFACED  = "special_ask.surfaced"
SPECIAL_ASK_SUBMITTED = "special_ask.submitted"
SPECIAL_ASK_DISMISSED = "special_ask.dismissed"


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

    # Phase R.5.b.2 (2026-05-27) — day-14 special-ask trigger.
    # On-read pattern: if day >= 14 and no row exists, mint one and
    # surface the modal on next /app/ mount. The flag travels with
    # the trial-status payload so the frontend never makes a 2nd RTT.
    special_ask_surface = False
    if not locked and day >= SPECIAL_ASK_TRIGGER_DAY:
        try:
            row = await get_or_mint_special_ask(
                account_id=account["id"],
                cohort_tag=account.get("cohort_tag"),
                trial_day=day,
            )
            if row and row.get("status") == "pending":
                special_ask_surface = True
        except Exception:
            pass

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
        "special_ask_surface":  special_ask_surface,
        "special_ask_at_day":   SPECIAL_ASK_TRIGGER_DAY,
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



# ─────────────────────────────────────────────────────────────────────
# Phase R.5.b — public read of in-app copy slots that the user sees
# (early_access_opt_in, day_16_banner). Authenticated user only; the
# slot identifier is whitelisted to the surfaces a regular user can
# legitimately render. Email slots (welcome_email, feedback_thanks)
# stay superadmin-only via the editor endpoints.
# ─────────────────────────────────────────────────────────────────────
_USER_VISIBLE_SLOTS = frozenset(("early_access_opt_in", "day_16_banner"))


@router.get("/copy/{slot}")
async def get_user_visible_copy(
    slot: str,
    _account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Frontend `EarlyAccessOptIn` + day-16 banner read their copy
    overrides via this endpoint. Returns `{slot, fields, values}`."""
    if slot not in _USER_VISIBLE_SLOTS:
        raise HTTPException(status_code=403, detail="Slot not user-visible.")
    row = await get_slot_override(slot)
    values = {f: (row or {}).get(f) for f in SLOT_FIELDS.get(slot, [])}
    return {"slot": slot, "fields": list(SLOT_FIELDS.get(slot, [])), "values": values}




# ═════════════════════════════════════════════════════════════════════
# Phase R.5.b.2 — Special-ask endpoints
# ═════════════════════════════════════════════════════════════════════

class SpecialAskIn(BaseModel):
    referral_name:      Optional[str] = Field(default=None, max_length=200)
    referral_email:     Optional[str] = Field(default=None, max_length=200)
    case_study_consent: Optional[bool] = None
    testimonial_text:   Optional[str] = Field(default=None, max_length=4000)


@router.get("/special-ask")
async def get_my_special_ask(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Return the user's special-ask row (if any) + the founder-saved
    `special_ask` copy slot overrides (or defaults). Frontend modal
    reads this on first mount of the trigger."""
    row = await get_special_ask(account_id=account["id"])
    override_row = await get_slot_override("special_ask")
    default_copy = {
        "modal_heading": "Before you go — one ask.",
        "modal_body":    "[FOUNDER: write 2-3 sentences in your voice asking for a referral name + email + (optional) case-study consent + (optional) testimonial. Edit before going live.]",
        "email_subject": "A small ask, from one founder to another",
        "email_body":    "[FOUNDER: write 3-4 sentences in your voice — same ask as the modal but for inbox. Edit before going live.]",
    }
    copy_values = overlay_slot(
        default_payload=default_copy, override_row=override_row, slot="special_ask",
    )
    return {
        "row":  row,
        "copy": copy_values,
        "trigger_at_day": SPECIAL_ASK_TRIGGER_DAY,
    }


@router.post("/special-ask")
async def put_my_special_ask(
    body: SpecialAskIn,
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Persist the user's submission. Status flips to `complete` only
    when referral_name + referral_email are both filled; otherwise
    `partial` (any other field filled) or `pending` (nothing)."""
    row = await save_special_ask(
        account_id=account["id"],
        referral_name=body.referral_name,
        referral_email=body.referral_email,
        case_study_consent=body.case_study_consent,
        testimonial_text=body.testimonial_text,
    )
    # Phase R.3 / R.5.b.2 — emit feature_event
    try:
        await emit_feature_event(
            event_type=SPECIAL_ASK_SUBMITTED,
            account_id=account["id"],
            cohort_tag=account.get("cohort_tag"),
            payload={"status": row.get("status"), "has_referral":
                     bool(row.get("referral_name") and row.get("referral_email"))},
        )
    except Exception:
        pass
    return row


@router.post("/special-ask/dismiss")
async def dismiss_my_special_ask(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """`Remind me later` action. Does NOT change the row's status —
    the modal will re-surface on the next session because the row
    stays `pending`. Just emits the `special_ask.dismissed` event so
    the cohort console can show "asked but dismissed" patterns."""
    try:
        await emit_feature_event(
            event_type=SPECIAL_ASK_DISMISSED,
            account_id=account["id"],
            cohort_tag=account.get("cohort_tag"),
        )
    except Exception:
        pass
    return {"ok": True, "dismissed_at": datetime.now(timezone.utc).isoformat()}


@router.post("/special-ask/surface-ack")
async def ack_my_special_ask_surfaced(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Frontend pings this on modal mount so the funnel records the
    surfacing event exactly once per session."""
    try:
        await emit_feature_event(
            event_type=SPECIAL_ASK_SURFACED,
            account_id=account["id"],
            cohort_tag=account.get("cohort_tag"),
        )
    except Exception:
        pass
    return {"ok": True}

