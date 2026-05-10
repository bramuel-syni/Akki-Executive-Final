# AKKI — Product Features & Functionality Review

**Document type:** Gap analysis (specification vs current build)
**Audience:** Internal PM / engineering / governance review
**Source of truth — spec side:** `docs/PRODUCT_SPEC.md`, Home Module Spec, Document Journal Module Spec, Streaming Transitions Design Spec, NED Cycle Manager Design
**Source of truth — build side:** Read-only codebase audit on branch `main`, repo `bramuel-syni/Akki-Executive`
**Status legend:** ✅ Built  ◐ Partial  ◇ Design-only  ✗ Missing  ⚠ Mocked / stubbed / hardcoded

---

## 1. Executive Summary

AKKI is an AI-powered intelligence layer for high-level corporate governance, serving Operating Executives (CEO/CFO) and Non-Executive Directors (NEDs) at listed or pre-IPO companies. The platform provides decision support, privacy-first data synthesis, and structured reasoning, distinguished by three architectural commitments: deterministic PII redaction (**Synisense Shield**), a verifiable hash-chained audit trail (**Trust-First Chat**), and architectural isolation between company contexts (**Privacy Wall**).

### Build maturity at a glance

| # | Module | Status | Headline |
|---|---|---|---|
| 1 | Home (Portfolio + Company) | ✅ Built | Per-tab isolation real; ExCo is a derived view, not first-class |
| 2 | Document Journal | ◐ Partial | Upload + reading + commentary + chat handoff real; drag-drop, PPTX, highlights, and 3 of 4 routing CTAs missing |
| 3 | Solva Reasoning Engine | ✅ Built | All 4 modes, Layer 0–4, Two-Pass, Frame Audit, audit-gap surfacing real |
| 4 | Work Studio | ✅ Built | Briefing + Deck + Report exports deterministic; Enhance real; Deck-PDF intentionally deferred |
| 5 | Cycle Manager (Executive) | ✅ Built | Setup/Run/Ship + Resend outbound + Postmark inbound threading wired; Resend in test-mode in dev |
| 6 | Cycle Manager (NED) | ✅ Built | Phase E shipped via `ned_cycle.py`; calendar + Co-Sec sharing deferred |
| 7 | Synisense Shield | ✅ Built | 3-layer ladder (regex → Presidio → LLM-fallback), deterministic, AES-GCM at rest |
| 8 | Trust-First Chat | ✅ Built | Hash chain real; direct streaming for Claude + Gemini; GPT-5.2 proxy-buffered |
| 9 | Privacy Wall | ◐ Partial | Phase 2b live, Phase G sentinels passing; Phase 2c (pulse-text redaction) explicit `NotImplementedError` |
| 10 | Pulse | ◐ Partial | Backend Phase G real (lifecycle, dedup, cross-board); frontend drawer + tabs NOT WIRED |
| 11 | Monitor | ◐ Partial | Surfacing real; baselines + first-class "goal-at-risk" flag not stored |
| 12 | Streaming Transitions | ◐ Partial | All three strategic spots animated; no centralised abstraction |

### Top risks
1. **Pulse frontend lags backend** — UX users do not yet see Phase G lifecycle states, confidence floors, or merge_count chips.
2. **Privacy Wall Phase 2c** is an explicit `NotImplementedError` — blocks cross-board content synthesis.
3. **Resend production readiness** — domain not verified; dev runs in restricted test-mode.
4. **Postmark inbound uses URL-secret, not HMAC signature** — production roadmap item.
5. **Documentation drift** — `cycle_manager.py:25` still claims NED is design-only; Phase E shipped via `ned_cycle.py`.
6. **No CI determinism gate** for Work Studio exports — documented invariant not enforced.

---

## 2. Cross-cutting architecture

### 2.1 Identity, tenancy, role
- `db.accounts` (UUID, email-unique, bcrypt password, `declared_role ∈ {executive, ned, dual, undeclared}`, MFA via TOTP, `default_context_id`, `is_sandbox`).
- `db.contexts` is the tenant; `db.memberships` is the `(account_id, context_id, role, sub_role, status)` join. **Live role is `membership.role`**, enforced in `backend/core.py:require_context_membership`.
- **Per-tab active-context isolation** via `sessionStorage` `X-Active-Context` header — two browser tabs can sit in two different companies safely.
- JWT HS256 (access 8 h cookie, refresh 7 d); Bearer header accepted for sandbox handoff.
- Sampled `db.auth_events` (1% success / 100% failure) for the admin auth-events panel.

