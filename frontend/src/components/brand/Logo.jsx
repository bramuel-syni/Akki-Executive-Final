import React from "react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Wordmark — "AKKI". Adds " · Sandbox" suffix iff the current account is
 * in sandbox mode. Outside the app shell (marketing pages, sign-in, sign-up)
 * the suffix simply doesn't show because there's no auth context yet — that's
 * the desired behaviour: the brand is AKKI; "Sandbox" is a status label
 * earned only by the disposable evaluation environment.
 *
 * Override either way with `showSandbox={true|false}` for explicit control.
 */
export default function Logo({ size = "md", inverted = false, className = "", showSandbox }) {
  const sizes = {
    sm: { text: "text-sm", bar: "w-1 h-4" },
    md: { text: "text-base", bar: "w-1 h-5" },
    lg: { text: "text-xl", bar: "w-1 h-6" },
  };
  const s = sizes[size] || sizes.md;

  // useAuth is always available here — AuthProvider wraps the entire app
  // (including marketing routes). Read account.is_sandbox to decide the
  // suffix; allow explicit override via the `showSandbox` prop.
  const { account } = useAuth();
  const isSandbox = !!account?.is_sandbox;
  const showSuffix = typeof showSandbox === "boolean" ? showSandbox : isSandbox;

  return (
    <div className={`flex items-center gap-2.5 ${className}`} data-testid="akki-logo">
      <div className={`${s.bar} bg-[var(--accent)]`} />
      <div className="flex items-baseline gap-1.5">
        <span
          className={`font-semibold tracking-[0.15em] ${s.text} ${inverted ? "text-white" : "text-[var(--ink)]"}`}
          style={{ fontFeatureSettings: '"ss01"' }}
        >
          AKKI
        </span>
        {showSuffix && (
          <span
            className={`text-[9px] font-medium uppercase tracking-[0.3em] ${inverted ? "text-[var(--accent)]" : "text-slate-400"}`}
            data-testid="akki-logo-sandbox-suffix"
          >
            Sandbox
          </span>
        )}
      </div>
    </div>
  );
}

export function TrustStamp({ label = "Synisense verified" }) {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-[var(--accent)]">
      <ShieldCheck className="w-3 h-3" strokeWidth={2} />
      {label}
    </span>
  );
}
