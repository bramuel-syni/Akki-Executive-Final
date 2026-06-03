# Q4Y harness sub-dispatch — Block 1 + Block 3 + KNOWN BLOCKER surface
**Date:** 2026-02 (sprint, fork-resume)
**Scope:** Harness-only. Document active-context mechanism, confirm
seed endpoint completeness, verify tester recipe end-to-end. Then
surface a pre-existing Q4Y FE bug that blocks the UI sub-checks
even WITH a working harness.
**Author:** main agent (autonomous on user scope)

---

## Block 1 — Active-context mechanism (READ-ONLY)

**Cited ground-truth:**

| What | File:line | Behaviour |
|---|---|---|
| Storage key | `frontend/src/lib/api.js:80` | `ACTIVE_CONTEXT_STORAGE_KEY = "akki_active_context_id"` |
| Storage type | `frontend/src/lib/api.js:75-101` | `sessionStorage` (per-tab, NOT localStorage, NOT a cookie, NOT a DB record) |
| Reader on mount | `frontend/src/contexts/AuthContext.jsx:45` | `useState` initialiser calls `readActiveContextId()` |
| Wire injection | `frontend/src/lib/api.js:203-206` | axios interceptor adds `X-Active-Context: <id>` header |
| Server side | `POST /api/me/active-context` | Audit-only — does NOT mutate SPA state; sessionStorage is the single source of truth |

**Answer to the spec question:** the mechanism is **a single
sessionStorage key**. Per your hard-no — "honesty: do not invent
work" — I am **NOT** adding a `POST /api/admin/qa/set-active-context`
endpoint (Block 2 skipped).

**Documentation:** `memory/auth_testing.md` §17 was updated with
the full Playwright recipe (`addInitScript` option A + post-nav
sessionStorage option B), including the explicit warning that
the headless tester's `activeContextId` initialises to `null`
post-login (AuthContext intentionally leaves it null so AppHome
can render the context switcher), which is exactly why the prior
test run flagged HUMAN_REQUIRED on the 4 UI sub-checks.

---

## Block 3 — Seed endpoint completeness (READ-ONLY)

`POST /api/admin/qa/seed/question` already returns the full row
with `context_id` at top-level (see
`backend/routers/admin_qa_hooks.py:307-322`). **No change needed.**
The tester can chain seed → set-active-context (via Playwright
addInitScript) → navigate, all from the seed response payload.

Documented in `auth_testing.md` §17 with the verbatim chain
recipe.

---

## Harness verification trace

`/tmp/q4y_harness_verify.py` drives the recipe end-to-end and
asserts the harness mechanism is sound:

1. Seed via the QA harness → captures `qid` + `context_id` from
   the response.
2. `context.add_init_script("sessionStorage.setItem('akki_active_context_id', <ctx_id>)")`.
3. Log in as admin → confirm sessionStorage carries the primed
   value on the first SPA render.
4. From the page's authenticated context, `fetch('/api/me/questions?q=<token>')`
   returns HTTP 200 with `total: 1` and the seeded row.

**Result:** 4 viewports × 3 steps = **12/12 PASS**.

---

## ⚠️ Critical divergence surfaced — pre-existing Q4Y FE bug

**No-Silent-Deviations applies.** While verifying the harness
end-to-end, the trace discovered that even with sessionStorage
correctly primed and the API returning the row, the `/app/questions`
page renders the empty state. Root cause is NOT in the harness.

### Evidence (verbatim Playwright network log)

```
SPA's actual network request:
GET /api/api/me/questions?status=open&page=1&page_size=10&sort=recent&q=PROBE-7e0066
→ HTTP 404

Probe via raw fetch (same page context, same cookies):
GET /api/me/questions?q=PROBE-7e0066&status=all
→ HTTP 200 {total: 1, items: [...]}
```

### Cause

`frontend/src/pages/Questions.jsx:456`:
```jsx
const r = await api.get("/api/me/questions", { params: {...} });
```

