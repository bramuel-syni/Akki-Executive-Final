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

Phase P5.19 (2026-02) — extended with signal + cycle_update
materialisers. Signals land in `db.signals` (context-scoped);
cycle updates land in `db.cycle_contributions` (context-scoped +
agenda/cycle-scoped). Both reuse the same origin envelope.
"""
from __future__ import annotations

import uuid
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


# ── Phase P5.19 — Signal + cycle_update materialisers ────────────


async def _existing_signal_for_routed(db, *, context_id: str,
                                        message_id: str) -> Optional[Dict[str, Any]]:
    return await db.signals.find_one(
        {
            "context_id": context_id,
            "origin.source": ORIGIN_EMAIL_AKKI,
            "origin.message_id": message_id,
        },
        {"_id": 0, "id": 1},
    )


async def materialize_signal_primary(
    db,
    *,
    message: Dict[str, Any],
    envelope,
    context_id: str,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Insert (or no-op on existing) a signal row in `db.signals`
    tagged with the email-akki origin envelope. Idempotency contract
    is `(context_id, origin.message_id)` — same shape as tasks.

    The signal shape is the minimum the Pulse feed serializer needs:
      id · context_id · surface_type · title · body · created_at
      · confidence (string band) · origin
    Other fields the Pulse feed reads (topic_class, freshness,
    actions_summary) default to safe values; the existing serializer
    treats them as optional."""
    existing = await _existing_signal_for_routed(
        db, context_id=context_id, message_id=message["id"],
    )
    if existing:
        return {"id": existing["id"], "status": "exists"}

    origin_env = build_origin_envelope(
        message_id=message["id"],
        confidence_band=envelope.confidence,
        decision_source=decision_source,
    )
    # Map classifier route_kind hint → signal surface_type. The
    # classifier's signal_kind hint is `concern` | `opportunity` |
    # `observation`; the Pulse serializer expects `risk` |
    # `opportunity` | `observation`.
    sig_kind_in = (envelope.target_hint.signal_kind or "observation")
    surface_type = {"concern": "risk", "opportunity": "opportunity"}.get(
        sig_kind_in, "observation",
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    sig_doc = {
        "id": "sig-akki-" + uuid.uuid4().hex[:12],
        "context_id": context_id,
        "surface_type": surface_type,
        "title": (message.get("subject") or "Email signal")[:240],
        "body": (envelope.citations[0].excerpt if envelope.citations else "")[:480],
        "topic_class": "operations",
        "freshness": "new",
        "confidence": envelope.confidence,
        "created_at": now_iso,
        "updated_at": now_iso,
        "origin": origin_env,
    }
    await db.signals.insert_one(dict(sig_doc))
    return {"id": sig_doc["id"], "status": "created"}


async def _existing_cycle_contribution_for_routed(db, *, context_id: str,
                                                    cycle_id: str,
                                                    message_id: str) -> Optional[Dict[str, Any]]:
    return await db.cycle_contributions.find_one(
        {
            "context_id": context_id,
            "agenda_id": cycle_id,
            "origin.source": ORIGIN_EMAIL_AKKI,
            "origin.message_id": message_id,
        },
        {"_id": 0, "id": 1},
    )


async def materialize_cycle_update_primary(
    db,
    *,
    message: Dict[str, Any],
    envelope,
    context_id: str,
    cycle_id: str,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Insert (or no-op on existing) a cycle_contributions row tagged
    with the email-akki origin envelope. Idempotency contract is
    `(context_id, agenda_id, origin.message_id)`."""
    existing = await _existing_cycle_contribution_for_routed(
        db, context_id=context_id, cycle_id=cycle_id,
        message_id=message["id"],
    )
    if existing:
        return {"id": existing["id"], "status": "exists"}

    origin_env = build_origin_envelope(
        message_id=message["id"],
        confidence_band=envelope.confidence,
        decision_source=decision_source,
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    contrib_doc = {
        "id": "cyc-contrib-akki-" + uuid.uuid4().hex[:10],
        "context_id": context_id,
        "agenda_id": cycle_id,
        "agenda_item_id": None,  # email-routed updates aren't bound to an item
        "team_member_id": None,
        "title": (message.get("subject") or "Email cycle update")[:240],
        "body_text": (
            message.get("text_body")
            or message.get("body_snippet")
            or ""
        )[:1200],
        "scores": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "origin": origin_env,
    }
    await db.cycle_contributions.insert_one(dict(contrib_doc))
    return {"id": contrib_doc["id"], "status": "created"}


__all__ = [
    "ORIGIN_EMAIL_AKKI",
    "build_origin_envelope",
    "is_email_akki_origin",
    "materialize_signal_primary",
    "materialize_cycle_update_primary",
]
