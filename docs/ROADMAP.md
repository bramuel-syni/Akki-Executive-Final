# AKKI Production Roadmap — Phases 12 through 19 (Phase A cleanup applied)

**Status:** Approved by product owner. Single-approval execution. Each phase closes cleanly before the next. Decision points are flagged; all other scope is locked.

**Phase A (post 15.3.5) — Cleanup & 12.3 close — applied 2026-05-04+.**
Deletes `_legacy/` archive, retires v1 Solva POSTs (read-only GETs preserved), drops the `/api/solve` 308 alias and the `solva_v2_poc` feature flag, renames `SolvaV2Poc → SolvaApp`, unifies PII shielding onto `services/synisense`, flips typography from Inter to Calibri (system stack), and closes Phase 12.3 doc drift.

**Phase B (post-A) — 15.3.5 stragglers + Sandbox hotfix — applied 2026-05-05.**
Chat soft-delete + 30-day retention cron, native SSE streaming chat, no-opinion Solva audit + regression test, AppHome consolidation refactor, Sandbox unsafe-uploads + local-storage dev-pod hotfix, `DEV_POD_CAVEATS` runbook, Postmark + Resend keys injected.

**Phase I — Solva v3 UX rebuild — applied 2026-05-05.**
Five sub-steps:

| # | Title | Outcome |
|---|---|---|
| I.1 | Landing simplification | New centred 4-card picker at `frontend/src/components/solva/SolvaLanding.jsx` (446 ll.); B.4 right panels (`RecentSessionsPanel`, `SessionHealthPanel`, `MarketingExplainer`) deleted. Card 04 user-facing label = "See Different Perspectives" (backend key `get_perspective` preserved). Recent Sessions are collapsible. |
| I.2 | Guided Flow state machine | New `frontend/src/lib/solvaFlow.js` reducer (303 ll., 36 jest tests). 14-state sequence `LANDING → FRAMING → Q1 → Q2 → Q3 → DEPTH_Q1 → DEPTH_Q2 → DEPTH_Q3 → PREPARING → ARTEFACT → REFLECT_1 → REFLECT_2 → REFLECT_3 → COMPLETE`, plus `ARTEFACT_REFUSAL` interrupt. New `frontend/src/pages/SolvaSession.jsx` page mounts at `/app/solva/session/:sessionId` and `/app/solva/session/new`. Cluster picker is gone from the UI; backend resolves a cluster from intent text via the new `_resolve_auto_cluster` keyword heuristic when `auto_cluster=true` (default in `StartV2In`). 5 flow components in `frontend/src/components/solva/flow/` (FramingScreen, QuestionScreen, PreparingInterstitial, ReflectionScreen, ProgressIndicator + Shell + PrimaryButton). |
| I.3 | Artefact composition | 5-section composition view: masthead, primary diagnosis, scenarios with animated probability bars, sensitivity drivers callout, surfaced tensions callout. New `frontend/src/components/solva/artefact/{SolvaArtefact, ProbabilityBar, ReasoningExpandable, SolvaRefusalArtefact}.jsx`. New shaping endpoint `GET /api/solva/v2/sessions/{sid}/artefact-reasoning` groups `reasoning_audit_log` into 4 sub-sections (candidates / triangulation / weighting breakdown / log entries). Bars animate 600 ms ease-out (instant under `prefers-reduced-motion`). |
| I.4 | PDF + DOCX export + Refusal artefact | `weasyprint>=60.0` added to `backend/requirements.txt`; `python-docx==1.2.0` reused. Two new endpoints `GET /api/solva/v2/sessions/{sid}/export.pdf` and `.docx` (auth-gated, refusal sessions automatically use the 4-section refusal anatomy and `X-Solva-Artefact: refusal` header). Implementation in `backend/solva_artefact_export.py` + Jinja2 templates `backend/templates/solva_artefact.html` and `solva_refusal_artefact.html`. Download dropdown (PDF / DOCX) in artefact masthead. Refusal artefact UI variant at `SolvaRefusalArtefact.jsx`. Tests: `backend/tests/test_phase_i_solva_export.py` — 13 tests, all pass. |
| I.5 | Reflection, A11y, sweep | 3-question reflection screen (`ReflectionScreen.jsx`) wires REFLECT_1..3 with locked text per brief §6 (refusal variant carries the alternative first question). On REFLECT_3 exit → returns to artefact with a 1.5 s "Session saved" toast. Skip option present but muted. Keyboard nav: Tab traversal, Enter / Ctrl+Enter to submit, Escape to skip. ARIA labels on probability bars (`role="img"` with full label) and reasoning expandable (`aria-expanded`, `aria-controls`). `prefers-reduced-motion` honoured by `usePrefersReducedMotion` hook + `transition: none` fallbacks across all motion. WCAG AA contrast audit at `backend/scripts/contrast_audit.py` — 20 specific surface combinations all PASS; introduces `ACCENT_DARK = #B85230` for interactive fills (4.90:1 on white) while keeping the brand `ACCENT = #C25A38` for kickers / dividers (large-text 3.82:1 on CREAM). |

**Brief-conflict resolved:** the Solva UX Redesign Brief specifies `ACCENT = #C25A38` AND WCAG AA contrast. White text on `#C25A38` ratios at 4.36 — below AA's 4.5 threshold for normal text. Kept the brand `ACCENT` for decorative kickers/dividers/callout rules (where the kickers are 13–14 pt italic / large text); introduced `ACCENT_DARK = #B85230` (sub-perceptually different) as the fill for buttons + refusal pill, which ratios 4.90:1 on `#FFFFFF`. Logged at `frontend/src/components/solva/flow/tokens.js` line 18-22.

