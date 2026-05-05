/**
 * Solva v3 design tokens (brief §7.1) — re-exported here so every flow /
 * artefact component picks them up from one place. Pure constants, no
 * runtime cost.
 */
export const TOKEN = Object.freeze({
  INK:    "#2A1B1D",
  DEEP:   "#5A4A4D",
  MUTED:  "#6B6B6B",
  RULE:   "#D5C9B6",
  CREAM:  "#F5EFE6",
  CREAM_DEEP: "#E8DCC8",
  ACCENT: "#C25A38",
  // Phase I.5 — WCAG AA-safe variant of the brand accent for *interactive*
  // surfaces (button fills, refusal pill, link hover). The decorative
  // ACCENT (#C25A38) ratios at 4.36 against #FFFFFF — that's a hair below
  // the 4.5:1 threshold for normal-weight text. Using ACCENT_DARK (#B85230)
  // for fills behind white text gets us to 4.90:1 (AA normal text).
  // Visual difference vs the brand accent is sub-perceptual; brand kickers
  // and dividers continue to use ACCENT.
  ACCENT_DARK: "#B85230",
  PAPER:  "#FAF7F2",
  LIGHT:  "#FFFFFF",
});

export const FONT = Object.freeze({
  GEORGIA: "Georgia, 'Times New Roman', serif",
  CALIBRI: "Calibri, 'Calibri Light', 'Helvetica Neue', Arial, sans-serif",
  CONSOLAS: "'Consolas', 'SF Mono', 'Menlo', monospace",
});

export const SUBMODULE_LABELS = Object.freeze({
  seek_clarity:        "Seek Clarity",
  develop_strategy:    "Develop Strategy",
  simulate_hypothesis: "Simulate Hypothesis",
  // User-facing label per the brief override; backend key stays `get_perspective`.
  get_perspective:     "See Different Perspectives",
});

/** prefers-reduced-motion helper. Returns true at module-evaluation time;
 *  every component should use the hook below for live updates. */
export function prefersReducedMotionSync() {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (_e) {
    return false;
  }
}
