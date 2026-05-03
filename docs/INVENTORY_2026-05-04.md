# AKKI-Executive — Codebase Inventory (2026-05-04)

_Read-only audit of `/app` (GitHub: `bramuel-syni/Akki-Executive`, branch `main`,
HEAD = `f1b284f`). Parallel reference to `PRODUCT_REVIEW.md` and
`INVENTORY_2026-05-02.md` — those remain authoritative; this file captures
post-Phase-12.1 / 12.2 drift only. No code was modified to produce this file._

---

## 1. Top-Level Structure

```
/app
├── backend/                         FastAPI + Motor monolith
│   ├── server.py                    577 ll. App assembler, startup (indexes,
│   │                                seeds, schedulers, Synisense boot guard +
│   │                                warmup thread)
│   ├── core.py                      DB handle, JWT helpers, audit writer,
│   │                                require_context_membership dependency
│   ├── llm_service.py               Tiered LLM proxy + legacy regex shield +
│   │                                Phase 11 independent Gemini-Flash validator
│   ├── llm_tier_quota.py            Race-safe deep-tier daily quota
│   ├── bm25.py                      Pure-Python BM25 retrieval
│   ├── briefings_service.py         Briefing composer + PDF/DOCX/board-deck
│   ├── citation_refs.py             Inline citation back-resolution
│   ├── documents_service.py         Storage abstraction + extraction
│   │                                (virus_scan_stub RETIRED — ClamAV is live)
│   ├── email_service.py             Resend wrapper (mode='sent'/'noop'/'error')
│   ├── paragraph_anchors.py         Stable hash anchors (Reading Viewer)
│   ├── reports_service.py           Cycle-report composer + chain-of-custody PDF
│   ├── sandbox_service.py           10-stage sandbox seed generator
│   ├── sandbox_templates.py         6 sector templates
│   ├── solve_clusters_seed.py / solve_comparables_seed.py
│   ├── solve_pdf.py                 Reportlab Solve PDF
│   ├── studio_sensitivity.py        Sensitivity scorer
│   ├── helpers/llm_json.py          Strict JSON-from-LLM extraction
│   ├── routers/                     50 routers, all /api-prefixed
│   ├── services/
│   │   ├── clamav_service.py        ClamAV sidecar (live; 503 on miss)
│   │   ├── storage_service.py       boto3 S3/MinIO abstraction
│   │   ├── stripe_webhook.py        idempotency indexes + dead-letter
│   │   └── synisense/               Phase 12.1 in-house pipeline
│   │       ├── pipeline.py          Orchestrator (regex → Presidio → LLM)
│   │       ├── encryption.py        AES-GCM envelope, per-record DEKs
│   │       ├── presidio_engine.py   spaCy + custom recognisers
│   │       ├── regex_recognisers.py 9-pattern fast path
│   │       ├── llm_fallback.py      Gemini Flash for low-confidence spans
│   │       └── pool.py              Process-pool scaffolding (off in dev)
│   ├── scripts/                     bootstrap_prod, seed_*, backfill_synisense_version
│   ├── tests/                       70+ pytest files (test_iter*.py,
│   │                                test_synisense_*.py, test_phase12_2_*.py,
│   │                                test_governance_endpoint.py)
│   ├── uploads/                     Local doc cache (S3 canonical when
│   │                                STORAGE_BACKEND=s3)
│   ├── requirements.txt             138 ll (incl. presidio-analyzer/anonymizer,
│   │                                spacy, cryptography for Phase 12.1)
│   └── .env                         Committed (see §6)
├── frontend/                        React 19 / craco / yarn
│   ├── package.json
│   ├── plugins/health-check/
│   ├── public/static/marketing,qa/
│   └── src/
│       ├── App.js                   Router (97 routes, auth gates, watermark
│       │                            alias /share/:token)
│       ├── contexts/AuthContext.jsx Cookie+Bearer self-healing auth
│       ├── lib/{api,utils,learnContent}.js
│       ├── hooks/                   8 hooks
│       ├── pages/                   40 page components
│       │   ├── admin/               6 admin pages
│       │   └── marketing/           9 marketing pages
│       └── components/              ~140 component files across 31 folders
│           (act, ask, brand, chat, collab, cycle, depth, documents, governance,
│            highlights, home, layout, learn, lens, marketing, monitor, plays,
│            prepare, reading, review, sandbox, settings, share, stream, studio,
│            synisense, trace, trust, ui, upload, walkin)
├── docs/
│   ├── ROADMAP.md
│   ├── PRODUCT_REVIEW.md
│   ├── INVENTORY_2026-05-02.md      Companion (slightly stale pre-12.2)
│   ├── INVENTORY_2026-05-04.md      ← THIS FILE
│   ├── SYNISENSE_SCOPE.md           Phase 12 scope + "actually shipped" diff
│   ├── CHAT_CITATIONS_AUDIT.md
│   ├── homepage-positioning-v1.md
│   ├── ux-advisories-v1.md
│   └── RUNBOOKS/
│       ├── PRODUCTION_ENV.md
│       ├── AZURE_DEPLOY.md
│       ├── MONGO_BACKUP.md
│       └── STORAGE_MIGRATION.md
├── memory/
│   ├── PRD.md                       Authoritative PRD with iteration history
│   ├── PRODUCT_FEATURES.md          ~2026-05-02 snapshot, slightly stale
│   ├── HOMEPAGE_AUDIT.md / HOME_AUDIT.md / UX_ADVISORIES_AUDIT.md
│   └── test_credentials.md          admin@akki.ai · viewer@akki.ai
├── scripts/                         backup_mongo.sh, restore_mongo.sh,
│                                    migrate_local_to_s3.py
├── tests/                           Empty harness root
├── test_reports/                    Pytest + screenshot artefacts
├── AUDIT_iter68.md
├── DEPLOY.md
├── auth_testing.md
├── design_guidelines.json
├── test_result.md                   Testing-agent communication contract
├── README.md
├── .gitignore / .gitconfig
└── .emergent / .git
```

