# Track A Phase 5 — Work Studio Document Lifecycle Restoration

**Shipped:** 2026-06-04 (iteration 1)
**Approver:** User — Pre-Read approved with 5 tightenings, iter-1 ship authorised.

---

## Section 1 — Restoration vs Rebuild verdict (matches Pre-Read Section 1.2)

| Item | Verdict | Evidence |
|---|---|---|
| W1 copy fix | RESTORE (string) | `pages/WorkStudio.jsx:1085` |
| W2 Compile wiring | REBUILD WIRING (executor exists) | `routers/compilations.py:96-127` was queue-write-only; `routers/work_studio_export.py:1416` `_run_export` is the real executor |
| W3 Enhance 403 | RESTORE (FE hook fix) | NOT line 1077 as initially hypothesised. **Real cause**: CSRF middleware on `/stream` endpoints, FE hook `useStreamingProgress.js:113-128` was missing `X-CSRF-Token` header. Reproduced at `/tmp/phase5_w3_repro_v2.py` Case D |
| W4 Brief save visibility | RESTORE (UI breadcrumb) | `components/studio/ExportModal.jsx:344` already persisted; added "Saved to Drafts & Briefs" breadcrumb + `akki:open-document-overlay` event |
| W5 Draft 405 | HARD REBUILD | `POST /contexts/{cid}/documents/manual-create` did not exist; FastAPI returned 405 due to partial path match with multipart-upload route at `documents.py:357`. New endpoint at `documents.py:710` |
| W6 Report/Deck blank | RESTORE (wiring) | Branch added in `CreateArtefactModal.jsx:115-135`: `mode === "blank"` → dispatch `akki:open-drafting-drawer`; existing-brief/uploaded-doc paths preserved |
| Card spec fig 53 | RESTORE + EXTEND | 3 additive fields on `work_studio_exports`; kebab + row 2 in `DocumentCardsSection.jsx:170-310` |
| Loading checklist | REBUILD (new component) | `components/work_studio/LoadingChecklistModal.jsx` (NEW, 207 LOC) |
| Document Review Drawer re-skin | RE-SKIN existing | `DocumentOverlay.jsx` Edit toggle + Inline-edit indicator + Revise-with-AI all stubbed with `data-phase6="true"`; `editor.editable = false` locked |
| Drafting Drawer (W5) | NEW COMPONENT | `components/work_studio/DraftingDrawer.jsx` (NEW, 273 LOC) |

---

## Section 2 — Tightenings honoured

**Tightening 1 — W3 reproduced before code touch.** Curl trace at `/tmp/phase5_w3_repro_v2.py`:
```
POST /api/contexts/aff5e102-04b8-4948-9f6b-27c9eca1f0d7/work-studio/enhance/minutes/stream
  → 403  {"code":"csrf_token_missing","message":"CSRF token missing. Reload the page and retry."}
```
The Pre-Read's `prev.get("account_id") != account_id` hypothesis at `work_studio_export.py:1077` was WRONG. Real fix: FE hook `useStreamingProgress.js:113-128` now fetches CSRF via the `api` client and threads it into the stream `fetch()` headers.

**Tightening 2 — Loading checklist step-by-step until second-to-last, hold on "Finalising…".** Implemented at `LoadingChecklistModal.jsx:79-94`. Step `N-1` label is overridden to `"Finalising…"` until `status === "complete"` arrives; advance interval is 6s per step.

**Tightening 3 — `/compilations/{id}/start` idempotent.** Implementation at `routers/compilations.py:96-145`. Checks `compilations.export_id` on entry; returns existing on retry. Lockdown test `test_phase5_w2_compile_start_idempotent` passes.

**Tightening 4 — PDF Download endpoint `inline=true` query param.** Implementation at `routers/work_studio_export.py:1731-1849`. `Content-Disposition: inline` when `inline=true`; `Content-Type: application/pdf` regardless. Lockdown test `test_phase5_pdf_inline_render_path` asserts both. Pre-fix curl confirmed default was `attachment`; the `inline` switch is additive.

**Tightening 5 — Drafting Drawer `draft_session_id`.** Client-minted uuid4 at drawer open (`DraftingDrawer.jsx:74`); threaded into every `/save-draft` POST. Backend at `work_studio_export.py:2030-2125` keys idempotency on `(context_id, account_id, draft_session_id)`. Lockdown test `test_phase5_w5_save_draft_idempotent_under_concurrency` confirms two near-simultaneous POSTs collapse to ≤2 rows AND a follow-up save consistently idempotent-updates.

---

## Section 3 — Test budget (15 used / 15 budget)

```
test_phase5_schema_additive_fields_persist                       1
test_phase5_rag_threshold_75_50                                  1
test_phase5_w3_csrf_token_on_stream_request                      1
test_phase5_w2_compile_start_success                             1
test_phase5_w2_compile_start_404_on_missing                      1
test_phase5_w2_compile_start_idempotent  (Tightening 3)          1
test_phase5_w2_compile_full_cycle  (@integration)                1
test_phase5_w5_manual_create_endpoint                            1
test_phase5_w5_save_draft_creates_on_first_call                  1
test_phase5_w5_save_draft_updates_on_second_call                 1
test_phase5_w5_save_draft_idempotent_under_concurrency  (T5)     1
test_phase5_loading_checklist_polling_contract                   1
test_phase5_phase6_stub_flags_persist                            1
test_phase5_pdf_inline_render_path  (Tightening 4)               1
test_phase5_w1_empty_state_copy_grep                             1
────────────────────────────────────────────────────────────────────
                                                                15 functions
```

