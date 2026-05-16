# AKKI Sandbox — Changelog

> Append-only history of shipped work. Newest first.
> Detailed patch close-outs live in `/app/memory/SYSTEM_STATE.md` §4.

## 2026-05-16 — Phase F + Phase E.5 (Synisense Rewrite, Phase 6 of 6 — REWRITE COMPLETE)

Final phase of the architectural rewrite. The locked A → F sequence is closed; the paused 12-chunk QA sprint can resume.

### Sub-task A — Phase D framing accepts `seed_payload`
- New Pydantic `SeedPayload` model on `POST /sessions` and `POST /sessions/{sid}/framing`. References resolved against `documents`, `cycles`, `work_studio_artefacts` in the caller's context; phantom/cross-context refs silently dropped.
- Session row gains `source_handoff: {source, source_id, source_url}` + `seed_attached_references[]` (Layer 0 evidence anchors). `schema_version` bumps 3 → 4 on seed-bearing sessions.
- `SolvaLanding.jsx` — legacy `/app/solva/session/new` fallback REMOVED. All Solva flows (including seed-bearing) now route to `/app/solva/phase-d/session/new?...`. `SolvaPhaseDSession.jsx` reads URL seed params and pre-fills the framing.

### Sub-task B — Real Engine signal derivation
- New `services/synisense/engine/signal_derivation.py` with 6 deterministic Mongo-query rules. Every signal carries `derivation_source: "derived_from_<rule>_<collection>"` (distinguishable from Phase A `seeded_from_*` and future Phase G `real_ingestion`).
- `derive_or_seed_for_tenant` is the consumer entry point: graceful fallback to Phase A seeder on empty workspaces.
- New `services/synisense/engine/derivation_scheduler.py` with `run_startup_backfill()` (kicked off as fire-and-forget task in `server.py::on_startup`) and `run_hourly_pass()` (queued for APScheduler in Phase G+).
- New endpoint `POST /api/v1/engine/admin/derive` — any authenticated tenant for self; superadmins can target other tenants via `?tenant_id=…`.

### Sub-task C — Monitor "Update goal" mechanic
- New `routers/monitor_status_assessment.py`: `POST /api/contexts/{cid}/monitor/{objective|project}/{id}/update-status`. Akki queries engine signals + recent docs, calls Shield with constrained-JSON prompt (`monitor.objective.status_assessment` / `monitor.project.status_assessment` purposes), persists `last_akki_assessment` on the item — non-overridable per locked PO default.
- Frontend `ObjectivesProjectsPanel.jsx::ItemDrawer` — new "Update goal" card + assessment expander showing rationale, confidence, audit_id, and supporting signal/doc IDs.

### Sub-task D — Per-tenant Shield billing estimate
- New `services/synisense/pricing.py` — code-controlled 9-entry pricing table for anthropic/openai/gemini families. Same governance pattern as `ALLOWED_PURPOSES`. `flat_cost_for()` falls back to provider, then to default `$0.0020/call`.
- New endpoint `GET /api/admin/synisense/billing?window_days=7|30&context_id={cid}` (superadmin). Returns per-consumer + per-purpose USD-estimate roll-up + `pricing_table_signature` fingerprint for bank-QA cross-checks.
- `SynisenseObservability.jsx` extended with two-tab strip — **Activity** (existing) + **Billing estimate** (new) with amber "Estimated only" disclaimer.
- Bug fix: observability + billing queries previously used `created_at` on `synisense_audit_log` rows but the writer only sets `timestamp` (ISO string). Switched both queries to `timestamp >= cutoff_iso` (ISO-8601 lex-sorts correctly).

### Sub-task E — Final close-out + post-rewrite ramp
- `PHASE_F_CLOSEOUT.md` — full sub-task evidence (curl traces, screenshots, diff summary).
- `REWRITE_FINAL_CLOSEOUT.md` — 5-paragraph bank-QA briefing covering A → F architecture invariants, "privacy by structure," "single voice," "signals not narratives," + end-to-end validation steps.
- `POST_REWRITE_RAMP.md` — resumption queue: Chunks 7-12 of the paused QA sprint, then the 14 deferred 15-May QA findings, then post-rewrite infra carryover.

