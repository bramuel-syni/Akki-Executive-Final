"""P5.17 — Upstream read-side adapter helpers.

`origin` envelope structure attached to backfilled primary-collection
rows so the FE can render the small "📧 From email" chip + the
source-message modal.

Envelope shape (kept lean; the wire payload is small enough that a
listing of 200 tasks doesn't bloat past ~2 KB on this field alone):

  {
    "source":          "email_akki",
    "message_id":      "<source admin_inbox_messages.id>",
    "routed_at":       "<ISO>",
    "confidence_band": "low" | "medium" | "high",
    "decision_source": "auto" | "human" | "override",
  }

`source` is a single string today (`"email_akki"`); future origin
classes (e.g. `"slack_akki"`, `"calendar_akki"`) drop in without
changing the envelope shape.

The envelope is also persisted on the source row directly (e.g. on
the `tasks` collection) — the upstream adapter does not read from
`inbox_routing_log` at serve time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

ORIGIN_EMAIL_AKKI = "email_akki"


def build_origin_envelope(
    *,
    message_id: str,
    confidence_band: str,
    decision_source: str = "auto",
    routed_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Pure — returns the dict. Callers persist as-is on the row."""
    return {
        "source":          ORIGIN_EMAIL_AKKI,
        "message_id":      message_id,
        "routed_at":       routed_at or datetime.now(timezone.utc).isoformat(),
        "confidence_band": confidence_band,
        "decision_source": decision_source,
    }


def is_email_akki_origin(origin: Optional[Dict[str, Any]]) -> bool:
    """True iff the row's origin envelope points at the email-akki
    source. Helper for the `?origin=` filter on listing endpoints."""
    return bool(origin) and origin.get("source") == ORIGIN_EMAIL_AKKI


__all__ = [
    "ORIGIN_EMAIL_AKKI",
    "build_origin_envelope",
    "is_email_akki_origin",
]
