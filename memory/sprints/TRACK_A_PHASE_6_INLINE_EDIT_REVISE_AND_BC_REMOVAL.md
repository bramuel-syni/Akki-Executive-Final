# Track A Phase 6 — Document Review Drawer inline editing + Revise-with-AI restoration + BC mirror removal

**Shipped:** 2026-06-04 (iter-1 of 1 + iter-0 stop-and-surface).
**Approver:** User direct dispatch + 5 tightenings + scope rebalance after iter-0 confidence-recompute deferral.

---

## TL;DR

Phase 6 restored the four `data-phase6="true"` stubs in `DocumentOverlay.jsx` that the Phase 5 dispatch deliberately disabled, dropped the Phase-4 BC mirror writes for `analyses.{narration,notes,notes_updated_at}`, sanitized the GET response shape so legacy rows don't surface deprecated keys, and added a save-on-close belt to catch tail edits the 30s autosave hasn't reached. Total **~80 LOC delta** across 4 files + 4 test migrations + 1 new Phase 6 lockdown file (10 default + 2 integration-marked = 12 tests) + 3 Playwright lockdowns in `/tmp/` (15 assertions). **73 BE + 15 FE = 88 lockdown assertions green.**

Confidence recompute on commit was DEFERRED per user A=(b) decision after iter-0 step 0 surfaced that no production runtime scoring path exists — only seeded demo payloads in `seed_chunks.py`. Logged in MASTER_STATE Section 5 as a future dedicated phase, not gold-plating.

---

## Iter-0 step 0 — Stop-and-surface findings

### Finding A — Confidence recompute prompt path greenfield

Ground-truthed `intelligence_report.confidence_pct` provenance:
- **Only writer:** `scripts/seed_chunks.py:64-160` (`_intel_for_kind`) — static seed payloads for demo data (committee_pack=86, report=72, deck=48).
- **Production path:** `routers/work_studio_export.py:1041` — real Work Studio docs start with `confidence_pct: None`. No runtime compute exists.

**User decision: A=(b) defer.** Logged in MASTER_STATE Section 5 backlog under "potential cross-cutting hygiene" with explicit "future dedicated phase with rubric Pre-Read" tag. Phase 6 scope rebalanced: drop 5 commit-recompute tests, add +2 commit-path regression + +3 narration-regression. Total stays 15/15 at budget cap.

### Finding B — BC mirror tests would fail without migration

Greped `/app/backend/tests/`. Four existing tests pinned the BC mirror fields:
- `test_track_a_phase4_iter2_corrective.py:213` (DB-write)
- `test_track_a_phase4_versioning_multi.py:267-268` (DB-write)
- `test_track_a_phase4_versioning_multi.py:328` (DB-write)
- `test_track_a_phase3_narration.py:362` (**API-response** — `len(body["notes"])`)

**User decision: B=(i) migrate all four to canonical shapes.** Implemented.

---

## Step-by-step execution

### Step 1 — FE flip (4 disable points + PDF carve-out)

Touched `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx`:

| Surface | Pre-fix | Post-fix |
|---|---|---|
| L430-449 Edit toggle | `disabled` + `data-phase6="true"` + opacity-60 + tooltip "Inline edit ships in Phase 6" | Live button, wrapped in `{doc.output_format !== "pdf" && (…)}` PDF carve-out (mirrors L869 Revise guard) |
| L693 Editor `editable` | `editable: false` (literal) | `editable: false` initially, then `setEditable(editMode && !isLegacyReadOnly)` via useEffect at L713 |
| L711-714 useEffect | `editor.setEditable(false)` regardless of inputs | `editor.setEditable(editMode && !isLegacyReadOnly)` — canonical Phase 5 inline-comment restoration |
| L782-787 Mode indicator | Subdued italic stub "Inline edit on — Phase 6" + `data-phase6="true"` | Live status: emerald "Inline edit on — autosaving every 30s" / muted "Read mode" |
| L867-882 Revise-with-AI button | `onClick={() => {}}` no-op + `disabled` + `data-phase6="true"` + opacity-40 | `onClick={onOpenRevise}` (wires to parent `setRevising(true)` at L257 — already plumbed), `disabled={!editMode}` for the "switch to Edit first" tooltip path |

**Net delta: ~30 LOC across the surface flips. Zero new dependencies. Zero new test-ids invented.**

### Step 2 — Save-on-close belt (Tightening 2 hardening)

`DocumentOverlay.jsx` — added `saveBeltRef = useRef(null)` at L91; `handleCloseWithSave` callback at L128-141 awaits the ref'd save with `silent: true`, catches via `console.error(... e)` + `toast.error("Couldn't save before close — content may be lost.")`, ALWAYS calls `onClose()` afterward. Wired into the backdrop click handler at L161 and the Toolbar's onClose prop at L184.

