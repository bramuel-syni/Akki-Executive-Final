# Akki — Product Features & Functionality Review
_Generated 2026-05-29 · Source of truth: repo state at HEAD_

---

## 1. Executive Summary

**Akki** is a board-grade decision-support workspace for founders and executive teams. It packages an LLM-backed strategic diagnostic engine (**Solva**), a structured authoring surface (**Work Studio**), a goal-evolution monitor (**Monitor**), and a task ladder (**Task Manager**) into one coherent app. The core promise is *seasoned-partner thinking, on demand*: numerically grounded diagnoses, calibrated confidence, named biases, adversarial counter-cases, and pre-mortem failure modes — never a chatbot pretending to be a CEO.

Primary users today: founders / CXOs at Series A → C, plus the small executive team they trust (max ~6 seats per tenant). A separate admin surface seeds tenants, manages cohort invites, and watches LLM spend.

**Status legend used throughout:**
- ✅ **Shipped & verified** — code in `main`, raw-trace evidence inline in PHASE_LEDGER, tests green
- 🟡 **In-flight** — actively being built or under user verification
- ⬜ **Planned** — scoped, not started
- ⚠️ **Blocked / Mocked** — surface exists but returns mocked / 503 / placeholder response

---

## 2. Personas & Access Model

| Persona | Surfaces they live in | Auth path |
|---|---|---|
| **Founder / CEO / executive** | Home, Solva, Work Studio, Monitor, Task Manager, Pulse, Chat, Documents, Cycle | Google OAuth (Emergent-managed) ✅ · email+password fallback ✅ · magic-link invite ✅ |
| **Member / contributor** | Same surfaces, scoped by tenant + role | Same as founder |
| **NED (Non-Exec Director)** | NED Inbox, NED Committee, NED Meeting (purpose-built read-mostly views) | Same — assigned to a tenant by the founder |
| **Superadmin** | `/admin/*` console — Tenants, Users, Cohort Console, Extractions, Auth Events, Health Dashboard, LLM Spend, Sandbox KPI, Signal KPI, Cohort Copy Editor | Email+password seeded via `seed_superadmin.py` |

Auth integrations:
- **Google OAuth (Emergent-managed)** ✅ — wired at `/api/auth/oauth/google/*`, redirect URI `https://akki-executive.preview.emergentagent.com/api/oauth/google/callback`
- **Microsoft Graph OAuth** ⚠️ **MOCKED** — `/api/auth/oauth/microsoft/*` returns `503 {error: "microsoft_oauth_not_configured"}` until `MICROSOFT_OAUTH_CLIENT_ID` + `MICROSOFT_OAUTH_CLIENT_SECRET` env vars arrive
- **Magic-link invites** ✅ — superadmin-issued via `Invite Founder` modal; activates trial countdown on click
- **JWT-based session** with refresh-token rotation; `JWT_SECRET` + `JWT_REFRESH_SECRET` separated so they can rotate independently

Tenant model is **single-tenant per app account** today (no cross-tenant impersonation). RBAC matrix lives in `backend/services/rbac.py`.

---

## 3. Feature Inventory (by surface)

### 3.1 Founding Cohort Trial Console ✅

**Surface:** `/admin/cohort` (page: `pages/admin/CohortConsole.jsx`) + `Invite Founder` modal.

**Purpose:** Onboard the first 50–100 founding users without billing infrastructure. Trial is **manually priced + manually granted** — superadmin issues a magic link, user clicks, trial timer starts.

**Key flows:**
- Superadmin opens Cohort Console → clicks `Invite Founder` → enters founder name + email + plan tier → issues magic link
- Resend email API delivers the link from `noreply@akki.syni.ai`
- On click, the activation page (`/invite/accept`, page: `InviteAccept.jsx`) creates the account, mounts the trial countdown, and signs the founder in
- A separate `Cohort Copy Editor` tool lets the team A/B-edit the invite copy without touching frontend code
- Trial status surfaces in the Settings page; expiry triggers a soft account lock (no Stripe involvement yet — `BILLING_ENABLED=false` in `.env`)

**Key endpoints:** `POST /api/admin/cohort/invite`, `POST /api/admin/cohort/resend`, `GET /api/admin/cohort/list`, `GET /api/trial-status`.

**Status:** ✅ Shipped, verified by superadmin testing.

---

