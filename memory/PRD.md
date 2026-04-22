# AKKI Sandbox — Product Requirements Document (PRD)

## Original problem statement
AKKI is a Context-primary intelligence platform for Non-Executive Directors (NEDs) and
operating Executives. BRD v3.0 (user-uploaded) replaced the original v1.0 Tenant-scoped
B2B spec mid-session. User and agent agreed on **Path B — Scoped v3.0 MVP** to fit within
the credit budget, covering Modules M0, M1, M2, M3, and a simplified M5. Paid/external
services (Stripe, real Synisense, real vector DBs) are deferred or mocked.

## User personas
- **Non-Executive Director (NED)**: Serves on one or more boards. Needs cross-board
  pattern awareness, pre-board briefings, and open-thread tracking.
- **Operating Executive**: Prepares for a specific board meeting. Needs pre-board prep,
  team report roll-up, and post-board follow-up tracking.
- **Dual**: Both roles — switches acting-role from the top nav.
- **Reportee**: Submits reports to an Executive (minimal scope).

## Core architecture
- **Frontend**: React + Tailwind + Shadcn UI, custom brand (navy `#0A1F44`, gold `#C9A961`).
- **Backend**: FastAPI + MongoDB, custom JWT (bcrypt) + optional TOTP MFA.
- **LLM**: Emergent Universal Key → Claude Sonnet 4.5 (via emergentintegrations lib)
  with a deterministic mock fallback if the key is missing.
- **Mocked**: Synisense trust/shielding layer, S3 (local disk at `/app/backend/uploads`),
  virus scan, vector DB (we inline extracted text into the prompt).

## Surfaces (six, per BRD §13)
| # | Surface | Module | Status |
|---|---------|--------|--------|
| 1 | Home | M0/M1 | **Live** |
| 2 | Workspace | M3 | **Live** |
| 3 | Highlights | M5 | **Live** |
| 4 | Ask | M5 | **Live** |
| 5 | Learn | M9 | Locked |
| 6 | Settings | M0 | **Live** |

## What's implemented (as of 2026-04-22)
- **G1 Scaffold** — Custom JWT auth (register/login/logout/refresh), bcrypt hashing,
  TOTP MFA (QR setup → verify → disable), login brute-force lockout (5 attempts → 15 min),
  Settings + Account Security pages.
- **M0 Data model** — Contexts (4 types: ned_personal, ned_sponsored,
  executive_personal, executive_enterprise), Memberships with role + sub_role +
  data_ownership + provisioning, Audit log on every mutation, Telemetry events,
  Invitations (token-based, 7-day expiry, email-bound accept).
- **M1 Shell** — Top navy header, left nav with six surfaces, context switcher
  (grouped Personal / Sponsored), role switcher (only shown when account is dual-capable),
  ⌘K command palette (switch context + add context + settings).
- **M2 Onboarding** — Role declaration, 7-question resumable audit wizard branching by
  declared_role, Context Object (versioned) stored in `context_objects` collection,
  mirrored onto `contexts.progress_state`.
- **M3 Workspace** — Multipart upload (`.pdf/.docx/.txt/.md/.rtf`, 25 MB limit),
  virus-scan stub, local disk storage, PDF/DOCX/TXT extraction, data-trust chip
  (trusted/mixed/weak), archive + download, detail drawer with extracted text preview.
- **M5 Highlights** — Signals generation (risks/opportunities/gaps), confidence chips,
  source citations, dismiss flow, focus-prompt input, summary by type.
- **M5 Ask** — Grounded Q&A composer (⌘/Ctrl+Enter), answer rendered with inline
  `[doc:xxx]` citation chips, source pills with doc name + trust, persistent history
  sorted oldest-first.
- **Audit log & Export** — Audit viewer per context, full JSON export endpoint.

## Test credentials
See `/app/memory/test_credentials.md`.

## Backend regression suite
`/app/backend/tests/test_akki_v3.py` — 55 pytest cases covering M0–M5.
Last run (2026-04-22): **55/55 pass** (brute-force lockout fix verified).

## Prioritized backlog (P0 = next up)
### P0 — Stability & polish
- [ ] Split `server.py` (1592 lines) into `/app/backend/routers/{auth,contexts,documents,signals,ask,audit}` modules.
- [ ] Onboarding wizard UI tested end-to-end by subagent (currently only CTA verified).

### P1 — Non-paid module expansion (no 3rd-party costs)
- [ ] **M4 Consent modal** — sponsored-seat consent UI + `consent_decisions` collection writes.
- [ ] **M7 Universal Search** — promote ⌘K to search docs, signals, ask history, and members.
- [ ] **M8 Workspace editor** — tiptap-based co-authoring in the Workspace (read/write notes that become context documents).
- [ ] **M9 Learn** — role-tuned curriculum surface (static seed library to start).

### P2 — Paid / external integrations (explicitly deferred)
- [ ] **M4 Stripe Billing** — sponsored seat subscriptions (test key exists in pod env).
- [ ] **Real Synisense** — replace mock-shielding module with real microservice.
- [ ] **Real vector DB** — Pinecone or pgvector for RAG grounding beyond the 40 KB inline budget.
- [ ] **M6 Integrations** — Google Calendar, board portals (Diligent / BoardPaQ).

## Recent fixes
- **2026-04-22** — Brute-force lockout: was keyed on `ip:email`, but Kubernetes ingress
  gives varying `request.client.host` values, so each attempt was a new identifier.
  Changed to key on email only. Verified via curl: 5 × 401 → 429 on attempt 6.
- **2026-04-22** — Highlights/Ask frontend surfaces built, wired to existing backend
  endpoints, unlocked in `AppShell` nav and `AppHome` tiles.
