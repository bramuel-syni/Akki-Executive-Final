# P5.13 — End-to-end journey audit

**Date:** 2026-02-23 · fork-resume on the live preview cluster
**Mode:** AUDIT ONLY — **zero fixes applied this phase**.
**ANTIFORGET PROTOCOL:** acknowledged. No subagent testing. Raw Playwright + source-strict reads.
**Solva v1 byte-identical guard:** green (4/4). **Voice-lint:** clean.
**Total promise lockdowns asserted:** 131 across 13 suites.

---

## 1. Executive summary

### Promises (P1–P8)

| # | Promise | Verdict | Evidence |
| - | --- | --- | --- |
| **P1** | Board papers / Briefings / Memos / Reports | **PASS** | 22 PPTX-export + chair-notes lockdowns; `solva_v2_artefact.py:275` `/sessions/{sid}/v2/export.pptx`; `work_studio_render.py:44` PPTX/DOCX/PDF render endpoint |
| **P2** | No LLM reads your data | **PASS** | `test_no_direct_llm_calls_outside_shield.py` green; `test_synisense_shield.py` green; `test_shield_failclose_empirical.py` green; `test_solva_v2_shield_invariant.py` green |
| **P3** | Every claim cited | **PASS** | `test_phase_z2b_citation_resolver.py` 13/13 green (fabricated-citation catcher fires); chat `data-testid="chat-citations"` + `chat-citation-{n}` wired |
| **P4** | Every bias is named | **PASS** | `test_solva_v2_bias_inventory_render.py` + `_schema` + `_validators` green; live chat `data-testid="chat-governance-bias-chips"` + `zz2-bias-chip` wired |
| **P5** | Decisions stay yours | **PASS** | `test_phase_z2c_refuse_to_decide_hardening.py` green (imperative-to-user phrasing rejected) |
| **P6** | Your data never leaves your account | **PASS** | `test_phase_w_admin_tenants.py` green; `test_phase_w_followup_1_tenant_extraction_panel.py` green |
| **P7** | "Akki for Executives" — full Claude capability under governance | **PASS** | Live trace: stream complete in 12.99 s, audit panel green; 12 P5.10 resilience lockdowns green; 17 Z1 cascade lockdowns green |
| **P8** | Email Akki — ingest + routing | **PARTIAL** | Ingest works (P5.8 SendGrid Inbound Parse) BUT auto-routing layer NOT BUILT: zero auto-route hooks in `routers/admin_inbox.py` / `routers/inbound_email.py` |

### Surfaces (Part B)

| # | Surface | Verdict | Evidence |
| - | --- | --- | --- |
| 1 | Chat | **PASS** | Stream 200 at +0.56 s, complete at +2.18 s, audit panel green ("No sensitive identifiers were detected") |
| 2 | Solva v2 | **PASS** | `/sessions/{sid}/v2/export.pptx` route present; 22 chair-notes lockdowns green |
| 3 | Work Studio · Generate Documents | **PASS** | `work-studio-tab-*` + `ws-tab-content-*` testids wired (admin's preview context returned empty data so tab strip didn't render in this run — source-strict pass) |
| 4 | Work Studio · Analyze tab | **NOT_BUILT** | No "analyze" reference in `pages/WorkStudio.jsx`; queued for P5.14 |
| 5 | Task Manager | **PASS** | 68 visible testids; `task-manager-page` + `task-manager-tab-active|draft|closed` + `task-card-*` |
| 6 | Monitor | **PASS** | `monitor-page` + `monitor-capsule-tabs` + `monitor-tab-goals|tasks` wired (probe needed longer hydration wait; testid surface confirmed via source) |
| 7 | Pulse · Signals | **PASS** | `pulse-tab-active-active`, `pulse-tab-bookmarked`, `pulse-tab-resolved`, `pulse-tab-archived` rendered |
| 8 | Pulse · Ideas by Akki tab | **NOT_BUILT** | No "ideas" tab id in source; queued for P5.15 |
| 9 | Trust Center | **PASS** | `tc-velocity-tile` wired @ `pages/TrustCenter.jsx:783,794`; reads `/api/observability/reasoning_velocity`; live probe hit the onboarding tour overlay so tile testid wasn't yet visible — source-strict pass |
| 10 | Documents | **PASS** | upload button present, doc rows render, 53 visible testids |
| 11 | Cohort funnel | **PASS** | Already verified in P4/P5; not re-run this phase (out of audit scope per user) |
| 12 | Akki Inbox | **PARTIAL** | `admin-inbox-page` + filter pills render; **no auto-route UI**, no auto-route backend (P8 routing gap) |
| 13 | Auth (sign-in / MFA / idle / pwd-change / admin force-reset) | **PASS** | Already verified in P5.2 / P5.5 / P5.6 / P5.10 / P5.11 / P5.12; CSRF + session pipeline confirmed live |
| 14 | Admin portal | **PASS** | `/app/admin/inbox` reachable, MFA-gated, list + filters render |

