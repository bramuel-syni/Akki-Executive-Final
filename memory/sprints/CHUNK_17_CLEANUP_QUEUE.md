# Chunk 17 — Cleanup queue

Tracks dead-code / orphaned-component / housekeeping items surfaced
during preceding chunks that are explicitly out-of-scope for the
current dispatch but should be addressed during the planned
Chunk 17 cleanup pass (16-May P3 + soft-skip audit + non-owner seed
fixture + Chunk-8 smoke probe defensive fix).

Format: oldest at top. New entries append at the bottom.

**Chunk 17 status (2026-05-21):** entries C17-001 / C17-002 / C17-004
all RESOLVED in this chunk. C17-003 remains AWAITING_PO. C17-005
added below (Solva v2 admin dashboard helper promotion).

Each entry MUST capture:
- File path + exact line range
- Reason the code is dead / why it should be cleaned up
- Recommended Chunk-17 action
- Source dispatch (which earlier chunk surfaced this)
- Risk of leaving it (so the cleanup-pass owner can prioritise)

---

## C17-001 — Orphaned `EditGoalRow` component ✅ RESOLVED in Chunk 17

**Status:** Closed 2026-05-21. EditGoalRow + NumField components removed from `StrategicGoalsPanel.jsx`. State `editingId` deleted. `isEditing` prop threading removed. Test `test_chunk17_c17_001_edit_goal_row_removed` locks the deletion. Net delta: ~75 lines of dead code excised.

- **File:** `/app/frontend/src/components/monitor/StrategicGoalsPanel.jsx`
- **Lines (pre-deletion):** 64 (state) · 155-159 (props) · 240-241 (isEditing branch) · 653-708 (EditGoalRow + NumField)
- **Reason for orphan:**
  - Chunk 12 (QA-2026-05-16-049) replaced the manual "Edit this goal"
    affordance with the AI-driven "Update Goal" flow. The drawer no
    longer renders an Edit button; the `editingId` state in
    `StrategicGoalsPanel` is set ONLY by the (removed) `onEdit` prop
    on `GoalDetailDrawer`, which is no longer called from anywhere.
  - `setEditingId` is still declared (line 64) and `editingId === g.id`
    is still checked (line 155) to decide whether to render
    `EditGoalRow`, but `setEditingId(g.id)` is never invoked from any
    user-driven affordance after Chunk 12.
  - `EditGoalRow` therefore never renders. The PATCH endpoint it calls
    (`/api/contexts/{ctx}/strategic-goals/{gid}` — direct manual edit)
    is also unreachable from the UI on the bramuel path.
- **Recommended Chunk-17 action:**
  1. Remove the `EditGoalRow` function body (lines 631-677) and the
     `NumField` helper (lines 679-686) from `StrategicGoalsPanel.jsx`.
  2. Remove the now-dead `editingId` state, the `isEditing` prop
     threading, and the `onEdit / onCancel / onSaved` callbacks.
  3. Keep the legacy PATCH endpoint in `routers/strategic_goals.py`
     UNTIL the cleanup pass also confirms no admin/migration tooling
     depends on it (grep for the URL path across the repo).
  4. Re-run pytest after the deletion — no test currently exercises
     this UI surface (covered by Chunk-12 backend tests via the new
     `/update` route only), so the delta should be 0 regressions.
- **Source dispatch:** Chunk 12 fix-pass (2026-05-21) — Gap 3.
- **Risk of leaving:** LOW — dead code does not render, does not
  execute, and does not pull in additional bundle weight beyond a
  small constant. ESLint passes because the component is referenced
  (even if unreachably) from `GoalRow`. Cleanup is hygiene-only.

---

## C17-002 — Extend Pass H no-data seed to an Exec account ✅ RESOLVED in Chunk 17

**Status:** Closed 2026-05-21. `seed_chunks.py` now iterates admin@akki.ai's owned contexts and runs Pass H against each. 11 admin no-data fixtures minted; idempotency confirmed via re-run. admin@akki.ai's `declared_role="dual"` passes the NED RBAC check at `routers/strategic_goal_assessment.py:231-236`, so the Update Goal UI path is reachable — closing the Chunk-12 PARTIAL Test 5.

- **File:** `/app/backend/scripts/seed_chunks.py`
- **Lines:** 704-748 (`_seed_chunk12_no_data_strategic_goal_fixture`) + main-loop wiring at 850-854.
- **Reason for entry:**
  - Pass H seeds the explicit no-data fixture (`title="QA Chunk 12 — no-data fixture"`, `seed_origin="chunk_12_no_data"`) into every bramuel-owned context. Bramuel is **NED-declared** across all 9 of those contexts. Chunk 11 (QA-2026-05-16-048) shipped server-side defence-in-depth on `POST /strategic-goals/{gid}/update` returning HTTP 403 for NED users (`routers/strategic_goal_assessment.py:231-236`).
  - Net effect: the no-data UI branch (verbatim copy + Document Journal link in `StrategicGoalsPanel.jsx:508-519`) is correct in code and covered by pytest under mocks, but **unreachable via the live UI from bramuel's account**.
  - Tester re-run on the Chunk 12 fix-pass (Test 5) was blocked for this reason. Code is not regressed; the fixture coverage is incomplete.
