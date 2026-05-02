# AKKI-Executive — Codebase Inventory (2026-05-02)

_Read-only audit generated against `/app` (GitHub: `bramuel-syni/Akki-Executive`, branch `main`). No code was modified to produce this file. Companion document to `PRODUCT_REVIEW.md`; where this disagrees with that doc, the running code is authoritative and the drift is tracked in §7 below._

---

## 1. Top-Level Structure

```
/app
├── backend/                         FastAPI + Motor monolith
│   ├── server.py                    App assembler, startup (indexes, seeds, schedulers)
│   ├── core.py                      DB handle, auth helpers, audit writer, membership guard
│   ├── requirements.txt             Python deps (133 lines)
│   ├── bm25.py                      Pure-Python BM25 over doc text
│   ├── briefings_service.py         Briefing composition logic
│   ├── citation_refs.py             Citation back-resolution
│   ├── documents_service.py         Upload pipeline, storage abstraction
│   ├── email_service.py             Resend wrapper (noop when key absent)
│   ├── llm_service.py               LLM proxy + regex shielding + validator
│   ├── llm_tier_quota.py            Race-safe deep-tier daily quota
│   ├── paragraph_anchors.py         Stable hash anchors for Reading Viewer
│   ├── reports_service.py           Cycle-report composer
│   ├── sandbox_service.py           Sandbox 10-stage streaming generator
│   ├── sandbox_templates.py         Six sector templates
│   ├── solve_clusters_seed.py       Solve cluster taxonomy seed
│   ├── solve_comparables_seed.py    27 anonymised Solve diagnoses
│   ├── solve_pdf.py                 Reportlab PDF export for Solve
│   ├── studio_sensitivity.py        Regex-ladder sensitivity classifier
│   ├── helpers/llm_json.py          Strict-JSON extraction helpers
│   ├── routers/                     50 domain routers (see §4)
│   ├── services/                    Infra wrappers (clamav, storage, stripe)
│   ├── scripts/                     bootstrap_prod.py, seed_* (one-off seeders)
│   ├── tests/                       ~60 pytest files
│   └── uploads/                     Per-doc local upload cache
├── frontend/                        React 19 / CRA-craco
│   ├── package.json                 Deps (§2)
│   └── src/                         Pages, components, contexts, hooks, lib
├── docs/                            PRODUCT_REVIEW, CHAT_CITATIONS_AUDIT, SYNISENSE_SCOPE, RUNBOOKS/
├── scripts/                         backup_mongo.sh, restore_mongo.sh, migrate_local_to_s3.py
├── memory/                          PRD, test_credentials.md, feature notes
├── test_reports/                    Pytest + screenshot artefacts
├── AUDIT_iter68.md, DEPLOY.md, design_guidelines.json, test_result.md
```

---

## 2. Tech Stack

**Frontend:** React 19, CRA wrapped by @craco/craco 7, react-router-dom 7, Radix UI primitives, TailwindCSS 3.4, framer-motion 12, sonner, recharts 3.6, react-resizable-panels, react-hook-form + zod, axios, lucide-react. Yarn 1.22.

**Backend:** FastAPI 0.110 / Starlette 0.37 / Uvicorn 0.25, Motor 3.3 / PyMongo 4.5, python-jose + PyJWT + passlib + bcrypt + pyotp, emergentintegrations 0.1, google-genai 1.71, openai 1.99, litellm 1.80, stripe 15, resend 2.29, boto3 (S3/MinIO), clamd (ClamAV), pypdf + reportlab + python-docx + pillow, APScheduler 3.10, pytest 9.

**Infra:** supervisor (backend :8001, frontend :3000). ClamAV + MinIO sidecars (Phase 10). MongoDB via `MONGO_URL`. Ingress: `/api/*` → backend, else → frontend.

---

## 3. Product Features (detected in code)