### 2.2 LLM layer
- **Anthropic Claude Sonnet 4.5 + Haiku 4.5** — direct SDK, real per-token streaming.
- **Google Gemini 2.5 Flash + Pro** — direct SDK, real per-token streaming.
- **OpenAI GPT-5.2** — proxy-only via `EMERGENT_LLM_KEY`; ⚠ proxy-buffered, not real per-token.
- **Emergent universal proxy** — multi-provider back-stop with per-call fallback on 5xx / network / parse error.
- **Single chokepoint**: `backend/llm_service.py` runs `shield_payload_async` (Synisense) before every provider call.
- `provider_used` + `fallback_triggered` audited on every `chat_messages` row and `work_studio_exports.llm_pass{1,2}`.

### 2.3 Email layer
- **Resend (outbound)** — real `resend.Emails.send`; deterministic opaque alias `<uuid5>@cycles.akki.ai`; ⚠ test-mode in dev; production needs verified sending domain.
- **Postmark (inbound)** — webhook wired live; URL `?secret=` shared-secret today; ⚠ HMAC signature deferred.
- ⚠ Invitation email is stubbed: `contexts.py:404` logs `[invite-email-stub]` instead of sending.

### 2.4 Audit
- **Chat hash chain is real** — `row_hash = SHA256(prev_hash + canonical_payload)`, genesis literal `"GENESIS-AKKI-CHAT-AUDIT-2026"`, downloadable verifier zip at `/api/chats/{cid}/audit/export.zip`. Daily retention sweep preserves chain integrity via a single `chat.hard_deleted` row.
- **Generic `db.audit_log`** — append-only, indexed `(context_id, created_at)`; **not** hash-chained.
- **Synisense audit** — `db.synisense_runs` per call records input SHA-256 (never raw text), surface tag, layer-won, latency.

### 2.5 Export pipeline
- python-docx (programmatic), python-pptx (programmatic), WeasyPrint + Jinja (PDF), reportlab.
- Determinism documented in `services/work_studio_export.py:1-21` — every renderer returns `(bytes, sha256, filename)`.
- Brand: **Georgia headings + Calibri body; INK colour** baked into helpers.
- ⚠ `render_deck_pdf` raises `NotImplementedError` — PPTX is canonical deck output.
- ⚠ No CI test enforces byte-determinism.

### 2.6 Test coverage
- 102 test files in `backend/tests/`.
- Privacy Wall regression: 6/6 passing; Phase G sentinel: 5/5 passing.
- Solva v2: 18+ files; Synisense: 5 files; Phase A/B/G/I/J/K/L/10/12 covered.
- 49 iter-regression files; Sprint 1/2/3/5/6 covered.
- Frontend Jest + Pa11y + Lighthouse CI configs present; no Playwright suite in-repo.

---

## 3. Module-by-module review

### Module 1 — Home (Portfolio + Company)

**Purpose.** Orient senior users in under ten seconds and route them to the right module. Two surfaces: Home 1 (Portfolio, all companies the user has a role in) and Home 2 (Company-specific, role-tuned for Exec / NED / ExCo).

**User flow.**
- Multi-company: Login → Home 1 (Portfolio) → select company → Home 2 (role-tuned) → module.
- Single-company: Login → Home 2 directly.
- Switch company affordance returns to Home 1.

**Components.** Top nav bar; primary nav; company cards (Home 1); orientation paragraphs ("coach voice"); "What needs attention" cards; recent activity list; module entry points; empty-state explainers.

**Functionality — built ✅.**
- Portfolio lists every membership; "+ New Company" creates new context.
- Per-context home dispatched from `AppHome.jsx` by `account.declared_role` (Executive / NED / Dual / Undeclared).
- Per-tab active-context isolation via `sessionStorage` `X-Active-Context`.
- `403 MEMBERSHIP_REVOKED` forces re-pick.
- Sandbox accounts pinned to `HomeExecutive`.

