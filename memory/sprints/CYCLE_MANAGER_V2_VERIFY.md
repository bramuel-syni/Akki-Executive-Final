# Cycle Manager v2 — Manual Verify Walkthrough

**Sprint:** Cycle Manager v2 — Multi-Cycle Support
**Brief:** `/app/memory/sprints/CYCLE_MANAGER_V2_BRIEF.md`
**Date:** 2026-02

---

## A. Automated test suite

```bash
cd /app/backend && python -m pytest \
  tests/test_privacy_wall.py \
  tests/test_phase_g_privacy_wall_sentinel.py \
  tests/test_privacy_wall_phase_2c.py \
  tests/test_universal_search.py \
  tests/test_exco_teams.py \
  tests/test_render_determinism.py \
  tests/test_cycle_assignment_handoff.py \
  tests/test_cycle_assignment_privacy_wall.py \
  tests/test_cycles_v2.py \
  tests/test_team_catalogue.py \
  tests/test_cycle_migration.py \
  -q
```

**Acceptance:** `86 passed` (41 baseline + 25 prior + 20 new).

## B. Migration marker

```bash
mongo $MONGO_URL/$DB_NAME --eval '
db["_migrations"].findOne({"id": "0001_multi_cycle"})
'
```

**Expected:** a row with `applied_at` populated and `stats: {cycles_created, contexts_scanned, backfilled_*}`.

## C. `/api/docs` new endpoint surface

```bash
curl -s http://localhost:8001/api/openapi.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
keep=lambda p:any(s in p for s in ['/cycles','/team-catalogue','/eligible-contributors','/check-team-duplicate','/activate','/close'])
for p in sorted(d['paths']):
  if keep(p):
    ms=','.join(m.upper() for m in d['paths'][p] if m in ('get','post','put','delete','patch'))
    print(f'{ms:18s} {p}')
"
```

Expected (10 new endpoints):

```
POST,GET            /api/contexts/{cid}/cycles
GET                 /api/contexts/{cid}/cycles/{cycle_id}
POST                /api/contexts/{cid}/cycles/{cycle_id}/activate
POST                /api/contexts/{cid}/cycles/{cycle_id}/close
POST                /api/contexts/{cid}/cycles/{cycle_id}/agenda-items/{ai_id}/check-team-duplicate
GET                 /api/contexts/{cid}/cycles/{cycle_id}/agenda-items/{ai_id}/eligible-contributors
GET,POST            /api/contexts/{cid}/team-catalogue
PATCH,DELETE        /api/contexts/{cid}/team-catalogue/{member_id}
```

Plus existing `/cycle/*` endpoints now accept `?cycle_id=...`.

## D. Hex literal sweep

```bash
grep -rnE '#[0-9a-fA-F]{3,8}\b' \
  frontend/src/pages/cycle \
  frontend/src/components/cycle \
  frontend/src/pages/Cycle.jsx \
  frontend/src/pages/CycleSettings.jsx \
  frontend/src/pages/ned/ \
  | grep -v 'color:var'
```

**Expected:** zero output.

## E. Browser walkthrough — Cycle list

| # | Step | Test-id | Expected |
|---|---|---|---|
| 1 | Sign in as a team-workspace owner | — | Land on `/app/home` |
| 2 | Navigate to `/app/cycle` | `cycle-list-page` | Cycle list renders. Existing migrated cycle appears with status=Active |
| 3 | Click "Add Cycle" (or press `c`) | `cycle-list-add-cycle` | Modal opens with title input |
| 4 | Type "Q1 2026" and Create | `cycle-list-new-create` | Redirects to `/app/cycle/{new_id}?tab=agenda` |
| 5 | Type in the search box "Q1" | `cycle-list-search` | List filters in real time |
| 6 | Change Sort to "Alphabetical A–Z" | `cycle-list-sort` | Cards re-order |
| 7 | Create >12 cycles to trigger pagination; verify previous/next | `cycle-list-pagination` | Pagination strip appears with total count |

## F. Browser walkthrough — Activate flow (PO #1 MANUAL)

| # | Step | Expected |
|---|---|---|
| 1 | Open the just-created Draft cycle | Breadcrumb shows "Cycle Manager > Q1 2026 · DRAFT" |
| 2 | "Activate Cycle" button visible top-right on Agenda tab | Disabled until title + ≥1 agenda item added |
| 3 | Add an agenda item, click Activate | Confirmation modal opens |
| 4 | Confirm | Status flips to Active, badge updates, button hides |
| 5 | Navigate back via breadcrumb "Cycle Manager" | Lands on list with cycle showing as Active |

## G. Browser walkthrough — Close flow

| # | Step | Expected |
|---|---|---|
| 1 | Open an Active cycle, walk to Compilation tab | Compilation step renders |
| 2 | Bottom step-nav shows "Close Cycle" button (oxblood) | — |
| 3 | Click Close Cycle | Modal: "Are you sure you want to close this cycle? Once closed, the cycle will be read-only and cannot be edited. Make sure you have downloaded the compilation document before closing." |
| 4 | Confirm | Redirects to cycle list, toast: "Cycle closed. You can still re-download the compilation document from the Compilation tab." |
| 5 | Re-open the now-completed cycle | Banner: "This cycle is closed and read-only…". All input fields disabled. Compilation tab keeps "Produce Draft Compilation" enabled. |
| 6 | Try to add a team member via the dialog | 409 from backend; surfaced as error toast |

