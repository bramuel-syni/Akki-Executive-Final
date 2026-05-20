---
source_url: https://customer-assets.emergentagent.com/job_feature-docs/artifacts/hllpole7_Solva_QA_Module_Brief%20%281%29%20%281%29.docx
original_filename: Solva_QA_Module_Brief (1) (1).docx
retrieved: 2026-05-20
parser: extract_file_tool (docx)
persisted_by: e1_main (Chunk 9.5 dispatch pre-flight, 2026-05-20)
total_findings: 8 (SV-01 through SV-08)
chunk9_5_scope: SV-01 / SV-02 / SV-03 (SV-04 → SV-08 deferred to Chunks 13-14)
---

# QA Module Brief — Solva Feature Analysis, Bugs, Recommendations & How It Should Work

**Module:** Solva
**QA Date:** 20th May 2026
**Prepared For:** Product Owner & Developer
**Total Issues:** 7 findings across bugs, missing features, and UX improvements (+ SV-08 added)
**Document Type:** QA Module Brief

## 1. Overview

This brief documents QA findings for the Solva module captured on 20th May 2026. Solva is Akki's AI-powered problem-solving environment where users work through complex questions, risks, and decisions with structured AI assistance. Signals from Pulse can be taken directly to Solva with context pre-loaded, and documents from the Document Reader can also be brought into Solva for deeper analysis. Seven findings are documented across bugs, missing features, and UX improvements. The most critical issues are a broken How Solva Reasons redirect, a broken View All Sessions redirect returning a Field Required error, and the absence of session saving — meaning users lose all Solva work between sessions. These must be resolved before the module can be considered production-ready.

**Priority framework:**
- **Critical** — blocks core functionality. Must fix before release.
- **High** — significantly affects usability. Fix before GA.
- **Medium** — noticeable gap. Fix in next iteration.
- **Low** — minor polish item.

## 2. Findings

Seven findings are documented below in priority order. Each includes the observed behaviour, the recommendation, and a specification of how the feature should work once implemented.

### SV-01 | How Solva Reasons — Redirect Goes to Wrong URL

**Bug · Priority: Critical**

**Observed:** Clicking the How Solva Reasons link redirects the user to `https://akki-executive.emergent.host/` — the platform root — instead of `https://akki-executive.emergent.host/solva` where the Solva content is. The user lands on the home page rather than the explanatory content about how Solva works.

**Recommendation:** Fix the redirect URL to point to `https://akki-executive.emergent.host/solva`. Alternatively, surface the How Solva Reasons content as an in-app panel or modal so the user does not need to navigate away from Solva to read it.

**How it should work:**
- **Option A — Fix the redirect**: update the link target from the root URL to the correct Solva page URL (`https://akki-executive.emergent.host/solva`). This is a one-line fix and should be prioritised immediately.
- **Option B — In-app panel**: replace the external redirect with a slide-in information panel that opens within the Solva interface. The panel explains how Solva reasons through problems — its methodology, what types of questions it is designed to help with, and what the user can expect from the synthesis output. This keeps the user in context and avoids an external redirect entirely. This is the recommended long-term approach. If the in-app panel is chosen, the panel should be dismissible and accessible from a persistent help icon within the Solva interface so the user can refer to it at any time during a session.

> **Decision locked for Chunk 9.5 dispatch:** Option A.

### SV-02 | View All Sessions — Redirect Returns Field Required Error

**Bug · Priority: Critical**

**Observed:** Clicking the View All Sessions button redirects the user to a page that displays a Field Required error. The page does not load correctly. Users cannot access their session history from this button.

**Recommendation:** Fix the View All Sessions redirect so it navigates correctly to the Solva sessions list page. The Field Required error indicates a form submission or API call is being made without the required parameters — investigate the request being made on redirect and ensure all required fields are included.

**How it should work:**
Investigate the request triggered by the View All Sessions button. The Field Required error indicates a missing parameter in the API call or form submission. Identify the missing field and ensure it is passed correctly when the button is clicked. Once the redirect is fixed, the destination page should display the full list of saved Solva sessions — see SV-03 for the session list design specification. If session saving is not yet implemented (SV-03), the View All Sessions page should display an empty state rather than an error — for example: *'No sessions saved yet. Complete a Solva session and it will appear here.'*

