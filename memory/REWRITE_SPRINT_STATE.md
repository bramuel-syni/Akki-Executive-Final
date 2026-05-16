# AKKI Rewrite Sprint — Canonical State

> READ FIRST after any handoff/compression. This file is the recovery surface.

## Sprint Goal
Full production rewrite per the 4 developer briefs in `/app/memory/briefs/`. Replaces ad-hoc LLM integration with the Synisense gateway architecture. 12-chunk QA plan (Chunks 7-12) PAUSED until rewrite completes.

## Source-of-Truth Documents
- `/app/memory/briefs/SYNISENSE.md`
- `/app/memory/briefs/SOLVA.md`
- `/app/memory/briefs/CHAT.md`
- `/app/memory/briefs/INTEGRATION.md`
- `/app/memory/docs/PRODUCT_FEATURES_REVIEW.md` (pre-rewrite baseline)

## Locked Decisions (user-approved)
1. Full production rewrite per the 4 briefs. NOT a shim.
2. 12-chunk QA plan PAUSED. Chunks 7-12 deferred to post-rewrite.
3. De-identification stack: regex → tenant entity dictionary → local spaCy `en_core_web_trf` (with `en_core_web_sm` fallback when `spacy-transformers`/torch unavailable). NO cloud LLM-NER.
4. Trust Receipts: HMAC-SHA256 + HKDF-derived per-tenant keys. Version `"v1"`.
5. Engine signals: seeded from existing Mongo with `derivation_source` markers. Real ingestion = Phase F.
6. `SYNISENSE_MASTER_SECRET` — dev fallback for now. Real secret arrives pre-Bank-QA.
7. `tenant_id` = existing `account_id`. Single-tenant-per-account. No new auth refactor.
8. PO defaults (locked 2026-05-13):
   - Cross-module document deletion → soft-delete with `deleted_at`; downstream signals/board packs show "source document deleted" banner.
   - "Around the Goals" → Solva sub-module that triangulates objectives ↔ cycle outcomes; stub the entry if spec is unclear, don't invent.
   - Akki-assigned Monitor status → **NOT** manually overridable.
9. Strict phase order: A → B → C → D → E → F. No skipping, no reordering.

## Phase Status Table
| Phase | Title | Status | QA findings absorbed | Close-out file |
|---|---|---|---|---|
| A | Synisense Foundation (Shield + Engine + Audit) | **complete** (2026-05-13) | — | `sprints/PHASE_A_CLOSEOUT.md` |
| B | LLM Call Migration | **complete** (2026-05-13) | 4: Generate Signals err, Take into Solva err, Add to Cycle err, Enhance Minutes err (all resolved by removing opaque catch-alls + Shield's canonical error format). 2 absorbed P1 risks: Solva single-session context_id scoping, SSE `repr(exc)` leaks. 2 items DEFERRED to Phase C: Document Reader Commentary loading state, sync→async conversion of 4 Doc Reader endpoints (524-prone) — both belong with the Phase C audit panel surface. | `sprints/PHASE_B_CLOSEOUT.md` |
| C | Chat Protective Layer + Audit Panel | **complete** (2026-05-13) | 5: chat overflow, archive flow, audit panel + 2 absorbed from Phase B (Doc Reader Commentary loading state, sync→async 4 Doc endpoints) — **all resolved**. Mode B inline-superscript annotation rendering + PDF privacy-report export deferred to a small follow-up patch (data + endpoints already in place). | `sprints/PHASE_C_CLOSEOUT.md` |
| D | Solva Backend Rewrite (UI unchanged) | **complete** (2026-05-16, fix bundle v1+v2 2026-05-16) | 1: framing-thin page leak — resolved by silent Layer 0 + question-bank-driven Layer 1 opening. Plus 3 fix-bundle defects (refusal gate, `invalidation_condition` leaks, ENT-only placeholder strip) closed in v1; family-wide `[[<UPPER>_<digits>]]` regex + macro-name strip + evidence-marker FAR heuristic closed in v2. All locked by 33 integration tests. Phase D code path has NO safety classifier — that's a Phase E item (legacy `solva_v2.py` has its own; the two paths will reach parity in Phase E). | `sprints/PHASE_D_CLOSEOUT.md` + `sprints/PHASE_D_FIX_BUNDLE.md` + `sprints/PHASE_D_FIX_BUNDLE_V2.md` |
| E | Solva Phases 2-4 (Tension / Guardrails / Polish) | **queued (next)** | — | — |
| F | Engine real signal generation | queued | 1: Monitor Akki status assignment mechanic | — |

## Deferred QA Findings (DO NOT TOUCH during rewrite)
14 items, pure UI/UX, no AI dependency. Resume after Phase F closes.
- Pulse 6: comments display, dual Resolved filter, save vs bookmark, drawer badges, citation removal, bullet points
- Cycle Manager 3: menu spacing, Activate Cycle cross-tab, duplicate Back/Next bars
- Monitor 7: Strategic Goals tabs/RAG/Achieved tab/category filter/NED parity/By Score dropdown/drawer rename
- Document Journal 3: delete icon (waits on cross-module-deletion PO answer), search bar in linked docs panel, side-drawer button parity
- Work Studio 3: destination picker for Add to Work Studio, remove icon, At Risk hover reveal
- Misc 4: Portfolio-first login flow, Context Bar role display, Bell icon broken page, context-switch loading state

## Scope Discipline Rules
- DO NOT fix anything in the deferred bucket while in rewrite phases.
- DO NOT invent product behavior on unanswered clarifications — apply the locked defaults OR park and surface.
- DO NOT touch surfaces outside the active phase's scope.

## Blocked Items (live list — append on encountering)
None at sprint start.

## Test Credentials Source
`/app/memory/test_credentials.md` — tester reads itself.

## Recovery Protocol After Handoff/Compression
1. Read this file.
2. Read `/app/memory/SYSTEM_STATE.md` for the latest patch close-out.
3. Read `/app/memory/sprints/PHASE_<X>_CLOSEOUT.md` for the most recently completed phase.
4. Resume from the next queued phase, OR continue the in-flight phase.
5. NEVER re-run a completed phase.
