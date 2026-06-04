# Track A Phase 2 + Track B Phase 2 — Combined Close Memo

**Date:** 2026-06-04T04:07:54Z
**Rails honoured:** R1 (MASTER_STATE.md read first), R3 (tester journey-completion gates all flips to ✅), R4 (9 lockdowns Track A · 9 lockdowns Track B, both ≤10), R5 (ground-truth read on DocumentDrawer chrome + tasks.py state machine before any change), R6 (zero out-of-scope work), R7 (one TM5 destination ambiguity surfaced + resolved before coding).

---

## 1 — File-touched diff

### Track A Phase 2
```
M backend/models/analysis.py                                +5    (objective field on Analysis)
M backend/routers/workbook_analysis.py                      +118  (Query import, objective on upload-multi, /v2/analyses LIST, PATCH objective, POST notes)
M backend/services/analysis_lifecycle.py                    +5    (objective threading through build)
A frontend/src/components/analyze/AnalyzeDrawer.jsx         +332  (NEW — Sheet + 3 Tabs, mirrors DocumentDrawer chrome)
A frontend/src/pages/AnalyzeJournal.jsx                     +196  (NEW — Documents-mirroring listing shell)
M frontend/src/App.js                                       +6/-1 (legacy → new redirect; new route mount)
A backend/tests/test_track_a_phase2_drawer_journal.py       +9 lockdowns
```

### Track B Phase 2
```
M backend/routers/tasks.py                                  +147  (commission/close endpoints + counts + audit + fan-out re-trigger)
M frontend/src/pages/TaskManager.jsx                        +31   (count fetch + tab badges with live numbers)
M frontend/src/components/tasks/TaskDrawer.jsx              +60   (Commission/Close CTAs in FooterCTAs + onPatched plumbing)
M frontend/src/components/tasks/FollowUpDraftsCard.jsx      +11   ("View more" → /app/cycle/drafts; verbatim QA cite in comment)
A backend/tests/test_track_b_phase2_task_lifecycle.py       +9 lockdowns
```

### Shared
```
M memory/MASTER_STATE.md                                    (Section 3 TM1/TM2/TM5; Section 4 Track A Phase 2 + Track B Phase B2; Section 7)
A memory/sprints/TRACK_A_PHASE2_AND_TRACK_B_PHASE2_combined.md (this memo)
```

**Totals:** 18 lockdowns added (9+9, both ≤10). All 18 green.

---

## 2 — Track A Phase 2 highlights

### Chrome citation (Documents drawer mirror)

Ground-truth read before coding: `frontend/src/components/documents/DocumentDrawer.jsx` (1093 lines) — uses shadcn `<Sheet side="right" className="!w-[60vw]">` + `<Tabs>` + per-tab `<TabsContent>`. `AnalyzeDrawer.jsx` replicates this chrome exactly:
- Same 60% viewport-width sheet (`!w-[60vw] !max-w-[60vw]`)
- Same topline-statistics header pattern (status pill + title + relative-time chips)
- Same tab shape (`rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]`)
- Same auto-saved notes pattern (textarea + save button + ordered list of prior notes with relative-time)

NO new chrome invented; everything mirrors the Documents drawer pattern.

### Three tabs

- **Bottom Line** (`TabsContent value="bottom-line"`): summary text block + the per-Analysis notes list + an inline note-add textarea. Phase 3 Solva v2 narration will populate the "What we have" block; today it shows deterministic source counts + a "Narration arrives in the next phase" line per dispatch contract ("Solva narration tabs land in Phase 3").
- **Sources** (`value="sources"`): one card per source file (filename, format, size, uploaded-at, blob-purged flag) + the `refresh_history[]` listing with per-event labels.
- **Export** (`value="export"`): three buttons hitting the Phase 1 endpoint shape `GET /api/workbook/analyses/{aid}/report.{ext}` for xlsx/docx/pptx.

### Objective + notes

- Objective: `<Textarea>` above the tabs, debounced 800ms → `PATCH /v2/analyses/{aid}/objective`. Auto-save spinner inline.
- Notes: append-only via `POST /v2/analyses/{aid}/notes`. Auto-saved on click. Notes persist past session-close (per D4 retention rule: excel binary deleted, Analysis + objective + notes retained indefinitely).

### Backward-compat

App.js: `<Route path="/app/work-studio/analyze" element={<Navigate to="/app/analyze" replace />} />` — the legacy URL redirects to the new journal. The `WorkStudioAnalyze` page module remains in the repo for future ad-hoc deep-link entry-points; it just isn't routed anymore (lazy import preserved with an eslint-disable so the dead-import lint doesn't trip).

### Track A Phase 2 lockdowns (9 of ≤10)

