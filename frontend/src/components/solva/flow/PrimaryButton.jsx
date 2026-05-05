/**
 * The single primary action affordance used across the flow. Brief §7.4.
 * Accent fill, INK text in hover, generous padding. Disabled style.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";

export default function PrimaryButton({
  children,
  onClick,
  disabled = false,
  type = "button",
  ariaLabel,
  testId,
  busy = false,
  fullWidth = false,
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      aria-label={ariaLabel}
      aria-busy={busy ? "true" : undefined}
      data-testid={testId}
      style={{
        fontFamily: FONT.CALIBRI,
        fontSize: 15,
        background: disabled ? TOKEN.RULE : TOKEN.ACCENT_DARK,
        color: TOKEN.LIGHT,
        border: "none",
        padding: "14px 32px",
        cursor: disabled ? "not-allowed" : "pointer",
        borderRadius: 2,
        letterSpacing: 0.5,
        width: fullWidth ? "100%" : undefined,
        transition: "background-color 200ms ease-out",
      }}
    >
      {busy ? "…" : children}
    </button>
  );
}

export function GhostLink({ children, onClick, ariaLabel, testId }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      data-testid={testId}
      style={{
        background: "transparent",
        border: "none",
        color: TOKEN.DEEP,
        fontFamily: FONT.CALIBRI,
        fontSize: 13,
        cursor: "pointer",
        textDecoration: "underline",
        textUnderlineOffset: 4,
        padding: 0,
      }}
    >
      {children}
    </button>
  );
}
