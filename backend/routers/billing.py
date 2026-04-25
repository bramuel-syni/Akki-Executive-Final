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


def _stripe() -> Any:
    """Lazy import + guard. Returns a configured StripeCheckout or raises 503."""
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Stripe not configured.")
    from emergentintegrations.payments.stripe.checkout import StripeCheckout  # noqa: WPS433
    # The webhook URL is filled by Stripe; emergentintegrations expects it
    # at construction time but the same SDK call is used for both create + status.
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
    status = await sc.get_checkout_status(session_id)
    payment_status = (status.payment_status or "").lower()
    session_status = (status.status or "").lower()

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
        "amount_total_cents": status.amount_total,
        "currency": status.currency,
    }


# ---------------------------------------------------------------------------
# Webhook (also catches checkout.session.completed + subscription.deleted)
# ---------------------------------------------------------------------------
@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    sc = _stripe()
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")
    try:
        evt = await sc.handle_webhook(payload, sig)
    except Exception as e:
        logger.exception("Stripe webhook verify failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")

    sid = getattr(evt, "session_id", None)
    if not sid:
        return {"ok": True, "ignored": True, "reason": "no session_id"}

    txn = await db.payment_transactions.find_one({"session_id": sid}, {"_id": 0})
    if not txn:
        logger.warning("Stripe webhook for unknown session %s", sid)
        return {"ok": True, "ignored": True, "reason": "no_txn"}

    payment_status = (getattr(evt, "payment_status", "") or "").lower()
    if payment_status == "paid" and txn.get("payment_status") != "paid":
        await db.accounts.update_one(
            {"id": txn["account_id"]},
            {"$set": {
                "plan": txn["plan_id"],
                "subscription_status": "active",
                "plan_updated_at": _iso(_now()),
            }},
        )
    await db.payment_transactions.update_one(
        {"session_id": sid},
        {"$set": {
            "payment_status": payment_status or txn.get("payment_status"),
            "webhook_event_type": getattr(evt, "event_type", None),
            "webhook_event_id": getattr(evt, "event_id", None),
            "updated_at": _iso(_now()),
        }},
    )
    return {"ok": True}
