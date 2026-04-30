# AKKI · Product Features & Functionality

> Source-of-truth inventory generated from a read-only review of the
> `bramuel-syni/Akki-Executive` codebase (branch `main`). Every claim
> below is anchored to a file path. Where the code is ambiguous, the
> entry is marked **unclear**.

---

## 1. Product Overview

**AKKI** is "an intelligence layer built for non-executive directors and
operating executives of listed and pre-IPO companies. You sit beside
them, reading their board packs, minutes, and operational data, and
telling them what a sharp, experienced board advisor would notice."
(verbatim, from the system prompt in `/app/backend/llm_service.py:22-49`).

The product positions itself as "the colleague who reads with you" — a
shielded LLM-backed reading and synthesis layer with editorial UX
(Georgia serif heads, cream/oxblood palette), evidence-first citations,
and "no AI slop" design rules. The full audit history of intent and
delivery is in `/app/AUDIT_iter68.md` (68 build iterations recorded).

The marketing promise (per `frontend/src/pages/Landing.jsx`):
> "AKKI reads the pack so you can read the room."

Three pillars surfaced on the landing page:
1. **AKKI Solve** — 4-phase decision-support engine (`Surface → Depth → Synthesis → Lock-in`).
2. **Cross-Board Pulse** — aggregated stream across multiple board contexts on Home.
3. **Decks + Reports Studio** — a unified Studio surface with sensitivity scoring + read receipts + "Exposure Score".

### Primary personas (detected in code)

| Persona | Evidence |
|---|---|
| **Operating Executive** (CFO/CEO etc.) | `core.AccountRole = "executive"`; `routers/contexts.py` provisions an `executive_personal` context by default. |
| **Non-Executive Director (NED)** | `AccountRole = "ned"`; `Cycle`, `Briefings`, `InfluenceMap` flows are NED-shaped. |
| **Dual** (NED + Executive) | `declared_role: "dual"` in `routers/auth.py`; admin seed account uses this. |
| **Sandbox prospect** (pre-auth) | `routers/sandbox.py` — disposable account `sandbox+<id>@akki.local`, hard-deleted day 22. |
| **External recipient / Chair** | `routers/studio.py` share-with-chair flow → JWT-signed tracker → `account_id = external:<sha256(email)>`. |
| **Reportee** (a direct report submitting to a cycle) | `routers/cycle.py` `/respond/{token}` checklist flow. |
| **Superadmin** | `is_superadmin: True` in seed, gates `/admin/*` endpoints. |
| **Blog subscriber** | `db.blog_subscribers`; public subscribe via `/api/blog/subscribe`. |

---

## 2. Tech Stack

### Backend
- **Framework**: FastAPI 0.110.1 (`/app/backend/server.py`, `requirements.txt`)
- **DB driver**: Motor 3.3.1 (async MongoDB) on PyMongo 4.5.0
- **Auth**: PyJWT 2.12.1 + bcrypt 4.1.3 + pyotp 2.9.0 + qrcode 8.2 (TOTP MFA)
- **Templating / docs**: pypdf 6.10.2, python-docx 1.2.0, reportlab 4.4.10
- **LLM gateway**: `emergentintegrations==0.1.0` (Universal Key wrapper around Anthropic / OpenAI / Gemini); also `litellm`, `openai`, `google-genai` are in deps
- **Email**: `resend==2.29.0`
- **Payments**: `stripe==15.0.1` (via `emergentintegrations.payments.stripe.checkout.StripeCheckout`)
- **Scheduling**: `APScheduler==3.10.4` (Tuesday-10:00 UTC blog cron, Monday-08:00 UTC influence digest)
- **Storage**: local disk (`/app/backend/uploads/`), shaped like S3, swappable via `STORAGE_BACKEND` env (per `documents_service.py:1-7`)
- **Retrieval**: BM25 (`/app/backend/bm25.py`) — vector DB explicitly deferred (audit §4)

### Frontend
- **Framework**: React 19 + react-router-dom 7.5
- **Build**: CRACO on react-scripts 5 (`craco.config.js`); package manager **yarn 1.22.22**
- **Styling**: TailwindCSS 3.4 + tailwind-merge + tailwindcss-animate; cream/oxblood/navy editorial palette
- **UI primitives**: Radix UI suite (accordion, dialog, dropdown, popover, tabs, toast, tooltip, …)
- **Forms / validation**: react-hook-form 7.56 + zod 3.24 + @hookform/resolvers
- **Animation/visualisation**: framer-motion 12.38, recharts 3.6, embla-carousel
- **Notifications**: sonner 2.0
- **HTTP**: axios 1.8 (`/app/frontend/src/lib/api.js`)
- **Date**: date-fns 4.1, react-day-picker 8.10
- **Visual editor plugin** (Emergent): `@emergentbase/visual-edits` dev dep

### Infra / hosting
- Supervisord-managed services; backend on `0.0.0.0:8001`, frontend on `:3000`, fronted by Kubernetes ingress that routes `/api/*` → backend.
- DEPLOY.md (`/app/DEPLOY.md`) targets Emergent Cloud with Entri-managed custom subdomain.
- Bootstrap one-shot at `/app/backend/scripts/bootstrap_prod.py` (creates superadmin + indexes).

---

## 3. Feature Catalogue

### 3.1 Sandbox (pre-auth evaluation)

- **Purpose**: Let a prospect explore a fully-populated AKKI workspace in ~60s with no signup, then convert.
- **User flow** (per `frontend/src/pages/Sandbox.jsx`, `SandboxGenerating.jsx` + `routers/sandbox.py`):
  1. `/sandbox` — 4–5 question intake (company, sector, role, region, optional objective).
  2. `POST /api/sandbox/generate` returns `session_id` + 10 streaming stage texts.
  3. Frontend drives 60s narrative (`useAIStageTicker` hook), polls `GET /api/sandbox/generate/{session_id}/status`.
  4. Backend picks a sector template (`backend/sandbox_templates.py`, `sandbox_service.py`), substitutes the prospect's answers, creates a disposable account `sandbox+<id>@akki.local`, a `type: sandbox` context, seeds documents/signals/briefings, returns access JWT.
  5. User lands on `/app/quick-results/:cid/:docId` (3 doc-bound use-cases — `pages/QuickResults.jsx`).
  6. After 24h, `ObjectiveCheck` card surfaces (`routers/sandbox.py` objective-check endpoints + `components/sandbox/ObjectiveCheck.jsx`) — yes/partial/no + note.
  7. `/api/sandbox/convert` upgrades sandbox → real account at signup.
- **Backend**: `/app/backend/routers/sandbox.py` (979 lines), `/app/backend/sandbox_service.py`, `/app/backend/sandbox_templates.py` (33,683 chars of curated sector templates).
  - `POST /api/sandbox/generate` — start session
  - `GET /api/sandbox/generate/{session_id}/status` — poll until ready
  - `GET /api/sandbox/templates` — list available templates
  - `POST /api/sandbox/cleanup/expired` — admin cron
  - `POST /api/sandbox/contexts/{cid}/capture-email` — late email capture
  - `GET / POST /api/sandbox/contexts/{cid}/tutorial` and `/tutorial/dismiss`
  - `GET / POST /api/sandbox/contexts/{cid}/sample-doc` and `/sample-doc/accept`
  - `GET / POST /api/sandbox/contexts/{cid}/objective-check`
  - `POST /api/sandbox/convert`
  - `POST /api/sandbox/contexts/seeded`
- **Frontend**: `pages/Sandbox.jsx`, `pages/SandboxGenerating.jsx`, `pages/QuickResults.jsx`, `components/sandbox/*` (`ObjectiveCheck`, `SandboxBanner`, `SandboxEmailCapture`, `SandboxPackDrop`, `SandboxSampleDoc`, `SandboxTutorial`).
- **Data**: `db.accounts` (with `is_sandbox: true`, `sandbox_session_id`), `db.contexts` (`type: sandbox`, `sandbox_metadata`), `db.documents`, `db.signals`, `db.briefings`, `db.sandbox_pickups`.
- **Integrations**: Synthetic (no LLM call required for seed); `EMERGENT_LLM_KEY` used if narrative is LLM-driven. Resend for late email capture.
- **Status**: **production** — `pages/Sandbox.jsx:279` discloses "fictional environment with mock data" (intentional copy, not an implementation gap).

### 3.2 AKKI Solve — 4-phase session engine

- **Purpose**: Decision-support engine: a guided NED/Exec problem-solving session that walks `Surface → Depth → Synthesis → Lock-in`, with curated comparables and three handoff targets (Brief / Decks / Cycle).
- **User flow** (per `pages/AppSolve.jsx`, `pages/SolveLanding.jsx`, `routers/solve_engine.py:1-28`):
  1. Pick a cluster (taxonomy seeded by `solve_clusters_seed.py`) + state intent (20–1200 chars).
  2. Backend creates a session; user posts one turn per phase (`POST /sessions/{sid}/turn`).
  3. Synthesis phase pulls 2–3 anonymised "comparable diagnoses" from `db.solve_comparables` (seeded by `solve_comparables_seed.py`, indexed on `cluster_id + sector_tag`).
  4. Lock-in phase produces a structured artefact ready for handoff.
  5. Handoff trio: `→ /handoff/brief` (creates a Catch-up brief), `→ /handoff/decks` (Studio outline), `→ /handoff/cycle` (drops 1–3 questions into question bank).
  6. Save & resume native (`GET /sessions` returns recent + in-progress).
  7. Pro tier (Opus) vs Free (Sonnet) gating via `/pro-status` and `db.solve_free_grants` monthly grant.
