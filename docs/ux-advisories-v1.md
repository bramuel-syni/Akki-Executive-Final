# AKKI · UX Advisories v1

The in-product design rules. Mirror of `homepage-positioning-v1.md`. The next person designing an AKKI surface argues against this; they do not start from scratch.

## Buyer (single, abstract — matches homepage v1)
Operating executives (CEO, CFO, CHRO, CTO, COO) and non-executive directors (Chairs, NEDs) at listed and pre-IPO companies. Role-light by default; role-shaped emphasis only where telemetry proves divergence.

## The 9 modalities
Ordered by load-bearing-ness, not feature weight.

1. **Home / Entry** — a river of what changed, not a dashboard.
2. **Reading (Workspace in nav)** — document + commentary rail.
3. **Conversation (Ask / Chat)** — Claude-shape with citation chips + mode selector.
4. **Approval (Daily Review)** — the load-bearing modality. One screen, keyboard-first, batched.
5. **First Session** — a guided conversation that ends with one artefact.
6. **Cycle** — horizontal timeline strip, named phases, per-context.
7. **Governance** — quiet system-utility, not marketing.
8. **Depth** — Lens / Simulate / Influence Map / Strategic Goals / Plays. Disclosed on threshold.
9. **Studio / Composition** — draft → refine → distribute. Sensitivity + read-receipt inherent.

## Locked defaults (v1)

### Nav + information architecture
- Primary left nav labels: **Home · Workspace · Cycle · Studio · Chat**. Below divider: **Depth** (expands when corpus threshold crossed).
- Top bar: **Logo · Context switcher · ⌘K Search/Ask · Daily Review badge · User menu**.
- ⌘K: typing runs BM25 local search; ↵ or "Ask AKKI" button escalates to LLM.
- Reading canonical surface: `/app/documents/:id` (merged). `/app/workspace` is the corpus browser + Ask.

### Approval (the load-bearing modality)
- Daily Review at `/app/review`. Badge in top bar shows count.
- Phase A queue items (v1): **Inbound-docs awaiting file + Briefings awaiting review.**
- Phase B queue items (later, backend-blocked): drafted emails, extracted cycle questions.
- Three actions only: **Approve (oxblood) · Edit (navy, opens inline side-panel) · Reject (muted).**
- Keyboard: ⏎ approve, e edit, x reject, ↑↓ navigate, esc exit.
- No inline approval toasts elsewhere in the product.

### Cycle
- 6-phase default per context: **Pack arriving · Reading week · Pre-board · Meeting · Minutes · Follow-up.**
- Per-context override in tenant settings.
- Schema: new collection `db.cycle_configs` keyed by `context_id`.

### Governance
- **De-identification scope: per-context default with per-message override.** Persisted per message in `db.chat_messages.shielding_override`.
- Top-bar chip: **"Shielded"** in accent when context default is on. When per-message override is active, chip dims to muted grey with tooltip "Override active for this turn."
- Audit log + sensitivity settings + avatar + inbound mgmt + connected models live in top-right user menu → "Trust" panel.

### Depth
- Threshold: **3 documents ingested OR 1 briefing generated**, whichever first.
- Disclosure: one offer at a time, phrased as invitation not menu.
- Sector defaults for the auto-suggested lens: Banking → Risk · SaaS → Growth · Healthcare → Compliance · Other → Audit Committee.
- Pro-gated features show inline **"Pro" pill**; click opens upgrade modal (no locked-icon overlay).

### Composition (Studio)
- v1 block library: **paragraph · heading 2 · heading 3 · callout · citation · signal-card · divider.**
- No image / table / embed blocks at v1.
- Schema: new collection `db.studio_blocks` per artefact.
- Sensitivity auto-classification on save. Read-receipts on share.

### Chat
- Citation chips at the end of every corpus-grounded response. Click chip → opens Reading modality at cited paragraph.
- Mode selector above input: **Ask · Solve · Draft.**
- No voice input. No image generation. No plugins.
- Chat history: top-right "Recent" dropdown (max 8), "View all →" link to `/chat`. No sidebar competing with Home.

### First Session
- 3-question intake (down from 7): **role · primary board/company · one-sentence top-of-mind.**
- Remaining onboarding questions asked on-demand when first document uploaded.
- 3 doors: forward email · upload · run Solve. Mobile downgrades upload.
- Ends with one artefact + 3-sentence rhythm explanation + exit.

### Mobile (Q1 commitment)
- **Reading**: document body full-width, right rail becomes bottom drawer (Apple Books style), citations inline.
- **Approval**: same focused queue, actions stacked vertically, swipe gestures optional.
- Studio + Cycle can be desktop-first.

## Editorial rules
- Voice: Financial Times leader column.
- Cream / oxblood / navy palette only. Georgia serif heads. No new tokens.
- Empty states: one sentence + one action. Never a feature tour.
- Loading: editorial voice, not spinners ("Reading the pack...", "Comparing across documents...").
- Errors: honest, not cute. "AKKI couldn't reach the document. The source link may have expired."
- No gamification. No badges. No completion bars. No streaks.
- No real-time collaboration. No cursors. No typing indicators.
- No emojis in UI copy.
- No exclamation marks in body copy.

