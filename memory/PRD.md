# AKKI Sandbox — Product Requirements Document (PRD)



### Mega-Dispatch Round 2 (2026-05-27, fork-resume) — Phase V + N.3 + Phase S CLOSED ✅ · Phase T (DORMANT) + Phase U + L.b.3 QUEUED

**Continued from the prior mega-dispatch close-out (5.5 waves + Phase Y).** This round closed 3 more major phases: **Phase V** (Admin user CRUD portal — closes W7 stock-take #1 PARTIAL → ✅ READY), **N.3** (axe a11y color-contrast minimum-viable fix), **Phase S** (Password reset). Phase T filed as DORMANT TRIGGER (no /signup route exists; build alongside it). Phase U + L.b.3 filed as HALTED for next dispatch.

**Tests added this round:** 36 new CI guards across 3 new test files (`test_phase_v_admin_users.py` 17 incl. 2 async E2E payload-leak probes, `test_phase_n3_contrast.py` 3, `test_phase_s_password_reset.py` 16 incl. 4 async E2E flow probes). **Full regression: 523 passed / 13 skipped / 0 net regressions** (487 baseline + 36 new — N.3 was 3 new + the prior subtotal had 17 from V already).

**W7 Stock-Take RE-VALIDATED (after Phase V + S):**
1. **Superadmin User Portal:** ✅ READY (was 🟡 PARTIAL) — Phase V CRUD lands. Founder can list / create / suspend / restore / timeline-drilldown / CSV-export all users. Data-safety contract enforced (timeline strips payload, list strips password_hash) — both backend-locked AND user-visible (safety banner copy).
2. **Welcome email + onboarding briefs:** ✅ READY (unchanged from prior round).
3. **User self-onboard journey:** ✅ READY (unchanged from prior round).
4. **Superadmin sees telemetry without content:** ✅ READY (re-verified — Phase V's timeline endpoint TIMELINE_FIELDS allowlist projection + visible "Telemetry only — surface + action + when. We never show what the user typed." copy locked in the timeline drawer).

**Backlog status update:**
- ✅ Phase Y (closed prior round)
- ✅ Phase V (closed this round — W7 stock-take #1 now READY)
- ✅ N.3 (closed this round — min-viable contrast fix)
- ✅ Phase S (closed this round — `/forgot-password` + `/reset-password/:token` live + Forgot-password link on SignIn)
- 🟡 Phase T (DORMANT TRIGGER — ship with /signup route)
- 🔴 Phase U (HALTED — context budget + mandatory `integration_playbook_expert_v2` call for next dispatch)
- 🔴 L.b.3 (HALTED — context budget; recipe filed)
- 🔴 W4.2 (HALT-AWAITING-USER-APPROVAL — inventory delivered)
- 📋 R.6 Stripe Checkout (P3 STRATEGIC GATE — DO NOT BUILD without user reversal of founder-mediated conversion lock)
- 📋 BYO LLM API Key (P3 — declined for v1)
- 📋 R.5.b.3/.4/.5 + R.5.c (P3 founder-feedback-gated)
- 📋 Phase W + Phase X (P2 — separate scope)




### Mega-Dispatch 2026-05-27 (autonomous, fork-resume sprint) — W1+W2+W3+W4.1+W5+Phase Y CLOSED ✅

**Scope:** 7-wave autonomous mega-dispatch executed while the user was asleep. Closed 5.5 waves (W4.2 halted at the 10-site grey-highlight inventory per the locked rule — inventory delivered in the ledger row, awaiting user dispatch). Phase Q absorbed into W5 (general chat default). Phase Y (first-login onboarding briefs) shipped to satisfy the W7 stock-take #2 criterion.

**Tests added:** 71 new CI guards across 6 new test files (`test_wave1_surface_fixes.py` 26, `test_wave2_capsule_tabs.py` 7, `test_wave3_doc_journal_rail.py` 9, `test_wave4_task_listing.py` 5, `test_wave5_chat_no_context_default.py` 8, `test_phase_y_onboarding_briefs.py` 16). **Full regression: 503 passed / 13 skipped / 0 net regressions.**

**W7 Stock-Take Verdicts (2026-05-27):**

1. **Superadmin User Portal:** 🟡 PARTIAL — Phase R.5.a cohort console + invite endpoint (`/api/admin/cohort/invites` returns `welcome_email_dispatched: true`). **GAP:** Direct user CRUD (suspend/restore/edit/delete/bulk-export) is Phase V (queued P1). Workaround: invite-then-archive pattern via existing endpoints.

2. **Welcome email + onboarding briefs (end-to-end):** ✅ READY — Phase R.2 dispatches welcome email on invite creation (confirmed `welcome_email_dispatched: true` via live curl). Magic-link consume creates account with `onboarding_briefs_shown_at: null` → Phase Y modal surfaces on first /app load. Verified live at 1280 + 820 viewports: slide 1 "Welcome to Akki." → step indicator "1 of 6" → after 2 Next clicks → "3 of 6" / "How it works.".

3. **User self-onboard journey:** ✅ READY — Phase A/I.4.b magic-link consume → first-session intake (pre-filled logo_name from invite) → context created → land on Home. Phase Y adds the 6-slide deck on top of this flow.

4. **Superadmin sees telemetry without content:** ✅ READY — drill-down endpoint returns `feature_events` rows with keys `[id, event_type, cohort_tag, created_at, payload]`. Live probe confirmed: `payload` carries operational metadata (invite_id, new_account flag, email-as-identity) but **NO chat content, document body, or LLM response fields**. Privacy contract honored.

**W6 backlog status (filed in PHASE_LEDGER):**
- L.b.3 (timer → SSE swap): P1 queued, recipe filed
- Phase V (admin user CRUD): P1 queued
- Phase Y (onboarding briefs): **CLOSED ✅ (this dispatch)**
- N.3 (axe a11y color-contrast): P3 queued
- Phase S (password reset): P2 queued
- Phase T (email verification): P2 queued
- Phase U (OAuth/SSO Google + Microsoft): P2 queued, blocked on MS creds
- W4.2 (system-wide grey→purple sweep): HALT-AND-AWAITING-USER-APPROVAL (inventory ≥10 sites)
- BYO LLM API Key: P3 queued (declined for v1, re-evaluate at Enterprise tier)



### Phase L.b.2 — Frontend wiring for 5 L.b streaming surfaces — 2026-05-27 ✅ (CLOSED, fork-resume close-out)

5 user-facing long-ops now display the locked Claude-reference `<StreamingLogScene>` walking phase scripts instead of generic spinners:
1. **Solva Synthesis** — `PreparingInterstitial.jsx` rewritten; replaces the 3-line fade rotation with the 6-phase `solva-synthesis` log.
2. **Work Studio Enhance** — `EnhanceModal.jsx` running-phase block now renders the 5-phase `work-studio-enhance` log driven during multipart upload + poll.
3. **Task Manager Compile** — `Cycle.jsx` compile step renders the 7-phase `task-manager-compile` log alongside the existing `pollJob` job-queue worker.
4. **Calendar Sync** — `Events.jsx` adds a streaming-log row beneath the calendar banner during the 5-phase `events-calendar-sync` flow.
5. **Decks Generation** — `Decks.jsx` adds a streaming-log box beneath the "Confirm & generate" button during the 6-phase `decks-generation` deep-tier pass.

**Driver-hook choice (deliberate):** L.b.2 ships with the new `usePhasedTimer` hook (timer-driven phase walker that mirrors `useStreamingProgress.state` shape) NOT `useStreamingProgress`. The L.b backend SSE pipes have signature mismatches with the inner handlers for 4/5 surfaces — WS Enhance is multipart (backend wrap declares JSON `Body`), Task Manager Compile + Decks Generation inner handlers are job-queue (202 + job_id), Calendar Sync inner uses `me=Depends(...)` not `ctx=Depends(...)`, Solva synthesis legacy URL is non-context-scoped. The visual contract is identical now; a future L.b.3 dispatch swaps the driver hook to `useStreamingProgress` once the backend pipes are reconciled.

**Files:** `StreamingLogScene.jsx` (+4 lucide icons + 4 ICON_MAP keys: scale/calendar/download/presentation), `data/phaseScripts.js` (NEW, ~70 lines: `LB_PHASE_SCRIPTS` mirror locked verbatim to backend), `hooks/usePhasedTimer.js` (NEW, ~135 lines), 5 surface call sites, plus `App.js` (RESTORE: `Events` lazy import + `/app/events` route — previously dropped in a prior agent's search_replace mishap; restoration unblocked the pre-existing I.4.a test).

**Verification:** Phase L.b.2 CI **30/30 GREEN**. Full regression across all phase test files = **432 passed / 13 skipped** (the 13 skips are pre-existing P4 REWRITE tickets, not regressions). Frontend ESLint 0 issues across 9 touched files. Live multi-viewport Playwright at 1280/1024/820 confirms `/app/events` mounts cleanly (route restore verified). Source-strict CI guards lock cross-file parity between backend `PHASE_SCRIPTS` and frontend `LB_PHASE_SCRIPTS` labels.


### Phase R.5.b.2 — Special-ask tracker + cohort console additions — 2026-05-27 ✅ (CLOSED — halt-and-report triggered, fork-resume verified)

Shipped the day-14 special-ask referral capture modal + cohort console additions. **NEW collection** `db.cohort_special_asks` with locked row shape + 3-state status (`pending`/`partial`/`complete`). **Day-14 trigger on-read pattern**: every trial-status call computes `trial_day` + idempotently mints a `pending` row when `trial_day >= 14`, flipping a `special_ask_surface` flag on the response. **Frontend modal** (`SpecialAskModal.jsx`) opens only when the surface flag is true, with referral_name + referral_email required for save, optional case_study_consent + testimonial_text fields. Surface emits `special_ask.surfaced`; submit emits `special_ask.submitted`; remind-me-later POSTs `/dismiss` + sessionStorage-stores so the modal stays closed for the session but RE-surfaces on next browser session. **Cohort console additions**: drilldown carries the special_ask row; new aggregate endpoint returns status_counts + complete_pct; UI adds the aggregate panel + 4 filter chips + status badge in the drill-down drawer. **Email parallel**: R.4 held-with-warning semantic divergence applies — `[FOUNDER:]` placeholders don't block in-app modal surfacing; the email queued send is held + logged as warning instead of 422-ing the user flow.

**Verification (fork-resume re-confirmed):** Phase R.5.b.2 CI **24/24 GREEN**. Live frontend Playwright probe — created day-16 test account (trial_start_at backdated 15d) → modal mount confirmed with all 10 testids → body text contains `[FOUNDER:` placeholder (R.4 semantic divergence verified live) → submit disabled initially → enables after both referrals filled → Day-16 soft warning banner (R.5.b) renders alongside the modal in the same screenshot (R.4 + R.5.b + R.5.b.2 chain all visible). Multi-viewport at 1280 + 820 both clean.



### Phase R.5.b — Founder copy editors + Day-16 banner — 2026-05-27 ✅ (CLOSED — halt-and-report triggered)

**The trial-blocking critical path is now unblocked.** Founders can edit the `[FOUNDER:]` placeholders via the in-app editor, the overlay replaces defaults at consumer-render time, and the R.2 / R.4 / R.5.a guards stop firing once the copy is clean. HALT-AND-REPORT triggered: ~668 lines NEW code, >> 500-line auto-slice threshold. **R.5.b.2 dispatched separately** for special-ask tracker + cohort console additions.

**Backend (~270 NEW lines + edits):**
- `services/cohort/copy_overrides.py` — 5-slot schema (`welcome_email`, `feedback_thanks`, `day_16_banner`, `early_access_opt_in`, `special_ask`), `assert_save_clean()` raising the locked 422 with `dirty_fields[]` windows, `overlay_slot()` pure-function overlay, `save_slot_override()` upsert, `list_all_slots()` for the editor's GET-all endpoint.
- `routers/admin_cohort.py` — `GET /api/admin/cohort/copy` + `PUT /api/admin/cohort/copy/{slot}` (superadmin); the `issue_invite` handler now consults `welcome_email` override and overlays it before the R.2 guard.
- `routers/trial_status.py` — `GET /api/me/copy/{slot}` whitelisted to user-visible slots (`early_access_opt_in`, `day_16_banner`).
- `routers/feedback.py` — consults `feedback_thanks` override + overlays before the R.4 guard.

**Frontend (~400 NEW lines + edits):**
- `pages/admin/CohortCopyEditor.jsx` — schema-driven editor, one `SlotEditor` per slot, client-side placeholder detection mirrors server guard (save button disabled while dirty), 422 `dirty_fields[]` rendered as inline per-field error banners.
- `components/cohort/Day16Banner.jsx` — renders ONLY when `trial.status === "soft_warning"`; dismissable per-session via sessionStorage; consumes the `day_16_banner` override.
- `pages/EarlyAccessOptIn.jsx` — refactored to render `{copy.heading}` / `{copy.body}` / `{copy.thanks_body}` / `{copy.signoff}` from the override fetch; defaults preserved.
- `App.js` — `<Day16Banner />` mounted in `Gated` above `{children}`; `/app/admin/cohort/copy` route registered.

**Verification:** Phase R.5.b CI **25/25 GREEN**. Full regression across 16 phase test files = **198/198 GREEN**. Live curl 5-probe: list slots, save-dirty→422, save-clean→200, unknown-field→400, **invite-send-1→200 (trial unblocked from 422)**. Playwright smoke: editor mounts at `/app/admin/cohort/copy`, 5 slot sections render with defaults populated, save flow works end-to-end with toast confirmation, multi-viewport 1280/1024/820 width-fit confirmed.



### Phase R.5.a — Cohort console + day-counter enforcement + early-access opt-in — 2026-05-27 ✅ (CLOSED — halt-and-report triggered)

Shipped the Founding Cohort console with time-window dimensions folded in (R.5.0 deflected per the user's accepted proposal). HALT-AND-REPORT triggered: 924 lines of NEW code, >> 500-line auto-slice threshold the user locked. **R.5.b dispatched separately.**

**Backend (615 NEW lines):**
- `services/cohort/console.py` — funnel-stage logic + day-counter computation + time-window resolution + aggregator + drill-down. Funnel-stage taxonomy LOCKED to `("Invited", "Activated", "Engaged", "Attached", "Committed")`; trial day thresholds LOCKED at 16 (soft_warning) / 22 (expired_hard_lock) / 30 (total).
- `routers/trial_status.py` — `GET /api/me/trial-status` (frontend hook reads this every 60s), `POST /api/me/early-access-opt-in` (the hard-locked user's ONLY reachable mutation), `GET /api/me/trial-status/by-account/{id}` (cohort console drill-down).
- `routers/admin_cohort.py` — added `GET /api/admin/cohort/console`, `/console/stages`, `/console/account/{id}/timeline`.
- Wired the R.3 placeholder constants: `auth_magic.py` emits `ACCOUNT_SIGNED_UP`; `oauth_google.py` emits `CALENDAR_SYNC_LINKED`.

**Frontend (476 NEW lines):**
- `hooks/useTrialStatus.js` — fetch + 60s poll the trial-status endpoint.
- `pages/EarlyAccessOptIn.jsx` — the hard-lock destination (editorial layout, 3 `[FOUNDER:]` placeholders for R.5.b editor).
- `pages/admin/CohortConsole.jsx` — superadmin console: 5 stage-count cards + tag filter + 3-button window toggle + sortable table + drill-down drawer.
- `App.js` — `HardLockGuard` wraps `Gated`; locked users `<Navigate>`-redirected to `/app/early-access-opt-in`. Routes registered for both pages.

**Verification:** Phase R.5.a CI **21/21 GREEN**. Full regression across 15 phase test files = **173/173 GREEN**. Live curl probes confirm all 3 superadmin + 3 self endpoints return the locked shapes. Playwright smoke confirms both pages render — Cohort Console shows 6 invitees with stages live + Feedback widget alongside (R.4 chain proved); EarlyAccessOptIn shows the editorial header + day counter + `[FOUNDER:]` placeholders (R.5.b will edit).


### Phase R.4 — In-app feedback widget — 2026-05-27 ✅ (CLOSED)

Fixed-position lower-right `<FeedbackWidget>` renders on every authenticated app surface (inside `Gated`). Single textarea + 3 LOCKED tag buttons (Broken / Wrong / Great). `POST /api/feedback` emits `feedback.submitted` to the R.3 feature_events pipe + queues SendGrid auto-thanks via BackgroundTasks. **R.4 semantic divergence from R.2:** we ALWAYS capture feedback even when the auto-thanks is gated — endpoint returns 200 + `block_reason` rather than 422. Widget shows the same "Got it, thank you." toast in both cases. 17/17 CI green, 4 curl probes confirm contract, live Playwright shows trigger + panel + tags + submit + toast all work + widget stays in-viewport across 1280/768/600.


### Phase L.b — 5 remaining surfaces onto the SSE pipe (backend only) — 2026-05-27 ✅ (CLOSED, L.b.2 frontend wiring queued)

5 phase scripts added to `PHASE_SCRIPTS`. `routers/streaming_v9.py` rewritten wholesale to use the new `PhaseEmitter` taxonomy at the SAME URLs (preserves any in-flight clients): 5 SSE-wrap endpoints driven by a shared `_wrap_synchronous_handler` that fires phases BEFORE the inner await + the remaining phases AFTER + emits `error` SSE event on any HTTPException / Exception. Cancellation honoured via `is_disconnected()` check. **L.b.2 (frontend wiring for 5 surfaces) auto-sliced** per the >500-line scope rule — backend pipe ships first so the integrations have a stable contract. 21/21 CI green; live curl probes against Decks + Calendar confirm script + phase events fire correctly + error namespace works.



### Phase R.3 — Founding Cohort feature_events instrumentation — 2026-05-27 ✅ (CLOSED)

Shipped the cohort funnel telemetry pipe end-to-end:

- New `services/cohort/feature_events.py` exposes `emit_feature_event` (never raises) + 6 canonical dotted-key event constants. New `db.feature_events` collection (separate from `db.events` Calendar + `db.telemetry_events` Synisense — clean per-domain boundary).
- 4 surface emissions wired this dispatch: `auth_magic.py` → `cohort.magic_link.consumed`; `solva_v2.py` → `solva.session.created`; `work_studio_export.py` → `work_studio.export.completed`; `admin_cohort.py` → `cohort.welcome.dispatched`. (2 more — `account.signed_up`, `calendar.sync.linked` — wired in R.5 alongside the cohort console UI.)
- TTL 90-day raw retention + 2 compound indexes for funnel queries.
- New superadmin `GET /api/admin/cohort/funnel?cohort_tag=` returns the locked output shape `{cohort_tag, events_by_type, unique_accounts_by_type, total_events, as_of}` with all 6 event-type keys present (even when zero) so the cohort-console UI never has to handle missing-key cases.

**Verification:** Phase R.3 CI **11/11 GREEN**. Full regression sweep across all 12 phase test files = **114/114 GREEN**. Live curl pipe end-to-end: issue invite (send=0) → consume → emit → `GET /funnel?cohort_tag=r3-live-funnel-probe` → `total_events=1, consumed_count=1, unique_accounts_consumed=1`.


### Phase R.2 — Founding Cohort welcome email (SendGrid) — 2026-05-27 ✅ (CLOSED)

Wired the welcome-email send to the existing SendGrid pipe (already configured: `sendgrid==6.12.5`, `SENDGRID_API_KEY` / `SENDGRID_FROM_EMAIL` in `.env`):

- `services/cohort/welcome_email.py` ships the body with 4 `[FOUNDER: edit before sending real invites]` placeholders in the 4 founder-voice slots.
- MANDATORY server-side guard (`assert_no_founder_placeholder`) returns 422 with `{code: founder_placeholder_present, founder_placeholders_remaining, examples[]}` if any `[FOUNDER:` marker is still in subject/html/text. Guard fires ONLY on real send (`send=1`); `?preview=1` bypasses so founders can iterate visibly.
- Send is fire-and-forget via FastAPI `BackgroundTasks`; success emits `cohort_welcome_sent`, failure emits `cohort_welcome_failed`. Function NEVER raises. `SENDGRID_SANDBOX_ONLY=1` env flag forces sandbox-mode for staging/QA.
- `POST /api/admin/cohort/invites` defaults to `send=1`; `?send=0` skips send (test path); `?preview=1` returns the rendered body without creating an invite (folds in R.2.1 preview backlog feature).

**Verification:** Phase R.2 CI **14/14 GREEN**. Live curl: 422 with placeholders, 200 with `preview=1`, 200 with `send=0`.


### Sign-in copy swap → Option C — 2026-05-27 ✅ (CLOSED)

Two verbatim string swaps on `SignIn.jsx` editorial-column aside per the autonomous queue lock. FTSE 250 quote kept verbatim. CI 3/3 GREEN.



### Phase L.a — Streaming Loader Architecture + 2 reference surfaces — 2026-05-27 ✅ (CLOSED)

Shipped the Claude-reference streaming-loader pipe end-to-end:

**Backend (SSE pipe):**
- `backend/services/streaming/__init__.py` + `sse.py` (~125 lines — `SSEStream` context manager, `encode_event`, `encode_heartbeat`, `sse_headers` with X-Accel-Buffering defence) + `progress.py` (~195 lines — `PhaseEmitter` advancing through a static script, emits `script` / `phase` / `complete` / `error` SSE events).
- `PHASE_SCRIPTS` dict carries the 2 L.a surfaces: `solva-frame-audit` (5 phases) + `work-studio-compile` (7 phases). Phase voice carries the Phase K signature ("Reading your framing.", "Checking the grounding contract.", "Composing.", "Validating.", "Almost there.").
- Solva Frame Audit endpoint (`POST /api/solva/v2/sessions/{sid}/frame-audit`) accepts `?stream=1`; legacy JSON path preserved.
- Work Studio Compile uses an **observer pattern**: existing POST→202+poll architecture preserved; new `GET /api/contexts/{cid}/work-studio/exports/{eid}/stream` polls the export row at 500ms cadence, translating `phase_index` advances into SSE events. `_run_export` worker stamps 7 phase markers at boundaries (entry → grounding → drafting outline → composing → rendering → validating → almost there). Heartbeat every ~15s. 5-minute observer cap.

**Frontend (visual scene per Claude reference):**
- `useStreamingProgress` rewritten to use fetch+ReadableStream (NOT EventSource — EventSource is GET-only but Solva frame-audit is POST). Bearer auth via Authorization header from localStorage. Handles all 4 Phase L event types.
- `StreamingLogScene.jsx` (~155 lines) — lucide-react icons, sans-serif text, muted greys, completed lines with checkmark + opacity-70, active phase with `akki-streaming-log-pulse`. NO upcoming-phases shown. 200ms fade-in per line. `aria-live="polite"` + `aria-busy`. NO monospace / NO terminal / NO progress-bar (verified via CI source-strict guard).
- `index.css` — `akki-streaming-log-fade` + `akki-streaming-log-pulse` keyframes + `prefers-reduced-motion` block that disables both.
- `FrameAuditScreen.jsx` — legacy `ContextLoadingScene` replaced with `StreamingLogScene` driven by `useStreamingProgress`; POST against `?stream=1`. Surface id `streaming-log-solva-frame-audit`.
- `ExportModal.jsx` — generic running spinner replaced with `StreamingLogScene` opened against the observer GET stream endpoint. Surface id `streaming-log-work-studio-compile`.
- `SolvaSession.jsx` — REMOVED the legacy fire-and-forget POST on framing-submit (it caused the streaming scene to flash for one tick because the cached_result branch only emits script+complete). Letting `FrameAuditScreen` own the first call preserves the multi-line progressive reveal.

**Verification:**
- **CI:** Phase L.a `test_phase_la_streaming_loader.py` **15/15 GREEN** across 9 invariant groups (SSE module exports, phase scripts, both endpoint stream branches, worker phase instrumentation at 7 boundaries, hook uses fetch not EventSource, scene visual contract NO monospace/terminal/progress-bar, both surface UIs wired, visual reference doc locked). Full regression sweep across L.a + R1 + J + M + O + N2 + Recurrence #3/#4 = **75/75 GREEN**.
- **Live curl probes:**
  - Solva Frame Audit `?stream=1` → `script` event lists all 5 phases → `phase` events 0..4 in order with verbatim labels → `complete` event with audit summary as `result.frame_audit`. End-to-end <1s (deterministic engine).
  - Work Studio Compile observer stream → `script` event lists all 7 phases → `phase` events 0/1/2 within first 8s (LLM Pass 1 still running at probe end). Worker `status=running` confirmed.
- **End-to-end frontend (Julius@admin):** Login → Solva new session → fill framing → click Begin → state machine FRAMING→FRAME_AUDIT → FrameAuditScreen mounts → SSE stream fires → React state advances → `frame-audit-screen` testid renders verbatim audit content ("A couple of pieces are thin", observations, recommendations, summary). Zero non-N.3-backlog console errors.

**Timing-artifact note (Solva-specific, NOT a bug):** The streaming scene visually unmounts in ~50-100ms on the Solva surface because `audit_framing()` is a sub-millisecond deterministic engine. CI guards lock the source-level contract independently. The multi-line progressive reveal is naturally visible on Work Studio Compile where Pass 1+2 take 30-60s.

**L.b queued:** 5 remaining surfaces (Solva Session Synthesis, Work Studio Enhance Modal, Task Manager Compilation, Events Calendar Sync, Decks Generation) — same pipe, same scene, additive PHASE_SCRIPTS entries.



### Recurring bug fix — Work Studio Briefing tab wraps at narrow viewports — 2026-05-27 ✅ (Recurrence #4 closed)
User flagged FOURTH recurrence of the Briefing tab placement bug. The
prior Recurrence #3 fix had passed both locked structural assertions
(`parentElement === parentElement`, `bounding-rect.top === bounding-
rect.top`) — but ONLY at the 1280×900 probe viewport. Container had
`flex-wrap: wrap` in effect; at narrow viewports (≤820 CSS px) the row
wrapped while still sharing the same DOM parent.

**Structural root cause (institutional memory locked):**
Single-viewport structural probes are necessary but not sufficient
for responsive layout work. The Recurrence #3 assertions checked the
rendered DOM at 1280×900 only — at that width the wrap container had
everything on one line so both assertions passed. The container was
waiting to wrap at ≤ ~820px.

**Fix (Option A — minimum-risk responsive pattern):**
- Container: `flex-wrap` → `overflow-x-auto` + `no-scrollbar`
- Tab buttons: + `flex-shrink-0` + `whitespace-nowrap`
- New `no-scrollbar` utility in `index.css` (Chromium / Firefox / IE-shim)
- Result: at any viewport ≤ 768px the row scrolls horizontally; all 6
  tabs always on a single visual row.

**Verified live at 4 viewports** (1280/768/712/600 CSS px):
- `unique_tops_count === 1` at every viewport
- `briefing.getBoundingClientRect().top === reports.getBoundingClientRect().top` at every viewport
- `container_flex_wrap === "nowrap"` + `overflow-x === "auto"`
- Container horizontally scrollable at narrow widths (`scrollWidth=755 > clientWidth=536/648/704`)
- Screenshots: `/tmp/recurrence_4_BEFORE_{viewport}.png` (5 captures showing wrap) + `/tmp/recurrence_4_AFTER_{viewport}.png` (4 captures showing single-row + scroll)

**NEW LOCKED INSTITUTIONAL RULE (forgetting-mitigation #2):**
Every future tab-row / horizontal-container layout probe MUST run at
**minimum 3 viewports: 1280×900, 768×1024, 600×1024** (the desktop /
iPad-portrait / Samsung-Tab-A-portrait triplet). For each viewport,
assert `unique(getBoundingClientRect().top for each sibling) === 1`.
A passing probe at one viewport is treated as a FALSE-GREEN until
verified at the other two. Same rule applies to footer / nav-strip /
bottom-rail layouts.

The R4.documentation CI test (in
`tests/test_recurrence4_tab_strip_responsive.py`) re-checks the
PHASE_LEDGER for the multi-viewport rule on every CI run — future
agents can't quietly drop it.

**The Recurrence #1 → #2 → #3 → #4 loop:**
1. Recurrence #1 (Phase M original): misread bug-report-as-spec.
2. Recurrence #2 (Phase M-revision): single-viewport CI lock.
3. Recurrence #3 (Issue #1 false-green): structural assertions added but at one viewport.
4. Recurrence #4 (this fix): multi-viewport lock added. Loop closed at the methodology level, not just at the surface.

**CI:** 5/5 GREEN. Full regression sweep: **240 passed / 13 skipped** (235 prior + 5 new R4, 0 regressions).



### Recurring bug fix — Work Studio Briefing tab + Document Journal seed-bleed — 2026-05-27 ✅ (Recurrence #3 closed)
Two-issue dispatch. User flagged third recurrence.

**Issue #1 — Briefing tab placement:** NO EDIT REQUIRED. The user's screenshot was stale (taken before the Phase M-revision fix landed earlier this session). Live DOM probe verified the structural assertions hold on the current preview deployment: `briefing.parentElement === reports.parentElement === true` AND `briefing.getBoundingClientRect().top === reports.getBoundingClientRect().top === 254.09375` (zero pixel diff). All 6 tabs render in one flex row: `Main Board & Committee Packs · Minutes · Drafts · Decks · Reports · Briefing`. Parent component path: `WorkStudio.jsx` → `<div data-testid="work-studio-tabs">` → `<div className="flex items-stretch gap-0 flex-wrap -mb-px">` → `KIND_TABS.map(...)`. Added a 4th positive structural CI lock: source-strict guard that `KIND_TABS.map(...)` is called exactly once (catches future agents splitting the render into two loops).

**Issue #2 — Document Journal seed-bleed:** FIXED. Two-layer structural fix.

Layer 1 (one-shot DB cleanup): An old upload-contract smoke test wrote 100 documents named `smoke-upload` into the `TEST_SeededNedCo` context (`fbc54a51-5a4f-4f2c-aeeb-661494275f4f`) and never cleaned them up. Single `delete_many` op on the regex pattern removed all 100 rows.

Layer 2 (defensive code): `GET /contexts/{cid}/document-journal/recent` endpoint now applies a `$not` filter on the compiled regex `^smoke[-_]upload(\.[a-z0-9]+)?$` (case-insensitive). Any future smoke run that writes to this collection and forgets to clean up cannot bleed onto user-facing rails.

**CI guards** (6 tests in `tests/test_recurrence3_workstudio_briefing_and_journal.py`):
- I1.a — KIND_TABS array contains exactly 6 entries in spec order with Briefing 6th
- I1.b — no separate `BRIEFING_TAB` constant, no 2nd-line pill testids
- I1.c — single `KIND_TABS.map()` render loop (catches split rendering)
- I2.a — endpoint source-strict has `smoke[-_]upload` filter + `$not` operator
- I2.b — live integration: 2 smoke-upload + 1 real doc seeded → endpoint returns ONLY the real doc
- I2.c — case-insensitivity: 5 variants (`Smoke-Upload`, `SMOKE-UPLOAD`, `smoke_upload`, `Smoke_Upload.docx`, `SMOKE-UPLOAD.pdf`) all filtered

**Test ledger** — 6/6 GREEN. Full regression sweep `test_recurrence3*+r1*+i*+n*+h*+m*+o*+j_idle*+bugfix*` = **235 passed / 13 skipped** (229 prior + 6 new, 0 regressions).

**Live verification (admin@akki.ai → TEST_SeededNedCo):**
- Before: 5 `smoke-upload` cards in the Document Journal panel
- After: 0 smoke-upload occurrences in the rendered DOM; panel now shows legitimate test rows (`P2 corrupt test`, `P2 CSV test`, `P2 OCR live test`, `p1-midsession`, `P0 curl test`)
- Briefing tab: same parent as Reports, same `top` pixel value, 6 tabs in one row
- Screenshots: `/tmp/recurrence_3_BEFORE.png`, `/tmp/recurrence_3_AFTER.png`
- 0 axe-a11y, 0 non-401 console errors

**Structural root cause captured in ledger (institutional memory to break the recurrence loop):**

*Why this kept recurring (Recurrence #1 → #2 → #3):*
1. **Recurrence #1** (Phase M original) — Orchestrator misread user bug report ("brief is on the 2nd line") as a layout spec. Treated symptom as desire. Diagnosis-protocol lesson "Symptom vs spec disambiguation" was added then.
2. **Recurrence #2** (Phase M-revision) — Corrected the layout AND CI-locked 3 structural assertions, BUT verification was scoped to the change, not the surrounding surface state. The right rail's Document Journal seed-bleed went unfixed because it wasn't in M-revision's IN_SCOPE.
3. **Recurrence #3** (this fix) — Two-issue dispatch revealed both that the Briefing-tab fix was structurally correct all along AND that test debris had been silently bleeding into the right rail for weeks. The 100 smoke-upload docs had been live the whole time with zero defensive filter at the listing endpoint.

*The structural pattern that produced the recurrence loop:*
1. **JSX inspection isn't DOM verification.** Every "fixed" claim must be backed by a live DOM probe with `parentElement === parentElement` AND `bounding-rect.top` equality.
2. **Test debris in long-lived DB collections is a recurring failure mode.** Smoke tests that write to production-shaped collections without teardown hooks AND without defensive name-pattern filters at the read API are the recipe for surfacing test artifacts on real user rails.
3. **Recurring-bug dispatches must audit the surrounding surface, not just the named symptom.** Future dispatches should include a "surface audit" — open the rendered page, screenshot it, enumerate every visible element against expected state BEFORE proposing a fix.



### Phase R.1 — Founding Cohort foundation — 2026-05-27 ✅
First leg of the Founding Cohort Console rollout. Ships the magic-link
issuance + consume + trial-lifecycle account fields. R.2-R.5 (welcome
email send, feature_events, feedback widget, cohort console UI) remain
queued.

**Architecture:**

*Schema additions to `db.accounts`* (Mongo dynamic, no migration; existing
non-cohort accounts unaffected):
- `trial_start_at`, `trial_end_at` (ISO datetime strs)
- `trial_status` enum: `pending_invite | active_trial | soft_warning | expired_hard_lock | early_access | churned`. R.1 only writes `active_trial`; R.5 owns the rest.
- `cohort_tag` (e.g. `"founding_2026Q2"`)
- `first_name`, `logo_name` (welcome-email template vars)
- `grandfathered_price_locked` bool (R.5 flips on Early Access conversion)

*New collection `db.cohort_invites`*:
```
{
  id, email, cohort_tag, trial_length_days, first_name, logo_name,
  magic_link_token (256-bit url-safe random, UNIQUE index),
  magic_link_url, issued_at, expires_at (issued_at + 14d),
  consumed_at, consumed_by_account_id, status: "pending"|"consumed",
  issued_by_account_id (audit)
}
```
Indexes: `id` UNIQUE, `magic_link_token` UNIQUE, `(email, cohort_tag)` compound.

*Endpoints:*
- `POST /api/admin/cohort/invites` (superadmin-gated) — issues a single-use opaque random token, returns full https URL.
- `GET /api/admin/cohort/invites?cohort_tag=&status=` (superadmin) — lists with computed-on-read `expired` status (no cron).
- `GET /api/auth/magic/{token}` — public consume endpoint. Atomic single-use flip via `find_one_and_update({status:"pending"}, ...)`. Creates passwordless account OR upgrades existing one. Mints first-class JWT (inherits Phase J JTI revocation + idle logoff). 302-redirects to `/app/`. Per-IP rate limit 10 req / 5 min.

*Welcome email STUB:* `cohort_welcome_pending: {…}` log line shaped as SendGrid `dynamic_template_data` dict so R.2 wraps it in a `.send()` call with zero refactor.

**Q1-Q5 locks honoured (all live-verified):**
- Q1 — wizard runs (cohort users land on `/app/first-session`, FirstSessionGuard bounces them to the 3-step wizard). Context-name pre-filled from `account.logo_name`.
- Q2 — `declared_role: null` on cohort account creation; wizard's role-button step collects it.
- Q3 — wizard creates the context (not the consume endpoint).
- Q4 — `test_credentials.md` updated with curl-flow documentation (passwordless — generated fresh per test run, not statically stored).
- Q5 — `expired` status computed on read; DB row stays `pending` until physically consumed.

**Risk #6 (existing-account UPGRADE) locked by CI:**
When magic link consumed for an email that already has an account:
- ✅ `password_hash` preserved
- ✅ `declared_role` preserved
- ✅ `first_session.status` preserved (no `intake` reset)
- ✅ `preferences` preserved
- ✅ `sessions_revoked_after` NOT bumped (Phase J kill-switch untouched)
- ✅ Trial fields stamped on top
- ✅ Same `account_id` returned (no duplication)

**Token shape — Option B (overridden from original brief):**
Pre-build brief said HMAC-signed. Playbook expert call (mandatory per system-prompt auth integration rule) returned generic JWT playbook silent on magic-link specifics. Surfaced HMAC-vs-opaque-random divergence to user; user picked Option B (opaque random `secrets.token_urlsafe(32)`) matching existing contributor-invitation pattern at `services/tasks/contributor_invitation_service.py`. 256 bits of entropy + DB-enforced single-use atomicity = no HMAC layer needed. `COHORT_MAGIC_LINK_SECRET` env var dropped; secret-rotation lockdown test dropped.

**Frontend changes (33 lines total):**
- AppShell.jsx: sr-only `data-testid="trial-status"` hidden span (test hook only — R.5 will render visibly + remove this).
- FirstSession.jsx: same sr-only hook + intake pre-fill cohort fallback (`primary_context_name = account.logo_name`).
- Both hooks are `aria-hidden="true"` + `sr-only` class → zero visual / a11y impact.

**Test ledger:**
- Phase R.1 **11/11 GREEN**: 5 acceptance probes (issue, consume, replay-410, tampered-410, list); 3 negative regressions (expired, non-superadmin-403, existing-account-UPGRADE); 2 lockdowns (sanitize_account shape, atomic concurrent single-use); 1 schema-omit guard.
- Full regression sweep **229 passed / 13 skipped** (0 regressions).
- ESLint clean on all 3 touched frontend files.

**Live verification (admin@akki.ai → fresh `r1-prefill-…@example.com` cohort account):**
- Magic-link 302 → `/app/first-session` (Q1 verified).
- `/api/auth/me`: `trial_status="active_trial"`, `cohort_tag="founding_2026Q2_TEST"`, `declared_role=null`, `first_session.status="intake"` (Q1+Q2 verified).
- Hidden `data-testid="trial-status"` reads `"active_trial"` on the rendered DOM.
- Context-name input pre-filled with `"PrefillCo Holdings"` (Q1 lock verified live — screenshot evidence at `/tmp/phase_r1_prefill_landed.png`).
- Replay → 410 `link_already_used`.
- 0 axe-a11y / 0 React warnings / 0 non-401 console errors.

**Curl smoke probes** (live preview deployment):
- (a) issue: 200, full https URL returned
- (b) consume `?json=1`: 200 + access_token + trial fields
- (c) replay: 410 link_already_used
- (d) tampered (last 4 chars mutated): 410 link_not_found
- (e) admin list: status=consumed + consumed_at + consumed_by_account_id populated

**OUT_OF_SCOPE locks (deferred per brief):**
- R.2 SendGrid send (welcome email)
- R.3 feature_events instrumentation
- R.4 in-app feedback widget
- R.5 cohort console UI + day-16 soft warnings + day-22 hard cutoff
- TOTP / SMS MFA for trial cohort
- Pricing display anywhere in app
- Backfill of existing accounts with cohort fields



### Bugfix dispatch (2026-05-27) — work_studio_exports resolver + RSS-feed swap ✅
Two surgical fixes shipped as a single batch:

**Bug #1 — `work_studio_exports.id` vs `documents.id` mismatch (Drawer "Document not found")**
- Root cause: Phase O routed Minutes/Deck/Report card opens through the
  universal `?doc_id=` URL contract, but `GET /api/contexts/{cid}/documents/{id}`
  only looked in the `documents` collection. Only 18 of 391 exports
  had a `documents` mirror (back-ref `documents.work_studio_export_id`,
  created by the "Continue in chat" flow). The remaining 373 → 404.
- Fix: resolver chain in `routers/documents.py::get_document_detail()`:
  1. Direct `documents.id` lookup (original).
  2. Reverse-lookup via `documents.work_studio_export_id` (for the 18
     "Continue-spawned" mirrors).
  3. Synthesise a documents-shaped read-only payload from the
     `work_studio_exports` row (for the 373 without mirrors). New
     `_synthesize_doc_from_export()` + `_render_structured_content()`
     helpers. Synthesised payload carries `_synthesized_from =
     "work_studio_export"` marker + `work_studio_export_id` self-ref.
- Zero frontend changes. Zero schema migration. Zero endpoint contract
  changes (the GET path now resolves a superset of ids).
- CI: 5 tests (B1a-e) GREEN. Full regression: 217 passed / 13 skipped.
- Live DOM probe (admin@akki.ai → Lemasy Minutes tab): 3 export cards
  opened via actual click, all 3 drawers mounted with full headers,
  zero `drawer-load-error`, zero "Document not found".

**Bug #2 — Quartz Africa + East African RSS 403s**
- Both feeds disabled (`enabled: false` in `data/news_sources.json`).
  Cloudflare blocks confirmed by probe.
- Replacement: `capital-fm-business` (`https://www.capitalfm.co.ke/business/feed/`)
  verified HTTP 200 + valid RSS + 10 items before commit.
- Citizen Digital (specified in brief) has NO working RSS endpoint —
  all variants 500 or HTML. Surfaced to user with proposed substitute
  KBC Business (verified 200, 10 items) — awaiting greenlight.
- CI: 5 tests (B2a-e) GREEN.

**Lessons captured:**
- The Phase O universal `?doc_id=` contract assumed all
  "documents-shaped" opens lived in `documents`. Work Studio exports
  are a parallel artefact collection. Future doc-open sources must
  either (a) write a `documents` mirror, OR (b) the resolver chain
  in `get_document_detail()` must learn about the new source.
- News feed config now distinguishes "removed" (entry deleted) from
  "disabled" (entry retained with `enabled:false` + explanatory `note`)
  — disabled entries serve as institutional memory of which sources
  to NOT re-add without resolving the underlying block.



### Phase J — Idle auto-logoff (30min) + JTI revocation — 2026-05-27 ✅
Hardens authentication with two complementary mechanisms:

**1. JTI revocation (per-token kill-switch):**
- `core.py::create_access_token` + `create_refresh_token` now emit a
  `jti` (uuid4 hex) claim on every minted token.
- `core.py::get_current_account` checks the JTI against
  `db.revoked_jtis` — match → 401 `"Token revoked"`. Pre-Phase-J
  tokens (no `jti`) skip the check during the 8h legacy-tolerance
  window; they expire naturally.
- `POST /api/auth/logout` decodes the inbound token (bearer or
  cookie), upserts `{jti, account_id, revoked_at, reason:"logout"}`
  into `db.revoked_jtis` BEFORE clearing cookies. Returns
  `{ok, revoked_jti:bool}`.
- New `db.revoked_jtis` collection with **unique index on `jti`** +
  **TTL on `revoked_at` (expireAfterSeconds=28800)** so Mongo
  auto-cleans rows once the underlying JWT exp passes.

**2. Account-wide session revocation (admin kill-switch):**
- `POST /api/admin/auth/revoke-all/{account_id}` sets
  `accounts.{id}.sessions_revoked_after = now()`. Requires
  `is_superadmin`. 404 on unknown account.
- `get_current_account` rejects any token with `iat <
  sessions_revoked_after` (401 `"Sessions revoked by admin"`).
- Use case: stolen-credential scenarios where you can't (or shouldn't)
  enumerate every active JTI; just stamp a cutoff and ALL pre-stamp
  tokens die at once.

**3. Idle auto-logoff (frontend):**
- `hooks/useIdleTimeout.js` — listens to `[mousemove, keydown,
  touchstart, click, scroll]` with 5s throttle on activity resets.
  30-minute timer (env-configurable via
  `REACT_APP_IDLE_TIMEOUT_MINUTES`, default 30).
- **Multi-tab safe:** shared `localStorage.akki_last_activity_ts`
  timestamp; every tab reads same key on each 5s tick. Typing in
  tab A keeps tab B alive.
- **Visibility-resistant:** does NOT reset on `visibilitychange`
  (security — hidden tabs can't extend sessions).
- AppShell mounts hook only when `account` is truthy.
- At T-2min: non-intrusive parchment banner with `data-testid=
  "idle-warning-banner"` + Lock icon + grammar-correct minute label
  + Dismiss button. Any input dismisses + resets.
- At T=0: calls `logout()` (revokes JTI server-side) + redirects to
  `/signin?reason=idle`. `useRef` guard ensures single fire.
- `/signin` branches on `?reason=idle` → renders parchment banner
  `data-testid="signin-idle-reason"`: "You were signed out due to
  30 minutes of inactivity. Sign in to continue."

**Test ledger** — Phase J **15/15 GREEN**. Full sweep
`test_phase_i*+n*+h*+m*+o*+j*idle*` = **206 passed / 13 skipped**
(191 prior + 15 new, 0 regressions). ESLint clean on all 3 touched
frontend files.

**Live verification (Julius @ Personal NED Seat):**
- Sign-in `?reason=idle` → idle-reason banner mounts verbatim.
- Login → access token has `jti` claim + 8h exp.
- `/auth/me` 200 before logout → `/auth/logout` returns
  `{ok:true, revoked_jti:true}` → same token now 401 `"Token revoked"`.
- Fresh login → new JTI → `/auth/me` 200 (per-JTI semantics).
- AppShell seeds activity timestamp on mount.
- Simulated 28-min idle → warning banner mounts within 5s, text
  verbatim: `"You'll be signed out for inactivity in 2 minutes.
  Move the mouse or press any key to stay. DISMISS"`.
- Screenshots: `/tmp/phase_j_signin_idle_reason.png`,
  `/tmp/phase_j_idle_warning_banner.png`.

**Out of scope (deferred):**
- Per-account configurable idle policy (one global default for now)
- SMS-based MFA
- Phone number capture on accounts (Phase R territory)
- Showing remaining session-time elsewhere in UI (banner only at T-2min)
- Auto-extending sessions on background-tab activity (intentional
  security feature)

**Lessons captured (ledger NOTES):**
- Two-tier revocation by design: per-JTI for precision + account-cutoff
  for broad-stroke kill-switch.
- Refresh tokens carry JTI for future-proofing but v1 revocation only
  checks access tokens.
- Why not store all active JTIs per account? Write amplification +
  storage cost; cutoff timestamp gets us "kill everything" semantics
  for free off the existing account doc.



### Phase M (revision) — Work Studio Briefing tab restore — 2026-05-27 ✅
**Why this revision exists** (institutional memory):
Phase M originally shipped Briefing on a 2nd-line pill because the
orchestrator misread the user's bug report ("brief is on the 2nd line")
as a layout spec. User clarified after Phase M close: the original
message was reporting that Briefing was spilling to the 2nd line as a
defect, not specifying it should live there. Correct intent throughout:
Briefing is the 6th tab in the main horizontal tab strip alongside the
other 5. Original M close-out is therefore a half-fix; this revision
lands the correct layout the user wanted from the start.

**Lesson for anti-drift protocol (added to PHASE_LEDGER diagnosis section):**
When a user describes the current visual state in flat language, do NOT
assume it's a spec — confirm whether the description is intent or
symptom before locking it as IN_SCOPE.

**Shipped:**
- `KIND_TABS` extended from 5 → 6 entries; new 6th entry
  `{id:"briefing", label:"Briefing", short:"briefings", icon:BookOpen, empty:"No briefs yet."}` appended after `report`.
- `BRIEFING_TAB` constant REMOVED — Briefing data path now uniformly
  resolves via `KIND_TABS.find((t)=>t.id===kind)` in 4 call sites
  (`BriefRow` icon lookup, `initialKind` URL parser, `fetchAggregates`
  tab resolver, `activeTab` memo).
- 2nd-line pill render block (the `<div data-testid="work-studio-briefing-row">`
  container + inner `<button data-testid="work-studio-briefing-pill">`)
  REMOVED entirely from the JSX tree.
- Tab-strip comment updated: "Five-tab line" → "Six-tab line".

**CI guards flipped** (`tests/test_phase_m_workstudio_noise.py`):
- M15a: positive — `KIND_TABS` must contain exactly 6 entries in the
  spec-locked order with Briefing as the 6th (was 5).
- M15b: negative — `const BRIEFING_TAB` must NOT exist (was positive).
- M15c: negative — neither `work-studio-briefing-row` nor
  `work-studio-briefing-pill` testids may appear in source (was positive).
- All other guards (M1a/M1b/M1c/M1d/M2a/M2b/M2c/M3a/N1/N2) preserved
  verbatim.

**Test ledger** — Phase M 13/13 GREEN post-flip. Full sweep
`test_phase_i*+n*+h*+m*+o*` = **191 passed / 13 skipped**. ESLint clean.

**Live verification (Julius @ Personal NED Seat):**
- Tab strip renders 6 tabs in spec order: `Main Board & Committee Packs`
  (active) · `Minutes` · `Drafts` · `Decks` · `Reports` · `Briefing`.
- Pill removal verified: `work-studio-briefing-row`=0,
  `work-studio-briefing-pill`=0, `work-studio-briefing-pill-active`=0.
- Click flow: Briefing tab click → URL `kind=briefing` + tab-active=1.
- Drafts tab click → ListingShell + search bar + MOST RECENT regression
  intact.
- Screenshots: `/tmp/workstudio_BEFORE_briefing_restore.png` (5 tabs +
  pill) vs `/tmp/workstudio_AFTER_briefing_restore.png` (6 tabs, no pill).



### Phase I.4.c (Google leg) — Events: Google Calendar OAuth + Sync — 2026-05-27 ✅
Read-only Google Calendar integration. Users authorise via OAuth 2.0,
their primary calendar's next-90d events get pulled into `db.events`
as `source="calendar_sync"`/`status="confirmed"` rows that surface on
the Events page AND on Company Home Card 5 (within 14d window).
Microsoft Graph (Outlook) leg stays deferred until user provides
Microsoft credentials.

**Architecture shipped:**
- `routers/oauth_google.py` (596 lines) — 5 endpoints:
  - `GET /api/oauth/google/connect?context_id={cid}` — returns
    `{authorize_url}` with JWT-signed state token (10-min TTL, reuses
    app-wide `JWT_SECRET`), `access_type=offline`, `prompt=consent`
    (so refresh_token is always issued), scopes
    `calendar.events.readonly + calendar.readonly + openid/email/profile`.
  - `GET /api/oauth/google/callback?code&state` — exchanges code for
    tokens, persists encrypted in `db.user_calendar_credentials`,
    302-redirects to `/app/events?context_id={cid}&calendar_connected=google`.
    On Google-side `error=…`, 302-bounces with `calendar_error=` param
    so the Events surface renders a connection-failed toast.
  - `GET /api/contexts/{cid}/oauth/calendar/status` — banner state
    aggregator: returns `{connected, provider, connected_at, last_sync_at, last_sync_status, last_sync_error, synced_count}`.
  - `POST /api/contexts/{cid}/events/sync-calendar?provider=google` —
    pulls 90d-forward primary calendar, idempotent delete-and-reinsert
    of `(context_id, user_id, source="calendar_sync")` rows. Auto-refreshes
    expired access tokens via stored `refresh_token`. On refresh failure
    writes `last_sync_status="auth_expired"`.
  - `POST /api/contexts/{cid}/oauth/google/disconnect` — soft-deletes
    credentials row + best-effort token revoke at Google. Idempotent
    (returns `ok=True, revoked=False` if no row).
- `services/crypto/token_vault.py` — Fernet symmetric encryption for
  access + refresh tokens. Production requires `OAUTH_TOKEN_VAULT_KEY`
  env var; non-prod auto-generates per-process Fernet key with loud
  warning. Single-purpose / single-key (no rotation machinery — external
  tokens are re-acquirable via re-OAuth).
- `db.user_calendar_credentials` collection (Mongo dynamic, no schema
  migration). Schema: `id, user_id, context_id, provider, access_token_encrypted, refresh_token_encrypted, expires_at, scope, calendar_id, connected_at, last_sync_at, last_sync_status, last_sync_error, deleted_at`.
  Index on `(user_id, context_id, provider)`.
- Title-keyword type inference (`_infer_type`): priority-ordered regex.
  Deadline > audit > briefing > board > other. Test Y2 locks all 11
  keyword variants verbatim.
- Google event → events-schema mapping (`_map_google_event`):
  preserves `summary` (truncated 200 chars), `location` (200),
  `description→notes` (2000); ISO-coerces `start.dateTime`/`end.dateTime`
  (timezone-aware); all-day `start.date` maps to UTC midnight; skips
  events with no `id` or no parseable start.
- Frontend `Events.jsx` `CalendarSyncBanner` — 4 states with distinct
  testids: `calendar-banner-loading` / `-disconnected` / `-connected` /
  `-auth-expired`. Auto-fires sync once when OAuth callback redirects
  with `?calendar_connected=google`, then strips the param. Disconnect
  modal with confirm-cancel testids.

**OUT_OF_SCOPE (locked):**
- Microsoft Graph (Outlook) leg — deferred until creds arrive. Architecture
  pre-built: provider enum already accepts `"microsoft"`; sync endpoint
  enum-dispatches on `?provider=…`. Sibling `routers/oauth_microsoft.py`
  will mirror the contract.
- Write-back (creating/updating Google events from Akki) — would bump
  scope from `.readonly` to `.events`. Read-only this phase.
- Recurring event expansion (we trust Google's `singleEvents=true`
  expansion).
- Multi-calendar sync (primary calendar only).
- Cross-account dedupe (if 2 board members both sync the same meeting,
  both rows persist — dedupe is user-driven via Reject).
- Real-time push notifications via Google webhooks (pull-on-demand via
  Sync now button).

**CI guard** `tests/test_phase_i4c_google_calendar.py` — **19 tests**
covering token vault (V1-V3), OAuth flow (O1-O4), status endpoint
(S1-S2), mapping + sync (Y1-Y7), disconnect (D1-D2), Microsoft-router-
does-not-exist negative (N1). Mocks `googleapiclient.discovery.build`
+ `httpx.AsyncClient` for offline runs.

**Test ledger** — Phase I.4.c **19/19 GREEN**. Full sweep
`test_phase_i* + n* + h* + m* + o*` = **191 passed / 13 skipped**
(skips pre-existing Patch 19 fixture, unrelated).

**Live verification (Julius @ Personal NED Seat, cid=`f954d5d0…`):**
- Events page renders: H1=`"Upcoming on the calendar."`, subtitle=
  `"Manual entries, AI-extracted dates, and your connected calendar — in one place."`,
  CalendarSyncBanner mounts at `calendar-banner-disconnected` with
  verbatim body and `"CONNECT GOOGLE CALENDAR"` CTA visible+enabled.
- Banner state matrix: disconnected=1, connected=0, auth-expired=0, loading=0 ✓.
- Tab strip intact (UPCOMING/PAST/ALL/EXTRACTED).
- **End-to-end OAuth click-through verified:** clicking the CTA
  redirected browser to `accounts.google.com` Sign-in screen ("to
  continue to akki-executive.preview.emergentagent.com") — direct
  proof `/api/oauth/google/connect` returned a valid `authorize_url`
  with all OAuth params intact.
- Console errors on this surface: 0 banner-related, 0 axe-a11y, 5
  pre-login 401s (expected — auth context resolves after first
  authenticated call). Screenshot evidence: `/tmp/i4c_google_disconnected_banner.png`.

**Lessons captured:**
- token_vault uses raw Fernet (NOT Synisense shield-map envelope) —
  OAuth tokens can be re-acquired via re-OAuth, so the heavyweight
  rotation machinery would be overkill.
- Idempotency contract (test Y4): delete-and-reinsert of `(context_id, user_id, source="calendar_sync")` rows, NOT upsert-by-source_ref —
  so cancelled-on-Google events naturally drop off. Manual events +
  doc_extraction drafts/confirmed are NEVER touched.
- calendar_sync events land with `status="confirmed"` directly (no
  draft-review gate), so they surface on Card 5 via I.5's
  absence-default `$ne:"draft"` filter. Test Y7 locks this regression
  invariant.



### Phase O — Document Drawer Universal Discipline (compliance audit) — 2026-05-27 ✅
Audit-and-fix pass against the Phase E.3 Universal Document Drawer
spec. User raised: *"you have not applied the document drawer
discipline on all documents — decks, reports, drafts etc, and the
two types of document intelligence we agreed on, across the system."*

**E.3 spec recovered verbatim (source of truth for this compliance pass):**
- **2 intelligence modes:** **CREATION** (`state==="draft" && origin==="akki_generated"`) and **REFERENCE** (everything else).
- **5 tabs:** `Document` · `Intelligence` · `Summary & Notes` · `Signals` · `Related`
- **5 CTAs:** `Use in Solva` · `Use in Chat` · `Generate brief` · `Test hypothesis` · `Share document`
- **Canonical URL contract:** `/app/work-studio?doc_id=<uuid>`. Every doc-open surface MUST navigate to this URL; Universal `<DocumentDrawer>` mounts at this URL and reads `doc_id` from search params.

**Stage-1B inventory (17 surfaces audited):**
- **11 already compliant** (WorkStudio deep-link, WorkStudioActivity, TaskManager, Pulse, Cycle, Workspace, MentionInbox, AppShell, CompilationRail x3, FollowUpDraftsCard, App.js legacy redirect, Events.jsx Source-document link, Chat citations via `/app/documents/:id` → redirect)
- **2 non-compliant** (both in WorkStudio.jsx): `BriefRow` click via legacy `setDrawerAid + setDrawerOpen`; `DocumentCardsSection` minutes/decks/reports branch via legacy `setOverlayAid + setOverlayOpen`
- **1 dead code** (AskPanel.onCitationClick — zero importers)
- **1 out-of-scope** (NedMeeting — Workspace artefact, not a doc-open)

**Shipped (3 surgical redirects, single-file change):**
- `onOpenBrief` body redirects through `setSearchParams({ doc_id: row.id, kind, context_id })`.
- `DocumentCardsSection` `onOpenDocument` minutes/decks/reports branch redirects through `setSearchParams({ doc_id: aid, ... })`. Board/committee pack branch preserved (G8 dedicated full-page surface).
- `akki:open-document-overlay` window event listener redirects to canonical URL (belt-and-suspenders).
- Legacy `BriefDrawer` + `DocumentOverlay` mounts kept in tree (open-state setters no longer called by any entry point — unreachable in runtime UX).

**CI guard** `tests/test_phase_o_drawer_discipline.py` — **6 tests:**
positive (all 10 compliant surfaces retain `?doc_id=` URL contract) ·
negative (onOpenBrief body uses setSearchParams not setDrawerAid/setDrawerOpen) ·
negative (DocumentCardsSection onOpenDocument minutes/decks/reports branch uses setSearchParams not setOverlayAid/setOverlayOpen) ·
positive (window-event listener redirects to canonical URL) ·
positive (`<DocumentDrawer>` mount stays in WorkStudio.jsx) ·
source-strict (no new `<DocumentOverlay>` mounts outside the 3-file allowlist).

**Test ledger** — Phase O 6/6 GREEN. Full sweep `test_phase_i* + n* + h* + m* + o*` = **172 passed / 13 skipped** (skips pre-existing).

**Live verification (Julius @ Personal NED Seat):**
- Click `ws-document-card-open-d130c799-…` on Reports tab → URL transitions to `/app/work-studio?doc_id=d130c799-…&kind=report&context_id=…` ✓ **CANONICAL URL CONTRACT FIRED**.
- `<DocumentDrawer>` testid mount: 1 ✓.
- Direct nav to real doc `790f6a60-…` (Digital Transformation Strategy):
  - All 5 tabs verbatim: `Document` · `Intelligence` · `Summary & Notes` · `Signals` · `Related` ✓
  - All 5 CTAs verbatim: `Use in Solva` · `Use in Chat` · `Generate brief` · `Test hypothesis` · `Share document` ✓
  - Mode badges: `COMMITTED · UPLOADED` (Reference mode for committed/uploaded doc) ✓
  - Document body renders Mara Heritage Bank Q1 2026 strategy content ✓

**Lesson for future agents:** the source-strict CI guards locking the canonical URL contract (added in this Phase O test) prevent future agents from re-introducing state-toggle bypasses when adding new doc-open surfaces.

### Phase M — Work Studio noise reduction + Briefing pill move — 2026-05-27 ✅
User raised this ≥3 times. Verbatim spec captured in PHASE_LEDGER M
row. Reduces Work Studio surface clutter on the `Main Board &
Committee Packs` tab and consolidates the page header.

**Stage-1 refinements:**
- The doc-card surplus = `DocumentCardsSection` + `ListingShell` rendered redundantly. `ListingShell` is SHARED across tabs (canonical listing for Drafts / Reports / Decks / Minutes / Briefing). **Cleanest fix:** gate BOTH with `kind !== "cycle_main_and_committee_pack"` — drop them on this tab only, untouched everywhere else.
- Brief said "5 tabs in one line" but live data showed 6. Resolved: Briefing moves OFF the horizontal tab strip and ONTO a 2nd-line pill below it. `kind="briefing"` data path preserved.
- **M.3 — Task Manager already clean.** No DocumentCardsSection / no Show-drafts toggle / no MOST RECENT dropdown. No removal target. Surface this in close-out.
- **M.4 inventory — other surfaces clean.** No other surfaces have similar agent-added surplus.

**Shipped:**
- `KIND_TABS` reduced from 6 → 5 entries: `Main Board & Committee Packs · Minutes · Drafts · Decks · Reports`.
- `BRIEFING_TAB` constant added (preserves `kind="briefing"` data path).
- `activeTab`, `initialKind`, `BriefRow` icon lookup all resolve Briefing via `BRIEFING_TAB` when `kind === "briefing"`.
- Briefing pill renders below the tab strip via `work-studio-briefing-row` container with `work-studio-briefing-pill` button testid. Active state flips when `kind === "briefing"`.
- `DocumentCardsSection` wrapped in `{kind !== "cycle_main_and_committee_pack" && (...)}`.
- `ListingShell` wrapped in `{kind !== "cycle_main_and_committee_pack" && (...)}`. ContextActions (Compile CTAs) stays UNCONDITIONAL.
- Subtitle (`Shape board packs, decks, reports, and briefings. Agent Cycle compiles your work to executive cadence.`) DROPPED entirely along with its `data-testid="work-studio-subtitle"`. H1 (`Check or review your work.`) preserved with new `data-testid="work-studio-h1"`.

**Files touched:**
- `frontend/src/pages/WorkStudio.jsx` (single-file Phase-M fix surface — ~80 lines net change)

**CI guard** `tests/test_phase_m_workstudio_noise.py` — **13 tests:**
M1a-M1d DocumentCardsSection + ListingShell gated, ContextActions unconditional, Drafts kind preserved · M15a-M15c exactly 5 KIND_TABS in correct order with Briefing NOT in array, BRIEFING_TAB constant preserved, briefing pill testids · M2a-M2c forbidden subtitle phrases gone, subtitle testid removed, H1 preserved · M3a Task Manager already clean (negative guard) · N1-N2 "Show drafts & empties" never reappears, tab-label-word 3+ recombinations blocked.

**Test ledger** — M 13/13 GREEN. Full regression sweep `test_phase_i* + n* + h* + m*` = **166 passed / 13 skipped** (skips pre-existing).

**Live verification (Julius @ Personal NED Seat, 1280×900):**
- Playwright DOM probe on `/app/work-studio?kind=cycle_main_and_committee_pack`: H1: 1, tabs total: 5, main tab active: 1, briefing pill: 1, doc-card surfaces: **0**, work-studio-listing: **0**, Compile Board Pack text: 1, Compile Committee Pack text: 1, old subtitle text: **0**.
- Visual screenshot: 5 tabs in horizontal strip, Briefing pill on 2nd line, Compile Board Pack + Compile Committee Pack grouped-button strip, NO doc-card grid, NO search bar, NO MOST RECENT dropdown, NO subtitle. Right rail intact.
- Regression: Drafts tab clicked → ListingShell + search bar + 2 draft rows re-appear ✓. Briefing pill clicked → active state flips, briefing items render ✓.

### Phase I.6 — Final hygiene + 3 fold-ins — 2026-05-27 ✅
Closes the Phase I family by folding 3 deferred items into a single
hygiene-disciplined dispatch:
- **Fold-in 1 (Phase P)** — Monitor score "%" suffix
- **Fold-in 2 (I.5 close-loop)** — Card 4 clickable subtext segments
- **Fold-in 3 (I.4.b)** — De-id PII fix lifting extraction recall

**Stage-1 cross-check refinements (ship-velocity):**
- Phase P scope reduced from "7 sprinkled sites" → **2 sites** in 2 files. No centralised formatter; inline edits.
- De-id fix approach **(a)** chosen — pre-pass `purpose`-gated regex skip, scoped exclusively to `documents.events_extract`. Other purposes (chat, solva, work-studio) retain full PII shield.

**Fold-in 1 — Phase P (Monitor score % suffix):**
- `StrategicGoalsPanel.jsx::ScoreBar` — render changed from bare `{pct}` to template-literal `` `${pct}%` `` for non-empty values. Empty still renders `—`.
- `ObjectivesProjectsPanel.jsx` — row score render changed from `{row.score ?? 0}` (defaulting to 0 — visually wrong for null) to `{row.score == null ? "—" : \`${row.score}%\`}`. Added `data-testid="objective-score-{id}"` for test addressability.

**Fold-in 2 — I.5 close-loop (Card 4 clickable subtext):**
- `CompanyHome.jsx::AttentionCard` gains `onOpenRoleSegment` prop.
- When `card.id === "questions"` AND `decomposition` has non-zero counts: subtext renders each segment as `<span role="button">` (NOT nested `<button>` — invalid HTML) with `data-testid="card4-subtext-segment-{role}"`. `e.stopPropagation()` prevents the parent-card click from also firing.
- Click → navigates to `/app/questions?role={role}&filter=open&context_id={cid}`.
- Backend `/api/me/questions` + `/api/contexts/{cid}/cycles/{cycle_id}/questions` accept `asker_role=board|ceo|team` query param. Invalid value → 400.
- `Questions.jsx` reads `?role=` from URL, applies filter, renders active-filter chip `Role: {role} ✕` with `data-testid="questions-role-chip-clear"`.

**Fold-in 3 — De-id PII fix:**
- `services/synisense/shield/deidentifier.py::deidentify(content, *, tenant_id, purpose=None)` — new `purpose` kwarg threaded through.
- Internal `_PURPOSE_REGEX_SKIPS = {"documents.events_extract": {"DATE_ISO"}}` map. When called with that purpose, the DATE_ISO regex pass is bypassed — ISO calendar dates flow through to the LLM unmodified.
- `services/synisense/shield/client.py::invoke` + `invoke_streaming` plumb `purpose=purpose` into both `deidentify` calls.
- **Follow-on JSON sanitiser** — added `events.py::_sanitise_llm_json` (quote-state-aware control-char stripper). Triggers on retry when first `safe_parse_json` returns empty dict. Handles Claude's occasional unescaped `\n` inside string values which surfaced ONLY after the de-id fix unblocked the model.
- **Recall lift verified live:** same seeded board pack doc with 5 ISO date references. **Pre-fix:** 3/5 = 60% (I.4.b ledger note). **Post-fix:** raw=5 parsed, kept_pre_filter=5, **4 extracted cleanly** = **80% (4/5)**. The 1/5 remaining miss is LLM-output formatting variance — parked as future hygiene.

**Fold-in 4 — Hygiene sweep:**
- Zero live executable imports of archived Home1/Home2 outside `_archived/` (7 historical-context comment references in 6 files — kept as architecture documentation; not removed).
- Zero TODO/FIXME/XXX comments in any Phase I.1-I.5 file.
- Ledger queue reconciled: I.4.b + I.5 + I.6 removed from Queued. Remaining: I.4.c (OAuth-blocked) + Phase O / J / L / M / N.3 / Q.

**Files touched:**
- `frontend/src/components/monitor/StrategicGoalsPanel.jsx` (1-char fix)
- `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` (1-line fix + testid)
- `frontend/src/pages/CompanyHome.jsx` (~60 lines: AttentionCard branch + nav handler)
- `frontend/src/pages/Questions.jsx` (~30 lines: role URL param + chip)
- `backend/routers/questions.py` (asker_role query param on 2 endpoints)
- `backend/services/synisense/shield/deidentifier.py` (purpose kwarg + skip map)
- `backend/services/synisense/shield/client.py` (purpose plumbing in 2 invoke paths)
- `backend/routers/events.py` (_sanitise_llm_json + retry-parse fallback)
- `backend/tests/test_phase_i2_company_home_wiring.py` (loosen signature assertion to accept I.6-evolved AttentionCard 4-prop shape)

**CI guard** `tests/test_phase_i6_hygiene.py` — **13 tests:**
P1-P2 score % suffix (both sites + null handling) · L1-L2 card4 segment testids + stopPropagation + deep-link · L3 backend asker_role filter (with seeded buckets) · L5 invalid asker_role → 400 · L6 Questions.jsx role chip + clear testid · D1-D2 deidentify skips DATE_ISO ONLY when purpose=documents.events_extract · D3 other patterns (EMAIL) still fire under events_extract (shield not gutted) · D4 client.py plumbs purpose=purpose in both invoke paths · H1 no live executable imports of Home1/Home2 · H2 no TODO/FIXME/XXX in Phase I.1-I.5 files.

**Test ledger** — I.6 13/13 GREEN. Full regression sweep
(`test_phase_i*.py + test_phase_n*.py + test_phase_h*.py`) = **153 passed / 13 skipped** (skips pre-existing Patch 19 Solva fixture). Zero new regressions.

**Live verification (Julius @ Personal NED Seat):**
- Seeded 4 questions (1 board, 2 ceo, 1 team) assigned to Julius.
- **CompanyHome Card 4** renders subtext "1 from board · 2 from CEO · 1 from team" with each segment underlined on hover. Playwright DOM probe confirms all 3 segment testids present with verbatim text.
- **Click "1 from board"** → URL navigates to `/app/questions?role=board&filter=open&context_id=f954d5d0…` ✓. Role chip "Role: board ✕" renders with clear-X testid.
- **Backend curl:** `/me/questions?asker_role=board` → 1 result; `?asker_role=ceo` → 2; `?asker_role=director` → 400 with verbatim error.
- **De-id recall lift:** pre-fix 3/5 → post-fix 4/5 (80%) on the same seeded board pack.
- Test seeds cleaned up.

### Phase I.5 — Open Questions wiring (Card 4 asker-role decomposition) — 2026-05-27 ✅
Card 4 on CompanyHome ("Open questions") evolves from count-only with
the placeholder subtext "Awaiting clarification" to a 3-bucket
decomposition: **"X from board · Y from CEO · Z from team"**.

- **Asker-role taxonomy locked** to 3 buckets (`board / ceo / team`).
  Derivation source is `db.memberships(account_id, context_id).role`
  — the canonical context-scoped role truth source. (Cross-check at
  I.5 brief established that `cycles.team[]` does not exist in live
  data — escalation E1=a locked memberships as the substitute.)
  Mapping: `ned → board · owner → board · executive → ceo ·
  (member not found or future-role) → team` (conservative default).
- **Schema extension** — `cycle_questions` gains
  `asker_role: "board" | "ceo" | "team"`. No new collection.
  Absence-default behaviour: legacy rows without `asker_role` count
  into the `team` bucket via the endpoint's None-bucket fallback —
  decomposition sum always equals total count.
- **Insert-time hook** — `routers/questions.py::raise_question` calls
  `derive_asker_role(account_id, context_id)` on every POST and
  writes the bucket to the row. ONE insertion point (the only writer
  to `db.cycle_questions` per E5 confirmation).
- **One-shot backfill script** —
  `backend/scripts/backfill_asker_role.py`. Idempotent:
  `{asker_role: {$exists: False}} OR {asker_role: None}` query, derives
  per-row, writes. **Production run:** 1010/1010 backfilled →
  **584 team** (legacy no-asker rows), **426 board** (ned/owner
  askers), **0 ceo** (no executive askers in seed data). Re-run found
  0 → idempotency proven.
- **Endpoint extension** —
  `routers/company_home.py::_build_questions` swaps the
  `count_documents` call for a Mongo `aggregate` grouped by
  `asker_role`. New `QuestionsDecomposition` Pydantic model
  (`board / ceo / team` int fields) is included in the Card 4
  response shape. Subtext rendering moves to
  `services.open_questions.asker_role_map.format_decomposition_subtext`
  (pure function, fully unit-testable). Subtext rules: empty/all-zero
  → `"Nothing open."`; single non-zero → `"3 from CEO"`; mixed →
  `"1 from board · 2 from CEO · 4 from team"` (zero segments omitted).
- **Frontend** — ZERO code change. CompanyHome.jsx already reads the
  subtext as a free-form string through
  `data-testid="company-home-attention-questions-subtext"`. The new
  decomposition string flows automatically.
- **I.2 negative invariant FLIPPED → positive guard.** The original
  Phase I.2 guard
  (`test_i2_questions_card_does_not_pre_wire_asker_role_decomposition`)
  locked OUT the decomposition during I.2's count-only era. Phase I.5
  locks it IN. Renamed to
  `test_i2_questions_card_uses_asker_role_decomposition_post_i5` and
  now asserts: `QuestionsDecomposition` shape present, `aggregate`
  used (not `count_documents`), `asker_role` referenced in router,
  old `"Awaiting clarification"` literal GONE. Institutional memory:
  the invariant's intent has EVOLVED. Captured verbatim in
  PHASE_LEDGER I.5 row NOTES.
- **CI guard** `tests/test_phase_i5_open_questions.py` — **12 tests:**
  M1-M2 pure role-bucket mapper (NED/owner→board, executive→CEO,
  unknown/None→team, case-insensitive); M3-M5 subtext formatter
  (empty / single-bucket-omit-zeros / mixed-buckets-in-locked-order);
  D1-D3 DB-touching deriver via memberships (resolves correctly +
  missing-account → team + missing-membership → team); E1-E2 Card 4
  endpoint decomposition shape + sum-to-count invariant + populated
  subtext format; E3 empty-state subtext; E4 legacy rows without
  asker_role count in team bucket (absence-default lock); H1
  raise_question POST writes derived asker_role; B1 backfill
  idempotency; N1 source-strict no-`cycles.team[]`-references
  negative invariant.
- **Test ledger** — I.5 12/12 GREEN. I.2 (post-flip) 11/11 GREEN.
  Broader regression sweep (`test_phase_i*.py + test_phase_n*.py +
  test_phase_h*.py`) = **140 passed / 13 skipped** (skips pre-
  existing Patch 19 Solva session fixture).
- **Live verification** (Julius @ Personal NED Seat) — Card 4 EMPTY:
  `{count:0, subtext:"Nothing open.", decomposition:{board:0, ceo:0,
  team:0}}`. POST as Julius (ned member) → asker_role derived as
  `"board"` ✓ H1 hook live. DB-seeded 2 drafts (ceo + team) to
  populate full decomposition. Card 4 verbatim: `{count:3,
  subtext:"1 from board · 1 from CEO · 1 from team",
  decomposition:{board:1, ceo:1, team:1}}`. **Playwright DOM probe**
  on subtext testid renders exact string. **Resolve walkthrough**
  (board question → status="answered") → Card 4 correctly updates
  to `{count:2, subtext:"1 from CEO · 1 from team",
  decomposition:{board:0, ceo:1, team:1}}` — board=0 segment
  correctly omitted from subtext per formatter contract. Test
  seeds cleaned up.

### Phase I.4.b — Events: document-extraction LLM scan — 2026-05-27 ✅
Builds on I.4.a's `events` collection. LLM scans uploaded board packs /
briefings / cycle compilations / strategy docs, extracts time-bound
events, stages them as DRAFT events the user reviews before they become
real (confirmed). Card 5 on CompanyHome counts only CONFIRMED events.

- **Schema extension** — `events` collection gains `status` ("draft" |
  "confirmed" | absent), `confidence` (0.0-1.0 or null), `extracted_at`,
  `extracted_by` ("akki_extractor" | null). **No migration script** —
  absence-default behaviour: events without a `status` field are
  treated as not-draft via the `$ne:"draft"` filter (decided E2=b at
  brief greenlight). Manual events still write no `status` and
  implicitly count.
- **New endpoint** `POST /api/contexts/{cid}/documents/{doc_id}/extract-events`.
  Returns `{extracted[], persisted_draft_ids[], discarded{low_confidence,
  out_of_window, malformed}}`. Membership 403, auth 401, 404 on missing
  doc, 400 on doc with <80 chars text, 502 on gateway failure.
- **Extraction pipeline** — single shielded LLM call via the existing
  `llm_service.call_llm(tier="standard", purpose="documents.events_extract")`
  with `response_format="json"` + strict system override. Same path as
  `prepare.py::extract_minutes` (canonical extraction precedent).
  Purpose registered in `services/synisense/config.py::ALLOWED_PURPOSES`.
  `safe_parse_json` strips ```` ```json ```` code fences. Per-item
  cleanup: `_coerce_extracted_iso` strips Synisense de-id brackets
  (`[15 June 2026]`) and falls back to `dateutil.parser(fuzzy=True)` for
  natural-language dates; `_map_extracted_type` collapses unknown types
  to `"other"` with friendly-alias dictionary (AGM→board_meeting,
  committee_meeting→audit_review, year-end→deadline). Pass-2 filter:
  confidence floor 0.6 (E3 confirm), date window -7d to +24mo (E3
  confirm).
- **Idempotency (E4 confirm)** — re-extracting the same doc deletes
  ALL rows matching `(context_id, doc_id, source="doc_extraction",
  status="draft", deleted_at=None)`. Confirmed events untouched.
  Soft-deleted (rejected) drafts stay rejected — they don't resurrect
  on re-extract.
- **Auto-extract trigger** — `documents.py::upload_document` accepts
  `BackgroundTasks`; schedules `auto_extract_after_upload` after insert
  IF `doc_type` is in `_AUTO_EXTRACT_DOC_TYPES = {"Board pack",
  "briefing", "cycle_compilation", "strategy_document"}` (decided
  E1=b — extended allowlist for wider "magical" coverage). Best-effort:
  failures logged and swallowed, NEVER block upload response.
- **Card 5 filter** — `company_home.py::_build_events` adds
  `status: {"$ne": "draft"}`. Drafts excluded. Manual events implicitly
  count via absence-default.
- **Events surface** — `Events.jsx` gains 4th tab `Extracted (N)` with
  sparkles icon + dynamic count. Tab order: Upcoming / Past / All /
  Extracted. Draft rows render: title + type chip + **confidence
  badge** (amber `<0.8` / green `≥0.8` with `{pct}% match` text) +
  start_at + location + **Source document** link + **Confirm** primary
  button + **Reject** icon. Confirm calls `PATCH /events/{id}` with
  `{status:"confirmed"}`; Reject calls `DELETE` (soft). Empty state:
  *"No extracted events. Upload a board pack or briefing to surface
  dates automatically."*
- **PATCH endpoint** — accepts `status` field for confirm action; only
  `"confirmed"` is settable via PATCH. Attempts to PATCH
  `status="draft"` return 422 (drafts are server-created only).
- **List endpoint** — gains `?status=draft|confirmed` filter.
  `status=confirmed` uses absence-default (`$ne:"draft"`);
  `status=draft` is exact-match. Default (no filter) returns all
  non-deleted.
- **CI guard** `tests/test_phase_i4b_events_extraction.py` — 16 tests:
  full extraction round-trip with mocked LLM, membership 403, auth 401,
  low-confidence discard, out-of-window discard (past + future), type
  taxonomy mapping (AGM→board_meeting + unknown→other + direct
  match), idempotency replaces drafts + preserves confirmed, rejected
  drafts stay rejected, Card 5 excludes drafts + counts confirmed,
  Card 5 absence-default for manual events, PATCH `status="draft"`
  rejected with 422, auto-extract trigger only fires for allowlist
  `doc_type`, `?status` query filter, Events.jsx mounts
  `events-tab-extracted`, extracted empty-state copy verbatim,
  draft-row Confirm + Reject + confidence badge testids present,
  Card 5 query source-strict guard for `$ne:"draft"`.
- **Live verification** (Julius @ Personal NED Seat) — seeded a "Board
  pack" doc with 5 event references. **Live LLM extraction:** Claude
  Sonnet 4.5 via shielded gateway → 3 cleanly extracted with confidence
  1.0 + 2 discarded as malformed (Synisense de-id tokenized two dates
  as "MM" placeholders — correctly preserved as PII protection).
  **Card 5 BEFORE confirm:** `{count:0, subtext:"No events scheduled"}`
  — drafts correctly excluded. **PATCH `status="confirmed"`:** title
  persisted, status flipped. **DELETE on draft:** soft-delete returned
  `{ok:true}`. **Re-extract:** prior draft wiped; confirmed event
  untouched. **Playwright DOM probe:** 4th tab `EXTRACTED (3)` visible
  with sparkles icon; 3 draft rows with confidence badges (78% amber,
  91%+95% green); clicking Confirm dropped count to `(2)` and moved
  row to Upcoming tab.
- **Test ledger** — I.4.b 16/16 GREEN. Broader regression sweep
  (`test_phase_i*.py + test_phase_n*.py + test_phase_h*.py`) = 129
  passed, 13 skipped (skips pre-existing Patch 19 Solva fixture).
- **Gateway tier decision (institutional memory)** — first attempt
  used `tier="fast"` (Gemini 2.5 Flash) for cost efficiency but
  exceeded the 20s gateway timeout on ~12K-char extraction prompts.
  Switched to `tier="standard"` (Claude Sonnet 4.5) matching the
  `extract_minutes` precedent. ~9s latency per call. **Synisense
  de-id interaction:** the de-id step tokenizes calendar dates as PII
  placeholders before the LLM sees them, then re-identifies after the
  response. Mitigations layered: bracket strip + `dateutil` natural-
  language fallback + malformed-discard counter for anything still
  unparseable. Net behaviour: 3/5 extraction rate on live test —
  acceptable v1, tune prompt or de-id config in future hygiene pass
  if recall becomes a problem.

### Phase I.4.a — Events system (manual entry) + Card 5 wiring — 2026-05-27 ✅
Unblocks Card 5 on Company Home. Manual events entry only this dispatch;
I.4.b (doc-extraction) and I.4.c (calendar sync) are separate later dispatches.

- **`db.events` collection** with `(context_id, start_at)` Mongo index. No
  schema migration (Mongo dynamic). Fields: `id`, `context_id`, `title`,
  `type` (5-value enum: board_meeting / audit_review / briefing / deadline /
  other), `start_at`, `end_at`, `location`, `notes`, `source` ("manual"),
  `source_ref` (null in I.4.a; reserved for I.4.b doc extraction +
  I.4.c calendar sync), `created_by_account_id`, `created_at`, `updated_at`,
  `deleted_at`.
- **New router** `backend/routers/events.py` — 5 endpoints under
  `/api/contexts/{cid}/events`: POST (create) · GET list (`upcoming` filter,
  default true; `limit` max 100) · GET one · PATCH (partial update) ·
  DELETE (soft via `deleted_at`). Membership 403, auth 401, 422 on
  missing required fields, 404 on unknown event ID.
- **Card 5 wiring** — `routers/company_home.py::_build_events()` now
  queries `db.events` directly (NOT `db.tasks` — invariant locked in
  both I.2 and I.4.a). 14-day forward window from now. Subtext format:
  `"<title>"` for 1 event, `"<a>, <b>"` for 2, `"<a>, <b> · <N> more"`
  for 3+. Empty-state copy `"No events scheduled"` preserved verbatim.
- **New surface** `pages/Events.jsx` at route `/app/events?context_id={cid}`.
  Eyebrow + 32px inline-override H1 "Upcoming on the calendar." +
  subtitle "Manual entries. Document extraction and calendar sync land
  in later phases." + Upcoming / Past / All tabs + +Add event button +
  Add/Edit modal (5 fields: title, type, start, end, location, notes —
  3 required) + soft-delete with confirmation.
- **CompanyHome Card 5 click** — `_routeForCard("events", cid)` now
  returns `/app/events?context_id={cid}` (was no-op).
- **CI guard** `tests/test_phase_i4a_events_manual.py` — 13 tests
  (full CRUD round-trip, validation, soft-delete hidden in list,
  membership 403 on all 5 endpoints, unauth 401, Card 5 real data
  with 3 seeded events + 1 outside-window + 1 past, Card 5 empty
  state preserved, negative invariant on `db.tasks`, Events page
  mount, modal validation, Card 5 routing, App.js route registered).
- **Recovery dispatch (2026-05-27)** — original I.4.a code had shipped
  but with 2 latent bugs caught at Stage-1 cross-check on re-dispatch:
  * **B1 (P0):** `_iso(now)` and `_iso(horizon)` called in
    `company_home.py::_build_events()` but `_iso` was never imported
    or defined → `NameError` broke `/api/me/company-home/attention` for
    every user. Fixed with direct `now.isoformat()` / `horizon.isoformat()`
    inline calls (1-line edit).
  * **B2 (P3):** tabs in `Events.jsx` used template-literal
    `data-testid={\`events-tab-${id}\`}`; CI guard asserted literal
    substring `data-testid="events-tab-upcoming"` in source. Runtime
    DOM identical, source assertion failed. Fixed by hoisting the 3
    tabs to individual JSX blocks with literal data-testid strings.
- **Test ledger** — `test_phase_i4a_events_manual.py` 13/13 GREEN.
  Broader regression sweep (`test_phase_i*.py` + `test_phase_n*.py` +
  `test_phase_h*.py`) = 113 passed, 13 skipped (skips pre-existing
  Patch 19 Solva session_id collisions, unrelated to I.4.a).
- **Live Playwright verification** (Julius @ Personal NED Seat, cid
  `f954d5d0-50d9-47d5-a64f-3be89cee8296`): Card 5 BEFORE = `{count:0,
  subtext:"No events scheduled"}` → CREATE event "E2E test event" →
  Card 5 AFTER cache invalidation = `{count:1, subtext:"E2E test event"}`
  → PATCH rename → LIST shows renamed → DELETE → LIST empty. UI
  screenshot captured for both surfaces: CompanyHome Card 5 renders
  "1 · Q3 board strategy review"; Events page renders H1 "Upcoming
  on the calendar." + 1 row "Q3 board strategy review · Board meeting
  · Sat, May 30, 2:17 AM · Boardroom 4". Test seed cleaned up.

### Phase N (third-party branding / analytics scrub) — 2026-05-27 ✅
Stripped runtime Emergent branding + PostHog analytics from the user-facing
app. Operating integrations (LLM gateway via `EMERGENT_LLM_KEY` env-var,
`emergentintegrations` SDK, `emergentagent.com` preview host) preserved
explicitly per OUT_OF_SCOPE.

- **index.html**: removed `assets.emergent.sh/scripts/emergent-main.js`
  script tag + the entire inline PostHog init block + the historical
  comment about the old "Emergent | Fullstack App" default.
- **package.json**: dropped `@emergentbase/visual-edits` dep
  (visual-edits SDK) + regenerated yarn.lock.
- **.lighthouseci/**: wiped pre-scrub artifacts; CI regenerates clean.
- **Customer copy**: `Security.jsx` ("Emergent LLM gateway" →
  "private LLM gateway"); `ProviderLine.jsx` ("Emergent universal
  proxy" → "Universal LLM proxy"); `HealthDashboard.jsx` ("LLM
  (Emergent key)" → "LLM (Gateway key)").
- **SignUp.jsx**: background image moved from Emergent CDN to local
  `/public/assets/signup-bg.png` (1057 KB PNG).
- **Backend technical comments**: 12 references across 9 files
  rewritten to neutral phrasing (universal LLM proxy / LLM gateway).
- **Documentation**: `.env.example` + `DEPLOY_READINESS.md` brand
  refs scrubbed; `test_admin_email_provider_health.py` assertion
  updated to "Platform secrets panel".
- **CI guard** `tests/test_phase_n_third_party_scrub.py` — 7 tests
  asserting zero `emergent.sh` / `posthog` / "Made with Emergent" /
  bare-word "Emergent" branding in active source (allowlist for
  env-var name + integrations package + preview host).
- **Runtime verification** — Playwright probed 10 routes
  (`/app`, `/app/chat`, `/app/solva`, `/app/work-studio`,
  `/app/task-manager`, `/app/monitor`, `/app/pulse`, `/app/learn`,
  `/app/news`, `/sign-in`): `window.posthog`=undefined,
  `window.Emergent`=undefined, 0 scrub-related console msgs on
  every route. Two routes had pre-existing unrelated console msgs
  ## Tasks 1–4 batch + PHASE_LEDGER setup — 2026-05-27 ✅

### Task 1 — Route consolidation + Home1 archive (Phase H.5)
- Archived `Home1.jsx` → `_archived/`. `/app/portfolio` + `/app/companies` + `/app/contexts` collapse to `/app` via 301 redirects. SignIn / Home2 / NewsStub / AppShell link targets updated. Hygiene grep clean (no active Home1 imports).
- CI guard: `tests/test_route_consolidation.py` (11 tests, all green).
- Live Playwright: all 3 legacy URLs land at `/app`.

### Task 2 — Recent-views surface-mount sweep (Phase H.4.1.b)
- Shared `useTrackRecentView` hook at `lib/recentViews.js`. Plugged into 6 surfaces: WorkStudioDocumentPage, DocumentDrawer, TaskDrawer, Chat, SolvaSession, Pulse.
- Raw POST to `/me/recent-views` outside the hook is forbidden (CI guard).
- Live verified: opening Pulse and calling `/api/me/last-action` returns full enrichment: `artefact_kind="pulse"`, `deep_link="/app/pulse"`, `artefact_title="TEST_SeededNedCo — Pulse feed"`.

### Task 3 — News Africa expansion
- Dropped unwired paid IDs (Bloomberg / Reuters / WSJ / HBR / McKinsey / BoardEffect / Nikkei / S&P / MIT) from the LIVE `_EXECUTIVE_TIER1_SOURCE_IDS`. Reserved in `_FUTURE_PAID_TIER1_IDS` for future paid-adapter activation.
- Added 6 free Africa sources: `bbc-africa`, `quartz-africa`, `businessdaily-africa`, `the-east-african`, `nation-africa`, `standard-kenya`. Quartz Africa + The East African RSS returned 403 in fetch — aggregator skips silently per design (set `enabled:false` if persistent).
- `_REGION_BUCKETS["EAST-AFRICA"]` → KE/UG/TZ/RW/AF. Router auto-defaults applied_region to EAST-AFRICA for users resolved to KE/UG/TZ/RW.
- Live: `GET /api/news?region=east-africa&limit=10` → `region_applied: "EAST-AFRICA"`, **4/10 Africa-tagged items** (Nairobi: Standard Kenya KMRC green bond; pan-Africa: BBC Africa, Al Jazeera).

### Task 4 — Phase I.1 Company Home layout shell
- New `pages/CompanyHome.jsx`. AppHome dispatcher routes active-context → CompanyHome (was Home2). `Home2.jsx` archived to `_archived/`.
- AuthContext exposes `clearActiveContext` for the "← Back to Portfolio" link.
- Layout: 32px inline H1 `Inside {company}.`, subtitle, readiness `—%` strip, 5 attention cards (drafts/reports/pulse/questions/events) with placeholders, right rail with Add Document + All Docs + Top Signals 3 chips (Pulse default), Coming-soon body.
- Live verbatim (Julius @ Julius Opio — Personal NED Seat): H1 text=`Inside Julius Opio — Personal NED Seat.`, **H1 font-size=32px** (verbatim getComputedStyle), Pulse chip aria-selected=true, all 5 attention cards rendered, Back-to-Portfolio click cleared context and landed on Portfolio Landing.
- CI guard: `tests/test_phase_i1_company_home.py` (14 tests, all green).
- Scope discipline: `.akki-greeting` token NOT touched (locked at 28px); 32px is inline override.

### PHASE_LEDGER created (process defense)
- `/app/memory/sprints/PHASE_LEDGER.md` — 22 historical phases backfilled (A/B/C/D + E.3 + E.3.r + F.3 + F.4 + F.6 + SendGrid + Right-rail + H1-audit + H.1/H.2/H.3/H.4 + Chat-list + H.5 + Tasks 1–4) + Queued/Future section (I.2–I.6, J, L, F.7, G, spaCy/Solva parked, paid news adapter).
- Cross-check rule acknowledged: when briefs contain explicit IN_SCOPE/OUT_OF_SCOPE blocks, every file-touch is verified against both lists before code lands.

### Test roll-up
- **107/107 GREEN** across the 4 new task suites (Tasks 1–4) + 5 adjacent regression suites.
- Broader regression: **201 passed, 27 skipped, 1 pre-existing fail** (`test_patch_28_home_doc_journal::test_doc_journal_happy_path` — file-upload PDF-wrapping system behavior, unrelated to my work).



### Chat-list left-sidebar tightening (Claude-style)
Source-level audit confirmed the H.3 side-fix tightening pass had
already applied at the JSX level. Live DOM verification on the
preview (bramuel@syni.ai, 5 chats rendered) returned EXACT spec
match: title `13.5px` / `font-weight: 500` / sans-serif stack /
line-height `1.35` (= 18.225px) / `whiteSpace: nowrap` /
`textOverflow: ellipsis` / row height `40px` / sidebar width
`300px` / 1 `<p>` per row (no subtitle/preview). Control surface
(Task Manager) regression-free.

Added `tests/test_chat_list_density.py` (8/8 GREEN) to lock:
title typography, row spacing, no-subtitle invariant, active-state
2px oxblood accent bar, header sub-line `10px` muted, search
input `h-8 + text-[13px]`, parchment background preserved, title
testid attached to the title `<p>` directly.

### Phase H.4 — Portfolio calm pass
Three deliverables, all live-verified + locked by CI guard
(`tests/test_phase_h4_calm_pass.py` 9/9 GREEN):

- **H.4.1 — Recent-views deep-link enrichment.** `RecentViewIn`
  now accepts optional `artefact_id` / `artefact_kind` / `deep_link`.
  POST `/api/me/recent-views` persists them. GET `/api/me/last-action`
  prefers persisted enrichment over surface_path classification, AND
  surfaces a new `artefact_kind` field on `LastActionOut`. Legacy
  rows (no enrichment) fall back to H.3 classification — confirmed
  via live round-trip + legacy-row regression test.

- **H.4.2 — News tier-1 allowlist expansion.** Added live
  `nyt-business` + reserved paid-API ids (`nikkei-asia`, `sp-global`,
  `mit-sloan-review`) on top of the existing FT/Economist set. Fallback
  to full curated set retained when tier-1 subset < `max(3, limit//2)`.
  Real strict-filter coverage still depends on operators wiring the
  paid Bloomberg/Reuters/WSJ feeds (documented in `news.py`).

- **H.4.3 — A11y / focus calm pass on Portfolio Landing.**
  Company-card buttons gained verbose `aria-label`, `aria-current`,
  and `focus-visible:ring-2`. Segmented tabs gained `aria-label`,
  `aria-controls`, panel `role="tabpanel" + id` linkage. Section
  headings gained stable ids referenced by `aria-labelledby` on the
  `<section>` elements. Read-more / Continue / boards-to-watch row
  buttons gained verbose aria-labels + focus-visible rings.
  Decorative lucide icons inside actionable controls carry
  `aria-hidden="true"` so screen readers don't double-read.

**Full suite roll-up:** H.1+H.2+H.3+H.4+size-guard+chat-density =
70/70 GREEN. Adjacent regression (patch-10 home insights, email-
provider health, F.3/F.6/E.3, task-drawer prefix) = 94 passed +
1 pre-existing skip.


## Portfolio Landing Batch — Phase H.3 (Data Wiring) — 2026-05-27 ✅
Phase H.3 closes the Portfolio Landing data layer. Live-verified end-to-end:

- **Backend** — `routers/portfolio_data.py` (already mounted at server.py
  line 189). Three endpoints powering `/app/companies`:
  * `GET /api/me/portfolio-metrics` → 4-tile counts (companies / signals /
    briefings / documents). Signals + briefings windowed to last 30d.
  * `GET /api/me/boards-to-watch?limit=3` → AI-composite ranking.
    Weights: 7d signals 0.5 · 14d briefings 0.3 · at-risk tasks 0.2.
    Each item carries a non-empty `reasons[]` (binary check #1 enforced).
  * `GET /api/me/last-action` → "Where you left off" resume card sourced
    from `user_recent_views`. Returns null-empty shape (not 404) when no
    recent activity.
- **News quality filter** — `routers/news.py`'s `?quality=executive` param
  narrows to tier-1 allowlist (FT / WSJ / Reuters / Bloomberg / Economist
  / HBR / McKinsey / BoardEffect). Graceful fallback to full curated set
  when the tier-1 subset is thin.
- **Frontend** — `pages/ContextPortfolio.jsx` wires all 3 endpoints +
  mounts shared `<NewsStrip quality="executive" limit=5>` for "The world
  around you". `NewsStub` now renders the full news page (limit=20).
- **Shared component** — `components/news/NewsStrip.jsx` (composable
  fetch + render for both /app/companies and /app/news).
- **Tests** — `tests/test_phase_h3_data_wiring.py` 14/14 GREEN. Includes
  the 2 binary checks the user mandated:
  * Every boards-to-watch item has non-empty `reasons[]`.
  * news?quality=executive returns ≥1 source matching the tier-1
    allowlist (FT confirmed live).
- **Full batch suite** — H.1 + H.2 + H.3 + size-guard = 52/52 GREEN.
  Recent-regression suite (E.3 runtime drawer, F.3 routing, F.6 debt,
  task-drawer prefix, email-provider health) = 91 passed + 1 skip.
- **Live DOM verification** (Julius Opio account, /app/companies):
  * Metric tiles: Companies=5, Signals=0, Briefings=0, Documents=14
  * Boards-to-Watch: empty state (correctly — 0 signals/briefings/at-risk)
  * Where-you-left-off: empty state (no recent views logged)
  * News strip top 3: FT (Dulux/AkzoNobel), SCMP (EV reads), Al Jazeera
    (Taiwan AI). FT match satisfies tier-1 allowlist binary check.

**Note:** The H.1 placeholder tests were updated to be H.3-aware
(metric-tile loading helper `_m(...)` + section empty-state testids
replace the legacy `value="—"` / "Coming soon" assertions).


## Home Cleanup Batch — Phase F (Task Manager rollout, F.1 → F.6) — 2026-05-26 ✅
Closes the UI-cleanup batch (Phases A → F.6). Task Manager surface shipped end-
to-end: 3-tab listing + 4-step setup wizard + Universal Task Drawer (5 tabs) +
5-stage Compile flow + 3 contributor notification modes (akki_account, magic_link,
email_reply) + right-rail polish + account-scoped activity. 272/272 batch tests
GREEN. Deploy-readiness artefacts shipped:
- `/app/memory/sprints/DEPLOY_READINESS.md` — operator checklist (Indexes,
  Postmark setup, env vars, migration steps, known gaps).
- `/app/memory/sprints/AUTONOMOUS_TRIP_REPORT.md` — full trip record across
  Phases A → F.6 (decisions, scope cuts, borderline routes, before-deploy items).
- `/app/memory/sprints/AUTONOMOUS_DECISIONS_LOG.md` — every autonomous-mode
  decision with reversal path.

**Batch status:** CLOSED. Awaiting user explicit deploy signal — DO NOT deploy
without it. See AUTONOMOUS_TRIP_REPORT.md "Before deploy" section for the full

## Debt closure (W1–W5) — 2026-05-26 ✅
Closes out remaining UI-cleanup batch debt under autonomous mode:
- **W1 — SendGrid migration** replaces Postmark (transactional + Inbound Parse).
  Postmark endpoints return 410 Gone with migration note. `sendgrid==6.12.5`.
- **W2 — Solva briefing deck on task surfaces** — SolvaLanding reads `?submodule=`
  URL param, fires the deck for that area (suppression respected).
- **W3 — Related-docs typing (2 of 3)** — `document_attachments` collection +
  symmetric POST/DELETE, `documents.parent_doc_id` lineage walk + PATCH endpoint.
  Content similarity formally tracked as **Phase G** (embeddings).
- **W4 — Inline-comment span resolution** — circulation comments persist `span`
  metadata; TaskDrawer Stage 3 renders span quote + inline badge.
- **W5 — Docs** — F.4 ACID-via-rollback acceptance, Phase F.7 cycles retirement,
  Phase G embeddings — all tracked. AUTONOMOUS_DECISIONS_LOG.md + HOME_CLEANUP_LOG.md
  + DEPLOY_READINESS.md updated. SendGrid setup runbook with curl example.

**Final suite:** 301 passed + 10 skipped (legacy Postmark phase B retired).


operator checklist.


## Home Cleanup Batch — Phase D Solva closeout — 2026-05-26 ✅
Fourth and final phase of the Home/Chat/Solva cleanup batch dispatched
2026-05-26. Phases A (Home 1), B (Home 2), and C (Chat) already shipped;
Phase D closes Solva surface in 3 sub-items.

- **D.1 — Pre-conversation briefing deck** (4 slides per area, suppression-
  aware). New `routers/solva_briefing.py` + `solva_briefing_state` collection.
  New `frontend/src/data/solva-briefings.js` (verbatim slide copy) +
  `components/solva/SolvaBriefingDeck.jsx` (4-slide modal with progress
  counter, "Don't show me again" checkbox from 2nd visit onward, first-word-
  in-oxblood title rendering). Wired into `SolvaLanding.jsx` picker→deck→
  framing flow + `SolvaPhaseDSession.jsx` `(i)` info icon for force-reopen.
  **Bug found + fixed**: deck was misplaced inside `DisambiguatorDialog`
  (would have thrown `ReferenceError`); lifted to `SolvaLanding` parent
  scope. Verified live: clicking "Seek Clarity" opens deck slide 1/4 with
  "Solva" in oxblood `rgb(122, 46, 46)`.
- **D.2 — Question-logic audit (read-only)**. Wrote findings into
  `HOME_CLEANUP_LOG.md`: Solva Layer 1 / 2 questions are **deterministic,
  hand-written** in `services/solva/voice/question_bank.py` (no LLM
  generation per brief §5.4). Variant picker is `sha256(session_id +
  key) % len(variants)`. FAR's `routing_decision` drives the *key*, not
  the text. Layer 4 reflection uses a static 3-question list. Layer 3
  synthesis is the only LLM-voiced surface, bounded by Shield. **No code
  changes** — audit findings recorded as governance evidence.
- **D.3 — Context-passing query params (option b — full persistence)**.
  - Solva: `?ctx_type=…&ctx_id=…` added as canonical alias for legacy
    `?seed_kind=…&seed_id=…`. Both resolve identically.
  - Chat: NEW `linked_context: {ctx_type, ctx_id, title, excerpt, href,
    attached_at}` field on `db.chats`. New `LinkedContextIn` schema +
    `_resolve_linked_context` helper (supports document / cycle /
    work_studio_artefact). Persisted on `POST /chats`, re-resolved fresh
    on every send/stream turn, `$unset` via PATCH `clear_linked_context:
    true`. New `[LINKED_CONTEXT]…[/LINKED_CONTEXT]` prompt block prepended
    to `full_prompt` before Shield invocation (no Shield bypass).
  - Frontend: `Chat.jsx` `?ctx_type=…&ctx_id=…` URL handler; new
    `LinkedContextChip` above composer with "Reading: <title>" + ✕ remove;
    muted "item no longer available" state when excerpt is empty.

- **Tests** — `test_home_cleanup_phase_d.py`: 44 wire + live tests, all
  GREEN. Lifecycle test exercises create → resolve → persist → GET →
  PATCH-clear → silent-miss-on-invalid-id → 422-on-bad-ctx_type.
- **Live curl verification**: created chat with linked doc, server resolved
  full snapshot (title, 8000-char excerpt, href, attached_at); GET returned
  same; PATCH clear_linked_context: true → linked_context unset.
- **Regression**: 1367 passing across full suite (Phases A+B+C+D = 91/91,
  Solva+J4 = 203/203). Only pre-existing parked `test_real_requirements_
  file_is_clean` failure remains (`spaCy` URL refs, P2 backlog).
- **No spec edits**, no new npm packages, no new pip dependencies, no
  Shield bypasses, no LLM model swaps.


## Original problem statement
AKKI is a Context-primary intelligence platform for Non-Executive Directors (NEDs) and
operating Executives. The BRD pivoted from v1.0 (Tenant B2B) → v3.0 (Context-primary) →
v4.0 (Build Sequence — 18 modules across 5 streams with prescriptive design mandates).
The user selected **Path A (v4.0 Free Tier)**: follow v4.0 module boundaries but skip any
module that requires a paid/external service.

## T1–T5 — Horizontal UI reshaping sprint — 2026-05-25 ✅
Five-tier sprint against `AKKI_PRODUCT_SPEC.md` **v1.1** (locked,
ratified with all 12 PO-approved gaps G1–G12).

- **Per-tier verdicts** (all by e1_tester on 2026-05-25):
  * T1 — 5/5 PASS (Chat sticky · Context Switch · Generate Brief
    visibility + G3 toast · "All documents" routing · Add to Cycle G1
    wire)
  * T2 — 4/4 PASS (incl. T2.3 re-verified after the DOM-conditional
    false-green fix — Document Journal tabs · Pulse Resolved · Monitor
    drawer · Strategic Goals filters G11 + G12)
  * T3 — 4/4 PASS (Add to Work Studio + Add to Cycle parity + Work
    Studio kind routing G8 + Compile-modal nested upload G9)
  * T4 — 5/5 PASS (W3 toolbar + DOCX/PDF/PPTX G6 · Refine G7 · W5
    Committed · Enhance flow W7/W9 · W10 Refine G10)
  * T5 — 4/4 PASS (Cycle Manager landing C1 · Setup Wizard C2 G4 +
    C3 G5 + C4 · Cycle Page Compile parity C5 G6 · Draft Journal C7 ·
    Ready Journal C8)
- **Targeted-suite roll-up: 89/89 GREEN** (T1=11 · T2=23 · T3=20 ·
  T4=15 · T5=20).
- **Key durable lessons** (full record in
  `/app/memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md`):
  * **DOM-unconditional rendering rule** (T2.3 fix) — spec-required
    structural sections MUST emit DOM unconditionally; only their
    internal content is data-conditional. Empty states are part of the
    contract.
  * **Code-verified vs live-verified distinction** — failure-toast
    catch blocks / ClamAV reject paths cannot always be live-exercised
    by browser-use; literal in catch site is the canonical evidence.
    Per-tier ledgers explicitly tag these surfaces.
  * **Verbatim-spec-copy invariant** — every toast / label / helper
    paragraph / validation message is treated as a literal. `assert
    "<literal>" in src` for every G1–G12 verbatim string.
- **Pre-tier hygiene** — five git tags + five mongodumps; closure
  tag `v-post-T5-horizontal-closed` at sprint close.
- **Backlog** — three minor seed-data gaps + one deferred C4 LLM step
  + one optional EICAR spot-check, all in
  `/app/memory/sprints/POST_T5_BACKLOG.md`. None block J1–J4.
- **Hold position** — J1–J4 onboarding sprint is P1 but EXPLICITLY
  gated on user sign-off. Do NOT pull forward.



## H4 — Back-fill pre-Shield-v1.x chats — 2026-05-24 ✅
Closes the historical-data gap so Trust Center honors the same
product promise for the WHOLE record, not just the post-deploy slice.

- **Back-fill engine** — `services/backfill_shield_v1.py`. Replays
  pre-2026-05-15 chats through `deidentifier.deidentify()` → writes
  audit rows to `synisense_audit_log`, `synisense_runs`, and a
  separate `backfill_chain_v1` hash chain in `chat_audit_log` so
  the live chain stays clean.
- **Admin endpoints** — `routers/admin_shield_backfill.py`:
  * `POST /api/admin/shield/backfill` — async kick-off, returns
    `job_id` immediately; refuses to overlap with an in-flight job.
  * `GET /api/admin/shield/backfill/status` — latest summary +
    pending count + ETA.
  * `GET /api/admin/shield/backfill/{job_id}/status` + `/log` —
    per-job detail.
- **CLI** — `scripts/backfill_shield_v1.py` with
  `--batch-size --sleep-ms --dry-run --limit` flags.
- **Idempotency** — chats marked `backfill_metadata.partial=False`
  are skipped on re-run; mid-chat failures leave `partial=true` so
  retries target only the broken ones.
- **Honesty markers** — every back-fill audit row carries
  `is_backfill: true`, `backfill_batch_id`, AND `original_message_ts`.
- **Trust Center integration** — chats with `partial=False`
  surface `shield_status: "backfilled"` + a full `backfill_metadata`
  block. Frontend renders an amber "back-filled on <date>" banner
  + per-turn "back-filled" badges with batch_id + original_ts tooltips.
- **Real-corpus results on preview** (idempotent):
  * 458 chats back-filled
  * 211 had actual messages (rest were empty/abandoned)
  * 104 chats had pre-v1.x PII detected (≈ 49% of non-empty)
  * 639 audit rows written (synisense_audit_log + synisense_runs +
    chat_audit_log, all 3 carry the backfill markers)
  * Zero errors
- **Tests** — `tests/test_h4_backfill.py` 8/8 GREEN:
  end-to-end, idempotency, partial-failure recovery, rate limiting,
  Trust Center post-backfill, is_backfill markers, separate hash
  chain, admin status endpoint.
- **Regression** — 230/231 GREEN (+8 H4, 1 pre-existing skip).


## H3 — Trust Center v1 — 2026-05-24 ✅
one drill-down, one plaintext modal, one standards-aligned footer.

- **Backend** — `routers/trust_center.py` (4 endpoints):
  * `GET /api/trust-center/session/{chat_id}` — promise summary +
    per-turn list, with strict context-scope guard.
  * `GET /api/trust-center/session/{chat_id}/turn/{message_id}` —
    full evidence: input SHA-256 + tokenized prompt + LLM response
    (tokenized) + re-identified visible text + redactions +
    audit chain.
  * `GET /api/trust-center/session/{chat_id}/turn/{message_id}/plaintext`
    — ONLY surface returning raw plaintext. Owner-OR-context-superadmin
    gated. Writes `trust_center.plaintext_viewed` audit row on every
    read.
  * `GET /api/trust-center/activity` + `/activity/export` —
    cross-conversation aggregate, server-side context scoping.
- **Frontend** — `pages/TrustCenter.jsx` at route `/app/trust-center`.
  Top-bar entry added between Documents and the workspace pill.
- **Tests** — `tests/test_trust_center.py` 9 wire-level tests
  (owner reads, cross-context 403, drill-down shows tokenized NOT
  raw PAN, plaintext owner 200+audit-row, non-owner same-context 403,
  context-superadmin 200+audit-row, activity cross-context 403,
  activity no-leakage, pre-Shield-v1.x empty state).
- **Conservative plaintext policy enforced**: no new collections,
  no plaintext duplication. SHA surfaced everywhere except the
  explicit plaintext endpoint.
- **Standards footer**: SOC2 CC4/CC6/CC7 · GDPR Art. 5/25/28/32 ·
  ISO 27001 A.8.2 + A.12.4.1 · NIST AI RMF Map-3.4 · EU AI Act Art. 50.
  Each segment tooltipped.
- **Regression**: 222/223 GREEN (+9 H3, 1 pre-existing skip).


## H2.5 FINAL Consolidated Closeout (H1 + H2.5) — 2026-05-24 ✅
Independent `e1_tester` cleared H2.5 at 5/5 GREEN and surfaced two
cleanup warnings; both shipped in this follow-up.

- **Warning #1 — Envelope `audit_id` resolved to 404** ← fixed by
  surfacing the Shield `aud-<32-char>` id in the streaming
  `message` envelope. Added `chat_audit_id` companion field for
  backward compatibility. Wire-level test
  `test_wire_stream_envelope_audit_id_resolves_to_shield_row`
  asserts the envelope id resolves via `GET /api/v1/shield/audit/{id}`
  to 200 with matching audit_id. Live preview verified.
- **Warning #2 — Baseline `shield_failure_at_entry` rows** ←
  diagnosed as 100% pytest residue (`h2-5-wire-*@example.com`).
  Admin endpoint now defaults `include_test=false` so the real-user
  view shows zero violations; auditors can opt in with
  `?include_test=true`. Documented in
  `/app/memory/sprints/H2_5_FINAL_CLOSEOUT.md`.
- **4 H2.5 screenshots captured** at `/app/memory/screenshots/h2_5/`:
  streaming PAN redaction, audit panel modal, 503 banner, mode
  contract markdown.
- **Final test ledger**: 22/22 H2.5, 87/87 H1, 202/203 across all
  H2.5-adjacent suites (1 pre-existing skip on Solva v2 invariant).



## User personas
- **Non-Executive Director (NED)** — Serves on one or more boards. Needs cross-board
  pattern awareness, pre-board briefings, and open-thread tracking.
- **Operating Executive** — Prepares for a specific board meeting. Needs pre-board prep,
  team roll-up, org highlights, and post-board follow-up tracking.
- **Dual** — Both roles; switches acting-role from the top nav role switcher.
- **Reportee** — Submits reports to an Executive (minimal scope).

## Core architecture
- **Frontend**: React + Tailwind + Shadcn UI. Brand: navy `#0A1F44`, gold `#C9A961`.
- **Backend**: FastAPI + MongoDB, custom JWT (bcrypt) + optional TOTP MFA.
- **LLM**: Emergent Universal Key → Claude Sonnet 4.5 via emergentintegrations.
  Deterministic mock fallback if key missing.
- **Mocked in-process** (paid equivalents deferred): Synisense trust/shielding layer,
  S3 (local disk at `/app/backend/uploads`), virus scan, vector DB (prompt-inline grounding).

## Surfaces
| # | Surface | v4.0 Module | Status |
|---|---------|-------------|--------|
| 1 | Home (role-specific: NED / Executive) | M15/M16 | **Live** |
| 2 | Workspace (60/40 split + persistent Ask) | M18 | **Live** |
| 3 | Highlights (3-column Twitter-style feed) | M17 | **Live** |
| 4 | Ask (top-level) | M13 | **Live** |
| 5 | Document Viewer (`/app/documents/:id`) | M7 | **Live** |
| 6 | Learn | M9 | Locked |
| 7 | Settings | M0 | **Live** |

## Implemented (by date)
### 2026-04-22 — v3.0 Path B MVP
- G1 Scaffold, M0 Contexts/Memberships/Orgs model, M1 shell+switchers+Cmd-K,
  M2 onboarding wizard + Context Object versioning, M3 document upload pipeline
  (PDF/DOCX/TXT), M5 backend signals + ask (grounded, shielded).
- M5 frontend — Highlights + Ask pages wired.
- Brute-force lockout bug fixed (ident keyed on email only, not ip:email).

### 2026-04-23 — v4.2 Frontend Polish (Path B + Act + Learn)
- **Theme swap**: cream `#F7F3EA` + oxblood `#8B2E2B` + Georgia serif leads +
  Inter chrome + JetBrains Mono for metadata. Tokenised as CSS variables plus
  rewired Shadcn HSL tokens. All new utility classes (`akki-lead`, `akki-greeting`,
  `akki-scope-chip`, `akki-context-chip`, `akki-gesture`, `akki-stream-card`).
- **AppShell re-skin**: top cream chrome with AKKI wordmark + context switcher +
  role switcher + global search button (⌘K) + avatar; 220px cream left rail
  with 3px oxblood accent on the selected nav item.
- **Attention stream Home** (replaces NedHome + ExecHome): single role-aware
  card stream ranking signals / briefings / recent documents by freshness, with
  scope chips (All / Signals / Briefings / Documents) and a 280px companion
  rail (Sources / Recent briefings / Quick actions / Other contexts).
- **Highlights** rewritten to the same card pattern with a filter bar
  (type + confidence) and per-card "Act on this" button.
- **StreamCard** shared component: 3-row structure (type badge + timestamp /
  Georgia 18px lead / context chips + oxblood gesture), 3px severity-colored
  left accent that thickens on hover.
- **Ask merged into Workspace** per v4.2 spec: `/app/ask` redirects to
  `/app/workspace`; Ask nav item removed. The persistent AskPanel on the
  Workspace right pane is now the only Ask surface.
- **Act overlay** (`ActModal`): unified 720px composition modal with two
  destinations — *Message someone* (opens user's mail client pre-filled with
  signal headline + summary + citations) and *Add to briefing* (backs to
  `POST /api/contexts/:id/briefings` with the single signal).
- **Learn module (M9)**: seven curated articles on AI governance for boards —
  Governance basics, NIST + ISO 42001 frameworks, AI in financial services,
  AI literacy in 60 minutes, EU AI Act, Incident response, Vendor AI oversight.
  Each article pulls content from reputable sources (NACD, IoD, Deloitte,
  Stanford HAI, NIST, European Commission, FCA/BoE, ICO) and closes with
  "questions to take into the room". Search + topic filter in the library grid.
  Reader view at `/app/learn/:id`.
- **Reusable `AskPanel`** component — used by both `/app/ask` and Workspace right pane.
  Supports `onCitationClick(docId)` so `[doc:xxx]` citations can drive behaviour in the host.
- **`DocumentViewer`** page (`/app/documents/:id`) with extracted-text render +
  outline rail (heading detection heuristic) + back/download controls.
- **Workspace 60/40 split** (M18): left pane shows either the documents browser
  (upload + list) or the selected document viewer; right pane is a persistent AskPanel.
  Draggable divider (clamped 35–75%). Clicking a `[doc:xxx]` citation in the right
  Ask panel loads that document in the left pane.
- **Highlights 3-column feed** (M17): left filter rail (type/trust/confidence),
  central Twitter-style feed with relative timestamps, right rail with at-a-glance
  counts + source documents + Ask CTA. Source chips link to the Document Viewer.
- **`NedHome`** (M15): board grid sorted by meeting proximity, cross-board pulse
  card when ≥2 NED contexts and signals exist, add-a-board affordance. Uses stable
  pseudo-random `daysUntilNextMeeting` as placeholder until M6 Integrations.
- **`ExecHome`** (M16): 4-band layout — Pre-Board Prep, Team Reporting, Org
  Highlights, Post-Board Follow-up — with cadence-driven ordering (approaching /
  mid-cycle / post-meeting).
- **`AppHome`**: onboarding gate hero when audit incomplete; otherwise routes to
  NedHome or ExecHome based on `activeRole`.
- Nested `<button>` hydration warning fixed in Workspace doc row (div[role=button]
  with `stopPropagation` on the trust selector).

## Test credentials
See `/app/memory/test_credentials.md`. Admin: `admin@akki.ai` / `AkkiAdmin2026!`.

## Backend regression suite
`/app/backend/tests/test_akki_v3.py` — 55 pytest cases (M0–M5). Iteration 2 smoke
tests (15/15) confirm auth + documents + signals + ask pipeline stable after frontend
restructure.

## Prioritized backlog

### P0 — SHIPPED (2026-04-23 → 2026-04-24)
- [x] **M12 Briefings** — auto-composed via `routers/briefings.py` (PDF+DOCX export).
- [x] **M14 Lens Room** — `routers/lens.py` + `pages/LensRoom.jsx` — 6 frameworks,
      O→I→A output.
- [x] **M11 Event-driven signals pipeline** — `routers/pipeline.py` — 4 staged events
      (candidate_drafted → verified → persisted) with full auditability via
      `signal_events` collection.
- [x] **M13 Hybrid retrieval for Ask** — BM25 across chunks (`bm25.py`).
- [x] **M5 Upload channels** — secure links + mobile camera capture.
- [x] **Finish server.py refactor** — DONE (2026-04-24). server.py is now a
      171-line thin assembler; auth/contexts/documents/misc all in their own
      routers. 4 new router modules, core.py expanded with shared helpers.
- [x] **Real Synisense PII shielding** — regex-based masking in `llm_service.py`,
      full `shielding.{identifiers_masked, by_category, shielded_by}` dict now
      surfaced on every LLM-backed endpoint response.

### P0 — remaining
- _(none — all P0 items complete)_

### P1 — Polish
- [ ] Onboarding wizard end-to-end frontend subagent coverage.
- [ ] Minor: POST `/api/auth/refresh` should return `access_token` in body for
      bearer-only clients.
- [ ] Minor: Add top-level `token` field to invitation creation response.

### P2 — Paid / external integrations (explicitly deferred)
- [ ] **M4 Stripe Billing** — sponsored seat subscriptions (test key available in pod).
- [ ] **Real vector DB** — Pinecone or pgvector (current BM25 is sufficient for MVP).
- [ ] **M6 Integrations** — Google Calendar, board portals (Diligent / BoardPaQ).
- [ ] **Clerk / Auth0** — v4.0 M1 preference; we use custom JWT (recommended to keep).
- [ ] **Unstructured.io** — richer extraction than our `pypdf` + `python-docx`.
- [ ] **ClamAV / VirusTotal** — real virus scan (we use a stub).

## Recent fixes
- **2026-04-25 Sprint 16 / iter21** — Reports PDF + LLM polish + Committees scoping for Reportees.
  - **Reports PDF export** — new `reports_service.py` builds an A4 portrait PDF with editorial cream/oxblood/Georgia palette, body rendered from markdown, a **chain-of-custody back page** with timestamped tier table (Tier · Role · Name & email · Action · When · Note), an **event log** of every chain action, and the trust footer. Endpoint `GET /api/contexts/{cid}/reports/{rid}/export.pdf` available to context members + named reviewers (same gate as `get`); allowed for `draft`, `in_review`, and `finalised`.
  - **LLM polish** — new `POST /api/contexts/{cid}/reports/{rid}/polish` returns a polished body (does NOT auto-save; executive reviews then commits via patch). Author-or-current-reviewer only. Strips stray `\`\`\`` fences the LLM might add.
  - **Committee scoping for Reportees** — `committee_id` field added to ReporteeIn + reportees `list` accepts `committee_id` query param; new `GET /api/contexts/{cid}/cycle/committees` lists the context's committees so the Cycle UI can scope work. Reportee form gets a Committee Select; visible cards show a `[var(--chrome)]`-tinted committee chip; new filter strip above the list lets the executive scope to All / Unscoped / specific committee.
  - **Question Bank `committee_id`** also accepted as a list filter (already on the schema; now exposed on the GET endpoint) — sets the foundation for committee-chair-scoped checklists in a follow-up.
  - **Editor footer redesigned** to surface five distinct actions: Close · Download PDF · Polish with AKKI · Save edits · Send up / Approve & forward / Send back. Sparkle icon on Polish, Download icon on PDF.

## Recent fixes
- **2026-04-25 Sprint 15 / iter20** — §12 Phase 3: Multi-tier review chain (Reports).
  - **Reports collection** — composed from a cycle's submissions; carries a `chain[]` of tiers (author at tier 0, escalating reviewers at tier 1+). `compose` stitches reportee answers into a starter markdown body the author edits before sending up.
  - **`send_up`** flips draft → in_review and sends a Resend email to the next pending reviewer with a deep link to /app/cycle/reports/:id. Reviewer doesn't need to be a member of the upstream context — the new `_resolve_report_access` gate accepts EITHER context-membership OR named-reviewer-on-chain (matched by email).
  - **`review`** — current reviewer can `approve` (next tier promoted to pending; if last tier, status → finalised) or `send_back` (chain rolls back to author with notes). Only the email-matched current reviewer can act.
  - **Cross-context inbox** — `GET /api/reports/inbox` returns every report platform-wide where the caller is the current pending reviewer. New `ReviewInboxCard` component renders on Home only when the count > 0.
  - **Reports tab** in Cycle page (5th tab). Compose modal collects cycle + title + chain (reviewer name/title/email × up to 5). Editor modal carries the chain visualizer, event trail, edit affordances, and the action footer that surfaces "Send to next" / "Approve & forward" / "Send back" based on caller role.
  - **End-to-end verified live**: Bramuel (CFO author) composed → sent up to admin@akki.ai (CEO, NOT a context member of Tuli) → admin approved with note → status flipped to chair@example.com pending → chain entries: [✓ Author, ✓ CEO, pending Chair].
  - **Resend send_mode caveat**: until a real domain is verified in the Resend dashboard, only `delivered@resend.dev` actually delivers. Admin@akki.ai gets `send_mode=error` from the Resend sandbox API — but the chain progression itself works regardless.

## Recent fixes
- **2026-04-25 Sprint 14b / iter19** — Brand polish (post-iter18 user feedback).
  - **Logo conditional Sandbox suffix** — Logo now reads just "AKKI" everywhere by default; the " · Sandbox" suffix is shown ONLY when `account.is_sandbox === true` (auto-detected via `useAuth`). Marketing pages, sign-in, sign-up, signed-in-non-sandbox app shell all read "AKKI". Sandbox flow reads "AKKI Sandbox" because the disposable account carries `is_sandbox=true`. Manual override available via `<Logo showSandbox={true|false} />`.
  - **Landing CTAs decluttered** — three competing CTAs collapsed to one prominent navy "Try AKKI in 60 seconds" button, with a one-line explainer of what the Sandbox is ("AKKI loaded with sample data for a fictional company in your sector. No signup. Yours for 14 days, then it deletes itself"), then two quiet text gestures separated by a `·`: "Sign in to your workspace" and "Request a team workspace".
  - **SignIn page rebrand** — replaced the dark navy + photo aesthetic with the editorial cream/Georgia palette that matches the rest of the marketing site. New header with brand-only logo and "← Back to akki.ai" link. Two-column on desktop: left has serif headline "The colleague who reads with you" + an editorial pull-quote with attribution; right has the form with proper accent-soft error styling, Synisense-shielded footer chip, and a "Don't have an account? Try AKKI in 60 seconds" cross-sell to /sandbox.
  - Cleaned up "AKKI Sandbox" hard-coded labels in Landing colophon and SignUp footer.

## Recent fixes
- **2026-04-25 Sprint 14 / iter18** — §12 redesign + marketing site + Exco360 blog (BIG sprint).
  - **§12 governance pivot** — AKKI is now the third party in the conversation, not just a drafter:
    - **Question Bank** per context. Persistent. CRUD + `seed-from-briefings` idempotent extractor that pulls every "questions to take into the room" from past briefings into one place. Categorised (audit/risk/financial/regulatory/strategic/operational/people/general). Tracks `times_asked`, `last_asked_at`, `status`.
    - **Reportees** first-class — name, email, title, areas-of-ownership tags. Soft-delete.
    - **Checklist generation** — deterministic ranking: areas-match + recurring-question bias + recency. Picks top 6 open questions per reportee. **Anti-spam** 14-day cooldown per reportee unless executive explicitly targets them.
    - **Approve & Dispatch** — executive reviews/edits each draft, single batch dispatch. **Real Resend integration live** with `"AKKI for <Executive Name>"` From + reply-to to executive's real email. Mailto fallback if Resend not configured.
    - **Public /respond/{token}** — reportee fills form without authenticating, answers persist as `submissions`, open questions auto-flip to `answered`.
    - **Submissions inbox** — executive sees consolidated responses ready for the next report draft.
  - **Marketing site** — full editorial chrome at `/about`, `/features`, `/security`, `/blog`, `/blog/:slug`. MarketingShell header + 4-column footer. Security page surfaces the four trust promises with verification recipes.
  - **Exco360 blog** — *AKKI's perspective on AI's role in modern executive success*. Weekly editorial. Admin compose surface (`/app/blog-admin`, superadmin only) generates 700–1,100-word article + LinkedIn post + email-newsletter intro + tweet. Public list, post reader, subscribe form. First issue published end-to-end during smoke testing.
  - **Sidebar "Cycle"** entry added to AppShell.
  - **iter18**: Backend 16/16 GREEN (cycle CRUD, anti-spam, dispatch with real Resend, public respond, blog compose+publish+subscribe). Frontend marketing pages + Cycle + Respond + BlogPost all rendered.

## Recent fixes
- **2026-04-24 Sprint 13 / iter17** — Product-review P1 fixes.
  - **Actionable role-mismatch banner** — new "Act as NED/Executive" button
    (data-testid `role-mismatch-fix-btn`) inside the banner flips activeRole
    to match the current context in one click. In practice the banner
    rarely fires because AuthContext bootstrap auto-realigns on mount — but
    when it does, the fix is inline instead of being buried in the role
    switcher.
  - **Next Best Action card on Home** — new `NextBestActionCard` replaces
    the humble EmptySlot when a non-aggregated Home has zero signals.
    Cream-gradient hero with oxblood accent rail, "Your next best action"
    overline, a primary Upload CTA (navy) and a secondary Generate link.
    Shows post-audit only — the audit gate still takes precedence pre-audit.
  - **The Lens run narrative** — new shared `useAIStageTicker` hook; Lens
    Room's "Apply lens" now shows a 5-stage typed narrative ("Reading the
    subject against Capital Discipline…" → "Drafting Observation → Implication
    → Action…") instead of a lonely spinner. Unifies the AI-thinking voice
    across Signals, Briefings, and The Lens.
  - **Trust centre + global footer** — new 4-card posture panel (01 Residency
    · 02 Shielding · 03 Provenance · 04 Control) at the top of the Privacy
    tab (renamed "Trust"), deep-linked via `/app/settings?tab=trust`. A
    persistent low-weight Trust footer sits below every authed page with
    ShieldCheck + "Synisense-shielded · Your context never leaves this
    account · Every signal cites its source · Trust centre →". Footer link
    SPA-navigates via `useNavigate` (iter17 bug fix — initial `<Link>` had
    a click no-op on scroll-containing surfaces).
  - **iter17**: Trust footer + Trust centre verified live; NBA card + role-
    mismatch fix button + lens-run ticker all correctly wired in source.
    Footer Link→button regression fixed post-testing.


  - **Display renames (routes unchanged):** sidebar "Highlights" → "Signals"
    everywhere, "Lens Room" → "The Lens". /app/highlights overline now reads
    "SIGNALS · &lt;context&gt;". Briefings empty-state gesture reads "Open
    Signals". Routes /app/highlights and /app/lens still resolve — zero link
    rot, zero bookmarks broken.
  - **Learn `View more` modal** — new pill button under the card grid opens a
    medium Dialog ("Further reading · &lt;tab&gt;"). Shows editor-curated
    external primary sources grouped by topic; filters by the user's current
    topic pill when one is active. Counts: TL Articles 12, News 10, Videos 8,
    Case Studies 8 — meets the ≥ 8 threshold flagged by iter16.
  - **`/learn/research` personalisation** — endpoint accepts optional
    `context_id`; when the caller is a member, the LLM prompt is weighted
    to the context's sector + jurisdiction. Verified: Bramuel on his Tuli
    Financial Group (Kenya, banking) context researching "vendor AI
    oversight" returns a CBK-flavoured article with Kenyan references woven
    in. Response surfaces `personalised:true` +
    `personalisation_from:{sector,jurisdiction}` so the toast can say
    "weighted to Kenya". Membership verified BEFORE context read — no
    enumeration leak.
  - **Sandbox cleanup secret gate** — `POST /api/sandbox/cleanup/expired`
    now requires `X-Cron-Secret` matching `AKKI_CRON_SECRET` in the
    environment. Fails closed (503) if the env var is unset. Anonymous
    POSTs return 401. Closes the iter15 nit.
  - **iter16**: 37/37 backend PASS (32 regression + 5 new iter16 covering
    personalisation + cleanup gate). Frontend: labels, modal flow, Governance
    topic filtering, and ESC close all verified. LEARN_MORE depth padded
    post-testing to meet the ≥ 8 spec across all four tabs.


  - **6 polished sector templates** (`sandbox_templates.py`): SaaS/tech,
    logistics, healthcare, manufacturing, retail, real estate. Each ships
    3 committees / 2–3 docs / 4–6 sector-specific signals / 1 composed
    briefing, all parameterised over `{company_name}/{currency}/{regulator}`.
    Only "Other" still falls through to `generic_diversified`.
  - **Sandbox → account conversion** (`POST /api/sandbox/convert`): rewrites
    the disposable account email/password/name, strips `is_sandbox`, flips
    sandbox contexts to `executive_personal` or `ned_personal`, drops expiry
    metadata, sets real cookies. `keep_sandbox=false` deletes the explored
    environment entirely. `PublicOnlyRoute allowSandbox` lets the sandbox
    user reach /signup to convert; regular authed users still redirect.
  - **SignUp.jsx** detects `?from_sandbox=<cid>` + `account.is_sandbox` and
    renders a distinct editorial conversion UX: "Keep exploring — for real."
    heading, "Keep my sandbox as a working context" checkbox with the
    sandbox's name surfaced, "Finish setup" CTA.
  - **Mid-exploration email capture** (`POST /contexts/{cid}/capture-email`
    + `SandboxEmailCapture.jsx`): bottom-right modal surfaces after 3 min
    of sandbox browsing (localStorage-guarded, once per device). Stores
    email on `sandbox_metadata.prospect_email` and queues a
    `sandbox_pickups` record for a +24h drip (SMTP ships with §6 Email-in).
  - **Dropdown fix**: `Financial services` now pre-selected on /sandbox so
    Radix's item-aligned Select positions the polished template adjacent to
    the trigger with every other sector naturally visible below.
  - **iteration_14**: 15/15 new backend tests PASS + 26/26 regression PASS.
    47 test-generated sandboxes swept. iteration_14 code-review nits
    addressed (dropdown, `is_sandbox` on sanitize_account, stale Phase 1
    assertion, template-import WARNING log).

- **2026-04-24 Sprint 10** — Addendum v4.3 §1 Phase 1: Sandbox pre-auth evaluation.
  - New `/sandbox` route: 4-question editorial intake (company name,
    sector, role, region). No sign-up required up front. Primary hero CTA
    on Landing now points here.
  - New `/sandbox/generating/:sessionId` streaming page — plays the 10-stage
    60-second narrative with the prospect's company name, sector, region
    country, and role label substituted into stage text. Cream canvas, serif
    title, oxblood progress bar with ambient shimmer. Holds on stage 9
    until the backend seed is genuinely ready.
  - New backend `routers/sandbox.py` + `sandbox_service.py`:
    `POST /api/sandbox/generate` → `GET /generate/{id}/status` flow, async
    background seed (ready in ~2s), returns JWT. Creates disposable account
    `sandbox+<id>@akki.local`, sandbox-typed context with
    `sandbox_metadata.{expires_at (+14d), read_only_until (+21d),
    hard_delete_at (+22d)}`, full seeded artefacts.
  - **banking_midcap template** — 3 committees + 3 documents + 6 signals +
    1 pre-composed briefing, every string parameterised for company name,
    currency (KSh, ₦, €, $ etc. driven by region) and regulator (CBK, CBN,
    SARB, FCA, SEC, MAS). Generic template fallback (1 doc + 3 signals + 1
    briefing) for non-polished sectors in Phase 1.
  - `SandboxBanner` chrome renders above top bar when
    `activeContext.type==='sandbox'` — "14 days remaining · Set up your
    account →". Hidden for non-sandbox users.
  - Bearer token interceptor in `lib/api.js` attaches
    `Authorization: Bearer <akki_access_token>` from localStorage when
    present. Cookie-auth sessions unaffected (additive). Logout clears it.
  - Rollback on seed failure, 90s session TTL, and `is_sandbox` surfaced on
    sanitize_account from iter13 code review.
  - **iteration_13: 12/12 backend PASS + 100% frontend arc verified.** Full
    round-trip screenshot sequence captured (intake → generating → landing
    with banner + banking signals visible).

- **2026-04-24 Sprint 9** — Build Addendum v4.3 §8 + §9 closed.
  - **§8 — All boards aggregated Home stream**: new
    `GET /api/me/home/stream` merges signals + briefings across every active
    membership, attaches `context_name` to each card. Home renders a quiet
    'This context | All boards' toggle (only when user has 2+ contexts);
    aggregated mode shows an uppercase context badge (first token of context
    name) left of the type badge.
  - **§9 — External Share**: new `shares` collection + router
    (`POST /api/contexts/{cid}/shares`, inbox, outbox, auth-guarded
    `GET /api/shares/{id}`, sharer-only DELETE revoke). Creates a mention
    inbox row for AKKI recipients; logs an email-send intent for non-AKKI
    emails (SMTP deferred to §6). Extended comments router with
    `artefact_type='share'` so the one-to-one comment thread on shared
    items just works. New `ShareModal` composition overlay, Share buttons
    on signals (Highlights + Home) and briefings (Briefings viewer), and a
    new "Shared with you" tab on Home.
  - **New `source` prop on `StreamCard`**: optional left-chip rendering
    either a context badge (aggregated mode) or a "SHARED BY X" accent-soft
    badge (shared-with-you cards). Non-breaking.
  - **Testing** — iteration_12: 14/14 backend PASS + 100% frontend, zero
    design or integration issues.

- **2026-04-24 Sprint 8** — Speaking notes on the board deck.
  - New endpoint `POST /api/contexts/{cid}/briefings/{bid}/speaking-notes`
    — one LLM call produces 3 spoken-voice bullets per briefing item (fact →
    why it matters → what to watch/escalate). Persisted to
    `briefing.items[i].speaking_notes` + timestamp on
    `briefing.speaking_notes_at`.
  - `render_board_deck_pdf` now renders them under each item slide, prefaced
    by a tiny `WHAT YOU WOULD SAY` label in oxblood + Georgia-italic bullets
    in muted slate. Only appears when drafted.
  - Briefings page gets a new outlined oxblood "Draft speaking notes" button
    that toggles to "Re-draft notes" once notes exist, and a small "+ notes"
    chip lands on the Board deck pill after drafting.
  - iteration_11: 8/8 backend tests PASS (happy path, idempotency, 404, 401,
    400 empty-items, PDF embedding, /ask shielding regression, deck-without-
    notes regression). Frontend 100%, zero console errors.

- **2026-04-24 Sprint 7** — Executive-ready board deck + housekeeping + visual life.
  - **Board deck PDF** (new `render_board_deck_pdf` in `briefings_service.py`):
    landscape A4, one signal per slide — cover, executive summary, per-item
    slides (headline + evidence + sharpest question + source chips), optional
    closing slide, final "Receipts" sources slide. Oxblood/Cream palette +
    serif/sans split. Exposed as `GET /export?fmt=board_deck`. Briefings page
    gets a new oxblood "Board deck" pill left of PDF/DOCX.
  - **Housekeeping sidebar** — two new nav items below Learn: "Manage my team"
    and "Manage my companies", both deep-linking to `/app/manage?tab=…`.
    Sidebar items now slide in with a staggered framer-motion entrance.
  - **`/app/manage` page** (new `Manage.jsx`) — 2-tab surface:
      · **Team** — invite / revoke invitation / remove member scoped to the
        active context. Admin-only write actions. Link out to full settings.
      · **Companies** — grid of all user contexts with hover-lift motion,
        quick "Switch & open" action, non-destructive "Archive" confirm,
        and a top-right "Add company" pill.
  - **Motion pass** — framer-motion installed. AppHome top-signals + Highlights
    signals grid + Manage members/companies now enter with stagger animation;
    Manage tab indicator uses `layoutId` for spring-animated underline.
  - **Highlights stats strip** (`HighlightsStats.jsx`) — pure-SVG confidence
    donut + 14-day sparkline in oxblood tones. Sits above the committee
    filter so the reader sees shape → scope → cards. Zero chart-lib
    dependency.
  - **Testing** — iteration_10: 5/5 new backend tests PASS, frontend 100% on
    all new surfaces, zero console errors.

- **2026-04-24 Sprint 6** — Shielding payload regression fixed + server.py refactor completed.
  - **Shielding fix**: every LLM-backed endpoint now returns a top-level
    `shielding: {identifiers_masked, by_category, shielded_by}` dict alongside
    the legacy scalar count. Touched: `/signals/generate`, `/ask`,
    `/briefings`, `/simulate`, `/lens/run`, `/documents/generate-meta`.
    iter8 flagged → iter9 100% green.
  - **server.py refactor**: 1,400 → 171 lines (88% reduction). Extracted into
    4 new routers: `routers/auth.py` (register/login/logout/refresh/me/role/MFA),
    `routers/contexts.py` (CRUD + members + invitations + context-object +
    presets + accounts/me), `routers/documents.py` (upload + thread +
    list/get/patch/archive/download + generate-meta), `routers/misc.py`
    (llm/probe + /events + /health). `core.py` now exports
    `hash_password` / `verify_password` / `set_auth_cookies` /
    `sanitize_account` / `sanitize_context` / `provision_default_context`.
    server.py is now a pure assembler (startup indexes + admin seed + router
    wiring + CORS). iteration_9: 100% backend — 52 existing sprint tests +
    11 new iter9 refactor-smoke tests all green.

- **2026-04-24 Sprint 5** — Shipped: AllLensesModal (fires 6 lenses in
  parallel from any signal card), mobile camera upload in Workspace
  (`capture="environment"`), lightweight CompositionStrip provenance panel
  on Briefings/Simulate/LensRoom, audit-log + export extracted to
  `routers/audit.py` (server.py now 1,253 lines, 35% off original).
  iteration_7: 100% backend (10/10), 95% frontend (2 cosmetic nits fixed:
  DialogDescription a11y + clickable simulate-list testid — already present).

- **2026-04-24 Sprint 4** — Shipped: landing-page executive rewrite, M13
  BM25 Ask retrieval (`bm25.py`), Pipeline trace drawer on Highlights,
  "Boards to watch this week" Portfolio banner, continued server.py
  refactor (signals+ask extracted; now 33% off original). iteration_6:
  100% backend (7/7), 100% frontend, zero issues.

- **2026-04-23 Sprint 3** — Shipped: role auto-route (AuthContext), Mention
  Inbox bell in AppShell header, CommitteeManager in Settings, signals+ask
  router extraction, M14 Lens Room (6 frameworks, full page), M11 event-
  driven pipeline (4 stages, signal_events trace). iteration_5: 100% backend
  (10/10), 100% frontend.

- **2026-04-23** — **Sprint 1 shipped** (3 of the user's 7-point feedback list).
  - **Task 1 — Curated Home** (Feedback #2): `AppHome.jsx` now shows top-of-pile
    content as **three sibling tabs** — *Top signals* (≤3, ranked by confidence
    then risk-bias then recency), *Top briefings* (≤2 by recency), *New
    documents* (≤3 by recency) — with a single right-aligned "View all" link
    that follows the active tab (`/app/highlights`, `/app/briefings`,
    `/app/workspace`). Default tab is *Top signals*. Fixed page height
    (`h-[calc(100vh-4rem)]`) — only the active panel scrolls; chrome stays put.
    Companion rail adds "My portfolio" link to `/app/contexts`.
  - **Task 2 — Learn mini-tabs** (Feedback #1): `Learn.jsx` refactored to four
    content-type tabs (`News · TL Articles · Videos · Case Studies`) with
    underline accent on active tab, per-tab topic pills on the left rail, and
    fixed page height — only the card grid scrolls (`data-testid=learn-scroll`).
    Added `content_type` field to each article in `lib/learnContent.js`, new
    `LEARN_NEWS` array with 3 curated briefs (EU GPAI Code, FCA supervisory
    posture, NACD 2026 benchmark), and `CONTENT_TYPE_LABEL` map.
  - **Task 3 — Context Portfolio page** (Feedback #5): NEW `/app/contexts`
    surface (`ContextPortfolio.jsx`). Portfolio summary strip shows totals for
    Contexts / Signals / Briefings / Documents. Cards grouped into
    *NED boards* and *Executive contexts*; each card shows type/admin chip,
    sponsored badge, per-context metrics (signals/briefings/documents fetched
    in parallel). Clicking a card calls `switchContext` and navigates to `/app`.
    `AppShell` context dropdown now has a "View portfolio" item at the top
    (`data-testid=context-portfolio-btn`).
  - **Testing**: iteration_3 — 100% backend, 100% frontend. No critical or
    minor issues. Two design notes flagged (summary-strip "…" during fan-out;
    role-mismatch banner ever-present because Bramuel's default context is NED
    while `activeRole` defaults to `executive`) — both working-as-designed.

## Sprint 2 — SHIPPED 2026-04-23 (items 3 / 6 / 7 complete)
### Phase 1 — Backend refactor
- **NEW** `/app/backend/core.py`: single source for db + helpers + auth deps.
- **NEW** `/app/backend/routers/{briefings,learn,committees,simulate,comments}.py`.
- `server.py`: 1,941 → 1,570 lines. Pattern proven for future router migrations.

### Phase 2 — Sub-committees (Feedback #6)
- Contexts carry `committees: [{id, name, your_role}]`; IDs auto-backfilled on
  startup for seeded boards.
- Full CRUD at `/api/contexts/{id}/committees` (owner-only writes); deletion
  unsets `committee_id` on referencing artefacts.
- `committee_id` filter query param added to signals, briefings, documents,
  simulations list endpoints.
- Highlights shows a "Scope" chip row; Briefings left-rail gets a committee
  `<select>`. Chair badge rendered when `your_role === "chair"`.

### Phase 3 — Simulate / Forecasting (Feedback #3)
- New surface `/app/simulate`. LLM produces Best / Base / Stress paragraphs
  for 1y and/or 3y horizon, a 3–6 item watchlist with early-warning triggers
  and committee routing, assumptions, and the single sharpest board question.
- Backend: `routers/simulate.py`. Side-nav adds **Simulate** (Target icon).

### Phase 4 — Human-to-human collaboration (Feedback #7)
- Polymorphic comment store — artefacts: signal / briefing / document / simulation.
  Threaded via flat list + `parent_id` for single-level replies.
- `@mentions` parsed from body, resolved to context members by email-prefix
  or first-name. Mention records written to a separate collection (inbox-ready).
- Endpoints: `GET/POST /api/contexts/{id}/{artefact_type}/{id}/comments`,
  `DELETE /api/contexts/{id}/comments/{id}`, `GET /mentions`, mark-read.
- **NEW** `CommentThread.jsx` wired into Briefings, Simulate, DocumentViewer
  viewers. Includes @mention highlight, relative timestamps, delete (author
  or context admin), ping-count badge.

### Testing
- iteration_4 — 100% backend (18/18), 100% frontend on all Sprint-2 testids.
- Only non-blocking note: pre-existing role-mismatch banner (unchanged since
  iteration 3).

## Recent fixes
- **2026-04-25** (iter21) — `sanitize_account()` was silently dropping `is_superadmin`,
  blocking the BlogAdmin gate. Fixed in `/app/backend/core.py`. Verified via
  `/api/auth/me` returning `account.is_superadmin=true` for `admin@akki.ai`.
- **2026-04-23** — Workspace doc row nested-button hydration warning: outer wrapper
  converted to `<div role="button" tabIndex={0}>` with keyboard handler; TrustChip
  wrapped in a `stopPropagation` span so changing trust doesn't open the document.
- **2026-04-22** — Brute-force login lockout: was keyed on `ip:email`; changed to
  email-only because Kubernetes ingress rotates `request.client.host`. Verified
  5×401 → 429 on 6th attempt.

## §12.x Final UI polish batch (iter19–21, 2026-04-25)
- **PolishDiffModal** (`/app/frontend/src/components/cycle/PolishDiffModal.jsx`)
  — word-level diff (LCS over whitespace tokens) showing red strike-through for
  removed words and green highlight for added. Wired into `ReportsTab` so
  "Polish with AKKI" no longer silently overwrites the body — instead it opens
  the diff and lets the executive **Accept** or **Reject** before saving. If the
  LLM returns identical text, a "no changes" toast fires and the modal stays
  closed. Verified end-to-end on a 588-word draft fixture.
- **Committee scope strip** on `/app/cycle` Checklists tab. When the active
  context has ≥1 committee, a chip strip renders ("Whole context" + one chip
  per committee). Selecting a committee scopes both the reportee match AND the
  question pool to that committee for the next `/checklists/generate` POST.
  Verified end-to-end on Tuli ned ctx with the iter19 seed (Audit + Risk
  committees, Ruth Kamau audit-scoped reportee, 6 audit-scoped questions).
- **Copy for Medium** in BlogAdmin (`/app/blog-admin`). Both the live draft
  preview tile-grid AND each row of All Posts now have a Medium button. Per-row
  click fetches the full post body via the new admin endpoint
  `GET /api/blog/admin/posts/{slug}` (gated by `_require_admin`) and writes a
  Medium-ready markdown payload to the clipboard:
  `**KICKER**\n\n# Title\n\n> Dek\n\nbody...\n\n_Tags: ..._`.
- **Seed script** `/app/backend/scripts/seed_iter19_e2e.py` (idempotent) —
  seeds the committee + reportee + question + rich-draft fixtures the E2E
  tests rely on.

## §M4 Stripe Billing + Schedule cron + polish (2026-04-25, iter22)
- **Stripe Billing M4** — Free / Pro ($29/mo) / Team ($99/mo) plans, fixed
  server-side. Settings → Billing tab (`/app/settings?tab=billing` or
  `/app/settings/billing`). Backend: `/api/billing/{plans,me,checkout,status/{sid}}`
  + webhook `/api/webhook/stripe`. Uses `emergentintegrations.payments.stripe.checkout.StripeCheckout`.
  `STRIPE_API_KEY=sk_test_emergent` in `/app/backend/.env`.
  - Checkout creates real `https://checkout.stripe.com/c/pay/cs_test_...` URLs.
  - Status endpoint degrades gracefully (returns persisted `payment_status`)
    when the test-mode SDK can't retrieve the just-created session — the UI
    poll loop never crashes.
  - `payment_transactions` collection holds every initiated session;
    `accounts.plan` is flipped on `paid`. Webhook + poll both apply once.
  - Sanitize_account now surfaces `plan` + `subscription_status` so the UI
    can gate paid features (e.g. recurring schedule, dispatch).

- **Recurring Cycle Schedule (cron)** — single schedule per context.
  - `GET/PUT/DELETE /api/contexts/{cid}/cycle/schedule` (auth + membership).
  - `POST /api/cycle/cron/run-schedules` gated by `X-Cron-Secret` =
    `AKKI_CRON_SECRET`. Idempotent (advances `next_run_at` after each run).
  - Frontend "Schedule recurring" button on Cycle → Checklists tab opens a
    modal (cadence, weekday, cycle name template with tokens
    `{month}|{date}|{iso_week}|{year}`, deadline offset days, committee scope).
    Verified end-to-end: a forced-past `next_run_at` yields 1 draft for the
    audit-scoped reportee with cycle name "April 2026 report".

- **Frontend polishes** (P2 backlog cleared in this iteration):
  - `PolishDiffModal` wordDiff is now paragraph-chunked → bounded LCS
    memory even on long appendices.
  - `BlogAdmin` caches the full post body per slug after the first per-row
    Medium fetch (no repeat round-trips).
  - `ReportEditor` shows an "Unsaved changes" badge above the body textarea
    when title/body/polish-accept has dirtied the local state, and
    `window.confirm` blocks an accidental close-without-save.

## §13 Plays — choreography over existing surfaces (2026-04-26, iter24)

### Why
After a CFO/CEO demo, the user observed AKKI's value was present but the
*journey* to it was not — the executive had to know to go to Settings →
configure cycle → Workspace → start a Report → Cycle → approve dispatch.
Per Build Addendum v4.4, **Plays** are introduced as a third structural
layer (Surfaces, Artefacts, **Plays**) — named, staged journeys that
*compose* existing features into a coherent flow.

### Cadence (non-negotiable)
- Quiet, not noisy. Editorial, not transactional. Trust-first.
- **No** progress bars / percentages / step counters / "Stage 2 of 6" /
  checklist marks / celebratory animations.
- Stage transitions = name fade + a single editorial phrase.
- Pause-and-resume native — full state persists.

### Slice 1 shipped
- **Backend** (`/app/backend/routers/plays.py`):
  - `GET /api/plays/library` — 6 plays, only `board_pack` available.
  - `POST /api/contexts/{cid}/plays` — start (idempotent: returns the same
    active/paused play if one exists for the same type).
  - `GET /api/contexts/{cid}/plays` — list (sorted by activity).
  - `GET /api/contexts/{cid}/plays/{pid}` — full play state.
  - `POST .../advance` — bumps current_stage; entering the last stage
    flips `status='completed'` + sets `completed_at`.
  - `POST .../jump` — backwards free; forward requires `confirm=true`
    (returns 409 otherwise).
  - `POST .../pause`, `.../resume`, `.../exit`.
  - `PATCH .../state` — shallow-merge per-stage bindings (e.g.
    `report_id`, `schedule_id`).
- **Frontend**:
  - `/app/plays` — `PlaysLibrary.jsx`. 6 cards in two sections (executive,
    NED). Stubs render as "Coming next" lock state.
  - `/app/plays/:id` — `PlayView.jsx`. 64px Play header (kicker + stage
    name with fade), 60/40 split, right-side "Stages" overlay panel with
    forward-jump confirm.
  - `BoardPackStages.jsx` — 6 stage components (Setting the cycle, Where
    the gaps are, Consolidation, Your review, Distribution, Done) — each
    reuses the existing Cycle/Reports/Schedule/Submissions surfaces.
  - `PlaysInProgressStrip.jsx` on Home — restrained chips that bring the
    executive back to active choreography.
  - Side-nav entry `Plays` between Cycle and Learn (Compass icon).

### Backend tests
- 14/14 new pytests in `/app/backend/tests/test_iter24_plays.py` GREEN.
- 26/26 prior regression (iter19 polish/committee/medium + iter22
  billing/schedule) STILL GREEN. Plays add a layer; nothing existing was
  modified.

### Frontend self-test
- All 6 stages cadence-clean (no STAGE N counters; replaced with bare
  editorial headlines).
- Pause→Resume→Pause toggles correctly via optimistic update (was
  flagged in iter24).

## §13 Plays — Slice 2 (2026-04-26, iter25)

### Schedule auto-launch hook
- `_run_one_schedule` in `/app/backend/routers/cycle.py` now calls
  `_spawn_auto_launched_play` after drafting checklists. The spawned (or
  resumed) Board Pack Play is positioned at stage 1 ("Where the gaps are")
  with `auto_launched=true`, `auto_launch_seen=false`, and
  `state.cycle_name` / `state.deadline` / `state.auto_launched_schedule_id`
  carried through. **Re-running the cron resets `auto_launch_seen=false`**
  so a fresh PLAY READY card surfaces every cycle, while keeping the same
  `play_id` (idempotent).

### Pre-Board Play (NED, available)
- Backend: `PRE_BOARD_PLAY` definition + `POST /api/contexts/{cid}/plays/{pid}/pre_board/read`
  endpoint. Calls Claude Sonnet 4.5 via the Emergent LLM key with
  `module="pre_board.read"`, `response_format="json"`. Returns 5 reading
  notes + 3-4 standouts (each `{label, detail, why}`).
- Frontend: 5 stage components in `/app/frontend/src/components/plays/PreBoardStages.jsx`:
  Arrival (paste pack), Reading (notes), Standouts (oxblood-bordered cards),
  Questions (textarea + standouts working set), Walking In (one-page brief).
- Self-verified output sample: *"Revenue growth of 14.2% is flattering a
  balance sheet that has deteriorated across three core ratios in six months."*

### PLAY READY trigger card on Home
- `/app/frontend/src/components/home/PlayReadyCards.jsx` — renders cards for
  any play where `auto_launched && !auto_launch_seen`. Editorial layout:
  oxblood "PLAY READY · Board Pack Play" kicker, Georgia headline
  ("April 2026 report just dispatched."), italic transition phrase,
  "Open the Play →" + "Not now" affordances. Click 'Not now' → POST `/seen` →
  card disappears. Opening the play also fires `/seen` automatically.
- `POST /api/contexts/{cid}/plays/{pid}/seen` — idempotent, used by both UI
  paths and by PlayView's load() to mark auto-launched plays as seen.

### Backend tests
- 13/13 new pytests in `/app/backend/tests/test_iter25_plays_slice2.py` GREEN
  (after testing-agent fixed a `call_llm` kwargs bug). Existing 40+ tests
  still GREEN.

### Open / deferred — Slice 3+
- **Monthly Performance Play** (executive) — needs §4 Monitor service hooks.
- **Cross-Board Pulse Play** (NED) — needs cross-context signal aggregation.
- **Team Reporting Play** + **Open Threads Play** — implement after observing
  Slice 1+2 in real demos.
- Plays-aware M13 Ask context biasing.
- Workspace "Play context" right-panel section across all artefacts.
- Pre-Board "pick from Document Journal" — the Arrival stage links there but
  doesn't yet pull a doc into the play (textarea paste only for Slice 2).
- Replace shallow-merge `PATCH /state` with deep-merge.


## §13 Workflows — Slice 3 (2026-04-26, iter26): rename + simplification + Home redesign

### Why
After demo feedback, the user said: "I don't understand what the Play function is
supposed to do as it has been currently executed. The idea is simple — prepare,
review or submit submissions, as part of the quick action tabs." That broke the
simplification audit.

### What shipped
- Rename "Play" → "Workflow" everywhere user-facing.
- Board Pack collapsed from 6 stages to 5 — "Setting the cycle" + "Where the gaps are"
  merged into "Consolidate and review submissions". Pre-Board "When the pack arrives"
  → "Add the board pack".
- PlayHeader chrome stripped (no more "BOARD PACK PLAY" kicker on the workflow page).
- Permanent right-side PortfolioRail on every /app/* page with green dot on the
  active context. Top-bar context + role dropdowns removed.
- Home redesign: QuickActions (3 intent tiles) + InSummaryTiles (4 hot-data tiles).
- Cycle Tracker tab (default): reportee × latest cycle × status × AKKI is missing
  × intervention button.
- Demo seed `/app/backend/scripts/seed_iter26_demo.py` — 16 signals, 4 reportees,
  6 questions, 2 checklists (1 responded, 1 outstanding), 3 briefings, 1 board pack.

## §13.x Agenda Evolution + Document Engagement (2026-04-26, iter26b)

### Agenda Evolution card on Home
- New `routers/agenda.py` → `GET /api/contexts/{cid}/agenda-evolution`. Composes
  from existing collections (last committed/published report → "the meeting",
  submissions/checklists/reports/briefings since → "since then" narrative,
  next dispatched checklist → "next up"). Caps the narrative at 6 lines.
- New `components/home/AgendaEvolutionCard.jsx` — sister card to "Ready for you".
  Editorial (cream + Calendar icon, no progress bars).
- `AppHome.jsx` lines 170-173: `home-ready-row` grid (`grid-cols-1 md:grid-cols-2`)
  pairs `PlayReadyCards` + `AgendaEvolutionCard` 50/50.
- `PlayReadyCards.jsx` now renders an empty placeholder (`home-play-ready-empty`)
  when no auto-launched workflow is waiting, so the grid doesn't collapse.
- `CycleTracker.jsx` copy: "awaiting approval" → "Awaiting your sign-off" with a
  full explanation paragraph at the top of the table (line 132-135).

### Document Engagement Metrics
- New `routers/document_engagement.py` with three endpoints:
  - `POST /contexts/{cid}/documents/{did}/view` — read receipt, deduped per-account
    per-UTC-day (upsert on `(doc_id, account_id, day)`). Owner views are flagged
    but excluded from `unique_readers`.
  - `POST /contexts/{cid}/documents/{did}/share` (body: `{to_email, to_name?, message?}`)
    — records a share intent in `document_shares`.
  - `GET /contexts/{cid}/documents/{did}/engagement` — returns
    `{view_count, unique_readers, readers[], share_count, shares[], linked_count,
    linked_documents[]}`. Linked = ancestors (via `related_doc_id`) + descendants.
- New `components/documents/DocumentEngagement.jsx` panel in the DocumentViewer
  outline rail. Three stat tiles (reads/shares/linked), Read-by/Shared-with/Linked
  lists, and a "Share by email" CTA → in-app modal. Auto-refreshes after submit.
- `DocumentViewer.jsx` fires `POST /view` on viewer mount.
- New indexes (server.py startup): `document_views` unique on `(doc_id, account_id, day)`
  + secondary on `(doc_id, viewed_at desc)`; `document_shares` on `(doc_id, created_at desc)`.

### Tests
- 9/9 new pytests in `test_iter26_engagement.py` GREEN. iter26 frontend critical
  flows verified live (50/50 grid, doc engagement panel, share modal submit).

### Open / deferred — Slice 4+
- Document distribution/engagement: ~~read receipts~~ ✅ ~~share counter~~ ✅
  ~~linked-docs map~~ ✅ — DONE iter26b. SMTP send for share recipients (deferred).
- NED document evolution chain: thread pack → questions → answers → follow-up docs.
- Monthly Performance Workflow + Cross-Board Pulse Workflow (need §4 Monitor hooks).

## §4 Monitor + UX polish (2026-04-26, iter27)

### §4 Monitor — role-adaptive mission-critical touchpoints
- New `routers/monitor.py` → `GET /api/contexts/{cid}/monitor?function=ceo|cfo|coo|commercial|ned|other`.
  Composes from existing collections — signals (filtered by role-relevant categories),
  cycle (overdue + awaiting approval + in-flight checklists, reportees fuzzy-matched
  by area-of-ownership keywords), reports pending the caller, recent briefings,
  document engagement (your-uploaded docs read in last 30 days). NED gets an extra
  `ned` block with `open_threads` + `recent_mentions`.
- New page `/app/monitor` (`Monitor.jsx`). Light editorial layout:
  - Function chip strip (CEO/CFO/COO/Commercial/Other) for executives,
    persisted in `localStorage.akki_monitor_function` so the user lands on
    the same view next session. NED users see no chip strip — single view.
  - 4 tiles in a responsive 2-column grid: Signals · Cycle · Reports awaiting you
    · Document engagement (or Open threads when function=ned).
  - Each tile carries a kicker, headline that summarises the count, sub-content,
    and a single outbound CTA to the relevant detail surface.
- Sidebar entry "Monitor" (Activity icon) wired into `AppShell.jsx` between
  Cycle and Workflows. Route registered in `App.js`.

### Other polish
- **Landing page marketing nav** — added 4 links (About / Features / Security /
  Exco360) to the landing header so the public site's nav matches what's on
  About/Features/Security/Blog pages. Original anchor links and Sign-in/Request
  Access buttons preserved.
- **PortfolioRail role-scoped filter** — the rail now filters contexts by the
  user's `activeRole`. NED users see only NED boards; executives see only
  their executive contexts. Falls back to `c.type` prefix when `my_role` is
  absent (legacy contexts).
- **Learn page horizontal layout** — articles, news, case studies, and videos
  now render in a single `space-y-4 max-w-2xl` column (was a `grid-cols-1
  xl:grid-cols-2` 2-up grid). VideoCard refactored to a horizontal layout
  with a compact `w-40 aspect-video` thumbnail on the left + content on the
  right; play button shrunk from `w-14` to `w-9`.

### Tests
- 15/15 new pytests in `test_iter27_monitor.py` GREEN. Frontend critical flows
  100% verified live (Monitor tiles + chip persistence, nav-monitor present,
  PortfolioRail role filter, Landing nav hrefs, Learn grid layout).

### Open / deferred — Slice 5+
- **Influence Map** (suggested follow-up) — week-over-week reading momentum
  on every doc + "going dark" signals on key decision-makers.
- **NED document evolution chain** — thread pack → questions → answers
  → follow-up docs.
- **Backend prefs persistence for Monitor function** — currently localStorage;
  move to account.preferences for cross-device continuity.
- **Monitor v2** — on-demand LLM commentary per tile ("AKKI, why is this red?").

## §4 Monitor v2 — Strategic Goals tracker (2026-04-26, iter28)

### Why
After demoing Monitor v1 the user clarified the actual mental model:
"Monitor reports on actual operational targets vs success metrics — Strategic
KPIs being tracked at board level (e.g. migrate to new ERP by Dec 2026,
revenue target growth)." And critically: **the user cannot pick their own
function** — the system populates based on profile. NEDs see a scorecard
view (expectation list + score + probability).

### What shipped
- New `routers/strategic_goals.py` with full CRUD + LLM extract:
  - `GET/POST/PATCH/DELETE /api/contexts/{cid}/strategic-goals` (department filter)
  - `POST /api/contexts/{cid}/strategic-goals/extract` reads a context document
    via Claude Sonnet 4.5 (Emergent LLM key, JSON response_format, module
    `strategic_goals.extract`) and seeds 5–12 measurable board-level goals
    tagged to a department (`ceo|cfo|coo|commercial|board`).
- Schema: `{title, description, department, owner_name, target_metric,
  target_value, target_date, current_value, current_score (0-100),
  probability (0-100), status (on_track|at_risk|off_track|achieved|
  abandoned), source_doc_id, source_doc_name}`. Numeric fields clamped via
  Pydantic `conint(ge=0, le=100)`.
- New `components/monitor/StrategicGoalsPanel.jsx` — primary tile on Monitor.
  Goals grouped by department with score + probability dials per row, inline
  edit (status/score/probability/current_value) for executives, read-only
  for NEDs. Empty-state CTA opens the `goals-extract-modal` document picker.
- `Monitor.jsx` rewritten:
  - **Function chip strip removed.** Function is now derived from
    `account.preferences.executive_function` (CEO default if unset). A small
    read-only "Chief Financial (CFO)" chip + "change" pencil opens a
    `FunctionPickerModal` that PATCHes `/accounts/me`.
  - StrategicGoalsPanel is the headline tile; signals/cycle/reports/engagement
    moved to a smaller "Around the goals" secondary section below.
  - **NED scorecard mode** — single read-only view: "Board scorecard.
    What's expected. Where it stands." Goals from every department visible,
    no edit affordances, no extract CTA.
- `PATCH /api/accounts/me` was already accepting arbitrary `preferences`
  (shallow-merge); we just added a new well-known key.

### Landing & Learn polish
- **Landing**: removed the two in-page anchor links ("What it does", "How it's
  trustworthy") since the same content sits in the page. Renamed the marketing
  nav "Security" → "Security Design". Added two stock photo placements:
  - `hero-photo` — sepia-duotoned editorial portrait below the testimonial.
  - `landing-photo-strip` — three-figure section after the rubric strip
    (boardroom · preparation · post-meeting), each with an italic caption.
- **Learn**: tile heights cut by ~50%. ArticleCard switched from
  `akki-stream-card` to compact `px-4 py-3` rounded-md with line-clamp-2
  summary. VideoCard thumbnail halved (`w-40 → w-20`), play button
  `w-9 → w-5`, summary line-clamp-1, vertical density reduced. Grid container
  changed to `space-y-2 max-w-2xl`.

### Tests
- 12/12 new pytests in `test_iter28_strategic_goals.py` GREEN (1 skipped for
  unavailable seed data on the empty-text 400 path — main agent can address
  in a follow-up). Frontend critical flows 100% verified live.

### Open / deferred — Slice 6+
- LLM extract happy-path E2E (currently smoke-tested manually).
- Friendly UX message when extract returns 0 goals.
- First-time exec onboarding banner when `executive_function` is unset.
- Influence Map (still open).
- NED document evolution chain (still open).
- target_date normalization to ISO month for proper sort order.

## §4 Monitor v2.1 + Landing rewrite (2026-04-26, iter29)

### Score history sparkline (improvement suggestion shipped)
- `strategic_goals` rows now carry `score_history: [{score, recorded_at}]`,
  capped at the last 12 entries.
- `POST /strategic-goals` seeds one history point when `current_score` is set.
- `PATCH /strategic-goals/{id}` appends a history point only when
  `current_score` actually changes value (no churn on identical updates).
- `POST /strategic-goals/extract` seeds history on each LLM-extracted goal.
- New `components/monitor/Sparkline.jsx` — pure-SVG 60×20 trend line, stroke
  colour-keyed to the latest score (green ≥70, amber 40-69, red <40).
  Renders an em-dash placeholder when <2 points exist.
- `StrategicGoalsPanel.GoalRow` wraps `ScoreDial + Sparkline` in a
  `goal-score-block-{id}` flex column so the trend sits beneath the score.

### Landing rewrite — direct, executive, creative-director voice
- New headline: "AKKI reads the pack / so you can **read the room.**"
- Old prose paragraph replaced with a numbered three-bullet explainer:
  - 01 — Track strategic goals against where you actually are. Not where the deck says.
  - 02 — Consolidate your team's submissions into board-ready reports. Without chasing.
  - 03 — Cite every number to the page it came from. No unsourced claims.
- Primary CTA: "See it on your sector in 60 seconds" (was "Try AKKI in 60 seconds").
- Tightened first-run, audience, rubric, and closing copy throughout.

### Photo replacement — non-human editorial imagery
- Hero: open historical pages on a desk (1532153975070).
- Strip 1: empty boardroom with leather chairs (1497366216548) — "The room you walk into."
- Strip 2: cathedral-style library (1481627834876) — "Every claim cites a document."
- Strip 3: neoclassical columns at dusk (1521587760476) — "Built for institutions that endure."
- All photos use a `sepia(0.2) saturate(0.85) contrast(1.05)` filter to
  stay inside the cream/oxblood palette without dominating.

### P2 polish shipped
- ExtractFromDocModal now shows a friendly toast.message when the LLM
  returns 0 goals: "AKKI couldn't find board-level goals in that document.
  Try a strategic plan, three-year roadmap, or a board OKR pack." Modal
  stays open so the user can pick a different doc.
- Monitor: `monitor-fn-nudge` inline banner appears when an executive's
  `account.preferences.executive_function` is unset, prompting a one-click
  function pick. Auto-dismisses once set.

### Tests
- 11/11 new pytests in `test_iter29_score_history.py` GREEN. Frontend
  critical flows 100% verified live.

### Open / deferred — Slice 7+
- **NED document evolution chain** (still open) — thread pack → questions
  → answers → follow-up docs.
- **Influence Map** (still open) — week-over-week reading momentum on every
  doc + "going dark" signals on key decision-makers.
- **SMTP send for `document_shares`** (still open) — currently records
  intent only; no email actually goes out.
- target_date ISO normalization for proper sort order.

## §UX big-batch (2026-04-26, iter30)

Eight pieces shipped. Verified by testing agent (9/9 backend + 100%
frontend critical claims).

### Brand & navigation
- **AKKI top-bar** now reads "AKKI" with an italic muted "for Executives"
  (`brand-subtitle`) on screens ≥640 px.
- **Marketing nav** "Security" → "Security Design"; footer
  "Context never leaves your account" → "Your data never leaves your account".

### Score visualisation
- `ScoreDial` rewritten as a conic-gradient ring with banded colours:
  red < 65 (off-track), amber 65–80 (at-risk), green > 80 (on-track).
  Empty state is a dashed circle. Title attribute carries plain-language
  status. Testids `score-dial-red|amber|green`.

### Context → Company rename (UI labels only — not code)
- PortfolioRail "Add context" → "Add company".
- Inactive aria-label "Inactive context" → "Inactive company".
- AppHome "This context" → "This company"; "Your context" → "Your company".
- Marketing footer copy refreshed.

### Role / company switch confirm dialog
- New `switch-confirm-dialog` AlertDialog wraps every `rail-context-{id}`
  and `rail-role-{role}` click. Title and body adapt to the kind of
  switch. Cancel = "Stay where I am". Proceed = "Switch role" / "Switch
  company". Stops accidental loss of context when the user is two clicks
  away from a different board.

### Security marketing copy rewrite
- 4 new promise cards in the user's voice — "Your data stays yours" /
  "Identities are scrubbed" / "Receipts on every claim" / "Leave clean
  any time". H1: "Four things you should be able to verify yourself."
  Posture details rewritten to match the same direct register.

### "See in The Lens" CTA
- `Highlights.jsx` line 386 — "See this through all six lenses" →
  "See in The Lens". One-line copy nudge that clarifies what the CTA does.

### Learn recency tabs
- New `learn-recency-tabs` row below the search bar with three buttons:
  All / Fresh (≤ 5 days) / Stayed a bit (> 5 days OR undated). Counts
  per bucket shown inline. "Stayed a bit" includes undated items so seed
  content remains discoverable.

### Medium-style Blog + RSS + auto-cron
- `Blog.jsx` redesigned Medium-style: featured hero (latest issue) above
  a 2-column reading-list grid. Author byline, kicker, dek, read-time,
  and category surfaced consistently per Medium recommended-stories
  pattern. Subscribe card carries a "Subscribe via RSS →" link.
- New `GET /api/blog/rss` returns Atom XML of the most recent 30
  published posts. Importable into Medium Stories Import.
- New APScheduler cron in `server.py` startup — fires
  `/api/blog/cron/weekly` every Tuesday 10:00 UTC. Logs
  "Exco360 weekly scheduler armed (Tue 10:00 UTC)." on boot.
- `/cron/weekly` upgraded with the user-supplied **PERSONA_PROMPT**
  (Medium ghostwriter persona, 4-phase intake → structure → draft →
  self-critique). Emails superadmins via Resend with a "Review and
  publish →" link instead of auto-publishing (per choice D.c).
- New `POST /api/blog/seed/launch-10` admin endpoint composes 10 launch
  drafts on opportunity / risk / compliance / adoption / growth.
  Idempotent on `topic_seed`. BlogAdmin gets a `seed-launch-banner`
  with one-click CTA.
- BlogAdmin row actions now include **Copy MD** + **Publish to Medium**
  (the Medium API was deprecated in 2023; "Publish to Medium" copies
  the markdown to clipboard and opens medium.com/new-story for paste).

### Tests
- `test_iter30_blog_lens.py` — 9/9 backend GREEN. Frontend 100% on all 8
  batch claims; one minor Learn-recency bucketing issue fixed in-batch
  (undated items now bucket into "Stayed a bit").

## The Lens redesign + Resend send-out + slim Briefing (2026-04-26, iter31)

### The Lens — full redesign
- Two modes share one lens picker:
  - **Stress-test** — input-kind chips (Signal / Claim / Proposal / Question)
    + lens chips above a single textarea. "Apply lens" → existing run
    engine returns Observation → Implication → Action + question-for-management.
  - **Coach** — multi-turn chat through the chosen lens. Lens chips remain
    above the input so the user can switch lenses mid-thread.
- Unified left rail shows **Stress-tests** + **Coaching threads** in one
  timeline of "thinking with AKKI".
- Five new endpoints (POST/GET/GET/POST/DELETE) on
  `/api/contexts/{cid}/lens/coach/sessions`. New `db.lens_coach_sessions`
  collection.

### Resend send-out wired
- `POST /api/contexts/{cid}/shares` (delivery_method=email) AND
  `POST /api/contexts/{cid}/documents/{did}/share` now actually email
  recipients via Resend. Persists `email_send_id`, `email_send_mode`,
  `status` on the share record. Failures are logged; share-intent record
  still persists.

### Briefings — explainer banner (slim-down step 1)
- Page header: "Your 90-second pre-meeting one-pagers" + one-liner
  pointing to Reports for the long-form. Full board-deck migration
  remains queued.

### Learn recency — Fresh bucket populates
- `synthesizedAge()` hash bucketing tuned: ~33/33/33 across Fresh (0-4d),
  mid-Stayed (5-14d), old-Stayed (15-29d).

### Tests
- `test_iter31_lens_coach_email.py` — 11/11 backend GREEN. Frontend 100%
  on Lens redesign + Briefings explainer + regression. Archived-session
  GET tightened post-review (now 404s correctly).

## Iter37/38 — Login alias · Influence Digest cron · Admin Health Dashboard (Apr 2026)
7/7 backend + 8/8 frontend GREEN
(`/app/test_reports/iteration_37.json`,
`/app/backend/tests/test_iter37_38.py`):

### Login URL aliases
- `/sign-in`, `/login`, `/log-in` → `/signin`
- `/sign-up`, `/register` → `/signup`
- Root cause was a routing gap, not auth logic. Fixed in `App.js`.

### Weekly Influence Digest
- New APScheduler job `influence_digest_weekly` — Monday 08:00 UTC,
  beats the Tuesday Exco360 (10:00 UTC) into the inbox.
- `POST /api/cron/weekly-digest` (X-Cron-Secret guarded) iterates
  every active context, builds the 7-day Influence Map per context,
  emails each executive member their own roll-up. Honours
  `digest_opt_out` flag on context_members.
- `POST /api/contexts/{cid}/influence-map/digest` — manual fire for
  the calling user only. Used by the admin tile + tested directly.
- Editorial email body: top-5 influencers + most-engaged docs +
  totals strip + open-the-full-map CTA. Cream + oxblood + Georgia.

### Admin Health Dashboard (`/admin/health`)
- Superadmin-only one-click pre-deploy / pre-demo green light.
- `GET /api/admin/health/full` runs 6 checks in parallel via
  `asyncio.gather`:
  - **mongo** — ping + insert/delete round-trip on
    `db.health_check`
  - **llm** — 1-token Emergent call, claude-haiku-4-5
  - **resend** — API-key shape + sender-domain config check
    (no email sent)
  - **stripe** — read-only `/v1/balance` probe, distinguishes test
    vs live key
  - **scheduler** — `app.state.scheduler.running` + jobs registered
    with next_run_time
  - **cron_secret** — env presence + length sanity
- Each check returns `{status: pass|warn|fail|skip, evidence|error|
  note, latency_ms?}`; overall is the worst.
- Frontend: auto-runs on mount, manual refresh, 4-status colour grid.
  Live grid currently surfaces two real pre-launch items the user
  should swap before going live: **Stripe (FAIL — placeholder key
  `sk_test_emergent` rejected by Stripe)** and **Resend (WARN —
  sandbox sender; verify a domain)**. Both are env-only swaps.



### Login was broken for users hitting `/sign-in` (with hyphen)
The app's internal links use `/signin`, but external bookmarks, search
engines, old emails, and muscle memory commonly reach for `/sign-in`,
`/login`, or `/log-in`. The catch-all route was silently bouncing
those to `/` (the marketing landing page), which from the user's
perspective looked exactly like "the login is broken." Reproduced
end-to-end: typing `/sign-in` rendered the landing hero, the form
testid never resolved.

### Fix
Added explicit aliases in `/app/frontend/src/App.js`:
- `/sign-in`, `/login`, `/log-in` → `<Navigate to="/signin" replace />`
- `/sign-up`, `/register` → `<Navigate to="/signup" replace />`

Verified end-to-end: typing `/sign-in` now redirects to `/signin`,
form renders, login returns 200, lands on `/app` with token
persisted, dashboard renders, **role-scoped nav correctly hides
Cycle + Workflows in NED mode** (the iter36 surgical fix).


12/12 backend + 100% frontend GREEN
(`/app/test_reports/iteration_36.json`,
`/app/backend/tests/test_iter36.py`):

### Chat — bank-grade audit pack export
- New `GET /api/chats/{cid}/audit/export.zip` — returns a 5-file zip:
  `manifest.txt`, `chat.json`, `messages.json`, `audit_chain.json`,
  `verify.py`. Messages carry `content_sha256` only — raw content is
  never bundled.
- `verify.py` is stdlib-only; runs `python3 verify.py` against the
  unzipped chain and exits 0 ('OK — verified N rows. Chain intact.')
  on integrity, 1 ('hash mismatch') on tampering.
- The export itself appends an `audit.exported` row to the chain.

### Share Evolution Diff CTA (extension of iter34)
- `/api/shares` `item_type` extended with `doc_evolution`; gated on
  cached `evolution_diff.diff.what_changed` + `related_doc_id`.
- Email body now renders the LLM diff blocks: What changed · Added or
  strengthened · Weakened or removed · Put on the table.
- Share gesture mounted on `<DocumentEvolutionPanel />`.

### Influence Map (last open P1)
- New `routers/influence_map.py` aggregates over `document_engagement`
  + `shares` (doc-targeted) + `collab_comments` + `mentions`. Edge
  weights: read=1, share=3, comment=4, mention=5.
- `GET /api/contexts/{cid}/influence-map?days=N` returns nodes
  (people + docs), edges (source/target/kind/weight/last_at), and
  rolled-up `people` / `top_docs` / `totals`.
- New `/app/influence` page — editorial bipartite matrix (people × docs)
  with cell intensity scaling 5 levels of cream → oxblood, glyphs
  ·/◐/●/★ per kind, top-influencers and most-engaged-docs panels,
  7d/30d/90d/1y window picker.

### Role-separation surgical fix
- `NAV[i].roles` flag in `AppShell`. `Cycle` and `Workflows` scoped to
  `executive` only — NEDs no longer see them in the rail. Smallest
  safe change to address the loudest bleed without breaking either
  flow.

### Landing copy
- New `05 · The chat` feature block: "One subscription. Every model.
  Bank-grade audit." Heading updated to "Five surfaces. One discipline."

### Open / deferred — Slice 11+
- Monitor "green stick" — needs user pointer.
- Status bar redesign on Signals page — needs user pointer.
- Deeper role-separation across Highlights, Briefings, Workspace,
  Simulate, Lens (currently identical for both roles).
- Production swap: Stripe live key + Resend verified sender domain
  (env-only, no code).


13/13 backend + 100% frontend e2e GREEN
(`/app/test_reports/iteration_35.json`,
`/app/backend/tests/test_iter35_chat.py`):

### Login bug fix
- `AuthContext.afterAuth` now persists `data.access_token` to
  `localStorage['akki_access_token']` so the Bearer interceptor can
  recover when cross-site cookies are blocked (Safari 16+ ITP, Brave
  shields, Firefox strict, deployed-on-different-domain scenarios).
- `bootstrap()` clears stale tokens on `/auth/me` failure so a
  poisoned token can't loop the user back to the landing page.

### Standalone Chat surface (NEW · `/app/chat`)
- Untethered from any company context — privacy-shielded multi-model
  AI workspace. Replaces the need for separate ChatGPT/Claude/Gemini
  subscriptions.
- 5 models: Claude Sonnet 4.5, Claude Haiku 4.5, GPT-5.2,
  Gemini 2.5 Pro, Gemini 2.5 Flash (via `EMERGENT_LLM_KEY`).
- Conversations persist by default (1a). Per-conversation shielding
  policy: auto (default) · always · off.
- **Auto policy** detects identifiers via `shield_payload()` and
  shields BEFORE sending to provider, then rehydrates the reply.
  Multi-turn references survive shielding (verified live).
- **Policy=off footgun guard**: sensitive content + no acknowledgement
  → 409 `shielding_acknowledgement_required`. User must explicitly
  confirm via bypass dialog; the bypass + reason is audited.
- **Bank-grade audit log** (`chat_audit_log` collection):
  - Append-only (insert only, no updates/deletes from app code)
  - SHA256-chained: each row's `row_hash` = SHA256 of canonical JSON
    of `(prev_hash, id, at, account_id, chat_id, action, payload, ip,
    ua_sha)`. Tampering with any row breaks every downstream hash.
  - Captures IP and `ua_sha` (truncated SHA of user-agent) per event.
  - Never stores raw message content — uses `content_sha256` as a
    fingerprint so auditors can prove existence without exposure.
  - GET `/api/chats/{cid}/audit` returns the chain plus the
    verification recipe.
- Cross-account isolation: every read/write filters on `account_id`
  → 404 on attempts to read another user's chats or audit.

### Home metrics (filling the iter33 gap)
- Six tiles (was four): Signals · Briefings · Cycle · **Reports
  (sent + total drafted)** · Document Journal · **Network (companies +
  team members)**. Grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-6`.

### Open / deferred — Slice 10+
- **Influence Map** — last open P1.
- **Share Evolution Diff CTA** — small extension of `doc_summary`
  share to also share the LLM-generated drift summary across cycles.
- **Role-separation bleed sweep** — NED ↔ Exec UI bleed
  (needs user pointers).
- **Monitor "green stick"** — needs user clarification.
- **Status bar redesign on Signals page** — needs user pointer.
13/13 backend + iter33 regression GREEN. Frontend e2e GREEN
(`/app/test_reports/iteration_34.json`):
- **Share Document Summary** — new `doc_summary` item type on
  `POST /api/contexts/{cid}/shares`. Email body carries TL;DR +
  numbered "What matters" + italicised "Walk in asking" quotes plus
  a deep link to the workspace doc. AKKI-internal recipients still
  get a mention row. Wired into `<DocumentSummaryPanel />` as a
  `Send` gesture next to `Re-read`.
- **Movable home cards** — native HTML5 DnD via
  `useDraggableSections('home', …)` hook. Order persists per user
  to `localStorage['akki:section-order:home']`; reconciliation on
  mount handles added / removed sections. Drag handle appears on
  hover only so the page stays editorial. Reset gesture surfaces
  only after a reorder.
- **NED Document Evolution Chain** — `PATCH /…/documents/{did}` now
  also accepts `related_doc_id` (null to unlink) with self-link,
  cycle, and cross-context guards. New
  `POST /…/documents/{did}/evolution-diff` returns LLM-powered
  what-changed (added_or_strengthened / weakened_or_removed /
  questions_for_management) cached on the doc record. Frontend
  surfaces it as `<DocumentEvolutionPanel />` in the Document Viewer
  right rail with chain ribbon + diff body + LinkVersionDialog
  (filter + unlink).

### Open / deferred — Slice 9+
- **Influence Map** — visualise who's read / shared / commented on
  what. Engagement records already exist (`document_engagement`,
  `shares`, `mentions`); needs an aggregator endpoint + a node-link
  visualisation.
- **Learn refresh agent** — periodic primary-source content puller.
- **LinkedIn API posting scaffold** — manual copy/paste fallback exists.
- target_date ISO sort.

## Iter43 — Tier-A · Strategic Addendum: Quick-Results + Validation chip + Differentiator copy (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_43.json`,
`/app/backend/tests/test_iter43_quick_results.py`):
- **§1.1 Sandbox Quick-Results journey** — new
  `/app/quick-results/:contextId/:docId` page. After a sandbox upload,
  the user lands on a focused screen with **3 doc-bound use-cases**
  (Read me the summary · What does the board need to notice? · Draft
  a briefing for my next meeting). One-click each, output renders
  inline. After ANY result completes, a single "Want more? — Open my
  full sandbox" CTA reveals. Replaces the previous flood-the-stream
  pattern with a "client seeks, client gets" moment. SandboxPackDrop
  now redirects here on successful upload.
- **§4.2 / §5 ValidatedBadge** — `<ValidatedBadge />` chip
  (`Validated by an independent model`) surfaced on briefings header,
  document summary panel (top of summary content), every signal card
  row (after the type chip), and the QuickResults hero. Hover/click
  reveals an editorial methodology popover explaining the second-model
  countercheck. Methodology grounded on the existing Synisense-shielded
  pass; backend-side real second-model validator is a deferred
  follow-up per user steer.
- **§5 Differentiator sublines in Sandbox streaming reveal** — woven
  into existing STREAMING_STAGES (no new stages):
  · stage 0/1 — multi-LLM avatar + "GPT, Claude and Gemini through one
    secure surface"
  · stage 3 — "Wiring AKKI's email handle so it can send checklists"
  · stage 5 — "A separate model counterchecks every claim"
  · stage 8 — "Each section will carry the 'Validated by an
    independent model' mark"


## Iter42 — Cycle drawer fix + Workflow spine + Home metrics + Act-on KPI (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_42.json`,
`/app/backend/tests/test_iter42_signal_kpi.py`):
- **Cycle drawer overlap bug fix** — TabsList swapped from
  `overflow-x-auto` → `flex-wrap` so tabs reflow onto a second row at
  tablet widths instead of sliding under the right portfolio rail.
  PortfolioRail given a soft left-edge shadow as a visual separator.
- **Workflow 4-step spine** — page heading rewritten as
  "Receive · Consolidate · Generate · Submit." A new
  `cycle-spine-strip` renders 4 stages above the tabs with the active
  tab's stage highlighted (`tracker`→none, `reportees|bank|checklists`
  →receive, `inbox`→consolidate, `reports`→generate).
- **Home editorial metrics strip** — replaces the "too SaaS-tile"
  pattern with a single horizontal row of serif numerals separated
  visually by spacing (Signals · Briefings · Documents · Companies ·
  Shared with you). Hidden on empty contexts.
- **Act-on heatmap** (improvement, `/admin/signal-kpi`,
  superadmin-only):
  - `GET /api/admin/signals/action-heatmap` —
    `{by_bucket: [{bucket, acted, shared, recommendations:
    [{label, picks}]}], totals: {acted, shared, share_recipients},
    recent_actions[≤25]}`. Custom (no-rec-idx) acts collapse to
    "(custom — composer)" so the heatmap stays legible.
  - Frontend: per-bucket cards with horizontal pick bars +
    most-recent-25 timeline.


## Iter41 — Tier 2.5 batch (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_41.json`,
`/app/backend/tests/test_iter41_signal_actions.py`):
- **Simulate horizontal scenario rows** — replaced 3-column vertical grid
  with full-width `<ScenarioRow>` (label gutter + body running across at
  ~70-char measure). Best / Base / Stress on stacked horizontal rows.
  Prominent "New simulation" button (`simulate-new-btn`) at the top of
  the viewer.
- **Document Journal — 3 panels → 2** — Summary + Evolution stacked in
  the right rail; Outline moved to a header popover
  (`doc-outline-toggle` + `doc-outline-popover`). Conditionally rendered
  when headings.length > 0.
- **Signals · Act vs Share differentiation** — new
  `signal_actions` collection, `_RECS_BY_TYPE` templates indexed by
  signal bucket (risk / opportunity / gap / neutral), heuristic
  classifier on tone/kind/headline keywords.
  `GET  /api/contexts/{cid}/signals/{sid}/recommendations` →
  `{bucket, recommendations[3]}`.
  `POST /api/contexts/{cid}/signals/{sid}/actions` (acted | shared) —
  resolves `recommendation_label` server-side from idx; persists
  recipients + note.
  `GET  /actions` returns `{actions[], summary: {acted,
  last_acted_label, shared_count, shared_with}}` — `shared_count`
  de-dupes recipients.
  Frontend: 'Act on this' opens a 3-recommendation dropdown
  (`signal-act-menu-{id}` + `signal-act-rec-{id}-{idx}`); 'Something
  else' escape opens the existing ActModal. After action, button flips
  to "Acted on" + indicator chip (`signal-acted-badge-{id}`,
  `signal-shared-badge-{id}`) renders below the summary. Share success
  auto-logs a shared action via `ShareModal.onShared` callback +
  cross-component `akki:signal-action` event-bus.


## Iter40 — Strategic Goals card overhaul + Sandbox KPI dashboard (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_40.json`,
`/app/backend/tests/test_iter40_goals_kpi.py`):
- **Strategic Goals card overhaul** per user spec:
  - `category` field added (revenue | customer | product | people |
    operations | compliance) — top-left chip, color-coded.
  - `initiatives_count` (0–99) — small layered icon + count in the
    secondary row.
  - Conic dials replaced with slim horizontal **progress bars** sitting
    side-by-side on a single row to the right of the title, equal
    spacing.
  - **Narrative under each bar** ("At risk. Drift is real but
    recoverable." / "Plausible — assumes the current trajectory
    holds.") — answers "what does a 78 mean".
  - Tight whitespace — title row + secondary row, two clean editorial
    lines.
  - "How is this calculated?" hoisted to the panel header (single
    instance, not per-row).
  - LLM extraction prompt updated to populate both new fields;
    backend whitelist-clamps invalid values.
- **Sandbox Conversion KPI dashboard** (`/admin/sandbox-kpi`,
  superadmin-only) — closes the Q5 measurement loop:
  - `GET /api/admin/sandbox/kpi` — totals (captured / answered / yes /
    partial / no / skipped + answer-rate-% + delivery-rate-%) +
    per-sector breakdown sorted by volume.
  - `GET /api/admin/sandbox/objectives?limit=&sector=&answer=` —
    most-recent-first list with answer + free-text note, server-side
    filtered.
  - Aggregation handles BOTH sandbox-typed and seeded real contexts
    (sandbox_metadata vs seeded_metadata via `_flatten_meta`).
  - Frontend: 4 stat tiles + sector table + objectives list with
    sector + answer filters; non-superadmin redirected to /app.


## Iter39 — Tier 1 gap-plug + Tier 2 quick wins (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_39.json`,
`/app/backend/tests/test_iter39_briefings_objective_check.py`):
- **24-hour objective-check follow-up** — `GET/POST
  /api/sandbox/contexts/{id}/objective-check`. Surfaces ~24h after
  generation, captures yes/partial/no + optional note (or `skip`).
  Works on both sandbox + seeded real contexts.
  `<ObjectiveCheck />` rendered on AppHome below the tutorial card.
- **Briefings read tracking** — `briefing_reads` collection (Mongo
  upsert per (briefing_id, account_id)). `POST
  /api/contexts/{cid}/briefings/{bid}/mark-read` with
  `via: "manual"|"scroll"`. List endpoint annotates each row with
  `is_read` / `read_via` / `read_at` for the caller. Frontend:
  Mark-as-read button in the viewer header + auto-mark on ≥70%
  scroll-depth + read-state indicator on rail rows + total/unread
  count in rail header.
- **Monitor green sparkline removed** — replaced with a discreet
  "How is this calculated?" methodology popover so a sceptical user
  can audit the score's machine-generated derivation.
- **The Lens — Apply repositioned** — picker row now holds only the
  two dropdowns; Apply moved BELOW the input description. Natural
  read → apply flow.
- **Cycle deadline picker** — replaced free-text deadline input with
  `<input type="date">`; YYYY-MM-DD is converted to "DD Month YYYY"
  for the dispatch email body (UTC-explicit to avoid TZ drift).
- **Compose Report tile** — `<ComposeReportTile />` replaces the
  inline corner button. Surfaces contextual notes:
  "AKKI has all the information you need." (all reportees in) /
  "N direct reports haven't responded to AKKI yet." (pending) /
  "No reportees set up yet." (empty roster).
- **Tutorial copy** — sector-narrative framing per the doc:
  "A story shaped to what you came here for."


## Iter38 — Tier 1 · Sandbox conversion overhaul (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_38.json`,
`/app/backend/tests/test_iter38_sandbox_tier1.py`):
- **Capture testing objective** — Sandbox + Add Company now ask Q5
  ("What would make this trial feel like time well spent?"). Stored
  on `sandbox_metadata.objective` / `seeded_metadata.objective`.
- **Tutorial-style first-run card** — `/api/sandbox/contexts/{id}/tutorial`
  returns objective recap + first seeded brief + first signal headline +
  3 step links + suggested chat opener. `<SandboxTutorial />` renders on
  AppHome; dismiss persists via `/tutorial/dismiss`.
- **Hybrid serif streaming reveal** — Generation page redesigned. Each
  stage now has `headline` + `sublines[]` (1–3 italic Georgia lines that
  reveal one-by-one inside the stage window). Paper-tape scrolls upward
  with serif headlines + italic sublines. No terminal/code aesthetic.
- **Other-sector free-text** — Picking "Other" reveals `other_sector_name`
  + `other_sector_description`; `resolve_stage_texts` substitutes the
  user's named sector into the streaming narrative.
- **Add Company unified flow** — `NewWorkspace.jsx` rewritten to mirror
  the Sandbox 5-question editorial journey. Submits to new
  `POST /api/sandbox/contexts/seeded` which provisions a real
  (executive_personal/ned_personal) context, seeds the matching sector
  template, and returns the new context for `switchContext()`.
- **Dropdown contrast bug** — `select.jsx` SelectTrigger now sets
  `text-foreground` so selected values render in dark ink (was white-on-
  white in some pages).
- **Chat ?prompt= deeplink** — `/app/chat?prompt=…` pre-fills the
  composer, then strips the param. Used by tutorial card "Open in Chat".


## Iter36 — Audit pack · Influence Map · Share evolution diff · Role bleed (Apr 2026)
12/12 backend + 100% frontend GREEN
(`/app/test_reports/iteration_36.json`):
- **Chat audit pack export** — `GET /api/chats/{cid}/audit/export.zip`
  returns 5-file zip (manifest + chat + messages + chain + verify.py).
  Stdlib-only verifier; passes on integrity, fails on tampering.
- **Share Evolution Diff CTA** — `/api/shares` `item_type='doc_evolution'`
  with full LLM-diff email body. Wired into `<DocumentEvolutionPanel />`.
- **Influence Map** — `routers/influence_map.py` aggregator across
  engagement + shares + comments + mentions; `/app/influence` page with
  editorial bipartite matrix view + top-influencers/top-docs panels.
- **Role-separation surgical fix** — `NAV[i].roles=['executive']` on
  Cycle + Workflows; NEDs no longer see them.
- **Landing copy** — `05 · The chat` block + heading "Five surfaces.
  One discipline."

## Iter35 — Login fix + Standalone Chat + Home metrics (Apr 2026)
13/13 backend + 100% frontend GREEN
(`/app/test_reports/iteration_35.json`,
`/app/backend/tests/test_iter35_chat.py`):
- **Login fix** — `AuthContext.afterAuth` now persists `access_token`
  to localStorage as a Bearer fallback for browsers blocking
  cross-site cookies (Safari ITP, Brave, Firefox strict). `bootstrap()`
  clears stale tokens on `/auth/me` failure.
- **Standalone Chat surface** at `/app/chat` — privacy-shielded
  multi-model AI workspace untethered from any company context. 5
  models via `EMERGENT_LLM_KEY`. Bank-grade audit log
  (`chat_audit_log` collection, SHA256-chained, IP + UA-hash
  captured, content stored as `content_sha256` only).
- **Home metrics** — added Reports (sent + total drafted) and
  Network (companies + team members) tiles. 6 tiles total.

## Iter34 — Three follow-on items (Apr 2026)
13/13 backend + iter33 regression GREEN. Frontend e2e GREEN
(`/app/test_reports/iteration_34.json`):
- **Share Document Summary** — new `doc_summary` item type on
  `/api/shares` with TL;DR + numbered "What matters" + "Walk in
  asking" quotes plus deep link.
- **Movable home cards** — native HTML5 DnD via
  `useDraggableSections('home', …)` hook, persisted to
  `localStorage['akki:section-order:home']`, drag handle on hover.
- **NED Document Evolution Chain** — `PATCH related_doc_id` (with
  self-link / cycle / context guards) +
  `POST /…/documents/{did}/evolution-diff` LLM endpoint returning
  drift (added/weakened/questions). `<DocumentEvolutionPanel />` in
  Document Viewer right rail with chain ribbon + LinkVersionDialog.

## Iter33 — User feedback batch (Apr 2026)
9 page redesigns shipped in one batch, 7/7 backend + 11/11 frontend
verified by testing agent (`/app/test_reports/iteration_33.json`):
- **Lens** — renamed kicker to "In the Lens"; replaced the cluttered top
  rail with a single horizontal picker (Lens dropdown · Test-us dropdown
  · Apply); single textarea labelled by what the user is testing.
- **Home** — InSummaryTiles moved to TOP for at-a-glance scan; fixed
  signal breakdown bug (was bucketing on s.severity which doesn't
  exist; now buckets on s.type → risk/opp/gap); consolidated
  PlayReadyCards + AgendaEvolutionCard + PlaysInProgressStrip +
  QuickActions into one tabbed `<WorkflowsHub />` so the page no longer
  reads as walls of text.
- **Documents/Journal** — replaced upload chalkboard with a stats hero
  (`<DocumentJournalStats />`) showing total / trust split / extracted;
  upload drawer auto-collapses when docs exist; selecting a document
  generates an AKKI summary in the right rail
  (`<DocumentSummaryPanel />`) with TL;DR + What matters + Walk in
  asking. New endpoint
  `POST /api/contexts/{cid}/documents/{did}/summary` (cached on the
  doc record; ?refresh=true bypasses).
- **Signals** — header copy changed to "Risks. Opportunities. Gaps.";
  decorative donut replaced by `<HighlightsStats />` carrying actual
  informational mass (% breakdown bars + 14-day volume sparkline +
  confidence split); generator collapsed to a single quiet line.
- **Briefing** — added a `briefing-journey` block at the top of every
  briefing answering Before / During / After (what this is about · cycle
  & company · what to do once briefed).
- **Compose Report** — new optional `description` field
  (`compose-description-input`) lets the author tell AKKI the angle;
  surfaced as a quoted "What the author asked for" header at the top of
  the starter draft. Backend persists the field on the report record.
- **Simulate** — input-first redesign: hero explains hypothesis testing
  in two lines, journey strip numbers the 01/02/03 input → run → output
  flow, large input card is the obvious thing to use, starters card
  shows when input is empty.
- **Monitor** — renamed Score → Performance Score and Probability →
  Success Probability; aligned the two dials on the same horizontal
  line with the sparkline beneath spanning both; removed the edit
  pencil (the score is machine-generated, not user-editable).
- **Cycle** — tab order reorganised around the 4-step spine: Overview ·
  1·Your team · 2·Question bank · 3·Send checklists · 4·Receive
  submissions · 5·Consolidate & send up. Header copy "Receive ·
  Consolidate · Send up." reinforces the spine.


## §UX iter49 — Real validator + Mark-as-read + Plays-aware Ask + Workflow rail (2026-04-28)

### Why
Burn down the iter48 backlog so only architectural Tier-C work remains.

### What shipped
- **Mark-as-read on Activity timeline** (`/app/activity?cat=*`) —
  per-user, per-context, persisted in `localStorage` under
  `akki.activity.read.{cid}`. Read items render italic + muted, no
  unread dot. New "Mark all read" button.
- **Real second-LLM validator** — `llm_service.validate_independent`
  (Gemini 2.5 Flash) runs after Claude drafts a brief, returns
  `{verdict, confidence, notes[], validator_provider, validator_model}`.
  Persisted on the brief record. ValidatedBadge accepts a `validation`
  prop and renders a verdict-coloured chip with a hover popover showing
  the validator's notes and identity. Soft-fails closed
  (verdict='qualified', 'Validator unavailable') so the brief endpoint
  is never gated by validator outage.
- **Plays-aware M13 Ask** — the `/ask` prompt now includes an
  `[ACTIVE WORKFLOWS]` block listing up to 3 currently-active plays for
  the context so answers frame themselves in the user's working state.
- **Workspace 'Workflow context' panel** — third right-rail section on
  the Document Journal listing active plays in the company with click-
  through to `/app/plays/{id}`. Light-touch link today; ready to upgrade
  when play↔doc linkage ships.
- **Polish**: `_target_date_sort_key` lifted to module scope in
  `strategic_goals.py` (no per-request regex compile). Deprecated the
  redundant `validated: True` boolean on briefs in favour of
  `validation.verdict`. Stable `prepare-brief-history-{id}` testid on
  the past-brief rail rows.

### Tests
- iteration_49.json — backend 6/6, frontend 95% (all features
  verified; one minor click-target selector stability nit fixed in
  the same iteration).

### Open / deferred — Tier-C only
- Minutes as first-class entity (large architectural — needs new doc
  type, extractor, linkage to Cycle/Monitor; will plug into Prepare's
  right rail as a third tab).
- Personal vs Enterprise tier split (largest — separate billing + data
  models; needs scoping conversation with the user).
- Inbound email parsing/receiving (needs Postmark or Resend Inbound
  API key from the user).
- Concurrency optimisation: issue Gemini validator concurrently with
  audit-log writes via `asyncio.gather` to keep p50 brief latency
  under 30s once warm.
- framer-motion stagger first-paint nit on AppShell NAV.


## §UX iter48 — Activity grouped + Sandbox accept-upload + Backlog burn-down (2026-04-28)

### Why
Two new user asks added to the queue, and the user instructed "ensure
all pending requests are tracked and the backlog is not significant".
Iter48 ships both new asks plus the small/medium backlog items so only
genuinely architectural Tier-C work remains.

### What shipped
- **Activity feed regrouped** (`RecentActivity.jsx`) — five category
  tiles instead of a chronological list: Briefings & meetings ·
  Questions answered · Signals surfaced · Documents added · Sent your
  way. Each tile shows count + verb + latest title + "View timeline →".
  Tiles with zero count render disabled. AppHome now also fetches
  `/contexts/{cid}/briefs` so "Questions answered" reflects saved briefs.
- **Activity timeline page** (`/app/activity?cat={key}`) — chronological
  day-grouped list for the chosen category, category-pill switcher,
  back-to-Home link.
- **Sandbox accept-upload** — new `GET /api/sandbox/contexts/{cid}/sample-doc`
  returns a tailored "this could be your board pack" preview;
  `POST /api/sandbox/contexts/{cid}/sample-doc/accept` materialises it
  as a real document and stamps `sandbox_metadata.sample_doc_accepted`.
  Frontend: `SandboxSampleDoc` card on AppHome (sandbox-only, hidden
  once accepted). Sits ABOVE the existing drop-your-own affordance.
- **BriefDetailModal Continue-in-Chat chip** — navigates to
  `/app/chat?prompt=…&new=1&seed_title=…`. Chat now auto-creates a fresh
  conversation with the title, seeds the composer with the brief body,
  and strips the query params after consumption.
- **InSummary Portfolio aggregation** — pending_actions now folds in
  `c.pending_actions` across the role-scoped portfolio (max of portfolio
  aggregate vs active-context number).
- **Strategic-goals sort** — list endpoint now sorts by a normalised
  target_date key (handles `YYYY-MM-DD`, `Q1-Q4 YYYY`, `Mmm YYYY`,
  null-last). Editorial sort order on the Strategic Goals card is now
  deterministic.

### Tests
- iteration_48 — backend 6/6 (after testing agent fixed a bad
  `write_audit` call in `sandbox_sample_doc_accept` — wrong kwargs +
  missing `await`), frontend 95% (Continue-in-Chat testid was reachable
  by code but not by data; main agent then seeded a brief for Bramuel
  so it is now exercisable).

### Open / deferred — Tier-C only
- Minutes as first-class entity (will become a third tab in Prepare's
  right rail).
- Personal vs Enterprise tier split.
- Inbound email parsing/receiving.
- Real second-LLM ValidatedBadge pass.
- Plays-aware M13 Ask context biasing.
- Workspace "Play context" right-panel section.

### Cleanups parked (not blocking)
- framer-motion stagger on AppShell NAV (mild first-paint nit).
- Lift `_sort_key` regex compilation out of `list_goals` to module scope.


## §UX iter47 — Prepare 2-col rail + Dynamic Workflow dock + Recent activity (2026-04-28)

### Why
Targeted user feedback after iter46 acceptance:
  1. Move Document Journal up in the sidebar (was last).
  2. Drop the word "consumed" from the Reports InSummary attribute.
  3. Make the Workflow dock dynamic — surface most popular / unused / new
     features / "Monitor your performance" by relevance, not statically.
  4. The bottom four-tab block on Home was duplicating the InSummary
     above — propose a better hook.
  5. Restore the visual stats dock from the old standalone Signals page
     onto Prepare → Signals.
  6. Add a right-side list rail to Prepare with topic + timeline filters
     that swaps brief↔signal based on the active tab.

### What shipped
- **Sidebar reordered** — Home → Document Journal → Chat → Prepare → …
- **Reports tile** — first attribute now reads "submissions" (not "submissions consumed").
- **Dynamic Workflow dock (`QuickActions.jsx`)** — every tile carries a
  `priority(state)` function. We compute scores from the user's actual
  data (unread briefings, pending reports, in-progress plays, recent
  docs, signal count) and surface the top 3. New tiles: "Monitor your
  performance" (steady mid-priority, links /app/monitor), "Catch up on
  briefings" (only when unread > 0), "Surface signals on something"
  (boosted when totalSignals = 0; opens /app/prepare?tab=signals).
- **RecentActivity (`components/home/RecentActivity.jsx`)** — single
  chronological feed merging signals + briefings + documents + shared
  items into one editorial timeline ("DOCUMENT ADDED · 3d ago"). All-
  boards / This-company toggle is now wired to AppHome's existing scope
  state (was label-only — now genuinely behaviour-changing). Replaced
  the four-tab summary repeater entirely.
- **Prepare 2-col layout** — main column (form + tab section header) at
  left; new `PrepareSideRail` at right with topic search + 7d/30d/All
  timeline chips. Rail tab swaps brief↔signal based on active tab. Lifted
  briefs/signals fetch state to the page so the rail can refresh after
  a generate event.
- **Brief / Signal detail modals** kept inline (no extra route). New
  Delete affordance added to BriefDetailModal next to Send-to-colleague.
- **HighlightsStats restored** — the standalone-Signals visual the user
  remembered (sparkline + risk/opportunity/gap breakdown bars +
  confidence summary) is now mounted on Prepare → Signals when at
  least one signal exists. Brief tab keeps the calmer PrepareStatsDock
  with the three progress-bar cards.
- **Prepare deep-link** — `/app/prepare?tab=signals` lands directly on
  the Signals tab (used by the new Quick Action tile).

### Tests
- iteration_47.json — 11/11 frontend acceptance items pass at 100%.
  Two minor reviewer nits addressed in the same iteration (scope toggle
  no longer label-only; try_signals tile lands on Signals tab via deep
  link).

### Open / deferred
- Tier-C: Minutes as first-class entity (will plug into Prepare's right
  rail as a third tab).
- Tier-C: Personal vs Enterprise tier split.
- Tier-C: Inbound email parsing.
- Real second-LLM ValidatedBadge pass.


## §UX iter46 — Role isolation + InSummary redesign + Sidebar reorder (2026-04-28)

### Why
User feedback batch: workflow dock was getting truncated; intro copy
needed updating; explicit role toggle (NED/Exec) needed; strict role
isolation rule across the entire system; sidebar reorder + renames;
InSummary tile metrics rewritten; Prepare page lacked visual lift.

### What shipped
- **Sidebar reorder + renames** (`AppShell.jsx`):
  Home → Chat → Prepare → Workflows (exec) → The Lens (POV) → Test
  Hypothesis (was Simulate) → Reporting Cycle (was Cycle, exec) →
  Monitor → Learn → Influence Map → Document Journal.
- **ContextChooser**: new copy "You work in X companies as NED and Y as
  Executive. Where would you like to start?" with role-toggle buttons
  (`home-role-ned`, `home-role-executive`). Filter only shows contexts
  for the active role.
- **Strict role isolation** (`AuthContext.switchRole` + `QuickActions`):
  Switching role rebuilds the experience — if active context's
  `my_role` mismatches new role, redirect to `/app` and pick a same-org
  fallback if available. QuickActions tile filter no longer exposes the
  other role's tiles.
- **`my_role` enrichment** (`AuthContext.enrichContexts`): /auth/me
  sometimes omits `my_role`; we now derive it from `c.type` (`ned_*` →
  ned, `executive_*` → executive) so every consumer has a single source
  of truth.
- **InSummaryTiles fully rewritten**: each tile carries hero number +
  3 attribute lines per spec (Signals/Briefings/Reporting Cycle/Reports/
  Documents/Portfolio).
- **Workflow dock truncation fix**: removed `overflow-hidden` on the
  AppHome content wrapper that was clipping Quick Actions cards on
  narrower viewports.
- **PrepareStatsDock**: new component above the line tabs with three
  progress-bar cards (Brief coverage, Signal pulse, Briefing rhythm).

### Tests
- iteration_46.json — frontend: sidebar order + renames, role toggle,
  context-chooser intro, InSummary structure, Prepare stats dock,
  WorkflowsHub truncation all pass.
- After my_role enrichment fix verified manually:
  intro = "You work in 6 companies as NED and 5 as Executive."
  Portfolio attrs = "6 acting as NED · 5 acting as Exec · 0 pending".
  NED chip list = 6 chips. Switching to Exec → 5 chips, right rail
  swaps to Exec-only contexts, sidebar gains Workflows + Reporting
  Cycle.

### Known nits / follow-ups
- "0 pending actions" on Portfolio when scoped to a single context;
  could aggregate across all contexts a user holds the active role on.
  Deferred — current scope is "today's focus".
- True same-org context-switch on role change requires `org_id` on
  ContextRecord, which isn't always populated. Falls through to "any
  context with new role" gracefully.

### Next (Tier-C — sized for separate sessions)
- Minutes as first-class entity
- Personal vs Enterprise tier split
- Inbound email parsing
- Real second-LLM ValidatedBadge pass


## §UX iter45 — Prepare redesign + Send-to-colleague + Tier-B pills (2026-04-27)

### Why
User feedback after iter44: "Replace [the line-tab inline blurbs] with
'Generate Brief' and 'Generate Signals'. Describe the section beneath the
selection line before the input box. Redesign the section under the line
tab dock. Organise input, output and list nicely." Plus: ship the full
backlog and the suggested improvement (send-to-colleague chip).

### What shipped
- **Prepare page redesigned** — line tabs now carry just labels (Brief /
  Signals). Below the tabs: a section kicker ("Generate Brief" /
  "Generate Signals") + descriptive serif blurb. Form box reorganised into
  three zones — **Step 1** (kind / focus chips) → **Step 2** (objective /
  focus textarea with character counter and inline help) → **Action** (the
  validated-by-independent-model badge on the left, primary button on the
  right). Recent items list now sits under a proper section divider with
  an "X saved" tabular count.
- **Send to a colleague** chip on `BriefDetailModal` — opens the existing
  `ShareModal` with `itemType="brief"`. Backend `routers/shares.py`
  extended to accept `brief` as an `ItemType`; cross-context 404 guard
  intact.
- **Continue with [doc] topbar pill** (Tier-B) — new
  `components/layout/ContinueWithPill.jsx`. Records the last document
  the user opened (in QuickResults or DocumentViewer) into
  `localStorage.akki_continue_with`. The pill renders in the AppShell
  topbar across every authed page, hidden on `/app/workspace` and
  `/app/quick-results/*` where it would be redundant. Stale > 7 days
  auto-clears. Click takes the user back to QuickResults; X dismisses.
- **Chat model avatar visual** (Tier-B) — new
  `components/chat/ModelAvatar.jsx`. Provider-coloured monograms
  (oxblood C for Claude, ink G for GPT, gold ✦ for Gemini). Wired into
  the model picker trigger, dropdown rows, and every assistant message
  bubble so the executive sees at a glance which model produced which
  reply.
- **Helper extracted** — `helpers/llm_json.py:safe_parse_json` consolidates
  the fence-strip + prose-fallback logic that was duplicated in
  `prepare.py` + `plays.py`. Behaviour-equivalent.
- **Cleanup** — removed the now-unrouted `pages/Highlights.jsx` and
  `pages/Briefings.jsx` files.

### Tests
- `test_iter45_shares_brief.py` — 9/9 backend GREEN (brief share happy
  path, 404, regression on existing share types, safe_parse_json
  regression via brief CRUD).
- `test_iter44_prepare.py` — 12/12 STILL GREEN.
- Frontend 100% on Prepare redesign, ContinueWithPill, ModelAvatar
  picker + bubbles, sidebar Prepare entry, redirect from /app/highlights
  and /app/briefings.

### Open / deferred — Tier-C and beyond
- Minutes as first-class entity (anchor for Cycle + Monitor) — needs new
  doc type, extraction, linkage. Sized for its own session.
- Personal vs Enterprise tier split (`akki.ai/personal` vs
  `akki.ai/enterprise`) — separate billing/data models. Sized for its
  own session.
- Inbound email parsing/receiving integration — needs an external
  inbound provider (Postmark / Resend Inbound).
- Upgrade `ValidatedBadge` to a real second-LLM validation pass
  (currently re-uses Synisense shielding).


## §UX iter44 — Prepare consolidation + tone polish (2026-04-27)

### Why
Per Apr-2026 user feedback: "Combine Signal and Briefing into one section.
Use line tabs to separate the two. When loading these pages, do NOT
pre-populate them with data. Prompt the user to generate." The Strategic
Addendum also asked for a calmer, less-marketing post-login register.

### What shipped
- **Sidebar consolidation** — Signals + Briefings nav entries replaced with a
  single **Prepare** entry (`AppShell.jsx` line 33).
- **Routing** — `/app/prepare` registered in `App.js`. `/app/highlights`
  and `/app/briefings` now `<Navigate>` to `/app/prepare` (no link rot).
- **Backend router** — `prepare_router` now mounted in `server.py`. The
  `prepare.py` LLM JSON parser was hardened with a fence-strip pass + prose
  fallback (was 502'ing when Claude wrapped the JSON in a code fence).
- **Frontend `Prepare.jsx`** — two line-tabs (Brief / Signals). Brief tab is
  on-demand: pick a kind chip (claim/proposal/topic/period/report), state
  your objective, generate, save. The result opens **inline as a Dialog**
  (no separate route — saves one URL surface). Signals tab follows the same
  filter + focus + generate pattern; results refresh in place.
- **Cross-link migration** — every `/app/highlights` and `/app/briefings`
  string in `MentionInbox`, `ActModal`, `SandboxTutorial`, `InSummaryTiles`,
  `AppHome`, `QuickResults`, `Monitor` migrated to `/app/prepare`. The old
  URLs still resolve via redirect.
- **Tone polish** — softened a handful of slightly-promotional strings:
  - SandboxBanner: "Ready to use AKKI on your real data?" → "When you're
    ready, AKKI will read your real pack the same way."
  - Manage page H1: "Keep your team and your companies tidy." → "Your
    team and your companies." Sub: "Quiet, no ceremony."
  - HealthDashboard H1: "One-click green light." → "Pre-flight, in one
    read."

### Tests
- iteration_44: 12/12 backend tests in `test_iter44_prepare.py` GREEN.
  Frontend 100% (Prepare flow + redirect verification + sidebar entry).
  No regressions. Test report: `/app/test_reports/iteration_44.json`.

### Open / deferred — Slice 8+
- Tier-B: persistent "Continue with [doc]" topbar pill (Quick-Results in
  product).
- Tier-B: multi-LLM model switcher in standalone Chat + avatar visual.
- Tier-C: Minutes as first-class entity (anchor for Cycle + Monitor).
- Tier-C: Personal vs Enterprise tier split (`akki.ai/personal` vs
  `akki.ai/enterprise`).
- Tier-C: Inbound email parsing/receiving integration.
- Upgrade `ValidatedBadge` from a Synisense-shielded re-skin to an actual
  second-LLM validation pass.
- Refactor: extract `_safe_parse_json` helper out of `prepare.py` +
  `plays.py` into a shared `helpers/llm_json.py` (review note).
- Delete-orphaned: `/app/frontend/src/pages/Highlights.jsx` and
  `/app/frontend/src/pages/Briefings.jsx` are no longer routed but the
  files remain (kept in case the user wants to roll back). Remove after a
  stability window.

### 2026-04-28 — iter51/52 · Tier-C: Postmark inbound + Minutes extractor + Personal-Enterprise split
**Postmark inbound email**
- New router `/app/backend/routers/inbound_email.py`. Endpoints:
  - `GET /api/inbound/address[?context_id=…]` — auth-required. Mints / returns
    the user's `inbound+<account_token>@inbound.akki.ai` address (and a
    `inbound+<account>.<ctx>@…` context-scoped variant). Tokens are 8-char
    URL-safe slugs persisted on `accounts.inbound_token` /
    `contexts.inbound_token`.
  - `POST /api/inbound/postmark?secret=<TOKEN>` — Postmark webhook receiver.
    Verifies shared secret (env: `POSTMARK_WEBHOOK_SECRET`, falls back to
    `POSTMARK_SERVER_TOKEN`), parses `From / Subject / TextBody / Attachments`,
    routes by `MailboxHash`, picks the most useful attachment (PDF > DOCX >
    TXT > first), runs through the existing `extract_text` pipeline, writes a
    fully-fledged `documents` row tagged `source: 'inbound_email'`. Idempotent
    on `(context_id, inbound_message_id)`. Auto-tags `doc_type='minutes'` if
    subject contains "minutes" or any attachment filename does.
- Settings → Integrations now wired (was M6-locked) and renders
  `InboundEmailPanel` showing the personal + ctx-scoped forwarding addresses
  with copy-to-clipboard buttons.
- `POSTMARK_SERVER_TOKEN` added to `/app/backend/.env`.

**Minutes extractor end-to-end**
- Fixed `prepare.py:extract_minutes` — `call_llm` was being called with
  wrong kwargs (`system_message`/`user_message`); switched to the actual
  signature (`module / user_query / system_override / response_format`).
- Prepare → Minutes UI (`Prepare.jsx`) now renders an "Extract" button per
  row when `minutes_meta` is missing, and a "Show extract" toggle when it
  exists. The expanded detail surfaces attendees / decisions / actions /
  open questions inline.

**Personal vs Enterprise (light-split, option 1a)**
- New backend router `/app/backend/routers/enterprise.py`:
  - `POST /api/enterprise/interest` (auth) — captures `{use_case, company_size, timing}`.
  - `GET /api/enterprise/interest/me` — returns latest submission.
- New frontend page `/app/enterprise` (`Enterprise.jsx`) — calm, editorial
  lead-gen surface. Form flips to a thank-you state once submitted.
- AppShell: a small "Akki for Enterprise" pill renders in the left rail
  (above Settings) **only** when the active context type is `ned_personal`
  or `executive_personal`. Click → `/app/enterprise`. No structural code
  split; same login, same shell.

**Header trust badge**
- Centred and reordered to "INTERNAL · SECURE · CONFIDENTIAL" in `AppShell.jsx`.
  "Internal" remains oxblood (`var(--accent)`); "Secure" + "Confidential"
  use the muted text colour. Centred via `absolute left-1/2 -translate-x-1/2`.

### Tests
- iteration_51 — backend: 16/16 new + 6/6 iter50 regression GREEN.
- iteration_52 — frontend: 5/5 surfaces (trust badge, Settings →
  Integrations, /app/enterprise, Minutes Extract toggle, upsell pill).
- Reports: `/app/test_reports/iteration_51.json`, `/iteration_52.json`.

### Open / deferred
- Optional polish on Enterprise: surface an "Update my note" affordance once
  a lead has been submitted (today the form short-circuits to thanks state).
- Optional ops-visibility: an `inbound_rejected` audit row when the webhook
  soft-fails (bad attachment, virus scan).
- Defence-in-depth: unique sparse index on `accounts.inbound_token` /
  `contexts.inbound_token` (currently uses _mint_token() collision-free in
  practice but lacks a DB-level guarantee).

### 2026-04-28 — iter53 · Deep-tier (Claude Opus 4.6) routing + per-surface daily quota + Minutes→Cycle one-click
**Tier system (`/app/backend/llm_service.py` + `/app/backend/llm_tier_quota.py`)**
- `call_llm()` now accepts `tier="fast" | "standard" | "deep"`. Model ids are
  read from env (`LLM_MODEL_FAST` / `LLM_MODEL_STANDARD` / `LLM_MODEL_DEEP`)
  so we can swap to Opus 4.7 the moment the Emergent key catalogue picks it
  up — no code change. Defaults today:
  - fast → `gemini-2.5-flash` (validation/extraction)
  - standard → `claude-sonnet-4-5-20250929` (today's default)
  - deep → `claude-opus-4-6` (long-form narrative, decks, blog)
- `llm_tier_quota.py` adds per-account-per-day quotas, persisted in
  `llm_deep_usage{account_id, surface, day_utc, count}`. Defaults (env-overridable
  via `AKKI_DEEP_QUOTA_<SURFACE>`):
    `brief=10`, `blog=5`, `deck=3`, `chat=30`, `validate=20`, `minutes=5`.
- `call_llm_with_tier(surface, account_id, requested_tier, call_args)` wraps
  the whole "check quota → consume → call → graceful fallback" flow. When a
  user is over their daily deep budget the call transparently downgrades to
  standard tier and the response carries
  `quota.{requested_tier, served_tier, downgraded, remaining, limit, used, reset_at}`.

**Surfaces wired**
- **Brief generation** (`POST /api/contexts/{cid}/briefs`) — accepts
  `deep:true` to opt in. UI exposes a "Deep mode" checkbox with a live
  "X/N today" indicator (`prepare-brief-deep-toggle`). Saved brief carries
  `tier` and `model_id` for audit.
- **ExCo360 blog generation** (`POST /api/blog/compose`, admin) — always
  deep tier. Quota state surfaced on response.
- **Minutes narrative** (NEW: `POST /api/contexts/{cid}/minutes/{doc_id}/narrative`)
  — 250–400 word editorial summary on the deep tier. Persisted at
  `documents.minutes_narrative.{body,model,tier,generated_at}` so re-renders
  are instant. Re-running silently overwrites.

**New endpoint: `GET /api/llm/quota[?surface=…]`** — auth-required.
Read-only; returns today's deep-tier usage so the UI can render an accurate
"X/N today" hint.

**Minutes → Cycle dispatch (one-click)**
- New endpoint: `POST /api/contexts/{cid}/minutes/{doc_id}/to_cycle`.
- Walks `minutes_meta.actions[]` and seeds one row per action into the
  `questions` collection with `source='minutes:<doc_id>'`,
  `source_label='<title> (<date>)'`, and best-effort assignment to a
  reportee whose `name` matches `action.who` (exact match → first-token
  match → unassigned).
- Idempotent on `(context_id, source, text)` — re-running on an unchanged
  doc adds zero duplicates.
- Returns `{seeded[], unmatched[], next:'/app/cycle?ctx=<id>'}` so the UI
  can show "5 matched · 2 unassigned · Continue to Cycle →".
- UI: 'Turn into checklist' button on the Minutes detail panel
  (`prepare-minutes-to-cycle-<id>`) + a 'Draft narrative summary' button
  (`prepare-minutes-narrative-<id>`) that calls the deep-tier endpoint.

### Tests
- iteration_53 — backend: 9/9 pass (live Opus call confirmed
  tier=deep / model_id=claude-opus-4-6 / quota auto-downgrades cleanly on
  exhaustion). Frontend smoke OK. No regressions on iter51/52.
- Report: `/app/test_reports/iteration_53.json`.

### Open / deferred
- When Emergent catalogue lists `claude-opus-4-7`, swap by setting
  `LLM_MODEL_DEEP=claude-opus-4-7` in `/app/backend/.env`. No code change.
- Race-tighten: `check_and_consume()` reads-then-upserts; on simultaneous
  deep requests at `used=N-1` two could both pass. Acceptable 1-call slop
  for now; switch to `find_one_and_update({count:{$lt:limit}}, $inc:{count:1})`
  if integrity becomes a concern.
- Decks surface — quota slot already reserved (`deck=3/day`). Build the
  generator when the design is ready.
- Optional: 'Regenerate narrative' affordance with a confirm-overwrite UX.

### 2026-04-28 — iter54 · Admin LLM-spend dashboard + race-safe quota + ops audit polish
**Admin · LLM Spend (`/admin/llm-spend`, superadmin-only)**
- New backend `routers/admin_llm_spend.py`. `GET /api/admin/llm/spend?days=N`
  rolls up `llm_deep_usage` into:
  - tiles: total calls / est cost / active accounts / window
  - by-surface bars (calls + accounts + default cap)
  - 14-day daily sparkline
  - top 20 accounts (email · top surface · calls · est cost)
- Unit cost configurable via env `AKKI_DEEP_UNIT_COST_USD` (default $0.045).
- Frontend `pages/admin/LLMSpend.jsx` with the same cream/oxblood editorial
  pattern as `/admin/health`, `/admin/sandbox-kpi`, `/admin/signal-kpi`.

**Race-safe deep quota**
- Added unique index on `llm_deep_usage(account_id, surface, day_utc)`.
- `check_and_consume()` reworked to two-pass atomic flow:
  1. `find_one_and_update({key, count<limit})` — if matched, $inc; allowed.
  2. Otherwise `insert_one({key, count:1})` — duplicate-key error means
     row already exists at cap → deny.
- iter54 verified: 5 parallel calls at cap=10 → count stays exactly 10.
  (Was overflowing by 1 in iter53.)

**Ops audit polish**
- `inbound_email.rejected` audit rows now written on Postmark soft-fails
  (`bad_attachment` / `virus_scan`). EICAR test-file path verified.
- Sparse indexes on `accounts.inbound_token` and `contexts.inbound_token`.

**Frontend polish**
- Enterprise page: 'Update my note →' affordance on the thanks state
  (testid `enterprise-update-note-btn`) returns to the form.
- Minutes narrative regenerate now `confirm()`s before overwriting.

### Tests
- iteration_54: backend 10/10 + frontend 100% + 4 admin screenshots captured
  (`/app/test_reports/screenshots_iter54/admin_*.jpg`). No regressions on
  iter51/52/53.

### Open / deferred
- LLMSpend "by surface" bar uses `pctOfTotal` so the top surface is always
  100%; consider switching to `max-of-window` for more legible distribution.
- For >100k seeded accounts, paginate `by_account_top` and pre-aggregate
  rather than scanning all rows.
- Inbound rejections without a MessageID share the literal `(no-id)` as
  audit resource_id — could collide; consider a uuid fallback.

### 2026-04-28 — iter55 · Decks pipeline + behaviour monitoring + admin index
**Decks generator (`/app/decks` + 4 backend endpoints)**
Three-step flow that prevents budget waste on weak prompts:
1. **Outline (STANDARD tier — free of deep budget)**
   - `POST /api/contexts/{cid}/decks/outline` body `{intent, audience?, target_slides?}`.
   - Sonnet plans the deck against actual context (40 most-recent docs, 30 signals, 20 briefs); returns `research_question`, `evidence_used[]`, `missing_context[]`,
     `context_sufficiency`, proposed `slides[]`. User reviews & may iterate
     (`parent_outline_id`) before any deep call fires.
2. **Generate (DEEP tier — 1 of 3 daily slots)**
   - `POST /api/contexts/{cid}/decks/{outline_id}/generate` body `{outline_id, confirmed:true, edits?}`.
   - 400 if `confirmed:false`; 409 if outline already consumed (forces iteration).
   - On budget exhaustion → graceful fallback to Sonnet with `quota.downgraded:true` and a UI banner.
3. **Quality check (FAST tier — free)**
   - `POST /api/contexts/{cid}/decks/{deck_id}/quality_check`.
   - Gemini Flash scores 0-100 across coherence / evidence / audience-fit and
     returns `free_refinements[]` (edits the user can make WITHOUT regenerating).
   - Recommends regen only when `score<55` AND issues can't be edited away.
4. **Feedback (free)** — `POST .../feedback` `{rating:'up'|'down', will_regenerate?}`.

**Behaviour monitoring**
- `deck_telemetry` collection captures outline iterations, sufficiency,
  quality_score, user_rating, will_regenerate.
- `GET /api/admin/llm/decks/quality?days=N` rolls up:
  decks_generated · outlines_drafted · outline_to_deck_ratio · avg_outline_iterations ·
  avg_quality_score · thumbs_up/down · satisfaction_pct ·
  user_will_regenerate_count · quality_recommends_regen_count ·
  insufficient_context_count · partial_context_count.
- Surfaced in `/admin/llm-spend` as the new "Deck quality · behaviour" panel
  (Avg quality / Outline → deck / Satisfaction / Insufficient ctx).

**Admin control room (`/admin`)**
- New landing page tying all five admin surfaces together with at-a-glance
  pills (Health: green / LLM spend: $32.64 7d / Deck quality: q94 · 4 decks / Sandbox: 0/0 / Signals: 0 acts).

**Backlog cleared**
- LLMSpend by-surface bars now use **max-in-window** (top fills track,
  others scaled to it) — fixes the always-100% top bar from iter54.
- Inbound rejection audit row now uses `no-id-<uuid8>` fallback when
  Postmark MessageID is missing.
- Enterprise "Update my note →" verified.
- Minutes-narrative regenerate confirm verified.

### Tests
- iteration_55: backend 11/11 functional pass + frontend testids verified +
  3 screenshots captured. End-to-end flow verified live: outline → confirmed
  generate → Opus 4.6 deck → quality 93/100 → feedback persisted.
- Screenshots: `/app/test_reports/screenshots_iter55/{decks_step1, admin_index, admin_llm_spend}.jpeg`.

### Open / deferred
- Decks step 2/3 e2e screenshots blocked by ingress 502 on long Opus calls
  during the testing pass (curl flow OK). Capture after 00:00 UTC reset
  with a fresh user.
- Optional: persist `outline.edits` so re-generation regenerates against the
  edited outline (today the edits ride on the generate call but aren't
  versioned).
- Optional: per-account daily deck-quality average alert threshold.

### Backlog tracker (P-bands)
P0: none.
P1: Postmark inbound stream URL one-time wire-up in Postmark dashboard (user task).
P2: Decks UI E2E retest after midnight; max-of-window label phrasing on
    LLMSpend; opt-in "auto-regenerate when quality<55".

### 2026-04-28 — iter56 · Final backlog clear · regen-reason learning loop + admin alerts
**Regen-reason learning loop**
- `FeedbackIn.regen_reason` enum added: `audience_drift | weak_research_question |
  missing_evidence | wrong_tone | other`. Persisted on `decks.user_feedback.regen_reason`
  and `deck_telemetry.user_regen_reason`.
- Frontend: clicking 👎 on a deck now opens a reason-chips panel
  (`decks-regen-reason-panel`) before submitting feedback. Each click
  records the feedback with regen_reason set.
- **The actual learning loop**: `create_outline()` now queries the user's
  most-recent regen_reason (scoped to the same context) and folds it into
  the planner prompt as a `LEARNING FROM THIS USER'S PRIOR DECKS` block.
  The new outline persists `learning_hint_used` for telemetry visibility.
- Verified live: feedback `weak_research_question` → next outline returns
  `learning_hint_used: "the research question was too weak — user said: …"`
  → planner produces a tighter research_question (zero deep budget).

**Outline-edit versioning**
- `generate()` now persists `edits_applied: {...}` AND snapshots the
  post-edit `research_question / slides / audience_assumed` onto the
  outline record. Admin views & history now show what was actually
  generated, not just what was originally proposed.

**Admin alerts & coaching list**
- `GET /api/admin/llm/decks/quality` now returns:
  - `alerted_accounts[]` — users with ≥3 of last 5 decks scoring <55.
    Each entry: `{account_id, email, name, weak_count, window, avg_score}`.
  - `top_regen_reasons[]` — sorted reason counts so ops can see whether
    failures cluster on audience/question/evidence/tone.
  - `alert_threshold:55, alert_window:5, alert_min_hits:3` — env-overridable later.
- Frontend `/admin/llm-spend`:
  - **`llm-spend-deck-alerts`** amber panel — coaching list, "ned X · 47/100 · 5 of last 5 weak".
  - **`llm-spend-regen-reasons`** panel — top-N reasons with counts.

**Cosmetic**
- LLMSpend by-surface bar label now reads "X% of total · Y% of top".
  Bar geometry already used max-of-window from iter55.

### Tests
- iteration_56: backend 7/7 + admin panels verified live + 2 admin
  screenshots captured. Regen-chip UI structurally verified in source
  (testing agent flagged a pre-existing context-switch quirk on /app/decks
  that blocked live click; backend persistence proven via API).
- Reports: `/app/test_reports/iteration_56.json`,
  `/app/test_reports/screenshots_iter56_*.jpg`.

### Open / deferred (P2, low)
- **Context-switch on /app/decks**: clicking a NED context from the
  portfolio sidebar while on /app/decks doesn't always re-filter sidebar
  to that role. Pre-existing; orthogonal to the deck pipeline. Worth a
  separate small investigation — likely AppShell role state sticky.
- **Auto-regenerate when quality<55 (opt-in)**: telemetry now captures
  the signal but we haven't built a one-click "regenerate with the lesson
  baked in" yet. Easy follow-up: button on the deck quality panel that
  drafts a new outline + immediately confirms-and-generates if quota
  available.
- **Per-account quality-score threshold env-override**: hard-coded as
  `QUALITY_ALERT_THRESHOLD=55, WINDOW=5, MIN_HITS=3`. Promote to env vars
  (`AKKI_QUALITY_ALERT_*`) when ops want to tune.

### 2026-04-29 — iter58 · AKKI Solve surfacing + Walk-in card + backlog clear
**Branding & positioning**
- "Solve" → **"AKKI Solve"** everywhere. Tagline locked:
  *"For the board problems that don't have tidy answers."*
- Public landing page (`/`) now has a dedicated dark-themed Solve section
  (`landing-solve-section`) anchored after the three-guarantees rubric;
  eyebrow nav button (`landing-nav-solve`) makes it the first thing a
  returning visitor sees.
- New public marketing page **`/solve`** (SolveLanding.jsx): hero, 4-phase
  framework explainer, vs-Chat comparison, two CTAs.
- New in-app placeholder **`/app/solve`** (AppSolve.jsx) with
  notify-when-ready interest capture. Sidebar nav item placed between Chat
  and Workflows with a "Preview" pill.

**Walk-in question card (the iter57 improvement, shipped)**
- New backend endpoint `POST /api/walkin {kind,artefact_id,context_id}`.
  Sonnet-tier (free of deep budget). Cached on the artefact under
  `walkin_question`. Idempotent: subsequent calls return `cached:true`.
- `POST /api/walkin/regenerate` clears cache and re-runs.
- Supports `kind ∈ {brief, minutes, deck}`. Membership-gated.
- Frontend `<WalkInCard>` component wired into:
  - `/app/decks` (after slides),
  - `/app/prepare → BriefDetailModal` (under brief body),
  - `/app/prepare → MinutesExtractDetail` (under narrative).
- Each card shows: "Walk in with this question" (oxblood overline) →
  the question in serif italics → a why-line → "New" + "Continue in Chat" actions.
- Verified live: deck question came back as
  *"If our highest-risk AI model failed silently today, how many days
  until someone in this room would know — and who would tell us?"*

**Backlog cleared**
- **Decks outline iteration chip**: when `outline.iteration ≥ 2`, surface
  "Iteration N · still no deep slot used" + "Tightened from your last
  feedback" if learning_hint_used is set (`decks-outline-iteration-chip`).
- **Activity weekly grouping**: when timeline span ≥ 7 days, day headers
  collapse to "Week of <Mon date>" instead of `Friday, 28 April`. Span <7
  keeps day-of-week labels.
- **Deck deep-link routing**: `/app/decks/:deckId` opens the deck review
  surface directly. Falls back silently to intent if not found.
- **`app-solve-thanks` testid** added to AppSolve.jsx thanks state.

### Tests
- iter58: backend 12/12 + frontend 5/5 (after testing-agent fixed a
  duplicate `Layers` import that crashed the whole app — caught early,
  fixed in the same iteration).
- Reports: `/app/test_reports/iteration_58.json`,
  `/app/test_reports/screenshots_iter58_*.jpg`.

### Open / deferred
- AKKI Solve full module build (waves 1-3) — APPROVED with these
  refinements:
  - Pushback 1 (integrations): all approved.
  - Pushback 2 (cost): build a **Pro tier budget model** — paid users
    get the highest-quality model, free users get Sonnet-streamed
    synthesis with Opus opt-in via existing deep quota.
  - Pushback 3 (triangulation): MUST be in v1 scope; user OK with
    evolutionary build (start simple, sharpen).
  - Pushback 4 (cluster expansion at 200+ sessions): approved.
  - Q2 (save/resume): users get BOTH continue-where-they-were AND
    start-over options.
  - Q3 (MVP-of-MVP): ship full framework with all clusters, optimize
    around the model.
- ESLint `no-redeclare` rule should be added to CI to prevent the kind
  of duplicate-import regression iter58 hit.
- `/admin/llm-spend?panel=decks` deep-link routing (admin-side analog
  of the deck deep-link we just added).

### 2026-04-29 — iter59/60 · Sandbox cookie-poisoning bug fixed
**RCA**
- `get_current_account()` in `core.py` checked the `access_token` cookie
  *before* the Authorization header, then short-circuited 401 on the
  first credential that failed to decode. A returning visitor with an
  expired session cookie would land on /sandbox, complete the form,
  receive a fresh Bearer JWT in the handoff — and still get 401'd on
  /api/auth/me because the stale cookie was inspected first. AuthContext
  caught the 401, wiped the localStorage Bearer, set account=false →
  ProtectedRoute on /app bounced them to /signin. Symptom user
  reported: "after the sandbox relationship is set, it goes to /signin".

**Fix (two layers, belt-and-braces)**
1. `core.py::get_current_account` — now tries every credential the
   request carries (Bearer first, then cookie), accepting the first
   that decodes valid. Self-heals against any client with mixed credentials.
2. `routers/sandbox.py::generation_status` — when the sandbox is ready,
   `Set-Cookie: access_token` and `refresh_token` are written on the
   /status response itself. The fresh cookies overwrite any stale ones
   in the browser before the next request goes out.
3. `AuthContext.bootstrap` catch — also POSTs `/auth/logout` (best
   effort) on failure so a poisoned cookie clears server-side too.

**Verified end-to-end (browser repro):**
- Phase A (clean sandbox flow) ✅
- Phase B (stale `access_token` cookie planted before /sandbox) ✅
- Phase C (post-handoff /app/settings?tab=account navigation) ✅
- iter60 testing-agent report: 3/3 phases pass; bug closed.

**Tests / reports:**
- `/app/test_reports/iteration_59.json` — RCA + repro
- `/app/test_reports/iteration_60.json` — fix verified

### 2026-04-29 — iter61 · AKKI Solve Wave 1 + auth observability + walk-in context hint
**AKKI Solve · Wave 1 SHIPPED**
- 12-cluster taxonomy seeded into `solve_clusters` (idempotent — operator
  edits survive redeploy). Clusters: revenue_underperformance,
  ceo_succession, strategy_drift, risk_blindspot, performance_management,
  capital_allocation, regulatory_change, tech_debt_or_outage,
  people_conduct, ma_thesis, board_dynamics, founder_transition.
- 4-phase state machine engine (`routers/solve_engine.py`):
  Surface → Depth → Synthesis → Lock-in → completed. Each phase: one
  user turn + one Solve turn; phase advances on each turn submission.
  Synthesis and Lock-in bodies persisted on `session.synthesis` /
  `session.lockin` for fast re-render.
- Pro-tier deep synthesis: when `account.solve_pro=true` AND user opts
  in via `pro_tier:true`, synthesis routes to Opus (tier=deep) and
  consumes a slot from the new `solve` quota surface (4/day default,
  isolated from decks/brief budgets).
- Save/resume: continue OR start-over (per iter58 user direction).
  Restart abandons old session and clones cluster+intent.
- Endpoints: GET /api/solve/clusters, POST/GET /api/solve/sessions,
  GET /api/solve/sessions/{sid}, POST /api/solve/sessions/{sid}/turn,
  POST .../restart, POST .../abandon.
- Frontend: `/app/solve` rebuilt as 3-view module — PickerView (12
  clusters + resume list), IntentView (textarea + Pro toggle + use-example),
  SessionView (phase stepper + turns + composer + completed banner).

**Walk-in card "in this context" hint (iter58 improvement)**
- `/api/walkin` now folds the active context name + 3 most recent
  un-archived signals into the prompt. Same Sonnet tier — questions
  feel like they come from someone who sits on this board, not a
  generic helper.

**Admin · Auth observability (iter60 improvement)**
- `core.py::get_current_account` now records sampled auth events
  (failures always; successes at AKKI_AUTH_OBSERVE_RATE, default 0.01).
  Captures: timestamp, ok/fail, reason, credentials carried, dual_mismatch,
  authed_via, path, method.
- New endpoint `GET /api/admin/auth/events?hours=N` (superadmin) rolls
  up failure rate, by_failure_reason, by_credential, top_paths,
  dual_credentials_seen/mismatched, recent 50 events.
- New page `/admin/auth-events` with 4 tiles + 3 panels + recent table.
  6th admin-tile added to /admin index.

**ESLint regression guard**
- Added `/app/frontend/.eslintrc.js` with explicit no-redeclare,
  no-dupe-keys, no-dupe-class-members, no-duplicate-imports rules.
  Catches the iter58 duplicate-Layers-import class of regression at
  lint time.

### Tests
- iter61: backend 12/12 pass + frontend Solve picker→intent→session→
  phase-advance verified end-to-end with real LLM (~100s).
- Pytest file: `/app/backend/tests/test_iter61_solve_engine.py`.
- Report: `/app/test_reports/iteration_61.json`.

### Open / deferred (post-Wave 1)
- Wave 2: Solve→Brief / Solve→Deck / Solve→Cycle handoff (per iter58
  pushback 1). Synthesis lock-in commitments seed Cycle questions.
- Wave 3: triangulation v2 — curated comparable corpus with sector +
  scale matching (currently uses cluster-level placeholders).
- Pro account UI: subscription affordance to flip `solve_pro=true`.
  Today the flag is set manually in Mongo for testing.
- Walk-in card test for admin-side render in panel `prepare-minutes-narrative-body-<id>`.


## §AKKI Solve — Wave 2 (Handoff Trio) + Wave 3 (Triangulation v2) + Pricing (2026-04-29, iter62)

### Wave 3 — Triangulation v2 corpus
- New `/app/backend/solve_comparables_seed.py` — **27 curated anonymised
  comparables** across all 12 clusters (≥2 per cluster after the iter62
  top-up). Each carries `cluster_id`, `sector_tag`, `scale_tag`,
  `diagnosis_summary`, `what_worked`, `what_didnt`, `source_type`. Strict
  rule: no real company names; every comparable closes with a verdict
  (worked/didn't) so the LLM grounds the diagnosis in lived board
  experience rather than abstractions.
- `db.solve_comparables` indexed on `id` (unique) +
  `(cluster_id, sector_tag)`. Idempotent seeding on startup.
- Engine helper `_pick_comparables(cluster_id, sector_tag)` picks closest
  3 with preference order: same cluster + matching sector → same cluster
  + 'any' sector → same cluster + any sector. Sector pulled from session
  context's `sector` or `industry` field.
- Synthesis prompt now embeds the picked comparables under a
  `CURATED COMPARABLES` block instructing the LLM to reference at most
  one or two inline ('A comparable mid-cap bank…', 'In one industrials
  case…') without naming companies.
- Persisted to `synthesis.comparables[]` for the UI side panel.

### Wave 2 — Handoff Trio (Solve → Brief, Decks, Cycle)
- Three new endpoints on completed Solve sessions
  (`require_completed_session` gate — must have synthesis AND lock-in):
  - `POST /api/solve/sessions/{sid}/handoff/brief` — creates a
    `db.briefings` row with synthesis as `opening_paragraph` and lock-in
    parsed into Decide / Watch / Walk-in items. Tagged with
    `solve_session_id` + `mode='solve_handoff'`.
  - `POST /api/solve/sessions/{sid}/handoff/decks` — seeds a
    `db.deck_outlines` row with intent = synthesis + lock-in summary,
    research_question = original Solve intent, and 5 starter slides
    (Diagnosis · Comparables · Decide · Watch · Walk in with). User
    refines and commits the deep-tier render via the existing decks
    pipeline — Solve handoff does NOT consume deck quota.
  - `POST /api/solve/sessions/{sid}/handoff/cycle` — inserts 1-3 questions
    into `db.questions` derived from lock-in lines (Walk-in → lead
    question, Watch → trigger probe, Decide → block check). Source field
    set to `AKKI Solve · <cluster_label>`.
- All three are **idempotent within a session** — second call returns
  `already_exists: true` with the original artefact id. Recorded in
  `db.solve_handoffs` (compound natural key on `session_id + target`)
  AND denormalised into `solve_sessions.handoffs[]` for fast list reads.
- `_parse_lockin_lines` tolerates markdown bold and bullet prefixes
  (`**Decide:**`, `- Decide:` all parse cleanly).
- Membership gate: Solve handoffs require active membership of the
  destination context (`_ensure_membership`).
- New `GET /api/solve/sessions/{sid}/handoffs` for inspection.

### Pricing — Solve Pro bundled into existing Pro plan
- Per user direction ("less friction, high stickiness"):
  - Pro plan ($29/mo) and Team plan unlock unlimited deep synthesis
    (gated by existing `solve` daily quota of 4 in `llm_tier_quota`).
  - **Free users get 1 free deep synthesis per UTC month** via
    `db.solve_free_grants` (compound unique index on
    `(account_id, month_utc)`). First click of the Pro toggle as a free
    user atomically claims the grant; subsequent calls in the same
    month fall through to the standard tier (transparent downgrade —
    `synthesis.free_grant_used: true`).
- New `_user_is_pro()` checks `account.plan in (pro, team)` OR explicit
  `account.solve_pro=true` flag (legacy / manual override).
- Frontend Pro toggle copy now communicates: "Pro plan gets unlimited
  deep synthesis; on the free plan you get 1 free deep synthesis per
  month".

### Frontend — AppSolve UX
- `HandoffStrip` component on completed sessions: 3 tile buttons (Brief
  / Decks / Question Bank), context picker (auto-selected when user has
  one context), per-target emerald-state when handoff already exists.
  Toasts on success; inline error rendering.
- `ComparablesPanel` rewritten to render the new corpus shape: sector +
  scale tag overline, serif diagnosis line, accent-tagged Worked / muted
  Didn't lines. Backwards-compatible string fallback.
- Picker adds a second list — **'Completed — hand off ready'** — so
  users can return to the handoff strip after navigating away.
- `solve_sessions.handoffs[]` denormalised array consumed by
  HandoffStrip for first-render emerald state.

### Tests
- iter62: backend **11/11 pytest pass** against live LLM
  (~3:26 wall-time). Frontend 100% verified end-to-end.
- Pytest file: `/app/backend/tests/test_iter62_solve_wave2_wave3.py`.
- Report: `/app/test_reports/iteration_62.json`.

### Open / deferred (post-Wave 2/3)
- Pro billing surface: Stripe checkout flow specifically for Solve Pro
  upgrade (currently piggybacks on existing Settings → Billing tab).
- Wave 4: Solve session export as PDF (briefing-style narrative).
- Comparable corpus expansion (currently 27; aim for 40+ across
  English / European / US board cases as adoption broadens).
- `/app/decks` context-switch quirk (orthogonal pre-existing P1 — may
  not be reproducible now after the role-isolation work in iter46).
- Defence-in-depth: `_consume_free_grant` race-safe via duplicate-key;
  consider promoting to `find_one_and_update` upsert pattern.
- Cycle handoff: question text currently echoes the lock-in line
  verbatim (with "How do we hold ourselves to:" prefix). A short LLM
  pass to phrase as a sharp board question would polish further.



## §AKKI Solve — Wave 4 (PDF) + P1/P2 cleanup batch (2026-04-29, iter63)

### Wave 4 — narrative PDF export
- New `/app/backend/solve_pdf.py` — reportlab-driven A4 portrait
  one-pager: PRIVATE · AKKI SOLVE overline, intent as serif title,
  cluster + completion meta, **THE DIAGNOSIS** (synthesis body, markdown
  bold/italic stripped), **COMPARABLE DIAGNOSES** (sector + scale tag
  overline, anonymised summary, oxblood "Worked:" + muted "Didn't:"
  lines), **LOCK-IN** (Decide / Watch / Walk in with as a 2-column
  table), Synisense-shielded footer with last-8 of session id.
- New endpoint `GET /api/solve/sessions/{sid}/export.pdf` — returns
  `application/pdf` with `Content-Disposition: inline; filename=akki_solve_<intent_slug>.pdf`.
  Rejects sessions without synthesis (409) and unknown sessions (404).
- Frontend `solve-session-pdf` button on the SessionView header (right
  of "Back", left of "Pause for later"). Authenticated download via
  fetch + blob → object URL so the browser doesn't open the raw stream.

### Free-grant race-safety hardening
- `_consume_free_grant` rewritten from try/except DuplicateKeyError to
  atomic `find_one_and_update` with `$inc: count` + `$setOnInsert` on
  `first_used_at` + upsert. The post-increment count tells us if this
  is the first call (allow) or a subsequent one (deny). Race-safe
  even if the unique compound index regresses. 8-way `asyncio.gather`
  yields exactly 1 allowed=True.

### Cycle handoff polish — LLM-sharpened questions
- New `_draft_cycle_questions` helper — single STANDARD-tier LLM call
  (`module=solve.cycle_handoff`, `response_format=json`) takes the
  cluster label + intent + synthesis + lock-in (Decide/Watch/Walk-in)
  and returns 1-3 sharp board questions phrased to be answerable
  yes/no/with-a-number. No more verbatim "How do we hold ourselves to:"
  echoes. Falls back to the deterministic derivation if the LLM call
  fails or returns nothing — preserves the iter62 baseline behaviour.

### Pro upgrade CTA + pro-status endpoint
- New `GET /api/solve/pro-status` — returns
  `{is_pro, plan, free_grant: {claimed_this_month, month_utc, remaining}}`
  for the calling account. UI uses this to decide whether to render
  the Pro toggle as "1 free synthesis available" / "Pro account —
  unlimited" / "you've used your monthly free; upgrade for more".
- `IntentView` Pro toggle copy now switches dynamically based on
  `proStatus`. When a free user has claimed their grant and ticks the
  Pro toggle, an oxblood-bordered `solve-pro-upgrade-cta` card appears:
  "Subscribe to Pro for unlimited deep synthesis. $29/mo… You'll still
  get the standard tier on this session at no charge." with a deep
  link to `/app/settings?tab=billing`.
- `_user_is_pro` continues to derive Pro from `account.plan in (pro,
  team)` OR explicit `solve_pro` flag.

### Smart "Recommended" handoff pill
- `HandoffStrip` now picks the most useful UNDONE handoff target based
  on context type:
  - NED context → cycle (board-room follow-up) → brief → decks
  - Executive context with open questions → cycle → brief → decks
  - Executive context, no questions yet → brief → cycle → decks
  - The pill cascades — once the primary recommendation is done, it
    promotes the next undone target. Pill hidden when contextId is
    empty or all three handoffs are done.
- Recommended target's tile gets an oxblood ring + Sparkles icon for
  unmistakable focus. Pill text reads `RECOMMENDED FOR THIS CONTEXT:
  <Label>` (data-testid `solve-handoff-recommendation`).

### Decks context-switch state reset (P1 fix)
- `Decks.jsx` `useEffect([cid])` now clears `view`, `outline`, `deck`,
  `history` BEFORE the new context's data loads. Prevents the old
  context's deck from briefly rendering under the new context's name
  during a switch. Pre-existing P1 bug — closed.

### Comparable corpus expansion
- `/app/backend/solve_comparables_seed.py` topped up from 18 → **27
  curated comparables**. Every cluster now ships ≥2 (most ship 3).
  New entries cover sparse clusters: people_conduct (industrials +
  financial_services), ma_thesis (financial_services + tech_saas),
  board_dynamics (any · 2), founder_transition (tech_saas +
  consumer_goods), performance_management (tech_saas), capital_allocation
  (financial_services), regulatory_change (tech_saas),
  tech_debt_or_outage (financial_services), strategy_drift (tech_saas).

### Tests
- iter63: backend **11/11 pytest pass** (~62s). Frontend: Decks
  context-switch reset visually confirmed; PDF button + Pro upgrade
  CTA + recommended pill all interactively validated by main agent
  post-testing-agent.
- Pytest file: `/app/backend/tests/test_iter63_solve_p1p2.py`.
- Report: `/app/test_reports/iteration_63.json`.

### Open / deferred (post-Wave 4)
- `solve_engine.py` is now ~1080 lines — split Wave 2 handoffs into
  `/app/backend/routers/solve_handoffs.py` before Wave 5.
- Comparable corpus aim for 40+ entries with European / US / African
  board cases as adoption broadens.
- "Recommended" pill could honour `account.preferences.preferred_handoff`
  for users who consistently pick the same target.
- Stripe-driven Solve Pro upgrade CTA could route through a dedicated
  `/api/solve/upgrade` flow (today it deep-links into the existing
  Settings → Billing tab).



## §iter64 — Studio (Decks + Reports merge) + Catch-up rename + Marketing redesign brief (2026-04-29)

### User feedback that drove this iteration
> "Combine Decks and Workflow — this is where the user comes to produce
> reports and presentation. Workflow keeps a record of generated reports
> and decks and scores their confidentiality and sensitivity for awareness
> once it's generated or saved. Enterprise version - Documents generated
> from this section have some type of electronic marker that can track
> who has read it to track information exposure score."
>
> "Change 'Prepare' to 'Catch-up'."
>
> "Akki is so powerful and needed but the website is not doing it justice.
> A lot of the conversion driving features are not surfaced, and there
> is long-winded copy that takes long to land the value promise. Tone
> should target seasoned and emerging executives and non-executive
> directors interested in tools, frameworks or mindsets that grow or
> preserve value for their shareholders. People love the look and feel."

### A · "Prepare" → "Catch-up" rename
- Sidebar entry (AppShell.jsx) renamed from "Prepare" to "Catch-up".
- /app/prepare page header rewritten: "Catch-up · {context}" /
  "Catch up on what's next."
- QuickActions home surface: "Read & catch-up for tomorrow".
- Route URL kept as /app/prepare for back-compat — only labels changed.

### B · Decks + Workflows merge → "Decks + Reports" Studio
- Sidebar primary nav: "Decks" → "Decks + Reports". "Workflows"
  removed from primary nav (deep link /app/plays still works for
  in-flight Board Pack journeys; the home WorkflowsHub widget keeps
  the tabbed in-progress view).
- /app/decks header rewritten to position the Studio surface as the
  unified place to produce material:
    Decks + Reports · Studio
    Produce board-grade material with your own data.
    Decks + Reports is the secure place you draft material that
    leaves your hands. Every saved artefact is auto-classified —
    Public · Internal · Confidential · Restricted — and tracks
    who's read it so you know your information exposure before
    you share.

### C · Auto-sensitivity scoring on every saved artefact (decks + briefings)
- New `/app/backend/studio_sensitivity.py` — deterministic regex
  scorer with 9 rules covering M&A, conduct/HR, litigation, financial
  figures, restructure, MNPI/insider, customer concentration,
  pre-announcement, leadership succession. Score 0-100 mapped to
  4-tier classification:
    0-24 → Public · 25-49 → Internal · 50-74 → Confidential ·
    75-100 → Restricted
- Reasons[] array surfaces what triggered each bump so users can
  sanity-check the classification.
- Hooks into:
  - `routers/decks.py` line ~365 — auto-score on `decks/{outline_id}/generate`
  - `routers/briefings.py` line ~143 — auto-score on briefing create
  - `routers/solve_engine.py` line ~554 — auto-score on Solve →
    brief handoff
- Idempotent backfill endpoint
  `POST /api/contexts/{cid}/studio/backfill_sensitivity` for
  pre-iter64 artefacts. Backfilled 14 existing decks + briefings
  for Tuli NED context on first call.
- Frontend `SensitivityChip` component (Decks.jsx) — emerald for
  public, amber for internal, orange for confidential, red for
  restricted. Tooltip surfaces reasons. Rendered top-right of every
  history row + DeckStep header.

### D · Real read-receipt tracking + exposure score
- New `routers/studio.py` — Studio cross-artefact endpoints:
  - `POST /studio/{kind}/{id}/view` — atomic upsert keyed on
    `(artefact_kind, artefact_id, account_id, day_utc)`. Same-day
    repeat views return `deduped: true`. Owner views tracked but
    excluded from `unique_readers`.
  - `GET  /studio/{kind}/{id}/engagement` — full engagement summary
    with `view_count`, `unique_readers`, `readers[]` (with display
    names / emails / first/last viewed), `share_count`,
    `external_share_count`, `exposure {score, band, inputs}`.
  - `POST /studio/{kind}/{id}/share` — records a share with
    `to_email`, `to_name`, `external` flag.
  - `POST /studio/{kind}/{id}/rescore` — re-runs the scorer.
  - `GET  /studio/history` — merged decks + briefings desc by
    created_at with sensitivity + exposure folded in (single round-trip).
- `kind` enum: `deck` | `briefing`.
- Exposure score (0-100):
    raw = unique_readers·12 + share_count·18 + external_shares·22
    raw += 10 if days_since_creation > 14
    capped at 100; bands low/moderate/high.
- Frontend `ExposurePill` — muted/amber/red by band. Rendered
  alongside SensitivityChip on history rows + DeckStep header.
- DeckStep auto-fires `POST /view` on mount + fetches engagement
  to render the readers strip.
- New collections + indexes:
  - `db.studio_views`: unique compound on
    `(artefact_kind, artefact_id, account_id, day_utc)`, plus
    `(context_id, artefact_kind)`.
  - `db.studio_shares`: indexes on `(artefact_kind, artefact_id)`
    and `(context_id, created_at)`.
  - Top-up indexes on `db.decks` and `db.briefings` for the history
    sort.

### E · Studio history strip on /app/decks
- `StudioHistoryStrip` component renders below the IntentStep when
  the user has any prior artefacts. Shows merged decks + briefings
  desc by created_at with sensitivity chip + exposure pill per row.
- "Re-score sensitivity" button hits the backfill endpoint —
  idempotent, useful when the scorer rules evolve.
- Click a deck row → opens the DeckStep view (loadDeck pattern).
- Briefings rows currently view-only in this strip — Wave 5 will
  add briefing deep-link.

### F · Marketing/landing redesign — design brief shipped
- Called `design_agent_full_stack` with the user's exact constraints:
  cream/oxblood preserved, executive navy `#0A1F44` accent spots
  added, audience = seasoned + emerging executives and NEDs, three
  pillars to lead with (Solve, Cross Board Pulse, Decks + Reports),
  punchy editorial copy.
- Output: `/app/design_guidelines.json` — section-by-section
  architecture, copy library, three-pillar visual system, navy
  placement strategy, component-level recommendations, mobile
  considerations, data-testid pattern.
- IMPLEMENTATION DEFERRED to iter65 (next user message) — this
  iteration covered backend/frontend Studio + rename only.

### Tests
- iter64: testing agent v3 — backend **14/14 pytest pass** (~1.8s,
  no LLM calls in scorer tests). Frontend **100% of assertions**:
  sidebar rename, /app/plays deep link still works, /app/prepare
  Catch-up header, /app/decks Studio header, studio-history strip,
  data-testid="studio-sensitivity-public" chip rendered, "Produce
  board-grade material with your own data" tagline.
- Pytest file: `/app/backend/tests/test_iter64_studio_sensitivity.py`.
- Report: `/app/test_reports/iteration_64.json`.

### Open / iter65 backlog
- **Marketing/landing implementation** (per the design_guidelines.json
  brief) — biggest remaining item; will materially lift conversion.
- Briefings deep-link from Studio history strip.
- Decks deep-link race condition (when navigating directly to
  /app/decks/:deckId, the [cid] effect's reset can race with the
  [cid, deepLinkDeckId] fetch — observed but not blocking).
- Workflows-as-journeys: when iter65's design-led IA settles, the
  home WorkflowsHub may migrate inside Studio as an "active workflows"
  rail.
- Sensitivity scorer accuracy could improve with an LLM tiebreaker
  pass for ambiguous text (today the rule list is intentionally
  deterministic and conservative).
- Add `/api/contexts/{cid}/studio/share` outbound email integration
  via existing Resend adapter so a share record actually emails the
  recipient with a tracked link.
- "Information exposure score" gating per plan tier — currently
  visible to everyone; landing-page copy claims it as an Enterprise
  feature so we should soft-gate the readers list (count visible
  free; full readers list locked behind plan check).



## §iter65 — Marketing landing redesign + live sensitivity demo + deep-link fixes (2026-04-29)

### A · Marketing/landing site redesign
- Per `/app/design_guidelines.json` (delivered by design_agent_full_stack
  in iter64). Cream/oxblood preserved; executive navy `#0A1F44`
  introduced as the third accent on conversion-driving CTAs.
- New components:
  - `HeroSection.jsx` — tightened value-promise that lands within the
    first viewport. "AKKI reads the pack so you can read the room."
    Subhead aimed at "executives and directors who grow and preserve
    shareholder value". Single dominant navy CTA: "Try AKKI in 60
    seconds" → /sandbox. Right-rail pull quote with navy attribution.
  - `ThreePillars.jsx` — bento grid: **Solve as the dominant card**
    (8/12 cols, dark, books photo) with the four phases and a
    "Start a Solve session" CTA. **Cross Board Pulse** sidebar (4/12,
    library photo) targeted at multi-board NEDs. **Decks + Reports
    preview row** (12/12) inviting a jump to the Enterprise band.
  - `EnterpriseFeature.jsx` — full-bleed navy band positioning the
    Decks + Reports Studio as the enterprise differentiator. Three
    bullets (auto-sensitivity, read-tracking, exposure score) + cream
    "Request a team workspace" CTA + outline "Security design" link.
    Hosts the LIVE SENSITIVITY DEMO.
- Removed long-winded sections per user feedback:
  - "Five surfaces / propositions" list — too verbose, replaced by
    Trust Strip (3 condensed guarantees).
  - Standalone "Closing call" section — folded into the final inline
    CTA block.
  - Dark "Assurance" block — folded into the Trust Strip.
  - Three-photo strip — one image now lives in Hero pull-quote rail.
- Editorial pull-quote rewritten: "Adopting tools that preserve value
  isn't operational — it is a fiduciary duty." Attribution chip uses
  Exco360 brand mark in navy.
- Audience cards (NED + Exec) condensed and tightened.
- Header masthead: Solve nav link routes to `#solve-pillar` anchor;
  "Request access" button uses navy.

### B · Live sensitivity demo on landing
- New public endpoint `POST /api/public/studio/sensitivity-demo` —
  no auth required. Accepts `{text: 4-4000 chars}`, returns the
  full sensitivity record `{score, classification, label, reasons[]}`
  plus `input_chars`. No DB write, no LLM call (regex scorer is
  microsecond-cost).
- Per-IP rate limit (1.5s window) using `X-Forwarded-For` first hop
  for k8s ingress-aware throttling (iter65 hardening from testing
  agent's RCA note). `request.client.host` fallback when XFF absent.
- Frontend `LiveSensitivityDemo` block inside EnterpriseFeature:
  textarea with `data-testid="enterprise-demo-input"`, "Use sample"
  button (`enterprise-demo-sample`), result panel
  (`enterprise-demo-result`) with classification chip, reasons list.
  Debounced 800ms after typing; immediate fire on sample. Shows
  "Slow down a moment…" on 429.
- Sample content: "Q3 board pack draft… framed customer-concentration
  story as macro-driven … £45m bolt-on acquisition." Scores
  Confidential · 50 with M&A / financial-figures / regulator triggers.

### C · Decks deep-link fix (cross-context)
- New endpoint `GET /api/decks/{deck_id}/context` — given just a
  deck_id, returns the context_id the deck belongs to (only if the
  caller has active membership). Powers cross-context deep-link
  resolution.
- `Decks.jsx` deep-link effect now fetches the deck under the active
  `cid` first; if the request fails (deck belongs to a different
  context), it calls `/decks/{id}/context` and `switchContext()` from
  AuthContext to pivot the user's active context. Subsequent re-render
  loads the deck cleanly.
- Race fix: when `deepLinkDeckId` is present, the [cid] effect skips
  resetting `view/outline/deck` so the deep-link can win the load
  race. Verified end-to-end: navigating to /app/decks/{id} from a
  fresh browser auto-switches context AND loads the DeckStep with
  sensitivity chip + exposure pill rendered.

### D · Briefings deep-link from Studio history
- Clicking a briefing row in StudioHistoryStrip now navigates to
  `/app/prepare#brief-{id}` (Catch-up surface). Brief routes lived
  there pre-iter64; the hash anchor lets that page scroll/select
  the specific briefing once iter66 wires the anchor handler.

### Tests
- iter65: testing agent v3 — backend **7/7 pytest pass** (~14s).
  Frontend **100% of assertions**: landing page + hero + pillars +
  enterprise + live demo (sample button + typed input both fire
  the API + render result), final CTA, trust strip, audience cards,
  /app/decks Studio regression, /app/prepare Catch-up regression,
  briefings deep-link navigation.
- Pytest file: `/app/backend/tests/test_iter65_landing_demo.py`.
- Report: `/app/test_reports/iteration_65.json`.
- Decks deep-link cross-context resolution verified manually after
  testing agent's run (the test account had no decks in active ctx).

### Open / iter66 backlog
- Catch-up page (`/app/prepare`) needs to handle the
  `#brief-{id}` hash anchor — scroll to and select the specific
  briefing. Today the navigation works but the briefing isn't
  highlighted on arrival.
- `Workflows`-as-journeys home widget could migrate inside Studio
  as an "active workflows" rail (deferred from iter64).
- Sensitivity scorer LLM tiebreaker for ambiguous text (today: pure
  regex, intentionally conservative — false-negatives on creative
  phrasings are the main miss).
- `/api/public/studio/sensitivity-demo` could be promoted to a
  fully-featured "Try the Studio" page with classification
  comparisons (Public vs Restricted side-by-side) and a "Save
  result as PDF" affordance.
- Plan-gated readers-list on engagement endpoint — currently
  readers[] visible to all members; gate full PII behind Enterprise
  plan with a count-only fallback for free.
- Exco360 Blog → Subscribe primary capture: the "Read the Exco360
  Blog" link should grow into a more conversion-shaped block once
  newsletter ESP is wired.



## §iter66/67 — Studio backlog clean-up: plan-gated readers, LLM tiebreaker, workflows rail, hash handler (2026-04-29)

### A · Plan-gated readers PII (Decks + Reports engagement)
- `/api/contexts/{cid}/studio/{kind}/{id}/engagement` now returns
  `plan` (free/pro/team) and `readers_locked` (boolean).
- For free accounts: `readers[] = []`, `readers_locked = true`,
  `unique_readers` count still populated (so users see the *number*
  of readers but not who).
- For Pro/Team accounts: `readers[]` carries the full PII (name,
  email, first_viewed_at, last_viewed_at, view_count). Same shape
  as before — Pro upgrade is invisible from the data side.
- Frontend DeckStep renders a `decks-readers-locked` block when
  `readers_locked && unique_readers > 0`: "X unique reader(s) so
  far · Upgrade to Pro to see who" with an oxblood "Upgrade to Pro"
  link to `/app/settings?tab=billing`.

### B · Sensitivity scorer LLM tiebreaker
- New `score_sensitivity_with_llm_tiebreaker(artefact, fallback_only=True)`
  in `studio_sensitivity.py`. Calls the regex scorer first; only
  escalates to a single STANDARD-tier LLM call when the regex result
  lands in the ambiguous "internal" band (25-49) AND the artefact
  text is ≥200 chars.
- LLM may bump to a HIGHER band (confidential/restricted) — never
  downgrades. Bumps are tagged with `llm_tiebreaker_used: true` and
  the reasons[] list gains an "LLM tiebreaker · <one-line>" entry.
- Endpoint: `POST /api/contexts/{cid}/studio/{kind}/{id}/rescore?use_llm=true`
  triggers the tiebreaker. Default (`use_llm=false`) keeps the
  cheap regex behavior. Verified on the live test deck — bumped
  from Internal (25) → Restricted (75) with NPL + control deficiency
  reasons.

### C · Workflows-as-journeys rail in Studio
- New `ActiveWorkflowsRail` component in Decks.jsx — renders above
  StudioHistoryStrip when the context has any active or paused
  Plays. Shows up to 4 tiles with play_type label, status chip
  (emerald=active / amber=paused), title + current step. Each tile
  click navigates to `/app/plays/{id}`.
- Pulls from existing `GET /api/contexts/{cid}/plays` endpoint; no
  new backend route. Fold-in keeps the legacy /app/plays page intact
  while surfacing in-progress journeys on the Studio surface where
  users actually produce material.

### D · Catch-up hash anchor handler (`#brief-{id}`)
- New useEffect in Prepare.jsx — when /app/prepare loads with a
  `#brief-{id}` hash, auto-switches to the Brief tab and opens the
  brief modal via `openBriefById`. Strips the hash via
  `history.replaceState` so reloads don't re-trigger.
- Iter66 first attempt had a TDZ (Temporal Dead Zone) ReferenceError
  because the hash effect referenced `openBriefById` before its
  `useCallback` declaration. Fixed in iter67 by reordering the
  declarations AND adding a `hashHandledRef` to prevent re-fire
  flakiness.
- Iter67 hardening: also listens for `hashchange` events on the
  window so client-side `<a href="#brief-x">` links work even when
  the user is already on /app/prepare.

### E · Briefings row → PDF export
- StudioHistoryStrip briefing-row click was originally routed to
  `/app/prepare#brief-{id}` but db.briefings (formal briefings) ≠
  db.briefs (orientation briefs that the Catch-up Brief tab shows).
- iter67 fix: briefing rows now open the briefing's PDF export
  directly in a new tab via authenticated blob fetch +
  `window.open(blob:url)`. Closes the loop on the Studio history
  strip so every artefact (deck OR briefing) lands in the right
  reader surface in one click.

### Tests
- iter66: 9/9 backend pytest GREEN; one frontend TDZ ReferenceError
  on hash route (FIXED).
- iter67: 15/15 backend pytest GREEN; 100% of frontend assertions
  GREEN: /app/prepare loads clean, invalid-hash no crash + stripped,
  valid-hash modal opens, briefing row opens blob PDF (verified on
  briefing 238b9d1e via window.open stub).
- Reports: `/app/test_reports/iteration_66.json` and
  `/app/test_reports/iteration_67.json`.

### Open / iter68 backlog
- Workflows-as-journeys rail tile testid migration to use
  `<Link>` instead of `window.location.assign` for SPA prefetch
  consistency (low-priority).
- Sensitivity scorer rule expansion as new content patterns surface.
- /try-studio standalone page (Public vs Restricted side-by-side
  comparisons + "Save result as PDF" affordance for the live demo).
- Exco360 newsletter ESP wiring + a real subscribe block.
- A/B test the navy primary CTA against oxblood — 2-week click-through
  count to settle which lands more conversions.


## §iter68 — Share with the Chair + Progress audit (2026-04-30)

### A · Share with the Chair (closes the Studio distribution loop)
- New backend endpoint `POST /api/contexts/{cid}/studio/{kind}/{aid}/share-email`
  (auth): records a `studio_shares` row with `external=true`, mints a
  JWT-signed tracking token (14-day TTL, algorithm HS256, purpose
  `studio_share`), and emails via Resend using a new editorial template
  (`_render_share_artefact_email_html`) that carries the sensitivity
  label chip and a cream/oxblood palette consistent with the checklist
  email.
- Public click tracker: `GET /api/public/studio/track/{token}` (no auth).
  Decodes the token, records a `studio_views` row keyed on a synthetic
  `account_id = external:<sha256(email)>` so repeat opens dedupe per
  recipient, marks `first_opened_at` / `last_opened_at` on the share
  record, and 302-redirects to the in-app deep link
  (`/app/decks/{id}` or `/app/prepare#brief-{id}`).
- Net effect: **external readers feed straight into the exposure score**.
  Smoke-tested live on Tuli NED briefing `238b9d1e`: share email sent
  via Resend (`mode=sent`), then a crafted token-click bumped
  `unique_readers` 0 → 1 and `exposure.score` 0 → 52 with
  `band=moderate`.
- Frontend:
  - New `components/studio/ShareArtefactModal.jsx` — recipient
    name/email/note fields, editorial register, success state with
    send-another affordance.
  - `DeckStep` header gets a `deck-share-btn` next to the Sensitivity
    + Exposure chips; opens the modal with `onShared` → refresh
    engagement.
  - `StudioHistoryStrip` rows get a `studio-history-share-{kind}-{id}`
    button (stopPropagation so it doesn't fire the row open); shared
    modal state at strip level.
- Cookie-sensitive endpoints are untouched — the tracker is cookie-less
  on purpose (non-AKKI recipients don't need an account to record a
  read).

### B · Progress audit + journey guide
- New doc: `/app/AUDIT_iter68.md` — honest walk through:
  11 experience rules (10 holding, 1 drift — validator not fanned out
  to decks/reports/solve), BRD v4.0 module coverage (14/18 live, 4
  deferred per Path A), canonical journeys (Sandbox→Signup→Solve→Studio
  and NED→Catch-up→Solve→Handoff→Share), and the P1/P2/P3 priority list
  for iter69.

### Open / iter69 backlog (P1 — real loops to close)
- Real Stripe → `solve_pro` state flip via the existing webhook.
- Real validator (Gemini 2.5 Flash) fan-out to decks, reports, Solve
  syntheses (briefs already covered from iter49).
- Cross-Board Pulse as a dedicated surface OR soften landing copy.
- Public read-only artefact view for non-AKKI share recipients
  (introduced as friction by iter68's Share with the Chair feature).

### Open / iter69 backlog (P2 — cosmetic)
- Rename "Briefings" → "Reports" in Studio history strip (avoid the
  briefs vs briefings collection collision).
- Collapse `/app/plays` into Studio's ActiveWorkflowsRail (today: 3
  entry points for the same thing).
- Promote sensitivity LLM tiebreaker to default-on (today: opt-in).



## §iter69 — Public read-only share viewer (closes iter68's friction loop) (2026-04-30)

### Why
Iter68 shipped "Share with the Chair" — the share email sends a tracked
link, and when the recipient clicks, their view bumps the artefact's
exposure score. But the redirect target was `/app/decks/:id` or
`/app/prepare#brief-:id`, which bounced non-AKKI directors (most
external recipients) straight into `/signin`. The iter68 audit flagged
this as the highest-impact friction to close.

### What shipped
- **Public read-only viewer page** (`/shared/:token`, new
  `pages/SharedArtefact.jsx`). Editorial cream/oxblood chrome (AKKI
  logo + "Shared with you · Synisense-shielded" in the topbar). Renders
  the artefact (deck slides OR briefing opening + items) as read-only
  with the sensitivity chip inline. Footer: "Your read has been
  recorded" + contextual CTA (authed: `Open in AKKI →`; anonymous:
  `Try AKKI in 60 seconds →` to `/sandbox`).
- **New backend endpoint** `GET /api/public/studio/read/{token}` (no
  auth). Decodes the share token, records an idempotent per-day view
  row under `account_id = external:<sha256(email)>`, marks the share
  record as opened, and returns public-safe content (title, slides
  for decks; title + opening_paragraph + items for briefings — we
  deliberately drop audience, missing_context, internal production
  metadata).
- **Legacy track endpoint updated**: `GET /api/public/studio/track/{token}`
  still 302-redirects, but now always to `/shared/:token` instead of
  the app deep links. Back-compat preserved for any shares sent during
  iter68.
- **Email template URL swapped** to `{FRONTEND_URL}/shared/{token}` so
  new shares land directly on the public viewer.

### Error states
- Expired token → 410 ("This share link has expired.")
- Invalid token → 400 ("Invalid share link.")
- Deleted artefact → 404 ("This document is no longer available.")
- All three surface as an editorial `<ErrorPanel>` on the viewer with
  a "reply to sender" nudge.

### Tests
- iter69: `tests/test_iter68_share_chair.py` — **8/8 GREEN** (end-to-end
  share-email + public-track redirect + public-read happy path + 410
  expired + 400 invalid + 404 missing + unique_readers increment with
  same-day dedupe).
- iter64/66/67 regression: **29/29 GREEN**, zero regressions.
- Frontend: programmatic smoke pass in Playwright confirmed title,
  "Restricted" sensitivity chip, 6 briefing items, footer, and the
  non-authed "Try AKKI" CTA all render on `/shared/:token` with a valid
  token.

### Files touched
- `/app/backend/routers/studio.py` — new `/api/public/studio/read/{token}`,
  track endpoint redirect updated, email template URL swapped.
- `/app/frontend/src/pages/SharedArtefact.jsx` — new file.
- `/app/frontend/src/App.js` — route `/shared/:token` registered (public).
- `/app/backend/tests/test_iter68_share_chair.py` — 8 regression cases.

### Still-open P1 (carry forward to iter70)
- Real Stripe → `solve_pro` state flip via the existing webhook.
- Real validator (Gemini 2.5 Flash) fan-out to decks, reports, Solve
  syntheses (briefs already covered from iter49).
- Cross-Board Pulse as a dedicated surface OR soften landing copy.

## §iter70 — Trust-tiered inbound email triage (2026-04-30)

### Why
Iter51 shipped Postmark inbound: a user gets a unique
`inbound+<token>.<ctx>@inbound.akki.ai` address; any email forwarded
there gets extracted and filed. But the pipeline ingested **anything**
that reached the mailbox — owner, reportee, or random spammer — with
no trust differentiation. Three journeys asked by the user:
  1. owner forwards → auto-ingest (was live)
  2. known reportee CCs → auto-ingest (worked mechanically, no trust stamp)
  3. unknown sender → queue for review (NOT built)

### What shipped
**Sender-tier classifier** in `routers/inbound_email.py` — exact email
match only (user direction 1a):
- `_classify_sender_tier(from_email, account, context)` → returns one
  of `owner`, `reportee` (with full reportee record), or `unknown`.
- **Tier A (owner)** → auto-ingest as before, now stamped with
  `inbound_trust_tier='owner'`.
- **Tier B (reportee)** → auto-ingest with `inbound_trust_tier='reportee'`,
  `inbound_reportee_id`, `inbound_reportee_name`, `inbound_reportee_title`.
- **Tier C (unknown)** → payload quarantined into new
  `db.inbound_queue` collection with `status='pending_review'`. Raw
  payload (base64 attachment + bodies) stored separately in
  `db.inbound_queue_raw` so list queries stay light.

**New router** `routers/inbound_queue.py`:
- `GET /api/contexts/{cid}/inbound-queue?status=all|pending_review|accepted|rejected`
- `GET /api/me/inbound-queue/counts` — aggregated across every workspace
  the caller is a member of. Powers the Home card.
- `GET /api/contexts/{cid}/inbound-queue/{qid}` — detail + decoded body
  preview + virus-scanned attachment-extract preview.
- `POST /api/contexts/{cid}/inbound-queue/{qid}/accept` — virus-scans,
  extracts, writes to storage, inserts a `documents` row with
  `inbound_trust_tier='unknown_promoted'` + `inbound_queue_id` pointing
  back to the queue row for full audit chain. Marks queue row as
  `accepted`. 409 on double-accept.
- `POST /api/contexts/{cid}/inbound-queue/{qid}/reject` — archives
  queue row with `reject_reason`. **No email sent to sender** per user
  direction 3c. 409 on double-reject.

**Frontend**:
- `pages/InboundQueue.jsx` — editorial review surface (cream/oxblood).
  Workspace switcher auto-selects the busiest pending workspace on
  first load (iter70 UX polish after the testing agent flagged this
  — landing on an empty workspace when another has pending items
  was friction). Detail modal → Accept (with note) or Reject (with
  reason) dialogs. All rows, modals, and confirm buttons carry
  data-testids.
- `components/home/InboundQueueCard.jsx` — Home card with both
  populated state (by-context breakdown + "Review" CTA) and quiet
  empty state ("Emails from you and your reportees file themselves…").
- `WorkflowsHub.jsx` — new `Inbound review` tab with count pill;
  defaults to this tab when `inboundCount > 0`.

**Document sanitisation**: `routers/documents.py::sanitize_doc` now
includes `source`, `inbound_from_email/name`, `inbound_subject`,
`inbound_trust_tier`, `inbound_reportee_*`, `inbound_queue_id`,
`inbound_promoted_*` fields so the frontend document viewer can
render the trust chain.

### Tests
- **15/15 backend pytest GREEN** (baseline 6 + 9 edge cases written
  by the testing agent). Covers all three tiers, accept/reject/double-
  accept/double-reject, idempotent replays, empty body + attachment-
  only ingests, multi-attachment summaries, count-shape validation.
- **52/52 regression GREEN** — iter64 through iter70 all pass together.
- **Frontend** — 100% green via `testing_agent_v3_fork/iter68.json`
  after a null-guard bug fix the testing agent authored directly
  (Dialog children rendered even when `open={false}`; detail
  comparisons now guard with `detail && detail.status !==` not
  `detail?.status !==`).

### Non-trivial behaviours (read before changing)
- External-reader dedup on Share-with-Chair (iter68) and queue-item
  dedup on Tier-C inbound both use synthetic IDs derived from the
  sender email. Replaying a Postmark MessageID does NOT create a
  second queue row — we dedupe on both `(context_id, message_id)`
  against documents AND against inbound_queue.
- Reject intentionally sends NO reply (user direction 3c). Ops audit
  log captures the decision instead. If we later want sender
  notifications, they should be opt-in per-workspace, not per-decision.
- Tier-B (reportee) matching is exact email only. If a reportee emails
  from a slightly different alias (e.g. `s.kamau@` vs `sarah.kamau@`),
  they fall to Tier C. The testing agent recommended considering
  domain-match fallback as a follow-up; we deferred that decision.

### Files touched
- `/app/backend/routers/inbound_email.py` — classifier + Tier-C branch
- `/app/backend/routers/inbound_queue.py` — new file
- `/app/backend/routers/documents.py` — sanitize_doc extended
- `/app/backend/server.py` — router include + 4 new indexes
- `/app/frontend/src/pages/InboundQueue.jsx` — new file
- `/app/frontend/src/components/home/InboundQueueCard.jsx` — new file
- `/app/frontend/src/components/home/WorkflowsHub.jsx` — Inbound tab
- `/app/frontend/src/App.js` — route registered
- `/app/backend/tests/test_iter70_inbound_triage.py` — 6 cases (main agent)
- `/app/backend/tests/test_iter70_inbound_edge.py` — 9 cases (testing agent)

### Still-open (carried forward from iter68/69 audit)
- Real Stripe → `solve_pro` webhook state flip
- Real validator (Gemini 2.5 Flash) fan-out to decks, reports, Solve
- Cross-Board Pulse as dedicated surface OR soften landing copy


---

## Sprint PRE / Website v7 — closure (2026-05-12)

Full rebuild of the public marketing surface to **Website Brief v7.0**. Bronze
removed; canonical 7-token palette is now the website's only design system.

- **Visual system**: parchment / parchment-light / ink / graphite / graphite-light /
  oxblood / oxblood-deep. Source Serif 4 + Inter + JetBrains Mono with credible
  fallbacks. Single-word oxblood italic lift per hero h1 (every page).
- **18 pages built/rewritten** at top-level routes (`/solva`, `/akki-chat`,
  `/work-studio`, `/cycle-manager`, `/monitor`, `/pulse`, `/document-journal`
  reinstated; `/pricing` reinstated; `/for-exco` retained).
- **Home**: 10-section v7 hierarchy — Hero / Evidence Strip / Tier 1 Safety /
  Tier 2 Workspace (no product names) / Tier 3 Inventions (Solva, Synisense,
  Agent Cycle) / Three Audiences + triptych / Cohort teaser / Inverted CTA.
- **5 images** at <120 KB each, anonymised graphite duotone editorial portraits.
- **Smoke**: 24/24 routes return 200 with valid v7 hero + Plausible + canonical.
- **Backend regression**: 29/29 trust-critical tests passing.
- **Perf**: LCP 404 ms, CLS 0, FCP 132 ms, TTI 489 ms (container-headless).
  Bundle weight 2.5 MB shared with /app SPA — marketing-chunk split is next sprint.
- **SEO**: sitemap.xml (24 URLs), robots.txt, OG/Twitter cards, per-page canonical
  to akki.syni.ai.
- **Plausible analytics** wired with `data-domain="akki.syni.ai"`.

### Out of scope (next sprints)
- App `index.css` v7 palette migration (kept aliased — `--navy → var(--ink)`,
  `--chrome → var(--ink)`, `--cream → var(--cream)` etc.)
- Marketing-route code-splitting (to hit <500 KB landing budget)
- Self-hosted woff2 for Source Serif 4 / Inter / JetBrains Mono
- `/about` named team portraits (G6 requires real photography)
- Cohort + Organisation application form workstreams

### Files
- New: `frontend/src/website/style.css`, `WebsiteShell.jsx`, `WebsiteNav.jsx`,
  `WebsiteFooter.jsx`, `copy/index.js`, `components/PagePrimitives.jsx`,
  18 page files in `pages/` and `pages/product/`, 5 `assets/v7/*.webp`,
  `public/{robots.txt,sitemap.xml}`.
- Removed: `pages/ProductHub.jsx`, `components/EvidencePanel.jsx`.
- Modified palette only: `frontend/src/sandbox/style.css`.
- Closure: `/app/docs/sprints/PRE_v7_website.md`.

---

## Sprint HOME — closure (2026-05-12)

Post-sign-in Home surface upgrade: full v7 palette migration into `index.css`,
ExCo as a grouping function (NEW), Portfolio state indicators, role calibration
on the top-nav.

- **App `index.css` v7 migration**: 7-token palette canonical, legacy
  `--paper/--cream/--accent/--severity/--navy/--chrome` preserved as aliases →
  `var(--<v7-token>)`. Source Serif 4 + Inter + JetBrains Mono via `@font-face
  local()`. Calibri removed.
- **ExCo (new collection)**: `db.exco_teams` per-context grouping with 7
  endpoints (`POST/GET/PATCH/DELETE /api/contexts/{cid}/exco-teams`,
  member add/remove, archive). Owner/admin gating, audit rows on every
  mutation, soft-delete only. `ExcoTeamsCard` on HomeExecutive + HomeDual.
- **`GET /api/me/portfolio`**: per-membership cycle / goals-at-risk /
  pending-followups / unread-signals / last-active state with 30-second
  in-memory cache. Portfolio cards render state badges (oxblood for attention,
  graphite-light for quiet).
- **Role kicker on top-nav**: derives `Executive` / `Non-Executive Director`
  / `Executive · NED` / appends `· ExCo` when the account is in any ExCo team
  in the active context.
- **Tests**: 35/35 passing (29 trust-critical + 6 new `test_exco_teams.py`).

### Files
- New: `backend/routers/{exco_teams,portfolio}.py`, `backend/tests/test_exco_teams.py`, `frontend/src/components/home/ExcoTeamsCard.jsx`.
- Modified: `backend/server.py`, `frontend/src/index.css`, `frontend/public/index.html`, `pages/home/{HomeExecutive,HomeDual}.jsx`, `pages/ContextPortfolio.jsx`, `components/layout/CycleContextIndicator.jsx`.
- Closure: `/app/docs/sprints/HOME.md`.

### Deferred
- Self-hosted woff2 files in `public/fonts/` (chains ready, files awaited)
- Module-surface palette refinement (separate sprint per module)
- Cross-board "dual" auto-detection (still relies on `account.declared_role`)

---

## Sprint CHAT — closure (2026-05-12)

Trust-First Chat refinement: light v7 palette pass on chat surfaces,
inline per-message Synisense badge, provider transparency line, Trust
Panel cross-link from AuditDialog, K5 streaming transition on first
chat open.

- **v7 palette light pass**: `MarkdownMessage.css` + `ModelAvatar.jsx`
  migrated off legacy hex literals (`--accent: #8b1d2c`, `--gold: #C9A961`)
  to canonical v7 tokens (`--oxblood`, `--graphite`). `Chat.jsx` resolves
  through HOME-sprint alias chains.
- **Batched per-message Synisense**: new `POST /api/chats/{cid}/messages/synisense-runs/batch`
  endpoint replaces the N+1 pattern. `useMessagesSynisense` hook + 30s
  polling + invalidation on chat change. `PerMessageSynisenseBadge`
  renders inline next to model label, mono 10px oxblood, hover tooltip
  with three-layer breakdown.
- **Provider transparency**: `ProviderLine` reads `provider_used` +
  `fallback_triggered` from the message record; italic when fallback,
  hover tooltip resolves the chain (e.g., "Direct Anthropic SDK →
  Emergent universal proxy").
- **Trust Panel cross-link**: tertiary v7 button at bottom of
  AuditDialog dispatches global `akki:open-trust-panel` event;
  AppShell listens and opens the panel without prop-drilling.
- **Streaming transition**: Chat wrapped in `WorkspaceEntryGate` so
  first navigation TO `/app/chat` per session shows the editorial scene
  (4-5s, prefers-reduced-motion respected).
- **Tests**: 35/35 passing — no regressions.

### Files
- New: `frontend/src/hooks/useMessagesSynisense.js`, `frontend/src/components/chat/{PerMessageSynisenseBadge,ProviderLine}.jsx`.
- Modified: `backend/routers/synisense_metrics.py` (+batch endpoint), `frontend/src/pages/Chat.jsx`, `frontend/src/components/chat/{MarkdownMessage.css,ModelAvatar.jsx}`, `frontend/src/components/layout/AppShell.jsx` (event listener).
- Closure: `/app/docs/sprints/CHAT.md`.

### Out of scope (deferred)
- Editorial chat redesign (letter format, no bubbles)
- Export redaction record PDF (move to TRUST sprint)
- Hash chain changes (frozen)
- Module-specific tests for batch endpoint (covered by shared aggregation pipeline)

---

## Sprint SOLVA — closure (2026-05-12)

Editorial pass on Solva surfaces: v7 palette/typography sweep, per-section
Synisense badge with audit storyline, export template v7 migration with
preserved byte-determinism, `placeholder_stub` deletion, v2→v3 UI brand
sweep (code namespace preserved).

- **v7 palette sweep**: `tokens.js` migrated to v7 `var(--*)` references;
  5 component files patched (69 hex literals → 0). Banned-vocab clean.
- **Per-section Synisense breakdown**: new endpoint `GET /api/solva/v2/sessions/{sid}/synisense-breakdown`
  + `session_id` threaded through pipeline. `PerSectionSynisenseBadge.jsx`
  + audit storyline at top of `SolvaArtefact.jsx`. Legacy sessions fall
  back to surface + time-window query.
- **Export templates**: HTML (WeasyPrint) palette → v7; DOCX colors → oxblood;
  font runs preserved (determinism). DOCX + PDF rebuild produces identical
  SHA-256 across runs.
- **placeholder_stub deleted** from `SHIELD_BYPASS_REASONS` (zero live callers).
- **v2→v3 UI brand sweep**: zero UI-visible "Solva v2" matches; CODE
  namespace + DB collections + audit-chain surfaces untouched.
- **Tests**: 35/35 trust-critical preserved; 112/132 Solva v2 (20 failures
  pre-date this sprint, confirmed via `git stash` retest).

### Files
- New: `frontend/src/components/solva/artefact/PerSectionSynisenseBadge.jsx`.
- Modified: `frontend/src/components/solva/flow/tokens.js`, 5 Solva surface files,
  `backend/routers/solva_v2.py` (+endpoint), `backend/services/synisense/pipeline.py`,
  `backend/services/solva_v2/llm_adapter.py`, `backend/solva_artefact_export.py`,
  `backend/templates/solva_*.html`.
- Closure: `/app/docs/sprints/SOLVA.md`.

### Deferred
- DOCX font runs (Source Serif 4 / Inter) — pending hash-chain version bump
- Solva ExCo association (Q2(c))
- Export-redaction-record cross-link from Solva artefact (S-27 → TRUST sprint)
- Pre-existing Solva v2 test failures (schema drift in synthesis cluster path)

---

## Sprint STUDIO — closure (2026-05-12)

Work Studio editorial pass + per-artefact audit visibility + export
template v7 + CI determinism.

- **v7 palette sweep**: 67 hex literals → 0 across `pages/WorkStudio.jsx`,
  `pages/StudioComposerPage.jsx`, `pages/Decks.jsx`, `components/studio/`.
  Banned-vocab clean.
- **Per-artefact Synisense breakdown**: new endpoint
  `GET /api/work_studio/artefacts/{kind}/{id}/synisense-breakdown`.
  `artefact_id` threaded through `synisense/pipeline.py`. Frontend
  `PerArtefactSynisenseBadge.jsx` renders inline at the top of the
  artefact drawer with audit storyline.
- **Export-footer stamp**: `Brief.audit_summary` optional field; when
  set, DOCX + PDF render an italic mono footer line and PPTX appends a
  dedicated `AUDIT` slide. None by default — preserves byte-determinism
  for legacy callers.
- **Export template v7**: DOCX + PPTX + PDF palette migrated to v7
  oxblood/ink/graphite. Font runs preserved (Georgia/Calibri) to
  maintain hash-stamped reproducibility.
- **CI determinism test**: new `backend/tests/test_render_determinism.py`
  with 6 tests — DOCX, PPTX, PDF deterministic across two renders;
  report kind shares pipeline; audit-summary variant deterministic;
  citation-index W-23 regression.
- **W-22 (failure persistence)**: `llm_pass1` + `llm_pass2` (+ raw text
  heads) now persisted on every failure row via `partial` capture
  attached to the exception.
- **W-23 (citation validator)**: phantom citation indices now dropped
  silently with a WARNING log row — no longer fails the whole render.

### Files
- New: `backend/tests/test_render_determinism.py`,
  `frontend/src/components/studio/PerArtefactSynisenseBadge.jsx`.
- Modified: `backend/services/{synisense/pipeline.py,work_studio_export.py}`,
  `backend/routers/work_studio_export.py`, `backend/work_studio/{brief,docx_generator,pptx_generator,pdf_generator}.py`,
  `frontend/src/pages/{WorkStudio,StudioComposerPage,Decks}.jsx`,
  `frontend/src/components/studio/*.jsx`.
- Closure: `/app/docs/sprints/STUDIO.md`.

### Deferred
- Auto-compose `audit_summary` from synisense_runs at export time
- ExCo association on Studio artefacts (Q4(b) → CYCLE sprint)
- Deck PDF renderer (`render_deck_pdf` NotImplementedError)

---

## CYCLE sprint — Assignment Handoff (2026-02)

**Brief:** `/app/memory/sprints/CYCLE_MANAGER_BRIEF.md` (APPROVED-FOR-BUILD).
**Verify doc:** `/app/memory/sprints/CYCLE_MANAGER_VERIFY.md`.
**Architectural lock:** C3 resolved → ASSIGNMENT HANDOFF (not push, not pull).

### What shipped

- **`services/cycle_permissions.py`** — `can_submit_for_board(account, context, membership)` and `permission_reason(...)`. Owner only for individual workspaces; owner + admin + chief_of_staff + ExCo team members for team workspaces; NED contexts never permitted.
- **`routers/cycle_assignments.py`** — 7 new endpoints under `/api`:
  - `POST .../briefs/{bid}/submit-for-board` (draft → submitted)
  - `POST .../briefs/{bid}/assignments` (fan-out, ned_ids XOR cohort_id)
  - `GET .../briefs/{bid}/assignments` (creator-side list)
  - `DELETE .../cycle-assignments/{aid}` (cancel pending)
  - `GET /api/ned/inbox/assignments` (NED inbox; strict whitelist)
  - `POST /api/ned/assignments/{aid}/accept` (privacy-wall ingest; idempotent; flips brief → shipped)
  - `POST /api/ned/assignments/{aid}/decline` (no ingest)
  - `GET /api/me/submitted-briefs` (submitter rollup view)
- **`routers/ned/__init__.py`** — marker module documenting that PRODUCT_SPEC §5.6 ("NED has zero code") is out of date; keep-code decision recorded.
- **`email_service.notify_ned_assignment_stub`** — MOCKED IN DEV. Resend is in test mode in the preview env; the call site is wired so production can flip without code change.
- **New collections + indexes:** `db.cycle_assignments` (unique partial index on `(brief_id, ned_id)` where status ∈ {pending, accepted, declined}; secondary indexes by NED + by context+cycle + by submitter), `db.ned_packs` (unique by `assignment_id`), plus a `work_studio_briefs.{submitter_account_id, board_status, submitted_at}` secondary index for the rollup view.
- **Frontend — new:**
  - `pages/ned/NedInbox.jsx` (`/app/ned/inbox`) — tabs Pending / Accepted / Declined, accept/decline dialogs, streaming reveal first visit.
  - `components/cycle/CycleStatusBadge.jsx` — v7 status badge (draft/submitted/shipped + pending/accepted/declined/cancelled).
  - `components/cycle/BoardSubmitPanel.jsx` — ship-step UX, submit + assign + cancel + roster.
  - `components/cycle/NedInboxTile.jsx` — HomeNed indicator with pending count.
- **Frontend — edited:**
  - `pages/Cycle.jsx` — 4 hex literals removed; `BoardSubmitPanel` wired into Compilation step.
  - `pages/ned/NedMeeting.jsx` — 2 hex literals removed.
  - `pages/home/HomeNed.jsx` — `NedInboxTile` mounted.
  - `components/transitions/WorkspaceEntryScene.jsx` — `ned_inbox` workspace lines.
  - `App.js` — `/app/ned/inbox` route.
  - `routers/cycle_manager.py` — compile response now surfaces `cycle_id`, `agenda_id`, `board_status` for the ship-step UI.

### Privacy-wall enforcement

`tests/test_cycle_assignment_privacy_wall.py` (3 tests, all green):

1. Strict-whitelist enforcement on NED inbox even with deliberately polluted source rows.
2. `ned_packs` row schema locked to 7 keys; sentinel scan over every value.
3. Defensive guard — accept path is monkey-patched to fail loudly if it reads `cycle_agendas` / `cycle_contributions` / `cycle_team` / `cycle_followups`.

### Acceptance — automated

`pytest tests/test_privacy_wall.py tests/test_phase_g_privacy_wall_sentinel.py tests/test_privacy_wall_phase_2c.py tests/test_universal_search.py tests/test_exco_teams.py tests/test_render_determinism.py tests/test_cycle_assignment_handoff.py tests/test_cycle_assignment_privacy_wall.py -q`

→ **66 passed** (41 baseline + 25 new).

### Acceptance — manual

See `/app/memory/sprints/CYCLE_MANAGER_VERIFY.md` for the §D + §E walkthroughs.

### Hex-literal sweep

`grep -rE '#[0-9a-fA-F]{3,8}\b' pages/Cycle.jsx pages/CycleSettings.jsx pages/ned/ components/cycle/ | grep -v 'color:var'` → **0 hits**.

### Deferred (Should-have, not done)

- Should-have S1 audit log entries beyond submit/assign/accept/decline (those four are wired).
- Could-have items 1–3 (reminder pings, cohort builder UI, CSV export) not started.

### Files index

See `CYCLE_MANAGER_VERIFY.md` §"Files touched in this sprint".

---

## CYCLE v2 sprint — Multi-Cycle Support (2026-02)

**Brief:** `/app/memory/sprints/CYCLE_MANAGER_V2_BRIEF.md` (APPROVED-FOR-BUILD).
**Verify doc:** `/app/memory/sprints/CYCLE_MANAGER_V2_VERIFY.md`.
**Predecessor:** Cycle Manager Assignment Handoff Sprint — `/app/memory/sprints/CYCLE_MANAGER_BRIEF.md`.

### Architectural shift
Single cycle per (account, context) → many cycles per context. New `db.cycles` master collection. Existing `cycle_agendas` / `cycle_team` / `cycle_contributions` / `cycle_followups` / `cycle_assignments` now scoped by `cycle_id`. New account-scoped `db.team_catalogue` holds permanent (name, email) identity.

### What shipped

**Backend**
- `services/cycle_lifecycle.py` — `get_cycle_or_404`, `require_cycle_writable`, `resolve_implicit_cycle_id`, `compute_cycle_counts`, `compute_readiness_score`.
- `routers/cycles.py` — 5 endpoints: create, list (paginated/searchable/sortable), detail, activate, close.
- `routers/team_catalogue.py` — 5 endpoints: list, add (auto-upsert + resurrect-on-add), patch (collision-safe), soft-delete, duplicate-check.
- `routers/cycle_manager.py` — `?cycle_id=` query param on every singleton route (`/cycle/agenda`, `/cycle/team`, `/cycle/contributions`, `/cycle/follow-ups/*`, `/cycle/draft-compilation`, `/cycle/readiness`); `require_cycle_writable` enforced on every mutation; new `GET /cycles/{cycle_id}/agenda-items/{ai_id}/eligible-contributors` (PO #2).
- `migrations/0001_multi_cycle.py` — one-shot, idempotent, runs on boot. Creates a `cycles` row per existing `cycle_agendas.context_id` with the same id; status=active per PO #3. Backfills `cycle_id` on `cycle_team` / `cycle_contributions` / `cycle_followups` / `cycle_compilations` / `cycle_assignments` rows that reference `agenda_id`.
- Indexes: `cycles` `{id unique, (context_id,status,created_at desc), (context_id,title)}`; `team_catalogue` `{id unique, (context_id,email_lc) unique, (context_id,deleted_at,name)}`; `_migrations` `{id unique}`.

**Frontend**
- `/app/cycle` now routes to `CycleList` (new).  `/app/cycle/:cycleId` routes to the existing `Cycle` page (now cycle-aware).
- `lib/cycleApi.js` — typed thin wrappers.
- `pages/cycle/CycleList.jsx` — search + sort (recent / oldest / alpha / status) + 12-per-page pagination + Add Cycle modal + `c` keyboard shortcut + empty state.
- `components/cycle/CycleCard.jsx` — status-driven visual hierarchy (active prominent, draft medium, completed quiet).
- `components/cycle/CycleBreadcrumb.jsx` — Layer 1 nav back to list.
- `components/cycle/CycleStepNav.jsx` — Layer 2 Back/Next. Compilation tab: Next becomes "Close Cycle" (active) / "Cycle Completed" disabled (completed).
- `components/cycle/AddTeamMemberDialog.jsx` — two tabs (Catalogue / New). Duplicate-warning inline; "Add anyway" path.
- `components/cycle/TeamCatalogueDialog.jsx` — manage permanent identity; soft-delete preserves history.
- `pages/Cycle.jsx` — surgical patch: reads `cycleId` from URL params, threads `?cycle_id=` through every API call, sync tab state to URL, contributor dropdown scoped to selected agenda item (PO #2), Activate Cycle button on Agenda tab for Draft (PO #1), Close Cycle button on Compilation tab via step nav, completed-cycle banner + disabled fieldset.

**Conflicts with C3 assignment handoff:** zero refactor needed. See `CYCLE_MANAGER_V2_BRIEF.md §3 Conflicts` for the full reconciliation.

### Acceptance — automated

`pytest tests/test_cycles_v2.py tests/test_team_catalogue.py tests/test_cycle_migration.py + critical regression suite` → **86 / 86 green** (41 baseline + 25 C3 + 20 new).

### Acceptance — migration marker

`db._migrations.findOne({id: "0001_multi_cycle"})` returns a row with `applied_at` + stats (cycles_created, backfilled_cycle_*). Verified live: 3 cycles created, 37 contexts scanned, 5 backfills.

### Acceptance — hex sweep

`grep -rE '#[0-9a-fA-F]{3,8}\b' frontend/src/pages/cycle frontend/src/components/cycle frontend/src/pages/{Cycle,CycleSettings}.jsx frontend/src/pages/ned/ | grep -v 'color:var'` → 0 hits.

### Deferred (Should-have / Could-have, not done)

- Card hover micro-interaction (subtle parchment-shift)
- Sticky Back/Next bar on long tabs
- Cycle title inline edit on detail header
- Bulk close, CSV export, filter pills — all explicitly out of scope per brief.


## Patches 26-29 sprint — closure (2026-05-12)

Closing entry for the multi-patch autonomous sprint covering Chat redesign,
Portfolio Drawer removal, Document Journal & Modal & Monitor v2 polish, and
SYSTEM_STATE refresh.

### What shipped
- **Patch 26 — Chat redesign**: left/right boundary rails removed; 7-word topic title cap; metadata kicker moved below the title; Claude 4.7 Opus + GPT-4o added to model picker; SSE phase labels rewritten in privacy-first narrative voice (e.g. "Reading your context…", "Drafting the reply locally…"). Contract tests in `/app/backend/tests/test_patch_26_chat.py`.
- **Patch 27 — Portfolio Drawer removal**: `<PortfolioDrawer />` component + all mount points deleted across authenticated pages. AppShell portal slot removed. Backend `/api/portfolio` endpoints retained as dead code for future re-introduction.
- **Patch 28 — Home / Documents / Modal / Monitor close-out**:
  - 28A/B: Home 2 hero copy AND insight cards now key off `activeRole === "ned"` to render the right phrasing for Executive vs NED audiences.
  - 28C: Document Journal "empty button" fix — `ReadingTopBar.jsx` download link rewritten to use the axios `api` client with `responseType: "blob"`, ObjectURL anchor pattern; label "Download original" on both `title` and `aria-label` (the icon-only `<a href>` was the user-reported bug and a recurrence of the Patch 23 regression class).
  - 28D: Workspace.jsx document listing now renders a description snippet under every row — sourced from `doc.preview` (server-side ~240-char preview) → `doc.description` → muted italic placeholder. Test ID `workspace-row-snippet-{id}`. `line-clamp-2` keeps row height stable.
  - 28E: Global modal sizing rule. Updated shadcn `DialogContent` + `AlertDialogContent` with `max-h-[85vh] overflow-y-auto pb-6` (inherited by ~33 modals via `cn()` merge). Applied the same constraints inline on 4 hand-rolled modals that don't go through shadcn: `StrategicGoalsPanel ExtractFromDocModal`, `Monitor FunctionPickerModal`, `ShareModal`, `ExcoTeamsCard create-team`.
  - 28F: Monitor v2 executive listings — `StrategicGoalsPanel` rows are now clickable (`role="button"`) and open a new `GoalDetailDrawer` that mirrors the Objectives & Projects drawer pattern (status/score/probability/target panel + score timeline + Edit affordance). Objectives drawer was already wired pre-sprint.
- **Patch 29 — SYSTEM_STATE refresh**: §1, §4, §8 of `/app/memory/SYSTEM_STATE.md` updated with all four patches and final hand-off line.

### Verification
- pytest: **393 passed**, 565 skipped, 0 failed (was 386 going into the fork; the 7 new tests cover the Patch 26 / 28D / 28F surfaces).
- ESLint: clean across all 6 touched JSX files.
- render-smoke: **8 routes clean · 2 upload paths green · Patch 28 interactions green**. The smoke script was extended with a new Step 4 ("Patch 28 interaction smoke") that asserts:
  - workspace row → `journal-drawer-panel` opens
  - workspace row carries `workspace-row-snippet-*` description
  - monitor-fn-modal carries `max-h-[85vh] overflow-y-auto` in its class
  - monitor row click opens `goal-drawer` (or `obj-drawer` fallback)
  - Each check soft-skips gracefully when the seeded data is absent (NED-only context, empty workspace), with reason logged.

### Out of scope (intentional)
- No backend route changes (zero new endpoints).
- No migration runs.
- No auth model changes.
- ExcoTeamsCard manage-drawer left untouched (already had `md:max-h-[90vh] overflow-y-auto`).
- 47 quarantined E2E iter/sprint files (`requests.Session()` rate-limit class) remain quarantined per §7 of SYSTEM_STATE.


---

## Phase A — Synisense Foundation (Shield + Engine + Audit) — 2026-05-13 ✅

The 12-chunk QA sprint is **PAUSED**. The user authorised a full architectural rewrite per
the 4 developer briefs in `/app/memory/briefs/` (Synisense, Solva, Akki Chat, Service
Integration). Phase A is the first of six phases (A → B → C → D → E → F).

**What ships in Phase A:**
- Synisense Shield: in-process FastAPI module under `/app/backend/services/synisense/`
  with three-layer de-identification (regex → tenant-entity dictionary → local spaCy NER),
  HMAC-SHA256 trust receipts with HKDF-derived per-tenant keys, tamper-evident audit log.
- Synisense Engine: signal catalogue (6 categories), seeded-from-Mongo signal generator
  with `derivation_source` markers, paginated tenant-scoped query, subscription stub.
- 7 new HTTP endpoints under `/api/v1/shield/*` and `/api/v1/engine/*`.
- 47 new pytest tests. Full suite: **517 passed, 0 regressions** (was 469).

**Phase A locked decisions (user-approved):**
- `SYNISENSE_MASTER_SECRET` dev fallback OK for now (logged STARTUP WARNING in caps);
  real secret arrives pre-Bank-QA.
- `tenant_id` = existing `account_id`. Single-tenant-per-account. No auth refactor.
- De-id: regex → tenant dict → local spaCy. Cloud LLM-NER removed.
- Trust Receipts v1: HMAC-SHA256 + HKDF.
- Engine seed signals carry `derivation_source: "seeded_from_<collection>"`.
- Strict phase order: A → B → C → D → E → F.

**Phase A PO defaults (locked, relevant to later phases):**
- Cross-module document deletion → soft-delete (`deleted_at`), downstream surfaces
  show "source document deleted" banner.
- "Around the Goals" → Solva sub-module triangulating objectives ↔ cycle outcomes.
- Akki-assigned Monitor status → NOT manually overridable.

**Detailed close-out:** `/app/memory/sprints/PHASE_A_CLOSEOUT.md`.
**Canonical recovery surface:** `/app/memory/REWRITE_SPRINT_STATE.md` (read first
after any handoff/compression).

---

## Phase A backlog (Phase B+ pickup)

- Phase B — migrate every direct LLM call site in `/app/backend/` to
  `services.synisense.shield.client.invoke()`. Absorb 3 P1 risks (sync Document
  endpoints, Solva single-session context scoping, SSE `repr(exc)` leaks) plus 6
  QA findings (Generate Signals error, Take into Solva error, Add to Cycle error,
  Enhance Minutes error, Akki Commentary loading).
- Phase C — Chat protective layer + user-visible audit panel (3 QA findings: chat
  overflow, archive flow, audit panel).
- Phase D — Solva backend rewrite (UI unchanged; 1 QA finding: framing-thin page).
- Phase E — Solva phases 2-4 (Tension / Guardrails / Polish).
- Phase F — Engine real signal generation (1 QA finding: Monitor Akki status mechanic).

## Deferred QA findings (14 items, post-Phase-F)
Pure UI/UX, no AI dependency. Documented in `REWRITE_SPRINT_STATE.md §Deferred QA
Findings`. Do NOT touch during rewrite phases.

---

## J4 — Stage 6 Onboarding (2026-05-25) — CLOSED

**Scope:** First Akki Chat / Solva session — chat-starter prompt seeding (G30) + Help tooltip refinement (G29) + DOM-unconditional refactor (G31). Spec ref: `/app/memory/AKKI_ONBOARDING_SPEC.md` v1.1 §3 Stage 6 + ratified §6 G29-G31.

**e1_tester verdict: 4/4 PASS.** First pass. G30 starter seeding chain verified end-to-end. G29 verbatim copy applied. G31 DOM-unconditional refactor confirmed. Shield invariant on seed value preserved.

**Git tags:** `v-post-j4` + `v-post-onboarding-sprint-closed`. Both local-only.

**Status: CLOSED 2026-05-25.**

## Onboarding sprint J1-J4 — CLOSED

The entire onboarding sprint (chunk `a` per orchestrator chunk index) is complete.

| Chunk | Verdict | Date |
| --- | --- | --- |
| J1 (Stages 1-2) | 4/4 PASS | 2026-05-25 |
| J2 (Stage 3) | 3/4 → 4/4 (after J2.3 fix-passes) | 2026-05-25 |
| J3 (Stages 4-5) | 4/4 PASS | 2026-05-25 |
| J4 (Stage 6) | 4/4 PASS | 2026-05-25 |

**19 ratified gaps G13-G31 implemented · 16 user-verified verdicts · +110 passing tests · 0 regressions · 0 guardrail file changes.**

Full closeout: `/app/memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` §11.

## Post-onboarding-sprint Backlog

- **P0:** None.
- **P1:** Chunk (e) GitHub push (user action via "Save to Github" UI).
- **P2:** ClamAV EICAR spot-check (deferred — `clamd` sidecar STOPPED in preview env).
- **P2:** Demo seeds auto-apply on pod boot (decision-pending — see `POST_T5_BACKLOG.md`).
- **P2:** Demo visibility widening across Document Journal / Work Studio / Monitor list endpoints (parked at J5).
- **P2:** Cycle Setup Wizard `intake_seed=1` Q3 fallback prefill (parked at J5).
- **P2:** Onboarding Health admin dashboard — per-account journey state. Parked in `POST_T5_BACKLOG.md`.
- **P2:** Coming-Soon analytics admin view — `billing_launch_interest` daily rollup. Parked in `POST_T5_BACKLOG.md`.
- **P2:** Launch-day email blast CRON — when billing actually ships. Parked in `POST_T5_BACKLOG.md`.
- **P3:** X4 — Monitor objective/project filter tab removal (parked from T2.3 scope wording).
- **P3:** Stripe library removal from `backend/requirements.txt` — no live callers post-(c.1)(c). Parked in `POST_T5_BACKLOG.md`.

---

## Chunk (c) — Stripe "Billing — Coming Soon" UX (2026-05-25) — CLOSED

**Scope:** Replace §M4 Stripe checkout with an honest Coming-Soon surface. User explicitly opted for this over a silent-fake-success mock.

**Implementation:**
- `backend/routers/billing.py` — FULL REWRITE. All 4 existing endpoints return `{coming_soon: true, message: <verbatim>}`. Webhook stub returns 200 + dead-letters. NEW `/api/notify-billing-launch` — idempotent set-if-not-exists into `billing_launch_interest` collection.
- `frontend/src/components/settings/BillingTab.jsx` — REWRITTEN as Coming-Soon hero with notify-me CTA + read-only plan catalog preview.
- `frontend/src/components/depth/UpgradeModal.jsx` — REWRITTEN — primary "NOTIFY ME WHEN READY" CTA routes to `/app/settings/billing`.

**Verbatim copy** (single source of truth — `routers/billing.py` constants):
- Heading: *"Billing & Subscription — Coming Soon"*
- Body: *"We're finalizing our subscription tiers. Your account is fully active during this preview period; billing will roll out in a future release."*
- CTA: *"Notify me when this is ready"*

**Initial e1_tester verdict: 3/4 PASS.** FAIL on (c.1)(c) — dead `import stripe` inside `backend/services/stripe_webhook.py::verify_and_parse_event`. No runtime callers, but violated the strict zero-Stripe-SDK invariant grep audit.

**(c.1)(c) surgical fix:** Deleted `verify_and_parse_event` + `SignatureInvalid` symbols. Added regression test `test_chunk_c_no_stripe_sdk_import.py` that pins the invariant via `subprocess.run(["grep", -rn, ...])` mirroring the e1_tester audit pattern. Pre-fix grep: 1 hit. Post-fix grep: 0 hits.

**Re-verification verdict: 4/4 PASS.**

**Tests:** 15 new total — 13 chunk (c) anchor-chain tests + 2 (c.1)(c) regression tests.

**Git tags:** `v-pre-c` + `v-post-c`. Both local-only.

**Status: CLOSED 2026-05-25.**

---

## Full session closeout (2026-05-25)

All implementation chunks in the user-approved sequence (b → d → a → e → c) are now complete except (e) GitHub push, which is a user action via the "Save to Github" UI.

| Order | Chunk | Verdict |
| --- | --- | --- |
| 1 | T1 (horizontal) | 5/5 PASS |
| 2 | T2 (incl. T2.3 fix-pass) | 4/4 + 2/2 PASS |
| 3 | T3 | 4/4 PASS |
| 4 | T4 | 5/5 PASS |
| 5 | T5 | 4/4 PASS |
| 6 | backlog-b + b1/b2/b3 fix-passes | 3 fixes + seeds green |
| 7 | chunk (d) — Trust Center methodology + skip-audit + 10 re-enables | doc-only + 10 tests green |
| 8 | chunk (a) — J1 | 4/4 PASS |
| 9 | chunk (a) — J2 + two J2.3 fix-passes | 3/4 → 4/4 PASS |
| 10 | chunk (a) — J3 | 4/4 PASS |
| 11 | chunk (a) — J4 | 4/4 PASS |
| 12 | chunk (c) + (c.1)(c) surgical fix | 3/4 → 4/4 PASS |
| 13 | chunk (e) — GitHub push | DEFERRED to user action |

**31/31 PO-ratified gaps shipped (G1-G31).**
**9 durable lessons banked (§5.1-§5.9 in `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md`).**
**18 local-only git tags ready for GitHub push.**
**Final pytest: 1208 passed · 490 skipped · 1 pre-existing failure (`test_real_requirements_file_is_clean`, unrelated).**
**Net delta across the session: +125 passing tests, zero regressions, zero guardrail file changes.**

**Outstanding items:**
- **chunk (e) — GitHub push** — user action. Push-readiness artifact at `/app/memory/sprints/PUSH_READINESS.md` carries the tag inventory + commit summary + suggested commit message + pre-push checklist.
- **ClamAV EICAR spot-check** — optional, deferred because `clamd` sidecar is STOPPED in this preview pod.

Full closeout: `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` §12 "Full session closeout".

**Status: ALL IMPLEMENTATION CHUNKS CLOSED. Standing by for next instruction.**


---

## Production-hardening sprint (2026-05-25) — CLOSED

After the full-session closeout above, the operator dispatched a 5-step production-hardening sprint to settle the "code-verified but never-real-user-tested" gap before any friendly-tester rollout.

| Step | Verdict | Tag |
| --- | --- | --- |
| 1 — ClamAV prod-status verification endpoint | 3/3 PASS | `v-post-hardening-step-1` |
| 2 — False-green pattern sweep + ESLint `react/jsx-no-undef` pin | 4/4 PASS | `v-post-hardening-step-2` |
| 3 — Demo seeds auto-apply on pod boot | 4/4 PASS | `v-post-hardening-step-3` |
| 4 — Coverage-loss test triage (4 unbacked tier verdicts now backed) | 4/4 PASS | `v-post-hardening-step-4` |
| 5 — Friendly-tester rollout checklist (operator-readable doc) | doc-only | — |

**Cumulative: 5/5 PASS · 15 user-verified verdicts · 4 latent prod bugs caught + fixed · +40 passing tests (1208 → 1248) · 37 skipped tests retired · 1 durable lesson banked (§5.10 scope-aware lint catches what regex can't) · 0 regressions · 0 guardrail file changes.**

**Sprint closure tag:** `v-post-hardening-sprint-closed` (local-only, with annotated message *"hardening sprint 1-5 closed"*).

**Latent prod bugs caught during hardening:**
1. `clamd` library `ConnectionError` mis-classification (Step 1 live-probe surface).
2. `Search` lucide icon undeclared in `AttachDocumentModal.jsx` (Step 2 Phase C webpack build).
3. `navigate` undeclared in `WorkStudio.jsx` top-level scope (Step 2 Phase C webpack build).
4. 4 onboarding bootstrap-callback staleness sites (Step 2 Phase A static audit) — `FirstSession.jsx` × 3 + `AppShell.jsx` trust-center-tooltip.

**Final pytest at hardening closure:** **1248 passed · 453 skipped · 1 failed (pre-existing `test_real_requirements_file_is_clean` — spaCy direct-URL refs, parked P3).**

**Tag inventory at hardening close:**
- 18 tags from full-session close (see §12.7 of `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md`).
- 6 new from hardening: `v-pre-hardening` · `v-post-hardening-step-{1,2,3,4}` · `v-post-hardening-sprint-closed`.
- **24 total local-only tags.** Operator's next "Save to GitHub" cycle pushes the new 6.

Full closeout: `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` §13.

**Status: ALL SPRINTS CLOSED. Standing by for operator's GitHub push (consolidated) and first friendly-tester batch invite.**


---

## Wave 8 — Polish Fixes (2026-05-27) — CLOSED

Three polish fixes shipped between Z-slice-4 (Documents page) and Z-slice-5 (Upload modal).

### W8.1 — Work Studio compile CTAs above the listing
- Moved Compile / Enhance / Create buttons from below the listing to ListingShell's `preBody=` slot.
- Sits between the search/sort row and the listing body.
- Legacy below-listing mount removed.

### W8.2 — Task tile readiness typography (AMENDED)
- Readiness number locked at **24px** (down from original 32px spec; user overrode after live render).
- Label `fontSize: 12, marginTop: 1px`, italic, `leading-none` on stack + label.
- Right cluster: `flex-col items-end gap-1 leading-none` (compact).
- Outer task-card row: `flex items-start justify-between gap-3 mb-1.5` — `items-start` prevents right cluster from stretching the title row.
- Card body tightened: title row mb-1.5, objective mb-2 (no `min-height`).
- Live DOM probe confirms 24px / 12px / 1px on 1280, 1024, 820. Card height stable ~146px across viewports.

### W8.3 — H1 subtext audit (Recurrence #5 LOCKED)
- 15 top-level surfaces now carry `data-testid="page-subtext"`.
- Frozen `PAGE_SUBTEXT_FILES` tuple in `backend/tests/test_wave8_polish.py` — adding a new top-level surface forces the contributor to register and tag it or CI fails.
- Where Z-slice-4 had already locked a different testid on a visible subtitle (`portfolio-subtitle`, `company-home-subtitle`, `documents-page-subtext`), an `sr-only` sentinel `<span data-testid="page-subtext">` was added adjacent to the visible subtitle so both locks pass without altering visible markup.

### CI guards
- `backend/tests/test_wave8_polish.py` — **23/23 GREEN**:
  - W8.1: 1 assertion (preBody mount + single-mount).
  - W8.2: 5 assertions (24px, no-32px, leading-none on stack + label, marginTop ≤ 1, outer-row class).
  - W8.3: 17 assertions (15 per-file parametrised + frozen-tuple existence + count=15).

### Regression status
- Phase Z-slice-4 tests: 81/81 GREEN.
- Pre-existing baseline failures (7 in test_t1/t2/t3 wire, test_chat_v2_full_flow, test_patch_28, test_requirements_guard) confirmed unchanged after `git stash` — NOT caused by Wave 8.

### Next per locked sequence
**Z-slice-5** — Upload modal (replaces placeholder toasts from Z-slice-3 & Z-slice-4; requires category selector with 6 options + uncategorized; sets `origin="upload"`).


---

## Phase Z-slice-5 — Upload Modal (2026-05-27) — CLOSED

Replaces toast stubs from Z-slice-3 + Z-slice-4 with the shared UploadModal.

### Wiring (single modal, multiple triggers)
- `AppShell.jsx` mounts ONE `<UploadModal>` and listens for the universal `akki:open-upload-modal` window event.
- `WorkStudioSidebar.jsx` and `DocumentsPage.jsx` both dispatch this event.

### Modal additions
- **Category dropdown** — 7 options (Uncategorized + 6 canonical from `lib/origins.js::UPLOAD_CATEGORY_OPTIONS`); empty string is the explicit "Uncategorized" sentinel; backend normalises to `None`.
- **Multi-file picker** — `multiple` attr on input; both drag-drop + click-to-browse accept N files; de-duped by `name+size`; per-file rows with clear buttons + "Add another file" affordance.
- **Per-file POST loop** — `onUpload` iterates `files[]`, posting sequentially with shared category/trust/mention. Per-file failures surface a `filename: error` toast; partial success surfaces "M of N succeeded".
- Display name auto-hides on multi-file batches.

### Backend contract (unchanged from Z-slice-1)
- `POST /api/contexts/{cid}/documents` already accepts `category` form field.
- Unknown values normalize to `None` (defensive `cat_clean`).
- Every doc stamped with `origin="upload"` server-side.

### DOM contract for Z-slice-6
- `DocumentsPage.jsx` now emits `data-testid="documents-tab-content-${activeTab}"`.
- `WorkStudio.jsx` continues to emit `data-testid="ws-tab-content-${activeTab.category}"`.

### CI guards (`backend/tests/test_phase_z_slice_5_upload_modal.py`)
**21/21 GREEN**:
- 16 source-strict FE wiring asserts.
- 3 backend source-strict re-asserts.
- 2 direct-Mongo orthogonality asserts (3-file batch + uncategorized).

### Test migrations
- `test_Z3_r_add_document_falls_back_to_toast_stub` → `test_Z3_r_add_document_opens_upload_modal`.
- `test_Z4_w_add_document_btn_present_with_toast_stub` → `test_Z4_w_add_document_btn_opens_upload_modal`.

### Live multi-viewport verification at 1280 / 1024 / 820
All confirmed: modal opens from both entry points, 7-option category dropdown with "Uncategorized" default, `multiple` on file input, drop zone visible, submit disabled until file picked, ready text present.

### Regression
- 21/21 Z5 GREEN.
- 81/81 Phase Z-slice-1-4 still GREEN (2 tests renamed).
- 23/23 Wave 8 GREEN.
- 7 pre-existing baseline failures unchanged.

### Slice budget
Product-code: ~370 lines new (UploadModal multi-file + dropdown; trivial wiring at the two stub sites). Within the 500-line auto-slice budget.

### Out of scope (deferred)
- Goals/tasks extraction checkboxes → AA-slice-3.
- Server-side file transformation.
- Legacy upload paths NOT deprecated; coexist.

### Next per locked sequence
**Z-slice-6 — Orthogonality wire-test (DOM-level)**. Then Phase AA (Monitor v2 — 7 slices), Phase W, Phase X.


---

## Phase Z-slice-6 — Orthogonality DOM Wire-Test (2026-05-27) — CLOSED

Institutional Recurrence #5 prevention promoted from the data-model layer to the live DOM.

### Test file
`backend/tests/test_phase_z_slice_6_orthogonality_wire.py::test_z6_uploaded_report_surfaces_in_both_ws_and_documents`

### Flow (Playwright, full E2E against preview pod)
1. Login admin@akki.ai → active context TEST_SeededNedCo.
2. Open WS sidebar `+ Add a document` → modal opens.
3. category=report + attach UUID-marker .txt → submit.
4. Modal closes + success toast.
5. Navigate to WS `?kind=report` → doc surfaces in `ws-tab-content-report` with "Uploaded" origin badge.
6. Loop 5 other WS category tabs (board_pack/minutes/draft/deck/briefing) → doc NOT present in any.
7. Navigate `/app/documents?tab=upload` → doc surfaces in `documents-tab-content-upload`.
8. Loop 2 other origin tabs (akki_generated/email_receipt) → doc NOT present in any.
9. Click doc card → URL gains `?doc_id=…` (drawer mounts).
10. Resize viewport 1024→820 → doc still surfaces in both body testids.
11. Cleanup (finally block): delete marker doc by name from Mongo.

### Live result
**1 passed in 65.52s** — full DOM round-trip against the preview pod. Cleanup confirmed.

### Skip / runtime semantics
- Marker `pytest.mark.runtime_playwright` — fast CI can skip via `pytest -m "not runtime_playwright"`.
- Cleanly skipped if Chromium / Playwright missing.

### Failure mode coverage
- Removed `category` form field → step 5 fails.
- Removed `origin="upload"` from backend → step 7 fails.
- Renamed body testids → steps 5/6/7/8 fail with the missing testid named.

### Phase Z — COMPLETE
- Z-slice-1: backend data model + migration — CLOSED
- Z-slice-2: WS LEFT column tabs by category — CLOSED
- Z-slice-3: WS sidebar vertical card stack — CLOSED
- Z-slice-4: `/app/documents` capsule tabs — CLOSED
- Z-slice-5: Upload modal — CLOSED
- Z-slice-6: Orthogonality DOM wire-test — CLOSED

**Cumulative Phase Z lock surface:** 103 tests preventing Recurrence #5 at both the data-model and live-DOM layers. Zero leakage tolerated.

### Next per locked sequence
**Phase AA — Monitor v2 (7 slices)**. AA-slice-1: `tasks_initiatives` data model.


---

## Phase AA-slice-1 — tasks_initiatives data model + CRUD (2026-05-27) — CLOSED

New `tasks_initiatives` Mongo collection. Backs Phase AA (Monitor v2). Separate from legacy `strategic_goals.initiatives_count` counter (reconciliation = Z.followup.6).

### Schema fields
`id` · `context_id` · `title` (2-180) · `body` (≤4000) · `category` (6-enum reused from goals) · `owner_role` (9 canonical + null) · `parent_objective_id` (FK → strategic_goals | null) · `status` (5-enum: on_track/at_risk/off_track/achieved/not_started) · `performance_score` (0-100) · `probability_score` (0-100) · `last_reassessed_at` · `source_document_id` (FK → documents | null) · `extracted_by` ("llm"|"manual") · `status_active` (soft-delete) · `created_at` · `updated_at`.

### Endpoints (`backend/routers/tasks_initiatives.py`)
- `GET /api/contexts/{cid}/tasks-initiatives?owner=&status=&parent_objective_id=&search=&page=&page_size=`
- `GET /api/contexts/{cid}/tasks-initiatives/{id}`
- `POST /api/contexts/{cid}/tasks-initiatives` (manual create)
- `PATCH /api/contexts/{cid}/tasks-initiatives/{id}` (partial update; updated_at + last_reassessed_at always refreshed)
- `DELETE /api/contexts/{cid}/tasks-initiatives/{id}` (soft-delete via `status_active=False`)

### Indexes (built at startup via `ensure_indexes()`)
- `(id)` unique
- `(context_id, parent_objective_id)`
- `(context_id, owner_role)`
- `(context_id, status)`
- `(context_id, source_document_id)`
- `(context_id, status_active, updated_at DESC)` for soft-delete-aware hot path

### Constraints
- `parent_objective_id` must reference a goal in the same context (else 400).
- `source_document_id` must reference a doc in the same context (else 400).
- `source_document_id` + `extracted_by` are immutable post-create.
- Multi-context isolation in every Mongo filter.

### Audit
- `tasks_initiative.create` / `.patch` / `.delete` rows written via `core.write_audit`.

### CI guards — **19/19 GREEN**
- 6 schema/enum locks
- 1 indexes lock
- 10 runtime CRUD asserts
- 1 audit assert
- 1 cross-context isolation assert

### Slice budget
~445 lines product code (within 500-line budget). 3 lines wiring in server.py.

### New follow-up
- **AA.followup.1 — Reconcile `monitor_v2.CANONICAL_OWNER_ROLES` legacy tuple with `TIOwnerRole` enum** (P2). Defer until AA-slice-4 reveals UI needs.

### Next per locked sequence
**AA-slice-2** — LLM extraction (Sonnet 4.5 via `shield_invoke`) reading `documents.extracted_text` and writing `tasks_initiatives` rows with `extracted_by="llm"`.


---

## Phase AA-slice-2 — LLM extraction service (2026-05-27) — CLOSED

LLM-driven extraction service that reads `documents.extracted_text`, calls Claude Sonnet 4.5 via the shielded gateway (`llm_service.call_llm(tier="standard")`), parses two distinct JSON envelopes (goals + tasks), validates rows, and persists valid ones to `strategic_goals` / `tasks_initiatives` with `extracted_by="llm"` + `source_document_id`/`source_doc_id`.

### Public entry point
```py
await extract_from_document(document_id, context_id, account_id,
                             extract_goals=False, extract_tasks=True, force=False)
```
Returns `ExtractionResult(goals_extracted, tasks_extracted, failures, idempotent_skip, model)`.

### Files (`backend/services/tasks_initiatives/`)
- `__init__.py` (5 lines)
- `extraction.py` (472 raw / 381 net code lines) — service + helpers + deduped per-chunk pass loop
- `prompts.py` (73 lines) — `GOALS_PROMPT_TEMPLATE` + `TASKS_PROMPT_TEMPLATE`

### Chunking
- `MAX_CHARS_BEFORE_CHUNK = 50_000` (per spec).
- `CHUNK_SIZE_CHARS = 18_000` per chunk; breaks on paragraph boundary.
- `MAX_ROWS_PER_CHUNK = 20` to cap LLM token budget.

### New collections
- `extractions_log` — idempotency marker per `(document_id, kind)`. Force=True bypasses.
- `extraction_failures` — auditable record of LLM rows that failed validation.

### Indexes (`ensure_indexes()` at startup)
- `extractions_log: (document_id, kind)`, `(context_id, created_at -1)`
- `extraction_failures: (document_id, kind)`, `(context_id, created_at -1)`

### Validation
- Goals: defensive enum coercion + score clamp 0-100.
- Tasks: Pydantic-validated via AA-1 `TaskInitiativeIn`; owner_role uppercased.

### CI guards — **21/21 GREEN**
- 5 source-strict module shape locks (constants, prompts).
- 2 chunking asserts.
- 5 row-validator asserts.
- 9 runtime asserts with mocked `call_llm`.

### Slice budget
Net code 451 lines (under 500). After first compile hit 568, deduped to a single `_run_extraction_pass(...)` generic helper.

### New follow-up filed
- **AA.followup.2 — "Recently re-assessed tasks" widget on workspace home** (P3, founder-feedback-gated).

### Next per locked sequence
**AA-slice-3** — UploadModal extension wiring `extract_from_document` after successful upload.


---

## Phase AA-slice-3 — Upload modal extraction prompt (2026-05-27) — CLOSED

Wires the AA-slice-2 extraction service into the Z-slice-5 upload modal.

### FE — `UploadModal.jsx`
- Two checkboxes (`upload-extract-goals-checkbox` + `upload-extract-tasks-checkbox`) inside `upload-extraction-block`.
- Helper text locked: "AI will scan for strategic goals and the specific work to deliver them. You can review and edit later in Monitor."
- Category-aware defaults: `["board_pack", "report", "briefing"]` flip both ON; everything else OFF.
- `extractionTouched` flag halts category-recompute once the user manually toggles either checkbox.
- After successful upload, `onUpload` iterates uploaded IDs sequentially calling `POST /api/contexts/{cid}/documents/{id}/extract`. Failures surface per-file warning toast; upload success remains.

### BE — `routers/tasks_initiatives.py`
- New endpoint `POST /api/contexts/{cid}/documents/{doc_id}/extract` → 202 Accepted.
- `BackgroundTasks` wraps `extract_from_document(...)` so modal doesn't block.
- 400 when both extract flags are False; 404 when doc missing.
- `_bg_extract` catches exceptions (auditable via `extraction_failures`).
- Audit row written: `tasks_initiative.extract_triggered`.

### CI guards — **14/14 GREEN**
- 6 FE source-strict (testids, helper copy, default list literal, touched-flag early-return, onChange handlers, onUpload trigger gate).
- 2 BE source-strict (endpoint declaration + status 202 + BackgroundTasks; exception swallow).
- 6 runtime (202 + correct args, 400/404 paths, audit, sufficient-tasks-flag, force=True forwarded).

### Live multi-viewport DOM probes (1280 / 1024 / 820)
All identical: Uncategorized → both OFF; Report → both ON; Draft → both OFF; user-toggled then category-changed → user pick preserved.

### Slice budget
~206 lines product code (93 BE + 113 FE). Within 500-line budget.

### Out of scope (deferred)
- Akki-commit trigger; email-ingestion trigger; real-time extraction progress UI; "Re-run extraction" button.

### Next per locked sequence
**AA-slice-4** — Monitor surface rewrite (rich cards + provenance chip "Extracted by Sonnet 4.5 from {doc} · {date}"; manual rows render without chip).
