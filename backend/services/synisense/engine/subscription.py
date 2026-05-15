"""Synisense Engine — subscription stub (Phase A).

Phase A returns `{subscription_id, status: "pending"}` for every
request. Real delivery (webhook / stream / poll) is Phase F.

We still persist the subscription so Phase F can pick up existing
subscribers without consumer-side migration.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from core import db

from services.synisense.models import SubscriptionRequest, SubscriptionResponse

SUBSCRIPTION_COLLECTION = "synisense_subscriptions"


async def create(req: SubscriptionRequest, *, tenant_id: str) -> SubscriptionResponse:
    sid = "sub-" + uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    row: Dict[str, Any] = {
        "subscription_id": sid,
        "tenant_id": tenant_id,
        "consumer_id": req.consumer_id,
        "signal_types": req.signal_types,
        "delivery": req.delivery,
        "webhook_url": req.webhook_url,
        "status": "pending",
        "created_at": now,
    }
    await db[SUBSCRIPTION_COLLECTION].insert_one(row)
    return SubscriptionResponse(
        subscription_id=sid, status="pending", delivery=req.delivery, created_at=now,
    )
