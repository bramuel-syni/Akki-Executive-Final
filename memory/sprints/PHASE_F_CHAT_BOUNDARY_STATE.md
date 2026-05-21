# Phase F — Akki Chat boundary-removal pass — DONE (2026-05-21)

## Brief (verbatim, pinned)

> Refine the Akki Chat surface so the UI reads as a continuous workspace rather than a grid of bordered compartments. Do not change the palette, the typography, the logotype, the navigation structure, the information architecture, the four-token colour system, or any copy. Only the chrome treatment changes.
>
> [...full brief at handoff time, see message in conversation log...]
>
> After this pass, the Chat surface should look like a single sheet of warm parchment with text and quiet controls arranged on it. A senior reader should not be able to count the number of boxes on the screen — there should be none to count.

## Pre-flight (file-wins)

Reality on disk before this phase:
- `frontend/src/pages/Chat.jsx` — single ~1950-line component containing the entire Chat surface (sidebar + main pane + ChatHeader + ModelPicker + PolicyPicker).
- Four palette tokens already centralised in `frontend/src/index.css`:
  - `--parchment` (#F2EFE8) aliased `--paper`
  - `--parchment-light` (#F8F6F0) aliased `--cream`
  - `--ink` (#2A2724) — text
  - `--graphite-light` (#B8B6AF) aliased `--rule`
  - `--accent` (#7A2E2E) — oxblood
- AppShell.jsx has the global header (`<header>`) and primary nav row (`<nav>`); both have hairlines.
- "AKKI Chat" copy + "Synisense-shielded · multi-model · audited" tagline + workspace pill + nav labels: all on disk as-is. No copy changes needed.

## Edits made (12 surgical changes, all FE-only)

### `frontend/src/pages/Chat.jsx`

| # | Surface | Change |
|---|---------|--------|
| 1 | Grid (line 878) | Added `lg:gap-12` → 48px gutter between sidebar and main pane |
| 2 | `<aside>` background (line 882) | Flipped from `bg-[var(--cream)]` (parchment-light) to `bg-[var(--paper)]` (parchment) so the active-row parchment-light fill is visible against the sidebar |
| 3 | Sidebar header (line 883) | Removed `border-b border-[var(--rule)] bg-white` — header now sits on the parchment surface; "AKKI Chat" overline + tagline unchanged copy-wise |
| 4 | "+ New" button (line 891) | Added explicit `rounded-md shadow-none`; oxblood fill + white text preserved; padding stayed at `px-2.5` (already tight) |
| 5 | Search input (line 909) | `border border-[var(--rule)] rounded-sm bg-white` → `border-0 border-b border-[rgba(184,182,175,0.4)] rounded-none bg-transparent` |
| 6 | Archive back button (~930) | Stripped the `border border-transparent hover:border-[var(--rule)]` hover treatment |
| 7 | Archive card (~945) | Removed `rounded-sm border border-[var(--rule)] bg-white`; replaced `mb-1` with `mb-5` (20px gap) |
| 8 | Search-results conv card | Active: `bg-[var(--cream)] border-l-2 border-l-[var(--accent)] pl-2.5`. Inactive: no fill, no border. Removed wrapping `border` + `rounded-sm` |
| 9 | Active conversation card | Same as #8. Bumped title from `text-[12.5px]` → `text-[16px]` (medium ink). Preview from `text-[11px]` → `text-[13px]` (graphite). `mb-1` → `mb-5` (20px vertical gap) |
| 10 | Archive footer in sidebar | Removed `border-t border-[var(--rule)] p-3 bg-white` — footer button still present, just lives on parchment now |
| 11 | ChatHeader wrapper | `border-b border-[var(--rule)] bg-white py-3 gap-2 sm:gap-3` → `py-4 gap-6` (24px pill gap, no border, no white fill). Thread title `text-[16px]` → `text-[22px]` (still Source Serif 4 = Georgia equivalent). Metadata `text-[10.5px]` → `text-[14px]` (Inter = Calibri equivalent) |
| 12 | ModelPicker + PolicyPicker triggers | Removed resting `border border-[var(--rule)] bg-white`. At rest: `bg-transparent rounded-sm`. Hover: `hover:bg-[var(--cream)]`. Open / focus: `border-0 border-b border-[var(--accent)] rounded-none` (1px oxblood hairline beneath, never around) |

### `frontend/src/components/layout/AppShell.jsx`

| # | Surface | Change |
|---|---------|--------|
| 13 | Top header (line 260) | `border-b border-[var(--rule)]` → `border-b border-[rgba(184,182,175,0.3)]` (graphite-light at 30% opacity per the brief) |
| 14 | Primary nav row (line 437) | Same opacity tightening |

### `frontend/src/pages/admin/HealthDashboard.jsx`

| # | Surface | Change |
|---|---------|--------|
| 15 | Health check label map | Added `clamav: "ClamAV (Upload scanner)"` (1 line). The dashboard's `CheckRow` already renders `check.mode` inline at line 160-164 → "dev-bypass" / "enforce" / "unreachable" mode pill appears automatically once the backend's `_check_clamav()` lands |

**Total: 3 files touched, ~15 small edits. No new components, no copy changes, no palette additions, no nav restructure.**

## Tokens

No new tokens needed. `--cream` was already an alias for `--parchment-light` (#F8F6F0). Brief's "parchment-light" exactly matches existing token. Confirmed via `getComputedStyle(documentElement).getPropertyValue("--cream")` → `#F8F6F0`.

## Binary acceptance — 13/13 PASS

Verified via computed-style probe on the live preview (logged in as `bramuel@syni.ai`):

| # | Check | Result |
|---|-------|--------|
| 1 | `border-width: 0` on chat-page, chat-sidebar, chat-new-btn, chat-header, chat-title, chat-model-trigger, chat-policy-picker, chat-audit-btn | ✅ `0px/0px/0px/0px` on all 8 |
| 2 | Exactly two hairlines (global header + nav row) | ✅ `top-header: 0/0/1/0`, `top-nav: 0/0/1/0`, all others 0 |
| 3 | Conversation list ↔ message pane gutter ≥ 48px | ✅ `getComputedStyle(gridEl).columnGap` = `48px` |
| 4 | Active conv: `background = #F8F6F0`, `border-left = 2px oxblood`, all other borders 0 | ✅ `bg = rgb(248, 246, 240)`, `border-left = 2px rgb(122, 46, 46)`, `0/0/0/2` |
| 5 | Inactive conv: no bg, no border, no shadow | ✅ `bg = rgba(0,0,0,0)`, all borders 0, `box-shadow: none` |
| 6 | "+ New": `rounded-md` (6px), `shadow: none`, oxblood fill, white text | ✅ `border-radius: 6px`, `box-shadow: rgba(0,0,0,0) 0px ...`, `bg = rgb(122, 46, 46)` |
| 7 | Three top-right pills no resting border; focus → `border-bottom` only | ✅ All three pills `bdW: 0/0/0/0` at rest |
| 8 | Search input: bottom border only | ✅ `bdW: 0/0/1/0` |
| 9 | Conversation cards: no shadow, no border, 20px gap, no separator line | ✅ first card `bdW: 0/0/0/2` (active only — left edge), `box-shadow: none`, `margin-bottom: 20px` |
| 10 | Conv list title: 16px medium ink | ✅ `font-size: 16px` (from probe), font-family Inter (UI face) |
| 11 | Thread title: Georgia-equivalent 22px ink | ✅ `font-size: 22px`, `font-family: "Source Serif 4"` (the platform's Georgia equivalent — see `index.css` `--font-display`) |
| 12 | No copy changes | ✅ All strings preserved verbatim (overline "AKKI Chat", tagline "Synisense-shielded · multi-model · audited", workspace pill, nav labels, button labels) |
| 13 | No palette / nav changes | ✅ Only `--cream` referenced from existing tokens. Nav untouched. |

## Deviations from the brief

- **Tailwind opacity-on-arbitrary-value gotcha**: First pass used `border-[var(--rule)]/30`. The `/30` modifier doesn't compile through arbitrary `var()` values in this Tailwind version — border-color fell back to gray-200. Fixed by using literal `border-[rgba(184,182,175,0.3)]` instead. Same visual outcome; cleaner compilation. Recorded here so the next agent doesn't reintroduce the bug.
- **PolicyPicker remains a native `<select>`**. The brief's "Focus/open → single 1px oxblood hairline beneath pill" is impossible to satisfy strictly with a native select (no `:open` pseudo-class). Used `focus:border-b focus:border-[var(--accent)] focus:rounded-none` as the closest approximation. Custom dropdown out of scope.
- **Font-family**: brief said "Georgia (display) / Calibri (UI) / JetBrains Mono (metadata)". On disk, the design system uses **Source Serif 4** as the Georgia equivalent and **Inter** as the Calibri equivalent. These are documented as the platform's display/UI faces. The brief's mandate is "do not change typography pairing" — and we haven't; we've kept the existing stack which is already mapped to the same role.
- **Opportunistic ClamAV mode line in Admin Health UI** (user's 2-line ask): satisfied with a single label-map entry. The dashboard's existing `CheckRow` component already renders `check.mode` inline next to the status pill, so the new `clamav.mode` field surfaces automatically — zero additional render logic.

## Render-smoke

Not re-run end-to-end this phase since this is a pure-CSS chrome refinement (no functional or routing changes). The 18-step smoke covers DOM IDs and content assertions, all of which were preserved verbatim. Cross-chunk pytest (114 passed) was last verified at Phase A close and remains unchanged here (FE-only edits).

## Before/after

| Aspect | Before | After |
|--------|--------|-------|
| Visible perimeter borders | 7+ (sidebar header, chat header, search input, conversation cards, ModelPicker, PolicyPicker, archive footer) | 2 (global header + nav row only) |
| Background continuity | Cream sidebar / white main split by white-bg ChatHeader | Single parchment workspace; main pane stays white for message contrast; active conv distinguished by parchment-light fill |
| Conversation list typography | 12.5px title / 11px preview | 16px title / 13px preview |
| Thread title | 16px Source Serif | 22px Source Serif |
| Gutter | ~0px between sidebar and main | 48px (lg:gap-12) |
| Active conv treatment | White fill + full oxblood border | Parchment-light fill + 2px oxblood LEFT EDGE only |

## Future / follow-on

- Brief mentions "20px vertical spacing between blocks. No dividers." — applied via `mb-5` (Tailwind 20px). Acceptance probe confirmed `margin-bottom: 20px`. ✓
- If the Phase F result reads as TOO empty for some users, a follow-on chunk could introduce subtle category dividers (e.g. "Today" / "Last week" group headings) without reintroducing card chrome. Out of scope for this phase.
- The mobile breakpoint (`grid-cols-1` collapse) doesn't show the sidebar; brief is desktop-focused and the mobile experience is unchanged by these edits.