- **Backend**: `/app/backend/routers/solve_engine.py` (1052 lines), `/app/backend/routers/solve.py` (interest capture only), `/app/backend/solve_clusters_seed.py`, `/app/backend/solve_comparables_seed.py`, `/app/backend/solve_pdf.py`.
  - `GET /api/solve/clusters` — taxonomy
  - `GET /api/solve/pro-status` — plan gating
  - `POST /api/solve/sessions` — start
  - `GET /api/solve/sessions` — list
  - `GET /api/solve/sessions/{sid}` — fetch
  - `POST /api/solve/sessions/{sid}/turn` — advance phase
  - `POST /api/solve/sessions/{sid}/restart` — clone
  - `POST /api/solve/sessions/{sid}/abandon` — soft-archive
  - `POST /api/solve/sessions/{sid}/handoff/brief|decks|cycle`
  - `GET  /api/solve/sessions/{sid}/handoffs`
  - `GET  /api/solve/sessions/{sid}/export.pdf` — PDF via `solve_pdf.py`
  - `POST /api/solve/interest`, `GET /api/solve/interest/me` (interest list pre-Pro)
- **Frontend**: `pages/SolveLanding.jsx`, `pages/AppSolve.jsx`.
- **Data**: `db.solve_clusters`, `db.solve_comparables`, `db.solve_sessions`, `db.solve_handoffs`, `db.solve_free_grants`, `db.solve_interest`, `db.llm_deep_usage` (Pro Opus quota).
- **Integrations**: LLM tiers — `tier=standard` (Sonnet 4.5) for free, `tier=deep` (Opus) for Pro, `tier=fast` (Gemini Flash) for validation. Feeds the Studio + Cycle + Briefs.
- **Status**: **production**. The audit notes the Pro flip via Stripe webhook is partial (P1 carry-over).

### 3.3 Studio — Decks + Reports + Briefings (read-receipts + sensitivity)

- **Purpose**: Single distribution surface for everything generated in AKKI's voice. Auto-classifies sensitivity (public/internal/confidential/restricted), tracks read-receipts, computes an "Exposure Score", supports tracked external email shares (Share-with-the-Chair, iter68).
- **User flow** (per `pages/Decks.jsx`, `routers/studio.py`, `routers/decks.py`):
  1. From Solve / Brief / direct prompt, build a deck **outline** (`POST /api/contexts/{cid}/decks/outline`).
  2. Confirm and **generate** the deck (`POST .../decks/{outline_id}/generate` — uses Opus tier on Pro plan).
  3. Auto-sensitivity scoring (`studio_sensitivity.py`) regex pass + optional LLM tiebreaker for the ambiguous "internal" band (iter66, opt-in via query param per audit).
  4. View tracked per `(artefact_kind, artefact_id, account_id, day_utc)` unique upsert (`db.studio_views`).
  5. Share via `POST .../studio/{kind}/{aid}/share-email` → Resend; recipient gets a JWT-signed tracker `GET /api/public/studio/track/{token}` → 302 to deep link, **non-AKKI recipient** clicks roll up into `account_id = external:<sha256(email)>`.
  6. Quality check (`POST .../decks/{deck_id}/quality_check`) and feedback (`POST .../decks/{deck_id}/feedback`).
- **Backend**: `/app/backend/routers/studio.py` (801 lines), `/app/backend/routers/decks.py` (615 lines), `/app/backend/studio_sensitivity.py`, `/app/backend/reports_service.py` (Reports composition, polish, send-up).
  - `POST /api/public/studio/sensitivity-demo` — landing-page live demo, regex-only, IP rate-limited
  - `POST /api/contexts/{cid}/studio/{kind}/{aid}/view`
  - `GET  /api/contexts/{cid}/studio/{kind}/{aid}/engagement`
  - `POST /api/contexts/{cid}/studio/{kind}/{aid}/share`
  - `POST /api/contexts/{cid}/studio/{kind}/{aid}/share-email`
  - `POST /api/contexts/{cid}/studio/{kind}/{aid}/rescore`
  - `POST /api/contexts/{cid}/studio/backfill_sensitivity`
  - `GET  /api/contexts/{cid}/studio/history`
  - `GET  /api/public/studio/track/{token}` — tracker (302 redirect)
  - `GET  /api/public/studio/read/{token}` — public read view (planned per audit P1)
  - Decks: `outline`, `generate`, `quality_check`, `feedback`, `GET /decks`, `GET /decks/{deck_id}`, `GET /decks/{deck_id}/context`
- **Frontend**: `pages/Decks.jsx`, `components/studio/ShareArtefactModal.jsx`. Sensitivity demo on `pages/Landing.jsx`.
- **Data**: `db.decks`, `db.deck_outlines`, `db.deck_telemetry`, `db.studio_views`, `db.studio_shares`, `db.briefings`, `db.reports`.
- **Integrations**: Resend (Share-with-Chair email), JWT (14-day tracker token), LLM Opus for deck generation.
- **Status**: **production for AKKI users**, **partial** for external recipients — clicking a tracker lands them on `/app/decks/:id` which bounces to `/signin` (audit calls this out as P1: build a public read-only artefact view).

### 3.4 Briefings (formal) + Briefs (Catch-up / Prepare)

> Note: codebase has **two distinct collections** — `db.briefings` (formal,
> 1–2 page meeting briefings, M12) and `db.briefs` (lightweight Catch-up
> briefs created in the Prepare surface). The audit flags this naming
> as a P2 cleanup.

- **Purpose (Briefings)**: A 1–2 page document a NED/Executive can take into a meeting, bundling AKKI's opening paragraph, signal-by-signal evidence, and the sharp question to ask. PDF + DOCX export via `reportlab` and `python-docx`.
- **Backend**:
  - **Briefings (formal)** — `routers/briefings.py` (427 lines), `briefings_service.py` (669 lines).
    - `POST /api/contexts/{cid}/briefings` — create
    - `GET / DELETE /api/contexts/{cid}/briefings(/{bid})`
    - `POST /api/contexts/{cid}/briefings/{bid}/mark-read`
    - `POST /api/contexts/{cid}/briefings/{bid}/speaking-notes`
    - `GET /api/contexts/{cid}/briefings/{bid}/export` — PDF/DOCX/text
  - **Briefs (Catch-up / Prepare)** — `routers/prepare.py` (534 lines).
    - `GET /api/prepare/brief-kinds`
    - `POST /api/contexts/{cid}/briefs`
    - `GET / DELETE /api/contexts/{cid}/briefs(/{brief_id})`
    - `GET /api/contexts/{cid}/minutes`
    - `POST /api/contexts/{cid}/minutes/{doc_id}/extract` — Minutes-as-first-class, derives questions
    - `POST /api/contexts/{cid}/minutes/{doc_id}/to_cycle`
    - `POST /api/contexts/{cid}/minutes/{doc_id}/narrative`
- **Frontend**: `pages/Prepare.jsx`, `components/prepare/PrepareSideRail.jsx`, `PrepareStatsDock.jsx`.
- **Data**: `db.briefings`, `db.briefs`, `db.briefing_reads`.
- **Integrations**: LLM (Sonnet for body, Gemini Flash for validator countercheck — iter49). PDF/DOCX export.
- **Status**: **production**. Validator badge visible across surfaces but the *real* second-LLM call is only wired on Briefings per audit (P1 drift).

### 3.5 Cycle — Reporting Cycles, Reportees, Submissions, Reports

- **Purpose**: Turn the messy "what did your team submit for the board pack" workflow into a checklisted, dispatched, consolidated report flow.
- **User flow** (`routers/cycle.py:1-20` + `pages/Cycle.jsx`):
  1. Define **questions** (manually or seed from briefings).
  2. Add **reportees** (direct reports).
  3. Generate **checklists** per reportee + dispatch via Resend (`/checklists/dispatch`).
  4. Each reportee gets a tokenised public link `/respond/{token}` (`pages/RespondToChecklist.jsx`).
  5. **Submissions** flow back; executive consolidates → **Reports** (compose, polish, send-up, review, export).
  6. Recurring cycles via `cycle/schedule` cron (`POST /api/cycle/cron/run-schedules`).
- **Backend**: `/app/backend/routers/cycle.py` (1577 lines — biggest router).
  - Questions: `GET / POST / PATCH /contexts/{cid}/questions`, `seed-from-briefings`
  - Reportees: `GET / POST / DELETE /contexts/{cid}/reportees`
  - Checklists: `generate`, `GET / PATCH /checklists`, `/dispatch`
  - Public response: `GET / POST /respond/{token}`
  - Submissions: `GET /contexts/{cid}/submissions`
  - Reports: `compose`, `GET /reports`, `GET / PATCH /reports/{rid}`, `send_up`, `review`, `polish`, `export.pdf`, `export.deck.pdf`
  - Inbox: `GET /reports/inbox`
  - Committees calendar: `GET /cycle/committees`
  - Schedule: `GET / PUT / DELETE /cycle/schedule`, cron runner
