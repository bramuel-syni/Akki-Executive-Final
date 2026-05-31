# P5.7.7 — Akki inbox status (2026-02)

## What addresses currently SEND from `akki.syni.ai` / `syni.ai`?

**Outbound from `akki@syni.ai`** — the production From-address for cohort transactional mail, configured in `backend/.env` as `SENDGRID_FROM_EMAIL=akki@syni.ai`. All of: Receipt, Approval, Decline, Reminder, and the P5.7.9 admin test sends use this address.

**Reply-To behaviour:**
- Default: not set — replies route back to the From address (`akki@syni.ai`).
- P5.7.9 admin test sends used `reply_to=bramuel@syni.ai` per the dispatch.
- The receipt email body promises "we read every reply" — this implicitly contracts that something is reading the `akki@syni.ai` inbox (see §receive findings below).

## What addresses currently RECEIVE on `akki.syni.ai` / `syni.ai`?

Per DNS query (see P5.7.8 DNS audit):

| Address pattern | MX target | What receives the mail | Status |
|---|---|---|---|
| `*@syni.ai` (apex) | `syni-ai.mail.protection.outlook.com.` | **Microsoft 365 / Outlook** mailbox infrastructure | Active — `akki@syni.ai` mail flows into a Microsoft Outlook tenant. |
| `*@akki.syni.ai` (subdomain) | **No MX record** | Mail to `*@akki.syni.ai` will NDR ("no MX target") | Not configured — `hello@akki.syni.ai`, `contact@akki.syni.ai`, `team@akki.syni.ai` etc. do NOT receive anything. |
| `*@inbound.akki.syni.ai` | `mx.sendgrid.net.` | **SendGrid Inbound Parse** webhook | Active — SendGrid will POST parsed messages to whatever URL is configured on their Inbound Parse settings. |

## Specific addresses the user asked about

| Address | Receives? | How |
|---|---|---|
| `akki@syni.ai` | **Yes** | Microsoft Outlook (tenant on `syni-ai.mail.protection.outlook.com`). Whoever owns that Outlook mailbox receives the mail. |
| `hello@akki.syni.ai` | **No** | No MX on `akki.syni.ai`. Mail will NDR at the sender's relay. |
| `contact@akki.syni.ai` | **No** | Same as above. |
| `team@akki.syni.ai` | **No** | Same as above. |
| `*@inbound.akki.syni.ai` (any local-part) | **Yes** | Routes to SendGrid Inbound Parse. Application code needs to handle the parse webhook to do anything with it. |

## Implication for the "we read every reply" promise

The Receipt email currently sends from `akki@syni.ai` with no explicit `Reply-To`. Replies route to `akki@syni.ai`, which lands in the Microsoft Outlook tenant tied to `syni.ai`. If a human is reading that Outlook inbox, the promise holds. If not, the promise is hollow.

**Three setup options to make the "we read every reply" promise structurally true:**

| Option | Setup | Recurring cost | Human reads where |
|---|---|---|---|
| **A. Keep status quo** — `akki@syni.ai` on the existing Outlook tenant | Zero — already works | Whatever the syni.ai Outlook subscription costs | Outlook inbox. User confirms a human reads it daily. |
| **B. SendGrid Inbound Parse → in-app admin inbox** | Configure SendGrid Inbound Parse to POST to a new `POST /api/admin/inbound/sendgrid` endpoint; render messages in the existing admin cohort page. | Free (within SendGrid's already-paid tier) | Inside the admin UI. Requires building the receiver + UI surface (out of P5.7 scope). |
| **C. ImprovMX alias to a real inbox** | DNS: add MX to `akki.syni.ai` pointing at ImprovMX. Then `*@akki.syni.ai` aliases to e.g. `bramuel@syni.ai`. | Free up to 50 aliases | Wherever the alias points (e.g. Bramuel's Outlook inbox). |

## Recommended setup (minimum viable for the promise)

If the user wants `hello@akki.syni.ai` / `contact@akki.syni.ai` to also work (e.g. as the contact address in the marketing footer and OG meta), **Option C (ImprovMX)** is the smallest move:

1. Add an `MX` record on `akki.syni.ai`:
   - Priority `10`, target `mx1.improvmx.com.`
   - Priority `20`, target `mx2.improvmx.com.`
2. In ImprovMX dashboard, claim `akki.syni.ai`, then add forward `hello@akki.syni.ai → bramuel@syni.ai` (or wherever).
3. Add an SPF includes for ImprovMX if outbound from `akki.syni.ai` is ever needed; for receive-only, no SPF change required.

If the user wants in-app reading (Option B), open a new ticket — that's a P5.8+ feature.

## Action items (for user decision)

- [ ] Confirm someone reads `akki@syni.ai` in the Outlook tenant daily. If yes, the Receipt email's promise is intact.
- [ ] Decide on Option A vs B vs C above for any additional inbox surface (`hello@`, `contact@`, etc.).
- [ ] If keeping Option A: add `Reply-To: akki@syni.ai` explicitly on outbound sends so the contract is visible in headers (currently implicit via From).

## Files / paths referenced

- `backend/.env` — `SENDGRID_FROM_EMAIL`, `SENDGRID_API_KEY`.
- `backend/services/cohort_email.py` — outbound pipeline; now supports `reply_to` param (P5.7.9).
- `backend/services/cohort/welcome_email.py` — magic-link welcome path; from-address comes from same env var.
- `frontend/src/website/copy/index.js` — no inbox surface in marketing copy currently; the footer's contact CTA does not exist yet.
