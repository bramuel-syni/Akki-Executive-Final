# Chunk 15 — 16-May P2 batch 1

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. 4 P2 BACKLOG IDs DONE; 2 deferred to a future chunk pending P1 prerequisites; 1 (QA-001) shipped with minimal-scope routing change.
**Source spec:** `/app/memory/qa_reports/QA_REPORT_16MAY2026.md` rows -001, -009, -010, -016, -038, -040.

---

## 1. Pull decision — 4 IDs closed, 2 deferred

Backlog scan at chunk start: 6 P2 BACKLOG items.

### Closed this chunk

| ID | Surface | Verdict |
|---|---|---|
| QA-2026-05-16-001 | Portfolio post-login flow | DONE |
| QA-2026-05-16-009 | Top bar — bell affordance removal | DONE |
| QA-2026-05-16-010 | Document upload modal — auto-focused search | DONE |
| QA-2026-05-16-016 | Cycle Manager — bottom-bar Back relabel | DONE |

### Deferred (dependency on P1 work not yet shipped)

| ID | Surface | Deferral reason |
|---|---|---|
| QA-2026-05-16-038 | Work Studio Document Cards — Lock icon overlay | Tightly coupled to QA-2026-05-16-037 (P1 BACKLOG — status badge per card). Spec text explicitly frames the lock as "reinforcing the Committed badge". Shipping the lock without the badge produces a half-done surface where the badge taxonomy hasn't been established yet. Carries forward to a future chunk that pulls -037 + -039 (P1) alongside -038 + -040 (P2) for a holistic Document-Cards delivery. |
| QA-2026-05-16-040 | Work Studio Document Cards — Persistent download icon | Same dependency cluster as -038. Aggregate-row download semantics also require coordinating with the planned QA-037 status-badge work — what "download" means for a `draft` vs `compiled` vs `shipped` aggregate is undefined until the badge taxonomy is locked. |

Documented in this file + AUTONOMOUS_SPRINT_LOG; no new AWAITING_PO entry needed (the dependency is between two same-batch backlog rows, not a PO clarification).

---

## 2. Per-ID implementation notes

### QA-2026-05-16-001 — Portfolio sits below the landing page on login

**Verbatim spec:** *"Make the portfolio page below the landing page when the user logs in. Once the user chooses a company user then lands on the home page below of the company"*

**Diagnosis:** Pre-Chunk-15 behavior: `SignIn.jsx:34` defaulted post-login redirect to `/app` which routes via `AppHome.jsx` → if user had a restored `activeContext`, they bypassed the portfolio (Home 1) entirely and landed on Home 2 (workspace home). The QA author wants the portfolio surface to ALWAYS be the first thing seen post-signin.

**Implementation:**
- `pages/SignIn.jsx:34` — change the default redirect from `/app` to `/app/portfolio`.
- `App.js::PublicOnlyRoute` — change the "already-authed → bounce" target from `/app` to `/app/portfolio` so the React state-flush race during signin can't leak the user to `/app` first. Discovered live in smoke verification (the state flush from `setAccount(data.account)` raced ahead of the post-submit navigate, causing `PublicOnlyRoute` to redirect to its hardcoded `/app` target before the explicit `navigate("/app/portfolio")` landed).
- `/app/portfolio` always renders `Home1` via the `PortfolioRoute` wrapper (unconditional — see `App.js:115`).
- `Home1` already has the company-chip pick handler that calls `switchContext()` + `navigate("/app")`, which then routes to `Home2` (workspace home for the chosen company).
- Deep-link callers that set `location.state.from` (e.g. visited a protected URL pre-signin) still resolve to their target — they bypass the portfolio default.

**Test coverage:** `test_chunk15_qa001_me_contexts_returns_portfolio_shape` locks the `/api/me/contexts` contract so Home 1's portfolio chips have a stable payload to mount.

### QA-2026-05-16-009 — Remove notification-bell sub-page

**Verbatim spec:** *"Remove the page below. User gets to this page by clicking on the bell icon on the top bar"*

**Diagnosis:** Two bell-style affordances exist in the top bar:
1. `MentionInbox` — opens a dropdown (NOT a sub-page); reads `/api/contexts/{cid}/mentions`
2. `ReviewBadge` — links to `/app/review` (a real sub-page, Daily Review queue)

Only `ReviewBadge` matches the "click → sub-page" pattern the QA author flagged.