**Gaps vs spec.**
- ⚠ **ExCo is not a first-class role** — approximated by `declared_role="dual"` + per-context `memberships.role`. No ExCo enum.
- ✗ Company cards on Portfolio do not surface state indicators ("Cycle ships Friday", "Two goals at risk", etc.) — spec calls for these.
- ⚠ Some frontend components read `account.declared_role` directly; live role should always come from `membership.role`.

**Risks / debt.** Dual sources of role-of-truth invites drift between intent and effective permission.

**Status:** ✅ Built (with caveats above).

---

### Module 2 — Document Journal

**Purpose.** The user's working library. Frictionless upload, substantive reading, Akki Commentary, and one-click routing to other modules.

**User flow.**
1. Upload (drag-drop / file picker / image capture / email forward).
2. Document appears in library with "Processing" → "Ready" status.
3. Open in side drawer (quick) or full reading view (substantive).
4. Engage with Akki Commentary in right panel; resolve to Pulse, mark not-relevant, add user note.
5. Route via sticky footer: Add to Cycle / Add to Work Studio / Take into Solva / Ask in Chat / Delete.

**Components.** Library landing; upload area; filter chips; document rows with descriptor lines; side drawer; full reading view (3-region); Akki Commentary panel; routing footer.

**Functionality — built ✅.**
- Upload accepts PDF, DOCX, TXT, MD, CSV, XLSX, images (PNG/JPG/JPEG/WEBP/HEIC/HEIF).
- File picker + camera capture wired.
- Email-forward via Postmark webhook → `inbound_queue` triage → accept/reject → `db.documents`.
- Library landing with reverse-chronological list, BM25 search-as-you-type (300 ms debounce), single-drawer pattern.
- Full reading view at `/app/documents/:id` with paragraph anchors + "Ask AKKI" deep-link.
- Akki Commentary panel — on-demand `POST /journal-commentary`, cached on the doc row.
- Document evolution diff between versions.
- Delete wired (`DELETE /api/contexts/{cid}/documents/{did}`).
- ClamAV in prod; dev bypass via `ALLOW_UNSAFE_UPLOADS`.

**Gaps vs spec.**
- ✗ **PPTX upload NOT in accept-string** (`UploadModal.jsx:17`). Spec lists PDF/DOCX/PPTX/JPEG.
- ⚠ **Drag-and-drop NOT WIRED** — no `onDrop` / `onDragOver` handlers in `Workspace.jsx` or `UploadModal.jsx`.
- ✗ **Highlight / annotate creation flow not implemented** — `HighlightsStats.jsx` is a counter only; no creation surface, no backend route.
- ✗ **Routing CTAs**: only "Continue in Chat" + "Ask in Chat" are present. **"Add to Cycle", "Add to Work Studio", "Take into Solva" are NOT on the document drawer.**
- ⚠ Pre-2026-05-05 journal-commentary rows are mis-bucketed under `surface="briefing"` in `synisense_runs` (forensic only).

**Risks / debt.** This is the highest-traffic module; missing routing CTAs and drag-drop are direct UX failures vs spec.

**Status:** ◐ Partial. Upload + reading + commentary + chat handoff real; PPTX, drag-drop, highlights, and 3 of 4 routing CTAs missing.

---

### Module 3 — Solva Reasoning Engine

**Purpose.** Multi-layered structured reasoning. Four specialised modes — **Seek Clarity, Develop Strategy, Simulate Hypothesis, Get Perspective** — each progressing through layers with a Frame Audit pre-step and a Two-Pass refusal/four-check pipeline.

**User flow.** Pick mode → Framing layer → Frame Audit (accept/edit) → Grounding → (Hypothesis, for `simulate_hypothesis`) → Synthesis → Reflection → Lock-in → optional Continue-in-Chat / Take-to-Cycle / Fork / Export.

**Components.** SolvaLanding picker (4 tiles); flow shell; FramingScreen, FrameAuditScreen, QuestionScreen, PreparingInterstitial, ReflectionScreen; artefact viewers (StrategyMemo, ClarityRead, HypothesisStressTest, PerspectiveRead, SolvaRefusalArtefact); ProbabilityBar; ReasoningExpandable.

