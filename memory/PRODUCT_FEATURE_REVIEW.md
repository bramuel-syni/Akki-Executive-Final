# AKKI Product Feature Review
_Generated: 2026-05-26_
_Source specs: AKKI_PRODUCT_SPEC.md (v1.1, 24 May 2026), AKKI_ONBOARDING_SPEC.md (v1.1, 25 May 2026)_
_Method: read-only audit. Spec text quoted verbatim. No paraphrasing._

## Legend
- ✅ Built — implementation matches spec
- 🟡 Partial — built but with gaps vs spec
- ❌ Not built — in spec, missing from code
- 🗄️ Archived — present in code but disabled/legacy
- ⚠️ Orphan — in code but not in spec (flag for review)

---

## Section 1: Feature Inventory (Spec → Implementation)

### §3.1 Synisense Shield (guardrail)

- **Spec text (verbatim):**
  > The deidentifier + canonical mint + reidentifier pipeline that owns every outbound LLM call.
  > … de-identifies inbound content (regex recognisers → Presidio → spaCy NER fallback), canonically tokens identifiers with HMAC-keyed mints, routes the de-identified payload through `llm_router.invoke()`, re-identifies the response, and writes an audit row + trust receipt.
- **Status:** ✅ Built (settled guardrail per spec §3 — "leveraged, not redesigned")
- **Backend file(s):** `backend/services/synisense/shield/deidentifier.py`, `canonical.py`, `reidentifier.py`, `llm_router.py`, `streaming.py`, `audit_log.py`, `trust_receipt.py`; `backend/services/synisense/regex_recognisers.py`
- **Frontend file(s):** none (server-side guardrail)
- **API endpoint(s):** invoked transitively by every LLM-producing journey
- **Test coverage:** `tests/test_no_direct_llm_calls_*` family + Shield unit tests

### §3.2 Trust Center / Master Audit (guardrail)

- **Spec text (verbatim):**
  > The user-facing forensic surface backed by the Shield audit log.
  > … view-time re-derivation of redactions per turn; per-turn drill-down with input SHA, tokenized prompt, tokenized LLM response, re-identified visible text, redactions, and audit chain; historical back-fill of pre-Shield-v1.x chats; gated plaintext endpoint that writes a `trust_center.plaintext_viewed` audit row on every read.
- **Status:** ✅ Built (settled guardrail per spec §3)
- **Backend file(s):** `backend/routers/trust_center.py`, `backend/services/backfill_shield_v1.py`, `backend/routers/admin_shield_backfill.py`, `backend/routers/healthz_shield.py`
- **Frontend file(s):** `frontend/src/pages/TrustCenter.jsx`
- **API endpoint(s):** `/api/trust-center/*`, `/api/healthz/shield`
- **Test coverage:** Trust Center methodology + chunk-(d) tests

### §3.3 ClamAV upload scanning (guardrail)

- **Spec text (verbatim):**
  > Virus scanning sidecar invoked on every document upload.
  > … scans uploaded files server-side before persistence; rejects infected files with an audit row.
- **Status:** ✅ Built (settled guardrail per spec §3)
- **Backend file(s):** `backend/services/clamav_service.py`, `backend/routers/healthz_clamav.py`
- **Frontend file(s):** none
- **API endpoint(s):** `/api/healthz/clamav`
- **Test coverage:** `tests/test_hardening_step1_healthz_clamav.py`

### §3.4 Postmark inbound email (MailboxHash routing) (guardrail)

- **Spec text (verbatim):**
  > Inbound email gateway for follow-up replies and document-by-email.
  > … ingests inbound email via Postmark webhook, routes by `MailboxHash` to the correct context / cycle / contributor record.
- **Status:** ✅ Built (settled guardrail per spec §3)
- **Backend file(s):** `backend/routers/inbound_email.py`, `backend/routers/inbound_queue.py`
- **Frontend file(s):** none
- **API endpoint(s):** Postmark webhook
- **Test coverage:** inbound-email tests in suite

### §3.5 Audit invariant violations (guardrail)

- **Spec text (verbatim):**
  > Cross-cutting integrity check on the audit chain.
  > … detects and surfaces audit-chain invariant violations (envelope mismatch, missing trust receipts, broken hash chain) for operators.
- **Status:** ✅ Built (settled guardrail per spec §3)
- **Backend file(s):** `backend/routers/admin_audit_invariant.py`
- **Frontend file(s):** none (operator-only)
- **API endpoint(s):** `/api/admin/audit-invariant/*`

### §3.6 LLM router (Shield-internal) (guardrail)

- **Spec text (verbatim):**
  > The single LLM dispatch point inside `shield/`.
  > … dispatches de-identified prompts to provider SDKs (Claude, OpenAI, Gemini) via `litellm`, captures `usage.prompt_tokens` + `completion_tokens`, returns the response to the caller in `client.invoke()` for re-identification.
- **Status:** ✅ Built (settled guardrail per spec §3)
- **Backend file(s):** `backend/services/synisense/shield/llm_router.py`
- **Test coverage:** `test_no_direct_llm_calls_outside_shield` + `test_no_direct_llm_calls_inside_shield_except_router`

### §4.A Document Journal — D1 Switching context lands on Home

- **Spec text (verbatim):**
  > 1. User clicks the context switcher (Figure 1).
  > 2. User selects a different company.
  > 3. System navigates to the Home page of the newly selected account — regardless of which page the user was on before initiating the switch.
- **Status:** ✅ Built
- **Backend file(s):** none (UI routing only per spec)
- **Frontend file(s):** `frontend/src/components/layout/CompanySwitcherDialog.jsx`, `components/layout/AppShell.jsx`, `components/search/ConfirmContextSwitchModal.jsx`
- **API endpoint(s):** none
- **Test coverage:** none located by grep

### §4.A — D2 "All documents" button navigates to Document Journal

- **Spec text (verbatim):**
  > 1. User clicks the "All documents" button.
  > 2. System navigates the user to the Documents Journal page shown in Figure 4.
- **Status:** ✅ Built
- **Backend file(s):** none
- **Frontend file(s):** `frontend/src/pages/Workspace.jsx`, `components/layout/AppShell.jsx`
- **API endpoint(s):** none
- **Test coverage:** indirectly via `test_t1_*`

### §4.A — D3 Filter tabs below the Document Journal search bar

- **Spec text (verbatim):**
  > 1. Below the search bar (Figure 4), render four filter tabs in this order: **All, Uploaded, Akki Generated, Briefings**.
  > 2. Each tab displays a count badge showing the number of documents in that category (Figure 5).
- **Status:** ✅ Built (per `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md`)
- **Backend file(s):** `backend/routers/documents.py`
- **Frontend file(s):** `frontend/src/pages/Workspace.jsx`
- **API endpoint(s):** existing `/api/contexts/{cid}/documents`-family endpoints
- **Test coverage:** `tests/test_t1_frontend_wire.py`, `tests/test_t1_backend.py` (per closeout doc)

### §4.A — D4 Document cards show origin badges (with `T:*` tags removed)

- **Spec text (verbatim):**
  > Under the All tab, cards render with the badges shown in Figure 6, with all `T:*` tags **removed** from user-facing output (Figure 7).
- **Status:** ✅ Built (per closeout)
- **Backend file(s):** none (display only — origin is a stored field)
- **Frontend file(s):** `frontend/src/pages/Workspace.jsx`
- **API endpoint(s):** none
- **Test coverage:** `tests/test_t1_frontend_wire.py`

### §4.A — D5 Add to Work Studio (from Document Journal side drawer)

