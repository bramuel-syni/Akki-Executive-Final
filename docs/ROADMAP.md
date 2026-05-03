# AKKI Production Roadmap — Phases 12 through 19

**Status:** Approved by product owner. Single-approval execution. Each phase closes cleanly before the next. Decision points are flagged; all other scope is locked.

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

### Phase 12 — Synisense Shield (IN FLIGHT)
- 12.1 engine + AES-GCM envelope encryption + `/api/synisense/status` + `/dryrun` + `/api/admin/synisense/perf` + tests
- 12.2 six-surface wiring (chat, ingest, Studio, Solva, public-read) + PreviewDrawer + TrustPanel rewrite + chat inline icon
- 12.3 marketing copy honesty pass + "Actually shipped" diff in SYNISENSE_SCOPE.md

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
  - Aliases scheduled for retirement in **Phase 14** (three sessions out)
    — see "Migration notes — `/api/solve` → `/api/solva` aliases" below.
- **13.2 Cycle Manager merger (~2d)** — pending. Absorb Prepare features
  into Cycle. Unified surface (briefs + cycle signals + minutes + action
  items). `/app/prepare` redirects to `/app/cycle` with deep-linked tabs.
  `briefs` vs `briefings` collection split preserved (intentional dual
  store).
- **13.3 Navigation + shortcuts + role-aware Home + handoffs (~2d)** —
  pending. 8-item top nav (Home · Chat · Solva · Work Studio · Cycle
  Manager · Monitor · Pulse · Learn). 64px fixed. Accent underline active
  state. Hamburger below 1024px. Cycle context indicator top-right.
  Cmd-K / Cmd-J / Cmd-S. Handoff primitives. Role-aware Home by
  `declared_role`.
- **13.4 WCAG 2.2 AA + perf budgets (~1.5d)** — pending. `@axe-core/react`
  dev-time + `pa11y-ci` CI gate. Fix top-20 hits. Lighthouse CI perf
  budget gates per surface.

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

### Phase 18 — Observability (~2 days)
- Sentry wired (DSNs captured: backend `a5409b...@o4511318182920192.ingest.de.sentry.io/4511318238756944`, frontend `cbd496...@o4511318182920192.ingest.de.sentry.io/4511318248456272`)
- Structured JSON logs with request IDs through LLM calls
- Rate limits per-user/per-account on /chat, /solva, /prepare (tunable per plan)
- LLM circuit breakers per adapter
- `/api/health` returns dependency status (Mongo, Resend, Postmark, Stripe, ClamAV, MinIO, Synisense)
- APScheduler leader election via Mongo lock (unblocks multi-replica)
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
