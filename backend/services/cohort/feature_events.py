"""Phase R.3 (2026-05-27) — Founding Cohort feature-usage instrumentation.

Locked autonomous-mode contract:
  - One emit helper `emit_feature_event(event_type, account_id, …)`
    that writes to a NEW `db.feature_events` collection — independent
    of the legacy `db.events` (Calendar) and `db.telemetry_events`
    (Synisense) collections.
  - 6 canonical event types (each a tiny dotted-key namespace):
        account.signed_up
        cohort.magic_link.consumed
        solva.session.created
        work_studio.export.completed
        cohort.welcome.dispatched
        calendar.sync.linked
  - Each event row carries `{id, event_type, account_id, cohort_tag,
    created_at, payload}` — `cohort_tag` is denormalized at emit-time
    for fast funnel queries.
  - TTL index on `created_at` → 90-day raw retention. Aggregates
    (funnel counters) are computed on read; R.5 cohort console can
    rebuild from raw any time within the retention window.
  - `emit_feature_event` NEVER raises (failures only log).

Why a NEW collection vs reusing `db.telemetry_events`:
  `db.telemetry_events` carries the Solva variant-cycle + Synisense
  signal-derivation events with a different schema (`signal_id`,
  `signal_type`, tenant-scoped). Mixing cohort funnel rows there
  would force every Synisense reader to filter by event_type and
  would couple two unrelated phase scopes. Following the codebase's
  pre-existing pattern of one collection per emit-domain (see
  `db.solva_variant_seen`, `db.solva_key_emissions`,
  `db.cohort_invites`) keeps R.3 boundaries clean.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core import db


log = logging.getLogger("akki.cohort.feature_events")


# ─────────────────────────────────────────────────────────────────────
# Canonical event-type namespace.
# Future additions MUST follow `domain.entity.verb_past_tense` form.
# Add new event types HERE (not inline at call sites) so the source
# of truth is single + searchable.
# ─────────────────────────────────────────────────────────────────────
ACCOUNT_SIGNED_UP            = "account.signed_up"
COHORT_MAGIC_LINK_CONSUMED   = "cohort.magic_link.consumed"
COHORT_WELCOME_DISPATCHED    = "cohort.welcome.dispatched"
SOLVA_SESSION_CREATED        = "solva.session.created"
WORK_STUDIO_EXPORT_COMPLETED = "work_studio.export.completed"
CALENDAR_SYNC_LINKED         = "calendar.sync.linked"
# Phase R.4 (2026-05-27) — in-app feedback widget.
FEEDBACK_SUBMITTED           = "feedback.submitted"


KNOWN_EVENT_TYPES = frozenset({
    ACCOUNT_SIGNED_UP,
    COHORT_MAGIC_LINK_CONSUMED,
    COHORT_WELCOME_DISPATCHED,
    SOLVA_SESSION_CREATED,
    WORK_STUDIO_EXPORT_COMPLETED,
    CALENDAR_SYNC_LINKED,
    FEEDBACK_SUBMITTED,
})


async def emit_feature_event(
    *,
    event_type: str,
    account_id: str,
    cohort_tag: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Insert a feature-event row. NEVER raises — failures only log.

    Args:
      event_type   : One of the dotted-key constants above. Caller
                     should use the constants (not raw strings) so
                     refactors stay searchable.
      account_id   : The account performing the action (`account.id`,
                     NOT user_id; mirror existing R.1 schema).
      cohort_tag   : Denormalized at emit-time. If the caller doesn't
                     know the account's tag, pass None — the funnel
                     query joins to `db.accounts` to recover it.
      payload      : Optional event-specific data (e.g. `{export_kind,
                     output_format}` for work_studio.export.completed).
                     Stays small; this is NOT a logging surface.
    """
    if event_type not in KNOWN_EVENT_TYPES:
        log.warning("feature_event_unknown_type: %s", event_type)
        # Don't drop the event — write it anyway so R.5 console can
        # surface the typo + we don't lose data.
    try:
        row = {
            "id":         uuid.uuid4().hex,
            "event_type": event_type,
            "account_id": account_id,
            "cohort_tag": cohort_tag,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload":    dict(payload) if payload else {},
        }
        await db.feature_events.insert_one(row)
    except Exception as e:  # noqa: BLE001
        log.error("feature_event_emit_failed: %s", {
            "event_type": event_type,
            "account_id": account_id,
            "error":      str(e)[:200],
        })


async def ensure_indexes() -> None:
    """Best-effort index creation. Called from server.py startup hook
    alongside the R.1 cohort_invites indexes."""
    try:
        # 90-day raw retention via TTL on the ISO `created_at` field.
        # Note: TTL indexes only work on BSON `Date` fields, so we
        # ALSO store `created_at_dt` as a Date. The Date duplicate is
        # only used by the TTL; read paths use the ISO string.
        await db.feature_events.create_index(
            "created_at_dt", expireAfterSeconds=90 * 24 * 3600,
            name="feature_events_ttl_90d",
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        # Compound for funnel queries: account_id × event_type
        await db.feature_events.create_index(
            [("account_id", 1), ("event_type", 1), ("created_at", -1)],
            name="feature_events_account_type",
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        # Compound for cohort funnel: cohort_tag × event_type
        await db.feature_events.create_index(
            [("cohort_tag", 1), ("event_type", 1), ("created_at", -1)],
            name="feature_events_cohort_type",
        )
    except Exception:  # noqa: BLE001
        pass
