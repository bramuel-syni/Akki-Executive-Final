# AKKI Product Spec

**Version:** 1.1
**Date:** 24 May 2026
**Authoring note:** Derived from the four QA reports dated 24 May 2026 + the guardrail services on disk as of this date. This document is a fresh clean-break — it does **not** merge from, supersede, or reference `/app/memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` (which has no authority for this spec).

**Change log:**
- v1.0 — 24 May 2026 — Initial spec derived from the four 24 May 2026 QA reports.
- v1.1 — 24 May 2026 — PO ratified G1–G12; G2 + G6 amended.

---

## 1. Source-of-truth hierarchy

This hierarchy is mandatory for every reader and every future agent that touches this document:

1. **The four 24 May 2026 QA reports are the canonical spec for product journeys** (Document Journal, Cycle Manager, Work Studio, Aggregated). Wherever they define a journey, screen, action, or behaviour — that is the truth. **Do not redesign. Do not reinterpret. Transcribe.**
2. **Existing guardrails stay as-is and are leveraged, not redesigned.** These are Synisense Shield, Trust Center / Master Audit, ClamAV upload scanning, Postmark inbound email, audit invariant violations, and the Shield-internal `llm_router`. Journeys note where they touch a guardrail; nothing in this document proposes a guardrail change.
3. **Gaps are filled with the smallest possible proposal and flagged.** Where a QA journey is silent or incomplete on a detail (an empty state, a confirmation copy, an edge case), this document inserts a minimal proposed fill, clearly delimited as `**GAP — proposed fill (awaiting PO sign-off)**`, so the PO can approve or override. Every such block is also indexed in §7 below.
4. **The legacy `AKKI_FEATURES_AND_FUNCTIONALITY.md` has no authority.** It is not read for design input here and is not edited by this work.

---

## 2. Product summary

AKKI is a privacy-shielded executive AI workspace for non-executive directors (NEDs) and C-suite executives. The platform supports the rhythm of governance work — document review, cycle preparation, structured executive thinking, board-pack assembly, signal monitoring — without ever sending raw customer content to a third-party LLM. The Synisense Shield gateway de-identifies every outbound prompt, routes it through `llm_router`, re-identifies the response on the way back, and writes a tamper-evident audit row for each call. The platform promise to the user is direct: **the LLM never sees your confidential data**.

---

## 3. Guardrails (existing, leveraged, NOT redesigned)

The following services are settled. Journeys in §5 reference them by name where relevant. None of the §5 journeys proposes a change to any of these guardrails.

### 3.1 Synisense Shield
The deidentifier + canonical mint + reidentifier pipeline that owns every outbound LLM call.

- **What it does**: de-identifies inbound content (regex recognisers → Presidio → spaCy NER fallback), canonically tokens identifiers with HMAC-keyed mints, routes the de-identified payload through `llm_router.invoke()`, re-identifies the response, and writes an audit row + trust receipt.
- **Where it lives** (canonical file paths):
  - `backend/services/synisense/shield/deidentifier.py`
  - `backend/services/synisense/shield/canonical.py`
  - `backend/services/synisense/shield/reidentifier.py` (PII-class skip list lives here)
  - `backend/services/synisense/shield/llm_router.py` (only file inside `shield/` permitted to import provider SDKs)
  - `backend/services/synisense/shield/streaming.py` (streaming coverage)
  - `backend/services/synisense/shield/audit_log.py`
  - `backend/services/synisense/shield/trust_receipt.py`
  - `backend/services/synisense/regex_recognisers.py` (Luhn-validated PAN detection)
- **How journeys interact with it**: any journey that produces, refines, summarises, or commits text via an LLM (chat replies, brief generation, pack compilation, enhance flows, status assessments, follow-up draft emails) routes through Shield. The journey never calls a provider SDK directly.

### 3.2 Trust Center / Master Audit
The user-facing forensic surface backed by the Shield audit log.

- **What it does**: view-time re-derivation of redactions per turn; per-turn drill-down with input SHA, tokenized prompt, tokenized LLM response, re-identified visible text, redactions, and audit chain; historical back-fill of pre-Shield-v1.x chats; gated plaintext endpoint that writes a `trust_center.plaintext_viewed` audit row on every read.
- **Where it lives**:
  - `backend/routers/trust_center.py`
  - `frontend/src/pages/TrustCenter.jsx`
  - `backend/services/backfill_shield_v1.py` + `backend/routers/admin_shield_backfill.py` (historical back-fill engine)
  - `backend/routers/healthz_shield.py` (Shield warmup + readiness probe)
- **How journeys interact with it**: every Shield call writes a `synisense_audit_log` row and a Trust Receipt; users can drill into any conversation turn from the Trust Center page. Back-filled chats surface a `shield_status: "backfilled"` badge in the journey UI.

### 3.3 ClamAV upload scanning
Virus scanning sidecar invoked on every document upload.

- **What it does**: scans uploaded files server-side before persistence; rejects infected files with an audit row.
- **Where it lives**: `backend/services/clamav_service.py`.
- **How journeys interact with it**: every upload flow (Document Journal upload, Cycle Manager "Add Contribution" attachment, Work Studio source-document upload-from-compile-modal, Enhance flow inline upload) passes through ClamAV. A failed scan halts the journey with a user-readable error.

### 3.4 Postmark inbound email (MailboxHash routing)
Inbound email gateway for follow-up replies and document-by-email.

- **What it does**: ingests inbound email via Postmark webhook, routes by `MailboxHash` to the correct context / cycle / contributor record.
- **Where it lives**: `backend/routers/inbound_email.py` + `backend/routers/inbound_queue.py`.
- **How journeys interact with it**: Cycle Manager follow-up emails sent from the Draft Journal carry a `MailboxHash` so the contributor's reply lands back against the correct cycle + agenda item. Document-by-email uploads also land here.

### 3.5 Audit invariant violations
Cross-cutting integrity check on the audit chain.

- **What it does**: detects and surfaces audit-chain invariant violations (envelope mismatch, missing trust receipts, broken hash chain) for operators.
- **Where it lives**: `backend/routers/admin_audit_invariant.py`.
- **How journeys interact with it**: passive — no user-facing journey touches it directly. Operator-only surface; named here so future agents do not re-derive it.

### 3.6 LLM router (Shield-internal)
The single LLM dispatch point inside `shield/`.

- **What it does**: dispatches de-identified prompts to provider SDKs (Claude, OpenAI, Gemini) via `litellm`, captures `usage.prompt_tokens` + `completion_tokens`, returns the response to the caller in `client.invoke()` for re-identification.
- **Where it lives**: `backend/services/synisense/shield/llm_router.py`.
- **How journeys interact with it**: indirectly — only `client.invoke()` calls it. Two CI guards protect this: `test_no_direct_llm_calls_outside_shield` and `test_no_direct_llm_calls_inside_shield_except_router`.

---

## 4. Product journeys (canonical, from the 24 May 2026 QA reports)

Each journey below is transcribed verbatim from its QA source where possible. Where the QA wording is paraphrased (only for readability — never for design change), the substance is preserved exactly. Gaps are surfaced as `**GAP — proposed fill (awaiting PO sign-off)**` blocks and re-indexed in §7.

### 4.A Document Journal

**Primary QA source:** `/app/memory/sprints/qa_24may2026/document_journal_qa_24may2026.md`

#### Journey D1 — Switching context lands on Home

- **QA source**: Document Journal QA · § Switching Context (Figure 1)
- **Actors**: any authenticated user (NED, Exec, Admin)
- **Trigger / entry point**: user picks a different company from the context switcher
- **Steps**:
  1. User clicks the context switcher (Figure 1).
  2. User selects a different company.
  3. System navigates to the Home page of the newly selected account — regardless of which page the user was on before initiating the switch.
- **Acceptance / done state**: user lands on the Home page of the new account.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none (UI routing only).
- **Status**: Per QA spec.

#### Journey D2 — "All documents" button navigates to the Document Journal

- **QA source**: Document Journal QA · § Document Journal item 1 (Figures 3 and 4)
- **Actors**: any authenticated user
- **Trigger / entry point**: user clicks the "All documents" button shown in Figure 3
- **Steps**:
  1. User clicks the "All documents" button.
  2. System navigates the user to the Documents Journal page shown in Figure 4.