| # | Test | Result |
|---|---|---|
| 1 | `test_v2_list_returns_only_tenant_rows` | ✅ |
| 2 | `test_upload_multi_persists_objective_text` | ✅ |
| 3 | `test_v2_detail_returns_full_entity` | ✅ |
| 4 | `test_note_post_then_appears_on_read` | ✅ |
| 5 | `test_two_notes_both_persist` (no silent dedup) | ✅ |
| 6 | `test_export_endpoints_still_serve_ana_ids` (Phase 1 regression — all 3 formats on `ana-*` ids) | ✅ |
| 7 | `test_cross_tenant_note_post_blocked` (3-vector negative: notes / objective / read) | ✅ |
| 8 | `test_legacy_workstudio_analyze_redirects_to_analyze` (source-strict on App.js) | ✅ |
| 9 | `test_analyze_drawer_renders_three_required_tabs` (source-strict on AnalyzeDrawer.jsx) | ✅ |

Test 10 — Solva v1 byte-identical guard 4/4 + voice-lint clean — delegated to the existing tree.

### Session-close regression

The dispatch lockdown #6 ("Session-close still deletes excel binary; Analysis + notes + objective retained") is covered by the **existing** Phase 1 test `test_session_close_purges_blob_retains_analysis`. I did NOT duplicate it in the new file; that's a Phase 1 invariant.

---

## 3 — Track B Phase 2 highlights

### State machine

Draft → Active (commission) → Closed (close). No skip, no reverse this phase (reopen is documented as not-supported in the QA spec: "Closed tasks become read-only and can no longer be edited, restarted, or reopened").

Endpoints:
- `POST /api/tasks/{id}/commission` — idempotent on Active, rejects Closed with HTTP 400 `cannot_commission_closed_task`.
- `POST /api/tasks/{id}/close` — idempotent on Closed, rejects Draft with HTTP 400 `cannot_close_draft_task`. Records `closed_at` ISO timestamp.

Audit:
- `task.commissioned` / `task.closed` rows inserted into `db.audit_log` with `metadata.prev_state` + `metadata.next_state`.
- Idempotent re-call writes NO new audit (test 3 + test 4 verify the count delta).

Contributor invitation fan-out: re-triggered on commission via existing `services/tasks/contributor_invitation_service.fan_out_invitations` — best-effort, logs but doesn't fail the request if fan-out errors.

### Confirmation modal copy (verbatim from QA Task Manager doc item 2)

The Close button uses `window.confirm(...)` with the EXACT QA text:
> "Are you sure you want to close this task? Once closed, the task will be marked as complete and cannot be reopened."

(Shadcn `<AlertDialog>` upgrade is deferred — `window.confirm` carries the verbatim copy today and is voice-lint clean.)

### Filter-tab live counts

New backend: `GET /api/tasks/counts?context_id=…` returns `{draft, active, closed, all}`. TaskManager.jsx fetches on mount and on every `refreshKey` bump. The tab buttons now render an inline badge `<span data-testid="task-manager-tab-{key}-badge">` ONLY when count > 0 (empty tabs stay clean).

### TM5 — "View more"

R5 ground-truth read before any code change:
- Grep for `View more` returned two surfaces: `FollowUpDraftsCard.jsx:115` (current target `/app/work-studio?kind=drafts`) and `RecentTaskActivityCard.jsx:135` (already wired to `/app/task-manager/activity`).
- The QA doc TM5 verbatim ask: *"I think the button should open a page that shows Follow Up Emails drafted by Akki to contributors with pending contributions."*
- Grep for `follow-up email` surfaced `pages/cycle/CycleDraftJournal.jsx` whose own header reads: *"lists every agent-cycle-drafted follow-up email across all active cycles in this context."* Mounted at `/app/cycle/drafts` (App.js:141-144).
- Match — verbatim. Re-wired `FollowUpDraftsCard` "View more" → `/app/cycle/drafts`. `RecentTaskActivityCard` left as-is (separate surface).

### Track B Phase 2 lockdowns (9 of ≤10)

| # | Test | Result |
|---|---|---|
| 1 | `test_commission_draft_to_active_and_audit` | ✅ |
| 2 | `test_close_active_to_closed_and_audit` | ✅ |
| 3 | `test_commission_idempotent_on_active` (no new audit row) | ✅ |
| 4 | `test_close_idempotent_on_closed` (no new audit row) | ✅ |
| 5 | `test_state_machine_guards` (commission-on-closed 400 + close-on-draft 400 combined) | ✅ |
| 6 | `test_cross_tenant_lifecycle_blocked` (commission + close cross-tenant) | ✅ |
| 7 | `test_filter_tab_counts_match_db` (3 drafts + 2 actives + 5 closeds → 3/2/5) | ✅ |
| 8 | `test_follow_up_drafts_view_more_targets_cycle_drafts` (TM5) | ✅ |
| 9 | `test_sanitize_task_redacts_account_id` (allow-list regression) | ✅ |

