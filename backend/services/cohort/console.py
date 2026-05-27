"""Phase R.5.a (2026-05-27) — Cohort console aggregator + funnel-stage logic.

Locked autonomous-mode contract:
  - Super-admin gated.
  - Table per logo (cohort invitee) with 5 funnel stages:
        Invited → Activated → Engaged → Attached → Committed
  - Time-window toggle: 7d / 28d / since-trial-start (default).
  - Per-user activity timeline drill-down (last 50 events).
  - Day-counter enforcement: Day 16 → soft_warning, Day 22 → expired_hard_lock.
  - Day counter is computed ON-READ from `trial_start_at` (set when
    the magic link is first consumed) — no cron needed.

Funnel-stage definitions (locked here; R.5.b copy editor cannot
change these — they are structural, not copy):

  Invited     — cohort_invite row exists, status=pending OR consumed.
                Anyone who got a magic link.
  Activated   — cohort.magic_link.consumed event exists for the account.
                First successful sign-in.
  Engaged     — ≥1 of: solva.session.created, work_studio.export.completed.
                Real product usage.
  Attached    — ≥2 distinct calendar days with Engaged-class events.
                Sticky usage — they came back at least once.
  Committed   — feedback.submitted with tag in ("Great", "Wrong").
                Constructive signal — they care enough to write.

Stages are CUMULATIVE: a Committed account is ALSO Attached, Engaged,
Activated, Invited. The console UI shows each account's HIGHEST stage.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from core import db


log = logging.getLogger("akki.cohort.console")


# ─────────────────────────────────────────────────────────────────────
# Trial day-counter thresholds — LOCKED at the autonomous-queue
# dispatch level. Day 16 = soft_warning banner. Day 22 = hard lock.
# ─────────────────────────────────────────────────────────────────────
TRIAL_SOFT_WARNING_DAY = 16
TRIAL_HARD_LOCK_DAY = 22
TRIAL_TOTAL_DAYS = 30  # 30-day founding cohort default


# ─────────────────────────────────────────────────────────────────────
# Funnel-stage rank — used to sort/group + render "highest stage so far"
# ─────────────────────────────────────────────────────────────────────
FUNNEL_STAGES = ("Invited", "Activated", "Engaged", "Attached", "Committed")


def _compute_trial_status(
    *,
    trial_start_at: Optional[str],
    now: Optional[datetime] = None,
) -> Tuple[str, int]:
    """Return `(trial_status, day_number)` computed from
    `trial_start_at` (ISO string). If `trial_start_at` is None
    (account hasn't activated yet), returns `("pending", 0)`.

    Statuses (locked):
      pending             — no trial started yet (account.trial_start_at is None)
      active_trial        — day 1 through TRIAL_SOFT_WARNING_DAY-1
      soft_warning        — TRIAL_SOFT_WARNING_DAY through TRIAL_HARD_LOCK_DAY-1
      expired_hard_lock   — TRIAL_HARD_LOCK_DAY onward
    """
    if not trial_start_at:
        return ("pending", 0)
    try:
        start = datetime.fromisoformat(trial_start_at.replace("Z", "+00:00"))
    except Exception:
        return ("pending", 0)
    cur = now or datetime.now(timezone.utc)
    delta = (cur - start).total_seconds() / 86400.0
    day = int(delta) + 1  # day 1 = first 24h
    if day < TRIAL_SOFT_WARNING_DAY:
        return ("active_trial", day)
    if day < TRIAL_HARD_LOCK_DAY:
        return ("soft_warning", day)
    return ("expired_hard_lock", day)


# ─────────────────────────────────────────────────────────────────────
# Time-window helpers
# ─────────────────────────────────────────────────────────────────────
def _resolve_window(
    *,
    window: str,
    trial_start_at: Optional[str],
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Return the ISO floor for the requested time window, or None
    for "all time" / since-trial-start when there's no trial yet.

    Acceptable `window` values: "7d", "28d", "since_trial_start".
    """
    cur = now or datetime.now(timezone.utc)
    if window == "7d":
        return (cur - timedelta(days=7)).isoformat()
    if window == "28d":
        return (cur - timedelta(days=28)).isoformat()
    # since_trial_start (default): floor = trial_start_at (or all time)
    return trial_start_at


# ─────────────────────────────────────────────────────────────────────
# Per-account stage computation
# ─────────────────────────────────────────────────────────────────────
async def _compute_funnel_stage_for_account(
    *,
    account_id: str,
    invite_present: bool,
    window_floor: Optional[str] = None,
) -> str:
    """Return the highest funnel stage the account has reached within
    the time window. `window_floor` is an ISO string; events older
    than the floor are ignored.

    Locked rules — see module docstring.
    """
    if not invite_present:
        # Account exists but no cohort invite — they're outside the
        # founding cohort. Treat as "Invited" only if they have any
        # event row at all in window; otherwise the console won't
        # render them (callers filter pre-stage).
        return "Invited"

    match: Dict[str, Any] = {"account_id": account_id}
    if window_floor:
        match["created_at"] = {"$gte": window_floor}

    # Pull only the event_type field for the per-account stage check.
    rows = await db.feature_events.find(
        match, {"_id": 0, "event_type": 1, "payload": 1, "created_at": 1},
    ).to_list(length=2000)

    consumed = any(r["event_type"] == "cohort.magic_link.consumed" for r in rows)
    engaged_events = [r for r in rows if r["event_type"] in (
        "solva.session.created", "work_studio.export.completed",
    )]
    engaged_days = {r["created_at"][:10] for r in engaged_events}  # YYYY-MM-DD
    committed = any(
        r["event_type"] == "feedback.submitted"
        and (r.get("payload") or {}).get("tag") in ("Great", "Wrong")
        for r in rows
    )

    if committed:
        return "Committed"
    if len(engaged_days) >= 2:
        return "Attached"
    if engaged_events:
        return "Engaged"
    if consumed:
        return "Activated"
    return "Invited"


# ─────────────────────────────────────────────────────────────────────
# Top-level aggregator — used by the cohort console table endpoint
# ─────────────────────────────────────────────────────────────────────
async def aggregate_cohort_console(
    *,
    cohort_tag: Optional[str] = None,
    window: str = "since_trial_start",
    limit: int = 200,
) -> Dict[str, Any]:
    """Build the rows for the cohort console table.

    Returns:
      {
        "cohort_tag": <str or null>,
        "window":     <"7d" | "28d" | "since_trial_start">,
        "rows": [
          {
            "account_id":       <str>,
            "email":            <str>,
            "first_name":       <str | null>,
            "logo_name":        <str | null>,
            "cohort_tag":       <str>,
            "trial_start_at":   <iso or null>,
            "trial_day":        <int>,
            "trial_status":     <"pending"|"active_trial"|"soft_warning"|"expired_hard_lock">,
            "stage":            <"Invited"|"Activated"|"Engaged"|"Attached"|"Committed">,
            "last_signal_at":   <iso or null>,
            "invite_status":    <"pending"|"consumed"|"expired">,
            "invite_consumed_at": <iso or null>,
          },
          ...
        ],
        "stage_counts":  { "Invited": N, "Activated": N, ... },
        "totals":        { "rows": N, "active_trials": N, "soft_warnings": N, "hard_locks": N },
        "as_of":         <iso>,
      }
    """
    cur = datetime.now(timezone.utc)
    q: Dict[str, Any] = {}
    if cohort_tag:
        q["cohort_tag"] = cohort_tag

    # 1) Pull invite rows (the source-of-truth for "Invited" stage —
    #    every cohort invitee should appear in the console even if
    #    they haven't consumed the link yet).
    invites = await db.cohort_invites.find(
        q, {"_id": 0},
    ).sort("issued_at", -1).to_list(length=limit)

    rows: List[Dict[str, Any]] = []
    stage_counts = {s: 0 for s in FUNNEL_STAGES}
    totals = {"rows": 0, "active_trials": 0, "soft_warnings": 0, "hard_locks": 0}

    for inv in invites:
        # Find the account associated with this invite (if consumed).
        account_id = inv.get("consumed_by_account_id")
        account_doc: Dict[str, Any] = {}
        if account_id:
            account_doc = (await db.accounts.find_one(
                {"id": account_id}, {"_id": 0},
            )) or {}

        trial_start_at = account_doc.get("trial_start_at")
        trial_status_str, trial_day = _compute_trial_status(
            trial_start_at=trial_start_at, now=cur,
        )

        window_floor = _resolve_window(
            window=window, trial_start_at=trial_start_at, now=cur,
        )

        # Funnel stage — only meaningful if we have an account_id.
        if account_id:
            stage = await _compute_funnel_stage_for_account(
                account_id=account_id,
                invite_present=True,
                window_floor=window_floor,
            )
            # Last-signal-at = most recent feature_event for this account.
            last_evt = await db.feature_events.find_one(
                {"account_id": account_id}, {"_id": 0, "created_at": 1},
                sort=[("created_at", -1)],
            )
            last_signal_at = last_evt["created_at"] if last_evt else None
        else:
            stage = "Invited"
            last_signal_at = None

        # Invite status (use the R.1 static field, refined with date)
        inv_consumed_at = inv.get("consumed_at")
        inv_expires_at = inv.get("expires_at")
        if inv_consumed_at:
            inv_status = "consumed"
        elif inv_expires_at and inv_expires_at < cur.isoformat():
            inv_status = "expired"
        else:
            inv_status = "pending"

        row = {
            "account_id":         account_id,
            "email":              inv["email"],
            "first_name":         inv.get("first_name"),
            "logo_name":          inv.get("logo_name"),
            "cohort_tag":         inv["cohort_tag"],
            "trial_start_at":     trial_start_at,
            "trial_day":          trial_day,
            "trial_status":       trial_status_str,
            "stage":              stage,
            "last_signal_at":     last_signal_at,
            "invite_status":      inv_status,
            "invite_consumed_at": inv_consumed_at,
        }
        rows.append(row)
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
        totals["rows"] += 1
        if trial_status_str == "active_trial":
            totals["active_trials"] += 1
        elif trial_status_str == "soft_warning":
            totals["soft_warnings"] += 1
        elif trial_status_str == "expired_hard_lock":
            totals["hard_locks"] += 1

    return {
        "cohort_tag":   cohort_tag,
        "window":       window,
        "rows":         rows,
        "stage_counts": stage_counts,
        "totals":       totals,
        "as_of":        cur.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────
# Per-account drill-down — recent activity timeline
# ─────────────────────────────────────────────────────────────────────
async def get_account_activity_timeline(
    *,
    account_id: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Return the most recent `limit` feature_events for the account,
    most-recent-first."""
    rows = await db.feature_events.find(
        {"account_id": account_id},
        {"_id": 0, "id": 1, "event_type": 1, "created_at": 1, "payload": 1,
         "cohort_tag": 1},
    ).sort("created_at", -1).to_list(length=limit)
    return rows
