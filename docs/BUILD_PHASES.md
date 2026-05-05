# AKKI — Build Phases (Management Ledger)

> Single source of truth for the four-phase build to take the app from
> "PARTIAL on multiple capabilities" to "ship-ready". Each phase is
> defined by a single, function-only acceptance bar. We do not start
> phase N+1 until phase N is signed off.
>
> Status legend: **NOT STARTED** · **IN PROGRESS** · **DONE** · **BLOCKED**.

| # | Phase | Status | Owner | Acceptance bar |
|---|---|---|---|---|
| 1 | Document Journal commentary backfill | **DONE — 2026-05-05** | main agent | ≥ 90 % of eligible docs carry `journal_commentary`; one `synisense_runs` row per backfilled doc with `surface=journal_commentary`; opening any populated doc in the Journal UI shows commentary without a generation spinner. |
| 2 | Privacy Wall (cross-context metadata-only projection guard) | NOT STARTED | — | `/api/me/home/stream` and any future cross-context aggregator return **only** `{severity, topic_class, ts, source_context_id}` — never `body_redacted`, never `extracted_text`, never raw signal text. Server-side recursive walk fires `500 Privacy Wall violation` if any leak slips through. Negative test: NED on three boards cannot read content from any board they are not on. |
| 3 | Akki Pulse (cross-context aggregator on top of Privacy Wall) | BLOCKED on Phase 2 | — | `/app/pulse` shows a real, populated stream of cross-board signals classified into 4 entity classes (capital, succession, regulatory, cyber) with attribution back to source context. Daily 07:00 UTC `PulseDigest` cron registered. NED + Executive view variants both render. Page no longer reads `pages/PulsePlaceholder.jsx`. |
| 4 | Service-mode flips (production-grade integrations) | BLOCKED on Phase 3 | — | Resend out of test mode (real recipients receive); ClamAV un-bypassed (`ALLOW_UNSAFE_UPLOADS=false`, `clamd` running, uploads 503 if scanner is missing); `STORAGE_BACKEND=s3` against MinIO/S3; Stripe `BILLING_ENABLED=true` decision boundary handed to product owner. Sentry initialised on backend + frontend. APScheduler leader-election scaffolded for multi-replica. |

## Phase 1 — Document Journal commentary backfill

**Why.** Today `journal_commentary` is populated on 0 / 154 docs because
generation is lazy on first user click. Testers see a spinner and assume
the feature is mocked. We backfill against the live preview DB, fix the
mis-labelled `synisense_runs.surface` (was `"briefing"`, must be
`"journal_commentary"`), and expose a superadmin-triggered re-run for
ops.

Implementation: extract the live-path generation logic into a shared
service `backend/document_commentary_service.py` so the router endpoint
and the backfill script call **one** function. Backfill is idempotent
(skips rows that already have commentary), resumable, throttled, and
records progress every 10 docs.

## Phase 2 — Privacy Wall

**Why.** Pulse is unbuildable without it. The current
`/api/me/home/stream` aggregator returns full content across contexts
keyed only on membership — Privacy-Wall-unsafe. Phase 2 introduces a
content-vs-metadata projection guard that **server-side** refuses to
ship body fields across context boundaries.

## Phase 3 — Akki Pulse

**Why.** This is the headline NED feature. Cross-board pattern
detection (capital pressure, succession risk, regulatory drift, cyber
exposure) with source attribution. Sits on top of Phase 2. No
client-side aggregation — everything goes through a vetted aggregator
that emits metadata-only rows.

## Phase 4 — Service mode flips

**Why.** Today the dev pod runs with `ALLOW_UNSAFE_UPLOADS=true`,
`STORAGE_BACKEND=local`, Resend in test mode, Stripe disabled, and no
Sentry. Production cut-over needs each switch flipped explicitly with
the right runbook. This is the boundary phase — past it, the app is
"ship-ready".

---
Last updated: 2026-05-05 by main agent.
