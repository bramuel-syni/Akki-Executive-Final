"""§M4 Stripe Billing.

Plans are fixed server-side (Free / Pro / Team); the frontend never sends
amounts. Frontend supplies its origin URL only — the backend builds the
Stripe success/cancel URLs from it. A `payment_transactions` row is
created BEFORE the redirect so we can reconcile via webhook + polling
without double-applying.

Endpoints:
  - GET  /api/billing/plans                   public, returns the fixed catalog
  - GET  /api/billing/me                      auth, returns current account.plan
  - POST /api/billing/checkout                auth, body {plan_id, origin_url}
  - GET  /api/billing/status/{session_id}     auth, polls Stripe for status
  - POST /api/webhook/stripe                  Stripe webhook endpoint
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, now as _now, iso as _iso, get_current_account, write_audit

# Lazy-imported below — only when STRIPE_API_KEY is present.
logger = logging.getLogger("akki.billing")

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Plan catalog — server-side source of truth.
# ---------------------------------------------------------------------------
PlanId = Literal["free", "pro", "team"]

PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free",
        "tagline": "Read sharper on one board.",
        "price_usd": 0.0,
        "interval": "month",
        "features": [
            "1 active context",
            "Briefings + Signals + Ask",
            "Manual reporting cycles (you click Draft each time)",
            "Community support",
        ],
        "cta": "Current",
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "tagline": "Everything you need to run multiple boards calmly.",
        "price_usd": 29.0,
        "interval": "month",
        "features": [
            "Unlimited contexts",
            "Reporting Cycle dispatch via Resend",
            "Recurring schedule cron",
            "Polish-with-AKKI report editor",
            "Priority email support",
        ],
        "cta": "Upgrade to Pro",
    },
    "team": {
        "id": "team",
        "name": "Team",
        "tagline": "For boards & exec teams who collaborate.",
        "price_usd": 99.0,
        "interval": "month",
        "features": [
            "Everything in Pro",
            "Up to 5 shared seats",
            "Cross-context commentary + @mentions",
            "Audit log export",
            "SSO on request",
        ],
        "cta": "Upgrade to Team",
    },
}


class CheckoutIn(BaseModel):
    plan_id: PlanId
    origin_url: str = Field(min_length=8, max_length=400,
                            description="window.location.origin from the browser")


def _billing_enabled() -> bool:
    return (os.environ.get("BILLING_ENABLED") or "").lower() in ("1", "true", "yes")


def _stripe() -> Any:
    """Lazy import + guard. Returns a configured StripeCheckout or raises 503.

    Phase 10 change: the ``sk_test_emergent`` default is gone. If
    ``BILLING_ENABLED=true`` is set and ``STRIPE_SECRET_KEY`` is unset,
    the process refuses to boot (see ``server.py`` startup check).
    When BILLING_ENABLED is off, this raises 503 so the caller never
    reaches a partially-real Stripe path.
    """
    if not _billing_enabled():
        raise HTTPException(status_code=503, detail="Billing is disabled in this environment.")
    api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="STRIPE_SECRET_KEY is not configured.")
    from emergentintegrations.payments.stripe.checkout import StripeCheckout  # noqa: WPS433
    return StripeCheckout(api_key=api_key, webhook_url="")


# ---------------------------------------------------------------------------
# Public catalog
# ---------------------------------------------------------------------------
@router.get("/billing/plans")
async def list_plans():
    return {"plans": list(PLANS.values())}


# ---------------------------------------------------------------------------
# Account-aware
# ---------------------------------------------------------------------------
@router.get("/billing/me")
async def get_my_plan(current: Dict[str, Any] = Depends(get_current_account)):
    plan_id = current.get("plan") or "free"
    return {
        "plan": PLANS.get(plan_id, PLANS["free"]),
        "stripe_customer_id": current.get("stripe_customer_id"),
        "subscription_status": current.get("subscription_status"),
    }


@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Frontend supplies origin only. Backend reads the fixed amount from PLANS,
    constructs success/cancel URLs, creates a Stripe session, and writes a
    pending row to `payment_transactions`."""
    plan = PLANS.get(body.plan_id)
    if not plan or plan["price_usd"] <= 0:
        raise HTTPException(status_code=400, detail="Unknown or non-billable plan.")

    from emergentintegrations.payments.stripe.checkout import (  # noqa: WPS433
        CheckoutSessionRequest,
    )
    sc = _stripe()
    success_url = f"{body.origin_url.rstrip('/')}/app/settings/billing?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{body.origin_url.rstrip('/')}/app/settings/billing?cancelled=1"
    metadata = {
        "account_id": current["id"],
        "account_email": current["email"],
        "plan_id": plan["id"],
        "source": "akki_billing",
    }
    req = CheckoutSessionRequest(
        amount=float(plan["price_usd"]),
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await sc.create_checkout_session(req)

    # MANDATORY: persist a pending row before returning.
    txn = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "account_id": current["id"],
        "account_email": current["email"],
        "plan_id": plan["id"],
        "amount_usd": float(plan["price_usd"]),
        "currency": "usd",
        "metadata": metadata,
        "payment_status": "pending",
        "status": "initiated",
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
    }
    await db.payment_transactions.insert_one(txn.copy())
    await write_audit(None, current["id"], "billing.checkout_initiated", "plan",
                      plan["id"], {"session_id": session.session_id})
    return {"url": session.url, "session_id": session.session_id}


