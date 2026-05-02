"""Phase 10 / Item C — Stripe webhook hardening.

Responsibilities separated from the router so the signature
verification + idempotency + dead-letter logic is unit-testable.

  * ``verify_and_parse_event(raw_body, sig_header)``
      - Verifies the ``Stripe-Signature`` header against
        ``STRIPE_WEBHOOK_SECRET``. Raises :class:`SignatureInvalid`
        on any failure. **Never** trusts the body before verify.
  * ``is_replay(event_id)`` / ``record_event(event_id)``
      - Idempotency via ``db.stripe_events`` with a 30-day TTL.
  * ``dead_letter(event, reason)``
      - Anything unhandled is stored raw in ``db.stripe_dead_letter``.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("akki.stripe_webhook")


class SignatureInvalid(Exception):
    pass


STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY", "")


def configured() -> Dict[str, bool]:
    return {
        "api_key": bool(STRIPE_API_KEY),
        "webhook_secret": bool(STRIPE_WEBHOOK_SECRET),
    }


def verify_and_parse_event(raw_body: bytes, sig_header: Optional[str]) -> Dict[str, Any]:
    """Verify signature, return the parsed event dict.

    Raises :class:`SignatureInvalid` if the secret is unset, the
    header is missing or the signature does not match.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise SignatureInvalid("STRIPE_WEBHOOK_SECRET is not set")
    if not sig_header:
        raise SignatureInvalid("missing Stripe-Signature header")
    try:
        import stripe  # lazy import
        event = stripe.Webhook.construct_event(
            payload=raw_body, sig_header=sig_header, secret=STRIPE_WEBHOOK_SECRET,
        )
    except ImportError as e:
        raise SignatureInvalid(f"stripe library unavailable: {e}") from e
    except Exception as e:  # noqa: BLE001 — Stripe SDK raises a family of errors
        raise SignatureInvalid(str(e)) from e
    return event


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
