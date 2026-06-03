# Track A Phase 1 — R3 BLOCKER Surgical Fix Close Memo

**Date:** 2026-06-03T20:58:11Z
**Rails honoured:** R1, R3 (the rail that caught this), R4 (≤10 tests), R5 (ground-truth read both options first), R6 (no side quests), R7 (honest reckoning section).

---

## 1 — Files touched

```
M backend/routers/workbook_analysis.py                  (+100 / -1 — new adapter + export-loader; 3 export endpoints re-routed)
R backend/tests/test_track_a_phase1_analysis_foundation.py
    (REWRITTEN — v2; legacy seed shortcut REMOVED; total 9 tests)
M memory/MASTER_STATE.md                                 (Section 7 timestamp; Track A Phase 1 stays 🟡 PARTIAL per dispatch)
A memory/sprints/TRACK_A_PHASE1_R3_BLOCKER_FIX.md        (this memo)
```

Admin first-session state reset (hygiene, not scope):
```
db.accounts({email: 'admin@akki.ai'}).first_session
  PRE:  {status:'in_progress', current_step:'door', intake:{role,primary_context_name,top_of_mind}}
  POST: {status:'skipped', current_step:'done', completed_at:<iso>, grandfathered:true}
```

---

## 2 — Option chosen + why

**Chose Option (a) — prefix-dispatch via a surgical sibling loader.**

One-sentence why: option (a) preserves the existing URL contract (`/api/workbook/analyses/{aid}/report.{ext}`) so the frontend (Phase 2) has ONE consumer, and the sibling-loader seam (vs. mutating the shared `_load_analysis`) keeps blast-radius surgical — only the three export endpoints branch, the synthesize/read endpoints stay legacy-collection-only with zero behaviour change.

### Implementation detail (deliberate refinement of (a) — surfaced per R5/R7)

The dispatch said "Make `_load_analysis()` dispatch by id prefix". Ground-truth read of `workbook_analysis.py:108-127` showed `_load_analysis` is called from TEN call sites — read (line 220), signals extract (233), simulate (278), forecast (350), anomalies (419), real-wire stream (465), and the three exports. The synthesize endpoints all mutate the returned `WorkbookAnalysis` and write back via `_save_analysis()` which targets `db.workbook_analyses`. If `_load_analysis` itself were dispatched, a synthesize call on an `ana-*` id would mutate the legacy collection — a silent data leak.

Surgical refinement: a sibling helper `_load_analysis_for_export(aid, account_id)` is used ONLY by the three export endpoints. The shared `_load_analysis` remains legacy-collection-only. Same semantic outcome as the dispatch's option (a), strictly smaller blast radius. Three lines changed at three export call sites.

### Adapter shape (Phase 1 — empty-synthesis safe)

