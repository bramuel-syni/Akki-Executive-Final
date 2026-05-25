# T4 Implementation Log

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (Ratified 24 May 2026).
Scope: T4 = "Work Studio compiled document" — 5 items:
1. W3 — Compiled Document toolbar + DOCX/PDF/PPTX download (G6 ratified)
2. W3 — Document Intelligence card + Refine flow (G7 ratified)
3. W5 — Committed state
4. W7 + W9 — Enhance entry point + enhanced-document drawer
5. W10 — Enhance Refine failure inside the drawer (G10 ratified)

**Hard rules:**
- All LLM calls go through `llm_router.invoke()` + `deidentifier.deidentify()`.
- No guardrail file changes (Shield, Trust Center, ClamAV, Postmark, audit invariants, llm_router).
- DOM-unconditional rule for every spec-required section.
- No T5 scope pulled forward.
- Verbatim spec copy on every toast, label, and button.

Scope-out → `/app/memory/sprints/POST_T5_BACKLOG.md`.

---

## Pre-tier hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-T4` → commit `b010ac2790d891bdb4366ee6582a0fb33f48c94c` | 2026-05-25T07:07:00Z |
| Mongo dump | `/app/backup/pre_T4_20260525T070755Z/akki_dev/` (237 bson + metadata files, 63 MB) | 2026-05-25T07:07:55Z |

Note: tag local-only. `git push origin v-pre-T4` requires the user's "Save to Github" feature.

---

## Disk re-verification + implementation (per item)

### T4.1 — W3 Compiled Document toolbar + DOCX / PDF / PPTX downloads (G6 ratified)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L508–L555 (§4.C → W3) + §6 → G6.

**Backend (new endpoint, server-produced):**
- `backend/routers/work_studio_render.py` (new, 250 lines) — `GET /api/contexts/{cid}/work-studio/documents/{aid}/render?format={docx|pdf|pptx}`:
  - Loads the artefact row from `work_studio_exports`; resolves `structured_content.sections`.
  - **DOCX** — rendered with `python-docx`. Title + Heading per section + paragraphs.
  - **PDF** — rendered with `reportlab` (SimpleDocTemplate + Paragraph styles). XML-safe escaping for body text.
  - **PPTX** — rendered with `python-pptx`. Title slide + one bulleted slide per section.
  - 422 for unknown format; 404 for missing artefact; **409 for missing `structured_content`** so the frontend can show a clean "not compiled yet" state.
  - Streams binary with `Content-Type` + `Content-Disposition: attachment; filename="<slug>.<fmt>"` + `X-AKKI-Sensitivity-Band` header (Shield invariant: every binary download carries the band).
  - Audit row written via `write_audit` → `audit_log.action = "work_studio.compiled_document.rendered"` with `{format, size_bytes}` metadata.
- `backend/server.py` — wired the new router (+2 lines).
- No new packages added — `python-docx`, `reportlab`, `python-pptx`, `weasyprint` all already installed.

**Frontend (toolbar 3-button refactor):**
- `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx`:
  - The pre-T4 single Download icon button (which routed to the legacy export-job pipeline at `/work-studio/exports/{aid}/download`) is REPLACED by three explicit format buttons. Each emits DOM unconditionally per T2.3 rule.
  - Buttons render in **DOCX → PDF → PPTX** order with testids `document-overlay-download-{docx,pdf,pptx}-btn` for tester anchoring.
  - The `onDownload` handler signature is now `(fmt) =>` and uses axios `responseType: "blob"` so the bearer token is attached and the download stream is consumed as a Blob. Filename is read from the `Content-Disposition` header.
  - 409 from the server surfaces a clean "This artefact has no compiled content yet." toast.

### T4.2 — W3 Refine failure (G7 ratified verbatim)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.C → W3 step 5 + §6 → G7.

**File changed:**
- `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` — AIRevisionPanel `submit()` catch block. Pre-T4 string was `apiErrorMessage(e, "Revision failed.")`. Now: literal `setError("We couldn't apply that refinement. Please try again.")`. The recommendation/state (instruction, scope, tone) is preserved so the user can retry without re-typing — only the in-flight diff is cleared at the start of submit, not in the catch.

### T4.3 — W5 Committed state
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.C → W5.

**Disk re-verification:** the W5 committed-state UI was already shipped via the pre-T4 `Chunk 8` (QA-2026-05-16-029…036) work:
- Lock icon overlay on document icon (`Lock` from lucide-react).
- `Create New Version` affordance present in source.
- Read-only mode replaces the Refine/Decline/Commit footer trio with `Create New Version` on a committed pack.
- Lifecycle states `draft / in_review / committed` already persisted in `work_studio_exports.lifecycle_state` and `status`.

No code changes needed for T4.3 beyond the regression test that asserts those elements remain in DOM (`test_t4_3_w5_committed_state_renders_create_new_version` + `..._renders_lock_indicator`).