### SV-03 | Sessions Not Saved — Introduce Automatic Session Saving

**Missing Feature · Priority: Critical**

**Observed:** Solva sessions are not currently saved. When a user navigates away from Solva — or closes the browser — all session content is lost. Users have no way to return to a previous session, review a past synthesis, or continue a paused conversation.

> **DIAGNOSTIC PRECEDENCE (Chunk 9.5 dispatch instruction):** Sessions ARE persisted server-side already (`solva_phase_d_sessions` collection + 541 orphan `solva_v2_sessions`). The QA author's claim "sessions not saved at all" is almost certainly wrong as stated. BEFORE writing any save plumbing, the dev must log in, complete one substantive exchange, then diagnose which of these is the actual gap: (a) save not firing per response, (b) listing endpoint broken / wrong param (likely tied to SV-02), (c) UI not rendering the listing response, (d) all three.

**Recommendation:** Implement automatic session saving. Every Solva session should be saved automatically after each response is provided. A toast notification confirms each save. All saved sessions are accessible from the View All Sessions page in a card-based list.

**How it should work:**
- Sessions are saved automatically after every response Akki provides within a session. The user does not need to take any action to save — saving is entirely automatic.
- A toast notification appears after each automatic save confirming the session has been saved. The toast is brief — 2 to 3 seconds — and non-intrusive. It should not block the user's interaction with the session. Example toast: **'Session saved.'**
- Each session is assigned a title automatically by Akki. The title is a key phrase extracted from the session content — for example, the main question or problem being worked through. The title is generated after the first substantive exchange and updates if the session topic shifts significantly.
- The user can edit the session title at any time from the saved sessions list. Clicking the title on a session card makes it editable inline.
- Sessions are account-scoped — a user only sees their own sessions, consistent with the information segregation model used across the platform.

> **Decision locked for Chunk 9.5 dispatch (auto-title):** Single Shield gateway LLM call per session after the first substantive exchange, store title on session row. No heuristic fallback path. CI guard `test_no_direct_llm_calls_outside_shield` must stay green.

### SV-04 | Sessions List — Design the All Sessions View With Card Format and Status Badges

**Missing Feature · Priority: High** · **DEFERRED to Chunks 13-14**

**Observed:** There is no sessions list view available to the user. The View All Sessions button fails (SV-02) and even when fixed, the destination page has not been designed. Users cannot see, search, filter, or return to previous sessions.

**Recommendation:** Design and build a sessions list page showing all saved Solva sessions as cards. Each card displays session metadata and a status badge. Sessions can be searched and filtered by status. The page is the destination for the View All Sessions button once SV-02 is resolved.

**How it should work:**
Each saved session is displayed as a card on the sessions list page. Cards are ordered by most recent first. Each card contains: the session title (bolded, auto-generated by Akki and editable by the user), the status badge (see badge definitions below), and the date of the session.

Four status badges are defined:

| Badge | Definition |
|-------|------------|
| ACTIVE | No synthesis has been shared and the user is currently interacting with the session. The session is live and in progress. |
| PAUSED | No synthesis has been shared, a day or more has passed since the last interaction, or the user navigated away from the session without completing it. The session is incomplete but recoverable. |
| COMPLETE | A synthesis has been shared by Akki and the user has not refused it. The session reached its intended conclusion. |
| REFUSED | A synthesis was shared by Akki and the user refused it. The session is closed but the refusal is recorded for reference. |

Each tab at the top of the sessions page — All, Active, Paused, Complete, Refused — filters the session cards to show only sessions with the corresponding status badge. The All tab shows every session regardless of status. Each tab displays a count badge showing the number of sessions in that status. The All tab shows the total count. The other tabs show status-specific counts. Clicking on a session card opens that session in the Solva interface, restoring the full conversation history. For Paused sessions, the user can continue from where they left off. For Complete and Refused sessions, the session is read-only — the user can review the synthesis but cannot add further inputs.

