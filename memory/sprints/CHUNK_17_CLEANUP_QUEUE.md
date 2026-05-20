# Chunk 17 — Cleanup queue

Tracks dead-code / orphaned-component / housekeeping items surfaced
during preceding chunks that are explicitly out-of-scope for the
current dispatch but should be addressed during the planned
Chunk 17 cleanup pass (16-May P3 + soft-skip audit + non-owner seed
fixture + Chunk-8 smoke probe defensive fix).

Format: oldest at top. New entries append at the bottom.

Each entry MUST capture:
- File path + exact line range
- Reason the code is dead / why it should be cleaned up
- Recommended Chunk-17 action
- Source dispatch (which earlier chunk surfaced this)
- Risk of leaving it (so the cleanup-pass owner can prioritise)

---

## C17-001 — Orphaned `EditGoalRow` component

- **File:** `/app/frontend/src/components/monitor/StrategicGoalsPanel.jsx`
- **Lines:** 631-686 (`function EditGoalRow` + helper `NumField`)
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