**Phase J — Sandbox v2 rebuild — applied 2026-05-05.**
Six sub-steps. Step 2 (Pulse) is intentionally deferred to **Phase D.2** — the
state machine reserves `STEP_2_PULSE` / `STEP_2_REVEAL` but the FORWARD map
skips from `STEP_1_REVEAL` directly to `STEP_3_STUDIO` (see comment at
`frontend/src/lib/sandboxV2Flow.js:36`).

| # | Title | Outcome |
|---|---|---|
| J.1 | Welcome step + state machine + persistence | New `frontend/src/pages/SandboxV2.jsx` mounted at `/sandbox` (legacy preserved at `/sandbox/legacy`). Pure reducer at `frontend/src/lib/sandboxV2Flow.js` (28 jest tests, all pass). 4-question Welcome (`WelcomeStep.jsx`). Backend `sandbox_v2_sessions` collection with TTL on `expires_at` (7 days). 5 endpoints: `POST /api/sandbox/v2/sessions`, `GET/PATCH /api/sandbox/v2/sessions/{sid}`, `POST /api/sandbox/v2/sessions/{sid}/exit`. |
| J.2 | Step 1 Solva wrapper + reusable Reveal | `Step1SolvaWrapper.jsx` wraps the Phase I Solva v3 flow with sub-module forced to `develop_strategy`, picker hidden, `sandbox: true` flag, 3-question compression (no depth round). Pre-loads opening-question + fallback-situation from corpus via the new GET endpoints. Refusal path renders `SolvaRefusalArtefact` and surfaces a brief-locked voice line. `StepReveal.jsx` is the reusable reveal component — Georgia 28 px bold title, Georgia 18 px italic body, 800/400/600 ms fade timing, `aria-live="polite"` status region carrying the full reveal text from frame 0, `prefers-reduced-motion` snaps to final state. |
| J.3 | Step 3 Work Studio split | `Step3StudioWrapper.jsx` 2-column split: source chips (left, click-to-expand modal) vs composition (right). Composition phases: 5 narration lines rotating over ~75 s under `aria-busy=true`, then composed-draft reveal with `[Doc N]`-style marker hover-citation, then provenance probe ("Add a sentence" → POST `/api/sandbox/v2/sessions/{sid}/studio/add-sentence`). Backend keyword-overlap check refuses unsourced claims using the corpus's per-context refusal voice (`pick_provenance_refusal(role, org_type)` — Bank uses the pack verbatim; other contexts use the same FT cadence generalised). |
| J.4 | Step 4 Cycle snapshot + Closing + save-and-send | `Step4CycleSnapshot.jsx` is a read-only static snapshot rendered from `pick_cycle_snapshot(role, org_type)` via `GET /api/sandbox/v2/sessions/{sid}/cycle-snapshot`: Timeline / Open items / Strategic baseline / Pulse-derived items, with the corpus's `voice` field used verbatim as the top banner ("This is a snapshot of what your Cycle Manager would look like after three cycles in Akki…"). `ClosingStep.jsx` surfaces the user's `hope` answer back to them, then a 3-CTA equal-weight conversion block (Demo / Early access / Save & send). Save-and-send POSTs to `/api/sandbox/v2/sessions/{sid}/save-and-send` which: persists the captured email, builds a resume URL (`PUBLIC_APP_URL/sandbox/resume?token=<sid>`), best-effort attaches the Solva v2 PDF if a `solva_session_id` was minted in Step 1 (via `solva_artefact_export.build_pdf` on a thread), and returns one of `{sent, noop, test_mode_restricted, error}`. The new `test_mode_restricted` mode is surfaced by `email_service.send_email` when Resend rejects the recipient under its test-key constraint; the UI renders a friendly "session is saved — bookmark the resume link" notice rather than a hard error. |
| J.5 | Sandbox Content Pack ingestion | `backend/sandbox_v2_corpus.py` (1,443 ll.) carries the 5 verbatim contexts (Mara Heritage Bank, Lenana Health Group, Korogocho Logistics Group, Tahidi Systems, Ministry of Industrial Modernisation) and the strict fallback routing rules: Pre-IPO → Bank, Listed corporate (operational role) → Logistics else Bank, Other → Technology. Public surface: `route_org_type`, `route_role`, `pick_opening_question`, `pick_fallback_situation`, `pick_pulse_signals`, `pick_studio_sources`, `pick_composed_draft`, `pick_provenance_refusal`, `pick_cycle_snapshot`, `corpus_health`. |
| J.6 | Visual register, motion, ARIA, contrast audit | Backgrounds: Welcome PAPER / Step 1 + Reveal CREAM / Step 3 + Reveal LIGHT / Step 4 + Reveal PAPER. Progress chrome and Exit Sandbox link visible on Steps 1/3/4. ARIA live regions on every reveal (`role="status" aria-live="polite"`) and on the Step 3 narration. `backend/scripts/contrast_audit.py` extended with 21 Sandbox v2 surface combinations — all PASS WCAG AA. |

**Tests on close:** 29/29 backend (`backend/tests/test_phase_j_sandbox_v2.py`), 28/28 frontend reducer (`frontend/src/lib/__tests__/sandboxV2Flow.test.js`), `pip check` clean, ruff + ESLint clean on every modified file, `/api/health` 200, `/openapi.json` 200, `/docs` 200. The 2 unrelated legacy `test_sandbox_phase{1,2}.py` failures (`test_bramuel_cookie_login_still_works_and_has_no_sandbox_flag`, `test_non_sandbox_caller_returns_400`) are pre-existing and out of scope per the C/D/F/E/G/H/I no-touch rule.