## H. Browser walkthrough — Team Catalogue & contributor scoping (PO #2)

| # | Step | Expected |
|---|---|---|
| 1 | Open a Draft cycle, go to Team tab | Two new buttons in header: "Manage Catalogue" + "+ Add Team Member" |
| 2 | Click "+ Add Team Member" | Modal opens at Catalogue tab |
| 3 | Catalogue is empty initially → switch to "Add New Member" tab | Form |
| 4 | Add a member with `owns_item_ids` = [Item A] | Member appears in team list; also visible in Catalogue |
| 5 | Click "+ Add Team Member" again | Catalogue tab now shows the previously-added member as a pickable row |
| 6 | Pick that member → name + email pre-fill in New tab → submit with `owns_item_ids` = [Item A] | Backend returns 409 duplicate warning; inline yellow box appears |
| 7 | Click "Add anyway" | Second per-cycle row created |
| 8 | Click "Manage Catalogue" → edit name → remove a member | Soft-delete; member no longer in catalogue; historical cycle_team rows preserved |
| 9 | Go to Contributions tab | Agenda item dropdown defaults to "Select an agenda item"; contributor dropdown disabled |
| 10 | Pick Item A from dropdown | Contributor dropdown enables and shows ONLY members with `owns_item_ids` containing Item A |

## I. Two-cycle isolation

| # | Step | Expected |
|---|---|---|
| 1 | Create Cycle A. Add team member "Alice". | Alice in Cycle A team |
| 2 | Create Cycle B. Go to Team tab. | Empty team list — Cycle B does NOT show Alice from Cycle A |
| 3 | In Cycle B, "+ Add Team Member" → Catalogue tab | Alice IS available in the catalogue (context-scoped, not cycle-scoped) |
| 4 | Pick Alice for Cycle B with empty role / description | Alice now in Cycle B team with blank role/description |

## J. Two-layer navigation

| # | Step | Expected |
|---|---|---|
| 1 | Open a cycle, switch to Team tab | URL updates to `?tab=team` |
| 2 | Click "Cycle Manager" breadcrumb | Returns to list; refresh on list preserves `tab=team` for that cycle on re-open (URL-backed) |
| 3 | Inside a tab, Back/Next moves between Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation | URL updates per tab; Back is disabled on Agenda; on Compilation, Next becomes "Close Cycle" (active) or "Cycle Completed" (completed/disabled). |

## K. Completed-cycle write enforcement (curl probe)

```bash
API=https://akki-executive.preview.emergentagent.com
curl -s -X POST "$API/api/contexts/<cid>/cycle/team?cycle_id=<completed_cycle_id>" \
  -H "Cookie: akki_jwt=<your_token>" -H "Content-Type: application/json" \
  -d '{"name":"X","email":"x@example.com","contribution_description":"-","owns_item_ids":[]}'
```

**Expected:** `409` with body containing `"code":"cycle_completed"`.

## L. Compilation re-download on completed cycles (PO acceptance)

```bash
curl -s -X POST "$API/api/contexts/<cid>/cycle/draft-compilation?cycle_id=<completed_cycle_id>" \
  -H "Cookie: akki_jwt=<your_token>"
```

**Expected:** `200` with `brief_id`, `sha256`, `file_name`, etc. — even though the cycle is closed.

---

## Files touched in this sprint

### Backend (new)

- `/app/backend/services/cycle_lifecycle.py`
- `/app/backend/routers/cycles.py`
- `/app/backend/routers/team_catalogue.py`
- `/app/backend/migrations/__init__.py`
- `/app/backend/migrations/_runner.py`
- `/app/backend/migrations/_0001_multi_cycle.py`
- `/app/backend/tests/test_cycles_v2.py`
- `/app/backend/tests/test_team_catalogue.py`
- `/app/backend/tests/test_cycle_migration.py`

### Backend (edited)

- `/app/backend/server.py` — router includes + indexes + migration boot hook
- `/app/backend/routers/cycle_manager.py` — `?cycle_id=` query param threaded through every singleton endpoint; `require_cycle_writable` applied on every mutation; new `eligible-contributors` endpoint

### Frontend (new)

- `/app/frontend/src/lib/cycleApi.js`
- `/app/frontend/src/pages/cycle/CycleList.jsx`
- `/app/frontend/src/components/cycle/CycleCard.jsx`
- `/app/frontend/src/components/cycle/CycleBreadcrumb.jsx`
- `/app/frontend/src/components/cycle/CycleStepNav.jsx`
- `/app/frontend/src/components/cycle/AddTeamMemberDialog.jsx`
- `/app/frontend/src/components/cycle/TeamCatalogueDialog.jsx`

### Frontend (edited)

- `/app/frontend/src/App.js` — `/app/cycle` → CycleList, `/app/cycle/:cycleId` → Cycle
- `/app/frontend/src/pages/Cycle.jsx` — `cycleId` from URL, `?cycle_id=` threaded through every api call, breadcrumb + activate/close buttons, step nav, team dialogs, contributor dropdown scoping

### Documentation

- `/app/memory/sprints/CYCLE_MANAGER_V2_BRIEF.md`
- `/app/memory/sprints/CYCLE_MANAGER_V2_VERIFY.md` (this file)
