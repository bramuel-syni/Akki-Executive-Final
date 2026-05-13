# AKKI — Product Features & Functionality Review

**Document date**: 2026-05-13
**Repository**: `Akki-Executive 2` (live preview: `https://akki-executive.preview.emergentagent.com`)
**Scope**: end-to-end product feature audit grounded in the actual code on disk. Not aspirational. Every claim cites a file path, route, or collection name.
**Audience**: this section's first page (§0) is stakeholder-readable. Everything from §1 onwards is engineering / PO reference material.

---

## 0. Executive Summary

### What AKKI is
AKKI is an **executive cognitive workbench** for board directors, NEDs, C-suite operators, and senior advisors. It compresses the four most expensive recurring tasks in board work — *preparing*, *reviewing*, *deciding*, and *following up* — into a single workspace that reads documents the way a sharp colleague would and surfaces decisions the way an editor would phrase them. The system is built around the principle that **the user's data never trains anyone else's model**, and that every AI-surfaced claim must be traceable to a citation.

### Personas
- **Executive** (CEO / CFO / COO / CHRO / Founder running their own board). Owns the workspace. Uploads documents, runs cycles, ships board packs.
- **NED** (non-executive director or independent chair). Sponsored into a workspace by an executive. Reads, comments, scores, approves.
- **Reportee** (team contributor — e.g. Finance lead, Programme lead). Invited per-cycle to contribute structured material; they don't see other contributors' work.
- **Admin** (owner of the parent account). Manages billing, users, MFA, retention.

### Current maturity (as of 2026-05-13)
- **Backend**: 442 → **453 Pytest tests passing** (Chunks 1–6 of the May QA-fix sprint). 565 quarantined (pre-existing E2E pollution). 0 failed.
- **Frontend**: editorial cream/parchment v7 design system; `render-smoke` Playwright suite green across 8 authenticated routes + 2 upload paths + 4 chunk-specific behaviours.
- **Sprint position**: 6 of 12 chunks shipped from the 13 May QA report (46 findings). Chunk 6.5 (left-rail shell refactor) shipped this session. 17 product-owner clarifications outstanding.
- **Production health**: deploys cleanly to `akki-executive` after the spaCy model lazy-load fix (March 2026 deployment unblock).
- **3rd-party state**: OpenAI / Anthropic / Gemini via the Emergent Universal Key; ClamAV scanning live (503 on outage — no stub); Stripe wired but billing screens MOCKED in dev.

### Value proposition (one line per audience)
- **Executive**: "Compose, approve, and ship a board pack in 60 minutes instead of 6 hours, with every signal cited and your IP staying on your side of the wall."
- **NED**: "Walk into the room having read every document twice — without actually having read any of them twice."
- **Investor / Board Chair**: "Cross-portfolio adjacency: see when the same concern is surfacing across three of the boards you sit on."

---

## 1. Architecture Snapshot

- **Stack**: FARM (FastAPI + React 19 SPA + MongoDB Motor async driver). Internal supervisor manages the two services. Kubernetes ingress proxies `/api` to backend on `:8001`, everything else to React on `:3000`.
- **AI providers**: OpenAI / Anthropic / Gemini via Emergent Universal Key. No direct SDK installs. `emergentintegrations` library is the only client.
- **Background processing**: `services/job_queue.py` + `routers/async_jobs.py` (poll endpoint `GET /api/jobs/{job_id}`). Long-running LLM work (briefing generation, signal generation, draft compilation) returns `202 Accepted` with a `job_id`; the frontend polls via `lib/pollJob.js` to avoid 524 gateway timeouts.
- **Streaming UX**: SSE for chat (`POST /api/chats/{id}/messages/stream`), enhance (`POST /api/work-studio/enhance/{kind}`), Solva turn (`POST /api/solva/v2/sessions/{sid}/turn`). Driven by `hooks/useStreamingPhases.js` on the frontend. Errors must be structured JSON `error` events — raw `repr(exc)` leaks logged in §4 as soft-debt.
- **API client enforcement**: `lib/api.js` is the only HTTP client. **Raw `fetch()` is banned by ESLint** (Patch 24 — `no-restricted-globals`). Every backend call goes through `api.get/post/patch/delete` with bearer + active-context interceptors.
- **MongoDB discipline**: never return `_id` in API responses. Every Pydantic response model strips ObjectId. Datetime stored as ISO strings (UTC).
- **Auth**: JWT bearer issued by `routers/auth.py`. 30-day expiry. MFA optional but recommended for context owners. Password hash via `bcrypt` (handled in `core.hash_password`).
- **Privacy wall**: `services/privacy_wall.py` (Synisense Shield) PII-redacts before LLM exposure for chats, briefs, decks, reports, and signals.

---

## 2. Cross-cutting Capabilities

### 2.1 Multi-workspace / context isolation
- Every document, brief, cycle, signal, objective, and Solva session is scoped by a single `context_id` (FK into `db.contexts`).
- An account can be a member of N contexts via `db.memberships`. Switching context updates the JWT context header but does NOT issue a new token.
- Listing endpoints filter by `context_id` extracted from `Depends(require_context_membership())` (`routers/contexts.py`). Cross-context leakage is treated as a P0 (see Chunk 1 fix below).
- Sponsored contexts (`isSponsoredContext` in `lib/sponsorship.js`) get a "Sponsored" badge in the LeftRail workspace switcher.

### 2.2 Auth & roles
- `db.accounts` carries `declared_role ∈ {executive, ned, reportee, dual}`. `dual` lets a user toggle between an executive lens and a NED lens.
- Per-context role is `db.memberships.role ∈ {executive, ned, reportee, member}` with optional `sub_role ∈ {admin, …}`.
- Role-mismatch banner surfaces in `AppShell.jsx` when `activeRole` (account-level) ≠ `activeContext.my_role` (context-level).
- `services/rbac.py` enforces per-endpoint role rules; gating decorators in `routers/cycle.py`, `routers/cycle_assignments.py`.

### 2.3 Privacy boundaries
- **Synisense Shield**: PII redaction before LLM submission (`services/privacy_wall.py`). Surfaces include chat, brief enhancement, Solva turn, signal generation. Per-artefact Synisense badge surfaces the redaction summary (`components/work_studio/PerArtefactSynisenseBadge`).
- **Cross-workspace leakage protection**: queries always include `context_id`. Patch 24 ESLint rule bans raw `fetch()` so context headers can't be bypassed.
- **Trust footer / Trust panel**: every page footer shows "Synisense-shielded · Your data never leaves this account · Every signal cites its source" with a link to the Trust Centre.

