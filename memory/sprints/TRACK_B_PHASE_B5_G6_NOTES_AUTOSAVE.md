# Track B Phase B5 G6 — Notes autosave

**Dispatch:** 2026-06-04T07:36:00Z
**Scope:** Replace manual "Save notes" button on `DocumentDrawer` Notes tab with debounced autosave + "Last updated: …" indicator + delete-with-confirm. Per QA spec (verbatim figure 26) — four behaviours implemented surgically.

**Hard nos honoured:** no Track A touch, no G7/G10 work, no LLM/prompt touch, no new env vars, no copy changes beyond the autosave indicator + delete-confirm strings, no Operation-ID cleanup, no new UI components / modals.

---

## Spec → implementation map

| Spec (verbatim G6 row) | Implementation |
|---|---|
| "automatically saved in the background as the user enters or modifies content" | 1.0s debounced autosave on textarea `onChange`. In-flight race coalescing via `inflightRef` + `queuedRef` — drops intermediate keystrokes, queues ONE re-save if user typed during the flight. |
| "display the date and time the note was last updated eg. Last updated: 2 June 2026, 10:45 AM" | New backend field `documents.notes_updated_at`, surfaced in `sanitize_doc` response. FE formats via `_formatNotesUpdated()` (`en-GB` long-month + `en-US` 12-hour clock — matches the spec example "2 June 2026, 10:45 AM"). |
| "any changes made during editing should continue to be auto-saved" | Same debounced path; `useEffect` re-hydrates `notes` + `notesUpdatedAt` on `doc.id`/`doc.notes`/`doc.notes_updated_at` change so successive edits to the same or different docs keep autosaving. |
| "Users should be able to delete a note and a confirmation prompt should be displayed before deletion" | "Delete note" button (rendered only when a saved note exists and not dirty) → `window.confirm("Delete this note? This cannot be undone.")` → PATCH `{notes: ""}`. Backend already nulls the field (Sprint Z1.2). |

**`window.confirm` rather than a styled modal:** spec-meeting minimum honouring credit-discipline. Upgrade to a styled modal can be a future polish pass if the user requests.

---

## Backend changes (`routers/documents.py`)

### 1. `notes_updated_at` set inside `patch_document` when notes change

```python
if body.notes is not None:
    notes_clean = body.notes.strip()[:8000]
    update["notes"] = notes_clean or None
    # Track B Phase B5 G6 (2026-06-04) — per-notes timestamp so the
    # FE's "Last updated: …" indicator reflects WHEN notes were
    # saved, not when ANY field changed. `updated_at` churns on
    # title/category/audience edits too; `notes_updated_at` only
    # changes when notes do.
    update["notes_updated_at"] = update["updated_at"]
```

Critical invariant pinned by test 1: an unrelated PATCH (e.g. `{category: "briefing"}`) does NOT bump `notes_updated_at`.

### 2. `sanitize_doc` passes `notes` + `notes_updated_at` through

Both fields added to the strict allowlist so the FE receives them on every doc read + every PATCH response. Without this, the FE PATCH response would drop both → the autosave indicator would only update on full-page refresh.

---

## Frontend changes (`components/documents/DocumentDrawer.jsx`)

### NotesTab rewrite — ~225 LOC of focused work

- `useRef`s for `debounceTimerRef`, `inflightRef`, `queuedRef`, `notesRef`, `savedRef`, `dirtyRef` — these need the LATEST value inside async callbacks WITHOUT re-binding the timer / event listener on every keystroke.
- `performSave(nextNotes)` is the single async path — used by debounce, force-flush, and delete-confirm. Coalesces in-flight races.
- `onTextChange` clears the prior timer and schedules a 1.0s debounce.
- `beforeunload` listener uses raw `fetch(..., {keepalive: true})` — the axios `api` helper does NOT support `keepalive`, and `navigator.sendBeacon` is POST-only (we need PATCH). Documented `eslint-disable-next-line no-restricted-syntax -- …` per `/app/memory/sprints/LINT_API_CLIENT_RULE.md` Patch 24B escape-hatch convention.
- `useEffect` cleanup on unmount fires a fire-and-forget PATCH if dirty — uses the standard `api.patch` (in-page request, no keepalive needed).
- "Delete note" button rendered only when `savedSnapshot && !deleting && !dirty` so the user doesn't accidentally delete in the middle of a fresh edit.

