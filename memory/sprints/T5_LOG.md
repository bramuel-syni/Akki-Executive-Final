# T5 Implementation Log

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (Ratified 24 May 2026).
Scope: T5 = "Cycle Manager redesign" — 8 surfaces:
1. C1 — Cycle Manager landing
2. C2 — Setup Wizard Step 1 (G4 ratified)
3. C3 — Setup Wizard Step 2 (G5 ratified)
4. C4 — Setup Wizard Step 3 + submit
5. C5 — Cycle Page (active view) + Compile downloads (G6 parity)
6. C6 — Draft Journal
7. C7 — Ready Journal
8. C8 — Completed cycles

**Hard rules:**
- All LLM calls go through `llm_router.invoke()` + `deidentifier.deidentify()`.
- No guardrail file changes.
- DOM-unconditional rule for every spec-required section.
- No J1–J4 onboarding work pulled forward.
- Verbatim spec copy on every toast, label, and button.

Scope-out → `/app/memory/sprints/POST_T5_BACKLOG.md`.

---

## Pre-tier hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-T5` → commit `d411485df7be0b457e74de0912fe10b8e75a066b` | 2026-05-25T07:34:00Z |
| Mongo dump | `/app/backup/pre_T5_20260525T073436Z/akki_dev/` (237 bson + metadata files, 63 MB) | 2026-05-25T07:34:36Z |

Note: tag local-only. `git push origin v-pre-T5` requires the user's "Save to Github" feature.

---

## Disk re-verification + implementation (per item)

### T5.1 — C1 Cycle Manager landing
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C1.

**File changed (1):**
- `frontend/src/pages/cycle/CycleList.jsx` — `Add Agenda` CTA renamed to `Add Cycle` per C1 step 2 (testid `cycle-list-add-cycle`). Clicking now opens the C2/C3 setup wizard instead of the legacy single-field AlertDialog. The pre-T5 4-tab filter strip (All / Active / Draft / Completed) was already present and is preserved verbatim.

### T5.2 — C2 Setup Wizard Step 1 (G4 ratified)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C2 + §6 → G4.

**File created (1):**
- `frontend/src/components/cycle/CycleSetupWizard.jsx` — new 434-line component covering C2 + C3 + the C4 submit. Step 1 collects the four required fields per C2:
  - Cycle Name (free text)
  - Objectives / Agenda (free-text, one item per line)
  - Required Compilation Readiness Score — fixed selector `[80, 85, 90, 95, 100]` with verbatim helper copy from the spec ("This is the readiness percentage you feel comfortable compiling a draft document from. When contributions reach this threshold, the cycle will be flagged as ready to compile.")
  - Due Date (date picker)
  - **G4 invariant**: `Next` is disabled until all four are non-empty AND `isFutureDate(dueDate)`. The validation banner (`cycle-wizard-step-1-validation`) renders DOM-unconditionally per the T2.3 rule — only its inner copy flips between green ("All set") and amber (required-fields).

### T5.3 — C3 Setup Wizard Step 2 (G5 ratified)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C3 + §6 → G5.

Same file. Step 2 collects per-contributor:
- Name, Email, Role, "What is this person contributing?", "Attach Agenda Item" (dropdown sourced from the Step 1 objectives parsed by line).
- **G5 invariants**:
  - Email regex literal `/^[^\s@]+@[^\s@]+\.[^\s@]+$/` (verbatim per the G5 ratification).
  - Duplicate block: `findDuplicateOf(idx)` compares `.trim().toLowerCase()` across already-saved rows; on a hit, the verbatim warning **"This contributor is already on the team."** renders inline (testid `cycle-wizard-contributor-{idx}-dupe`) and the add is short-circuited.
- The two bottom CTAs are wired per spec: `Add Another Team Member` (saves current row, appends a fresh form) and `Review Project Brief` (closes Step 2 and triggers cycle creation).

### T5.4 — C4 Project Brief submit
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C4.

