# Backlog (post-autonomous-sprint candidates)

Items flagged during the Phase A → E autonomous sprint that did NOT
make the sprint scope. None of these are bugs; they're follow-on
opportunities the user owns the dispatch decision on.

## P2 — Design

### G-001: Extend Phase F boundary-removal to Cycle Manager / Monitor / Strategic Goals

- **Source**: Phase F close (2026-05-21). Phase F was scoped to the
  Chat surface only at user direction.
- **Rationale**: After Phase F, Chat reads as a continuous parchment
  workspace. Cycle Manager + Monitor + Strategic Goals still use the
  enclosed-card / `border border-[var(--rule)] bg-white` aesthetic,
  creating an inconsistent design language across the product.
- **Scope (estimated)**:
  - Cycle Manager: `frontend/src/pages/CycleManager.jsx` + briefing
    composer + agenda timeline
  - Monitor / Strategic Goals: `frontend/src/pages/Monitor.jsx` +
    `StrategicGoalsPanel.jsx` + `GoalDetailDrawer.jsx`
  - Same chrome rules as F: strip perimeter borders, prefer whitespace
    + single-edge hairlines + active-row left-edge accents
  - Re-use Phase F's `data-testid` + 30% opacity hairline pattern
- **Risk**: Medium — these surfaces have more interactive elements
  (drawers, modals, inline edits) than Chat, and the active-conv left-
  edge accent doesn't translate 1:1 to a goal-card grid layout.
- **Effort**: ~1.5x Phase F (3 surfaces vs 1).
- **Acceptance template**: Adapt Phase F's 13 binary checks per surface.

## P3 — Backlog

### G-002: Mobile breakpoint Chat polish (Phase F follow-on)

- **Source**: Phase F close note
- **Rationale**: Phase F was desktop-focused. Mobile collapses
  `grid-cols-1` and hides the sidebar; the de-chromed conversation
  list spacing rules may need re-tuning for portrait viewports.
- **Effort**: S

### G-003: Date-grouped conversation headings (Today / Last week)

- **Source**: Phase F close note
- **Rationale**: If reviewers find the de-chromed list too flat, group
  headings restore implicit structure without reintroducing card boxes.
- **Effort**: S

### G-004: `/api/admin/security/recent-blocks` endpoint

- **Source**: Phase A close note
- **Rationale**: `upload_scan_log` exists now. A small read-only endpoint
  surfacing the last N "infected" or "unreachable" rows would feed a
  morning-standup security dashboard.
- **Effort**: ~25 LOC
