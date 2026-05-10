/**
 * Phase C.3 — Revision history strip.
 *
 * Horizontal cards: original then each enhance, in chronological order.
 * Refused revisions render struck-through but stay clickable so the
 * executive can read the validator's reason. The card carrying the
 * `active_revision_id` gets an accent ring.
 */
import React from "react";
import { Check, AlertTriangle, GitBranch, Eye } from "lucide-react";

function shortDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return "—"; }
}

function verdictChip(v) {
  const map = {
    validated: { cls: "bg-emerald-50 text-emerald-800 border-emerald-100", label: "validated" },
    qualified: { cls: "bg-sky-50 text-sky-800 border-sky-100",         label: "qualified" },
    refused:   { cls: "bg-rose-50 text-rose-800 border-rose-100",       label: "refused" },
  };
  const x = map[v] || map.qualified;
  return (
    <span className={`inline-flex items-center text-[10px] uppercase tracking-[0.14em] font-mono border rounded-sm px-1.5 py-[1px] ${x.cls}`}>
      {x.label}
    </span>
  );
}

export default function RevisionStrip({
  revisions = [],
  activeId,
  selectedId,
  onSelect,
}) {
  if (!revisions || revisions.length === 0) {
    return (
      <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="revision-strip-empty">
        No revisions yet.
      </p>
    );
  }
  return (
    <div data-testid="revision-strip">
      <div className="flex items-center gap-2 mb-2">
        <GitBranch className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.7} />
        <h3 className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
          Revision history · {revisions.length}
        </h3>
      </div>
      <ol className="flex items-stretch gap-3 overflow-x-auto pb-2" data-testid="revision-strip-list">
        {revisions.map((r, idx) => {
          const isActive = r.id === activeId;
          const isSelected = r.id === selectedId;
          const isRefused = (r.validation?.verdict === "refused");
          const isOriginal = !r.parent_revision_id;
          const tag = isOriginal ? "Original" : `Rev ${idx}`;
          const ringCls = isSelected
            ? "ring-2 ring-[var(--accent)] ring-offset-1"
            : isActive
              ? "ring-1 ring-[var(--accent)] ring-offset-0"
              : "";
          return (
            <li key={r.id} className="shrink-0">
              <button
                type="button"
                onClick={() => onSelect?.(r.id)}
                className={`text-left w-[260px] border border-[var(--rule)] bg-white rounded-md px-3 py-2.5 hover:border-[var(--accent)] transition-colors ${ringCls}`}
                data-testid={`revision-card-${r.id}`}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] font-medium">
                    {tag}
                  </span>
                  {isActive && (
                    <span className="inline-flex items-center text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--accent-dark)] gap-1">
                      <Check className="w-3 h-3" /> active
                    </span>
                  )}
                  <span className="ml-auto text-[10.5px] text-[var(--muted)] font-mono">{shortDate(r.created_at)}</span>
                </div>
                <p
                  className={`akki-serif text-[13px] text-[var(--ink)] leading-[1.45] ${isRefused ? "line-through opacity-70" : ""} line-clamp-2`}
                  title={r.instruction}
                >
                  {r.instruction || "(no instruction recorded)"}
                </p>
                <div className="flex items-center gap-2 mt-2">
                  {verdictChip(r.validation?.verdict)}
                  {isRefused && (
                    <AlertTriangle className="w-3 h-3 text-rose-700" strokeWidth={1.8} aria-label="Refused — cannot be set active" />
                  )}
                  <Eye className="w-3 h-3 text-[var(--muted)] ml-auto" strokeWidth={1.7} aria-label="Click to inspect" />
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
