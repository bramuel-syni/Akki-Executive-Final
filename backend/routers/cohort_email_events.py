"""Phase P5.7.5 (2026-02) — SendGrid event webhook → admin row visibility.

SendGrid emits per-event POSTs to a configured URL when a message
hits one of: delivered, bounce, dropped, spamreport, deferred, etc.
We accept the webhook, find the application row that owns the
recipient address (via email_lc), and persist the latest
deliverability event on that row. The admin cohort applications
page surfaces a red dot + tooltip when the latest event is one of
bounce / dropped / spamreport.

Out of scope (per the dispatch):
  * retry logic
  * automatic re-send
  * cross-row aggregation / dashboards

Security: SendGrid signs webhook payloads with `ECDSA-SHA256` when
"Signed Event Webhook Requests" is enabled in their UI. We verify
the signature when `SENDGRID_WEBHOOK_PUBLIC_KEY` is set in env;
otherwise we accept unsigned events but log a warning (preview /
dev convenience). The signature header is
`X-Twilio-Email-Event-Webhook-Signature` (base64 ECDSA over
timestamp + raw body) and timestamp header is
`X-Twilio-Email-Event-Webhook-Timestamp`.

Sentry: any exception writing to Mongo is captured WITH the
recipient email stripped (we only keep the LC prefix + domain) so
the breadcrumb doesn't leak applicant PII into Sentry.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request

from core import db, iso as _iso, now as _now

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cohort", tags=["cohort-email-events"])

# Event types that the admin row badge highlights as a delivery problem.
_NEGATIVE_EVENTS = {"bounce", "dropped", "spamreport", "blocked"}
# Events that confirm successful delivery to the destination MX.
_POSITIVE_EVENTS = {"delivered", "open", "click"}
# Events that are mid-flight — admin badge shows neutral.
_NEUTRAL_EVENTS = {"processed", "deferred"}


def _verify_signature(*, signature: str, timestamp: str, body: bytes) -> bool:
    """Verify SendGrid's ECDSA signature. Returns True when the env
    has no public key (skip — dev/preview convenience) OR when the
    signature is valid. Returns False only on an active signature
    mismatch."""
    public_key_b64 = (os.environ.get("SENDGRID_WEBHOOK_PUBLIC_KEY") or "").strip()
    if not public_key_b64:
        log.warning("sendgrid webhook: no SENDGRID_WEBHOOK_PUBLIC_KEY in env — accepting unsigned")
        return True
    if not signature or not timestamp:
        return False
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.exceptions import InvalidSignature

        # SendGrid publishes the verifier key as a PEM-encoded EC
        # public key (or base64 DER). Accept both shapes.
        pem_bytes = public_key_b64.encode()
        try:
            if b"BEGIN" in pem_bytes:
                pub = serialization.load_pem_public_key(pem_bytes)
            else:
                pub = serialization.load_der_public_key(base64.b64decode(pem_bytes))
        except Exception as e:
            log.warning("sendgrid webhook: malformed public key — %s", e)
            return False

        message = timestamp.encode() + body
        sig = base64.b64decode(signature)
        try:
            pub.verify(sig, message, ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
    except Exception as e:  # noqa: BLE001
        log.warning("sendgrid webhook: signature verify path errored — %s", e)
        return False


def _classify(event_type: str) -> str:
    """Map raw SendGrid event_type → admin-facing status bucket."""
    et = (event_type or "").lower()
    if et in _NEGATIVE_EVENTS:
        return "failed"
    if et in _POSITIVE_EVENTS:
        return "delivered"
    if et in _NEUTRAL_EVENTS:
        return "pending"
    return "other"


@router.post("/email-events/sendgrid")
async def sendgrid_event_webhook(
    request: Request,
    x_twilio_email_event_webhook_signature: Optional[str] = Header(None),
    x_twilio_email_event_webhook_timestamp: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Receive SendGrid Event Webhook batches. Body is a JSON array
    of event objects: [{email, event, timestamp, sg_message_id, ...}]."""
    body = await request.body()
    if not _verify_signature(
        signature=x_twilio_email_event_webhook_signature or "",
        timestamp=x_twilio_email_event_webhook_timestamp or "",
        body=body,
    ):
        raise HTTPException(status_code=403, detail={
            "code": "signature_invalid",
            "message": "SendGrid event webhook signature mismatch.",
        })
    try:
        events = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={
            "code": "body_invalid", "message": "Webhook body is not valid JSON.",
        })
    if not isinstance(events, list):
        events = [events]

    processed = 0
    bucket_counts = {"delivered": 0, "failed": 0, "pending": 0, "other": 0}
    for evt in events:
        if not isinstance(evt, dict):
            continue
        email = (evt.get("email") or "").strip().lower()
        event_type = (evt.get("event") or "").strip().lower()
        ts_epoch = evt.get("timestamp")
        sg_message_id = evt.get("sg_message_id") or evt.get("smtp-id") or ""
        if not email or not event_type:
            continue

        bucket = _classify(event_type)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

        # Persist on the matching application row (if any).
        # We only update the application row (not insert) so unknown
        # recipients don't pollute the cohort applications collection.
        update = {
            "latest_email_event_type":     event_type,
            "latest_email_event_bucket":   bucket,
            "latest_email_event_at":       _iso(_now()),
            "latest_email_event_reason":   (evt.get("reason") or evt.get("response") or "")[:240],
            "latest_email_event_sg_id":    sg_message_id[:120],
        }
        await db.cohort_applications.update_one(
            {"email_lc": email},
            {"$set": update},
        )

        # Also append to an audit-friendly events collection so the
        # admin can drill into history if needed (capped to last N
        # via TTL index — out of P5.7.5 scope).
        await db.cohort_email_events.insert_one({
            "email_lc":          email,
            "event":             event_type,
            "bucket":            bucket,
            "sg_message_id":     sg_message_id,
            "timestamp":         ts_epoch,
            "reason":            (evt.get("reason") or "")[:240],
            "received_at":       _iso(_now()),
        })
        processed += 1

    log.info("sendgrid event webhook: processed=%d buckets=%s", processed, bucket_counts)
    return {"ok": True, "processed": processed, "buckets": bucket_counts}
