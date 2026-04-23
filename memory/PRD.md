# AKKI Sandbox — Product Requirements Document (PRD)

## Original problem statement
AKKI is a Context-primary intelligence platform for Non-Executive Directors (NEDs) and
operating Executives. The BRD pivoted from v1.0 (Tenant B2B) → v3.0 (Context-primary) →
v4.0 (Build Sequence — 18 modules across 5 streams with prescriptive design mandates).
The user selected **Path A (v4.0 Free Tier)**: follow v4.0 module boundaries but skip any
module that requires a paid/external service.

## User personas
- **Non-Executive Director (NED)** — Serves on one or more boards. Needs cross-board
  pattern awareness, pre-board briefings, and open-thread tracking.
- **Operating Executive** — Prepares for a specific board meeting. Needs pre-board prep,
  team roll-up, org highlights, and post-board follow-up tracking.
- **Dual** — Both roles; switches acting-role from the top nav role switcher.
- **Reportee** — Submits reports to an Executive (minimal scope).

## Core architecture
- **Frontend**: React + Tailwind + Shadcn UI. Brand: navy `#0A1F44`, gold `#C9A961`.
- **Backend**: FastAPI + MongoDB, custom JWT (bcrypt) + optional TOTP MFA.
- **LLM**: Emergent Universal Key → Claude Sonnet 4.5 via emergentintegrations.
  Deterministic mock fallback if key missing.
- **Mocked in-process** (paid equivalents deferred): Synisense trust/shielding layer,
  S3 (local disk at `/app/backend/uploads`), virus scan, vector DB (prompt-inline grounding).

## Surfaces
| # | Surface | v4.0 Module | Status |
|---|---------|-------------|--------|
| 1 | Home (role-specific: NED / Executive) | M15/M16 | **Live** |
| 2 | Workspace (60/40 split + persistent Ask) | M18 | **Live** |
| 3 | Highlights (3-column Twitter-style feed) | M17 | **Live** |
| 4 | Ask (top-level) | M13 | **Live** |
| 5 | Document Viewer (`/app/documents/:id`) | M7 | **Live** |
| 6 | Learn | M9 | Locked |
| 7 | Settings | M0 | **Live** |

## Implemented (by date)
### 2026-04-22 — v3.0 Path B MVP
- G1 Scaffold, M0 Contexts/Memberships/Orgs model, M1 shell+switchers+Cmd-K,
  M2 onboarding wizard + Context Object versioning, M3 document upload pipeline
  (PDF/DOCX/TXT), M5 backend signals + ask (grounded, shielded).
- M5 frontend — Highlights + Ask pages wired.
- Brute-force lockout bug fixed (ident keyed on email only, not ip:email).

### 2026-04-23 — v4.0 Path A Phase 1 (UI restructure)
- **Reusable `AskPanel`** component — used by both `/app/ask` and Workspace right pane.
  Supports `onCitationClick(docId)` so `[doc:xxx]` citations can drive behaviour in the host.
- **`DocumentViewer`** page (`/app/documents/:id`) with extracted-text render +
  outline rail (heading detection heuristic) + back/download controls.
- **Workspace 60/40 split** (M18): left pane shows either the documents browser
  (upload + list) or the selected document viewer; right pane is a persistent AskPanel.
  Draggable divider (clamped 35–75%). Clicking a `[doc:xxx]` citation in the right
  Ask panel loads that document in the left pane.
- **Highlights 3-column feed** (M17): left filter rail (type/trust/confidence),
  central Twitter-style feed with relative timestamps, right rail with at-a-glance
  counts + source documents + Ask CTA. Source chips link to the Document Viewer.
- **`NedHome`** (M15): board grid sorted by meeting proximity, cross-board pulse
  card when ≥2 NED contexts and signals exist, add-a-board affordance. Uses stable
  pseudo-random `daysUntilNextMeeting` as placeholder until M6 Integrations.
- **`ExecHome`** (M16): 4-band layout — Pre-Board Prep, Team Reporting, Org
  Highlights, Post-Board Follow-up — with cadence-driven ordering (approaching /
  mid-cycle / post-meeting).
- **`AppHome`**: onboarding gate hero when audit incomplete; otherwise routes to
  NedHome or ExecHome based on `activeRole`.
- Nested `<button>` hydration warning fixed in Workspace doc row (div[role=button]
  with `stopPropagation` on the trust selector).

## Test credentials
See `/app/memory/test_credentials.md`. Admin: `admin@akki.ai` / `AkkiAdmin2026!`.

## Backend regression suite
`/app/backend/tests/test_akki_v3.py` — 55 pytest cases (M0–M5). Iteration 2 smoke
tests (15/15) confirm auth + documents + signals + ask pipeline stable after frontend
restructure.

## Prioritized backlog

### P0 — Path A Phase 2 (backend expansion, no paid services)
- [ ] **M12 Briefings** — auto-compose briefings from generated signals with opening
      paragraph + evidence drawers + PDF/DOCX export (reportlab + python-docx) + versioning.
- [ ] **M14 Lens Room** — 6-framework stress-testing engine embedded in Workspace
      (First Principles, Customer Obsession, Systems Thinking, Capital Discipline,
      Stakeholder Integration, Organisational Culture).
- [ ] **M11 Event-driven signals pipeline** — refactor `/signals/generate` into a
      `document.extracted` → candidate → mock-Synisense verify → persist flow so the
      real Synisense microservice can be dropped in later via URL swap.
- [ ] **M13 Hybrid retrieval for Ask** — upgrade inline grounding to BM25 keyword
      scoring across chunks (no external vector DB yet).
- [ ] **M5 Upload channels** — secure-link uploads and mobile camera capture
      (email-to-upload deferred; needs SMTP/Mailgun which is paid).
- [ ] **Refactor `server.py`** (1592 lines) into `/app/backend/routers/{auth,
      contexts,documents,signals,ask,audit}.py`.

### P1 — Polish
- [ ] Onboarding wizard end-to-end frontend subagent coverage.
- [ ] Minor: POST `/api/auth/refresh` should return `access_token` in body for
      bearer-only clients.
- [ ] Minor: Add top-level `token` field to invitation creation response.

### P2 — Paid / external integrations (explicitly deferred)
- [ ] **M4 Stripe Billing** — sponsored seat subscriptions (test key available in pod).
- [ ] **Real Synisense** — replace mock-shielding module with real microservice.
- [ ] **Real vector DB** — Pinecone or pgvector.
- [ ] **M6 Integrations** — Google Calendar, board portals (Diligent / BoardPaQ).
- [ ] **Clerk / Auth0** — v4.0 M1 preference; we use custom JWT (recommended to keep).
- [ ] **Unstructured.io** — richer extraction than our `pypdf` + `python-docx`.
- [ ] **ClamAV / VirusTotal** — real virus scan (we use a stub).

## Recent fixes
- **2026-04-23** — Workspace doc row nested-button hydration warning: outer wrapper
  converted to `<div role="button" tabIndex={0}>` with keyboard handler; TrustChip
  wrapped in a `stopPropagation` span so changing trust doesn't open the document.
- **2026-04-22** — Brute-force login lockout: was keyed on `ip:email`; changed to
  email-only because Kubernetes ingress rotates `request.client.host`. Verified
  5×401 → 429 on 6th attempt.