### T4.4 — W7 + W9 Enhance flow
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.C → W7, W9.

**Disk re-verification:** `frontend/src/components/studio/EnhanceModal.jsx` (826 lines) already implements W9 — it covers instruction capture, the loading state, the success path with a download-format selector + new card pulse, the failure modal with `Adjust and try again` + `Close` CTAs, and the C2 refine path.

No code changes needed for T4.4 beyond the regression test that asserts the modal file exists.

### T4.5 — W10 Enhance Refine failure (G10 ratified verbatim)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 §4.C → W10 + §6 → G10.

**File changed:**
- `frontend/src/components/studio/EnhanceModal.jsx` — the C2 refine submit catch block (line ~278). Pre-T4 string was `setErrMsg(apiErrorMessage(err))`. Now: literal `setErrMsg("We couldn't refine this version. Please try again.")`. The existing enhanced content + intelligence is left in place per G10 (we don't clear `c2Result`).

---

## Tests written and run

- `backend/tests/test_t4_backend.py` (7 tests) — parameterised DOCX/PDF/PPTX render returning a non-empty binary with correct magic bytes + Content-Type + Content-Disposition + Sensitivity-Band headers; unknown-format 422; missing-artefact 404; **409 when `structured_content` is null** (post-T3.1 fresh Draft); audit row emitted.
- `backend/tests/test_t4_frontend_wire.py` (8 tests) — toolbar emits the 3 buttons in spec order, hits `/render` with each format via `responseType: "blob"`, all three buttons DOM-unconditional (T2.3 rule), G7 verbatim toast, W5 elements present, EnhanceModal file present, G10 verbatim toast.

**Pre-fix-evidence (anti-false-green guard):** ran the 15 new T4 tests against the `v-pre-T4` worktree. **11/15 failed** before the fix. The 4 that pass are trivially-correct existence checks (Enhance modal existed pre-T4, W5 lock indicator existed pre-T4, 404-for-missing-artefact returns 404 because the endpoint itself is missing pre-T4 — same status, different cause; render-output-headers test crashes pre-T4 because route is missing). Strong regression cover on G6 + G7 + G10.

Run results (25 May 2026):

```
$ pytest backend/tests/test_t4_backend.py backend/tests/test_t4_frontend_wire.py -v
======================== 15 passed, 7 warnings in 2.85s ========================

$ pytest backend/tests/test_t1_*.py backend/tests/test_t2_*.py backend/tests/test_t3_*.py \
         backend/tests/test_t4_*.py backend/tests/test_cycle_feel_pass.py \
         backend/tests/test_cycles_v2.py backend/tests/test_iter28_strategic_goals.py \
         backend/tests/test_patch_5_monitor_v2.py backend/tests/test_patch_6_pulse_synisense.py \
         backend/tests/test_cycle_manager_actions_tab.py -q
97 passed, 13 skipped, 7 warnings in 5.27s
```

**+15 from the T3 baseline of 82 → 97 pass.** 13 pre-existing skips.

---

## Spec invariants check

| Invariant | Status |
| --- | --- |
| **G6 DOCX endpoint** functional + server-produced | ✅ `_render_docx` via `python-docx`; covered by `test_t4_1_g6_render_returns_nonempty_binary_with_correct_headers[docx-...]` |
| **G6 PDF endpoint** functional + server-produced | ✅ `_render_pdf` via `reportlab`; covered by same parametrised test |
| **G6 PPTX endpoint** functional + server-produced | ✅ `_render_pptx` via `python-pptx`; covered by same parametrised test |
| **G7 W3 Refine toast** verbatim | ✅ Literal `"We couldn't apply that refinement. Please try again."` in `DocumentOverlay.jsx` AIRevisionPanel catch block |
| **G10 W10 Refine toast** verbatim | ✅ Literal `"We couldn't refine this version. Please try again."` in `EnhanceModal.jsx` C2 refine catch block |
| **All LLM calls routed through `llm_router` + `deidentifier`** | ✅ No new LLM call sites were added in T4. The render endpoint is a pure formatting pass over already-Shielded `structured_content`. AIRevisionPanel / EnhanceModal both delegate to the existing pre-T4 endpoints which are Shield-routed (Phase C.2 + H2.5). |
| **No guardrail files modified** | ✅ `git diff` excludes `services/synisense/**`, `services/clamav_service.py`, `inbound_email.py`, `trust_center.py`, `admin_audit_invariant.py`, `llm_router.py`. New file `work_studio_render.py` only reads `db.work_studio_exports` + emits an audit row via the public `write_audit` helper. |
| **No T5 scope pulled forward** | ✅ Cycle Manager landing surface, setup wizard, and Cycle Page (C1–C8) untouched. No new code under `pages/Cycle*` or `pages/cycle/`. |

