# Q4Y-FIX sibling sub-dispatch — Questions.jsx `/api/api` typo repair
**Date:** 2026-02 (sprint, fork-resume)
**Scope:** ONE line of product code. Repair the pre-existing
doubled-`/api/api/me/questions` 404 bug surfaced by the prior
harness sub-dispatch. Unblocks the 4 UI sub-checks that the tester
flagged HUMAN_REQUIRED.
**Author:** main agent (autonomous on Option A approval)

---

## What broke and why

**Root cause (cited file:line):**
- `frontend/src/pages/Questions.jsx:456` called
  `api.get("/api/me/questions", ...)`.
- `frontend/src/lib/api.js:45-49` sets axios `baseURL = "/api"`.
- Axios prepends `baseURL` to non-absolute URLs. Net request URL:
  `/api` + `/api/me/questions` = **`/api/api/me/questions`** → HTTP
  404.
- `Questions.jsx:481-483` `catch` block swallows the error,
  `setItems([])` + `setTotal(0)` runs, `ListingShell` renders the
  empty state.

**Blame (cited from prior dispatch):**
```
c0feb6790  (2026-05-12 09:14:23 +0200 456) const r = await api.get("/api/me/questions", {
```
Predates the entire fork. Patch 14 — the page's original
implementation. Single-line outlier; every other `api.get()` call
in the codebase uses the bare-path form.

**Why prior 7/7 API-layer TCs passed:** those tests called
`/api/me/questions` directly via `AsyncClient`, bypassing the
SPA's broken axios client. The 4 UI sub-checks hit the SPA-side
path and silently saw the empty state.

---

## The fix — exactly one line

`frontend/src/pages/Questions.jsx:456`:

```diff
- const r = await api.get("/api/me/questions", { params: {...} });
+ const r = await api.get("/me/questions", { params: {...} });
```

Drop the redundant `/api/` prefix. Axios `baseURL` adds it back.
End-state matches every other `api.get()` caller in the codebase.

**Repo-wide sweep ran first** to find any same-class typo:
```
$ grep -rE 'api\.(get|post|put|patch|delete)\("/api/' frontend/src
frontend/src/pages/Questions.jsx:456:        const r = await api.get("/api/me/questions", {
```
**Only one hit. No siblings to repair.**

---

## Lockdown tests (2 new, source-text only)

`backend/tests/test_q4y_fix_questions_api_prefix.py`:

1. **`test_q4y_fix_questions_page_uses_bare_me_questions_path`** —
   asserts `Questions.jsx` does NOT contain
   `api.get("/api/me/questions"` and DOES contain
   `api.get("/me/questions"`. Locks down the specific regression.
2. **`test_q4y_fix_no_doubled_api_prefix_repo_wide`** — sweeps
   every `.js`/`.jsx` under `frontend/src` and asserts no axios
   verb call carries a leading `/api/` URL. Catches the same-root-
   cause class anywhere in the FE, not just on this page. Strips
   line-comments so doc strings are tolerated.

Both PASS.

---

## Raw Playwright trace

`/tmp/q4y_fix_trace.py` — single viewport (1280x800; per dispatch
contract, bug is not viewport-sensitive). Full user click
sequence:

```
  ✓ signed in
  ✓ sessionStorage primed
  ✓ row rendered (count=1, testid='question-row-99200f5ba1734af2af006cef90d075bd')
  ✓ drawer opened
  ✓ all 4 CTAs render
  ✓ mark-answered flipped status
  ✓ re-opened answered row
  ✓ Use in Solva → ctx_type=question&ctx_id=99200f5ba1734af2af006cef90d075bd
  ✓ Use in Chat → ctx_type=question&ctx_id=99200f5ba1734af2af006cef90d075bd

OVERALL: PASS
```

**9/9 steps PASS.** Verbatim row text captured:
`'Q4Y-FIX trace QFIX-9344ad\n\nAsked today\n·\nOpen'`. This
closes the 4 UI sub-checks the tester previously flagged
HUMAN_REQUIRED (Mark as Answered · Use in Solva · Use in Chat ·
row renders at all).

---

## Verbatim discipline gates

```
4 passed, 15 warnings in 3.24s        # Solva v1 byte-identical guard
voice_lint: clean across customer-copy surfaces.
2 passed, 15 warnings in 3.45s         # New source-text lockdown
189 passed, 22 warnings in 599.43s (0:09:59)   # Full broad sweep (23 files)
```

### Suite-size delta
Prior dispatch baseline (harness only): **187 passing**.
This dispatch: **189 passing.**
Net new: **+2** (the two source-text lockdowns).

---

## Honesty surface

1. **Single-line scope honored.** No sibling typos found by the
   repo-wide grep. No bundled "while we're here" refactors. The
   axios `baseURL = /api` configuration is unchanged.
2. **No silent deviations.** The doubled-prefix typo was surfaced
   in the prior harness dispatch's memo BEFORE any fix was
   applied; this dispatch is the explicit follow-on you authorized.
3. **No new env vars. No SendGrid changes. No GCP creds. No git
   filter-repo.**

---

## Files touched (verbatim `git status --short`)

```
 M frontend/src/pages/Questions.jsx                    # 1 line
?? backend/tests/test_q4y_fix_questions_api_prefix.py  # 2 tests
?? memory/sprints/q4y_fix.md
?? /tmp/q4y_fix_trace.py
```

Plus the docs refresh below.

---

## Production env actions

**None required.**

---

## Closes

- 4 UI sub-checks previously flagged `HUMAN_REQUIRED` by the
  tester. The verbatim row text + CTA URLs are captured in this
  memo's Playwright section.
- The KNOWN PRE-EXISTING BLOCKER section in `auth_testing.md`
  §17 (which documented the bug pending this fix).
- The Q4Y P0+P1 dispatch is now fully consumable by both the
  API-layer TCs (7/7 already passed) AND the SPA UI flows.

## Resume contract

After your final e1_tester re-run on the 4 UI sub-checks + a final
regression sweep, the bug-fix roadmap (P0 + P1 + Q4Y + harness +
Q4Y-FIX) is closed. The consolidated handoff with remaining
user-side blockers comes next.

Remaining backlog (unchanged):
- 🟡 P8 SendGrid Inbound Parse webhook — BLOCKED on you
- 🟢 P5.18 OAuth migration — BLOCKED on GCP creds
- 🟢 Q4Y P2-F4 (assignee filter) — deferred
- 🔵 Future / backlog low (digest cadence, etc.)