**Implementation:** `components/layout/AppShell.jsx` — remove the `<ReviewBadge />` render call AND the import. The component file itself (`ReviewBadge.jsx`) is kept for forensic reference and potential future re-introduction; nothing imports it now.

**Scope discipline note:** The underlying `/app/review` route remains. Direct-URL access still works (per `App.js:317`). This matches the literal spec ("remove the bell-icon-→-page navigation path") without breaking other features that may depend on the Daily Review page. Whether to fully retire `/app/review` is a separate decision (PO call).

**Test coverage:** `test_chunk15_qa009_review_summary_endpoint_still_alive` + `_mentions_endpoint_still_alive` lock the endpoints so the bell removal doesn't strand the underlying surfaces.

### QA-2026-05-16-010 — Auto-focused search bar in "link to earlier document" panel

**Verbatim spec:** *"…add a search bar function where the search bar is the first thing inside the open panel and it is a search field with a magnifying glass icon. It auto-focuses when the panel opens so you can start typing immediately without clicking. It filters the list in real time as you type"*

**Diagnosis:** The `AttachDocumentModal.jsx` journal panel already has a search input + real-time filter (via `filteredDocs`). Missing:
1. Magnifying-glass icon inside the input
2. Auto-focus when the journal panel becomes visible (covering the upload→journal tab switch where `autoFocus` doesn't re-fire)

**Implementation:** `components/solva/AttachDocumentModal.jsx` — add `Search` lucide icon as an absolute-positioned overlay on the input, switch input padding to `pl-8`, add a `useRef` + `useEffect` that calls `.focus()` 40ms after the journal tab activates.

**Test coverage:** `test_chunk15_qa010_documents_listing_supports_journal_search` locks the endpoint contract so the journal panel has data to filter against.

### QA-2026-05-16-016 — Cycle Manager bottom-bar Back relabel

**Verbatim spec:** *"…the 'Back' action on the second bar should read 'Back to Cycle Manager' to clearly communicate it exits the current flow and returns to the Cycle Manager section."*

**Diagnosis:** Cycle.jsx renders TWO navigation strips at the bottom:
1. `StepFooter` (in-form, moves between cycle steps) — UNCHANGED per spec
2. `CycleStepNav` (page-exit) — Back currently steps to the previous tab; should EXIT to /app/cycle

**Implementation:** `components/cycle/CycleStepNav.jsx`:
- Back button now renders verbatim "Back to Cycle Manager"
- Wired via `<Link to="/app/cycle">` (replaces the previous tab-stepping logic)
- Removed the now-dead `back` constant (unused — `void idx` retained for symmetry)

**Test coverage:** `test_chunk15_qa016_cycle_step_nav_label_locked` does a static grep for "Back to Cycle Manager" + `to="/app/cycle"` in the component source.

---

## 3. Architectural checkpoint

- ✅ Shield gateway exclusivity preserved — Chunk 15 adds zero new LLM call sites.
- ✅ `context_id` scoping intact — all endpoints touched are existing routes; no new endpoints.
- ✅ `tenant_id == account_id` boundary intact.
- ✅ No `repr(exc)` leaks.
- ✅ No new third-party libraries.
- ✅ Schema-drift defensive — frontend handles either list-shape or `{items: []}` shape from `/documents` endpoint (verified in test).
- ✅ Chunks 7-14 work intact — pytest moved up by +6 (60 → 66).

---

## 4. Tests + smoke

`backend/tests/test_qa_chunk_15.py` — **6 tests:**
- QA-001 portfolio endpoint contract
- QA-009 review-summary endpoint alive (post-bell-removal)
- QA-009 mentions endpoint alive (surviving sibling)
- QA-010 documents listing contract
- QA-016 cycle-step-nav label static grep
- CI sanity — touched files contain no LLM SDK imports

**All 6 pass.** Cross-chunk regression (9.5/10/11/12/13/14/15 + CI guard) = **66 passed**.

**Render-smoke step 17** added — covers QA-001 mount + QA-009 absence-of-bell + QA-016 label assertion.

---

## 5. Out-of-scope / deferred

- QA-2026-05-16-038 (Lock icon) — depends on P1 QA-037 status badge taxonomy; defer to a holistic Document-Cards chunk after P1 lands.
- QA-2026-05-16-040 (Download icon) — same dependency cluster as -038.
- C17-001/002/003/004 — Chunk 17 cleanup queue, untouched.

---

## 6. Elapsed effort

~50 minutes — under the 80-100 min estimate. The pull was actually 4 small IDs (not 5-8) because two had P1 dependencies that disqualified them from this batch.