The axios client `api` has `baseURL = "/api"` (see
`frontend/src/lib/api.js:45-49`). Axios prepends baseURL to any
URL that doesn't have a protocol. Result: actual request URL is
`/api` + `/api/me/questions` = `/api/api/me/questions` → 404.

The page's `catch` block at `Questions.jsx:481-483` swallows the
error, calls `setItems([])` + `setTotal(0)`, and the
`ListingShell` renders the empty state.

### Blame

```
c0feb6790  (2026-05-12 09:14:23 +0200 456) const r = await api.get("/api/me/questions", {
```

Predates this entire fork. Patch 14 (the page's original
implementation). The cycle-scoped sibling call on line 446 uses
the correct bare-path form (`/contexts/{cid}/cycles/{cid}/questions`)
— this single line is the outlier.

### Why prior 7/7 API-layer TCs passed

The 7 API-layer tests called `/api/me/questions` directly via
`AsyncClient` (which bypasses the SPA's broken axios client) and
hit the backend correctly. The 4 UI sub-checks that the tester
flagged HUMAN_REQUIRED were the ones that needed the SPA to
actually render rows — they hit this bug.

### Why this is NOT in scope for THIS dispatch

You explicitly said: *"No Q4Y backend or frontend code change —
this dispatch is harness-only."* So:

- The 1-line fix is **NOT applied**.
- Surfaced here per the No-Silent-Deviations contract.
- Documented in `auth_testing.md` §17 as KNOWN PRE-EXISTING
  BLOCKER so the tester knows the harness is not the problem.

### Minimal fix for a follow-on dispatch (NOT applied)

```diff
- const r = await api.get("/api/me/questions", { params: {...} });
+ const r = await api.get("/me/questions", { params: {...} });
```

Estimated impact: 1 line. Regress with all 34 Q4Y backend tests +
a Playwright trace asserting the row renders. Ready when you
authorize.

---

## Verbatim discipline gates

```
4 passed, 15 warnings in 3.27s        # Solva v1 byte-identical guard
voice_lint: clean across customer-copy surfaces.
187 passed, 22 warnings in 580.99s (0:09:40)   # Full broad sweep
12/12 PASS                             # Harness verify trace
```

**Suite-size delta: 0.** Harness-only dispatch — 187 tests, same as
prior. No new tests added (none required; the harness mechanism is
fully verified by the Playwright trace, and the SPA-side bug is
out of scope).

---

## Files touched (verbatim `git status --short`)

```
 M memory/auth_testing.md          # §17 expanded with recipe + KNOWN BLOCKER
?? memory/sprints/q4y_harness_block1.md
?? /tmp/q4y_harness_verify.py
```

**Zero Q4Y code changes.** Zero new endpoints. Zero new env vars.

---

## Resume contract

Harness-only dispatch closed clean. **The 4 UI sub-checks will
remain blocked** until the pre-existing `Questions.jsx:456` bug
is fixed in a follow-on dispatch. Two clean options:

**Option A — Ship the 1-line FE fix as a sibling sub-dispatch.**
~1 line of code + a Playwright trace asserting the drawer opens
with the row + regression of the 34 Q4Y backend tests. ~30 mins
of work. Unblocks the 4 UI sub-checks.

**Option B — Defer.** Accept the 4 UI sub-checks as
`BLOCKED_BY_PRE_EXISTING_BUG` in the test report and address in
the next maintenance window. The API contracts are proven (7/7
TCs); the FE-side gap is documented.

Awaiting your steer.

Remaining backlog (unchanged):
- 🟡 P8 SendGrid Inbound Parse webhook — BLOCKED on you
- 🟢 P5.18 OAuth migration — BLOCKED on Google GCP creds
- 🟢 Q4Y P2-F4 (assignee filter) — deferred
- 🔵 Future / backlog: digest cadence, etc.