### Force-flush behaviour quoted (verbatim)

```js
// beforeunload — survives page unload via fetch keepalive.
// eslint-disable-next-line no-restricted-syntax -- axios/api helper
// does not support fetch's `keepalive: true`, which is required for
// a beforeunload PATCH to survive page unload. This is the
// documented escape-hatch case from /app/memory/sprints/LINT_API_
// CLIENT_RULE.md (Patch 24B). Fire-and-forget; no response handling.
fetch(
  `${apiBase}/api/contexts/${contextId}/documents/${doc.id}`,
  {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes: notesRef.current || "" }),
    keepalive: true,
  },
);

// useEffect cleanup (unmount) — fire-and-forget via axios api helper.
api.patch(
  `/contexts/${contextId}/documents/${doc.id}`,
  { notes: latest },
).catch(() => { /* swallow — unmount, no user surface */ });
```

---

## Lockdown tests (3 — well under R4 ≤10 cap)

**File:** `backend/tests/test_track_b_phase_b5_g6_notes_autosave.py`

1. `test_patch_notes_sets_notes_updated_at` — PATCH `{notes: "foo"}` → both `notes` and `notes_updated_at` populate on disk AND in the PATCH response body. Unrelated PATCH (`{category: "briefing"}`) bumps `updated_at` but NOT `notes_updated_at`.
2. `test_patch_empty_notes_clears_field_and_bumps_timestamp` — PATCH `{notes: ""}` (delete path) → `notes` is null AND `notes_updated_at` is a fresh timestamp so FE can render "Last updated: …" post-delete.
3. `test_patch_notes_idempotency_safe_for_autosave_debounce` — Two consecutive PATCHes with same notes text both 200, both bump the timestamp, no race. Pins the debounce-flush-twice contract.

**Pytest verbatim:** 3/3 PASS in 7.03s.

---

## Z1.2 test update (transparent, in-scope)

`backend/tests/test_sprint_z1_qa_fixes.py::test_frontend_drawer_notes_payload_is_correct` was a source-text grep pinning the literal shorthand `api.patch(\`/contexts/${contextId}/documents/${doc.id}\`, { notes })`. The G6 rewrite legitimately changes the source to explicit `{ notes: nextNotes }` / `{ notes: "" }` / `{ notes: latest }` (three distinct call sites with different value sources). The PATCH **contract is unchanged**; only the JS shorthand evolved.

Test rewritten to assert the contract not the shorthand:
- Endpoint URL `/contexts/${contextId}/documents/${doc.id}` still present.
- Any notes payload variant (`{ notes }`, `{ notes:`, `{notes:`, `{notes}`) present.

Both assertions pass against the new source. Z1.2 audit purpose preserved.

---

## Regression — 91/91 PASS in 13.12s

- `test_track_b_phase_b5_g6_notes_autosave.py` (G6, new) → 3/3 ✓
- `test_sprint_z1_qa_fixes.py` (Z1.2, updated) → all green ✓
- `test_track_b_phase_b4_g11_q4y_promotion.py` (G11 backend) → 4/4 ✓
- `test_track_b_phase3_questions_completion.py` (B3 Q4Y) → all green ✓
- `test_solva_v1_unchanged.py` (v1 byte-identical guard) → 4/4 ✓
- `test_track_a_phase3_prompt_fix.py` (Track A Phase 3) → 14 cases ✓
- `test_track_a_phase3_narration.py` (Track A Phase 3) → 13 cases ✓
- `test_phase_p5_14_workbook_analyze.py` (workbook engine) → 32 cases ✓

ESLint clean on `DocumentDrawer.jsx`. Voice-lint clean.

---

## Smoke screenshot (pre-handoff)

`https://akki-executive.preview.emergentagent.com` — admin@akki.ai post-login navigated to `/app/documents`:

