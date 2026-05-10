/**
 * Phase C.3 — Work Studio shared constants.
 *
 * The picker payload from `GET /api/work_studio/picker` is the canonical
 * source for option labels and FT-toned insight strings. These local
 * constants exist purely as a render-time fallback if the picker call
 * fails — they MUST stay in sync with `backend/work_studio/brief.py::PICKER`.
 */
export const FORMAT_ORDER = ["docx", "pptx", "pdf"];
export const DEPTH_ORDER = ["executive_brief", "board_summary", "deep_dive"];
export const FIDELITY_ORDER = ["low", "high"];

export const FORMAT_LABEL = {
  docx: "Word document",
  pptx: "PowerPoint deck",
  pdf: "PDF",
};

export const DEPTH_LABEL = {
  executive_brief: "Executive Brief",
  board_summary: "Board Summary",
  deep_dive: "Deep Dive",
};

export const FIDELITY_LABEL = {
  low: "Low Fidelity (Draft)",
  high: "High Fidelity (Board Grade)",
};

/**
 * Mid-flight insight fallbacks. Replaced at runtime by the picker payload.
 * Two lines of dry copy each — matches the C.1 PICKER schema.
 */
export const FALLBACK_INSIGHT = {
  format: {
    docx: "Word — narrative prose with two-tier headings. The native form for governance memos and board narrative.",
    pptx: "PowerPoint — 16:9 slides with persistent left sidebar. The native form for board read-outs and committee briefings.",
    pdf:  "PDF — programmatic HTML rendered to a fixed page. The native form for shareable, print-ready output.",
  },
  depth: {
    executive_brief: "One-page distillation. The most consequential sentence first; everything else compresses around it.",
    board_summary: "Three-to-five page board read-out. The standard length for a tabled paper.",
    deep_dive: "Long-form analysis with supporting tables. For working sessions and committee briefings.",
  },
  fidelity: {
    low:  "Draft fidelity. Bullets and short paragraphs. For circulation under embargo or pre-read.",
    high: "Board-grade fidelity. Structured tables, KPI contracts, action grids. Production-ready output.",
  },
};

/**
 * The four scopes the C.2 enhance endpoint accepts. The fifth form
 * `section:<id>` is composed at call-time from a picked section_id.
 */
export const SCOPE_OPTIONS = [
  { value: "whole_brief", label: "Whole brief",          hint: "Edit any field; sections may be added or removed." },
  { value: "exec_summary", label: "Executive summary",   hint: "Cover, lead paragraph, and the framing section only." },
  { value: "recommendations", label: "Recommendations",  hint: "Recommendation rows and the action grid only." },
];

export function depthLabelFromPicker(picker, key) {
  const it = (picker?.depth || []).find((x) => x.key === key);
  return it?.label || DEPTH_LABEL[key] || key;
}

export function fidelityLabelFromPicker(picker, key) {
  const it = (picker?.fidelity || []).find((x) => x.key === key);
  return it?.label || FIDELITY_LABEL[key] || key;
}

export function formatLabelFromPicker(picker, key) {
  const it = (picker?.format || []).find((x) => x.key === key);
  return it?.label || FORMAT_LABEL[key] || key;
}