### 2.4 Background job polling
- `services/job_queue.py`: thin wrapper around `asyncio.create_task()` that writes a row to `db.jobs` with `{id, status, result, error, created_at, updated_at}`.
- `routers/async_jobs.py` exposes `GET /api/jobs/{job_id}` — returns `{status: queued|running|completed|failed, result, error}`.
- `lib/pollJob.js` on the frontend wraps the polling (1 s interval, 5-minute timeout).
- Currently used by: `POST /briefings` (202), `POST /signals/generate` (202), `POST /cycle/draft-compilation` (202). See Chunk 2 close-out for full migration log.

### 2.5 SSE streaming
- Chat token-stream: `POST /api/chats/{chat_id}/messages/stream` → `text/event-stream` with `phase` + `delta` + `done` events. Frontend: `hooks/useStreamingPhases.js` + `pages/Chat.jsx`.
- Enhance stream: `POST /api/work-studio/enhance/{kind}` → SSE with `progress` + `result` + `error` events. Frontend: `components/work_studio/EnhanceDrawer.jsx`.
- Solva turn stream: `POST /api/solva/v2/sessions/{sid}/turn` → SSE with frame-by-frame outputs.

### 2.6 API client enforcement
- `lib/api.js` exports `api` (axios instance) + `apiErrorMessage` + `apiErrorCode` (added in Chunk 6 for nested-dict `{code, message}` errors).
- ESLint rule (Patch 24): `no-restricted-globals: ['fetch']` — any raw `fetch()` call fails CI.
- Bearer + active-context interceptors set on every request automatically.

---

## 3. Modules

### 3.1 Home / Dashboard

