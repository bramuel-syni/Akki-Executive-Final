# Cycle Manager Sprint — Manual Verify Walkthrough

**Sprint:** Cycle Manager Assignment Handoff
**Date:** 2026-02
**Brief:** `/app/memory/sprints/CYCLE_MANAGER_BRIEF.md` §3.3 (locked C3 = ASSIGNMENT HANDOFF)
**Acceptance gate:** all binary criteria below must pass before sprint is declared done.

---

## A. Backend automated test suite

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
  -q
```

**Acceptance:** `66 passed` (41 baseline + 25 new). No regression in the critical 41.

---

## B. /api/docs surface check

```bash
curl -s http://localhost:8001/api/openapi.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
keep=lambda p:any(k in p for k in ['cycle-assignment','submit-for-board','/ned/inbox/','/ned/assignments/','/me/submitted-briefs','/briefs/{brief_id}/assignments'])
for p in sorted(d['paths']):
  if keep(p):
    print('  '.join(m.upper() for m in d['paths'][p] if m in ('get','post','put','delete')) + '  ' + p)
"
```

**Expected output (7 endpoints):**

```
DELETE  /api/contexts/{context_id}/cycle-assignments/{assignment_id}
POST GET  /api/contexts/{context_id}/cycles/{cycle_id}/briefs/{brief_id}/assignments
POST  /api/contexts/{context_id}/cycles/{cycle_id}/briefs/{brief_id}/submit-for-board
GET  /api/me/submitted-briefs
POST  /api/ned/assignments/{assignment_id}/accept
POST  /api/ned/assignments/{assignment_id}/decline
GET  /api/ned/inbox/assignments
```

---

## C. Hex literal sweep on Cycle surfaces

```bash
grep -nE '#[0-9a-fA-F]{3,8}\b' \
  /app/frontend/src/pages/Cycle.jsx \
  /app/frontend/src/pages/CycleSettings.jsx \
  /app/frontend/src/pages/ned/*.jsx \
  /app/frontend/src/components/cycle/*.jsx \
  | grep -v 'color:var'
```

**Acceptance:** zero output. All colour literals on Cycle / NED / cycle-component surfaces resolve through CSS variables (`var(--oxblood)`, `var(--oxblood-deep)`, `var(--ink)`, `var(--muted)`, `var(--rule)`, `var(--parchment)`, `var(--accent)`).

---

## D. Browser walkthrough — Executive submitter

Use the test credentials in `/app/memory/test_credentials.md`. The credentials below assume the dev seed; substitute as appropriate in CI.

| # | Step | Test ID anchor | Expected |
|---|---|---|---|
| 1 | Sign in as an executive owner of a team-workspace context (e.g. `juliusaopio@gmail.com`) | — | Land on `/app/home` |
| 2 | Navigate to `/app/cycle` | `cycle-stepper-strip` | 6-step stepper renders; v7 palette; staggered reveal plays first session-visit |
| 3 | Step through Agenda → Team → Contributions → Scoreboard → Follow-ups | — | Existing flow unchanged |
| 4 | Click "Compilation" step. Click "Produce draft compilation" | `cycle-compile-btn` | Compile succeeds; result block renders with sha256 + download chip |
| 5 | Scroll below the result block | `board-submit-panel-draft` | New panel: "Send this draft to the board." with oxblood submit CTA |
| 6 | Click "Submit for board reporting" | `board-submit-open-confirm` | Confirm dialog opens explaining the move to SUBMITTED |
| 7 | Click "Submit" in the dialog | `board-submit-confirm-go` | Brief moves to `submitted` board_status; assignment form revealed |
| 8 | Add a NED account id (e.g. one of Julius's NED context owner ids) and a note. Click "Assign" | `board-assign-submit` | Toast "Assigned to 1 NED(s) · 1 new". Roster row appears with `pending` badge |
| 9 | Try assigning the same NED id again | `board-assign-submit` | Toast "Assigned to 1 NED(s)" (newly == 0). No duplicate row |
| 10 | Click "Cancel" on the pending row | `roster-cancel-<id>` | Row disappears; toast "Assignment cancelled." |
| 11 | Assign two NED ids together; refresh the page | — | Roster persists; counts update |

**Acceptance:** all steps complete without errors; no console errors in DevTools; no JS exceptions.

---

## E. Browser walkthrough — NED inbox

| # | Step | Test ID anchor | Expected |
|---|---|---|---|
| 1 | Sign out, sign in as one of the NEDs assigned above | — | Land on `/app/home` (NED variant) |
| 2 | Look for the new inbox tile near top of `HomeNed` | `ned-home-inbox-tile` | Shows "Inbox · N pending" in oxblood |
| 3 | Click the tile | `ned-inbox-page` | Land on `/app/ned/inbox`. Streaming reveal plays first visit. Tabs render: Pending / Accepted / Declined |
| 4 | Open a pending card | `ned-inbox-card-<id>` | Card shows submitter display name + cycle title + note + pending badge. NO agenda fields, NO contribution fields, NO scoring data |
| 5 | Click "Accept" | `ned-inbox-accept-<id>` | Toast "Accepted. The brief is now in your durable record." Card moves to "Accepted" tab |
| 6 | Open another pending card; click "Decline" | `ned-inbox-decline-<id>` | Dialog opens. Type a reason. Click Decline. |
| 7 | Confirm card moves to "Declined" tab | `ned-inbox-tab-declined` | Card shown there with declined badge |
| 8 | Try `/api/ned/assignments/<another-neds-assignment>/accept` via curl with this NED's token | — | 404 (assignment scoping by ned_id) |

**Acceptance:** all steps complete; data-testids resolve; no Exec-internal field surfaces in any inbox card.

---

## F. Privacy-wall negative-test enforcement

`/app/backend/tests/test_cycle_assignment_privacy_wall.py` has three tests:

1. `test_ned_inbox_strips_polluted_assignment_fields` — even a deliberately polluted `cycle_assignments` row never surfaces forbidden keys / sentinel values through the NED inbox API.
2. `test_accept_writes_minimal_ned_packs_row` — `ned_packs` row schema is locked to `{id, ned_id, assignment_id, brief_id, submitter_display_name, cycle_title, received_at}`.
3. `test_accept_never_reads_exec_internal_collections` — the accept code path is monkey-patched to fail loudly if it touches `cycle_agendas` / `cycle_contributions` / `cycle_team` / `cycle_followups`.

All three pass: **3 / 3 green**.

---

## G. Permissions matrix verification

Run from inside `/app/backend`:

```python
python3 -c "
import asyncio
from services.cycle_permissions import can_submit_for_board

async def go():
    # individual workspace, owner
    ok = await can_submit_for_board(
        account={'id':'a'},
        context={'id':'c1','type':'executive_personal','owner_account_id':'a'},
        membership={'role':'executive','sub_role':'admin'},
    )
    assert ok
    # individual workspace, non-owner admin → still refused
    ok = await can_submit_for_board(
        account={'id':'b'},
        context={'id':'c1','type':'executive_personal','owner_account_id':'a'},
        membership={'role':'executive','sub_role':'admin'},
    )
    assert not ok
    # ned context → never permitted
    ok = await can_submit_for_board(
        account={'id':'a'},
        context={'id':'c1','type':'ned_personal','owner_account_id':'a'},
        membership={'role':'ned'},
    )
    assert not ok
    print('OK')
asyncio.run(go())
"
```

**Acceptance:** prints `OK`. (Team-workspace permutations covered by `test_cycle_assignment_handoff.py`.)

---

## H. Audit log integrity

After completing walkthroughs D + E, the audit log should carry these actions in order:

```
cycle.brief.submit_for_board       (submitter)
cycle.brief.assigned               (one row per NED)
cycle.brief.assignment_cancelled   (if a row was cancelled)
cycle.brief.assignment_accepted    (per accept)
cycle.brief.assignment_declined    (per decline)
```

```bash
mongo $MONGO_URL/$DB_NAME --eval '
db.audit_log.find({action: {$regex: "^cycle.brief"}}, {_id:0, action:1, metadata:1}).sort({created_at: -1}).limit(20).pretty()
'
```

**Acceptance:** the chain reflects the operations performed; `metadata.permission_reason` is populated on submit rows.

---

## I. Brief board_status lifecycle

After accepting the first assignment, the brief in `db.work_studio_briefs` should carry `board_status = "shipped"`:

```javascript
db.work_studio_briefs.find({"id": "<brief_id>"}, {_id:0, board_status:1, submitted_at:1, submitter_account_id:1})
```

---

## J. Resend MOCKED-IN-DEV marker

Verify the assignment notification call site is wired but does NOT send real email in dev:

```bash
grep -n 'MOCKED IN DEV\|notify_ned_assignment_stub' \
  /app/backend/routers/cycle_assignments.py \
  /app/backend/email_service.py
```

**Expected:** 4 hits showing `# MOCKED IN DEV` annotations and the stub function. Backend log on a real assign should contain `ned_assignment_notification.MOCKED ...`.

---

## K. PRODUCT_SPEC §5.6 reconciliation marker

`routers/ned/__init__.py` exists and documents the keep-code decision:

```bash
head -25 /app/backend/routers/ned/__init__.py
```

---

## Files touched in this sprint

### Backend (new)
- `/app/backend/services/cycle_permissions.py`
- `/app/backend/routers/cycle_assignments.py`
- `/app/backend/routers/ned/__init__.py`
- `/app/backend/tests/test_cycle_assignment_handoff.py`
- `/app/backend/tests/test_cycle_assignment_privacy_wall.py`

### Backend (edited)
- `/app/backend/server.py` — register router + indexes
- `/app/backend/email_service.py` — `notify_ned_assignment_stub`
- `/app/backend/routers/cycle_manager.py` — expose `cycle_id` / `agenda_id` / `board_status` on compile response

### Frontend (new)
- `/app/frontend/src/pages/ned/NedInbox.jsx`
- `/app/frontend/src/components/cycle/CycleStatusBadge.jsx`
- `/app/frontend/src/components/cycle/BoardSubmitPanel.jsx`
- `/app/frontend/src/components/cycle/NedInboxTile.jsx`

### Frontend (edited)
- `/app/frontend/src/App.js` — route `/app/ned/inbox`
- `/app/frontend/src/pages/Cycle.jsx` — hex-literal sweep + BoardSubmitPanel hookup
- `/app/frontend/src/pages/ned/NedMeeting.jsx` — hex-literal sweep
- `/app/frontend/src/pages/home/HomeNed.jsx` — NedInboxTile
- `/app/frontend/src/components/transitions/WorkspaceEntryScene.jsx` — `ned_inbox` workspace lines

### Documentation
- `/app/memory/sprints/CYCLE_MANAGER_BRIEF.md` — marked APPROVED-FOR-BUILD, locked C3 decision
- `/app/memory/sprints/CYCLE_MANAGER_VERIFY.md` — this document