**Functionality — built ✅.**
- All four submodules implemented (`state_machine.py:36-39`).
- Layer flow `framing → grounding → synthesis → reflection`; `simulate_hypothesis` inserts `hypothesis` between grounding and synthesis.
- Frame Audit engine `frame_audit@1.0` writes `frame_audit_summary` + `audit_gaps[]`.
- Two-Pass orchestration in `services/two_pass.py` (classifier → provider → four-check; refusal templates; banned-word grep).
- Refusal-of-speculation guardrail when grounding contract fails.
- PDF + DOCX deterministic exports.
- Continue-in-chat tethering, attach-document, take-to-cycle (backend), fork.

**Gaps vs spec.**
- ⚠ **Take-to-Cycle frontend CTA is stubbed** (`SolvaArtefact.jsx:413,545` shows TODO + "coming soon" toast) while the backend endpoint exists.
- ⚠ "Attach material — coming soon" tile in `FramingScreen.jsx:176`.
- ⚠ Naming drift: UX calls it "Solva v3", code is `solva_v2` everywhere (deliberate non-rename per spec §14.1 to preserve audit rows).
- ⚠ `llm_adapter.py:52` references a `"placeholder_stub"` engine name — needs grep for live callers.

**Risks / debt.** Solva is the showcase module; partial wiring (CTA-but-no-callsite) hurts trust.

**Status:** ✅ Built.

---

### Module 4 — Work Studio

**Purpose.** Central hub for board materials with iterative AI polishing ("Enhance") and deterministic exports (DOCX / PPTX / PDF) following Financial Times-style brand guidelines.

**User flow.** Pick artefact (Board Pack / Minutes / Committee Pack) → open side-drawer → 5-button bar: `Export brief`, `Export summary deck`, `Export report`, `Enhance my deck`, `Enhance my report` → async export with polling → download or continue-in-chat / take-to-Solva.

**Components.** Three-tab aggregate listing; side drawer; 5-button bar; ExportModal; EnhanceModal; ShareArtefactModal; SourceStep; BlockComposer; deck-outline editors.

**Functionality — built ✅.**
- Async export pattern (`export_id` + `status="running"`; frontend polls).
- Pass 1 (silent reasoning) + Pass 2 (strict JSON) + render + sensitivity scoring (0–100 → PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED).
- SHA-256 returned per render; `byte_len` persisted.
- Banned-word grep on every output string.
- Enhance is iterative: same pipeline with prior artefact + instructions in scope.
- Continue-in-Chat mints tethered chat (`continue_chat_id`, `continue_doc_id`).
- Take-to-Solva on Work Studio artefacts (`kind: "solva_artefact"`).
- Deck DOCX uses programmatic python-docx with **Georgia headings + Calibri body, INK colour** — deterministic, no Jinja templates.

**Gaps vs spec.**
- ✗ `render_deck_pdf` raises `NotImplementedError` — PPTX is canonical deck output (intentional).
- ⚠ `llm_pass1` / `llm_pass2` only persisted on success rows (not on failure).
- ⚠ "Thin enhance" guard emits a server-authored refusal artefact rather than a degraded enhancement.
- ✗ **No CI test for byte-determinism** (`test_render_determinism.py` does not exist).

**Risks / debt.** Citation-index validator occasionally flags briefings with `Section X references citation [N] but only Y citations are declared`.

**Status:** ✅ Built (with deck-PDF carve-out).

---

### Module 5 — Cycle Manager (Executive)

**Purpose.** Workflow tool to manage board cycles through three acts: **Setup, Run, Ship**. Outputs land as Briefs in Work Studio. Outbound follow-ups use Resend with opaque cycle aliases; inbound replies thread back via Postmark.

**User flow.** Setup (Agenda, Team) → Run (Contributions, Scoreboard, Follow-ups) → Ship (Compilation → Brief in Work Studio).

**Components.** Three-act pill bar; CyclePhaseSheet; CycleStrip; CycleTracker; JudgementPanel; PolishDiffModal; ReportsTab; ReviewInboxCard.

