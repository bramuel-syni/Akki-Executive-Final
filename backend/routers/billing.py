"""Billing — "Coming Soon" UX (chunk c, 2026-05-25).

The earlier §M4 Stripe integration is replaced by an honest "Coming
Soon" surface. Real Stripe checkout flows are NOT shipped in the
preview release; the user has explicitly opted to surface this to
end-users instead of running a silent-fake-success mock.

Endpoints kept (now read-only / coming-soon-aware):
  - GET  /api/billing/plans                returns the catalog with a
                                           ``coming_soon: true`` marker
  - GET  /api/billing/me                   returns the user's current
                                           plan + ``coming_soon: true``
  - POST /api/billing/checkout             returns 200 with
                                           ``{coming_soon: true, message}``
                                           — NEVER a Stripe URL. The
                                           verbatim copy is the
                                           Coming-Soon body text.
  - GET  /api/billing/status/{session_id}  returns 200 with
                                           ``{coming_soon: true}``.
                                           The session_id is treated
                                           opaquely — no Stripe call.
  - POST /api/webhook/stripe               kept for shape-compat with
                                           any upstream caller. Returns
                                           ``{coming_soon: true,
                                           accepted: false}`` and writes
                                           an audit entry so the operator
                                           sees attempted webhook hits.
                                           Signature is NOT verified
                                           because no Stripe is wired.
  - POST /api/notify-billing-launch        NEW. Records the requester's
                                           account id + UTC timestamp in
                                           ``billing_launch_interest``.
                                           Set-if-not-exists; second
                                           POST returns
                                           ``{already_subscribed: true}``.

The catalog itself (free/pro/team + names + features + price labels)
remains in this file as a static reference so the UI can render the
"what you'll get later" preview if needed. Pricing strings remain for
operator reference only; the frontend MUST NOT charge against them.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from core import db, now as _now, iso as _iso, get_current_account, write_audit

logger = logging.getLogger("akki.billing")

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Verbatim copy — chunk (c) ratified at orchestrator's 2026-05-25 brief.
# Kept as module constants so test_chunk_c_billing_coming_soon.py can
# verbatim-assert without re-typing the text.
# ---------------------------------------------------------------------------
COMING_SOON_HEADING = "Billing & Subscription — Coming Soon"
COMING_SOON_BODY = (
    "We're finalizing our subscription tiers. Your account is fully "
    "active during this preview period; billing will roll out in a "
    "future release."
)
COMING_SOON_CTA = "Notify me when this is ready"

# ---------------------------------------------------------------------------
# Plan catalog — informational. The UI renders these as a preview only;
# no checkout flow is reachable.
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
        "cta": "Coming soon",
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
        "cta": "Coming soon",
    },
}


# ---------------------------------------------------------------------------
# Public catalog
# ---------------------------------------------------------------------------
@router.get("/billing/plans")
async def list_plans():
    """Read-only plan catalog. The ``coming_soon`` flag is asserted at
    the top level so any frontend that lands here gets the honest
    response — no fake "Upgrade now" CTA wiring is possible."""
    return {
        "plans": list(PLANS.values()),
        "coming_soon": True,
        "message": COMING_SOON_BODY,
    }


# ---------------------------------------------------------------------------
# Account-aware
# ---------------------------------------------------------------------------
@router.get("/billing/me")
async def get_my_plan(current: Dict[str, Any] = Depends(get_current_account)):
    """Current plan for the authenticated user. Always marks
    ``coming_soon: true`` so the frontend renders the Coming-Soon
    surface even if the account already has ``plan: pro`` from an
    earlier preview-period grant."""
    plan_id = current.get("plan") or "free"
    return {
        "plan": PLANS.get(plan_id, PLANS["free"]),
        "stripe_customer_id": None,
        "subscription_status": current.get("subscription_status"),
        "coming_soon": True,
        "message": COMING_SOON_BODY,
    }


class CheckoutIn(BaseModel):
    plan_id: PlanId
    origin_url: str = Field(min_length=8, max_length=400,
                            description="window.location.origin from the browser")


@router.post("/billing/checkout")
async def create_checkout(
    body: CheckoutIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Coming-Soon stub. The frontend should NEVER reach this endpoint
    — the BillingTab UI surfaces the Coming-Soon page directly and has
    no Stripe CTA — but if anything (an old SPA build, a stale
    bookmark, a curl test) DOES hit it, the response is honest:
    ``{coming_soon: true, message: <verbatim body>}``.

    A receipt is written to the audit log so the operator sees that
    someone attempted a checkout."""
    await write_audit(
        None, current["id"], "billing.checkout_attempted_coming_soon", "plan",
        body.plan_id, {"origin_url": body.origin_url},
    )
    return {
        "coming_soon": True,
        "message": COMING_SOON_BODY,
        "plan_id": body.plan_id,
    }