`DocumentSurface` extended:
- `handleSaveNow({ silent = false } = {})` parameter — silent saves use label "Auto-save (on close)", emit no success toast, and **re-raise** on failure so the parent belt's promise rejects cleanly. User-initiated Save (button click) emits "Saved." toast on success, `toast.error` on failure (existing behavior preserved).
- `useEffect` at L770-779 installs `handleSaveNow` into `saveBeltRef.current` only when `editor && editMode && !isLegacyReadOnly` are all true; nulls the ref otherwise (cleanup safe).

**Tightening 2 contract honored verbatim:**
- ✅ `await` the save in the close handler.
- ✅ If save throws, `console.error(...)` (Guard Rail 2: no silent except-swallow) + `toast.error("Couldn't save before close — content may be lost.")` + proceed with close.
- ✅ 30s autosave is the primary belt; on-close is safety net.
- ✅ No confirm dialog, no blocking, no gold-plate.

### Step 3 — BC mirror removal end-to-end

**Frontend (3 read-site migrations) — `frontend/src/components/analyze/AnalyzeDrawer.jsx`:**

| File:line | Before | After |
|---|---|---|
| L329 | `(analysis.notes_history \|\| analysis.notes \|\| []).length === 0` | `(analysis.notes_history \|\| []).length === 0` |
| L333 | `(analysis.notes_history \|\| analysis.notes \|\| []).map(…)` | `(analysis.notes_history \|\| []).map(…)` |
| L401-409 | `analysis?.narration?.partial_narration_missing_forecast_low_signal` | IIFE wrapping `analysis?.runs?.[analysis.runs.length-1]?.partial_narration_missing_forecast_low_signal` with a clarifying provenance comment |

**Backend (3 write removals + 2 API response sanitizations + 1 listing fallback drop) — `backend/routers/workbook_analysis.py`:**

| File:line | Change |
|---|---|
| L99-114 (NEW) | `_strip_phase6_bc_mirrors()` helper + `_PHASE6_BC_MIRRORS` constant. Strips legacy top-level keys from API responses for the 3 BC mirror fields. |
| L755 GET v2 | Wrap return in `_strip_phase6_bc_mirrors(row)` — legacy rows DON'T surface BC keys on the API. |
| L780-815 sources-purged refusal path | Pre-fix wrote top-level `narration` + returned `update["narration"]`. Post-fix pushes a refusal run to `runs[]` (no top-level mirror), returns the local refusal dict. API response shape unchanged for callers. |
| L1064-1088 synthesize | `cached=row.get("narration")` → reads `runs[-1]` shape directly (with the canonical fields synthesized into a local dict). Forces the cache path to use the new canonical source. |
| L1095 update_set | Dropped `"narration": narration` from `$set`. |
| L1182 listing | `r.get("notes_history") or r.get("notes") or []` → `r.get("notes_history") or []`. |
| L1226-1228 PATCH objective | Wrap return in `_strip_phase6_bc_mirrors(fresh)`. |
| L1281-1294 notes POST | Dropped `"notes": body.body, "notes_updated_at": note["created_at"]` from `$set`. Kept `"updated_at": note["created_at"]`. |

**Pydantic model — `backend/models/analysis.py`:**

Dropped `narration: Optional[Dict[str, Any]]` field (L113 pre-fix) and `notes: List[AnalysisNote]` field (L117 pre-fix). Without this drop, `Analysis.model_dump()` on initial `insert_one` was seeding `narration: None` and `notes: []` at top level — defeating the BC mirror removal. The Phase 6 inline comment marks the deprecation provenance.

**Test migrations (Tightening 3) — 4 migrations completed:**

| File:line | Old (BC mirror) | New (canonical) |
|---|---|---|
| `test_track_a_phase4_iter2_corrective.py:213` | `row.get("notes") == ""` | `row.get("notes_history")[-1]["body"] == ""` + `"notes" not in row` |
| `test_track_a_phase4_versioning_multi.py:268-269` | `row.get("notes") == "..."` + `row.get("notes_updated_at") == note["created_at"]` | `history[-1]["body"]` + `history[-1]["created_at"]` + `"notes" not in row` + `"notes_updated_at" not in row` |
| `test_track_a_phase4_versioning_multi.py:328` | `row.get("notes") == "Third note."  # BC mirror = latest` | `history[-1]["body"] == "Third note."` + `"notes" not in row` |
| `test_track_a_phase3_narration.py:362` | `len(body["notes"]) >= 1` (API response shape) | `len(body["notes_history"]) >= 1` + `"notes" not in body` + `"notes_updated_at" not in body` + `"narration" not in body` |

Plus the file-level docstring at `test_track_a_phase4_versioning_multi.py:24-27` reworded to drop the "Top-level `notes` mirror" framing.

### Step 4 — Phase 6 lockdowns (15 tests at budget cap)

**New lockdown file: `backend/tests/test_track_a_phase6_inline_edit_and_bc_removal.py`** (12 tests; 10 default + 2 integration-marked):