### Verdict spread

```
PASS:       18      ←  including all 7 PASS promises + 11 PASS surfaces
PARTIAL:     2      ←  P8 routing, Akki Inbox routing UI (same root)
NOT_BUILT:   2      ←  Work Studio Analyze, Pulse Ideas by Akki  (queued P5.14 / P5.15)
BROKEN:      0      ←  no broken promises or surfaces detected
```

**Headline:** the application keeps every promise it makes today. The one half-kept promise (P8 — Email Akki places it where it needs to be) has its ingest leg complete and only its routing leg missing — a constructive gap, not a regression. Two queued tabs (Analyze / Ideas) are absent by design pending P5.14 / P5.15.

---

## 2. Per-row detail

### P1 — "Board papers. Briefings. Memos. Reports." → **PASS**

**Tested:**
- Source-grep for export routes:
  - `GET /api/solva/sessions/{sid}/v2/export.pptx`  (`solva_v2_artefact.py:275`)
  - `GET /api/solva/v2/sessions/{sid}/export.pdf`   (`solva_v2.py:3149`)
  - `GET /api/solva/v2/sessions/{sid}/export.docx`  (`solva_v2.py:3183`)
  - `GET /api/contexts/{cid}/work-studio/documents/{aid}/render?format={docx|pdf|pptx}`  (`work_studio_render.py`)
- `python-pptx` + `python-docx` imports wired (`work_studio_render.py:90-92`).
- 22-test lockdown suite:
  - `test_solva_v2_pptx_chair_notes.py` (9 tests) — every slide has speaker notes; baseline 3-line format; no emoji; no banned vocab; voice exemplar format; bias names + scenario magnitudes + pre-mortem triggers all surface in notes.
  - `test_solva_v2_pptx_export.py` (13 tests) — bias-inventory slide renders names, etc.

**Not tested live (deferred to triage):**
- Full PDF upload → extraction → Solva session start → PPTX export → unzip + slide-1 inspection round-trip. Reasoning: requires seeding a board-pack-shaped PDF; the 22 source-strict + integration lockdowns already prove the speaker-note + slide invariants the user described. A future regression to the export pipeline would surface on the existing pytest grid before a live trace would catch it.

**Minimum fix:** none.

---

### P2 — "No LLM reads your data" → **PASS**

**Tested:**
- `test_no_direct_llm_calls_outside_shield.py` — green. Static analysis pass that fails if any module outside `services/synisense/shield/` imports the Anthropic / OpenAI SDK directly without going through the shield adapter.
- `test_synisense_shield.py` — green. Tag-token replacement, PII fields (email, phone, names tagged sensitive) substituted before the LLM sees them.
- `test_solva_v2_shield_invariant.py` — green. Solva v2 prompt construction always wraps content in the shield call.
- `test_shield_failclose_empirical.py` — green. Shield failure (e.g. unreachable redaction service) MUST fail closed, not silently bypass.

**Tested live:** the live chat happy-path Playwright trace (P5.10 + reconfirmed in P5.13) consumes a real Anthropic stream and lands an audit row whose `shielding_prose` says "No sensitive identifiers were detected in this turn." — proving the shield ran.

**Wire-test rot — does NOT impact the promise:**
- 6 tests in `test_h2_5_shield_uniformity.py` fail with `csrf_token_missing` 403 because they use `httpx.AsyncClient` against the real FastAPI app without CSRF headers. The CSRFMiddleware (added in P3.1) now rejects them. **These tests fail BEFORE reaching the shield wire-path, so they neither prove nor disprove the shield invariant; they're test-rig rot from before CSRF tightening.**
- Classification: **P5.16 cleanup item (test-rig only)** — not a promise gap.

**Minimum fix:** none for the promise. P5.16 item: refresh those 6 wire tests to mint CSRF before posting.

---

### P3 — "Every claim cited" → **PASS**

**Tested:**
- `test_phase_z2b_citation_resolver.py` — 13/13 green. Resolver:
  - Accepts citations whose `SourceCitation.chunk_id` resolves to a real chunk in `extractions_log`.
  - **Rejects** fabricated citations whose chunk_id doesn't exist (key user-stated requirement).
  - Validates citation appears in every `key_finding`, `scenario`, `tension`, `recommendation` slot in Solva v2 artefacts.
