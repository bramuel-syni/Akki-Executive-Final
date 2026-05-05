> Read-only inventory produced by e1_dev on 2026-05-05. Frozen snapshot for reference.

# AKKI / Akki-Executive — Code Inventory

> **Scope.** Read-only review of `/app` (= `bramuel-syni/Akki-Executive`, branch `main`). Quoted paths are exact. No code was modified. No code was executed.
> **NOTE — not Expo / React Native.** This is a **Create React App (CRACO) web SPA** + **FastAPI / MongoDB** monolith. There is no React Native, Expo, iOS, or Android code anywhere in the tree.

---

## 1) Top-level repo structure

```
/app/
├── backend/                       # FastAPI app (uvicorn, supervised)
│   ├── server.py                  # Thin assembler — wires 53 routers, CORS, startup/shutdown
│   ├── core.py                    # Mongo client, JWT, auth deps, password hashing, audit_log helper
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── routers/                   # 53 route modules — see §4
│   ├── services/                  # Cross-cutting domain services
│   │   ├── synisense/             # 8-file in-house PII shielding pipeline
│   │   ├── solva_v2/              # State machine + reasoning engines
│   │   ├── rbac.py                # Phase A — role gating using X-Active-Context
│   │   ├── privacy_wall.py        # Phase 2b — PAUSED / partially built
│   │   ├── clamav_service.py
│   │   ├── storage_service.py     # local + S3 (MinIO bypassed in dev)
│   │   └── stripe_webhook.py
│   ├── helpers/                   # llm_json helper
│   ├── scripts/                   # 18 seed/backfill scripts
│   ├── tests/                     # 100+ pytest files (iter01..iter71 + phase-* + sprint*)
│   ├── templates/                 # Jinja templates (Solva PDF + refusal artefact)
│   ├── uploads/                   # Local file store (24 sub-folders by upload-id)
│   ├── *_service.py               # Domain helpers (briefings, documents, document_commentary,
│   │                              # email, llm, llm_tier_quota, reports, sandbox_v2_corpus,
│   │                              # sandbox_v2_strategic, paragraph_anchors, etc.)
│   └── .env                       # Secrets — see §6
│
├── frontend/                      # React 19 SPA (CRACO)
│   ├── package.json
│   ├── craco.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── components.json            # shadcn/ui registry
│   ├── jsconfig.json
│   ├── lighthouserc.json          # Phase 13.4 perf budgets
│   ├── plugins/health-check/
│   ├── public/
│   └── src/
│       ├── App.js                 # Router wiring (60 routes, see §4)
│       ├── App.css, index.css     # Brand tokens (CREAM/PAPER/INK/ACCENT)
│       ├── index.js               # ReactDOM.createRoot + axe-core dev hook
│       ├── pages/                 # 51 page components — see §4
│       ├── components/            # ~150 components, see structure below
│       ├── contexts/AuthContext.jsx   # JWT + per-tab X-Active-Context state
│       ├── hooks/                 # 11 custom hooks
│       └── lib/                   # api.js, solvaFlow.js, sandboxV2Flow.js, sponsorship.js, utils.js
│
├── docs/                          # 21 markdown design/PRD docs + RUNBOOKS
├── scripts/                       # backup_mongo, restore_mongo, migrate_local_to_s3
├── tests/                         # (placeholder — only __init__.py)
├── memory/                        # test_credentials.md (canonical seeded users)
├── test_reports/                  # 71 iteration JSON reports + 50+ pytest XMLs + screenshots
├── test_result.md                 # Testing protocol + agent communication log (5,200+ lines)
├── AUDIT_iter68.md                # Iter 68 audit dump
├── DEPLOY.md                      # Deployment runbook
├── auth_testing.md                # Notes on auth tests
├── design_guidelines.json         # Design tokens
├── README.md                      # 1-line stub
├── afya.docx, syni.docx           # Source briefs (40 KB & 31 KB)
├── backend_test.py                # Top-level integration test scaffold
└── .gitignore, .gitconfig, .git/, .emergent/
```

Frontend `components/` is organised by domain: `act/`, `ask/`, `brand/`, `chat/`, `collab/`, `cycle/`, `depth/`, `documents/`, `governance/`, `highlights/`, `home/`, `layout/`, `learn/`, `lens/`, `marketing/`, `monitor/`, `plays/`, `prepare/`, `reading/`, `review/`, `sandbox/`, `settings/`, `share/`, `shell/`, `solva/`, `stream/`, `studio/`, `synisense/`, `trace/`, `trust/`, `ui/` (45 shadcn primitives), `upload/`, `walkin/`.

Latest git commits are auto-commits ("auto-commit for `<uuid>`") — no semantic history preserved on disk. Branch: `main`. Remote: not configured locally (`git remote -v` empty), but per analysis the origin is `bramuel-syni/Akki-Executive`.

---

## 2) Tech stack

### Frontend (`frontend/package.json`)
| Layer | Library | Version |
|---|---|---|
| Framework | **React** (DOM) | `^19.0.0` |
| Build | **react-scripts 5.0.1** + **`@craco/craco ^7.1.0`** (CRA override) | — |
| Routing | **react-router-dom** | `^7.5.1` |
| Styling | **Tailwind CSS** (`^3.4.17`), `tailwindcss-animate`, `tailwind-merge`, `clsx`, `class-variance-authority` | — |
| UI primitives | **Radix UI** (28 packages: dialog, dropdown-menu, popover, scroll-area, select, tabs, toast, tooltip, …) — assembled via shadcn/ui (`components/ui/*`) | — |
| Icons | **lucide-react** | `^0.507.0` |
| Forms | **react-hook-form**, `@hookform/resolvers`, **zod** | — |
| Data | **axios** `^1.8.4` | — |
| Markdown | **react-markdown 9** + **remark-gfm 4** + **rehype-highlight 7** + **highlight.js 11** | (Phase B.1) |
| Charts | **recharts** | `^3.6.0` |
| Animation | **framer-motion** | `^12.38.0` |
| Toasts | **sonner** | `^2.0.3` |
| Misc | embla-carousel-react, cmdk (command palette), date-fns, react-day-picker, vaul (drawer), input-otp, react-resizable-panels, next-themes | — |
| Dev | ESLint 9.23, `@axe-core/react` 4.11 (dev-only a11y reporting), `@lhci/cli` 0.15, `pa11y-ci` 4.1, postcss, autoprefixer | — |
| Visual editor | `@emergentbase/visual-edits 1.0.8` (Emergent platform integration) | — |
| Pkg manager | **yarn 1.22.22** | — |

### Backend (`backend/requirements.txt`)
| Layer | Library | Version |
|---|---|---|
| Framework | **FastAPI** | `0.110.1` |
| Server | **uvicorn** | `0.25.0` (started by supervisord, never directly) |
| DB driver | **motor** (async MongoDB) | `3.3.1` (over `pymongo 4.5.0`) |
| Validation | **pydantic** | `2.12.5` |
| Auth | **PyJWT 2.12.1**, **bcrypt 4.1.3**, **passlib 1.7.4**, **pyotp 2.9.0** (MFA), **python-jose 3.5.0** | — |
| LLM | **openai 1.99.9**, **google-generativeai 0.8.6** + `google-genai 1.71.0`, **litellm 1.80.0**, **emergentintegrations 0.1.0** | — |
| Tokens | **tiktoken** | `0.12.0` |
| PII shielding | **presidio-analyzer ≥2.2** + **presidio-anonymizer ≥2.2** + **spaCy ≥3.7** + `cryptography ≥41.0` (AES-GCM) | (Phase 12.1) |
| File parsing | **python-docx 1.2.0**, **pypdf 6.10.2**, **lxml 6.1.0** | — |
| Doc rendering | **WeasyPrint ≥60.0** (Solva PDF), **reportlab 4.4.10**, **Jinja2 3.1.6**, **Pillow 12.2.0**, **qrcode 8.2** | — |
| Email | **resend 2.29.0** (outbound), Postmark webhooks (no SDK — raw POST) | — |
| Payments | **stripe 15.0.1** | (DISABLED in env) |
| Storage | **boto3 1.42.86** (S3/MinIO) | — |
| AV | `clamd ≥1.0.2` (ClamAV) | (BYPASSED in dev) |
| Scheduler | **APScheduler 3.10.4** | — |
| HTTP | **httpx 0.28.1**, **aiohttp 3.13.5**, **websockets 16.0** | — |
| Test/lint | **pytest 9.0.3** + `pytest-asyncio`, **ruff** (cache present), **black 26.3.1**, mypy 1.20.0, flake8 7.3.0 | — |

