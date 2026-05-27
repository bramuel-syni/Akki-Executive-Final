/**
 * CHAT sprint (2026-05-12) — ProviderLine.
 *
 * Renders under each AKKI assistant message metadata row, e.g.:
 *
 *   Routed via Claude Sonnet 4.5 — direct stream
 *
 * Italic if `fallback_triggered=true`. Tooltip on hover shows the
 * resolution chain.
 *
 * Style: mono 10px graphite. Pure render — no fetch.
 */
import React, { useState } from "react";

// Friendly labels per provider id (best-effort; falls through to raw id).
const PROVIDER_LABEL = {
  "anthropic_direct": "Claude · direct stream",
  "anthropic":        "Claude · direct stream",
  "claude_sonnet_4_5":"Claude Sonnet 4.5 · direct stream",
  "claude":           "Claude · direct stream",
  "openai_direct":    "GPT · direct stream",
  "openai":           "GPT · direct stream",
  "gpt-5.2":          "GPT-5.2 · direct stream",
  "google_direct":    "Gemini · direct stream",
  "google":           "Gemini · direct stream",
  "gemini-3-pro":     "Gemini 3 Pro · direct stream",
  "emergent_proxy":   "Universal LLM proxy",
  "emergent":         "Universal LLM proxy",
};

function pretty(provider) {
  if (!provider) return "Universal LLM proxy";
  return PROVIDER_LABEL[provider] || provider;
}

function chainTooltip(provider, fallback) {
  // Best-effort resolution narrative for the hover.
  if (fallback) {
    return `${pretty(provider)} — fell through to Universal LLM proxy.`;
  }
  if (provider && provider.includes("emergent")) {
    return "Universal LLM proxy — direct SDK keys not present, proxy fielded the call.";
  }
  return `${pretty(provider)} — direct SDK call, no fallback.`;
}

export default function ProviderLine({ providerUsed, fallbackTriggered, testId }) {
  const [open, setOpen] = useState(false);
  if (!providerUsed && !fallbackTriggered) return null;
  const label = pretty(providerUsed);
  const tooltip = chainTooltip(providerUsed, fallbackTriggered);
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        tabIndex={0}
        className={`font-mono text-[10px] text-[var(--graphite)] cursor-default ${
          fallbackTriggered ? "italic" : ""
        }`}
        data-testid={testId || "chat-msg-provider-line"}
      >
        Routed via {label}
      </span>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full mt-1 z-30 whitespace-nowrap font-mono text-[10px] tracking-wide px-2 py-1 rounded-sm bg-[var(--ink)] text-[var(--parchment)]"
          data-testid={`${testId || "chat-msg-provider-line"}-tooltip`}
        >
          {tooltip}
        </span>
      )}
    </span>
  );
}
