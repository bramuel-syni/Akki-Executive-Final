import React from "react";
import { ShieldCheck } from "lucide-react";

/** Wordmark: AKKI · with gold bar */
export default function Logo({ size = "md", inverted = false, className = "" }) {
  const sizes = {
    sm: { text: "text-sm", bar: "w-1 h-4" },
    md: { text: "text-base", bar: "w-1 h-5" },
    lg: { text: "text-xl", bar: "w-1 h-6" },
  };
  const s = sizes[size] || sizes.md;
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
        <span
          className={`text-[9px] font-medium uppercase tracking-[0.3em] ${inverted ? "text-[var(--accent)]" : "text-slate-400"}`}
        >
          Sandbox
        </span>
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
