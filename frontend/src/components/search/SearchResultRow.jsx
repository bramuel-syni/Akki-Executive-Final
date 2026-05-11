/**
 * Phase F0 — SearchResultRow.
 *
 * Single row used by both `UniversalSearchDialog` and `SearchResults`
 * page. Keep the shape consistent so a row never looks different
 * depending on where it renders.
 */
import React from "react";
import { FileText, MessageSquare, Activity, Target, Layers } from "lucide-react";

const SURFACE_META = {
  documents:   { Icon: FileText,      label: "Document" },
  chats:       { Icon: MessageSquare, label: "Chat" },
  pulse:       { Icon: Activity,      label: "Signal" },
  monitor:     { Icon: Target,        label: "Goal" },
  cycle:       { Icon: Layers,        label: "Cycle activity" },
  work_studio: { Icon: FileText,      label: "Work Studio" },
  briefs:      { Icon: FileText,      label: "Brief" },
};

function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined,
      { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function SearchResultRow({ row, isCurrentContext, active, onClick }) {
  const meta = SURFACE_META[row.surface] || { Icon: FileText, label: row.type || "Item" };
  const Icon = meta.Icon;
  return (
    <button
      onClick={onClick}
      data-testid={`search-result-row-${row.surface}-${row.id}`}
      className={[
        "w-full px-4 py-2.5 text-left transition-colors flex items-start gap-3",
        active ? "bg-slate-50" : "hover:bg-slate-50",
      ].join(" ")}
    >
      <Icon className="w-4 h-4 mt-0.5 text-slate-400 flex-shrink-0" strokeWidth={1.6} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm text-[var(--ink)] font-medium truncate">{row.title}</p>
          {!isCurrentContext && (
            <span
              data-testid={`search-result-context-chip-${row.id}`}
              className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-amber-100 text-amber-800 flex-shrink-0"
            >
              {row.context_name}
            </span>
          )}
        </div>
        {row.snippet && (
          <p className="text-[12px] text-slate-500 truncate mt-0.5 akki-sans">
            {row.snippet}
          </p>
        )}
        <div className="flex items-center gap-2 mt-1 text-[10px] uppercase tracking-wider text-slate-400">
          <span>{row.type || meta.label}</span>
          {row.date && <span>· {fmtDate(row.date)}</span>}
        </div>
      </div>
    </button>
  );
}

export default SearchResultRow;