### 3.1 Accounts, Auth, MFA
`backend/routers/auth.py`, `backend/core.py`, `frontend/src/contexts/AuthContext.jsx`, `frontend/src/pages/{SignIn,SignUp,AccountSecurity}.jsx`. JWT register/login/refresh, brute-force lockout (`db.login_attempts`), TOTP MFA via pyotp+qrcode, `declared_role`, superadmin flag, sampled auth events (`db.auth_events`).

### 3.2 Contexts & Memberships
`backend/routers/{contexts,committees}.py`, `frontend/src/pages/{ContextPortfolio,NewWorkspace,TenantSettings,InviteAccept}.jsx`. CRUD + members + invitations + nested committees + context-object onboarding.

### 3.3 First Session (onboarding)
`backend/routers/first_session.py`, `frontend/src/pages/FirstSession.jsx`. Three-question intake → three doors (forward email / upload / run Solve). Guarded by `<FirstSessionGuard>` (App.js).

### 3.4 Documents & Reading Viewer (paragraph citations)
`backend/routers/{documents,document_engagement}.py`, `backend/paragraph_anchors.py`, `frontend/src/pages/ReadingView.jsx`, `frontend/src/components/reading/*`. Chunked upload → ClamAV + S3/MinIO → text extraction → stable `paragraphs[]` hash anchors → rail-commentary viewer → daily 03:00 UTC anchor sweep cron.

### 3.5 Studio (Briefings, Decks, Reports) + Sensitivity + Block Composer (Phase 8)
`backend/routers/{briefings,decks,cycle,studio,studio_blocks}.py`, `backend/studio_sensitivity.py`, `frontend/src/components/studio/{BlockComposer,ShareArtefactModal}.jsx`, `frontend/src/pages/{Decks,StudioComposerPage}.jsx`, `frontend/src/components/trust/ValidatedBadge.jsx`. Deterministic regex sensitivity classifier (PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED) + LLM tiebreaker. Signed JWT share tokens (30-day TTL). Block composer is wired (`server.py:76,140`).

### 3.6 Cycle Strip + Reports + Checklists + Responses
`backend/routers/{cycle,cycle_config}.py`, `frontend/src/pages/{Cycle,CycleSettings}.jsx`, `frontend/src/components/cycle/*`. Six-phase ribbon; reportee checklists → tokenised `/respond/:token`; minutes extract → narrative → cycle.

### 3.7 Daily Review (approval queue)
`backend/routers/daily_review.py`, `frontend/src/pages/DailyReview.jsx`, `frontend/src/components/review/*`. Keyboard-first batched queue. Phase A only — drafted emails and extracted cycle questions are backend-stubbed (`cycle.py:15`).

### 3.8 Signals + Ask + Signal Actions
`backend/routers/{signals_ask,signal_actions,admin_signal_kpi}.py`. LLM-grounded signal generation with `references[]`, per-signal recommendations, admin action heatmap.

### 3.9 Chat (Claude-shape)
`backend/routers/chat.py`, `frontend/src/pages/Chat.jsx`, `frontend/src/components/chat/ModelAvatar.jsx`. Untethered from contexts; SHA-256-chained audit with ZIP export including `verify.py`. Model selector (Claude Sonnet/Haiku 4.5, GPT-5.2, Gemini 2.5 Pro/Flash). Per-message `shielding_override`.

### 3.10 Prepare (Catch-up Briefs + Minutes)
`backend/routers/prepare.py`, `frontend/src/pages/Prepare.jsx`. Distinct `db.briefs` collection from formal `db.briefings`. Validator runs here via `validate_independent` in `llm_service.py`.

### 3.11 Solve (four-phase pause)
`backend/routers/{solve,solve_engine}.py`, `backend/solve_pdf.py`, `backend/solve_clusters_seed.py`, `backend/solve_comparables_seed.py`, `frontend/src/pages/{AppSolve,SolveLanding}.jsx`. Surface → Depth → Synthesis → Lock-in. 27 curated comparables. Monthly free-tier grant.