- **Spec text (verbatim):**
  > An **Add to Work Studio** modal opens with: Title "Add to Work Studio", Supporting text "Choose the artefact type for this document", Artefact type cards: Board Pack · Minutes · Committee Pack · Deck · Report …
- **Status:** ✅ Built
- **Backend file(s):** `backend/routers/work_studio_export.py` + `work_studio_overlay.py`
- **Frontend file(s):** `frontend/src/components/shared/AddToWorkStudioModal.jsx`, `components/documents/DocumentRoutingActions.jsx`
- **API endpoint(s):** Work-Studio family endpoints
- **Test coverage:** `tests/test_t1_*`, `tests/test_t3_*`

### §4.A — D6 Add to Cycle (from Document Journal side drawer)

- **Spec text (verbatim):**
  > An **Add to Cycle** modal opens with: Title "Add to Cycle", Supporting text "Choose which cycle this document contributes to", Select Cycle dropdown — lists all **Active** and **Draft** cycles available in the Cycle Manager module.
  > **RATIFIED — PO decision 24 May 2026** — frontend posts `{cycle_id: <selected>, kind: "document", source_doc_id: <doc.id>, title: <doc.name>}` to `/api/contexts/{cid}/cycle/contributions?cycle_id=<selected>`.
- **Status:** ✅ Built (G1 ratified + consumed by T1.6 / T3.2 per closeout)
- **Backend file(s):** `backend/routers/cycle_manager.py` (`/cycle/contributions`)
- **Frontend file(s):** `frontend/src/components/shared/AddToCycleModal.jsx`, `components/documents/DocumentRoutingActions.jsx`, `components/shell/HandoffActions.jsx`
- **API endpoint(s):** `POST /api/contexts/{cid}/cycle/contributions`
- **Test coverage:** `tests/test_t1_add_to_cycle_g1.py`, `tests/test_t1_frontend_wire.py`

### §4.A — D7 Take into Solva (from Document Journal side drawer)

- **Spec text (verbatim):**
  > **RATIFIED — PO decision 24 May 2026** — *Behaviour after the error is fixed (with explicit continuity guarantee)*
  > Clicking "Take into Solva" opens the Solva mode-picker (4 modes: Seek Clarity / Develop Strategy / Simulate Hypothesis / Get Perspective). After the user selects a mode, the system creates a Solva session and **the source document is automatically loaded as grounding material into that new session**. The user MUST NOT have to re-select, re-upload, or restart anything …
- **Status:** ✅ Built (G2 ratified + consumed by T1 per closeout)
- **Backend file(s):** `backend/routers/solva_v2.py`, `backend/routers/solva_phase_d.py`
- **Frontend file(s):** `frontend/src/components/documents/DocumentRoutingActions.jsx`, `lib/takeToSolva.js`
- **API endpoint(s):** `POST /api/solva/v2/sessions` (legacy session route, with `intake_seed`)
- **Test coverage:** `tests/test_t1_*` (G2 anchor)

### §4.A — D8 Document Reader: Send to Work Studio / Add to Cycle / Generate Brief / Resolve Signals

- **Spec text (verbatim):**
  > **Send to Work Studio** (Figure 10): align this CTA's modal behaviour, loading state, toast notification, and post-action navigation to the **Add to Work Studio** flow defined in **D5** above.
  > **Add to Cycle** (Figure 10): align to the **Add to Cycle** flow defined in **D6** above.
  > **Generate Brief button visibility** … **Make the button text visible.**
  > **Resolve Signals button** (Figure 12): Add a **Resolve Signals** button fixed to the bottom of the *Akki's Commentary* panel … Clicking it navigates to the **Pulse** page with filters pre-set to `Type: All` and `Freshness: New`.
  > **RATIFIED — PO decision 24 May 2026** — *Generate Brief failure*: re-enable the Generate Brief button, dismiss the loading state, and show an error toast: *"We couldn't generate a brief from this document. Please try again."*
- **Status:** ✅ Built (G3 ratified + consumed by T1.4 per closeout)
- **Backend file(s):** Brief generation routed via Shield + existing endpoints
- **Frontend file(s):** `frontend/src/components/reading/ReadingTopBar.jsx`, `frontend/src/pages/Pulse.jsx`
- **API endpoint(s):** Brief / Pulse endpoints
- **Test coverage:** `tests/test_t1_*` (G3 anchor)

### §4.B Cycle Manager — C1 Landing page

- **Spec text (verbatim):**
  > The landing page has two areas: the **main content area** showing the cycle list, and a **fixed side panel on the right**.
  > Primary CTA — `Add Cycle` button. Rename the current `Add Agenda` button to `Add Cycle`.
  > Search and Sort … Filter tabs: All / Active / Draft / Completed … Cycle cards: title, due date, status badge, compilation readiness score, agenda item count, contributor count.
- **Status:** ✅ Built (per T5 closeout)
- **Backend file(s):** `backend/routers/cycles.py`
- **Frontend file(s):** `frontend/src/pages/cycle/CycleList.jsx`
- **API endpoint(s):** `GET /api/contexts/{cid}/cycles`
- **Test coverage:** `tests/test_t5_backend.py`, `tests/test_t5_frontend_wire.py`, `tests/test_cycles_v2.py`

### §4.B — C2 Add Cycle setup wizard (Step 1)

- **Spec text (verbatim):**
  > Cycle Name … Objectives / Agenda … Required Compilation Readiness Score (80%, 85%, 90%, 95%, 100%) … Due Date …
  > **RATIFIED — PO decision 24 May 2026** — *Required-field validation*: each of the four fields is required; `Next` is disabled until all four are non-empty and Due Date is in the future.
- **Status:** ✅ Built (G4 ratified + consumed by T5.2 per closeout)
- **Backend file(s):** `backend/routers/cycles.py`
- **Frontend file(s):** `frontend/src/components/cycle/CycleSetupWizard.jsx`
- **Test coverage:** `tests/test_t5_*` (G4 anchor)

### §4.B — C3 Add Cycle setup wizard (Step 2 — build the team)

- **Spec text (verbatim):**
  > Name … Email … Role … What is this person contributing? … Attach Agenda Item …
  > **RATIFIED — PO decision 24 May 2026** — *Email validation & duplicate handling*: emails must match a valid-email regex; adding a contributor whose email matches one already added warns inline (*"This contributor is already on the team."*) and prevents the duplicate.
- **Status:** ✅ Built (G5 ratified + consumed by T5.3)
- **Frontend file(s):** `frontend/src/components/cycle/CycleSetupWizard.jsx`
- **Backend file(s):** `backend/routers/cycle_manager.py` (team endpoints)
- **Test coverage:** `tests/test_t5_*`

### §4.B — C4 Project Brief modal (Commission / Review / Save as Draft)

- **Spec text (verbatim):**
  > **Commission Cycle** … status set to Active immediately. Toast: *Cycle commissioned successfully.* … pulsing three times before settling.
  > **Review** … Review Notes input … Update CTA … no limit.
  > **Save as Draft** … status Draft … Toast: *Cycle saved as draft.*
- **Status:** ✅ Built (per T5 closeout)
- **Backend file(s):** `backend/routers/cycles.py`, `backend/routers/cycle_manager.py`
- **Frontend file(s):** `frontend/src/components/cycle/CycleSetupWizard.jsx`
- **Test coverage:** `tests/test_t5_*`

### §4.B — C5 Cycle Page (Active or Draft)

