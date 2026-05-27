/**
 * Phase L.b.2 (2026-05-27) — Frontend mirror of the L.b PHASE_SCRIPTS.
 *
 * The backend's `services/streaming/progress.PHASE_SCRIPTS` is the
 * canonical source. This file mirrors the 5 L.b surfaces so the
 * frontend can drive `<StreamingLogScene>` via `usePhasedTimer` for
 * surfaces where the backend SSE pipe is not yet reachable from the
 * current frontend POST shape (multipart upload, 202-job-queue,
 * legacy v2 URL paths). When those pipes are reconciled in a future
 * L.b.3 dispatch, the consumers swap to `useStreamingProgress` with
 * zero label changes.
 *
 * Labels + icons are kept VERBATIM with the backend so a future
 * source-strict CI guard can lock cross-file parity.
 */

export const LB_PHASE_SCRIPTS = {
  // L.b Surface #1 — Solva Session Synthesis (6 phases).
  "solva-synthesis": [
    { label: "Reading the layer ingest.",        icon: "book-open" },
    { label: "Checking the grounding contract.", icon: "shield-check" },
    { label: "Weighing the probability rail.",   icon: "scale" },
    { label: "Composing.",                       icon: "pen-tool" },
    { label: "Validating.",                      icon: "check-square" },
    { label: "Almost there.",                    icon: "sparkles" },
  ],

  // L.b Surface #2 — Work Studio Enhance Modal (5 phases).
  "work-studio-enhance": [
    { label: "Reading the artefact.",            icon: "book-open" },
    { label: "Checking the grounding contract.", icon: "shield-check" },
    { label: "Composing the refinement.",        icon: "pen-tool" },
    { label: "Validating.",                      icon: "check-square" },
    { label: "Almost there.",                    icon: "sparkles" },
  ],

  // L.b Surface #3 — Task Manager Compilation (7 phases).
  "task-manager-compile": [
    { label: "Reading the cycle responses.",     icon: "book-open" },
    { label: "Checking the grounding contract.", icon: "shield-check" },
    { label: "Drafting the outline.",            icon: "list" },
    { label: "Composing.",                       icon: "pen-tool" },
    { label: "Rendering the compilation.",       icon: "file-text" },
    { label: "Validating.",                      icon: "check-square" },
    { label: "Almost there.",                    icon: "sparkles" },
  ],

  // L.b Surface #4 — Events / Google Calendar Sync (5 phases).
  "events-calendar-sync": [
    { label: "Reaching Google Calendar.",        icon: "calendar" },
    { label: "Reading your calendar list.",      icon: "list" },
    { label: "Fetching the upcoming events.",    icon: "download" },
    { label: "Mapping to your context.",         icon: "map" },
    { label: "Almost there.",                    icon: "sparkles" },
  ],

  // L.b Surface #5 — Decks Generation (DEEP-tier 6 phases).
  "decks-generation": [
    { label: "Reading the outline.",             icon: "book-open" },
    { label: "Checking the grounding contract.", icon: "shield-check" },
    { label: "Composing the deck.",              icon: "pen-tool" },
    { label: "Rendering the slides.",            icon: "presentation" },
    { label: "Validating.",                      icon: "check-square" },
    { label: "Almost there.",                    icon: "sparkles" },
  ],
};

export const LB_SURFACE_IDS = Object.keys(LB_PHASE_SCRIPTS);
