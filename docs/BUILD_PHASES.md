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
| 2a | Privacy Wall — design + leakage audit | **IN PROGRESS — 2026-05-05** | main agent | `docs/PRIVACY_WALL_DESIGN.md` and `docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` shipped; one of (a)/(b)/(c) recommended; TBD product calls listed for human sign-off. **NO CODE CHANGES IN THIS STEP.** |
| 2b | Privacy Wall — implementation foundation | NOT STARTED | — | `backend/services/privacy_wall.py` ships with `project_for_pulse`, `redact_for_pulse_text`, `assemble_pulse_prompt`. `routers/shares.py:/me/home/stream` and `routers/governance.py:/me/governance/audit` refactored to call it. Two regression tests in CI: a field-drift test + an AST sweep over every router for unguarded cross-context queries. `STRICT_PRIVACY_WALL=true` posture in CI. Pulse stays placeholder. |
| 2c | Privacy Wall — Pulse build on top | BLOCKED on 2b | — | `backend/routers/pulse.py` ships with metadata-only endpoints. `pages/PulsePlaceholder.jsx` replaced with the real surface. Daily 07:00 UTC `PulseDigest` cron registered. Per-context flag-ON gate. Negative test: NED on three boards cannot read content from any board they are not on, even via the Pulse aggregator. |
| 3 | Akki Pulse (cross-context aggregator) — productisation pass | BLOCKED on 2c | — | `/app/pulse` shows a real, populated stream of cross-board signals classified into 4 entity classes (capital, succession, regulatory, cyber) with attribution back to source context. NED + Executive view variants both render. **Note: 2c builds the wall+endpoints; Phase 3 is the polish pass — copy, design, NED variant.** |
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

## Phase 2 — Privacy Wall (split into 2a → 2b → 2c)

**Why.** Pulse is unbuildable without it. The current
`/api/me/home/stream` aggregator returns full content across contexts
keyed only on membership — Privacy-Wall-unsafe. Phase 2 introduces a
content-vs-metadata projection guard that **server-side** refuses to
ship body fields across context boundaries.

**2a (this round) — design + leakage audit only.** Two new docs:
`docs/PRIVACY_WALL_DESIGN.md` (threat model, field-level metadata vs
content taxonomy, three architectures considered, recommendation,
failure-mode detection plan, phasing) and
`docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` (read-only honest accounting of
which routes ship content cross-context today; baseline for 2b).
**Recommendation: field-projection guard (option a).** TBDs parked
for human sign-off — see leakage-audit doc and the design doc §2.

**2b — implementation foundation.** `backend/services/privacy_wall.py`
helper, refactor `home/stream` + `governance/audit` through it, two
regression tests in CI, `STRICT_PRIVACY_WALL=true` posture in CI.
Pulse remains placeholder.

**2c — Pulse build on top.** `routers/pulse.py`, real
`pages/Pulse.jsx`, daily cron, per-context flag-ON gate, negative
test.

## Phase 3 — Akki Pulse productisation pass

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