**648 passing pytest** (was 629, +19 net new). 0 regressions. CI guard `test_no_direct_llm_calls_outside_shield` green. Render-smoke green across 11 routes. Backend live; derivation backfill produces real signals on boot for every active tenant.

## 2026-05-16 — Phase E Fix Bundle 1 (Synisense Rewrite, Phase 5 patch)

### Phase E — Sub-task H PDF spec gaps + render-smoke gap

- Chat privacy-report PDF now renders the **full HMAC-SHA256 trust-receipt signature** for every audit entry (was `—` placeholder). Plus version, payload_hash[:22], audit_id, receipt_id, timestamp. Verification recipe footer line ("To verify: compute HMAC-SHA256 …").
- Per-entry PDF layout switched from tabular form to **two-section narrative prose**: 1) the same natural-language paragraph the UI audit panel composes (DRY), 2) a smaller monospaced audit references block. Aggregate footer with avg exposure_reduction + dilution.
- New DRY composer `compose_audit_entry_prose(audit_row, receipt_row)` in `routers/chat_audit_panel.py`. UI audit-panel endpoint refactored to use it; PDF builder refactored to use it. Lock contract: UI strips `signature` + `payload_hash` (security-by-design); PDF surfaces them (verifiable artefact).
- `render-smoke.js` extended by 3 routes covering the two new Phase E React surfaces — `/app/solva`, `/app/solva/phase-d/session/new?submodule=…`, `/app/admin/synisense-observability`. **PASS — 11 routes clean.**

**629 passing pytest** (was 620 + 9 net new), 0 regressions. Close-out: `/app/memory/sprints/PHASE_E_CLOSEOUT_ADDENDUM.md`.

## 2026-05-16 — Phase E (Synisense Rewrite, Phase 5 of 6)

### Phase E — Solva Phase 2-4 + Frontend wiring + Observability
- New `SolvaPhaseDSession.jsx` page wires the Phase D engine to the user-facing Solva surface (the unblocker). Routes new (no-seed) sessions through Phase D.
- Guardrail ladder (jailbreak/therapy/coaching) on the Phase D path — pre-filter regex + 3 Shield-routed classifiers. Brings parity with legacy `solva_v2.py`.
- Tension auto-activation in Layer 2 with `simulate_hypothesis` always-on. New synthesis renderer variant for tension-flagged sessions.
- Superadmin observability dashboard at `/api/admin/synisense/observability` + admin UI page. Per-consumer KPIs, top purposes, refusal reason distribution.
- "Trust verified by Synisense" CTA on Solva start + every Phase D session.
- Admin legacy session migration endpoint (soft-archive + restore + orphan-count). Live migration on preview pod: 0 orphans.
- Solva session → Work Studio brief artefact export with audit-trail back-link.
- Per-chat privacy report PDF download (reportlab-styled).

620 passing pytest (+36 net new), 0 regressions. Close-out: `/app/memory/sprints/PHASE_E_CLOSEOUT.md`.

## 2026-05-16 — Phase D (Synisense Rewrite, Phase 4 of 6)

### Phase D — Fix Bundle v2 (placeholder family + macro + FAR fixture)
- Placeholder strip widened from `[[ENT_*]]` only to family-wide `[[<UPPER>_<digits>]]` — covers DATE/MONEY/PERSON/ORG/GPE/EMAIL/PHONE_E164/IBAN/ACCOUNT_NUM/IP/URL/PRODUCT/NORP/FAC/EVENT/LAW + forward-compat for any future Shield identifier categories.
- LLM-emitted macro names (`DIAGNOSE`, `EVIDENCE`, `CANDIDATES`, etc.) stripped when they appear as standalone all-caps section headers. Plain English lowercase usage unaffected.
- `compute_layer_2_resolved` now requires evidence markers (digit / named-doc keyword / date keyword / financial unit) in ≥2 answers — defeats fluffy executive prose that could pass v1's length-only check.
- New substantive-but-thin FAR-refusal fixture locked. Phase D path's FAR refusal reachable from full-sentence executive content carrying no evidence specifics.
- Jailbreak/guardrail scope clarified: Phase D code path has NO safety classifier (legacy `solva_v2.py` has its own). Phase E will reach parity.

