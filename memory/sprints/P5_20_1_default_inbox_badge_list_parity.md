# P5.20.1 — Default-inbox badge list parity + test-infra unblock

Date: 2026-02-06

## Scope (two narrow fixes, no scope creep)

1. **Default-inbox badge on Cycle list rows.** P5.20 shipped the badge
   on the cycle DETAIL page only (`Cycle.jsx`). The same badge must
   also surface on every cycle list row whose cycle is the auto-
   scaffolded default-inbox cycle, so testers can identify it without
   clicking through.
2. **Active-context sessionStorage tester docs.** Testers had hit the
   empty-workspace-picker state 3 times across P5.17 / P5.19 / P5.20
   when running Playwright traces. The canonical injection snippet,
   per-account context_ids, and pitfalls all live in
   `/app/memory/test_credentials.md` so any future tester can reach
   a context-dependent surface from a fresh login without guessing.

## Implementation

### 1. CycleCard.jsx badge wire-up

`frontend/src/components/cycle/CycleCard.jsx`:

```jsx
{cycle.is_default_inbox_cycle && (
  <span
    className="ml-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm border bg-amber-50 text-amber-800 border-amber-300 align-middle"
    data-testid="cycle-default-inbox-badge"
    title="Auto-scaffolded cycle for inbound email routing."
  >
    <span aria-hidden>✉</span> default inbox
  </span>
)}
```

- Read-only, purely informational. No click handler — row click
  affordance (the `<Link>` wrapping the card) is untouched.
- Style/text parity with the `Cycle.jsx` detail-page badge.
- `is_default_inbox_cycle` flows through unchanged: `_hydrate_cycle`
  in `backend/routers/cycles.py` returns `{**row, ...}`, so the flag
  reaches the JSON envelope by default. **No serializer change
  needed**; the new lockdown test
  (`test_cycle_list_endpoint_carries_is_default_inbox_flag`) guards
  against an accidental future projection that drops it.

### 2. test_credentials.md P5.20.1 section

Replaced the prior narrative section with:
- A concise Python Playwright injection snippet (settle wait,
  setItem, reload).
- Common-pitfalls list (correct key name, per-tab semantics, settle
  before set, reload after set).
- **Table-format canonical context_ids** per test account, with the
  recommended default first and TEST_* transient seeds clearly
  flagged.
- The exact path to the verbatim validation script.

Live DB pull is reproducible: `python3 /tmp/p5_20_1_fetch_context_ids.py`.

## Lockdown tests (+2 in `test_phase_p5_20_default_inbox_cycle.py`)

1. `test_cycle_list_endpoint_carries_is_default_inbox_flag` — calls
   `GET /api/contexts/{cid}/cycles?status=all` against admin's
   default-inbox context and asserts the seeded row has
   `is_default_inbox_cycle: True`. Guards the hydrate pass-through.
2. `test_cycle_card_renders_default_inbox_badge_conditionally` —
   source-strict read of `CycleCard.jsx` asserts both the
   `cycle.is_default_inbox_cycle` conditional AND the
   `data-testid="cycle-default-inbox-badge"` literal are present.

## Live raw Playwright traces (per ANTIFORGET PROTOCOL)

### Trace A: list-page badge at 4 viewports
`/tmp/p5_20_1_list_badge_trace.py` — admin login, lookup default-
inbox context, seed a sibling user-curated cycle, navigate to
`/app/cycle?cid=<ctx>`, probe both `cycle-card-title-<default_cyc>`
and `cycle-card-title-<user_cyc>` for the badge child.

Verbatim stdout (re-run 2026-02-06):

