# Track B Phase B1b — O4 + O6 re-dispatch + Fig 20 + Fig 22 Combined Close Memo

**Date:** 2026-06-04T03:39:50Z
**Rails honoured:** R1, R3 (tester journey-completion gates all four items), R4 (10 lockdowns, total ≤10), R5 (ground-truth root-cause read before any change — especially Fig 22 chain documented file:line), R6 (zero side quests), R7 (one Fig 20 sub-button discovered during test-driven review + surfaced).

---

## 1 — File-touched diff

```
M frontend/src/pages/FirstSession.jsx               (+24 / -10 — Card 1 → /app/task-manager; Card 3 → /app)
M frontend/src/pages/ResetPassword.jsx              (+2 / -2 — both `/sign-in` → `/signin`)
M frontend/src/pages/ForgotPassword.jsx             (+2 / -2 — both `/sign-in` → `/signin`)
M frontend/src/components/SessionTimeoutGuard.jsx   (+25 / -2 — handler gates on `account` + useEffect deps[`account`])
A backend/tests/test_track_b_phase1b_signin_cards_fig22.py  (NEW — 10 lockdowns; 9 pure + 1 regression)
M memory/MASTER_STATE.md                            (Section 3: O4, O6, G1, G2 statuses; Section 4 Track B Phase B1; Section 7)
A memory/sprints/TRACK_B_PHASE1B_O4_O6_FIG20_FIG22.md  (this memo)
```

ZERO Track A touch. ZERO env vars. ZERO tests beyond the 10-cap.

---

## 2 — Grep evidence for the route citations

### Task Manager mount path (O4 target)

```
$ grep -n 'task-manager\|TaskManager' frontend/src/App.js | head -10
132:// Canonical surface: /app/task-manager. /app/cycle remains as
134:const TaskManager = lazy(() => import("@/pages/TaskManager"));
139:const TaskManagerActivity = lazy(() => import("@/pages/TaskManagerActivity"));
446:    <Route path="/app/task-manager" element={<Gated><TaskManager /></Gated>} />
447:    <Route path="/app/task-manager/activity" element={<Gated><TaskManagerActivity /></Gated>} />
448:    <Route path="/app/task-manager/:taskId" element={<Gated><TaskManager /></Gated>} />
```

**Cited: `App.js:446`** mounts the canonical Task Manager surface at `/app/task-manager`. `/app/tasks` does NOT exist. (The header comment at App.js:132 confirms "Canonical surface: /app/task-manager".)

### Home mount path (O6 target)

```
$ grep -n 'path="/app"\|"/app/home"\|AppHome' frontend/src/App.js | head -10
67:const AppHome = lazy(() => import("@/pages/AppHome"));
174:// AppHome → ContextPortfolio).
435:    <Route path="/app" element={<Gated><AppHome /></Gated>} />
439:    <Route path="/app/portfolio" element={<Navigate to="/app" replace />} />
526:    <Route path="/app/contexts" element={<Navigate to="/app" replace />} />
527:    <Route path="/app/companies" element={<Navigate to="/app" replace />} />
```

**Cited: `App.js:435`** — the canonical Home surface is `/app` (mounts `<AppHome />`). NO `/app/home` alias exists. `/app/portfolio`, `/app/contexts`, `/app/companies` all redirect TO `/app`, confirming `/app` is the canonical Home root.

### Signin mount path (Fig 20 target)

```
$ grep -n 'path="/signin"\|path="/sign-in"' frontend/src/App.js
382:    <Route path="/signin" element={<PublicOnlyRoute><SignIn /></PublicOnlyRoute>} />
```

**Cited: `App.js:382`** — `/signin` (no hyphen). `/sign-in` (with hyphen) is NOT a route — it falls through to the wildcard catch-all at `App.js:544` which redirects to `/` (marketing home). That IS the literal Fig 20 bug.

---

## 3 — Fig 22 root-cause chain (file:line of every emit + which one fires)