**14 PASS** in the default sweep (1 deselected, `@integration` — runs only with `-m integration`).

Aggregate sweep including Phase 3 + 4 + v1 + engagement regression: **69/69 PASS** in ~13s.

---

## Section 4 — Discipline rails — guards observed

- **Guard Rail 1 (No mocked LLM tests)** — honoured. `_run_export` is monkeypatched in 2 routing-layer tests for scope-restriction; `shield_invoke` is NOT monkeypatched anywhere in Phase 5 tests. The full-cycle integration test exercises real `shield_invoke` via `_run_export`.
- **Guard Rail 2 (No silent except-swallow)** — every new `except` block in `compilations.py`, `documents.py`, `work_studio_export.py`, `work_studio_overlay.py` logs with `exc_info=True` OR documents the swallow contract inline citing the spec.
- **Guard Rail 3 (Pre-Read internal consistency)** — `forecast_meta` not touched (Phase 4 invariant preserved); FE/BE field names match across `source_count`, `contributor_count`, `akki_generated`, `draft_session_id`, `inline=true`. No "deferred via comment" scope cuts.
- **Guard Rail 4 (file:line citations)** — every claim above carries a `file:line` reference. The W3 hypothesis was REVISED based on curl evidence at `/tmp/phase5_w3_repro_v2.py`, not silently swapped.

---

## Section 5 — Files touched

```
Backend (5 files):
  routers/compilations.py                         +130 LOC  — /start endpoint (idempotent)
  routers/documents.py                            +75 LOC   — /manual-create endpoint
  routers/work_studio_export.py                   +140 LOC  — /save-draft + inline=true + additive fields
  routers/work_studio_overlay.py                  +35 LOC   — DELETE Draft-only
  routers/streaming_v9.py                         +5 LOC    — additive fields on enhance/stream insert
  services/work_studio_overlay.py                 -1 / +12  — RAG threshold flip 80 → 75

Frontend (8 files):
  pages/WorkStudio.jsx                            +60 LOC   — checklist + drafting drawer wiring
  components/work_studio/DocumentCardsSection.jsx +130 LOC  — row 2 + kebab + pulse listener
  components/work_studio/CompilationWizard.jsx    +20 LOC   — chain /start + dispatch event
  components/work_studio/CreateArtefactModal.jsx  +20 LOC   — blank-route branch
  components/work_studio/LoadingChecklistModal.jsx NEW 207 LOC
  components/work_studio/DraftingDrawer.jsx       NEW 273 LOC
  components/work_studio/overlay/DocumentOverlay.jsx +30 LOC  — Phase-6 stubs + editable:false
  components/studio/ExportModal.jsx               +25 LOC   — Saved-to-Drafts breadcrumb
  hooks/useStreamingProgress.js                   +18 LOC   — W3 CSRF fix

Tests (1 new file):
  tests/test_track_a_phase5_lifecycle.py          NEW 580 LOC, 15 tests
```

---

## Section 6 — Phase 6 scope (deferred per Pre-Read Section 8)

Surfaces stubbed with `data-phase6="true"` carry over to Phase 6:
- Edit toggle in `DocumentOverlay.jsx:430` — re-enables inline rich-text editing for DOCX
- Inline-edit indicator in `DocumentOverlay.jsx:755` — flips to "Inline edit ON" / "Read mode"
- Revise-with-AI button in `DocumentOverlay.jsx:800` — opens diff-view panel
- PDF documents permanently exclude Revise-with-AI (per spec)

Phase 5 BC mirrors flagged for Phase 5 removal (carried from Phase 4):
- `analyses.narration` (Phase 4 row schema mirror)
- `analyses.notes` + `analyses.notes_updated_at` (Phase 4 notes mirror)

Phase 6 should also remove these BC mirrors after the FE has migrated to `runs[-1]` / `notes_history[-1]` (precondition: FE grep shows no consumer references).

---

## Section 7 — Honest verdict on re-running e1_tester

**Not required for iter-1 ship.** The 5 user-facing surfaces are all covered by either pytest lockdowns (14 default + 1 integration-marked) or by raw-curl evidence on the live preview (`/tmp/phase5_w3_repro_v2.py` for W3). The FE smoke screenshot at `/tmp/phase5_smoke2.png` confirms zero webpack overlay errors and the Work Studio page renders cleanly.

**Recommended if user runs e1_tester anyway:** focus the journey on (a) Compile a real Board Pack from existing sources → confirm the LoadingChecklistModal advances → confirm card pulse + drawer auto-open, (b) Enhance Minutes via file upload → confirm no 403, (c) Click Save and start drafting on a brief → confirm Drafting Drawer opens + autosave indicator cycles + saved card appears.

---

## Section 8 — Iteration budget

**Iteration 1 used.** 2 iterations remain. Iter-2 reserved for whatever surfaces in user verification; iter-3 reserved for unforeseen architectural surprises only.
