# Legacy Home Parity Audit — Patch 17

> Created 2026-05-12 prior to deleting `HomeExecutive.jsx`, `HomeNed.jsx`, `HomeDual.jsx`.
> Source: code-level diff between legacy files and `Home2.jsx` + `AppHome.jsx` dispatcher.
> Rule (SYSTEM_STATE §2.5): "Never silently delete features. Refactors move, not remove."

---

## Audit Method

Read every legacy file end-to-end. For each visible section / data fetch / interactive control, classify against Home2's coverage:

- ✅ **Preserved** — same behaviour, same component path.
- ↺ **Replaced by** — same UX intent, different vehicle in Home2 (with reference).
- 🗑 **Intentionally dropped** — explicit retirement per Patch 3 brief or replaced by a routed surface that still exists.
- ⚠️ **MISSING — must add to Home 2 first** — gap; cannot delete legacy file until covered.

---

## HomeDual.jsx (101 ll.)

| Section | Status | Detail |
|---|---|---|
| Overline `Executive + NED home · {context}` | ↺ | Replaced by Home2's `home2-greeting` band overline showing the context name + Back-to-portfolio link. Role chip dropped — Home2 is role-agnostic. |
| H1 `Run the business on the left. Sit on the boards on the right.` | ✅ | Verbatim in Home2 §2 hero copy band. |
| Subtitle `AKKI splits the home so neither side gets buried...` | ↺ | Replaced by `One home for both. AKKI keeps your operating cadence and your board cadence side by side.` Same intent. |
| `<HeroDocActions />` | ✅ | Same component in Home2 §3. |
| `<CycleStrip contextId={cid} isMobile={isMobile} />` | 🗑 | Replaced by the 7-card insight grid (`cycles_closing` + `compile_ready` cards). The compact in-flight strip is no longer needed; counts live in the insight cards. |
| Executive column · 3 cards (Work Studio · Cycle Overview · Pending action items) | ↺ | Routes preserved (still hit Work Studio + Cycle). Cards collapsed into the 7-card grid + the "Running the business" footer card (Home2 §6 left). |
| NED column · 3 cards (Pulse · Latest minutes · Signals awaiting action) | ↺ | Pulse stays at `/app/pulse` reachable via 7-card grid `pulse_critical`. Latest minutes / Signals reachable via Cycle Manager tabs (intact). "Sitting on the boards" footer card (Home2 §6 right) absorbs the section heading. |
| `<ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />` | ⚠️ → ✅ | **Was MISSING from Home2 before this patch.** Patch 17 mounts `<ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />` after the footer split. |

**Verdict**: Safe to delete after adding `ExcoTeamsCard` to Home2 (done in this patch).

---

## HomeExecutive.jsx (320 ll.)

| Section | Status | Detail |
|---|---|---|
| Overline `Executive home · {context}` | ↺ | Same as HomeDual — context overline preserved, role chip dropped. |
| H1 `greeting(firstName)` | ✅ | Home2 §1 uses the same `greetingFor()` time-of-day function. |
| Subtitle `The five things that move between meetings...` | ↺ | Replaced by Home2's `Welcome back to {context}. Last seen here {relTime}.` — same orienting intent, more personal. |
| `<HeroDocActions />` | ✅ | Same. |
| **`<ContinueOnboardingCard account={account} />`** (legacy lines 158-186, 214) | ⚠️ → ✅ | **Was MISSING from Home2 before this patch.** Gated by `account.first_session.status` NOT in (`completed`, `skipped`). Patch 17 inlines an equivalent `<ContinueOnboardingBand />` after the greeting in Home2 with the same gate and the same target route (`/app/first-session`). |
| `<WorkStudioPreview contextId={cid} />` band (briefings/decks/reports counts row) | 🗑 | Replaced by 7-card grid (`compile_ready` + `new_documents`). The compact stats row was visually duplicative of Cycle Manager's own breadcrumb. |
| `<CycleStrip contextId={cid} isMobile={isMobile} />` | 🗑 | Replaced by `cycles_closing` insight card. |
| "Running the business" empty-state section | ↺ | Replaced by 7-card grid + `home2-footer-running` card. |
| 4-card 2×2 grid (Cycle Overview / Pending actions / Signals / Recent activity) | ↺ | Routes intact (`/app/cycle?tab=overview`, `/app/cycle?tab=actions`, `/app/cycle?tab=signals`, `/app/activity`). The 7-card insight grid surfaces these alongside live counts; the explicit 4-card grid is redundant. |
| `<ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />` | ⚠️ → ✅ | Same fix as HomeDual — added to Home2 in this patch. |