**Functionality — built ✅.**
- Three-act pill bar (`Cycle.jsx:53-55`); 6 steps mapped to acts.
- `POST /cycle/draft-compilation` → builds Brief → persists to Work Studio → renders DOCX.
- **Real Resend** (`resend.Emails.send`) with opaque alias `<uuid5>@cycles.akki.ai`.
- **Postmark inbound webhook** wired; cycle-alias recipients matched against `db.accounts.inbound_token` and threaded into the cycle thread.
- Public reportee respond at `/api/respond/{token}`.
- APScheduler crons for `cycle/cron/run-schedules`.

**Gaps vs spec.**
- ⚠ Resend in **TEST MODE in dev** — non-test recipients return `{"mode": "test_mode_restricted"}`. Production sending domain not yet verified.
- ⚠ Postmark webhook uses **URL `?secret=` shared-secret**, not HMAC signature (roadmap).
- ⚠ Compilation injects a **placeholder citation row** `{"doc_id":"stub","doc_name":"Cycle compilation",…}` when no real citation resolves.

**Risks / debt.** Two cycle routers coexist (`cycle.py` legacy + `cycle_manager.py` Phase D) — cognitive collision for new contributors.

**Status:** ✅ Built.

---

### Module 6 — Cycle Manager (NED)

**Purpose.** NED-side companion to the Executive cycle: landing rollup, meeting CRUD with notes / positions / followups, committee through-line, BM25 search across NED-scoped artefacts.

**User flow.** Landing → meeting → notes / positions / followups → optional send-followup.

**Components.** HomeNed; NedMeeting; NedCommittee.

**Functionality — built ✅.**
- **Phase E shipped via `backend/routers/ned_cycle.py`** (12 endpoints).
- Routes wired in `App.js`: `/app/ned/meeting/:id`, `/app/ned/committee/:cid/:committee`.
- "No real-time AI in the NED In-Meeting surface" enforced as a hard rule.

**Gaps vs spec.**
- ✗ Calendar integration (deferred to v1.1).
- ✗ Sharing model with Company Secretary (deferred to v1.1).
- ⚠ **Documentation drift**: `cycle_manager.py:25` (the *Executive* router) still says verbatim *"NED-side flow ships as design only"*. That comment is **outdated** — Phase E is shipped via the separate `ned_cycle.py` router.

**Risks / debt.** Spec author should update `docs/NED_CYCLE_MANAGER_DESIGN.md` and the comment in `cycle_manager.py:25` to reflect Phase E reality.

**Status:** ✅ Built.

---

### Module 7 — Synisense Shield

**Purpose.** 3-layer PII redaction engine that de-identifies sensitive data before AI processing. Deterministic; same input → same placeholder; AES-GCM envelope-encrypted at rest.

**Architecture.**
- **Layer 1 — regex** (high-precision; wins on overlap).
- **Layer 2 — Presidio + spaCy `en_core_web_lg`** (NER).
- **Layer 3 — LLM-fallback** small-model judge (Gemini 2.5 Flash via proxy).

**Components.** Pipeline; encryption; pool; presidio_engine; regex_recognisers; llm_fallback; adapter; status surface; admin perf endpoint.

**Functionality — built ✅.**
- Deterministic placeholder labels — same token → same placeholder within one run.
- Per-surface taxonomy (16+ surfaces): `chat`, `chat_classifier`, `chat_four_check`, `chat_evidence_list`, `ingest`, `briefing`, `deck`, `report`, `brief`, `minutes`, `journal_commentary`, `enhance`, `blog`, `solva_v2.{framing,synthesis,reflection,hypothesis}`.
- Boot-time spaCy warmup.
- AES-GCM master key required in prod (`MasterKeyMissing` refusal if absent).
- Insecure-dev fallback nag loop every 60 s.
- `db.synisense_runs` records input SHA-256 (never raw text), surface tag, layer-won, latency.
- `db.synisense_shield_maps` holds AES-GCM envelope with TTL via `expireAfterSeconds=0`.

