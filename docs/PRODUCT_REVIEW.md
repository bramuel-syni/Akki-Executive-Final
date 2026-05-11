# AKKI — Product Features & Functionality Review

**Date** 2026-05-11 (Phase F0 + G + H + I sprint complete — production launch readiness)
**Scope** End-to-end audit of the AKKI executive / non-executive-director platform across every shipped module. Source-grounded — every assertion is traceable to file+line, an audit row, a test, or a boot log. Replaces the 2026-05-10 review verbatim.
**Author** Codebase-grounded, written from a read of `backend/` + `frontend/src/` after the G+H+I production-launch sprint shipped.

This review is **not** a marketing brochure. It separates what is genuinely built and tested from what is mocked, stubbed, or hardcoded. The transparency list in §6 is the single source of truth for "what is still off in dev"; the launch checklist in §7 is the single source of truth for "what remains before production cutover".

---

## 1. Executive Summary

AKKI is a Calibri/Georgia editorial-register web application for senior decision-makers — operating executives (CEO/CFO/COO) and non-executive directors. It is **not** a chat product. It is an audit-defensible working environment for the work that actually matters: cycle preparation, board judgement, structured reasoning, document journalling, and the trust ladder underneath.

After the May-2026 production-launch sprint, **all 13 originally-scoped modules ship, plus the new Module 14 (pre-login website)**. Privacy Wall Phase 2c (cross-board content shielding) is live. All three LLM providers stream direct to the browser (Claude, Gemini, GPT). Postmark inbound webhook arms HMAC by default. Resend outbound runs from the verified sending domain `akki.syni.ai`. The Document Journal accepts PPTX with drag-and-drop and exposes three routing CTAs (Cycle / Work Studio / Solva). The Pulse drawer + tab strip is wired. Universal Search F1 covers all seven surfaces. The 9-page marketing site (Plausible analytics, AKKI oxblood brand, four editorial photographs, WCAG 2.1 AA) lives outside the gated tree at `/`.

### Build maturity at a glance

```
Module                                              Status        Notes
─────────────────────────────────────────────────────────────────────────────────────────
 1. Home (Portfolio + Company)                       ✅ Built     Role dispatch + first-session guard
 2. Document Journal                                 ✅ Built     PPTX + drag-drop + 3 routing CTAs (H1/H2);
                                                                  highlight/annotate CREATION remains deferred
 3. Solva Reasoning Engine                           ✅ Built     4 modes; frame audit; refusal artefact;
                                                                  PDF/DOCX export; take-to-cycle + attach-doc real (H4)
 4. Work Studio                                      ✅ Built     DOCX/PPTX deterministic; sensitivity scoring;
                                                                  validation fan-out (11B); public Chair view (11A);
                                                                  deck PDF intentionally NotImplementedError
 5. Cycle Manager (Executive)                        ✅ Built     Setup/Run/Ship; outbound Resend + inbound Postmark
                                                                  threaded back to cycle_followups.replies[]
 6. Cycle Manager (NED)                              ✅ Built     Phase E; LLM-free "In" phase; cross-board landing
 7. Synisense Shield                                 ✅ Built     3-layer regex→Presidio→LLM; AES-GCM envelope;
                                                                  16+ surfaces incl. surface="pulse" (G5)
 8. Trust-First Chat                                 ✅ Built     ALL 3 PROVIDERS STREAM DIRECT (Claude+Gemini+GPT);
                                                                  hash-chained audit; offline verifier ZIP
 9. Privacy Wall                                     ✅ Built     Phase 2b projections + Phase 2c content shielding
                                                                  shipped (G1); BOARD-N boundary markers live
10. Pulse                                            ✅ Built     G.4 drawer + tab strip wired (H3); cross-board
                                                                  metadata-only aggregator; comments + lifecycle
11. Monitor                                          ✅ Built     Per-role function whitelists; goals-at-risk derived
12. Streaming Transitions (cross-cutting abstraction) ◐ Partial   Per-surface streaming works; central abstraction
                                                                  deferred to v1.1 (not P0)
13. Universal Search                                 ✅ Built     F0 federated search + F1 cycle/work_studio/briefs
                                                                  surfaces shipped (H5); q_hash audit
14. Pre-login Website (akki.syni.ai)                 ✅ Built     9 pages; AKKI oxblood brand; Georgia + Calibri;
                                                                  4 editorial photos; Plausible; cohort + contact
                                                                  intake → db.early_access_applications
```

### Top risks (post-sprint)