- **Acceptance / done state**: Documents Journal page is rendered.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none.
- **Status**: Per QA spec.

#### Journey D3 — Filter tabs below the Document Journal search bar

- **QA source**: Document Journal QA · § Document Journal items 2 and 3 (Figures 4 and 5)
- **Actors**: any authenticated user on the Document Journal page
- **Trigger / entry point**: page load; the journal renders the filter tabs below the search bar
- **Steps**:
  1. Below the search bar (Figure 4), render four filter tabs in this order: **All, Uploaded, Akki Generated, Briefings**.
  2. Each tab displays a count badge showing the number of documents in that category (Figure 5).
     - **All** — every document in the journal regardless of origin. Count = total across both categories.
     - **Uploaded** — only documents the user manually uploaded (from device or external source via the upload flow).
     - **Akki Generated** — only documents produced automatically by Akki (reports, decks, and compiled documents generated through Work Studio and stored in the journal).
     - **Briefings** — a document qualifies as a Briefing **if and only if** it was produced by the Generate Brief action.
  3. The active tab is visually distinct from the inactive tabs (Figure 5).
  4. **All** is selected by default on page load and shows the complete document list.
  5. Selecting a tab filters the document list immediately without a page reload.
- **Acceptance / done state**: tabs render with live count badges; switching tabs filters the list without reload; All is the default tab on load.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none.
- **Status**: Per QA spec.

#### Journey D4 — Document cards show origin badges (with `T:*` tags removed)

- **QA source**: Document Journal QA · § Document Journal items 3, 4, and 5 (Figures 6 and 7)
- **Actors**: any authenticated user
- **Trigger / entry point**: rendering of cards under the All tab; rendering of the side drawer for a card
- **Steps**:
  1. Under the All tab, cards render with the badges shown in Figure 6, with all `T:*` tags **removed** from user-facing output (Figure 7).
  2. Side drawer metadata line follows this rule:
     - If the existing label `Internal` conveys that the document was manually uploaded by the user, **replace** `Internal` with `Uploaded`.
     - Otherwise, if the document was uploaded by the user, **append** the `Uploaded` tag so the line reads, e.g., `10 May 2026 · 4 KB · Internal · Uploaded`.
     - If the document origin is Akki Generated (produced by Akki through Work Studio or another generation tool), append the `Akki Generated` tag so the line reads, e.g., `20 May 2026 · 4 KB · Akki Generated` or `20 May 2026 · 4 KB · Internal · Akki Generated`.
- **Acceptance / done state**: cards under All display the new badges; the literal substring `T:` (followed by any tag value) does not appear in user-facing output; side-drawer metadata line is constructed per the rule above.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none (display only; origin is a stored field).
- **Status**: Per QA spec.

#### Journey D5 — Add to Work Studio (from Document Journal side drawer)

- **QA source**: Document Journal QA · § Document Journal items 6 and 7 (Figure 7)
- **Actors**: any authenticated user
- **Trigger / entry point**: user clicks "Add to Work Studio" (circled green in Figure 7) in the document side drawer
- **Steps**:
  1. An **Add to Work Studio** modal opens with:
     - **Title**: Add to Work Studio
     - **Supporting text**: Choose the artefact type for this document.
     - **Artefact type** (selectable cards, user can select only one): Board Pack · Minutes · Committee Pack · Deck · Report.
  2. Modal CTAs:
     - **Cancel** — closes the modal with no action taken.
     - **Add document ([selected artefact type])** — e.g. *Add document (Board Pack)*. Disabled until an artefact type is selected.
  3. On clicking **Add document**:
     - Modal closes.
     - A loading state appears to indicate that AKKI is processing the document.
     - On success, a toast notification appears:
       > Your document has been added to Work Studio as a [artefact type].
       > **Example:** Your document has been added to Work Studio as a Board Pack.
     - On failure, an error toast appears:
       > We couldn't add this document to Work Studio. Please try again.
  4. Navigation after completion:
     - Open the Work Studio page and automatically navigate the user to the tab matching the selected artefact type.
     - Display the newly created document card as the first item in that tab.
     - On first appearance, highlight the new card with **2–3 gentle pulses** using the platform accent colour. After the animation completes, the card returns to its normal/default state.
- **Acceptance / done state**: card appears at the top of the matching Work Studio tab and pulses 2–3 times before settling; user lands on that tab.
- **Edge cases / errors**: failure toast above.
- **Guardrail touchpoints**: Shield (any LLM step Akki runs to generate the artefact passes through Shield); Trust Center (audit row written per Shield call).
- **Status**: Per QA spec.

#### Journey D6 — Add to Cycle (from Document Journal side drawer)

- **QA source**: Document Journal QA · § Document Journal item 8 (Figures 7 and 8)
- **Actors**: any authenticated user
- **Trigger / entry point**: user clicks "Add to Cycle" in the document side drawer (currently throws the error in Figure 8)
- **Steps**:
  1. An **Add to Cycle** modal opens with:
     - **Title**: Add to Cycle
     - **Supporting text**: Choose which cycle this document contributes to.
     - **Select Cycle** dropdown — lists all **Active** and **Draft** cycles available in the Cycle Manager module.
  2. Modal CTAs:
     - **Cancel** — closes the modal with no action taken.
     - **Attach to cycle** — attaches the document to the selected cycle.
  3. On clicking **Attach to cycle**:
     - Modal closes.
     - Document is attached to the selected cycle.
     - Toast notification appears:
       > Your document has been added to Cycle Manager in [cycle name].
       > **Example:** Your document has been added to Cycle Manager in Q2 Board Preparation Cycle.
  4. Error handling: if processing fails, display an error toast:
     > We couldn't add this document to the cycle. Please try again.
  5. Navigation after completion:
     - Open the Cycle Manager page and automatically navigate the user to the cycle listing, **All** tab.
     - Display the newly attached cycle card with the pulse highlight: **2–3 gentle pulses** in the accent colour, then settle.
- **Acceptance / done state**: cycle card representing the destination cycle is pulsed on the All tab; document is attached server-side.
- **Edge cases / errors**: failure toast above. Current 422 error path (`agenda_item_id` invalid, `team_member_id` required, `kind` wrong) is replaced by the new modal contract — see Aggregated QA gap notes in §4.D for backend payload alignment.