**Gaps vs spec.**
- ⚠ **Pulse signals are NOT routed through Synisense** at read time (no `surface="pulse"` runs). Same-context boundary holds today by query shape, not by projection.
- ⚠ Inbound-email `surface="ingest"` coverage on Postmark-delivered raw bodies is **unverified**.
- ✗ **`SYNISENSE_MASTER_KEY` rotation NOT supported** — any rotation invalidates `synisense_shield_maps` rows.

**Risks / debt.** Master-key rotation is currently a one-time event.

**Status:** ✅ Built.

---

### Module 8 — Trust-First Chat

**Purpose.** Multi-model chat with real-time streaming and a verifiable hash-chained audit log.

**User flow.** Pick model → ask → stream tokens → audit row written → optional restore / export-audit-zip / soft-delete.

**Components.** Model picker (5 models); MarkdownMessage with streaming; ModelAvatar; markdownStream helper.

**Functionality — built ✅.**
- **Five models exposed**: Claude Sonnet 4.5, Claude Haiku 4.5, GPT-5.2, Gemini 2.5 Pro, Gemini 2.5 Flash.
- **Hash chain real**: `row_hash = SHA256(prev_hash + canonical_payload)`; genesis `"GENESIS-AKKI-CHAT-AUDIT-2026"`.
- **Audit-zip export** at `GET /api/chats/{cid}/audit/export.zip` returns chain plus a verifier script.
- **Real per-token streaming** for Anthropic + Gemini via SSE (Phase B.3 cutover).
- Two-pass orchestration: classifier → provider → four-check.
- Daily 03:30 UTC retention sweep; chain-preserving `chat.hard_deleted` row preserves integrity.
- Per-call provider failover: direct SDK → Emergent proxy on 5xx / network / parse error.

**Gaps vs spec.**
- ⚠ **GPT-5.2 streaming is proxy-buffered**, not real per-token. Direct OpenAI keys not provisioned.
- ⚠ Strategic-deliverable Pass-2 chat turns are still proxy-buffered.
- ⚠ Mid-stream failure does **not** fall back to proxy (would double-emit); user sees `{"type":"error","code":"stream_interrupted"}`.

**Risks / debt.** GPT-5.2 perceived latency higher than Claude / Gemini due to proxy-buffering.

**Status:** ✅ Built.

---

### Module 9 — Privacy Wall

**Purpose.** Architectural isolation between company contexts. Scope is `(user, company, role)`. No cross-tenant payload leakage; cross-board features run on metadata signatures only.

**Implementation.**
- `services/privacy_wall.py` — `project_for_pulse`, `project_audit_row`, `cross_context_query`, `assert_no_cross_context_payload`.
- `services/metadata_signatures.py` — `derive_and_persist`, `derive_governance_themes`, `derive_pulse_classes`, `derive_regulatory_refs`.
- `_ALLOW_*` and `_DENY_*` field sets per collection.
- `db.context_metadata_signatures` — content-free joining table.

**Functionality — built ✅.**
- **Phase 2b live**: field-projection guards on every cross-context aggregation path.
- **Strict mode**: `STRICT_PRIVACY_WALL=true` logs drift at WARN; `STRICT_PRIVACY_WALL_RAISE=true` raises `PrivacyWallDriftError` 500.
- Cross-tenant payload reads refuse with 403/404 (verified by `test_privacy_wall.py::test_p7_payload_endpoints_refuse_foreign_context`).
- **Phase G sentinel passing**: `test_phase_g_privacy_wall_sentinel.py` 5/5 — state, content_hash, merge_count, comments, bookmarked_at, resolved_at, resolution_note, reasoning, last_merged_at all denylisted from cross-board response.

**Gaps vs spec.**
- ⚠ `redact_for_pulse_text(text)` is a **NO-OP PASS-THROUGH** placeholder (`privacy_wall.py:392-400`).
- ✗ `assemble_pulse_prompt(per_context_outputs)` raises **`NotImplementedError("Phase 2c")`**.
- ⚠ Same-context Pulse feed bypasses the projection guard (relies on `context_id` filter alone) — belt-and-braces wiring pending.

**Risks / debt.** Phase 2c is the gating dependency for any cross-board AI synthesis.

**Status:** ◐ Partial — 2b live + Phase G denylist; 2c is explicit `NotImplementedError`.

---

### Module 10 — Pulse

