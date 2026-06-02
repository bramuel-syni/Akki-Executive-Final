# C1-revised — Phase A + Phase B combined dispatch
**Date:** 2026-02 (sprint)
**Scope:** P0 from QA sweep — First-login password set + Task-
contribution magic-link error clarity.
**Author:** main agent (autonomous on user choice (c) + (ii))

---

## Honesty Protocol — what shipped vs. what was claimed

**Phase A — First-login password set (NEW behaviour):**
- New `accounts.has_set_password` field (boolean, optional).
- New middleware `services/first_login_password_set.py` that blocks
  POST/PUT/PATCH/DELETE for accounts with strict-bool false. Legacy
  `null | missing | true` all bypass.
- New `POST /api/auth/set-password` endpoint (authenticated, CSRF-
  gated) that flips the flag + sets the hash + refreshes
  `last_activity_at`.
- New SPA page `/auth/set-password` + `SetPasswordGuard` wrapping
  `<Gated>` before `<FirstSessionGuard>`.
- Five entry paths now write the flag:
  | Path | Writes |
  |------|--------|
  | `POST /api/auth/register` | `True` |
  | `POST /api/auth/magic-link/consume` mode=password | `True` |
  | `GET /api/auth/magic/{token}` (direct cohort consume) | `False` |
  | `GET /api/auth/oauth/google/finish` (NEW account) | `False` |
  | `GET /api/auth/oauth/microsoft/finish` (NEW account) | `False` |
- Sanitize_account surfaces the field ONLY for strict True/False
  (legacy missing stays lean — no field on the wire).

**Phase B — Contribution magic link error clarity (REFACTOR, not
fix):**
- The happy-path verifier ALREADY worked end-to-end pre-Phase B.
  Verified via live preview: fresh task creation + token mint +
  `GET /api/tasks/contribute/{token}` → HTTP 200 with full payload.
- The user-perceived "magic link invalid" mapped to three
  indistinguishable 404 paths surfacing as a catch-all "Link not
  valid" narrative:
  1. Token rotated by a re-invite (`used=True` +
     `revoked_reason="rotated_on_reinvite"`).
  2. Token still valid but the referenced task was deleted.
  3. Token + task valid but the contributor was removed from the
     team.
- Phase B distinguishes 6 negative codes + the 200 happy path:
  - `404 link_invalid` — token never existed.
  - `410 link_revoked` — rotated.
  - `410 link_used`    — submitted (no rotation reason).
  - `410 link_expired` — past `expires_at`.
  - `410 task_gone`    — task deleted.
  - `410 not_on_team`  — contributor removed.
- Frontend reads `r.json().detail.code` and renders one of seven
  narratives. `data-error-code` attribute on the error surface
  pins the active narrative for Playwright.

**What I did NOT touch (no scope creep):**
- The token mint code, the email send shape, the SendGrid wire,
  the contributor portal happy-path form, the email body copy, or
  the existing reset-password / magic-link routes.
- The cross-test fixture leak (`Future attached to a different
  loop`) — explicitly left logged per your earlier instruction.

---

## No silent deviations

**Two pre-existing P4 test failures** surfaced when I ran the broad
sweep. They predate C1-revised. Confirmed via `git stash` →
re-run failing → `git stash pop`:

```
FAILED tests/test_phase_p4_cohort_funnel.py::test_p4_a_receipt_flag_off_logs_redacted
FAILED tests/test_phase_p4_cohort_funnel.py::test_p4_b_decline_writes_audit_and_skips_email_when_flag_off
```

Root cause: P1-B set `COHORT_EMAILS_ENABLED=true` in
`backend/.env`. The two failing tests were written when the env
defaulted to `false`, asserting status `flag_off`. With the env on,
the path advances to `_send_via_sendgrid`, which short-circuits on
`COHORT_NOTIFY_DISABLED=true` (set by conftest) and returns
`test_mode_disabled` instead. Both shapes are still safe — no real
SendGrid call is made under pytest — but the legacy assertion
disagrees.

**I did NOT touch these tests** (out of scope for C1-revised). Two
clean options for next dispatch:
1. Update `conftest.py` to also set `COHORT_EMAILS_ENABLED=false`
   so legacy tests pass under both env shapes.
2. Update the two failing tests to assert
   `test_mode_disabled`+`flag_off` (any safe terminal status).

Surfacing here; no silent fix applied.

---

## Lockdown tests

`backend/tests/test_c1_a_first_login_password_set.py` — 16 tests
covering source-strict wire-up + middleware behaviour at every
flag shape + the new endpoint's flip + idempotency + register-path
default + sanitize_account lean response.

`backend/tests/test_c1_b_contributor_link_codes.py` — 10 tests
covering each of the 6 negative codes + happy-path regression +
cross-tenant isolation guard (token A's email cannot leak task B's
data).