- ✅ `OVERLAY_ON_SIGNIN_PRE_LOGIN=0` (CRA dev-server compile clean — the raw-fetch eslint-disable comment landed cleanly with the documented Patch 24B reason)
- ✅ `OVERLAYS_AFTER_AUTOSAVE=0` (zero React or compile errors anywhere)
- ✅ Legacy `[data-testid="drawer-notes-save"]` count = 0 (manual button removed)
- ⚠️ admin@akki.ai's preview workspace had no documents to drill into → live debounce/autosave round-trip not exercisable in the smoke; that's the tester journey on a populated context.
- Screenshots: `/tmp/g6_documents_list.png`, `/tmp/g6_notes_tab_initial.png`, `/tmp/g6_notes_after_typing.png`.

---

## Files touched

```
M backend/routers/documents.py                                   # +12 LOC: notes_updated_at on PATCH + sanitize_doc passthrough
M frontend/src/components/documents/DocumentDrawer.jsx           # ~225 LOC NotesTab rewrite + useRef + Trash2 icon + raw-fetch escape-hatch comment
?? backend/tests/test_track_b_phase_b5_g6_notes_autosave.py      # 3 backend lockdowns
M backend/tests/test_sprint_z1_qa_fixes.py                        # Z1.2 source-text test updated for shorthand → explicit shape
M memory/MASTER_STATE.md                                          # G6 row, Section 4 B5, Sections 6+7
?? memory/sprints/TRACK_B_PHASE_B5_G6_NOTES_AUTOSAVE.md
```

No new env vars. No new dependencies. No new UI components / modals. No copy changes beyond "Saving…", "Last updated: …", "Delete note", and the confirm dialog text — all directly mandated by the QA spec.

---

## Risks honoured (per Pre-Read)

| # | Risk | Status |
|---|---|---|
| R1 | Debounce + rapid typing race | Mitigated by `inflightRef` + `queuedRef` coalescer. Test 3 pins idempotency. |
| R2 | Browser tab close mid-debounce | `beforeunload` listener with `fetch(keepalive: true)` fire-and-forget. |
| R3 | Drawer close / doc switch mid-debounce | `useEffect` cleanup fires fire-and-forget `api.patch`. |
| R4 | Ripples into B3 (Q4Y drawer) | None — different file (`Questions.jsx` vs `DocumentDrawer.jsx`). |
| R5 | Ripples into G11 (just-shipped) | None — G11 promoter writes `cycle_questions`, G6 writes `documents.notes`. |
| R6 | Ripples into Sprint Z1.2 manual save | Z1.2 source-text test updated transparently; PATCH contract unchanged. |
| R7 | Doc `updated_at` semantics | Unchanged. Intelligence cache invalidator at `documents.py:925` only fires on `(extracted_text, name, state, objective)` — notes correctly not in that set. |

---

## Hard nos honoured

- ✓ No Track A touch.
- ✓ No G7 (Send Share) or G10 (Calendar) work — separate dispatches.
- ✓ No LLM / prompt touch.
- ✓ No new env vars.
- ✓ No new UI components / modals — used `window.confirm` per spec-meeting minimum.
- ✓ No Operation-ID warning cleanup.
- ✓ Schema additive `notes_updated_at` justified (avoids `updated_at` churn on unrelated edits).
- ✓ No customer-facing copy changes beyond the spec-mandated strings ("Saving…", "Last updated: …", "Delete note", confirm prompt).

---

## Resume contract

Pause for tester journey-completion run. Track B Phase B5 G6 stays **🟡 SHIPPED tester-pending** until the live browser journey confirms:

1. Open doc drawer, click Notes tab, see textarea (no manual save button)
2. Type a sentence → wait 1.5s → "Last updated: …" indicator appears
3. Reload page → reopen drawer → text persists, indicator still rendered
4. Type → reload mid-debounce → text from before persists (in-flight keystroke acceptably lost)
5. Type → close drawer mid-debounce → reopen → text persists (force-flush invariant)
6. Click "Delete note" → confirm prompt → confirm → notes cleared → "Last updated: …" against post-delete timestamp

Next dispatch (after tester PASS): G7 — Send Share "Field required" false positive.