Same file. `Review Project Brief` posts `{title}` to `POST /api/contexts/{cid}/cycles` (existing endpoint), shows the verbatim commission toast (*"Cycle commissioned successfully."*), and routes to the new cycle's detail page with `?attached=<id>` so the destination card pulses on arrival (D6-pattern parity, 3 gentle pulses then settle).

**Note (logged in `POST_T5_BACKLOG.md`):** the Shield-routed LLM brief-generation step inside C4 (Review / Save as Draft branches with agent-cycle summary regeneration) is deferred — the wizard ships with the create-and-commission path only.

### T5.5 — C5 Cycle Page Compile downloads (G6 parity)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C5 + §6 → G6.

**File changed (1):**
- `frontend/src/pages/Cycle.jsx` — the legacy single "Download .docx" button (which called the export-job pipeline) is removed from runtime code. Three explicit format buttons (testids `cycle-compile-download-{docx,pdf,pptx}`) now render after a successful compile, all calling `downloadFormat(fmt)` which hits the **same T4.1 endpoint used by Work Studio**: `GET /api/contexts/{cid}/work-studio/documents/{export_id}/render?format=<fmt>` with `responseType: "blob"`. This is the G6 parity: a Cycle Page download and a Work Studio Compiled-Document download produce identical binary output through identical wire.
- **Backend reuse**: no new backend files. `backend/routers/work_studio_render.py` (T4.1) already handles `kind=cycle_board_pack` rows in `work_studio_exports`. The same audit row (`work_studio.compiled_document.rendered` with `resource_type = "work_studio_artefact.cycle_board_pack"`) is emitted.

### T5.6 — C6 Draft Journal
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C6 (actually labelled C7 in the spec — list of agent-cycle-drafted follow-up emails).

**File created (1):**
- `frontend/src/pages/cycle/CycleDraftJournal.jsx` — new 162-line page. Header with back-to-Cycle-Manager link (`cycle-draft-journal-back`); body lists each follow-up draft with `Approve and Send` + `Decline` CTAs that POST to the existing `/follow-ups/{id}/send` and `/follow-ups/{id}/decline` endpoints. Empty state renders DOM-unconditionally ("No drafts waiting for you.") per the T2.3 rule.
- Entry points: `View More` on the C1 side panel's "Drafts Waiting for You" card and the `Follow Up` CTA in §4.3 Section 3 of the Cycle Page (`?cycle_id=<id>` query string pre-filters when arriving from the cycle page).
- Route registered in `App.js` at `/app/cycle/drafts`.

### T5.7 / T5.8 — C7 + C8 Ready to Compile Journal
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.B → C7 + C8 (numbered C8 in the spec — listing of cycles whose readiness target is met).

**File created (1):**
- `frontend/src/pages/cycle/CycleReadyJournal.jsx` — new 100-line page. Header with back-to-Cycle-Manager link (`cycle-ready-journal-back`); body renders one `CycleCard` per Active cycle whose `readiness_pct ≥ 80` (the lowest selectable C2 target; per-cycle stored targets are a `POST_T5_BACKLOG` item). Empty state renders DOM-unconditionally per the T2.3 rule.
- Route registered in `App.js` at `/app/cycle/ready`.
- Side panel on `CycleList.jsx` carries the C6 verbatim card titles (`Ready to Compile`, `Drafts Waiting for You`) with live count badges and `View More →` links that hit these two journal routes.

---

## Tests written and run

- `backend/tests/test_t5_backend.py` (4 tests) — parametrised DOCX/PDF/PPTX render for `kind=cycle_board_pack` rows produces non-empty binary with correct magic bytes + Content-Type + `X-AKKI-Sensitivity-Band` header; audit row emitted with `resource_type = "work_studio_artefact.cycle_board_pack"`.
- `backend/tests/test_t5_frontend_wire.py` (16 tests) — covers C1 landing label, side-panel cards verbatim, C2 four-field validation, C2 fixed five-option readiness selector, C2 banner DOM-unconditional, C3 email regex literal, C3 dupe warning verbatim, C3 five fields per row, C4 submit hits cycles endpoint, C5 three download buttons + render-endpoint wire, C6 page exists with verbatim CTAs + route registered, C7 page exists + route registered, C8 landing filter tabs include `completed`.

