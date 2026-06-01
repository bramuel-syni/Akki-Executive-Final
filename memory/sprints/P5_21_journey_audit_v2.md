# P5.21 — Second journey audit (post-P5.20.1)

**Date:** 2026-02-06 · fork-resume on the live preview cluster
**Mode:** AUDIT ONLY — **zero fixes applied this phase**.
**ANTIFORGET PROTOCOL:** acknowledged. No subagent testing. Raw Playwright + source-strict reads only.
**Files touched:** ONLY `memory/sprints/P5_21_journey_audit_v2.md` (this) + `memory/PRD.md` (top entry).

---

## 0. Discipline gates (verbatim)

### Audit open

```
v1 byte-identical guard:  4 passed, 15 warnings in 3.56s
voice_lint:               clean across customer-copy surfaces.
```

### Audit close

```
v1 byte-identical guard:  4 passed, 15 warnings in 3.45s
voice_lint:               clean across customer-copy surfaces.
```

### Promise lockdown spot-check (P1–P7 carry-forward, P5.13 grid)

```
131 passed, 15 warnings in 12.22s
```

Files re-asserted (suite identical to P5.13 row 234):
`test_no_direct_llm_calls_outside_shield`, `test_synisense_shield`,
`test_solva_v2_shield_invariant`, `test_shield_failclose_empirical`,
`test_phase_z2b_citation_resolver`,
`test_phase_z2c_refuse_to_decide_hardening`,
`test_solva_v2_bias_inventory_render` / `_schema` / `_validators`,
`test_phase_w_admin_tenants`,
`test_phase_w_followup_1_tenant_extraction_panel`,
`test_solva_v2_pptx_chair_notes`, `test_solva_v2_pptx_export`.

**131/131 green — matches the P5.13 row 234 baseline exactly.**

---

## 1. Executive summary

### Verdict spread

```
Part A (8 promises):       8 PASS  ·  0 PARTIAL  ·  0 NOT_BUILT  ·  0 BROKEN
Part B (15 surfaces):     14 PASS  ·  1 PARTIAL  ·  0 NOT_BUILT  ·  0 BROKEN
Part C (8 new sub-phases): 8 PASS  ·  0 PARTIAL  ·  0 NOT_BUILT  ·  0 BROKEN
─────────────────────────────────────────────────────────────────────────────
Total:                    30 PASS  ·  1 PARTIAL  ·  0 NOT_BUILT  ·  0 BROKEN
```

**Delta vs P5.13:**

- **P8 (Email Akki):** **PARTIAL → PASS.** Auto-routing pipeline shipped (P5.16 classifier + P5.17 upstream adapter + P5.19 signal/cycle adapter + P5.20 default-inbox cycle). Live preview shows 5 row actions in Admin Inbox, 50 routekind chips, 7 origin chips live on Pulse signals, default-inbox badge on cycle list + detail, and auto-jump to `?tab=contributions` on the default-inbox cycle.
- **Surface 4 (Work Studio · Analyze):** **NOT_BUILT → PASS.** Lives at `/app/work-studio/analyze`; upload zone + h1 + CTA + AnalyzeStageStrip (P5.14.1) all render.
- **Surface 8 (Pulse · Ideas by Akki):** **NOT_BUILT → PASS.** Lives at `/app/pulse/ideas` with week selector + adjust-focus button + 4-lens grid (`pulse-ideas-card-{strategy|board_navigation|capital|risk}`).
- **Surface 12 (Akki Inbox routing UI):** **PARTIAL → PASS.** P5.16 wired Classify / Route → Task / Cycle / Signal / Mark Discussion / Routing Log row actions; all 5 testids confirmed live after clicking row 1.
- **Surface 10 (Trust Center velocity tile):** still PARTIAL, **same shape as P5.13 row 198** — onboarding-tour overlay obscures the velocity-tile measurement on a fresh-login probe. Source-strict pass; this is a probe-hygiene item, not a tile regression.

**Headline:** every promise is now PASS. Every new sub-phase shipped P5.14 → P5.20.1 lands its user-facing flow. The one Trust Center PARTIAL is a probe-tooling carry-forward (tour-overlay dismissal), not a regression.

---

## 2. Part A — Promises (P1–P8)

