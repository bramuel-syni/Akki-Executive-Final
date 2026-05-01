# HOME_AUDIT.md — Phase 5 Part A (read-only audit)

**Scope:** `/app/frontend/src/pages/AppHome.jsx` (current Home) + `/app/frontend/src/components/home/*` (8 cards) + `/app/frontend/src/components/layout/AppShell.jsx` (top bar / left rail) + `/app/backend/routers/shares.py` `GET /api/me/home/stream` + `/app/frontend/src/contexts/AuthContext.jsx`.
**Goal:** map what exists and what must be preserved before rebuilding Home as a "river of changes" behind `?home=v2`.

---

## A1 · Current Home inventory (`AppHome.jsx`, 551 lines)

### Top-of-page (always visible once onboarded)

| # | Section | Lines | Shows | Data source | Category |
|---|---------|-------|-------|-------------|----------|
| 1 | **Greeting line** ("Good morning, <first>.") | 157–159 | Time-of-day salutation | `account.name` | Cosmetic — keep |
| 2 | **ContextChooser** | 168–177, 325–474 | Inline context/role picker; intro line counting NED vs Exec boards; chip-row of contexts; role toggle (NED/Exec) when user has both. Single-context case shows a "soft lead" line with the most interesting signal/briefing/document | `useAuth()` state + in-memory `signals/briefings/documents` from the same fetch | **Load-bearing** — only role-switching surface outside PortfolioRail |
| 3 | **CycleStrip** | 180–184 | Phase 2 horizontal 6-phase strip, pinned below the chooser | `GET /api/contexts/{cid}/cycle-config` | **Load-bearing (Phase 2 contract)** — must keep |

### First-time user gate (returns early at 122–148)

If `!isDeclared || !auditComplete` → renders a single "Next · 7 minutes" card with "Begin audit" button linking to `/app/first-session`. With Phase 4's FirstSessionGuard this branch is almost unreachable in practice (guard redirects earlier), but the fallback still exists.

### Mid-page (conditional / sandbox / first-run)

| # | Section | Lines | Shows | Data source | Category |
|---|---------|-------|-------|-------------|----------|
| 4 | **SandboxTutorial** | 190 | First-run guided card for sandbox users; auto-dismisses | `GET /api/sandbox/contexts/{cid}/tutorial` | Sandbox-only — leave alone (sandbox scope out of Phase 5) |
| 5 | **ObjectiveCheck** | 194 | 24h follow-up for sandbox objective | `GET /api/sandbox/contexts/{cid}/objective-check` | Sandbox-only — leave alone |
| 6 | **SandboxSampleDoc** | 200 | Proactive sample pack offer | sandbox | Sandbox-only |
| 7 | **SandboxPackDrop** | 204 | Drop-your-own-pack affordance | sandbox | Sandbox-only |

### Draggable board (`DraggableHomeBoard`, 485–548)

Three rearrangeable sections, order persisted to `localStorage: akki:section-order:home`:

| # | Card | File | Shows | Data source | Category |
|---|------|------|-------|-------------|----------|
| 8 | **InSummaryTiles** | `components/home/InSummaryTiles.jsx` (260 lines) | 6 tiles: Signals, Briefings, Reporting, Reports, Documents, Portfolio — each a hero number + 3 attribute lines | 7 per-context endpoints: `/signals`, `/briefings`, `/submissions`, `/checklists`, `/documents`, `/reports`, `/members` | **Metrics dashboard — remove from v2 Home** (belongs in /workspace or a dedicated /insights surface) |
| 9 | **WorkflowsHub** | `components/home/WorkflowsHub.jsx` (105 lines) | Compact tab-switcher hosting 5 inner cards (see below); auto-picks the most-urgent tab | `GET /api/contexts/{cid}/plays` + `GET /api/me/inbound-queue/counts` | **Feature-discovery noise on Home — move/trim** |
| 10 | **ReviewInboxCard** | `components/cycle/ReviewInboxCard.jsx` | Phase-B review-inbox card (legacy cycle review UI, pre-Daily-Review) | cycle-report endpoints | **Redundant** — Phase 3's Daily Review + ReviewBadge supersede it. Candidate for removal on v2 |

### WorkflowsHub sub-cards (via tabs inside #9)