### 3.2 Work Studio ✅

**Surface:** `/app/work-studio` (page: `pages/WorkStudio.jsx`) + `/app/documents` (`pages/DocumentsPage.jsx`) + sub-routes.

**Purpose:** The single authoring + reading surface for everything a founder hands the LLM (board memos, briefs, drafts, uploaded references). Replaces an earlier triage-style workflow.

**Key flows:**
- **Drafts + Briefs merged tab** ✅ — Phase Z merged what were previously two split tabs into one canonical journal view; Phase W3.x rewrote the LEFT column rendering
- **Document upload** ✅ — drag-drop or click; backend extracts via Claude Sonnet 4.5 wrapped in `shield_invoke` (PII redaction + provenance metadata)
- **Document Journal page** at `/app/documents` ✅ — single timeline of every uploaded artefact in the tenant
- **Studio Composer** (`/app/work-studio/composer/:id`) ✅ — block-based rich editor; saves blocks to `studio_blocks` collection
- **Render endpoints** — DOCX / PDF / PPTX on-the-fly via `work_studio_render` router (T4.1/G6)
- **Hairline divider + 0.0px-gap discipline** ✅ — locked CSS rules; no tab boundary collapses to a thicker rule
- **Per-document overlay viewer** ✅ — opens inline in the LEFT column without page nav

**Key endpoints (router prefix `/api/work_studio`):** create draft, list documents, save blocks, export, overlay extraction.

**Status:** ✅ Shipped through Phase Z (Document Journal) → Phase Z-slice-4 (canonical Documents page).

---

### 3.3 Monitor ✅

**Surface:** `/app/monitor` (page: `pages/Monitor.jsx`).

**Purpose:** The single pane of glass for goal evolution across the tenant. Watches strategic_goals, tasks, signals, and exec inputs converge over time.

**Key flows:**
- **Progress Timeline** ✅ — auto-populating goal-evolution feed (router: `strategic_goal_evolution.py`); each turn the founder records a signal, the timeline updates without manual intervention
- **Owner capsule strip** ✅ — Phase AA replaced an earlier owner-dropdown affordance with a horizontal capsule strip; visually denser, no nested click-to-reveal interaction
- **Strategic Goals shared primitive** ✅ — `StrategicRow` component (Phase Y slice 1) extracted so the same row pattern renders across Monitor, Task Manager, and Pulse without three separate codepaths
- **Status Assessment** ✅ — `monitor_status_assessment.py` router synthesises a colour-coded status against the goal's last-recorded confidence

**Key endpoints (router prefix `/api`):** `/api/strategic-goals/*`, `/api/strategic-goal-assessment/*`, `/api/strategic-goal-evolution/*`.

**Status:** ✅ Shipped through Phase AA (Monitor v2).

---

### 3.4 Task Manager ✅

**Surface:** `/app/task-manager` (page: `pages/TaskManager.jsx`).

**Purpose:** The execution-side ladder under Monitor. Surfaces `tasks_initiatives` (the new card + initiative pairing) instead of the old flat task list.

**Key flows:**
- **Card composition redesign** ✅ — Phase Y slice 2 collapsed a previously-fragmented card into a single composable `<TaskCard>` that uses the shared `<StrategicRow>` primitive
- **Activity tab** at `/app/task-manager/activity` ✅
- **Initiative grouping** — tasks roll up under named initiatives; initiative-level progress aggregates from child task confidence

**Key endpoints (router prefix `/api`):** `/api/tasks-initiatives/*`, `/api/tasks/*`.

**Status:** ✅ Shipped through Phase Y slices 1+2.

---

### 3.5 Home 1 / Home 2 ✅

**Surface:** `/app/today` (Home 1, page: `pages/AppHome.jsx`) + `/app/company` (Home 2, page: `pages/CompanyHome.jsx`).

**Purpose:**
- **Home 1 (Today)** — personal landing: today's signals, pending Solva sessions, NED inbox count, recent documents
- **Home 2 (Company)** — tenant-wide view: cross-team strategic goals, exec team activity stream, current cycle status

Both consume the same backend (`company_home.py` router) but render different facets.

**Status:** ✅ Shipped. ⚠️ Known cosmetic gap: `CompanyHome.jsx` causes ~39px horizontal overflow at 820px viewport (P3 parked, see §8).

---