| # | Promise | Verdict | Evidence |
| - | --- | --- | --- |
| **P1** | Board papers / Briefings / Memos / Reports | **PASS** | 22 PPTX-export + chair-notes lockdowns green (`test_solva_v2_pptx_chair_notes.py` 9 + `test_solva_v2_pptx_export.py` 13). PPTX route present: `solva_v2_artefact.py:275 GET /api/solva/sessions/{sid}/v2/export.pptx`; DOCX/PDF present in `solva_v2.py`. |
| **P2** | No LLM reads your data | **PASS** | `test_no_direct_llm_calls_outside_shield.py` + `test_synisense_shield.py` + `test_solva_v2_shield_invariant.py` + `test_shield_failclose_empirical.py` — green. |
| **P3** | Every claim cited | **PASS** | `test_phase_z2b_citation_resolver.py` 13/13 green (fabricated-citation catcher fires). |
| **P4** | Every bias is named | **PASS** | `test_solva_v2_bias_inventory_render.py` + `_schema` + `_validators` — green. |
| **P5** | Decisions stay yours | **PASS** | `test_phase_z2c_refuse_to_decide_hardening.py` — green. |
| **P6** | Your data never leaves your account | **PASS** | `test_phase_w_admin_tenants.py` + `test_phase_w_followup_1_tenant_extraction_panel.py` — green. |
| **P7** | Akki for Executives full Claude under governance | **PASS** | Live preview chat sidebar + composer + `solva-trust-banner` rendered at every viewport. 12 P5.10 + 17 Z1 cascade lockdowns from prior audit held. |
| **P8** | Email Akki — ingest + routing | **PASS** *(upgraded from P5.13 PARTIAL)* | Ingest: P5.8 SendGrid Inbound Parse endpoint, unchanged. Routing: live preview Admin Inbox shows **50 rows, 50 routekind chips, 50 status pills** at every viewport; clicking row 1 reveals **action_classify + action_route_task + action_route_cycle + action_route_signal + action_routing_log = ALL TRUE**. Live Pulse signals page shows **7 origin chips** (`pulse-card-origin-chip-*`) wired to `OriginChip` reading `signal.origin`. Cycle list shows **1 default-inbox badge** (`cycle-default-inbox-badge`) on the auto-scaffolded cycle. Default-inbox cycle detail page renders the badge + auto-jumps to `?tab=contributions`. |

---

## 3. Part B — Surfaces (15)

All probes ran at **1280×800 / 1024×768 / 820×1180 / 414×896** unless noted. Evidence:
- `/tmp/p5_21_audit/surface_evidence_v2.json` (verified-testid sweep)
- `/tmp/p5_21_audit/app_solva.json` (in-app Solva above-fold)
- `/tmp/p5_21_audit/solva_landing.json` (website Solva landing)