### Infrastructure
- Python entrypoint: `backend/server.py` (FastAPI app — `/api/docs`, `/api/openapi.json` mounted under `/api` for K8s ingress).
- Process manager: **supervisord** (per system prompt).
- DB: **MongoDB** (local on `mongodb://localhost:27017`, `DB_NAME=akki_dev` in dev).
- LLM key: **EMERGENT_LLM_KEY** (single Emergent universal key, used for OpenAI / Anthropic / Gemini via `emergentintegrations`).

---

## 3) Product features

> Status legend (mirrors `docs/PRODUCT_FEATURES.md` audit dated 2026-05-05): **WORKS** = wired end-to-end · **PARTIAL** = degraded by env flag/mock/missing key · **STUB** = endpoint exists, logic canned · **MISSING** = placeholder only.

### 3.1 Authentication & Identity
- **Status:** WORKS · **Files:** `backend/routers/auth.py`, `backend/core.py` (`get_current_account`, `create_access_token`, `hash_password`, `set_auth_cookies`), `frontend/src/contexts/AuthContext.jsx`, `frontend/src/pages/SignIn.jsx`, `SignUp.jsx`, `AccountSecurity.jsx`, `InviteAccept.jsx`, `frontend/src/components/ProtectedRoute.jsx`.
- **Functionality:** Email/password registration → bcrypt hash → JWT access (8h) + refresh (7d). Cookies `access_token` / `refresh_token` (`HttpOnly`, `Secure`, `SameSite=None`) **AND** Authorization Bearer header both accepted (iter59 self-healing path). MFA via TOTP (`pyotp` + `qrcode`). Sampled auth-event observability (`db.auth_events`, 1% success / 100% failure, surfaced at `/admin/auth/events`).
- **In/Out:** Inputs `{email, password, name?, tenant_name?}`. Outputs `{access_token, account, contexts[]}`.
- **Dependencies:** Mongo `accounts`, `memberships`, `contexts`, `login_attempts`, `auth_events`. JWT secret = `JWT_SECRET` env. Admin bootstrap: on every boot `server.py` ensures `ADMIN_EMAIL`/`ADMIN_PASSWORD` user exists and provisions a default context.

### 3.2 Role-aware Active Context (Phase A)
- **Status:** WORKS · **Files:** `backend/routers/active_context.py`, `backend/services/rbac.py`, `frontend/src/components/layout/ContextSwitchModal.jsx`, `frontend/src/contexts/AuthContext.jsx`, `frontend/src/lib/api.js` (header interceptor).
- **Functionality:** Tab-isolated active context. SPA persists context id in **`sessionStorage`** (per-tab); axios interceptor attaches it as **`X-Active-Context`** header on every authenticated call. Server `require_role()` dependency reads the header, validates membership in `db.memberships`, and gates routes by role (`executive` / `ned` / `dual`). Switching context POSTs `/api/me/active-context`, writes a `context.switched` audit row, and returns verbatim memo modal copy. `/api/me/contexts` is the authoritative role-per-membership source. Two role-probe endpoints (`/api/me/role-probe/{executive,ned}`) are mounted for boot guards.
- **Dependencies:** `db.memberships`, `db.contexts`, `db.audit_log`. Per `WEBSITE_BRIEF_V3.md`, the auto-pick UX deviation (auto-pick first membership instead of full-screen picker) is flagged as P1 in the analysis context.

### 3.3 Context (Company) Management
- **Status:** WORKS · **Files:** `backend/routers/contexts.py`, `frontend/src/pages/ContextPortfolio.jsx`, `Manage.jsx`, `NewWorkspace.jsx`, `TenantSettings.jsx`. Layout `frontend/src/components/layout/PortfolioRail.jsx`, `CycleContextIndicator.jsx`.
- **Functionality:** CRUD for "contexts" (= companies). Four canonical `type` values: `ned_personal`, `ned_sponsored`, `executive_personal`, `executive_enterprise`. Membership invitations via emailed token (currently logged as `[invite-email-stub]` — see §3.21). Members table, leave-context, default-context selector, consent decisions, industry/jurisdiction presets. Sponsoring-org concept (`sponsoring_org_id`) — per Phase K.2 audit, **no functional gates** depend on it (cosmetic only).
- **In/Out:** Standard REST (see §4.2 for endpoints).
- **Dependencies:** `db.contexts`, `db.memberships`, `db.invitations`, `db.organisations`, `db.consent_decisions`, `db.context_objects`, `db.committees`.

### 3.4 First-session onboarding (Phase 4)
- **Status:** WORKS · **Files:** `backend/routers/first_session.py`, `frontend/src/pages/FirstSession.jsx`. Guard: `App.js` `FirstSessionGuard`.
- **Functionality:** Forced step before app access. Endpoints: `GET ""`, `POST /start`, `POST /intake`, `POST /choose-door`, `POST /complete`, `POST /skip`. Account doc carries `first_session.status ∈ {not_started, in_progress, completed, skipped}`. Grandfathered legacy users land directly on `skipped`.

### 3.5 Document Journal (Workspace)
- **Status:** WORKS · **Files:** `backend/routers/documents.py`, `backend/document_commentary_service.py`, `backend/paragraph_anchors.py`, `backend/routers/admin_journal.py`, `frontend/src/pages/Workspace.jsx`, `ReadingView.jsx`, `frontend/src/components/documents/*` (DocumentBodyModal, DocumentJournalStats, DocumentSummaryCard, DocumentSummaryPanel, DocumentEvolutionPanel, DocumentPlayContext), `frontend/src/components/reading/*` (ReadingBody, ReadingRail, ReadingTopBar, CitationChip, CommentaryDrawer, CommentaryItem, TierChip).
- **Functionality:** Upload → Synisense ingest → extracted_text + paragraph anchors → `journal_commentary`. Workspace lists docs; row click opens reader; "Open original" opens an in-app modal. Journal commentary is auto-generated per doc with on-demand regeneration. **Paragraph anchors** sweep nightly at 03:00 UTC (`POST /api/cron/paragraph-anchors-sweep`). Backfill admin: `POST /api/admin/journal/backfill` (superadmin only).
- **Per audit (2026-05-05):** journal_commentary populated on **154 / 154** docs.

### 3.6 Chat (multi-model, hash-chained audit, streaming) — **Phase B.1 in progress**
- **Status:** WORKS · **Files:** `backend/routers/chat.py` (1,977 lines), `frontend/src/pages/Chat.jsx`, `frontend/src/components/chat/ModelAvatar.jsx`.
- **Functionality:**
  - 5 supported models: **Claude Sonnet 4.5** (`claude-sonnet-4-5-20250929`, default), **Claude Haiku 4.5**, **GPT-5.2**, **Gemini 2.5 Pro**, **Gemini 2.5 Flash** (lines 54–65).
  - Untethered or **context-tethered** chats. Tethered chats run **BM25 grounding** over the context's documents (top-5 paragraphs), inject `[GROUNDING]` block, instruct model to cite using `[[cite:<anchor_id>]]` markers, then **deterministically drop hallucinated citations** and renumber `[1]..[n]` (Phase 11 ITEM C — `_process_citations`).
  - **SSE streaming** at `POST /api/chats/{cid}/messages/stream` (Phase B.1).
  - **In-turn file attachments** at `POST /api/chats/{cid}/attach` (de-identified text injected as `[ATTACHMENT]` block).
  - **Conversation history search** at `GET /api/chats/search`.
  - **SHA-256 hash-chained audit log** (`db.chat_audit_log`, 169 rows in dev DB, genesis = `"GENESIS-AKKI-CHAT-AUDIT-2026"`); each row carries `prev_hash` + `row_hash`. Cancellation persistence on `asyncio.CancelledError` (Phase B.1 backend fix).
  - 30-day retention sweep at 03:30 UTC daily (`POST /api/admin/chat-retention/sweep`).
  - Audit trail visible to user at `GET /api/chats/{cid}/audit`; bank-grade ZIP export at `GET /api/chats/{cid}/audit/export.zip`.
