"""J1 — User onboarding status (re-intro banner + Help/Trust-Center
tooltips state).

Three concepts, all per-user, all read at the AppShell top-level:

* **Re-intro banner** — surfaced when the user predates Shield v1.x AND
  has not acknowledged the banner AND has dismissed it fewer than 3
  times. State on ``accounts.shield_v1_intro_*``.
* **Trust Center tooltip** — one-shot on the Trust Center top-bar
  entry. Suppressed once the re-intro is acknowledged. State on
  ``accounts.trust_center_tooltip_dismissed_at``.
* **Help tooltip** — one-shot on the Help top-bar entry. State on
  ``accounts.help_tooltip_dismissed_at``.

Conservative writes
-------------------
All transitions are idempotent. Dismissal counter capped at 3 (further
``POST /dismiss`` calls return the capped state). Acknowledgement is
permanent. No way to RE-show the banner once acknowledged (the
re-intro is a one-time announcement, not a recurring nudge).

Detection logic (file:line)
---------------------------
The "grandfathered" cutoff is the same env-configurable
``SHIELD_V1_DEPLOY_TIMESTAMP`` constant used by the H1 indicator
(``routers/synisense_metrics.py:47``). Importing from there keeps a
single source of truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core import db, get_current_account

# Single source of truth for the H1/J1 cut-over. Env-overridable via
# SHIELD_V1_DEPLOY_TIMESTAMP. NEVER hardcode the date here.
from routers.synisense_metrics import (
    _SHIELD_V1_DEPLOY_TIMESTAMP_STR as SHIELD_V1_DEPLOY_ISO,
    _shield_v1_cutoff as _shield_v1_deploy_dt,
)


router = APIRouter(prefix="/api/users/me/onboarding-status", tags=["onboarding"])

MAX_DISMISSALS = 3


def _coerce_dt(value: Any):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None
    return None


async def _compute_status(account: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the onboarding-status payload AND the diagnostic
    fields the FE uses to decide which tooltips to render. Pure
    read-side function — no writes."""
    account_id = account["id"]
    acknowledged_at = account.get("shield_v1_intro_acknowledged_at")
    dismissals_count = int(account.get("shield_v1_intro_dismissals_count") or 0)

    # Has the user got ≥1 chat already? Use a cheap count, capped at 1.
    # Brand-new users (no chats) go through First Session, not the
    # re-intro banner.
    has_chats = await db.chats.count_documents(
        {"account_id": account_id}, limit=1,
    ) > 0

    # Is the user pre-Shield-v1.x? Their oldest chat must be before
    # the cutoff. (A new account with no chats is NOT grandfathered
    # — they'll go through First Session.)
    is_grandfathered = False
    reason = "none"
    if has_chats:
        cutoff = _shield_v1_deploy_dt()
        oldest = await db.chats.find_one(
            {"account_id": account_id},
            {"_id": 0, "created_at": 1},
            sort=[("created_at", 1)],
        )
        oldest_created = _coerce_dt((oldest or {}).get("created_at"))
        if oldest_created and cutoff and oldest_created < cutoff:
            is_grandfathered = True
            reason = "pre_shield_v1_chats_exist"

    if not is_grandfathered:
        needs_reintro = False
    elif acknowledged_at:
        needs_reintro = False
        reason = "already_acknowledged"
    elif dismissals_count >= MAX_DISMISSALS:
        needs_reintro = False
        reason = "max_dismissals_reached"
    else:
        needs_reintro = True

    # Tooltip suppression: once the re-intro is acknowledged, the
    # user has seen Trust Center already — don't show the tooltip
    # again. If they haven't seen the re-intro and never dismissed
    # the tooltip, show it.
    tc_dismissed = bool(account.get("trust_center_tooltip_dismissed_at"))
    help_dismissed = bool(account.get("help_tooltip_dismissed_at"))
    show_tc_tooltip = (
        not tc_dismissed and not acknowledged_at
    )
    show_help_tooltip = not help_dismissed

    # J3 (2026-05-25, ratified spec §3 Stage 5) — Trust Center
    # introduction (3-stop tour overlay on the Trust Center page).
    # Gated on the user having uploaded at least one document (the
    # Stage 4 `first_doc_uploaded` flag) AND not having dismissed
    # the tour previously. Idempotent.
    fs = account.get("first_session") or {}
    first_doc_uploaded = bool(fs.get("first_doc_uploaded"))
    tc_introduced = bool(fs.get("trust_center_introduced"))
    show_tc_tour = first_doc_uploaded and not tc_introduced

    return {
        "needs_reintro": needs_reintro,
        "reason": reason,
        "dismissals_count": min(dismissals_count, MAX_DISMISSALS),
        "max_dismissals": MAX_DISMISSALS,
        "acknowledged_at": acknowledged_at,
        "trust_center_tooltip": {
            "show": show_tc_tooltip,
            "dismissed_at": account.get("trust_center_tooltip_dismissed_at"),
        },
        "help_tooltip": {
            "show": show_help_tooltip,
            "dismissed_at": account.get("help_tooltip_dismissed_at"),
        },
        "trust_center_tour": {
            "show": show_tc_tour,
            "first_doc_uploaded": first_doc_uploaded,
            "trust_center_introduced": tc_introduced,
        },
        "shield_v1_deploy_at": SHIELD_V1_DEPLOY_ISO,
    }