**Purpose & user value**
A morning-coffee dashboard. Tells the user: *(a) what's changed since they were last here, (b) what's on the calendar today, (c) which artefacts need their attention.* Two surfaces stitched together: Home 1 (insights / news) and Home 2 (what's new). Implemented as a single page (`pages/AppHome.jsx`) toggling between layouts.

**Primary user flows**
1. **Sign in → land on /app**. Home renders 6 sections: greeting, news strip (MOCKED), upcoming calendar, what's new, daily review queue, quick-actions row.
2. **What's-new card → click** → routes to the originating surface (e.g. a new comment on a brief routes to the brief).
3. **Daily review card → click** → routes to `/app/daily-review`.
4. **Quick action → click** → opens the Cycle Manager quick-action dialog (4 templates: Main Board, Answer Questions, Project Proposal, Fund Raising).

**Key screens / components**
- `pages/AppHome.jsx`
- `components/home/Home1.jsx`, `Home2.jsx`, `WhatsNew.jsx`, `DailyReviewCard.jsx`, `CalendarPeek.jsx`, `QuickActionsRow.jsx`
- `data/mock_news.json` (MOCKED — 5 sample headlines)

**Backend endpoints**
- `GET /api/contexts/{cid}/home/insights` — Home 1 payload (calendar peek, KPIs)
- `GET /api/contexts/{cid}/home/whats-new` — Home 2 payload (events since `last_seen_at`)
- `GET /api/me/recent-views` — last 5 visited surfaces (used by the LeftRail Recent section too)
- `POST /api/me/recent-views` — write a recent-view ping when a surface mounts

**Data model**
- `db.user_recent_views`: `{ id, account_id, surface_path, label, created_at }`
- `db.home_events`: events surfaced by the what's-new aggregator

**Integrations**
- **News strip: MOCKED** — `frontend/src/data/mock_news.json`. The `data-testid="home1-news-mock-badge"` carries the visible "Curated · sample feed" label.

**Recent fixes in this sprint**
- Chunk 6.5 — LeftRail surfaces the recent-views list (limit raised from 3 → 5).

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| MS-R01 | Bell icon routes to Brief Review Centre; users expected a notifications drawer | Medium | Pending (PO clarification #1) |

**Pending PO clarifications**: #1 — Bell icon function.

**Acceptance criteria for "working" today**
- Home 1 renders all 6 sections without console errors.
- News strip clearly marked MOCKED.
- What's-new card click routes correctly to source surfaces.
- Daily review badge count matches `/me/daily-review` count.

---

### 3.2 Cycle Manager

**Purpose & user value**
The board-cycle command surface. An executive sets an agenda, assigns contributors per item, watches readiness signals as contributors fill in their pieces, and ships a compiled board pack to the boardroom. **Agent Cycle** is the deterministic readiness engine — not an LLM agent — that nudges contributors and tracks completeness.

**Primary user flows**
1. **Quick action → Main Board cycle**: 4-template wizard creates a fresh cycle with a standard agenda + the user's ExCo team (from `db.exco_teams`).
2. **Cycle list → pick a cycle** → 2-layer nav (Patch CM v2): Layer 1 breadcrumb (Cycle / Agenda / Team / Compilation), Layer 2 tab body.
3. **Agenda tab**: add agenda items; each item carries owner + due-date + readiness state.
4. **Team tab**: add reportees from the team catalogue; assign each to one or more agenda items.
5. **Contributions tab**: contributors POST their material (text + supporting docs).
6. **Readiness rail** (sticky right at ≥1100px): aggregates readiness across items into Ready / At-risk / Outstanding buckets.
7. **Compilation tab** → click *"Compile board pack"* → POSTS `/cycle/draft-compilation` → 202 returns `job_id` → frontend polls `/jobs/{id}` → toast on completion with redirect to composer.
8. **Approve → Ship**: review the compiled artefact, approve, ship. Audit row written.

**Key screens / components**
- `pages/Cycle.jsx` (single-cycle detail) + `CycleList.jsx` route (currently inside `Cycle.jsx`)
- `components/cycle/AgendaTab.jsx`, `TeamTab.jsx`, `ContributionsTab.jsx`, `ReadinessRail.jsx`, `CompilationTab.jsx`
- `components/cycle/Scoreboard.jsx`, `FollowUpDraft.jsx`
- `pages/RespondToChecklist.jsx` (contributor-side response form)

**Backend endpoints** (highlights)
- `GET/POST /contexts/{cid}/cycle/agenda` — agenda items
- `GET/POST /contexts/{cid}/cycle/team` + `DELETE /cycle/team/{id}` + `PATCH /cycle/team/{id}` — team membership
- `GET/POST /contexts/{cid}/cycle/contributions` — contributor submissions
- `POST /cycle/contributions/{id}/score` — reviewer score with reasoning
- `GET /cycle/readiness` — aggregated readiness state (deterministic)
- `POST /cycle/follow-ups/draft` + `/approve` + `/send` — Agent Cycle follow-up draft pipeline
- `POST /cycle/draft-compilation` (**202** — async via `job_queue.py`)
- `POST /api/contexts/{cid}/reports/compose` — multi-tier review-chain Report flow (separate from Work Studio reports)

**Data model**
- `db.cycles`: `{ id, context_id, name, status: draft|active|completed, template, owner_id, created_at, updated_at }`
- `db.cycle_agenda_items`: `{ id, cycle_id, title, owner_id, due_date, readiness, position }`
- `db.cycle_team`: `{ id, cycle_id, account_id, role, assignments: [agenda_item_id] }`
- `db.cycle_contributions`: `{ id, cycle_id, agenda_item_id, contributor_id, body, attachments, status, score }`
- `db.cycle_followups`: `{ id, cycle_id, draft, approved_at, sent_at }`
- `db.jobs`: async-job records for compilation (`status, result.compilation_id`)

**Integrations**
- LLM via Emergent Universal Key — used in `cycle_synthesis.py` for follow-up drafts.
- Async job queue (`services/job_queue.py`) for compilation.

**Recent fixes in this sprint**
- Chunk 2 (CM-R04): `POST /cycle/draft-compilation` migrated from synchronous to 202 + job polling.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| CM-R04 | Draft-compilation timed out via gateway (524) | High | **Fixed in Chunk 2** |
| — | Scoreboard CTA after poor score is unclear | Low | Pending (PO clarification #15) |

**Pending PO clarifications**: #15 — Scoreboard CTA after poor score.

**Acceptance criteria for "working" today**
- Create → activate → contribute → compile → approve → ship round-trip completes without manual intervention.
- Async compilation returns within 5 minutes; toast on completion.
- Readiness rail updates within 2 s of a contribution save.

---

### 3.3 Work Studio (Briefs, Decks, Reports, Compilation Wizard)

**Purpose & user value**
The artefact editor. Where a user *composes* and *enhances* the things they ship: briefs, decks, reports, plus cycle-aggregate artefacts (board pack, minutes, committee pack). One block composer for everything (`StudioComposerPage.jsx`).

**Primary user flows**
1. **Tabs across kinds**: Briefing · Deck · Report · Board Pack · Minutes · Committee Pack. (`pages/WorkStudio.jsx`)
2. **Create-Summary-Deck / Create-Report** (Chunk 5 — fixed). Three paths per kind: Blank · From Existing Brief · From External Document. Single endpoint `POST /work-studio/artefacts`.
3. **Brief drawer click** (Chunk 6 — fixed): row → drawer with "Open in composer" CTA → routes to `/app/studio/composer/{kind}/{id}`.
4. **Block composer** (`components/studio/BlockComposer.jsx`): heading / paragraph / table / image blocks. Per-block Enhance via SSE. Per-block citation chips. Review → Approve gate. (PO clarification #4)
5. **Enhance flow** (`POST /work-studio/enhance/{kind}`, SSE): user instructs ("rewrite for an investor audience"), worker runs two-pass schema, returns reshaped artefact. Adjust-and-Retry preserves selected source documents (Chunk 3 fix).
6. **Compilation Wizard** (Chunk 4 — fixed): from Work Studio's "Compile with Agent" CTAs → 3-step modal (Type → Sources → Compile) → emits the kind-aware aggregate.
7. **Export**: `POST /work_studio/exports` → DOCX / PPTX / PDF rendered server-side, downloadable via `GET /work_studio/exports/{id}/download`.

**Key screens / components**
- `pages/WorkStudio.jsx`, `pages/StudioComposerPage.jsx`
- `components/work_studio/CreateArtefactModal.jsx` (Chunk 5)
- `components/work_studio/CompilationWizard.jsx` (Chunk 4)
- `components/work_studio/EnhanceDrawer.jsx`
- `components/work_studio/PerArtefactSynisenseBadge.jsx`
- `components/studio/BlockComposer.jsx`, `SourceStep.jsx`, `ExportModal.jsx`

**Backend endpoints** (highlights)
- `GET /contexts/{cid}/briefings/aggregates` + `/aggregates/{aggregate_id}` (Chunk 6 — six-kind dispatch)
- `POST /contexts/{cid}/briefings` (202 — async via job_queue) — Patch C.1 brief generation
- `POST /contexts/{cid}/work-studio/artefacts` (Chunk 5) — create draft deck/report
- `POST /contexts/{cid}/work-studio/from-source` — Solva session → artefact bridge
- `POST /work-studio/enhance/{kind}` (SSE) — block-level rewrite
- `POST /work_studio/exports` + `GET /work_studio/exports/{id}` + `/download` — DOCX/PPTX/PDF render
- `POST /api/contexts/{cid}/decks/outline` + `/decks/{outline_id}/generate` — LLM deck generation
- `GET /api/contexts/{cid}/studio/blocks/{kind}/{id}` + `PUT /…/blocks` — block CRUD

**Data model**
- `db.work_studio_briefs`: parent brief row `{ id, context_id, account_id, source_type, title, subtitle, active_revision_id, revision_count }`
- `db.work_studio_brief_revisions`: revision history `{ id, brief_id, snapshot, diff, claims_changed, validation, llm_audit }`
- `db.decks`: `{ id, context_id, title, body, description, source, brief_id, source_document_id, status, slides[] }`
- `db.reports`: `{ id, context_id, title, body, description, source, brief_id, source_document_id, status, chain[] }`
- `db.boardpacks`: cycle-aggregate output `{ id, cycle_id, sections[], …}`
- `db.studio_blocks`: one row per `(artefact_kind, artefact_id)` carrying the seeded block array

**Integrations**
- LLM via Emergent Universal Key for brief synthesis (`build_brief_from_solva`), deck outline, enhance two-pass.
- DOCX rendering via `python-docx` (`work_studio/docx_generator.py`).
- PPTX rendering via `python-pptx` (`work_studio/pptx_generator.py`).
- PDF rendering via `reportlab` (`work_studio/pdf_generator.py`).

**Recent fixes in this sprint**
- Chunk 1 (WS-R16): Solva V2 sessions list now `context_id`-scoped — closed P0 cross-account leak.
- Chunk 3 (WS-R06/R12/R15): worker_crash fixed across Minutes/Report/Deck enhance flows; Adjust-and-Retry preserves docs.
- Chunk 4 (WS-R02/R04/R05/R07/R08): Compilation Wizard `initialType` mapping + Step-1 preselect drift fixed.
- Chunk 5 (WS-R09/R10/R11/R13/R14): Create-Summary-Deck + Create-Report now functional across all 3 paths.
- Chunk 6 (WS-R01/R17/R18/R19): aggregate detail dispatch for non-cycle kinds; drawer "Open in composer" CTA; nested-dict toast; long-title DOCX render.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| WS-R01 | Drawer CTA with undefined target | High | **Fixed in Chunk 6** |
| WS-R02 | Wizard landed on Step 2 (preselect-truthy bug) | High | **Fixed in Chunk 4** |
| WS-R03 | "Board Pack appears on the rail" — confusing copy | Low | Pending (PO clarification #3 — rename "rail" → "Compilation panel") |
| WS-R04 | Step 1's radio pre-selected Report | High | **Fixed in Chunk 4** |
| WS-R05 | Step 2 fetched wrong kind sources | High | **Fixed in Chunk 4** |
| WS-R06 | Minutes Enhance `KeyError: 'minutes'` + retry loses doc | High | **Fixed in Chunk 3** |
| WS-R07 | Wizard Step 2 pre-filtered wrong artefact | High | **Fixed in Chunk 4** |
| WS-R08 | Wizard Step 2 truncated kind list | High | **Fixed in Chunk 4** |
| WS-R09 | Brief picker dropdown empty even with briefs | High | **Fixed in Chunk 5** |
| WS-R10 | Deck Blank + External Document paths broken | Critical | **Fixed in Chunk 5** |
| WS-R11 | Create Summary Deck non-functional overall | Critical | **Fixed in Chunk 5** |
| WS-R12 | Report Enhance worker_crash | High | **Fixed in Chunk 3** |
| WS-R13 | Report brief picker empty | High | **Fixed in Chunk 5** |
| WS-R14 | Create Report Blank + External Document broken | Critical | **Fixed in Chunk 5** |
| WS-R15 | Deck Enhance worker_crash | High | **Fixed in Chunk 3** |
| WS-R16 | Solva session cross-account leakage (P0) | Critical | **Fixed in Chunk 1** |
| WS-R17 | "Bad aggregate id" on brief click | High | **Fixed in Chunk 6** |
| WS-R18 | Chat → brief returns opaque "Seed Failed" | High | **Fixed in Chunk 6** |
| WS-R19 | DOCX brief title truncated / wrong | High | **Fixed in Chunk 6** |
| — | Composer Review vs Approve workflow unclear | Low | Pending (PO clarification #4) |
| — | "Daily Review" + "public" semantics | Low | Pending (PO clarification #5) |
| — | Document → Work Studio transition trigger | Medium | Pending (PO clarification #6) |
| — | Contributor recognition criteria | Medium | Pending (PO clarification #2) |

**Acceptance criteria for "working" today**
- All 3 create-paths × 2 kinds (deck, report) round-trip to composer.
- Compilation Wizard dispatches the correct backend by kind.
- Enhance flow never returns `worker_crash` for the 6 kinds.
- DOCX titles render verbatim up to 200 chars.

---

### 3.4 Akki Chat

**Purpose & user value**
A first-class chat surface where the user converses with AKKI about anything in the active workspace — documents, briefs, cycles, signals, objectives. Akki carries citation chips on every assistant message so claims are traceable. Conversations persist; "Open in composer" promotes a thread into a brief (Chunk 6 ties the chat title verbatim to the brief title).

**Primary user flows**
1. **New conversation**: `pages/Chat.jsx` → "New conversation" → optionally pick a model (chat models endpoint).
2. **Send a message**: streams via SSE; assistant deltas appear token-by-token; citation chips render on `done`.
3. **Attach a document** to a chat (existing context document, not upload-from-modal).
4. **Restore a deleted chat** within 30 days.
5. **Open in composer** → `SourceStep.jsx` → POSTs `/work-studio/from-source` with `source_type=chat_artefact` → composer surface.
6. **Generate document now** (Chunk 6 — chat title becomes brief title verbatim).

**Key screens / components**
- `pages/Chat.jsx`, `components/chat/MessageList.jsx`, `MessageComposer.jsx`, `CitationChip.jsx`, `ModelPicker.jsx`
- `components/studio/SourceStep.jsx` (the chat→brief bridge with the empty-chat pre-flight)

**Backend endpoints**
- `GET /api/chat/models` — available LLM models (Emergent Universal Key)
- `POST /api/chats` — create a chat
- `POST /api/chats/{id}/attach` — attach a document
- `GET /api/chats` — list (paginated)
- `GET /api/chats/search` — semantic search inside chats
- `GET /api/chats/{id}` + `PATCH` + `DELETE` + `POST /restore`
- `POST /api/chats/{id}/messages` — non-streaming send
- `POST /api/chats/{id}/messages/stream` — SSE token stream
- `GET /api/chats/{id}/audit` + `/audit/export.zip` — per-chat audit trail
- `POST /api/admin/chat-retention/sweep` — admin retention sweep

**Data model**
- `db.chats`: `{ id, account_id, context_id, title, model_id, message_count, status: active|deleted, created_at, updated_at }`
- `db.chat_messages`: `{ id, chat_id, role: user|assistant|system, content, citations, created_at }`
- `db.chat_audit`: per-message redaction summary + LLM model identity

**Integrations**
- OpenAI / Anthropic / Gemini via Emergent Universal Key (model identity stored on each message).
- Synisense Shield PII redaction pre-LLM.

**Recent fixes in this sprint**
- Chunk 6 (WS-R18 / R19): chat → brief surfaces clean `{code, message}` 409s; chat title threads verbatim into brief.title.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| WS-R18 | Empty chat → brief returned opaque "Seed Failed" | High | **Fixed in Chunk 6** |
| — | What can Chat access? PII handling rules | Low | Pending (PO clarification #16) |

**Pending PO clarifications**: #16 — Chat scope.

**Acceptance criteria for "working" today**
- Streaming completes for prompts up to 4000 tokens.
- Multi-conversation with separate sessions works.
- Citation chips clickable; route to source documents.
- Empty-chat pre-flight disables Generate buttons.

---

### 3.5 Solva Reasoning Engine

**Purpose & user value**
The structured-reasoning workbench. Where a user picks a *submodule* — *Seek Clarity*, *Develop Strategy*, *Simulate Hypothesis*, *Get Perspective* — and works through a multi-frame Solva session to land on a *Synthesis* with claims + recommendations + validation. The reasoning trail is auditable. Solva sessions can be exported to PDF/DOCX or pushed into a Work Studio brief.

**Primary user flows**
1. **Pick a submodule** from `/app/solva` landing → start a session.
2. **Multi-turn session**: each turn streams via SSE through the Solva frame pipeline (frame-audit → continue-chat → turn).
3. **Attach documents** to the session for citation grounding.
4. **Frame audit** → if the engine detects a missing premise, surfaces a frame-audit dialog → user decides whether to enrich or proceed.
5. **Take to Cycle** / **Take to Solva** / **Handoff to Cycle** — pivot the session into an actionable artefact.
6. **Export**: PDF (`/sessions/{sid}/export.pdf`) or DOCX (`/sessions/{sid}/export.docx`).
7. **Fork**: clone an existing session with the same frame.
8. **Stale-session sweep** (cron): abandon sessions inactive for N hours.

**Key screens / components**
- `pages/SolvaApp.jsx`, `SolvaLanding.jsx`, `SolvaSession.jsx`, `SolvaSessions.jsx` (list)
- `components/solva/FrameRail.jsx`, `SynthesisCard.jsx`, `ReasoningLog.jsx`

**Backend endpoints** (22 total in `routers/solva_v2.py`)
- `POST /sessions` — start a session (context-scoped — Chunk 1 fix)
- `GET /sessions` — list (context-scoped)
- `POST /sessions/{sid}/turn` — SSE turn
- `POST /sessions/{sid}/frame-audit` + `/frame-audit-decision`
- `POST /sessions/{sid}/attach-document` + `DELETE /attached-documents/{doc_id}`
- `POST /sessions/{sid}/take-to-cycle` + `/handoff/cycle`
- `GET /sessions/{sid}` + `/reasoning-log` + `/synisense-breakdown`
- `POST /sessions/{sid}/fork`
- `POST /sessions/{sid}/abandon`
- `POST /cron/stale-session-sweep`
- `GET /sessions/{sid}/export.pdf` + `/export.docx`

**Data model**
- `db.solva_v2_sessions`: `{ id, account_id, context_id (Chunk 1), submodule, intent, status, synthesis, persona, claims, recommendations, validation, … }`
- `db.solva_v2_frames`: per-turn frame snapshots

**Integrations**
- LLM via Emergent Universal Key.
- Synisense Shield PII redaction per-turn.

**Recent fixes in this sprint**
- Chunk 1 (WS-R16, P0): `GET /solva/v2/sessions` now strictly filters by `context_id`; cross-account leakage closed.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| WS-R16 | Solva V2 sessions list returned cross-account rows | Critical (P0) | **Fixed in Chunk 1** |
| — | Single-session Solva routes still need explicit `context_id` scope review (12 of 22 routes audited so far) | Medium | Open in §4 |
| — | 524 / 541 orphan sessions (data debt — sessions without active `context_id` or `account_id`) | Low | Open in §4 |

**Acceptance criteria for "working" today**
- Sessions list never leaks across accounts.
- Multi-turn session completes without SSE hang.
- Export PDF / DOCX renders the full reasoning log.

---

### 3.6 Monitor

**Purpose & user value**
The objectives / projects / KPIs tracker. Goals live here; their current scores are auto-computed; their adjacency (recent activity, contributors, linked Pulse signals) surfaces "around the goals". For a NED, it's the answer to *"what does this company look like today vs the plan?"*

**Primary user flows**
1. **Open `/app/monitor`** → see Objectives / Projects / KPIs panes (the Monitor V2 surface).
2. **Auto-suggest objectives** (LLM-backed) → user picks from the suggestion list.
3. **Create / edit / delete** an objective / project / KPI.
4. **Around-the-Goals** section (per PO clarification #14): recent activity + contributors + linked signals (currently planned, partially implemented).
5. **Manual status override** (PO clarification #13 — planned with audit trail).

**Key screens / components**
- `pages/Monitor.jsx`
- `components/monitor/ObjectivesPane.jsx`, `ProjectsPane.jsx`, `KpisPane.jsx`, `ScoreCard.jsx`

**Backend endpoints** (7 routes in `routers/monitor_v2.py`)
- `GET /contexts/{cid}/monitor/auto-suggest-objectives` — LLM suggestions
- `GET /contexts/{cid}/monitor/auto-suggest-projects` — LLM suggestions
- `GET /contexts/{cid}/monitor/{kind}` — list (kind ∈ objectives, projects, kpis, goals)
- `POST /contexts/{cid}/monitor/{kind}` — create
- `GET /contexts/{cid}/monitor/{kind}/{rid}` — detail
- `PATCH /contexts/{cid}/monitor/{kind}/{rid}` — update
- `DELETE /contexts/{cid}/monitor/{kind}/{rid}` — delete

**Data model**
- `db.monitor_objectives`, `db.monitor_projects`, `db.monitor_kpis`, `db.monitor_goals`: each `{ id, context_id, title, score, target, probability, status, owner_id, contributors[], created_at }`

**Integrations**
- LLM via Emergent Universal Key for auto-suggestions.

**Recent fixes in this sprint**
- None in Chunks 1–6.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| — | Performance Score vs Current Score naming drift | Low | Pending (PO clarification #12 — collapse to "Current Score") |
| — | Manual objective status override missing | Medium | Pending (PO clarification #13) |
| — | "Around the Goals" section incomplete | Medium | Pending (PO clarification #14) |

**Pending PO clarifications**: #12, #13, #14.

**Acceptance criteria for "working" today**
- CRUD on objectives / projects / KPIs / goals works without console errors.
- Auto-suggest renders results within 10 s.
- Detail pane shows the score history.

---

### 3.7 Pulse

**Purpose & user value**
The AI-surfaced signal feed. Pulse listens to documents, cycles, and external news (MOCKED for news) and surfaces *signals* — short, dated, cited claims about the workspace's state. Signals are categorised (risk / opportunity / regulatory / market / etc.), tagged with confidence, and routed to action: comment, share, resolve, archive, bookmark, take to Solva.

**Primary user flows**
1. **Open `/app/pulse`** → see active signals. Filter by freshness / category / source.
2. **Click a signal** → drawer shows full claim + citations + comment thread.
3. **Comment / share / resolve / unresolve / bookmark / save / take-to-Solva** actions.
4. **Across Other Boards** (PO clarification #11): same signal/topic in user's other workspaces.
5. **Archive** flow (PO clarification #9 — currently has Archived tab but no archive action).

**Key screens / components**
- `pages/Pulse.jsx`
- `components/pulse/SignalCard.jsx`, `SignalDrawer.jsx`, `FilterBar.jsx`, `AcrossBoardsPane.jsx`

**Backend endpoints** (11 routes in `routers/pulse.py`)
- `GET /contexts/{cid}/pulse/feed` — paginated signal feed
- `GET /contexts/{cid}/pulse/across-boards` — cross-portfolio adjacency
- `POST /contexts/{cid}/pulse/signals/{sid}/comment` + `DELETE /comments/{cid}` — comment thread
- `POST /contexts/{cid}/pulse/signals/{sid}/share` — share with team
- `POST /contexts/{cid}/pulse/signals/{sid}/resolve` + `/unresolve`
- `POST /contexts/{cid}/pulse/signals/{sid}/bookmark` + `/unbookmark`
- `POST /contexts/{cid}/pulse/signals/{sid}/save`
- `POST /contexts/{cid}/pulse/signals/{sid}/take-to-solva` — promotes signal to a Solva session

**Data model**
- `db.signals`: `{ id, context_id, claim, category, confidence, freshness, sources[], status, created_at }`
- `db.signal_comments`: comment thread
- `db.signal_actions_log`: bookmark / save / resolve audit

**Integrations**
- LLM via Emergent Universal Key for signal synthesis (deterministic dedup in `services/signal_dedup.py`).
- News (MOCKED — `services/news_aggregator.py` returns static fixtures in dev).

**Recent fixes in this sprint**
- None in Chunks 1–6.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| — | Save vs Bookmark distinction unclear | Low | Pending (PO clarification #7 — recommend collapse to Bookmark) |
| — | Freshness filter appears twice (top-level + dropdown) | Low | Pending (PO clarification #8) |
| — | Archived tab exists with no archive action | Medium | Pending (PO clarification #9) |
| — | "High" badge semantics ambiguous | Low | Pending (PO clarification #10) |
| — | "Across Other Boards" function undefined | Low | Pending (PO clarification #11) |

**Pending PO clarifications**: #7, #8, #9, #10, #11.

**Acceptance criteria for "working" today**
- Feed paginates; filters narrow correctly.
- Resolve / bookmark / save round-trip and persist.
- Take-to-Solva opens a new Solva session with the signal as the seed claim.

---

### 3.8 Document Journal

**Purpose & user value**
The source-of-truth document library. Every upload lands here first; AKKI generates a summary, paragraph anchors, and a journal commentary chain. Documents can be later promoted into briefs (PO clarification #6). The journal supports cross-document evolution diffs (track how a board pack changed from cycle to cycle).

**Primary user flows**
1. **Upload** via the top-bar + button → `UploadModal` → file scan (ClamAV — `services/clamav_service.py`, 503 if engine down — no stub fallback) → preview generation → AKKI summary.
2. **List view** at `/app/workspace` → rows show name + description (Patch 28D `preview → description → placeholder` chain) + meta.
3. **Detail drawer** → preview + AKKI summary + paragraph anchors + journal commentary thread.
4. **Document → Brief** transition (PO clarification #6 — currently auto-surfaces in Work Studio after a brief is generated from it).
5. **Tag contributors** (PO clarification #17 — planned via `team_catalogue`).
6. **Evolution diff** — `POST /documents/{id}/evolution-diff` compares two versions of a doc.

**Key screens / components**
- `pages/Workspace.jsx` (the Document Journal list)
- `components/upload/UploadModal.jsx`
- `components/documents/DocumentDrawer.jsx`, `ParagraphAnchors.jsx`, `JournalCommentary.jsx`

**Backend endpoints** (16 routes in `routers/documents.py`)
- `POST /contexts/{cid}/documents` — upload
- `GET /contexts/{cid}/documents` — list
- `GET /contexts/{cid}/documents/{doc_id}` — detail
- `PATCH /contexts/{cid}/documents/{doc_id}` — rename / metadata
- `DELETE /contexts/{cid}/documents/{doc_id}` — soft-delete
- `POST /contexts/{cid}/documents/{doc_id}/summary` — AKKI summary
- `POST /contexts/{cid}/documents/generate-meta` — metadata regen
- `GET /contexts/{cid}/documents/{doc_id}/thread` — journal thread
- `GET /contexts/{cid}/document-journal` + `/document-journal/search`
- `POST /contexts/{cid}/documents/{doc_id}/journal-commentary` — append to thread
- `POST /contexts/{cid}/documents/{doc_id}/evolution-diff` — diff vs another doc
- `GET /contexts/{cid}/documents/{doc_id}/download`
- `GET /contexts/{cid}/documents/{doc_id}/paragraphs` + `/paragraphs/{pid}/original`
- `POST /cron/paragraph-anchors-sweep` — cron rebuild

**Data model**
- `db.documents`: `{ id, context_id, account_id, name, doc_type, status, size, mime, preview, akki_summary, extracted_text, contributors[], created_at, updated_at }`
- `db.document_thread`: journal commentary thread
- `db.document_paragraphs`: anchor index for citation chips

**Integrations**
- **ClamAV** virus scan — live; on outage the upload returns 503 (NO STUB fallback per `services/clamav_service.py`).
- LLM via Emergent Universal Key for summary + journal commentary.

**Recent fixes in this sprint**
- Chunk 2 (DJ-R03, DJ-R05): document-journal list + journal-commentary append migrated to async job queue; closed 524 timeouts.

**Known issues / open findings**
| ID | Description | Severity | Status |
|----|---|---|---|
| DJ-R03 | Doc journal list timed out at gateway | High | **Fixed in Chunk 2** |
| DJ-R05 | Journal-commentary append 524'd on long thread | High | **Fixed in Chunk 2** |
| — | When does a document show up in Work Studio? | Medium | Pending (PO clarification #6) |
| — | Tag contributors on upload | Medium | Pending (PO clarification #17) |

**Pending PO clarifications**: #6, #17.

**Acceptance criteria for "working" today**
- Upload → scan → preview → summary completes within 60 s.
- List shows rows with description line.
- Evolution diff renders without TypeError.
- ClamAV outage returns clean 503 (NO STUB fallback).

---

### 3.9 Settings / Admin

**Purpose & user value**
Account / workspace / billing / security / audit / retention controls. Split surface: per-account (`/app/settings`, `/app/security`) vs per-workspace (`/app/manage`, `/app/manage/tenant`).

**Primary user flows**
1. **Account settings** → profile, MFA enrolment, password rotation.
2. **Security** → audit-log download, session list, device list.
3. **Workspace management** → user list, role assignments, invites, retention.
4. **Trust panel** → "what we send to LLM" preview + Synisense redaction summary.
5. **Billing** (Stripe — **MOCKED** in dev; `routers/billing.py` writes stub plans).
6. **Universal Key spend** (admin-only) — per-account LLM cost ledger.

**Key screens / components**
- `pages/AccountSecurity.jsx`, `Manage.jsx`, `TenantSettings.jsx`, `Enterprise.jsx`
- `components/governance/TrustPanel.jsx`, `MfaEnrollment.jsx`

**Backend endpoints**
- `routers/auth.py`: login / logout / signup / refresh / MFA enrol / password change
- `routers/billing.py`: Stripe checkout session / portal / webhook (Stripe **MOCKED** in dev)
- `routers/governance.py`: trust-panel data, audit retention
- `routers/admin_*.py`: 6 admin routers — sandbox KPI, LLM spend, signal KPI, journal, auth events, health

**Data model**
- `db.accounts`, `db.memberships`, `db.contexts`, `db.audit_log`, `db.llm_spend`, `db.mfa_enrollment`

**Integrations**
- **Stripe — MOCKED** in dev (test keys in pod env; production webhook in `services/stripe_webhook.py`).
- Emergent Universal Key spend tracking.

**Recent fixes in this sprint**
- None in Chunks 1–6.

**Known issues / open findings**: none QA-flagged.

---

## 4. Open Risks & Technical Debt

| Area | Risk / Debt | Severity | Status |
|---|---|---|---|
| **Sync Document endpoints** (P1-risk) | `POST /documents` upload + `POST /summary` still synchronous; large PDFs (>20MB) risk 524 timeouts at gateway | Medium | **NOT STARTED** (queued for Chunk 7 or later) |
| **Single-session Solva routes** | 12 of 22 routes in `routers/solva_v2.py` audited for `context_id` scope; remaining 10 still rely on `account_id` only | Medium | **NOT STARTED** |
| **SSE raw `repr(exc)` leaks** | `routers/streaming_v9.py` emits raw Python exception strings in 2 SSE error paths | Low (P2 soft-debt) | **NOT STARTED** (logged in Chunk 3 close-out) |
| **47 E2E tests quarantined** | `tests/test_*sprint*.py` + `tests/test_phase12_*.py` rely on `requests.Session` against a live server; need rewrite to `httpx.AsyncClient` + `ASGITransport` | Medium | **NOT STARTED** (Phase 4/5 of QUARANTINE_TRIAGE_PLAN.md) |
| **524/541 orphan Solva sessions** | `db.solva_v2_sessions` carries ~524 rows lacking explicit `context_id`, ~541 missing `account_id` cleanly | Low (data debt) | **NOT STARTED** (write-once data; safe to ignore until migration sprint) |
| **`work_studio_brief_revisions` orphan-prune** | Brief deletes don't always cascade to revisions; ~3% orphan rate | Low | **NOT STARTED** |
| **Mobile narrow viewport (<768px)** | LeftRail hidden; mobile drawer carries 9 modules but Work Studio + Cycle's two-column composer surfaces don't reflow well | Low | **NOT STARTED** |

---

## 5. Sprint Status Map (12-chunk plan from the 13 May QA sprint)

| Chunk | Scope | Status | Outcome (1 line) |
|---|---|---|---|
| SETUP | PO Clarifications memo | ✅ Done | 17 items aggregated + defaults applied; awaiting PO sign-off |
| 1 | P0 Solva cross-account leakage (WS-R16) | ✅ Done | `GET /solva/v2/sessions` strictly `context_id`-scoped |
| 2 | Backend 524 timeouts (DJ-R03, DJ-R05, CM-R04) | ✅ Done | 3 endpoints migrated to async job queue + polling |
| 3 | Enhance worker_crash (WS-R06, R12, R15) | ✅ Done | Minutes registered + scraper hardened + Adjust-and-Retry preserves docs |
| 4 | Compilation Wizard kind mapping (WS-R02/R04/R05/R07/R08) | ✅ Done | `initialType` propagation fixed; correct kind dispatch |
| 5 | Create Summary Deck + Create Report (WS-R09/R10/R11/R13/R14) | ✅ Done | New unified `/work-studio/artefacts` endpoint; 6 paths green |
| 6 | Brief surfaces (WS-R01/R17/R18/R19) | ✅ Done | Aggregate detail dispatch + drawer CTA + nested-dict toast + long-title DOCX |
| **6.5** | Left dashboard navigation (cross-cutting shell) | ✅ Done (parked per PO direction during this doc sprint) | Persistent LeftRail + slim TopBar replace dual-header layout |
| 7 | (PARKED) — likely Pulse cleanup batch (clarifications #7–#11) | 🟡 Queued | Awaiting PO sign-off on Pulse defaults |
| 8 | (PARKED) — likely Monitor cleanup (clarifications #12–#14) | 🟡 Queued | Awaiting PO sign-off on Monitor defaults |
| 9 | (PARKED) — likely Document Journal tagging (clarifications #6, #17) | 🟡 Queued | Depends on `team_catalogue` enrichment |
| 10 | (PARKED) — likely Cycle scoreboard + follow-up flow (#15) | 🟡 Queued | Awaiting PO sign-off |
| 11 | (PARKED) — likely Chat scope + privacy doc (#16) | 🟡 Queued | Awaiting PO sign-off |
| 12 | (PARKED) — likely final cleanup + sync-doc-endpoint migration + SSE error formatting | 🟡 Queued | Picks up remaining §4 items |

Chunks 7–12 are working hypotheses based on the clarifications memo grouping; the PO can re-prioritise.

---

## 6. QA Findings Matrix

Aggregated from the 13 May QA sprint (46 findings), the chunk diagnoses, and the clarifications memo. Findings with explicit IDs are tracked; clarification-tagged findings (Pulse, Monitor, Chat, Composer, Document Journal) are bucketed under PO-pending.

| ID | Module | Description | Severity | Chunk | Status |
|---|---|---|---|---|---|
| WS-R01 | Work Studio | Drawer CTA target = undefined | High | 6 | ✅ Fixed |
| WS-R02 | Work Studio | Compilation Wizard lands on Step 2 | High | 4 | ✅ Fixed |
| WS-R03 | Work Studio | "Board Pack appears on the rail" copy confusing | Low | — | 🟡 Pending PO #3 |
| WS-R04 | Work Studio | Wizard Step 1 pre-selects Report | High | 4 | ✅ Fixed |
| WS-R05 | Work Studio | Wizard Step 2 fetches wrong kind | High | 4 | ✅ Fixed |
| WS-R06 | Work Studio | Minutes Enhance `KeyError: 'minutes'` + retry loses doc | High | 3 | ✅ Fixed |
| WS-R07 | Work Studio | Wizard Step 2 pre-filter wrong | High | 4 | ✅ Fixed |
| WS-R08 | Work Studio | Wizard Step 2 truncated kind list | High | 4 | ✅ Fixed |
| WS-R09 | Work Studio | Brief picker empty even with briefs | High | 5 | ✅ Fixed |
| WS-R10 | Work Studio | Deck Blank + External Document paths broken | Critical | 5 | ✅ Fixed |
| WS-R11 | Work Studio | Create Summary Deck non-functional overall | Critical | 5 | ✅ Fixed |
| WS-R12 | Work Studio | Report Enhance worker_crash | High | 3 | ✅ Fixed |
| WS-R13 | Work Studio | Report brief picker empty | High | 5 | ✅ Fixed |
| WS-R14 | Work Studio | Create Report Blank + External Document broken | Critical | 5 | ✅ Fixed |
| WS-R15 | Work Studio | Deck Enhance worker_crash | High | 3 | ✅ Fixed |
| WS-R16 | Work Studio / Solva | Sessions list cross-account leakage | Critical (P0) | 1 | ✅ Fixed |
| WS-R17 | Work Studio | "Bad aggregate id" on brief click | High | 6 | ✅ Fixed |
| WS-R18 | Work Studio / Chat | Chat → brief opaque "Seed Failed" toast | High | 6 | ✅ Fixed |
| WS-R19 | Work Studio | DOCX brief title truncated / wrong | High | 6 | ✅ Fixed |
| DJ-R03 | Doc Journal | List 524 timeout | High | 2 | ✅ Fixed |
| DJ-R05 | Doc Journal | Journal-commentary 524 timeout | High | 2 | ✅ Fixed |
| CM-R04 | Cycle Manager | Draft-compilation 524 timeout | High | 2 | ✅ Fixed |
| MS-R01 | Misc / Home | Bell routes to Brief Review Centre vs notifications | Medium | — | 🟡 Pending PO #1 |
| PO-#2 | Work Studio | Contributor recognition criteria | Medium | — | 🟡 Pending |
| PO-#4 | Composer | Review → Approve workflow | Low | — | 🟡 Pending |
| PO-#5 | Composer | Daily Review + public semantics | Low | — | 🟡 Pending |
| PO-#6 | Doc Journal | Document → Work Studio transition trigger | Medium | — | 🟡 Pending |
| PO-#7 | Pulse | Save vs Bookmark distinction | Low | — | 🟡 Pending |
| PO-#8 | Pulse | Freshness double-layer | Low | — | 🟡 Pending |
| PO-#9 | Pulse | Archive mechanism missing | Medium | — | 🟡 Pending |
| PO-#10 | Pulse | "High" badge semantics | Low | — | 🟡 Pending |
| PO-#11 | Pulse | "Across Other Boards" function | Low | — | 🟡 Pending |
| PO-#12 | Monitor | Performance vs Current Score naming | Low | — | 🟡 Pending |
| PO-#13 | Monitor | Manual objective status override | Medium | — | 🟡 Pending |
| PO-#14 | Monitor | "Around the Goals" section | Medium | — | 🟡 Pending |
| PO-#15 | Cycle | Scoreboard CTA after poor score | Medium | — | 🟡 Pending |
| PO-#16 | Chat | Chat scope / privacy boundary | Low | — | 🟡 Pending |
| PO-#17 | Doc Journal | Tag contributors on upload | Medium | — | 🟡 Pending |

**Counted**: 22 explicit-ID findings tracked → **19 fixed, 3 pending PO**. Plus 14 PO-tagged findings pending sign-off. Aligns with the QA report's "46 findings" (the residual 10 are clarification-only one-liners absorbed into the same PO items).

---

## 7. Testing & Verification Status

### Pytest
- **Backend**: **453 passing**, 565 skipped (quarantined), 0 failed, 0 errors. Runtime: ~115 s.
- **Per-chunk additions**:
  - Chunk 1 — `test_chunk1_solva_leak.py` (4 tests)
  - Chunk 2 — `test_chunk2_async_jobs.py` (7 tests)
  - Chunk 3 — `test_chunk3_enhance_worker.py` (6 tests)
  - Chunk 4 — `test_chunk4_wizard_aggregates.py` (6 tests)
  - Chunk 5 — `test_chunk5_create_artefact.py` (14 tests)
  - Chunk 6 — `test_chunk6_brief_surfaces.py` (11 tests)
- **Quarantine totals**: 47 tests in `tests/test_*sprint*.py` + 5 in `tests/test_phase12_2_e2e.py` etc. blocked on `requests.Session` → `httpx + ASGITransport` rewrite.

### render-smoke (frontend Playwright)
- **Routes covered (8)**: Home, Work Studio, Cycle, Workspace, Pulse, Monitor, Chat, Questions.
- **Upload paths covered (2)**: Doc Journal upload + Work Studio upload.
- **Chunk-specific steps**: Patch 28 interactions, Chunk 4 wizard, Chunk 5 create-artefact, Chunk 6 brief drawer CTA, Chunk 6.5 left-rail.
- **Always-green**: 0 page errors, 0 uncaught exceptions, 0 console errors across all 8 routes.

### What is NOT covered
- **Full multi-turn Solva session E2E** (quarantined in `test_phase12_*`).
- **Stripe webhook full pipeline** (MOCKED).
- **News aggregator** (MOCKED).
- **DOCX render byte-comparison** beyond Chunk 6's title-presence assertion.
- **Mobile-viewport responsive layouts** (<768px) — Playwright only runs at 1920×800.
- **Cross-context permissions matrix** — covered ad-hoc per chunk but no exhaustive RBAC test matrix exists.

---

## 8. Glossary

- **Context** — a single workspace. Every artefact is scoped to one context. An account joins via a membership row.
- **Workspace** — synonymous with context in product copy; *context* is the schema term, *workspace* is the user-facing term.
- **Brief aggregate** — the compound id surfaced by `briefings/aggregates`. Format: `<kind>::<uuid>`. The `kind` ∈ {`cycle_board_pack`, `cycle_minutes`, `cycle_committee_pack`, `briefing`, `deck`, `report`}.
- **Artefact** — any shippable Work Studio output: brief, deck, report, board pack, minutes, committee pack. Each kind has its own collection (`work_studio_briefs`, `decks`, `reports`, `boardpacks`, etc.).
- **Cycle** — a structured board cycle with an agenda, a team, contributions, readiness, and an eventual compiled artefact. Lives in `db.cycles` + child collections.
- **Solva session** — a structured-reasoning thread in one of 4 submodules (Seek Clarity / Develop Strategy / Simulate Hypothesis / Get Perspective). Lives in `db.solva_v2_sessions`. Synthesises into a Brief.
- **Pulse signal** — an AI-surfaced, cited claim about the workspace state. Categorised + dated + confidence-tagged.
- **Document Journal entry** — a single document + its summary + its journal commentary thread + its paragraph anchors.
- **Composer** — `pages/StudioComposerPage.jsx` + `BlockComposer.jsx`. The block-level editor used by every kind.
- **Compilation Wizard** — the 3-step modal that turns Cycle output into a kind-aware Work Studio aggregate (Patch 2B.2). Right-rail sticky at ≥1100px.
- **Enhance** — block-level LLM rewrite. SSE-streamed. Two-pass schema (`services/two_pass.py`).
- **Synisense Shield** — the privacy wall (`services/privacy_wall.py`). PII redacts everything before LLM exposure.
- **Agent Cycle** — the deterministic readiness engine for Cycle Manager. Not an LLM agent — pure rule-based readiness aggregation.
- **Aggregate id** — compound id `<kind>::<uuid>` used to address artefacts uniformly in the briefings/aggregates listing API.
- **`title_override`** — Chunk 6 parameter on `build_brief_from_solva` that bypasses the submodule prefix for chat-sourced briefs.
- **`composer_url`** — Chunk 6 field on aggregate detail responses pointing at the canonical edit surface.
- **Render-smoke** — `yarn render-smoke` — local Playwright suite that exercises 8 routes + 2 upload paths + chunk-specific behaviours.
- **Emergent Universal Key** — single shared LLM API key spanning OpenAI / Anthropic / Gemini. Backed by `emergentintegrations` library. Spend tracked per account in `db.llm_spend`.

— end of document —