Plus the two raw Playwright traces under `/tmp` (NO generic testing
subagents):
- `/tmp/c1a_set_password_trace.py` — 4 viewports × 6 step
  assertions = **24/24 PASS**.
- `/tmp/c1b_contribution_trace.py` — 4 viewports × 7 scenarios =
  **28/28 PASS**.

Voice-lint: **clean across customer-copy surfaces.**
Solva v1 byte-identical guard: **4 passed.**

---

## Verbatim sweep summary

```
139 passed, 2 deselected, 22 warnings in 238.15s (0:03:58)
```

Active bundle (15 files):
- test_solva_v1_unchanged
- test_admin_qa_hooks
- test_p0_c_oauth_session_ingestion
- test_p1_a_intel_to_pulse
- test_p1_b_cohort_approval_email
- test_phase_r1_cohort_foundation
- test_phase_p4_cohort_funnel (2 pre-existing failures deselected;
  see "No silent deviations")
- test_phase_p5_5_session_reauth
- test_phase_s_password_reset
- test_home_cleanup_phase_f5
- **test_c1_a_first_login_password_set** (NEW, 16 tests)
- **test_c1_b_contributor_link_codes** (NEW, 10 tests)
- test_phase_r2_welcome_email
- test_phase_p3_1_csrf
- test_phase_p5_6_csrf_cookie_domain

### Suite-size delta vs. prior baseline
Prior baseline (handoff): **~64 passing tests** for the active
sweep bundle.
This dispatch: **139 passing tests** for an expanded active sweep
bundle. Net new from C1-revised: **+26 tests** (16 Phase A + 10
Phase B). The remaining +49 are due to broader file inclusion in
this sweep (P4 cohort funnel, P5.5 session re-auth, password
reset, R1 cohort foundation, R2 welcome email, P3.1/P5.6 CSRF, F.5
home cleanup, P0-C OAuth, P1-A intel→pulse, P1-B cohort approval,
admin QA hooks, Solva v1 unchanged) — files that were ALREADY
green at the time of fork but weren't in the prior baseline's
"active sweep" tag.

---

## Files touched

### Backend
| File | Change |
|------|--------|
| `backend/services/first_login_password_set.py` | NEW — middleware |
| `backend/server.py` | wire middleware after SessionTimeout |
| `backend/core.py` | sanitize_account surfaces `has_set_password` for strict True/False only |
| `backend/routers/auth.py` | `POST /auth/set-password` + register sets flag True |
| `backend/routers/auth_magic.py` | direct magic consume writes `has_set_password=False` |
| `backend/routers/cohort_magic_link.py` | consume writes flag True/False per mode |
| `backend/routers/auth_oauth.py` | Google + Microsoft NEW-account writes flag False |
| `backend/routers/tasks.py` | `_resolve_contributor_token` + `contributor_view` return structured `{code, message}` per failure mode |

### Frontend
| File | Change |
|------|--------|
| `frontend/src/pages/SetPasswordRequired.jsx` | NEW — first-login set page |
| `frontend/src/pages/ContributorPortal.jsx` | reads `detail.code`, renders 7 narratives, sets `data-error-code` |
| `frontend/src/App.js` | `SetPasswordGuard` wraps `<Gated>` before `<FirstSessionGuard>`; `/auth/set-password` route registered |

### Tests + memory
| File | Change |
|------|--------|
| `backend/tests/test_c1_a_first_login_password_set.py` | NEW — 16 tests |
| `backend/tests/test_c1_b_contributor_link_codes.py` | NEW — 10 tests |
| `/app/memory/auth_testing.md` | new sections 12 + 13 documenting both phases |
| `/app/memory/test_credentials.md` | C1-revised Phase A + B repro recipes |
| `/tmp/c1a_set_password_trace.py` | NEW — raw Playwright trace |
| `/tmp/c1b_contribution_trace.py` | NEW — raw Playwright trace |

---

## Production env actions (none required)

Phase A + Phase B add no new env vars EXCEPT one optional escape
hatch (incident-only):

```
FIRST_LOGIN_PASSWORD_GATE_DISABLED=1
```

Default: not set → gate is enabled. Set to `1` to disable entirely
(matches the shape of `CSRF_TEST_BYPASS_HEADER` and
`RATE_LIMIT_DISABLED`). The conftest.py for the test suite does NOT
set this — every gate test runs against the live middleware.

---

## Resume contract

C1-revised closed clean. Pause for e1_tester re-verification before
the next phase per protocol. Remaining open backlog (unchanged):
- 🟡 P8 Trust Loop SendGrid Inbound Parse webhook — BLOCKED on user
- 🟢 "Questions for you" page work (deprioritized per user)
- 🟢 P5.18 OAuth migration — BLOCKED on GCP creds
- 🟢 Task Manager bug 27 / Fig 42 — Email Reply mode plumbing
- 🔵 Future / backlog low (digest cadence, why-not-shown diff,
     re-target badge, Postmark history scrub deferred)