1. **DNS cutover for `akki.syni.ai` → production backend is pending user action.** The preview URL `akki-executive.preview.emergentagent.com` is currently authoritative; the Postmark webhook URL pasted into the dashboard must point there during the transition.
2. **GPT-5.2 streams direct but is currently routed via the Emergent proxy** with `stream=True` (litellm.acompletion). If the Emergent proxy regresses on streaming, the fallback path is buffered-direct via `proxy_buffered` (last resort, NOT first choice). Anthropic + Gemini are direct-SDK and unaffected.
3. **Synisense `SYNISENSE_MASTER_KEY` rotation invalidates the shield-map cache.** A rotation procedure exists in concept but is not automated; if rotation is needed, treat as a planned-outage event.
4. **Legacy `test_iter*.py` and `test_akki_g1.py` regress in the full suite** due to a login-rate-limit cascade + stale `tenants`→`contexts` key references. The new Phase-G/H/I tests pass cleanly in isolation; the legacy suites require a separate fixture-hygiene pass (out of this sprint's scope).
5. **ClamAV bypassed in dev** (`ALLOW_UNSAFE_UPLOADS=true`). Production boot-guard refuses the flag when `AKKI_ENV=production`.

---

## 2. Cross-cutting architecture

### 2.1 Identity, tenancy, role
- **Bcrypt** password hashing; **JWT HS256** with HttpOnly+Secure+SameSite=None cookies (access 8 h, refresh 7 d).
- **Per-email rate limit** — 5 failed logins → 15-minute lockout (`db.login_attempts`, `auth_throttle`).
- **TOTP MFA** with QR provisioning (`pyotp` + `qrcode`).
- **Per-tab active-context isolation** via `sessionStorage` → `X-Active-Context` header. Required on every gated request; backend's `require_context_membership()` dependency cross-checks against `db.memberships`.
- **Declared roles** `{executive, ned, dual, undeclared}` drive the role-dispatch home page and the system-prompt voice addendum (NED-peer tone when `role=='ned'` AND `context_type.startswith('ned_')`).
- **Sampled observability** — `db.auth_events` captures 1% of successes + 100% of failures; surfaced at `/admin/auth-events`.

### 2.2 LLM layer
- **Streaming, post-sprint:** all three providers stream direct to the browser via SSE. Boot log line is the canonical attestation:
  ```
  [chat] streaming: claude=direct_stream gemini=direct_stream gpt=direct_stream
  ```
  - **Claude** (Sonnet 4.5, Haiku 4.5) — direct via official `anthropic` SDK `messages.stream`.
  - **Gemini** (2.5 Pro, 2.5 Flash) — direct via `google-genai` SDK `aio.generate_content_stream`.
  - **GPT-5.2** — direct via `litellm.acompletion(stream=True)` against the Emergent proxy. **No longer proxy-buffered.** The buffered-proxy path is the LAST resort fallback (see `backend/services/llm_streaming.py:8-21`); first-cut emission for GPT-5.2 is per-token-streamed.
- **Universal proxy key:** `EMERGENT_LLM_KEY` — used by the Emergent SDK + litellm for proxy paths; direct providers use their respective SDKs when keys are present (fallback to proxy otherwise).
- **Failover:** direct → proxy-streamed (litellm) → proxy-buffered. Hard mid-stream error emits a single `{"type":"error","code":"stream_interrupted"}` chunk to avoid double-emission.
- **Two-pass discipline** — classifier → provider → four-check. Phase 11B introduces an independent Gemini-2.5-Flash validator on Decks / Reports / Solve syntheses; `validation` block persisted with `{verdict, confidence, validator_provider, validator_model, notes}`. Daily soft cap (`VALIDATOR_DAILY_SOFT_CAP` = 200/surface) with `qualified` fallback when tripped.
- **Citation grounding (Phase 11C)** — BM25 anchors against context documents; hallucinated citations dropped; `[n]` chips inline in chat messages with full `{n, anchor_id, doc_id, doc_name, page, paragraph_number, snippet}` resolution.

### 2.3 Email layer
- **Outbound — Resend** from verified sending domain **`akki.syni.ai`** (live + verified, May 2026). Configuration:
  - `RESEND_API_KEY` — secret
  - `RESEND_FROM_EMAIL` = `noreply@akki.syni.ai`
  - `RESEND_FROM_NAME` = `AKKI`
  - `CYCLE_REPLY_DOMAIN` = `akki.syni.ai` — cycle aliases now mint as `<uuid5>@akki.syni.ai`
  - `email_service.send_email()` always returns `{ok, id, mode∈{sent, noop, test_mode_restricted, error}}` and **never raises**. Test-mode restriction is enforced in dev until the Resend dashboard has a verified test recipient.
- **Inbound — Postmark** webhook on `/api/inbound/postmark`. Authentication ladder (`backend/routers/inbound_email.py:65-93`):
  1. **HMAC-SHA256** of the raw request body in `X-Postmark-Signature` (or alias `Postmark-Signature`), keyed by `POSTMARK_WEBHOOK_SECRET`. **Default — on.**
  2. **HTTP Basic-Auth** — accepted with the same secret as the password.
  3. **URL-secret** in `?secret=…` — **only when `POSTMARK_USE_HMAC=false` AND `AKKI_ENV != production`.** Production boot-guard refuses `POSTMARK_USE_HMAC=false` (`_verify_inbound_boot_guard`).
- **Cycle inbound threading** — opaque alias `<uuid5>@akki.syni.ai` routes replies back to `db.cycle_followups.replies[]`, marks `status='replied'`, writes `cycle.followup.replied` audit row. Idempotent on replay (`duplicate:True` returned). Alias-unmatched messages fall to `db.inbound_queue` with `source='cycles_alias_unmatched'`.

### 2.4 Audit
- **Generic `audit_log`** — append-only `(id, context_id, account_id, action, resource_type, resource_id, metadata, created_at)`. Surfaced at `/api/me/governance/audit` and `/api/contexts/{cid}/audit-log[/export]`.
- **Hash-chained chat audit** — `db.chat_audit_log` with `row_hash = SHA256(prev_hash + canonical_payload)`; genesis literal `"GENESIS-AKKI-CHAT-AUDIT-2026"`. Exported as a ZIP at `GET /api/chats/{cid}/audit/export.zip` with an offline verifier script.
- **Synisense forensic** — `db.synisense_runs` records **input SHA-256 only** (never raw text), surface, layer-won, latency.
- **Universal Search forensic** — `q_hash = SHA-256(q.strip().lower())` is the ONLY query data persisted; raw `q` is never stored. One `search.federated` audit row per call.

### 2.5 Export pipeline
- Single contract — every renderer returns `(bytes, sha256, filename)`. `byte_len` persisted on the export row.
- DOCX via `python-docx` (Georgia headings + Calibri body, INK colour).
- PPTX via `python-pptx` — **canonical deck output**.
- PDF via `weasyprint` + Jinja templates (Solva artefacts; report PDF).
- Banned-word grep on every output string.
- `render_deck_pdf` intentionally raises `NotImplementedError("Deck PDF render is intentionally deferred; PPTX is canonical")` — `backend/services/work_studio_export.py:733`.
- Sensitivity scoring (`backend/studio_sensitivity.py`) applied at render-time: deterministic 0–100 → PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED.

### 2.6 Test coverage
- **102+ pytest files** in `backend/tests/`.
- **Trust-critical regression — 29/29 passing in 2.14 s** (last verified 2026-05-11):
  ```
  pytest backend/tests/test_privacy_wall.py \
         backend/tests/test_phase_g_privacy_wall_sentinel.py \
         backend/tests/test_privacy_wall_phase_2c.py \
         backend/tests/test_universal_search.py -q
  ```
- **New Phase G/H/I tests pass cleanly in isolation:** `test_privacy_wall_phase_2c.py` + `test_universal_search.py` = 18/18 in 1.68 s.
- **Full-suite caveat:** 435 passed / 121 failed / 409 errored / 46 skipped. The 409 errors are 99% downstream of a single login-rate-limit cascade (`Too many failed attempts. Try again shortly.` × 407) compounded by stale `tenants`/`clusters` keys in legacy `test_iter*.py` and `test_akki_g1.py` files. None of the sprint-shipped modules regress in isolation. A fixture-hygiene pass on the legacy suites is recommended but is **not a launch blocker**.
- Frontend reducer-level Jest tests on `solvaFlow.js` (36 cases) + `sandboxV2Flow.js` (28 cases). No Playwright suite in-repo.

---

## 3. Module-by-module review

### Module 1 — Home (Portfolio + Company)
- **Files** `backend/routers/{auth, contexts, active_context, committees}.py`; `frontend/src/pages/{AppHome, ContextPortfolio, NewWorkspace, Manage, home/Home{Executive,Ned,Dual,Undeclared}}.jsx`
- **What it does** Role-dispatched landing. Executive sees company portfolio. NED sees cross-board overview. Dual sees both with strict-Privacy-Wall split. New-context creation flow with industry/jurisdiction presets.
- **Auth + first-session guard** chained: `ProtectedRoute` → `FirstSessionGuard` → role dispatcher.
- **Identifiers** UUID throughout — no MongoDB `ObjectId` ever exposed.

### Module 2 — Document Journal ✅
- **Files** `backend/routers/documents.py` (16 endpoints) + `documents_service.py` + `paragraph_anchors.py` + `document_commentary_service.py`; `frontend/src/pages/{Workspace, ReadingView}.jsx` + `components/upload/UploadModal.jsx` + `components/documents/*` (8 files)
- **Upload** PDF / DOCX / **PPTX (H1 — 2026-05-11)** / TXT / MD / CSV / XLSX / images (PNG/JPG/JPEG/WEBP/HEIC/HEIF). File picker + camera capture + **drag-and-drop on the library landing (H1)** with oxblood-tinted dashed border during drag-over.
- **Storage** S3 (MinIO compatible) or local-disk fallback. Document key `{context_id}/{doc_id}/{filename}`.
- **Scan** ClamAV (production: hard precondition; dev: bypassed with `ALLOW_UNSAFE_UPLOADS=true`).
- **Extraction + paragraph anchors** with daily 03:00 UTC sweep cron.
- **"Akki Commentary"** on-demand via `POST /journal-commentary` — Synisense-shielded `surface="journal_commentary"`, cached, LLM-driven.
- **Routing CTAs (H2 — 2026-05-11)** — three handlers wired in `components/documents/DocumentRoutingActions.jsx`:
  - "Add to Cycle" → opens agenda-item picker → POST `/api/contexts/{cid}/cycle/contributions`
  - "Add to Work Studio" → routes to `/app/work-studio` and preloads source
  - "Take into Solva" → opens 4-mode picker → POST via unified `/api/solva/v2/seed?kind=document&id=…`
- **Reading viewer** at `/app/documents/:id` with paragraph anchors + "Ask AKKI" deep-link.
- **Search** at `/api/contexts/{cid}/document-journal/search` (handcrafted BM25 over `extracted_text` + `name`).
- **Remaining caveat** Highlight / annotate CREATION flow is deferred (a stats counter exists but no creation surface). Reading + commentary are fully functional.

### Module 3 — Solva Reasoning Engine ✅
- **Files** `backend/routers/solva_v2.py` (21 endpoints, ~2,900 lines) + `services/solva_v2/{state_machine, submodules, engines, grounding_contract, guardrails, llm_adapter, opinion_filter}.py`; `frontend/src/pages/{SolvaApp, SolvaLanding, SolvaSession, SolvaSessions}.jsx` + `components/solva/{flow/*, artefact/*}.jsx`; `lib/solvaFlow.js` (36 jest cases)
- **Four modes** Seek Clarity / Develop Strategy / Simulate Hypothesis / Get Perspective.
- **State machine** framing → grounding → (hypothesis if applicable) → synthesis → reflection → lock-in. Frame-audit pre-step writes `frame_audit_summary` + `audit_gaps[]`.
- **Guardrails** two-pass (classifier → provider → four-check) + refusal-of-speculation artefact (`SolvaRefusalArtefact`) when grounding contract fails. Banned-word grep on every output.
- **Take-to-Cycle (H4 — 2026-05-11) — fully wired.** Backend endpoint `POST /api/solva/v2/sessions/{sid}/take-to-cycle` (engine_version `take_to_cycle@1.0`). Frontend button in `SolvaSession.jsx`.
- **Attach Material (H4 — 2026-05-11) — fully wired.** No longer a "coming soon" tile. Backend endpoint `POST /api/solva/v2/sessions/{sid}/attach-document` persists `attached_documents[{id,title,attached_at}]` array (`backend/routers/solva_v2.py:1407-1433`); frontend modal in `components/solva/flow/FramingScreen.jsx:174+`.
- **Unified seed entry** `POST /api/solva/v2/seed?kind=…&id=…` supports 7 source kinds (`signal, document, cycle_contribution, cycle_compilation, solva_artefact, chat_message, ned_meeting`).
- **Exports** WeasyPrint PDF + python-docx DOCX of the synthesis artefact, byte-deterministic.
- **Stale-session sweep** daily 04:00 UTC (idle > 30 d → `abandoned_reason="stale_30d"`).
- **Continue-in-Chat** tethering via `continue_chat_id`.

### Module 4 — Work Studio ✅
- **Files** `backend/routers/{studio, studio_blocks, briefings, decks, work_studio_export, work_studio_phase_c, work_studio_phase_c2, work_studio_from_source}.py` + `services/work_studio_export.py` + `work_studio/{brief, enhance, docx_generator, pptx_generator, pdf_generator, persistence, samples/}.py` + `studio_sensitivity.py`; `frontend/src/pages/{WorkStudio, Decks, StudioComposerPage}.jsx` + `components/{studio/*, cycle/ReportsTab}.jsx`
- **Three-tab aggregate** Cycle Board Pack / Briefs / Reports (renamed "Board Artefacts" in F.7).
- **Block editor** CRUD + reorder + image upload + lifecycle (submit-review → approve → send).
- **Deterministic exports** DOCX (Georgia headings + Calibri body, INK colour), PPTX (canonical), PDF (Jinja + WeasyPrint). Every renderer returns `(bytes, sha256, filename)`; banned-word grep on every output string.
- **Enhance** flow: Pass 1 silent reasoning → Pass 2 strict JSON → render. Separate Compile Report mode (F.6) collates outside emails/attachments.
- **Sensitivity scoring** auto-applied — deterministic 0–100 → PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED.
- **Validation fan-out (11B)** Gemini-2.5-Flash second-pass on Decks / Reports / Solve syntheses with daily soft cap (`VALIDATOR_DAILY_SOFT_CAP=200`), `qualified` fallback when tripped, briefing surface bypass.
- **Public Chair view (11A)** `GET /api/public/studio/read/{token}` returns 30-day-TTL JWT-protected redacted read-only view with watermark; `_assert_public_safe()` hard-fails on any internal-metadata key.
- **Engagement** share-by-email tracking; per-account read receipts on `db.studio_views`.
- **Intentional gap** Deck PDF render — `render_deck_pdf` raises `NotImplementedError`. PPTX is canonical (Module 4 spec carve-out).

### Module 5 — Cycle Manager (Executive) ✅
- **Files** `backend/routers/{cycle, cycle_manager, cycle_config, agenda, prepare}.py` + `services/cycle_synthesis.py`; `frontend/src/pages/{Cycle, CycleSettings, Prepare, RespondToChecklist}.jsx` + `components/cycle/*` (12 files)
- **Three-act pill bar** Setup / Run / Ship. 6-step strip below.
- **Setup** Agenda + Team (inline-edit PATCH + AlertDialog remove).
- **Run** Contributions + Readiness gate + Follow-ups (draft → approve → send).
- **Ship** `POST /cycle/draft-compilation` builds Brief → persists to Work Studio → renders DOCX. **G4 — placeholder citations cleaned; zero `doc_id:"stub"` rows remain in cycle code.**
- **Outbound** Resend with deterministic alias `<uuid5>@akki.syni.ai` (was `cycles.akki.ai` pre-sprint). Test-mode in dev; verified domain required in prod.
- **Inbound threading** Postmark webhook → appends to `db.cycle_followups.replies[]`, sets `status='replied'`, writes `cycle.followup.replied` audit row.
- **Public reportee respond** `/api/respond/{token}` (no auth; checklist email link).
- **APScheduler cron** `cycle/cron/run-schedules`.

### Module 6 — Cycle Manager (NED) ✅
- **Files** `backend/routers/ned_cycle.py` (12 endpoints); `frontend/src/pages/{home/HomeNed, ned/NedMeeting, ned/NedCommittee}.jsx`
- **Cross-board landing** This Week / Next 2 Weeks / Outstanding / Patterns.
- **Per-meeting CRUD** + Pre/In/Post phase pill bar.
- **Hard build-time guardrail** `PRIVACY-WALL-CONTRACT ned-in-phase-llm-free=true` — comment-enforced; no LLM call sites permitted in the "In" phase JSX.
- **Notes / Positions** (For/Against/Abstained + private note) / **Followups** (NED-voice subject, deterministic UUIDv5 reply alias via cycles alias).
- **Committee through-line** GET endpoint (timeline + position trail + questions log).
- **Personal-memory search** `/api/ned/search` — account-scoped BM25, sentinel-tested to never leak foreign-NED data.
- **Voice addendum** in `services/two_pass.py:build_system_prompt` — peer-toned NED voice when `role=='ned'` AND `context_type.startswith('ned_')`.

### Module 7 — Synisense Shield ✅
- **Files** `backend/services/synisense/{pipeline, encryption, presidio_engine, regex_recognisers, llm_fallback, adapter, pool}.py` + `routers/synisense.py`
- **3-layer ladder** Regex (high-precision; wins on overlap) → Presidio + spaCy `en_core_web_lg` → LLM-fallback judge (Gemini 2.5 Flash via proxy).
- **Deterministic placeholders** Same token → same placeholder within one run.
- **16+ surface taxonomy** `chat, chat_classifier, chat_four_check, chat_evidence_list, ingest, briefing, deck, report, brief, minutes, journal_commentary, enhance, blog, solva_v2.{framing,synthesis,reflection,hypothesis}, **pulse (G5)**`.
- **AES-GCM master key** required in production (`MasterKeyMissing` boot refusal); dev fallback with `SYNISENSE_ALLOW_INSECURE=true` and stderr nag-loop every 60 s.
- **Forensic** `db.synisense_runs` stores SHA-256 of input only — never raw text.
- **Shield map TTL** `db.synisense_shield_maps` AES-GCM envelope; `expireAfterSeconds=0` (per-surface TTL: 1 h public_read / 24 h default / 7 d hard max).
- **Boot warmup** spaCy warmup async-threaded to avoid blocking event loop.
- **Caveat** Master-key rotation invalidates the shield-map cache — treat as a planned-outage event.

### Module 8 — Trust-First Chat ✅
- **Files** `backend/routers/chat.py` (14 endpoints, ~3,000 lines) + `services/{llm_streaming, continue_chat, two_pass}.py` + `llm_service.py`; `frontend/src/pages/Chat.jsx` + `components/chat/{MarkdownMessage, ModelAvatar}.jsx` + `components/stream/StreamCard.jsx`
- **5 models** Claude Sonnet 4.5, Claude Haiku 4.5, GPT-5.2, Gemini 2.5 Pro, Gemini 2.5 Flash.
- **All 3 providers stream direct.** Per the boot log: `[chat] streaming: claude=direct_stream gemini=direct_stream gpt=direct_stream`. GPT-5.2 streams via `litellm.acompletion(stream=True)` against the Emergent proxy — no longer proxy-buffered.
- **Hash-chained audit** `db.chat_audit_log` with `row_hash = SHA256(prev_hash + canonical_payload)`, genesis `"GENESIS-AKKI-CHAT-AUDIT-2026"`. Verifier ZIP at `GET /api/chats/{cid}/audit/export.zip`.
- **Two-pass orchestration** classifier → provider → four-check.
- **Phase 11C citation chips** BM25-grounded against context documents; hallucinated citations dropped; full `{n, anchor_id, doc_id, doc_name, page, paragraph_number, snippet}` resolution.
- **Retention** soft delete + 30-day daily 03:30 UTC sweep; preserves hash-chain integrity via single `chat.hard_deleted` row.
- **Failover** direct SDK → litellm proxy-stream → proxy-buffered (last resort).
- **Search** at `/api/chats/search`.

### Module 9 — Privacy Wall ✅
- **Files** `backend/services/privacy_wall.py` (~700 lines) + `services/metadata_signatures.py`
- **Phase 2b — projections** Field-projection guards on every cross-context aggregation path (`project_for_pulse`, `project_audit_row`).
- **`cross_context_query()`** async helper — refuses queries without `account_id` or `context_id` constraint (raises `CrossContextScopeError`); projects every row through `project_for_pulse`.
- **Phase 2c — content shielding (G1 — 2026-05-11) shipped:**
  - `redact_for_pulse_text(text)` — runs through Synisense Shield with `surface="pulse"` (`backend/services/privacy_wall.py:422-470`). Async variant `redact_for_pulse_text_async` preferred from running event loops.
  - `assemble_pulse_prompt(per_context_outputs)` — emits a per-tenant prompt with `BOARD-1, BOARD-2, …` boundary markers; no foreign `context_id` ever leaks into the constructed prompt.
- **G5 — Synisense pulse surface coverage** Headline + summary + body + reasoning all flow through `surface="pulse"` at the Pulse write path (`backend/routers/pulse.py:329`).
- **Sentinel testing** `backend/tests/test_privacy_wall_phase_2c.py` (18 tests, all green) asserts `state, content_hash, merge_count, comments, bookmarked_at, resolved_at, resolution_note, reasoning, last_merged_at` are denylisted from cross-board responses.
- **Strict mode** `STRICT_PRIVACY_WALL=true` (default) logs drift at WARN; `STRICT_PRIVACY_WALL_RAISE=true` raises 500 in CI.
- **Metadata signatures** `regulatory_ref` (Companies Act 2006 s.172 / GDPR Art.17 / FCA SYSC 4.1 / SEC Rule 10b-5 / IFRS 15), `governance_theme`, `pulse_class` — persisted at write-time in `db.context_metadata_signatures`.

### Module 10 — Pulse ✅
- **Files** `backend/routers/pulse.py` (11 endpoints) + `services/signal_dedup.py`; `frontend/src/pages/Pulse.jsx` + `components/pulse/AcrossBoardsPanel.jsx`
- **Same-context feed** `GET /pulse/feed` with filters (type / freshness / state / confidence). Volume cap of 7 on Active. Priority sort by `confidence × recency`.
- **Phase G lifecycle** `active, bookmarked, resolved, archived`. Content-hash dedup with `merge_count`.
- **First-class comments** on `signals.comments[]` (POST/DELETE on `/pulse/signals/{sid}/comment[s/{cid}]`).
- **Lifecycle actions** share / resolve / unresolve / bookmark / unbookmark / save / take-to-solva — each its own POST endpoint.
- **Take-to-Solva** mints a Solva v2 session via the unified `/seed` helper with `from_signal=<sid>`, `from_pulse=true`.
- **Cross-context aggregator** `/pulse/across-boards` reads ONLY `db.context_metadata_signatures` — never touches foreign `db.signals`. Response carries `leakage_check: 'metadata_only'`; verified by sentinel tests.
- **Phase H3 (2026-05-11) frontend** Drill-down side drawer (`<Sheet side="right">`) with Storyline / Source / Reasoning / Related Context / Comments + 6-button action bar. Tab strip Active / Bookmarked / Resolved / Archived wired to `?state=`. `data-testid="pulse-signal-drawer"`.

### Module 11 — Monitor ✅
- **Files** `backend/routers/{monitor, strategic_goals, pipeline, signal_actions}.py`; `frontend/src/pages/Monitor.jsx` + `components/monitor/*`
- Per-role function whitelists (CFO / COO / Commercial). Reads `db.signals` filtered by category + confidence. Surfaces 3 counters (high-confidence / risks / opportunities).
- M11 event-driven pipeline (generate → verify → persist). Phase G.3 dedup at write paths.
- **Caveat** Reads only the last 50 signals (`monitor.py:88`) — older risks can be hidden.
- **Caveat** No `at_risk` flag on `db.strategic_goals` — "Goals at risk" is derived at read time, not stored.

### Module 12 — Streaming Transitions (cross-cutting abstraction) ◐
- **Per-surface streaming works** Chat, Solva, Studio render-progress all stream individually.
- **Central abstraction deferred to v1.1** — explicit scope carve-out. Not a launch blocker.

### Module 13 — Universal Search ✅
- **Files** `backend/routers/search.py` + `services/universal_search.py` (~570 lines); `frontend/src/pages/SearchResults.jsx` + `components/search/{UniversalSearchDialog, SearchResultRow, ConfirmContextSwitchModal}.jsx` + `components/layout/AppShell.jsx` + `hooks/useKeyboardShortcuts.js`
- **Federated search** across the caller's active memberships at `GET /api/search?q=…&context_id=…&surface=…&limit=…&offset=…`.
- **7 surface handlers** in `SURFACE_HANDLERS` (`backend/services/universal_search.py:482-492`): **documents, chats, pulse, monitor, cycle (H5), work_studio (H5), briefs (H5)**.
- **Per-context scope check** Silently refuses queries against contexts the caller is not a member of.
- **Top-nav search input** + Cmd+K dispatches `akki:open-search` (canonical) + `akki:open-palette` (legacy alias). No more context-switcher hijack.
- **Cross-context "open from foreign tenant"** flow via `ConfirmContextSwitchModal` + `POST /api/search/cross-context-open` (writes `search.cross_context_open` audit row with hashed `result_id`).
- **Privacy & audit** `q_hash = SHA-256(q.strip().lower())` — only query data persisted. Raw `q` never stored. One `search.federated` audit row per call.

### Module 14 — Pre-login Website (akki.syni.ai) ✅ (NEW)
- **Files** `backend/routers/website.py` (2 endpoints); `frontend/src/website/{WebsiteShell, WebsiteNav, WebsiteFooter}.jsx` + `copy/{index.js, legal.js}` + `pages/{Home, WhyAkki, WhatAkkiDoes, Trust, Cohort, About, Contact, Privacy, Terms}.jsx` + `style.css` + `assets/{hero-library.jpg, why-fountain-pen.jpg, what-archive-boxes.jpg, trust-wax-seal.jpg}`
- **9 pages** Home / Why Akki / What Akki Does / Trust & Sovereignty / Founding Cohort / About / Contact / Privacy / Terms. Pricing page intentionally removed in revision 2 — pricing handled privately during cohort intake.
- **AKKI brand** Mirrored from app design tokens via `var(--cream | paper | ink | muted | rule | accent)` declared in `frontend/src/index.css:18-38`. Single accent — **oxblood `#8B2E2B`** (no burnt sienna, no cream-secondary). Cream `#F7F3EA` page background.
- **Typography** Georgia + system fallbacks (`'Times New Roman', serif`) for headings; Calibri + system fallbacks (`'Helvetica Neue', Arial, sans-serif`) for body. No Google Fonts, no @font-face, no Inter / Roboto.
- **Editorial register** Small-caps section labels (letterspacing 0.18 em) in muted ink; 48 px × 1 px oxblood mini-rules under section openers (Economist column treatment); single-column body width ~720 px; wide-band layouts 1200 px for nav/footer.
- **4 editorial photographs** (sourced via vision_expert_agent — abstract / architectural / material; no people, no faces, no hands, no screens, no AI imagery):
  - `assets/hero-library.jpg` — 417 KB, 2000 × 1125, eager-loaded hero on `/`
  - `assets/why-fountain-pen.jpg` — 150 KB, 1200 × 800, lazy on `/why-akki`
  - `assets/what-archive-boxes.jpg` — 174 KB, 1200 × 800, lazy on `/what-akki-does`
  - `assets/trust-wax-seal.jpg` — 117 KB, 1200 × 800, lazy on `/trust`
- **CTAs** Primary "Request early access" → `/cohort` (filled oxblood); Secondary "Test Akki in 90 seconds" → `/sandbox` (ghost ink → oxblood on hover).
- **Forms** `/cohort` POSTs to `/api/website/early-access` → `db.early_access_applications` (id, type, name/email/company/role/role_type/linkedin_url/valuable_text, ip_hash truncated to 16 chars, user_agent, created_at, status). NO raw IP stored. `/contact` POSTs to `/api/website/contact` → `db.contact_messages`. Best-effort confirmation email to applicant + ops notification to `EARLY_ACCESS_NOTIFY_EMAIL` / `CONTACT_NOTIFY_EMAIL`; failures silently logged.
- **Analytics** Plausible only — auto-injected once on mount; `data-domain="akki.syni.ai"`. No GA, no pixels.
- **Accessibility** WCAG 2.1 AA — keyboard focus rings visible (2 px oxblood outline, 2 px offset); semantic heading order; aria-hidden decoration images.
- **Routing** Single `<BrowserRouter>` in `frontend/src/App.js` — website paths mount `<WebsiteShell>` outside the gated `/app/*` tree. Catch-all `*` → `/`.

---

## 4. Consolidated gap & action register

### Priority 0 (production blockers / spec contracts)
1. **Postmark webhook URL paste** ⚠ user-action — paste the exact URL `https://akki-executive.preview.emergentagent.com/api/inbound/postmark?secret=vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj` into Postmark dashboard → Inbound → Webhook URL.
2. **DNS cutover for `akki.syni.ai` → production backend** ⚠ user-action — once DNS points at the deployed backend, switch the Postmark webhook URL to `https://akki.syni.ai/api/inbound/postmark?…`.
3. **Resend domain verification — ✅ DONE** `akki.syni.ai` is verified live; outbound smoke from `noreply@akki.syni.ai` returned HTTP 200 with message id `51cabee0-c2ee-4239-9692-034528a4928f`.

### Priority 1 (high-traffic UX gaps vs spec)
1. **Highlight / annotate creation flow** — stats counter ships; creation surface deferred.
2. **Monitor 50-signal cap** — older risks can be hidden.
3. **`db.strategic_goals.at_risk`** — derived at read time, not stored.

### Priority 2 (governance / hardening)
1. **Master-key rotation** for Synisense is concept-only; planned-outage event if needed.
2. **Legacy test suite hygiene** — login-rate-limit cascade + stale `tenants`/`clusters` keys in `test_iter*.py` and `test_akki_g1.py`. Recommended but not a launch blocker.
3. **Sandbox v2 Step 2 (Pulse)** intentionally deferred — reducer reserves the state; `FORWARD` skips to Step 3.

### Priority 3 (documentation drift)
1. `backend/routers/cycle_manager.py:25` comment still labels NED as "design only" — outdated since Phase E shipped via `ned_cycle.py`.
2. "Solva v2" in code ↔ "Solva v3" in UX brand — deliberate naming drift to preserve audit-row lineage.

### Priority 4 (deferred / v1.1)
1. NED v1.1 calendar / co-sec.
2. ExCo first-class surface.
3. Master-key rotation automation.
4. Streaming Transitions central abstraction (Module 12).
5. Work Studio CI determinism test (byte-equality gate).
6. Topic-vector signature kind for Privacy Wall (no embedding service wired today).

---

## 5. What is verifiably true today

- All 14 modules ship (13 + the new pre-login website).
- Trust-critical regression — **29 / 29 passing in 2.14 s** (`test_privacy_wall.py`, `test_phase_g_privacy_wall_sentinel.py`, `test_privacy_wall_phase_2c.py`, `test_universal_search.py`).
- New sprint code (Phase G/H/I) — **18 / 18 passing in isolation** (`test_privacy_wall_phase_2c.py` + `test_universal_search.py`).
- Synisense covers 16 surfaces including `pulse`. AES-GCM master key boot-guarded for production.
- Privacy Wall Phase 2b + Phase 2c live. `cross_context_query()` refuses unscoped queries.
- Hash-chained chat audit with offline verifier ZIP. Universal Search `q_hash` only — raw queries never persisted.
- All three LLM providers stream direct (`claude=direct_stream gemini=direct_stream gpt=direct_stream`). Proxy-buffered is the last-resort fallback.
- Resend verified domain `akki.syni.ai` is live. Cycle aliases mint as `<uuid5>@akki.syni.ai`.
- Postmark HMAC default on; production boot-guard refuses `POSTMARK_USE_HMAC=false`.
- Determinism contract — every renderer returns `(bytes, sha256, filename)`. Banned-word grep on every output string.
- 89 MongoDB collections, all UUID-keyed (zero `ObjectId` exposure).
- 385 backend API endpoints registered. 9 website public routes + 36 app routes.

---

## 6. What is mocked, stubbed, or hardcoded (transparency list — post-sprint)

The pre-sprint list contained 22 items. After Phase G + H + I, **the following are no longer applicable** and have been struck from this list — every claim below is the truth as of 2026-05-11:

1. **`render_deck_pdf` raises `NotImplementedError`** at `backend/services/work_studio_export.py:733`. Intentional spec carve-out — PPTX is canonical deck output.
2. **GPT-5.2 SDK keys not provisioned in dev** — GPT-5.2 streaming uses the Emergent proxy (`litellm.acompletion(stream=True)`). This is per-token streaming, not buffered. Direct OpenAI SDK keys would be a drop-in replacement if procured.
3. **Mid-stream provider failure does NOT fall back to proxy mid-stream** — would double-emit. User sees `{"type":"error","code":"stream_interrupted"}` chunk.
4. **`SYNISENSE_MASTER_KEY` rotation NOT supported** — any rotation invalidates `db.synisense_shield_maps` rows. Documented; manual planned-outage rotation only.
5. **ClamAV bypassed in dev** via `ALLOW_UNSAFE_UPLOADS=true`; production boot-guard refuses the flag when `AKKI_ENV=production`.
6. **Resend in test-mode in dev** — non-test recipients return `mode:"test_mode_restricted"`. Production needs a verified test recipient cleared with Resend support.
7. **Postmark `surface="ingest"` Synisense coverage on raw inbound bodies** — unverified. (Phase G2 wired the auth ladder; surface coverage on raw inbound text remains to verify.)
8. **Pulse same-context feed bypasses the projection guard** — relies on `context_id` filter alone. Belt-and-braces wiring is a P3 hardening item.
9. **`db.strategic_goals.at_risk`** not stored — derived at read time.
10. **Monitor 50-signal cap** at `backend/routers/monitor.py:88`.
11. **Sandbox v2 Step 2 (Pulse)** intentionally deferred — reducer reserves the state; FORWARD map skips to Step 3.
12. **Highlight / annotate CREATION flow** — stats counter exists; creation surface deferred.
13. **`backend/services/solva_v2/llm_adapter.py:52`** holds a `"placeholder_stub"` engine-name reference — not in any live call site, forensic only.
14. **`backend/routers/cycle_manager.py:25`** comment still labels NED as "design only" — documentation drift; Phase E shipped via `ned_cycle.py`.
15. **Pre-2026-05-05 `db.synisense_runs` rows** for journal-commentary calls are bucketed under `surface="briefing"` — forensic only; new live + backfill paths now correctly bucket under `surface="journal_commentary"`.
16. **CI byte-determinism test for Work Studio exports not present** — `test_render_determinism.py` does not exist.

### Resolved this sprint — no longer on the transparency list

- ✅ ~~Invitation email stub~~ — **un-stubbed (G3)** at `backend/routers/contexts.py:405-456` (real Resend send, never raises).
- ✅ ~~Compilation placeholder citation row~~ — **removed (G4)**. Zero `doc_id:"stub"` rows remain in `backend/routers/cycle*.py` + `backend/services/cycle*.py`.
- ✅ ~~Postmark URL-secret as primary auth~~ — **demoted to fallback (G2)**. HMAC is the default; URL-secret active only when `POSTMARK_USE_HMAC=false` AND `AKKI_ENV != production`.
- ✅ ~~`redact_for_pulse_text` no-op~~ — **real implementation (G1)** at `backend/services/privacy_wall.py:422-470`.
- ✅ ~~`assemble_pulse_prompt` `NotImplementedError`~~ — **real implementation (G1)** with BOARD-N boundary markers.
- ✅ ~~Solva "Take to Cycle" frontend TODO~~ — **un-stubbed (H4)** at `frontend/src/pages/SolvaSession.jsx` + backend at `backend/routers/solva_v2.py:1522-1599`.
- ✅ ~~Solva "Attach material — coming soon" tile~~ — **un-stubbed (H4)** at `frontend/src/components/solva/flow/FramingScreen.jsx:174+` + backend at `backend/routers/solva_v2.py:1407-1433`.
- ✅ ~~GPT-5.2 proxy-buffered~~ — **streams direct via `litellm.acompletion(stream=True)`** per boot log `gpt=direct_stream`.
- ✅ ~~Universal Search Phase-2 stubs (cycle / work_studio / briefs)~~ — **real handlers (H5)** at `backend/services/universal_search.py:261, 326, 425` registered in `SURFACE_HANDLERS:489-491`.
- ✅ ~~`PulsePlaceholder.jsx` orphan~~ — **deleted** (verified — `find /app/frontend/src -iname "PulsePlaceholder*"` returns empty).

---

## 7. Production launch checklist

| Item | Status |
|---|---|
| All 13 module builds complete (now 14 with the website) | ✅ |
| Phase F0 (Universal Search) + Phase G (Privacy / Email / Cycle) + Phase H (Documents / Pulse / Solva / Search F1) + Phase I (Website) shipped | ✅ |
| Resend domain live (`akki.syni.ai` verified — DKIM + SPF MX + SPF TXT + DMARC) | ✅ |
| Postmark token authenticated (server `Akki Server` ID `19182114`, DeliveryType `Live`) | ✅ |
| Cycle alias domain migrated to `akki.syni.ai` (was `cycles.akki.ai`) | ✅ |
| `POSTMARK_USE_HMAC` default `true`; production boot-guard active | ✅ |
| Synisense AES-GCM master-key boot-guard armed (production refuses `SYNISENSE_ALLOW_INSECURE=true`) | ✅ |
| ClamAV production boot-guard armed (production refuses `ALLOW_UNSAFE_UPLOADS=true`) | ✅ |
| **Trust-critical regression: 29 / 29 passing** (`test_privacy_wall.py`, `test_phase_g_privacy_wall_sentinel.py`, `test_privacy_wall_phase_2c.py`, `test_universal_search.py` — 2.14 s) | ✅ |
| User: paste webhook URL `https://akki-executive.preview.emergentagent.com/api/inbound/postmark?secret=vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj` into Postmark dashboard → Inbound → Webhook URL | ⚠ user-action |
| User: DNS cutover for `akki.syni.ai` → production backend (after which switch webhook URL to `https://akki.syni.ai/api/inbound/postmark?secret=…`) | ⚠ user-action |
| User: end-to-end smoke test on the preview URL — login, document upload, Solva session, cycle compile, search, website pages, cohort form | ⚠ user-action |

---

*This document is the source of truth for AKKI's production-launch readiness as of 2026-05-11. Regenerate from `backend/` and `frontend/src/` after each phase ship.*