---

## 2. Tech Stack

**Frontend:** React 19, react-router-dom 7.5, CRA wrapped by @craco/craco 7,
TailwindCSS 3.4 (cream/oxblood/navy editorial palette, Georgia serif heads +
Inter chrome + JetBrains Mono metadata), 27 Radix UI primitives assembled
shadcn-style in `components/ui/` (46 files), framer-motion 12.38, recharts 3.6,
react-hook-form + zod, axios, lucide-react, sonner, cmdk, vaul,
react-resizable-panels, react-day-picker, input-otp. Yarn 1.22.

**Backend:** FastAPI 0.110 / Starlette 0.37 / Uvicorn 0.25, Motor 3.3 / PyMongo
4.5, PyJWT + bcrypt + passlib + python-jose + pyotp + qrcode (TOTP MFA),
emergentintegrations 0.1 (Universal-Key wrapper for Anthropic + OpenAI +
Gemini), litellm 1.80, openai 1.99, google-genai 1.71, stripe 15, resend 2.29,
boto3 1.42 (+ s5cmd) for S3/MinIO, clamd ≥ 1.0.2 for ClamAV, pypdf 6.10 +
reportlab 4.4 + python-docx 1.2 + pillow 12, APScheduler 3.10, pytest 9.

**Phase 12.1 additions:** `presidio-analyzer ≥ 2.2`, `presidio-anonymizer ≥
2.2`, `spacy ≥ 3.7`, `cryptography ≥ 41` (`requirements.txt:131-138`).

**Infra:** supervisor (backend `:8001`, frontend `:3000`). ClamAV + MinIO
sidecars. MongoDB via `MONGO_URL`. Kubernetes ingress: `/api/*` → backend,
else → frontend.

---

## 3. Product Features

### 3.1 Auth, MFA, Cookie-or-Bearer
`backend/routers/auth.py`, `backend/core.py`, `frontend/src/contexts/AuthContext.jsx`,
`frontend/src/pages/{SignIn,SignUp,InviteAccept,AccountSecurity}.jsx`. Email/password +
8h JWT access / 7d refresh, bcrypt, brute-force lockout, optional TOTP MFA, sampled
auth observability (`db.auth_events`).

### 3.2 Contexts, Memberships, Committees, Invitations
`backend/routers/{contexts,committees}.py`. Polymorphic context types
(`executive_personal` / `ned_personal` / `org_provisioned` / `sandbox`). Nested
committees CRUD. Tokenised invitations.