**Purpose.** Twitter-style signal feed per company plus a cross-board aggregator that surfaces metadata-only patterns across the user's portfolio.

**User flow (same-context).** Open Pulse → filter by type / freshness / state / confidence → comment / resolve / bookmark / save / share / take-to-Solva.

**User flow (cross-board).** Open across-boards panel → see metadata signatures matched across ≥ N other boards in window — no content, no foreign context_ids.

**Functionality — built ✅.**
- Same-context feed with filters; volume cap of 7 on Active; priority sort by `confidence × recency`.
- **Phase G** lifecycle (`active`, `bookmarked`, `resolved`, `archived`); content_hash dedup with `merge_count`.
- First-class comments on `signals.comments[]`.
- Take-to-Solva mints a Solva v2 session with `from_signal=<sid>`, `from_pulse=true`.
- **Cross-context aggregator IS REAL** (not a placeholder) — `pulse_across_boards` reads ONLY `db.context_metadata_signatures`; never touches foreign `db.signals`; verified by sentinel tests.

**Gaps vs spec.**
- ✗ **Phase G.4 frontend drill-down side drawer NOT WIRED** — `Pulse.jsx` still has F.1 single-column layout with inline comment composer. No `<Sheet side="right">`, no Storyline/Source/Reasoning/Related Context/Comments sections, no 6-button action bar in a drawer.
- ✗ **Phase G.4 tab-strip** (Active / Bookmarked / Resolved / Archived) **NOT in Pulse.jsx** — backend supports `?state=` but frontend has no tab UI.
- ⚠ `PulsePlaceholder.jsx` is an orphan file (pre-F.1; not imported).
- ✗ Topic-vector signature kind for E.0 Privacy Wall (deferred to v1.1).

**Risks / debt.** Frontend ships F.1-era UX while backend speaks Phase G — users do not see lifecycle states, confidence floors, or merge_count chips today.

**Status:** ◐ Partial.

---

### Module 11 — Monitor

**Purpose.** Surface goals at risk, baseline extraction, and signal counts (high-confidence / risks / opportunities) per role function.

**Functionality — built ✅.**
- Per-role function whitelists for signal categories (CFO / COO / Commercial).
- Reads `db.signals` filtered by category + confidence; surfaces three counters.
- `POST /strategic-goals/extract` runs LLM over context-object docs to extract goals.
- `POST /pipeline/run` runs M11 event-driven generate → verify → persist pipeline.
- Phase G.3 dedup applied at write paths.

**Gaps vs spec.**
- ✗ No dedicated `baseline` collection or route — strategic-goals extraction approximates baseline-from-docs.
- ⚠ "Goals at risk" is **derived at read time** from signal type + confidence; **no `at_risk` flag on `db.strategic_goals`**.
- ⚠ Monitor reads only the **last 50 signals** (`monitor.py:88`) — older risks can be hidden on active boards.

**Status:** ◐ Partial.

---

### Module 12 — Streaming Transitions (cross-cutting)

**Purpose.** Calm-in-motion design language for a senior cohort. Three strategic spots warrant elaborate transitions; everything else is calm-fast default (150–250 ms fade or instant).

**Strategic spots — built ✅.**
1. **Workspace Entry** — `NewWorkspace.jsx` uses framer-motion for new-workspace creation transition.
2. **Context Loading** — `AppShell.jsx` + `ContextSwitchModal.jsx` use framer-motion.
3. **Solva Page Transitions** — `PreparingInterstitial.jsx`, `TransitionMessage.jsx`, `Shell.jsx` with `usePrefersReducedMotion.js` — full transition framework.

**Defaults — built ✅.** `index.css:163-214` defines 150 ms ease transitions on borders / colours / shadows. SSE token streaming on chat.

**Gaps vs spec.**
- ⚠ **No centralised abstraction** — `components/stream/` contains only `StreamCard.jsx`. Transitions are scattered across feature components, not a `useStreamingTransition` hook or `StreamingScene` primitive.
- ⚠ Reduced-motion preference is honoured **only inside Solva**, not globally.

**Status:** ◐ Partial.

---

## 4. Consolidated gap & action register