**Brief-conflict resolved:** the Sandbox Content Pack supplies per-context demo content (opening questions, source documents, composed paragraphs, refusal voices, cycle data) but does not carry the structural reveal copy, closing CTA labels, or hope-loop wrapper. The "DO NOT draft new strings" rule applies to demo content. Structural reveal/CTA copy is kept compact and brand-aligned and is surfaced as `title`/`body` props on `StepReveal` so editorial can swap without rebuilding. The Cycle banner uses the corpus's `voice` field verbatim — no client-side string drafted.

**Source-of-truth documents:**
- `AKKI_Objectives_Discovery_Rewrite.docx` — product vision, persona tiers, 4 modules + 2 surfaces
- `Solva_Developer_Brief_v2.docx` — Solva v2 architecture, reasoning engines, grounding contract
- `Akki_Website_Brief_v2.docx` — 9-page website with locked copy, design system, pricing
- `Akki_UIUX_Architect_Brief.docx` — 5 surface types, 8-item nav, WCAG 2.2 AA, performance budgets

## Locked nomenclature

| Old | New |
|---|---|
| Solve | **Solva** |
| Studio | **Work Studio** |
| Prepare / Catch-up (merged with Cycle) | **Cycle Manager** (briefs + cycle signals + minutes + action items) |
| Signals (cross-context aggregator) | **Akki Pulse** |
| Learn | **Executive Learn** |

## Locked pricing (Phase 16)

| Plan | Price/mo | Includes |
|---|---|---|
| NED | $129 | All 5 surface types, multi-board context, cross-board Pulse, Solva, Synisense Shield |
| Executive | $179 | Cycle Manager, Work Studio, Solva, all reporting surfaces, Synisense Shield |
| Dual | $249 | NED + Executive in one account |
| Reportee add-on | $49 | Work Studio + Pulse only (reduced surface) |

Annual: 15% off. Three-year: 25% off. No free tier (Sandbox is free).

## 8-item post-login navigation (top bar, 64px fixed)

`Home · Chat · Solva · Work Studio · Cycle Manager · Monitor · Pulse · Learn`

Active item: 2px accent underline (never background fill). Collapses to hamburger below 1024px. Cycle context indicator top-right.

## 5 surface types

| Surface | Pages | Layout |
|---|---|---|
| Stream | Home, Pulse, Learn | Editorial cards by recency/importance |
| Workspace | Work Studio, Solva sub-modules | 3-col desktop (materials / artefact / controls), 1-col mobile |
| Reading | Document viewers, Pulse signal detail, briefings | Long-form focus mode, 1.55-1.65 line-height |
| Structural | Cycle Manager, Monitor | Operational status views |
| Conversational | Chat | Natural language module invocation |

## Design system tokens (locked)

- Palette: Ink `#2A1B1D`, Deep, Muted, Rule, Cream `#F5EFE6`, Accent
- Fonts: Georgia (editorial), Calibri (interface)
- Scale: 1.25 ratio
- Spacing: 8px base (4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128)
- Reading surfaces: line-height 1.55-1.65. Interface: 1.4-1.5.
- Accent: max 2 uses per screen
- Motion: 150-200ms state, 250-350ms transitions. Never > 600ms. `prefers-reduced-motion` respected.

## Banned words (enforced in CI for Phase 17 website)

`seamless, leverage, unlock, empower, revolutionize, cutting-edge, game-changer, AI-powered, next-gen, trusted by leading organizations, world-class, best-in-class, innovative solution`

## Approved phases

### Phase 12 — Synisense Shield ✅ CLOSED (12.3 closed in Phase A)
- 12.1 engine + AES-GCM envelope encryption + `/api/synisense/status` + `/dryrun` + `/api/admin/synisense/perf` + tests
- 12.2 six-surface wiring (chat, ingest, Studio, Solva, public-read) + PreviewDrawer + TrustPanel rewrite + chat inline icon
- 12.3 marketing copy honesty pass + "Actually shipped" diff in SYNISENSE_SCOPE.md (closed in Phase A — chat surface unified onto Synisense, legacy regex shield retired, see SYNISENSE_SCOPE.md "Actually shipped" diff)

### Phase 13 — Nomenclature & Navigation Rebuild (~7-8 days, split into 4 sub-phases)

**Status:** 13.1 done · 13.2-13.4 pending fresh-session dispatch.

- **13.1 Nomenclature rename (~1.5d)** ✅ **DONE 2026-05-04.**
  - Solve → Solva: backend routers `solve.py` → `solva.py`, `solve_engine.py` →
    `solva_engine.py`. API canonicalised on `/api/solva/*`. Legacy `/api/solve/*`
    served by `routers/solva_aliases.py` returning HTTP 308 with `Location:
    /api/solva/...` (preserves method + body). Frontend pages renamed
    (`SolveLanding.jsx` → `SolvaLanding.jsx`, `AppSolve.jsx` → `AppSolva.jsx`).
    `/solve` and `/app/solve` aliased via `<Navigate replace />` in `App.js`.
  - Studio → Work Studio: user-visible copy only (StudioComposerPage,
    Decks, Features, EnterpriseFeature, ThreePillars). Backend route
    surface and file names retained for internal stability.
  - Mongo collection names retain the `solve_` prefix (`solve_sessions`,
    `solve_clusters`, etc.) — renaming is a data-migration risk for zero
    user benefit. Stored data values like `role: "solve"` and
    `surface: "solve"` (in `llm_deep_usage`) follow the same logic.
  - Marketing copy refreshed: SolvaLanding, ThreePillars,
    EnterpriseFeature, Security, FirstSession.
  - 4 new alias regression tests in `test_solva_route_aliases.py`. Existing
    39 Phase 12 tests still green (43 total now).
  - **Aliases retired in Phase A (2026-05-04+).** `routers/solva_aliases.py`
    deleted, `/api/solve/*` now 404. Test corpus at
    `tests/test_solva_route_aliases.py`, `tests/test_iter61_solve_engine.py`,
    `tests/test_iter63_solve_p1p2_followon.py` deleted with the alias.
    `test_iter67_regression.py::test_solve_clusters_returns_12` migrated to
    `/api/solva/clusters`.
  - Aliases scheduled for retirement in **Phase 14** (three sessions out)
    — see "Migration notes — `/api/solve` → `/api/solva` aliases" below.
