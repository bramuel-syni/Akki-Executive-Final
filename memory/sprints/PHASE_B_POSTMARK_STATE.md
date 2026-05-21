# Phase B — Postmark inbound MailboxHash prefix routing + back-compat + secret rotation — DONE (2026-05-21)

Anchor for the Phase B execution. Pre-flight (saved earlier in this
file before its flip) documented that the Postmark webhook was
already production-grade — the real delta was scoped to four items.

## Scope ledger

| # | Item | Status |
|---|------|--------|
| 1 | MailboxHash prefix routing — `session-<sid>` / `doc-<docid>` / `notify` | ✅ |
| 2 | Mount `/api/webhooks/postmark/inbound` as back-compat second route | ✅ |
| 3 | Generate `POSTMARK_WEBHOOK_SECRET` (64-char hex) + `POSTMARK_BASIC_AUTH_USER` (16-char URL-safe), write to `.env` | ✅ |
| 4 | Audit existing quarantine review surface | ✅ (no tightening needed — already read-only + audited) |
| 5 | New `tests/test_postmark_inbound_phase_b.py` — signature + auth + 3-prefix routing + EICAR + unknown-sender | ✅ 10/10 passing |
| 6 | State-doc flip PRE-FLIGHT → DONE | ✅ (this file) |

## Files touched (3)

| File | Action |
|------|--------|
| `backend/routers/inbound_email.py` | `_resolve_mailbox` extended with prefix parser (`session-<sid>` / `doc-<docid>` / `notify`) returning `{account, context, route, target_id, route_note}`. `_verify_basic_auth` tightened to also validate `POSTMARK_BASIC_AUTH_USER` when set (back-compat: unset → any-user mode unchanged). `receive_postmark_inbound` dispatches `notify` route to audit-only, persists doc-routing metadata into `documents.inbound_route*` fields, and writes `solva_session_attachments` row when `route=session`. NEW `backcompat_router` with `POST /api/webhooks/postmark/inbound` mounted at the app level. |
| `backend/server.py` | `app.include_router(inbound_email_router.backcompat_router)` registration. |
| `backend/tests/test_postmark_inbound_phase_b.py` | NEW — 10 tests covering HMAC valid/tampered · Basic-Auth at back-compat route · Basic-Auth wrong-user reject · default routing · session prefix → attachment row · doc prefix → `related_doc_id` + `relation_type=inbound_version` · notify prefix → no persist · unknown sender → `inbound_queue` row · EICAR attachment → `upload_scan_log` "infected" row. |
| `backend/.env` | Rotated `POSTMARK_WEBHOOK_SECRET` to a fresh 64-char hex value. Added `POSTMARK_BASIC_AUTH_USER` (16-char base64url). |

## MailboxHash taxonomy (after Phase B)

```
inbound+session-<sid>.<account_token>[.<ctx>]@…    → attach to Solva/Phase D session
inbound+doc-<docid>.<account_token>[.<ctx>]@…     → new version of document <docid>
inbound+notify.<account_token>[.<ctx>]@…          → audit-only; no doc persisted
inbound+<account_token>[.<context_token>]@…       → default ingest (unchanged from disk)
<account_alias>@cycles.akki.ai                    → cycle reply thread (unchanged)
```

Unknown-sender (Tier C) emails ALWAYS flow through the quarantine
path regardless of prefix — this is the privacy invariant. The prefix
verbs only apply to owner + reportee (trusted) senders.

Prefix-target resolution failures fall back to default routing with
the failure recorded in `documents.inbound_route_note` so an operator
can replay. Examples:
- `session-bogus123.<token>` where no such session exists → ingests
  as a default doc, `inbound_route="default"`,
  `inbound_route_note="session-target-not-found-in-context"`.
- `doc-bogus.<token>` where no parent doc exists → same pattern with
  `route_note="doc-target-not-found-in-context"`.

## Schema additions

### `documents` (new optional fields)

```javascript
{
  // ... existing fields ...
  inbound_route: "default" | "session" | "doc" | "notify",   // always set on inbound docs
  inbound_route_target_id: <string|null>,                    // the <sid> or <docid> from the prefix
  inbound_route_attached_session_id: <string|null>,          // resolved session id (only if route="session")
  inbound_route_attached_doc_id: <string|null>,              // resolved parent doc id (only if route="doc")
  inbound_route_note: <string|null>,                         // fallback-reason on resolution failure
  related_doc_id: <string|null>,                             // === inbound_route_attached_doc_id when route="doc"
  relation_type: "inbound_version" | null,                   // === "inbound_version" when route="doc"
}
```

