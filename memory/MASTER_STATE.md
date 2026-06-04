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

**Total items across 3 QA docs: 37. ✅ 11 · 🟡 5 · ❌ 19 · 🚧 2 · ❔ 0.** (Plus 1 standalone Bug #30 outside the 3 docs.)

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
| O4 | fig 2, fig 3 | "Create your first cycle" card | "Why does 'Create your first cycle' option redirect the user to the page in figure 2?" | "I think the user should be redirected to the Task Manager Module shown in figure 3" | 🟡 PARTIAL — `NEEDS_RE-DISPATCH` | Prior dispatch shipped to `/app/cycle?wizard=1` (Cycle Setup Wizard) per spec G21. QA doc explicitly expects Task Manager. Divergence. |
| O5 | fig 4 | "Upload a Document" card | "Why does 'Upload a Document' option redirect the user to the page in figure 4?" | "I think the user should be prompted to upload a document instead then redirected to the Document Journal Page" | ✅ SHIPPED | P0-B Card 2 — routes to `/app/documents?upload=1`. Aligns with QA expectation. |
| O6 | fig 5, fig 6 | "Try the Demo" card | "Why does 'Try the Demo' option redirect the user to the page in Figure 5 after going through the steps in figure 6?" | "I think the user should land on the Home Page" | 🟡 PARTIAL — `NEEDS_RE-DISPATCH` | Prior dispatch shipped to `/app/cycle` (Cycle Manager) per spec G22. QA doc explicitly expects Home Page. Divergence. |
| O7 | fig 7 | Begin button | "Why is the text in the button shown in figure 7 not visible?" | "I think the text should be 'Begin'" | 🟡 PARTIAL | Track B Phase 1 Fig 7 v2 root-cause fix shipped 2026-06-03T21:09:00Z (`.akki-overline` descoped from `<button>` in `index.css`). Live-DOM verified white-on-oxblood delta=209. Tester re-verification pending. |
| O8 | fig 8 | Greeting | "Why is the salutation in figure 8 'there'?" | "I think this should be personalized" | ✅ SHIPPED | Cleanup Task B — personalised greeting. |
| O9 | fig 8 | Help callout | "Why do we have a not visible black callout that is circled in figure 8 under the Help option?" | (callout should be removed / visible) | ✅ SHIPPED | Cleanup Task C — hidden black callout removed. |

---

### Doc 2 — Task Manager QA (5 items; TM2 carries a 12-line closure-flow spec inline)

| # | Figs | Surface | Symptom (verbatim) | Expected (verbatim) | Status | Notes |
|---|---|---|---|---|---|---|
| TM1 | fig 40 | Filter tabs | "Why do the filter tabs in figure 40 missing number badges?" | "I think each tab should have a number badge if there is content" | ❌ OPEN | Track B Phase B2. |
| TM2 | fig 41 | Task draft / closure flow | "How can a user commission a task in draft as shown in figure 41?" | "I think we should add a commission button below the draft, progress and date metadata." **Closure flow spec (verbatim from doc 2 paragraphs 2-13):** "Once a task is active the button changes to [Close]. When the user clicks [Close], a confirmation modal is displayed. Modal Content — Title: Close Task / Supporting Text: 'Are you sure you want to close this task? Once closed, the task will be marked as complete and cannot be reopened.' / Primary CTA: Close Task / Secondary CTA: Cancel. Expected Behaviour: Selecting Close Task updates the task status to Closed. Closed tasks are removed from active task lists and displayed within closed tasks filter tab. Closed tasks become read-only and can no longer be edited, restarted, or reopened. The task closure date and time should be recorded and displayed in the task card." | ❌ OPEN | Track B Phase B2. One item logically; full closure-flow spec is inline. |
| TM3 | fig 42 | Email Reply | "Why can't a user respond with their contribution when they send it via email received by clicking the 'Email Reply' circled in figure 42 once a task is commissioned? The response to user is '550 Mailbox not found'" | (Email Reply should accept inbound contributions) | 🚧 USER-BLOCKED | SendGrid Inbound Parse console URL needs Basic Auth embedded + `%25` encoding. See Section 5. |
| TM4 | fig 43 | Magic link | "Why is the link sent via the magic link shown in figure 43 not valid?" | (magic link should be valid) | ✅ SHIPPED | C1-revised Phase B — 6 distinct error codes; valid-link path verified. |
| TM5 | fig 40 | "View more" link | "Where does the view more button circled in green in figure 40 redirect the user to?" | "I think the button should open a page that shows Follow Up Emails drafted by Akki to contributors with pending contributions" | ❌ OPEN | Track B Phase B2. |

---

### Doc 3 — Google Login + Doc Reader + Calendar + Open Questions QA (23 items)

| # | Figs | Surface | Symptom (verbatim) | Expected (verbatim) | Status | Notes |
|---|---|---|---|---|---|---|
| G1 | fig 20 | Signin redirect | "Why is the user being redirected https://akki-executive.emergent.host/ to instead of https://akki-executive.emergent.host/signin after clicking the button shown in figure 20?" | (button in fig 20 should redirect to /signin) | ❌ OPEN | Track B Phase B1. Previously BLOCKED_NEED_SCREENSHOT — the doc names the wrong-target URL explicitly. The screenshot in fig 20 identifies WHICH button; without fig 20 image I cannot identify the specific surface (header CTA, footer, etc.). Still blocked on fig 20 image. |
| G2 | fig 21, fig 22 | Google signin | "Why can't the user sign in with google as shown in figure 21? User encounters the error in figure 22 after being redirected to the platform?" | (Google signin should succeed; no error in fig 22) | 🚧 USER-BLOCKED | C2 row "Google sign-in fails" — needs GCP OAuth creds. The fig 22 post-redirect error is part of this same item per the QA doc (NOT a separate Fig 22 item as the prior matrix had). |
| G3 | fig 23, fig 24 | Continue → workspace | "Why is the user redirected to figure 24 after clicking continue in figure 23?" | "I think the platform should first redirect to the company/workspace the document belongs to eg. Lemasy Limited then redirect to the workspace document journal" | ✅ SHIPPED | P0-B Card 4 — Continue lands at workspace doc journal with context. |
| G4 | fig 25.1, fig 25.2 | Generate Brief | "Why does clicking the generate brief button in figure 25.1 result in the error shown in the same figure despite having the intelligence (refer to figure 25.1) and signals (refer to figure 25.2) already generated?" | (brief generation should succeed when intelligence + signals exist) | ✅ SHIPPED | P0-A. |
| G5 | fig 25.2 | "Signals tab" terminology | "What is the signals tab as indicated in the error in figure 25.2" | (clarification ask) | ✅ SHIPPED | Subsumed by G4 fix — the error string in 25.2 is gone post-P0-A. |
| G6 | fig 26 | Notes autosave | "Why is the platform not saving the notes made by the user in figure 26?" | "I think: The notes should be automatically saved in the background as the user enters or modifies content. Once the note is saved, display the date and time the note was last updated eg. Last updated: 2 June 2026, 10:45 AM. The existing note can be edited at any time and any changes made during editing should continue to be auto-saved. Users should be able to delete a note and a confirmation prompt should be displayed before deletion." | ❌ OPEN | Track B Phase B5. |
| G7 | fig 27, fig 28 | Send Share error | "Why does the error in figure 27 appear when the user clicks on 'Send Share' button in the same figure. The modal in figure 27 is pops up when user clicks 'share document' in figure 28?" | (Send Share should succeed without "Field required" false-positive) | ❌ OPEN | Track B Phase B5. |
| G8 | fig 29, fig 30 | Upload button consistency | "Why does the Upload document button in figure 29 behaves differently from other upload buttons in the platform?" | "I think all upload document buttons should follow the process shown in figure 30" | ✅ SHIPPED | Cleanup Task D — Upload Document button consolidation. |
| G9 | fig 31, fig 25.2 | Pulse signals | "Why are there no signals in the pulse page shown in figure 31 despite generating signals in page shown in figure 25.2?" | (signals generated in doc reader should propagate to Pulse) | ✅ SHIPPED | P1-A — doc-extracted signals propagate to Pulse. |
| G10 | fig 32 | Calendar text leakage | "Why do we have the text circled in figure 32?" | "I think the text should be removed" | ❌ OPEN | Track B Phase B5. Calendar edit modal `SELECTED — COMMITS ON SAVE CHANGES` placeholder. |
| G11 | fig 25.1, fig 33 | Doc-question surfacing | "Where can a user access the questions surfaced from a document as shown in figure 25.1?" | "I think the user can access the questions by clicking on Open Question card shown in figure 33." | ❌ OPEN | Track B Phase B4. Card surface exists but click-through-to-Q4Y wiring + 0-count fix not in. |
| G12 | fig 34 | Your Questions page | "When a user clicks an Open Question card, they are redirected to the Your Questions page in Figure 34." | "The Your Questions page should displays all generated questions as individual cards. The questions cards should contain question and a status badge (Open or Answered). Users should be able to filter by status (All, Open, Answered) and sort by Most Recent or Oldest." | ✅ SHIPPED | Q4Y — filter-by-status, sort, status-badge all in. |
| G13 | — | Question side drawer | "When a user clicks on a question card, a side drawer opens displaying: Full question, the Status badge and the related document as an attachment." | (drawer must show all three) | 🟡 PARTIAL | Drawer exists; full Q + status badge surfaced; **related-doc-as-attachment field NOT surfaced**. Track B Phase B3. |
| G14 | — | Drawer CTAs | "The CTA buttons at the bottom left of the side drawer are: [Use in Solva] [Use in Chat] [Share] [Mark as Answered]" | (four CTAs in this exact order) | 🟡 PARTIAL | 3 of 4 shipped (Use in Solva, Use in Chat, Mark as Answered). Share CTA pending. |
| G15 | — | Use in Solva CTA | "Use in Solva redirects the user to Solva Page where user selects one of the four available Solva options. The selected question is then automatically populated into the Solva input field associated with the chosen option." | (full spec verbatim) | ✅ SHIPPED | Q4Y "Use in Solva". |
| G16 | — | Use in Chat CTA | "Use in Chat, opens a chat session and automatically pre-populates the selected question. The response" | (full spec verbatim — sentence ends abruptly in doc) | ✅ SHIPPED | Q4Y "Use in Chat". |
| G17 | — | Share CTA | "Share, opens a Share Question modal that allows users to: enter one or more email recipients, add an optional message and send the question and related document link via email." | (full spec verbatim) | ❌ OPEN | Track B Phase B3. |
| G18 | — | Mark as Answered CTA | "Mark as Answered, allows users to manually indicate that their question has been sufficiently resolved. On click, the question status is updated from Open to Answered." | (full spec verbatim) | ✅ SHIPPED | Q4Y "Mark as Answered". |
| G19 | — | Response association | "When user submits a question to Solva or Chat the resulting response provided is automatically associated with the originating question. The question record should store: response source (Solva or Chat), Date answered and Link to the Solva session or Chat conversation. This is information will be displayed in the Question drawer as Response showing Solva Session Link or Chat Conversation Link with a date and time eg. 2nd June 2026 10:15am. Selecting a response redirects the user to the associated Solva session or Chat conversation where the full response can be viewed." | (full spec verbatim) | ❌ OPEN | Track B Phase B3. |
| G20 | — | Open-until-confirmed | "A question may have response links associated with it and still remain Open until the user confirms resolution." | (status stays Open even with response links) | ❌ OPEN | Track B Phase B3. Folds into G19 implementation. |
| G21 | — | Reopening flow | "Answered questions can be reopened at any time when the user performs any of the following actions: Use in Solva, Use in Chat, Share" | (specified actions reopen an Answered question) | ❌ OPEN | Track B Phase B3. |
| G22 | — | Response History | "Upon reopening the question status changes from Answered to Open, a new response session is created, any subsequent Solva analyses or Chat conversations are automatically added to the Response History and existing response history is preserved and remains accessible." | (full spec verbatim) | ❌ OPEN | Track B Phase B3. |
| G23 | — | Empty state | "The Empty state of the Your Questions Page to be 'You have not generated any questions yet. Go to a document to generate questions.' And the CTA button 'Go to Document' that redirects the user to the Document Journal" | (full spec verbatim) | ❌ OPEN | Track B Phase B3. NEW ITEM — not in prior 29-bug matrix. |

---

### Out-of-3-docs items (preserved for continuity)

| # | Source | Surface | Symptom | Status |
|---|---|---|---|---|
| Bug #30 | User-surfaced (not in 3 docs) | Forecaster column-pair picker | `forecast_invalid: workbook_analyzer.forecaster: need at least 3 (date, value) pairs to fit` on a 28,626-row workbook with valid Date + Actual Sales columns | ❌ OPEN — folds into Track A Phase 3 (forecast → Solva narration); underlying picker still needs fixing. |

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
- Phase 2 (Chrome): Drawer mirroring Documents pattern + Analyze Journal listing + chat/objective input → ❌ NOT STARTED
- Phase 3 (Synthesis): Solva v2 narration + Bottom Line + drill-down tabs (What changed / What's likely next / What's odd / Sources / Export). Bug #30 folded here. → ❌ NOT STARTED
- Phase 4 (Multi-workbook + Versioning): Cross-file observation synthesis + refresh-creates-new-version + notes history → ❌ NOT STARTED

### Track B — QA cleanup
- Phase B1 (small mechanical onboarding + signin): **Adds** O4 `NEEDS_RE-DISPATCH` (Create your first cycle → Task Manager, not Cycle Setup Wizard) + O6 `NEEDS_RE-DISPATCH` (Try the Demo → Home Page, not Cycle Manager); **carries** G1 (signin redirect, BLOCKED_NEED_SCREENSHOT) + O7 Fig 7 (🟡 PARTIAL, tester re-verification pending) → 🟡 PARTIAL. Reshape NEEDED: B1 is currently scoped to "C2 Sign-in + Post-redirect + Fig 7"; reconciliation surfaces O4/O6 as NEW B1 work.
- Phase B2 (Task Manager lifecycle): TM1 (filter badges) + TM2 (Commission button + full Closure flow) + TM5 (View more → follow-up emails page) → ❌ NOT STARTED
- Phase B3 (Questions feature wiring): G13 (related-doc-as-attachment) + G14 (Share CTA) + G17 (Share modal full spec) + G19 (response association) + G20 (Open-until-confirmed) + G21 (reopening flow) + G22 (response history) + G23 (empty state + Go to Document CTA — NEW vs prior matrix) → ❌ NOT STARTED
- Phase B4 (cross-feature surfacing): G11 (Open Question card click → Your Questions; doc-extracted Q surface) → ❌ NOT STARTED
- Phase B5 (Document workflow + Calendar polish): G6 (Notes autosave full spec) + G7 (Send Share Field-required error) + G10 (Calendar text in fig 32 to be removed) → ❌ NOT STARTED

---

## Section 5 — User-Side Blockers (no code action possible)

- SendGrid Inbound Parse console URL: format `https://user:URL_ENCODED_PASS@inbound.akki.syni.ai/api/inbound/sendgrid` with `%` encoded as `%25` (unblocks C1 Email Reply 550 + P8 inbound loop)
- Google GCP OAuth creds (unblocks C2 Google sign-in flow)
- Prod env: `COHORT_EMAILS_ENABLED=true` (without this, cohort approval emails won't send in prod)
- Prod env: `POSTMARK_WEBHOOK_SECRET` decision — keep env var OR request follow-up to remove boot-guard at `server.py:573`
- Optional prod cleanup: `python3 /app/backend/migrations/cleanup_postmark_fixtures.py`

---

## Section 6 — Active Phase

None. Awaiting tester journey-completion verification (R3) for Track A Phase 1 + Track B Phase 1 (Fig 7), plus screenshots for Track B Figs 20 + 22.

---

## Section 7 — Last Updated

- **Written:** 2026-06-03T20:04:22Z (initial); 2026-06-03T20:43:17Z; 2026-06-03T20:58:11Z; 2026-06-03T21:09:00Z; 2026-06-04T03:24:00Z (Discipline Step 2 — Section 3 fully reconciled against the 3 source QA docs; Section 4 Track B reshaped to align with real open items)
- **Agent:** discipline-step-1 → track-a-track-b-phase1 → track-a-r3-blocker-fix → fig7-v2-root-cause-fix → master-state-reconciliation (this update)
- **Mode:** READ-ONLY on product code/tests/env this dispatch. Only files touched: this file + the audit memo.
- **Audit memo:** `sprints/MASTER_STATE_RECONCILIATION_2026-06-03.md`