### 3.12 Depth Disclosure + Pro gating
`backend/routers/depth.py`, `frontend/src/hooks/useDepthStatus.js`, `frontend/src/components/depth/*`. Surfaces Lens / Simulate / Influence Map / Strategic Goals / Plays on evidence threshold.

### 3.13 Lens / Simulate / Monitor / Strategic Goals / Influence Map / Plays
Respective routers; Mon 08:00 UTC Influence Digest cron.

### 3.14 Inbound Email (Postmark) + Triage Queue
`backend/routers/{inbound_email,inbound_queue}.py`, `frontend/src/pages/InboundQueue.jsx`.

### 3.15 Cross-context Shares + Home stream
`backend/routers/shares.py`, `frontend/src/pages/SharedArtefact.jsx` (public `/shared/:token`).

### 3.16 Governance (Trust panel) + Audit
`backend/routers/{governance,audit}.py`, `frontend/src/components/governance/TrustPanel.jsx`.

### 3.17 Synisense (regex-only today)
`backend/routers/synisense.py`, `backend/llm_service.py` regex shielding. Scope doc: `docs/SYNISENSE_SCOPE.md`.

### 3.18 Sandbox (pre-auth demo)
`backend/routers/sandbox.py`, `backend/sandbox_service.py`, `backend/sandbox_templates.py`, `frontend/src/pages/{Sandbox,SandboxGenerating,QuickResults}.jsx`.

### 3.19 Marketing + Blog (Exco360)
`backend/routers/{blog,early_access,enterprise,product_features}.py`, `frontend/src/pages/marketing/*`. Tue 10:00 UTC weekly cron.

### 3.20 Billing (Stripe) — Phase 10 hardened
`backend/routers/billing.py`, `backend/services/stripe_webhook.py`. Boot guard (`server.py:219-227`) refuses to start with `BILLING_ENABLED=true` but no key. Idempotency indexes on startup. Disabled by default.

### 3.21 LLM Quota + Deep-tier Spend + Admin surfaces
`backend/routers/{llm_quota,admin_llm_spend,admin_health,admin_sandbox_kpi,admin_signal_kpi,admin_auth_events}.py`, `frontend/src/pages/admin/*`.

---

## 4. Routes

### Frontend (`frontend/src/App.js`) — grouped
Public: `/`, `/solve`, marketing pages, `/blog*`, `/respond/:token`, `/shared/:token`, `/signin` + aliases, `/signup` + aliases, `/invite/:token`, `/sandbox*`.
Auth-gated (`<ProtectedRoute>` + `<FirstSessionGuard>`): `/app/first-session`, `/app`, `/app/cycle`, `/app/monitor`, `/app/plays[/:id]`, `/app/workspace`, `/app/prepare`, `/app/inbound-queue`, `/app/activity`, `/app/simulate`, `/app/lens`, `/app/chat`, `/app/influence`, `/app/quick-results/:cid/:docId`, `/app/learn[/:id]`, `/app/manage`, `/app/enterprise`, `/app/decks[/:deckId]`, `/app/studio/composer/:kind/:artefactId`, `/app/solve`, `/app/documents/:id`, `/app/contexts[/new]`, `/app/settings[/cycle,/billing]`, `/app/review`, `/app/security`.
Admin: `/admin[/health,/sandbox-kpi,/signal-kpi,/llm-spend,/auth-events]`.

### Backend — 50 routers, all `/api` prefixed
See `PRODUCT_REVIEW.md` Appendix A for the exhaustive method × path list; registration order in `backend/server.py:98-147`.

---

## 5. Data Models

