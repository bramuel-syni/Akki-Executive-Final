# AKKI — Build Phases (Management Ledger)

> Single source of truth. Reset 2026-05-05 against
> `docs/MEMO.md` (Bram Mwalo Product Feedback Memo, 8 items).
> Old phases (1, 2a, 2b/c privacy wall, 3, 4) collapsed into the new
> A→H ordering below. The Phase 2b Privacy Wall foundation is
> **PAUSED-PARTIAL** — see footnote.
>
> Status legend: **NOT STARTED** · **IN PROGRESS** · **DONE** ·
> **PAUSED** · **BLOCKED**.

## CHANGELOG (newest first)
- **2026-05-05** — `/api/me/governance/audit` and `/audit/export` no
  longer include the free-form audit `metadata` blob (Privacy Wall
  TBD-4 sign-off, applied during paused 2b work). Per-context audit
  feed at `/api/contexts/{cid}/audit-log` retains the raw `metadata`.
- **2026-05-05** — Roadmap reset against the new product memo.
  Phases relabelled A→H. Phase 2b Privacy Wall paused-partial.

## The active roadmap

| # | Phase | Memo item | Priority | Status | Acceptance bar |
|---|---|---|---|---|---|
| **A** | Roles & Company Navigation (security guardrail) | Item 5 | P0 | **IN PROGRESS** | Role binding to (user, context) on every authenticated request; switcher lists only memberships; switch fires modal with verbatim memo copy; `X-Active-Context` header required on membership routes; per-tab session isolation; audit rows on every privilege check + every switch. |
| **B** | Chat — production UX + two-pass method baked in | Item 8 | P0 | NOT STARTED | Two-pass method runs on every Chat turn (silent guardrail). Production-grade UX. |
| **C** | Workspace rewire (single drawer pattern, deterministic export) | Item 2 | P1 | NOT STARTED | Workspace consolidates around a single drawer. `python-pptx` + `python-docx` deterministic export ships first; LLM-composed layout behind a "creative" toggle (D-002). |
| **D** | Cycle Manager — Executive flow + NED-side design doc | Item 3 | P1 | NOT STARTED | Cycle Manager rebuilt as a drafting engine with three managed objectives. Forwarding alias `akki+<slug>@syni.ai` (D-001). NED-side gets a design-only doc at `docs/NED_CYCLE_MANAGER_DESIGN.md` (D-003) — no NED engineering effort in this phase. |
| **E** | Documents Journal rewire | Item 1 | P1 | NOT STARTED | Documents off main menu. Homepage "All documents · NN" button (D-006). Single-drawer document detail. Index-search across content + Akki notes + metadata. Menu collapses by one slot; nothing promoted (D-007). |
| **F** | Pulse — Twitter-style social feed | Item 4 | P2 | BLOCKED on Privacy Wall resume (see footnote) | Cross-context aggregator behind the projection guard from `docs/PRIVACY_WALL_DESIGN.md`. Real Pulse view, filterable, engagement affordances. |
| **G** | Solva 2×2 tile UI fix | Item 6 | P3 | NOT STARTED | Surface-level: 4 cluster tiles in a 2×2 grid. No engine change. |
| **H** | UI width consistency | Item 7 | P3 | NOT STARTED | All authenticated surfaces share the same content max-width and gutter rules. Surface-level only. |

---

## Frozen surfaces (until their named phase lands)

From 2026-05-05 onwards, **no new functionality, copy, or visual
change** lands on a surface that is scheduled for rewire. Old
surfaces stay frozen in place until their named phase. Helpful
tweaks, "while we're here" fixes, and copy adjustments are not
permitted on frozen surfaces. If something is broken on a frozen
surface and blocks a user journey, flag it and wait for its phase.

| Surface | Frozen until phase |
|---|---|
| `/app/workspace` (legacy three-column Document Journal) | E |
| The legacy three-column document detail | E |
| The "Document Journal" nav entry shipped under Phase 1 | E (it stays in place until E moves it) |
| Cycle Manager UI (`/app/cycle`, `/app/cycle/...`) | D |
| Solva tiles UI (`SolvaLanding.jsx`, `SolvaApp.jsx`) | G |
| Pulse placeholder (`PulsePlaceholder.jsx`) | F |
| Chat surface (`/app/chat`, `pages/Chat.jsx`) | B |

The Phase A scope below explicitly does NOT touch any of those.

---

## Footnote — Phase 2b Privacy Wall: PAUSED-PARTIAL

The Privacy Wall foundation was started before the roadmap reset.
Three artifacts are already live in the tree and remain there
because they close HIGH-severity cross-context content leaks
identified in `docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` (security
improvements, not features — the freeze rule does not apply).

| In-tree artifact | What it does |
|---|---|
| `backend/services/privacy_wall.py` | Per-collection metadata allowlists + `project_for_pulse` helper + `STRICT_PRIVACY_WALL` / `STRICT_PRIVACY_WALL_RAISE` env flags + the locked 4-class signals enum (`capital`, `succession`, `regulatory`, `cyber`). |
| `routers/shares.py:/me/home/stream` | Now projects every cross-context row (`signals`, `boardpacks`, `documents`, `inbound_queue`) through the wall. Sets `x-privacy-wall-projected-keys` header so testers can confirm. **Header retained for Phase A regression sanity** (slated for removal in Phase H). |
| `routers/governance.py:/me/governance/audit` + `/audit/export` | TBD-4 strip: free-form audit `metadata` blob no longer ships on the cross-context feed. CSV export drops the `metadata_json` column (CHANGELOG entry above). Per-context `/api/contexts/{cid}/audit-log` keeps the raw blob. |

Not yet shipped (and won't ship until Phase F resumes the wall):
- The two regression tests (field-drift + AST sweep over routers)
- Wiring of `admin/signals/action-heatmap` and the two LOW
  audit-row strip points
- The Pulse-time prompt-isolation contract test

When Phase F starts, Pulse work resumes from this point — the
foundation is in place; the rest is wiring + tests + Pulse itself.
Design doc at `docs/PRIVACY_WALL_DESIGN.md` and leakage baseline at
`docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` remain authoritative.

---

## How to add a new phase

1. Append a row to "The active roadmap" table.
2. Add a one-paragraph "Why this phase" section below.
3. Add a CHANGELOG entry at the top.
4. Do not modify historical entries.

---
Last updated: 2026-05-05 by main agent.
