# AKKI — Sprint Audit (state-of-the-app, read-only)

**Generated:** 2026-02 (fork agent, pre-Cycle-Manager-resume)
**Mode:** Read-only. No code edits performed.
**Source-of-truth precedence:** Sprint brief / closure doc → `/app/docs/PRODUCT_SPEC.md` → live code in `/app/backend` + `/app/frontend`.

When a dedicated sprint brief is missing, the relevant PRODUCT_SPEC section is used as fallback and **BRIEF NOT FOUND** is flagged. Closure docs in `/app/docs/sprints/` (`PRE_v7_website.md`, `HOME.md`, `CHAT.md`, `SOLVA.md`, `STUDIO.md`) are post-completion reports — used as the requirement contract when no pre-sprint brief exists.

---

## 1. Pre-Login / Pre-Signup

Surfaces: **Marketing Website · Sign-in · Sign-up · Sandbox**

### 1.1 Marketing Website

- **Sprint brief:** `/app/docs/WEBSITE_BRIEF_V3.md` (657 lines, pasted verbatim from `Akki_Website_Brief_v3.docx`)
- **Closure doc:** `/app/docs/sprints/PRE_v7_website.md` (257 lines)
- **Requirements count: 38 total** (A1–A10 visual, B1–B3 voice, C1–C4 home hierarchy, D1–D18 pages × 18 routes, E1–E4 nav/footer, F1–F5 hero/strip/CTA, G1–G6 images, H1–H4 perf/a11y/seo)

| # | Item | Status | Evidence |
|---|---|---|---|
| A1 | Bronze removed from website + sandbox + public | Done | grep clean across `frontend/src/website/`, `frontend/src/sandbox/` |
| A2 | 7-token v7 palette installed | Done | `frontend/src/website/style.css:64-71` |
| A3 | Source Serif 4 + Inter + JetBrains Mono | Done | `style.css:39-62`, `local()` chain; **NO woff2 self-hosted** — falls back to Georgia / system fonts |
| A4 | Type sizes verbatim | Done | `style.css:84-152` |
| A5 | Single-word oxblood lift per hero | Done | `PagePrimitives.jsx:HeroWithLift` |
| A6 | Body type never oxblood | Done | smoke `forbidden_hits == 0` |
| A7 | Buttons (primary/tertiary/CTA) | Done | `style.css:155-218` |
| A8 | Hero staggered reveal (50/200/380/560 ms) | Done | `WebsiteShell.jsx:71-74` rAF arm |
| A9 | Section reveal IntersectionObserver | Done | `WebsiteShell.jsx:75-91` |
| A10 | Forbidden motion absent | Done | grep returns 0 |
| B1 | Banned marketing vocab absent | Done | grep clean |
| B2 | Anti-spec vocab absent | Done | grep clean |
| B3 | Approved proper nouns scoping | Done | Solva/Synisense/Agent Cycle only in Tier 3 / per-product pages |
| C1 | 10-section sequence on Home | Done | `pages/Home.jsx:36-217` |
| C2 | Tier 1 image band wired | Done | `Home.jsx:115-122` |
| C3 | Tier 2 NO product names | Done | `copy/index.js:TIER_2.capabilities` |
| C4 | Three Audiences triptych | Done | `Home.jsx:178-186` |
| D1–D18 | 18 page routes verbatim copy | Done | 24/24 routes HTTP 200 (incl. back-compat) |
| E1 | Nav layout (sticky, blur, wordmark + 4 + 2) | Done | `WebsiteNav.jsx` |
| E2 | Five effective items | Done | semantic equivalence verified |
| E3 | Footer 4-column with oxblood headings | Done | `WebsiteFooter.jsx`; `style.css:702-710` |
| E4 | No mega-menus / dropdowns | Done | nav is flat |
| F1 | Hero layout | Done | `Home.jsx:40-77`; `style.css:381-417` |
| F2 | Marginalia (mono 11px, ≥1100px) | Done | `Home.jsx:43`; `style.css:441-452` |
| F3 | Staggered reveal | Done | verified in screenshot |
| F4 | Evidence Strip (280 → 2, 5, 100%, SHA-256) | Done | `Home.jsx:80-94` |
| F5 | Inverted CTA (parchment on ink) | Done | `Home.jsx:201-217` |
| G1 | home-hero image (87 KB, eager) | Done | `assets/v7/home-hero.webp` |
| G2 | tier1-safety-band image (104 KB) | Done | `assets/v7/tier1-safety-band.webp` |
| G3 | audience-triptych image (53 KB) | Done | `assets/v7/audience-triptych.webp` |
| G4 | for-executives-hero (67 KB) | Done | `assets/v7/for-executives-hero.webp` |
| G5 | for-neds-hero (52 KB) | Done | `assets/v7/for-neds-hero.webp` |
| G6 | about-team portraits | **Not done** | DEFERRED in closure — requires real photography |
| H1 | LCP <1.5s / CLS <0.1 / TTI <2s / Page weight | Partial | LCP 404ms ✅, CLS 0 ✅, TTI 489ms ✅; **JS bundle weight 2.5MB ⚠** (shared SPA chunk; marketing code-split deferred) |
| H2 | Plausible analytics | Done | `WebsiteShell.jsx:51-58`, akki.syni.ai domain; lazy-injected |
| H3 | SEO (titles, meta, canonical, OG, sitemap, robots) | Done | `WebsiteShell.jsx:24-49`; 24 URLs in `public/sitemap.xml`; `public/robots.txt` |
| H4 | A11y AA (focus rings, alt, reduced motion, semantic) | Done | `style.css:212-218`, `:319-330` |