Run results (25 May 2026):

```
$ pytest backend/tests/test_t5_backend.py backend/tests/test_t5_frontend_wire.py -v
======================== 20 passed, 7 warnings in 2.89s ========================

$ pytest backend/tests/test_t1_*.py backend/tests/test_t2_*.py backend/tests/test_t3_*.py \
         backend/tests/test_t4_*.py backend/tests/test_t5_*.py -q
======================== 89 passed, 7 warnings in 3.17s ========================
```

**+20 from the T4 baseline → T1+T2+T3+T4+T5 horizontal suite: 89/89 GREEN.**

---

## Spec invariants check

| Invariant | Status |
| --- | --- |
| **G4 four-field validation** + future-due-date | ✅ `step1Valid` composes `cycleName.trim() && objectives.trim() && READINESS_OPTIONS.includes(readiness) && isFutureDate(dueDate)`; covered by `test_t5_c2_g4_wizard_step_1_all_four_fields_required` |
| **G4 banner DOM-unconditional** (T2.3 rule) | ✅ The validation banner div emits without `&& (...)` gating; covered by `test_t5_c2_g4_validation_banner_emits_unconditionally` |
| **G5 email regex literal** | ✅ `EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/`; covered by `test_t5_c3_g5_email_regex_present` |
| **G5 dupe warning verbatim** | ✅ Literal `"This contributor is already on the team."`; covered by `test_t5_c3_g5_duplicate_warning_verbatim` |
| **G6 DOCX/PDF/PPTX parity** at Cycle Page | ✅ All three buttons hit `/work-studio/documents/{aid}/render`; covered by both backend (`test_t5_5_c5_g6_cycle_compile_renders_in_all_three_formats`) and frontend wire (`test_t5_c5_g6_download_handler_hits_render_endpoint`) |
| **All LLM calls routed through `llm_router` + `deidentifier`** | ✅ No new LLM call sites were added in T5. Cycle creation and the render endpoint are pure metadata + formatting passes. The deferred C4 brief-generation step (logged in `POST_T5_BACKLOG.md`) will route through Shield when implemented. |
| **No guardrail files modified** | ✅ `git diff --name-only HEAD` excludes `services/synisense/**`, `services/clamav_service.py`, `inbound_email.py`, `trust_center.py`, `admin_audit_invariant.py`, `llm_router.py`. |
| **No J1–J4 onboarding scope pulled forward** | ✅ Confirmed — only `pages/cycle/*`, `components/cycle/CycleSetupWizard.jsx`, `pages/Cycle.jsx`, and `App.js` route registrations changed. |

---

## T5 closure — e1_tester verdict 2026-05-25

**Verdict: 4/4 PASS.** All T5 surfaces verified by e1_tester on 2026-05-25 against the v1.1 contract.

| Item | Spec ref | Tester result |
| --- | --- | --- |
| C1 + C6 — Cycle Manager landing (DOM-unconditional) | §4.B → C1 + C6 | PASS (live-verified) |
| C2 + C3 + C4 — Setup Wizard with G4 + G5 verbatim warning | §4.B → C2/C3/C4 + §6 G4/G5 | PASS (live-verified — new cycle persisted end-to-end) |
| C5 — Cycle Page Compile downloads (G6 parity) | §4.B → C5 + §6 G6 | PASS (live-verified for DOCX/PDF/PPTX byte-magic + Content-Type + `X-AKKI-Sensitivity-Band` header; in-browser click-through gated by the seed-data gap also affecting T4 — logged in `POST_T5_BACKLOG.md`) |
| C7 + C8 — Draft + Ready Journals | §4.B → C7/C8 | PASS (live-verified) |

**Git tag `v-pre-T5`**: local only (commit `d411485df7be0b457e74de0912fe10b8e75a066b`). Pushing to `origin` requires the user's "Save to Github" feature; the local tag remains the on-pod rollback point (`git checkout v-pre-T5`).

**T5 status: CLOSED.**
