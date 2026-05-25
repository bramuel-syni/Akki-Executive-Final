# Switching Context
- When a user switches company account context using the context switcher circled in figure 1 they should always land on the Home page of the newly selected account — regardless of which page they were on before initiating the switch.

Figure 1


Figure 2

# Document Journal
- The All documents button circled in figure 3 should navigate the user to the documents journal page in figure 4
Figure 3



Figure 4
- Below the search bar in the documents journal as per the arrow in figure 4 , add 4 filter tabs: All, Uploaded, Akki Generated, Briefings. The tabs should be positioned in the location indicated in Figure 4.
- Each tab displays a count badge (refer to figure 5) showing the number of documents in that category:
- All — shows every document in the journal regardless of origin. The count badge reflects the total number of documents across both categories.
- Uploaded — shows only documents that the user has manually uploaded to the platform. These are documents the user brought in from their device or external source via the upload flow.
- Akki Generated — shows only documents that Akki has produced automatically — reports, decks, and compiled documents generated through Work Studio and stored in the journal. These documents originate from Akki's generation tools, not from a user upload.
- Briefings - A document qualifies as a Briefing if and only if it was produced by the Generate Brief action.
- The active tab should be visually distinct from the inactive tabs (refer to figure 5). By default the All tab is selected on page load, showing the complete document list. Selecting a tab filters the document list immediately without requiring a page reload
Figure 5

- Under the All tabs in item 2, the cards to appear with badges as shown in Figure 6 with T:* tags removed as per item 4

Figure 6
- Remove all the T:* tags from user-facing output as highlighted in figure 7
Figure 7
- Referring to the arrow on Figure 7, the side drawer currently includes the label internal. Apply the following logic: if the existing label internal conveys that the document was manually uploaded by the user replace the word internal with uploaded. If it is not, if the document is uploaded by the user then add Uploaded tag for it to read 10 May 2026 · 4 KB· Internal· Uploaded

If the document origin is Akki Generated — that is, the document was produced by Akki through Work Studio or another generation tool — the Akki Generated tag is appended. In this case the metadata line reads: 20 May 2026 · 4 KB · Akki Generated or 20 May 2026 · 4 KB ·Internal· Akki Generated

- When user clicks on Add to Work Studio circled in green in figure 7, an Add to Work Studio modal opens up.

Modal content:

- Title: Add to Work Studio
- Supporting text: Choose the artefact type for this document.
- Artefact type options: Display selectable cards for
- Board Pack
- Minutes
- Committee Pack
- Deck
- Report
The user can select only one artefact type
- Modal CTAs to be:
- Cancel – closes the modal with no action taken.
- Add document (selected artefact type) – e.g. Add document (Board Pack) which is disabled until an artefact type is selected

- On clicking “Add document” button on the modal:
- The modal closes.
- A loading state appears to indicate that AKKI is processing the document.
- Once processing is complete, display a toast notification confirming success. If processing fails → show error toast (“We couldn’t add this document to Work Studio. Please try again.”)

- Toast message example
Your document has been added to Work Studio as a [artefact type].
- Example:
Your document has been added to Work Studio as a Board Pack.

- Navigation after completion to be:
- Open the Work Studio page and automatically navigate the user to the tab matching the selected artefact type.
- Display the newly created document card as the first item in that tab with the following highlight behaviour:
- On first appearance, highlight the new card with 2–3 gentle pulses using the platform accent colour.
- After the animation completes, the card returns to its normal/default state.

- When user clicks Add to Cycle button in figure 7, user incurs the error in figure 8.
Figure 8

- Fix the error by updating the modal as follows:
- Modal content:
- Title: Add to Cycle
- Supporting text: Choose which cycle this document contributes to.
- Add a Select Cycle dropdown listing all Active and Draft cycles available in the Cycle Manager module.
- The user can select the cycle they want to attach the document to.
- Modal CTAs are
- Cancel – closes the modal with no action taken.
- Attach to cycle  – attaches the document to the selected cycle.
- On clicking “Attach to cycle”
- The modal closes.
- The document is attached to the selected cycle.
- Display a toast notification confirming success.
Toast message example
Your document has been added to Cycle Manager in [cycle name].
Example:
Your document has been added to Cycle Manager in Q2 Board Preparation Cycle.
Error handling
If processing fails, display an error toast: We couldn’t add this document to the cycle. Please try again.

- Navigation after completion
- Open the Cycle Manager page and automatically navigate the user to the cycle listing, All Tab
- Display the newly attached cycle card within that cycle listing with highlighting behaviour:
- •	On first appearance, highlight the new card with 2–3 gentle pulses using the platform accent colour.
- •	After the animation completes, the card returns to its normal/default state.

- When user clicks Take into Solva button in figure 7, the modal in figure 9 appears. Fix the error captured in figure 9.

Figure 9


- Update the user journey for “Send to Work Studio” in Figure 10 to align with the flow defined in item 6. This includes updating the modal behaviour, loading state, toast notification, and post-action navigation to ensure consistency with the Add to Work Studio experience.

Figure 10
- Align the “Add to Cycle” button in Figure 10 to the flow in item 8
- Add the badges (uploaded or Akki Generated) discussed in item 3 next to badge as shown in the arrow in figure 10 ie. Add the origin badge — either Uploaded or Akki Generated — to the right of the existing Mixed badge in the same header row.
- Make the button text circled in blue in figure 10 visible. The text was originally “Generate Brief”

On click: Disable the Generate Brief button immediately and display a loading state to confirm the action is in progress.

- On completion: Show a toast notification confirming the brief has been generated and added to the Document Journal. Redirect the user to the Document Journal Briefings tab where the new briefing card appears at the top of the list, pulsing to draw attention to it.

- Briefing card: When the user clicks a briefing card, a side drawer opens as shown in figure 11. The CTA in the drawer is Add to Work Studio. Clicking it follows the Work with Document flow defined in item 6.

- After adding to Work Studio: When the user returns to a briefing card that has already been added to Work Studio, the Add to Work Studio CTA is replaced with a label showing it has been added — for example Added to Work Studio as [artefact type] where the artefact type reflects what was generated, for example Brief, Deck, or Report.
Figure 11


- Add a Resolve Signals button fixed to the bottom of the Akki’s Commentary panel as shown in figure 12 such that it remains visible as the user scrolls through the signals list above it. 

Clicking Resolve Signals button navigates the user to the Pulse Page navigates the user to the Pulse page with the filter pre-set to Type: All and Freshness: New.

For the text displayed beneath the Akki's Commentary title change “notes”  to read “signals”
Figure 12