| Tab | Component | File | Shows | Category |
|-----|-----------|------|-------|----------|
| `actions` | **QuickActions** | `QuickActions.jsx` (~220 lines) | Dynamic tile dock — Upload pack / Generate signals / Draft briefing / Run Lens / Run Simulate / Start cycle — ranked by `priority(state)` | Feature-discovery — belongs on `/app/workspace` or empty state |
| `ready` | **PlayReadyCards** | `PlayReadyCards.jsx` | Auto-launched-but-unseen Plays | Moved to Plays library (`/app/plays`) |
| `agenda` | **AgendaEvolutionCard** | `AgendaEvolutionCard.jsx` | "What happened since last meeting" editorial line items from last report + submissions + checklists + briefings | Candidate: **stream entries** (weave into river) |
| `active` | **PlaysInProgressStrip** | `PlaysInProgressStrip.jsx` | Chips for active/paused Plays | Moved to `/app/plays` |
| `inbound` | **InboundQueueCard** | `InboundQueueCard.jsx` | Pending inbound-email count + byContext breakdown | **Superseded by Daily Review** — route to `/app/review` |

### Bottom-of-page

| # | Section | Lines | Shows | Category |
|---|---------|-------|-------|----------|
| 11 | **RecentActivity** | 215–225, `RecentActivity.jsx` (217 lines) | 5 category cards (Briefings & meetings, Questions answered, Signals surfaced, Documents added, Sent your way), each "kicker + count + most-recent title + view timeline →". Takes `signals/briefings/documents/shared/briefs` from AppHome's own fetch + scope toggle (current vs all boards) | **Closest existing thing to a river-of-changes** — the v2 Home should essentially replace this block and promote it to the main column |

### Data fetched per render (AppHome `load()` lines 57–92)

- **Scope = all boards:** `GET /me/home/stream?limit=20` + `GET /me/shares/inbox?limit=30`
- **Scope = current context:** `GET /contexts/{cid}/signals`, `.../briefings`, `.../documents`, `.../briefs?limit=50`, + shares inbox.
- **No context:** just shares inbox.

All of the above is tripped again every time `contextId` or `scope` changes. No debounce, no caching.

---

## A2 · Phase 2/3/4 integration points on Home

- **Phase 2 — CycleStrip** mounted at `AppHome.jsx:180–184`. Props: `contextId`, `isMobile`. Data: `GET /api/contexts/{cid}/cycle-config`. Must remain pinned at the top of v2 Home.
- **Phase 3 — ReviewBadge** lives in the **top bar**, not on Home (`AppShell.jsx:205`). Polls `GET /api/me/review-queue/counts` every 60s + on focus. v2 Home doesn't need to render it — just leave AppShell alone. Per the brief a right-rail "Awaiting your approval" pinned queue is optional; it would read the same endpoint.
- **Phase 4 — FirstSessionGuard** wraps every `/app/*` route in `App.js`. `/app` (AppHome) is behind `<Gated>`. If `account.first_session.status ∈ {not_started, in_progress}` the guard redirects to `/app/first-session`. The v1→v2 flag has to live **inside** `AppHome.jsx` (or a thin wrapper) so the guard still fires before we hit the stream. Also: legacy `AppHome.jsx:139` still has an in-page fallback link to `/app/first-session` for the (now-unreachable) `!isDeclared || !auditComplete` branch.
- **No other prior-phase hooks on Home.** Reading Viewer (Phase 1) doesn't touch Home; Daily Review (Phase 3) only contributes the top-bar badge.

---

## A3 · Backend stream endpoint — `GET /api/me/home/stream`

**File:** `/app/backend/routers/shares.py:403–454`.

**Params:** `limit: int = 30` (capped at 100 internally).

**Auth:** cookie (`get_current_account`).

**Returns:**
```
{
  "signals":   [ { ...signal_doc, context_name } ]  // sorted created_at desc, status != archived
  "briefings": [ { ...briefing_doc, context_name } ]  // sorted created_at desc, status == active
  "contexts":  [ { id, name, type } ]                 // every active context the user is a member of
}
```

**Aggregation:** one sweep each of `db.signals` and `db.briefings` restricted to the user's active context ids, then in-Python decoration of `context_name`. **No merged+sorted merged stream is returned** — the frontend has to interleave signals/briefings itself (which `RecentActivity` already does in-memory).

**Pagination:** `limit` only. No cursor, no `?since=`, no per-kind filter. For the v2 river we'll likely need a `?cursor=<iso_ts>` or similar — but that's a **non-breaking additive extension**.

**Collections NOT currently aggregated that a river-of-changes needs:**
- `db.documents` (new uploads) — exists per-context via `/contexts/{cid}/documents`, not in the aggregate stream.
- `db.inbound_queue` (unknown-sender email arrivals) — per-account via `/me/inbound-queue`.
- `db.briefings` items `awaiting_approval` — already surfaced by `/me/review-queue`.
- Mentions — per-account via the `/mentions` endpoint (not audited today; used by `MentionInbox`).

