# J1 Preserved State (reverted 2026-05-24)

J1 onboarding work was reverted before T1-T5 began — the UI it would
describe is being reshaped, so the banner + tooltips + intro card
copy would all need rewriting after T1-T5 anyway. Saving the diff
here for clean restoration after T5 ships.

## Files reverted

| Path | State | How |
|---|---|---|
| `backend/routers/onboarding_status.py` | DELETED | `rm` (file was NEW in the J1 commit) |
| `backend/tests/test_j1_onboarding.py` | DELETED | `rm` (NEW) |
| `backend/server.py` | restored to `074a79c` | `git checkout 074a79c -- backend/server.py` |
| `frontend/src/App.js` | restored to `074a79c` | `git checkout 074a79c -- frontend/src/App.js` |
| `frontend/src/components/layout/AppShell.jsx` | restored to `074a79c` | `git checkout 074a79c -- frontend/src/components/layout/AppShell.jsx` |
| `frontend/src/pages/TrustCenter.jsx` | restored to `074a79c` | `git checkout 074a79c -- frontend/src/pages/TrustCenter.jsx` |

## Files NOT reverted (intentional)

| Path | Why kept |
|---|---|
| `.dockerignore` | Deploy hygiene fix from the same commit. Removing the `.env` ignore stanzas protects against the prod-502 outage class we already hit once. NOT a J1 onboarding artefact — it's an Emergent-deploy invariant. Surface this to user during T5 closeout if they want it touched. |
| `memory/sprints/READ_FIRST.md` | Documentation only — was written PRIOR to J1 anyway. |
| `memory/sprints/ONBOARDING_INVENTORY.md` | Read-only inventory — useful reference for the J1 restoration brief. |

## Full diff of the reverted work

The complete unified diff (684 insertions, 17 deletions across 7 files
in commit `b48ee23`) is preserved at `/tmp/j1_full_diff.patch` AND
viewable in git history forever via:

```bash
git show b48ee23 --
```

## Schema/data migrations introduced by J1 (preserve for restoration)

When J1 is restored after T5, the following user-doc fields will be
re-added to `db.accounts.*`:

| Field | Type | Set by | Purpose |
|---|---|---|---|
| `shield_v1_intro_acknowledged_at` | ISO 8601 string | `POST /api/users/me/onboarding-status/acknowledge` | One-time lock — never re-show the banner |
| `shield_v1_intro_dismissals_count` | int (0-3) | `POST .../dismiss` | Caps at MAX_DISMISSALS=3 |
| `shield_v1_intro_last_dismissed_at` | ISO 8601 string | Same | Most recent dismissal timestamp |
| `trust_center_tooltip_dismissed_at` | ISO 8601 string | `POST .../tooltips/trust-center/dismiss` | One-shot |
| `help_tooltip_dismissed_at` | ISO 8601 string | `POST .../tooltips/help/dismiss` | One-shot |

**Production impact**: NONE. These fields don't exist on any prod user
account today (J1 was reverted before any prod write). When J1 is
restored post-T5, all existing users will simply start with the
default `false`-equivalent state for these fields and the banner /
tooltips will surface for grandfathered users on next login.

## Endpoint additions (preserve for restoration)

The J1 commit added one new router module wired into `server.py`:

```
POST   /api/users/me/onboarding-status                 — GET (auth-required, returns status payload)
POST   /api/users/me/onboarding-status/dismiss         — increment counter, returns updated state
POST   /api/users/me/onboarding-status/acknowledge     — permanent lock, returns updated state
POST   /api/users/me/onboarding-status/tooltips/trust-center/dismiss — one-shot
POST   /api/users/me/onboarding-status/tooltips/help/dismiss          — one-shot
```

The route module read the `SHIELD_V1_DEPLOY_TIMESTAMP` cutoff from
`routers.synisense_metrics` (env-overridable single source of truth)
— so restoration must verify that the import target still exists +
exports `_shield_v1_cutoff()` and `_SHIELD_V1_DEPLOY_TIMESTAMP_STR`.

## Test coverage at the moment of revert

`backend/tests/test_j1_onboarding.py` — 9 tests, all WIRE-LEVEL with
positive content assertions:
1. grandfathered user → needs_reintro:true + reason set
2. brand-new user (zero chats) → needs_reintro:false
3. acknowledge endpoint → permanent lock + tc tooltip also dismissed
4. dismiss endpoint → counter increments
5. three dismissals → max_dismissals_reached
6. acknowledge writes the timestamp to Mongo + response matches
7. /trust-center alias route declared in App.js (verified by source-read)
8. trust-center tooltip dismiss endpoint
9. help tooltip dismiss endpoint

The tests were NEVER run pre-revert because the revert was authorised
mid-build. Re-running them is part of the J1 restoration acceptance.

## Restoration recipe (one-liner)

```bash
cd /app && git cherry-pick b48ee23 && sudo supervisorctl restart backend
```

If a merge conflict arises post-T5 (likely on `AppShell.jsx` and
`TrustCenter.jsx`, both touched by T1-T5), resolve by re-applying the
five surgical edits the J1 diff makes to those files, NOT by accepting
the b48ee23 verbatim. The five edits are well-isolated:

1. **`AppShell.jsx`** — add `BookOpen` to the lucide-react import (~1 line)
2. **`AppShell.jsx`** — add `onbStatus` hook + `postOnb` helper after the `mobileNavOpen` state (~40 lines)
3. **`AppShell.jsx`** — re-intro banner JSX above the M.4 comment block (~30 lines)
4. **`AppShell.jsx`** — wrap Trust Center button in a `relative` div + add tooltip JSX; add Help button + its tooltip JSX after Trust Center (~70 lines)
5. **`TrustCenter.jsx`** — add `showIntroCard` / `acknowledgeIntro` state + intro card JSX after header (~50 lines)
6. **`App.js`** — alias route `/trust-center` → `/app/trust-center` (~6 lines)
7. **`server.py`** — import + include the new router (~2 lines)

## Post-revert state verification

```bash
# All J1 markers gone from live code:
$ grep -rn "onboarding-status\|shield_v1_intro\|trust-center-tooltip" \
    backend/routers backend/server.py frontend/src/
(empty)

# Backend boots clean:
$ curl -s -o /dev/null -w "%{http_code}" $REACT_APP_BACKEND_URL/api/healthz/shield
200

# Frontend serves:
$ curl -s -o /dev/null -w "%{http_code}" $REACT_APP_BACKEND_URL/signin
200
```

✅ **Reverted. Clean. Ready for T1.**