Bug 27 regression coverage is via the existing `test_bug27_*` suite (untouched by this dispatch).

---

## 4 — Sanity sweep

```
tests/test_track_a_phase2_drawer_journal.py            9 passed
tests/test_track_b_phase2_task_lifecycle.py            9 passed
tests/test_track_a_phase1_analysis_foundation.py       9 passed
tests/test_track_b_phase1b_signin_cards_fig22.py       9 passed
tests/test_track_b_phase1_signin_begin.py              7 passed, 2 skipped (legacy stubs)
tests/test_phase_p5_14_workbook_analyze.py            31 passed
tests/test_solva_v1_unchanged.py                       4 passed
voice_lint                                             clean
```

**77 passed + 3 expected legacy skips.** No regressions across Track A Phase 1, Track B Phase B1/B1b, P5.14 surface, or Solva v1 byte-identical guard.

---

## 5 — MASTER_STATE.md updates

**Section 3:**
- **TM1** (filter-tab badges): ❌ OPEN → 🟡 PARTIAL (tester-pending).
- **TM2** (Commission button + Closure flow): ❌ OPEN → 🟡 PARTIAL (tester-pending). Confirmation modal copy is verbatim per QA doc; `closed_at` recorded; reopen-from-Closed intentionally not supported.
- **TM5** ("View more" → follow-up emails): ❌ OPEN → 🟡 PARTIAL (tester-pending). Wired to `/app/cycle/drafts` per verbatim QA + verbatim destination-page header.

**Section 4:**
- **Track A Phase 2 (Chrome):** ❌ NOT STARTED → 🟡 SHIPPED tester-pending.
- **Track B Phase B2:** ❌ NOT STARTED → 🟡 SHIPPED tester-pending.

**Section 7:** timestamped 2026-06-04T04:07:54Z; agent line updated.

---

## 6 — Honest reckoning (R7)

1. **TM5 destination resolved deterministically** — initial grep showed two "View more" surfaces; the QA destination wasn't explicitly named. I followed R5 (root-cause-first ground-truth read) by grep'ing for "follow-up email" in the codebase; `CycleDraftJournal` header text matched the QA ask verbatim. No guessing.
2. **Phase 1 multi-file synthesis content remains empty.** Per Phase 1 contract; Phase 3 (Solva v2 narration) populates `observations[]`. Bottom Line tab today shows a deterministic "Narration arrives in the next phase" message + the source counts + the notes list.
3. **`window.confirm()` not shadcn AlertDialog** — chose the simplest path that carries the verbatim QA modal text. Upgrading to AlertDialog is a polish task (Track B Phase B5 or later) — not in B2 scope.
4. **Reopen flow intentionally NOT supported** — per QA verbatim: "Closed tasks become read-only and can no longer be edited, restarted, or reopened." If the C6 reopening flow for Questions (G21) ever influences this product decision, surface for re-dispatch.
5. **Backend `tasks.py` `_sanitize_task` allow-list was NOT changed.** New fields (`status_history`, `closed_at`) are already part of the existing serialised shape; the lockdown asserts no `_`-prefixed key leaks. If the allow-list ever needs to add `closed_at`, the existing bug-27 pattern is documented at `routers/tasks.py`.
6. **No new env vars, no Stripe, no SendGrid console, no GCP creds, no Solva narration code, no multi-workbook synthesis.** R6 honoured.
7. **No Track B Phase B3/B4/B5 items touched** despite some being adjacent in the codebase. R6 honoured.

---

## 7 — Tester re-verification journey

### Track A Phase 2
> Sign in. Visit `/app/analyze` — Analyze Journal lists prior analyses (or empty state). Type an objective + click Upload to upload 1+ files. Drawer opens at Bottom Line tab. Confirm objective is persisted (reload page → objective still there). Switch to Sources tab — see per-file metadata + refresh history. Switch to Export tab — download all 3 formats and confirm they open in Office. Add 2 notes → reload → both notes still listed. Visit `/app/work-studio/analyze` (legacy URL) → redirected to `/app/analyze`. Cross-tenant: viewer cannot list/open admin's Analysis.

### Track B Phase 2
> On the TaskManager page, verify the three tabs (Active / Draft / Closed) carry live count badges matching the actual task counts. Open a Draft task → Commission button visible → click → toast confirms + task moves to Active filter. Open the now-Active task → Close button visible → click → confirm prompt with verbatim QA text → confirm → task moves to Closed filter. Verify Closed task drawer no longer shows Commission or Close. Open the Task Manager card "View more" on the Follow-Up Drafts panel → should land at `/app/cycle/drafts`. Cross-tenant: viewer cannot commission/close admin's task.
>
> If both pass → flip Section 3 (TM1, TM2, TM5) + Section 4 (Track A Phase 2, Track B Phase B2) to ✅. Not my call — tester's call.
