"""NED-side routers — design decision marker.

PRODUCT_SPEC §5.6 (HEAD) claims "the NED layer has zero code today."
That claim is OUT OF DATE. The live codebase ships:

  - `routers/ned_cycle.py` — 12 NED routes under /api/ned/* (Phase E)
  - `routers/cycle_assignments.py` — NED inbox + accept/decline endpoints
    under /api/ned/inbox/* and /api/ned/assignments/* (Cycle sprint 2026-02)
  - `frontend/src/pages/ned/NedMeeting.jsx` + `frontend/src/pages/ned/NedCommittee.jsx`

Per the Cycle Manager sprint brief
(`/app/memory/sprints/CYCLE_MANAGER_BRIEF.md` §3, decision C1):
**keep the live code, treat PRODUCT_SPEC §5.6 as out of date**.
Do NOT delete NED code in response to that spec claim.

This is a marker module only. NED-side router instances live in
`routers/ned_cycle.py` and `routers/cycle_assignments.py`. This
package is intentionally empty otherwise so existing imports don't
break.
"""
