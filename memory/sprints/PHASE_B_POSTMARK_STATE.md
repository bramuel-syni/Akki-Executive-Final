# Phase B — Postmark inbound webhook — PRE-FLIGHT (2026-05-21)

**Status**: Pre-flight only. No code touched. Same forgetting-mitigation
finding as Phase A — the dispatch's framing assumed "mocked"; on-disk
reality is "already production-grade across the entire surface".

## File-wins audit summary

The Phase B brief said *"Endpoint: `POST /api/webhooks/postmark/inbound`
(Basic Auth required, IP allowlist optional)"*. Reality:

| Brief requirement | On-disk state |
|-------------------|---------------|
| Real Postmark inbound webhook handler | ✅ `routers/inbound_email.py` (router prefix `/api/inbound`, endpoint `/postmark` → full path `/api/inbound/postmark`) |
| Signature verification (HMAC-SHA256) | ✅ `_verify_hmac()` — hex + base64 variants both accepted; constant-time compare |
| Basic-auth alternative | ✅ `_verify_basic_auth()` — Postmark's native option, ignores user, compares password to secret |
| URL-secret legacy fallback | ✅ but gated: ONLY when `POSTMARK_USE_HMAC=false` AND `AKKI_ENV != "production"`. Prod accepts HMAC OR Basic only. |
| Boot guard refusing prod with weakened auth | ✅ `_verify_inbound_boot_guard()` raises at startup if `AKKI_ENV=production` AND HMAC disabled |
| `MailboxHash` routing | ✅ `_resolve_mailbox()` parses `<account_token>` or `<account_token>.<context_token>`; both 8-char URL-safe slugs minted lazily; fallback to user's first active context |
| Sender quarantine pattern | ✅ Tier C ("unknown") senders → `db.inbound_queue` row with `status="pending_review"`; raw payload → `db.inbound_queue_raw` (separate collection so list queries stay light); admin review surface exists at `/api/inbound-queue` |
| ClamAV scan on attachments before persist | ✅ `await clamav_service.scan(...)` wired Phase E.A |
| Idempotency on `MessageID` | ✅ `db.documents.find_one({"inbound_message_id": message_id})` early-return; also dedupes against `db.inbound_queue` |
| Cycle-reply alias threading (`<uuid>@cycles.akki.ai`) | ✅ `_handle_cycle_reply()` — recovers via `cycle_followups.reply_to_alias` exact match OR `email_service.cycles_alias_for(account_id)` fallback for legacy rows |
| Sender tier classifier | ✅ `_classify_sender_tier()` — Tier A owner email match · Tier B reportee match · Tier C unknown. Exact email match only per Iter 70 direction. |

## Routing taxonomy on disk

The brief proposed `session-<id>` / `doc-<id>` / `notify` MailboxHash
prefixes; the existing implementation uses a different (already
shipped) convention:

```
inbound+<account_token>@<POSTMARK_INBOUND_DOMAIN>           → account inbox
inbound+<account_token>.<context_token>@<POSTMARK_INBOUND_DOMAIN>  → ctx-scoped
<account_alias>@cycles.akki.ai (alias is uuid-derived)      → cycle reply thread
```

`account_token` and `context_token` are persistent 8-char URL-safe
slugs minted on first use (`accounts.inbound_token`,
`contexts.inbound_token`). The new "session-`<id>`" prefix the brief
proposed is NOT present; this is a real delta.

## Genuinely missing vs the brief

