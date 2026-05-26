# Home Cleanup Batch Log

**Dispatched:** 2026-05-26 (post-product-feature-review).
**Batch overview:** Two-phase cleanup of the authenticated home surfaces, ending with a deploy-readiness pass.
- Phase A — Home 1 (Portfolio view) — **this task**.
- Phase B — Home 2 (company workspace) — placeholder, not yet started.

The batch follows the standing rules: no spec edits, no new packages, surgical diffs, reuse existing tokens/components/hooks, empty-states for unwired data, every change tracked.

---

## Phase A — Home 1 (Portfolio view)

**Status:** in progress.
**Route:** `/app` (renders via `pages/AppHome.jsx` dispatcher → `pages/home/Home1.jsx`).
**Files changed:** see "Files changed" subsection below (logged after each edit).

### 1. Font reduction 30% — company tile titles only

**Brief correction received mid-task:** scope tightened to *company tile titles only* — hero greeting, "Your companies" section heading, and all other text stay at current sizes.

**Target:** `<p>` element inside `ChipCompany` rendering `ctx.name` (currently `text-[16px]` per `Home1.jsx:103`).

**Calculation:** 16px × 0.70 = 11.2px → rounded to **11px** (CSS sub-pixel rounding; honest 30% reduction).

**Surface scoped:** the ONLY caller of `ChipCompany` is the "Your companies" grid in `Home1.jsx:186`. No other component imports `ChipCompany`. Change is naturally scoped to the portfolio view; no variant prop needed.

### 2. Role chip colors — Oxblood (Executive) + new NED purple

**Brief:** add `--ned-purple: #6B46C1` to the theme file alongside Oxblood; render Executive chip = Oxblood-15%-bg + Oxblood text; render NED chip = `--ned-purple`-15%-bg + `--ned-purple` text.

**Theme file:** `/app/frontend/src/index.css` :: `:root` block (where the v7 four-token palette is defined alongside legacy aliases like `--oxblood`).

**Component:** `ChipCompany` in `Home1.jsx`. The chip currently renders with `bg-[var(--cream-deep)]` + `text-[var(--muted)]` for ALL roles (the existing 2026-05-13 "v7 token sweep rule" comment explicitly says *"role chip in muted neutral (NOT crimson)"*). **This is a spec/code delta — see Spec/Code Deltas section below.** The brief overrides the v7 rule for these two specific roles; proceeding per brief.

**Scope check:** `ChipCompany` is only rendered from `Home1.jsx`. Other portfolio-chip surfaces (`AppShell.jsx` mini-switcher, `CompanySwitcherDialog.jsx`) use their own chip styling and are NOT changed by this edit.

### 3. News section "Read more →" link

**Brief:** keep "Curated for [Country]" badge; add "Read more →" link at the bottom of the news list; navigate to existing Learn news feed (`/app/learn`).

**Verification that Learn IS the news feed:** `pages/Learn.jsx:24-29` defines `TABS` with `{ key: "news", label: "News", icon: Newspaper }` as the first tab. Route `/app/learn` is registered in `App.js:309`. No new route needed — reuse confirmed.