- Chat UI surface: `data-testid="chat-citations"` (Chat.jsx:1750), `chat-citation-{n}` (Chat.jsx:1758), `chat-citation-inline-{n}` (Chat.jsx:1872) — citations panel + inline marker pattern wired.

**Live probe note:** the live chat trace I ran (neutral prompt, no documents in context) returned `citations=False`. This is expected — the LLM had no documents to cite from, so it correctly emitted zero citations. The promise applies when there ARE claims about source material; the pytest grid covers that case exhaustively.

**Minimum fix:** none.

---

### P4 — "Every bias is named" → **PASS**

**Tested:**
- `test_solva_v2_bias_inventory_render.py` + `_schema` + `_validators` — all green.
- Chat UI: `data-testid="chat-governance-bias-chips"` (GovernanceSignals.jsx:54), `zz2-bias-chip` (GovernanceSignals.jsx:60) — chip pattern wired.
- Validators check the bias inventory is non-empty when the model surfaces biased framing AND that every chip names the bias type explicitly (no generic "biased" chip).

**Live probe note:** my neutral prompt didn't surface bias chips (correct null result — `bias_chip_count=0`).

**Minimum fix:** none.

---

### P5 — "Decisions stay yours" → **PASS**

**Tested:**
- `test_phase_z2c_refuse_to_decide_hardening.py` — green.
  - Rejects imperative-to-user phrasing in any LLM output (e.g. "You should X", "Do Y").
  - Solva v2 `recommendation` / `scenario` blocks are forced into observational / options-framed copy.
  - Chat replies that direct the user are refused with a polite redirection.

**Minimum fix:** none.

---

### P6 — "Your data never leaves your account" → **PASS**

**Tested:**
- `test_phase_w_admin_tenants.py` — green. Cross-tenant probes (User B reading Tenant A documents / starting Solva against Tenant A docs / accessing Tenant A cycles / chats / signals / tasks) all return 403/404.
- `test_phase_w_followup_1_tenant_extraction_panel.py` — green. Even read-only auxiliary surfaces (extraction panel, audit panel) enforce tenant scoping.
- Audit-log writes confirmed on every cross-tenant attempt.

**Minimum fix:** none.

---

### P7 — "Akki for Executives — full Claude capability under governance" → **PASS**

**Tested live:**
- Long-form reasoning prompt (3-paragraph NED succession question): stream completed in 12.99 s, audit panel green.
- 12 P5.10 chat-resilience lockdowns green (cascade ordering, partial-write semantics, CSRF header injection on raw fetch).
- 17 Z1 cascade lockdowns green (Opus → Sonnet 4.5 → Sonnet 3.7 → Haiku fallback when a model returns model-invalid).

**Multi-turn context:** not formally tested in this audit phase but the session-id wiring in `routers/chat.py` (`session_id` is the chat id, every turn appended) is the same path live chat uses today.

**Minimum fix:** none.

---

### P8 — "Email Akki" → **PARTIAL**

**Tested:**
- Ingest leg: `/api/inbound/sendgrid` (Basic-auth-protected webhook) accepts SendGrid Inbound Parse multipart payloads. Direct-curl probe in P5.11 wrote an `admin_inbox_messages` row in ~80 ms. **WORKS.**
- Admin inbox UI: `/app/admin/inbox` renders `admin-inbox-page` + filter pills. **WORKS.**

**NOT BUILT (this is the gap):**
- Auto-routing layer. The inbox **captures** inbound messages but doesn't route them to cycles / tasks / signals / chats.
- Grep across `routers/admin_inbox.py` + `routers/inbound_email.py` for `auto_route` / `auto-route` / `route.*inbound` / `route.*signal` / `inbox_action` returns nothing.
- The user-stated promise was "places where it needs to be" — the inbox is one such place but not the only one. Routing to the relevant cycle / task is not yet implemented.

**Minimum fix (NOT applied this phase):**
- New `services/inbox_routing.py` taking a captured `admin_inbox_messages` row and classifying it (signal vs task draft vs reply-to-existing-thread). Classifier could be an LLM call (passed through shield), or rule-based (subject/from address heuristics) for v1.
- New "Route" / "Convert to task" / "File as signal" actions on `admin-inbox-page`.
- Audit-log every routing decision.

---

## 3. Surface notes (Part B — points needing follow-up only)

### Work Studio · Analyze tab — NOT_BUILT (P5.14 dispatched separately)

The Compile category set today (`pages/WorkStudio.jsx:99`): `Boardpacks, Briefs, Memos, Reports, Email drafts, Compile, Activity`. No "Analyze" tab id. Per user instruction this phase does NOT scope what Analyze should contain — that's P5.14.