- **Spec text (verbatim):**
  > Draft-cycle banner … `Activate Cycle` button … toast *Cycle is now active.*
  > §4.1 Cycle Status Overview: Due Date + Compilation Readiness Score progress bar.
  > §4.2 Contributions Table: Agenda Item, Contributor, Contribution Status (Pending / Missing / Score), Follow-ups (Awaiting Approval / Sent + colour rules).
  > §4.3 Cycle Actions: Add Agenda · Add Team Member · Add Contribution · Manage Members · Follow Up · Compile.
  > **RATIFIED — PO decision 24 May 2026** — *Compile output format options*: post-compile state presents three download buttons — **DOCX**, **PDF**, and **PPTX** — all produced server-side.
- **Status:** ✅ Built (G6 ratified + consumed by T4.1 / T5.5 per closeout)
- **Backend file(s):** `backend/routers/cycle_manager.py`, `backend/routers/work_studio_render.py` (DOCX/PDF/PPTX)
- **Frontend file(s):** `frontend/src/pages/Cycle.jsx`
- **API endpoint(s):** `/api/contexts/{cid}/cycle/{agenda|team|contributions|readiness|follow-ups|draft-compilation}`, `/api/contexts/{cid}/work-studio/documents/{aid}/render`
- **Test coverage:** `tests/test_t5_*`, `tests/test_t4_*`, `tests/test_cycle_manager_actions_tab.py`

### §4.B — C6 Landing-page side panel (Ready to Compile + Drafts Waiting for You)

- **Spec text (verbatim):**
  > §5.1 Ready to Compile card … Lists cycles whose current compilation readiness score has met or exceeded the target … `Ready to Compile | 4` … up to three cycle names … View More link opens the Ready to Compile Journal.
  > §5.2 Drafts Waiting for You card … follow-up emails drafted by the agent cycle … `Drafts Waiting for You | 7` … up to three draft emails … View More link opens the Draft Journal.
- **Status:** ✅ Built (per T5 closeout)
- **Frontend file(s):** `frontend/src/pages/cycle/CycleList.jsx`
- **Test coverage:** `tests/test_t5_*`

### §4.B — C7 Draft Journal

- **Spec text (verbatim):**
  > Two entry points — `View More` on the Drafts Waiting for You side-panel card, or the Follow Up CTA in §4.3 Section 3 of the Cycle Page. When opened from the Follow Up CTA, the Draft Journal is **pre-filtered** to that specific cycle. When opened from the side panel, it shows all drafts across all cycles.
  > Approve and Send … badge changes from `Draft` to `Sent`.
  > Decline … badge changes from `Draft` to `Declined`.
- **Status:** ✅ Built (T5 closeout — "C7 Draft Journal + C8 Ready to Compile Journal")
- **Frontend file(s):** `frontend/src/pages/cycle/CycleDraftJournal.jsx`
- **Backend file(s):** `backend/routers/cycle_manager.py` (`/cycle/follow-ups/{id}/{approve,send}`)
- **Test coverage:** `tests/test_t5_*`

### §4.B — C8 Ready to Compile Journal

- **Spec text (verbatim):**
  > Cards … cycle title, due date, status badge, compilation readiness score, agenda item count, contributor count.
  > Cycle Card side drawer … cycle title, compilation readiness score, due date, list of contributors and their respective agenda items.
  > CTA in the side drawer is **Compile** … download options for the compiled document — the **same options** available from the Compile button on the Cycle Page (DOCX / PDF / PPTX per G6).
- **Status:** ✅ Built (per T5 closeout)
- **Frontend file(s):** `frontend/src/pages/cycle/CycleReadyJournal.jsx`
- **Backend file(s):** `backend/routers/work_studio_render.py`
- **Test coverage:** `tests/test_t5_*`

### §4.C Work Studio — W1 Remove redundant document cards in all tabs

- **Spec text (verbatim):**
  > Remove the document cards circled in Figure 1 in **all the tabs**. Retain only the section below the document cards.
- **Status:** ✅ Built (per T3 closeout)
- **Frontend file(s):** `frontend/src/pages/WorkStudio.jsx`
- **Test coverage:** `tests/test_t3_frontend_wire.py`

### §4.C — W2 Document card lifecycle states (Board Packs / Committee Packs only)

- **Spec text (verbatim):**
  > Status badge: **Draft** (gray pill), **In Review** (amber pill), **Committed** (dark filled pill + lock icon overlay).
  > Confidence score colour-coded: >75% neutral, 50–75% amber, <50% red.
  > Download icon — persistent action on every card regardless of lifecycle state.
- **Status:** ✅ Built (per T3 closeout)
- **Frontend file(s):** `frontend/src/pages/WorkStudio.jsx`
- **Test coverage:** `tests/test_t3_*`

### §4.C — W3 Compiled Document page (Board Packs / Committee Packs)

- **Spec text (verbatim):**
  > Toolbar … back arrow, document title (inline editable), status badge … Download.
  > Document Intelligence card … Compiled document content (scrollable).
  > Fixed footer: Agent Recommendation + three CTAs (Refine / Decline / Commit).
  > **RATIFIED — PO decision 24 May 2026** — *Refine failure path*: inline error in the footer (*"We couldn't apply that refinement. Please try again."*) and leave the recommendation in place.
- **Status:** ✅ Built (G7 ratified + consumed by T4.2 per closeout)
- **Frontend file(s):** `frontend/src/pages/WorkStudioDocumentPage.jsx`
- **Backend file(s):** `backend/routers/work_studio_export.py`, `work_studio_overlay.py`, `work_studio_render.py`
- **Test coverage:** `tests/test_t3_*`, `tests/test_t4_*`

### §4.C — W4 Pack side drawer (alternate review surface)

- **Spec text (verbatim):**
  > **RATIFIED — PO decision 24 May 2026** — *Drawer-vs-page disambiguation*: the dedicated document page is the canonical surface for **Board Packs** and **Committee Packs** (W3); the side drawer is the canonical surface for **Minutes**, **Decks**, and **Reports** cards opened from the Recents panel or directly from those tabs.
- **Status:** ✅ Built (G8 ratified + consumed by T3.3 per closeout)
- **Frontend file(s):** `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx`
- **Test coverage:** `tests/test_t3_*`

### §4.C — W5 Committed pack behaviour

- **Spec text (verbatim):**
  > download icon remains available on the committed card … clicking the committed card navigates to the document page where the pack is displayed in **read-only mode** … Fixed footer CTAs replaced by a single `Create New Version` button … automatically named using the next version number (e.g. *Q2 2026 Board Pack V2*).
- **Status:** ✅ Built (per T3/T4 closeout)
- **Frontend file(s):** `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx`, `pages/WorkStudioDocumentPage.jsx`
- **Test coverage:** `tests/test_t3_*`

### §4.C — W6 Remove the "Compile a report" button

- **Spec text (verbatim):**
  > remove the **Compile a report** button shown in Figure 4.
- **Status:** ✅ Built (per T3 closeout)
- **Frontend file(s):** `frontend/src/pages/WorkStudio.jsx`
- **Test coverage:** `tests/test_t3_frontend_wire.py`

### §4.C — W7 Replace "Ready to Compile" with "Recents"

- **Spec text (verbatim):**
  > Replace the **Ready to Compile** section with **Recents**. Surface the last **5 documents** the user has worked on across all document types … Board Pack or Committee Pack → dedicated document page (W3) … Minutes / Deck / Report → side drawer (W4).
- **Status:** ✅ Built (per T3 closeout — "Recents panel routes correctly per G8")
- **Frontend file(s):** `frontend/src/pages/WorkStudio.jsx` (Recents section)
- **Test coverage:** `tests/test_t3_*`