**Done:** 36 / 38
**Not done:** G6 (about-team portraits — DEFERRED), H1 page-weight (PARTIAL)
**Deviations:**
- A3 — fonts use `local()` only; no `.woff2` ship; non-spec fallback chain in production for users without these fonts installed locally
- G6 about-team — text-only About page per spec permission, but brief allowed for real photography (deferred indefinitely)
- H1 — JS bundle 2.5 MB exceeds the implied <500 KB landing budget; marketing code-split deferred

### 1.2 Sign-in / Sign-up

- **Sprint brief:** BRIEF NOT FOUND (no dedicated SignIn/SignUp brief in `/app/docs/sprints/`).
- **Fallback:** `PRODUCT_SPEC.md §5.12 Authentication & Sandbox` + HOME sprint closure mentions sign-in palette migration.
- **Requirements count: 8 total** (JWT+bcrypt, MFA, `/signin`, `/signup`, `/invite/:token`, MFA setup, brute-force lockout, v7 palette on sign-in)

| Item | Status | Evidence |
|---|---|---|
| JWT (HS256 8h access / 7d refresh) + bcrypt | Done | `backend/core.py`; `routers/auth.py` (9 endpoints) |
| TOTP MFA | Done | `pyotp` + `qrcode`; setup at `/app/security` |
| `/signin`, `/signup`, `/invite/:token` routes | Done | `App.js:220-222` |
| MFA setup page | Done | `pages/AccountSecurity.jsx` |
| Brute-force lockout (email-only key) | Done | per PRD §recent-fixes |
| Sampled (1%) success + 100% failure auth events | Done | `db.auth_events`; `db.login_attempts` |
| Sign-in v7 palette (parchment, oxblood WELCOME BACK kicker, Source Serif h1) | Done | HOME sprint screenshot evidence |
| **Invitation email actually sends** | **Not done** | `routers/contexts.py:405` — code comment claims "un-stubbed"; PRODUCT_SPEC §14 risk 6 says stubbed; live state ambiguous |

**Done: 7 / 8**
**Not done: 1** (Invitation email — code says un-stubbed Phase G3 but spec still flags as stubbed — **AMBIGUOUS, AUDIT-WORTHY**)
**Deviations:** Cookie-only login deviates from typical Bearer-only API expectation; both cookie + Bearer are accepted (additive — non-blocking)

### 1.3 Sandbox

- **Sprint brief:** BRIEF NOT FOUND (no dedicated sandbox brief in `/app/docs/sprints/`).
- **Fallback:** `PRODUCT_SPEC.md §5.12` + `PRD.md` (Sprint 10 Sandbox Phase 1; Sprint 14 Phase 4 enrichment).
- **Requirements count: 6 total**

| Item | Status | Evidence |
|---|---|---|
| `/sandbox` pre-auth intake (4-question) | Done | `frontend/src/sandbox/SandboxApp.jsx` (replaces legacy SandboxV2) |
| 60-second streaming generation page | Done | `pages/SandboxV2.jsx` (legacy retained at `/legacy-sandbox`) |
| Disposable account `sandbox+<id>@akki.local` | Done | `routers/sandbox.py` |
| Sandbox → real account conversion | Done | `POST /api/sandbox/convert` |
| 14-day TTL + 22-day hard-delete metadata | Done | `sandbox_metadata.{expires_at, hard_delete_at}` |
| Bronze removed from sandbox surface | Done | sandbox/style.css aliases all bronze tokens to v7 |

**Done: 6 / 6**
**Deviations:** Sandbox shares the same SPA bundle (no separate chunk) — analytics on `/sandbox` are intentionally NOT loaded (Plausible loaded only on website surfaces).

---

## 2. Post Sign-in surfaces