- 4 BC mirror removal end-to-end
- 2 commit-path regression (Work Studio `/commit` still locks + still creates pre-commit snapshot — confirms BC removal doesn't ripple via shared helpers)
- 3 narration-regression (fresh synthesize/notes rows + GET response shape contract)
- 1 deterministic pre-revision snapshot test (Tightening 4 reallocation — Shield monkeypatched to raise; snapshot still exists)
- 2 integration-marked real-LLM Revise tests (Tightening 4: happy round-trip + refusal-no-Shield-call)

**3 Playwright lockdowns in `/tmp/`:**

| File | Assertions | Result |
|---|---|---|
| `phase6_inline_edit_journey.py` | 6 (edit toggle visible/enabled/no-stub, editor editable, save toast, marker persists after reload) | 6/6 PASS |
| `phase6_save_on_close.py` | 3 (marker typed, marker persists after close belt, "Auto-save (on close)" version snapshot exists) | 3/3 PASS |
| `phase6_revise_with_ai_journey.py` | 6 (Revise btn visible/enabled/no-stub, panel opens, diff section card renders, revised text applied to editor) | 6/6 PASS |

**Migrated/inverted: `test_phase5_phase6_stub_flags_persist`** — was a positive assertion of 3+ `data-phase6="true"` markers (pre-Phase-6 evidence). Phase 6 inverts to `n == 0` (markers must NOT remain) + retains the "Phase 6" anchor-comment assertion. Documents the flip in the test docstring.

---

## Aggregate sweep status

**73 BE pytest PASS** across:
- `test_qa_chunk_8.py` (30 tests, except 1 pre-existing rag_band regression — unrelated to Phase 6; reproduced on clean checkout)
- `test_track_a_phase3_narration.py` (9)
- `test_track_a_phase4_versioning_multi.py` (8)
- `test_track_a_phase4_iter2_corrective.py` (4)
- `test_track_a_phase5_lifecycle.py` (12 incl. the inverted Phase 6 stub-flags test) + sibling `test_track_a_phase5_*.py` files
- `test_track_a_phase6_inline_edit_and_bc_removal.py` (10 default)
- `test_solva_v1_unchanged.py` (v1 byte-identical guard — still 2/2)

**4 deselected:**
- 2 real-LLM integration tests in the new Phase 6 file (opt-in via `pytest -m integration`)
- 1 chunk8 integration-marked
- 1 pre-existing `test_chunk8_rag_band_thresholds` regression — `rag_band(79) == "amber"` but actual `"green"`. Surfaced via `git stash`-confirmed pre-existing failure; NOT introduced by Phase 6.

**15 FE Playwright assertions PASS** — see table above.

**88/88 lockdown assertions green for the Phase 6 work.**

---

## Hard-no compliance audit

- ✅ No new env vars.
- ✅ No third-party libraries (StarterKit covers everything; no diff library imported).
- ✅ No `shield_invoke` signature change.
- ✅ No Track B retouch.
- ✅ No schema migrations beyond additive — actually a SUBTRACTION: Pydantic model dropped 2 fields, Mongo `$set` dropped 3 keys. No additive fields landed.
- ✅ No collaborative editing.
- ✅ No PPTX structural editing.
- ✅ No rich-media insertion.
- ✅ No mocked LLM tests for backend Revise tests (real `shield_invoke` with `@pytest.mark.integration`).
- ✅ Save-on-close failure path: `console.error` + `toast.error` + `await` + proceed-with-close (Guard Rail 2 — no swallow, NO confirm dialog, NO blocking).
- ✅ BC mirror removal honest end-to-end: DB writes drop, API response shape drops, legacy rows stripped on read, tests migrate to canonical shapes. No derived BC field as fallback.
- ✅ OpenAPI cross-check via router-decorator grep (Guard Rail 3) — every endpoint cited verified in source. Zero invented paths.
- ✅ ESLint clean on `DocumentOverlay.jsx` + `AnalyzeDrawer.jsx`.
- ✅ Ruff clean on `workbook_analysis.py` + `models/analysis.py` + Phase 6 lockdown file.

---

## Decisions explicitly DECLINED as gold-plating

- **Confidence recompute on commit** — DEFERRED per user A=(b) decision after iter-0 surfaced no production scorer exists. Logged as a future dedicated phase in MASTER_STATE Section 5.
- **Removing the unused `AnalysisNote` Pydantic class** — left intact to avoid breaking unknown external importers (still in `__all__`).
- **Reusing the `_strip_phase6_bc_mirrors` helper for the listing endpoint** — listing endpoint already builds a hand-shaped summarized dict at L1180-1199, so the strip helper is unnecessary there. The shape never surfaces the BC mirrors.
- **`useFileInputResetOnInvoke` cross-cutting hook** (BUG-ANL-002 follow-up) — DECLINED previously; no new file-input surfaces introduced in Phase 6.

---

## Status

**Track A Phase 6 → ✅ COMPLETE 2026-06-04.**
- Total: 1 FE component + 1 FE page + 1 BE router + 1 BE Pydantic model + 1 new BE lockdown file + 4 BE test migrations + 3 FE Playwright lockdowns.
- Iter-0 step 0 stop-and-surface: 1 of 1 (confidence recompute deferred + BC test inventory).
- Iter budget: 1 of 3 used.
- 88/88 lockdown assertions PASS.
