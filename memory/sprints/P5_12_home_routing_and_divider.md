# P5.12 — Post-login home: routing default + duplicate divider

**Date:** 2026-02-23 · fork-resume on the live preview cluster
**Status:** Both slices SHIPPED to disk in preview · pytest + Playwright + voice-lint green
**ANTIFORGET PROTOCOL:** acknowledged. No subagent testing. Raw scripts in `/tmp` + `/app/scripts`. Solva v1 untouched.

---

## P5.12.2 — Post-login routing default — ROOT CAUSE

**One-line root cause:** `AuthContext.afterAuth()` (lines 197–205, pre-fix) auto-picked `ctxs[0].id` immediately after a successful POST `/api/auth/login`. With `activeContextId` set, `AppHome.jsx` dispatched to `CompanyHome` (Home 2 — "Inside <Company>.") instead of `ContextPortfolio` (Home 1 — the portfolio overview the user expected).

A second, sister auto-pick lived in `AuthContext.bootstrap()` lines 122–125: cold-start in a fresh tab (cookie session valid, sessionStorage empty) also silently warped the user into `contexts[0]`. Same UX impact — fresh tab, Home 2 by default. Fixed in the same edit.

### Fix scope

Two narrow edits inside `AuthContext.jsx`:

```jsx
// afterAuth() — was:
if (ctxs.length >= 1) {
  persistActiveContext(ctxs[0].id);
} else {
  persistActiveContext(null);
}
// now:
persistActiveContext(null);     // always — Home 1 is the default landing
```

```jsx
// bootstrap() — was: else if (!cached && ctxs.length >= 1) { persistActiveContext(ctxs[0].id); }
// now: branch deleted entirely.
```