### §4.C — W8 Compile modal (Select Source Items + inline upload)

- **Spec text (verbatim):**
  > Search bar filters the list by document name in real time.
  > "Can't find your document? Upload it here." persistent inline prompt.
  > Nested file-upload modal on top of the compile modal … uploaded document is added to the **Document Journal** under the **Upload** tab and automatically appears in the *Select Source Items* list with its checkbox selected.
  > **RATIFIED — PO decision 24 May 2026** — *Upload failure inside the compile modal*: close only the file-upload modal, return the user to the Select Source Items step with the existing selection intact, surface ClamAV verbatim toast *"We couldn't upload that file. It was rejected by virus scanning."* or generic *"Upload failed. Please try again."*
- **Status:** ✅ Built (G9 ratified + consumed by T3.4 per closeout)
- **Frontend file(s):** `frontend/src/components/studio/SourceStep.jsx`
- **Backend file(s):** `backend/services/clamav_service.py`, `backend/routers/work_studio_phase_c.py` / `phase_c2.py`
- **Test coverage:** `tests/test_t3_*`

### §4.C — W9 Enhance flow (Minutes / Decks / Reports tabs)

- **Spec text (verbatim):**
  > Identical behaviour across Minutes, Decks, and Reports. Only the document type referenced in the modal title and card list changes.
  > Modal title: *"Improve Minutes you already have"* (Decks/Reports follow pattern).
  > On success: download button matching output format … card appears at top of list with pulse animation … added to Document Journal Akki Generated tab.
  > On failure: warning + *"Enhancement did not complete."* + plain-language explanation. CTAs: **Adjust and try again**, **Close**.
- **Status:** ✅ Built (per T4 closeout)
- **Frontend file(s):** `frontend/src/components/studio/EnhanceModal.jsx`
- **Backend file(s):** `backend/routers/work_studio_phase_c2.py` (enhance endpoints)
- **Test coverage:** `tests/test_t4_*`

### §4.C — W10 Enhanced document side drawer (Minutes / Decks / Reports)

- **Spec text (verbatim):**
  > Document Intelligence in the drawer: Confidence score · What was changed · What was preserved · Instructions applied · What was not changed and why.
  > Three CTAs: **Save** (inactive until title edit), **Refine** (compact instruction input → iterative refinement loop), **Delete** (confirmation modal).
  > **RATIFIED — PO decision 24 May 2026** — *Refine failure inside the drawer*: leave the existing enhanced content + intelligence in place and show an inline error inside the drawer (*"We couldn't refine this version. Please try again."*).
- **Status:** ✅ Built (G10 ratified + consumed by T4.5 per closeout)
- **Frontend file(s):** `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx`
- **Test coverage:** `tests/test_t4_*`

### §4.D Aggregated — X1 Search bar in "Link an earlier document" panel

- **Spec text (verbatim):**
  > A search bar is added at the top of the dropdown list (Figure 1). Typing in the search bar filters the available options by document name **in real time as the user types**.
- **Status:** 🟡 Partial — grep for `"Link an earlier document"` returns 0 hits in `frontend/src/`. The Add-to-Document-Journal flow does not surface a labelled "Link an earlier document" search-bar component on disk.
- **Backend file(s):** none required (client-side filter per spec)
- **Frontend file(s):** none located by grep for the verbatim panel title
- **API endpoint(s):** none
- **Test coverage:** none located

### §4.D — X2 Akki Chat responsive layout + fixed input bar

- **Spec text (verbatim):**
  > Responsive layout … message bubbles and text wrap within the available width rather than overflow. No horizontal scrolling.
  > Fixed input bar … is fixed and remains anchored to the bottom of the screen at all times.
- **Status:** ✅ Built (per T2 closeout)
- **Frontend file(s):** `frontend/src/pages/Chat.jsx`
- **Test coverage:** `tests/test_t2_frontend_wire.py`

### §4.D — X3 Pulse: Resolved tab + remove citations + bullet-restructure signal cards

- **Spec text (verbatim):**
  > **Resolved tab** (Figure 4): all signals that have been marked as resolved are surfaced under the **Resolved** tab.
  > Signal card restructure: Remove document citations highlighted in Figure 5. Restructure content within each signal card into concise bullet points.
- **Status:** ✅ Built (per T2 closeout)
- **Frontend file(s):** `frontend/src/pages/Pulse.jsx`
- **Test coverage:** `tests/test_t2_*`

### §4.D — X4 Monitor: remove filter tabs (objectives + projects)

- **Spec text (verbatim):**
  > delete the filter tabs circled in Figure 6 and Figure 7.
- **Status:** ✅ Built (per T2 closeout — flagged in §7 as backlog item "X4 Monitor filter tab pending removal" — see Section 7)
- **Frontend file(s):** `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx`
- **Test coverage:** `tests/test_t2_*`

### §4.D — X5 Monitor: objective / project side drawer

- **Spec text (verbatim):**
  > Delete the Akki Status section. Move the Description section to sit below the Status card.
  > Update CTA: **Update Objective** / **Update Project** … agent searches the Document Journal for relevant documents … if no relevant documents are found, the file-upload modal opens …
  > Status Card updates immediately … corresponding card in the list also updates simultaneously. Drawer remains open.
  > Citations Card appears below the Update CTA after an update has been processed. Timeline at the bottom shows chronological log.
- **Status:** ✅ Built (per T2 closeout)
- **Frontend file(s):** `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx`
- **Backend file(s):** `backend/routers/monitor_status_assessment.py`, `backend/routers/monitor_v2.py`
- **Test coverage:** `tests/test_t2_backend.py`, `tests/test_t2_frontend_wire.py`

### §4.D — X6 Monitor Strategic Goals: dual RAG progress bars

- **Spec text (verbatim):**
  > Performance Progress Bar — On Track / Achieved (green) · At Risk (amber) · Off Track (red).
  > Probability Progress Bar — High confidence (green) · Moderate confidence (amber) · Low confidence (red).
  > **RATIFIED — PO decision 24 May 2026** — *Probability bands thresholds*: **High ≥ 70**, **Moderate 40–69**, **Low < 40**.
- **Status:** ✅ Built (G11 ratified + consumed by T2.4 per closeout)
- **Frontend file(s):** `frontend/src/components/monitor/StrategicGoalsPanel.jsx`, `pages/Monitor.jsx`
- **Backend file(s):** `backend/routers/strategic_goals.py`, `backend/routers/strategic_goal_assessment.py`
- **Test coverage:** `tests/test_t2_*`

### §4.D — X7 Strategic Goals: "Document journal link" → "Upload Document" link

- **Spec text (verbatim):**
  > change the **document journal link** in Figure 10 to an **Upload Document** link that opens the **file-upload modal directly**.
- **Status:** ✅ Built (per T2 closeout)
- **Frontend file(s):** `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx`
- **Test coverage:** `tests/test_t2_*`

### §4.D — X8 Strategic Goals: filter tabs + category filter

- **Spec text (verbatim):**
  > Filter tabs: **All, On Track, At Risk, Off Track, Achieved, Not Started** + count badges.
  > Category filter on the right side (Operations, People, Compliance, Product, Commercial) — works in combination with status tabs.
  > **RATIFIED — PO decision 24 May 2026** — *Category source list*: source from `strategic_goals.department` values for the active context, plus the example labels as fixed options if no department values exist.