- **RATIFIED — PO decision 24 May 2026** — *Backend wire format*
  > When the user submits the new modal, the frontend posts `{cycle_id: <selected>, kind: "document", source_doc_id: <doc.id>, title: <doc.name>}` to `/api/contexts/{cid}/cycle/contributions?cycle_id=<selected>`. `agenda_item_id` and `team_member_id` remain optional per the existing `ContributionIn` schema; the document attaches at the cycle root with no agenda-item/contributor binding (which the QA's Select-Cycle-only flow allows).

- **Guardrail touchpoints**: ClamAV (the underlying document was already scanned at upload); Shield (no LLM call in this journey itself); Trust Center (server emits an audit row for the attach operation via the existing `write_audit` helper).
- **Status**: Per QA spec for the user-facing flow; backend wire format **ratified** per G1 (24 May 2026).

#### Journey D7 — Take into Solva (from Document Journal side drawer)

- **QA source**: Document Journal QA · § Document Journal item 9 (Figures 7 and 9)
- **Actors**: any authenticated user
- **Trigger / entry point**: user clicks "Take into Solva" in the document side drawer (currently throws the error in Figure 9)
- **Steps**: the QA states *"Fix the error captured in figure 9"* without redefining the journey beyond that error fix.

- **RATIFIED — PO decision 24 May 2026** — *Behaviour after the error is fixed (with explicit continuity guarantee)*
  > Clicking "Take into Solva" opens the Solva mode-picker (4 modes: Seek Clarity / Develop Strategy / Simulate Hypothesis / Get Perspective). After the user selects a mode, the system creates a Solva session and **the source document is automatically loaded as grounding material into that new session**. The user MUST NOT have to re-select, re-upload, or restart anything — the document carries through as-is, and the new session opens already grounded on it. The 422 error is fixed by aligning the frontend payload to the backend `StartV2In` schema (`intent` required, ≥20 chars, plus `intake_seed: {kind: "document", id: <doc.id>}`). The session then routes the user to that Solva session.

- **Acceptance / done state**: Solva session opens with the document already attached as grounding; the user lands directly inside the session with no further input required to bring the document along.
- **Edge cases / errors**: not specified in QA beyond fixing the captured error.
- **Guardrail touchpoints**: Shield (Solva LLM calls); Trust Center (audit rows).
- **Status**: **Ratified** per G2 (24 May 2026), with continuity guarantee binding.

#### Journey D8 — Document Reader: Send to Work Studio / Add to Cycle / Generate Brief / Resolve Signals (Figure 10 + Figure 12)

- **QA source**: Document Journal QA · § Document Journal items 10–15 (Figures 10, 11, 12)
- **Actors**: any authenticated user, on the Document Reader page
- **Trigger / entry point**: user opens a document in the Document Reader
- **Steps**:
  1. **Send to Work Studio** (Figure 10): align this CTA's modal behaviour, loading state, toast notification, and post-action navigation to the **Add to Work Studio** flow defined in **D5** above. (Identical flow; the only entry point difference is that the trigger is on the Document Reader rather than the journal side drawer.)
  2. **Add to Cycle** (Figure 10): align to the **Add to Cycle** flow defined in **D6** above.
  3. **Origin badges in the Document Reader header row** (Figure 10): add the origin badge — either `Uploaded` or `Akki Generated` — to the right of the existing `Mixed` badge in the same header row, following the same rule as **D4**.
  4. **Generate Brief button visibility** (Figure 10, circled blue): the button text was originally "Generate Brief". **Make the button text visible.**
  5. **Generate Brief — on click**:
     - Disable the button immediately and display a loading state to confirm the action is in progress.
  6. **Generate Brief — on completion**:
     - Show a toast notification confirming the brief has been generated and added to the Document Journal.
     - Redirect the user to the Document Journal **Briefings** tab.
     - The new briefing card appears at the top of the list, **pulsing** to draw attention.
  7. **Briefing card behaviour** (Figure 11):
     - Clicking a briefing card opens a side drawer.
     - CTA in the drawer: **Add to Work Studio** (same Work-with-Document flow as **D5**).
     - After adding to Work Studio, when the user returns to a briefing card that has already been added, the `Add to Work Studio` CTA is replaced with a label showing it has been added — e.g. `Added to Work Studio as [artefact type]`, where the artefact type reflects what was generated (Brief / Deck / Report).
  8. **Resolve Signals button** (Figure 12):
     - Add a **Resolve Signals** button fixed to the bottom of the *Akki's Commentary* panel; it remains visible as the user scrolls the signals list above it.
     - Clicking it navigates to the **Pulse** page with filters pre-set to `Type: All` and `Freshness: New`.
     - In the *Akki's Commentary* panel, change the text below the title from `notes` to `signals`.
- **Acceptance / done state**: Generate Brief produces a card in the Briefings tab that pulses on arrival; Resolve Signals lands the user on Pulse with the prescribed filters; Send-to-Work-Studio and Add-to-Cycle mirror **D5** and **D6** exactly.
- **Edge cases / errors**:
  - Generate Brief failure path: not specified in QA.
  - **RATIFIED — PO decision 24 May 2026** — *Generate Brief failure*: on failure, re-enable the Generate Brief button, dismiss the loading state, and show an error toast: *"We couldn't generate a brief from this document. Please try again."*
- **Guardrail touchpoints**: Shield (Generate Brief is an LLM call); Trust Center (audit row per call); ClamAV (already enforced at upload).
- **Status**: Per QA spec for items 1–8; Generate Brief failure toast **ratified** per G3 (24 May 2026).

---

### 4.B Cycle Manager

**Primary QA source:** `/app/memory/sprints/qa_24may2026/cycle_manager_qa_24may2026.md`

> **Naming convention (locked by QA §1):** the individual items within a cycle are called **Agendas**. The container that holds agendas, team members, contributions, and outputs is called a **Cycle**. The button to create a new cycle is **Add Cycle**.

#### Journey C1 — Cycle Manager landing page

- **QA source**: Cycle Manager QA · §2 (Figure 1)
- **Actors**: any authenticated user
- **Trigger / entry point**: user opens the Cycle Manager page
- **Steps**:
  1. The landing page has two areas: the **main content area** showing the cycle list, and a **fixed side panel on the right**. Both are always visible simultaneously.
  2. **Primary CTA** — `Add Cycle` button. Rename the current `Add Agenda` button to `Add Cycle`. Clicking it opens the Setup Wizard (Journey **C2**).
  3. **Search and Sort** — a search bar filters cycles by title in real time. A sort control sits beside it with options **Most Recent (default)**, **Oldest First**, **Alphabetical A to Z**. The active sort is visually indicated.
  4. **Filter tabs** below search/sort, each with a count badge:
     - **All (default)** — every cycle regardless of status (selected by default on page load).
     - **Active** — cycles that have been commissioned and are currently in progress.
     - **Draft** — cycles saved as drafts that have not yet been commissioned.
     - **Completed** — cycles the user has marked as completed.
  5. **Cycle cards** — ordered most recent first by default. Each card shows: cycle title (primary identifier), due date, status badge (Active / Draft / Completed), compilation readiness score (current readiness as a percentage), agenda item count (e.g. *3 agendas*), contributor count (e.g. *2 contributors*). Clicking anywhere on a card opens the Cycle Page (Journey **C4**).
- **Acceptance / done state**: page renders both areas; tabs and sort default to the values above; cards are clickable.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none on the landing surface (server-side scoring under Shield surfaces inside the Cycle Page).
- **Status**: Per QA spec.

#### Journey C2 — Add Cycle setup wizard (Step 1)

- **QA source**: Cycle Manager QA · §3.1
- **Actors**: cycle creator (Exec or any user with create permission in this context)
- **Trigger / entry point**: user clicks `Add Cycle` on the landing page; a two-step modal opens
- **Steps** — Step 1 collects the cycle configuration with the following input fields (titles above each field):
  1. **Cycle Name** — free-text.
  2. **Objectives / Agenda** — free-text where the user describes the agenda items or objectives for the cycle.
  3. **Required Compilation Readiness Score** — predefined selector with five options: **80%, 85%, 90%, 95%, 100%**. Helper text appears below:
     > This is the readiness percentage you feel comfortable compiling a draft document from. When contributions reach this threshold, the cycle will be flagged as ready to compile.
  4. **Due Date** — date picker for the target completion date.
  5. `Next` advances to Step 2. `Cancel` closes the wizard without saving.
- **Acceptance / done state**: clicking Next opens Step 2.
- **Edge cases / errors**: not specified in QA (e.g. validation rules per field).
- **RATIFIED — PO decision 24 May 2026** — *Required-field validation*: each of the four fields is required; `Next` is disabled until all four are non-empty and Due Date is in the future.
- **Guardrail touchpoints**: none (LLM is not invoked until the Project Brief step, **C4**).
- **Status**: Per QA spec; field-level validation **ratified** per G4 (24 May 2026).

#### Journey C3 — Add Cycle setup wizard (Step 2 — build the team)

- **QA source**: Cycle Manager QA · §3.2
- **Actors**: cycle creator
- **Trigger / entry point**: completion of Step 1
- **Steps** — Step 2 allows the user to add contributors; the following input fields are presented for each contributor:
  1. **Name** — contributor's full name.
  2. **Email** — contributor's email.
  3. **Role** — contributor's role or job title.
  4. **What is this person contributing?** — free-text contribution brief describing what this contributor is expected to provide.
  5. **Attach Agenda Item** — dropdown listing the agenda items defined in Step 1. The contributor is assigned to one or more agenda items from this list.
  6. Two CTAs at the bottom:
     - **Add Another Team Member** — saves the current contributor's details and presents a fresh input form. No limit on contributors.
     - **Review Project Brief** — saves the current contributor's details and triggers the agent cycle to generate a **Project Brief** (a summary of the cycle based on Steps 1 and 2). A toast confirms the contributor has been added; Step 2 modal closes; the **Project Brief modal** opens (Journey **C4**).
- **Acceptance / done state**: the team is captured and the Project Brief modal opens.
- **Edge cases / errors**: not specified in QA.
- **RATIFIED — PO decision 24 May 2026** — *Email validation & duplicate handling*: emails must match a valid-email regex; adding a contributor whose email matches one already added warns inline (*"This contributor is already on the team."*) and prevents the duplicate.
- **Guardrail touchpoints**: Shield (the Project Brief generation triggered by `Review Project Brief` is an LLM call routed through Shield).
- **Status**: Per QA spec; email validation + duplicate handling **ratified** per G5 (24 May 2026).

#### Journey C4 — Project Brief modal (Commission / Review / Save as Draft)

- **QA source**: Cycle Manager QA · §3.3
- **Actors**: cycle creator
- **Trigger / entry point**: opens automatically when Step 2 ends with `Review Project Brief`
- **Steps**: the modal presents the agent cycle's summary of the cycle (based on cycle name, objectives/agendas, readiness target, due date, and team member details). Three CTAs:
  1. **Commission Cycle**:
     - Cycle status is set to **Active** immediately.
     - Toast: *Cycle commissioned successfully.*
     - Modal closes. A new cycle card appears at the top of the **All** and **Active** tabs on the landing page, **pulsing three times** before settling.
  2. **Review**:
     - An input box labelled **Review Notes** appears within the modal.
     - User types notes and clicks **Update**.
     - A brief loading state appears as the agent cycle uses the notes to update the Project Brief summary.
     - The user can review and update as many times as needed — no limit.
     - Once satisfied, the user can click `Commission Cycle` or `Save as Draft`.
  3. **Save as Draft**:
     - Cycle is saved with **Draft** status.
     - Toast: *Cycle saved as draft.*
     - Modal closes. A new cycle card appears at the top of the **All** and **Draft** tabs on the landing page, **pulsing three times** before settling.
- **Acceptance / done state**: the corresponding card lands in the right tab(s) and pulses three times.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Shield (Project Brief generation + each Review update is an LLM call); Trust Center (audit rows).
- **Status**: Per QA spec.

#### Journey C5 — Cycle Page (Active or Draft)

- **QA source**: Cycle Manager QA · §4 (Figure 2 for §4.1 inspiration)
- **Actors**: any user with access to the cycle
- **Trigger / entry point**: clicking a cycle card on the landing page
- **Steps**: Cycle Page is organised into three sections.
  - **Draft-cycle banner** (§4 callout): a Draft cycle displays an `Activate Cycle` button at the top. Clicking it immediately sets status to **Active** and shows a toast: *Cycle is now active.*
  - **§4.1 Section 1 — Cycle Status Overview**:
    - **Due Date** — displayed with the number of days remaining (e.g. *15 June 2026 · 22 days remaining*).
    - **Compilation Readiness Score** — progress bar showing current readiness against the setup target; the target is visually marked on the bar; below the bar shows the number of agenda items with missing or pending contributions (e.g. *3 agendas pending*).
  - **§4.2 Section 2 — Contributions Table**:
    - Columns: **Agenda Item**, **Contributor**, **Contribution Status**, **Follow-ups**.
    - **Contribution Status** values: `Pending` / `Missing` if no contribution; if submitted, the contribution `Score` is shown (reflecting relevance, fullness, and readiness).
    - **Follow-ups** values: `Awaiting Approval` (a follow-up draft has been generated but not yet approved by the user) and `Sent` (the follow-up email has been sent).
    - For `Sent`: **green** if the contributor has responded; **red** if no response after 3 days from send date; **orange** if no response and fewer than 3 days have passed since send. For red and orange, surface metadata showing the date sent.
  - **§4.3 Section 3 — Cycle Actions**: a horizontal strip of six action CTAs, each with an icon. The **Compile** button is filled (black background, white text); the others are outlined.
    1. **Add Agenda** — opens a modal with an `Agenda Description` field; a contributor dropdown listing all team members across all cycles; if the required contributor is not in the list, an `Add Contributor` option appears in the dropdown which opens a modal to enter contributor details (name, email, role, contribution brief), and on save a toast confirms and the new contributor appears in the dropdown immediately. Adding a contributor to an agenda is optional. CTA is `Add Agenda`; on click, toast confirms and the new agenda item appears in Section 2.
    2. **Add Team Member** — opens a modal with fields **Name**, **Email**, **Role**, **What are they contributing**, **Agenda to attach**. CTA is `Add Member`; on click, toast: *Contributor added. You can view and manage them in Manage Members.*
    3. **Add Contribution** — opens a modal where the user attaches a document to a contributor. Document attachment field (user selects or uploads); contributor dropdown (team members assigned to the current cycle). CTA is `Record Contribution`; on click, contribution status in the table updates accordingly.
    4. **Manage Members** — opens the Manage Members page showing all contributors assigned to the current cycle. Each entry shows: name, email, role, contribution brief, the agenda item they own. An **edit** icon makes all fields editable inline with `Save` and `Cancel` CTAs. A **delete** icon opens a confirmation modal: *Are you sure you want to remove this member from the cycle?* with `Cancel` and `Delete` CTAs; on Delete, the contributor is removed from the cycle.
    5. **Follow Up** — opens the **Draft Journal** filtered to show only follow-up email drafts for the current cycle (Journey **C7**).
    6. **Compile** — triggers the agent cycle to compile the cycle's contributions into a document. A loading state appears while the agent processes. On completion, the user is presented with download options for the compiled document.
- **Acceptance / done state**: each action above completes with the prescribed toast/state change.
- **Edge cases / errors**:
  - **Add Contribution** — the QA does not specify the wire format (cf. **D6** GAP).
  - **RATIFIED — PO decision 24 May 2026** — *Compile output format options*: the QA states "the user is presented with download options" but does not enumerate them. The post-compile state presents three download buttons — **DOCX**, **PDF**, and **PPTX** — all produced server-side.
- **Guardrail touchpoints**: ClamAV (each `Add Contribution` attachment is scanned); Shield (Compile is an LLM call; the agent-cycle follow-up drafter is also Shield-routed); Trust Center (audit rows for every LLM step); Postmark (follow-up emails leave via Postmark; MailboxHash routes replies back to the cycle).
- **Status**: Per QA spec; Compile output formats (DOCX / PDF / PPTX) **ratified** per G6 (24 May 2026).

#### Journey C6 — Landing-page side panel (Ready to Compile + Drafts Waiting for You)

- **QA source**: Cycle Manager QA · §5
- **Actors**: any user with access to the landing page
- **Trigger / entry point**: page load — the side panel is always visible alongside the cycle list
- **Steps**:
  1. **§5.1 Ready to Compile card**:
     - Lists cycles whose current compilation readiness score has **met or exceeded** the target the user set during the setup wizard.
     - Updates in real time — a cycle appears on this card automatically the moment its readiness score hits the target.
     - Card title shows `Ready to Compile` with the total qualifying-cycle count on the right (e.g. *Ready to Compile | 4*).
     - Card body lists **up to three cycle names**. Clicking a cycle name navigates directly to that cycle's page.
     - Below the list, a `View More` link opens the **Ready to Compile Journal** (Journey **C8**).
  2. **§5.2 Drafts Waiting for You card**:
     - Shows follow-up emails drafted by the agent cycle that are awaiting the user's approval or decline before being sent.
     - Card title shows `Drafts Waiting for You` with the total pending count on the right (e.g. *Drafts Waiting for You | 7*).
     - Card body lists **up to three draft emails** showing `To: [Contributor Name]` for each. Clicking a contributor name navigates the user to the **Draft Journal** (Journey **C7**).
     - Below the list, a `View More` link opens the **Draft Journal**.
- **Acceptance / done state**: both cards render with live counts and the per-card behaviours above.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Postmark (the drafts are pending Postmark sends after approval).
- **Status**: Per QA spec.

#### Journey C7 — Draft Journal

- **QA source**: Cycle Manager QA · §6
- **Actors**: any user with access to the cycle or to the landing-page side panel
- **Trigger / entry point**: two entry points — `View More` on the **Drafts Waiting for You** side-panel card, or the **Follow Up** CTA in §4.3 Section 3 of the Cycle Page. When opened from the Follow Up CTA, the Draft Journal is **pre-filtered** to that specific cycle. When opened from the side panel, it shows all drafts across all cycles.
- **Steps**:
  1. A back button at the top of the page returns the user to the Cycle Manager landing page.
  2. The page lists all agent-cycle-drafted follow-up emails as individual entries. Each entry shows: email subject, `To: [Contributor Name]`, `Cycle: [Cycle Name]`, `For: [Agenda Item]`, and the current badge status (initially `Draft`).
  3. Each entry has two CTAs:
     - **Approve and Send** — the email is sent to the contributor; toast confirms send; badge changes from `Draft` to `Sent`.
     - **Decline** — the email is not sent; toast confirms decline; badge changes from `Draft` to `Declined`.
- **Acceptance / done state**: entry badge transitions to `Sent` or `Declined` per CTA.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Postmark (`Approve and Send` sends via Postmark with MailboxHash so the contributor's reply maps back to the cycle/agenda); Shield (initial follow-up drafting was a Shield-routed LLM call).
- **Status**: Per QA spec.

#### Journey C8 — Ready to Compile Journal

- **QA source**: Cycle Manager QA · §7
- **Actors**: any user with access to the landing-page side panel
- **Trigger / entry point**: `View More` on the **Ready to Compile** side-panel card
- **Steps**:
  1. A back button at the top returns the user to the Cycle Manager landing page.
  2. Cycles are displayed as cards. Each shows: cycle title, due date, status badge (Active / Draft / Completed), compilation readiness score, agenda item count (e.g. *3 agendas*), contributor count (e.g. *2 contributors*).
  3. **Cycle Card side drawer** — clicking a card opens a side drawer with: cycle title, compilation readiness score, due date, list of contributors and their respective agenda items.
  4. CTA in the side drawer is **Compile**. Clicking it triggers the agent cycle to compile the document. A loading state appears while the agent processes. On completion, the user is presented with download options for the compiled document — the **same options** available from the Compile button on the Cycle Page (DOCX / PDF / PPTX per G6).
- **Acceptance / done state**: side drawer opens; Compile produces downloadable outputs.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Shield (Compile is a Shield-routed LLM call); Trust Center (audit rows).
- **Status**: Per QA spec.

---

### 4.C Work Studio

**Primary QA source:** `/app/memory/sprints/qa_24may2026/work_studio_qa_24may2026.md`

#### Journey W1 — Remove redundant document cards in all tabs

- **QA source**: Work Studio QA · item 1 (Figure 1)
- **Actors**: any authenticated user
- **Trigger / entry point**: page load on any Work Studio tab
- **Steps**:
  1. Remove the document cards circled in Figure 1 in **all the tabs**.
  2. Retain only the section below the document cards.
- **Acceptance / done state**: the circled cards no longer render in any tab; the section beneath them is preserved.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none.
- **Status**: Per QA spec.

#### Journey W2 — Document card lifecycle states (Board Packs / Committee Packs only)

- **QA source**: Work Studio QA · item 2 (Figures 2 and 3)
- **Actors**: any user viewing the Board Packs or Committee Packs tab
- **Trigger / entry point**: page render for those two tabs
- **Steps**: every pack compiled by the agent via **Compile Board Pack** and **Compile Committee Pack** has a lifecycle with three states surfaced directly on every document card. Three states apply **exclusively** to cards in the Board Packs and Committee Packs tabs:
  1. **Status badge**:
     - **Draft** — the document has been compiled by the Agent but has not yet been reviewed. Every pack enters this state immediately after compilation. Styled as a **gray pill**.
     - **In Review** — the pack has been opened and reviewed by the user. Styled as an **amber pill**. (How it is reviewed is described in **W3**.)
     - **Committed** — the user has version-locked the pack. No further editing is permitted on this version. Styled as a **dark filled pill**. A small **lock icon** is overlaid on the bottom-right corner of the document icon as a second visual signal that the pack is locked.
  2. **Confidence score** — from the Document Intelligence model, displayed on every card as a percentage, colour-coded:
     - Above 75% — neutral
     - 50% to 75% — amber
     - Below 50% — red
  3. **Download icon** — persistent action on every card regardless of lifecycle state. Clicking it downloads the pack in its source format.
  4. **Updated card layout** (Figure 3):
     - **Row 1**: Document icon (with lock overlay for Committed) — Document title — Status badge — Download icon.
     - **Row 2**: Date created · Document sources count · Contributor count · any existing metadata — Confidence score.
  5. Clicking on the card opens the **Compiled Document page** (Journey **W3**).
- **Acceptance / done state**: cards in those two tabs render with the new layout, badges, scores, and download icon.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Shield (the confidence score originates from a Shield-routed Document Intelligence call); Trust Center (audit rows).
- **Status**: Per QA spec.

#### Journey W3 — Compiled Document page (Board Packs / Committee Packs)

- **QA source**: Work Studio QA · item 3
- **Actors**: any user opening a pack card in Board Packs or Committee Packs
- **Trigger / entry point**: clicking a document card in Board Packs or Committee Packs
- **Steps**:
  1. Navigation: opens a **dedicated document page**. Opening the page automatically moves the compiled document card from **Draft** → **In Review**.
  2. **Toolbar** (fixed bar that remains visible at all times):
     - **Left group**: a back arrow that returns to the Board Packs / Committee Packs tab; the **document title** (inline editable — click, type, confirm with Enter or click-away; dashed underline on hover); the **status badge** showing current lifecycle (`Draft` / `In Review` / `Committed`).
     - **Right group**: **Download** — downloads the document in its source format.
  3. **Document Intelligence card** — sits directly below the toolbar and remains visible at all times (does not scroll away). Displays in compact format: number of source documents used, number of contributors, period covered by the pack, **confidence score** colour-coded (above 75% neutral, 50–75% amber, below 50% red).
  4. **Compiled document content** — the only scrollable area on the page. The user reads the content directly on the page.
  5. **Fixed footer** at the bottom, always visible:
     - **Agent Recommendation** — the agent surfaces an enhancement recommendation in plain language above the CTAs (e.g. *"The executive summary could be strengthened with Q3 variance data from the Management Accounts."*).
     - Three CTAs: **Refine**, **Decline**, **Commit**.
       - **Refine** — accepts the agent's recommendation; the agent implements the suggested changes automatically. If an additional source document is required, the **file-upload modal** opens prompting the user to upload the relevant file; once uploaded, the agent proceeds with the refinement and the document content + Document Intelligence card update.
       - **Decline** — dismisses the agent recommendation; the recommendation text is removed from the footer.
       - **Commit** — version-locks the pack. A confirmation modal appears informing the user that the pack will be locked and cannot be refined further once committed. Two options: **Confirm** and **Cancel**. On confirm: page closes; user returns to the tab; the committed card appears at the top of the list with a **pulse animation** and a **lock icon overlay** on the document icon; the card badge updates to **Committed**.
- **Acceptance / done state**: lifecycle transitions occur correctly; the committed card appears at the top of the tab with pulse + lock overlay.
- **Edge cases / errors**: not specified in QA (e.g. failure during Refine).
- **RATIFIED — PO decision 24 May 2026** — *Refine failure path*: if the Shield-routed Refine call fails, show an inline error in the footer (*"We couldn't apply that refinement. Please try again."*) and leave the recommendation in place so the user can retry.
- **Guardrail touchpoints**: Shield (Refine is a Shield-routed LLM call; Document Intelligence is Shield-routed); Trust Center (audit rows for every LLM step); ClamAV (the file-upload modal under Refine scans the uploaded file).
- **Status**: Per QA spec; Refine failure path **ratified** per G7 (24 May 2026).

#### Journey W4 — Pack side drawer (alternate review surface)

- **QA source**: Work Studio QA · item 3 (continued, mentions a side drawer)
- **Actors**: any user viewing a pack card
- **Trigger / entry point**: opening the side drawer for a pack card

- **RATIFIED — PO decision 24 May 2026** — *Drawer-vs-page disambiguation*: the dedicated document page is the canonical surface for **Board Packs** and **Committee Packs** (W3); the side drawer is the canonical surface for **Minutes**, **Decks**, and **Reports** cards opened from the Recents panel or directly from those tabs.

- **Steps** (drawer when used):
  1. Title at the top of the drawer is inline editable.
  2. Document intelligence section directly below the title — compact format with: number of source documents used, number of contributors, period covered by the pack, confidence score (same RAG thresholds as W2).
  3. Compiled document content below the Document Intelligence section. Drawer is **fully scrollable**.
  4. Fixed, always-visible recommendation section at the bottom — the Agent surfaces enhancement recommendations based on analysis of the compiled document.
- **Acceptance / done state**: drawer renders the four blocks above and remains scrollable.
- **Edge cases / errors**: not specified.
- **Guardrail touchpoints**: Shield + Trust Center as in W3.
- **Status**: Drawer-vs-page disambiguation **ratified** per G8 (24 May 2026); otherwise per QA spec for the drawer contents.

#### Journey W5 — Committed pack behaviour

- **QA source**: Work Studio QA · item 3 (committed-state paragraph)
- **Actors**: any user
- **Trigger / entry point**: viewing a committed Board Pack or Committee Pack card; clicking it
- **Steps**:
  1. The card displays: document title, date created, source document count, contributor count, confidence score, and a **lock icon overlaid on the bottom-right corner** of the document icon. Status badge updates to **Committed**.
  2. The **download icon remains available** on the committed card as a persistent action. No other actions are available directly on the card.
  3. Clicking the committed card navigates to the **document page** where the pack is displayed in **read-only mode**:
     - Document title is locked and no longer editable.
     - Document Intelligence card remains visible as part of the document record.
     - Fixed footer CTAs (Refine / Decline / Commit) are **replaced by a single `Create New Version` button** sitting on the same line as the document title and Committed badge in the toolbar.
  4. Clicking **Create New Version** generates a new card in the tab list, **automatically named using the next version number** (e.g. *Q2 2026 Board Pack V2*). The new card enters the list in **Draft** state with no lock icon. Clicking it opens the document page where the user can read, refine, and commit it following the same flow from the beginning.
- **Acceptance / done state**: read-only mode is enforced for committed packs; `Create New Version` produces a new V2 card in Draft state.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Shield (the new version, once edited and committed, follows W3 routing); Trust Center (audit rows).
- **Status**: Per QA spec.

#### Journey W6 — Remove the "Compile a report" button

- **QA source**: Work Studio QA · item 4 (Figure 4)
- **Actors**: any user
- **Trigger / entry point**: Work Studio page render
- **Steps**: remove the **Compile a report** button shown in Figure 4.
- **Acceptance / done state**: the button no longer renders anywhere in Work Studio.
- **Edge cases / errors**: not specified.
- **Guardrail touchpoints**: none.
- **Status**: Per QA spec.

#### Journey W7 — Replace "Ready to Compile" with "Recents"

- **QA source**: Work Studio QA · item 5
- **Actors**: any user
- **Trigger / entry point**: Work Studio right-panel render
- **Steps**:
  1. Replace the **Ready to Compile** section with **Recents**.
  2. Surface the last **5 documents** the user has worked on across all document types.
  3. Each entry shows the document name and how long ago it was last accessed.
  4. **Navigation rules**:
     - Clicking a **Board Pack** or **Committee Pack** entry in the Recents panel navigates the user to the **dedicated document page** for that pack (W3), replacing the current view. The back button returns the user to the Work Studio tab they came from.
     - Clicking a **Minutes**, **Deck**, or **Report** entry in the Recents panel opens the **side drawer** (W4) for that document, **overlaying** the current view without navigating away from the page.
- **Acceptance / done state**: panel renders 5 entries; click behaviour is split per the rule above.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none for the panel itself; W3/W4 guardrails apply on click.
- **Status**: Per QA spec.

#### Journey W8 — Compile modal (Select Source Items + inline upload)

- **QA source**: Work Studio QA · item 6 (Figure 5)
- **Actors**: any user invoking Compile
- **Trigger / entry point**: opening the compile modal
- **Steps**:
  1. A **search bar** sits directly below the *Select source items* heading and filters the list by document name in real time.
  2. Below the list, a **persistent inline prompt** reads:
     > Can't find your document? Upload it here.
  3. Clicking the prompt opens a **file-upload modal on top of the compile modal**. The user uploads the file and clicks **Save**.
  4. The uploaded document is added to the **Document Journal** under the **Upload** tab and automatically appears in the *Select Source Items* list with its checkbox selected.
  5. The user returns to the Sources step with the uploaded document already selected.
- **Acceptance / done state**: nested upload preserves the user's place in the compile flow; the uploaded document is selected on return.
- **Edge cases / errors**: not specified in QA.
- **RATIFIED — PO decision 24 May 2026** — *Upload failure inside the compile modal*: if the nested upload fails (e.g. ClamAV reject), close only the file-upload modal, return the user to the Select Source Items step with the existing selection intact, and surface a toast: *"We couldn't upload that file. It was rejected by virus scanning."* (or generic *"Upload failed. Please try again."* for non-ClamAV failures).
- **Guardrail touchpoints**: ClamAV (upload is scanned); Shield + Trust Center as in W3 once Compile fires.
- **Status**: Per QA spec; upload-failure path **ratified** per G9 (24 May 2026).

#### Journey W9 — Enhance flow (Minutes / Decks / Reports tabs)

- **QA source**: Work Studio QA · items 7–10 (Figures 6, 7, 8)
- **Actors**: any user on the Minutes, Decks, or Reports tab
- **Trigger / entry point**: invoking Enhance on one of those three tabs
- **Steps**:
  1. **Scope**: identical behaviour across Minutes, Decks, and Reports. Only the document type referenced in the modal title and card list changes.
  2. **Modal title** for Minutes: change to *"Improve Minutes you already have"*. (Decks and Reports follow the same naming pattern.)
  3. The document is enhanced per the instruction provided in the modal in Figure 6.
  4. On **Enhance** click, a loading state appears; on completion, a toast at the top of the screen indicates success or failure.
  5. **On success**:
     - A **download button** appears in the modal matching the output format selected earlier. Once the user clicks **Download**, the modal closes and the enhanced document card appears at the **top of the list** (Figure 7) for the relevant tab.
     - The card enters with a **pulse animation** to draw attention before settling. The card displays the document title, date created, file format (e.g. DOCX), file size, and a download icon.
     - The enhanced document is also added to the **Document Journal** under the **Akki Generated** tab.
     - Clicking the card opens a **side drawer** containing: an editable document title; a download icon; the Document Intelligence details for the enhanced document. Side drawer specifications are in **W10**.
  6. **On failure** (within the modal):
     - The error state appears within the modal. A **warning indicator** plus the message *"Enhancement did not complete."* is displayed along with a plain-language explanation of what went wrong (e.g. *"Your instructions are too long. Please shorten them and try again."*). The **technical error detail is not shown** to the user.
     - Two CTAs appear:
       - **Adjust and try again** — returns the user to the editable modal with their previous inputs intact.
       - **Close** — dismisses the modal entirely.
- **Acceptance / done state**: a successful enhance produces a pulsing card at the top of the relevant tab + an entry in the Document Journal Akki Generated tab; failures stay inside the modal with the prescribed warning copy.
- **Edge cases / errors**: handled by the on-failure block above.
- **Guardrail touchpoints**: Shield (Enhance is a Shield-routed LLM call); Trust Center (audit rows); ClamAV (any nested file upload).
- **Status**: Per QA spec.

#### Journey W10 — Enhanced document side drawer (Minutes / Decks / Reports)

- **QA source**: Work Studio QA · items 11–13 (Figure 8)
- **Actors**: any user opening the side drawer for an enhanced document
- **Trigger / entry point**: clicking the enhanced document card after W9 success
- **Steps**:
  1. **Document Intelligence in the drawer** (Figure 8) covers:
     - **Confidence score** — measures how well the enhanced output matches the user's instructions. A high score = instructions clearly interpreted and fully applied; lower score = some instructions ambiguous, partially applied, or unactionable.
     - **What was changed** — a plain-language summary of the improvements made, mapped to the instructions the user provided.
     - **What was preserved** — confirmation that citations, data references, and key figures from the original document were kept intact.
     - **Instructions applied** — a record of the exact instructions the user submitted (audit trail of what was asked and what was actioned).
     - **What was not changed and why** — if any part of the instructions could not be applied, flagged with a plain-language explanation.
  2. **Three CTAs at the bottom**: **Save**, **Refine**, **Delete**.
     - **Save** — remains **inactive until the user edits the title**; activates as soon as a change is made.
     - **Refine** — opens a **compact instruction input field** within the side drawer. The user types additional instructions and submits. A loading state appears; the document is re-enhanced; the Document Intelligence details update automatically (including confidence score and all intelligence details) to reflect the latest enhancement pass. The title remains editable throughout. This turns the enhancement into an iterative refinement loop.
     - **Delete** — triggers a confirmation modal with **Cancel** and **Delete**. Any changes made in the side drawer (including title edits and deletions) are reflected immediately on the corresponding entry in the **Document Journal**.
- **Acceptance / done state**: drawer renders the five Document Intelligence sub-sections + the three CTAs with the prescribed gating.
- **Edge cases / errors**: not specified for Refine failure within the drawer.
- **RATIFIED — PO decision 24 May 2026** — *Refine failure inside the drawer*: on Refine failure, leave the existing enhanced content + intelligence in place and show an inline error inside the drawer (*"We couldn't refine this version. Please try again."*).
- **Guardrail touchpoints**: Shield (Refine is a Shield-routed LLM call); Trust Center (audit rows).
- **Status**: Per QA spec; Refine-failure-in-drawer path **ratified** per G10 (24 May 2026).

---

### 4.D Aggregated / cross-surface flows

**Primary QA source:** `/app/memory/sprints/qa_24may2026/aggregated_qa_24may2026.md`

#### Journey X1 — Search bar in "Link an earlier document" panel (Add a document to Document Journal)

- **QA source**: Aggregated QA · § Adding a Document to Document Journal (Figure 1)
- **Actors**: any authenticated user adding a document
- **Trigger / entry point**: opening the dropdown list shown in Figure 1 during the add-document flow
- **Steps**:
  1. A search bar is added at the top of the dropdown list (Figure 1).
  2. Typing in the search bar filters the available options by document name **in real time as the user types**.
- **Acceptance / done state**: scroll-through-the-full-list is no longer required; live filter narrows the list.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none (client-side filter over the existing document corpus).
- **Status**: Per QA spec.

#### Journey X2 — Akki Chat responsive layout + fixed input bar

- **QA source**: Aggregated QA · § Akki Chat (Figures 2 and 3)
- **Actors**: any authenticated user on Akki Chat
- **Trigger / entry point**: rendering the chat surface
- **Steps**:
  1. **Responsive layout** (Figure 2): the chat interface is fully responsive, adjusting its content width to fit within the visible viewport at all times. Message bubbles and text wrap within the available width rather than overflow. **No horizontal scrolling** is required to read conversation content.
  2. **Fixed input bar** (Figure 3): the input box at the bottom of the chat interface — where the user types a question, attaches a document, or pastes text — **is fixed and remains anchored to the bottom of the screen at all times**. It does not scroll with the chat content. The chat messages above it are the only element that scrolls.
- **Acceptance / done state**: no horizontal scroll on any viewport; input bar stays anchored regardless of scroll position.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Shield (every chat message is Shield-routed); Trust Center (audit rows).
- **Status**: Per QA spec.

#### Journey X3 — Pulse: Resolved tab + remove citations + bullet-restructure signal cards

- **QA source**: Aggregated QA · § Pulse (Figures 4 and 5)
- **Actors**: any authenticated user on Pulse
- **Trigger / entry point**: page render
- **Steps**:
  1. **Resolved tab** (Figure 4): all signals that have been marked as resolved are surfaced under the **Resolved** tab in the Pulse page.
  2. **Signal card restructure** (Figure 5):
     - **Remove document citations** highlighted in Figure 5.
     - **Restructure content** within each signal card into concise bullet points presenting the key information.
- **Acceptance / done state**: Resolved tab lists all resolved signals; signal-card content is bulleted with no document citations.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: Shield (signal generation is Shield-routed); Trust Center (audit rows).
- **Status**: Per QA spec.

#### Journey X4 — Monitor: remove filter tabs (objectives + projects)

- **QA source**: Aggregated QA · § Monitor item 1 (Figures 6 and 7)
- **Actors**: any authenticated user on Monitor
- **Trigger / entry point**: page render
- **Steps**: delete the filter tabs circled in Figure 6 and Figure 7.
- **Acceptance / done state**: those filter tabs no longer render.
- **Edge cases / errors**: not specified in QA.
- **Guardrail touchpoints**: none.
- **Status**: Per QA spec.

#### Journey X5 — Monitor: objective / project side drawer

- **QA source**: Aggregated QA · § Monitor (Figures 8 and 9)
- **Actors**: any authenticated user on Monitor
- **Trigger / entry point**: clicking an objective card or project card opens a side drawer (Figure 8)
- **Steps** — the drawer displays objective or project details (Figure 9), with the following updates:
  1. **Delete the Akki Status** section.
  2. **Move the Description section** to sit **below the Status card**. The Description is displayed as entered by the user; it is the primary input the agent uses to understand the context of the objective or project when processing an update.
  3. **Update CTA** — a single button sits directly below the Description:
     - For objectives: **Update Objective**
     - For projects: **Update Project**
     - When clicked, the agent searches the **Document Journal** for relevant documents to assess the current status, score, and trend.
     - If no relevant documents are found, the agent prompts the user to upload a document directly. The **file-upload modal opens**, the user uploads the relevant document, and the agent proceeds with the update using the uploaded file.
  4. **On completion**:
     - The **Status Card** at the top of the drawer updates immediately to reflect the new status, score, and trend.
     - The corresponding card in the objectives/projects list **also updates simultaneously**.
     - The drawer **remains open** so the user can review the changes in context.
  5. **Citations Card** — appears directly below the Update CTA **after** an update has been processed. Lists the document references the agent used to justify the updated status, score, and trend. Each citation shows the document name and is presented as a reference the user can verify. The card updates each time a new update is processed.
  6. **Timeline** — sits at the bottom of the drawer below the Citations card. Shows a chronological log of all updates made to the objective or project. Each entry shows the timestamp and the change made. Displays **"No timeline events yet"** when no updates have been processed.
- **Acceptance / done state**: drawer renders with the new order and the Update CTA produces the prescribed cascading updates.
- **Edge cases / errors**: not specified beyond the "no relevant documents" branch above.
- **Guardrail touchpoints**: Shield (Update is a Shield-routed LLM call); Trust Center (audit rows); ClamAV (any inline upload).
- **Status**: Per QA spec.

#### Journey X6 — Monitor Strategic Goals: dual RAG progress bars

- **QA source**: Aggregated QA · § Monitor (Figure 9)
- **Actors**: any authenticated user on Monitor → Strategic Goals
- **Trigger / entry point**: page render
- **Steps**:
  1. The **performance progress bar** and **probability progress bar** on each strategic goal card use **distinct colours independently of each other**, since a goal can have a high probability of being achieved while currently being off track on performance, or vice versa.
  2. **Performance Progress Bar** — colour maps to the performance status shown on the card:
     - **On Track** — green
     - **Achieved** — green
     - **At Risk** — amber
     - **Off Track** — red
  3. **Probability Progress Bar** — colour follows the same logic based on the probability assessment:
     - **High confidence** — green
     - **Moderate confidence** — amber
     - **Low confidence** — red
- **Acceptance / done state**: each bar's colour reflects its independent status.
- **Edge cases / errors**: not specified.
- **RATIFIED — PO decision 24 May 2026** — *Probability bands thresholds*: align with the existing strategic-goal `probability` field — **High ≥ 70**, **Moderate 40–69**, **Low < 40**.
- **Guardrail touchpoints**: Shield (probability + performance are derived from Shield-routed Update calls); Trust Center (audit rows).
- **Status**: Per QA spec for the colour rule; numeric thresholds for probability bands **ratified** per G11 (24 May 2026).

#### Journey X7 — Strategic Goals: "Document journal link" → "Upload Document" link

- **QA source**: Aggregated QA · § Monitor (Figure 10)
- **Actors**: any authenticated user on a Strategic Goal
- **Trigger / entry point**: state where the goal has no relevant documents in the journal
- **Steps**: change the **document journal link** in Figure 10 to an **Upload Document** link that opens the **file-upload modal directly**. The user uploads the relevant document and the agent uses it to reassess the goal.
- **Acceptance / done state**: link target is the file-upload modal, not the journal page; the agent reassesses on completion.
- **Edge cases / errors**: not specified.
- **Guardrail touchpoints**: ClamAV (upload scanned); Shield (reassess is Shield-routed); Trust Center (audit rows).
- **Status**: Per QA spec.

#### Journey X8 — Strategic Goals: filter tabs + category filter

- **QA source**: Aggregated QA · § Monitor (Figure 11)
- **Actors**: any authenticated user on Monitor → Strategic Goals
- **Trigger / entry point**: page render
- **Steps**:
  1. Add filter tabs in the Strategic Goals section: **All, On Track, At Risk, Off Track, Achieved, Not Started**. Each tab shows a **count of strategic goals** in that state (arrow under *25 goals…* in Figure 11). Clicking a tab filters the strategic goals list to show only goals matching that status.
  2. On the **same line** as the filter tabs, add a **category filter on the right side** allowing the user to filter strategic goals by category — for example **Operations, People, Compliance, Product, Commercial**.
  3. The category filter and status tabs **work in combination** — the user can select a status tab and a category simultaneously to narrow the list to a specific subset.
- **Acceptance / done state**: status tabs + category filter both render with live counts and combine for narrower filtering.
- **Edge cases / errors**: not specified.
- **RATIFIED — PO decision 24 May 2026** — *Category source list*: source from the existing `strategic_goals` collection's `department` field values for the active context, plus the example labels as fixed options if no department values exist.
- **Guardrail touchpoints**: none for the tabs themselves; X5 / X7 guardrails apply when goals are updated.
- **Status**: Per QA spec for the tabs + category filter behaviour; canonical category list **ratified** per G12 (24 May 2026).

---

## 5. Other surfaces — out of scope for this spec

The following surfaces exist in product but are **not covered by the four 24 May 2026 QA reports** and are therefore explicitly **out of scope** for this document. No journeys are invented for them here.

- **Solva** — has its own brief at `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md` (SV-01 … SV-08). Deferred from this spec at the PO's direction.
- **Onboarding (J1 re-intro banner + Trust Center tooltips)** — built once on disk, then reverted; preserved at `/app/memory/sprints/J1_PRESERVED_STATE.md`. Dormant pending T5 completion. Out of scope here.
- **Trust Center user page** — guardrail-side (§3.2) is in scope; the page UX is settled and not covered by these four reports. Out of scope for journeys.
- **Admin / Superadmin surfaces** — Shield observability, audit-invariants, back-fill admin endpoints. Operator-only; out of scope for product journeys here.
- **Landing / marketing site** — not covered by any of the four reports. Out of scope.
- **Settings (Profile, Billing, MFA)** — not covered by any of the four reports. Out of scope.

---

## 6. PO decisions on §6 gaps (ratified)

Every `GAP — proposed fill` block from §4 was ratified by the PO on **24 May 2026**. The table below is the consolidated decision surface; the inline ratification copy lives in §4 for each journey.

| Gap ID | Journey | Surface | Short title | Cross-ref | Decision | Status |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | D6 | Document Journal | Add to Cycle — backend wire format for the new Select-Cycle-only modal | §4.A → D6 | Approved | Ratified by PO — 24 May 2026 |
| G2 | D7 | Document Journal | Take into Solva — behaviour after the 422 error is fixed | §4.A → D7 | Approved + amended (continuity guarantee: source document MUST be auto-loaded as grounding into the new Solva session — no re-select / re-upload / restart) | Ratified by PO — 24 May 2026 |
| G3 | D8 | Document Journal | Generate Brief — failure-state toast wording | §4.A → D8 | Approved | Ratified by PO — 24 May 2026 |
| G4 | C2 | Cycle Manager | Setup Wizard Step 1 — required-field validation rules | §4.B → C2 | Approved | Ratified by PO — 24 May 2026 |
| G5 | C3 | Cycle Manager | Setup Wizard Step 2 — email validation + duplicate handling | §4.B → C3 | Approved | Ratified by PO — 24 May 2026 |
| G6 | C5 | Cycle Manager | Compile — enumerated download output formats | §4.B → C5 | Approved + amended (PPTX added; final set is **DOCX / PDF / PPTX**, all server-produced) | Ratified by PO — 24 May 2026 |
| G7 | W3 | Work Studio | Compiled Document page — Refine failure path | §4.C → W3 | Approved | Ratified by PO — 24 May 2026 |
| G8 | W4 | Work Studio | Side drawer vs dedicated page — entry-point disambiguation by card kind | §4.C → W4 | Approved | Ratified by PO — 24 May 2026 |
| G9 | W8 | Work Studio | Compile modal — failure inside the nested file-upload modal | §4.C → W8 | Approved | Ratified by PO — 24 May 2026 |
| G10 | W10 | Work Studio | Enhanced-document drawer — Refine failure inside the drawer | §4.C → W10 | Approved | Ratified by PO — 24 May 2026 |
| G11 | X6 | Aggregated / Monitor | Strategic Goals — numeric thresholds for probability bands | §4.D → X6 | Approved | Ratified by PO — 24 May 2026 |
| G12 | X8 | Aggregated / Monitor | Strategic Goals — canonical category source list | §4.D → X8 | Approved | Ratified by PO — 24 May 2026 |

**Total ratified GAPs: 12 (10 Approved as proposed, 2 Approved + amended — G2 and G6).**

---

## 7. Reference index

### 7.1 The four 24 May 2026 QA reports (canonical journey source)

| Report | Persisted markdown | Persisted docx |
| --- | --- | --- |
| Document Journal | `/app/memory/sprints/qa_24may2026/document_journal_qa_24may2026.md` | `/app/memory/sprints/qa_24may2026/document_journal_qa_24may2026.docx` |
| Cycle Manager | `/app/memory/sprints/qa_24may2026/cycle_manager_qa_24may2026.md` | `/app/memory/sprints/qa_24may2026/cycle_manager_qa_24may2026.docx` |
| Work Studio | `/app/memory/sprints/qa_24may2026/work_studio_qa_24may2026.md` | `/app/memory/sprints/qa_24may2026/work_studio_qa_24may2026.docx` |
| Aggregated | `/app/memory/sprints/qa_24may2026/aggregated_qa_24may2026.md` | `/app/memory/sprints/qa_24may2026/aggregated_qa_24may2026.docx` |

### 7.2 Guardrail code paths (cited for §3 only; no design changes here)

| Guardrail | Code paths |
| --- | --- |
| Synisense Shield — deidentify | `backend/services/synisense/shield/deidentifier.py` |
| Synisense Shield — canonical mint | `backend/services/synisense/shield/canonical.py` |
| Synisense Shield — reidentify (PII-class skip list) | `backend/services/synisense/shield/reidentifier.py` |
| Synisense Shield — LLM router | `backend/services/synisense/shield/llm_router.py` |
| Synisense Shield — streaming coverage | `backend/services/synisense/shield/streaming.py` |
| Synisense Shield — audit log | `backend/services/synisense/shield/audit_log.py` |
| Synisense Shield — trust receipt | `backend/services/synisense/shield/trust_receipt.py` |
| Synisense Shield — Luhn-validated PAN | `backend/services/synisense/regex_recognisers.py` |
| Trust Center — backend | `backend/routers/trust_center.py` |
| Trust Center — frontend | `frontend/src/pages/TrustCenter.jsx` |
| Trust Center — historical back-fill engine | `backend/services/backfill_shield_v1.py` |
| Trust Center — back-fill admin endpoints | `backend/routers/admin_shield_backfill.py` |
| Shield readiness probe | `backend/routers/healthz_shield.py` |
| ClamAV upload scanning | `backend/services/clamav_service.py` |
| Postmark inbound (MailboxHash routing) | `backend/routers/inbound_email.py`, `backend/routers/inbound_queue.py` |
| Audit invariant violations | `backend/routers/admin_audit_invariant.py` |

---

*End of `AKKI_PRODUCT_SPEC.md` v1.0 (24 May 2026).*