### SV-05 | Sessions List — Add Search Functionality

**Missing Feature · Priority: High** · **DEFERRED to Chunks 13-14**

**Observed:** There is no way for a user to search for a previous Solva session by keyword or phrase. As sessions accumulate over time, browsing the full list to find a specific session becomes impractical.

**Recommendation:** Add a search bar to the sessions list page. The user can type a word or phrase and the session cards update in real time to show only sessions whose title or content matches the search term.

**How it should work:**
A search bar sits at the top of the sessions list page, above the status tabs and session cards. As the user types, the session cards update in real time to show only sessions containing the search term in the session title or in the session content. Search applies across all sessions regardless of the active status tab filter. If the user has the Active tab selected and performs a search, results should come from all sessions — not only Active ones — since the user is searching for specific content, not filtering by status. If no sessions match the search term, an empty state message appears: *'No sessions found for "[search term]". Try a different word or phrase.'* Clearing the search bar restores the full sessions list in the currently selected status tab.

### SV-06 | Response Formatting — Improve Readability of Solva Outputs

**UX · Priority: Medium** · **DEFERRED to Chunks 13-14**

**Observed:** Solva responses are not well formatted. The output lacks structure — responses appear as dense unbroken text without paragraphs, headings, or lists where appropriate. This makes longer responses difficult to read and reduces the professional quality of the synthesis output, particularly for executive and NED users who will use Solva outputs for governance decisions.

**Recommendation:** Enable rich text formatting in Solva responses. Responses should use complete sentences, structured paragraphs, and lists where appropriate. Apply the same formatting standard recommended for Akki Chat in the Akki Chat QA Brief (E-03).

**How it should work:**
Solva responses should be formatted using structured paragraphs — one idea or argument per paragraph — rather than a single block of unbroken text. Where Akki identifies a list of items, steps, or options within a response, it should format these as bullet points or numbered lists rather than running them together in a sentence. Bold text should be applied to key terms, headings within a response, and critical conclusions — particularly in the synthesis output where the user needs to identify the most important points quickly. Confirm that the Solva interface renders formatted text correctly before enabling rich formatting at the model level — if the interface does not render Markdown or rich text, raw formatting symbols will appear in the response and worsen the experience. This formatting standard applies to all Solva responses — both during the interactive question-and-answer phase and in the final synthesis output.

### SV-07 | Output Window — Increase Size and Add Scroll Support

**UX · Priority: Medium** · **DEFERRED to Chunks 13-14**

**Observed:** The Solva output window is too small — it occupies a very small section of the screen and does not scroll when the content exceeds the window height. Users cannot read the full response without the content being cut off. This is a significant usability issue given that Solva responses are typically long and structured.

**Recommendation:** Increase the size of the output window so it occupies a meaningful portion of the screen. Add scroll support so that content longer than the visible area can be scrolled within the window rather than being cut off.

**How it should work:**
The output window should occupy the majority of the available vertical space on the Solva page — a minimum of 60% of the viewport height is recommended. The specific dimensions should be decided by the designer but the guiding principle is that a user should be able to read a full paragraph of Solva output without needing to scroll immediately. Add a vertical scroll bar to the output window. When the response content exceeds the visible height of the window, the scroll bar appears and the user can scroll within the window to read the full response. The window itself does not expand indefinitely — it maintains its defined height with the scroll bar providing access to overflow content. The input area — where the user types their next question or response — should remain visible and accessible at all times, regardless of how much content is in the output window. The output window and the input area should not compete for screen space in a way that makes either unusable. Test the output window at different screen sizes — desktop, laptop, and tablet — to confirm the layout adapts correctly and the output window remains readable across viewport widths.

### SV-08 | Error with status code 422 encountered when querying solva

**Bug · Priority (assumed): Critical** · **DEFERRED to Chunks 13-14**

(Spec text in the source brief ends with "as per below screen shot" — referenced screenshot not included in this document. Deferred until the screenshot artefact is provided.)