- **Status:** ✅ Built (G12 ratified + consumed by T2.4 per closeout)
- **Frontend file(s):** `frontend/src/components/monitor/StrategicGoalsPanel.jsx`
- **Backend file(s):** `backend/routers/strategic_goals.py`
- **Test coverage:** `tests/test_iter28_strategic_goals.py`, `tests/test_t2_*`

### §5 Out-of-scope surfaces (per spec §5 — listed for transparency, NOT audited as features)

The product spec §5 explicitly defers the following from this spec — they are listed below but not status-audited against the product spec because the product spec does not define their behaviour. Where a separate canonical source exists, it is cited.

| Surface | Spec disposition |
| --- | --- |
| Solva | "has its own brief at `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md` (SV-01 … SV-08). Deferred from this spec at the PO's direction." |
| Onboarding (J1 re-intro banner + Trust Center tooltips) | "built once on disk, then reverted; preserved at `/app/memory/sprints/J1_PRESERVED_STATE.md`. Dormant pending T5 completion. Out of scope here." — subsequently respec'd in `AKKI_ONBOARDING_SPEC.md` v1.1 (audited below). |
| Trust Center user page UX | "guardrail-side (§3.2) is in scope; the page UX is settled and not covered by these four reports. Out of scope for journeys." |
| Admin / Superadmin surfaces | "Operator-only; out of scope for product journeys here." |
| Landing / marketing site | "not covered by any of the four reports. Out of scope." |
| Settings (Profile, Billing, MFA) | "not covered by any of the four reports. Out of scope." |

### Onboarding Spec — Stage 1 — Sign-up / Authentication

- **Spec text (verbatim):**
  > an authenticated session backed by a real `accounts` row with hashed password (or SSO) and a fresh access+refresh token pair.
  > Entry point: `/signup` (or `/signin` for existing accounts).
  > Submit → `POST /api/auth/register` (`backend/routers/auth.py:57`).
  > Server creates `accounts` row with `declared_role: "undeclared"`, password-hashes via bcrypt, auto-provisions a default context …
- **Status:** ✅ Built ("Existing live for password auth"); G15-G17 deferred to J1 v1.1 per spec table.
- **Backend file(s):** `backend/routers/auth.py`, `backend/core.py`
- **Frontend file(s):** `frontend/src/pages/SignUp.jsx`, `frontend/src/pages/AppHome.jsx` (`FirstSessionGuard`)
- **API endpoint(s):** `POST /api/auth/register`, `POST /api/auth/login`
- **Test coverage:** `tests/test_j1_stages_1_2.py`, `tests/test_j1_onboarding.py`

### Onboarding Spec — Stage 2 — Org / Context creation + Role declaration

- **Spec text (verbatim):**
  > Three questions, sequential, single-column editorial layout: Q1 *"Which best describes your role?"* … Q2 *"What's the primary board or company you sit on?"* … Q3 *"What's on your mind for the next meeting? One sentence."*
  > Submit → `POST /api/me/first-session/intake` …
- **Status:** ✅ Built (per J1 sprint closeout); G18 (Shield de-identification of intake answers) + G20 (context-type emission per role) ratified verbatim 2026-05-25.
- **Backend file(s):** `backend/routers/first_session.py`, `backend/core.py` (`provision_default_context`)
- **Frontend file(s):** `frontend/src/pages/FirstSession.jsx`
- **API endpoint(s):** `GET /api/me/first-session`, `POST /api/me/first-session/intake`, `POST /api/me/first-session/skip`
- **Test coverage:** `tests/test_j1_stages_1_2.py`, `tests/test_j1_onboarding.py`

### Onboarding Spec — Stage 3 — First Cycle invitation (or "Try the demo")

- **Spec text (verbatim):**
  > Replace with a 4-door layout (gap G21):
  > Door A — "Create your first cycle" → routes to the T5 Cycle Setup Wizard …
  > Door B — "Upload a document" → routes to the Document Journal upload sheet …
  > Door C — "Ask Akki something" → routes to the home chat surface with the Q3 answer pre-typed.
  > Door D — "Try the demo" → routes to `/app/cycle` AND auto-attaches the user's account to the `DEMO_T5_BACKLOG` rows by stamping `seed_marker_visible_for: [account_id]`. (Idempotent — same pattern as backlog-b.)
- **Status:** ✅ Built (G21-G23 ratified verbatim 2026-05-25, consumed by J2)
- **Backend file(s):** `backend/routers/first_session.py`, `backend/routers/cycles.py`
- **Frontend file(s):** `frontend/src/pages/FirstSession.jsx`
- **API endpoint(s):** `POST /api/me/first-session/choose-door`
- **Test coverage:** `tests/test_j2_stage_3.py`, `tests/test_j2_3_cycle_door_behavior.py`, `tests/test_j2_3_fix_a_d_auth_refresh.py`

### Onboarding Spec — Stage 4 — First document upload (Shield from the first byte)

- **Spec text (verbatim):**
  > Server side, in order:
  > a. ClamAV scan via `services/clamav_service.scan()` — reject + verbatim G9 toast … if INFECTED.
  > b. Text extraction (pdf2text / docx / xlsx / pptx) via existing pipelines.
  > c. Shield first-pass de-identification via `deidentifier.deidentify(text)` …
  > d. Document stored with the SHIELDED text body; original bytes encrypted at rest.
  > e. `audit_log.document.uploaded` written, sensitivity band assigned.
- **Status:** ✅ Built ("Existing live for upload + ClamAV + Shield + audit (T3.4 + G9)"); G24 (empty-document) + G25 (>50 MB) ratified verbatim 2026-05-25.
- **Backend file(s):** `backend/services/clamav_service.py`, `backend/services/synisense/shield/deidentifier.py`, `backend/routers/documents.py`
- **Test coverage:** `tests/test_j3_stage_4_5_backend.py`, `tests/test_j3_stage_4_5_frontend.py`, `tests/test_hardening_step1_healthz_clamav.py`

### Onboarding Spec — Stage 5 — Trust Center introduction

- **Spec text (verbatim):**
  > After Stage 4 completes, on the next route change the AppShell top-bar renders a one-shot tooltip pointing at the Trust Center icon (re-enable from `b48ee23`).
  > Tooltip copy: *"This is your Trust Center. We've recorded what Shield touched on your first upload — take a look."* (verbatim G27.)
  > Tooltip auto-dismisses on click … `POST /api/users/me/onboarding-status/tooltips/trust-center/dismiss`.
- **Status:** ✅ Built (G26-G28 ratified verbatim 2026-05-25, consumed by J3)
- **Backend file(s):** `backend/routers/onboarding_status.py`
- **Frontend file(s):** `frontend/src/components/layout/AppShell.jsx` (tooltip), `frontend/src/components/trust/TrustCenterTour.jsx`
- **API endpoint(s):** `POST /api/users/me/onboarding-status/tooltips/trust-center/dismiss`, `GET /api/users/me/onboarding-status`
- **Test coverage:** `tests/test_j3_stage_4_5_backend.py`, `tests/test_j3_stage_4_5_frontend.py`

### Onboarding Spec — Stage 6 — First Akki Chat / Solva session

- **Spec text (verbatim):**
  > The home chat surface receives a `?starter=<intake_top_of_mind>` query param from First Session's Door C OR auto-populates from `accounts.first_session.intake.top_of_mind` on home mount.
  > After the FIRST answer renders, the AppShell top-bar's Help tooltip surfaces (re-enable from `b48ee23`).
  > Tooltip copy: *"Tap Help any time. Akki has a built-in tour of every screen."* (verbatim G29.)