### 2.1 Home

- **Sprint brief:** BRIEF NOT FOUND (no pre-sprint brief).
- **Closure doc:** `/app/docs/sprints/HOME.md` (139 lines) — used as the requirement contract.
- **Requirements count: 6 sections × ~3 items = 16 total** (A v7 palette · B ExCo teams · C Portfolio state · D voice/copy · E role calibration · F streaming transitions)

| Section | Items | Status | Evidence |
|---|---|---|---|
| A | 7-token palette in `index.css`; bronze hex removed; aliases preserved; Source Serif/Inter/JBM declared; `.akki-citation-pill`; oxblood focus ring; sign-in renders v7; build clean | Done (8/8) | `index.css:66-93`; `index.css:96-99`; `:222-235`; build "Done in 19.64s" |
| B | `db.exco_teams` + indexes; 7 CRUD endpoints; admin/owner auth; member validation; no email in responses; audit rows on every mutation; 6 pytests; `ExcoTeamsCard` rendered on Home; live smoke 201/list/archive | Done (9/9) | `routers/exco_teams.py:300-307`; `test_exco_teams.py` 6/6 GREEN |
| C | `GET /api/me/portfolio`; 30s cache; cycle state derivation; goals_at_risk_count; live smoke; portfolio state badges; cards pass state through | Done (7/7) | `routers/portfolio.py:163-217`; `ContextPortfolio.jsx:155-201` |
| D | Banned-vocab grep clean; calm peer voice preserved | Done (2/2) | grep returns 0 across AppHome/home/components |
| E | Role kicker derivation; `EXECUTIVE`/`NED` labels; dual `EXECUTIVE · NED`; `· ExCo` append; rendered in top-nav | Done (5/5) | `CycleContextIndicator.jsx:25-43,78-84` |
| F | `WorkspaceEntryGate` + `ContextLoadingScene` wired previously | Done (2/2) | Verified in K5/HOME |

**Done: 33 / 33** (when each sub-item is counted)
**Not done:** 0
**Deviations:**
- woff2 not self-hosted (same as marketing — system fallback acceptable per HOME closure)
- `/api/contexts/{cid}/members` shape contract degrades gracefully if mismatched (HOME closure §Limitations point 2)
- Cross-board `Dual` role detection requires `account.declared_role === "dual"` — per-context dual not auto-detected

### 2.2 Chat

- **Sprint brief:** BRIEF NOT FOUND.
- **Closure doc:** `/app/docs/sprints/CHAT.md` (121 lines).
- **Requirements count: 6 sections × items = 17 total** (A palette · B per-message Synisense badge · C provider line · D Trust Panel cross-link · E banned-vocab · F streaming transition)

| Section | Items | Status | Evidence |
|---|---|---|---|
| A | `MarkdownMessage.css` v7 tokens; `ModelAvatar.jsx` migrated; `Chat.jsx` resolves through v7; headings → Source Serif; metadata → JBM; smoke /app/chat | Done (6/6) | grep clean; build clean |
| B | `useMessagesSynisense` batched hook; replaces N+1; backend batch endpoint; `PerMessageSynisenseBadge`; tooltip; wired into metadata row | Done (6/6) | `synisense_metrics.py:142-200` (1 call vs N) |
| C | `ProviderLine` component; hover tooltip with fallback chain; wired in; provider id → friendly label map | Done (4/4) | `ProviderLine.jsx` |
| D | Trust panel link in audit dialog; routes via global event bus; `data-testid` | Done (3/3) | `Chat.jsx:1698-1715`; `AppShell.jsx:155-162` |
| E | Banned-vocab grep on Chat copy | Done (1/1) | grep returns 0 |
| F | `WorkspaceEntryGate workspace="chat"` | Done (1/1) | `Chat.jsx:772-774` |

**Done: 21 / 21**
**Deviations:**
- Tooltip on touch devices surfaces via long-press only (acceptable per CHAT closure)
- Trust Panel cross-link uses `window.dispatchEvent` (event bus) instead of React context (pragmatic, single-consumer)

### 2.3 Solva

- **Sprint brief:** BRIEF NOT FOUND.
- **Closure doc:** `/app/docs/sprints/SOLVA.md` (124 lines).
- **Requirements count: 6 sections** (A palette · B per-section Synisense badge · C export template v7 · D placeholder_stub cleanup · E streaming transition · F v2 → v3 brand)