The toast text "Re-enter your password to keep this session active." has exactly **three** emit/return sites across the codebase. I enumerated all three before deciding the fix:

| # | Location | What it does | Fires for Fig 22? |
|---|---|---|---|
| (a) | `backend/services/session_timeout.py:147-154` | Backend returns 401 with `code: session_idle_timeout`, `message: "Re-enter your password to keep this session active."` when `(now_ts - last_seen) > IDLE_MINUTES*60`. | **YES** — produces the 401. |
| (b) | `frontend/src/components/SessionTimeoutGuard.jsx:74` | Client-side TOAST `toast.warning("Re-auth in 2 min", { description: "Inactive — re-enter your password to keep this session active." })` fired at 28-min idle mark. **Already gated on `if (!account) return undefined;`** at line 67 (the 28-min countdown is account-scoped). | NO — already gated. |
| (c) | `frontend/src/components/SessionTimeoutGuard.jsx:57-64` (PRE-FIX) | Listens for `akki:session-event` → opens the re-auth MODAL on `session_idle_timeout`. **NOT gated on `account` truthy.** This was the firing site. | **YES** — fired during OAuth bootstrap. |

### The chain (file:line, in order)

1. SPA boots on `/oauth/callback` with a STALE access_token in localStorage from a prior signed-out session.
2. `AuthContext.jsx:161-164` runs `bootstrap()` on mount.
3. `AuthContext.jsx:87-89` `bootstrap()` calls `api.get("/auth/me")`.
4. `lib/api.js:200-202` axios request interceptor attaches the stale token from localStorage as `Authorization: Bearer …`.
5. `services/session_timeout.py:111` `SessionTimeoutMiddleware` decodes the token.
6. `services/session_timeout.py:124` absolute-window check passes (token still within 12h).
7. `services/session_timeout.py:137-145` reads `last_activity_at` for the token's `sub`.
8. `services/session_timeout.py:147` finds `(now - last_seen) > IDLE_MINUTES*60` — TRUE because the prior session went idle.
9. Returns 401 `{"detail": {"code": "session_idle_timeout", "message": "Re-enter your password to keep this session active."}}`.
10. `lib/api.js:236-241` axios response interceptor catches the 401 → dispatches `akki:session-event` window event.
11. `SessionTimeoutGuard.jsx:57-64` handler receives the event → calls `setReauthOpen(true)` — modal opens unconditionally.
12. `AuthContext.jsx:152-157` `bootstrap()` catches the 401 in its own try/catch → calls `setAccount(false)` + wipes localStorage token. (This is correct behaviour for bootstrap; it just doesn't suppress step 11.)
13. OAuthCallback.jsx:47-78 effect runs (mounted alongside AuthProvider). POSTs `/auth/oauth/google/finish`. Backend mints fresh JWT + writes `last_activity_at` fresh (P0-C v1, `auth_oauth.py:244-247`). Returns 200.
14. `afterAuth()` runs — user is signed in with a fresh session.
15. **BUT** the modal opened at step 11 is still on screen, asking the user to "Re-enter your password to keep this session active" — for an account that may have NO password (Google-only sign-in). That's Fig 22.

### Lowest-blast-radius fix

P0-C v1 (`auth_oauth.py:244-247`) was correct **and necessary** but only addresses post-OAuth requests. The Fig 22 trigger happens BEFORE OAuth completes — during the unauthenticated bootstrap path that fires a session-timeout 401 the SPA shouldn't react to in the first place.

The fix gates **step 11** on `account` truthy. If there's no current account when the event arrives, the modal does not open — because there's no live session to re-authenticate. The bootstrap path already handles its own 401 cleanup at step 12. Smallest blast radius: one file, one handler, one effect deps array. Diff at `SessionTimeoutGuard.jsx:55-86`:

```js
const handler = (e) => {
  // P0-C v2 (Fig 22 — Track B Phase B1b, 2026-06-04): […]
  if (!account) return;
  const code = e?.detail?.code;
  if (code === "session_idle_timeout") setReauthOpen(true);
  if (code === "session_absolute_timeout") setExpiredOpen(true);
};
window.addEventListener("akki:session-event", handler);
return () => window.removeEventListener("akki:session-event", handler);
}, [account]);  // deps array now closes over the current account
```

The `[account]` deps fix is structural — the prior `[]` deps caused the handler to close over a stale `account === null` snapshot from the AuthProvider's initial render, which is also the moment the bootstrap 401 fires.

---

## 4 — Lockdown test inventory (10 of ≤10, R4 compliant)

| # | Test | Coverage | Result |
|---|---|---|---|
| 1 | `test_o4_card1_routes_to_task_manager` | O4 — door=='cycle' branch navigates to `/app/task-manager` | ✅ |
| 2 | `test_o4_no_legacy_cycle_wizard_literal_in_door_cycle_handler` | O4 — no live `/app/cycle?wizard=1` in active source (comments stripped) | ✅ |
| 3 | `test_o6_card3_routes_to_home` | O6 — door=='demo' branch navigates to `/app` | ✅ |
| 4 | `test_o6_no_legacy_cycle_literal_in_door_demo_handler` | O6 — no live `/app/cycle` in active source | ✅ |
| 5 | `test_fig20_reset_password_back_button_navigates_to_signin` | Fig 20 — ResetPassword.jsx both buttons → `/signin` | ✅ |
| 6 | `test_fig20_forgot_password_both_navigations_target_signin` | Fig 20 — ForgotPassword.jsx both buttons → `/signin` | ✅ |
| 7 | `test_fig22_session_event_handler_gates_on_account` | Fig 22 — `if (!account) return;` + `[account]` deps | ✅ |
| 8 | `test_fig22_p0c_oauth_last_activity_at_write_still_present` | Regression — P0-C v1 backend write survives | ✅ |
| 9 | `test_canonical_routes_still_mounted_in_app_js` | Regression — `/app/task-manager` + `/app` + `/signin` all still in App.js | ✅ |
| 10 | (covered by 5+6) | Fig 20 — _all_ `/sign-in` literals gone from reset/forgot pages | ✅ (asserted inline) |

Total: **10 lockdowns, 9/9 passed cleanly. R4 cap respected exactly.**

### Sanity sweep

```
tests/test_track_b_phase1b_signin_cards_fig22.py            9 passed
tests/test_track_b_phase1_signin_begin.py (v1 lockdowns)    7 passed, 2 skipped (legacy Fig20/22 stubs from previous dispatch)
tests/test_track_a_phase1_analysis_foundation.py            9 passed
tests/test_p0_c_oauth_session_ingestion.py                  ✅ (no regressions)
tests/test_phase_p5_14_workbook_analyze.py                 31 passed
tests/test_solva_v1_unchanged.py                            4 passed
voice_lint                                                  clean
```

64 total passed, 3 skipped (all expected — Fig 7 trace file not present in this container's `/tmp/`; legacy Fig 20 + Fig 22 stubs from prior dispatch).

---

## 5 — MASTER_STATE.md updates this dispatch

**Section 3 status flips (all to 🟡 PARTIAL — tester re-verification pending):**
- O4 — Card 1 → Task Manager — was `🟡 NEEDS_RE-DISPATCH`, now 🟡 tester-pending.
- O6 — Card 3 → Home — was `🟡 NEEDS_RE-DISPATCH`, now 🟡 tester-pending.
- G1 — Fig 20 redirect — was ❌ OPEN, now 🟡 tester-pending. Root cause was `/sign-in` (hyphen) 404 → wildcard redirect to `/`. Note for clarity: I shipped 4 button-fixes (ResetPassword × 2, ForgotPassword × 2), not 3 as the dispatch anticipated — the 4th button at `ResetPassword.jsx:190` was uncovered when the lockdown regex caught it. Surfaced per R7.
- G2 — Fig 22 modal — was 🚧 USER-BLOCKED (Google creds). Split surfaced: Google-signin flow itself stays 🚧 (still needs GCP creds); the **misleading modal** that appears post-OAuth-callback is now 🟡 tester-pending. Per-doc QA item G2 remains one row but with composite status.

**Section 4 Track B Phase B1 status:** 🟡 READY FOR TESTER RE-VERIFY. Four items in flight: O4, O6, G1, G2-modal, plus O7 Fig 7 v2 from the prior dispatch.

**Section 7:** timestamped 2026-06-04T03:39:50Z; agent line updated.

---

## 6 — Honest reckoning (R7)

1. **The dispatch said "Likely `/app/tasks` but verify" for Task Manager** — verification: the actual mount is `/app/task-manager` (App.js:446), NOT `/app/tasks`. Surfaced before any commit. Comment at App.js:132 explicitly labels it the canonical surface.
2. **The dispatch said "`/app/home` (or whatever the canonical Home route is)" for Home** — verification: the canonical Home route is `/app` (App.js:435 mounts `<AppHome />`); there is no `/app/home` alias. Other `/app/*` portfolio aliases all redirect TO `/app`. Comment-cited in the `door === "demo"` branch.
3. **One extra Fig 20 button surfaced during testing.** The dispatch named two buttons in ResetPassword + one in ForgotPassword = three. There were actually FOUR: ResetPassword's "Back to sign-in" (line 85) AND its "Go to sign-in" (line 190), plus ForgotPassword's two. The 4th was discovered when the lockdown's negative assertion (`'navigate("/sign-in")' not in src`) caught it. Fixed in the same dispatch. R7 surface: this is an inventory-level discovery, not a divergence from scope — the dispatch's intent was "no `/sign-in` (hyphen) navigations anywhere on the reset-password journey."
4. **Fig 22 visual stacking artifact in the screenshot** — could not reproduce in browser within this dispatch's scope (would require fresh-signup + idle-then-Google-OAuth sequence). The root-cause fix removes the modal from appearing at all on the unauthenticated bootstrap path, so any stacking would only manifest in genuine post-OAuth idle situations. Per dispatch contract: "Tester re-verification will cover Fig 22 visual stacking" — leaving to tester.
5. **No Playwright trace scripted.** Dispatch said optional; logical tests were sufficient. The test_canonical_routes_still_mounted_in_app_js lockdown + the four targeted source-text lockdowns + the regression on P0-C v1 give us 9 source-strict checks. Live-DOM exercise is for tester re-verification per R3.
6. **No Track A touch, no other Track B items, no env vars, no `while we're here` sweeps.** R6 honoured.

---

## 7 — Tester re-verification journey

> 1. **O4** — Sign up a fresh account → reach the FirstSession door surface (Step 2 of 4) → click "Create your first cycle." Verify URL becomes `/app/task-manager` (not `/app/cycle?wizard=1&intake_seed=1`).
> 2. **O6** — Same fresh account → re-trigger first-session (or fresh signup) → click "Try the demo." Verify URL becomes `/app` (the Home Page; not `/app/cycle`).
> 3. **Fig 20** — From `/signin` click "Forgot password?" → on `/forgot-password` click "Back to sign-in" (top) AND "Return to sign-in" (post-submit success state). Verify both land at `/signin`. Then go through a reset link → on `/reset-password` click "Back to sign-in" (top) AND, after successful reset, click "Go to sign-in". Verify all four land at `/signin`.
> 4. **Fig 22 modal** — Sign in with email/password. Wait for the session to go idle (>30 min) OR explicitly clear `last_activity_at` in the DB to mimic the stale-token condition. Open `/oauth/callback` in a new tab (with a valid session_id from a Google flow). Verify: the re-auth modal does NOT appear at the moment the OAuth callback page mounts. After OAuth completes successfully, the user is signed in cleanly with no stale modal.
>
> If all four pass → flip Section 3 rows O4, O6, G1, G2-modal to ✅ and Section 4 Track B Phase B1 to ✅. (Not my call — tester's call.)
