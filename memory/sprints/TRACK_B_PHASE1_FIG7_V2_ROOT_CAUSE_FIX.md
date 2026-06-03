# Track B Phase 1 Fig 7 v2 — Root-Cause Close Memo

**Date:** 2026-06-03T21:09:00Z
**Rails honoured:** R1 (MASTER_STATE.md read first), R3 (live-DOM exercised, not just source-text), R4 (≤10 tests for Track B Phase 1; final = 9), R5 (ground-truth audit before option choice), R6 (zero side quests — no Track A touch, no Fig 20/22 touch), R7 (audit results surfaced).

---

## 1 — Files touched

```
M frontend/src/index.css                                 (+18 / -1 — .akki-overline:not(button) descope rule)
M backend/tests/test_track_b_phase1_signin_begin.py      (+62 / -2 — added v2 source-strict test + live-DOM subprocess test)
R /tmp/track_b_phase1_fig7_v2_trace.py                   (NEW — sibling of v1 trace; seeds intake state via DB, drives Chromium, asserts computed colour delta)
M memory/MASTER_STATE.md                                 (Section 3 C8 row 🟡 PARTIAL; Section 4 Track A Phase 1 ✅; Section 7 timestamp)
A memory/sprints/TRACK_B_PHASE1_FIG7_V2_ROOT_CAUSE_FIX.md  (this memo)
```

---

## 2 — Option chosen + grep evidence

**Chose Option (iv) — descope `.akki-overline` color to `:not(button)` in `index.css`.**

**Grep evidence (verbatim, automated audit of `frontend/src`, exclusions: `node_modules`, `_archived_*`):**

```
TOTAL .akki-overline JSX usages: 248
BUTTON consumers: 7
NON-BUTTON consumers: 241
```

The 7 button consumers (FULL LIST):

