/**
 * Phase Z (2026-05-27) — Document origin + category display helpers.
 *
 * Frontend mirror of `backend/services/documents/origin_display.py`.
 * Both files share the SAME literal label strings — locked by
 * `test_phase_z_*.py::test_Z_a_display_maps_match`.
 *
 * The orthogonal classification mental model:
 *   origin   = "where did this doc come from?" → /app/documents tabs
 *   category = "what kind of artefact is it?"  → Work Studio tabs
 * A document has BOTH. See `auth_testing.md` and PHASE_LEDGER Phase Z
 * NOTES for the full architecture.
 *
 * Every place that renders an origin or category in the UI MUST go
 * through these helpers — `displayOrigin(o)` / `displayCategory(c)`.
 * Source-strict CI guard
 * (`test_Z_a_no_raw_origin_strings_in_jsx`) forbids raw "upload" /
 * "email_receipt" / "akki_generated" string literals in JSX so the
 * map can never drift between FE/BE.
 */

// ─────────────────────────────────────────────────────────────────
// Origin enum + display map
// ─────────────────────────────────────────────────────────────────
export const ORIGIN_VALUES = ["akki_generated", "upload", "email_receipt"];

export const ORIGIN_DISPLAY = {
  akki_generated: "Akki-generated",
  upload:         "Uploaded",
  email_receipt:  "Emailed",
};

export function displayOrigin(origin) {
  if (!origin) return "Unknown source";
  return ORIGIN_DISPLAY[origin] || "Unknown source";
}

// ─────────────────────────────────────────────────────────────────
// Category enum + display map
// ─────────────────────────────────────────────────────────────────
export const CATEGORY_VALUES = [
  "board_pack", "minutes", "draft", "deck", "report", "briefing",
];

export const CATEGORY_DISPLAY = {
  board_pack: "Main Board & Committee Packs",
  minutes:    "Minutes",
  draft:      "Drafts",
  deck:       "Decks",
  report:     "Reports",
  briefing:   "Briefing",
};

export function displayCategory(category) {
  if (!category) return "Uncategorized";
  return CATEGORY_DISPLAY[category] || "Uncategorized";
}

// ─────────────────────────────────────────────────────────────────
// Upload modal — category options list (the "+ Add a document"
// dropdown shows these 6 plus an "uncategorized" sentinel that maps
// to null on submit).
// ─────────────────────────────────────────────────────────────────
export const UPLOAD_CATEGORY_OPTIONS = [
  { value: "",           label: "Uncategorized" },
  { value: "board_pack", label: "Main Board / Committee Pack" },
  { value: "minutes",    label: "Minutes" },
  { value: "draft",      label: "Draft" },
  { value: "deck",       label: "Deck" },
  { value: "report",     label: "Report" },
  { value: "briefing",   label: "Briefing" },
];
