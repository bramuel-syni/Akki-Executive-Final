"""Stripe webhook helpers — idempotency + dead-letter plumbing.

Chunk (c) closeout (2026-05-25): the Stripe signature verification
helper (``verify_and_parse_event``) and its companion
``SignatureInvalid`` exception were DELETED to pin the strict
zero-Stripe-SDK invariant. That function contained a lazy
load of the Stripe SDK that, while never reached at runtime under
the Coming-Soon contract, still appeared in source and tripped
the codebase grep audit.

What remains is purely Mongo-side plumbing (TTL indexes + replay
tracking + dead-letter writes) that the Coming-Soon webhook stub
in ``routers/billing.py`` may still call. None of it loads the
Stripe SDK.

  * ``configured()`` — env-flag probe (useful for ops dashboards).
  * ``is_replay(event_id)`` / ``record_event(event_id)`` — idempotency
    via ``db.stripe_events`` with a 30-day TTL.
  * ``ensure_indexes(db)`` — additive TTL index creation at startup.
  * ``dead_letter(db, event, reason)`` — writes raw event payloads
    into ``db.stripe_dead_letter`` for operator inspection.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

logger = logging.getLogger("akki.stripe_webhook")


STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY", "")


def configured() -> Dict[str, bool]:
    return {
        "api_key": bool(STRIPE_API_KEY),
        "webhook_secret": bool(STRIPE_WEBHOOK_SECRET),
    }


async def is_replay(db, event_id: str) -> bool:
    if not event_id:
        return False
    existing = await db.stripe_events.find_one({"_id": event_id}, {"_id": 1})
    return existing is not None


async def record_event(db, event_id: str, event_type: str) -> None:
    if not event_id:
        return
    now = datetime.now(timezone.utc)
    await db.stripe_events.update_one(
        {"_id": event_id},
        {
            "$setOnInsert": {
                "_id": event_id,
                "type": event_type,
                "received_at": now.isoformat(),
                "expires_at": now + timedelta(days=30),
            }
        },
        upsert=True,
    )


async def ensure_indexes(db) -> None:
    """Called once at startup — indexes are additive."""
    try:
        await db.stripe_events.create_index("expires_at", expireAfterSeconds=0)
        await db.stripe_dead_letter.create_index("received_at", expireAfterSeconds=0)
    except Exception as e:  # noqa: BLE001
        logger.warning("stripe idempotency index create failed: %s", e)


async def dead_letter(db, event: Dict[str, Any], reason: str) -> None:
    now = datetime.now(timezone.utc)
    await db.stripe_dead_letter.insert_one({
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "received_at": now.isoformat(),
        # Dead-letter rows live for 90 days by default — long enough for
        # an operator to inspect, short enough that we don't accumulate
        # webhook history forever.
        "expires_at": now + timedelta(days=90),
        "reason": reason,
        "raw": event,
    })

