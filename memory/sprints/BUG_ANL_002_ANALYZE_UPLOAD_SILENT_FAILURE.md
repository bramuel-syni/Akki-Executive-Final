# BUG-ANL-002 — Analyze upload picker silent-failure on file selection

**Shipped:** 2026-06-04 (single-dispatch surgical fix, iter 1 of 1).
**Approver:** User dispatched directly with hypothesis space + diagnosis brief.

---

## Symptom (user-reported, verbatim shape)

- URL: `/app/analyze?context_id=<valid>` (Analyze Journal, valid context).
- Click "Upload files (.xlsx / .csv)" → OS file picker opens.
- Select a file → **nothing happens**. No staged file in UI, no upload progress, no error toast.
- Page refresh is the only consistent workaround. Re-attempt "sometimes" works.

---

## Diagnosis (reproduced on live preview)

### Step 1 — happy-path reproduction (`/tmp/bug_anl_002_diagnose.py`)

Logged in as admin@akki.ai → /app/analyze?context_id=… → `set_input_files()` on a freshly seeded `.csv` → captured network + console + DOM state.

Result: `POST /api/workbook/upload-multi` → **200** with `{"id":"ana-bc68255e9884",…}`. Success toast `"Analysis created (1 file)"` rendered. Drawer opened. **Happy path works.**

### Step 2 — root-cause confirmation (`/tmp/bug_anl_002_confirm_stale_input.py`)

Tested two retry sequences with a manual onChange listener attached to the input:

**Sequence A — re-pick after SUCCESS:**

```
After pick #1: change_log=['onChange:1']
input.value after upload settles: ''        ← React cleared it on success
After pick #2 (same file): change_log=['onChange:1']  ← re-fires ✓
```

**Sequence B — re-pick after FAILURE (injected 500):**

```
After failed upload: change_log=['onChange:1']
                     input.value='C:\\fakepath\\bug_anl_002_sample.csv'  ← NOT cleared
Toasts after failed upload: ['injected_500_for_bug_anl_002']
After retry of SAME file: change_log=[]           ← onChange DID NOT FIRE
                     input.value='C:\\fakepath\\bug_anl_002_sample.csv'  ← still stuck
Toasts after retry: ['injected_500_for_bug_anl_002']  (the stale toast from the prior attempt)
```

**Verdict:** The pre-fix `pages/AnalyzeJournal.jsx:135` reset `fileInput.current.value = ""` *inside the `try` block, after the API call resolved*. On the failure path the `catch` ran (with toast.error) and `finally` reset `creating=false`, but the input retained the picked filename. The next OS-picker selection of the same file did not change `input.value` → no `change` event → no `onCreate` invocation → silent failure.

This is the canonical HTML `<input type="file">` quirk: same-value re-selection suppresses `onChange`. Closest to user hypothesis 1 (handler not firing) but the root cause is state retention, not handler binding.

### Why "refresh fixes it" and "sometimes succeeds"

- **Refresh fixes it:** fresh mount of `AnalyzeJournal` re-creates the input with `value=""`. The next pick fires onChange.
- **Sometimes succeeds:** re-picking a DIFFERENT-named file changes `input.value` → onChange fires → upload re-runs → if the original failure cause is transient (network, race), it succeeds.

The user's note "no error toast" on the silent retry is also explained: the stale toast from the prior FAILED attempt may have already dismissed, and the retry attempt produced no new event, so the screen is silent.

---

## Fix landed

`pages/AnalyzeJournal.jsx` — relocate the input-value cleanup from the success branch to the `finally` block of `onCreate`:

```diff
       const { data } = await api.post("/workbook/upload-multi", fd, {
         headers: { "Content-Type": "multipart/form-data" },
       });
       toast.success(`Analysis created (${filesList.length} file${filesList.length === 1 ? "" : "s"})`);
       setObjective("");
-      if (fileInput.current) fileInput.current.value = "";
       await load();
       openDrawer(data.id);
     } catch (e) {
       toast.error(apiErrorMessage(e));
     } finally {
       setCreating(false);
+      // BUG-ANL-002 — ALWAYS clear input.value after an upload
+      // attempt, success OR failure. (…inline rationale…)
+      if (fileInput.current) fileInput.current.value = "";
     }
```

**Net: +12 LOC (comment + relocated line) / -1 LOC.** No behaviour change on the success path; closes the failure-retry silent path.

**Files touched (1):**

```
frontend/src/pages/AnalyzeJournal.jsx     +12 LOC / -1 LOC
```

**Backend unchanged.** No new dependencies. No Phase 5/Phase 6 retouch. No swallowed exceptions added; the existing `catch` already surfaces `toast.error(apiErrorMessage(e))`.

---

## Verification (live preview)

`/tmp/bug_anl_002_upload_journey.py` — 8 assertions, all PASS:

```
=== BUG-ANL-002 lockdown ===
  A1_first_pick_fired_change: PASS
  A2_first_pick_toast: PASS
  A3_finally_cleared_value: PASS
  B1_failed_pick_fired_change: PASS
  B2_failed_pick_error_toast: PASS
  B3_finally_cleared_after_failure: PASS         ← the critical assertion
  C1_retry_same_file_fired_change: PASS          ← was FAIL pre-fix
  C2_retry_same_file_success_toast: PASS         ← was FAIL pre-fix

OVERALL: PASS — 8/8 assertions
```

Sequence: A is the happy-path success; B injects 500 on the next call to assert the failure-path clears `input.value`; C lifts the injection and re-picks the same file to prove the retry actually fires and succeeds.

---

## Discipline rails observed

- **Ground-truth read first**: re-read `AnalyzeJournal.jsx:1-258`, `lib/api.js:248-279` (`apiErrorMessage` confirmed surfaces all detail shapes), and the backend `routers/workbook_analysis.py:644-708` (`/upload-multi` route) before any edit.
- **Reproduced before fixing**: 2 diagnostic Playwright scripts captured the exact silent-failure state via network + console + DOM snapshots + the `change_log` audit.
- **Diagnosis documented first**: hypothesis space mapped to actual root cause in the prelude memo before any code touched.
- **No swallowed exceptions**: pre-existing `catch` block already surfaces toast.error; no new swallows added.
- **Surgical fix to the broken hop**: one cleanup line relocated; no rewrite of the upload component or its event wiring.
- **Iteration budget**: 1/1 used. No deeper architectural surprise surfaced.
- **No backend involvement**: this is purely an FE state-management quirk; backend contract is correct.
- **No Phase 6 retouch / no Phase 5 retouch / no scope creep**.

---

## What this dispatch did NOT touch

- `.xls` (legacy binary) parser support — explicitly out of scope per user hard-no.
- The `<input>` markup, `ref` binding, or `onChange` prop — handler binding was correct; the bug was upstream of the binding.
- Any other route or upload surface. Greped `accept=".xlsx,.csv"` and `set_input_files` patterns in the FE: this is the only Analyze upload surface; Documents library uses a separate component (`UploadModal`) which already resets its file input inside a useEffect on close.

---

## Status

**BUG-ANL-002 → ✅ COMPLETE 2026-06-04.**
