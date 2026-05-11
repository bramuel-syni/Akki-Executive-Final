# Cycle Manager v2 — Multi-Cycle Support — Sprint Brief

**Status:** APPROVED-FOR-BUILD (2026-02). Scope locked. Source doc: `Cycle_Manager_Feature_Enhancement.docx`.
**Predecessor:** Cycle Manager Sprint (Assignment Handoff) — `/app/memory/sprints/CYCLE_MANAGER_BRIEF.md`.

## Locked Product Owner decisions

1. **Draft → Active transition: MANUAL.** User clicks "Activate Cycle". No auto-transition.
2. **Contributor dropdown scoping: FILTERED.** When an agenda item is selected on the Contributions tab, the contributor dropdown shows only team members assigned to that agenda item.
3. **Data migration:** existing single-cycle data migrates as **ACTIVE** status. No data loss. User closes manually when ready.
4. **Assignment-handoff system** (just-shipped C3 work): **leave in place**. Do not design v2 around it. If v2 architecture conflicts, refactor or remove the conflicting parts of the assignment system as needed and document in §Conflicts.

## Architectural shift

Single cycle per (account, context) → **many cycles per context**. Existing cycle-scoped collections (`cycle_agendas`, `cycle_team`, `cycle_contributions`, `cycle_followups`, `cycle_compilations`, `cycle_assignments`) become scoped by `cycle_id`. New `cycles` collection becomes the master. New account-scoped `team_catalogue` collection holds permanent member identity (name + email); per-cycle records hold role / contribution_description / agenda_assignments.

## Implementation key insight

Existing `cycle_agendas.id` already functions as the de-facto cycle id for the downstream collections (`cycle_team`, `cycle_contributions`, `cycle_followups` all reference it via `agenda_id`). The migration preserves these IDs and creates a parallel `cycles` row using the same id, so no downstream rewrite is needed beyond adding a `cycle_id` field equal to `agenda_id`.

## Must-have items (build order)

### Backend
1. `cycles` collection + 5 endpoints (create/list/detail/activate/close)
2. Migration script `/app/backend/migrations/0001_multi_cycle.py` + `_migrations` marker
3. `require_cycle_writable(cycle_id)` write-guard for completed cycles
4. `team_catalogue` collection + 4 CRUD endpoints + duplicate warning on add
5. `GET .../cycles/{cycle_id}/agenda-items/{ai_id}/eligible-contributors`
6. Compilation re-download must work on completed cycles
7. Existing cycle routes (agenda / team / contributions / followups / draft-compilation) accept `?cycle_id=...` query param; default to the unique active cycle if exactly one exists, else 400

### Frontend
8. Cycle list landing page at `/app/cycle` with search + sort + 12-per-page pagination
9. CycleCard component with status-driven visual hierarchy
10. Two-layer navigation (breadcrumb + Back/Next)
11. Activate Cycle + Close Cycle flows (with confirm modals)
12. Add Team Member dialog with Catalogue + New tabs + Manage Catalogue side panel
13. Per-cycle data scoping inside detail page
14. v7 palette sweep across cycle list, cards, all 6 tabs, modals

## Out of scope (explicit)

- NED Brief Review Centre / Exec-NED independence (future roadmap)
- Pulse, Monitor, Learn sprints
- Chat / streaming UX polish
- Stripe, Azure stack, deployment blockers
- LLM/provider changes

## Conflicts

Reconciliation notes with the just-shipped C3 ASSIGNMENT HANDOFF system live here as they emerge during build.

### Conflict #1 — `BoardSubmitPanel` cycle_id source

**State (pre-v2):** `BoardSubmitPanel` reads `cycle_id` from `out.cycle_id || out.agenda_id` returned by `POST /cycle/draft-compilation`. Compile-step always operates on the active cycle of the context.

**v2 impact:** the compile endpoint must operate on a specific cycle. The frontend now opens the compile tab with an explicit `cycle_id` from the URL `/app/cycle/:cycle_id`; the compile endpoint already returns `cycle_id`/`agenda_id` (added during C3) so `BoardSubmitPanel` continues to work without code change. **No refactor needed.**

### Conflict #2 — `cycle_assignments.cycle_id`

**State (pre-v2):** `cycle_assignments` rows already carry `cycle_id` (stored at create time from the URL).

**v2 impact:** none. The existing endpoint `POST /contexts/{cid}/cycles/{cycle_id}/briefs/{bid}/assignments` already requires `cycle_id` in the path. With v2's multi-cycle backend, this URL stays valid and now points to a *specific* cycle row in `db.cycles` rather than the implicit active one. **No refactor needed.**

### Conflict #3 — Single-cycle endpoints (`/contexts/{cid}/cycle/agenda`)

**State (pre-v2):** routes like `/cycle/agenda`, `/cycle/team`, `/cycle/contributions`, `/cycle/follow-ups`, `/cycle/draft-compilation` work against the unique active cycle per context.

**v2 resolution:** routes accept an optional `?cycle_id=...` query param. Resolution rule:
- If `cycle_id` provided → use it (validate it exists and belongs to context).
- If absent and exactly one active cycle exists → use it (legacy behaviour).
- If absent and multiple cycles → return 400 `{"detail": "cycle_id required: context has multiple cycles"}`.
- If absent and no cycles → fall through to the legacy auto-create behaviour for the agenda endpoints only; the other endpoints return 404.

This preserves all existing frontend code paths during the rollout and allows the new frontend to opt in to explicit `cycle_id`.

## Acceptance criteria

See the build directive for the full binary list. Summary:
- `pytest` green on new + existing Cycle tests
- `_migrations` marker recorded; first-run logs visible
- Hex-literal sweep on `frontend/src/pages/cycle*` + `frontend/src/components/cycle/*` returns 0
- `/api/docs` shows new endpoints

## Files index

- `/app/memory/sprints/CYCLE_MANAGER_V2_BRIEF.md` (this file)
- `/app/memory/sprints/CYCLE_MANAGER_V2_VERIFY.md` (manual smoke walkthrough)
- Backend new: `routers/cycles.py`, `routers/team_catalogue.py`, `migrations/0001_multi_cycle.py`, `services/cycle_lifecycle.py`, `tests/test_cycles_v2.py`, `tests/test_team_catalogue.py`, `tests/test_cycle_migration.py`
- Backend edited: `server.py`, `routers/cycle_manager.py` (cycle_id param)
- Frontend new: `pages/cycle/CycleList.jsx`, `pages/cycle/CycleDetail.jsx`, `components/cycle/CycleCard.jsx`, `components/cycle/CycleBreadcrumb.jsx`, `components/cycle/CycleStepNav.jsx`, `components/cycle/AddTeamMemberDialog.jsx`, `components/cycle/TeamCatalogueDialog.jsx`, `components/cycle/ActivateCycleButton.jsx`, `components/cycle/CloseCycleButton.jsx`, `lib/cycleApi.js`
- Frontend edited: `App.js`, `pages/Cycle.jsx` (deleted/replaced), `components/cycle/BoardSubmitPanel.jsx` (pass-through `cycle_id` prop)