- **Dependencies:** `services.synisense` (mandatory pre-LLM redaction), `db.chats`, `db.chat_messages`, `db.chat_audit_log`, EMERGENT_LLM_KEY.

### 3.7 Synisense Shield (PII redaction)
- **Status:** WORKS · **Files:** `backend/services/synisense/{__init__,adapter,encryption,llm_fallback,pipeline,pool,presidio_engine,regex_recognisers}.py`, `backend/routers/synisense.py`, `frontend/src/components/synisense/PreviewDrawer.jsx`.
- **Functionality:** 3-layer pipeline — (1) regex recognisers, (2) Presidio + spaCy NER, (3) optional LLM fallback (capped, concurrent-bounded). Substitutes detected entities with stable `[ORG_1]`/`[PERSON_1]`/`[TITLE_1]` placeholders. AES-GCM-encrypted shield map persisted to `db.synisense_shield_maps` with TTL (1h public_read / 24h default / 7d hard max). Master key = `SYNISENSE_MASTER_KEY` (boot raises `MasterKeyMissing` in production unless `SYNISENSE_ALLOW_INSECURE=true`). Boot warmup loads spaCy in a thread; insecure-fallback nag loop logs every 60s.
- **Endpoints:** `GET /api/synisense/status`, `POST /api/synisense/dryrun`, `GET /api/admin/synisense/perf`. Per-execution audit-lite at `db.synisense_runs` (2,671 rows in dev across surfaces `chat`, `ingest`, `briefing`, `deck`, `report`, `solve_v2.*`, `journal_commentary`).
- **Tests:** `backend/tests/test_synisense_*.py` (5 files: encryption, integration, regex, security, surface_validation).

### 3.8 Solva v2 (Reasoning surface)
- **Status:** WORKS · **Files:** `backend/routers/solva_v2.py` (1,977 lines), `backend/services/solva_v2/` (state_machine, guardrails, opinion_filter, grounding_contract, llm_adapter, submodules + 6 engines: candidate_generation, llm_adapter_proxy, probability_weighting, reflection, refusal, tension_detector, triangulation), `backend/solva_artefact_export.py`, `backend/templates/solva_artefact.html`, `solva_refusal_artefact.html`, `frontend/src/pages/SolvaApp.jsx`, `SolvaSession.jsx`, `SolvaLanding.jsx`, `frontend/src/components/solva/SolvaLanding.jsx`, `frontend/src/components/solva/flow/*`, `frontend/src/components/solva/artefact/*`, `frontend/src/lib/solvaFlow.js` (pure reducer + 36 jest tests).
- **Functionality:** 4-tile picker (Seek clarity · Develop strategy · Simulate hypothesis · Get perspective). 14-state session flow with reflection, candidate generation, triangulation, probability-weighted comparison, tension detection, hard-block refusal ladder. PDF + DOCX artefact export (WeasyPrint + python-docx). Cycle handoff queue feeds Daily Review.
- **Endpoints:** `POST /api/solva/v2/sessions` (auto-cluster default), `POST /sessions/{sid}/turn`, `GET /sessions/{sid}/reasoning-log`, `GET /sessions/{sid}/artefact-reasoning`, `GET /sessions/{sid}/export.pdf`, `/export.docx`, `POST /sessions/{sid}/handoff/cycle`, `POST /sessions/{sid}/abandon`, `POST /sessions/{sid}/fork`, `POST /intent/classify`, `POST /cron/stale-session-sweep`. Daily 04:00 UTC sweep marks 30-day-idle sessions abandoned.

### 3.9 Sandbox v2 (pre-auth demo)
- **Status:** WORKS · **Files:** `backend/routers/sandbox.py`, `backend/sandbox_v2_corpus.py` (1,443 lines, 5 verbatim industry contexts: Bank/Healthcare/Logistics/Gov/Tech), `backend/sandbox_v2_strategic.py` (Phase L 14-doc strategic pack), `backend/sandbox_service.py`, `frontend/src/pages/SandboxV2.jsx`, `frontend/src/components/sandbox/v2/*` (Step1SolvaWrapper, Step3StudioWrapper, Step4CycleSnapshot, ClosingStep, StepReveal, StepShell, ProgressChrome).
- **Functionality:** 4-step pre-auth walkthrough at `/sandbox`. Endpoints under `/api/sandbox/v2/*`: opening question, fallback situation, studio sources, cycle snapshot, pulse signals, composed draft, provenance probe (`/studio/add-sentence`), save-and-send (Resend test-mode aware → emits `test_mode_restricted` if recipient not the allowed test address). 7-day TTL on `db.sandbox_v2_sessions`.

### 3.10 Cycle Manager (reporting cycle / committees / minutes / boardpacks)
- **Status:** WORKS · **Files:** `backend/routers/cycle.py`, `cycle_config.py`, `committees.py`, `signals_ask.py`, `prepare.py`, `briefings.py`, `agenda.py`, `routers/admin_signal_kpi.py`, `signal_actions.py`, `daily_review.py`. Frontend: `pages/Cycle.jsx`, `CycleSettings.jsx`, `Prepare.jsx`, `DailyReview.jsx`, `RespondToChecklist.jsx`. Components in `cycle/` + `prepare/` + `review/`.
- **Functionality:** Questions → reportees → checklists → submissions → reports (compose / send-up / review / polish / export.pdf / export.deck.pdf). Committee CRUD (default 6: Audit, Risk, Nominations, Remuneration, ESG, Strategy). Cycle config phases + per-phase summaries. Public reportee reply at `GET/POST /api/respond/{token}`. Cron: schedules driver at `POST /api/cycle/cron/run-schedules`. Daily Review (`/api/me/review-queue`) batches `studio_artefact`, `solva_handoff`, and `report` items.
- **Boardpack:** Aggregation collection `db.boardpacks` (88 rows in dev, post-M.3 migration; legacy `briefings` collection now empty). URL paths under `/api/contexts/{cid}/briefings/*` are kept as deliberate URL-stable backwards compat.

### 3.11 Work Studio (block-based composer)
- **Status:** WORKS · **Files:** `backend/routers/studio.py`, `studio_blocks.py`, `decks.py`, `backend/studio_sensitivity.py`, `frontend/src/pages/WorkStudio.jsx`, `StudioComposerPage.jsx`, `Decks.jsx`, `frontend/src/components/studio/BlockComposer.jsx`, `ShareArtefactModal.jsx`. Email-based public read at `frontend/src/pages/SharedArtefact.jsx` (routed at `/share/:token` and `/shared/:token`).
- **Functionality:** Block-level CRUD/reorder/lifecycle (`submit-review` → `approve` → `send`) for kinds `briefing | deck | report`. Deterministic 0–100 sensitivity scorer → `PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED` band. Image upload (gated by ClamAV in prod, bypassed in dev). Public Chair view at `GET /api/public/studio/read/{token}` carries a `watermark` block and runs `_assert_public_safe()` denylist check on the response (Phase 11 ITEM A — denylist hits return 500). 30-day token TTL.
- **Decks:** `POST /decks/outline` → `POST /decks/{id}/generate` → `quality_check` + `feedback`. Deck generation runs **Gemini 2.5 Flash second-pass validation** (Phase 11 ITEM B), persisted as `decks.validation` (`verdict ∈ validated|qualified|flagged`). Daily soft cap per surface (`db.llm_validator_usage`).