- **Frontend**: `pages/Cycle.jsx`, `pages/RespondToChecklist.jsx`, `components/cycle/CycleTracker.jsx`, `PolishDiffModal.jsx`, `ReportsTab.jsx`, `ReviewInboxCard.jsx`.
- **Data**: `db.questions`, `db.reportees`, `db.checklists`, `db.submissions`, `db.reports`, `db.cycle_schedules`, `db.committees` (committee scoping).
- **Integrations**: Resend (checklist email — `email_service.render_checklist_email_html`); reportees can reply by email which Postmark inbound routes back (cycle reply ingestion is marked as a stub in `routers/cycle.py:15`).
- **Status**: **production** for happy path; **stub** for email-reply ingestion.

### 3.6 Documents — upload, extract, viewer, engagement

- **Purpose**: First-class document store; PDFs / DOCX / TXT / MD / RTF up to 25MB; extraction → BM25-indexed grounding; per-doc summary, evolution diff, threaded comments.
- **Backend**:
  - `routers/documents.py` (585 lines): upload (`POST /contexts/{cid}/documents`), generate-meta, summary, thread, list, get/patch/delete, evolution-diff, download.
  - `routers/document_engagement.py` (282 lines): view (`POST .../view`), share (`POST .../share`), engagement (`GET .../engagement`).
  - `documents_service.py`: `virus_scan_stub` (EICAR-only — real ClamAV deferred), local-disk storage rooted at `UPLOADS_DIR` (default `/app/backend/uploads`), `extract_text`, `make_preview`.
- **Frontend**: `pages/DocumentViewer.jsx`, `components/documents/*` (DocLensRail, DocumentEngagement, DocumentEvolutionPanel, DocumentJournalStats, DocumentPlayContext, DocumentSummaryCard, DocumentSummaryPanel, DocumentThread), `components/upload/UploadModal.jsx`.
- **Data**: `db.documents`, `db.document_views` (uniq on `doc_id+account_id+day`), `db.document_shares`.
- **Integrations**: pypdf, python-docx, BM25 (`bm25.py`).
- **Status**: **production** for ingest/read; **virus-scan is a stub** (only catches EICAR test signature — `documents_service.py:26`).

### 3.7 Signals + Ask + BM25 grounding (M5 / M13)

- **Purpose**: Generate evidence-cited Risk/Gap/Opportunity signals from ingested docs; ask questions of the corpus with the same grounding contract.
- **Backend**: `routers/signals_ask.py` (301 lines), `routers/signal_actions.py` (199 lines), `routers/admin_signal_kpi.py`.
  - `POST /api/contexts/{cid}/signals/generate` — produce signals
  - `GET / DELETE /api/contexts/{cid}/signals(/{sid})`
  - `POST / GET /api/contexts/{cid}/ask`
  - `GET /api/contexts/{cid}/signals/{sid}/recommendations`
  - `POST / GET /api/contexts/{cid}/signals/{sid}/actions`
  - Admin: `GET /api/admin/signals/action-heatmap`
- **Frontend**: `components/ask/AskPanel.jsx`, signals woven into Home + Workspace pages.
- **Data**: `db.signals`, `db.ask_messages`, `db.signal_actions`, `db.signal_events`.
- **Integrations**: LLM (Sonnet) shielded via `llm_service.shield_payload`; BM25 retrieval (M13).
- **Status**: **production**.

### 3.8 Lens (analytical lenses) + Simulate

- **Purpose**: Apply named "lenses" (analytical viewpoints) to a context; run simulations against scenarios; coach sessions inside the Lens room.
- **Backend**: `routers/lens.py` (384 lines), `routers/simulate.py` (205 lines).
  - Lens: `GET /api/lens/catalog`, `POST /api/contexts/{cid}/lens/run`, `GET / DELETE .../lens/runs(/{rid})`, coach sessions CRUD + messages.
  - Simulate: `POST/GET/DELETE /api/contexts/{cid}/simulations(/{sid})`.
- **Frontend**: `pages/LensRoom.jsx`, `pages/Simulate.jsx`, `components/lens/AllLensesModal.jsx`.
- **Data**: `db.lens_runs`, `db.lens_coach_sessions`, `db.simulations`.
- **Integrations**: LLM (standard tier), shielding.
- **Status**: **production**.

### 3.9 Plays (Workflows)

