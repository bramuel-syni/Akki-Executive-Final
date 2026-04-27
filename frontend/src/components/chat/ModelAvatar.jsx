/**
 * ModelAvatar — tiny coloured square + monogram for an LLM model.
 *
 * Lets the executive see at a glance which model is answering. We don't
 * use the providers' own logos (trademark + visual noise) — instead a
 * disciplined typographic mark, colour-keyed per provider.
 *
 *   Anthropic / Claude  → oxblood
 *   OpenAI / GPT        → ink (near-black)
 *   Gemini              → muted gold
 *   Other / unknown     → muted slate
 */
import React from "react";

const PROVIDER_PALETTE = {
  anthropic: { bg: "var(--accent)", fg: "#FFFFFF", monogram: "C" },
  openai:    { bg: "var(--ink)",    fg: "#FFFFFF", monogram: "G" },
  gemini:    { bg: "var(--gold, #C9A961)", fg: "#1A1A1A", monogram: "✦" },
  default:   { bg: "var(--muted)",  fg: "#FFFFFF", monogram: "?" },
};

function paletteFor(model) {
  const provider = (model?.provider || "").toLowerCase();
  return PROVIDER_PALETTE[provider] || PROVIDER_PALETTE.default;
}

/**
 * size: "xs" (16px) | "sm" (20px, default) | "md" (28px)
 */
export default function ModelAvatar({ model, size = "sm", className = "" }) {
  const p = paletteFor(model);
  const px = size === "xs" ? 16 : size === "md" ? 28 : 20;
  const fontPx = size === "xs" ? 9 : size === "md" ? 14 : 11;
  const label = model?.label || model?.id || "Model";
  return (
    <span
      title={label}
      style={{
        background: p.bg,
        color: p.fg,
        width: px,
        height: px,
        fontSize: fontPx,
        lineHeight: `${px}px`,
      }}
      className={`inline-flex items-center justify-center rounded-sm font-semibold tabular-nums select-none shrink-0 ${className}`}
      data-testid={`model-avatar-${model?.provider || "unknown"}`}
      aria-label={label}
    >
      {p.monogram}
    </span>
  );
}