### 3.3 First Session (gated onboarding)
`backend/routers/first_session.py`, `frontend/src/pages/FirstSession.jsx`,
`<FirstSessionGuard>` in `App.js`. Three-question intake → three doors (forward
email / upload / run Solve).

### 3.4 Documents, Reading Viewer, Engagement
`backend/routers/{documents,document_engagement}.py`, `backend/paragraph_anchors.py`,
`backend/services/{clamav_service,storage_service}.py`. Chunked upload → ClamAV
→ S3/MinIO → text extraction → stable `paragraphs[]` hash anchors → rail-commentary
viewer → daily 03:00 UTC anchor sweep. **Phase 12.2 ITEM B**: Synisense
per-paragraph redact in `shield_reversible` mode (24h TTL); anchors stable
through redaction.

### 3.5 Synisense — In-house De-Identification (Phase 12.1) + Surface Wiring (Phase 12.2)
- **Engine**: `backend/services/synisense/{pipeline,encryption,presidio_engine,regex_recognisers,llm_fallback,pool}.py`
- **Router**: `backend/routers/synisense.py`
- **UI**: `frontend/src/components/synisense/PreviewDrawer.jsx`,
  `frontend/src/components/trust/ValidatedBadge.jsx`,
  `frontend/src/components/governance/TrustPanel.jsx`
- **Three-tier hybrid**: regex fast-path (9 patterns) → Presidio NER (with
  custom DEAL_CODENAME, EXECUTIVE_TITLE, CHAIR_NAME, FINANCIAL_FIGURE_LARGE) →
  Gemini Flash low-confidence fallback (capped, timeout-bounded). AES-GCM
  envelope encryption with per-record DEKs and `key_version` rotation.
  TTL-indexed `synisense_shield_maps` (1h public_read, 24h default, 7d max).
  Entity-stable replacement tokens. In-memory ring-buffer perf.
- **Surfaces wired**: Chat (`routers/chat.py`), Ingest (`documents.py`), Studio
  block-save (`studio_blocks.py`), Solva synthesis (`solva_engine.py`),
  Public-read assertion (`studio.py` — `synisense_version >= 1` 410-gate),
  Governance TrustPanel (`governance.py`).
- **Endpoints**: `GET /api/synisense/status`, `POST /api/synisense/dryrun`,
  `GET /api/admin/synisense/perf` (superadmin),
  `POST /api/studio/{kind}/{aid}/synisense-accept`.
- **Boot guards**: refuses prod start without `SYNISENSE_MASTER_KEY`. spaCy
  warmed in background thread.

### 3.6 Studio (Decks + Reports + Briefings) — Block Composer + Sensitivity + Share
`backend/routers/{studio,studio_blocks,decks,briefings}.py`,
`backend/{studio_sensitivity,reports_service,briefings_service}.py`,
`frontend/src/components/studio/{BlockComposer,ShareArtefactModal}.jsx`,
`frontend/src/pages/{Decks,StudioComposerPage}.jsx`. 9-block palette;
auto-sensitivity with optional LLM tiebreaker; lifecycle draft → in_review →
approved → sent. 30-day JWT share tokens; watermarked, redacted, denylist-asserted
public read with fail-loud `_assert_public_safe()`. Phase 11 ITEM B independent
Gemini-Flash validator on Decks / Reports / Solve syntheses with daily soft cap.

### 3.7 Cycle — Reportees, Checklists, Submissions, Reports, Recurring Schedule
`backend/routers/{cycle,cycle_config}.py` (cycle.py is 1,621 ll — biggest router).
Six-phase ribbon, question bank, reportees, deterministic-rank checklists, Resend
dispatch, public `/respond/{token}`, multi-tier `chain[]` send-up with polish, PDF
+ board-deck export, recurring schedule cron.

### 3.8 Daily Review (approval queue)
`backend/routers/daily_review.py`, `frontend/src/pages/DailyReview.jsx`.
Keyboard-first batched queue.

### 3.9 Signals + Ask + Signal Actions
`backend/routers/{signals_ask,signal_actions,admin_signal_kpi}.py`. LLM-grounded
Risk/Gap/Opportunity signals with citations. BM25-grounded Ask.