**Recommendation for v2:** extend with `documents[]` + `approvals[]` + optional `cursor`, keep `signals[]` / `briefings[]` / `contexts[]` unchanged for v1 callers (legacy `RecentActivity` + `AppHome`).

---

## A4 · Top bar inventory (`AppShell.jsx:159–263`)

| Position | Element | Lines | Notes |
|----------|---------|-------|-------|
| Left | `<Logo>` — "AKKI · for Executives" linking to `/app` | 164–169 | Keep |
| Centre | Trust micro-badge: "Internal · Secure · Confidential" | 171–180 | Decorative, 10px overline — keep |
| Right | **ContinueWithPill** (Tier-B — last-opened doc pill) | 186 | Cosmetic, hides itself on many surfaces. Keep |
| Right | **⌘K Search button + kbd hint** | 189–197 | Keep |
| Right | **MentionInbox** bell | 200 | Existing, pulls `/mentions` |
| Right | **ReviewBadge** (Phase 3) | 205 | Phase-3 contract — keep |
| Right | **Account avatar dropdown** (Settings / Account security / Sign out) | 212–261 | Keep |

**Top-bar nav today is LEFT-RAIL, NOT HORIZONTAL.** All of `Home · Workspace · Chat · Solve · Catch-up · Decks + Reports · Lens · Test Hypothesis · Reporting Cycle · Monitor · Learn · Influence Map` lives in the 220 px left sidebar (`AppShell.jsx:277–354`), with a `+ Add document` oxblood pill at the top of that sidebar.

**Delta vs rules-doc target (`Home · Workspace · Cycle · Studio · Chat`):**
- Target is a **horizontal top-bar nav**, 5 items.
- Today ships a **vertical left-rail nav**, 12+ items with 2 housekeeping links + sponsored-upsell block.
- `Studio` label doesn't exist in nav today — closest is `Decks + Reports` (`/app/decks`). `/app/studio` route exists but isn't in primary nav.
- `Cycle` is there as `Reporting Cycle`.
- `Chat` is there as `Chat`.

**Per the brief the top bar "leave alone" instruction wins** → I will NOT touch the top bar or left rail in Part B. The rules-doc target is a separate, larger navigation rework that will need its own phase.

**Right side:** `PortfolioRail` (`AppShell.jsx:269`) is a sticky right-rail that's collapsed by default (48 px sliver), expandable to show contexts + role toggle. It pushes main content with `lg:pr-[48px]`. The left-side "left rail (240px)" requested for v2 Home is a **new** piece; I'll add it in the Home v2 main column, not in AppShell, so the existing 220-px nav rail + 48-px portfolio rail are untouched.

---

## A5 · What to keep / move / remove for Home v2

### KEEP (they belong on a river-of-changes Home)

1. **Greeting line** (small, typography-led) — quiet editorial line.
2. **CycleStrip** pinned at top (Phase 2 contract — non-negotiable).
3. **ContextChooser (role toggle only)** when the user has both NED and Executive roles — the "where am I" moment. In v2, fold into the left Context-rail with the chip list.
4. **RecentActivity (conceptually)** — but rebuilt as a proper merged reverse-chronological river rather than 5 category cards.
5. **Shared with you / mentions** — as a stream category (using the same `/me/shares/inbox` + `/mentions` data).

### MOVE (feature-discovery, not change-tracking)

