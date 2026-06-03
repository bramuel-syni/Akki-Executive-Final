# MASTER_STATE.md
**Canonical state file. Single source of truth.**
Read first every dispatch. Update at every phase close.

---

## Section 1 — Discipline Rails (verbatim)

**R1** — MASTER_STATE.md is the single source of truth. Read first every dispatch; updated at every phase close.
**R2** — Intent Pre-Read mandatory before any code dispatch. User approval in writing required. No approval = no dispatch.
**R3** — A phase is "done" only when matrix items move to ✅ AND tester journey-completion passes (NOT surface-render).
**R4** — Lockdown test set per phase ≤10 tests. Full regression only at phase close.
**R5** — Root-cause-first: ground-truth read on product code BEFORE any harness extension or workaround.
**R6** — No side quests. Anything outside the approved Intent Pre-Read goes to backlog.
**R7** — Antiforget continuity check at every session boundary; surface partial antiforget immediately.

---

## Section 2 — Decision Log

Verbatim, dated:

- **D1** (approved 2026-06-03): Run QA cleanup track and Analyze redesign track in PARALLEL.
- **D2** (approved 2026-06-03): LLM ON from day 1 — Solva v2 synthesis enabled from first Analyze ship; user will absorb upgrade complications as they arise.
- **D3** (approved 2026-06-03): Per-file analysis + merging at the observation/intelligence layer. Plus a chat/objective input surface on the drawer for synchronized analysis.
- **D4** (approved 2026-06-03): "Analyze Journal" listing (mirrors Documents library). Retain context memory from excel sheets; DELETE the excel binary on session close. Return-visit shows analysis + notes history. Chats live in chats, not in journal.
- **D5** (approved 2026-06-03): C1 → C2 cluster order confirmed for QA track.
- **D6** (approved 2026-06-03): Intent Pre-Read ritual before every phase confirmed.
- **D-extra** (approved 2026-06-03): Drawer chrome organized like documents drawers — clean, neat, intuitive (topline statistics, notes, tabs).

---

## Section 3 — The 29-Bug Matrix (verbatim from user's pasted brief)

Status legend:
- ✅ SHIPPED — verified in prod (or shipped in preview, awaiting prod deploy)
- 🟡 PARTIAL — shipped with known gap
- ❌ OPEN — not yet built
- 🚧 USER-BLOCKED — waits on external action (creds, env var, console config)

### C1 · Email infra (P0)
- Magic link not sent after signup → ✅ SHIPPED (P1-B, gated on `COHORT_EMAILS_ENABLED=true`)
- Magic link invalid (Fig 43) → ✅ SHIPPED (C1-revised Phase B — 6 distinct error codes)
- Email Reply 550 "Mailbox not found" (Fig 42) → 🚧 USER-BLOCKED (SendGrid Inbound Parse console URL needs Basic Auth embedded + `%25` encoding)
- P8 inbound trust loop → 🚧 USER-BLOCKED (same)

### C2 · Auth / OAuth (P0)
- Sign-in lands at `/` not `/signin` (Fig 20) → ❌ OPEN
- Google sign-in fails (Fig 21) → 🚧 USER-BLOCKED (needs GCP OAuth creds)
- Post-redirect error (Fig 22) → ❌ OPEN
- "Re-enter password" toast (Fig 22) → ✅ SHIPPED (P0-C OAuth `last_activity_at` refresh)
- Continue redirect lost context (Fig 23→24) → ✅ SHIPPED (P0-B Card 4)
- No first-login password prompt → ✅ SHIPPED (C1-revised Phase A)

### C3 · Onboarding card routing (P0)
- "Create your first cycle" → Task Manager (Fig 2 vs 3) → ✅ SHIPPED (per spec G21 = Cycle Setup Wizard)
- "Upload a document" → Document Journal (Fig 4) → ✅ SHIPPED (P0-B Card 2)
- "Try the Demo" → Home (Fig 5) → ✅ SHIPPED (per spec G22 = Cycle Manager `/app/cycle`)
- "Continue" lands on Work Studio with context (Fig 24) → ✅ SHIPPED (P0-B Card 4)

### C4 · Cross-feature state propagation (P0)
- Generate Brief errors despite intelligence + signals (Fig 25.1, 25.2) → ✅ SHIPPED (P0-A)
- Doc-extracted signals don't appear in Pulse (Fig 31) → ✅ SHIPPED (P1-A)
- Doc-extracted questions have no surface (Fig 33→34) → ❌ OPEN
- "Open questions" tile shows 0 → ❌ OPEN

### C5 · Task Manager lifecycle (P1)
- No Commission button on Draft (Fig 41) → ❌ OPEN
- Task closure flow not implemented (per spec) → ❌ OPEN
- Filter tab count badges missing (Fig 40) → ❌ OPEN
- "View more" link has no destination (Fig 40) → ❌ OPEN

