# VISUAL AUDIT — Follow-up Sprint §4

> Captured 2026-05-12 via Playwright + the in-pod screenshot tool.
> Login: `bramuel@syni.ai`. Viewport: 1920×1080. Quality 40 JPEG.
>
> Browser used a redirect that left us on the platform's `screenshot-cdn`
> domain rather than `akki-executive.preview.emergentagent.com`, so the
> first auto-redirect surface differs from the user's typical entry.
> All subsequent captures use explicit `/app/...` navigations.

## Surface-by-surface

### 1. Home 1 — Portfolio entry
**File**: `patch3_home1_portfolio.jpeg`
**URL captured**: `/app/portfolio`

Rendered sections visible:
- Greeting band: "Good morning, Bramuel." + portfolio overline
- Portfolio chips strip: 5 company chips (Carbon Industries Plc, Capricorn Investments PLC, Tuli Financial Group, Sherwood Investment, Personal NED Seat) with role chips + grey "no signal" health dots — per spec §3.1 #2
- "Continue where you left off" with History icon + empty-state copy
- "Coming up" Calendar peek — empty-state copy *"No upcoming events on your calendar."* (matches locked copy)
- "What's moving in your world" news strip with **CURATED · SAMPLE FEED** mock badge (per spec §3.1 #5 — MOCKED IN DEV)
- "New in AKKI" release notes card with 3 entries (Patch 2B.2, 2B.1, Cycle Manager v2)

### 2. Home 2 — Active-context home
**File**: `patch3_home2_active.jpeg`
**URL captured**: `/app`

Rendered sections visible:
- Greeting band: time-of-day + context name
- Hero copy band: *"Run the business on the left. Sit on the boards on the right."*
- HeroDocActions: `+ Add document` + `All documents` buttons (preserved from Patch 2A)
- Leading-insight Quick Action cards — **all 7 visible in 2-column grid**:
  - Sign-offs needed (urgency 5)
  - Cycles closing this week (urgency 4)
  - Compile report (urgency 3)
  - Open questions (urgency 2)
  - Solva sessions waiting (urgency 1)
  - New documents (urgency 0)
  - Pulse alerts (urgency 6)
- "What's new since your last visit" feed with empty-state *"You're all caught up since your last visit."*
- Running the business / Sitting on the boards footer split

### 3. Cycle Manager list
**File**: `patch2b1_cycle_manager_list.jpeg`
**URL captured**: `/app/cycle`

Rendered visible:
- Subtitle (locked verbatim): *"Cycle Manager is where you organise your team to produce collaborative outputs. Set the agenda, assign contributors, and commission Agent Cycle to follow up and keep readiness moving until you ship."*
- Quick Action bar (4 cards: Set up a Main Board · Answer Pending Questions · Project Proposal · Fund Raising)
- Filter tabs: ALL · ACTIVE · DRAFT · COMPLETED
- Search bar with `+ Add Agenda` button mounted in the controlsRight slot (parchment/ink primary style — NOT oxblood per spec)
- One cycle row rendered as a **full-width row**, single line:
  - Title: "Tuli Q1 Strategic Review"
  - Status badge (Closed)
  - Readiness numeral (JetBrains Mono + READINESS label)
  - Created date
  - Intel strip: `Agenda · 1 · Team · 0 · Last activity · 12h ago · Next · Closed`
  - Right chevron

### 4. Work Studio
**File**: `patch2b1_work_studio.jpeg`
**URL captured**: `/app/work-studio`

Rendered visible:
- Subtitle (locked verbatim): *"Shape board packs, decks, reports, and briefings. Agent Cycle compiles your work to executive cadence."*
- **6-tab line in exact order with NO "Cycle" prefix**:
  `Board Packs | Minutes | Committee Packs | Decks | Reports | Briefing`
- Active tab "Board Packs" with `Compile Board Pack` contextual action above the search/sort row
- **Universal Quick Action row absent** (removed per spec)
- **Status filter strip absent** (removed per spec)
- Search input + `MOST RECENT` sort selector
- Empty state with the new copy *"No board packs yet."*
- **Sticky right rail** (≥1100px viewport visible):
  - Primary CTA: `Compile a Report`
  - "Ready to compile" section → *"Nothing ready yet."*
  - "At risk" section with severity-tone header → *"Nothing at risk. Healthy queue."*

### 5. Monitor v2 — Objectives & Projects panel
**File**: `patch5_monitor_v2.jpeg`
**URL captured**: `/app/monitor`

Rendered visible:
- **Objectives & Projects** section at the TOP of the page (per Patch 5 spec #1)
- Kind toggle: `Objectives | Projects`
- ListingShell layout: search input + R/A/G filter tabs (`ALL · ON TRACK · AT RISK · OFF TRACK`)
- `+ Add objective` button in controlsRight slot
- Empty state: *"No objectives yet."*
- Below the panel: legacy "Strategic Goals" section preserved as the SECONDARY block per spec #2

### 6. Monitor v2 drawer with timeline visual
**File**: not captured.
**Reason**: The objective seeded via `POST /api/contexts/{cid}/monitor/objective` during the capture run landed in the user's `default_context_id`, but the live Monitor page reads from `useAuth().activeContext.id`, which resolved to a different context for the test account (auth/me returned `active: null` and an empty `contexts` array — the page's chip "Tuli Financial Group (CFO)" is sourced through the AuthContext path, not the bare `auth/me` payload). The drawer component is fully implemented (`/app/frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` lines 95–145 — `ItemDrawer` renders the vertical `<ol>` of `timeline_events` with the dot rail and oldest-at-bottom ordering), is wired to fire on `obj-row` click, and the backend payload supports the `timeline_events` array (verified via the seed POST returning `200` with the full chain present). A live capture requires seeding into the precise active context the screenshot session resolves to.

## Bug found and fixed during capture

**Cycle Manager list page was rendering an uncaught runtime error** — `addAgendaButton is not defined` — because a prior Patch 2B.1 `search_replace` to `/app/frontend/src/pages/cycle/CycleList.jsx` had silently failed to apply (tool reported "Edit was successful" but the source still carried the old `headerRight = (Button with oxblood)` block + `Add Cycle` label + `No cycles yet` empty state). Re-applied the edit during this capture run. CycleList now lints clean, hex-sweep clean, and renders correctly.

## File index

| Surface | File path |
|---|---|
| Home 1 portfolio | `/app/memory/visual_audit/patch3_home1_portfolio.jpeg` |
| Home 2 active-context | `/app/memory/visual_audit/patch3_home2_active.jpeg` |
| Cycle Manager list | `/app/memory/visual_audit/patch2b1_cycle_manager_list.jpeg` |
| Work Studio (6 tabs + rail) | `/app/memory/visual_audit/patch2b1_work_studio.jpeg` |
| Monitor v2 (Objectives & Projects) | `/app/memory/visual_audit/patch5_monitor_v2.jpeg` |