`_adapt_new_analysis_to_workbook_analysis(row)` builds an ephemeral, never-persisted `WorkbookAnalysis` view from an `Analysis` row:
- `filename` ← row.title (or first source's filename as fallback)
- `file_format` ← first source's format (default xlsx)
- `file_size_bytes` ← sum of all sources' bytes
- `document_id` ← row.id (surrogate; satisfies the legacy schema's required-field guard)
- `sheets` ← ONE synthetic sheet "Analysis Sources" with 3 columns (filename / format / size_bytes), N rows
- `signals` / `simulations` / `forecasts` / `anomalies` ← empty lists (Phase 3 will populate via Solva v2 narration)
- `status` ← `"ready"`

Builders handle empty lists gracefully (PPTX skips empty sections; my DOCX has `if analysis.signals:` guards; my XLSX writes header-only sheets when empty). Verified by tests 4/5/6 — all three formats produce valid Office files from an `ana-*` Analysis.

---

## 3 — Test inventory (9 of ≤10, R4 compliant)

| # | Test | Status |
|---|---|---|
| 1 | `test_multi_file_upload_creates_one_analysis_with_two_source_refs` | ✅ |
| 2 | `test_250mb_boundary_rejects_overflow` | ✅ |
| 3 | `test_pptx_builder_byte_identical_on_same_input` (legacy schema regression guard) | ✅ |
| 4 | `test_multi_file_xlsx_export_end_to_end` (**NEW — closes R3 gap**) | ✅ |
| 5 | `test_multi_file_docx_export_end_to_end` (**NEW — closes R3 gap**) | ✅ |
| 6 | `test_multi_file_pptx_export_end_to_end` (**NEW — closes R3 gap**) | ✅ |
| 7 | `test_session_close_purges_blob_retains_analysis` | ✅ |
| 8 | `test_tenant_scope_viewer_cannot_read_admin_analysis` (now also covers .pptx, viewer-seed cross-direction, v2 read both directions) | ✅ |
| 9 | `test_openapi_spec_includes_new_endpoints` | ✅ |

Final count: **9 tests, all green**. (Test 10 = the Solva v1 byte-identical guard + voice-lint, both delegated to the existing tree per the phase contract.)

What was dropped vs. v1: the `_seed_admin_workbook` helper which seeded via the legacy `/upload` endpoint. v2 has a single `_seed_multi_analysis` helper that goes through `/upload-multi`. No more seed-via-legacy shortcut.

---

## 4 — Sanity sweep results

```
tests/test_track_a_phase1_analysis_foundation.py    9 passed
tests/test_track_b_phase1_signin_begin.py           5 passed, 2 skipped (Fig 20+22 blocked)
tests/test_phase_p5_14_workbook_analyze.py         31 passed
tests/test_solva_v1_unchanged.py                    4 passed
voice_lint                                          clean
```

Total: 49 passed, 2 skipped. No regressions to P5.14 surface (the legacy export endpoints are byte-identical for `wba-*` ids — they fall through `_load_analysis_for_export` to `_load_analysis` exactly as before).

---

## 5 — Honest reckoning (R7 — STOP-and-surface inventory)

1. **The R3 gap was real and in my work.** v1's `_seed_admin_workbook` helper called the legacy `/upload` endpoint; the export tests pinned on `wba-*` ids. The multi-file → export journey was never exercised at the test layer. v2's `_seed_multi_analysis` calls `/upload-multi` and the export tests pin on `ana-*` ids. This is exactly the failure mode R3 was written to catch. Acknowledged.

2. **Dispatch option (a) refined.** The dispatch's literal "Make `_load_analysis()` dispatch by id prefix" would have leaked the new entity into the synthesize endpoints (signals/simulate/forecast/anomalies write back via `_save_analysis` to the legacy collection). Surfacing per R5/R7 — chose the sibling-loader pattern for zero blast radius. Semantically identical from the export consumer's perspective.

3. **Phase 1 multi-file exports carry no synthesis content.** A multi-file Analysis today carries no signals / simulations / forecasts / anomalies — the new entity is the shell. The exports for `ana-*` ids produce valid Office files listing the sources + cover narration, with empty synthesis sections. Phase 3 (Solva v2 narration) populates them. Tester journey-completion should verify "file opens cleanly, lists sources" — NOT "contains rich narration".

4. **The Track A Phase 1 row stays 🟡 PARTIAL.** Per dispatch: "MASTER_STATE.md Section 4 Track A Phase 1 stays 🟡 PARTIAL until tester re-verifies (not your call to flip)". Honoured.

5. **No new env vars, no Stripe/SendGrid/GCP, no Solva narration code, no multi-workbook merging, no frontend touch.** R6 honoured.

6. **Admin first-session reset to terminal state** per the dispatch hygiene clause. Verbatim PRE/POST shown in §1.

---

## 6 — Tester re-verification journey (R3 gate)

> Sign in as admin@akki.ai. Verify `/app/work-studio` (or wherever) is reachable normally — the first-session intake does NOT re-trigger (state reset confirmed). Then via API: `POST /api/workbook/upload-multi` with two real files; capture the returned `ana-*` id. Issue all three `GET /api/workbook/analyses/{aid}/report.{xlsx|docx|pptx}` — confirm 200, PK magic, openable in Office, file lists the source inventory. Cross-tenant negative: viewer@akki.ai gets 404 on all three exports of admin's `aid`.
>
> If that passes → Track A Phase 1 row flips to ✅ in MASTER_STATE.md Section 4. (Not my call — tester's call.)