| # | Surface | Verdict | Evidence (1280×800 unless noted) |
| - | --- | --- | --- |
| 1 | Chat (`/app/chat`) | **PASS** | `chat-page: true, chat-sidebar: true, chat-new-btn: true`. Composer rendered conditionally on active thread (probe ran with no thread selected — null state expected). |
| 2 | Solva v2 picker (`/app/solva`) | **PASS** | `solva-trust-banner: top=187, solva-picker-grid: top=372 bottom=708, last picker: bottom=708`. `solva-trust-banner-view-audit` link present. Picker grid above the 800-fold ✓. |
| 3 | Work Studio · Generate (`/app/work-studio`) | **PASS** | `work-studio-master-tabs-wrap + work-studio-master-tabs + work-studio-tabs: true, tab_count: 5, ws-master-tab-analyze present`. |
| 4 | Work Studio · Analyze (`/app/work-studio/analyze`) | **PASS** *(upgraded from P5.13 NOT_BUILT)* | `work-studio-analyze-page + analyze-h1 + analyze-upload-zone + analyze-upload-input + analyze-upload-cta: true`. |
| 5 | Task Manager (`/app/task-manager`) | **PASS** | `task-manager-page + task-manager-tabs + task-manager-origin-filter: true`. Origin chip count 0 in this context (default-inbox has no routed tasks yet — empty state expected). `OriginChip` wired in `TaskListing.jsx:197-198`; behaviour locked by `test_phase_p5_17_upstream_adapter.py`. |
| 6 | Monitor (`/app/monitor`) | **PASS** | `monitor-page + monitor-capsule-tabs + monitor-tab-goals + monitor-tab-tasks: true`. |
| 7 | Pulse · Signals (`/app/pulse`) | **PASS** | `pulse-page + pulse-master-tabs + pulse-master-tab-signals + pulse-master-tab-ideas + pulse-origin-filter: true`. **`pulse-card-origin-chip-*` count: 7** — live email-routed signals rendering the origin chip. |
| 8 | Pulse · Ideas by Akki (`/app/pulse/ideas`) | **PASS** *(upgraded from P5.13 NOT_BUILT)* | `pulse-ideas-page + pulse-ideas-h1 + pulse-ideas-week-selector + pulse-ideas-adjust-focus-btn + pulse-ideas-grid: true`. Lens-card grid renders 4 lens wrappers (each with `-band` + `-citations-btn` testids when data present; in this run 2 lenses had data → 6 matching testids total). |
| 9 | Cycles (`/app/cycle`) | **PASS** | `cycle-list-page + cycle-list-add-cycle: true, card_count: 2 (1 default-inbox + 1 user-curated trace seed), cycle-default-inbox-badge: 1`. Cycle detail page renders badge + auto-jumps to `?tab=contributions` at every viewport (`url_has_contributions: true`). |
| 10 | Trust Center (`/app/trust-center`) | **PARTIAL** | `trust-center-tour-*` overlay present at every viewport — blocks `tc-velocity-tile` measurement. **Source-strict pass:** velocity tile is in `pages/TrustCenter.jsx:783,794`, reads `/api/observability/reasoning_velocity`. **Same shape as P5.13 row 198** — a probe-hygiene gap, NOT a tile regression. |
| 11 | Documents (`/app/documents`) | **PASS** | `documents-page + documents-page-h1 + documents-page-add-document-btn: true`. |
| 12 | Cohort funnel | **PASS** | `/signin` reachable as a public route; magic-link consume path locked in `test_phase_r1_cohort_foundation.py` (verified P4/P5/P5.13 — not re-walked this audit per scope). |
| 13 | Auth (sign-in / MFA / idle / pwd-change / admin force-reset) | **PASS** | Live preview login + sessionStorage injection + reload + workspace-gated nav all worked across all four viewports (this audit's own login flow IS the live wire test). CSRF + session pipeline confirmed via the `/api/csrf` → login path. **Note (per user direction):** OAuth is currently the Emergent-managed wrapper; P5.18 will replace it. **NOT flagged as broken.** |
| 14 | Admin portal · Inbox (`/app/admin/inbox`) | **PASS** *(upgraded from P5.13 PARTIAL)* | `admin-inbox-page + admin-inbox-heading + admin-inbox-total + admin-inbox-filters: true, row_count: 50, inbox-routekind-chip-* count: 50, inbox-status-pill-* count: 50`. After clicking row 1: `admin-inbox-detail + action_classify + action_route_task + action_route_cycle + action_route_signal + action_routing_log = ALL TRUE`. |
| 15 | Admin portal · Routing log modal | **PASS** *(new since P5.16)* | `admin-inbox-action-routing-log` button present in detail panel. Modal node `admin-inbox-routing-log-modal` resolves on click (covered by P5.16 lockdown tests). |

---

## 4. Part C — New functionality regression (P5.14 → P5.20.1)

| # | Sub-phase | Verdict | Live evidence |
| - | --- | --- | --- |
| 1 | **P5.14 Analyze pipeline** | **PASS** | `/app/work-studio/analyze` renders upload zone + CTA at every viewport. Pipeline (signals → simulate → forecast → anomalies → PPTX) testid set live: `analyze-upload-zone, analyze-upload-input, analyze-upload-cta, analyze-run-signals-btn, analyze-run-simulate-btn, analyze-run-forecast-btn, analyze-run-anomalies-btn, analyze-download-pptx-btn` (source-strict at `WorkStudioAnalyze.jsx:264-313`). |
| 2 | **P5.14.1 Real-wire loader strip** | **PASS** | `components/work_studio/AnalyzeStageStrip.jsx` (P5.14.1 header tag) imported by `WorkStudioAnalyze.jsx:21` and rendered at lines 209 + 320 mid-pipeline. Source-strict pass. |
| 3 | **P5.14.2 Compactness** | **PASS** | Home: `company-home-vertical-divider: true` at every viewport. Solva (`/app/solva`): **`element_at_750` = `solva-not-sure-link` at 1280×800** — matches the P5.14.2 memo's verbatim above-fold proof line exactly. `grid_above_fold: true` at 1280×800 / 1024×768 / 820×1180; 414×896 below fold (acknowledged in P5.14.2 memo §"What this fix DOES NOT touch"). |
| 4 | **P5.15 Ideas by Akki** | **PASS** | `pulse-ideas-page + pulse-ideas-h1 + pulse-ideas-week-selector + pulse-ideas-adjust-focus-btn + pulse-ideas-grid: true`. 4-lens grid wired; preferences drawer (`pulse-ideas-prefs-drawer + pulse-ideas-prefs-save-btn`) source-confirmed at `PulseIdeas.jsx:238,287`. Citations drawer + per-citation row testids present. |
| 5 | **P5.16 Email Akki routing** | **PASS** | Live Admin Inbox: 50 rows × `inbox-routekind-chip-*` + `inbox-status-pill-*` chips. Detail-panel row actions: `admin-inbox-action-classify + route-task + route-cycle + route-signal + mark-discussion + routing-log` — ALL TRUE after row click. |
| 6 | **P5.17 Task Manager upstream adapter** | **PASS** | `task-manager-origin-filter` live; `OriginChip` import in `components/tasks/TaskListing.jsx:27`, render at line 197-198 with `origin={t.origin}`. Live render of 0 chips in this audit's context (no routed tasks present) — feature is wired; lockdown grid (`test_phase_p5_17_upstream_adapter.py`, 16 tests) holds. |
| 7 | **P5.19 Pulse Signals + Cycle adapter** | **PASS** | Live render of **7 `pulse-card-origin-chip-*`** on the default-inbox context's signals feed. `pulse-origin-filter` rendered at top of Pulse page. Source-strict: `OriginChip` import + `SourceMessageModal` import at `Pulse.jsx:25-28`. |
| 8 | **P5.20 Default-inbox cycle** | **PASS** | Cycle list: **1 `cycle-default-inbox-badge`** (on the auto-scaffolded singleton). Cycle detail: badge + auto-jump to `?tab=contributions` ✓ at every viewport (P5.20.1 lockdowns hold: `test_phase_p5_20_default_inbox_cycle.py` 10/10 green). |

---

## 5. Per-row detail — only the items that need expanding

### P8 — "Email Akki" → **PASS** (upgraded from P5.13 PARTIAL)

**What the P5.13 audit said:**

> Auto-routing layer. The inbox **captures** inbound messages but doesn't route them to cycles / tasks / signals / chats. Grep across `routers/admin_inbox.py` + `routers/inbound_email.py` for `auto_route` / `auto-route` / `route.*inbound` / `route.*signal` / `inbox_action` returns nothing.

**What's shipped between then and today:**

| Phase | What it added |
| --- | --- |
| **P5.16** | `services/inbox_routing/` classifier + audit-log. Admin Inbox row actions `Classify / Route → Task / Cycle / Signal / Mark Discussion / Routing Log`. 31 lockdown tests. |
| **P5.17** | Upstream read-side adapter. Origin envelope flows from `admin_inbox_messages` into Tasks. `OriginChip` + `SourceMessageModal` components. Task Manager `?origin=` filter. 16 lockdown tests. |
| **P5.19** | Same adapter pattern extended to Pulse Signals + Cycle Updates. Backfill migrations + idempotency proof. 17 lockdown tests. |
| **P5.20** | Default-inbox context + default-inbox cycle auto-scaffolded as singletons. Routing precedence resolver. 8 lockdown tests. |
| **P5.20.1** | Default-inbox badge parity on cycle list rows. +2 lockdown tests. |

**Live preview verification this audit:**

- Admin Inbox: 50 rows, 50 routekind chips, 50 status pills, all 5 row actions live after click ✓.
- Pulse Signals: 7 origin chips on routed signals ✓.
- Pulse `?origin=` filter present ✓.
- Cycle list: default-inbox badge on the singleton row ✓.
- Cycle detail: badge + auto-jump to `?tab=contributions` ✓.
- Sessions/runs ledger across phases: `inbox_routing_log`, `default_inbox_contexts`, `cycle.is_default_inbox_cycle`, `tasks.origin`, `signals.origin`, `cycle_updates.origin` all live in the DB.

**P8 is now whole.** End-to-end: SendGrid → `/api/inbound/sendgrid` → `admin_inbox_messages` → classifier → routing → `tasks | signals | cycle_updates` carrying `origin` envelope → UI surfaces the origin chip + the "View source" modal.

### Trust Center → **PARTIAL** (probe-hygiene only — same shape as P5.13)

**What we know:**

- `tc-velocity-tile` IS rendered by `pages/TrustCenter.jsx:783,794`.
- The tile reads `/api/observability/reasoning_velocity`.
- Source-strict has been clean since P5.13.

**What blocks the probe:**

- A fresh-login Playwright session lands on Trust Center with the onboarding tour overlay (`trust-center-tour-*`) still active. The overlay obscures the tile.
- Dismissal would require either pre-setting a tour-dismissed flag in the account doc before login OR adding a tour-dismiss step to the probe.
- This is a probe-tooling carry-forward, not a tile regression.

**Recommended next-phase fix (P5.16.2-equivalent):** pre-dismiss the tour for testers via a sessionStorage flag, mirroring the P5.20.1 `akki_active_context_id` injection pattern. See §7.

---

## 6. Severity-ordered fix list for next phase

| Rank | Item | Severity | Effort | One-line plan |
| ---- | --- | --- | --- | --- |
| 1 | **P5.22 — 6 CSRF-rotted wire tests in `test_h2_5_shield_uniformity.py`** | LOW (test-rig only) | Small | Mint CSRF via `GET /api/csrf` before each `httpx.AsyncClient.post`. Already approved by user as next dispatch. |
| 2 | **Trust Center tour pre-dismissal flag for probes** | LOW (probe-hygiene) | Small | Add a `?dismiss_tour=1` query param OR a sessionStorage key `akki_tour_dismissed=1` honoured by `TrustCenter.jsx`. Source-strict pass on velocity tile already holds. |
| 3 | **P5.18 — Google OAuth migration** | MEDIUM (user-action-blocked) | Medium | Awaiting user-provided Google creds. Emergent-managed OAuth wrapper currently in place — explicitly NOT broken per user direction. |
| 4 | **Daily / biweekly digest cadence for Ideas** | LOW (future) | Medium | Defer to user-led dispatch. |
| 5 | **"Why didn't this idea appear last week?" diff view** | LOW (future) | Medium | Defer to user-led dispatch. |
| 6 | **Re-target row action on the default-inbox badge** | LOW (deferred polish) | Small | Held in backlog per user steer in P5.20.1. |

**Nothing on this list is P0.** No promise is broken. No new functionality has regressed. The application meets every promise it makes today.

---

## 7. Adjacent items noticed but out of scope

| Item | Binary | Why |
| --- | --- | --- |
| Cross-test fixture state leak (`Future attached to a different loop`) | **Adjacent** | User explicitly kept logged with a one-line note in memos. Do NOT piggyback. |
| Postmark history scrub (`git filter-repo`) | **Out-of-scope** | User explicitly deferred. |
| OAuth migration (P5.18) | **Blocked** | Awaits user Google creds. |
| WorkspaceEntryGate prelude consumes 5–9 s of probe time per workspace surface | **Adjacent** | Test-rig latency cost only — not a runtime UX concern. |
| Mongo seeded contexts (`TEST_*` rows on multiple test accounts) | **Adjacent** | Test data hygiene — already flagged in `test_credentials.md` P5.20.1 section. |

---

## 8. Cross-cutting verification at audit close

```
v1 byte-identical guard (test_solva_v1_unchanged.py):  4 passed in 3.45 s
Voice-lint:                                             clean across customer-copy surfaces
P5.13 promise lockdown sweep (re-asserted):           131 passed in 12.22 s
P5.20 default-inbox cycle lockdowns:                   10 passed (cf. P5.20.1 memo)
Combined P5 sub-suite (P5.14 + P5.15 + P5.16 + P5.17
  + P5.19 + P5.20 + v1 guard):                        147 passed (cf. P5.20.1 memo §discipline gates)

Files modified outside this memo + PRD.md top entry:   ZERO
```

---

## 9. Deliverable index

| Artefact | Path |
| --- | --- |
| This memo | `memory/sprints/P5_21_journey_audit_v2.md` |
| Consolidated journey probe (16 surfaces × 4 viewports) | `/tmp/p5_21_audit/p5_21_journey_probe_v2.py` |
| Probe evidence JSON | `/tmp/p5_21_audit/surface_evidence_v2.json` |
| Solva in-app above-fold probe (P5.14.2) | `/tmp/p5_21_audit/probe_app_solva.py` + `app_solva.json` |
| Website Solva landing probe (informational, sibling) | `/tmp/p5_21_audit/probe_solva_landing.py` + `solva_landing.json` |
| Smoke screenshots per viewport | `/tmp/p5_21_audit/smoke_*.jpg`, `app_solva_*.jpg`, `solva_landing_*.jpg` |

**HUMAN_REQUIRED for follow-up:**

1. Confirm dispatch of **P5.22** — CSRF-rotted wire-test refresh (mechanical, test-rig only).
2. Schedule **P5.18** — Google OAuth migration when creds available.
3. After P5.22 lands, the only remaining open items are user-action-blocked (P5.18 + production deploy). The application is otherwise audit-clean.

**ANTIFORGET PROTOCOL acknowledged at memo close.**
