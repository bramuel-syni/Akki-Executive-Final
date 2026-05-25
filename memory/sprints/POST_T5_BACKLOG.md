# POST-T5 Backlog

This file collects out-of-scope observations surfaced during T1–T5 implementation. Nothing here is acted on until after T5 completes. Each entry: discovery date · sprint where it surfaced · brief note · pointer.

---

## T1 (24–25 May 2026) — no items
T1 ran clean against the spec. No off-scope issues surfaced.

## T2 (25 May 2026) — seed-data coverage gap

- **Seed-data gap** — at least one objective + one project should have populated `supporting_docs` for future Citations link rendering tests. (Surfaced during T2.3 re-verification 2/2 PASS + 1 SKIP — the SKIP was because no live row produced supporting docs after an Update assessment.)
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Consolidated under the T5 section below (same fix). See `demo-t5backlog-obj-001` + `demo-t5backlog-prj-001`.

## T2 (25 May 2026) — 1 deferred item

## T3 (25 May 2026) — optional spot-check

- **EICAR spot-check** — Optional human EICAR spot-check on Compile modal nested upload to live-verify G9 ClamAV reject path. Not blocking; e1_tester verified the toast wording in source.
  - **2026-05-25 (backlog-b chunk) — RE-PARKED.** Attempted live spot-check; `supervisorctl status` reports `clamd: STOPPED` in the preview environment (production stance — clamd is a sidecar that's not running here). `clamav_service.scan()` therefore raises `ClamAVUnreachable` → 503 instead of producing the `INFECTED + signature` reply needed to exercise the G9 reject path. Re-parked until a follow-on environment with clamd live.


## T4 (25 May 2026) — seed-data gap

- **Compiled Board Pack / Committee Pack with non-null `structured_content`** missing from seed. Manual compile required to demo G6 downloads end-to-end. Recommend adding 1-2 seeded compiled artefacts (`work_studio_exports` rows with rich `structured_content.sections`) for future tester coverage. Not blocking.
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Seeded by `/app/backend/scripts/seed_backlog_b_demo.py`. One Board Pack (`demo-t5backlog-bp-001`, lifecycle=committed) + one Committee Pack (`demo-t5backlog-cp-001`, lifecycle=draft) in Bramuel's Tuli CFO executive context. Idempotent, marker `seed_marker = "DEMO_T5_BACKLOG"`. 3 sections each. Test: `tests/test_backlog_b_seed.py::test_t4_gap_board_pack_has_non_null_structured_content` + `…_committee_pack…` GREEN.

## T5 (25 May 2026) — seed-data gap + deferred LLM step

- **Seed-data gap — Cycle compilation** — one Cycle Manager cycle should be seeded with a compiled `work_studio_exports.structured_content` (kind=`cycle_board_pack`) so the C5 Cycle Page download click-path is browser-observable end-to-end. Same gap pattern as T4 (Board/Committee Pack seed gap). The render endpoint itself is verified GREEN at the wire layer; only the live click-through demo is gated.
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Seeded by `/app/backend/scripts/seed_backlog_b_demo.py`. One cycle (`demo-t5backlog-cycle-001`, status=active, readiness_pct=95 vs target 85) + one linked compilation (`demo-t5backlog-cycle-compile-001`, kind=cycle_board_pack, 3 sections) in Bramuel's Tuli NED context. Test: `tests/test_backlog_b_seed.py::test_t5_gap_cycle_has_linked_compilation_with_structured_content` GREEN.

- **T2.3 seed-data gap (re-parked here for consolidation)** — at least one objective + one project should have populated `supporting_docs` for future Citations link rendering tests.
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Seeded by `/app/backend/scripts/seed_backlog_b_demo.py`. Objective `demo-t5backlog-obj-001` + Project `demo-t5backlog-prj-001` in Bramuel's Tuli NED context. Each carries `last_akki_assessment.supporting_docs` resolving to 2 real (non-orphan) document references from the existing Tuli strategic-pack mirror. Tests: `tests/test_backlog_b_seed.py::test_t2_3_gap_objective_supporting_docs_resolves_at_least_two` + `…_project…` + `…does_not_create_orphan_doc_references` GREEN.

- **C4 Project Brief LLM step deferred** — the wizard ships with the direct create-and-commission path. The full C4 Review / Save-as-Draft branches (with Shield-routed agent-cycle summary regeneration via `llm_router.invoke()` + `deidentifier.deidentify()`) are not in this tier. Follow-on sprint should add the brief-generation endpoint + the `Review` + `Save as Draft` CTAs alongside `Commission Cycle`.

## Backlog-b deployment-pipeline gap (25 May 2026) — RESOLVED at Hardening Step 3

- ~~**Demo seeds are NOT auto-applied on preview pod boot.** During the backlog-b verification, e1_tester had to manually run `cd /app/backend && python -m scripts.seed_backlog_b_demo` on a fresh preview pod. The seed itself is idempotent and safe; the gap is procedural.~~
  - ~~**Park decision** (deferred to future sprint): *"Decide whether demo seeds should auto-apply on preview pod boot (e.g. via an idempotent startup hook), or remain manual to keep prod-like environments lean."*~~

  **RESOLVED 2026-05-25 at Hardening Step 3.** Auto-apply implemented via a FastAPI `@app.on_event("startup")` handler in `backend/server.py::on_startup_demo_seed`. Fail-soft (exception logged, pod keeps booting). Operator opt-out via `DISABLE_DEMO_SEED=1` env-flag. Live boot log over 5 consecutive supervisor restarts confirms idempotency (`rows=7, delta=0`). See `HARDENING_LOG.md` Step 3.



- **X4 — Remove Monitor objective/project filter tabs** (`AKKI_PRODUCT_SPEC.md` v1.1 L687–L695). The user's T2 scope named only "Monitor drawer redesign" (X5) and explicitly excluded Strategic Goals (X6–X8 covered separately). X4 removes the RAG filter tabs on the *Objectives & Projects* listing panel itself — not the drawer. Strictly outside T2.3 by the user's own wording, so deferred. Surface to revisit during a follow-on sprint focused on Monitor listing UX. Spec text: *"delete the filter tabs circled in figure 6 and figure 7."*
  - File that would be touched: `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` (filterTabs L539–L548 + `<ListingShell filterTabs={filterTabs}>` prop at L658).




## J2 closure observation (2026-05-25) — LOW PRIORITY

- ~~**Transient dev-server ESLint overlay in `AppShell.jsx` intermittently obscures UI during manual QA.** Non-blocking, dev-only. Schedule a lint cleanup pass when convenient. Production builds are unaffected (the overlay only renders when CRA's `WDS_SOCKET_HOST` dev hot-reload signals an ESLint error).~~

  **RESOLVED 2026-05-25 at J4 ship.** The two raw-`fetch()` calls in `AppShell.jsx::onbStatus`+`postOnb` (legacy from the J1 b48ee23 cherry-pick) were migrated to the project's `api` client per `memory/sprints/LINT_API_CLIENT_RULE.md`. Dev overlay now compiles clean.

## J3 closure observation (2026-05-25) — RESOLVED at J4 ship

- ~~`TrustCenterTour.jsx` line 27 imports `api` as a default export (`import api from "../../lib/api"`) but `lib/api.js` exports `api` as a NAMED export only. This caused a hard compile error visible in the dev-server overlay on every page mount.~~

  **RESOLVED 2026-05-25 at J4 ship.** Import switched to `import { api } from "../../lib/api"`. Module compiles clean.


## J4 closure observation (2026-05-25) — P2 ENHANCEMENT

- **Onboarding Health admin dashboard** — single page that surfaces per-account journey state (the 5 J1/J2/J3/J4 status flags `first_session_intake_complete` · `door_taken` · `first_doc_uploaded` · `trust_center_introduced` · `first_chat_seen` + the `complete` rollup) for the operator. Today the same data is only readable per-user via `GET /api/users/me/onboarding-status`; an admin view would slash tester ramp-up time and make demo prep one click.
  - Idea source: J4 finish suggestion (orchestrator parked it explicitly at P2 — "we're closing scope, not expanding").
  - Sketch: `/app/admin/onboarding-health` route, table with rows per account, columns per flag (✓/–), filter by "stuck at stage X". Backend: `GET /api/admin/onboarding-health` aggregating `accounts.first_session.*` projection.
  - Not in flight. Pick up when admin tooling sprint surfaces.


## Chunk (c) closure observations (2026-05-25) — P2 ENHANCEMENTS

- **Coming-Soon analytics admin view** — surface `billing_launch_interest` row counts per day / per week so the operator can see the demand shape ahead of actually shipping billing. Trivial to add as part of a future admin tooling sprint. Lives alongside the Onboarding Health dashboard idea.
  - Idea source: chunk (c) finish suggestion (orchestrator parked it explicitly at P2).
  - Sketch: `/app/admin/billing-launch-interest` route, daily rollup line chart, CSV export. Backend: `GET /api/admin/billing-launch-interest/summary` aggregating `billing_launch_interest` rows by `subscribed_at` date bucket.
  - Not in flight.

- **Launch-day email blast CRON** — when billing actually ships, a 4-line CRON job that emails every account in `billing_launch_interest` closes the loop on the Notify-me CTA promise. Trivial to add at launch time.
  - Idea source: chunk (c.1) finish suggestion (orchestrator parked it as a post-launch follow-on).
  - Sketch: re-use the existing Resend mailer. `scripts/notify_billing_launch.py` reads `billing_launch_interest`, sends one email per account, marks each row with `notified_at: <iso>` to prevent duplicate sends. Idempotent via the `notified_at` flag.
  - Not in flight.

## Chunk (c.1) closure observation (2026-05-25) — P3 CLEANUP

- **Stripe library removal from `backend/requirements.txt`** — the `stripe` package + `emergentintegrations.payments.stripe.*` are no longer imported anywhere in the codebase post-chunk-(c.1)(c). Removing them from the pinned requirements is a defensible cleanup. Deferred per the user's "leave it for now (removal is a separate cleanup chunk)" directive at chunk (c) dispatch.
  - Files to touch: `backend/requirements.txt`.
  - Verification: `pip uninstall stripe` + `pytest -q` should remain green (regression test `test_chunk_c_no_stripe_sdk_import.py` pins the invariant at the import level).
  - Not in flight.

## Hardening Step 3 closure observation (2026-05-25) — P2 ENHANCEMENT

- **`/api/healthz/boot-seed` endpoint** — surface the latest seed-run's `(rows, delta, ran_at_utc)` from the boot hook so an admin dashboard or readiness probe can assert that the seed actually fired (not just that the hook is registered). Matches the `/api/healthz/clamav` surface stance from Hardening Step 1.
  - Idea source: Step 3 finish suggestion (orchestrator parked it explicitly — "scope creep for now").
  - Sketch: store the most recent seed-run result on a module global (or a single Mongo row in `boot_seed_status`) at the end of `on_startup_demo_seed`. New router `routers/healthz_boot_seed.py` exposes `GET /api/healthz/boot-seed` returning `{ran_at_utc, rows, delta, ok, error?}`. No auth (mirrors the clamav probe surface).
  - Not in flight. Pick up if/when a future admin-tooling sprint needs the wire format.


## Hardening Step 4 closure observation (2026-05-25) — P3 HOUSEKEEPING

- **spaCy `requirements.txt` cleanup** — the pre-existing `tests/test_requirements_guard.py::test_real_requirements_file_is_clean` fails because `requirements.txt` lines 33/34/185 carry direct-URL refs to `en_core_web_lg` / `en_core_web_sm`. This is the Patch-30 hotfix regression (the wheel pattern was set up earlier and the test never caught up).
  - Files to touch: `backend/requirements.txt` (or the test itself — `tests/test_requirements_guard.py`).
  - Two valid resolutions:
    1. **Test-side fix** — rewrite the guard to allow the spaCy-wheel direct-URL pattern (the wheel reference IS the canonical way to pin a spaCy model version, so blocking it is the guard being too strict).
    2. **Requirements-side fix** — switch to the `spacy download en_core_web_sm` post-install pattern (more fragile, less reproducible).
  - **Recommended:** test-side fix. Verify spaCy model loading still works (Shield's de-identification uses `en_core_web_sm`; regression here would break G18).
  - Carried forward from before the hardening sprint. Has been the sole pytest failure across Steps 1-4 (1248 passed · 1 pre-existing failure).
  - Not in flight. Resolve in a future housekeeping pass.


## Hardening Step 5 closure observation (2026-05-25) — P2 ENHANCEMENT

- **Landing-page revenue optimisation sprint** — surface friction-funnel data from `FRIENDLY_TESTER_FINDINGS_<date>.md` (the artefact produced by §6 of the hardening Step-5 checklist) and translate the top 3 friction points into landing-page / signup-page conversion improvements. Industry rule-of-thumb: 10-30% conversion lift per top-funnel friction point fixed.
  - Idea source: hardening Step 5 finish suggestion (orchestrator parked it as scope creep).
  - **Required input:** at least one completed `FRIENDLY_TESTER_FINDINGS_<date>.md` from §6 of the rollout checklist. Don't dispatch without that data — without it the sprint is guesswork.
  - Not in flight. Pick up after the first friendly-tester batch returns and the findings doc has been aggregated.