@router.get("")
async def get_onboarding_status(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Read-only — used by AppShell to decide which banner / tooltips
    to render."""
    return await _compute_status(current)


@router.post("/dismiss")
async def dismiss_reintro(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Increment the re-intro dismissals counter. Caps at
    ``MAX_DISMISSALS=3``; further calls return the capped state."""
    current_count = int(current.get("shield_v1_intro_dismissals_count") or 0)
    new_count = min(current_count + 1, MAX_DISMISSALS)
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {
            "shield_v1_intro_dismissals_count": new_count,
            "shield_v1_intro_last_dismissed_at":
                datetime.now(timezone.utc).isoformat(),
        }},
    )
    current["shield_v1_intro_dismissals_count"] = new_count
    return await _compute_status(current)


@router.post("/acknowledge")
async def acknowledge_reintro(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Permanently lock off the re-intro banner. Sets
    ``shield_v1_intro_acknowledged_at`` and also marks the Trust
    Center tooltip dismissed (the user has now provably seen the
    Trust Center surface)."""
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {
            "shield_v1_intro_acknowledged_at": now,
            "trust_center_tooltip_dismissed_at": now,
        }},
    )
    current["shield_v1_intro_acknowledged_at"] = now
    current["trust_center_tooltip_dismissed_at"] = now
    return await _compute_status(current)


@router.post("/tooltips/trust-center/dismiss")
async def dismiss_trust_center_tooltip(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Hide the Trust Center top-bar tooltip permanently. Does NOT
    affect the re-intro banner (those are independent)."""
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"trust_center_tooltip_dismissed_at": now}},
    )
    current["trust_center_tooltip_dismissed_at"] = now
    return await _compute_status(current)


@router.post("/tooltips/help/dismiss")
async def dismiss_help_tooltip(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Hide the Help top-bar tooltip permanently."""
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"help_tooltip_dismissed_at": now}},
    )
    current["help_tooltip_dismissed_at"] = now
    return await _compute_status(current)


@router.post("/trust-center-tour/dismiss")
async def dismiss_trust_center_tour(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """J3 (2026-05-25, ratified spec §3 Stage 5) — Mark the Trust
    Center introduction tour as completed. Idempotent. Once
    dismissed, the tour does NOT re-appear on subsequent visits.

    Flips `accounts.{id}.first_session.trust_center_introduced` to
    True with an ISO timestamp; the `_compute_status` reader gates
    `trust_center_tour.show` on this flag.
    """
    now = datetime.now(timezone.utc).isoformat()
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {
            "first_session.trust_center_introduced": True,
            "first_session.trust_center_introduced_at": now,
        }},
    )
    # Refresh the in-memory representation for `_compute_status`.
    fs = dict(current.get("first_session") or {})
    fs["trust_center_introduced"] = True
    fs["trust_center_introduced_at"] = now
    current["first_session"] = fs
    return await _compute_status(current)