@router.get("/billing/status/{session_id}")
async def get_checkout_status(
    session_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Polled by the frontend after Stripe redirects back. Idempotent — flips
    the account.plan only on the first transition from pending → paid."""
    txn = await db.payment_transactions.find_one(
        {"session_id": session_id, "account_id": current["id"]}, {"_id": 0},
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    sc = _stripe()
    # The emergentintegrations SDK with sk_test_emergent may not be able to
    # retrieve the very session it created (proxy/account mismatch).
    # We degrade gracefully: if retrieve fails, fall back to the persisted
    # row so the poll loop doesn't crash. Webhook (or a future upgrade) will
    # eventually flip the row.
    persisted_payment = (txn.get("payment_status") or "pending")
    persisted_session = (txn.get("status") or "initiated")
    try:
        status = await sc.get_checkout_status(session_id)
        payment_status = (status.payment_status or "").lower()
        session_status = (status.status or "").lower()
        amount_total_cents = status.amount_total
        currency = status.currency
    except Exception as e:  # noqa: BLE001
        logger.warning("Stripe retrieve failed for %s: %s", session_id, e)
        payment_status = persisted_payment
        session_status = persisted_session
        amount_total_cents = int(round(float(txn.get("amount_usd", 0)) * 100))
        currency = txn.get("currency", "usd")

    # Only apply the upgrade ONCE per session
    already_applied = txn.get("payment_status") == "paid"
    if payment_status == "paid" and not already_applied:
        await db.accounts.update_one(
            {"id": current["id"]},
            {"$set": {
                "plan": txn["plan_id"],
                "subscription_status": "active",
                "plan_updated_at": _iso(_now()),
            }},
        )
        await write_audit(None, current["id"], "billing.upgraded", "plan",
                          txn["plan_id"], {"session_id": session_id})

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": payment_status or "pending",
            "status": session_status or txn.get("status"),
            "updated_at": _iso(_now()),
        }},
    )
    return {
        "session_id": session_id,
        "payment_status": payment_status,
        "status": session_status,
        "plan_id": txn["plan_id"],
        "amount_total_cents": amount_total_cents,
        "currency": currency,
    }


# ---------------------------------------------------------------------------
# Webhook (Phase 10 hardening).
#
#   - ``Stripe-Signature`` header verified against ``STRIPE_WEBHOOK_SECRET``.
#     Unset or invalid → 400.
#   - Idempotency via ``db.stripe_events`` (TTL 30 d). Replays are no-ops.
#   - Unhandled event types are persisted to ``db.stripe_dead_letter``
#     (TTL 90 d) with the full event so an operator can inspect + replay.
# ---------------------------------------------------------------------------
_HANDLED_EVENT_TYPES = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "customer.subscription.deleted",
    "customer.subscription.updated",
}


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    from services import stripe_webhook as sw

    raw = await request.body()
    sig = request.headers.get("Stripe-Signature")
    try:
        event = sw.verify_and_parse_event(raw, sig)
    except sw.SignatureInvalid as e:
        logger.warning("stripe webhook rejected: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")

    # Stripe's SDK returns a StripeObject — normalise to a dict for storage.
    event_dict = dict(event) if not isinstance(event, dict) else event
    event_id = event_dict.get("id") or ""
    event_type = event_dict.get("type") or ""

    if await sw.is_replay(db, event_id):
        return {"ok": True, "replay": True, "event_id": event_id}
    await sw.record_event(db, event_id, event_type)

    if event_type not in _HANDLED_EVENT_TYPES:
        await sw.dead_letter(db, event_dict, reason=f"unhandled_event_type:{event_type}")
        return {"ok": True, "dead_lettered": True, "event_id": event_id, "type": event_type}

    # Apply the state change. All supported types carry the session id
    # on ``data.object``; subscription events carry a customer id.
    data_obj = (event_dict.get("data") or {}).get("object") or {}
    session_id = data_obj.get("id") if event_type.startswith("checkout.session.") else None
    customer_id = data_obj.get("customer") if event_type.startswith("customer.subscription.") else None

    if session_id:
        txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not txn:
            await sw.dead_letter(db, event_dict, reason="no_matching_transaction")
            return {"ok": True, "dead_lettered": True, "event_id": event_id, "reason": "no_txn"}
        payment_status = (data_obj.get("payment_status") or "").lower() or "paid"
        if event_type == "checkout.session.async_payment_failed":
            payment_status = "failed"
        if payment_status == "paid" and txn.get("payment_status") != "paid":
            await db.accounts.update_one(
                {"id": txn["account_id"]},
                {"$set": {
                    "plan": txn["plan_id"],
                    "subscription_status": "active",
                    "plan_updated_at": _iso(_now()),
                }},
            )
            await write_audit(
                None, txn["account_id"], "billing.upgraded", "plan",
                txn["plan_id"], {"session_id": session_id, "event_id": event_id},
            )
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": payment_status,
                "webhook_event_type": event_type,
                "webhook_event_id": event_id,
                "updated_at": _iso(_now()),
            }},
        )
        return {"ok": True, "event_id": event_id, "payment_status": payment_status}

    if customer_id and event_type == "customer.subscription.deleted":
        # Downgrade: flip the account's plan back to "free". We look the
        # account up by stripe_customer_id (populated on the upgrade path).
        account = await db.accounts.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "id": 1})
        if account:
            await db.accounts.update_one(
                {"id": account["id"]},
                {"$set": {
                    "plan": "free",
                    "subscription_status": "canceled",
                    "plan_updated_at": _iso(_now()),
                }},
            )
            await write_audit(
                None, account["id"], "billing.downgraded", "plan",
                "free", {"stripe_customer_id": customer_id, "event_id": event_id},
            )
        return {"ok": True, "event_id": event_id, "downgraded": bool(account)}

    # A handled type we recognised but didn't find a target for.
    await sw.dead_letter(db, event_dict, reason=f"handled_but_no_target:{event_type}")
    return {"ok": True, "dead_lettered": True, "event_id": event_id}
