# Adding a Document to Document Journal
- A search bar is added at the top of the dropdown list in figure 1, allowing the user to filter the available options by document name in real time as they type. This prevents the user from having to scroll through the full list to find the required document
Figure 1
# Akki Chat
- The chat interface in figure 2 should be fully responsive, adjusting its content width to fit within the visible viewport at all times
- Message bubbles and text should wrap within the available width rather than overflow
- No horizontal scrolling should be required to read conversation content


Figure 2
- The input box at the bottom of the chat interface in figure 3 — where the user types a question, attaches a document, or pastes text — is fixed and remains anchored to the bottom of the screen at all times. It does not scroll with the chat content. The chat messages above it are the only element that scrolls, allowing the user to review previous exchanges while the input box remains immediately accessible without the user needing to scroll back down to find it.

Figure 3
# Pulse
- AAll signals that have been marked as resolved are surfaced under the Resolved tab in the Pulse page shown in figure 4.

Figure 4
- Remove document citations highlighted in figure 5 and restructure content within each signal card into concise bullet points presenting the key information


Figure 5
# Monitor
- Delete the filter tabs circled in figure 6 and figure 7
Figure 6


Figure 7

- Clicking an objective card or project card in the Monitor page opens a side drawer in figure 8

Figure 8
The drawer in figure 9 displays the objective or project details. Update as follows:
- Delete the Akki Status
- Move Description Section to sit below the status card. It Displays the objective or project description as entered by the user. This is the primary input the agent uses to understand the context of the objective or project when processing an update.
- Update CTA - A single button — Update Objective for objectives and Update Project for projects — sits directly below the Description section. When clicked, the agent searches the Document Journal for relevant documents to assess the current status, score, and trend of the objective or project. If no relevant documents are found in the journal, the agent prompts the user to upload a document directly. The file upload modal opens, the user uploads the relevant document, and the agent proceeds with the update using the uploaded file.
- On completion the Status Card at the top of the drawer updates immediately to reflect the new status, score, and trend. The corresponding card in the objectives or projects list also updates simultaneously. The drawer remains open so the user can review the changes in context.
- Add Citations Card - citations card appears directly below the Update CTA after an update has been processed. The card lists the document references the agent used to justify the updated status, score, and trend. Each citation shows the document name and is presented as a reference the user can verify. The citations card updates each time a new update is processed to reflect the most recent sources used.
- Timeline - Sits at the bottom of the drawer below the citations card. Shows a chronological log of all updates made to the objective or project. Each entry shows the timestamp and the change made. Displays "No timeline events yet" when no updates have been processed.

- The performance progress bar and probability progress bar on each strategic goal card in figure 9 to use distinct colours to reflect the current status of each metric. The two bars are intentionally coloured independently of each other since a goal can have a high probability of being achieved while currently being off track on performance, or vice versa.
- Performance Progress Bar
- The progress bar colour maps to the performance status displayed on the card:
- On Track — green
- Achieved — green
- At Risk — amber
- Off Track — red
- Probability Progress Bar
- The probability progress bar follows the same colour logic based on the probability assessment:
- High confidence — green
- Moderate confidence — amber
- Low confidence — red


Figure 9
- Change document journal link in figure 10 to Upload Document link that opens the file upload modal directly. The user uploads the relevant document and the agent uses it to reassess the goal

Figure 10
- Add filter tabs at Strategic Goals section — All, On Track, At Risk, Off Track, Achieved, and Not Started — each showing a count of strategic goals in that state (arrow showing below “25 goals...” in figure 11. Clicking a tab filters the strategic goals list to show only goals matching that status.
Figure 11
On the same line as the filter tabs, add a category filter on the right side allowing the user to filter strategic goals by category — for example Operations, People, Compliance, Product, Commercial. The category filter and status tabs work in combination — the user can select a status tab and a category simultaneously to narrow the strategic goals list to a specific subset.