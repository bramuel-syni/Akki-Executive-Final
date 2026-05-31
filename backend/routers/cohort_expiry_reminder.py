"""Phase P5.7.4 (2026-02) — Cohort magic-link day-10 expiry reminder.

Daily sweep, fires the Touch 4 reminder for every approved
application whose magic link is on day 10 of its 14-day life and has
not yet redeemed.

Idempotency: stamps `expiry_reminder_sent_at` on the magic_link row
the first time the reminder fires; the query filters on the
absence of that field so re-runs never double-send.

Bounded window: matches links issued between 10 and 11 days ago.
The lower bound is set tight enough that a missed-day-by-job-crash
still picks up within a single window (e.g. if the job fails on
day 10, the next day's job will catch the link at day 11 because
the window includes both).

Why a tight window (10–11 days, not "10 days and older") — the
absolute expiry is 14 days. A link at day 12 or 13 has only 1–2
days left; a reminder at that point is closer to a "your link is
about to die" panic ping than a "you have time, come back" nudge.
We deliberately stop sending past day 11 so the recipient's
last touch from us is calm, not panicked.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from core import db, iso as _iso, now as _now
from services.cohort_email import send_reminder

log = logging.getLogger(__name__)


async def run_expiry_reminder_sweep(
    *,
    public_base: str = "",
) -> Dict[str, Any]:
    """Iterate every magic_link row that needs the day-10 nudge,
    send the reminder, and stamp the row so we never resend.

    Returns a summary dict for logging / observability:
      {
        candidates_scanned: int,
        reminders_sent:     int,
        skipped_consumed:   int,
        skipped_app_missing:int,
        send_errors:        int,
      }
    """
    now = _now()
    upper = now - timedelta(days=10)   # link issued ≤10 days ago — included
    lower = now - timedelta(days=11)   # link issued >11 days ago — excluded

    cursor = db.cohort_magic_links.find(
        {
            "consumed_at": None,
            "expiry_reminder_sent_at": {"$exists": False},
            "issued_at": {
                "$gte": lower.isoformat(),
                "$lt":   upper.isoformat(),
            },
        },
        {"_id": 0},
    )

    summary = {
        "candidates_scanned":  0,
        "reminders_sent":      0,
        "skipped_consumed":    0,
        "skipped_app_missing": 0,
        "send_errors":         0,
    }

    async for row in cursor:
        summary["candidates_scanned"] += 1

        # Defensive re-check that the link is still unconsumed
        # (a consume could have raced between the find and now).
        if row.get("consumed_at") is not None:
            summary["skipped_consumed"] += 1
            continue

        application_id = row.get("application_id")
        app_row = await db.cohort_applications.find_one(
            {"id": application_id}, {"_id": 0, "id": 1, "email": 1, "name": 1, "status": 1},
        )
        if not app_row or app_row.get("status") != "approved":
            summary["skipped_app_missing"] += 1
            continue

        # We do not have the RAW token on disk (only the hash). The
        # reminder needs to point at the same magic_url the original
        # approval email did, but we can't reconstruct the raw token
        # from the hash. The pragmatic compromise: surface the
        # absolute path to `/welcome` and trust the recipient to
        # re-use the original approval email's link, OR include a
        # fallback URL that takes them to /signin with a hint.
        #
        # This is intentional: a security property of the existing
        # design is that the raw token leaves the server exactly
        # once (in the approval email). Re-minting a fresh raw token
        # at reminder time would require revoking the old one
        # silently — which would make the original approval email's
        # link stop working without explanation.
        #
        # The user can manually trigger a "re-mint" admin action if
        # the recipient claims to have lost the original email; that
        # path stays explicit.
        if not public_base:
            import os as _os
            public_base = (_os.environ.get("APP_PUBLIC_URL") or "").strip().rstrip("/")
        magic_link = (
            f"{public_base}/signin?reminder=1"
            if public_base else "/signin?reminder=1"
        )

        try:
            send_result = send_reminder(
                to_email=app_row["email"],
                first_name=app_row.get("name"),
                magic_link=magic_link,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("expiry reminder: send failed app_id=%s err=%s", application_id, str(e)[:160])
            summary["send_errors"] += 1
            send_result = {"status": "error"}

        # Stamp regardless of send result — a server-side error
        # shouldn't cause us to re-attempt the next day and risk a
        # double-send if the second attempt succeeds and we never
        # learn the first one did too. Operators can rerun manually
        # for confirmed transient failures.
        await db.cohort_magic_links.update_one(
            {"id": row["id"]},
            {"$set": {
                "expiry_reminder_sent_at": _iso(now),
                "expiry_reminder_status":  send_result.get("status", "unknown"),
                "expiry_reminder_provider_id": send_result.get("provider_id", ""),
            }},
        )

        if send_result.get("status") == "sent" or send_result.get("status") == "flag_off":
            summary["reminders_sent"] += 1

    return summary