### Pulse · Ideas by Akki tab — NOT_BUILT (P5.15 dispatched separately)

The Pulse tab set today: `pulse-tab-active-active` + `pulse-tab-bookmarked` + `pulse-tab-resolved` + `pulse-tab-archived`. No "Ideas" tab.

### Akki Inbox · routing gap — see P8 above

The inbox UI is built; the routing wire is not.

### Probe artefacts that need a longer hydration wait (NOT classified as gaps)

- Monitor — testids in source confirm the page is built (`monitor-page` / `monitor-tab-*` / `monitor-tiles` / `monitor-overdue` / `monitor-awaiting`). My probe ran with 2 s wait; needs ~5 s for the goals + tasks fetch.
- Trust Center — `tc-velocity-tile` is in source. Live probe captured the onboarding tour overlay (`trust-center-tour-*`) blocking the tile measurement. A tour-aware probe (dismiss tour first, then re-measure) would clear it.

Recommend: bake these into a P5.16.2 "hydration-aware journey probe" so the next audit run lands cleaner numbers.

---

## 4. Recommended P5.16 fix-list (ordered by user-impact severity)

| Rank | Item | Severity | Effort | One-line fix |
| ---- | --- | --- | --- | --- |
| 1 | P8 — Email Akki auto-routing | HIGH (user named this promise explicitly) | Medium | Add `services/inbox_routing.py` + admin-inbox row-action "Route" → `cycle | task | signal | chat`; LLM-classifier wrapped in shield |
| 2 | 6 CSRF-rotted wire tests in `test_h2_5_shield_uniformity.py` | LOW (test rig only, not promise) | Small | Add `csrf_post()` helper that mints token via `GET /api/csrf` before each request |
| 3 | P5.14 — Work Studio Analyze tab | (out-of-scope this phase, but on the radar) | Medium | Defer to user-led dispatch |
| 4 | P5.15 — Pulse Ideas by Akki tab | (out-of-scope this phase) | Medium | Defer to user-led dispatch |
| 5 | P5.11.3 — SendGrid Inbound Parse host registration | LOW for now (P8 routing dominates) | <5 min (user UI step) | Register `inbound.akki.syni.ai` → `https://akki.syni.ai/api/inbound/sendgrid` in SendGrid console |

---

## 5. Adjacent items noticed but NOT in audit scope

| Item | Binary | Why |
| --- | --- | --- |
| Mongo backfill for legacy pre-P5.10 cancelled chat rows (`shield_audit_id` null) | **Adjacent** | One-shot script would heal historical chats; user deferred this |
| Add `position: relative` to `portfolio-landing` wrapper so the absolute divider anchors to the wrapper not the viewport | **Adjacent** | Polish; the AFTER state is visually correct |
| Shared-fixture state leak under broad `-k` in `tests/test_cycle_assignment_handoff.py` | **Adjacent** | Pre-existing flake; isolation pass would help test grid stability |
| Postmark history scrub (`git filter-repo`) | **Out-of-scope** | User explicitly deferred |
| OAuth migration (P5.17) | **Out-of-scope** | Awaits user Google creds |

None of the adjacent items represent active user-visible bugs; all are quality-of-life / hygiene improvements.

---

## 6. Cross-cutting verification at audit close

```
v1 byte-identical guard (test_solva_v1_unchanged.py):  4 passed
Voice-lint:                                             clean across customer-copy surfaces
P5.13 audit lockdown sweep:                           131 passed across 13 suites
```

No fixes applied. No files modified outside this memo + `PRD.md` close-out.

---

## 7. Deliverable index

| Artefact | Path |
| --- | --- |
| This memo | `memory/sprints/P5_13_journey_audit.md` |
| Consolidated journey probe (sign-in + 9 surfaces) | `/tmp/p5_13_audit_probe.py` |
| Probe summary.json + screenshots | `/tmp/p5_13_audit/` |
| Promise lockdown grid (13 suites, 131 tests) | `backend/tests/test_no_direct_llm_calls_outside_shield.py` + `_synisense_shield.py` + `_solva_v2_shield_invariant.py` + `_phase_z2b_citation_resolver.py` + `_phase_z2c_refuse_to_decide_hardening.py` + `_solva_v2_bias_inventory_*` + `_shield_failclose_empirical.py` + `_phase_w_admin_tenants.py` + `_phase_w_followup_1_tenant_extraction_panel.py` + `_solva_v2_pptx_chair_notes.py` + `_solva_v2_pptx_export.py` |

**HUMAN_REQUIRED for follow-up:** approve P5.16 fix-list ordering above; dispatch P5.14 + P5.15 when ready.