### 3.12 Decks + Reports validation (Phase 11 ITEM B)
- **Status:** WORKS · **Files:** `backend/llm_service.py` (`_validator_soft_cap_ok`), `backend/routers/decks.py`, `cycle.py`, `solva_v2.py`. Frontend: `frontend/src/components/trust/ValidatedBadge.jsx`.
- **Functionality:** Independent-validator fan-out across decks, reports, solve syntheses. `verdict ∈ validated|qualified|flagged`, `confidence 0..100`, validator_provider/model populated. Daily soft cap (`VALIDATOR_DAILY_SOFT_CAP`, default 200/surface) — when tripped, returns `qualified` fallback with note "Daily validator cap reached" rather than blocking.

### 3.13 Influence Map + Weekly Influence Digest
- **Status:** WORKS · **Files:** `backend/routers/influence_map.py`, `frontend/src/pages/InfluenceMap.jsx`. Cron at `POST /api/cron/weekly-digest` fires every Monday 08:00 UTC.

### 3.14 Monitor + Strategic Goals
- **Status:** WORKS · **Files:** `backend/routers/monitor.py`, `strategic_goals.py`, `frontend/src/pages/Monitor.jsx`, `frontend/src/components/monitor/Sparkline.jsx`, `StrategicGoalsPanel.jsx`. Strategic-goal extraction from documents at `POST /strategic-goals/extract`.

### 3.15 The Lens (POV) + Lens Coach
- **Status:** WORKS · **Files:** `backend/routers/lens.py`, `frontend/src/pages/LensRoom.jsx`, `frontend/src/components/lens/AllLensesModal.jsx`. Lens catalog + per-context runs + chat-style coach sessions. Pro-gated for free plan.

### 3.16 Test Hypothesis (Simulate)
- **Status:** WORKS · **Files:** `backend/routers/simulate.py`, `frontend/src/pages/Simulate.jsx`. Pro-gated.

### 3.17 Plays (workflow library)
- **Status:** WORKS · **Files:** `backend/routers/plays.py`, `frontend/src/pages/PlaysLibrary.jsx`, `PlayView.jsx`, `frontend/src/components/plays/{BoardPackStages,PreBoardStages}.jsx`, `frontend/src/components/home/PlayReadyCards.jsx`, `PlaysInProgressStrip.jsx`. State machine with advance / jump / pause / resume / seen / exit / pre_board/read.

### 3.18 Inbound Email (Postmark) + Inbound Triage Queue
- **Status:** WORKS · **Files:** `backend/routers/inbound_email.py`, `inbound_queue.py`, `frontend/src/pages/InboundQueue.jsx`, `frontend/src/components/home/InboundQueueCard.jsx`. Per-account & per-context inbound tokens (`accounts.inbound_token`, `contexts.inbound_token`). Webhook at `POST /api/inbound/postmark`. Trust-tiered triage queue at `db.inbound_queue` with accept/reject.

### 3.19 Walk-in (free text → solve recommendation)
- **Status:** WORKS · **Files:** `backend/routers/walkin.py`, `frontend/src/components/walkin/WalkInCard.jsx`. `POST /api/walkin` + `/regenerate`.

### 3.20 Marketing site (public)
- **Status:** WORKS · **Files:** `frontend/src/pages/Landing.jsx`, `SolvaLanding.jsx`, and `frontend/src/pages/marketing/*` (About, Blog, BlogAdmin, BlogPost, EarlyAccess, Enterprise, Features, Plans, Security). Components in `frontend/src/components/marketing/*` (HeroSection, ThreePillars, SharpestUseCase, SixtySecondProof, Exco360Voice, EnterpriseFeature, ClosingCTA, MarketingNav, MarketingFooter, MarketingShell). Blog backed by `backend/routers/blog.py` with weekly Tuesday 10:00 UTC scheduled post (`POST /api/blog/cron/weekly`), RSS feed, subscribers, slug-based posts.

### 3.21 Email — Outbound (Resend)
- **Status:** **PARTIAL — TEST MODE** · **Files:** `backend/email_service.py`. `RESEND_API_KEY` set in `backend/.env` but key is in Resend test mode → only the registered test recipient is delivered to; everyone else gets `mode=test_mode_restricted`. Invitation email (`routers/contexts.py` line 404) is a `[invite-email-stub]` log — does NOT call `send_email`. Phase 16 dependency.

### 3.22 Email — Inbound (Postmark)
- **Status:** WORKS — LIVE · `POSTMARK_SERVER_TOKEN` set in `backend/.env`. See §3.18.

