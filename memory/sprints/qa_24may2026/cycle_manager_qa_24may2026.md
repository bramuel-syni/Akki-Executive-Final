
FEATURE REDESIGN SPECIFICATION
Cycle Manager
Landing Page  |  Setup Wizard  |  Cycle Page  |  Side Panel  |  Journals

| Module | Cycle Manager |
| --- | --- |
| Type | Feature Redesign Specification |
| Prepared For | Product Owner & Developer |
| Scope | Landing Page, Setup Wizard, Cycle Page, Side Panel, Draft Journal, Ready to Compile Journal |
| Date | 2026 |


1.  Overview
This document specifies the full redesign of the Cycle Manager module. It covers the landing page, the Add Cycle setup wizard, the cycle card list, the cycle page for individual cycles, the side panel, and two dedicated journal pages — the Ready to Compile Journal and the Draft Journal. The specification is self-contained and should be read and implemented as a complete redesign rather than a set of incremental changes.

| Key naming convention | The individual items within a cycle are called Agendas. The container that holds agendas, team members, contributions, and outputs is called a Cycle. The button to create a new cycle is Add Cycle. |
| --- | --- |



# 2.  Cycle Manager Landing Page
The Cycle Manager landing page shown in figure 1 has two areas: the main content area showing the cycle list, and a fixed side panel on the right. Both are always visible simultaneously.
Figure 1

## 2.1  Add Cycle Button
The primary CTA on the landing page is the Add Cycle button. Clicking it opens the Setup Wizard as specified in Section 3. Rename the current Add Agenda button to Add Cycle

## 2.2  Search and Sort
A search bar allows the user to search cycles by title in real time. A sort control sits beside the search bar with options: Most Recent (default), Oldest First, and Alphabetical A to Z. The active sort is visually indicated.

## 2.3  Filter Tabs
Four filter tabs sit below the search and sort controls. Each tab displays a count badge.

| Tab | Behaviour |
| --- | --- |
| All (default) | Lists all cycle cards regardless of status. Selected by default on page load. |
| Active | Lists only cycles that have been commissioned and are currently in progress. |
| Draft | Lists only cycles saved as drafts that have not yet been commissioned. |
| Completed | Lists only cycles the user has marked as completed. |


## 2.4  Cycle Cards
Each cycle is displayed as a card in the list. Cards are ordered by most recent by default. Each card contains:

Cycle title — the primary identifier displayed prominently.
Due date — the target completion date set during setup.
Status badge — one of three: Active, Draft, or Completed.
Compilation readiness score — the current readiness score as a percentage, reflecting contributions received so far.
Agenda item count — for example '3 agendas'.
Contributor count — for example '2 contributors'.

Clicking anywhere on a card opens the Cycle Page for that cycle as specified in Section 4.
# 3.  Add Cycle — Setup Wizard
Clicking the Add Cycle button opens a two-step setup wizard as a modal. The wizard collects the information needed to create, commission or draft a cycle.

## 3.1  Step 1 — Create a Cycle
Step 1 collects the cycle configuration. The following input fields are presented with their titles above each field:

Cycle Name — a free-text field for the name of the cycle.
Objectives / Agenda — a free-text field where the user describes the agenda items or objectives for the cycle.
Required Compilation Readiness Score — a predefined selector with five options: 80%, 85%, 90%, 95%, 100%. A helper text appears below the selector explaining what the score means: 'This is the readiness percentage you feel comfortable compiling a draft document from. When contributions reach this threshold, the cycle will be flagged as ready to compile.'
Due Date — a date picker for the target completion date of the cycle.

The Next button advances the user to Step 2. The Cancel button closes the wizard without saving.

## 3.2  Step 2 — Build the Team
Step 2 allows the user to add contributors to the cycle. The following input fields are presented for each contributor:

Name — the contributor's full name.
Email — the contributor's email address.
Role — the contributor's role or job title.
What is this person contributing? — a free-text field for the contribution brief describing what this contributor is expected to provide.
Attach Agenda Item — a dropdown listing the agenda items defined in Step 1. The contributor is assigned to one or more agenda items from this list.

Two CTAs are available at the bottom of Step 2:

Add Another Team Member
Clicking Add Another Team Member saves the current contributor's details and presents a fresh input form to add another contributor. The user can add as many contributors as needed. There is no limit.