### C6 · Questions feature (P1)
- Filter by status → ✅ SHIPPED (Q4Y)
- Sort → ✅ SHIPPED (Q4Y dead dropdown wired)
- Side drawer with full Q + status + related doc → 🟡 PARTIAL (drawer exists; related-doc field not surfaced)
- "Use in Solva" CTA → ✅ SHIPPED (Q4Y)
- "Use in Chat" CTA → ✅ SHIPPED (Q4Y)
- "Share" CTA → ❌ OPEN
- "Mark as Answered" CTA → ✅ SHIPPED (Q4Y)
- Response association → ❌ OPEN
- Reopening flow → ❌ OPEN
- Response history → ❌ OPEN

### C7 · Document workflow polish (P2)
- Notes save UX unclear (Fig 26) → ❌ OPEN
- Send Share "Field required" false-positive (Fig 27) → ❌ OPEN
- Upload Document button consolidation (Fig 29 vs 30) → ✅ SHIPPED (Cleanup Task D)
- Calendar edit modal literal `SELECTED — COMMITS ON SAVE CHANGES` placeholder leakage (Fig 32) → ❌ OPEN

### C8 · UI / copy polish (P2)
- "Begin" button text invisible (Fig 7) → ❌ OPEN
- Generic salutation "there" instead of first name (Fig 8) → ✅ SHIPPED (Cleanup Task B)
- Hidden black callout under Help (Fig 8) → ✅ SHIPPED (Cleanup Task C)

### Bug #30 — Forecaster column-pair picker
- `forecast_invalid: workbook_analyzer.forecaster: need at least 3 (date, value) pairs to fit` on 28,626-row workbook with valid Date + Actual Sales columns → ❌ OPEN — folds into Analyze redesign Phase 3 (forecast moves into Solva narration) but the underlying picker still needs fixing.

**Matrix count audit (Honesty Protocol — surfaced per R7):** This section reproduces every line you pasted verbatim. The line-by-line count is C1=4 + C2=6 + C3=4 + C4=4 + C5=4 + C6=10 + C7=4 + C8=3 + Bug #30=1 = **40 items**, not 30. The matrix label is preserved as "29-Bug Matrix" per your brief's wording, but the audit floor in the verification step (≥30) is comfortably exceeded. No items were dropped or added; the count divergence is in the pasted brief itself, not in this reproduction. Flag for confirmation at next dispatch.

---

## Section 4 — Two Tracks Status

### Track A — Analyze Journal redesign
- Phase 1 (Foundation): Backend Analysis entity + multi-file upload + 250MB + session-close excel deletion + .xlsx/.docx exports → ❌ NOT STARTED (Intent Pre-Read pending user approval)
- Phase 2 (Chrome): Drawer mirroring Documents pattern + Analyze Journal listing + chat/objective input → ❌ NOT STARTED
- Phase 3 (Synthesis): Solva v2 narration + Bottom Line + drill-down tabs (What changed / What's likely next / What's odd / Sources / Export). Bug #30 folded here. → ❌ NOT STARTED
- Phase 4 (Multi-workbook + Versioning): Cross-file observation synthesis + refresh-creates-new-version + notes history → ❌ NOT STARTED

### Track B — QA cleanup
- Phase B1 (small mechanical): C2 Sign-in landing + C2 Post-redirect error + C8 "Begin" button invisible → ❌ NOT STARTED
- Phase B2 (large): C5 Task Manager lifecycle (Commission + Closure + Tab badges + View more) → ❌ NOT STARTED
- Phase B3 (feature wiring): C6 Questions Share + response association + reopening + history + related-doc-in-drawer → ❌ NOT STARTED
- Phase B4 (cross-feature): C4 doc-extracted Questions surface + Open questions tile count → ❌ NOT STARTED
- Phase B5 (polish): C7 Notes UX + Send Share false-positive + Calendar SELECTED placeholder leak → ❌ NOT STARTED

---

## Section 5 — User-Side Blockers (no code action possible)

- SendGrid Inbound Parse console URL: format `https://user:URL_ENCODED_PASS@inbound.akki.syni.ai/api/inbound/sendgrid` with `%` encoded as `%25` (unblocks C1 Email Reply 550 + P8 inbound loop)
- Google GCP OAuth creds (unblocks C2 Google sign-in flow)
- Prod env: `COHORT_EMAILS_ENABLED=true` (without this, cohort approval emails won't send in prod)
- Prod env: `POSTMARK_WEBHOOK_SECRET` decision — keep env var OR request follow-up to remove boot-guard at `server.py:573`
- Optional prod cleanup: `python3 /app/backend/migrations/cleanup_postmark_fixtures.py`

---

## Section 6 — Active Phase

None. Awaiting user approval on Intent Pre-Reads for Track A Phase 1 and Track B Phase 1.

---

## Section 7 — Last Updated

- **Written:** 2026-06-03T20:04:22Z
- **Agent:** discipline-step-1
- **Mode:** read-only on /app/memory + matrix; ZERO product code touched; ZERO tests touched; ZERO env changes.
- **File-creation scope:** this file only.
