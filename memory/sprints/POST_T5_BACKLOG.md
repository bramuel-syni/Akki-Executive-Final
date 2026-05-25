# POST-T5 Backlog

This file collects out-of-scope observations surfaced during T1–T5 implementation. Nothing here is acted on until after T5 completes. Each entry: discovery date · sprint where it surfaced · brief note · pointer.

---

## T1 (24–25 May 2026) — no items
T1 ran clean against the spec. No off-scope issues surfaced.

## T2 (25 May 2026) — 1 deferred item

- **X4 — Remove Monitor objective/project filter tabs** (`AKKI_PRODUCT_SPEC.md` v1.1 L687–L695). The user's T2 scope named only "Monitor drawer redesign" (X5) and explicitly excluded Strategic Goals (X6–X8 covered separately). X4 removes the RAG filter tabs on the *Objectives & Projects* listing panel itself — not the drawer. Strictly outside T2.3 by the user's own wording, so deferred. Surface to revisit during a follow-on sprint focused on Monitor listing UX. Spec text: *"delete the filter tabs circled in figure 6 and figure 7."*
  - File that would be touched: `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` (filterTabs L539–L548 + `<ListingShell filterTabs={filterTabs}>` prop at L658).

