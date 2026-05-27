"""Phase R.5.b.2 (2026-05-27) — Founding Cohort special-ask tracker.

Day-14 trigger: when a cohort user lands inside `/app/*` on day 14
or later of their trial AND there's no `cohort_special_asks` row for
them yet, the backend mints a `pending` row + flags the modal to
surface. The frontend modal collects (referral_name + referral_email
required) + (case_study_consent boolean) + (testimonial_text optional)
and PUTs the row → status flips to `complete` (referral filled) or
`partial` (some fields but no referral) or stays `pending`.

The email parallel (BackgroundTasks SendGrid send at the same day-14
boundary) follows the R.4 semantic divergence: if the founder hasn't
filled the `special_ask` copy slot yet, the EMAIL is HELD with a
warning log line but the in-app modal STILL surfaces. The user
experience must not break because the founder forgot to edit copy.

Locked row schema (do NOT alter without a new R sub-phase):

  {
    "id":              <hex32>,
    "account_id":      <str>,
    "cohort_tag":      <str | null>,
    "asked_at":        <iso8601>,
    "surfaced_via":    "in_app" | "email" | "both",
    "referral_name":   <str | null>,
    "referral_email":  <str | null>,
    "case_study_consent": <bool | null>,
    "testimonial_text":  <str | null>,
    "captured_at":     <iso8601 | null>,
    "status":          "pending" | "partial" | "complete",
  }

Status transitions are computed by `compute_status()` on every write.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core import db


log = logging.getLogger("akki.cohort.special_ask")


# ─────────────────────────────────────────────────────────────────────
# Locked trigger threshold — day 14 of the founding cohort trial.
# Day counter uses the same on-read pattern as R.5.a's day-counter
# (computed from `accounts.trial_start_at`).
# ─────────────────────────────────────────────────────────────────────
SPECIAL_ASK_TRIGGER_DAY = 14


def compute_status(*, referral_name: Optional[str], referral_email: Optional[str],
                   case_study_consent: Optional[bool], testimonial_text: Optional[str]) -> str:
    """Derive the row's status from the captured fields.

    Locked rules:
      complete  — referral_name AND referral_email both filled
      partial   — any of the optional fields filled but NOT both
                  referral_name + referral_email
      pending   — every field is empty / None
    """
    has_referral = bool((referral_name or "").strip() and (referral_email or "").strip())
    has_any = any([
        (referral_name or "").strip(),
        (referral_email or "").strip(),
        case_study_consent is True,
        (testimonial_text or "").strip(),
    ])
    if has_referral:
        return "complete"
    if has_any:
        return "partial"
    return "pending"


# ─────────────────────────────────────────────────────────────────────
# get_or_mint_special_ask — day-14 trigger entry point
# ─────────────────────────────────────────────────────────────────────
async def get_or_mint_special_ask(
    *,
    account_id: str,
    cohort_tag: Optional[str],
    trial_day: int,
    surfaced_via: str = "in_app",
) -> Optional[Dict[str, Any]]:
    """If trial_day >= SPECIAL_ASK_TRIGGER_DAY and no row exists for
    this account, mint a `pending` row + return it. If a row exists,
    return it unchanged. Returns None when day < 14 (no surfacing
    yet).
    """
    if trial_day < SPECIAL_ASK_TRIGGER_DAY:
        return None
    row = await db.cohort_special_asks.find_one(
        {"account_id": account_id}, {"_id": 0},
    )
    if row:
        return row
    now_iso = datetime.now(timezone.utc).isoformat()
    rec = {
        "id":                 uuid.uuid4().hex,
        "account_id":         account_id,
        "cohort_tag":         cohort_tag,
        "asked_at":           now_iso,
        "surfaced_via":       surfaced_via,
        "referral_name":      None,
        "referral_email":     None,
        "case_study_consent": None,
        "testimonial_text":   None,
        "captured_at":        None,
        "status":             "pending",
    }
    await db.cohort_special_asks.insert_one(rec)
    return rec


async def get_special_ask(*, account_id: str) -> Optional[Dict[str, Any]]:
    """Return the row for the account or None. Pure read."""
    return await db.cohort_special_asks.find_one(
        {"account_id": account_id}, {"_id": 0},
    )


async def save_special_ask(
    *,
    account_id: str,
    referral_name: Optional[str],
    referral_email: Optional[str],
    case_study_consent: Optional[bool],
    testimonial_text: Optional[str],
) -> Dict[str, Any]:
    """Persist the user's submission. Computes status + stamps
    captured_at. Row must already exist (use `get_or_mint_special_ask`
    first to create it on day-14 trigger). Returns the updated row.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    status = compute_status(
        referral_name=referral_name, referral_email=referral_email,
        case_study_consent=case_study_consent, testimonial_text=testimonial_text,
    )
    update = {
        "referral_name":      (referral_name or "").strip() or None,
        "referral_email":     (referral_email or "").strip() or None,
        "case_study_consent": case_study_consent,
        "testimonial_text":   (testimonial_text or "").strip() or None,
        "captured_at":        now_iso,
        "status":             status,
    }
    row = await db.cohort_special_asks.find_one_and_update(
        {"account_id": account_id},
        {"$set": update},
        return_document=False,
    )
    if not row:
        # No mint yet — caller hit the save endpoint before the day-14
        # trigger landed. Create-with-update so we don't lose the data.
        rec = {
            "id":              uuid.uuid4().hex,
            "account_id":      account_id,
            "cohort_tag":      None,
            "asked_at":        now_iso,
            "surfaced_via":    "in_app",
            **update,
        }
        await db.cohort_special_asks.insert_one(rec)
    return await db.cohort_special_asks.find_one(
        {"account_id": account_id}, {"_id": 0},
    )


async def aggregate_cohort_special_asks(*, cohort_tag: str) -> Dict[str, Any]:
    """Per-cohort aggregate used by the cohort console additions.

    Returns:
      { cohort_tag, total_invitees, total_asks, status_counts: {pending, partial, complete} }
    """
    invitees = await db.cohort_invites.count_documents({"cohort_tag": cohort_tag})
    rows = await db.cohort_special_asks.find(
        {"cohort_tag": cohort_tag}, {"_id": 0, "status": 1},
    ).to_list(length=1000)
    counts = {"pending": 0, "partial": 0, "complete": 0}
    for r in rows:
        s = r.get("status") or "pending"
        if s in counts:
            counts[s] += 1
    return {
        "cohort_tag":     cohort_tag,
        "total_invitees": invitees,
        "total_asks":     len(rows),
        "status_counts":  counts,
        "complete_pct":   round(100 * counts["complete"] / max(1, invitees), 1),
    }