### Priority 0 (production blockers / spec contracts broken)
- **Privacy Wall Phase 2c** — `redact_for_pulse_text` no-op + `assemble_pulse_prompt` `NotImplementedError`. Blocks any cross-board content synthesis.
- **Resend production domain verification** — sending domain not verified; non-test recipients silently rejected.

### Priority 1 (high-traffic UX gaps vs spec)
- **Document Journal**: add PPTX to accept-string; wire drag-and-drop; ship highlight/annotate creation flow; add "Add to Cycle", "Add to Work Studio", "Take into Solva" CTAs on document drawer.
- **Pulse**: ship Phase G.4 drill-down side drawer + tab-strip (state filter) on frontend.
- **Solva**: un-stub "Take-to-Cycle" frontend CTA (backend endpoint exists).
- **Postmark inbound**: replace URL-secret with HMAC signature.

### Priority 2 (governance / hardening)
- **Privacy Wall**: wire `project_for_pulse` on same-context Pulse feed (belt-and-braces).
- **Synisense**: route Pulse signals through Shield at read time; verify `surface="ingest"` coverage on Postmark inbound; implement master-key rotation migration.
- **Work Studio**: add `test_render_determinism.py` CI gate; persist `llm_pass1`/`llm_pass2` on failure rows.
- **Chat**: provision direct OpenAI keys to unlock GPT-5.2 per-token streaming.
- **Monitor**: first-class `at_risk` flag on `db.strategic_goals`; paginate beyond last-50 signals.

### Priority 3 (documentation drift)
- Update `cycle_manager.py:25` and `docs/NED_CYCLE_MANAGER_DESIGN.md` to reflect Phase E ship.
- Resolve Solva naming drift (`solva_v2` code ↔ "v3" UX brand) — deliberate, but should be a single-line README note.
- Decide on ExCo as first-class role vs continued derived-view treatment.

### Priority 4 (deferred / v1.1)
- Deck PDF renderer.
- NED calendar integration; Co-Sec sharing model.
- Topic-vector signature kind for Privacy Wall.

---

## 5. What is verifiably true today

- Privacy Wall regression suite: **6/6 passing**.
- Phase G Privacy Wall sentinel: **5/5 passing**.
- Backend health endpoint live: `GET /api/health → {"status":"ok","db":"up"}`.
- 102 backend test files including 18+ Solva v2 tests and 5 Synisense tests.
- Hash chain in `db.chat_audit_log` is mathematically real and exportable.
- Resend `resend.Emails.send` is the live outbound call; Postmark inbound webhook is live in dev.
- Synisense runs persist input SHA-256 only — **never raw text**.

## 6. What is mocked, stubbed, or hardcoded (transparency list)

- ⚠ Invitation email stub (`contexts.py:404` logs instead of sending).
- ⚠ Resend test-mode in dev (`test_mode_restricted` for non-test recipients).
- ⚠ Postmark webhook URL-secret (HMAC signature pending).
- ⚠ Compilation placeholder citation row `{"doc_id":"stub",…}`.
- ⚠ Solva "Take-to-Cycle" frontend CTA — TODO + toast (backend endpoint real).
- ⚠ Solva "Attach material — coming soon" tile.
- ⚠ Solva `llm_adapter.py:52` `"placeholder_stub"` engine name reference.
- ⚠ Privacy Wall `redact_for_pulse_text` — no-op pass-through.
- ✗ Privacy Wall `assemble_pulse_prompt` — `NotImplementedError("Phase 2c")`.
- ⚠ Work Studio `render_deck_pdf` — `NotImplementedError` (PPTX is canonical).
- ⚠ GPT-5.2 streaming — proxy-buffered, not real per-token.
- ⚠ Pulse frontend on `Pulse.jsx` — F.1 layout (no Phase G drawer / tabs).
- ⚠ `PulsePlaceholder.jsx` orphan file.
- ⚠ ClamAV bypassed in dev via `ALLOW_UNSAFE_UPLOADS=true`.
- ⚠ "Goals at risk" derived at read time, no `at_risk` flag stored.

---

*Document generated by codebase audit on branch `main`. For changes to feature status, regenerate from `backend/` and `frontend/src/` after each phase ship.*