Collections (see `server.py` `on_startup` for indexes): `accounts`, `contexts`, `memberships`, `invitations`, `audit_log`, `telemetry_events`, `login_attempts`, `consent_decisions`, `organisations`, `documents`, `signals`, `ask_messages`, `briefings`, `briefs`, `decks`, `deck_outlines`, `deck_telemetry`, `reports`, `studio_views`, `studio_shares`, `studio_blocks`, `inbound_queue`, `inbound_queue_raw`, `comments`, `mentions`, `chats`, `chat_messages`, `chat_audit_log`, `solve_sessions`, `solve_clusters`, `solve_comparables`, `solve_handoffs`, `solve_free_grants`, `llm_deep_usage`, `auth_events`, `cycle_configs`, `document_views`, `document_shares`, `shares`, `early_access_registrations`, `stripe_events`, plus feature-specific stores (`lens_runs`, `simulations`, `plays_catalog`, `strategic_goals`, `monitor_*`, `blog_posts`, `blog_subscribers`, `agenda_evolution`, `pipeline_events`, `walkin_questions`).

Relationships: `accounts 1..* ↔ 1..* contexts` via `memberships`. Every content collection scopes to `context_id`. `studio_views`/`studio_shares` polymorphic across briefings/decks/reports/block drafts. `audit_log` append-only. `solve_sessions → solve_handoffs → (brief|decks|cycle)`.

---

## 6. Environment

Backend `.env` keys: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `APP_NAME`, `CORS_ORIGINS`, `EMERGENT_LLM_KEY`, `AKKI_CRON_SECRET`, `CLAMAV_HOST/PORT/TIMEOUT_SECONDS`, `ALLOW_UNSAFE_UPLOADS`, `STORAGE_BACKEND`, `BILLING_ENABLED`, `BACKUP_DIR`. Conditionally: Stripe/Resend/Postmark secrets, `LLM_MODEL_{DEEP,STANDARD,FAST}`, `FRONTEND_URL`, S3/MinIO creds.

Frontend `.env`: `REACT_APP_BACKEND_URL`, `WDS_SOCKET_PORT`.

External integrations: Emergent Universal Key (Claude + Gemini + OpenAI), Gemini 2.5 Flash validator, Resend, Postmark, Stripe (disabled), ClamAV, MinIO/S3, Synisense (regex-only), BM25 (capped).

---

## 7. Known gaps / mocks / drift

1. **Phase 11 active work — ITEM A:** `GET /api/public/studio/read/{token}` exists in `studio.py:707`; 30-day TTL present; watermark + redaction assertion pending. `/share/:token` alias route pending.
2. **Phase 11 active work — ITEM B:** Validator fan-out to Decks/Reports/Solve not yet wired (only Briefings/Catch-up briefs call `validate_independent` today).
3. **Phase 11 active work — ITEM C:** Chat today has no retrieval pipeline; reply text has no structured `citations[]`; no click-through to Reading Viewer.
4. **Synisense:** regex-only today; live URL swap deferred (Phase 12).
5. **Stripe → Solve Pro entitlement flip:** incomplete; latent (`BILLING_ENABLED=false`).
6. **Daily Review Phase B:** drafted emails + extracted cycle questions are backend-stubbed (`cycle.py:15`).
7. **Plays catalog:** static `_PLAY_STUBS` seeded at boot; no admin CRUD.
8. **Invitation email send:** `contexts.py:404` logs `[invite-email-stub]` when Resend unkeyed.
9. **`briefs` vs `briefings` split:** two collections, two UX paths — cosmetic.
10. **Cross-Board Pulse:** Home v2 toggle, not a dedicated surface.
11. **`documents_service.py:4`:** `virus_scan_stub` is RETIRED — ClamAV is the live path. `studio_blocks.py:815` comment still references the retired stub (cosmetic).
12. **`AppHome` flag switch:** `HomeV2` vs `LegacyAppHome` — both code-resident.
13. **`PRODUCT_REVIEW.md` drift:** says `studio_blocks.py` is not wired and `BlockComposer.jsx` doesn't exist. Both are **false** as of Phase 8 wire-up. Doc fix is Phase 11 item D.

---

_End of inventory. Generated 2026-05-02 against `/app` at HEAD of `main`. Kept as a working note; `PRODUCT_REVIEW.md` remains the narrative document._