| Section | Items | Status | Evidence |
|---|---|---|---|
| A | Hex literals removed (was 69, now 0); `tokens.js` TOKEN/FONT bridge; per-file sweep; banned-vocab grep clean | Done (4/4) | grep returns 0 across SolvaSession/SolvaSessions/SolvaLanding/TransitionMessage/SolvaArtefact |
| B | `GET /api/solva/v2/sessions/{sid}/synisense-breakdown`; session_id threading; inline badge; storyline at top; wired in artefact | Done (5/5) | `solva_v2.py:1946-2057`; `SolvaArtefact.jsx:158-179, 312-369` |
| C | PDF HTML palette; DOCX color tokens; font runs preserved (Georgia/Calibri intentionally for hash stability); byte-determinism verified | Done (4/4) | `templates/solva_artefact.html`; `solva_artefact_export.py:451-465`; SHA-256 stable across 2 renders |
| D | `placeholder_stub` removed from `SHIELD_BYPASS_REASONS` | Done (2/2) | `services/solva_v2/llm_adapter.py:45-60` |
| E | `WorkspaceEntryGate workspace="solva"` | Done (1/1) | `pages/SolvaApp.jsx:19` |
| F | UI v2 labels swept (zero); code namespace `solva_v2` preserved for audit-chain | Done (2/2) | grep clean; `routers/solva_v2.py:81-88` explanatory comment |

**Done: 18 / 18** (sprint scope)
**Pre-existing failures NOT caused by sprint:**
- `test_solva_v2_shield_invariant.py::test_invariant_holds_across_full_session` — `KeyError: 'clusters'` at HEAD without sprint changes
- `test_solva_v2_session_limits.py` — 3 tests failing on session-cap logic (pre-existing)
- 9 errors are fixture / mongo connectivity issues for sub-surface validator tests
- Verified via `git stash` + retest at HEAD

**Deviations:**
- DOCX runs stay Georgia/Calibri NOT Source Serif/Inter (intentional — byte-determinism for hash-chained exports)
- "Solva v3" is brand-only — code stays `solva_v2.*` everywhere (deliberate non-rename to preserve audit row integrity)
- Pre-sprint sessions return `per_surface: []` (fallback time-window catches most; UI degrades to "—" badge)

### 2.4 Work Studio

- **Sprint brief:** BRIEF NOT FOUND.
- **Closure doc:** `/app/docs/sprints/STUDIO.md` (137 lines).
- **Requirements count: 7 sections × items = ~20 total** (A palette · B per-artefact badge + export stamp · C template v7 · D CI determinism · E llm_pass persistence on failure · F citation validator · G streaming transition)

| Section | Items | Status | Evidence |
|---|---|---|---|
| A | Hex literals removed; v7 palette + typography sweep | Done (4/4) | grep returns 0 across `pages/WorkStudio.jsx`, `pages/StudioComposerPage.jsx`, `pages/Decks.jsx`, `components/studio/` |
| B | Breakdown endpoint; `artefact_id` threaded; frontend badge; storyline below badge; wired into drawer | Done (6/6) | `routers/work_studio_export.py:1334-1421`; `PerArtefactSynisenseBadge.jsx`; `WorkStudio.jsx:202-216` |
| B | **PDF/DOCX/PPTX audit footer stamp** | Partial | Generators carry the footer (`brief.audit_summary`) BUT route at `work_studio_phase_c.py` never POPULATES the field on `brief` before render — exports never actually carry the storyline today. **AMBIGUOUS / GAP** |
| B | `Brief.audit_summary` schema field | Done | `backend/work_studio/brief.py:67-72` |
| C | DOCX/PPTX/PDF palette migrated; font runs preserved; determinism verified | Done (5/5) | `test_render_determinism.py` 6/6 GREEN |
| D | Test file; SOURCE_DATE_EPOCH pinned; citation-index regression | Done (3/3) | `tests/test_render_determinism.py:1-200` |
| E | Partial-state capture; pass1 failure persists; pass2 failure persists; worker persists on raise | Done (4/4) | `routers/work_studio_export.py:381-395, 533-540, 700-712, 600-617` |
| F | Phantom citation indices dropped silently; regression test | Done (3/3) | `services/work_studio_export.py:148-170` |
| G | `WorkspaceEntryGate workspace="work_studio"` | Done (1/1) | `pages/WorkStudio.jsx:48, 221` |