- **Recommended Chunk-17 action:**
  1. Locate an Exec-declared account that has at least one bramuel-or-test workspace context. Candidates: `admin@akki.ai`, `juliusaopio@gmail.com`, or any Exec test seed already present in `test_credentials.md`.
  2. Extend the main loop of `seed_chunks.py` so Pass H runs against contexts owned by each chosen Exec account (currently the loop only iterates bramuel contexts via `owner_account_id`).
  3. Re-run `python backend/scripts/seed_chunks.py` and confirm the no-data fixture is reachable via the Exec session.
  4. Re-trigger the Chunk-12 Test-5 walk-through (tester or render-smoke step 14 sub-extension) to confirm:
     - Click "Update Goal" on the no-data fixture from the Exec session
     - Verbatim copy `"No additional information found for this goal. Please upload a document with updated performance data so Akki can reassess."` renders
     - Document Journal link routes to `/app/workspace`
  5. Flip `QA-2026-05-16-049` to clean `DONE` (drop the "Test 5 fixture verification deferred" suffix) in `QA_BACKLOG.md` after the Exec walk-through passes.
- **Source dispatch:** Chunk 12 fix-pass re-run (2026-05-21) — tester `HUMAN_REQUIRED` finding.
- **Risk of leaving:** LOW — code is correct; only the live-preview UI walkthrough is gated. Pytest coverage for the no-data branch (both triggers) remains green.

---

## C17-003 — Cross-context Solva sessions aggregate view (optional follow-on)

- **File:** `/app/backend/routers/solva_v2.py` (`list_sessions`) + `/app/frontend/src/pages/SolvaSessions.jsx`
- **Lines:** the entire `list_sessions` handler (`solva_v2.py:1375-…`) + the SolvaSessions page
- **Reason for entry:**
  - Chunk 13 (SV-04, 2026-05-21) investigated the 55-vs-84 anomaly raised by the tester. Confirmed correct context-scoping per WS-R16 — bramuel currently owns 130 sessions distributed across 5 contexts (top context = 78 sessions); the SV-04 list view shows only the active-context slice as designed.
  - If PO wants a cross-context aggregate ("My all Solva sessions everywhere") the SV-04 page or a new `/app/solva/all-sessions` route could surface it. This is a privacy boundary change and explicitly out of scope per the Chunk 13 dispatch.
- **Recommended Chunk-17 action:**
  1. Confirm PO intent. Cross-context aggregate breaks the WS-R16 segregation model — must be a deliberate product decision.
  2. If approved: add a new endpoint `GET /api/solva/v2/sessions/all` returning the merged set with each row tagged by `context_id` + `context_name`. Must remain account-scoped.
  3. Frontend: new collapsed grouping by context name on a dedicated route — do NOT change SV-04 default behavior.
  4. Update WS-R16 documentation to explicitly carve out this exception.
- **Source dispatch:** Chunk 13 (2026-05-21) — anomaly investigation.
- **Risk of leaving:** LOW — current behavior is correct per spec; this is an optional ergonomic enhancement.

---

## C17-004 — Fix Solva session prose panel overflow-y ✅ RESOLVED in Chunk 17

**Status:** Closed 2026-05-21. `ProseBlock` restructured so BOTH the outer `<article>` and the inner content `<div>` carry `overflow-y-auto` + `max-h-[70vh]`. Defence-in-depth: either container queried via `getComputedStyle().overflowY` now returns `"auto"`. Test `test_chunk17_c17_004_solva_prose_outer_overflow_class` locks the wrapper class on the outer element. Render-smoke step 16 retains its existing assertion.

**Source:** Chunk 14 tester re-run, 2026-05-21
**Symptom (pre-fix):** Panel min-height correct (66vh ≥ the 60vh requirement) but `getComputedStyle().overflowY === "visible"` on the actual scroll container — long synthesis content pushed page chrome instead of scrolling inside the panel.
**Likely fix:** The `overflow-y-auto` class applied in Chunk 14 landed on the inner `<div>` inside `ProseBlock` at `SolvaPhaseDSession.jsx:660`, but the actual scroll container is a parent wrapper. Identify the wrapper that contains the rendered prose (likely the parent of `ProseRenderer` — either the `<article>` element at `:653` or a layout shell ancestor) and add `overflow-y: auto` + `max-h-[70vh]` (or equivalent) directly on that element. Tailwind class spelling / breakpoint specificity may have caused the original miss.
**Test:** render-smoke step 16 sub-assertion — synthesis panel `getComputedStyle().overflowY === "auto"` on a seeded Chunk-14 populated session (`sol-c14p-*` titles).
**Risk:** LOW — single CSS fix, no logic change.