- **Status:** ✅ Built (G29-G31 ratified verbatim 2026-05-25, consumed by J4)
- **Backend file(s):** `backend/routers/onboarding_status.py`, `backend/routers/chat.py`
- **Frontend file(s):** `frontend/src/components/layout/AppShell.jsx` (Help tooltip)
- **API endpoint(s):** `POST /api/users/me/onboarding-status/tooltips/help/dismiss`
- **Test coverage:** `tests/test_j4_stage_6_backend.py`, `tests/test_j4_stage_6_frontend.py`

---

## Section 2: Functional Audit (Behavior vs Spec)

For each feature marked 🟡 Partial or ❌ Not built:

### §4.D — X1 Search bar in "Link an earlier document" panel

- **Spec requires:** A search bar at the top of the dropdown list shown in Figure 1 of the Aggregated QA. Typing filters the dropdown options by document name in real time.
- **Current behavior:** No frontend file in `frontend/src/` contains the verbatim string "Link an earlier document". The Add-to-Document-Journal flow uses `LinkExistingDocPicker.jsx`-style components (none found by the exact label), or the panel may be implemented under a different component name not surfaced by the grep recipe.
- **Gap:** Either (a) the panel exists under a different label and the spec/code labels are out of sync, or (b) the dropdown was not migrated to include a real-time search bar.
- **Evidence:**
  - `grep -rln "Link an earlier document" frontend/src --include="*.jsx"` → 0 hits.
  - `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` does not enumerate X1 in its consumed-by-tier table (G1–G12 only; X1 has no ratified gap).
  - Status flag from spec §4.D X1: "Per QA spec" — spec considers it shippable but the code presence is unverified.

---

## Section 3: Orphaned / Legacy Surfaces (⚠️ Not in Spec)

### `backend/routers/cycle.py` — pre-spec endpoint families (21 endpoints)

Per `/app/memory/sprints/PROVENANCE_TRACE_PLAYS_CYCLE.md` (Task B, 2026-05-26): router was first introduced commit `59b609f` on 2026-04-25, predates spec v1.1. The router as a whole has no canonical citation. The following 21 endpoints have **zero live frontend callers** (only archived components or `components/plays/` callers, both archived):