### 3.23 Stripe Billing
- **Status:** **DISABLED (confirmed)** · **Files:** `backend/routers/billing.py`, `backend/services/stripe_webhook.py`. `BILLING_ENABLED=false` in env; `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are commented out. Endpoints exist (`/api/billing/{plans,me,checkout,status/{sid}}`, `/api/webhook/stripe`) but boot guard in `server.py` lines 235–243 refuses startup if `BILLING_ENABLED=true` without a key. `db.stripe_events` carries idempotency TTL index. `db.payment_transactions` empty.

### 3.24 ClamAV virus scan
- **Status:** **PARTIAL — BYPASSED IN DEV** · **Files:** `backend/services/clamav_service.py`. In production = hard precondition (uploads return 503 if down). In dev: `clamd: STOPPED`, `ALLOW_UNSAFE_UPLOADS=true` bypasses; stderr nag every 60s.

### 3.25 Object storage
- **Status:** PARTIAL · **Files:** `backend/services/storage_service.py`, `scripts/migrate_local_to_s3.py`. Two backends: `local` (current dev — files written to `/app/backend/uploads/<uuid>/`) and `s3` (boto3-based, MinIO compatible, NOT running in dev pod). Selected by `STORAGE_BACKEND` env.

### 3.26 Akki Pulse (cross-context aggregator)
- **Status:** **MISSING (placeholder confirmed)** · **Files:** `frontend/src/pages/PulsePlaceholder.jsx`. No `pulse_signals` collection. No aggregator endpoint registered. Nav slot wired to `/app/pulse`. **Phase F dependency.**

### 3.27 Privacy Wall (metadata-only projection guard)
- **Status:** **MISSING / PAUSED** · **Files:** `backend/services/privacy_wall.py` (partially built — paused), `docs/PRIVACY_WALL_DESIGN.md`, `docs/PRIVACY_WALL_LEAKAGE_AUDIT.md`. No `privacy_wall` collection. Cross-context reads in `GET /api/me/home/stream` are membership-based, NOT Privacy-Wall-safe. Per the analysis context, **explicitly paused** by the user to prioritise Phases A+B.

### 3.28 Admin & Observability
- **Status:** WORKS · **Files:** `backend/routers/admin_health.py`, `admin_auth_events.py`, `admin_journal.py`, `admin_llm_spend.py`, `admin_sandbox_kpi.py`, `admin_signal_kpi.py`. Frontend: `frontend/src/pages/admin/{AdminIndex,AuthEvents,HealthDashboard,LLMSpend,SandboxKPI,SignalKPI}.jsx`.
- **Functionality:** Health full-dashboard, auth-event tail, LLM spend + decks quality + retries_24h, sandbox KPI + objectives, signal action heatmap, journal backfill trigger.

### 3.29 Sharing (cross-account artefact share)
- **Status:** WORKS · **Files:** `backend/routers/shares.py`, `frontend/src/components/share/ShareModal.jsx`. Inbox/outbox + per-share read. Powers the Home Stream aggregator at `GET /api/me/home/stream`.

### 3.30 Comments + Mentions
- **Status:** WORKS · **Files:** `backend/routers/comments.py`, `frontend/src/components/collab/{CommentThread,MentionInbox}.jsx`. Per-artefact threads + mention inbox.

### 3.31 Audit & Governance
- **Status:** WORKS · **Files:** `backend/routers/audit.py`, `routers/governance.py`, `frontend/src/components/governance/TrustPanel.jsx`. Per-context audit log readout + export. `/api/me/governance` carries trust panel rollups.

### 3.32 Documents — engagement & paragraph anchors
- **Status:** WORKS · **Files:** `backend/routers/document_engagement.py`, `backend/paragraph_anchors.py`. Per-day-deduplicated views + share counts at `db.document_views`, `db.document_shares`. `paragraphs[]` lazy-on-read or via daily 03:00 UTC sweep cron.

### 3.33 Learn (research + content library)
- **Status:** WORKS · **Files:** `backend/routers/learn.py`, `frontend/src/pages/Learn.jsx`, `frontend/src/lib/learnContent.js`, `frontend/src/components/learn/{LearnMoreModal,VideoModal}.jsx`. `POST /api/learn/research`.

### 3.34 LLM quota + tier (Opus/Deep)
- **Status:** WORKS · **Files:** `backend/routers/llm_quota.py`, `backend/llm_tier_quota.py`. `db.llm_deep_usage` race-safe via `(account_id, surface, day_utc)` unique compound. `db.llm_validator_usage` for second-pass validators.

### 3.35 Pipeline (multi-stage doc → signals → briefings)
- **Status:** WORKS · **Files:** `backend/routers/pipeline.py`. `POST /api/contexts/{cid}/pipeline/run` + `GET /api/contexts/{cid}/pipeline/events`.

### 3.36 Early Access marketing intake
- **Status:** WORKS · **Files:** `backend/routers/early_access.py`, `frontend/src/pages/marketing/EarlyAccess.jsx`. Public `POST /api/early-access/register` (deduped by email).

### 3.37 Enterprise interest
- **Status:** WORKS · **Files:** `backend/routers/enterprise.py`, `frontend/src/pages/Enterprise.jsx`, `frontend/src/pages/marketing/Enterprise.jsx`.

### 3.38 Depth offer (corpus-threshold gating)
- **Status:** WORKS · **Files:** `backend/routers/depth.py`, `frontend/src/components/depth/{DepthOfferCard,ProPill,UpgradeModal}.jsx`, `frontend/src/hooks/useDepthStatus.js`. Lens / Simulate / Influence Map only render in left rail when corpus threshold (3 docs OR 1 briefing) is met; routes stay URL-accessible regardless.

### 3.39 Product features API (self-documentation)
- **Status:** WORKS · **Files:** `backend/routers/product_features.py`. Serves `docs/PRODUCT_FEATURES.md`, `docs/PRODUCT_REVIEW.md`, `docs/ux-advisories-v1.md` over `/api/product-features[.md]`, `/api/ux-audit[.md]`, `/api/ux-advisories[.md]`.

---

## 4) Routes / pages / endpoints

### 4.1 Frontend routes (`frontend/src/App.js`)

**Public / unauth (15 routes):**
| Path | Component | File |
|---|---|---|
| `/` | Landing | `pages/Landing.jsx` |
| `/solva` | SolvaLanding | `pages/SolvaLanding.jsx` |
| `/about` | About | `pages/marketing/About.jsx` |
| `/features` | Features | `pages/marketing/Features.jsx` |
| `/security` | Security | `pages/marketing/Security.jsx` |
| `/plans` | Plans | `pages/marketing/Plans.jsx` |
| `/enterprise` | EnterpriseMarketing | `pages/marketing/Enterprise.jsx` |
| `/early-access` | EarlyAccess | `pages/marketing/EarlyAccess.jsx` |
| `/blog`, `/blog/:slug` | Blog, BlogPost | `pages/marketing/{Blog,BlogPost}.jsx` |
| `/respond/:token` | RespondToChecklist | `pages/RespondToChecklist.jsx` |
| `/shared/:token`, `/share/:token` | SharedArtefact | `pages/SharedArtefact.jsx` |
| `/signin`, `/signup` | SignIn / SignUp (PublicOnlyRoute) | `pages/{SignIn,SignUp}.jsx` |
| `/invite/:token` | InviteAccept | `pages/InviteAccept.jsx` |
| `/sandbox`, `/sandbox/resume` | SandboxV2 | `pages/SandboxV2.jsx` |

**Authenticated `/app/*` (Gated = ProtectedRoute + FirstSessionGuard, 31 routes):**
| Path | Component | File |
|---|---|---|
| `/app` | AppHome (role dispatcher) | `pages/AppHome.jsx` (→ `pages/home/{HomeExecutive,HomeNed,HomeDual,HomeUndeclared}.jsx`) |
| `/app/first-session` | FirstSession (no FirstSessionGuard) | `pages/FirstSession.jsx` |
| `/app/cycle` | Cycle | `pages/Cycle.jsx` |
| `/app/monitor` | Monitor | `pages/Monitor.jsx` |
| `/app/plays`, `/app/plays/:playId` | PlaysLibrary, PlayView | `pages/{PlaysLibrary,PlayView}.jsx` |
| `/app/blog-admin` | BlogAdmin | `pages/marketing/BlogAdmin.jsx` |
| `/app/workspace` | Workspace (Document Journal) | `pages/Workspace.jsx` |
| `/app/inbound-queue` | InboundQueue | `pages/InboundQueue.jsx` |
| `/app/activity` | Activity | `pages/Activity.jsx` |
| `/app/simulate` | Simulate | `pages/Simulate.jsx` |
| `/app/lens` | LensRoom | `pages/LensRoom.jsx` |
| `/app/chat` | Chat | `pages/Chat.jsx` |
| `/app/influence` | InfluenceMap | `pages/InfluenceMap.jsx` |
| `/app/learn`, `/app/learn/:id` | Learn | `pages/Learn.jsx` |
| `/app/manage` | Manage | `pages/Manage.jsx` |
| `/app/enterprise` | Enterprise (in-app) | `pages/Enterprise.jsx` |
| `/app/work-studio` | WorkStudio | `pages/WorkStudio.jsx` |
| `/app/decks/:deckId` | Decks | `pages/Decks.jsx` |
| `/app/pulse` | PulsePlaceholder | `pages/PulsePlaceholder.jsx` |
| `/app/studio/composer/:kind/:artefactId` | StudioComposerPage | `pages/StudioComposerPage.jsx` |
| `/app/solva` | SolvaApp | `pages/SolvaApp.jsx` |
| `/app/solva/session/new`, `/app/solva/session/:sessionId` | SolvaSession | `pages/SolvaSession.jsx` |
| `/app/documents/:id` | ReadingView (via DocumentRouteSwitch) | `pages/ReadingView.jsx` |
| `/app/contexts`, `/app/companies` | ContextPortfolio | `pages/ContextPortfolio.jsx` |
| `/app/contexts/new`, `/app/companies/new`, `/app/new-workspace` | NewContext (NewWorkspace) | `pages/NewWorkspace.jsx` |
| `/app/settings`, `/app/settings/billing` | TenantSettings | `pages/TenantSettings.jsx` |
| `/app/settings/cycle` | CycleSettings | `pages/CycleSettings.jsx` |
| `/app/review` | DailyReview | `pages/DailyReview.jsx` |
| `/app/security` | AccountSecurity | `pages/AccountSecurity.jsx` |

**Admin `/admin/*` (ProtectedRoute, 6 routes):**
| Path | Component |
|---|---|
| `/admin` | AdminIndex |
| `/admin/health` | HealthDashboard |
| `/admin/sandbox-kpi` | SandboxKPI |
| `/admin/signal-kpi` | SignalKPI |
| `/admin/llm-spend` | LLMSpend |
| `/admin/auth-events` | AuthEvents |

**Top nav** (`frontend/src/components/layout/AppShell.jsx` lines 59–69): Home · Document Journal · Chat · Solva · Work Studio · Cycle Manager · Monitor · Pulse · Learn.

### 4.2 Backend API endpoints (318 total across 53 routers)

All endpoints are mounted under `/api/*` (Kubernetes ingress prefix). Below is grouped by feature; counts in parens are routes per file. Full source-of-truth is `GET /api/openapi.json` and `GET /api/docs` (Swagger UI mounted under `/api`).

> **Note on grep-derived counts.** Some files mount multi-decorator routes; the precise count below comes from `grep -rE '@router\.(get|post|put|patch|delete)' backend/routers/`.

| Domain | Router | Count | Selected endpoints |
|---|---|---|---|
| Auth | `auth.py` | 8 | `POST /auth/{register,login,logout,refresh,declare-role}`, `GET /auth/me`, `POST /auth/mfa/{setup,verify,disable}` |
| Active Context | `active_context.py` | 5 | `GET /me/contexts`, `POST /me/active-context`, `GET /me/role-probe[/executive|/ned]` |
| Contexts (companies) | `contexts.py` | 18 | `POST/PATCH/DELETE/GET /contexts/{cid}`, members, invitations, accept-invite, leave, presets/industries, presets/jurisdictions, accounts/me, default-context, consent-decisions, context-object |
| Documents | `documents.py` | 13 | `POST /contexts/{cid}/documents`, `GET /contexts/{cid}/documents[/{did}]`, `/document-journal`, `/journal-commentary`, `/evolution-diff`, `/download`, `/paragraphs[/{pid}/original]`, `/thread`, `POST /cron/paragraph-anchors-sweep` |
| Document engagement | `document_engagement.py` | 3 | `POST /view`, `/share`, `GET /engagement` |
| Briefings (BoardPack) | `briefings.py` | 9 | `POST /briefings`, `/mark-read`, `/speaking-notes`, `GET /briefings[/{bid}/export]`, `/boardpacks[/{bpid}]`, `POST /boardpacks/{bpid}/regenerate-commentary` |
| Committees | `committees.py` | 4 | CRUD on `committees` |
| Cycle | `cycle.py` | 25 | questions, reportees, checklists, dispatch, public respond/{token}, submissions, reports compose/send_up/review/polish, exports, cycle/committees, cycle/schedule (CRUD), `POST /cycle/cron/run-schedules`, cycle/actions, reports inbox |
| Cycle config | `cycle_config.py` | 5 | get/put/advance/reset config, phase summary |
| Prepare | `prepare.py` | 9 | brief-kinds, briefs CRUD, minutes, minutes extract / to_cycle / narrative |
| Daily Review | `daily_review.py` | 5 | `GET /me/review-queue[/counts]`, `POST /items/{kind}/{iid}/{approve,reject,edit}` |
| Chat | `chat.py` | 13 | `GET /chat/models`, `POST /chats`, `POST /chats/{cid}/{attach,messages,messages/stream}`, `GET /chats[/{cid}/{audit,audit/export.zip}]`, `GET /chats/search`, `PATCH/DELETE /chats/{cid}`, `POST /admin/chat-retention/sweep` |
| Solva v2 | `solva_v2.py` | 13 | `POST /sessions`, `/turn`, `/abandon`, `/handoff/cycle`, `/fork`, `GET /sessions[/{sid}/{reasoning-log,reasoning-log/summary,artefact-reasoning,export.pdf,export.docx}]`, `POST /intent/classify`, `POST /cron/stale-session-sweep` |
| Sandbox v1+v2 | `sandbox.py` | 22 | `POST /generate`, `/cleanup/expired`, `/convert`, `/contexts/seeded`, capture-email, tutorial, sample-doc, objective-check, `POST /v2/sessions[/{sid}/{exit,studio/add-sentence,save-and-send}]`, `GET /v2/sessions/{sid}/{opening-question,fallback-situation,studio-sources,cycle-snapshot,pulse-signals,composed-draft}`, templates |
| Synisense | `synisense.py` | 3 | `GET /synisense/status`, `POST /synisense/dryrun`, `GET /admin/synisense/perf` |
| Studio (artefacts) | `studio.py` | 9 | view, engagement, share, share-email, rescore, history, backfill_sensitivity, public/sensitivity-demo, public/track/{token}, public/read/{token} |
| Studio blocks | `studio_blocks.py` | 12 | per `{kind, artefact_id}`: blocks CRUD/move/reorder, upload-image, lifecycle, submit-review, approve, send, synisense-accept |
| Decks | `decks.py` | 7 | outline, generate, quality_check, feedback, list/get, decks/{id}/context |
| Comments | `comments.py` | 5 | per-artefact comments + mentions inbox + read |
| Shares | `shares.py` | 6 | `POST /contexts/{cid}/shares`, `GET /me/shares/{inbox,outbox}`, `GET/DELETE /shares/{sid}`, `GET /me/home/stream` |
| Plays | `plays.py` | 12 | library, list/get, create, advance/jump/pause/resume/seen/exit/state, pre_board/read |
| Strategic goals | `strategic_goals.py` | 5 | CRUD + extract |
| Signals + Ask | `signals_ask.py` | 5 | signals generate/list/delete + ask |
| Signal actions | `signal_actions.py` | 3 | recommendations + actions list/post |
| Lens | `lens.py` | 8 | catalog, run, runs CRUD, coach sessions CRUD + messages |
| Simulate | `simulate.py` | 4 | simulate post + list/get/delete |
| Influence Map | `influence_map.py` | 3 | map, digest, `POST /cron/weekly-digest` |
| Monitor | `monitor.py` | 1 | `GET /contexts/{cid}/monitor` |
| Walkin | `walkin.py` | 2 | `POST /api/walkin`, `/regenerate` |
| Inbound email | `inbound_email.py` | 2 | `GET /address`, `POST /postmark` |
| Inbound queue | `inbound_queue.py` | 5 | counts + list/get/accept/reject |
| Audit | `audit.py` | 2 | log + export |
| Governance | `governance.py` | 3 | get + audit + audit/export |
| Pipeline | `pipeline.py` | 2 | run + events |
| Agenda | `agenda.py` | 1 | agenda-evolution |
| Learn | `learn.py` | 1 | research |
| Billing | `billing.py` | 5 | plans, me, checkout, status/{sid}, webhook/stripe |
| Blog | `blog.py` | 10 | posts (public), subscribe, compose, publish, weekly cron, seed/launch-10, delete, admin posts, subscribers, `/rss` |
| Misc | `misc.py` | 4 | `/`, `/health`, `/events`, `POST /contexts/{cid}/llm/probe` |
| LLM quota | `llm_quota.py` | 1 | quota |
| Depth | `depth.py` | 2 | get + dismiss |
| First session | `first_session.py` | 6 | get, start, intake, choose-door, complete, skip |
| Early access | `early_access.py` | 2 | register, registrations |
| Enterprise | `enterprise.py` | 2 | interest, interest/me |
| Product features | `product_features.py` | 6 | product-features[.md], ux-audit[.md], ux-advisories[.md] |
| Admin — health | `admin_health.py` | 1 | full |
| Admin — auth events | `admin_auth_events.py` | 1 | events |
| Admin — journal | `admin_journal.py` | 1 | backfill |
| Admin — LLM spend | `admin_llm_spend.py` | 3 | spend, decks/quality, retries_24h |
| Admin — sandbox KPI | `admin_sandbox_kpi.py` | 2 | kpi, objectives |
| Admin — signal KPI | `admin_signal_kpi.py` | 1 | signals/action-heatmap |

Cron endpoints fired by APScheduler in `server.py`: `/api/blog/cron/weekly` (Tue 10:00), `/api/cron/weekly-digest` (Mon 08:00), `/api/cron/paragraph-anchors-sweep` (daily 03:00), `/api/admin/chat-retention/sweep` (daily 03:30 — registered indirectly via `routers.chat.run_chat_retention_sweep`), `/api/solva/v2/cron/stale-session-sweep` (daily 04:00). All require `X-Cron-Secret = AKKI_CRON_SECRET`.

---

## 5) Data models / entities (MongoDB)

**Core auth/identity:**
- `accounts` — `{id, email (unique), name, declared_role ∈ {executive,ned,dual,undeclared}, password_hash, mfa_enabled, mfa_secret, default_context_id, is_superadmin, plan, subscription_status, first_session.status, is_sandbox?, sandbox_session_id?, inbound_token, preferences}`
- `contexts` — `{id, name, type ∈ {ned_personal,ned_sponsored,executive_personal,executive_enterprise}, industry, jurisdiction, sector, sponsoring_org_id, owner_account_id, status, progress_state, committees[], inbound_token, sandbox_metadata?}`
- `memberships` — `{id, account_id, context_id, role ∈ {executive,ned,dual}, sub_role ∈ {admin,member}, provisioning, data_ownership, status}`
- `invitations` — `{token (unique), context_id, email}`
- `organisations` — sponsoring orgs
- `consent_decisions`
- `committees` (also embedded under `contexts.committees[]`)

**Audit + observability:**
- `audit_log` — generic per-context audit (write_audit helper)
- `auth_events` — sampled login attempts
- `chat_audit_log` — **SHA-256 hash-chained**, immutable; rows carry `{prev_hash, row_hash, account_id, chat_id, action, payload, ip, ua_sha, at}`
- `login_attempts`, `telemetry_events`

**Documents + engagement:**
- `documents` — `{id, context_id, name, extracted_text, status, sensitivity_band, sensitivity_score, sensitivity_label, sensitivity_reasons, doc_kind, body_redacted, synisense_version, journal_commentary, paragraphs[], anchors_version, data_trust}`
- `document_views` — unique on `(doc_id, account_id, day)`; `document_shares`, `document_engagement`

**Synisense:**
- `synisense_runs` — `{input_sha256, surface ∈ {chat, ingest, briefing, deck, report, solve_v2.*, journal_commentary}, ts, context_id, spans[]}`
- `synisense_shield_maps` — TTL-indexed AES-GCM envelopes

**Cycle / Reports / Briefings:**
- `questions`, `reportees`, `checklists`, `submissions`, `reports` (`{status ∈ {draft,in_review,sent}, body, validation, tier_chip}`), `cycle_configs`, `cycle_schedules`, `cycle_history`, `briefings` (post-M.3 empty), `boardpacks` (`{commentary}`), `briefs`, `briefing_reads`, `signals`, `signal_events`, `signal_actions`, `ask_messages`

**Studio + Decks + Plays:**
- `studio_blocks`, `studio_views` (unique `(artefact_kind, artefact_id, account_id, day_utc)`), `studio_shares`, `studio_images`
- `decks`, `deck_outlines`, `deck_telemetry`
- `plays`

**Solva v2:**
- `solva_v2_sessions` — `{id, account_id, started_at, status ∈ {active,completed,abandoned,blocked_hard}, version, cluster_id, cluster_resolution, submodule, synthesis.{validation}, reasoning_audit_log[]}`
- `solva_clusters` — 12 canonical
- `solva_cycle_handoff_queue` — feeds Daily Review
- `solva_handoffs` (legacy)
- `solva_v1_*_archive` (legacy, archived; not read at runtime)

**Lens / Simulate / Strategic Goals / Influence:**
- `lens_runs`, `lens_coach_sessions`
- `simulations`, `strategic_goals`
- (no separate `influence_map` collection — derived on-demand from documents + memberships)

**Sharing / Comments / Highlights:**
- `shares`, `comments` (= `collab_comments`), `mentions`, `highlights`

**Sandbox:**
- `sandbox_pickups` (legacy v1)
- `sandbox_v2_sessions` — TTL 7d, `state ∈ {WELCOME, STEP_1_SOLVA, STEP_3, …, CLOSING}`

**Inbound:**
- `inbound_queue` (`status ∈ {pending,new,awaiting_review,accepted,rejected}`), `inbound_queue_raw`

**LLM cost / quota:**
- `llm_deep_usage` — unique `(account_id, surface, day_utc)`
- `llm_validator_usage` — unique `(day_utc, surface)`
- `llm_retry_log` — TTL 30d

**Marketing / Blog / Early Access:**
- `blog_posts`, `blog_subscribers`, `early_access_registrations` (unique on email), `enterprise_interest`

**Billing:**
- `stripe_events` (TTL idempotency), `stripe_dead_letter`, `payment_transactions` (empty)

**Other:**
- `context_objects` (versioned context object), `context_members` (legacy alias), `health_check`, `command` (queue stub)

**Indexes** are created at startup in `server.py` lines 315–442 (≈40 unique/compound/TTL indexes; full list there).

**Key relationships:** `accounts (1) ─── (M) memberships (M) ─── (1) contexts`. Most artefact tables (`documents`, `signals`, `boardpacks`, `decks`, `plays`, `reports`, `studio_blocks`, etc.) carry `context_id` for tenant scoping. `chat_audit_log` and `chats` are scoped per `account_id` (chats can optionally tether to `context_id`).

---

## 6) Environment variables, config files, external integrations

### `backend/.env` (24 keys present; values redacted in this report)
| Key | Purpose | Notes |
|---|---|---|
| `MONGO_URL` | Mongo connection | dev: `mongodb://localhost:27017` |
| `DB_NAME` | Mongo DB name | dev: `akki_dev` |
| `JWT_SECRET` | JWT signing | required |
| `APP_NAME` | Cosmetic | `AKKI Sandbox` |
| `CORS_ORIGINS` | CORS allowlist (or `*`) | server.py lines 180–222 falls back to permissive regex |
| `EMERGENT_LLM_KEY` | Universal LLM key (Claude / GPT-5.2 / Gemini) | mandatory |
| `AKKI_CRON_SECRET` | Required for APScheduler crons to fire | optional (skipped if unset) |
| `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_TIMEOUT_SECONDS` | ClamAV daemon | dev: bypassed |
| `ALLOW_UNSAFE_UPLOADS` | Dev escape hatch | `true` in dev |
| `STORAGE_BACKEND` | `local` or `s3` | dev: `local` |
| `BILLING_ENABLED` | Stripe gate | `false` in dev |
| `BACKUP_DIR` | Mongo backup target | for `scripts/backup_mongo.sh` |
| `SYNISENSE_MASTER_KEY` | AES-GCM master key | required in production |
| `SYNISENSE_POOL_SIZE`, `SYNISENSE_USE_POOL` | spaCy pool tuning | optional |
| `SYNISENSE_ALLOW_INSECURE` | Dev fallback | nag every 60s when set |
| `SYNISENSE_LLM_FALLBACK_{CAP,CONCURRENCY,TIMEOUT_MS}` | LLM fallback bounds | optional |
| `SYNISENSE_SHIELD_MAP_TTL_HOURS` | Shield map TTL override | default 24h |
| `RESEND_API_KEY` | Outbound email | TEST MODE in dev |
| `POSTMARK_SERVER_TOKEN` | Inbound email | LIVE in dev |

**Implicit / commented / referenced (not present in dev `.env`):** `STRIPE_SECRET_KEY`, `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` (boot guard refuses startup if `BILLING_ENABLED=true` without these); `FRONTEND_URL`, `PUBLIC_APP_URL` (used by save-and-send for resume URLs); `ADMIN_EMAIL`, `ADMIN_PASSWORD` (boot seeds — defaults `admin@akki.ai` / `AkkiAdmin2026!`); `AKKI_AUTH_OBSERVE_RATE` (default 0.01); `VALIDATOR_DAILY_SOFT_CAP` (default 200); `AKKI_ENV`.

### `frontend/.env`
```
REACT_APP_BACKEND_URL=https://akki-executive.preview.emergentagent.com
WDS_SOCKET_PORT=443
```

### Config files
- `frontend/craco.config.js`, `tailwind.config.js`, `postcss.config.js`, `jsconfig.json` (path alias `@/* → src/*`), `lighthouserc.json`, `components.json` (shadcn registry), `.pa11yci.json` (referenced by `yarn a11y:ci`)
- `backend/pytest.ini`
- `.gitconfig`, `.gitignore`
- Design tokens: `design_guidelines.json`, `frontend/src/App.css` + `index.css` (CSS vars `--cream`, `--paper`, `--ink`, `--accent`, `--accent-dark`, `--rule`, `--muted`)

### External integrations (third-party services)
| Service | Purpose | SDK | Status | Required key | Where |
|---|---|---|---|---|---|
| **Emergent Universal Key** | Claude (Anthropic) + GPT-5.2 (OpenAI) + Gemini 2.5 (Google) | `emergentintegrations 0.1.0` + `litellm 1.80.0` + `openai 1.99.9` + `google-generativeai 0.8.6` | LIVE | `EMERGENT_LLM_KEY` | All chat/solva/studio/decks/lens/simulate flows |
| **Resend** | Outbound email | `resend 2.29.0` | TEST MODE | `RESEND_API_KEY` | `backend/email_service.py` |
| **Postmark** | Inbound email webhook | raw POST | LIVE | `POSTMARK_SERVER_TOKEN` | `backend/routers/inbound_email.py` |
| **Stripe** | Payments | `stripe 15.0.1` | DISABLED | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | `backend/routers/billing.py`, `services/stripe_webhook.py` |
| **ClamAV** | Virus scan | `clamd ≥1.0.2` | BYPASSED in dev pod | host/port env | `backend/services/clamav_service.py` |
| **MinIO / AWS S3** | Object storage | `boto3 1.42.86` + `s3transfer` + `s5cmd` | NOT running in dev | (none in dev — `STORAGE_BACKEND=local`) | `backend/services/storage_service.py` |
| **Presidio + spaCy** | PII detection (in-house) | `presidio-analyzer ≥2.2`, `spacy ≥3.7` | LIVE | `SYNISENSE_MASTER_KEY` | `backend/services/synisense/` |
| **WeasyPrint** | PDF render (Solva, reports) | `weasyprint ≥60.0` | LIVE | (none) | `backend/solva_artefact_export.py`, `backend/templates/solva_artefact.html` |

---

## 7) Incomplete / mocked / stubbed / paused items

| # | Item | File / line | Status |
|---|---|---|---|
| 1 | **Akki Pulse** — placeholder page only; no aggregator endpoint, no `pulse_signals` collection. | `frontend/src/pages/PulsePlaceholder.jsx`; nav at `AppShell.jsx:67` | **MISSING** (Phase F) |
| 2 | **Privacy Wall** — design + leakage audit docs exist; service file partially built; not wired into cross-context reads. | `backend/services/privacy_wall.py`; `docs/PRIVACY_WALL_DESIGN.md`; `docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` | **PAUSED** (per analysis context) |
| 3 | **Invitation email** is a log-only stub — does not call `send_email`. | `backend/routers/contexts.py:404` — `logger.info(f"[invite-email-stub] to={email} …")` | **STUB** (Phase 16) |
| 4 | **ClamAV** stopped in dev pod; uploads bypassed via `ALLOW_UNSAFE_UPLOADS=true`. Stderr nag every 60s. | `backend/services/clamav_service.py`; env | **PARTIAL — BYPASSED** |
| 5 | **MinIO / S3 storage** not running in dev pod. `STORAGE_BACKEND=local` writes to `/app/backend/uploads/`. | env; `services/storage_service.py` | **PARTIAL — LOCAL FALLBACK** |
| 6 | **Stripe billing** disabled. Endpoints registered but boot guard refuses `BILLING_ENABLED=true` without keys. | `backend/server.py:235-243`; `backend/routers/billing.py` | **DISABLED** (Phase 16) |
| 7 | **Resend outbound** in test mode → only registered test recipient delivered to. Other recipients receive `mode=test_mode_restricted`. | `backend/email_service.py` | **PARTIAL — TEST MODE** |
| 8 | **Pre-2026-05-05 journal-commentary runs** mis-bucketed under `surface=briefing` in `synisense_runs` (forensic-only — fixed for live + backfill paths from 2026-05-05 onward). | `docs/PRODUCT_FEATURES.md:31` | **DOCUMENTED LEGACY** |
| 9 | **Solva v1** routers (`solva.py`, `solva_engine.py`) deleted in M.4; v1 collections renamed to `solva_v1_*_archive` and not read at runtime. | `backend/server.py:71-72,146`, `backend/scripts/migrate_phase_m4_legacy_cleanup.py` | **ARCHIVED** |
| 10 | **Sandbox v2 Step 2 (Pulse)** intentionally deferred — reducer reserves the state but `FORWARD` map skips to Step 3. | `frontend/src/lib/sandboxV2Flow.js`; `pages/SandboxV2.jsx:20` (comment) | **DEFERRED** |
| 11 | **`/app/prepare` and `/app/decks` redirect-aliases retired in M.4** — replaced with direct links to canonical surfaces. | `AppShell.jsx:95-98` (comment) | **REMOVED — DEAD ROUTES** |
| 12 | **NAV / DEPTH_NAV / MANAGE_NAV arrays** in `AppShell.jsx` lines 89–120 retained for legacy code paths (depth gating, lookup helpers) but the **left-rail rendering of these was removed in Phase 13.3**. | `AppShell.jsx:71-73` (comment) | **DEAD — KEPT FOR LOOKUP** |
| 13 | **Phase 11 ITEM E** stale comment cleanup — cosmetic, no functional change. | `backend/routers/studio_blocks.py` | **COSMETIC ONLY** |
| 14 | **Cycle reply/submission stub** — comment in `cycle.py:15`. | `backend/routers/cycle.py:15` | **STUB MENTIONED** |
| 15 | **Phase 15 Solva v2 reasoning placeholder** comment for prior 15.0/15.1/15.2 surfaces. | `backend/routers/solva_v2.py:1542` | **DOCUMENTED LEGACY** |
| 16 | **TODO(tier-limits) breadcrumb** in sponsorship lib — flag for a future Phase 16 tier policy. | `frontend/src/lib/sponsorship.js` | **COSMETIC TODO** |
| 17 | **Schedulers are in-process APScheduler** — single-replica only. For HA, the comment in `server.py:497` says route to an external scheduled trigger. | `backend/server.py:497` | **DOCUMENTED LIMITATION** |
| 18 | **Cycle Manager Executive flow / NED-side design doc** (Phase D) — referenced in analysis context as a future task, not yet built. | (no file) | **NOT STARTED** |
| 19 | **Phase B.2 (Two-pass method baked into Chat)** — referenced as next phase, not yet built. | (no file) | **NOT STARTED** |

**No failing imports, no broken commented-out code blocks** were observed in spot checks of `App.js`, `server.py`, `core.py`, `chat.py`, `documents.py`, or `auth.py`. The commented-out import lines in `server.py` (`# M.4: solva v1 (...) deleted.`) are intentional and explanatory.

---

## 8) Quick reference: seeded test credentials

From `/app/memory/test_credentials.md`:
- **Superadmin:** `admin@akki.ai` / `AkkiAdmin2026!` (owns `Syni.ai HQ` + 5 strategic-pack demo contexts)
- **Non-owner viewer:** `viewer@akki.ai` / `Viewer2026!`
- **Phase K.3 tester:** `juliusaopio@gmail.com` / `Julius@Akki!2026-Exec` (dual / superadmin / 5 contexts mirroring 14 strategic-pack docs)

Re-seed with: `python3 backend/scripts/seed_julius_opio.py` or `seed_admin_strategic_data.py`.

---

## 9) Caveats on this inventory

- The audit table in `docs/PRODUCT_FEATURES.md` is dated **2026-05-05** and was used as the verified baseline for §3 statuses. Five days of subsequent work (Phase A complete, Phase 1 backfill, Phase B.1 in-progress per the analysis context) are reflected.
- **318 backend routes** were enumerated by grep; the canonical OpenAPI surface is at `GET /api/openapi.json` and `GET /api/docs`.
- **51 frontend pages** + ~150 components were enumerated by directory listing. Component-level wiring to features was inferred from imports in pages and feature-named subdirectories under `components/`.
- The 100+ pytest files under `backend/tests/` and the 71-iteration archive in `test_reports/` indicate this codebase has been built across many small phases (iter01 → iter71 → phase A/B/J/K/L/M).
- **No environment variable values, secrets, or credentials are reproduced in this report** — only key names, presence, and purpose.