### 3.10 Chat (multi-model, shielded, bank-grade audit)
`backend/routers/chat.py`, `frontend/src/pages/Chat.jsx`. Untethered or
context-tethered (Phase 11 ITEM C, BM25 grounding with hallucination drop).
**Phase 12.2 ITEM A** synisense pre-LLM redact + legacy regex defence-in-depth +
post-LLM rehydrate. SHA-256-chained audit log + verify ZIP. 5 models exposed
(Claude Sonnet 4.5 default, Claude Haiku 4.5, GPT-5.2, Gemini 2.5 Pro, Gemini 2.5
Flash).

### 3.11 Prepare (Catch-up Briefs + Minutes)
`backend/routers/prepare.py`. Distinct `db.briefs` collection. Minutes-as-first-class
extracts open questions and routes them into the cycle.

### 3.12 Solve (4-phase decision engine)
`backend/routers/{solve,solve_engine}.py`,
`backend/{solve_pdf,solve_clusters_seed,solve_comparables_seed}.py`. Surface →
Depth → Synthesis → Lock-in. 27 anonymised comparables. Three handoffs (brief /
decks / cycle). Pro/Free tier gating.

### 3.13 Lens, Simulate, Plays, Monitor, Strategic Goals, Influence Map
Respective routers + pages. Plays catalog has six entries; only `board_pack` and
`pre_board` are wired through to UI. Monitor is function-aware (CEO/CFO/COO/
Commercial/NED). Influence Map runs Mon 08:00 UTC weekly digest cron.

### 3.14 Inbound Email (Postmark) + Triage Queue
`backend/routers/{inbound_email,inbound_queue}.py`. Per-user/per-context
mailbox `inbound+<token>[.<ctx_token>]@<INBOUND_DOMAIN>`. Iter70 trust-tiered
triage queue.

### 3.15 Cross-context Shares + Home Stream
`backend/routers/shares.py`, `frontend/src/pages/SharedArtefact.jsx` (public
`/shared/:token` + `/share/:token` watermark alias).

### 3.16 Governance / Trust Panel + Audit Log + Export
`backend/routers/{governance,audit}.py`, `frontend/src/components/governance/TrustPanel.jsx`.
**Phase 12.2 ITEM F** — real `synisense` block aggregating from `db.synisense_runs`
over `$or: [{context_id ∈ ctx_ids}, {account_id == current.id}]`.

### 3.17 Marketing Site + Blog (Exco360)
`frontend/src/pages/{Landing,SolveLanding}.jsx`,
`frontend/src/pages/marketing/*.jsx`,
`frontend/src/components/marketing/*.jsx`,
`backend/routers/blog.py`. Tue 10:00 UTC weekly cron drafts via Sonnet
ghostwriter persona.

### 3.18 Sandbox (pre-auth demo)
`backend/routers/sandbox.py` (1,005 ll), `backend/{sandbox_service,sandbox_templates}.py`,
`frontend/src/pages/{Sandbox,SandboxGenerating,QuickResults}.jsx`. 4-Q intake → 60s
narrative → JWT + disposable account, hard-deleted day 22.

### 3.19 Billing (Stripe via Emergent)
`backend/routers/billing.py`. Free / Pro ($29/mo) / Team ($99/mo). Boot guard.
`BILLING_ENABLED=false` in current `.env`.

### 3.20 Comments + Mentions, Walk-In, Agenda Evolution, Learn
Respective routers + pages.

### 3.21 Admin Surfaces
`backend/routers/{admin_health,admin_auth_events,admin_llm_spend,admin_sandbox_kpi,admin_signal_kpi,llm_quota}.py`,
`frontend/src/pages/admin/*.jsx`. Superadmin-only.

---

## 4. Routes

### Frontend (`frontend/src/App.js`)
Public: `/`, `/solve`, marketing pages, `/blog*`, `/respond/:token`,
`/shared/:token` + `/share/:token` watermark alias, `/signin` (+ aliases),
`/signup` (+ aliases), `/invite/:token`, `/sandbox` + `/sandbox/generating/:sid`.

