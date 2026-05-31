# P5.7.3 — Leaked secret provenance (2026-02)

## Provider identification

**Provider: Postmark (legacy outbound + inbound email).**

The leaked secret was the Postmark **inbound-webhook authentication URL secret** — used in three places by the inbound handler at the time (`backend/routers/inbound_email.py`):

1. As a `?secret=...` query-string parameter on the webhook URL configured in Postmark's dashboard ("Webhook delivery URL" field on the inbound stream).
2. As HTTP Basic auth password when Postmark was set to authenticate via Basic (alternative to query-string).
3. As the HMAC-SHA256 signing key against `x-postmark-signature` header values.

## Leaked value vs current env value

| Field | Value | Origin |
|---|---|---|
| Leaked value (in earlier `docs/PRODUCT_REVIEW.md` commit) | `vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj` (32 base62 chars) | Visible in the unredacted commit captured before P3.5 redaction. The leak vector was a screenshot-and-paste of the Postmark dashboard's webhook URL into the review doc. |
| Current `.env` value (`POSTMARK_WEBHOOK_SECRET`) | `c04b327c553c0ea28e6f2935bb801159617d28a6a485ee59ae3674390906d15a` (64 hex chars) | Generated locally (looks like `secrets.token_hex(32)`); distinct from the leaked value. |

The two are different secrets. Either:
- The user rotated the inbound-webhook secret on Postmark before P5.7.3 was dispatched (and updated `.env`), making the leaked value dead, OR
- The `.env` value was always different from what was in the leaked dashboard URL (e.g. the env was set during a manual rotation that pre-dated the doc commit).

**Working assumption (high confidence):** the leaked secret was rotated. The current `.env` value has not appeared in any commit of `docs/PRODUCT_REVIEW.md` that this repo carries.

## Provider status: in current production use?

**Postmark — partial.**

| Surface | Provider | Status |
|---|---|---|
| Outbound — cohort transactional (Receipt, Approval, Decline, Reminder) | **SendGrid** | Active. P5.7's send pipeline lives in `services/cohort_email.py` and uses `SENDGRID_API_KEY`. Postmark is NOT referenced from this path. |
| Outbound — auth (password reset, magic-link signin) | **SendGrid** | Active. `services/cohort/welcome_email.py` uses SendGrid. |
| Inbound — incoming applicant replies | **Postmark** | Still wired. `routers/inbound_email.py` is the active handler; the `.env` carries `POSTMARK_WEBHOOK_SECRET` AND `POSTMARK_SERVER_TOKEN`. SendGrid Inbound Parse MX records also exist on `inbound.akki.syni.ai` (see P5.7.8 DNS audit) but the application has not switched to it. |

User's statement ("changed away from Postmark") matches the outbound side. The inbound side is still on Postmark.

## What the leaked secret could DO if it were still live

A holder of the leaked `?secret=` value could:
1. Craft fake inbound emails and POST them to the configured webhook URL, bypassing the HMAC/Basic checks because they'd present the right URL secret.
2. The fake inbound emails would land in `inbound_messages` and be visible to admins as if they came from a real applicant.

It could NOT:
- Send outbound mail (that requires a Postmark **server token**, not a webhook secret).
- Read mailbox contents.
- Modify the Postmark account / billing / configuration.
- Compromise SendGrid (different provider, separate credentials).

So the blast radius of the original leak was **inbound spam injection** scoped to one URL endpoint, not outbound spoofing or account compromise. Bad, but contained.

## Recommended action (in priority order)

### A. Confirm the rotation (5 minutes)

Log into the Postmark dashboard → Servers → the active server's Inbound stream → "Webhook" section → "Webhook URL". Confirm the `?secret=` query parameter (or the configured HMAC signing key) matches the current `.env` `POSTMARK_WEBHOOK_SECRET=c04b327c553c...` value, NOT the leaked `vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj`.

If the leaked value still appears anywhere in the live config, rotate immediately (Postmark dashboard → regenerate webhook secret → update `.env` → `sudo supervisorctl restart backend` → redeploy production).

### B. Decide whether Postmark stays (10 minutes' deliberation)

The user said they "changed away from Postmark." Two paths:

| Path | What it means | Effort |
|---|---|---|
| Migrate inbound to SendGrid Inbound Parse | Switch `inbound.akki.syni.ai` MX to SendGrid's parse subdomain (already in DNS — see P5.7.8). Rewrite `routers/inbound_email.py` to accept SendGrid's parse payload shape (multipart form, not JSON). Decommission Postmark account. | ~4 hours of code + redeploy + 24h DNS settle. |
| Keep Postmark for inbound | Rotate the webhook secret (done already, per the value comparison above). No code change. Continue paying for one Postmark service tier. | Zero. |

The user's stated direction ("changed away from") suggests Path 1. Surface for decision.

### C. Git history scrub (15-60 minutes depending on history depth)

The leaked value still lives in the commit history of this repo even though the doc has been redacted. Two options:

| Option | Pros | Cons |
|---|---|---|
| `git filter-repo --replace-text` over the leaked value | Removes the secret from every blob in history; commit hashes rewrite. | Force-push required. Anyone who's cloned the repo before the scrub still has the old history locally. |
| Leave the history alone | Zero risk of disrupting collaborators. | Anyone who clones future versions of the repo can run `git log --all -p | grep vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj` and recover the (now-dead) secret. |

If the leaked secret is genuinely dead (confirmed under §A), the scrub is **cosmetic** — the secret won't unlock anything. Recommended for hygiene, not urgency.

## Tracking checklist (for user)

- [ ] Confirm Postmark dashboard webhook secret matches `.env` (action §A above).
- [ ] Decide Postmark stay/leave (action §B above).
- [ ] If staying: optional history scrub (action §C).
- [ ] If leaving: schedule the migration to SendGrid Inbound Parse (separate ticket).

## Files / paths referenced

- `backend/.env` lines for `POSTMARK_WEBHOOK_SECRET`, `POSTMARK_SERVER_TOKEN`, `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`.
- `backend/routers/inbound_email.py` (the active webhook receiver — still Postmark-shaped).
- `backend/services/cohort_email.py` (outbound — SendGrid).
- `docs/PRODUCT_REVIEW.md` (currently redacted version; git history retains pre-redaction commits).