| # | Path/file | Description | Last commit / archived? | Recommendation |
| --- | --- | --- | --- | --- |
| 1 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/cycle/committees` | Pre-spec committees endpoint family | 2026-04-25, live but no callers | escalate |
| 2 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/cycle/schedule` | Pre-spec schedule endpoint | 2026-04-25, live but no callers | escalate |
| 3 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/cycle/actions` | Pre-spec actions aggregator | 2026-04-25, live but no callers | escalate |
| 4 | `backend/routers/cycle.py` :: `/api/cycle/cron/run-schedules` | Admin cron only | 2026-04-25, live | keep |
| 5 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reportees` | Pre-spec reportees CRUD | 2026-04-25, live but no callers | escalate |
| 6 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reportees/{rid}` | Pre-spec reportees CRUD | 2026-04-25, live but no callers | escalate |
| 7 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/compose` | iter20 multi-tier review chain | 2026-04-25, live but no callers | escalate |
| 8 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/{rid}/export.deck.pdf` | Pre-spec export | 2026-04-25, live but no callers | escalate |
| 9 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/{rid}/export.pdf` | Pre-spec export | 2026-04-25, live but no callers | escalate |
| 10 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/{rid}/polish` | Pre-spec polish | 2026-04-25, live but no callers | escalate |
| 11 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/{rid}/send_up` | Pre-spec send-up | 2026-04-25, live but no callers | escalate |
| 12 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/checklists` | Live caller in `components/home/QuickActions.jsx` + `InSummaryTiles.jsx` | 2026-04-25, live + 2 callers | escalate |
| 13 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/checklists/dispatch` | Live caller in Home dashboard | 2026-04-25, live + caller | escalate |
| 14 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/checklists/generate` | Live caller in Home dashboard | 2026-04-25, live + caller | escalate |
| 15 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/checklists/{cid}` | Live caller in Home dashboard | 2026-04-25, live + caller | escalate |
| 16 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/questions` | Live caller in `pages/Questions.jsx`, `Home2.jsx`, `HandoffActions.jsx` | 2026-04-25, live + 4 callers | escalate |
| 17 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/questions/seed-from-briefings` | Live | 2026-04-25, live + caller | escalate |
| 18 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/questions/{qid}` | Live | 2026-04-25, live + caller | escalate |
| 19 | `backend/routers/cycle.py` :: `/api/respond/{token}` | Live — `pages/RespondToChecklist.jsx` + `App.js /r/:token` | 2026-04-25, live + caller | escalate |
| 20 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/submissions` | Live caller `InSummaryTiles.jsx` | 2026-04-25, live + caller | escalate |
| 21 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/me/submitted-briefs` | Live caller | 2026-04-25, live + caller | escalate |
| 22 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports` (GET / POST) | Live — `pages/Monitor.jsx` calls reports inbox | 2026-04-25, live + caller | escalate |
| 23 | `backend/routers/cycle.py` :: `/api/reports/inbox` | Live — `pages/Monitor.jsx` | 2026-04-25, live + caller | escalate |
| 24 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/{rid}` | Live | 2026-04-25, live + caller | escalate |
| 25 | `backend/routers/cycle.py` :: `/api/contexts/{cid}/reports/{rid}/review` | Live — Monitor v1 path | 2026-04-25, live + caller | escalate |

### Additional orphan surfaces (per provenance trace + audit)

| # | Path/file | Description | Last commit / archived? | Recommendation |
| --- | --- | --- | --- | --- |
| 26 | `backend/routers/monitor.py` (v1) | Monitor v1 router. Spec §4.D X4–X8 maps to `monitor_v2.py` / `monitor_status_assessment.py` / `strategic_goal_assessment.py`. v1 retained via `tests/test_monitor_v1_compat.py` for back-compat. | live + back-compat anchor | escalate |
| 27 | `backend/routers/agenda.py` | Serves `/api/contexts/{cid}/agenda-evolution` for Home `AgendaEvolutionCard.jsx`. No canonical citation in product or onboarding specs. Live consumers in `components/home/AgendaEvolutionCard.jsx`, `tests/test_iter26_engagement.py`, `tests/test_iter29_score_history.py`. | live + callers | escalate |
| 28 | `backend/routers/cycle_assignments.py` | Pre-spec assignment ops. Audit did not surface a canonical citation. | live | escalate |
| 29 | `backend/routers/help.py` :: `/api/help/features` | Serves `AKKI_PRODUCT_SPEC.md` (post Bucket-1 cleanup). Endpoint not specified by either spec; the `/help` page UX is "out of scope" per product spec §5 (Settings). | live, source switched 2026-05-26 | keep |
| 30 | `frontend/src/pages/HelpFeatures.jsx` | The frontend consumer of `/api/help/features`. Out of scope per spec §5. | live | keep |
| 31 | `backend/routers/work_studio_phase_c.py` + `work_studio_phase_c2.py` | Pre-Phase-C.3 export + enhance routers, NOT context-scoped. Overlap conceptually with `work_studio_export.py` (Phase C.2 context-scoped) and `work_studio_render.py` (T4.1 G6). Live callers in `SourceStep.jsx` + `EnhanceModal.jsx`. | live + callers | escalate |
| 32 | `frontend/src/components/home/QuickActions.jsx` Plays-integration block (lines 84, 95, 108, 137-150) | Calls `/api/contexts/{cid}/plays` (now 404) inside `.catch(() => ({ data: { plays: [] } }))` graceful fallback. Plays surface archived 2026-05-26. | live but Plays surface archived | escalate |
| 33 | `frontend/src/pages/Decks.jsx` Plays-integration block (lines 49, 65, 93, 97, 102, 155-156) | Reads + lists active Plays from `/api/contexts/{cid}/plays` (now 404) with graceful fallback. | live but Plays surface archived | escalate |
| 34 | `frontend/src/components/home/WorkflowsHub.jsx` + `PlaysInProgressStrip.jsx` + `PlayReadyCards.jsx` + `DocumentPlayContext.jsx` | Plays-integration components for Home dashboard. Plays surface (router + pages + components) archived 2026-05-26 per `REDEPLOY_CLEANUP_LOG.md`. | live but Plays surface archived | escalate |

---

## Section 4: Archived Surfaces (🗄️ Already Removed)

Per `/app/memory/sprints/CLEANUP_B1_LOG.md` + `/app/memory/sprints/REDEPLOY_CLEANUP_LOG.md`. Enumerated only — no commentary.

### Frontend pages
- `frontend/src/_archived_legacy/pages/SolvaLanding.jsx.archived`
- `frontend/src/_archived_legacy/pages/SandboxV2.jsx.archived`
- `frontend/src/_archived_legacy/pages/CycleSettings.jsx.archived`
- `frontend/src/_archived_legacy/pages/PlaysLibrary.jsx.archived`
- `frontend/src/_archived_legacy/pages/PlayView.jsx.archived`

### Frontend components
- `frontend/src/_archived_legacy/components/cycle/ReportsTab.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/CycleTracker.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/ReviewInboxCard.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/NedInboxTile.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/CycleStrip.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/CyclePhaseSheet.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/tabs/ActionsTab.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/tabs/BoardpackTab.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/tabs/MinutesTab.jsx.archived`
- `frontend/src/_archived_legacy/components/cycle/tabs/SignalsTab.jsx.archived`
- `frontend/src/_archived_legacy/components/lens/AllLensesModal.jsx.archived`
- `frontend/src/_archived_legacy/components/depth/DepthOfferCard.jsx.archived`
- `frontend/src/_archived_legacy/components/streaming/StreamingShell.jsx.archived`
- `frontend/src/_archived_legacy/components/plays/PreBoardStages.jsx.archived`
- `frontend/src/_archived_legacy/components/plays/BoardPackStages.jsx.archived`

### Frontend hooks
- `frontend/src/_archived_legacy/hooks/useCycleConfig.js.archived`

### Backend routers
- `backend/_archived_legacy/routers/plays.py.archived`
- `backend/_archived_legacy/routers/cycle_config.py.archived`

### Backend tests
- `backend/tests/_archived_coverage_loss/test_iter22_billing_schedule.py.archived`
- `backend/tests/_archived_coverage_loss/test_iter24_plays.py.archived`
- `backend/tests/_archived_coverage_loss/test_iter25_plays_slice2.py.archived`
- `backend/tests/_archived_coverage_loss/test_iter19_polish_committee_medium.py.archived`
- `backend/tests/_archived_coverage_loss/test_iter40_goals_kpi.py.archived`
- `backend/tests/_archived_coverage_loss/test_iter41_signal_actions.py.archived`
- `backend/tests/_archived_coverage_loss/test_iter62_solve_wave2_wave3.py.archived`

---

## Section 5: Summary Table

| Spec Feature | Status | Backend | Frontend | Tests |
| --- | --- | --- | --- | --- |
| §3.1 Synisense Shield | ✅ | `services/synisense/shield/*` | — | `test_no_direct_llm_calls_*` |
| §3.2 Trust Center / Master Audit | ✅ | `routers/trust_center.py` + back-fill | `pages/TrustCenter.jsx` | TC methodology tests |
| §3.3 ClamAV scanning | ✅ | `services/clamav_service.py` + healthz | — | `test_hardening_step1_*` |
| §3.4 Postmark inbound | ✅ | `routers/inbound_email.py`, `inbound_queue.py` | — | inbound-email tests |
| §3.5 Audit invariants | ✅ | `routers/admin_audit_invariant.py` | — | invariant tests |
| §3.6 LLM router | ✅ | `services/synisense/shield/llm_router.py` | — | direct-call guard tests |
| §4.A D1 context switcher → Home | ✅ | — | `CompanySwitcherDialog`, `AppShell` | — |
| §4.A D2 All documents button | ✅ | — | `Workspace.jsx`, `AppShell.jsx` | `test_t1_*` |
| §4.A D3 Filter tabs | ✅ | `routers/documents.py` | `Workspace.jsx` | `test_t1_*` |
| §4.A D4 Origin badges + `T:*` removal | ✅ | — | `Workspace.jsx` | `test_t1_*` |
| §4.A D5 Add to Work Studio | ✅ | `work_studio_*` | `AddToWorkStudioModal`, `DocumentRoutingActions` | `test_t1_*`, `test_t3_*` |
| §4.A D6 Add to Cycle (G1) | ✅ | `cycle_manager.py` | `AddToCycleModal`, `DocumentRoutingActions` | `test_t1_add_to_cycle_g1.py` |
| §4.A D7 Take into Solva (G2) | ✅ | `solva_v2.py`, `solva_phase_d.py` | `DocumentRoutingActions`, `takeToSolva.js` | `test_t1_*` |
| §4.A D8 Document Reader actions (G3) | ✅ | Brief endpoints | `ReadingTopBar`, `Pulse.jsx` | `test_t1_*` |
| §4.B C1 Cycle landing | ✅ | `cycles.py` | `pages/cycle/CycleList.jsx` | `test_t5_*`, `test_cycles_v2.py` |
| §4.B C2 Setup wizard Step 1 (G4) | ✅ | `cycles.py` | `CycleSetupWizard.jsx` | `test_t5_*` |
| §4.B C3 Setup wizard Step 2 (G5) | ✅ | `cycle_manager.py` | `CycleSetupWizard.jsx` | `test_t5_*` |
| §4.B C4 Project Brief modal | ✅ | `cycles.py`, `cycle_manager.py` | `CycleSetupWizard.jsx` | `test_t5_*` |
| §4.B C5 Cycle Page (G6) | ✅ | `cycle_manager.py`, `work_studio_render.py` | `pages/Cycle.jsx` | `test_t5_*`, `test_t4_*` |
| §4.B C6 Landing side panel | ✅ | `cycles.py` | `pages/cycle/CycleList.jsx` | `test_t5_*` |
| §4.B C7 Draft Journal | ✅ | `cycle_manager.py` | `pages/cycle/CycleDraftJournal.jsx` | `test_t5_*` |
| §4.B C8 Ready to Compile Journal | ✅ | `work_studio_render.py` | `pages/cycle/CycleReadyJournal.jsx` | `test_t5_*` |
| §4.C W1 Remove redundant cards | ✅ | — | `WorkStudio.jsx` | `test_t3_*` |
| §4.C W2 Pack lifecycle states | ✅ | — | `WorkStudio.jsx` | `test_t3_*` |
| §4.C W3 Compiled Document page (G7) | ✅ | `work_studio_export.py`, `work_studio_overlay.py`, `work_studio_render.py` | `WorkStudioDocumentPage.jsx` | `test_t3_*`, `test_t4_*` |
| §4.C W4 Pack side drawer (G8) | ✅ | — | `components/work_studio/overlay/DocumentOverlay.jsx` | `test_t3_*` |
| §4.C W5 Committed pack | ✅ | — | `DocumentOverlay.jsx`, `WorkStudioDocumentPage.jsx` | `test_t3_*` |
| §4.C W6 Remove "Compile a report" | ✅ | — | `WorkStudio.jsx` | `test_t3_*` |
| §4.C W7 Recents panel | ✅ | — | `WorkStudio.jsx` | `test_t3_*` |
| §4.C W8 Compile modal (G9) | ✅ | `clamav_service.py`, `work_studio_phase_c*.py` | `SourceStep.jsx` | `test_t3_*` |
| §4.C W9 Enhance flow | ✅ | `work_studio_phase_c2.py` | `EnhanceModal.jsx` | `test_t4_*` |
| §4.C W10 Enhanced doc drawer (G10) | ✅ | — | `DocumentOverlay.jsx` | `test_t4_*` |
| §4.D X1 "Link an earlier document" search | 🟡 | — | not located by grep | none located |
| §4.D X2 Chat responsive + fixed input | ✅ | — | `pages/Chat.jsx` | `test_t2_*` |
| §4.D X3 Pulse Resolved tab + restructure | ✅ | — | `pages/Pulse.jsx` | `test_t2_*` |
| §4.D X4 Monitor remove filter tabs | ✅ | — | `monitor/ObjectivesProjectsPanel.jsx` | `test_t2_*` |
| §4.D X5 Monitor objective/project drawer | ✅ | `monitor_status_assessment.py`, `monitor_v2.py` | `monitor/ObjectivesProjectsPanel.jsx` | `test_t2_*` |
| §4.D X6 Strategic Goals dual RAG (G11) | ✅ | `strategic_goals.py`, `strategic_goal_assessment.py` | `monitor/StrategicGoalsPanel.jsx`, `Monitor.jsx` | `test_t2_*` |
| §4.D X7 Upload Document link | ✅ | — | `monitor/ObjectivesProjectsPanel.jsx` | `test_t2_*` |
| §4.D X8 Strategic Goals filter tabs (G12) | ✅ | `strategic_goals.py` | `monitor/StrategicGoalsPanel.jsx` | `test_iter28_strategic_goals.py`, `test_t2_*` |
| Onboarding Stage 1 Sign-up | ✅ | `auth.py`, `core.py` | `SignUp.jsx`, `AppHome.jsx` | `test_j1_stages_1_2.py` |
| Onboarding Stage 2 First-session intake | ✅ | `first_session.py` | `FirstSession.jsx` | `test_j1_*` |
| Onboarding Stage 3 4-door layout (G21-G23) | ✅ | `first_session.py`, `cycles.py` | `FirstSession.jsx` | `test_j2_*` |
| Onboarding Stage 4 First upload (Shield) | ✅ | `clamav_service.py`, `deidentifier.py`, `documents.py` | — | `test_j3_stage_4_5_*`, `test_hardening_step1_*` |
| Onboarding Stage 5 Trust Center tooltip (G26-G28) | ✅ | `onboarding_status.py` | `AppShell.jsx`, `TrustCenterTour.jsx` | `test_j3_stage_4_5_*` |
| Onboarding Stage 6 Chat starter + Help tooltip (G29-G31) | ✅ | `onboarding_status.py`, `chat.py` | `AppShell.jsx` | `test_j4_stage_6_*` |

---

## Section 6: Health & Integrations Snapshot

Factual one-liners only.

- **ClamAV:** `GET /api/healthz/clamav` returns `{"clamd_daemon": "unreachable", "scans_last_24h": {"ok": 0, "infected": 0, "bypassed": 14, "error": 0}, "preflight_size_check_active": true}` as of 2026-05-26T02:40Z in the preview pod. Production-status verification endpoint shipped in Hardening Step 1.
- **Stripe:** Billing surface routed to the "Coming Soon" stub — `routers/billing.py` returns `coming_soon: true` from every endpoint per chunk-c (2026-05-25). Frontend `BillingTab.jsx` renders the Coming Soon UX. `test_chunk_c_no_stripe_sdk_import.py` enforces no Stripe SDK imports.
- **Postmark:** `routers/inbound_email.py` + `routers/inbound_queue.py` live; `POSTMARK_SERVER_TOKEN`, `POSTMARK_WEBHOOK_SECRET`, `POSTMARK_USE_HMAC`, `POSTMARK_BASIC_AUTH_USER` configured in `backend/.env`.
- **LLM providers:** `EMERGENT_LLM_KEY` (universal — OpenAI/Anthropic/Gemini via emergentintegrations) plus direct keys `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`. All routed through `services/synisense/shield/llm_router.py`. Stream model overrides via `ANTHROPIC_STREAM_MODEL` + `GEMINI_STREAM_MODEL` env vars.
- **News RSS sources:** 9 live sources in `backend/data/news_sources.json` (post-cleanup). 4 stale sources (`iod`, `frc-uk`, `hbr`, `reuters-biz`) removed 2026-05-26 — see `REDEPLOY_CLEANUP_LOG.md` Task 2.

---

## Section 7: Known Tech Debt (from prior sprints)

Reference items only — do not solve.

- **45 skipped pytest test files** as of 2026-05-26 (45 files matching `pytestmark.*skip`). Full triage in `/app/memory/sprints/SKIP_LEDGER.md` §2 ("broken-masked-prequel" class). Includes 28 Patch-8-quarantined `test_iter*.py` files.
- **3 spaCy direct-URL refs in `requirements.txt`** — `test_real_requirements_file_is_clean` flags `en_core_web_sm`/`lg` direct-URL refs at lines 33/34/185. Parked in `POST_T5_BACKLOG.md` as P2 housekeeping.
- **Stripe library still in `requirements.txt`** — `stripe==…` listed but `routers/billing.py` returns Coming Soon stub and `test_chunk_c_no_stripe_sdk_import.py` asserts no Stripe SDK usage. Library is dead weight pending removal.
- **X4 Monitor filter tab pending removal** — spec §4.D X4 says "delete the filter tabs circled in Figure 6 and Figure 7." T2 closeout marked the journey complete; this item is listed in the brief as still-pending. Verification: per closeout the X4 work was consumed by T2; the brief's "X4 pending removal" callout may reference a residual tab on a related surface — not re-investigated here.
- **`backend/routers/cycle.py` pre-spec endpoint pruning** — provenance trace identified 21 endpoints without canonical citations (Section 3, rows 1-25 above). Surgical pruning is a refactor sprint; not authorised by current chunk.
- **Plays-integration call sites in live Home/Decks code** — `QuickActions.jsx`, `Decks.jsx`, `WorkflowsHub.jsx`, `PlaysInProgressStrip.jsx`, `PlayReadyCards.jsx`, `DocumentPlayContext.jsx` still reference `/api/contexts/{cid}/plays` via graceful-fallback `.catch(() => ({ data: { plays: [] } }))`. Plays router archived 2026-05-26; integration sites left in place per "no refactor beyond cleanup" rule.
- **`/api/healthz` returns 404** while `/api/healthz/clamav` and `/api/healthz/shield` return 200. The `healthz` namespace only has sub-routes — no root-level catch-all. Tester flagged this as P3 / not a blocker. Not in scope for this audit.

---

## Audit metadata

- **Spec ambiguities logged as gaps during this audit:** 1 (X1 "Link an earlier document" panel — verbatim component label not located in code by grep).
- **Files modified outside `/app/memory/PRODUCT_FEATURE_REVIEW.md`:** 0.
- **Spec files modified:** 0.
- **Pytest runs during this audit:** 0.

*Read-only audit complete.*