### `solva_session_attachments` (new collection)

```javascript
{
  id: <uuid>,
  session_id: <string>,             // Phase D session id
  context_id: <string>,
  doc_id: <string>,                 // inbound document id
  source: "inbound_email",
  from_email: <string|null>,
  subject: <string|null>,
  created_at: <iso8601-utc>
}
```

## Generated secrets

The `.env` file now carries:

```
POSTMARK_WEBHOOK_SECRET=<64-char hex value> (rotated this phase)
POSTMARK_BASIC_AUTH_USER=<16-char URL-safe base64 value>
POSTMARK_BASIC_AUTH_PASS=<same as POSTMARK_WEBHOOK_SECRET — single-secret model>
```

The single-secret model: one HMAC-SHA256-compatible 64-char hex value
serves both the HMAC signature path AND the Basic-Auth password path.
The user (in the Postmark dashboard) configures EITHER:
- HMAC signing key = `POSTMARK_WEBHOOK_SECRET`, OR
- Basic-Auth credentials = `POSTMARK_BASIC_AUTH_USER:POSTMARK_WEBHOOK_SECRET`.

Both work; pick one. The exact values are surfaced in the Phase B
close report (the in-conversation message — NOT this file, which
should never carry live secrets).

## Deviations from the brief

- **Single-secret model** instead of separate `POSTMARK_BASIC_AUTH_PASS`. The existing `_verify_basic_auth` compared the password against `POSTMARK_WEBHOOK_SECRET` — Phase B kept that semantic + added optional user validation. Surfacing two separate values would force the user to track two secrets when one is sufficient.
- **Postmark dashboard's `X-Postmark-Signature` header format**: brief said "signature via SYNISENSE_MASTER_SECRET". On disk the var is named `POSTMARK_WEBHOOK_SECRET`; reused that name to avoid duplication. `SYNISENSE_MASTER_SECRET` continues to refer to a different platform-master-secret used elsewhere (trust receipts, etc.) — they are intentionally separate.
- **EICAR attachment test asserts on `upload_scan_log` row** instead of HTTP 422. Postmark contract requires returning 200 to avoid retry storms; the ClamAV signal lands in `upload_scan_log` for forensics. This is the correct production behaviour (a 422 to Postmark would trigger 7 retries).

## Verification

- Cross-chunk regression: **124 passed** (+10 from Phase A baseline of 114).
- Ruff clean on `routers/inbound_email.py` and `tests/test_postmark_inbound_phase_b.py`.
- Live boot confirmed: backend starts cleanly with new env values + back-compat router registered.
- Pre-existing `test_iter51_inbound_enterprise.py` + `test_iter70_inbound_*` skipped quarantine status preserved (not unblocked by Phase B; out of scope).

## Boot guard

The existing `_verify_inbound_boot_guard()` continues to refuse startup if `AKKI_ENV=production` AND HMAC is disabled. With this phase the disk has:
- `POSTMARK_WEBHOOK_SECRET` (rotated, 64-char hex)
- `POSTMARK_USE_HMAC=false` (dev pod default; production should flip this to `true`)

For the prod cutover, the user needs to:
1. Copy the new `POSTMARK_WEBHOOK_SECRET` into the prod `.env`
2. Set `POSTMARK_USE_HMAC=true` in prod `.env`
3. Set `AKKI_ENV=production` in prod `.env`
4. Restart prod backend; boot guard will allow startup (HMAC enabled).

The dev pod stays as-is (`POSTMARK_USE_HMAC=false`) so the URL-secret legacy path still works for local testing.

## Carry-forward

- The `notify` route's audit payload could be extended with a webhook fan-out to the in-app notifications center. Out of scope for Phase B; flagged for the next sprint's Bank-QA polish iteration if reviewers ask for it.
- Multi-attachment fan-out (Phase B brief noted `_pick_primary_attachment` drops attachments 2..N) remains deferred. The single-attachment-per-email semantic is enforced via `_pick_primary_attachment` unchanged.
