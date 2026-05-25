# T3 Implementation Log

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (Ratified 24 May 2026).
Scope: T3 = "Cross-surface flows" — 4 items:
1. Add to Work Studio modal (cross-surface entry) — spec §4.A + §4.C, G8 ratified.
2. Add to Cycle modal cross-surface parity (verify G1 is the canonical pattern; patch outliers if any).
3. Work Studio card lifecycle routing (W3/W4 + G8 ratified) — Board/Committee Packs → page; Minutes/Decks/Reports → drawer.
4. Compile modal updates (W8 G9 ratified) — nested file-upload failure handling. NOT G6 PPTX.

**Explicit scope confirmation (per user directive):**
- G6 PPTX (Compile *download* formats DOCX/PDF/PPTX) is **deferred to T4**, NOT touched in T3.
- T3 only modifies the Compile *modal* itself (the nested upload failure branch). The post-compile download buttons / output formats are untouched.
- No guardrail file changes (Shield, Trust Center, ClamAV, Postmark, llm_router, audit invariants).

Scope-out → `/app/memory/sprints/POST_T5_BACKLOG.md`.

---

## Pre-tier hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-T3` → commit `ff32d5cbc495c93e1ea12a200b7cef2e1e160d10` | 2026-05-25T06:24:00Z |
| Mongo dump | `/app/backup/pre_T3_20260525T062409Z/akki_dev/` (237 bson + metadata files, 63 MB) | 2026-05-25T06:24:09Z |

Note: tag local-only. `git push origin v-pre-T3` requires the user's "Save to Github" feature.

---

## Disk re-verification + implementation (per item)

### T3.1 — Add to Work Studio modal (D5 + G8)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L161–L184 (§4.A → D5) + §6 → G8.

**Backend (new endpoint):**
- `backend/routers/work_studio_from_source.py` — appended `POST /api/contexts/{cid}/work-studio/from-document` (+131 lines). Accepts `{kind ∈ {board_pack, committee_pack, minutes, deck, report}, source_doc_id}`. Inserts a Draft row into `work_studio_exports` with `origin: {source: "document_journal_add", document_id}` and emits an audit entry. Returns the G8-ratified `redirect_url`: board_pack/committee_pack → `/app/work-studio/document/{aid}`; minutes/deck/report → `/app/work-studio?kind=<kind>&pulse=<aid>`.
- Validation: `kind` outside the 5-set → 422 (Pydantic Literal). Missing `source_doc_id` → 404.

**Frontend (new modal + refactored CTA):**
- `frontend/src/components/shared/AddToWorkStudioModal.jsx` (new, 154 lines) — implements D5 verbatim:
  - Title: *"Add to Work Studio"*
  - Supporting text: *"Choose the artefact type for this document."*
  - 5 type cards in spec order: Board Pack · Minutes · Committee Pack · Deck · Report.
  - CTA: *"Add document ({Type})"* — disabled until selection.
  - Success toast: `Your document has been added to Work Studio as a ${labelFor(selectedKind)}.`
  - Failure toast: `We couldn't add this document to Work Studio. Please try again.`
- `frontend/src/components/documents/DocumentRoutingActions.jsx` — full rewrite. The pre-T3 `onAddToWorkStudio` simply did `navigate("/app/work-studio?from_doc=...")`; T3 now mounts AddToWorkStudioModal. The Cycle path uses the shared modal (see T3.2).

**DOM-unconditional rule:** all 5 type cards + the CTA + Cancel render unconditionally inside the modal body; only `selectedKind` gates the CTA's enabled state.

---

### T3.2 — Add to Cycle cross-surface parity (G1)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.A → D6 + §6 → G1.

**Extracted shared modal:**
- `frontend/src/components/shared/AddToCycleModal.jsx` (new, 187 lines) — extracted from `DocumentRoutingActions.jsx`. Carries the G1 verbatim wire format (`{cycle_id, kind: "document", source_doc_id, title}` + `cycle_id` query param), the Active+Draft parallel fetch, the verbatim D6 toasts, and the 400/422/423 status-aware failure paths.

**Cross-surface consumers:**
- `DocumentRoutingActions.jsx` — mounts the shared modal (was inline before).
- `frontend/src/components/shell/HandoffActions.jsx` — patched. Pre-T3, the document case posted silently to `/api/contexts/{cid}/questions` (a question-bank seeding journey, NOT G1). Now, when `kind === "document"` and an `id` is present, the button opens the shared AddToCycleModal — same wire format as DocumentRoutingActions. For other kinds (briefing/deck/signal) the legacy `/questions` flow is preserved verbatim because those kinds are a different journey (cycle dispatch seeding) where G1 does not apply.

**Inventory of other "Add to Cycle"-shaped surfaces** (grepped):
- `pages/Cycle.jsx` — the per-agenda-item *inline* contribution panel (C5 §4.3 Action 3 in the spec). DIFFERENT journey ("Add Contribution" with contributor dropdown), NOT a G1 use case. Left intact per user directive.
- Website marketing pages (`website/pages/product/CycleManager.jsx`) — non-interactive copy. Out of scope.

---

### T3.3 — Work Studio card lifecycle routing (W3/W4 + G8)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L508–L615 + §6 → G8.

