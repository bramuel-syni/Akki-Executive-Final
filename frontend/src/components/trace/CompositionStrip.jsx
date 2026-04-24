import React, { useState } from "react";
import { GitBranch, Shield, Clock, User, FileText, Sparkles, ChevronDown } from "lucide-react";

/**
 * Lightweight "How this was composed" strip for LLM-generated artefacts that
 * don't use the M11 event pipeline (briefings, simulations, lens runs).
 *
 * Shows: LLM mode (live/synth), Synisense shielding count, input count
 * (signals for briefings, hypothesis for simulations), created_by + timestamp.
 *
 * Collapsed by default — a quiet provenance strip, not a loud drawer.
 */
export default function CompositionStrip({
  artefact,
  kind, // "briefing" | "simulation" | "lens"
}) {
  const [open, setOpen] = useState(false);

  const rows = buildRows(artefact, kind);
  if (!rows.length) return null;

  return (
    <section
      className="mt-6 border-t border-[var(--rule)] pt-4"
      data-testid={`composition-strip-${kind}-${artefact.id}`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-[var(--muted)] hover:text-[var(--deep)] transition-colors"
        data-testid={`composition-toggle-${artefact.id}`}
      >
        <GitBranch className="w-3 h-3" strokeWidth={1.8} />
        How this was composed
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <dl className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-[12px] akki-fade-up">
          {rows.map(({ icon: Icon, label, value }) => (
            <div
              key={label}
              className="flex items-start gap-2 bg-[var(--cream-deep)]/50 border border-[var(--rule)] rounded-sm px-3 py-2"
            >
              <Icon className="w-3.5 h-3.5 text-[var(--accent)] mt-0.5 shrink-0" strokeWidth={1.8} />
              <div className="min-w-0">
                <dt className="text-[10px] uppercase tracking-wider text-[var(--muted)]">{label}</dt>
                <dd className="text-[12.5px] text-[var(--deep)] mt-0.5 font-mono break-words">{value}</dd>
              </div>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

function buildRows(a, kind) {
  if (!a) return [];
  const rows = [];

  rows.push({ icon: Sparkles, label: "LLM mode", value: a.mode || "synth" });

  if (a.shielding_masked != null) {
    rows.push({
      icon: Shield,
      label: "Identifiers shielded",
      value: `${a.shielding_masked} masked`,
    });
  }

  if (kind === "briefing") {
    rows.push({ icon: FileText, label: "Signals used", value: `${(a.signal_ids || []).length} signal(s)` });
    rows.push({ icon: FileText, label: "Source documents", value: `${(a.source_doc_ids || []).length} doc(s)` });
  }
  if (kind === "simulation") {
    rows.push({ icon: FileText, label: "Horizon", value: a.horizon === "1y3y" ? "1y + 3y" : a.horizon });
    if ((a.signal_ids || []).length > 0) {
      rows.push({ icon: FileText, label: "Grounded against", value: `${a.signal_ids.length} signal(s)` });
    }
  }
  if (kind === "lens") {
    rows.push({ icon: FileText, label: "Lens applied", value: a.lens_name });
    if (a.signal_id) rows.push({ icon: FileText, label: "Signal ref", value: a.signal_id.slice(0, 8) + "…" });
  }

  if (a.created_at) {
    rows.push({ icon: Clock, label: "Composed", value: new Date(a.created_at).toLocaleString() });
  }
  if (a.created_by || a.author_name) {
    rows.push({
      icon: User,
      label: "By",
      value: (a.author_name || a.created_by || "unknown").slice(0, 40),
    });
  }

  return rows;
}