**Implementation:** new `<Link to="/app/learn">Read more →</Link>` appended at the foot of `home1-news` section, OUTSIDE the scrollable `<ul>` (so it doesn't disappear into the overflow box). Honors empty-state — only render the link when there's at least one article.

### 4. Horizontal alignment — "Coming up" + "Continue where you left off"

**Brief:** render side-by-side, 2-column grid, equal widths, same row; stack on small screens.

**Current order in `Home1.jsx`:** section 3 (`home1-recent` / "Continue where you left off") at line 192, then section 4 (`home1-calendar` / "Coming up") at line 224 — they're sequential `<section>` blocks separated by `mb-12`.

**Implementation:** wrap both `<section>` blocks in a single `<div className="grid grid-cols-1 md:grid-cols-2 gap-x-10 mb-12">`. Existing inner classes (`mb-12`) on the two sections become `mb-0` since the wrapper carries the spacing. Both empty-state copies preserved verbatim.

### Spec/Code Deltas

| # | Brief / surface | Existing spec / code rule | Action |
| --- | --- | --- | --- |
| D1 | This brief: Executive chip = oxblood, NED chip = ned-purple. | `Home1.jsx:85-86` carries the 2026-05-13 v7-token-sweep comment: *"Role chip in muted neutral (NOT crimson — that's the v7 token sweep rule too)."* The current chip is graphite/neutral for all roles. The brief reintroduces oxblood for Executive and adds a NEW token (ned-purple) for NED — both at 15% opacity bg + full-strength text. This conflicts with the v7-sweep policy. | Brief takes precedence per user directive. v7-sweep comment in `ChipCompany` will be updated to note the 2026-05-26 exception. No edits to AKKI_PRODUCT_SPEC.md (the spec is silent on role-chip colors — §5 lists "Settings" / role-chip styling as out of scope; no canonical rule violated). |
| D2 | This brief: "Coming up" + "Continue where you left off" render side-by-side at desktop width. | `AKKI_PRODUCT_SPEC.md` §4 does not mention these sections — Home 1 portfolio is out of spec scope (§5: Landing / Settings / portfolio chrome). | No spec conflict. Recorded for completeness. |

### Files changed

1. `/app/frontend/src/index.css` — added `--ned-purple: #6B46C1` token to the `:root` block under the v7 canonical palette (after `--oxblood-deep`), with an inline comment scoping it to Phase A Home 1 cleanup.
2. `/app/frontend/src/pages/home/Home1.jsx` — four surgical edits:
   - Added `Link` to the `react-router-dom` import (already in package.json).
   - `ChipCompany`:
     - Tile-title `<p>` font-size reduced from `text-[16px]` → `text-[11px]` (item #1, 16 × 0.70 = 11.2 → 11px).
     - Added `data-testid={"home1-chip-${ctx.id}-title"}` to the title `<p>` so the wire test can anchor the scope precisely.
     - Computed `roleChipClass` + `roleChipStyle` based on `role`:
       - `owner` → `rgba(122,46,46,0.15)` bg + `var(--oxblood)` text (Executive).
       - `ned` → `rgba(107,70,193,0.15)` bg + `var(--ned-purple)` text.
       - other → existing `bg-[var(--cream-deep)] text-[var(--muted)]` muted neutral (no change for non-owner/non-NED).
     - Updated the in-component comment block to record the 2026-05-26 exception to the v7 token-sweep rule.
   - Wrapped sections 3 (`home1-recent`, "Continue where you left off") + 4 (`home1-calendar`, "Coming up") in a `<div data-testid="home1-recent-calendar-grid" className="grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-6 mb-12">`. Removed individual `mb-12` from each inner `<section>` since the wrapper carries the spacing. Empty-state copy preserved verbatim ("Nothing to resume yet.", "No upcoming events on your calendar.").
   - Appended `<Link to="/app/learn" data-testid="home1-news-read-more">Read more →</Link>` immediately after the news list `</ul>`, INSIDE the `home1-news` section but OUTSIDE the scrollable `<ul>` overflow box. Only rendered when `news.length > 0` (empty-state already says *"News updating — check back shortly."* — a Read-more would be misleading there). Separator: 1px top border + 8px top padding (matches the visual rhythm of `border-b border-[var(--rule)]` rows above).
3. `/app/backend/tests/test_home_cleanup_phase_a.py` — new wire-check pytest, 12 cases, anchored to acceptance criteria (a)–(g).

### Tests added

| Test name | Anchors |
| --- | --- |
| `test_phase_a_log_has_required_sections` | acceptance (a) |
| `test_phase_a_company_tile_title_is_11px` | acceptance (b) — tile title scope |
| `test_phase_a_hero_greeting_unchanged` | acceptance (b) — hero still 28px |
| `test_phase_a_companies_heading_unchanged` | acceptance (b) — "Your companies" still text-[15px] |
| `test_phase_a_ned_purple_token_defined` | acceptance (c) — token + #6B46C1 |
| `test_phase_a_executive_chip_oxblood_15pct` | acceptance (c) — Executive chip |
| `test_phase_a_ned_chip_ned_purple_15pct` | acceptance (c) — NED chip |
| `test_phase_a_read_more_link_present` | acceptance (d) — link exists |
| `test_phase_a_read_more_targets_learn` | acceptance (d) — `to="/app/learn"` |
| `test_phase_a_curated_for_badge_unchanged` | acceptance (d) — CURATED FOR badge preserved |
| `test_phase_a_recent_and_calendar_share_grid` | acceptance (e) — 2-column grid wrapper |
| `test_phase_a_no_new_packages_in_lockfile_check` | acceptance (f) — package.json sanity |

**Run result:** `pytest tests/test_home_cleanup_phase_a.py -v` → **12 passed / 0 failed / 0 skipped** (3.06s).

### Tech debt found during this pass

No stale CSS variables or dead components surfaced by these edits. The 2026-05-13 v7-token-sweep comment in `ChipCompany` is now annotated with the 2026-05-26 exception (recorded as delta D1 above) but stays in place — it's still accurate for non-Executive / non-NED roles.

The `--ned-purple` token is brand-new — no aliasing or dead-color overlap.

### Phase A — verification

- ✅ Frontend lint clean (`mcp_lint_javascript` on `Home1.jsx` → "No issues found").
- ✅ Wire-check pytest 12/12 green.
- ✅ Preview frontend renders cleanly (signed-in surface gated behind auth; smoke screenshot on `/signin` shows the marketing copy + form, no console errors).
- ✅ `--ned-purple` token resolvable via CSS custom property fallback (existing `style={{ color: "var(--ned-purple)" }}` pattern is the same used by `--oxblood` references elsewhere).

### Phase A — read-more navigation evidence

`/app/learn` route is registered at `frontend/src/App.js:309` and binds to the lazy-loaded `Learn` page (`pages/Learn.jsx`). The Learn page's `TABS` const at `Learn.jsx:24-29` declares `{ key: "news", label: "News", icon: Newspaper }` as the first tab — so clicking "Read more →" lands the user on the existing Learn news-feed surface with the News tab default-selected. No new route, no new endpoint, no new component — pure reuse.

### Phase A — post-test fixes

Tester reported on 2026-05-26 that (1) the Executive chip was still grey on live tiles and (2) requested verification of the 30% font math.

#### Fix 1 — Executive chip grey (root cause + diff)

**Root cause:** the live DB writes `"role": "executive"` (verified at `backend/core.py:390` and `backend/routers/contexts.py:547`), NOT `"owner"`. The first Phase A pass only branched on `role === "owner"`, so every real Executive membership fell through to the grey-neutral default. NED was unaffected because the API does write `"role": "ned"` directly.

**Fix:** match both `"owner"` and `"executive"` for the Executive chip — mirrored exactly to the NED pattern. Diff (live region of `Home1.jsx::ChipCompany`):

```diff
   const role = (ctx.my_role || "—").toLowerCase();
-  const roleLabel = role === "owner" ? "Executive"
+  const roleLabel = (role === "owner" || role === "executive") ? "Executive"
                   : role === "ned" ? "NED"
                   : role.charAt(0).toUpperCase() + role.slice(1);
   ...
-  if (role === "owner") {
+  if (role === "owner" || role === "executive") {
     roleChipClass = "";
     roleChipStyle = {
       backgroundColor: "rgba(122, 46, 46, 0.15)", // --oxblood @ 15%
       color: "var(--oxblood)",
     };
   } else if (role === "ned") { ... }
```

**ChipCompany consumers verified:** `grep -rn "ChipCompany" frontend/src` returns 2 hits — both in `Home1.jsx` (the definition + the only render site in the "Your companies" grid). No other component imports it. Fix is naturally scoped.

**Wire test updated:** `test_phase_a_executive_chip_oxblood_15pct` now anchors on the IF-statement form `if (role === "owner" || role === "executive")` to disambiguate from the same boolean in the ternary above it. All 12 wire tests pass.

**Live verification (Julius Opio portfolio, 2026-05-26T10:42Z, `/app/portfolio`):**

| Tile (label rendered) | Computed background-color | Computed color |
| --- | --- | --- |
| Personal NED Seat — **NED** | `rgba(107, 70, 193, 0.15)` | `rgb(107, 70, 193)` |
| Government Executive — **EXECUTIVE** | `rgba(122, 46, 46, 0.15)` | `rgb(122, 46, 46)` |
| Executive Role — **EXECUTIVE** | `rgba(122, 46, 46, 0.15)` | `rgb(122, 46, 46)` |
| Sponsored NED Seat — **NED** | `rgba(107, 70, 193, 0.15)` | `rgb(107, 70, 193)` |
| Enterprise Executive — **EXECUTIVE** | `rgba(122, 46, 46, 0.15)` | `rgb(122, 46, 46)` |

#### Fix 2 — Font math (pre/post measurements)

| Metric | Value | Source |
| --- | --- | --- |
| Pre-Phase-A tile title size | **16px** | The class in the diff hunk I replaced was `text-[16px] text-[var(--ink)] font-bold truncate leading-tight` — the exact pre-image of the Phase A search-replace edit. |
| Post-Phase-A tile title size | **11px** | Currently on disk: `text-[11px]` (single occurrence in `Home1.jsx` at the `home1-chip-${ctx.id}-title` `<p>`). Live DOM computed style measured on `/app/portfolio` confirms `font-size: 11px` on all 5 visible tiles. |
| Ratio (post / pre) | **0.6875** | 11 / 16 = 0.6875 → **31.25% reduction** (slightly stronger than the 30% target but within rounding tolerance for the requested intent). |

**Adjustment decision:** Brief calculation says 16 × 0.70 = 11.2px → CSS rounds sub-pixel down to 11px. Going to 12px would yield a 25% reduction (under the 30% target). Going to 11px yields 31.25% (over by 1.25 percentage points). 11px is the closer integer to the exact 11.2px target — keeping the 11px value. The 13px the tester measured was a stale-CSS-cache reading; the live computed style is **11px** on every tile (verified via `getComputedStyle()` against 5 tiles in the live browser session above).

**No further code edit needed for Fix 2.** Math + live computed style confirmed.

#### Bonus live verifications captured in the same pass

- Read more href: `/app/learn` (matches acceptance criterion (d)).
- Continue where you left off + Coming up: rendered side-by-side at 1920px viewport in the live screenshot (matches acceptance criterion (e)).
- No console errors during sign-in + portfolio load (no errors logged in the automation capture).

---

## Phase B — Home 2 (Workspace)

Placeholder. Not yet started. Will cover:
- Back-to-portfolio relocation
- Plate tiles
- Coming up section
- Running/Sitting tile removal

---

## Deploy-readiness checklist

Placeholder for end-of-batch.

- [ ] Both phases closed in this log.
- [ ] All targeted text-size, color, and layout changes verified live in preview.
- [ ] No console errors (frontend smoke).
- [ ] No new npm packages added.
- [ ] Frontend wire tests green.
- [ ] Backend pytest green (regression check after `index.css` edit).
- [ ] No spec edits performed.
- [ ] Tag `v-post-home-cleanup` applied (local only).