**Done: 22 / 23**
**Partial: 1** — audit footer wiring (generators ready, route doesn't populate from synisense_runs)
**Deviations:**
- Pre-sprint artefacts return empty `per_surface` (no artefact_id threaded — degrades to "—" badge)
- PPTX AUDIT slide uses primitive shapes (intentional for byte-determinism)
- STUDIO closure explicitly acknowledges this in §"Known limitations point 1": "Caller-side `Brief.audit_summary` not yet auto-populated"
- `render_deck_pdf` raises `NotImplementedError` — PPTX is the deck output of record (intentional per spec)

### 2.5 Cycle Manager

- **Sprint brief:** **BRIEF NOT FOUND** for a v7 cycle-manager sprint.
- **Fallback design doc:** `/app/docs/NED_CYCLE_MANAGER_DESIGN.md` (178 lines, design-only per spec).
- **Source-of-truth:** `PRODUCT_SPEC.md §5.6 Cycle Manager` + `Akki_NED_Cycle_Manager_Module_Specification.docx` (referenced by `routers/ned_cycle.py`).
- **Requirements count: 12 total** (Executive 6-step stepper + NED design × 6 surfaces)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Executive 6-step stepper (Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation) | Done | `pages/Cycle.jsx`; `routers/cycle_manager.py` (14 endpoints) |
| 2 | Cycle Manager additive collections (`cycle_agendas`, `cycle_team`, `cycle_contributions`, `cycle_followups`) | Done | router writes verified |
| 3 | Follow-ups send via Resend (`From: akki+<context_slug>@syni.ai`) | Done | `routers/cycle_manager.py` |
| 4 | Draft Compilation (citation-cited summary) | Partial | Works but injects placeholder citation row `{"doc_id":"stub",...}` when no real citation resolved (`routers/cycle_manager.py:726`) |
| 5 | Per-step audit_log rows | Done | per-step audit emitted |
| 6 | NED catch-up: Briefing pre-read + private notes | Partial | `routers/ned_cycle.py` ships endpoints (`GET /ned/landing`, `GET /ned/committee/{cid}/{committee}`, `POST /ned/meetings/{id}/notes` etc — 12 routes); CONTRADICTS PRODUCT_SPEC §5.6 which still claims "NED side has zero code today" |
| 7 | NED Questions-to-ask surface | Done | `routers/ned_cycle.py` |
| 8 | NED Signals worth digging into | Done | `routers/ned_cycle.py` cross-references signals |
| 9 | NED Minutes consumption + diff | Partial | endpoint present, but exec compilation diff narrative not verified |
| 10 | NED Commitments + decisions log | Partial | extraction reuses `routers/prepare.py:minutes/*` |
| 11 | NED Open questions ledger | Done | `routers/ned_cycle.py:_positions/_followups` |
| 12 | NED-private writes isolation (`db.ned_annotations`) | Done | `services.privacy_wall.cross_context_query` import; per-account scoping |

**Done: 7 / 12**
**Partial: 4** (Compilation placeholder citation, NED catch-up coverage, Minutes diff narrative, Commitments extraction)
**Not done: 0** — but the **scope is undefined without a sprint brief**.
**Deviations:**
- PRODUCT_SPEC §5.6 outdated — claims "NED side has zero code today"; reality is `routers/ned_cycle.py` ships **12 routes** under `/api/ned/*` + `pages/ned/NedMeeting.jsx`, `pages/ned/NedCommittee.jsx`
- 4 hex literals remain in `pages/Cycle.jsx` (`#8B2E2B`) — bypasses v7 token system on bg/text/border combos; not part of v7-Studio sweep
- Two cycle routers coexist (`cycle_manager.py` Phase D + legacy `cycle.py` 30 endpoints) — intentional but cognitive collision risk

### 2.6 Monitor

- **Sprint brief:** BRIEF NOT FOUND.
- **Fallback:** `PRODUCT_SPEC.md` does not have a dedicated Monitor section. Code header `routers/monitor.py:1-22` is the closest contract.
- **Requirements count: 6 total** (CEO/CFO/COO/Commercial/NED/Other function-aware filters + Strategic Goals dashboard)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | `GET /api/contexts/{cid}/monitor?function=...` endpoint | Done | `routers/monitor.py` |
| 2 | Function-aware filtering (CEO/CFO/COO/Commercial/NED/Other) | Done | header comments + body |
| 3 | Reportee fuzzy match against area-of-ownership keywords | Done | `routers/monitor.py` |
| 4 | Strategic Goals: CRUD + LLM extract from documents | Done | `routers/strategic_goals.py`; CRUD + score_history sparkline |
| 5 | `Monitor.jsx` page with function chip strip + tiles | Done | `pages/Monitor.jsx`; `FunctionPickerModal` |
| 6 | NED scorecard mode (read-only) | Done | per PRD iter28 |

**Done: 6 / 6**
**Deviations:**
- Function picker now in `account.preferences.executive_function` (not URL param) — diverges from initial v1 chip strip; users cannot pick on the page (must edit profile)
- NED users see no chip strip — single board scorecard
- Monitor surface NOT covered by any v7 sprint; palette compliance not separately audited

### 2.7 Pulse

- **Sprint brief:** BRIEF NOT FOUND.
- **Fallback:** `PRODUCT_SPEC.md §5.10 Akki Pulse — same-context aggregator [PARTIAL]`
- **Requirements count: 7 total** (feed + 5 social actions + Synisense routing)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Feed at `/app/pulse` with type/freshness filters | Done | `pages/Pulse.jsx` (489 lines); `routers/pulse.py` |
| 2 | Social action: save | Done | `POST .../signals/{sid}/save` |
| 3 | Social action: comment | Done | reuses `routers/comments.py` |
| 4 | Social action: share | Done | reuses `routers/shares.py` |
| 5 | Social action: resolve | Done | `routers/pulse.py` |
| 6 | Social action: take-to-Solva | Done | mints Solva v2 session pre-populated |
| 7 | Pulse routed through Synisense (`surface="pulse"`) | **Not done** | PRODUCT_SPEC §5.2 confirms — "Pulse signals are not routed through Synisense at read time"; same-context boundary holds by accident-of-architecture |

**Done: 6 / 7**
**Not done: 1** (Pulse Synisense routing — DEFERRED behind Privacy Wall §2c per spec)
**Deviations:**
- Cross-context aggregation deferred (matches spec) — DEFERRED behind Privacy Wall §2c
- `db.signals.topic` field does not enforce `PULSE_CLASSIFIER_ENUM` (privacy-wall constant defined but unused) — backfill needed
- 2 hex literals remain in `pages/Pulse.jsx` (`#8B2E2B`) — not part of any v7 sweep
- Cluster resolution still labelled "deferred" (`routers/pulse.py:426`)
- Orphan file `frontend/src/pages/PulsePlaceholder.jsx` not imported anywhere (cleanup item)

### 2.8 Learn

- **Sprint brief:** BRIEF NOT FOUND.
- **Fallback:** `PRODUCT_SPEC.md §5.x` mentions Learn via `routers/learn.py` (`POST /learn/research`).
- **Requirements count: 5 total** (library, search, topic filter, recency tabs, personalisation)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Library of curated articles + News + TL Articles + Videos + Case Studies | Done | `lib/learnContent.js`; iter18-20 PRD entries; `LEARN_NEWS` array |
| 2 | Search + topic filter | Done | `pages/Learn.jsx` |
| 3 | 4-tab content-type segmentation | Done | iter18 — News / TL Articles / Videos / Case Studies |
| 4 | Recency tabs (All / Fresh ≤5d / Stayed a bit >5d) | Done | iter30 — `learn-recency-tabs` |
| 5 | Sector + jurisdiction personalisation | Done | `POST /learn/research` accepts `context_id`; CBK-flavoured Kenyan results verified |

**Done: 5 / 5**
**Deviations:**
- Learn is **not** wrapped in `WorkspaceEntryGate` (no streaming transition on first open) — deviation if v7 directive applies; no sprint brief said it should
- Horizontal `space-y-4 max-w-2xl` layout per iter27 — diverges from 2-up grid earlier in iter18

---

## 3. Deployment Briefs

- **Sprint brief:** `/app/docs/DEPLOYMENT.md` (598 lines) — production runbook, NOT a sprint brief
- **Architecture target:** Azure VM (Ubuntu 22.04 LTS) + Cosmos DB vCore + MinIO + ClamAV via Cloudflare proxy
- **Requirements count: 11 total** (infra prereqs + secret flow + image flow + cron + health + storage paths + 4 deploy blockers)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Architecture diagram + bidirectional flows documented | Done | `docs/DEPLOYMENT.md §1` |
| 2 | Azure VM bootstrap script | Done | `scripts/deploy/bootstrap-vm.sh` |
| 3 | Secret load script (Key Vault → `/etc/akki/akki.env`) | Done | `scripts/deploy/akki-load-secrets.sh` |
| 4 | GitHub Actions deploy workflow | Done | `.github/workflows/deploy.yml` |
| 5 | docker-compose.prod.yml present | Done | `/app/docker-compose.prod.yml` |
| 6 | Rollback script | Done | `scripts/deploy/akki-rollback.sh` |
| 7 | Secret rotation across Group A list pre-prod | **Not done** | PRD risk #7 — strategic blocker |
| 8 | Cosmos vCore `retrywrites=false` in connection string | **Not done** | Listed as deploy blocker |
| 9 | Postmark inbound webhook secret in Key Vault | **Not done** | Listed as deploy blocker |
| 10 | `db.health_check` TTL index | **Not done** | Row bloat risk; deploy blocker #7 in runbook |
| 11 | Distributed lock for APScheduler (multi-replica safety) | **Not done** | Single-replica constraint loud in runbook |

**Done: 6 / 11**
**Not done: 5** (all explicitly listed as deploy blockers — see PRODUCT_SPEC §14)
**Deviations:**
- Deployment scaffolding is **scaffolded**, not **cut over** — production has never run this stack live
- ClamAV bypass via `ALLOW_UNSAFE_UPLOADS=true` is dev-only (intentional)
- `STORAGE_BACKEND=local` in dev (production must reverse)
- Resend in test mode in dev — production must verify a sending domain

---

## 4. State of Styling, UX/UI architecture, user journey fluency

### 4.1 v7 palette migration coverage per surface

| Surface | Status | Evidence |
|---|---|---|
| Marketing Website (`/`, `/why-akki`, …) | Done | PRE_v7_website sprint — bronze stripped, 7-token v7 live |
| Sandbox | Done | Aliased through v7 tokens (palette only) |
| Sign-in / Sign-up | Done | HOME sprint — v7 palette confirmed via screenshot |
| App index.css (shell tokens) | Done | HOME sprint — 7-token palette + legacy aliases |
| Home (AppHome, HomeExecutive/NED/Dual/Undeclared) | Done | grep returns 0 hex literals |
| Chat | Done | CHAT sprint — MarkdownMessage.css + ModelAvatar migrated |
| Solva (SolvaApp, SolvaLanding, SolvaSession, SolvaArtefact) | Done | SOLVA sprint — was 69 hex literals → 0 |
| Work Studio (WorkStudio, StudioComposer, BlockComposer, Decks) | Done | STUDIO sprint — extended palette swept; grep 0 |
| Cycle Manager (Cycle.jsx) | **Partial** | 4 `#8B2E2B` hex literals remain at lines 63, 223, 340, 421 |
| Monitor | **Not started** | No sprint brief or sweep; palette compliance unverified |
| Pulse | **Partial** | 2 `#8B2E2B` hex literals remain at lines 88, 147 |
| Learn | **Not started** | No sprint brief or sweep; palette compliance unverified |
| Document Journal (`Workspace.jsx`) | Unverified | Not part of any post-v7 sprint |
| Plays / PlayView / PlaysLibrary | Unverified | Not part of any post-v7 sprint |

### 4.2 Typography compliance (Source Serif 4 / Inter / JetBrains Mono)

- **Declaration:** `frontend/src/index.css:31-56` + `frontend/src/website/style.css:39-62` — both use `@font-face local()` chains
- **woff2 self-hosting:** **NOT shipped** — production users without the fonts installed locally fall through to Georgia / system sans / system mono
- **DOCX exports (Solva + Studio):** Intentionally **stay Georgia / Calibri** — switching to Source Serif/Inter would break byte-determinism on hash-chained exports
- **Cycle / Monitor / Pulse / Learn surfaces:** Font tokens flow through CSS vars resolving to `--font-display` / `--font-ui` / `--font-mono` — but no per-page sprint enforced banned-vocab + font sweep

### 4.3 User journey gaps (broken hand-offs)

| Journey | Surface | Gap |
|---|---|---|
| Solva session → Work Studio export | `routers/work_studio_phase_c.py` | Brief.audit_summary never populated from `synisense_runs` — generated exports do not actually carry the audit footer despite the infrastructure being in place |
| NED Cycle Manager surfaces ↔ PRODUCT_SPEC | doc inconsistency | Spec §5.6 claims NED has zero code; reality is 12 routes in `ned_cycle.py` + 2 frontend pages. Onboarding doc out of date |
| `/app/learn` first-mount | `pages/Learn.jsx` | No `WorkspaceEntryGate` wrap (deviation from the K5 pattern applied to Solva/Cycle/Studio/Monitor/Chat) |
| Chat audit Trust Panel link | `Chat.jsx` ↔ `AppShell.jsx` | Uses `window.dispatchEvent` event bus rather than React context — works, but fragile if a second consumer needs it |
| Pulse same-context boundary | `routers/pulse.py` | NOT routed through `services/privacy_wall.project_for_pulse` — same-context boundary holds by accident-of-architecture, not by guard |
| `db.signals.topic` field | mongo | Does NOT enforce `PULSE_CLASSIFIER_ENUM` — blocks cross-context lift |
| Invitation email | `routers/contexts.py:405` | Comment claims "un-stubbed Phase G3"; PRODUCT_SPEC §14 risk #6 claims stubbed — **AMBIGUOUS, live state unverified** |
| GPT-5.2 streaming | `routers/chat.py` | Proxy-buffered only; no direct OpenAI streaming (boot log makes this explicit) |
| Cross-context Pulse | `services/privacy_wall.py` | `redact_for_pulse_text` no-op; `assemble_pulse_prompt` raises `NotImplementedError("Phase 2c")` |
| Strategic-deliverable chat Pass 2 | `routers/chat.py` | Proxy-buffered only; not direct-streamed (deferred until traffic justifies) |

---

## 5. 3rd Party Integrations

| Provider | Status | File path(s) | Notes / MOCKED behaviour |
|---|---|---|---|
| **Anthropic** (Claude Sonnet 4.5 / Haiku 4.5) | Wired | `services/llm_streaming.py:14-77`; `llm_service.py:163`; `services/two_pass.py` | Direct SDK (Phase B.3) + Emergent proxy auto-fallback. Boot log `[chat] streaming: claude=direct_stream` |
| **OpenAI** (GPT-5.2) | Partial | `services/llm_streaming.py:174-229` (code path exists; only fires if `OPENAI_API_KEY` set) | Direct streaming **PARTIAL** — code exists at `:190-229`; falls back to Emergent proxy when `OPENAI_API_KEY` absent. Boot log `gpt=proxy_buffered` in current dev |
| **Google Gemini** (2.5 Flash / 2.5 Pro) | Wired | `services/llm_streaming.py`; `services/synisense/llm_fallback.py` | Direct SDK + proxy fallback. Used as validator tier + Synisense layer-3 small-model judge |
| **Emergent Universal Key** (multi-provider proxy) | Wired | `services/llm_streaming.py:176-184`; `.env:EMERGENT_LLM_KEY` | Backstop for direct paths; used by Sora-2 / image gen / etc. |
| **Resend** (outbound email) | Partial — **MOCKED IN DEV (TEST MODE)** | `backend/email_service.py:155, 211` | Returns `mode: "test_mode_restricted"` for any recipient not on the registered test list. Production must verify a sending domain before real delivery |
| **Postmark** (inbound email webhook) | Partial | `routers/inbound_email.py`; `.env:POSTMARK_*` | URL-shared-secret authentication today (not HMAC). Phase G2 added HMAC support but `POSTMARK_USE_HMAC=false` in dev. Production boot guard requires the secret to be set |
| **Plausible** (analytics) | Wired | `frontend/src/website/WebsiteShell.jsx:51-58` | Domain `akki.syni.ai`; lazy-injected; loaded on website + sign-in surfaces. **NOT** loaded on `/sandbox` (intentional — sandbox is not analytics surface) or `/app/*` |
| **Stripe** (billing) | Planned — **DISABLED** | `services/stripe_webhook.py` exists; `BILLING_ENABLED=false` in `.env` | Code path present; webhook handler scaffolded; secrets unset; boot guard refuses if flag flipped without keys |
| **Azure Key Vault** (production secrets) | Planned (scaffolded) | `scripts/deploy/akki-load-secrets.sh` | Loader script present; VM managed identity assumed; **never run in production yet** |
| **Azure Container Registry** (image hosting) | Planned (scaffolded) | `.github/workflows/deploy.yml` | GitHub Actions wired for push → ACR → SSH; **never run in production yet** |
| **Azure Cosmos DB for MongoDB vCore** | Planned (scaffolded) | `docs/DEPLOYMENT.md §1` | Connection-string format documented; **`retrywrites=false` MANDATORY, NOT YET CONFIGURED** |
| **Cloudflare** (edge TLS, WAF) | Planned (scaffolded) | `docs/DEPLOYMENT.md §1` | Origin certificate model documented; **never run in production yet** |
| **MinIO** (S3-compatible storage) | Wired (dev=local, prod=MinIO scaffolded) | `backend/services/storage_service.py` | `STORAGE_BACKEND=local` in dev pod; production runbook reverses to `STORAGE_BACKEND=s3` against MinIO container |
| **ClamAV** (virus scanning) | Wired (BYPASSED IN DEV) | `services/clamav_service.py` | `ALLOW_UNSAFE_UPLOADS=true` in dev = **BYPASSED**. Production must set `false` and run the daemon |
| **Microsoft Presidio** (PII NER layer 2) | Wired | `services/synisense/presidio_engine.py` | spaCy `en_core_web_lg` baked into prod Docker image at build time |
| **APScheduler** (in-process cron) | Wired (SINGLE-REPLICA CONSTRAINT) | `backend/server.py` `:540+` | Crons fire only if `AKKI_CRON_SECRET` set. **Running >1 replica duplicates every cron** — distributed-lock work pending |
| **WeasyPrint / python-docx / python-pptx** | Wired | `services/work_studio_export.py`; `work_studio/{pdf,docx,pptx}_generator.py` | Deterministic; `render_deck_pdf` raises `NotImplementedError` intentionally (PPTX is deck output of record) |

---

*End of audit.*
