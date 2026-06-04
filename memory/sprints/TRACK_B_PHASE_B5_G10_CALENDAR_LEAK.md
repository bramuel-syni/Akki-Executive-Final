# Track B Phase B5 G10 — Calendar SELECTED placeholder leak

**Dispatch:** 2026-06-04T08:13:00Z
**Scope:** Surgical FE deletion of two developer-authored reassurance `<p>` blocks on the Events modal. Single file, ~-18 LOC, zero behaviour change.

**Hard nos honoured:** no Track A touch, no G6/G7 retouch, no LLM/prompt touch, no new env vars, no new components, no Operation-ID cleanup, no `DateTimeApplyPicker` internal change, no `aria-live` rework.

---

## Problem (per QA spec G10 + MASTER_STATE row)

QA spec G10 (verbatim): *"Why do we have the text circled in figure 32?" — "I think the text should be removed."*

MASTER_STATE pinned the exact shape: *"Calendar edit modal `SELECTED — COMMITS ON SAVE CHANGES` placeholder."*

The leak source — `frontend/src/pages/Events.jsx:340-348` (start) and `:360-368` (end) — two near-identical `<p>` blocks rendered conditionally when `startAt` / `endAt` was set:

```jsx
{startAt && (
  <p
    className="mt-1 text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--ned-purple)]"
    data-testid="event-modal-start-selected"
    aria-live="polite"
  >
    Selected — commits on Save changes
  </p>
)}
```

Source string was mixed-case (`Selected — commits on Save changes`); Tailwind class `uppercase` rendered it on screen as `SELECTED — COMMITS ON SAVE CHANGES`, matching the all-caps shape fig 32 circles.

---

## Author-intent note (transparency)

The affordance was author-intended scaffolding, NOT a placeholder leak or unresolved i18n key. The comment at `Events.jsx:330-333` made the intent explicit: it reassured users that the picker's `Apply` button stages the value while the form's `Save changes` button commits.

Per QA verdict, the scaffolding is redundant — the picker's own visible trigger value + Apply/Save buttons together convey the workflow without the hand-holding line. The two `<p>` blocks are removed.

---

## Fix

Two `<p>` blocks deleted via single `search_replace` in `Events.jsx`. ~-18 LOC. Surrounding `<DateTimeApplyPicker>` + `<Label>` blocks untouched. The conditional `{startAt && (…)}` / `{endAt && (…)}` blocks were the only thing the `<p>` controlled — they go with it.

---

## Verification

### Grep assertion (zero hits across the entire codebase)

```bash
grep -rn "Selected — commits on Save changes\|event-modal-start-selected\|event-modal-end-selected" /app/frontend/src /app/backend
# (no output)
```

Both the source-case string AND the legacy `data-testid`s are completely absent post-fix.

### ESLint clean

`Events.jsx` passes ESLint with zero issues.

### Regression — 93/93 PASS in 13.65s

Same suite as G7 close-out (FE-only fix → BE expected zero churn):
- G7 + G6 + G11 + B3 + v1 byte-identical + Track A Phase 3 + workbook-analyze + Z1.2 — all green.

### Live wire smoke (admin@akki.ai on preview env)

```
OVERLAYS_ON_EVENTS=0
trigger 'button:has-text("Add event")' count=1
MODAL_OPEN_ATTEMPT=True
PICKED_START=True
LEAK_SOURCE_CASE_COUNT=0
LEAK_UPPERCASE_COUNT=0
LEGACY_TESTID_START_PRESENT=0
LEGACY_TESTID_END_PRESENT=0
RESULT: PASS — leak strings + legacy testids gone, no overlays
```

- ✅ `/app/events` mounts clean (no CRA / React errors).
- ✅ "Add event" modal opens; "Start" + "End (optional)" fields visible with the date pickers.
- ✅ June 2026 calendar grid renders; Cancel / Apply buttons present and clickable on the picker popover.
- ✅ After picking a date and applying — zero occurrences of "Selected — commits on Save changes" (source case) OR "SELECTED — COMMITS ON SAVE CHANGES" (uppercase-rendered) anywhere in the DOM.
- ✅ Both legacy `data-testid="event-modal-{start,end}-selected"` selectors return 0 — confirms the elements are not just hidden, they're absent.

Screenshot: `/tmp/g10_events_modal_after_pick.png` — shows the Add event modal mid-flow with the date picker open, no leak text visible.

---

## Files touched

```
M frontend/src/pages/Events.jsx       # -18 LOC: two <p> blocks deleted
M memory/MASTER_STATE.md              # G10 → 🟡, B5 counter 3/3, Sections 6+7, count recount
?? memory/sprints/TRACK_B_PHASE_B5_G10_CALENDAR_LEAK.md
```

Single source file change. Zero new dependencies. Zero new env vars. Zero copy creep (pure deletion).

---

## Risks honoured (per Pre-Read)

| # | Risk | Verified |
|---|---|---|
| R1 | Other Calendar surfaces consume the leaked string | Grep returns zero hits across the codebase post-fix — both source-case AND uppercase variants. |
| R2 | Test referencing legacy `data-testid` | Grep returns zero hits across `/app/backend/tests/`, `/tmp/`, and the FE codebase. |
| R3 | Accessibility regression on `aria-live="polite"` | None — `aria-live` was announcing a STATIC string ("Selected — commits on Save changes"), not a dynamic value. Screen readers lose nothing useful. The picker's trigger button surfaces the picked value with native form semantics. |
| R4 | Ripples into Cycle / Pulse calendar consumers | None — different pickers, different surfaces. The leak text was unique to `Events.jsx`. |
| R5 | The reassurance was load-bearing UX | Per QA spec the user explicitly does not want it. Apply + Save changes + visible picked value convey the workflow without the line. |
| R6 | Ripples into G6 / G7 / G11 / B3 | None — different files. Regression sweep stayed at 93/93 PASS. |

---

## Hard nos honoured

- ✓ No Track A touch.
- ✓ No G6 / G7 retouch.
- ✓ No LLM / prompt touch.
- ✓ No new env vars.
- ✓ No new dependencies.
- ✓ No new UI components.
- ✓ No copy creep beyond the literal-string deletion.
- ✓ No Operation-ID warning cleanup.
- ✓ No `DateTimeApplyPicker` internal change.
- ✓ No `aria-live` rework to compensate.

---

## Resume contract

Pause for tester journey-completion run. Track B Phase B5 G10 stays **🟡 SHIPPED tester-pending** until the live browser journey confirms:

1. Log in, navigate to `/app/events`
2. Click "Add event"
3. Pick a start date via the picker
4. Assert NO "SELECTED — COMMITS ON SAVE CHANGES" text under the start field
5. Pick an end date
6. Assert NO same text under the end field
7. Save the event → assert event still persists to BE (control — confirm the deletion didn't break the save path)

**On tester PASS:** G10 → ✅ COMPLETE closes Phase B5 (3/3). All 30 QA-doc items would then sit at ✅ apart from the two USER-BLOCKED items (TM3 SendGrid + G2 Google OAuth). Next dispatch flag for the user: Track A Phase 4 (multi-workbook cross-file synthesis + refresh-creates-new-version + notes-history + noisy-drift forecaster threshold tuning).