### 3.6 Solva v1 (Diagnostic Artefact) ✅

**Surface:** `/app/solva/session/:sid` when feature flag `SOLVA_V2_ENABLED=false` (default off in production until v2 is approved).

**Purpose:** Deliver a fully-formatted, board-grade strategic diagnostic from a 5-layer reasoning pass:
- **Layer 0 — Frame Audit** (the user's stated framing is reflected back, named, and stress-tested)
- **Layer 1 — Surface** (what's literally on the page from intake)
- **Layer 2 — Depth** (what's underneath — tensions surfaced)
- **Layer 3 — Synthesis** (scenario weighting, confidence calibration, sensitivity analysis)
- **Layer 4 — Reflection** (3 reflection questions back at the founder)

**Engine location:** `backend/services/solva/` (the original v1 codepath).

**Frontend renderer:** `frontend/src/components/solva/artefact/` (one prose-style scrollable artefact, no slide pagination).

**Locked invariant:** Solva v1 is **byte-identical guarded** during v2 development. Any v2 work that touches v1 files fails the regression suite.

**Status:** ✅ Shipped, in production; flag-gated so v2 can ship behind a switch.

---

### 3.7 Solva v2 (Elevated Diagnostic Partner) 🟡

**Surface:** `/app/solva/session/:sid` when `SOLVA_V2_ENABLED=true` OR superadmin auto-flag is set OR URL carries `?v2=1`.

**Purpose:** Upgrade the v1 prose artefact into a **15-element slide-grade artefact** with progressive live-reasoning rendering, named biases, an adversarial debate, and a pre-mortem. Gives the founder a board-ready deck *and* the seasoned-partner intuition that v1 lacks.

**Engine location:** `backend/services/solva_v2/`.

**Frontend renderer:** `frontend/src/components/solva/artefact_v2/` — 15 slide components + orchestrator + SSE consumer hook + reasoning ticker.

#### 3.7.1 Slice-by-slice ship status

| Slice | Scope | User-facing value | Status | Evidence |
|---|---|---|---|---|
| **1a** | Structured JSON schema (initially 13 elements) + integrity validators (citation_lint, confidence_calibration_audit, refuse_to_decide_enforcement, methodological_honesty_present) | Backend contract that the frontend can rely on; validators block empty / hallucinated diagnoses | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Solva v2 — Slice 1a CLOSED" |
| **1b** | Payload builder, v2 prompts, parity tests vs v1 telemetry | The v2 schema is auto-populated from existing audit-log entries — no new founder intake required | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Slice 1b CLOSED" |
| **2a** | Backend payload endpoint `GET /api/solva/sessions/{sid}/v2/payload` + frontend `SlideShell` + 4 core slides + feature-flag wiring | Founders behind the flag see the new deck | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Slice 2a CLOSED" |
| **2b** | All 13 slide kinds + section dividers + `@media print` stylesheet + admin auto-flag + cross-account URL override + 3 contract tests | Full deck renders end-to-end; clean print output | ✅ Shipped 2026-05-29 (after one correction round) | PHASE_LEDGER §"Slice 2b CORRECTION CLOSED" |
| **2b — Identity audit** | Sweep all v2 code paths for stray `SOLVE` / `Solve` strings; lock 8 audit-guard tests | Brand consistency: only `Solva` (not `SOLVE`) appears in the artefact and engine | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Slice 2b IDENTITY AUDIT CLOSED" |
| **3a** | Backend SSE reasoning stream — `stream_schema.py`, `stream_synthesizer.py`, `GET /api/solva/sessions/{sid}/v2/stream` | Engine emits a typed event stream the frontend can subscribe to | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Slice 3a CLOSED" |
| **3b** | Frontend SSE consumer (`useSolvaReasoningStream` hook) + per-slide `loading → ready → placeholder` skeleton transitions + live `SolvaReasoningTicker` + `?replay=0/1` URL override | The founder watches the diagnostic *think* — slides crystallise as each layer completes | ✅ Shipped 2026-05-29 (after 2 correction rounds — a recurring "claimed-evidence-doesn't-reproduce" failure mode locked into the discipline doc) | PHASE_LEDGER §"Slice 3b SECOND CORRECTION CLOSED" |
| **4** | Bias inventory rendering — 14th locked slide; 3 named biases (e.g. confirmation, anchoring, narrative_fallacy) each citing user inputs; likelihood pill (low/med/high) at allowlisted opacity | Trust pillar 2: Solva names the bias the framing might be subject to and grounds it in the actual intake | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Slice 4 (Bias Inventory) close-out evidence" |
| **5** | Adversarial debate (steel-man "case against" callout on most-critical pathway item AND leading decision branch) + Pre-mortem slide (15th locked slide; 3 evidence-grounded imagined-failure modes with triggering signals + observational counter-action) | Trust pillar 4: Solva *argues against itself* before the founder commits, and imagines how the recommended pathway could fail 12 months out | ✅ Shipped 2026-05-29 | PHASE_LEDGER §"Slice 5 (Adversarial debate + Pre-mortem)" |
| **6** | Cost asymmetry slide — explicit framing of "what does Plan A cost if it's wrong vs. Plan B if it's wrong?" | Pillar 5: makes the asymmetric-bet logic legible in deck form | ⬜ Planned (next P1) | — |
| **7** | Verification + polish — `data-solva-v2-slide-ready-at` timestamp attributes; Session Complete replay side-panel re-opening from the topbar icon stub | Trust pillar 3 polish: founders can audit when each slide became authoritative | ⬜ Planned (P1) | — |

#### 3.7.2 Locked 15-slide deck order

`cover · headline · tensions_overview · per_tension · scenarios_overview · per_scenario_table · sensitivity · reflection · bias_inventory · pathway · pre_mortem · decision_logic · risk_mitigation · methodological_honesty · in_closing`

#### 3.7.3 Trust pillars (named contracts the engine enforces)

1. **No hallucinated numbers** — `citation_lint` validator blocks any numerical claim without a `source_input_id` resolving to a real audit-log / user-turn / coarse layer tag
2. **Explicit confidence grounding** — `confidence_calibration_audit` blocks confidence percentages without a calibration-reasoning string ≥ locked min length
3. **Refuse-to-decide observational tone** — `refuse_to_decide_enforcement` blocks imperative phrasings ("You must…", "We recommend…", "Pivot now"); only observational tone passes
4. **Adversarial debate** — every artefact carries a steel-man counter on the leading conclusion + a 3-mode pre-mortem (Slice 5)
5. **Bias inventory** — every artefact names ≥1 bias that may be operating, with evidence and a low/med/high likelihood pill (Slice 4)
6. **Methodological honesty** — every artefact closes with a "what this report is / what it is not" disclosure of the diagnostic's own limits
7. **Live reasoning visible** — the founder watches Solva think (Slice 3)

#### 3.7.4 Test coverage

| Surface | Count |
|---|---|
| Solva v2 schema + validators + render + parity + multi-viewport | **381 passed** |
| Quarantined / waiting on engine-side rewrite | 23 skipped (pre-existing) |
| Failed | 0 |

`v1 byte-identical guard:` `git diff backend/services/solva backend/services/solva_v1 frontend/src/components/solva/artefact` returns empty — verified at every Solva v2 close-out.

**Status:** 🟡 In-flight overall (Slice 6 + 7 outstanding); ✅ Shipped through Slice 5 inclusive.

---

### 3.8 Adjacent surfaces (covered for completeness)

| Surface | Page | Status |
|---|---|---|
| **Pulse** | `pages/Pulse.jsx` | ✅ Shipped — daily surfacing of new signals, exec replies, NED nudges |
| **Chat** | `pages/Chat.jsx` | ✅ Shipped — direct LLM chat (Claude Sonnet 4.5 / Gemini 2.5 Flash via `chat` service); `ArchivedChats` page for history |
| **Cycle** | `pages/Cycle.jsx`, `cycle/CycleList.jsx`, `cycle/CycleDraftJournal.jsx`, `cycle/CycleReadyJournal.jsx` | ✅ Shipped — quarterly board-cycle authoring + ready/draft journal pair |
| **Daily Review** | `pages/DailyReview.jsx` | ✅ Shipped — morning cycle prompt |
| **Decks** | `pages/Decks.jsx` | ✅ Shipped — deck library |
| **Documents** | `pages/DocumentsPage.jsx` | ✅ Shipped (Phase Z-slice-4) |
| **Influence Map** | `pages/InfluenceMap.jsx` | ✅ Shipped — stakeholder graph |
| **Lens Room** | `pages/LensRoom.jsx` | ✅ Shipped — multi-lens diagnostic side-by-side |
| **NED Inbox / Committee / Meeting** | `pages/ned/*` | ✅ Shipped — NED-specific persona surface |
| **Inbound Queue** | `pages/InboundQueue.jsx` | ✅ Shipped — Postmark + SendGrid inbound email triage |
| **Trust Center** | `pages/TrustCenter.jsx` | ✅ Shipped — security + privacy posture page |
| **Synisense Observability** | `pages/SynisenseObservability.jsx` | ✅ Shipped — internal LLM-shield observability dashboard |
| **Marketing site** | `pages/marketing/{About,Blog,Plans,Security,Enterprise,EarlyAccess,Features}.jsx` | ✅ Shipped — public-facing pages on the same React SPA |

---

### 3.9 Integrations

| Integration | Purpose | Status |
|---|---|---|
| **Anthropic Claude Sonnet 4.5** (via `shield_invoke` + Emergent LLM key as fallback) | Primary diagnostic + extraction LLM (`ANTHROPIC_STREAM_MODEL=claude-sonnet-4-5-20250929`) | ✅ Shipped |
| **Gemini 2.5 Flash** | Chat secondary model (`GEMINI_STREAM_MODEL=gemini-2.5-flash`) | ✅ Shipped |
| **OpenAI** | Tertiary fallback for chat + embeddings | ✅ Shipped |
| **Emergent LLM Key** | Universal key for OpenAI / Anthropic / Gemini text + Nano Banana image gen + Sora 2 video | ✅ Shipped (`EMERGENT_LLM_KEY` set) |
| **Resend** (email) | Outbound transactional email from `noreply@akki.syni.ai` | ✅ Shipped |
| **Postmark** (inbound + outbound) | Bounce/complaint webhooks + cycle-reply alias inbound | ✅ Shipped (HMAC + Basic-Auth + URL-secret tri-mode auth) |
| **SendGrid** | Backup outbound + inbound parse on `inbound.akki.syni.ai` | ✅ Shipped (sandbox key in dev — must rotate to production-tier with verified `@akki.ai` domain before launch) |
| **Google OAuth (Emergent-managed)** | Social sign-in | ✅ Shipped |
| **Microsoft Graph OAuth** | Social sign-in via Microsoft | ⚠️ **MOCKED** — returns 503 `microsoft_oauth_not_configured` until creds added |
| **MinIO / S3** (object storage) | Document uploads | ✅ Shipped (`STORAGE_BACKEND=local` in dev pod; production must flip to `s3` per `DEV_POD_CAVEATS.md`) |
| **ClamAV** | Virus scanning on uploads | ✅ Shipped (sidecar on `127.0.0.1:3310`; `ALLOW_UNSAFE_UPLOADS=true` is a dev-only escape hatch with stderr warning every 60s) |
| **Stripe** | Billing | ⬜ Planned — `BILLING_ENABLED=false` until Founding Cohort matures past trial-issuance phase |
| **Sentry** | Error tracking | ⬜ Planned — `SENTRY_DSN` empty placeholder in `.env` |

---

## 4. Technical Architecture (concise)

- **Stack:** FARM — FastAPI (Python 3.11) + React (CRA) + MongoDB (single DB `akki_dev` in dev, `akki_prod` planned). One supervisor-managed backend on `0.0.0.0:8001`, one supervisor-managed frontend on `:3000`.
- **Server entrypoint:** `backend/server.py` (~1300 LOC) imports ~110 routers under `backend/routers/*.py`; all routes are prefixed `/api/*` so the Kubernetes ingress routes them to the backend pod.
- **SSE streaming:** Solva v2 uses Server-Sent Events for the live-reasoning feed (Slice 3a/3b); chat uses direct token-stream mode (`CHAT_STREAMING_MODE=direct_stream`) into the same SSE pattern.
- **LLM-shield:** `synisense` services intercept every LLM call for PII redaction + provenance metadata + cost capture before the request reaches Anthropic / Gemini / OpenAI.
- **Testing:** Pytest with **Playwright-in-Pytest** for DOM-level multi-viewport regression. Raw-trace evidence rule (locked into PHASE_LEDGER): inline rendered-DOM evidence in close-outs MUST come from the exact founder-facing flow the tester will test — synthetic event injection is forbidden.
- **Feature flags:** Multi-layer (env var, admin auto-flag, URL override) — see `services/solva_v2/feature_flag.py`. Drift-prevention: `SOLVA_V2_ENABLED` is read at call-time, not module-import time, so pytest fixtures can flip it cleanly.
- **Hot reload:** both backend (uvicorn `--reload`) and frontend (CRA dev server) — supervisor restart is only needed on `.env` changes or dependency installs.

---

## 5. Data Model Highlights

| Collection | Shape | Notes |
|---|---|---|
| `accounts` | superadmin + founder accounts | Includes `is_superadmin`, hashed password, refresh-token jti |
| `tenants` | one per founder org | Cohort tier, trial expiry, billing flag (off today) |
| `users` | tenant members + NEDs | RBAC role, joined-at, last-seen |
| `documents` | uploaded artefacts | Provenance, virus-scan status, S3 / local path |
| `extractions_log` | every LLM extraction | Cost in USD-cents, model used, prompt+response hash, PII-redaction trace |
| `audit_log` | every admin action | Tamper-evident hash chain (Phase 12.1 Synisense) |
| `reasoning_audit_log` | Solva engine telemetry | Layer-tagged entries; consumed by `payload_builder.py` and `stream_synthesizer.py` |
| `strategic_goals` | tenant goals | Confidence percentages, owner, last-updated |
| `tasks_initiatives` | execution tasks under goals | Roll up to initiative-level progress |
| `feature_events` | user-facing event stream | What a founder did when — populates Pulse + Activity tabs |
| `studio_blocks` | Work Studio Composer blocks | Block-level versioning, soft-delete |
| `solva_sessions` | one diagnostic session | Holds `synthesis`, `tensions`, `scenarios`, `recommendations` shape consumed by both v1 + v2 builders |
| `cohort_invites` | magic-link invitations | One-time tokens, expiry, click telemetry |
| `auth_events` | login + suspicious activity | Surfaced in `/admin/auth-events` |
| `llm_spend` | rolling cost ledger | Surfaced in `/admin/llm-spend` |

ID convention: every collection uses a UUID4 string `id`, never the Mongo `_id`. `_id` is excluded from every API response (`db.x.find({}, {"_id": 0})` pattern enforced).

---

## 6. Key API Surface

Grouped by domain. Every route is `/api/*` prefixed.

### Auth + Onboarding
- `POST /api/auth/login`, `POST /api/auth/register`, `POST /api/auth/refresh`, `POST /api/auth/logout`
- `GET /api/auth/oauth/google/start`, `GET /api/oauth/google/callback`
- `POST /api/auth/oauth/microsoft/start` ⚠️ returns 503 mock
- `POST /api/auth/magic/issue`, `POST /api/auth/magic/redeem`
- `POST /api/auth/password-reset/request`, `POST /api/auth/password-reset/confirm`

### Solva v2
- `GET  /api/solva/sessions/{sid}/v2/payload` — full 15-slide payload (validated against `ArtefactPayload` schema)
- `GET  /api/solva/sessions/{sid}/v2/stream` — SSE event stream (slide.ready / layer.start / session.complete events)
- `GET  /api/solva/sessions/{sid}/artefact-v2` — convenience wrapper (legacy alias)

### Solva v1 (legacy, still in production)
- `GET  /api/solva/sessions/{sid}` — prose artefact
- `POST /api/solva/sessions/{sid}/turn` — submit a founder turn
- `GET  /api/solva/sessions` — list sessions for tenant

### Work Studio + Documents
- `POST /api/work_studio/draft`, `GET /api/work_studio/documents`, `POST /api/work_studio/blocks/save`
- `GET  /api/work_studio/render/{kind}` (DOCX / PDF / PPTX)
- `POST /api/documents/upload`, `GET /api/documents`, `POST /api/documents/{id}/extract`
- `POST /api/work_studio/from-source`, `POST /api/work_studio/overlay/{doc_id}`

### Monitor + Tasks
- `GET /api/strategic-goals`, `POST /api/strategic-goals`
- `GET /api/strategic-goal-evolution/{goal_id}` — Progress Timeline
- `GET /api/strategic-goal-assessment/{goal_id}` — colour-coded status read
- `GET /api/tasks-initiatives`, `POST /api/tasks-initiatives`

### Admin
- `GET /api/admin/users`, `GET /api/admin/tenants`
- `POST /api/admin/cohort/invite`, `GET /api/admin/cohort/list`
- `GET /api/admin/extractions`, `GET /api/admin/auth-events`
- `GET /api/admin/health`, `GET /api/admin/llm-spend`
- `GET /api/admin/sandbox-kpi`, `GET /api/admin/signal-kpi`

### Cycle + NED
- `GET /api/cycle/current`, `POST /api/cycle/draft`, `POST /api/cycle/ready`
- `GET /api/ned/inbox`, `GET /api/ned/committee`, `GET /api/ned/meeting/{id}`

### Telemetry + Health
- `GET /api/healthz`, `GET /api/healthz/clamav`, `GET /api/healthz/shield`
- `GET /api/synisense/observability/*` (admin-only)

(Full machine-readable list available at runtime via FastAPI's OpenAPI: `GET /api/openapi.json`. ~110 routers; ~400 routes.)

---

## 7. UI/UX Discipline Rules (enforced by tests)

1. **Multi-viewport responsiveness mandatory.** Every Solva v2 slide is wire-tested at **1280, 1024, and 820** widths via Playwright `getBoundingClientRect()` + `getComputedStyle()`. Regex / JSX-string scraping is forbidden — DOM-strict only.
2. **No flex-wrap on slide-body classes.** Locked source-strict test (`test_no_flex_wrap_on_slide_body_classes`) blocks any slide that introduces `flex-wrap` inside the slide body — wrapping breaks the deck-frame contract.
3. **Hairline-divider + 0.0px-gap policy.** Tab boundaries must collapse to exactly `0px` gap; no thicker rule sneaking in via parent-stack padding.
4. **Tailwind opacity-step source-strict allowlist (Wave 4.2.followup.2).** Brand-purple opacity values must be inside `{5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100}`. No `bg-[var(--token)]/N` arbitrary-value escape hatch — the modifier silently fails on hex CSS variables in some Tailwind builds, so we use the `bg-ned-purple/N` short-name only.
5. **Solva 5-layer naming is locked.** Codepath sweeps lock zero `SOLVE` / `Solve` strings; every Solva v2 file has been audited (Slice 2b identity audit).
6. **Test ID contract for Solva v2.** Every interactive element AND every UX-impacting element MUST carry a `data-testid` (kebab-case, function-not-style names). Solva v2 slides additionally carry: `data-solva-v2-slide="true"`, `data-solva-v2-slide-kind="{kind}"`, `data-solva-v2-slide-number="{n}"`, `data-solva-v2-slide-state="loading|ready|placeholder"`, `data-solva-v2-slide-footer="true"`.
7. **Inline raw-trace evidence in close-outs.** Every Solva v2 slice closes with verbatim DOM dumps captured from the exact founder-facing flow the tester will use — no synthetic event injection, no mock-test claims standing in for real render evidence. (Discipline rule locked after 3 recurrences of the "claimed-evidence-doesn't-reproduce" failure mode.)
8. **500-LOC auto-slice halt rule.** A single slice that exceeds ~500 LOC of new code is auto-split into `5a` + `5b` (backend + frontend) so reviewers can hold each surface in head at once.

---

## 8. Known Gaps / Limitations

| Gap | Severity | Status |
|---|---|---|
| AppShell topbar overflow on sub-1024px viewports — secondary controls hidden at `xl:` breakpoint | P0 | ✅ FIXED in the most recent dispatch (2026-05-29) |
| **CompanyHome.jsx 39px content overflow at 820px** — the topbar is fixed but a fixed-width child on the company home still extrudes 39px past the viewport | P3 | 🟢 **PARKED** — frontend-only investigation outstanding |
| **Microsoft OAuth pending credentials** — `/api/auth/oauth/microsoft/start` returns `503 microsoft_oauth_not_configured` | P2 | ⚠️ **MOCKED** — unblock by setting `MICROSOFT_OAUTH_CLIENT_ID` + `MICROSOFT_OAUTH_CLIENT_SECRET` |
| **Stripe billing** — `BILLING_ENABLED=false` so trials are manually granted; no billing UI surfaced | P1 (post-cohort) | ⬜ Planned |
| **Sentry DSN unset** — error tracking off in dev/prod until a DSN arrives | P2 | ⬜ Planned |
| **Production bundle staleness** — production deploy currently lags `main`; user must press "Deploy" in chat UI to promote | Operational | 🟡 In user's hands |
| **23 quarantined Solva v2 tests** — pre-existing skips before the 2026-02 autonomous sprint; not regressions, but worth re-greening | P2 | ⬜ Planned (`adversarial_guardrails`, `submodules`, `session_limits`, `post_redirect_recovery` test files) |
| **SendGrid sandbox key** in dev — recipient allowlist applies; production must rotate to a tier with the verified `@akki.ai` sender domain | Operational | 🟡 In `DEPLOYMENT_NOTES.md` checklist |

---

## 9. Roadmap Snapshot

### Near-term (P1) — next 2 dispatches
- **Slice 6 — Cost asymmetry slide** (Solva v2): explicit "what does Plan A cost if it's wrong vs. Plan B" framing as a 16th locked slide
- **Slice 7 — Verification + polish** (Solva v2): `data-solva-v2-slide-ready-at` timestamp attributes; Session Complete replay side-panel re-opens from the topbar icon stub; final UX polish before flag-flip

### Mid-term (P2)
- **Stripe billing** wired in — `BILLING_ENABLED=true`, webhook verification, trial-to-paid conversion flow
- **Microsoft Graph OAuth** unblocked (creds + redirect URI)
- **Sentry** error tracking on
- **PPTX export** for Solva v2 (currently DOCX/PDF on the v1 codepath only)
- **Dry-run admin endpoint** for Solva prompt tuning (`POST /api/admin/solva/dry-run` → exercises the prompt without mutating audit-log)
- **`LiveQueue` engine-side broadcast** — true live-mode rendering on in-flight sessions instead of post-hoc replay
- **`recommended_action` LLM extension** — pathway items grow a typed-action handle the founder can convert into a `tasks_initiatives` row in one click
- **Per-file category override** in Documents — founder reclassifies an extraction post-hoc
- **"Download deck" CTA** on the Solva v2 surface — exports the 15-slide artefact as PPTX

### Long-term (P3)
- **Solva diff feature** — view how a diagnosis evolved across re-runs (deltas in scenario weights, confidence percentages, named biases)
- **Pre-mortem signal watchlist (proposed Slice 8)** — surface a small inbox-style alert on the founder's home dashboard whenever an in-the-wild signal matches a previously-emitted `triggering_signal` pattern from a past pre-mortem
- **Cross-tenant impersonation** for superadmin support flows
- **Mobile-grade UX** — current target is desktop ≥820px; sub-820px is not yet a contract

---

## 10. Quality & Testing Posture

- **Solva v2 test suite:** **381 passed / 23 skipped (pre-existing) / 0 failed** as of 2026-05-29, post-Slice-5 close.
- **Playwright headless DOM validation in Pytest.** Every Solva v2 slide ships with a multi-viewport probe; every close-out includes raw-trace evidence pulled from the exact preview URL (`https://akki-executive.preview.emergentagent.com/app/solva/session/{sid}`) the tester will hit.
- **Raw-trace discipline rule** (locked after 3 recurrences): "Inline rendered-DOM evidence in close-outs must come from the exact same flow/URL the tester will test. Do NOT use synthetic event injection or mock tests to claim frontend UI behavior works." Synthetic claims have been a recurring failure mode and are now blocked at the close-out review.
- **v1 byte-identical guard.** `git diff backend/services/solva backend/services/solva_v1 frontend/src/components/solva/artefact` returns empty diff at every Solva v2 close-out. Any v2 work that drifts into v1 territory fails the regression suite.
- **Identity-audit guard.** 8 new audit-guard tests lock zero `SOLVE` / `Solve` strings across v2 codepaths.
- **Anti-drift contracts.** `LOCKED_SLIDE_KINDS` is mirrored across 4 surfaces (Pydantic enum, `stream_schema`, `stream_synthesizer.SLIDE_DECK_ORDER`, frontend hook). Drift between any two surfaces fails an existing test.
- **Deploy-check job** (`.github/workflows/deploy.yml`): `pytest -m runtime_playwright` runs against Phase Z-slice-6 + AA-slice-7 orthogonality regressions before the deploy step; failure blocks the deploy.

---

_End of document. Maintained by the orchestrator. Source of truth: repo HEAD as of 2026-05-29 post-Slice-5._