@router.get("/billing/status/{session_id}")
async def get_checkout_status(
    session_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Coming-Soon stub. The session_id is treated opaquely — no
    Stripe call is made. Returns ``{coming_soon: true}`` so legacy
    poll loops degrade gracefully to "still coming soon"."""
    return {
        "coming_soon": True,
        "message": COMING_SOON_BODY,
        "session_id": session_id,
        "payment_status": "coming_soon",
        "status": "coming_soon",
    }


# ---------------------------------------------------------------------------
# Webhook stub — Stripe is not wired. Any inbound webhook hits are
# logged + dead-lettered so the operator sees the attempt, but no
# signature verification is performed and no account.plan is flipped.
# ---------------------------------------------------------------------------
@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Coming-Soon stub. Stripe isn't wired in this release — any
    inbound webhook is recorded to the audit log + dead-lettered into
    ``stripe_dead_letter`` for operator visibility, then a
    ``{coming_soon: true, accepted: false}`` response is returned.

    A ``200`` (not ``400``) is intentional — Stripe will keep
    retrying on 4xx; we want them to stop. The dead-letter row is
    sufficient for the operator to manually replay later once
    billing actually ships."""
    raw = b""
    try:
        raw = await request.body()
    except Exception:  # noqa: BLE001
        pass

    sig = request.headers.get("Stripe-Signature") or ""
    await db.stripe_dead_letter.insert_one({
        "id": f"coming_soon_{_iso(_now())}",
        "received_at": _iso(_now()),
        "signature_header": sig[:80],
        "body_prefix": raw[:200].decode("utf-8", errors="replace") if raw else "",
        "reason": "coming_soon_no_stripe_wired",
    })
    logger.info("billing.webhook_received_coming_soon size=%d", len(raw))
    return {
        "coming_soon": True,
        "accepted": False,
        "message": COMING_SOON_BODY,
    }


# ---------------------------------------------------------------------------
# Notify me when billing launches — set-if-not-exists.
# ---------------------------------------------------------------------------
class NotifyOut(BaseModel):
    """Response shape for both first-time + repeat POST."""
    coming_soon: bool
    notified: bool
    already_subscribed: bool
    message: str


@router.post("/notify-billing-launch", response_model=NotifyOut)
async def notify_billing_launch(
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Records the authenticated account's interest in being notified
    when billing actually ships. Idempotent — second POST does NOT
    duplicate the row; instead the ``already_subscribed`` flag is set.

    The Mongo collection ``billing_launch_interest`` carries:
        - account_id   : the user's account id
        - account_email: cached email at signup time (audit only)
        - subscribed_at: ISO UTC timestamp of first subscription
        - source       : "notify_billing_launch" (literal, future-
                         proof if we ever add other notify-me funnels)
    """
    account_id = current["id"]
    existing = await db.billing_launch_interest.find_one(
        {"account_id": account_id}, {"_id": 0, "subscribed_at": 1},
    )
    if existing:
        return NotifyOut(
            coming_soon=True,
            notified=True,
            already_subscribed=True,
            message=COMING_SOON_BODY,
        )

    await db.billing_launch_interest.insert_one({
        "account_id": account_id,
        "account_email": current.get("email") or "",
        "subscribed_at": _iso(_now()),
        "source": "notify_billing_launch",
    })
    await write_audit(
        None, account_id, "billing.notify_launch_subscribed", "billing",
        "launch", {},
    )
    return NotifyOut(
        coming_soon=True,
        notified=True,
        already_subscribed=False,
        message=COMING_SOON_BODY,
    )