- **13.2 Cycle Manager merger (~2d)** ✅ **DONE 2026-05-04.**
  - Outer tab shell on `/app/cycle`: 5 tabs (Overview · Briefs · Signals ·
    Minutes · Actions). Deep-linked via `?tab=<id>` query string so URLs
    pasted into chat / email land on the right tab. Accent underline on
    active (per UI/UX brief; never background fill).
  - **Overview tab** retains the existing reporting-cycle workflow
    verbatim (Receive → Consolidate → Generate → Submit spine + 6 inner
    sub-tabs: tracker / reportees / bank / checklists / inbox / reports).
    Lifted into `OverviewTab` inside `pages/Cycle.jsx`.
  - **Briefs / Signals / Minutes** absorb `/app/prepare`. New thin wrappers
    in `frontend/src/components/cycle/tabs/{BriefsTab,SignalsTab,MinutesTab}.jsx`
    render `<Prepare embedded forceTab="..." />`. `Prepare.jsx` was
    refactored to accept `embedded` (skip AppShell + page H1) and
    `forceTab` (skip the inner line-tab nav). All existing Prepare
    functionality preserved: stats dock, brief generation form with
    deep-tier toggle + quota meter, validator badge, history side rail,
    brief-detail modal, signal-detail modal, minutes UI.
  - **Actions tab** ("Action Items progress") is a new aggregator
    surface: signal_actions (acted) + in-flight plays (active/paused) +
    pending checklists (pending_approval/dispatched). Backed by the new
    read-only endpoint `GET /api/contexts/{cid}/cycle/actions` in
    `routers/cycle.py`. No new collections, no new write paths.
  - **`/app/prepare` → `/app/cycle?tab=briefs`** as a `<Navigate replace />`
    alias in `App.js`. `/app/highlights` now chains to
    `/app/cycle?tab=signals`; `/app/briefings` chains to
    `/app/cycle?tab=briefs`. Bookmarks and external email deep-links keep
    working silently.
  - `briefs` vs `briefings` collection split intentionally preserved
    (informal vs formal, different surfaces, different endpoints).
  - 5 new tests in `test_cycle_manager_actions_tab.py` (3) and
    `test_prepare_redirect_alias.py` (2). Existing 43 still green
    (48 total now).
  - Nav-label rename "Cycle" → "Cycle Manager" and keyboard shortcuts
    are deliberately deferred to Phase 13.3 (the nav rebuild).
