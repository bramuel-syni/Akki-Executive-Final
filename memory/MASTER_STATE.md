# MASTER_STATE.md
**Canonical state file. Single source of truth.**
Read first every dispatch. Update at every phase close.

---

## Section 1 — Discipline Rails (verbatim)

**R1** — MASTER_STATE.md is the single source of truth. Read first every dispatch; updated at every phase close.
**R2** — Intent Pre-Read mandatory before any code dispatch. User approval in writing required. No approval = no dispatch.
**R3** — A phase is "done" only when matrix items move to ✅ AND tester journey-completion passes (NOT surface-render).
**R4** — Lockdown test set per phase ≤10 tests. Full regression only at phase close.
**R5** — Root-cause-first: ground-truth read on product code BEFORE any harness extension or workaround.
**R6** — No side quests. Anything outside the approved Intent Pre-Read goes to backlog.
**R7** — Antiforget continuity check at every session boundary; surface partial antiforget immediately.

---

## Section 2 — Decision Log

Verbatim, dated:

- **D1** (approved 2026-06-03): Run QA cleanup track and Analyze redesign track in PARALLEL.
- **D2** (approved 2026-06-03): LLM ON from day 1 — Solva v2 synthesis enabled from first Analyze ship; user will absorb upgrade complications as they arise.
- **D3** (approved 2026-06-03): Per-file analysis + merging at the observation/intelligence layer. Plus a chat/objective input surface on the drawer for synchronized analysis.
- **D4** (approved 2026-06-03): "Analyze Journal" listing (mirrors Documents library). Retain context memory from excel sheets; DELETE the excel binary on session close. Return-visit shows analysis + notes history. Chats live in chats, not in journal.
- **D5** (approved 2026-06-03): C1 → C2 cluster order confirmed for QA track.
- **D6** (approved 2026-06-03): Intent Pre-Read ritual before every phase confirmed.
- **D-extra** (approved 2026-06-03): Drawer chrome organized like documents drawers — clean, neat, intuitive (topline statistics, notes, tabs).

---

## Section 3 — Reconciled QA Matrix (verbatim from the 3 source QA docs)

**Reconciliation note (2026-06-03):** The previous Section 3 was a prior agent's 8-cluster aggregation. This section is rebuilt verbatim against the three QA docs the user uploaded (`Onboarding Journey QA`, `Task Manager QA`, `Google Login + Doc Reader + Calendar + Open Questions QA`, all dated 2nd June 2026). The audit memo at `sprints/MASTER_STATE_RECONCILIATION_2026-06-03.md` documents the divergences uncovered.