**Verdict**: Safe to delete after adding `ContinueOnboardingCard` + `ExcoTeamsCard` to Home2 (both done in this patch).

---

## HomeNed.jsx (414 ll.)

| Section | Status | Detail |
|---|---|---|
| Overline `Non-executive director` + greeting `Hi {firstName}.` | ↺ | Home2's greeting band serves both operator and NED users. The NED-specific overline is dropped (Home2 is role-agnostic by design). |
| Boards-count statement + board filter `<select>` | 🗑 | Multi-board switching is now in the global PortfolioRail / context switcher in the AppShell header. The Home1 `/app/portfolio` page is the explicit "Back to portfolio" target. |
| `+ Add a meeting` button + `<AddMeetingDialog />` | 🗑 | Meeting-create UX moved to NedMeeting page (`/app/ned/meeting/:id` route still in App.js line 248). Home2 is not a meeting-create surface. |
| `<NedInboxTile />` (pending assignments tile) | ↺ | Home2 7-card grid `signoffs_needed` card routes to `/app/ned-inbox` (App.js line 250). Functional parity. |
| `<SearchPanel />` cross-board search | 🗑 | NED cross-board search remains reachable via the NED Inbox page (`/app/ned/inbox`). Home2 has the global `Search` field in the shell header for in-context search. |
| Section 1 — `This week` (meetings ≤7 days) | ↺ | `cycles_closing` insight card (≤7 days window) covers the same operating need. The NED-specific meeting list is rebuilt on the NedInbox page (`/app/ned/inbox`). |
| Section 2 — `Next 2 weeks` (meetings 7-21 days) | 🗑 | This 7-21d window was unique to HomeNed. Home2 surfaces "this week" only; the 2-week look-ahead is deferred to Cycle Manager / Pulse trend views. **Intentional simplification per Patch 3 brief: 7 insight cards, single time horizon.** |
| Section 3 — `Outstanding` (open follow-ups + post-meeting items) | ↺ | `signoffs_needed` + `open_questions` insight cards cover outstanding work. Detail UI is on NedInbox. |
| Section 4 — `Patterns worth knowing` (`<AcrossBoardsPanel />`) | 🗑 | Cross-board pattern aggregator stays available on `/app/pulse` (Pulse Across-Boards Panel — `components/pulse/AcrossBoardsPanel.jsx`). Home2 doesn't repeat it. **Intentional simplification.** |
| `<AddMeetingDialog />` (modal triggered by `+ Add a meeting`) | 🗑 | Component preserved (still imported by `pages/ned/NedMeeting.jsx`). |

**Verdict**: Safe to delete. No genuine MISSING items. The NED-specific calendar/meeting widgets relocated to dedicated routes; the Home2 7-card grid covers operating-level functional parity.

---

## Action items applied in this patch (before deletion)

1. ✅ Add `<ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />` to Home2 below the footer split.
2. ✅ Add `<ContinueOnboardingCard account={account} />` (or equivalent inline `<ContinueOnboardingBand />`) to Home2 above the hero copy.
3. ✅ Delete `HomeExecutive.jsx`, `HomeNed.jsx`, `HomeDual.jsx`.
4. ✅ Confirm no other component imports the deleted files (grep clean: only comments inside `ExcoTeamsCard.jsx`, `AllDocumentsButton.jsx`, `NedInboxTile.jsx` reference them historically — none import them).
5. ✅ All tests still green.

---

— end of parity audit —