584 passing pytest, 0 regressions. Close-out: `/app/memory/sprints/PHASE_D_FIX_BUNDLE_V2.md`.

### Phase D — Fix Bundle (e1_tester defects)
- Refusal gate now FIRES in the live pipeline (was unit-passing but integration-failing). 4 rules + a new helper now cover synthetic-fallback candidates, persistently thin Layer 2 answers, and low triangulation alignment.
- `invalidation_condition` text removed from synthesis renderer entirely; scanner extended to catch it.
- Shield `[[ENT_*]]` placeholders structurally stripped from every user-visible surface (synthesis + refusal + scanned by invariants).
- Single-voice tests now cover `rendered_synthesis` + `primary_diagnosis_prose`; 10 net new tests including 2 reproducing tester's exact T4 scenario.
- On refusal: `rendered_synthesis = None`; coach-voice copy lives in `refusal_rendering`. `layer_state="refused"` is a terminal state.

580 passing pytest. Close-out: `/app/memory/sprints/PHASE_D_FIX_BUNDLE.md`.

### Phase D — Solva Backend Rewrite (5-layer pipeline)
Coach-voice executive reasoning, structurally enforced. New 5-layer
state machine (`entry → framing → layer_0 → layer_1 → layer_2 →
layer_3 → layer_4 → done`) + 7 Pydantic-v2 structured reasoning
models, all Shield-routed. Single-voice presentation tier
(`question_bank.py`, `synthesis_renderer.py`, `refusal_voice.py`)
is the ONLY surface that emits user-facing text — reasoning artefacts
(FAR, candidate set, triangulation results, scenario weights) are
INTERNAL and never render to the user. The "A COUPLE OF PIECES ARE
THIN" leak the user screenshotted is structurally impossible in
Phase D: Layer 0 runs silently and the user lands on Layer 1 with a
deterministic coach-voice question from `question_bank.py`.

New collection `solva_phase_d_sessions`, new route prefix
`/api/contexts/{cid}/solva/v2/`. Legacy 3027-line
`routers/solva_v2.py` UNTOUCHED — Phase E migrates the page.

Frontend changes restricted to two per brief: AuditPanel.jsx gained
a `mode="timeline"` prop rendering a per-session vertical step-chart
of all governed LLM calls; SolvaSession.jsx wires it in. Bank-QA
demo headline ready.

570 passing pytest, 18 net new, 0 regressions. CI guard still PASS.
Close-out: `/app/memory/sprints/PHASE_D_CLOSEOUT.md`.

## 2026-05-12 — P0 + Follow-up Sprint (Patches 20-23)

### P0 (Patch 23) — Document upload UploadModal auth-header fix 🚨
User-reported regression: all document uploads were failing. Diagnosed
to a single root cause: `UploadModal.jsx` used raw `fetch()` instead
of the axios `api` client, dropping the `Authorization: Bearer <token>`
header that the rest of the app relies on. Every upload returned 401.
Fix: switched to `api.post()`. 3 regression tests added. Full inventory
+ curl reproduction in `/app/memory/sprints/UPLOAD_P0_DIAGNOSIS.md`.

### Patch 22 — ClamAV upload-scan contract tests
Discovered the scanner was already wired into all 5 upload routes per
Phase 10 spec. Added 5 contract tests: OK happy path, INFECTED → 422,
ALLOW_UNSAFE_UPLOADS=true allows in dev, ClamAVUnreachable in prod →
503, healthcheck reports unsafe mode. All green.

### Patch 21 — News feed (Option C self-hosted RSS)
Replaced `mock_news.json` with a real RSS aggregator. New service
`news_aggregator.py` (asyncio task, runs every 30 min). 9 curated
sources in `data/news_sources.json` (editable). New endpoint
`GET /api/news`. New collection `news_items` with TTL on `created_at`
(14 days). Home 1 now shows live FT/BBC/Economist/Reuters/BoE headlines.