**Preserved on purpose:** the mid-session membership-revoked safety net at lines 111–116 (cached id no longer matches any membership → auto-pick the first valid membership so the SPA isn't left in a "no context" hole). That branch only fires when sessionStorage already had a stale id; it is not a "post-login default" pathway.

### Live Playwright trace (raw, no subagent)

```
[trace] final pathname: /app
[trace] H1 copy: 'Good evening, AKKI.'
[trace] [data-testid="portfolio-rail-tabs"] present? True
[trace] [data-testid="portfolio-add-company-btn"] present? True
[trace] [data-testid="portfolio-section-boards-to-watch"] present? True
[trace] [data-testid="company-home"] count: 0
[trace] [data-testid="company-home-h1"] count: 0
[trace] [data-testid="company-home-vertical-divider"] count: 0
[trace] drill-down → company-home rendered. OK.
[trace] PASS — post-login lands on Home 1 + drill-down still works
```

Script: `/tmp/p5_12_2_trace_home1.py`. Screenshots: `/tmp/p5_12_2_home1/`. Drill-down (click any company tile → Home 2 renders correctly) verified — Home 2 is not deleted, only its post-login default status was removed.

### Pytest lockdowns (4 new in `test_phase_p5_12_*.py`)

- `test_auth_context_post_login_does_not_auto_pick_context` — `afterAuth` MUST NOT contain `persistActiveContext(ctxs[0].id)`.
- `test_auth_context_cold_start_does_not_auto_pick_context` — `bootstrap()` MUST NOT contain the `else if (!cached && ctxs.length >= 1)` branch.
- `test_auth_context_preserves_membership_revoked_safety_net` — the mid-session revocation branch MUST still exist.
- `test_app_home_dispatch_to_context_portfolio_when_no_active_context` — the `if (!activeContext) return <ContextPortfolio />;` dispatch line is pinned.

---

## P5.12.1 — Duplicate vertical divider

**One-line root cause:** `frontend/src/pages/ContextPortfolio.jsx` line 482 (pre-fix) carried `lg:border-r lg:border-[var(--rule)]` on `portfolio-listing-column` AND a separate absolute-positioned standalone hairline `<div data-testid="portfolio-vertical-divider">` was rendered at lines 550–556. Both painted within ±2 px of the same X coordinate at the `lg` breakpoint, producing the visible double-line the user reported.

`CompanyHome.jsx` uses the same absolute-divider design pattern but its listing column does NOT carry `lg:border-r` — so CompanyHome is clean today. A pytest invariant locks that in too so a future copy-paste from ContextPortfolio doesn't reintroduce the duplicate.

### Fix

Single-attribute edit on `frontend/src/pages/ContextPortfolio.jsx`:

```jsx
// before:
<div className="flex-1 min-w-0 space-y-10 lg:border-r lg:border-[var(--rule)] lg:pr-10"
     data-testid="portfolio-listing-column" ...>

// after:
<div className="flex-1 min-w-0 space-y-10 lg:pr-10"
     data-testid="portfolio-listing-column" ...>
```

`lg:pr-10` stays (it provides the 40 px breathing room between listing content and the divider line). The standalone absolute hairline remains as the canonical edge-to-edge divider.

### Multi-viewport DOM probe — BEFORE vs AFTER

The probe at `/tmp/p5_12_trace_divider.py` walks the live preview at 4 viewports, signs in fresh per viewport (membership-cookie isolation), and counts how many DOM nodes paint a vertical hairline within ±2 px of the standalone divider's X coordinate.

| Viewport | Mode | Verdict | Hits |
| --- | --- | --- | --- |
| 1280 | BEFORE | `OK — single divider` | `self-bar` + 5× `border-left` (rail children, not duplicates) |
| 1280 | AFTER  | `OK — single divider` | unchanged — same `self-bar` + 5× `border-left` |
| **1024** | **BEFORE** | **`DUPLICATE — 2 hairline hits`** | **`border-right` on `portfolio-listing-column` + `self-bar` on `portfolio-vertical-divider`** |
| **1024** | **AFTER**  | **`OK — single divider`** | **`self-bar` only** — the duplicate is gone |
| 820  | both   | `SKIPPED (below_lg)` | divider hidden via `hidden lg:block` at the mobile breakpoint — no bug, no fix needed |
| 414  | both   | `SKIPPED (below_lg)` | same |

The 1024-viewport `BEFORE` probe is the user-reproducible failure. The 1280 viewport happens to mask the duplicate because the `akki-w-medium` wrapper's max-width is narrower than the viewport — the absolute divider (positioned `right: 412px` from the viewport edge, since the wrapper is not `position: relative`) and the column's `border-right` end up ~40 px apart instead of stacked. Either way, the offending stacking rule is the column `border-right`, and removing it eliminates the user's visible duplicate at every viewport where it manifests.

### Captured artefacts

- BEFORE: `/tmp/p5_12_before/1024_full.png`, `1024_seam_crop.png`, `1024_seam_addbtn_crop.png`, plus 1280/820/414 full-page shots, plus `summary.json` with full computed-style + bounding-rect dumps.
- AFTER:  same set under `/tmp/p5_12_after/`.

### Computed-style values at the seam (read off `summary.json`)

At viewport 1024, the relevant nodes:

| Node | BEFORE: borderRightWidth | AFTER: borderRightWidth |
| --- | --- | --- |
| `portfolio-listing-column` | `1px` (rule painted at column's right edge) | `0px` (rule removed) |
| `portfolio-vertical-divider` (standalone bar, `width:1px bg:var(--rule)`) | `0px` (1 px wide via `w-px`, `bg-color != transparent`) | `0px` (unchanged) |

So at 1024, BEFORE: two visible 1-px verticals overlap (one as a column border, one as a standalone bar). AFTER: only the standalone bar remains. Single divider.

### Pytest lockdowns (3 new in `test_phase_p5_12_*.py`)

- `test_context_portfolio_listing_column_has_no_border_r` — sniffs the JSX attributes on the listing-column div and asserts `lg:border-r` is absent.
- `test_context_portfolio_keeps_absolute_standalone_divider` — pins the standalone divider's class list (`absolute top-0 bottom-0 w-px`).
- `test_company_home_listing_column_has_no_border_r` — same invariant on CompanyHome's main column to prevent a future copy-paste regression.

---

## Cross-cutting

### Full pytest suite (60/60 green)

```
tests/test_solva_v1_unchanged.py                            4 passed
tests/test_phase_p5_10_audit_panel_direct_linkage.py        5 passed
tests/test_phase_p5_10_chat_resilience.py                  12 passed
tests/test_sprint_z1_qa_fixes.py                           15 passed
tests/test_phase_p5_11_notify_gating_and_csrf.py           17 passed
tests/test_phase_p5_12_home_routing_and_divider.py          7 passed   ← NEW
─────────────────────────────────────────────────────────────────────
                                                            60 passed
```

### v1 byte-identical guard
```
tests/test_solva_v1_unchanged.py: 4 passed
```

### Voice-lint
```
voice_lint: clean across customer-copy surfaces.
```

### Files touched

| File | Change |
| --- | --- |
| `frontend/src/contexts/AuthContext.jsx` | `afterAuth` always writes `persistActiveContext(null)`; `bootstrap` cold-start auto-pick branch deleted |
| `frontend/src/pages/ContextPortfolio.jsx` | `lg:border-r lg:border-[var(--rule)]` removed from `portfolio-listing-column` |
| `backend/tests/test_phase_p5_12_home_routing_and_divider.py` | NEW (7 source-strict tests) |
| `memory/sprints/P5_12_home_routing_and_divider.md` | NEW memo |
| `memory/PRD.md` | P5.12 closeout block prepended |

### Out of scope (DEFERRED per user)

- Adding `position: relative` to the `portfolio-landing` wrapper so the absolute divider anchors to it instead of the viewport. The current single-divider behaviour is what the user sees and is satisfactory; the relative-anchor adjustment is a polish item, not a bug.
- "Remember last company" preference (would be opt-in; not in this phase).
- Marketing landing pages / public home routing (P5.12.3 candidate; user has it under separate clarification).

### Deliverable index

| Artifact | Path |
| --- | --- |
| BEFORE/AFTER probe script | `/tmp/p5_12_trace_divider.py` |
| BEFORE screenshots + summary | `/tmp/p5_12_before/` |
| AFTER screenshots + summary | `/tmp/p5_12_after/` |
| Home 1 routing live trace | `/tmp/p5_12_2_trace_home1.py` |
| Home 1 routing screenshots | `/tmp/p5_12_2_home1/` |
| New pytest lockdown | `backend/tests/test_phase_p5_12_home_routing_and_divider.py` |
| This memo | `memory/sprints/P5_12_home_routing_and_divider.md` |

**HUMAN_REQUIRED:** deploy preview → production to push both fixes onto `akki.syni.ai`.