6. **InSummaryTiles** → `/app/workspace` (or future `/app/insights`). Dashboard-style numbers belong in a reporting surface, not on Home.
7. **WorkflowsHub → QuickActions** tab → stay on `/app/workspace` or become the empty-state CTA on v2 Home.
8. **WorkflowsHub → PlayReadyCards / PlaysInProgressStrip** → `/app/plays` (they're Play-library concerns).
9. **WorkflowsHub → AgendaEvolutionCard** → derive its content into stream entries (each submission / report / checklist IS a change event; the agenda card was already a reverse-chronological summary).
10. **WorkflowsHub → InboundQueueCard** → `/app/inbound-queue` already exists, plus the Daily Review badge covers the "attention required" part.

### REMOVE

11. **The entire `WorkflowsHub` wrapper** (the tabs-on-tabs with counts is gamification-adjacent noise per the rules doc).
12. **ReviewInboxCard** (superseded by Daily Review + ReviewBadge).
13. **DraggableHomeBoard** wrapper + the `akki:section-order:home` localStorage toggle (invented flexibility; the v2 Home has one canonical order).
14. **`NextBestActionCard`** (defined at 271–311 but not actually rendered anywhere in the current file — dead code). Confirmed by grep: no JSX usage.
15. **First-time-user gate** fallback (122–148) — Phase 4's FirstSessionGuard makes this unreachable. Clean it up while we're in here.
16. **The `scope` toggle (current vs all boards)** — v2 Home IS the cross-board river by default. Per-context view lives on `/app/workspace?context=<cid>`.

---

## A6 · Risks

1. **CycleStrip contract.** Phase 2 ships a mobile-aware Cycle strip on Home. Any v2 that doesn't re-mount it breaks the Phase 2 acceptance test. Mitigation: mount it at the top of v2 Home unchanged.
2. **FirstSessionGuard timing.** The `?home=v2` flag must be read **inside** the gated route, after the guard has fired. If we switch pages based on the URL query before the guard, a brand-new user could hit v2 Home instead of being redirected to `/app/first-session`. Mitigation: keep `AppHome` as the routed component; branch internally on `new URLSearchParams(location.search).get("home") === "v2"`.
3. **ReviewBadge coupling.** The top bar is untouched; ReviewBadge keeps working because it's in `AppShell`, not Home. No risk there.
4. **Sandbox users land on Home.** `SandboxTutorial`, `ObjectiveCheck`, `SandboxSampleDoc`, `SandboxPackDrop` render only when `account.is_sandbox === true`. Removing them from v2 Home would break sandbox onboarding (users wouldn't see the sample-pack offer or the drop-zone). Mitigation: either keep sandbox-branch unchanged (render sandbox cards above the river when `is_sandbox`), or explicitly scope v2 flag to non-sandbox until sandbox gets its own v2 treatment.
5. **Routes/links pointing TO Home from elsewhere expecting specific elements.**
   - Top-bar logo link → `/app` (generic landing, no element dependency).
   - `FirstSession.jsx` "Go to home" button → `/app`.
   - `FirstSession.jsx` done-state fallback → `/app`.
   - `AuthContext.switchRole()` (`AuthContext.jsx:156`) does a hard `window.location.assign("/app")` when roles change to re-anchor. This means a role-switch from deep in the app MUST leave v2 Home rendering cleanly even on first paint.
   - `/app/highlights` and `/app/briefings` 301-style redirect to `/app/prepare` (not Home — unaffected).
   - `/app/ask` redirects to `/app/workspace` — unaffected.
   - `DocumentRouteSwitch` (`App.js:73`) renders `ReadingView` for any `/app/documents/:id` — unaffected.
   - **No other code reads Home's DOM or its testids.** The ones defined (`home-nba-card`, `home-context-chooser`, `home-draggable-board`, etc.) are only referenced inside `AppHome.jsx` itself. Our prior-phase QA screenshots `p3_home_no_badge.png` etc. cared only that the top-bar review badge was absent/present — they don't care about card layout.
6. **InSummary tile fetches** currently trigger 7 per-context API calls on every Home visit. v2 must not re-do this (river only needs `/me/home/stream` + a small extension). Deleting `InSummaryTiles` from v2 Home is a **perf win**, not a regression.
7. **Scope toggle default.** Today's Home defaults to `scope="current"` and shows single-context sections. v2's cross-board river is a **semantic change**: users who anchored to the current-context view may feel the content shifted under them. Mitigation: because v2 is flag-gated (`?home=v2`) and the old surface stays default for a week, there is a full week of soak time before the flip.
8. **`/me/home/stream` contract.** Other callers? Grep inside `frontend/src`: the endpoint is only called from `AppHome.jsx:65`. No external dependencies. **Safe to extend additively** (new keys on the response, new optional query params). No breaking change required.

---

## Summary for orchestrator decision

**Ready to flip to Part B once you confirm the keep/move/remove table in A5.** Specifically need a yes/no on:

- [ ] Keep CycleStrip at top ✓ (must)
- [ ] Keep greeting + context rail (left 240 px) with chips ✓
- [ ] River cards: documents, signals, briefings, approvals-needed, mentions/shares ✓
- [ ] Optional right rail (320 px) "Awaiting your approval" pulling `/me/review-queue` — keep or drop?
- [ ] Drop InSummaryTiles, WorkflowsHub (and its 5 sub-tabs), ReviewInboxCard, DraggableHomeBoard wrapper, NextBestActionCard (dead), first-time-user fallback gate, the `scope` toggle?
- [ ] Sandbox users: v2 flag ignored for `is_sandbox` (sandbox cards keep rendering unchanged), or v2 applies to everyone and we weave sandbox cards into the river?
- [ ] Leave top bar + left rail untouched, do NOT attempt the "Home · Workspace · Cycle · Studio · Chat" top-bar rework in this phase?
- [ ] Backend: extend `/me/home/stream` additively with `documents`, `approvals`, `cursor` — or stick to the current shape and do frontend-only interleave with extra per-context fetches?

Nothing in Part B will ship until the above are confirmed.