**Files changed:**
- `frontend/src/pages/WorkStudioDocumentPage.jsx` (new, 72 lines) — dedicated full-page surface that wraps `DocumentOverlay` with an AppShell + back-to-Work-Studio header. G8-canonical for Board Packs + Committee Packs.
- `frontend/src/App.js` — registered `<Route path="/app/work-studio/document/:artefactId" element={<Gated><WorkStudioDocumentPage /></Gated>}/>`. The pre-T3 route at the same path pointed to `<WorkStudio />` which auto-opened the overlay; per G8 that URL now lands on the dedicated page.
- `frontend/src/pages/WorkStudio.jsx` — the `onOpenDocument` callback now receives `(aid, exportKind)`. For `cycle_board_pack | board_pack | cycle_committee_pack | committee_pack`, navigates to `/app/work-studio/document/{aid}`. For Minutes / Deck / Report, opens the existing overlay drawer in place (W4 surface).
- `frontend/src/components/work_studio/DocumentCardsSection.jsx` — the card click callback now forwards `it.export_kind` alongside the artefact id so WorkStudio.jsx can dispatch by kind.

---

### T3.4 — Compile modal inline upload (W8 + G9)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L572–L600 (§4.C → W8) + §6 → G9. G6 (PPTX download format) **NOT touched** — deferred to T4.

**File changed:**
- `frontend/src/components/work_studio/CompilationWizard.jsx` — Step 2 ("Select source items"):
  - **Inline prompt** below the source list, ALWAYS rendered (T2.3 DOM-unconditional rule):
    - Verbatim copy: *"Can't find your document? Upload it here."*
    - Upload button.
  - **Nested upload modal** mounted OUTSIDE the parent `DialogContent` so closing it does not dismiss the Compile wizard. Hidden `<input type="file">` accepts PDF/DOCX/PPTX/XLSX/TXT/MD/CSV.
  - **Happy path**: POST to `/api/contexts/{cid}/documents` → on success, close ONLY the nested modal + `toast.success("Document added to your library.")` + refetch source list so the new doc surfaces under any matching aggregate.
  - **G9 ratified failure paths** (verbatim toasts):
    - ClamAV reject detection (`/clamav|virus|infected|malware/i` on the error detail): *"We couldn't upload that file. It was rejected by virus scanning."*
    - Other failures: *"Upload failed. Please try again."*
  - In ALL failure cases, only the nested modal closes; the parent Compile modal + existing `selectedSourceIds` selection are preserved per user directive.

---

## Tests written and run

- `backend/tests/test_t3_backend.py` (7 tests) — parameterised happy-path for each of the 5 D5 kinds (board_pack/committee_pack hit the page-route URL; minutes/deck/report hit the listing+pulse URL); unknown-kind 422; missing-doc 404; persisted-row schema (status=draft, source_document_ids, origin.source).
- `backend/tests/test_t3_frontend_wire.py` (13 tests) — covers AddToWorkStudioModal type-card order + verbatim copy + CTA gating, DocumentRoutingActions modal mounts (with comment-aware regex to avoid false negatives), AddToCycleModal extraction, HandoffActions document-branch wiring, WorkStudio kind routing, dedicated page route registration + component existence, Compile modal inline prompt + nested modal + G9 verbatim toasts + nested-only-close invariant.
- `backend/tests/test_t1_frontend_wire.py` — 3 tests updated to follow the AddToCycleModal extraction (now read from the shared file).

**Pre-fix-evidence:** Ran the new T3 tests against the `v-pre-T3` worktree. **19/20 failed** before the fix (the 1 pass is a 404 trivially returned for an unregistered route — different cause but same status). This proves the tests detect the regression and won't false-green a missing implementation.

Run results (25 May 2026):

```
$ pytest backend/tests/test_t3_backend.py backend/tests/test_t3_frontend_wire.py -v
======================== 20 passed, 7 warnings in 2.85s ========================

$ pytest backend/tests/test_t1_*.py backend/tests/test_t2_*.py backend/tests/test_t3_*.py \
         backend/tests/test_cycle_feel_pass.py backend/tests/test_cycles_v2.py \
         backend/tests/test_iter28_strategic_goals.py \
         backend/tests/test_patch_5_monitor_v2.py \
         backend/tests/test_patch_6_pulse_synisense.py \
         backend/tests/test_cycle_manager_actions_tab.py -q
82 passed, 13 skipped, 7 warnings in 5.16s
```

T1 (11 tests) + T2 (23 tests) + T3 (20 tests) + baseline (28 tests) = 82 pass. 13 pre-existing skips. **+20 from the T2 baseline of 62.**

---

## Spec invariants check

| Invariant | Status | Where |
| --- | --- | --- |
| **G1 wire format** used in cross-surface Add-to-Cycle parity | ✅ Single source in `AddToCycleModal.jsx`; HandoffActions and DocumentRoutingActions both mount the same modal |
| **G8 routing** (Board/Committee Packs → page; Minutes/Decks/Reports → drawer) | ✅ Backend `redirect_url` emits per-kind; frontend `WorkStudio.jsx::onOpenDocument` dispatches by `export_kind` |
| **G9 ClamAV toast** verbatim | ✅ Literal in `CompilationWizard.jsx::onUploadFile`: *"We couldn't upload that file. It was rejected by virus scanning."* |
| **G9 generic toast** verbatim | ✅ Literal: *"Upload failed. Please try again."* |
| **G6 PPTX** NOT touched | ✅ No changes to `work_studio_export.py` post-compile-render flow or any `_run_export` block; CompilationWizard Step 2's existing download/output_format selector unchanged |
| **No guardrail files modified** | ✅ `git diff --name-only HEAD` excludes `services/synisense/**`, `services/clamav_service.py`, `inbound_email.py`, `trust_center.py`, `admin_audit_invariant.py`, `llm_router.py`. The new `from-document` endpoint resides alongside the existing `work_studio_from_source.py` module and only reads `db.documents` + writes `db.work_studio_exports`. |
| **No T4/T5 scope pulled forward** | ✅ Compile *download formats* (G6 PPTX) untouched. Refine flow (W3/W5) untouched. Enhance flow (W9/W10) untouched. Cycle setup wizard (C2/C3/C4) untouched. |