```
[seed] ctx=ctx-akki-inbox-d29828f3b6 default_cyc=cyc-akki-inbox-5fd5dc4d18 user_cyc=cyc-user-trace-7b20995d6c
[1280x800] {'badge_count': 1, 'default_card_present': True, 'user_card_present': True, 'default_card_has_badge': True, 'user_card_has_badge': False, 'badge_text': '✉\nDEFAULT INBOX'}
[1024x768] {'badge_count': 1, 'default_card_present': True, 'user_card_present': True, 'default_card_has_badge': True, 'user_card_has_badge': False, 'badge_text': '✉\nDEFAULT INBOX'}
[820x1180] {'badge_count': 1, 'default_card_present': True, 'user_card_present': True, 'default_card_has_badge': True, 'user_card_has_badge': False, 'badge_text': '✉\nDEFAULT INBOX'}
[414x896] {'badge_count': 1, 'default_card_present': True, 'user_card_present': True, 'default_card_has_badge': True, 'user_card_has_badge': False, 'badge_text': '✉\nDEFAULT INBOX'}
```

Per-viewport result: exactly **one** badge in the DOM (the default-
inbox row); the user-curated sibling row has **no** badge.

Viewport screenshots stored at `/tmp/p5_20_1_list_badge/cycles_list_*.jpg`.

### Trace B: sessionStorage snippet validation
`/tmp/p5_20_1_session_storage_snippet_validation.py` — fresh
Playwright session, login, **3-second settle**, set
`akki_active_context_id`, reload, navigate to the default-inbox
cycle, assert URL auto-jumps to `?tab=contributions`.

Verbatim stdout (re-run 2026-02-06):

```
[setup] admin default-inbox ctx=ctx-akki-inbox-d29828f3b6 cyc=cyc-akki-inbox-5fd5dc4d18
[step 1] login: OK
[step 2] sessionStorage.akki_active_context_id = ctx-akki-inbox-d29828f3b6
[step 2b] page reloaded — AuthProvider re-initialises from sessionStorage.
[step 3] final URL after 1s wait: https://akki-executive.preview.emergentagent.com/app/cycle/cyc-akki-inbox-5fd5dc4d18?tab=contributions
[step 3] active tab testid: None
[step 4] URL contains tab=contributions ✓ (P5.20 auto-jump fired correctly)

VALIDATION PASSED ✓
```

**Note:** the first run without the post-login settle wait failed
intermittently because AuthProvider's bootstrap raced with the
setItem and clobbered the value. The pitfall is captured in
`test_credentials.md` and the snippet itself.

## Discipline gates (verbatim)

- **Combined suite:** `147 passed, 15 warnings in 112.22s (0:01:52)`.
  Suite-size delta vs P5.20 baseline (145): **+2**.
- **v1 byte-identical guard:** `4 passed, 15 warnings in 3.47s`.
- **Voice-lint:** `voice_lint: clean across customer-copy surfaces.`
- **JS lint (CycleCard.jsx):** ✅ No issues found.

## Files touched

Edit:
- `frontend/src/components/cycle/CycleCard.jsx` — list badge.
  (Already present from prior P5.20.1 attempt; re-verified.)
- `backend/tests/test_phase_p5_20_default_inbox_cycle.py` — +2
  lockdown tests at the bottom.
- `memory/test_credentials.md` — P5.20.1 section rewritten to
  table-format canonical context_ids + Playwright snippet.
- `tmp/p5_20_1_session_storage_snippet_validation.py` — added
  3-second post-login settle; fixed flake.

Add:
- `memory/sprints/P5_20_1_default_inbox_badge_list_parity.md` (this).
- `tmp/p5_20_1_fetch_context_ids.py` — live DB pull helper.
- `tmp/p5_20_1_diag.py` — diagnostic-rich validation (kept; useful
  for future flake repros).

No change to:
- `services/solva_v1/**` (v1 byte-identical guard remains green).
- `backend/routers/cycles.py` (`_hydrate_cycle` already passes the
  flag through via `{**row}`).

## Backlog (deferred — explicitly out of scope)

- Re-target row action on the list badge (would add new click
  affordance; user kept this in deferred polish).
- Cross-test fixture state leak (`Future attached to a different loop`)
  — user kept this logged, do NOT piggyback.