- **13.3 Navigation + shortcuts + role-aware Home + handoffs (~2d)** ✅ **DONE 2026-05-04.**
  - **8-item primary top nav** rebuilt in `components/layout/AppShell.jsx`:
    `Home · Chat · Solva · Work Studio · Cycle Manager · Monitor · Pulse · Learn`.
    64px fixed row directly under the existing 64px brand header. Active
    state = 2px `var(--accent)` underline only (never background fill).
    Below 1024px the row hides and a hamburger drawer with the same 8
    items takes its place. Legacy left-rail nav removed (the `<aside>`
    tree is wrapped in a `false` guard and left in source for code
    archaeology, not rendered). Routes that were only surfaced in the
    left rail (Lens, Simulate, Influence Map, Manage shortcuts) remain
    URL-accessible and discoverable via the ⌘K palette.
  - **Cycle context indicator** in `components/layout/CycleContextIndicator.jsx`
    (top-right of the brand header). Shows the active context name +
    role (Executive / NED / Member). Click → dropdown of all the user's
    contexts; click a row → `switchContext(id)` (existing AuthContext
    method) → all scoped surfaces (Cycle Manager, Monitor, Work Studio)
    re-fetch automatically.
  - **Keyboard shortcuts** in `hooks/useKeyboardShortcuts.js` mounted
    once at the AppShell level. ⌘/Ctrl-K dispatches `akki:open-palette`
    (AppShell listens, toggles the existing palette dialog). ⌘/Ctrl-J
    looks up the focused page's `[data-solva-seed="kind:id"]` element
    and navigates to `/app/solva?seed_kind=&seed_id=`; falls through to
    the Solva landing if no seed is on screen. ⌘/Ctrl-S preventDefault
    + dispatches `akki:save` for context-sensitive editor saves. `?`
    key opens a discoverable help overlay (`components/layout/KeyboardHelp.jsx`)
    listing every shortcut. Mouse path: a Keyboard icon button in the
    header opens the same overlay.
  - **Cross-module handoffs** in `components/shell/HandoffActions.jsx`.
    Three buttons — Take into Solva / Send to Work Studio / Add to
    Cycle. Mounted in: brief detail modal (`pages/Prepare.jsx`), signal
    detail modal (same file), deck detail (`pages/Decks.jsx`), document
    detail (`pages/ReadingView.jsx`). Each row also stamps a
    `data-solva-seed="kind:id"` attribute so ⌘J picks the artefact up
    automatically. "Add to Cycle" calls
    `POST /api/contexts/{cid}/questions` and lands the user on the
    Cycle Manager Overview tab.
  - **Work Studio landing hub** in `pages/WorkStudio.jsx` at
    `/app/work-studio`. Aggregates in-flight briefings + decks +
    reports across the active context. Inner tabs: All / Briefings /
    Decks / Reports with counts; sort by `updated_at desc`. Each row
    carries title, sensitivity chip, Synisense `shielded` flag,
    validator badge (Phase 11 honesty), last-edit. "Start a briefing /
    deck / report" buttons up top. Reads `?view=` deep-link, so
    `/app/decks` (legacy listing) `<Navigate replace />`s to
    `/app/work-studio?view=decks`. Per-deck detail (`/app/decks/:id`)
    still routes to the existing `<Decks />` component.
  - **Pulse placeholder** in `pages/PulsePlaceholder.jsx` at
    `/app/pulse`. Honest editorial holding copy describing what Phase
    14 ships; deep-link to per-board signals at `/app/cycle?tab=signals`.
  - **Role-aware Home** in `pages/AppHome.jsx`:
    - `declared_role === "ned"` → `<HomeNed />`
      (`pages/home/HomeNed.jsx`) — Pulse cross-board card, latest
      minutes, signals awaiting action, agenda evolution.
    - `declared_role === "executive"` → `<HomeExecutive />`
      (`pages/home/HomeExecutive.jsx`) — Work Studio in-flight
      preview band on top, then the existing executive home wholesale
      from `LegacyAppHome` (telemetry preserved).
    - `declared_role === "dual"` → `<HomeDual />`
      (`pages/home/HomeDual.jsx`) — split layout, executive cards on
      the left, NED cards on the right.
    - `declared_role === "undeclared"` → `<HomeUndeclared />`
      (`pages/home/HomeUndeclared.jsx`) — three-button picker with a
      link to `/app/first-session` for the full intake.
    - Sandbox accounts pinned to LegacyAppHome (frozen single-context).
    - `?home=v2` / `?home=legacy` URL overrides preserved.
  - No backend changes. 48 existing tests stay green; no new tests
    added (the brief explicitly noted "the project has no Jest/RTL setup;
    skip component tests"). Live evidence captured for all eight
    deliverables on the preview environment.
- **13.4 WCAG 2.2 AA + perf budgets (~1.5d)** ✅ **DONE 2026-05-04.**
  - **`@axe-core/react`** wired in `frontend/src/index.js` with a
    `NODE_ENV !== "production"` guard so it tree-shakes out of the
    production bundle. Logs WCAG 2.2 AA violations to the browser
    console as users navigate.
  - **`pa11y-ci`** + config at `frontend/.pa11yci.json`. Scans 10
    public + auth-form URLs against the `WCAG2AA` standard via the axe
    runner. New `yarn a11y:ci` script.
  - **Lighthouse CI** + config at `frontend/lighthouserc.json`. Runs
    against three sample URLs (one per accessible surface bucket) on
    desktop preset. Budget assertions on FCP / LCP / TTI / CLS / TBT /
    speed-index. New `yarn perf:ci` script. All assertions are `warn`
    on the first run \u2014 tighten in a follow-up once the baseline is
    stable.
  - **a11y fix delta**: 159 issues (69 errors + 90 warnings across 10
    URLs) \u2192 **10 issues** (10 errors, all known false positives \u2014
    documented in `ACCESSIBILITY.md`). Net **\u22121,049% noise** in the
    pre-merge accessibility report. Top fixes:
    - `<main>` landmark added to `Landing.jsx` and `SolvaLanding.jsx`
      (kills 87 `region` warnings + the 2 `landmark-one-main` warnings).
    - Decorative `\u00b7` separator dots bumped from `text-[var(--rule)]`
      (1.3:1) to `text-[var(--muted)]` (5.6:1) in `MarketingFooter`,
      `Exco360Voice`, `HeroSection` (kills 60+ contrast errors).
    - `Why not just chat` overline + Solva pill labels on navy
      bumped from `text-[var(--accent)]` to `text-[var(--cream)]/85`
      in `SolvaLanding` (4.4:1 \u2192 14:1).
    - Numbered `01\u201304` mono labels on the dark Solva pillar in
      `ThreePillars` bumped to `text-[var(--cream)]/85` (4.4:1 \u2192 14:1).
    - SignIn legacy "Try AKKI in 60 seconds" link gained `underline`
      (kills `link-in-text-block`).
    - Security page `<h3>` promoted to `<h2>` to fix heading order.
    - Hero quote panel `<aside>` re-tagged as `<div>` (kills
      `landmark-complementary-is-top-level`).
    - Top-nav links gained `focus-visible:ring-2 focus-visible:ring-[var(--accent)]`.
    - All sectioned pages (`<section>`) now carry `aria-labelledby`
      pointing at their heading.
  - **Lighthouse baseline (desktop)**:
    - `/`         FCP 744ms / LCP 3528ms / TTI 3691ms / CLS 0.000 \u2014 LCP + TBT warn
    - `/security` FCP 728ms / LCP 2249ms / TTI 2431ms / CLS 0.000 \u2014 all pass
    - `/solva`   FCP 730ms / LCP 2241ms / TTI 2445ms / CLS 0.000 \u2014 TBT 1ms over
  - **Two new docs**: `docs/ACCESSIBILITY.md` (posture + tool stack +
    known exceptions) and `docs/SURFACE_TYPES.md` (route\u2192surface map +
    perf budgets).

## Phase 13 \u2014 CLOSED

All four sub-phases shipped clean. 13.1 Solva rename (with `/api/solve`
HTTP 308 aliases). 13.2 Cycle Manager merger (5-tab outer shell +
embedded Prepare). 13.3 8-item nav rebuild + role-aware Home + cross-
module handoffs + ⌘K/J/S/? keyboard shortcuts. 13.4 WCAG 2.2 AA + perf
budgets in CI. 48 backend tests still green throughout. No regression
on Synisense, Phase 11 ValidatedBadge, Resend / Stripe / Sentry stubs.

#### Phase 13.1 migration notes — `/api/solve` → `/api/solva` aliases
- Legacy paths return HTTP 308 (Permanent Redirect, preserves method +
  body). Implemented in `backend/routers/solva_aliases.py` as a
  catch-all path-converter route mounted at `/api/solve` and registered
  AFTER the canonical Solva routers. Query strings carry across.
- Frontend route aliases (`/solve` → `/solva`, `/app/solve` →
  `/app/solva`) live in `App.js` as `<Navigate to="..." replace />`
  entries. The `replace` flag means the legacy URL never lands in
  history — clean back-button behaviour.
- The aliases are observable on the wire (308 in access logs, no body)
  so we can decide when to retire them. Plan: **retire in Phase 14**
  once Pulse landing surfaces have migrated and external bookmarks have
  had three sessions to bake in.

### Phase 14 — Akki Pulse (~4 days)
- Cross-account Pulse aggregator across all context memberships a user holds
- Privacy wall: aggregation reads metadata only (severity, topic), NEVER content cross-context
- Entity/pattern classification: cyber, capital, succession, regulatory (LLM-classified from existing signals + docs)
- NED view: cross-board patterns with source attribution back to originating board
- Executive view: within-org change detection (reportee submissions, cycle deltas, inbound triage)
- Daily `PulseDigest` at 07:00 UTC via Resend (noop until key set)
- Per-surface non-blocking toast when a new Pulse item is auto-generated while user is working

### Phase 15 — Solva v2 Engine (~10 days, split)
- **15.1 Orchestration tier** (~4d): layer state machine, question routing, `solva_session` schema with `reasoning_audit_log`, 5-tier grounding contract enforcement, 4 reasoning engines as standalone services (candidate generation/refinement, triangulation, probability weighting, refusal logic). Reasoning tier behind thin LLM adapter — interchangeable.
- **15.2 Four sub-modules + tension detection** (~3.5d): Seek Clarity / Develop Strategy / Simulate Hypothesis / Get Perspective. Tension detector with auto-activation in Simulate Hypothesis. Per-sub-module entry flows.
- **15.3 Guardrails + Reflection + UX polish** (~2.5d): jailbreak (soft→hard block), therapy redirect (not refusal), Layer 4 Reflection with 3 locked questions, Layer 3 synthesis rendering (probability intervals like "45% (35-55%)", citation chips, sensitivity callouts), session resume, cross-module invocation.

### Phase 16 — Reportee Accounts + Billing Enablement (~3 days)
- `reportee_accounts` sub-account model under a parent executive
- Reduced surface: Work Studio + Pulse only (no Solva, no Cycle Manager, no Monitor)
- Provisioning flow from executive's Cycle Manager
- Enable Stripe with locked pricing above. Annual/3-year discounts.
- Solve Pro affordance reads live from `account.plan` per session (closes the Phase 10 flagged incomplete loop)
- 90-day export-and-delete on cancel
- **DECISION at phase boundary:** live keys vs defer (BILLING_ENABLED=false)

### Phase 17 — Website Rewrite (~3 days)
- All 9 pages with locked copy verbatim from Website Brief: Home, For NEDs, For Executives, How it works, Solva, Sandbox, Pricing, About, Demo
- Design system from tokens above
- Sandbox page runs actual Solva session on fictional context (rebuild per locked decision)
- Photography: Unsplash curated + restrained grading (per locked decision)
- Banned-words lint rule in CI
- Demo form + calendar integration
- No feature-tour pages, no vendor cadence

### Phase 18 — Observability (~2 days) [Phase G in current plan]
- Sentry wired (DSNs captured: backend `a5409b...@o4511318182920192.ingest.de.sentry.io/4511318238756944`, frontend `cbd496...@o4511318182920192.ingest.de.sentry.io/4511318248456272`)
- Structured JSON logs with request IDs through LLM calls
- Rate limits per-user/per-account on /chat, /solva, /prepare (tunable per plan)
- LLM circuit breakers per adapter
- `/api/health` returns dependency status (Mongo, Resend, Postmark, Stripe, ClamAV, MinIO, Synisense)
- APScheduler leader election via Mongo lock (unblocks multi-replica)
- **Install `clamd` + `freshclam` in the container image; set `autostart=true` on `clamd.conf`; drop the `ALLOW_UNSAFE_UPLOADS` dev bypass.** Recreate the `clamav` system user and flip `clamd.conf` `user=root` back to `user=clamav`. (Phase B sandbox hotfix wired the dev bypass; Phase G removes it.)
- **Install `minio` in the container image; set `autostart=true` on `minio.conf`; flip `STORAGE_BACKEND=local` back to `s3` in dev.** (Phase B sandbox hotfix wired the local-disk fallback; Phase G removes it.) See `docs/RUNBOOKS/DEV_POD_CAVEATS.md` for the current dev-pod posture.
- Frontend React error boundary at route level

### Phase 19 — Deployment Topology (~1 day, docs only)
- akki.ai marketing / app.akki.ai app split
- Final `AZURE_DEPLOY.md` with approved nav + pricing + Phase 16/17/18 completion state
- CI/CD skeleton finalized (GitHub Actions → ACR → Container Apps rolling deploy, Sentry release tagging)

## Locked product decisions

1. **Approved phase order:** 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19
2. **Billing timing:** decide at Phase 16 boundary
3. **Photography:** Unsplash curated + restrained grading
4. **Sandbox:** rebuild to run actual Solva session on fictional context

## Out of scope for v1 (UI/UX Architect + Solva briefs explicitly)

- Native mobile apps (iOS/Android) — responsive web only
- Offline mode
- Dark mode beyond system default
- Multi-user Solva sessions
- Solva session learning / pattern improvement
- Voice/audio interfaces
- Cross-context triangulation (privacy wall)
- Custom design system extensions for Enterprise
- i18n (i18n-ready from day one, but launching English-only)

## Anti-over-engineering rules (efficiency shortcuts approved)

1. Reuse Phase 11 citation infrastructure in Solva grounding contract
2. Reuse Phase 11 ValidatedBadge as Solva refusal rendering
3. Reuse Phase 12 Synisense as Solva ingestion sanitizer
4. Reuse Phase 8 block composer as Work Studio (renames only)
5. Reuse existing signals engine as per-context substrate for Pulse
6. Reuse existing Sandbox 10-stage streaming — rewrite copy, realign the 4-step journey, bind to a real Solva session

## Agent workflow rules

- Each phase: brief from orchestrator → e1_dev build → e1_tester verification → clean close. No backlogs.
- Decision points surface only when a genuine trade-off exists the agent shouldn't make alone.
- Every phase writes its own "honest deviations" section in the closeout.
- No silent un-stubbing across phase boundaries.
- Every new env var → `.env.example` + `PRODUCTION_ENV.md`.
- Mocks/stubs always explicitly labelled in code comments and UI copy.


## Phase A — Cleanup & 12.3 close (applied 2026-05-04+)

Single-shot cleanup pass between 15.3.5 and 16. Scope was tight:
delete the `_legacy/` archive, finish v1 retirement, unify PII shielding,
flip typography, close 12.3 doc drift. **Closed.**

- `_legacy/` directory deleted from the live tree (forensic comm history retained in git).
- `routers/solva_engine.py` rewritten as **read-only forensic surface**: every POST handler removed, helper `_v1_decommissioned()` deleted, six GETs preserved (`/clusters`, `/pro-status`, `/sessions[/{sid}/...]`, `/export.pdf`).
- `routers/solva_aliases.py` deleted; `/api/solve/*` now 404 (no 308 alias).
- `account.solva_v2_poc` flag residue cleared from live code: `require_solva_v2_flag()` deleted (every callsite now uses `Depends(get_current_account)`), `core.sanitize_account` no longer surfaces the flag, `POST/GET /api/admin/solva-v2/flag` removed, `admin_router` unmounted from `server.py`. Field stays in MongoDB on existing accounts (no migration).
- `frontend/src/pages/SolvaV2Poc.jsx` renamed to `SolvaApp.jsx`; `App.js` rewires `/app/solva` to `SolvaApp`. `frontend/src/pages/AppSolva.jsx` (the 17-line `<Navigate>` stub) deleted.
- PII shielding unified on `services/synisense`. `services/synisense/adapter.py` exposes a `shield_payload_async / shielding_report / rehydrate` trio with the legacy tuple shape so existing callsites migrate without refactoring their rehydrate flow. `llm_service.shield_payload`, `shielding_report`, `rehydrate` and the regex constants deleted. `chat.py` migrated end-to-end (legacy second-pass regex shield removed; reply rehydration now uses pipeline-derived `shield_map`).
- Typography: Inter retired. Calibri ships from the system stack `Calibri, "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif`. Google Fonts Inter import removed from `index.css` and `public/index.html` (the platform-injected "Made with Emergent" badge keeps its own Inter ref — out of scope).
- `services/solva_v2/__init__.py` package docstring rewritten to reflect the post-15.3.5 / Phase A reality (real engines, four sub-modules, guardrail ladder, Calibri stack — no stub language).
- Phase 15.3.5 cutover items 1, 2, 4, 8, 10 (no-opinion prompt audit, Solva landing redesign, Home divergence collapse, chat soft-delete + 30-day cron, streaming chat SSE) are NOT in Phase A — moved forward to **Phase B**.

## Phase K — Home consolidation, sponsored gate audit, Julius tester (applied 2026-05-05)

Three sub-steps. **Closed.**

| # | Title | Outcome |
|---|---|---|
| K.1 | Home consolidation — delete legacy executive monolith | Deleted `frontend/src/pages/ExecutiveHomeShell.jsx` (579 ll. — the pre-Phase-5 "LegacyAppHome" with `?home=v2` toggle, duplicate first-session gate, 4 sandbox-only widgets superseded by Sandbox v2). Rewrote `frontend/src/pages/home/HomeExecutive.jsx` (296 ll.) as a self-contained role shell mirroring `HomeNed.jsx` / `HomeDual.jsx`: greeting + role overline, the "Continue onboarding" card from Phase B.6 (the only legacy widget worth preserving), `WorkStudioPreview` band, `CycleStrip`, and a 4-card brand-aligned quick-link grid (Cycle Overview / Pending actions / Signals / Recent activity). `pages/AppHome.jsx` dispatcher unchanged — one canonical home, four role shells, no duplicate Home components. ESLint clean. |
| K.2 | Sponsored gate audit — remove every functional gate | Audit complete. Result: **no functional gates exist**. Every sponsored reference in the codebase is cosmetic (chrome labels, nav rail grouping, an informational "your data stays with the sponsoring company" banner) or data-only (`sponsoring_org_id` field init, type whitelist). `require_context_membership(owner_only=True)` applies equally to all context types. Sponsored contexts already have byte-identical feature parity with personal contexts. Breadcrumb TODO documented in `frontend/src/lib/sponsorship.js` for the future Phase 16 tier-limits decision. |
| K.3 | Julius Opio tester account | Idempotent seed at `backend/scripts/seed_julius_opio.py` creates `juliusaopio@gmail.com` (dual / superadmin / plan=enterprise / subscription=active / first_session.status=skipped / mfa=off), one throwaway `Acme Sponsor Org`, four contexts (one per type — `ned_personal` as default, `ned_sponsored`, `executive_personal`, `executive_enterprise`), four memberships (Julius as owner+admin on each), and the standard 6-committee set (Audit · Risk · Nominations · Remuneration · ESG · Strategy) on every context. Re-running rotates the password back to canonical and reasserts all flags. Verified: `POST /api/auth/login` returns HTTP 200 + 252-char JWT + `account.is_superadmin=true` + `contexts.length=4`. Tests: 4/4 in `backend/tests/test_phase_k_seed_julius.py`. |

**Tests on close:** 4/4 new pytests for K.3 (`test_phase_k_seed_julius.py`), Phase J still 29/29, sandboxV2Flow jest still 28/28, ruff + ESLint clean on every modified file, `/api/health` 200, `/openapi.json` 200, `/docs` 200, `pip check` clean.

## Phase L — Strategic Documents Pack ingestion (applied 2026-05-05)

Bridge phase before Phase D. Four sub-steps. **Closed.**

| # | Title | Outcome |
|---|---|---|
| L.1 | Ingest 14 strategic docs into Sandbox v2 corpus | New module `backend/sandbox_v2_strategic.py` (1 file, ~720 ll) carrying the verbatim 14-doc Sandbox Strategic Documents Pack across 5 contexts (Bank ×3, Healthcare ×3, Logistics ×3, Government ×3, Technology ×2). Public surface: `pick_strategic_documents(org_type, kind=None)`, `strategic_doc_titles`, `strategic_doc_by_id`, `strategic_corpus_health`. `pick_studio_sources` extended with `include_strategic=False` flag (default preserves Step 3 UI contract); `pick_cycle_snapshot` now carries additive `strategic_baseline_source` (plan title) and `strategic_plan_refs` array (id / title / kind / preview / pack_section) so the Step 4 baseline section reads as institutional memory. doc_kind vocabulary locked: `strategic_plan` / `framework` / `strategy` / `theory_of_change` / `investment_thesis` / `political_economy`. Self-check at module load fails the boot if the pack count or word-band drifts. |
| L.2 | Seed 14 strategic docs into admin@akki.ai | New idempotent seeder `backend/scripts/seed_admin_strategic_data.py` that reuses the shared helper `backend/scripts/_strategic_ingest.py`. Mints one "<Org Display Name> · Demo" context per pack org_type (5 contexts) under admin ownership with executive+admin membership, ingests every strategic doc as a real `documents` row through Synisense pipeline (`surface=ingest`) and `studio_sensitivity.score_sensitivity`. Idempotent on `(context_id, title, source="strategic_pack_v1")`. Deployment-level sensitivity floor: strategic-pack docs floor at `internal`; political-economy briefs floor at `confidential`. Result on this DB: 14/14 docs, all carrying `body_redacted`, `synisense_version=1`, `sensitivity_score`, `sensitivity_band ∈ {internal, confidential}`. |
| L.3 | Mirror to Julius's account | `backend/scripts/seed_julius_opio.py` extended: 5th context "Julius Opio — Government Executive" (type `executive_personal`, sector "Ministry · industrial modernisation", same 6-committee set). After the existing K.3 seed completes the script then calls `ingest_strategic_documents(account=julius, context_name_by_org_type=...)` to mirror the 14 docs into Julius's existing 5 contexts (no new "· Demo" contexts created). Idempotent re-run: every doc creates / skips per row; password rotation + flag reassertion preserved from K.3. |
| L.4 | Verify + docs sweep + endpoint enrichment | `GET /api/contexts/{cid}/documents/{did}` extended to surface `body_redacted`, `synisense_version`, `sensitivity_score`, `sensitivity_band`, `sensitivity_label`, `sensitivity_reasons`, `doc_kind` on the detail payload (additive on top of `sanitize_doc`). Manual smoke: both admin and Julius login + per-context list documents + open one detail confirms all fields populated. Sandbox smoke: `pick_strategic_documents("bank")` returns 3 docs with verbatim titles; `pick_cycle_snapshot("ceo","bank").strategic_baseline_source` returns `"Mara Heritage Bank · Five-Year Strategic Plan 2024-2028 — Executive Summary"`. |

**Tests on close:** 12/12 new pytests for Phase L (`test_phase_l_strategic_pack.py`); regression suite 45/45 across Phase J (29) + Phase K (4) + Phase L (12). `pip check` clean, ruff clean on every Phase L file, ESLint untouched. `/api/health` + `/openapi.json` + `/docs` all 200.

**Synisense redaction proof.** Sample from `backend/sandbox_v2_strategic._LOGISTICS_DOCS[1]` (Founder-CEO Succession Framework):
- Original: `"Korogocho Logistics Group · Nominations Committee · Q1 2026 ... Founder-CEO James Korogocho has led the company for fifteen years..."`
- Redacted: `"[ORG_1] · [ORG_2] · Q1 [DATE_1] ... Founder-[TITLE_1] [PERSON_1] has led the company for fifteen years..."`
- 48 PII spans on this doc; comparable counts across all 14.

**Surprises (two).**
1. The default sensitivity scorer (`backend/studio_sensitivity.py`) does not match the disclosure labels the pack uses (`Confidential`, `Restricted Distribution`, `Highly Confidential` are not in the regex vocabulary). The whole pack would have landed PUBLIC. Resolved by applying a deployment-level floor in the L.2 / L.3 ingest helper (strategic_pack → internal, political_economy → confidential) rather than mutating the scorer — keeps Phase D / E scorer logic untouched. Documented inline.
2. The L.2 seeder originally created contexts but no memberships, which broke the API (login payload + `require_context_membership`) until I patched `_ensure_demo_context` to insert an admin/executive-admin membership alongside every context. Caught by the L.4 verification pass — `/api/contexts/{cid}/documents` 403'd until memberships landed.