| File:line | Element | text-* utility on the same className |
|---|---|---|
| `governance/TrustPanel.jsx:190` | `<button>` | `text-[var(--ink)]` |
| `governance/TrustPanel.jsx:210` | `<button>` | `text-white bg-[var(--ink)]` |
| `governance/TrustPanel.jsx:382` | `<button>` | `text-[var(--muted)]` |
| `pages/FirstSession.jsx:188` | `<button>` | `text-white bg-[var(--accent)]` (Fig 7 — THE BUG) |
| `pages/FirstSession.jsx:247` | `<button>` | `text-[var(--muted)]` |
| `pages/FirstSession.jsx:597` | `<button>` | `text-white bg-[var(--accent)]` (same root cause; tester didn't screenshot but same victim class) |
| `pages/DailyReview.jsx:594` | `<Button>` (shadcn → `<button>`) | `text-white bg-[var(--accent)]` (same root cause) |

**Every single button consumer already supplies an explicit `text-*` Tailwind utility.** The `.akki-overline` `color: var(--oxblood)` rule was silently overriding all 7 because (a) the CSS-class color tied on specificity with `.text-*` Tailwind utilities and (b) `.akki-overline` is defined AFTER Tailwind in the cascade. Options (i), (ii), (iii) would have patched ONE button each and left the other 6 broken. Option (iv) corrects the entire class of bug at one stroke. **The 241 non-button consumers are entirely unaffected** — the `:not(button)` selector preserves the oxblood color for `<p>` / `<h3>` / `<span>` / `<div>` / `<label>` consumers (which is what the class was designed for in the first place).

**The fix shape (`frontend/src/index.css:223-247`):**

```css
.akki-overline {
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.16em;
}

/* Track B Phase 1 Fig 7 (2026-06-03): descope .akki-overline's color
   to non-button elements. […audit summary…] */
.akki-overline:not(button) {
  color: var(--oxblood);
}
```

Why this is correct cascade-wise: the typography props (font/size/weight/uppercase/letter-spacing) stay on the base class — every consumer (button or not) still gets the eyebrow treatment. Only the `color:` declaration is descoped. On `<button class="akki-overline …">` the Tailwind utility now wins because `.akki-overline` no longer sets a competing color.

---

## 3 — Computed-color test result (verbatim from live-DOM trace)

`/tmp/track_b_phase1_fig7_v2_trace.py` run against `https://akki-executive.preview.emergentagent.com`:

```
[setup] viewer@akki.ai forced to first_session.current_step=intake
[step] signed in as viewer; post-signin url = https://akki-executive.preview.emergentagent.com/app
[step] landed at https://akki-executive.preview.emergentagent.com/app/first-session
[diag]  visible testids (first 30): ['first-session-shell', 'first-session-intake',
        'first-session-role-executive', 'first-session-role-ned',
        'first-session-role-chair', 'first-session-role-dual',
        'first-session-context-name', 'first-session-top-of-mind',
        'first-session-skip', 'first-session-intake-submit',
        'first-session-account-email', 'trial-status']
[step] FirstSession intake reached
[disabled] text-color:       rgb(255, 255, 255)
[disabled] background-color: rgb(122, 46, 46)
[disabled] per-channel max delta: 209
[active]   text-color:       rgb(255, 255, 255)
[active]   background-color: rgb(122, 46, 46)
[active]   per-channel max delta: 209
[cleanup] viewer@akki.ai first_session restored to done
[Fig 7 v2] PASS
```

Before the v2 fix the tester reported `text == bg == rgb(122,46,46)`, per-channel delta 0. After: white text on oxblood bg, per-channel delta 209. Visible.

Note on the bg-color: it resolves to `rgb(122,46,46)` (oxblood) NOT a lightened/composited accent — the disabled-state still uses the saturated tint produced by the `bg-[var(--accent)]/70` Tailwind utility composited onto the cream parent. The TEXT is now correctly white (the Tailwind `text-white` utility finally takes effect post-descope).

---

## 4 — Test inventory (9 of ≤10, R4 compliant — Track B Phase 1)

| # | Test | Status |
|---|---|---|
| 1 | `test_fig7_first_session_begin_button_no_low_contrast_disabled` (v1 source-strict) | ✅ |
| 2 | `test_fig7_root_cause_akki_overline_descoped_from_buttons` (**NEW — v2 source-strict, root cause**) | ✅ |
| 3 | `test_fig7_begin_button_keeps_data_testid_for_playwright` | ✅ |
| 4 | `test_p0_c_oauth_last_activity_at_refresh_still_present` (regression) | ✅ |
| 5 | `test_c1_a_has_set_password_gate_still_present` (regression) | ✅ |
| 6 | `test_p0_b_card_2_documents_upload_route_still_present` (regression) | ✅ |
| 7 | `test_fig7_live_dom_text_color_not_equal_bg_color` (**NEW — subprocess → Playwright; THE test that catches the bug v1 missed**) | ✅ |
| 8 | `test_fig20_unauth_root_lands_on_signin` | ⏭ SKIPPED — BLOCKED_NEED_SCREENSHOT |
| 9 | `test_fig22_post_redirect_no_error_state` | ⏭ SKIPPED — BLOCKED_NEED_SCREENSHOT |

Total: **7 passed, 2 skipped**. Two tests added vs. previous dispatch (the maximum the dispatch allowed). Final count 9 ≤ R4 cap of 10.

---

## 5 — Sanity sweep

```
tests/test_track_b_phase1_signin_begin.py            7 passed, 2 skipped
tests/test_track_a_phase1_analysis_foundation.py     9 passed
tests/test_phase_p5_14_workbook_analyze.py          31 passed
tests/test_solva_v1_unchanged.py                     4 passed
voice_lint                                           clean
```

Total: 51 passed + 2 skipped. No regressions across Track A (which the dispatch told me NOT to touch and which is now ✅), no Solva v1 byte-identical drift, no voice-lint regression.

---

## 6 — Honest reckoning (R7)

1. **My v1 fix was directionally correct but mechanically insufficient.** The /40 → /70 opacity bump assumed the disabled bg was the contrast problem — actually the foreground was being silently overridden by the `.akki-overline` class color. Tester caught it because they ran the live-DOM check that my v1 lockdown didn't include. Acknowledged.

2. **The same root cause exists on 6 other buttons.** The audit confirmed `.akki-overline` is on a `<button>` 7 times in the active codebase — only Fig 7 was visible (white-text-on-oxblood is the worst-case combination). Six other buttons had less-visible but still-broken styling (e.g. `text-[var(--muted)]` getting overridden to oxblood). Option (iv) corrects all 7 with no other touches.

3. **Live-DOM lockdown is now in the test suite.** It runs as a `subprocess` invocation of the trace script and asserts on its exit code + the verbatim output containing `[Fig 7 v2] PASS`. If `.akki-overline` is ever re-scoped to include buttons, OR if the FirstSession Begin button's text-color drifts, OR if the cascade order changes, the test will fail with the verbatim computed colors in its error message — exactly the diagnostic the v1 test couldn't surface.

4. **Tester re-verification gate.** Per dispatch — Fig 7 row in Section 3 stays 🟡 PARTIAL until tester re-verifies. Track A Phase 1 row in Section 4 flipped to ✅ per the tester's verdict in the prior dispatch.

5. **Hygiene cleanup.** The trace seeds `viewer@akki.ai` into `first_session.current_step=intake` then restores them to `status=skipped, current_step=done, grandfathered=true` on PASS. No accounts are left mid-flow.

6. **No new env vars, no Stripe/SendGrid/GCP, no Figs 20+22, no Track A touch, no regression-sweep beyond what was already in the file.** R6 honoured.

---

## 7 — Tester re-verification journey

> Open the preview. Navigate to `/app/first-session`. (Either: sign up a fresh account, OR temporarily reset the test account's `first_session.current_step` to `"intake"` via the admin QA hook.) Confirm the BEGIN → button text is clearly readable in BOTH the disabled state (before filling fields) AND the active state (after filling all three fields). White text on oxblood bg, both states.
>
> If that passes → C8 Fig 7 row in MASTER_STATE.md Section 3 flips to ✅. (Not my call — tester's call.)
