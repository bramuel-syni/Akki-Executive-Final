/**
 * Solva v3 design tokens — migrated to v7 canonical palette
 * (SOLVA sprint, 2026-05-12). Every key now points at the canonical
 * v7 token via the CSS variable bridge, so the visible palette flows
 * from one source of truth (`frontend/src/index.css`).
 *
 * The legacy uppercase names are preserved as the JS-side dictionary so
 * the ~50 component call sites continue to render without a sweep.
 * Hard-coded brand red (`#C25A38`) becomes oxblood (`#7A2E2E`); paper /
 * cream become parchment / parchment-light. Decorative ACCENT_DARK
 * collapses into oxblood-deep.
 */
export const TOKEN = Object.freeze({
  INK:         "var(--ink)",
  DEEP:        "var(--ink)",
  MUTED:       "var(--graphite)",
  RULE:        "var(--graphite-light)",
  CREAM:       "var(--parchment-light)",
  CREAM_DEEP:  "var(--parchment)",
  ACCENT:      "var(--oxblood)",
  ACCENT_DARK: "var(--oxblood-deep)",
  PAPER:       "var(--parchment-light)",
  LIGHT:       "var(--parchment-light)",
});

export const FONT = Object.freeze({
  GEORGIA:  "var(--font-display, 'Source Serif 4', Georgia, serif)",
  CALIBRI:  "var(--font-ui, Inter, 'Calibri Light', 'Helvetica Neue', Arial, sans-serif)",
  CONSOLAS: "var(--font-mono, 'JetBrains Mono', Consolas, 'SF Mono', monospace)",
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