Review Project Brief
Clicking Review Project Brief saves the current contributor's details and triggers the agent cycle to generate a Project Brief — a summary of the cycle based on everything the user has provided in Steps 1 and 2. A toast notification appears confirming the contributor has been added. The Step 2 modal closes and the Project Brief modal opens.

## 3.3  Project Brief Modal
The Project Brief modal presents the agent cycle's summary of the cycle based on the cycle name, objectives/agendas, readiness target, due date, and team member details provided in the setup wizard. The user reads the brief and has three CTAs:

Commission Cycle
The cycle status is set to Active immediately.
A toast notification appears: 'Cycle commissioned successfully.'
The modal closes and a new cycle card appears at the top of the All and Active tabs on the landing page, pulsing three times before settling.

Review
An input box labelled Review Notes appears within the modal.
The user types their review notes and clicks Update.
A brief loading state appears as the agent cycle uses the notes to update the Project Brief summary accordingly.
The user can review and update as many times as needed — there is no limit on the number of review cycles.
Once satisfied, the user can click Commission Cycle or Save as Draft.

Save as Draft
The cycle is saved with a Draft status.
A toast notification appears: 'Cycle saved as draft.'
The modal closes and a new cycle card appears at the top of the All and Draft tabs on the landing page, pulsing three times before settling.

# 4.  Cycle Page
Clicking on a cycle card opens the Cycle Page for that cycle. The Cycle Page is organised into three sections. Draft cycles additionally display an Activate Cycle button at the top of the page.

| Draft cycle | A cycle in Draft status displays an Activate Cycle button at the top of the Cycle Page. Clicking it immediately sets the cycle status to Active and shows a toast notification: 'Cycle is now active.' |
| --- | --- |


## 4.1  Section 1 — Cycle Status Overview
Section 1 provides a high-level health view of the cycle. It contains:

Due Date — displayed with the number of days remaining to the due date, for example: '15 June 2026 · 22 days remaining'.
Compilation Readiness Score — displayed as a progress bar. The bar shows the current readiness score as a fill against the target set in the setup wizard. The target is visually indicated on the bar — for example a marker at 80% — so the user can see how far the current score is from the threshold. Below the bar the number of agenda items with missing or pending contributions is shown, for example: '3 agendas pending'.
Use figure 2 for inspo

Figure 2

## 4.2  Section 2 — Contributions Table
Section 2 displays a table listing all agenda items in the cycle, their contributors, contribution status, and follow-up status.

| Column | Values | Description | Notes |
| --- | --- | --- | --- |
| Agenda Item | — | The name of the agenda item as defined in setup. | One row per agenda item. |
| Contributor | — | The name of the team member assigned to this agenda item. | Populated from the team setup. |
| Contribution Status | Pending / Missing, [Score] | Pending or Missing if no contribution has been received. If a contribution has been submitted, the contribution score is shown. | Score reflects relevance, fullness, and readiness. |
| Follow-ups | Awaiting Approval, Sent | Awaiting Approval — a follow-up draft has been generated but not yet approved by the user. Sent — the follow-up email has been sent. | For Sent: green if contributor has responded, red if no response after 3 days from send date, orange if no response and fewer than 3 days have passed since send date. For sent is red and orange provide metadata showing date sent |


## 4.3  Section 3 — Cycle Actions
Section 3 contains six action CTAs: Add Agenda, Add Team Member, Add Contribution, Manage Members, Follow Up, and Compile.

The 6 CTAs to sit in a horizontal strip and to have icons

The compile button to filled in (color black, text white) rather than outlined liked the others

Add Agenda
Opens a modal where the user can add a new agenda item to the cycle.
The modal contains an Agenda Description input field.
A contributor dropdown lists all team members added across all cycles. If the required contributor is not in the list, an Add Contributor option appears within the dropdown. Clicking it opens a modal where the user enters contributor details — name, email, role, and contribution brief — and saves. A toast notification confirms the contributor has been added and they appear in the dropdown immediately.
Adding a contributor to an agenda is optional.
The CTA in the modal is Add Agenda. Clicking it shows a toast notification confirming the agenda has been added and the new agenda item appears in the contributions table in Section 2.

Add Team Member
Opens a modal where the user adds a contributor to the cycle.
Input fields: Name, Email, Role, What are they contributing (contribution brief), Agenda to attach.
The CTA is Add Member. Clicking it shows a toast notification: 'Contributor added. You can view and manage them in Manage Members.'