| # | Gap | Severity |
|---|-----|----------|
| 1 | Endpoint path mismatch — brief said `/api/webhooks/postmark/inbound`, disk says `/api/inbound/postmark`. Mounting both for back-compat is trivial (1-line). | Low (Postmark dashboard already points at disk path) |
| 2 | MailboxHash taxonomy doesn't carry the explicit `session-<id>` / `doc-<id>` / `notify` prefixes the brief proposed. The disk uses `<account_token>` / `<account_token>.<context_token>` instead. The disk shape is more flexible (auto-routes to whatever context resolves) but does NOT support deep-link routing to a specific session OR document OR a notification-only path. | Medium — if the user wants session-attach as a first-class flow, this is the gap to fill. |
| 3 | The boot guard only fires for the Postmark webhook. ClamAV has its own (Phase E.A). These are independent; both are wired. | None — by design |
| 4 | Generated `SYNISENSE_MASTER_SECRET` (64-char hex) + basic-auth user/pass — the brief authorised Phase B to generate and surface these. Not in `.env` yet. | Will be done in Phase B execution |
| 5 | IP allowlist for the Postmark webhook — brief said "optional". Not on disk. | Optional; recommend deferring unless ops requests |
| 6 | The `_pick_primary_attachment` only handles the FIRST attachment; multi-attachment emails drop attachments 2..N silently. Brief doesn't address this. | Low; user-spec silent. Recommend deferring. |
| 7 | The unknown-sender quarantine path exists but the brief's "admin review surface (read-only list endpoint + simple UI panel)" — disk has the LIST endpoint (`/api/inbound-queue`) but a "simple UI panel" lives in the FE and I haven't audited whether it's truly read-only-list-of-quarantined. | Medium; verify during Phase B. |

## Recommended Phase B execution scope (file-wins basis)

Given how production-grade the existing webhook is, Phase B's real
work shrinks dramatically:

1. **MailboxHash taxonomy extension** — Add optional prefix routing on top of the existing `<account_token>[.<context_token>]` model:
   ```
   inbound+session-<sid>.<account_token>@…           → attach to Solva/Cycle session
   inbound+doc-<docid>.<account_token>@…             → attach as new version of a document
   inbound+notify.<account_token>@…                  → fire notification only; do NOT persist
   inbound+<account_token>[.<context_token>]@…       → existing path (unchanged)
   ```
   `_resolve_mailbox()` gets a prefix-parser. Routing dispatches via a small enum.

2. **Endpoint path back-compat** — Mount `/api/webhooks/postmark/inbound` as a second route that calls into the existing `receive_postmark_inbound` handler. Lets the Postmark dashboard URL be re-pointed without a hard cutover.

3. **Secret generation + .env wiring** — Generate `POSTMARK_WEBHOOK_SECRET` (the brief used the name `SYNISENSE_MASTER_SECRET` — the disk uses `POSTMARK_WEBHOOK_SECRET` already; same role, different name). Generate basic-auth user/pass. Write to `.env` (not `.env.example`). Surface both in the phase report so the user can paste into the Postmark dashboard.

4. **Quarantine review surface audit** — Confirm `/api/inbound-queue` is read-only + admin-gated; verify the FE panel; tighten if anything is missing.

5. **Tests** — One new test file `tests/test_postmark_inbound_phase_b.py` covering:
   - HMAC signature verification (valid + tampered)
   - Basic-Auth path
   - Three MailboxHash prefixes (session-attach / doc-attach / notify)
   - Plain MailboxHash (existing path)
   - Tier-C unknown → quarantine row
   - Attachment-with-EICAR → 422 + audit row in `upload_scan_log`

6. **State doc** — `PHASE_B_POSTMARK_STATE.md` updated from this pre-flight to "DONE" status with file paths, generated secret formats (NOT the values themselves — those go in the final report only), test count, regression delta.

## Sequencing decision

Phase F (FE chat boundary-removal) is dispatched and pending. It's
small, FE-only, and won't conflict with Phase B's backend work.
Recommended order: **F next (small win), then B**. Phase B will need
the user to take the generated secrets and paste them into the
Postmark dashboard — putting it after F maximises the time-between
when the user wakes up and when they need to do that step.

## Decision-lock

When Phase B fires, all six items above proceed without further
authorisation per the user's "Operating mode: AUTONOMOUS for
remainder of this sprint" delegation. Anything that would expand
scope (e.g. multi-attachment fan-out, IP allowlist) gets explicitly
DEFERRED to Phase B.5 or beyond, not silently bundled.