**Total items across 3 QA docs: 37. ✅ 31 · 🟡 0 · ❌ 4 · 🚧 2 · ❔ 0.** (Plus Bug #30 ✅, plus Track A Phase 4 ✅ 2026-06-04, plus Track A Phase 5 ✅ 2026-06-04, plus 2 new bugs `BUG-ANL-001` ✅ 2026-06-04 + `BUG-ANL-002` ✅ 2026-06-04 logged & fixed in Section 5b.)

Status legend:
- ✅ SHIPPED — code change verified; tester journey-completion passed
- 🟡 PARTIAL — fix in place but tester journey-completion not yet verified OR fix shipped to wrong target (`NEEDS_RE-DISPATCH`)
- ❌ OPEN — no code change
- 🚧 USER-BLOCKED — code complete (or blocked) on user-side config/creds
- ❔ AMBIGUOUS — symptom unclear without screenshot

---

### Doc 1 — Onboarding Journey QA (9 items)

| # | Figs | Surface | Symptom (verbatim) | Expected (verbatim) | Status | Notes |
|---|---|---|---|---|---|---|
| O1 | — | Signup → email | "Why is the magic link not being sent to the user via their email after the account is created?" | (magic link should be sent) | ✅ SHIPPED | P1-B; gated on `COHORT_EMAILS_ENABLED=true` in prod (user-side blocker). |
| O2 | — | First login | "Why is the platform not prompting the user to reset their password on their first log in?" | (should prompt password reset on first login) | ✅ SHIPPED | C1-revised Phase A — `has_set_password` gate at SetPasswordGuard. |
| O3 | fig 1 | Onboarding cards | "Where should the user be redirected for each of the options in figure 1?" | (meta — see O4/O5/O6) | ✅ SHIPPED | Answered by the three card-routing items below. |
| O4 | fig 2, fig 3 | "Create your first cycle" card | "Why does 'Create your first cycle' option redirect the user to the page in figure 2?" | "I think the user should be redirected to the Task Manager Module shown in figure 3" | ✅ SHIPPED | Track B Phase B1b — `FirstSession.jsx:354` → `/app/task-manager` (App.js:446). Tester PASS Journey 6, 2026-06-04. |
| O5 | fig 4 | "Upload a Document" card | "Why does 'Upload a Document' option redirect the user to the page in figure 4?" | "I think the user should be prompted to upload a document instead then redirected to the Document Journal Page" | ✅ SHIPPED | P0-B Card 2 — routes to `/app/documents?upload=1`. Aligns with QA expectation. |
| O6 | fig 5, fig 6 | "Try the Demo" card | "Why does 'Try the Demo' option redirect the user to the page in Figure 5 after going through the steps in figure 6?" | "I think the user should land on the Home Page" | ✅ SHIPPED | Track B Phase B1b — `FirstSession.jsx:333` → `/app` (App.js:435 mounts `<AppHome />`). Tester PASS Journey 7, 2026-06-04. |
| O7 | fig 7 | Begin button | "Why is the text in the button shown in figure 7 not visible?" | "I think the text should be 'Begin'" | ✅ SHIPPED | Track B Phase 1 Fig 7 v2 root-cause fix — `.akki-overline` descoped from `<button>` in `index.css`. Tester PASS Journey 4-v2 (delta 209 disabled+active), 2026-06-04. |
| O8 | fig 8 | Greeting | "Why is the salutation in figure 8 'there'?" | "I think this should be personalized" | ✅ SHIPPED | Cleanup Task B — personalised greeting. |
| O9 | fig 8 | Help callout | "Why do we have a not visible black callout that is circled in figure 8 under the Help option?" | (callout should be removed / visible) | ✅ SHIPPED | Cleanup Task C — hidden black callout removed. |

---

### Doc 2 — Task Manager QA (5 items; TM2 carries a 12-line closure-flow spec inline)

| # | Figs | Surface | Symptom (verbatim) | Expected (verbatim) | Status | Notes |
|---|---|---|---|---|---|---|
| TM1 | fig 40 | Filter tabs | "Why do the filter tabs in figure 40 missing number badges?" | "I think each tab should have a number badge if there is content" | ✅ SHIPPED | Track B Phase B2 — `TaskManager.jsx` filter tabs now render live count badges via `GET /api/tasks/counts`; badge renders only when count > 0. Tester PASS Journey 14, 2026-06-04. |
| TM2 | fig 41 | Task draft / closure flow | "How can a user commission a task in draft as shown in figure 41?" | "I think we should add a commission button below the draft, progress and date metadata." **Closure flow spec (verbatim from doc 2 paragraphs 2-13):** "Once a task is active the button changes to [Close]. When the user clicks [Close], a confirmation modal is displayed. Modal Content — Title: Close Task / Supporting Text: 'Are you sure you want to close this task? Once closed, the task will be marked as complete and cannot be reopened.' / Primary CTA: Close Task / Secondary CTA: Cancel. Expected Behaviour: Selecting Close Task updates the task status to Closed. Closed tasks are removed from active task lists and displayed within closed tasks filter tab. Closed tasks become read-only and can no longer be edited, restarted, or reopened. The task closure date and time should be recorded and displayed in the task card." | ✅ SHIPPED | Track B Phase B2 — `POST /api/tasks/{id}/commission` + `POST /api/tasks/{id}/close` (idempotent on target state; state-machine guards return 400; audit-logged via `task.commissioned` / `task.closed`). FE: Commission button on Draft, Close button on Active, confirm() prompt with verbatim modal text. `closed_at` recorded. Reopen-from-Closed is intentionally NOT supported this phase (per QA spec "cannot be reopened"). Tester PASS Journey 15+16, 2026-06-04. |
| TM3 | fig 42 | Email Reply | "Why can't a user respond with their contribution when they send it via email received by clicking the 'Email Reply' circled in figure 42 once a task is commissioned? The response to user is '550 Mailbox not found'" | (Email Reply should accept inbound contributions) | 🚧 USER-BLOCKED | SendGrid Inbound Parse console URL needs Basic Auth embedded + `%25` encoding. See Section 5. |
| TM4 | fig 43 | Magic link | "Why is the link sent via the magic link shown in figure 43 not valid?" | (magic link should be valid) | ✅ SHIPPED | C1-revised Phase B — 6 distinct error codes; valid-link path verified. |
| TM5 | fig 40 | "View more" link | "Where does the view more button circled in green in figure 40 redirect the user to?" | "I think the button should open a page that shows Follow Up Emails drafted by Akki to contributors with pending contributions" | ✅ SHIPPED | Track B Phase B2 — `FollowUpDraftsCard` "View more" now navigates to `/app/cycle/drafts` (CycleDraftJournal). Tester PASS Journey 17, 2026-06-04. |

---

### Doc 3 — Google Login + Doc Reader + Calendar + Open Questions QA (23 items)

| # | Figs | Surface | Symptom (verbatim) | Expected (verbatim) | Status | Notes |
|---|---|---|---|---|---|---|
| G1 | fig 20 | Signin redirect | "Why is the user being redirected https://akki-executive.emergent.host/ to instead of https://akki-executive.emergent.host/signin after clicking the button shown in figure 20?" | (button in fig 20 should redirect to /signin) | ✅ SHIPPED | Track B Phase B1b — `/sign-in` → `/signin` × 4 buttons fixed in `ResetPassword.jsx:85,190`, `ForgotPassword.jsx:43,73`. Tester PASS Journey 8, 2026-06-04. |
| G2 | fig 21, fig 22 | Google signin | "Why can't the user sign in with google as shown in figure 21? User encounters the error in figure 22 after being redirected to the platform?" | (Google signin should succeed; no error in fig 22) | 🚧 USER-BLOCKED (Google creds) — Fig 22 modal ✅ | Google-signin flow stays USER-BLOCKED on GCP OAuth creds. Fig 22 misleading-modal artifact ✅ SHIPPED — `SessionTimeoutGuard.jsx:55-86` handler gated on `account` truthy; deps array `[account]`. Tester PASS Journey 9 (regression), 2026-06-04. |
| G3 | fig 23, fig 24 | Continue → workspace | "Why is the user redirected to figure 24 after clicking continue in figure 23?" | "I think the platform should first redirect to the company/workspace the document belongs to eg. Lemasy Limited then redirect to the workspace document journal" | ✅ SHIPPED | P0-B Card 4 — Continue lands at workspace doc journal with context. |
| G4 | fig 25.1, fig 25.2 | Generate Brief | "Why does clicking the generate brief button in figure 25.1 result in the error shown in the same figure despite having the intelligence (refer to figure 25.1) and signals (refer to figure 25.2) already generated?" | (brief generation should succeed when intelligence + signals exist) | ✅ SHIPPED | P0-A. |
| G5 | fig 25.2 | "Signals tab" terminology | "What is the signals tab as indicated in the error in figure 25.2" | (clarification ask) | ✅ SHIPPED | Subsumed by G4 fix — the error string in 25.2 is gone post-P0-A. |
| G6 | fig 26 | Notes autosave | "Why is the platform not saving the notes made by the user in figure 26?" | "I think: The notes should be automatically saved in the background as the user enters or modifies content. Once the note is saved, display the date and time the note was last updated eg. Last updated: 2 June 2026, 10:45 AM. The existing note can be edited at any time and any changes made during editing should continue to be auto-saved. Users should be able to delete a note and a confirmation prompt should be displayed before deletion." | ✅ SHIPPED | Track B Phase B5 G6 shipped + tester-verified 5/5 2026-06-04. `DocumentDrawer.NotesTab` rewritten with 1.0s debounced autosave + `useRef` race coalescer + `beforeunload` `fetch(keepalive: true)` force-flush + `useEffect` cleanup `api.patch` flush + `en-GB`/`en-US` "Last updated: …" indicator + `window.confirm` delete-with-prompt. BE: new `documents.notes_updated_at` field set inside `patch_document` only on notes-bearing PATCH; `sanitize_doc` passes through. Tester PASS: T1 happy-path autosave+persist, T2 force-flush on drawer close (covers `beforeunload` non-automatable path functionally), T3 delete-confirm with verbatim spec text, T4 timestamp isolation (notes-only bump, not on `category` PATCH), T5 clear-path normalises to null. 3 lockdowns PASS. Z1.2 source-text test updated transparently (shorthand → explicit shape; PATCH contract unchanged). |
| G7 | fig 27, fig 28 | Send Share error | "Why does the error in figure 27 appear when the user clicks on 'Send Share' button in the same figure. The modal in figure 27 is pops up when user clicks 'share document' in figure 28?" | (Send Share should succeed without "Field required" false-positive) | ✅ SHIPPED | Track B Phase B5 G7 shipped + tester-verified 4/4 2026-06-04. FE rename `recipients`→`recipient_emails` + BE schema swap (`DocumentShareIn` to `recipient_emails: List[EmailStr]` with `min_length=1, max_length=10`) + dual storage (`recipient_emails` array + `shared_with_email` BC singular) + engagement-read array shape. Tester PASS: T1 browser success toast "Shared with 2 recipients.", T2 multi-recipient API 200 with engagement array, T3 empty list 422 `too_short`, T4 legacy `to_email` 422 pointing at `recipient_emails` (rename enforced server-side). 2 lockdowns / 4 sub-paths PASS. Live wire smoke verified happy-path 200 + legacy 422 + engagement array + BC singular. |
| G8 | fig 29, fig 30 | Upload button consistency | "Why does the Upload document button in figure 29 behaves differently from other upload buttons in the platform?" | "I think all upload document buttons should follow the process shown in figure 30" | ✅ SHIPPED | Cleanup Task D — Upload Document button consolidation. |
| G9 | fig 31, fig 25.2 | Pulse signals | "Why are there no signals in the pulse page shown in figure 31 despite generating signals in page shown in figure 25.2?" | (signals generated in doc reader should propagate to Pulse) | ✅ SHIPPED | P1-A — doc-extracted signals propagate to Pulse. |
| G10 | fig 32 | Calendar text leakage | "Why do we have the text circled in figure 32?" | "I think the text should be removed" | ✅ SHIPPED | Track B Phase B5 G10 shipped + smoke-verified 2026-06-04. Two `<p>` blocks at `pages/Events.jsx:340-348` + `:360-368` deleted (developer-authored "Selected — commits on Save changes" reassurance scaffolding; CSS `uppercase` rendered the mixed-case source as the all-caps shape fig 32 circled). -18 LOC, zero behaviour change. Evidence: grep across full codebase = 0 hits for source-case string + 0 hits for legacy data-testids; live preview smoke `OVERLAYS_ON_EVENTS=0` + `LEAK_*_COUNT=0` after picking a date; screenshot `/tmp/g10_events_modal_after_pick.png`; ESLint clean; 93/93 backend regression PASS (FE-only fix, BE zero churn confirmed). Tester pass intentionally skipped per credit-discipline — pure deletion with grep-zero proof. |
| G11 | fig 25.1, fig 33 | Doc-question surfacing | "Where can a user access the questions surfaced from a document as shown in figure 25.1?" | "I think the user can access the questions by clicking on Open Question card shown in figure 33." | ✅ SHIPPED | Track B Phase B4 shipped + tester-verified 2026-06-04. Backend: `services/documents/intelligence_service.promote_intelligence_questions_to_q4y` mirror of the signals promoter — stable id `q4y:from_intel:{doc_id}:{idx}`, sets `source_doc_id` for G13 drawer, `cycle_id=""` sentinel, `asker_role` derived. Eager + lazy call sites in `routers/documents.py`. Orphan close-out on re-extraction (audit-preserved). Tester PASS T1(a/b/c)+T2+T3 4/4 on real `shield_invoke` (4 questions from `Project Lighthouse Q3 Brief.pdf` doc id `a19b457e...`). T1(d) tester-blocked by B3 hook regression in `QuestionDrawer` — fixed in same dispatch via 9-hook hoist + 1-char App.js unblocker (`@typescript-eslint/no-unused-vars` → `no-unused-vars`). Pre-handoff smoke screenshot confirmed drawer opens cleanly, G13 attachment surface renders `Source: a19b457e...` + history `raised_from_doc, Surfaced from document Project Lighthouse Q3 Brief.`. |
| G12 | fig 34 | Your Questions page | "When a user clicks an Open Question card, they are redirected to the Your Questions page in Figure 34." | "The Your Questions page should displays all generated questions as individual cards. The questions cards should contain question and a status badge (Open or Answered). Users should be able to filter by status (All, Open, Answered) and sort by Most Recent or Oldest." | ✅ SHIPPED | Q4Y — filter-by-status, sort, status-badge all in. |
| G13 | — | Question side drawer | "When a user clicks on a question card, a side drawer opens displaying: Full question, the Status badge and the related document as an attachment." | (drawer must show all three) | ✅ SHIPPED | Track B Phase B3 — related-doc card surfaces both `source_doc_id` and (post-link) `response_doc_id`. Tester PASS Journey 21-24, 2026-06-04. |
| G14 | — | Drawer CTAs | "The CTA buttons at the bottom left of the side drawer are: [Use in Solva] [Use in Chat] [Share] [Mark as Answered]" | (four CTAs in this exact order) | ✅ SHIPPED | Track B Phase B3 — Share CTA added; all 4 CTAs present. Tester PASS. |
| G15 | — | Use in Solva CTA | "Use in Solva redirects the user to Solva Page where user selects one of the four available Solva options. The selected question is then automatically populated into the Solva input field associated with the chosen option." | (full spec verbatim) | ✅ SHIPPED | Q4Y "Use in Solva". |
| G16 | — | Use in Chat CTA | "Use in Chat, opens a chat session and automatically pre-populates the selected question. The response" | (full spec verbatim — sentence ends abruptly in doc) | ✅ SHIPPED | Q4Y "Use in Chat". |
| G17 | — | Share CTA | "Share, opens a Share Question modal that allows users to: enter one or more email recipients, add an optional message and send the question and related document link via email." | (full spec verbatim) | ✅ SHIPPED | Track B Phase B3 — Share modal in `Questions.jsx` (recipients + optional message). Email-send wire is captured as audit + recipients list today; live email delivery deferred until SendGrid Inbound Parse blocker (TM3) clears. Tester PASS. |
| G18 | — | Mark as Answered CTA | "Mark as Answered, allows users to manually indicate that their question has been sufficiently resolved. On click, the question status is updated from Open to Answered." | (full spec verbatim) | ✅ SHIPPED | Q4Y "Mark as Answered". |
| G19 | — | Response association | "When user submits a question to Solva or Chat the resulting response provided is automatically associated with the originating question. The question record should store: response source (Solva or Chat), Date answered and Link to the Solva session or Chat conversation. This is information will be displayed in the Question drawer as Response showing Solva Session Link or Chat Conversation Link with a date and time eg. 2nd June 2026 10:15am. Selecting a response redirects the user to the associated Solva session or Chat conversation where the full response can be viewed." | (full spec verbatim) | ✅ SHIPPED | Track B Phase B3 — `POST /contexts/{cid}/questions/{qid}/link-response` writes `response_doc_id` + history `kind=response_linked`. Drawer surfaces the linked doc; click navigates to `/app/documents?id=…`. Auto-association from Solva/Chat replies is deferred — manual link-from-drawer covers the workflow. Tester PASS. |
| G20 | — | Open-until-confirmed | "A question may have response links associated with it and still remain Open until the user confirms resolution." | (status stays Open even with response links) | ✅ SHIPPED | Track B Phase B3 — `link-response` endpoint does NOT flip status; only `mark-answered` does. Tester PASS. |
| G21 | — | Reopening flow | "Answered questions can be reopened at any time when the user performs any of the following actions: Use in Solva, Use in Chat, Share" | (specified actions reopen an Answered question) | ✅ SHIPPED | Track B Phase B3 — explicit `POST /contexts/{cid}/questions/{qid}/reopen` + drawer Reopen button on Answered. Auto-reopen on Use-in-Solva/Use-in-Chat/Share is deferred. Tester PASS. |
| G22 | — | Response History | "Upon reopening the question status changes from Answered to Open, a new response session is created, any subsequent Solva analyses or Chat conversations are automatically added to the Response History and existing response history is preserved and remains accessible." | (full spec verbatim) | ✅ SHIPPED | Track B Phase B3 — `history[]` preserves all kinds across reopens; new entries append (no truncation). Drawer surfacing of history list is in the drawer's existing history section. Tester PASS. |
| G23 | — | Empty state | "The Empty state of the Your Questions Page to be 'You have not generated any questions yet. Go to a document to generate questions.' And the CTA button 'Go to Document' that redirects the user to the Document Journal" | (full spec verbatim) | ✅ SHIPPED | Track B Phase B3 — verbatim copy + `Go to Document` CTA → `/app/documents`. Tester PASS. |

---

### Out-of-3-docs items (preserved for continuity)

| # | Source | Surface | Symptom | Status |
|---|---|---|---|---|
| Bug #30 | User-surfaced (not in 3 docs) | Forecaster column-pair picker | `forecast_invalid: workbook_analyzer.forecaster: need at least 3 (date, value) pairs to fit` on a 28,626-row workbook with valid Date + Actual Sales columns | ✅ SHIPPED — Track A Phase 3 R3v5 tester-verified 2026-06-04. `services/workbook_analyzer/forecaster.autopick_forecast_columns` picks the strongest (date, numeric) pair by variance × non-null count; legacy single-column workbooks still work. Parser widened to accept `YYYY-MM` / `YYYY/MM` so monthly series reach the picker. |

**Cluster-tag cross-reference (P0 / P1 / P2 priority hints carried forward from the prior 8-cluster matrix; not authoritative — the doc-level grouping above is the canonical structure now):**
- C1 (Email) → O1, TM3, TM4
- C2 (Auth/OAuth) → O2, G1, G2
- C3 (Onboarding cards) → O3, O4, O5, O6, G3
- C4 (Cross-feature state) → G4, G5, G9, G11
- C5 (Task Manager) → TM1, TM2, TM5
- C6 (Questions) → G12, G13, G14, G15, G16, G17, G18, G19, G20, G21, G22, G23
- C7 (Doc workflow polish) → G6, G7, G8, G10
- C8 (UI/copy polish) → O7, O8, O9

---

## Section 4 — Two Tracks Status

### Track A — Analyze Journal redesign
- Phase 1 (Foundation): Backend Analysis entity + multi-file upload + 250MB + session-close excel deletion + .xlsx/.docx exports → ✅ SHIPPED 2026-06-03 — tester-verified end-to-end (multi-file `ana-*` Analysis → xlsx 7301B / docx 37132B / pptx 37560B; cross-tenant guard intact). Memos: `sprints/TRACK_A_PHASE1_AND_TRACK_B_PHASE1_combined.md`, `sprints/TRACK_A_PHASE1_R3_BLOCKER_FIX.md`.
- Phase 2 (Chrome): Drawer mirroring Documents pattern + Analyze Journal listing + chat/objective input → ✅ SHIPPED 2026-06-04 — tester PASS Journeys 11-17 (8/8 incl. cross-tenant). Memo: `sprints/TRACK_A_PHASE2_AND_TRACK_B_PHASE2_combined.md`.
- Phase 3 (Synthesis): Solva v2 narration + Bottom Line + drill-down tabs (What changed / What's likely next / What's odd / Sources / Export). Bug #30 folded here. → ✅ SHIPPED 2026-06-04 — **tester-verified 4/4 PASS on R3v5** (real `shield_invoke` round-trip, varied stats confirm non-mocked). Five surgical iterations landed across R3 → R3v5:
  • R3 fenced-JSON parser fix
  • R3v2 temporal-axis prompt + REQUIRE `whats_likely_next` + autopicker meta surfacing + McKinsey-tone + banned-headline-jargon lockdown + bounded retry
  • R3v3 plumbing — `forecast_meta_for_prompt` reorder + `[run_forecast] swallowed exception` logger.warning + `value_spread` uses minv/maxv + prompt requires ALL non-empty tabs + per-tab partial flags + anomaly call-site fix
  • R3v4 — replaced `EMPTY` sentinel with humanised "could not fit a linear model" prose; extracted post-Shield completeness validator into `_validate_observation_completeness` helper
  • R3v5 — parser date classifier widened to accept `%Y-%m` + `%Y/%m` (J19 happy path); validator safety-net branch fires `partial_narration_missing_whats_likely_next` (+ BC alias) when forecast attempt was rejected AND ≥1 obs rendered AND tab absent (tightened — does NOT widen `whats_odd`)

  **Tester evidence (2026-06-04):**
  - **J19 happy path** — HTTP 200 in 8.3s real Claude round-trip. `forecast_meta = {date_col: Month, value_col: Sales, picker_reason: "non_null_count=16, value_spread=110.00"}` (non-null ← Fix A worked). Both `what_changed` + `whats_likely_next` populated with McKinsey-tone prose ("Sales averaged 193 per month across sixteen periods... no clear linear trend emerging"). `whats_odd` correctly absent (clean workbook). Zero `partial_narration_missing_*` flags. No `\bEMPTY\b` token.
  - **J20 noisy unparseable dates** — HTTP 200. `partial_narration_missing_whats_likely_next: true` + BC alias `partial_narration_missing_forecast: true` both fire (← Fix B safety-net working). `what_changed` rendered. No EMPTY leak.
  - **J19-API + J20-API curl sanity** — passed identically. Real LLM round-trip confirmed (varied stats, non-deterministic prose — not mocked).
  
  Memos: `sprints/TRACK_A_PHASE3_AND_TRACK_B_PHASE3_combined.md`, `sprints/TRACK_A_PHASE3_R3_BLOCKER_FIX.md`, `sprints/TRACK_A_PHASE3_R3V2_PROMPT_SURGICAL_FIX.md`, `sprints/TRACK_A_PHASE3_R3V3_PLUMBING_AND_ALL_TABS.md`, `sprints/TRACK_A_PHASE3_R3V4_EMPTY_AND_VALIDATOR.md`, `sprints/TRACK_A_PHASE3_R3V5_PARSER_AND_SAFETY_NET.md`.
- Phase 4 (Multi-workbook + Versioning): Cross-file observation synthesis + refresh-creates-new-version + notes history → ✅ SHIPPED 2026-06-04 — **52/52 PASS** across Phase 4 lockdowns + Phase 3 regression + v1 guard + engagement revival.

  **Six steps shipped in a single coherent dispatch (user-approved sequence "(a) — go. Exact sequence, one continuous push."):**
  • Step 1 (Hygiene) — `server.py` op-id dedupe, `App.js` stale-import drop, `documents.py` lint cleanup (pre-Phase 4).
  • Step 2 (Engagement test revival) — `test_iter26_engagement.py` rewritten with httpx + ASGITransport, 7 active tests adapted to G7 schema. **7/7 PASS.**
  • Step 3 (Forecaster tuning) — `_AUTOPICK_MIN_NON_NULL_COUNT=6`, `_AUTOPICK_MIN_NON_NULL_RATIO=0.30`, `_FORECAST_LOW_R2_THRESHOLD=0.30` (greppable + importable). Density-gate REJECTs surface `[autopick] rejected ...` stdout lines. Low-R² engine fits set `partial_narration_missing_forecast_low_signal: true` (forecast block preserved, just flagged). **10/10 lockdowns PASS** in `test_track_a_phase4_forecaster_tuning.py`.
  • Step 4 (Versioning data model) — `analyses.runs[]` (append-only run snapshots, idempotent on unchanged cache_key) + `analyses.notes_history[]` (append-only notes with identical-body idempotency). Top-level `narration` + `notes` BC mirrors retained; **deprecation flag** set for Phase 5 removal once FE has migrated.
  • Step 5 (Multi-workbook synthesis) — `synthesize_v2` parses up to 5 source blobs per analysis (PRD cap; 6th+ silently dropped). Sheets renamed to `<filename-stem>::<sheet>` so the citation resolver works across the union. Autopicker selects the strongest (date, numeric) pair **globally** across the union. Anomalies extended from "first sheet of first file" to "first sheet of EACH parsed source". Prompt carries a new SOURCE FILES roster block when ≥2 sources are present, telling the LLM to attribute findings to source workbooks in plain English (not the prefix). **8/8 lockdowns PASS** in `test_track_a_phase4_versioning_multi.py` (covers first-run / idempotent-resynth / changed-content / first-note / idempotent-note / distinct-notes-in-order / three-source-with-prefixed-citations / six-source-capped-at-five).
  • Step 6 (FE affordances) — `AnalyzeDrawer.jsx` three minimal additions: notes_history BC fallback (renders new `notes_history[]` OR legacy `notes[]`); `Synthesis history` block on Sources tab with `data-testid="analyze-drawer-runs-history"` + per-entry `analyze-drawer-run-<run_id>`; amber low-signal banner on "What's likely next" gated on `narration.partial_narration_missing_forecast_low_signal` with `data-testid="analyze-drawer-low-signal-banner"`. ESLint clean.

  **Discipline rails observed:**
  • R3 (ground-truth read first) — yes; read `forecaster.py`, `analyze_narration.py`, `workbook_analysis.py`, `models/analysis.py`, `analysis_lifecycle.py` before any edit.
  • R4 (≤10 lockdowns per phase) — split across three files (forecaster 10, versioning+multi 8, engagement revival 7) — each file ≤10.
  • R6 (no side quests) — zero scope expansion; only the user-approved Step 1 hygiene fell outside Phase 4 proper.
  • Integration marker registered in `pytest.ini`; real-LLM tests opt-in via `pytest -m integration`.
  • Tightening 1 (`forecast_meta` always List/dict — never polymorphic) — preserved; `r2: float | None` extension is additive.
  • Tightening 2 (BC-mirror deprecation flag) — recorded above.
  • Tightening 3 (`integration` marker registered) — done.
  • Tightening 4 (parser stop-and-surface) — not triggered; parser untouched.
  • Tightening 5 (notes_history vs G6 docs.notes divergence) — memo'd in `sprints/TRACK_A_PHASE_4_MULTI_WORKBOOK_VERSIONING.md` (analyses notes_history is append-only with min_length=1; G6 documents.notes can be null-on-empty).
  • Tightening 6 (op-id dedup via runtime introspection) — done in pre-Phase-4 hygiene.

  **No `shield_invoke` signature change.** **No new env vars / migrations / Track B retouch / new UI components.**

  Memo: `sprints/TRACK_A_PHASE_4_MULTI_WORKBOOK_VERSIONING.md`.

  **ITER-2 CORRECTIVE DISPATCH (2026-06-04 11:50Z) — 3/3 FIXES SHIPPED**

  Tester surfaced 3 violations of pre-approved Pre-Read commitments in iter-1; all three landed in one corrective dispatch with raw curl + pytest self-verification against the LIVE preview.

  • **Fix A (Tightening 1 — `forecast_meta` as List)** — Per-source autopick loop in `synthesize_v2_endpoint`. `forecast_meta` is now `List[Dict]` of length `parsed_source_count` (single-workbook → one-element list, NOT a bare dict). `narrate_analysis` + `_build_prompt` signatures + result envelope updated to List. The "deferred to Phase 5" code comment deleted. FE grep: 1 consumer file (`AnalyzeDrawer.jsx`), uses partial flag (not raw `forecast_meta`) — invisible to the List-shape change.

  • **Fix B (No silent except-swallow)** — `_to_ordinal` in `services/workbook_analyzer/forecaster.py` extended to accept ISO date strings via the parser's grammar (`%Y-%m-%d`, `%Y/%m/%d`, `%d/%m/%Y`, `%m/%d/%Y`, `%Y-%m`, `%Y/%m`). The CSV string-date path now reaches `run_forecast` → R² is computed → low-signal flag gate is reachable. Caller logs swallowed `ValueError` with `exc_info=True` AND surfaces `failure_reason` on the per-source meta entry; no silent holes.

  • **Fix C (Notes empty-body deletion contract)** — `_AnalysisNoteIn.body` + `AnalysisNote.body` (models/analysis.py) changed from `min_length=1` to `min_length=0`. Empty-body POST appends `{body: ""}` as a deletion history event; BC mirror `notes` becomes `""` (NOT null — divergence vs G6 documents.notes locked in Tightening 5). Idempotency unchanged — identical-body re-POST (including empty) returns tail entry.

  **Iter-2 lockdowns: 3 NEW + 7 UPDATED.**
  • NEW: `test_track_a_phase4_iter2_corrective.py` (3/3 PASS) covering `_to_ordinal` grammar + empty-append + CSV noisy-data E2E.
  • Updated 3 tests in `test_track_a_phase4_forecaster_tuning.py` (forecast_meta dict → list).
  • Updated 4 tests in `test_track_a_phase3_prompt_fix.py` (forecast_meta dict → list).

  **Aggregate Phase 4 lockdown status — 55/55 PASS in 13.44s** across 7 test files (forecaster tuning + versioning+multi + iter-2 corrective + engagement revival + Phase 3 prompt-fix regression + Phase 3 narration regression + v1 byte-identical guard).

  **Self-verification against LIVE preview** (`/tmp/phase4_iter2_verify.py` — raw curl, real `shield_invoke`):
  • J21: `forecast_meta = List[1]`, real-LLM round-trip OK, R²=0.9999918341972287 — **PASS**
  • J23: empty-body append + BC mirror `""` + idempotent re-POST — **PASS**
  • J24: CSV string-date coercion worked, R²=0.0052, low-signal flag fired — **PASS**

  **Discipline rails — iter-2 observed:**
  • Honesty Protocol — surfaced violations explicitly; no silent re-roll.
  • All `except` blocks in Phase 4 code now log with `exc_info=True` AND document the swallow contract inline.
  • No new env vars / migrations / Track B retouch / new UI components / `shield_invoke` signature change.
  • R3 ground-truth re-read on all four affected files (forecaster, workbook_analysis, analyze_narration, models/analysis) before each fix.
  • Iteration budget: 2/3 used. Iteration 3 reserved for unforeseen architectural surprises only.

  **VERBATIM CURL EVIDENCE — `/tmp/phase4_iter2_verify.py` against `https://akki-executive.preview.emergentagent.com` (2026-06-04 11:50Z):**
  ```
  === Phase 4 iter-2 raw verification — https://akki-executive.preview.emergentagent.com ===

  J21 PASS — forecast_meta = List[1], date_col='month', value_col='actual_sales', r2=0.9999918341972287
  J23 PASS — empty body appends as history event, BC mirror = '', idempotent on re-fire.
  J24 PASS — CSV string dates coerced, R²=0.0052, low-signal flag fired.

    J21: PASS
    J23: PASS
    J24: PASS
  ```
  • **J21** — real `shield_invoke` round-trip via the LIVE preview synthesize endpoint; response carries `forecast_meta` as a 1-element List per Tightening 1.
  • **J22** — already PASS from the first tester pass (multi-workbook synthesis run with prefixed-sheet citations); not re-verified in iter-2 because no iter-2 fix touched that path.
  • **J23** — three-step curl: non-empty note → empty-body POST (200, not 422) → idempotent empty re-POST returns the same tail entry id; `notes_history` len = 2, BC mirror `notes` = `""` (NOT null).
  • **J24** — CSV upload with ISO-string date cells; engine fits a model thanks to the Fix B `_to_ordinal` extension; `R² = 0.0052` is well below the `_FORECAST_LOW_R2_THRESHOLD = 0.30` gate, so `partial_narration_missing_forecast_low_signal: true` fires on the response. Pre-iter-2 this entire code path was dead — exception was swallowed, `r2` stayed `None`, flag never fired.

  **Tightening 2 — Phase 5 deprecation flag (SCHEDULED-FOR-REMOVAL):**
  • `analyses.narration` top-level BC mirror — duplicates `analyses.runs[-1]` content. Removal: Phase 5 after FE migrates to `runs[-1]`.
  • `analyses.notes` + `analyses.notes_updated_at` top-level BC mirrors — duplicate `analyses.notes_history[-1]` content. Removal: Phase 5 after FE migrates to `notes_history[-1]`.
  Both deprecation flags carry forward into Phase 5's Pre-Read — DO NOT remove until the FE consumer is verified migrated (single grep target on `AnalyzeDrawer.jsx`).

- Phase 5 (Work Studio Document Lifecycle Restoration): W1 copy + W2 Compile + W3 Enhance + W4 Brief save + W5 Draft + W6 Report/Deck blank + card fig-53 + Loading Checklist modal + Document Review drawer re-skin + Drafting Drawer + schema additive fields → ✅ SHIPPED 2026-06-04 (iter-1 11-item ship + iter-2 4-failure corrective). **69/69 lockdown PASS** across Phase 5 (14) + Phase 4 (21) + Phase 3 (25) + v1 byte-identical guard (2) + engagement revival (7). Live LLM compile evidence on report+docx + minutes+docx + 3 historical enhance/minutes completions in DB.

  **Iter-1 ship — 11 scope deliverables (single coherent dispatch with 5 user-approved tightenings):**
  • W1 — `pages/WorkStudio.jsx:1085` empty-state copy "below" → "above". Grep `actions below` = 0 hits.
  • W2 — `/work-studio/compilations/{id}/start` endpoint (idempotent per Tightening 3); LoadingChecklistModal + auto-open chain.
  • W3 — CSRF token threaded into `hooks/useStreamingProgress.js` for `/stream` endpoints (real failure cause; Pre-Read hypothesis was wrong — revised on curl evidence at `/tmp/phase5_w3_repro_v2.py`).
  • W4 — ExportModal success modal carries "Saved to Drafts & Briefs" breadcrumb + `akki:open-document-overlay` event + cards-section pulse.
  • W5 — `/contexts/{cid}/documents/manual-create` NEW endpoint (was 405); `DraftingDrawer.jsx` new component (273 LOC) with tiptap autosave + stable `draft_session_id` (Tightening 5).
  • W6 — `CreateArtefactModal` blank branch dispatches `akki:open-drafting-drawer`.
  • Card spec fig-53 — additive fields `source_count`, `contributor_count`, `akki_generated` on `work_studio_exports` inserts (4 call sites).
  • Loading Checklist modal — NEW component (207 LOC), step-by-step progression with HOLD on "Finalising…" (Tightening 2).
  • Drawer re-skin — `data-phase6="true"` on Edit toggle + Inline-edit mode indicator + Revise-with-AI button (line 435 / 767 / 817); PDF hides Revise-with-AI via JSX conditional.
  • Drafting Drawer — see W5.
  • Schema additive fields — on `work_studio_exports` collection; no migration; RAG threshold flipped 80→75 across 3 files.

  **Iter-2 corrective dispatch (2026-06-04 19:35Z) — 4/4 root-cause fixes shipped:**
  • **Fix A (Listing endpoint stripped additive fields)** — `services/work_studio_overlay.py:259-300` projection allow-list extended with `source_count`, `contributor_count`, `akki_generated`, `confidence_pct`, `export_kind`, `status`. Iter-1 wrote the fields on insert but the projection dropped them; tester confirmed all four returned None on the live listing. Verified via `/tmp/phase5_iter2_listing_repro.py`.
  • **Fix B (Lifecycle terminus 4-hop break at TWO hops)** — Hop 3: `_create_continue_chat` at `routers/work_studio_export.py:967-1015` now writes `category` (via new `_KIND_TO_CATEGORY` mapping mirroring FE KIND_TABS) + Phase-5 fields onto the **sibling `documents` collection row**; iter-1's misread that the universal listing reads from `work_studio_exports` was wrong — it reads from `documents`, which needed the same additive fields mirrored. Hop 4: `LoadingChecklistModal.onComplete` now threads `continue_doc_id`; auto-open routes through the canonical `?doc_id=continueDocId` URL contract (the DocumentDrawer expects a documents-collection id, not a work_studio_exports id — iter-1's 404'd silently). `pages/WorkStudio.jsx:DocumentRow` extended with fig-53 row 2 (sources · contributors · Akki Generated · confidence chip).
  • **Fix C (Minutes DOCX renderer gap)** — new product gap surfaced during iter-2: `kind=minutes format=docx` had no renderer ("No renderer for kind=minutes" rejection at `routers/work_studio_export.py:764`). Fix: `services/work_studio_export.py:111` accepts `kind="minutes"` in `validate_content` (treated as report-shape); `routers/work_studio_export.py:740-758` branches `kind in ("report", "minutes")` for both DOCX + PDF dispatch, reusing `_ex.render_report_docx/pdf`. Zero new templates. Live compile: `status=complete`, `sha256=7d889166be2cf3eef9...e5c36237aa`.
  • **Fix D (W3 endpoint alignment — structural verification, no code drift)** — iter-1 Pre-Read's prose mentioned the invented path `/work-studio/documents/{aid}/enhance` but the shipped code never called it. EnhanceModal already targeted the canonical `/work-studio/enhance/{kind}/stream`. Iter-2 added `akki:open-enhance-modal` event handler at `pages/WorkStudio.jsx:715-730` so the DraftingDrawer's Enhance CTA routes through the same modal — avoiding the temptation of inventing an alias endpoint. Grep confirms zero call sites of the invented path.

  **VERBATIM LIVE COMPILE TRACE (4-hop evidence from `/tmp/phase5_iter2_e2e_verify.py`, 2026-06-04 19:35Z):**
  ```
  ══ Compile report/docx ══
    HOP 1 PASS  export_id=384115b1-6f40-4d…
    HOP 2 PASS  status=complete  wall_s=124  continue_doc_id=66104789-…
    HOP 3 PASS  doc in /documents?category=report  category=report
    HOP 4 PASS  source_count=0, contributor_count=1, akki_generated=True

  ══ Compile minutes/docx ══
    HOP 1 PASS  export_id=d30caff8-2985-496a-9b2b-9bbd8d6a6335
    HOP 2 PASS  status=complete  sha256=7d889166be2cf3eef9...e5c36237aa
    HOP 3 PASS  doc_id=8db7d08e-…  category=minutes
    HOP 4 PASS  akki_generated=True, source_count=0, contributor_count=1

  ══ Enhance minutes (W3) ══
    3 historical completions in db.work_studio_exports for
    {source:enhance, kind:minutes, account:admin@akki.ai}
    — all status=complete with sha256 populated.
  ```

  **Phase 6 deferred items (verified reachable as `data-phase6="true"` stubs in source):**
  1. **Inline rich-text edit for DOCX** — `components/work_studio/overlay/DocumentOverlay.jsx:435` Edit toggle disabled with `data-phase6="true"` + tooltip "Inline edit ships in Phase 6".
  2. **Inline slide edit for PPTX** — same toggle covers PPTX (Phase 6 split decision deferred); editor is locked to `editable: false` at `DocumentOverlay.jsx:680`.
  3. **Revise-with-AI panel with diff view** — `components/work_studio/overlay/DocumentOverlay.jsx:817` button disabled with `data-phase6="true"` + tooltip "Revise with AI ships in Phase 6"; **HIDDEN entirely for PDF** via `{doc.output_format !== "pdf" && (...)}` JSX conditional.

  **What I almost shipped silently (lessons captured in the sprint memo for the next agent):**
  1. **Listing projection allow-list invisible to allow-list testers** — `overlay_payload()` stripped the additive fields the pytest layer never read end-to-end. Future Pre-Reads MUST grep both insert sites AND projection allow-lists.
  2. **Pre-Read invented an endpoint path that didn't exist in `/openapi.json`** — Pre-Read self-grep MUST cross-check endpoint names against the OpenAPI inventory, not just internal consistency. The "self-consistency check" in iter-1 was too narrow.
  3. **4-hop terminus break needed an explicit hop-by-hop trace** — "pytest passes therefore wiring works" is the same fallacy that bit Phase 4 iter-1. Future "lifecycle" claims need a curl that walks every hop.
  4. **Minutes-DOCX renderer gap surfaced only by attempting the full journey** — the renderer dispatch is its own contract. Future "ship a new kind" Pre-Reads MUST trace through validator + prompt + dispatch.

  **No `shield_invoke` signature change.** **No new env vars / migrations / Track B retouch / new UI component libraries.** All 8 backend + 8 FE touched files ruff/ESLint clean.

  **Iteration budget**: 2/3 used. Iter-3 reserved for unforeseen architectural surprises only.

  Memos: `sprints/TRACK_A_PHASE_5_WORK_STUDIO_LIFECYCLE.md`.


### Track B — QA cleanup
- Phase B1 (small mechanical onboarding + signin): **O4** ✅ + **O6** ✅ + **G1** ✅ (Fig 20 — `/sign-in` → `/signin` × 4 buttons) + **G2 Fig 22 modal** ✅ (SessionTimeoutGuard handler gated on `account`); **O7** ✅ Fig 7. Phase status: ✅ SHIPPED — tester PASS Journeys 4-v2, 6, 7, 8, 9 (5/5 incl. regression), 2026-06-04. Memos: `sprints/TRACK_B_PHASE1_FIG7_V2_ROOT_CAUSE_FIX.md`, `sprints/TRACK_B_PHASE1B_O4_O6_FIG20_FIG22.md`.
- Phase B2 (Task Manager lifecycle): TM1 (filter badges) + TM2 (Commission button + full Closure flow) + TM5 (View more → follow-up emails page) → ✅ SHIPPED — tester PASS Journeys 14-17 (8/8 incl. cross-tenant), 2026-06-04. Commission/Close endpoints (idempotent, audit-logged); filter-tab live count badges via `/api/tasks/counts`; FollowUpDraftsCard "View more" → `/app/cycle/drafts`. Memo: `sprints/TRACK_A_PHASE2_AND_TRACK_B_PHASE2_combined.md`.
- Phase B3 (Questions feature wiring): G13 (related-doc-as-attachment) + G14 (Share CTA) + G17 (Share modal full spec) + G19 (response association) + G20 (Open-until-confirmed) + G21 (reopening flow) + G22 (response history) + G23 (empty state + Go to Document CTA) → ✅ SHIPPED 2026-06-04 — tester PASS Journeys 21-24 (4/4). Memo: `sprints/TRACK_A_PHASE3_AND_TRACK_B_PHASE3_combined.md`.
- Phase B4 (cross-feature surfacing): G11 (Open Question card click → Your Questions; doc-extracted Q surface) → ✅ SHIPPED 2026-06-04 — tester-verified 4/4 on real `shield_invoke` extraction (`Project Lighthouse Q3 Brief.pdf`, doc id `a19b457e...`). Promoter writes verified; G13 attachment surface confirmed in live drawer. T1(d) drawer-open subtask required a same-dispatch B3 hook-order hotfix (`Questions.jsx` 9-hook hoist) + 1-char App.js unblocker — both fixed and smoke-verified. Memos: `sprints/TRACK_B_PHASE_B4_G11_DOC_QUESTION_SURFACING.md`, `sprints/TRACK_B_PHASE3_HOTFIX_DRAWER_HOOK_ORDER.md`.
- Phase B5 (Document workflow + Calendar polish): G6 (Notes autosave full spec) + G7 (Send Share Field-required error) + G10 (Calendar text in fig 32 to be removed) → ✅ COMPLETE 2026-06-04 (3/3 done) — **G6 ✅ tester-verified 5/5**. **G7 ✅ tester-verified 4/4**. **G10 ✅ smoke-verified** (tester pass intentionally skipped per credit-discipline — pure deletion with grep-zero proof; same pattern as the B3 drawer hotfix). Memos: `sprints/TRACK_B_PHASE_B5_G6_NOTES_AUTOSAVE.md`, `sprints/TRACK_B_PHASE_B5_G7_SEND_SHARE_VALIDATION.md`, `sprints/TRACK_B_PHASE_B5_G10_CALENDAR_LEAK.md`.

---

## Section 5 — User-Side Blockers (no code action possible)

- SendGrid Inbound Parse console URL: format `https://user:URL_ENCODED_PASS@inbound.akki.syni.ai/api/inbound/sendgrid` with `%` encoded as `%25` (unblocks C1 Email Reply 550 + P8 inbound loop)
- Google GCP OAuth creds (unblocks C2 Google sign-in flow)
- Prod env: `COHORT_EMAILS_ENABLED=true` (without this, cohort approval emails won't send in prod)
- Prod env: `POSTMARK_WEBHOOK_SECRET` decision — keep env var OR request follow-up to remove boot-guard at `server.py:573`
- Optional prod cleanup: `python3 /app/backend/migrations/cleanup_postmark_fixtures.py`

### Section 5b — New open bugs (logged, NOT auto-fixed)

- **BUG-ANL-002 — Analyze upload picker silent-failure on file selection** → ✅ COMPLETE 2026-06-04T21:30:00Z (single-dispatch surgical fix, iter 1 of 1).
  - Symptom: `/app/analyze?context_id=<valid>` → click Upload → pick file → silently nothing happens (no toast, no progress, no error); refresh "fixes" it, retries "sometimes work".
  - Root cause: `pages/AnalyzeJournal.jsx:135` reset `fileInput.current.value = ""` *inside the success branch* of the `try`. On the failure path the input retained the picked filename. The OS file picker doesn't fire `onChange` when the user picks the same file the input already holds (canonical HTML quirk). User became stuck in a silent-retry loop until refresh.
  - Diagnosis evidence: `/tmp/bug_anl_002_diagnose.py` confirmed happy-path works; `/tmp/bug_anl_002_confirm_stale_input.py` reproduced the silent retry — pick-after-failure `change_log=[]` and `input.value='C:\\fakepath\\bug_anl_002_sample.csv'` (stuck).
  - Fix: relocate the `fileInput.current.value = ""` cleanup from the success branch to the `finally` block — always clears after attempt, regardless of outcome. Net +12 LOC / -1 LOC, comment + relocated line.
  - Verified on live preview via `/tmp/bug_anl_002_upload_journey.py` — 8/8 assertions PASS including the critical `B3_finally_cleared_after_failure` (was the silent-bug state pre-fix) and `C1_retry_same_file_fired_change` (was FAIL pre-fix).
  - No backend change; no new dependencies; no swallowed exceptions added; no Phase 5/Phase 6 retouch; no other upload surface affected (Documents `UploadModal` clears its input on close — already safe).
  - Memo: `sprints/BUG_ANL_002_ANALYZE_UPLOAD_SILENT_FAILURE.md`.

- **BUG-ANL-001 — Analyze Journal route fires `context_id_required` toast on direct `/app/analyze` load** → ✅ COMPLETE 2026-06-04T20:05:00Z (user picked option (a) — route guard).
  - Screenshot: https://customer-assets.emergentagent.com/job_feature-docs/artifacts/mc4gtnev_Screenshot_20260604_222916_Chrome.jpg
  - Root cause: `AnalyzeJournal.jsx` mount-time fetches + the multipart upload POST both assumed `context_id` was present in URL or on the account row's `active_context_id`. When neither was set, the upload 400'd with `context_id_required` (`backend/routers/workbook_analysis.py:660-665`) and the user saw the toast.
  - Fix landed at `frontend/src/pages/AnalyzeJournal.jsx` (+35 / -6 LOC):
    - Mount-time `useEffect` reads `activeContextId` and `account.default_context_id` from `useAuth()`. If URL is missing `?context_id=`, the URL is backfilled via `setParams({...}, { replace: true })`; if no context anywhere, redirect to `/app/home` with `toast.info("Pick a context to view your Analyze Journal.")`.
    - `onCreate` upload handler now threads `effectiveContextId` into the multipart `FormData` defensively (explicit > implicit).
  - Verified via live-preview screenshot: Case 1 (no `context_id`) → URL backfilled to `?context_id=aff5e102-04b8-4948-9f6b-27c9eca1f0d7`, NO toast. Case 2 (valid `context_id`) → listing renders cleanly with upload form + 8+ history rows.
  - Coverage sweep: 8 sibling routes audited (`Events.jsx`, `Questions.jsx`, `TaskManager.jsx`, `InboundQueue.jsx`, `WorkStudio.jsx`, `CompanyHome.jsx`, `Learn.jsx`, `TenantSettings.jsx`) — all already handle missing-context safely (mostly via `if (!cid) return` early-exits OR `WorkspaceEntryGate`). NO sibling bugs of the same pattern.
  - Memo: `sprints/BUG_ANL_001_ANALYZE_ROUTE_GUARD.md`.

---

## Section 6 — Active Phase

**None active.** Track A Phase 5 ✅ COMPLETE 2026-06-04 (iter-1 11-item ship + iter-2 4-failure corrective: listing projection / lifecycle terminus 4-hop / minutes-DOCX renderer / W3 endpoint alignment). All 11 shipped phases verified (Track A Phase 1+2+3+4+5, Track B B1 incl. B1b + B2 + B3 + B4 + B5). Paused pending user pick of next phase.

---

## Section 7 — Last Updated

- **Written:** 2026-06-04T21:30:00Z (BUG-ANL-002 fixed in one surgical dispatch — `AnalyzeJournal.jsx` `finally`-block clear of `input.value` after every upload attempt; 2 diagnostic Playwright scripts + 1 lockdown Playwright script all green on live preview).
- **Agent:** bug-anl-002-upload-silent-failure.
- **Mode:** Single-file FE fix, no backend change, no new dependencies. Evidence: `/tmp/bug_anl_002_diagnose.py` (happy-path works) + `/tmp/bug_anl_002_confirm_stale_input.py` (silent-retry root cause: `change_log=[]` on same-file re-pick after failure + `input.value` stuck at picked filename) + `/tmp/bug_anl_002_upload_journey.py` (post-fix 8/8 assertions PASS including the critical `B3_finally_cleared_after_failure` and `C1_retry_same_file_fired_change`). Memo: `sprints/BUG_ANL_002_ANALYZE_UPLOAD_SILENT_FAILURE.md`.
- **Counts after BUG-ANL-002 close:** ✅31 / 🟡0 / ❌4 / 🚧2 across the original 37 QA items (unchanged). Plus Bug #30 ✅ + Track A Phase 4 ✅ + Track A Phase 5 ✅ + BUG-ANL-001 ✅ + BUG-ANL-002 ✅. **0 new open bugs.**

---

## Section 8 — Cumulative Health Snapshot (2026-06-04 21:30Z BUG-ANL-002 close)

- ✅ **11 phases shipped + verified**: Track A Phase 1 + 2 + 3 + 4 + 5, Track B B1 (incl. B1b) + B2 + B3 + B4 + B5.
- ✅ **2 standalone bugs closed**: BUG-ANL-001 Analyze Journal route guard + BUG-ANL-002 Analyze upload silent-failure on same-file retry.
- 🟡 **0 phases pending tester.**
- ❌ **4 ❌ open items** across the 3 QA docs (unchanged).
- 🟠 **0 new open bugs.**
- 🚧 **2 USER-BLOCKED items unchanged:** SendGrid Inbound Parse webhook config (TM3), Google GCP OAuth creds (G2).
- ✅ **v1 byte-identical guard intact** (2/2 across all 11 phases).
- ✅ **Phase 5 lockdown sweep 14/14 PASS** (+ 1 integration-marked deselected).
- ✅ **Aggregate regression sweep 69/69 PASS** (Phase 5 iter-1 + iter-2 + Phase 4 + Phase 3 + v1 guard + engagement revival).
- ✅ **BUG-ANL-002 lockdown 8/8 PASS** (`/tmp/bug_anl_002_upload_journey.py` against live preview).
- ✅ **Phase 6 deferral surfaces verified reachable** in source at `DocumentOverlay.jsx` lines 435 / 767 / 817; PDF hides Revise-with-AI via JSX conditional.
- ✅ **Voice-lint clean** across customer-copy surfaces.
- ✅ **ESLint clean** on every file touched.
- ✅ **Ruff clean** on all backend files touched during Phase 5.

---

**Paused per orchestrator instruction.** NOT auto-starting Phase 6 / any backlog hygiene pass / any sibling-route guard generalisation. The minutes-template polish proposal from the Phase 5 iter-2 finish summary remains **DECLINED as gold-plating**. User decides next dispatch — per the BUG-ANL-002 close-out brief, the Phase 6 Pre-Read (inline DOCX edit / inline PPTX edit / Revise-with-AI diff panel — surfaces stubbed at `DocumentOverlay.jsx` lines 435 / 767 / 817) is the locked next dispatch when the user lands the formal brief. Holding for that signal.