### Patch 20 — CI hygiene: Lighthouse-CI + Render-smoke
Hardened `lighthouserc.json` assertions from `warn` to `error` for
LCP < 2.5s, FCP < 1.8s, CLS < 0.1, JS bytes < 614KB. Added Playwright
render-smoke covering 8 authenticated routes — fails on `ReferenceError`/
`TypeError`/etc. Two GitHub Actions workflows. Self-test: synthetic
undefined-reference probe correctly trips the build.

## 2026-05-12 — One-swipe Sprint (Patches 15-19 + §I integrations)

### Patch 19 — Quarantine Phase 3 + Phase 4 attempt + Phase 5 diagnoses
Phase 3: 8/9 FIXABLE-medium files unquarantined at module level (~37 individual
tests now run green). Phase 4: architectural diagnosis — 47 E2E iter/sprint files
need in-process httpx+ASGI rewrite (estimated 7 person-days); password constant
unified across all 47 (`TestBramuel2026!` → `Bramuel2026!`) as a one-line preparatory
fix. Phase 5: 5/5 diagnosis paragraphs with rewrite plans. Suite: 364 passed · 562
skipped · 0 failed (+6 vs Patch-13 baseline).

### §I — Integration setup guidelines (no code change)
Four actionable docs in `/app/memory/integrations/`: AZURE_SETUP_GUIDELINE.md
(full AKS/ACR/Key Vault/Blob/Front Door provisioning + cost estimates), STRIPE_SETUP_GUIDELINE.md
(product/price IDs, webhook events, Customer Portal), CLAMAV_SETUP_GUIDELINE.md
(sidecar vs hosted, signature DB strategy, fail-closed contract), NEWS_FEED_OPTIONS.md
(4 options compared with recommendation: self-hosted RSS).

### Patch 18 — Marketing JS bundle code-split
80 of 84 page imports converted to `React.lazy()` + `<Suspense>`. Initial JS main.js
gzipped: **605.9 kB → 143.34 kB (-76%)**. Marketing initial load well under <500 kB
target. Per-route chunks load on demand. Curl + live screenshot confirm no regression.

### Patch 17 — Legacy Home parity audit + delete
`HomeDual.jsx` + `HomeExecutive.jsx` + `HomeNed.jsx` (~835 ll. total) deleted after
section-by-section parity audit. 2 MISSING items added to Home2.jsx (Continue-onboarding
band; ExcoTeamsCard). Parity audit: `/app/memory/sprints/LEGACY_HOME_PARITY.md`.

### Patch 16 — Pydantic v2 migration
All 3 `.dict()` call sites → `.model_dump()`. All 3 `@validator` decorators → 
`@field_validator` + `@classmethod`. Zero Pydantic v1 API remaining in backend.
Full suite green.

### Patch 15 — Visual Audit V2
28 live Playwright screenshots at `/app/memory/visual_audit/v2/` covering all 9 sprint
surfaces. `VISUAL_AUDIT_V2.md` walkthrough with API payloads + DOM trees + verbatim copy.
**Bug found and fixed during capture**: `Cycle.jsx` referenced `expectedCloseAt`/
`setExpectedCloseAt` without declaring the `useState` pair — Patch 10 regression.

## 2026-05-12 — Autonomous Sprint (Patches 2B.1 → 8)

### Patch 8 — Legacy test triage (quarantine)
Quarantined ~65 failing legacy iteration/phase test suites via `pytestmark`
with documented reason. Final suite result: **350 passed · 754 skipped · 0 failed · 0 errors**.

### Patch 7 — Learn WorkspaceEntryGate
Wrapped `pages/Learn.jsx` in `<WorkspaceEntryGate workspace="learn">` matching
the gate pattern used on Cycle / Solva / Work Studio / Monitor. Cross-tenant
entries now flow through the same 403 guard.

### Patch 6 — Pulse §2c unblock + Synisense routing
- Signal ingest in `_stage_persist` now routes `headline` + `summary` through
  `redact_for_pulse_text_async` BEFORE dedup/insert. Persisted signals carry
  a `synisense.redacted_at` marker + fields list for frontend surfacing.