Add Contribution
Opens a modal where the user attaches a document to a contributor.
The modal contains a document attachment field — the user selects or uploads a document to attach as the contribution.
A contributor dropdown lists team members assigned to the current cycle. The user selects the contributor the document belongs to.
The CTA is Record Contribution. Clicking it saves the contribution and the contribution status in the table updates accordingly.

Manage Members
Opens the Manage Members page showing all contributors assigned to the current cycle.
Each entry shows: contributor name, email, role, contribution brief and the agenda item they own.
An edit icon on each entry makes all fields editable inline. CTAs become Save and Cancel. Clicking Save updates the contributor details and dismisses the edit state.
A delete icon on each entry opens a confirmation modal: 'Are you sure you want to remove this member from the cycle?' with Cancel and Delete CTAs. Clicking Delete removes the contributor from the cycle.

Follow Up
Opens the Draft Journal filtered to show only follow-up email drafts for the current cycle. The Draft Journal is specified in Section 6.

Compile
Clicking Compile triggers the agent cycle to compile the cycle's contributions into a document.
A loading state appears while the agent cycle processes.
On completion, the user is presented with download options for the compiled document.

# 5.  Landing Page Side Panel
A fixed side panel is visible on the Cycle Manager landing page (figure 1) at all times alongside the cycle list. The panel contains two cards that update in real time as cycle data changes.

## 5.1  Ready to Compile Card
This card lists cycles whose current compilation readiness score has met or exceeded the target the user set during the setup wizard. The card updates in real time — a cycle appears on this card automatically the moment its readiness score hits the target.

The card title shows Ready to Compile with the total number of qualifying cycles displayed on the right — for example: 'Ready to Compile  |  4'.
The card body lists up to three cycle names. Clicking a cycle name navigates the user directly to that cycle's page.
Below the list a View More link opens the Ready to Compile Journal as specified in Section 7.

## 5.2  Drafts Waiting for You Card
This card shows follow-up emails drafted by the agent cycle that are awaiting the user's approval or decline before being sent.

The card title shows Drafts Waiting for You with the total number of pending email drafts displayed on the right — for example: 'Drafts Waiting for You  |  7'.
The card body lists up to three draft emails showing To: [Contributor Name] for each. Clicking a contributor name navigates the user to the Draft Journal as specified in section 6.
Below the list a View More link opens the Draft Journal as specified in Section 6.


# 6.  Draft Journal
The Draft Journal is accessible from two entry points: the View More link in the Drafts Waiting for You side panel card, and the Follow Up CTA in Section 3 of the Cycle Page. When opened from the Follow Up CTA, the Draft Journal is pre-filtered to show only drafts for that specific cycle. When opened from the side panel, it shows all drafts across all cycles.

A back button at the top of the page returns the user to the Cycle Manager landing page.
The page lists all agent cycle drafted follow-up emails as individual entries. Each entry shows the email subject, To: [Contributor Name], Cycle: [Cycle Name], For: [Agenda Item],and the current badge status which is Draft
Each entry has two CTAs: Approve and Send, and Decline.

Approve and Send
The email is sent to the contributor.
A toast notification confirms the email has been sent.
The badge on the entry changes from Draft to Sent.

Decline
The email is not sent.
A toast notification confirms the draft has been declined.
The badge on the entry changes from Draft to Declined.

# 7.  Ready to Compile Journal
The Ready to Compile Journal is accessible from the View More link in the Ready to Compile side panel card. It lists all cycles whose compilation readiness score has met or exceeded the user's target threshold.

A back button at the top of the page returns the user to the Cycle Manager landing page.
Cycles are displayed as cards. Each card shows: Cycle title, Due date, Status badge — one of three: Active, Draft, or Completed, Compilation readiness score, Agenda item count — for example '3 agendas', Contributor count — for example '2 contributors'.

Cycle Card Side Drawer
Clicking on a cycle card in the Ready to Compile Journal opens a side drawer containing:
Cycle title.
Compilation readiness score.
Due date.
List of contributors and their respective agenda items.

The CTA in the side drawer is Compile. Clicking Compile triggers the agent cycle to compile the document. A loading state appears while the agent cycle processes. On completion, the user is presented with download options for the compiled document — the same options available from the Compile button on the Cycle Page.