## Execution order (Phase 1)
1. **Reading Viewer (Advisory 2)** — first, pairs with paragraph-anchor schema work.
2. **Cycle strip (Advisory 6)** — second, pairs with `cycle_configs` schema.
3. **Daily Review Phase A (Advisory 4)** — third, uses existing inbound_queue + briefings data.

All other advisories (1 Home, 3 Chat refactor, 5 First Session rewrite, 7 Governance panel, 8 Depth disclosure, 9 Studio composition) wait until 1–3 are shipped and observed.

## Things deferred to v2
- Advisory 7 live de-id badge (blocked on Synisense live-URL swap)
- Advisory 9 public Chair view (blocked on `GET /api/public/studio/read/{token}`)
- Advisory 2 validator-confirmed-signal in rail (blocked on validator running on Decks/Reports/Solve — today only Briefings)
- Advisory 4 Phase B drafted-emails (blocked on cycle reply ingestion + in-app share email — both stubs today)

## Validation
A modality is correct when:
- It has one primary action.
- It is usable by someone who has never read AKKI's marketing.
- Its citations are visible without special interaction.
- It compiles down to the palette + serif + tokens already in the design system.

## Rejected v1 UX directions (do not re-propose without new evidence)
- Three-pane collaboration UI (cursors, presence) — not the voice.
- Gamification (badges, streaks, percent-complete) — infantilising for this buyer.
- AI-voice interaction — unshippable for the audit-trail contract.
- Chat-history sidebar — competes with Home.
- Feature tours and tooltip chains — the first session ends with one artefact, not a tour.
- Per-surface primary nav (Lens, Simulate, etc.) — depth disclosed, not flaunted.

## Changelog

### v1.1 — Phase 1: Reading Viewer
- Schema: `db.documents.paragraphs[]` added with stable hash IDs.
- Endpoint: `GET /api/contexts/{cid}/documents/{doc_id}/paragraphs` (lazy-compute).
- Cron: `POST /api/cron/paragraph-anchors-sweep` (daily 03:00 UTC).
- UI: `ReadingView.jsx` shipped behind `?v=2`. Old DocumentViewer stays at default until the v2 default flip in next release.
- Citation contract: signals / ask / briefings now include `references[]` with optional paragraph_id.
- Mobile: Reading is mobile-shippable. Bottom drawer for commentary.
- Deferred: validator-confirmed signal in rail (still only running on Briefings); paragraph-level LLM prompts (next pass).

### v1.2 — Phase 2: Cycle strip + cycle_configs schema
- Reading Viewer is now the default at `/app/documents/:id`. Legacy at `?v=1` for one week.
- Schema: new `db.cycle_configs` collection per context, with 6-phase default.
- Endpoints: `GET/PUT /api/contexts/{cid}/cycle-config`, `POST .../advance`, `POST .../reset`, `GET .../phases/{phase_id}/summary`.
- UI: Horizontal `CycleStrip.jsx` component pinned at top of Home + `/app/cycle`. Click a phase → Sheet with artefact summary.
- Tenant settings: `/app/settings/cycle` — owner/admin can rename, reorder, change durations, reset.
- Mobile: strip is horizontally scroll-snap; side-panel becomes bottom Sheet.
- Deferred to v2: previous-cycle history (cycle_offset < 0), full filtered Workspace view from phase summary.

### v1.3 — Phase 3: Daily Review (Phase A) + DocumentViewer cleanup
- Legacy DocumentViewer removed. ReadingView is the only document viewing surface.
- New unified `/app/review` queue across inbound docs + briefings awaiting review.
- Endpoints: `GET /api/me/review-queue`, `GET .../counts`, `POST .../items/{kind}/{id}/{approve|reject|edit}`.
- Top-bar badge polls counts every 60s; click → /app/review.
- Keyboard-first: ⏎ approve, e edit, x reject, ↑↓ navigate, esc exit.
- Phase B (drafted emails, extracted cycle questions) still deferred — backend pipelines stubbed.

### v1.4 — Phase 4: First Session rewrite
- Legacy 7-question Onboarding replaced by First Session: 3-question intake + 3 doors + one AKKI-generated artefact + rhythm explanation.
- New endpoints: `GET /api/me/first-session`, `POST .../start`, `.../intake`, `.../choose-door`, `.../complete`, `.../skip`.
- Account schema: new `first_session` sub-doc tracks state (`status`, `current_step`, `door_taken`, `artefact`, `intake`).
- Existing onboarded users (legacy `context_object.completed=true` OR any context with `progress_state.onboarding_completed=true` OR superadmin) are auto-marked `status: "skipped"` on first `/auth/me` call — grandfathered, no UI change for them.
- `POST /sandbox/convert` now returns a `prefill_first_session` map so sandbox-converted users see role + company name + objective already filled in (editable).
- Deferred questions (jurisdiction / board_count / sector_depth / industry_depth) now surface as on-demand prompts after first document upload (hook in place; triggering logic to be wired in the next pass).
- Door step: email card emphasised on mobile (shows inbound address + copy button), upload de-emphasised ("Easier from desktop."), Solve card redirects to `/app/solve?intent=<top_of_mind>`.
- Frontend route `/app/first-session` (protected); `FirstSessionGuard` in `App.js` forces redirect from any `/app/*` route until completed or skipped. Exceptions: `/app/first-session` itself, `/app/settings/*`, `/app/security`, `/app/review`.
- Legacy `/onboarding` → 301-style redirect to `/app/first-session`. Files removed: `pages/Onboarding.jsx`, `lib/onboardingQuestions.js`.
- Post-signup redirect changed: `/signup` → `/app/first-session` (was `/onboarding`).

