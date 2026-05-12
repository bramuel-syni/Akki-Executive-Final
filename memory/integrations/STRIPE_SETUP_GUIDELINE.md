# Stripe Setup Guideline — AKKI Billing

> Drafted 2026-05-12 by Patch 15-19 sprint. Work through sequentially; the order matters because some setup steps depend on earlier ones (e.g. webhook secret requires the endpoint to exist first).

---

## 1. Stripe account setup

1. Create or sign in to your Stripe account at https://dashboard.stripe.com/.
2. **Use the same email** that will own AKKI's billing — if you sign up under a personal email and later want to transfer to a company account, Stripe makes you migrate manually.
3. Complete the **Business profile** section:
   - Legal business name
   - Business type (UK Ltd / sole trader / partnership)
   - Business address
   - VAT number (if registered) — required for charging UK/EU customers VAT correctly
4. Enable the **UK** and any other countries you want to charge customers in. Stripe disables payouts in countries you haven't activated.

**Test mode vs Live mode**: Stripe's dashboard has a toggle (top-right). Treat them as completely separate environments:
- **Test mode** has its own API keys, products, prices, webhooks, customers. Use card `4242 4242 4242 4242` for happy-path tests, `4000 0000 0000 0002` for declines.
- **Live mode** is real money. Move to live mode only when production checkout is fully tested.

**Recommendation**: Do all wiring + acceptance testing in **test mode first**. Switch to live mode only on the cutover day.

## 2. Product + Price IDs

AKKI needs at minimum 3 tiers. Create one Product per tier, two Prices per product (monthly + annual). Suggested structure:

### Product 1 — `AKKI Solo`
For a single executive without an ExCo seat.
- **Price 1**: £29 / month, recurring monthly, GBP. Save the `price_xxxxx` ID.
- **Price 2**: £290 / year, recurring yearly, GBP (= 2 months free). Save the `price_xxxxx` ID.

### Product 2 — `AKKI Team`
For an ExCo with up to 5 seats.
- **Price 1**: £149 / month per seat (metered or per-seat — see below). Recurring monthly, GBP.
- **Price 2**: £1490 / year per seat (= 2 months free).
- **Seat model**: choose **per-seat licensing**, not metered. Set `usage_type=licensed`. AKKI tells Stripe how many active members the workspace has at the start of each billing cycle.

### Product 3 — `AKKI Enterprise`
For organisations with >5 seats + custom features (Azure private link, SOC-2 evidence pack, dedicated CSM).
- **Price 1**: £999 / month flat (negotiable; serve as the on-platform default; large customers move to off-platform invoicing).
- **Price 2**: £9990 / year flat.

Save **all 6 `price_*` IDs** — AKKI's backend will reference them by ID.

## 3. Webhook endpoint

1. In Stripe dashboard → Developers → Webhooks → **+ Add endpoint**.
2. **Endpoint URL** (production):
   ```
   https://app.akki.ai/api/billing/stripe/webhook
   ```
   For test mode, also add the staging/dev URL (e.g. `https://staging.akki.ai/api/billing/stripe/webhook`).
3. **API version**: pin to the latest (Stripe will show e.g. `2026-04-30.acacia`).
4. **Events to listen to** — subscribe to exactly these:
   ```
   checkout.session.completed
   customer.subscription.created
   customer.subscription.updated
   customer.subscription.deleted
   customer.subscription.trial_will_end
   invoice.payment_succeeded
   invoice.payment_failed
   invoice.finalized
   payment_method.attached
   payment_method.detached
   ```
5. Click **Add endpoint**. Stripe will display the endpoint detail page.

## 4. Webhook signing secret

On the endpoint detail page (top right), click **Reveal** under "Signing secret". The value starts with `whsec_…`. Copy it.

This secret is how AKKI verifies that incoming webhook requests genuinely came from Stripe (not a forged request). It must be passed as `STRIPE_WEBHOOK_SIGNING_SECRET`. **Rotate it every 90 days.**

## 5. API keys

In Stripe dashboard → Developers → API keys:
- **Publishable key** (`pk_test_…` in test mode, `pk_live_…` in live): used by the frontend. Safe to expose to browsers.
- **Secret key** (`sk_test_…` / `sk_live_…`): backend only. Never commit; never expose in frontend code.

Generate a **restricted secret key** for production (recommended over the master `sk_live_*`):
- Permissions: `Customers: Write`, `Charges: Write`, `Subscriptions: Write`, `Invoices: Read`, `Prices: Read`, `Products: Read`, `Webhook Endpoints: None`, everything else: None.
- This limits the blast radius if the key leaks.

## 6. What to give me back

Send all values back. Use ENV var names exactly as listed — they're what AKKI's backend will load:

```
STRIPE_PUBLISHABLE_KEY:                  pk_(test|live)_xxxxxxxxxxxxxxxxxxxxxxxx
STRIPE_SECRET_KEY:                       sk_(test|live)_xxxxxxxxxxxxxxxxxxxxxxxx     (use restricted key in live)
STRIPE_WEBHOOK_SIGNING_SECRET:           whsec_xxxxxxxxxxxxxxxxxxxxxxxx

# Solo
STRIPE_PRICE_SOLO_MONTHLY:               price_xxxxxxxxxxxxxx
STRIPE_PRICE_SOLO_ANNUAL:                price_xxxxxxxxxxxxxx
# Team
STRIPE_PRICE_TEAM_MONTHLY:               price_xxxxxxxxxxxxxx
STRIPE_PRICE_TEAM_ANNUAL:                price_xxxxxxxxxxxxxx
# Enterprise
STRIPE_PRICE_ENTERPRISE_MONTHLY:         price_xxxxxxxxxxxxxx
STRIPE_PRICE_ENTERPRISE_ANNUAL:          price_xxxxxxxxxxxxxx

# Optional but recommended
STRIPE_TAX_AUTOMATION:                   on|off    (set to "on" if you turn on Stripe Tax for VAT — recommended)
STRIPE_CUSTOMER_PORTAL_CONFIGURATION_ID: bpc_xxxxxxxxxxxxxx   (only if you customise the customer portal)
```

## 7. Stripe Tax (recommended if you'll bill UK/EU)

If your customers are UK/EU and you're VAT-registered, **turn on Stripe Tax** (Settings → Tax → Activate). Stripe will:
- Auto-calculate VAT on each subscription
- Collect VAT IDs from B2B customers (reverse-charge mechanism)
- Generate VAT reports each quarter

Cost: 0.4% of transactions where tax was calculated. Worth it — manually computing VAT across 27+ jurisdictions is a tax-compliance nightmare.

## 8. Customer Portal

Enable Stripe's hosted Customer Portal (Settings → Billing → Customer portal) so users can:
- Update payment method
- Cancel/pause subscription
- Download invoices

Configure:
- Allowed actions: update payment method ✅ · update billing info ✅ · view invoices ✅ · cancel subscription ✅
- Cancellation: allow on cancellation at period end (don't refund mid-cycle by default)
- Save the **Configuration ID** (starts with `bpc_…`) — pass as `STRIPE_CUSTOMER_PORTAL_CONFIGURATION_ID`.

## 9. Pre-flight before live mode

Before flipping to live:
- ✅ Bank account linked (for payouts)
- ✅ Identity verification completed
- ✅ Webhook endpoint shows recent test events (200 OK) in the dashboard
- ✅ Tax settings configured if applicable
- ✅ Test mode end-to-end: subscribe → cancel → resubscribe → upgrade tier
- ✅ Decline test: card `4000 0000 0000 0002` fails cleanly without breaking the UI

— end of Stripe setup guideline —