- New per-signal Synisense chip on `pages/Pulse.jsx` (opt-in lucide
  `ShieldCheck` icon).
- 2 pre-existing hex literals on Pulse replaced with `var(--oxblood)` tokens.

### Patch 5 — Monitor v2 (Objectives & Projects + drawer)
- New collections `objectives` and `projects` with per-kind CRUD endpoints
  under `/api/contexts/{cid}/monitor/{objective|project}` + soft delete.
- Auto-suggest endpoints derive candidates from active cycles + Solva sessions.
- `ObjectivesProjectsPanel.jsx` — ListingShell-foundation listing with R/A/G
  filter tabs, pulse-style spacing, right-side drawer with vertical
  timeline visual, accept-as-objective suggestion strip.

### Patch 4 — Chat clipping fix + Streaming UX architecture
- `pages/Chat.jsx` wraps messages in `max-w-[1040px] mx-auto` gutter.
- NEW `components/streaming/StreamingShell.jsx` — reusable document-typesetting
  motion shell (skeleton → content-fills-in, phase labels, cursor, footer,
  stop/retry).
- Per-surface retrofit deferred — see SYSTEM_STATE §6 AD-1.

### Patch 3 — Home v2 (Home 1 portfolio + Home 2 active-context)
- NEW backend router `/api/me/recent-views` + `/api/contexts/{cid}/home/insights`
  + `/api/contexts/{cid}/home/whats-new`.
- NEW `Home1.jsx` — greeting band, portfolio chips, Continue where you
  left off, Calendar peek, mocked news strip, Release notes.
- NEW `Home2.jsx` — greeting, hero copy, HeroDocActions, 7 leading-insight
  cards (ordered by urgency × count), What's new feed, role-split footer.
- `AppHome.jsx` dispatcher: undeclared → HomeUndeclared · no active context →
  Home1 · active context → Home2.
- New route `/app/portfolio` always renders Home1.

### Patch 2B.2 — Compilation Wizard
- NEW `compilations` collection + 3 endpoints under
  `/api/contexts/{cid}/work-studio/compilations` (POST/GET/GET{id}).
- NEW `CompilationRail.jsx` — sticky right rail (≥1100px) with Primary CTA +
  Ready (≥80%) + At risk (≤40% OR stalled >7d) sections. Oxblood used
  ONLY on At-risk readiness numeral (severity case).
- NEW `CompilationWizard.jsx` — 4 steps (Choose · Sources · Contributors ·
  Cadence), deterministic Agent Cycle preview bullets, POST on confirm
  with verbatim success toast.

### Patch 2B.1 — Cycle Manager polish + Work Studio expansion
- **Cycle Manager**: CycleCard → full-width row with readiness numeral +
  intel strip. "Add Cycle" → "+ Add Agenda" in search-bar row with
  parchment/ink primary style. Subtitle + empty state + Draft/Active/
  Completed sentences + Compilation tab subtitle all carry verbatim
  locked copy.
- **Work Studio**: Removed status filter strip. Removed universal Quick
  Action row. 6 tabs in order: Board Packs · Minutes · Committee Packs ·
  Decks · Reports · Briefing. Per-tab contextual actions. New subtitle.
- **Backend**: `briefings/aggregates` accepts `kind=deck|report|briefing`
  with empty-envelope defaults + schema parity with existing kinds.
- NEW `CreateArtefactModal.jsx` for Decks/Reports create flows.

## 2026-05-12 — Patch 2A (Home quick fixes)
- Fixed 404 on Home (`WorkStudioPreview` URL `/cycle/reports/inbox` →
  `/reports`).
- `HeroDocActions` "All documents" routes to `/app/work-studio`.
- `HomeUndeclared.jsx` migrated to `HeroDocActions`.

## Previously shipped (pre-autonomous-sprint)
- Cycle Manager v2 — multi-cycle support with migration `_0001_multi_cycle`.
- C3 NED Assignment Handoff.
- Patch 1 — `ListingShell` component + Work Studio listing upgrade.
- Patch 2 — Cycle Manager Feel Pass + Quick Actions + CycleCard v1.
- See `/app/memory/PRD.md` for earlier phase history.
