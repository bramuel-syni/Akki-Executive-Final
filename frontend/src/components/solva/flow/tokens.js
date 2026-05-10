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

/**
 * Phase B.1 (2026-05-10) — submodule-specific framing copy. The previous
 * implementation rendered the same generic h1 + placeholder for every
 * submodule, which violates the spec's "render strategy-specific copy
 * at each layer" requirement (PRODUCT_SPEC.md §5.1). FT-toned framings
 * derived from the SolvaLanding card prompts; the underlying state
 * machine, scoring, and refusal templates are unchanged.
 */
export const SUBMODULE_FRAMING_COPY = Object.freeze({
  seek_clarity: {
    headline: "Tell me what's making the situation feel foggy.",
    placeholder:
      "What's hard to see clearly? Set out the numbers, the people, " +
      "what's been said, and what hasn't.",
  },
  develop_strategy: {
    headline: "Tell me about the strategic decision you're working through.",
    placeholder:
      "What are you deciding between? Set out the options, the binding " +
      "constraints (capital, time, people, the chair), and the success " +
      "criterion.",
  },
  simulate_hypothesis: {
    headline: "Tell me the hypothesis you want stress-tested.",
    placeholder:
      "State the claim. What would falsify it? What evidence would " +
      "change your mind?",
  },
  get_perspective: {
    headline: "Tell me the situation you want re-read from another angle.",
    placeholder:
      "What's the situation, and whose lens do you want it read through?",
  },
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