- **Purpose**: Editorially-cadenced multi-stage flows (e.g. "Board Pack Play"). Stages are **named, not numbered** (per audit's experience rules).
- **Backend**: `routers/plays.py` (476 lines).
  - `GET /api/plays/library`
  - `GET / POST /api/contexts/{cid}/plays(/{pid})`
  - `POST /plays/{pid}/advance|jump|pause|resume|seen|exit|pre_board/read`
  - `PATCH /plays/{pid}/state`
- **Frontend**: `pages/PlaysLibrary.jsx`, `pages/PlayView.jsx`, `components/plays/BoardPackStages.jsx`, `PreBoardStages.jsx`, `components/home/PlayReadyCards.jsx`, `PlaysInProgressStrip.jsx`, `WorkflowsHub.jsx`.
- **Data**: `db.plays`.
- **Status**: **production**, but audit calls out 3 entry points (`/app/plays`, Home PlayReady, Studio ActiveWorkflowsRail) as redundant — P2 cosmetic.

### 3.10 Chat — multi-model with shielded audit

- **Purpose**: Personal AI conversation surface, untethered from a specific context; auto-shielding via Synisense regex masker; bank-grade SHA-chained audit log + zip export.
- **Backend**: `routers/chat.py` (676 lines).
  - `GET /api/chat/models` — supported set
  - `POST /api/chats`, `GET /chats`, `GET /chats/{cid}`, `PATCH /chats/{cid}`, `DELETE /chats/{cid}`
  - `POST /api/chats/{cid}/messages`
  - `GET /api/chats/{cid}/audit`, `GET /api/chats/{cid}/audit/export.zip`
- **Frontend**: `pages/Chat.jsx`, `components/chat/ModelAvatar.jsx`.
- **Models exposed** (`routers/chat.py:48-58`): Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`), Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), GPT-5.2 (`gpt-5.2`), Gemini 2.5 Pro, Gemini 2.5 Flash. Default = Claude Sonnet 4.5.
- **Data**: `db.chats`, `db.chat_messages`, `db.chat_audit_log`.
- **Integrations**: Emergent Universal Key → emergentintegrations.LlmChat; shielding policy `auto | always | off`.
- **Status**: **production**. The audit zip ships with `verify.py` for chain verification.

### 3.11 Influence Map

- **Purpose**: Read-only graph layer that aggregates engagement across documents/shares/comments to show "who is reading, sharing, mentioning what".
- **Backend**: `routers/influence_map.py` (450 lines).
  - `GET /api/contexts/{cid}/influence-map?days=30`
  - `POST /api/contexts/{cid}/influence-map/digest`
  - `POST /api/cron/weekly-digest` — Monday 08:00 UTC scheduler hook
- **Frontend**: `pages/InfluenceMap.jsx`.
- **Data**: aggregated query layer over `db.document_views`, `db.shares`, `db.collab_comments`, `db.mentions`. **No new collection.**
- **Integrations**: Resend (weekly digest email).
- **Status**: **production**.

### 3.12 Inbound Email (Postmark)

- **Purpose**: Each user/context gets a unique mailbox `inbound+<account_token>[.<context_token>]@<INBOUND_DOMAIN>`. Forward an email (with attachments) → it becomes a first-class AKKI document.
- **Backend**: `routers/inbound_email.py` (496 lines), `routers/inbound_queue.py` (338 lines).
  - `GET /api/inbound/address` — fetch user's inbound address
  - `POST /api/inbound/postmark` — Postmark webhook receiver, verifies via `?secret=…` shared secret
  - Inbound triage queue (iter70): `GET /api/contexts/{cid}/inbound-queue`, `GET /api/me/inbound-queue/counts`, `GET /inbound-queue/{qid}`, `POST /accept`, `POST /reject`
- **Frontend**: `pages/InboundQueue.jsx`, `components/home/InboundQueueCard.jsx`, `components/settings/InboundEmailPanel.jsx`.
- **Data**: `db.documents`, `db.inbound_queue`, `db.inbound_queue_raw`, sparse `inbound_token` indexes on `db.accounts` and `db.contexts`.
- **Integrations**: **Postmark** (envelope verified by shared secret per `routers/inbound_email.py:50-55` — falls back to `POSTMARK_SERVER_TOKEN` if `POSTMARK_WEBHOOK_SECRET` unset).
- **Status**: **production** (live per audit). Trust-tiered queue triage shipped iter70.

### 3.13 Auth & Accounts

- **Purpose**: Email/password + JWT (access ~8h, refresh 7d) + optional TOTP MFA. Cookie-first with Bearer fallback (Safari/Brave-friendly per `core.py:72-94`).
- **Backend**: `routers/auth.py` (236 lines), `core.py` (auth helpers + `get_current_account` dependency + `auth_events` sampled observability).
  - `POST /api/auth/register` — creates account + provisions personal context
  - `POST /api/auth/login` — 5-attempt lockout (15-min) per `db.login_attempts`
  - `POST /api/auth/logout`, `POST /api/auth/refresh`
  - `GET /api/auth/me` — account + decorated contexts (with `my_role`)
  - `POST /api/auth/declare-role` — ned / executive / dual / undeclared
  - `POST /api/auth/mfa/setup` — generates TOTP secret + QR data URL
  - `POST /api/auth/mfa/verify`, `POST /api/auth/mfa/disable`
- **Frontend**: `contexts/AuthContext.jsx`, `pages/SignIn.jsx`, `pages/SignUp.jsx`, `pages/AccountSecurity.jsx`, `pages/Onboarding.jsx`, `pages/InviteAccept.jsx`, `components/ProtectedRoute.jsx`.
- **Data**: `db.accounts`, `db.login_attempts`, `db.auth_events` (sampled 1% successes + all failures), `db.consent_decisions`, `db.invitations`.
- **Integrations**: bcrypt, PyJWT (HS256), pyotp + qrcode for TOTP, optional auth-events admin dashboard.
- **Status**: **production**. Iter59 fixed cookie-poisoning (try-every-credential ordering).

### 3.14 Contexts, Memberships, Committees, Invitations

- **Purpose**: A "context" is a board / company-seat. Memberships scope role; committees scope a sub-board; invitations bring colleagues in.
- **Backend**: `routers/contexts.py` (500 lines), `routers/committees.py` (97 lines).
  - Account: `PATCH /api/accounts/me`, `POST /api/accounts/me/default-context`, `GET /api/accounts/me/consent-decisions`
  - Contexts CRUD: `POST / GET / PATCH / DELETE /api/contexts(/{cid})`, leave, members CRUD, invitations CRUD, accept-by-token
  - Context-object (M2 onboarding state): `GET / POST /api/contexts/{cid}/context-object`
  - Presets: `GET /api/presets/industries`, `GET /api/presets/jurisdictions`
  - Committees: `GET / POST /api/contexts/{cid}/committees`, `PATCH / DELETE /committees/{committee_id}`
- **Frontend**: `pages/ContextPortfolio.jsx`, `pages/NewWorkspace.jsx`, `pages/InviteAccept.jsx`, `pages/TenantSettings.jsx`, `components/settings/CommitteeManager.jsx`, `components/layout/PortfolioRail.jsx`.
- **Data**: `db.contexts`, `db.memberships`, `db.organisations`, `db.invitations`, `db.context_objects`, `db.committees`, `db.consent_decisions`, `db.audit_log`, `db.telemetry_events`.
- **Integrations**: Resend (invitation email — note `routers/contexts.py:404` logs a `[invite-email-stub]` line; whether Resend is wired here is **unclear** — looks like a logging fallback when Resend not configured).
- **Status**: **production**.

### 3.15 Strategic Goals + Monitor

- **Purpose**: Track strategic goals against where the company actually is; visualise score history.
- **Backend**: `routers/strategic_goals.py` (364 lines), `routers/monitor.py` (236 lines).
  - `GET / POST / PATCH / DELETE /api/contexts/{cid}/strategic-goals(/{goal_id})`
  - `POST /api/contexts/{cid}/strategic-goals/extract` — derive goals from documents
  - `GET /api/contexts/{cid}/monitor` — composite monitor dashboard
- **Frontend**: `pages/Monitor.jsx`, `components/monitor/StrategicGoalsPanel.jsx`, `Sparkline.jsx`.
- **Data**: `db.strategic_goals`.
- **Status**: **production**.

### 3.16 Pipeline, Audit, Synisense (trust)

- **Backend**:
  - `routers/pipeline.py` (330 lines): `POST /api/contexts/{cid}/pipeline/run`, `GET .../pipeline/events` — trace strip on every LLM-backed answer.
  - `routers/audit.py`: `GET /api/contexts/{cid}/audit-log`, `POST /api/contexts/{cid}/export`.
  - `routers/synisense.py` (125 lines): `GET /api/synisense/status`, `POST /api/synisense/dryrun`. Mock today; real service swaps via URL.
- **Frontend**: `components/trace/CompositionStrip.jsx`, `components/trust/ValidatedBadge.jsx`.
- **Status**: **production scaffold**, **mock-Synisense** (per `pages/TenantSettings.jsx:849-850`: "Running in mock-scaffolding mode. A live Synisense service replaces the mock at M5.").

### 3.17 Comments + Mentions (collab)

- **Backend**: `routers/comments.py` (275 lines).
  - `GET / POST /api/contexts/{cid}/{artefact_type}/{artefact_id}/comments`
  - `DELETE /api/contexts/{cid}/comments/{comment_id}`
  - `GET /api/contexts/{cid}/mentions`, `POST /api/contexts/{cid}/mentions/{mention_id}/read`
- **Frontend**: `components/collab/CommentThread.jsx`, `MentionInbox.jsx`.
- **Data**: `db.comments` (and/or `db.collab_comments`), `db.mentions`.
- **Status**: **production**.

### 3.18 Shares (artefact distribution + Home stream)

- **Backend**: `routers/shares.py` (454 lines).
  - `POST /api/contexts/{cid}/shares` — share an artefact in-app
  - `GET /api/me/shares/inbox`, `GET /api/me/shares/outbox`
  - `GET /api/shares/{share_id}`, `DELETE /api/shares/{share_id}`
  - `GET /api/me/home/stream` — aggregated cross-board stream
  - Public: `GET /shared/:token` (frontend route → `pages/SharedArtefact.jsx`)
- **Frontend**: `components/share/ShareModal.jsx`, `pages/SharedArtefact.jsx`, `components/stream/StreamCard.jsx`.
- **Data**: `db.shares`.
- **Status**: **production**. ShareModal log shows email is "stub logged — SMTP delivery ships with email-in integration" (`components/share/ShareModal.jsx:96`) — i.e. in-app share is real, **outbound email on this surface is a stub** distinct from the Studio share-with-Chair (which is real Resend).

### 3.19 Decks (handled inside Studio above) + Reports + Polish

Already covered under **3.3 Studio** and **3.5 Cycle**. Reports include polish-with-AKKI editor (`POST /reports/{rid}/polish`) and chained send-up.

### 3.20 Walk-In ("walk-in question" surfacing)

- **Backend**: `routers/walkin.py` (205 lines).
  - `POST /api/walkin` — generate walk-in question
  - `POST /api/walkin/regenerate`
- **Frontend**: `components/walkin/WalkInCard.jsx`.
- **Status**: **production**.

### 3.21 Agenda Evolution

- **Backend**: `routers/agenda.py`: `GET /api/contexts/{cid}/agenda-evolution`.
- **Frontend**: `components/home/AgendaEvolutionCard.jsx`.
- **Status**: **production**.

### 3.22 Learn

- **Backend**: `routers/learn.py` (132 lines): `POST /api/learn/research`.
- **Frontend**: `pages/Learn.jsx`, `lib/learnContent.js`, `components/learn/LearnMoreModal.jsx`, `VideoModal.jsx`.
- **Status**: **production**.

### 3.23 Blog — "Exco360" editorial series

- **Purpose**: Weekly research-driven posts authored by AKKI's voice. Public read; admin compose/publish; Resend-backed email fan-out to subscribers; auto-cron each Tuesday 10:00 UTC.
- **Backend**: `routers/blog.py` (747 lines).
  - Public: `GET /api/blog/posts`, `GET /api/blog/posts/{slug}`, `POST /api/blog/subscribe`, `GET /api/blog/rss`
  - Admin: `POST /api/blog/compose`, `POST /api/blog/posts/{slug}/publish`, `DELETE /api/blog/posts/{slug}`, `GET /api/blog/admin/posts/{slug}`, `GET /api/blog/subscribers`, `POST /api/blog/seed/launch-10`
  - Cron: `POST /api/blog/cron/weekly` (gated by `X-Cron-Secret`)
- **Frontend**: `pages/marketing/Blog.jsx`, `BlogPost.jsx`, `BlogAdmin.jsx`.
- **Data**: `db.blog_posts`, `db.blog_subscribers`.
- **Integrations**: Emergent LLM Key (deep tier for compose), Resend (publish fan-out), APScheduler.
- **Status**: **production**.

### 3.24 Billing (Stripe via Emergent)

- **Backend**: `routers/billing.py` (287 lines).
  - `GET /api/billing/plans` — fixed catalog (Free / Pro / Team)
  - `GET /api/billing/me`, `POST /api/billing/checkout`, `GET /api/billing/status/{session_id}`
  - `POST /api/webhook/stripe`
- **Frontend**: `components/settings/BillingTab.jsx`, `pages/TenantSettings.jsx`.
- **Data**: `db.payment_transactions`.
- **Integrations**: `STRIPE_API_KEY` → `emergentintegrations.payments.stripe.checkout.StripeCheckout`. Returns 503 if unset (`routers/billing.py:94-100`).
- **Status**: **partial**. The audit (§4.1) flags that the webhook flips `account.plan = "pro"` but **Solve Pro affordance still requires a manual flip** — close-the-loop is a P1 carry-over.

### 3.25 Enterprise + Solve Interest capture

- **Backend**: `routers/enterprise.py` (`POST /api/enterprise/interest`, `GET /api/enterprise/interest/me`), `routers/solve.py` (Solve interest: `POST /api/solve/interest`, `GET /me`).
- **Frontend**: `pages/Enterprise.jsx`, `components/marketing/EnterpriseFeature.jsx`.
- **Data**: `db.enterprise_interest`, `db.solve_interest`.
- **Status**: **production**.

### 3.26 Marketing site

- **Frontend pages**: `pages/marketing/About.jsx`, `Features.jsx`, `Security.jsx`, `Blog.jsx`, `BlogPost.jsx`, `BlogAdmin.jsx`; `pages/Landing.jsx`, `pages/SolveLanding.jsx`.
- **Components**: `components/marketing/HeroSection.jsx`, `ThreePillars.jsx`, `EnterpriseFeature.jsx`, `MarketingShell.jsx`.
- **Public APIs surfaced**: `/api/public/studio/sensitivity-demo`, blog posts, RSS.
- **Status**: **production**.

### 3.27 Admin dashboards

- **Backend**:
  - `routers/admin_health.py`: `GET /api/admin/health/full`
  - `routers/admin_auth_events.py`: `GET /api/admin/auth/events`
  - `routers/admin_llm_spend.py`: `GET /api/admin/llm/spend`, `GET /api/admin/llm/decks/quality`
  - `routers/admin_sandbox_kpi.py`: `GET /api/admin/sandbox/kpi`, `GET /api/admin/sandbox/objectives`
  - `routers/admin_signal_kpi.py`: `GET /api/admin/signals/action-heatmap`
  - `routers/llm_quota.py`: `GET /api/llm/quota`
- **Frontend**: `pages/admin/AdminIndex.jsx`, `HealthDashboard.jsx`, `SandboxKPI.jsx`, `SignalKPI.jsx`, `LLMSpend.jsx`, `AuthEvents.jsx`.
- **Data**: `db.auth_events`, `db.llm_deep_usage`, `db.deck_telemetry`, `db.sandbox_pickups`, `db.signal_events`.
- **Status**: **production**, gated by `is_superadmin` flag on the admin seed account.

### 3.28 Misc

- `routers/misc.py`: `GET /api/`, `GET /api/health`, `POST /api/contexts/{cid}/llm/probe`, `POST /api/events` (telemetry).

---

## 4. API Endpoints Summary

> 200+ routes total across 43 routers. Table is grouped by router for readability. Auth column: **C** = `get_current_account` cookie/Bearer; **M** = `require_context_membership`; **P** = public; **S** = shared-secret (cron / webhook); **A** = admin / superadmin.

| Router file | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| `auth.py` | POST | `/api/auth/register` | P | Create account + default context |
| `auth.py` | POST | `/api/auth/login` | P | Email/password → JWT cookies |
| `auth.py` | POST | `/api/auth/logout` | C | Clear cookies |
| `auth.py` | POST | `/api/auth/refresh` | (refresh cookie) | Rotate access token |
| `auth.py` | GET | `/api/auth/me` | C | Account + contexts |
| `auth.py` | POST | `/api/auth/declare-role` | C | Set ned / executive / dual |
| `auth.py` | POST | `/api/auth/mfa/setup` | C | TOTP secret + QR |
| `auth.py` | POST | `/api/auth/mfa/verify` | C | Confirm 6-digit code |
| `auth.py` | POST | `/api/auth/mfa/disable` | C | Disable MFA |
| `contexts.py` | PATCH | `/api/accounts/me` | C | Update profile |
| `contexts.py` | POST | `/api/accounts/me/default-context` | C | Set default context |
| `contexts.py` | POST | `/api/contexts/{cid}/leave` | M | Leave membership |
| `contexts.py` | GET | `/api/accounts/me/consent-decisions` | C | Audit |
| `contexts.py` | GET | `/api/presets/industries` / `/jurisdictions` | C | M2 onboarding presets |
| `contexts.py` | GET/POST | `/api/contexts/{cid}/context-object` | M | M2 onboarding state |
| `contexts.py` | POST/GET/PATCH/DELETE | `/api/contexts(/{cid})` | C/M | CRUD |
| `contexts.py` | GET/DELETE | `/api/contexts/{cid}/members(/{aid})` | M | Members |
| `contexts.py` | POST/GET/DELETE | `/api/contexts/{cid}/invitations(/{iid})` | M | Invitations |
| `contexts.py` | GET/POST | `/api/invitations/by-token/{token}` / `/accept` | P | Accept invite |
| `committees.py` | GET/POST/PATCH/DELETE | `/api/contexts/{cid}/committees(/{committee_id})` | M | Committees |
| `documents.py` | POST | `/api/contexts/{cid}/documents/generate-meta` | M | LLM-meta |
| `documents.py` | POST | `/api/contexts/{cid}/documents/{did}/summary` | M | Summary |
| `documents.py` | POST | `/api/contexts/{cid}/documents` | M | Upload |
| `documents.py` | GET/PATCH/DELETE | `/api/contexts/{cid}/documents(/{did})` | M | CRUD |
| `documents.py` | GET | `/api/contexts/{cid}/documents/{did}/thread` / `/download` | M | Read |
| `documents.py` | POST | `/api/contexts/{cid}/documents/{did}/evolution-diff` | M | Versioning |
| `document_engagement.py` | POST | `/api/contexts/{cid}/documents/{did}/view` / `/share` | M | Track |
| `document_engagement.py` | GET | `/api/contexts/{cid}/documents/{did}/engagement` | M | Read receipts |
| `signals_ask.py` | POST | `/api/contexts/{cid}/signals/generate` | M | Generate signals |
| `signals_ask.py` | GET/DELETE | `/api/contexts/{cid}/signals(/{sid})` | M | List / del |
| `signals_ask.py` | POST/GET | `/api/contexts/{cid}/ask` | M | Q&A grounding |
| `signal_actions.py` | GET/POST | `/api/contexts/{cid}/signals/{sid}/recommendations` / `/actions` | M | Action loop |
| `briefings.py` | POST/GET/DELETE | `/api/contexts/{cid}/briefings(/{bid})` | M | CRUD |
| `briefings.py` | POST | `/api/contexts/{cid}/briefings/{bid}/mark-read` / `/speaking-notes` | M |  |
| `briefings.py` | GET | `/api/contexts/{cid}/briefings/{bid}/export` | M | PDF/DOCX |
| `prepare.py` | GET | `/api/prepare/brief-kinds` | C | Catalog |
| `prepare.py` | POST/GET/DELETE | `/api/contexts/{cid}/briefs(/{bid})` | M | Catch-up briefs |
| `prepare.py` | GET/POST | `/api/contexts/{cid}/minutes` / `/{did}/extract,to_cycle,narrative` | M | Minutes-as-first-class |
| `cycle.py` | GET/POST/PATCH | `/api/contexts/{cid}/questions(/{qid})` | M | Question bank |
| `cycle.py` | POST | `/api/contexts/{cid}/questions/seed-from-briefings` | M |  |
| `cycle.py` | GET/POST/DELETE | `/api/contexts/{cid}/reportees(/{rid})` | M |  |
| `cycle.py` | POST/GET/PATCH | `/api/contexts/{cid}/checklists(/{cid2})` | M |  |
| `cycle.py` | POST | `/api/contexts/{cid}/checklists/dispatch` | M | Resend email |
| `cycle.py` | GET/POST | `/api/respond/{token}` | P (token) | Reportee response |
| `cycle.py` | GET | `/api/contexts/{cid}/submissions` | M |  |
| `cycle.py` | POST/GET/PATCH | `/api/contexts/{cid}/reports(/{rid})` | M | Reports |
| `cycle.py` | POST | `/reports/{rid}/send_up` / `/review` / `/polish` | M |  |
| `cycle.py` | GET | `/api/reports/inbox` | C | Cross-context |
| `cycle.py` | GET | `/reports/{rid}/export.pdf` / `export.deck.pdf` | M |  |
| `cycle.py` | GET | `/api/contexts/{cid}/cycle/committees` | M |  |
| `cycle.py` | GET/PUT/DELETE | `/api/contexts/{cid}/cycle/schedule` | M |  |
| `cycle.py` | POST | `/api/cycle/cron/run-schedules` | S | Cron |
| `decks.py` | POST | `/api/contexts/{cid}/decks/outline` | M | Outline |
| `decks.py` | POST | `/api/contexts/{cid}/decks/{oid}/generate` | M | Opus deck |
| `decks.py` | POST | `/api/contexts/{cid}/decks/{did}/quality_check` / `/feedback` | M |  |
| `decks.py` | GET | `/api/contexts/{cid}/decks(/{did})` | M | List/get |
| `decks.py` | GET | `/api/decks/{did}/context` | C | Resolve |
| `studio.py` | POST | `/api/public/studio/sensitivity-demo` | P | Landing demo |
| `studio.py` | POST | `/api/contexts/{cid}/studio/{kind}/{aid}/view` / `/share` / `/share-email` / `/rescore` | M | Engagement |
| `studio.py` | GET | `/api/contexts/{cid}/studio/{kind}/{aid}/engagement` | M | Score |
| `studio.py` | POST | `/api/contexts/{cid}/studio/backfill_sensitivity` | M | One-shot |
| `studio.py` | GET | `/api/contexts/{cid}/studio/history` | M | Strip |
| `studio.py` | GET | `/api/public/studio/track/{token}` | P (jwt) | Tracker → 302 |
| `studio.py` | GET | `/api/public/studio/read/{token}` | P (jwt) | Public read |
| `solve_engine.py` | GET | `/api/solve/clusters` / `/pro-status` | C | Taxonomy / plan |
| `solve_engine.py` | POST/GET | `/api/solve/sessions(/{sid})` | C | Session CRUD |
| `solve_engine.py` | POST | `/api/solve/sessions/{sid}/turn` / `/restart` / `/abandon` | C | State machine |
| `solve_engine.py` | POST | `/api/solve/sessions/{sid}/handoff/brief|decks|cycle` | C | Handoff trio |
| `solve_engine.py` | GET | `/api/solve/sessions/{sid}/handoffs` / `/export.pdf` | C |  |
| `solve.py` | POST/GET | `/api/solve/interest(/me)` | P/C | Pre-Pro interest |
| `sandbox.py` | POST | `/api/sandbox/generate` | P | Start session |
| `sandbox.py` | GET | `/api/sandbox/generate/{sid}/status` | P | Poll |
| `sandbox.py` | GET | `/api/sandbox/templates` | P |  |
| `sandbox.py` | POST | `/api/sandbox/cleanup/expired` | A | Maintenance |
| `sandbox.py` | POST/GET | `/api/sandbox/contexts/{cid}/capture-email` / `/tutorial(/dismiss)` / `/sample-doc(/accept)` / `/objective-check` | C |  |
| `sandbox.py` | POST | `/api/sandbox/convert` | C | Sandbox → real |
| `sandbox.py` | POST | `/api/sandbox/contexts/seeded` | A | Bootstrapped flag |
| `chat.py` | GET | `/api/chat/models` | C |  |
| `chat.py` | POST/GET/PATCH/DELETE | `/api/chats(/{cid})` | C | Chats CRUD |
| `chat.py` | POST | `/api/chats/{cid}/messages` | C | Send + reply |
| `chat.py` | GET | `/api/chats/{cid}/audit` / `/audit/export.zip` | C | Bank-grade |
| `lens.py` | GET | `/api/lens/catalog` | C |  |
| `lens.py` | POST/GET/DELETE | `/api/contexts/{cid}/lens/run`, `/lens/runs(/{rid})` | M |  |
| `lens.py` | POST/GET/DELETE | `/api/contexts/{cid}/lens/coach/sessions(/{sid})` | M |  |
| `lens.py` | POST | `/api/contexts/{cid}/lens/coach/sessions/{sid}/messages` | M |  |
| `simulate.py` | POST/GET/DELETE | `/api/contexts/{cid}/simulations(/{sid})` | M |  |
| `plays.py` | GET | `/api/plays/library` | C |  |
| `plays.py` | GET/POST | `/api/contexts/{cid}/plays(/{pid})` | M |  |
| `plays.py` | POST | `/plays/{pid}/advance|jump|pause|resume|seen|exit|pre_board/read` | M | State |
| `plays.py` | PATCH | `/plays/{pid}/state` | M |  |
| `comments.py` | GET/POST | `/api/contexts/{cid}/{type}/{aid}/comments` | M | Threaded |
| `comments.py` | DELETE | `/api/contexts/{cid}/comments/{cid2}` | M |  |
| `comments.py` | GET/POST | `/api/contexts/{cid}/mentions(/{mid}/read)` | M |  |
| `shares.py` | POST | `/api/contexts/{cid}/shares` | M |  |
| `shares.py` | GET/DELETE | `/api/me/shares/(inbox|outbox)` / `/shares/{sid}` | C |  |
| `shares.py` | GET | `/api/me/home/stream` | C | Aggregated cross-board |
| `agenda.py` | GET | `/api/contexts/{cid}/agenda-evolution` | M |  |
| `learn.py` | POST | `/api/learn/research` | C |  |
| `monitor.py` | GET | `/api/contexts/{cid}/monitor` | M |  |
| `strategic_goals.py` | GET/POST/PATCH/DELETE | `/api/contexts/{cid}/strategic-goals(/{gid})` | M |  |
| `strategic_goals.py` | POST | `/api/contexts/{cid}/strategic-goals/extract` | M |  |
| `influence_map.py` | GET | `/api/contexts/{cid}/influence-map` | M |  |
| `influence_map.py` | POST | `/api/contexts/{cid}/influence-map/digest` | M |  |
| `influence_map.py` | POST | `/api/cron/weekly-digest` | S | APScheduler |
| `walkin.py` | POST | `/api/walkin` / `/api/walkin/regenerate` | C |  |
| `pipeline.py` | POST/GET | `/api/contexts/{cid}/pipeline/run` / `/pipeline/events` | M | Trace strip |
| `audit.py` | GET | `/api/contexts/{cid}/audit-log` | M |  |
| `audit.py` | POST | `/api/contexts/{cid}/export` | M |  |
| `synisense.py` | GET/POST | `/api/synisense/status` / `/dryrun` | C | Mock layer |
| `blog.py` | GET | `/api/blog/posts(/{slug})` | P |  |
| `blog.py` | POST | `/api/blog/subscribe` | P |  |
| `blog.py` | POST | `/api/blog/compose` / `/posts/{slug}/publish` | A |  |
| `blog.py` | POST | `/api/blog/cron/weekly` | S | APScheduler |
| `blog.py` | POST | `/api/blog/seed/launch-10` | A |  |
| `blog.py` | DELETE | `/api/blog/posts/{slug}` | A |  |
| `blog.py` | GET | `/api/blog/admin/posts/{slug}` / `/subscribers` | A |  |
| `blog.py` | GET | `/api/blog/rss` | P |  |
| `billing.py` | GET | `/api/billing/plans` | P |  |
| `billing.py` | GET | `/api/billing/me` | C |  |
| `billing.py` | POST | `/api/billing/checkout` | C |  |
| `billing.py` | GET | `/api/billing/status/{session_id}` | C |  |
| `billing.py` | POST | `/api/webhook/stripe` | S | Stripe webhook |
| `inbound_email.py` | GET | `/api/inbound/address` | C |  |
| `inbound_email.py` | POST | `/api/inbound/postmark` | S | Postmark webhook |
| `inbound_queue.py` | GET | `/api/contexts/{cid}/inbound-queue` | M |  |
| `inbound_queue.py` | GET | `/api/me/inbound-queue/counts` | C |  |
| `inbound_queue.py` | GET/POST | `/api/contexts/{cid}/inbound-queue/{qid}(/accept,/reject)` | M | Triage |
| `enterprise.py` | POST/GET | `/api/enterprise/interest(/me)` | P/C |  |
| `llm_quota.py` | GET | `/api/llm/quota` | C |  |
| `admin_health.py` | GET | `/api/admin/health/full` | A |  |
| `admin_auth_events.py` | GET | `/api/admin/auth/events` | A |  |
| `admin_llm_spend.py` | GET | `/api/admin/llm/spend` / `/decks/quality` | A |  |
| `admin_sandbox_kpi.py` | GET | `/api/admin/sandbox/kpi` / `/objectives` | A |  |
| `admin_signal_kpi.py` | GET | `/api/admin/signals/action-heatmap` | A |  |
| `misc.py` | GET | `/api/` / `/api/health` | P | Liveness |
| `misc.py` | POST | `/api/contexts/{cid}/llm/probe` / `/api/events` | M/C | Telemetry |

### Frontend routes (`/app/frontend/src/App.js`)

Public: `/`, `/solve`, `/about`, `/features`, `/security`, `/blog`, `/blog/:slug`, `/respond/:token`, `/shared/:token`, `/signin` (+ aliases `/sign-in`, `/login`, `/log-in`), `/signup` (+ aliases), `/invite/:token`, `/sandbox`, `/sandbox/generating/:sessionId`.

Protected: `/onboarding`, `/app`, `/app/cycle`, `/app/monitor`, `/app/plays`, `/app/plays/:playId`, `/app/blog-admin`, `/app/workspace`, `/app/prepare`, `/app/inbound-queue`, `/app/activity`, `/app/simulate`, `/app/lens`, `/app/chat`, `/app/influence`, `/app/quick-results/:cid/:docId`, `/app/learn(/:id)`, `/app/manage`, `/app/enterprise`, `/app/decks(/:deckId)`, `/app/solve`, `/app/documents/:id`, `/app/contexts(/new)`, `/app/new-workspace`, `/app/settings(/billing)`, `/app/security`. Admin: `/admin`, `/admin/health`, `/admin/sandbox-kpi`, `/admin/signal-kpi`, `/admin/llm-spend`, `/admin/auth-events`. Redirects: `/app/highlights → /app/prepare`, `/app/briefings → /app/prepare`, `/app/ask → /app/workspace`. Catch-all → `/`.

---

## 5. Data Model (Mongo Collections)

| Collection | One-line description |
|---|---|
| `accounts` | Users; bcrypt password, MFA, role, plan, sandbox flag, default context, inbound token. |
| `memberships` | Account ↔ context links; role (`ned`/`executive`), `sub_role`, `provisioning`, `data_ownership`, `status`. |
| `organisations` | Sponsoring orgs (when context type is org-provisioned). |
| `contexts` | Boards / company seats; `type` (executive_personal / sandbox / ned_*), industry, jurisdiction, sector, committees, progress_state. |
| `committees` | (Embedded in `contexts.committees` and/or this collection — committee CRUD). |
| `context_objects` | M2 onboarding answers; versioned per context, used as LLM grounding. |
| `consent_decisions` | Per-(account, context) consent capture for audit. |
| `invitations` | Tokenised invites to contexts. |
| `audit_log` | Immutable audit trail per context. |
| `telemetry_events` | Product telemetry. |
| `auth_events` | Sampled auth observability (1% successes + all failures). |
| `login_attempts` | Lockout tracker (5 attempts → 15min lock). |
| `documents` | Uploaded + inbound docs; extracted text, trust band, status. |
| `document_views` | Read receipts on docs (uniq on `doc_id+account_id+day`). |
| `document_shares` | Outbound shares of docs. |
| `signals` | Risk/Gap/Opportunity findings tied to docs. |
| `signal_events` / `signal_actions` | Action loop on signals. |
| `ask_messages` | Free-form Q&A history. |
| `briefings` | Formal 1–2 page meeting briefings (M12). |
| `briefing_reads` | Per-briefing read receipts. |
| `briefs` | Catch-up briefs from the Prepare surface (separate from briefings). |
| `questions` | Reporting-cycle question bank. |
| `reportees` | Direct reports for cycles. |
| `checklists` | Dispatched checklists per reportee. |
| `submissions` | Submitted answers from reportees. |
| `reports` | Composed board reports (with polish + send_up + review). |
| `cycle_schedules` | Recurring cycle definitions. |
| `decks` / `deck_outlines` / `deck_telemetry` | Decks pipeline. |
| `studio_views` / `studio_shares` | Studio engagement (per artefact_kind+artefact_id). |
| `shares` | In-app artefact share inbox/outbox. |
| `comments` (a.k.a `collab_comments`) / `mentions` | Threaded collab. |
| `chats` / `chat_messages` / `chat_audit_log` | AKKI Chat with bank-grade audit. |
| `lens_runs` / `lens_coach_sessions` | Lens Room. |
| `simulations` | Simulate surface. |
| `plays` | Workflow / Play state. |
| `solve_clusters` | Solve taxonomy (seeded). |
| `solve_comparables` | Curated anonymised comparables for Triangulation v2. |
| `solve_sessions` | Solve session state machine. |
| `solve_handoffs` | Brief / Decks / Cycle handoffs from Solve. |
| `solve_free_grants` | Monthly free deep-tier grants for non-Pro users. |
| `solve_interest` | Pre-Pro waitlist. |
| `strategic_goals` | Goals + scores. |
| `llm_deep_usage` | Per-account-day-surface deep-tier (Opus) quota counter. |
| `payment_transactions` | Stripe checkout sessions. |
| `enterprise_interest` | Marketing capture. |
| `blog_posts` / `blog_subscribers` | Exco360. |
| `inbound_queue` / `inbound_queue_raw` | Iter70 trust-tiered triage queue. |
| `sandbox_pickups` | Sandbox follow-up. |
| `health_check` | Used in tests. |

---

## 6. Integrations & External Services

### LLMs (via Emergent Universal Key)

Routed through `/app/backend/llm_service.py` which uses `emergentintegrations.llm.chat.LlmChat`. Three tiers (env-overridable):

| Tier | Provider | Default model | Used by |
|---|---|---|---|
| `fast` | Gemini | `gemini-2.5-flash` (`LLM_MODEL_FAST`) | Validator countercheck, JSON extraction |
| `standard` | Anthropic | `claude-sonnet-4-5-20250929` (`LLM_MODEL_STANDARD`) | Default for briefs, signals, chat, free Solve |
| `deep` | Anthropic | `claude-opus-4-6` (`LLM_MODEL_DEEP`) | Decks, Pro Solve synthesis, blog compose, long-form |

Chat surface additionally exposes Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), GPT-5.2 (`gpt-5.2`), Gemini 2.5 Pro. Default chat model: Claude Sonnet 4.5 (`routers/chat.py:60`).

**Synisense shielding** (regex-based PII masker in `llm_service.shield_payload`): masks emails, URLs, phones, Kenya national IDs, IBANs, bank accounts, credit cards, SWIFT codes, person proper-nouns. Every shielded call returns `shielding: {identifiers_masked, by_category, shielded_by}`. The "live Synisense service" referenced in TenantSettings copy is a planned URL swap — current implementation is the local masker (status: **mock-scaffolding**).

### Email (Resend)

`/app/backend/email_service.py`. From-format: `"AKKI for <Executive Name>" <noreply@…>` with reply-to set to the principal. Used by: cycle checklists, blog publish fan-out, studio share-with-Chair, influence digest, invitations (with stub fallback log line). Returns `{ok, id, mode}` (mode: `sent` / `noop` / `error`) — never raises.

### Inbound mail (Postmark)

`/app/backend/routers/inbound_email.py`. Verifies with `?secret=…` (env `POSTMARK_WEBHOOK_SECRET`, falling back to `POSTMARK_SERVER_TOKEN`). Each user/context gets `inbound+<token>[.<ctx_token>]@<INBOUND_DOMAIN>`.

### Payments (Stripe via emergentintegrations)

`/app/backend/routers/billing.py`. Lazy-imports `emergentintegrations.payments.stripe.checkout.StripeCheckout`. Returns 503 if `STRIPE_API_KEY` unset. Webhook `POST /api/webhook/stripe`. Plan flip is real; downstream Pro feature flip (Solve Pro) is partial per audit §4.

### Scheduler (APScheduler in-process)

Two crons in `server.py:362-417`, gated by `AKKI_CRON_SECRET`:
- Tuesday 10:00 UTC → `POST /api/blog/cron/weekly` (Exco360 draft)
- Monday 08:00 UTC → `POST /api/cron/weekly-digest` (Influence Digest)

### Required environment variables

From `core.py` (hard-required) and `os.environ.get` usages across the backend:

**Hard-required** (`core.py:21-23`): `MONGO_URL`, `DB_NAME`, `JWT_SECRET`.

**Strongly recommended**:
- `EMERGENT_LLM_KEY` (LLM access; without it `llm_service.call_llm` returns `mode=no-key-fallback`)
- `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `RESEND_FROM_NAME`
- `POSTMARK_SERVER_TOKEN`, `POSTMARK_WEBHOOK_SECRET`, `POSTMARK_INBOUND_DOMAIN`
- `STRIPE_API_KEY`
- `AKKI_CRON_SECRET` (otherwise schedulers skip)
- `ADMIN_EMAIL` (default `admin@akki.ai`), `ADMIN_PASSWORD` (default `AkkiAdmin2026!`)
- `CORS_ORIGINS`, `FRONTEND_URL`, `FRONTEND_ORIGIN`
- `APP_NAME` (default `AKKI Sandbox`)
- `UPLOADS_DIR` (default `/app/backend/uploads`)
- `LLM_MODEL_FAST` / `_STANDARD` / `_DEEP`
- `AKKI_AUTH_OBSERVE_RATE` (default 0.01)
- `AKKI_DEEP_UNIT_COST_USD` (default 0.045)
- `AKKI_DEEP_QUOTA_BRIEF` / `_BLOG` / `_DECK` / `_CHAT` / `_VALIDATE` / `_MINUTES` (10/5/3/30/20/5)

**Frontend** (`/app/frontend/src/lib/api.js`): `REACT_APP_BACKEND_URL`.

> Note: at review time **no `.env` files exist** at `/app/backend/.env` or `/app/frontend/.env`. Production deploy expects them per `/app/DEPLOY.md`.

---

## 7. Gaps, TODOs, Mocked Areas

Anchored to code, with cross-reference to `/app/AUDIT_iter68.md`.

1. **Virus scan = stub** (`backend/documents_service.py:26`).
   > "Real ClamAV wires in M4." Only catches the EICAR test signature.

2. **Synisense = local mock** (`backend/llm_service.py:1-9`, `pages/TenantSettings.jsx:849-850`).
   > "Real Synisense service replaces the mock via URL swap in a later build."

3. **Stripe → Solve Pro state flip = partial** (audit §4.1, P1).
   Webhook flips `account.plan` to `pro` but the Solve Pro affordance still requires manual flip — close-the-loop pending.

4. **Validator badge drift = partial** (audit §1, §4.2, P1).
   Real Gemini-Flash countercheck runs only on Briefings; Decks/Reports/Solve syntheses show the "Validated" badge without the second-LLM call.

5. **Cross-Board Pulse claim = soft** (audit §4.3, P1).
   Landing implies a dedicated surface; today it's a toggle on `/app` Home aggregated stream.

6. **Public read-only artefact view = missing** (audit §4.7, P1, introduced by iter68).
   Share-with-Chair tracker lands non-AKKI recipients on `/app/decks/:id` → `/signin`.

7. **Workflows route duplication** (audit §4.5, P2). `/app/plays`, Home PlayReady cards, Studio ActiveWorkflowsRail — three entry points.

8. **`briefings` vs `briefs` collection naming collision** (audit §3 weak link, P2 cosmetic).

9. **Vector DB deferred** (audit §4.4, P2). BM25 today; Pinecone/pgvector later.

10. **Sensitivity LLM tiebreaker is opt-in** (audit §4.6, P2). Iter66 added it for the ambiguous "internal" band but it's gated by query parameter.

11. **Cycle email-reply ingestion = stub** (`routers/cycle.py:15`, "Submissions inbox + reply ingestion stub"). Postmark inbound is live for user-forwards, but routing replies *to* a checklist back into a submission is not wired.

12. **In-app share email = stub** (`components/share/ShareModal.jsx:96`).
    > "Email stub logged — SMTP delivery ships with email-in integration."
    Distinct from the Studio Share-with-Chair surface (real Resend).

13. **Invite email = stub log path** (`routers/contexts.py:404`):
    `[invite-email-stub] to=… link=…`. **Unclear** whether Resend is wired in parallel — the stub log appears unconditionally; recommend confirming during a real deploy.

14. **Sandbox copy admits mock data** (`pages/Sandbox.jsx:279`):
    > "This creates a fictional environment with mock data."
    Intentional, not a defect — flagged for completeness.

15. **`AKKI_CRON_SECRET` unset → schedulers silently skipped** (`server.py:362,419`).
    Operationally fine, but means dev environments don't run weekly crons.

16. **No `.env` files committed** at repo root for either backend or frontend at review time. Bootstrap via `DEPLOY.md` + `/app/backend/scripts/bootstrap_prod.py`.

17. **Test suite = 50+ smoke/iteration tests** under `/app/backend/tests/` — pytest-based; **unclear** how many currently pass without external keys (they likely require `EMERGENT_LLM_KEY`).

---

## 8. File Map

### Backend (`/app/backend/`)

```
server.py                    FastAPI bootstrap, CORS, MongoDB indexes, admin seed, APScheduler
core.py                      Shared infra: db, JWT, auth dep, audit, password, sanitisers, provision_default_context
llm_service.py               Tiered LLM proxy (fast/standard/deep) + Synisense regex shield + validator
email_service.py             Resend wrapper + checklist email HTML renderer
documents_service.py         Local-disk storage, virus_scan_stub, pypdf/python-docx extraction
briefings_service.py         M12 briefing composer + PDF/DOCX/text export
sandbox_service.py           Region/sector profile substitution + seed payload builder
sandbox_templates.py         Curated sector templates (banking, SaaS, logistics, …)
solve_clusters_seed.py       Solve taxonomy seed
solve_comparables_seed.py    Triangulation-v2 anonymised comparables seed
solve_pdf.py                 Solve session PDF export
studio_sensitivity.py        Regex sensitivity scorer (public/internal/confidential/restricted)
reports_service.py           Cycle reports composer + polish + send_up
bm25.py                      Tiny BM25 retrieval
llm_tier_quota.py            Race-safe deep-tier quota (per account/surface/day)
helpers/llm_json.py          Robust JSON-from-LLM parsing

routers/
  auth.py                    Register/login/logout/refresh/me/declare-role/MFA
  contexts.py                Contexts CRUD, members, invitations, presets, context-object
  committees.py              Committee CRUD
  documents.py               Document upload/get/delete + summary/thread/evolution-diff/download
  document_engagement.py     view/share/engagement (read receipts)
  signals_ask.py             Signal generation + Ask
  signal_actions.py          Signal recommendation/action loop
  briefings.py               Formal briefings (M12) + speaking-notes + export
  prepare.py                 Catch-up briefs + Minutes-as-first-class
  cycle.py                   Reporting cycles end-to-end (questions/reportees/checklists/submissions/reports/schedule)
  decks.py                   Outline → generate → quality_check → feedback (Studio backend)
  studio.py                  Sensitivity demo + read receipts + history + share-email + tracker
  solve.py                   Solve interest capture
  solve_engine.py            4-phase Solve state machine + handoff trio + PDF export
  sandbox.py                 Pre-auth evaluation, sandbox→signup conversion, tutorial, sample-doc, objective-check
  chat.py                    Multi-model chat + bank-grade audit + ZIP export
  lens.py                    Lens runs + coach sessions
  simulate.py                Scenario simulations
  plays.py                   Workflow state machine
  comments.py                Threaded comments + mentions
  shares.py                  In-app share inbox/outbox + Home stream
  agenda.py                  Agenda evolution
  learn.py                   Learn research
  monitor.py                 Monitor dashboard
  strategic_goals.py         Strategic goals CRUD + extract
  influence_map.py           Influence graph + weekly digest cron
  pipeline.py                Pipeline trace strip
  audit.py                   Audit log + export
  synisense.py               Synisense status/dryrun (mock today)
  blog.py                    Exco360 — public read, admin compose/publish, RSS, weekly cron
  billing.py                 Stripe plans / checkout / status / webhook
  inbound_email.py           Postmark webhook receiver + per-user/context address minting
  inbound_queue.py           Iter70 trust-tiered triage queue
  enterprise.py              Enterprise interest capture
  walkin.py                  Walk-in question generator
  llm_quota.py               LLM quota status
  admin_health.py            /admin/health/full
  admin_auth_events.py       /admin/auth/events
  admin_llm_spend.py         /admin/llm/spend + decks/quality
  admin_sandbox_kpi.py       /admin/sandbox/kpi + objectives
  admin_signal_kpi.py        /admin/signals/action-heatmap
  misc.py                    /api/, /api/health, /api/events telemetry, /llm/probe

scripts/
  bootstrap_prod.py          One-shot prod bootstrap (idempotent)
  seed_bramuel.py            Demo seed
  seed_bramuel_sprint1.py    Sprint-1 demo seed
  seed_iter19_e2e.py         End-to-end demo seed
  seed_iter26_demo.py        Engagement demo seed

tests/                       60+ pytest smoke/iteration tests (test_iter*.py)
uploads/                     Local document storage root
```

### Frontend (`/app/frontend/src/`)

```
App.js                       Router + AuthProvider + Toaster
index.js / index.css         Entry + Tailwind base
contexts/AuthContext.jsx     Auth state, context switcher, role isolation
hooks/                       use-toast, useAIStageTicker (sandbox), useDraggableSections
lib/
  api.js                     axios instance (Bearer + cookie)
  utils.js                   classnames helper
  learnContent.js            Learn page content
  onboardingQuestions.js     Onboarding catalogue

pages/
  Landing.jsx                Marketing home (iter65 redesign)
  SolveLanding.jsx           Solve marketing page
  SignIn.jsx, SignUp.jsx, InviteAccept.jsx, Onboarding.jsx, AccountSecurity.jsx
  Sandbox.jsx, SandboxGenerating.jsx, QuickResults.jsx
  AppHome.jsx                Authed home (cross-board stream + cards)
  Workspace.jsx              Doc-grounded workspace (with merged Ask)
  Prepare.jsx                Catch-up briefs + Minutes
  Activity.jsx               Recent activity
  DocumentViewer.jsx         Doc viewer with thread/engagement/evolution
  Cycle.jsx, RespondToChecklist.jsx
  PlaysLibrary.jsx, PlayView.jsx
  Decks.jsx                  Studio (decks + history)
  AppSolve.jsx               Solve session UI
  LensRoom.jsx, Simulate.jsx
  Chat.jsx                   Multi-model chat
  Monitor.jsx                Strategic monitor
  InfluenceMap.jsx
  Learn.jsx
  ContextPortfolio.jsx, NewWorkspace.jsx, Manage.jsx, TenantSettings.jsx
  InboundQueue.jsx
  Enterprise.jsx
  SharedArtefact.jsx         Public shared link landing
  admin/                     AdminIndex, HealthDashboard, AuthEvents, LLMSpend, SandboxKPI, SignalKPI
  marketing/                 About, Features, Security, Blog, BlogPost, BlogAdmin

components/
  ProtectedRoute.jsx
  layout/                    AppShell, ContinueWithPill, PortfolioRail
  brand/                     Logo
  marketing/                 HeroSection, ThreePillars, EnterpriseFeature, MarketingShell
  home/                      AgendaEvolutionCard, InSummaryTiles, InboundQueueCard, PlayReadyCards, PlaysInProgressStrip, QuickActions, RecentActivity, WorkflowsHub
  documents/                 DocLensRail, DocumentEngagement, DocumentEvolutionPanel, DocumentJournalStats, DocumentPlayContext, DocumentSummaryCard, DocumentSummaryPanel, DocumentThread
  cycle/                     CycleTracker, PolishDiffModal, ReportsTab, ReviewInboxCard
  prepare/                   PrepareSideRail, PrepareStatsDock
  monitor/                   StrategicGoalsPanel, Sparkline
  plays/                     BoardPackStages, PreBoardStages
  studio/                    ShareArtefactModal
  share/                     ShareModal
  upload/                    UploadModal
  walkin/                    WalkInCard
  sandbox/                   ObjectiveCheck, SandboxBanner, SandboxEmailCapture, SandboxPackDrop, SandboxSampleDoc, SandboxTutorial
  chat/                      ModelAvatar
  collab/                    CommentThread, MentionInbox
  lens/                      AllLensesModal
  learn/                     LearnMoreModal, VideoModal
  ask/                       AskPanel
  act/                       ActModal
  trace/                     CompositionStrip
  trust/                     ValidatedBadge
  highlights/                HighlightsStats
  stream/                    StreamCard
  settings/                  BillingTab, CommitteeManager, InboundEmailPanel
  ui/                        ~50 Radix-based primitives (shadcn-style)
```

### Repo root

```
README.md                    One-liner ("Here are your Instructions")
AUDIT_iter68.md              Authoritative iter-68 progress audit (source for §1 + §7)
DEPLOY.md                    Production deployment checklist + env var matrix
auth_testing.md              Auth testing notes
design_guidelines.json       Editorial design tokens
test_result.md               Testing-agent communication contract
test_reports/                Generated test artefacts
backend/, frontend/, tests/, memory/
```

---

_Generated read-only from the codebase as committed to `main` (commit `4acc401 Auto-generated changes`). No source files were modified during this review._