### v1.5 — Phase 5 Part B: Home v2 (river of changes)
- Behind `?home=v2` flag (no-op for sandbox accounts which keep v1).
- 3-column desktop layout: 240 px context rail · main river · 320 px awaiting-you rail (auto-hides when empty).
- Reverse-chronological stream of document/signal/briefing/mention cards, dense typography-led, no thumbnails.
- Empty state: single editorial line + inbound-address CTA, no checklists.
- `/api/me/home/stream` extended additively with `documents[]`, `approvals[]` (cap 5), optional `cursor` param + `next_cursor` response field.
- Phase 2 CycleStrip pinned at top (preserved). Phase 3 ReviewBadge in AppShell (untouched).
- Removed from v2 Home: InSummaryTiles, WorkflowsHub, ReviewInboxCard, DraggableHomeBoard, NextBestActionCard, first-time-user fallback, scope toggle. Sandbox flow on v1 untouched.
- Top bar + left nav: hands-off this phase (horizontal-nav rework deferred).
- LegacyAppHome.jsx extracted byte-identical from the old AppHome.jsx; new AppHome.jsx is a 30-line flag-reader wrapper.
- Default flip from v1 → v2 scheduled one week post-ship.

### v1.6 — Phase 6: Depth disclosure (Advisory 8)
- New endpoint `GET /api/me/depth-status` returns `{eligible, threshold, suggested_offer, offer_dismissed, pro_features}`. Eligibility = ≥3 documents OR ≥1 briefing across the user's active contexts (briefings preferred as `threshold_met_via` when both apply).
- New endpoint `POST /api/me/depth-status/dismiss` sets `db.accounts.{id}.depth_offer_dismissed_at = now()`. Sticky until manually cleared.
- Sector → lens mapping: Banking/FS/Fintech→Risk · SaaS/Tech→Growth · Healthcare/Pharma→Compliance · everything else→Audit Committee. Read from the user's primary (oldest-active) context's `sector`.
- AppShell left rail: Lens / Simulate / Monitor / Influence Map pulled out of base NAV and rendered under a "DEPTH" divider only when `eligible === true`. Routes stay URL-accessible regardless (bookmarks don't break).
- Pro-gated features (Lens, Simulate) render an inline ProPill next to the nav label for free-plan users. Clicking a gated nav item intercepts navigation and opens the UpgradeModal.
- Home v2: single `DepthOfferCard` above the river. One sector-correct lens offered, two CTAs (Run or Not now). Dismissal persists server-side + invalidates the session cache.
- UpgradeModal: Radix Dialog, Georgia-serif heading, 3-line body, two CTAs (mailto enterprise, /plans). No fake pricing, no comparison table.
- Depth cache is per-session (`useDepthStatus`), keyed on `account.id`. Eligibility is sticky; a minute of staleness on nav gating is harmless.

### v1.7 — Phase 7: Governance panel (Advisory 7)
- New "Trust" item in top-right user menu opens a Sheet (right side on desktop ~520 px, bottom sheet on mobile). NOT in primary nav — system-utility feel.
- 5 sections inside the panel:
  1. **Audit log** — total entries, most-recent 10, filterable by action/date, ZIP export (CSV + manifest.txt).
  2. **De-identification** — static "SHIELDED · REGEX" chip + italic note that the live Synisense badge ships later.
  3. **Inbound email** — monospace address with copy button (mints the token lazily if absent, same pattern as `/api/inbound/address`).
  4. **Connected models** — reads `SUPPORTED_MODELS` from `routers/chat.py` so the list never drifts; decorated with "used in" surfaces.
  5. **Sensitivity at a glance** — 4 tiles (Public / Internal / Confidential / Restricted), last-classified timestamp. Honest zeros when the classifier hasn't run yet.
- New endpoints: `GET /api/me/governance`, `GET /api/me/governance/audit?action=&since=&until=&cursor=&limit=`, `POST /api/me/governance/audit/export`. No new collections, no new schema.
- Export format: ZIP containing `audit_log.csv` + `manifest.txt` (actor email, filter window, row count). Same pattern as `/chats/{id}/audit/export.zip`.
- Quiet-system register: no oxblood emphasis, no spinners, no emojis. Editorial loading copy ("Reading your trust ledger…").
- Live de-identification badge in the top bar deferred to v2 (waits for Synisense live service URL).