Auth-gated (`<ProtectedRoute>` + `<FirstSessionGuard>`): `/app/first-session`,
`/app`, `/app/cycle`, `/app/monitor`, `/app/plays[/:id]`, `/app/workspace`,
`/app/prepare`, `/app/inbound-queue`, `/app/activity`, `/app/simulate`,
`/app/lens`, `/app/chat`, `/app/influence`, `/app/quick-results/:cid/:docId`,
`/app/learn[/:id]`, `/app/manage`, `/app/enterprise`, `/app/decks[/:deckId]`,
`/app/studio/composer/:kind/:artefactId`, `/app/solva` _(legacy `/app/solve` aliased via Navigate)_, `/app/documents/:id`,
`/app/contexts[/new]`, `/app/settings[/cycle,/billing]`, `/app/review`,
`/app/security`. Redirects: `/app/{highlights,briefings,ask}` → consolidated
surfaces.

Admin: `/admin[/health,/sandbox-kpi,/signal-kpi,/llm-spend,/auth-events]`.

### Backend — 50 routers, all `/api`-prefixed
See `PRODUCT_FEATURES.md` Appendix A for the exhaustive method × path list;
registration order in `backend/server.py:98-147`. New since 2026-05-02:
- `POST /api/studio/{kind}/{aid}/synisense-accept` (Phase 12.2 ITEM C)
- `GET /api/contexts/{cid}/documents/{doc_id}/paragraphs/{pid}/original` (Phase 12.2 ITEM B)

---

## 5. Data Models

Collections (indexes set in `backend/server.py:299-435`):

- **Identity**: `accounts`, `memberships`, `invitations`, `organisations`,
  `consent_decisions`, `login_attempts`, `auth_events`.
- **Contexts**: `contexts`, `committees`, `context_objects`, `audit_log`,
  `telemetry_events`.
- **Documents**: `documents`, `document_views` (uniq on
  `(doc_id, account_id, day)`), `document_shares`.
- **Signals**: `signals`, `signal_events`, `signal_actions`, `ask_messages`.
- **Briefings/briefs**: `briefings` (formal, M12), `briefs` (Catch-up, Prepare),
  `briefing_reads`. Two-collection split is intentional but flagged cosmetic.
- **Cycle**: `questions`, `reportees`, `checklists`, `submissions`, `reports`,
  `cycle_schedules`, `cycle_configs`.
- **Decks/Studio**: `decks`, `deck_outlines`, `deck_telemetry`, `studio_views`
  (uniq on `(artefact_kind, artefact_id, account_id, day_utc)`), `studio_shares`,
  `studio_blocks`.
- **Chat/Lens/Simulate/Plays**: `chats`, `chat_messages`, `chat_audit_log`,
  `lens_runs`, `lens_coach_sessions`, `simulations`, `plays`.
- **Solve**: `solve_clusters`, `solve_comparables`, `solve_sessions`,
  `solve_handoffs`, `solve_free_grants`, `solve_interest`.
- **LLM ops**: `llm_deep_usage` (uniq on `(account_id, surface, day_utc)`),
  `llm_validator_usage` (uniq on `(day_utc, surface)`).
- **Synisense (Phase 12.1)**:
  - `synisense_runs`: `{id, context_id, surface, mode, ts, account_id,
    input_sha256, spans, stats, shield_map_id, synisense_version}` — indexed
    on `(context_id, ts desc)`, `(surface, ts desc)`, `input_sha256`.
  - `synisense_shield_maps`: TTL on `expires_at`.
- **Strategic/Monitor**: `strategic_goals`.
- **Inbound**: `inbound_queue`, `inbound_queue_raw`.
- **Marketing/payments**: `blog_posts`, `blog_subscribers`,
  `early_access_registrations`, `enterprise_interest`, `payment_transactions`,
  `stripe_events`.
- **Sandbox**: `sandbox_pickups`.
- **Polymorphic**: `shares`, `comments`, `mentions`.

**Relationships**: `accounts (1..*) ↔ (1..*) contexts` via `memberships`.
Every content collection scopes to `context_id`. `studio_views` /
`studio_shares` polymorphic across briefings/decks/reports/blocks.
`audit_log` append-only. `solve_sessions → solve_handoffs → (briefs | decks |
cycle_questions)`. `synisense_runs` aggregates over `context_id ∪ account_id`
(Governance rollup uses `$or`).

