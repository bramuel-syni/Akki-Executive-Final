"""Chunk (c) — Billing & Subscription "Coming Soon" UX.

The earlier §M4 Stripe checkout has been replaced by an honest
Coming-Soon surface. These tests enforce:

  C.B1 — `/api/billing/plans` returns the catalog AND a top-level
         ``coming_soon: true`` marker. Anyone hitting this endpoint
         (old SPA build, curl test, staleweb cache) gets the honest
         response, not a stripe URL.
  C.B2 — `/api/billing/me` returns the user's plan AND
         ``coming_soon: true`` AND the verbatim Coming-Soon body.
  C.B3 — `POST /api/billing/checkout` returns 200 with
         ``{coming_soon: true, message: <verbatim>}`` — NEVER a Stripe
         URL. This is the kill-switch on the previous fake-checkout
         behavior. An audit row is written for operator visibility.
  C.B4 — `GET /api/billing/status/{sid}` returns 200 with
         ``{coming_soon: true}`` regardless of session id. Legacy
         poll loops degrade gracefully.
  C.B5 — `POST /api/webhook/stripe` accepts inbound webhooks but
         dead-letters them (no signature verification, no plan flip).
         Returns 200 so Stripe stops retrying.
  C.B6 — `POST /api/notify-billing-launch` records the requester's
         interest. First call: ``already_subscribed: false`` +
         row inserted. Second call (idempotency): ``already_subscribed:
         true`` + NO duplicate row. Mongo row shape verified.
  C.B7 — Anti-regression — the billing module no longer imports the
         `emergentintegrations.payments.stripe.checkout` shim. A
         future regression that pulls Stripe back in breaks this.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app

REPO = Path(__file__).resolve().parents[2]
BILLING_ROUTER = REPO / "backend/routers/billing.py"

VERBATIM_HEADING = "Billing & Subscription — Coming Soon"
VERBATIM_BODY = (
    "We're finalizing our subscription tiers. Your account is fully "
    "active during this preview period; billing will roll out in a "
    "future release."
)
VERBATIM_CTA = "Notify me when this is ready"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register(c: httpx.AsyncClient, prefix: str):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!@#",
            "name": f"{prefix.title()} Tester",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["account"], body["contexts"][0]["id"]


# ── C.B1 — /billing/plans carries coming_soon: true ─────────────────
@pytest.mark.asyncio
async def test_c_b1_plans_returns_coming_soon():
    async with _client() as c:
        r = await c.get("/api/billing/plans")
        assert r.status_code == 200
        body = r.json()
        assert body.get("coming_soon") is True, body
        # Verbatim body copy reachable at the top level.
        assert body.get("message") == VERBATIM_BODY, body
        # Catalog still present — informational preview is allowed.
        plans = body.get("plans") or []
        assert {p["id"] for p in plans} == {"free", "pro", "team"}


# ── C.B2 — /billing/me carries coming_soon: true + verbatim body ────
@pytest.mark.asyncio
async def test_c_b2_me_returns_coming_soon_with_verbatim_body():
    async with _client() as c:
        token, _, _ = await _register(c, "c-b2")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get("/api/billing/me", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("coming_soon") is True, body
        assert body.get("message") == VERBATIM_BODY, body
        # Plan defaults to free for a fresh account.
        assert (body.get("plan") or {}).get("id") == "free"


# ── C.B3 — /billing/checkout returns coming_soon, NEVER a Stripe URL
@pytest.mark.asyncio
async def test_c_b3_checkout_returns_coming_soon_not_stripe_url():
    async with _client() as c:
        token, account, _ = await _register(c, "c-b3")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            "/api/billing/checkout",
            json={"plan_id": "pro", "origin_url": "https://example.com"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Coming-soon contract.
        assert body.get("coming_soon") is True, body
        assert body.get("message") == VERBATIM_BODY, body
        assert body.get("plan_id") == "pro", body
        # CRITICAL anti-regression — NO Stripe URL leaks.
        for key, val in body.items():
            if isinstance(val, str):
                assert "stripe.com" not in val.lower(), (
                    f"Stripe URL leaked through checkout response "
                    f"at key '{key}': {val}"
                )
        # An audit row records the attempt — operator visibility.
        audit_count = await core_mod.db.audit_log.count_documents({
            "account_id": account["id"],
            "action": "billing.checkout_attempted_coming_soon",
        })
        assert audit_count >= 1, "audit row missing for checkout attempt"
        # No payment_transactions row was created (the mocked side effect is gone).
        txn_count = await core_mod.db.payment_transactions.count_documents({
            "account_id": account["id"],
        })
        assert txn_count == 0, (
            f"payment_transactions row created for a coming-soon "
            f"account ({account['id']}) — fake-success behavior "
            f"regressed."
        )


# ── C.B4 — /billing/status returns coming_soon ──────────────────────
@pytest.mark.asyncio
async def test_c_b4_status_returns_coming_soon_for_any_session_id():
    async with _client() as c:
        token, _, _ = await _register(c, "c-b4")
        h = {"Authorization": f"Bearer {token}"}
        # Opaque session id — no Stripe call attempted.
        r = await c.get(
            "/api/billing/status/cs_nonexistent_session",
            headers=h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("coming_soon") is True
        assert body.get("payment_status") == "coming_soon"
        assert body.get("status") == "coming_soon"
        assert body.get("session_id") == "cs_nonexistent_session"


# ── C.B5 — webhook dead-letters + returns 200 ───────────────────────
@pytest.mark.asyncio
async def test_c_b5_stripe_webhook_dead_letters_no_signature_verify():
    """Stripe will keep retrying on 4xx — we need 200 so they stop.
    The webhook body is dead-lettered for operator visibility."""
    pre_count = await core_mod.db.stripe_dead_letter.count_documents({
        "reason": "coming_soon_no_stripe_wired",
    })
    async with _client() as c:
        r = await c.post(
            "/api/webhook/stripe",
            json={"id": "evt_test_chunk_c", "type": "checkout.session.completed"},
            headers={"Stripe-Signature": "t=123,v1=garbage"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("coming_soon") is True
        assert body.get("accepted") is False
    post_count = await core_mod.db.stripe_dead_letter.count_documents({
        "reason": "coming_soon_no_stripe_wired",
    })
    assert post_count == pre_count + 1, (
        f"webhook dead-letter row not written: pre={pre_count}, "
        f"post={post_count}"
    )


# ── C.B6 — /notify-billing-launch idempotent insert ─────────────────
@pytest.mark.asyncio
async def test_c_b6_notify_billing_launch_idempotent_insert():
    async with _client() as c:
        token, account, _ = await _register(c, "c-b6")
        h = {"Authorization": f"Bearer {token}"}
        # First call — inserts.
        r1 = await c.post("/api/notify-billing-launch", headers=h)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1.get("coming_soon") is True
        assert b1.get("notified") is True
        assert b1.get("already_subscribed") is False
        assert b1.get("message") == VERBATIM_BODY
        # Mongo row exists.
        row = await core_mod.db.billing_launch_interest.find_one(
            {"account_id": account["id"]}, {"_id": 0},
        )
        assert row is not None
        assert row["account_id"] == account["id"]
        assert row["source"] == "notify_billing_launch"
        assert row.get("subscribed_at")
        first_subscribed_at = row["subscribed_at"]
        # Second call — idempotent, no duplicate.
        r2 = await c.post("/api/notify-billing-launch", headers=h)
        assert r2.status_code == 200, r2.text
        b2 = r2.json()
        assert b2.get("coming_soon") is True
        assert b2.get("notified") is True
        assert b2.get("already_subscribed") is True
        # Mongo still has exactly one row + the subscribed_at is unchanged.
        count = await core_mod.db.billing_launch_interest.count_documents({
            "account_id": account["id"],
        })
        assert count == 1, f"duplicate row created on idempotent POST: count={count}"
        row2 = await core_mod.db.billing_launch_interest.find_one(
            {"account_id": account["id"]}, {"_id": 0, "subscribed_at": 1},
        )
        assert row2["subscribed_at"] == first_subscribed_at


# ── C.B7 — anti-regression: no Stripe SDK import in billing.py ──────
def test_c_b7_billing_module_no_stripe_sdk_import():
    """The Coming-Soon billing module MUST NOT import the Stripe SDK
    or the emergentintegrations Stripe checkout helper. A future
    regression that re-pulls Stripe (e.g. someone reverts the
    rewrite) breaks this test."""
    src = BILLING_ROUTER.read_text(encoding="utf-8")
    forbidden_imports = [
        "from emergentintegrations.payments.stripe.checkout import",
        "import stripe",
        "from stripe import",
    ]
    offenders = [s for s in forbidden_imports if s in src]
    assert not offenders, (
        f"Stripe SDK import regressed in routers/billing.py: "
        f"{offenders}. Chunk (c) Coming-Soon contract violated."
    )
    # Positive — the verbatim copy constants are present.
    assert 'COMING_SOON_HEADING = "Billing & Subscription — Coming Soon"' in src
    assert "We're finalizing our subscription tiers." in src
    assert 'COMING_SOON_CTA = "Notify me when this is ready"' in src