---

## 6. Environment

### Backend `.env` (committed)
`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `APP_NAME`, `CORS_ORIGINS`,
`EMERGENT_LLM_KEY`, `AKKI_CRON_SECRET`, `CLAMAV_HOST/PORT/TIMEOUT_SECONDS`,
`ALLOW_UNSAFE_UPLOADS`, `STORAGE_BACKEND`, `S3_*`, `BILLING_ENABLED`,
`BACKUP_DIR`, `SYNISENSE_MASTER_KEY`, `SYNISENSE_POOL_SIZE`,
`SYNISENSE_USE_POOL`, `SYNISENSE_ALLOW_INSECURE`,
`SYNISENSE_LLM_FALLBACK_CAP/CONCURRENCY/TIMEOUT_MS`,
`SYNISENSE_SHIELD_MAP_TTL_HOURS`.

Conditionally set in deploy: `RESEND_API_KEY`, `POSTMARK_*`, `STRIPE_*`,
`LLM_MODEL_{FAST,STANDARD,DEEP}`, `VALIDATOR_DAILY_SOFT_CAP`,
`SYNISENSE_MASTER_KEY_v<N>`, `AKKI_ENV`, `FRONTEND_URL`,
`AKKI_AUTH_OBSERVE_RATE`, `AKKI_DEEP_*`.

### Frontend `.env`
`REACT_APP_BACKEND_URL`, `WDS_SOCKET_PORT`.

### External integrations
Emergent Universal Key (Anthropic + OpenAI + Gemini),
Resend (outbound),
Postmark (inbound webhook only),
Stripe (disabled),
ClamAV (live),
MinIO/S3,
APScheduler in-process,
Synisense in-house (no external service call other than optional Gemini
fallback via Emergent key).

### Test credentials
- Superadmin: `admin@akki.ai` / `AkkiAdmin2026!`
- Non-owner viewer: `viewer@akki.ai` / `Viewer2026!`

---

## 7. Known gaps / mocks / drift

1. **Phase 12.2 closeout BUG 1, 2, 3** — three live-preview defects flagged in
   `test_result.md` and the testing-agent dispatch. Fix pass in flight on
   2026-05-04. See `INVENTORY_2026-05-02.md` §7 item 1 for code-reading
   interpretation; live curl evidence supersedes.
2. **Cycle email-reply ingestion = stub** (`backend/routers/cycle.py:15`).
3. **Invitation email = stub log path on missing Resend** (`contexts.py:404`).
4. **In-app share email = stub** (`components/share/ShareModal.jsx:96`) —
   distinct from Studio Share-with-Chair (real Resend).
5. **Daily Review Phase B = stub** (drafted emails + extracted cycle questions
   backend-stubbed).
6. **Plays catalog = static stubs** — only `board_pack` + `pre_board` shipped.
7. **Stripe → Solve Pro entitlement flip = partial** (audit P1).
8. **Marketing copy honesty (Phase 12.3 carry)** — `pages/marketing/Plans.jsx`
   intentionally minimal; `Security.jsx` not re-anchored against Phase 12.1
   in-house engine. Phase 12.3 scoped, **not started**.
9. **`briefings` vs `briefs` collection split** — cosmetic.
10. **DEAL_CODENAME entity priority** — Phase 12.3 fine-tuning carry-over.
11. **`AppHome` flag switch** — `HomeV2.jsx` (598 ll) vs `LegacyAppHome.jsx`
    (571 ll) both code-resident. Cosmetic.
12. **Process pool stays disabled in dev** (`SYNISENSE_USE_POOL=false`) —
    uvicorn `--reload` is hostile to fork; scaffolding intact for prod flip.
13. **`CORS_ORIGINS=*` in committed `.env`** with `allow_credentials=True` —
    handled at runtime by `server.py:164-210` via `allow_origin_regex=".*"`.
14. **70+ pytest files** in `backend/tests/` — many require `EMERGENT_LLM_KEY`
    to fully execute.

---

_End of inventory. Generated 2026-05-04 against `/app` at HEAD of `main`._
_Companion to `INVENTORY_2026-05-02.md` and `PRODUCT_REVIEW.md`._
