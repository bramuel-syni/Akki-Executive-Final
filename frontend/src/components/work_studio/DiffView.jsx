/**
 * Phase C.3 — Section-by-section diff view.
 *
 * Consumes the diff array shape returned by C.2:
 *   [{section_id, change_type ∈ modified|added|removed, before, after}]
 *
 * Each entry renders as a card with two columns. `__envelope:<field>`
 * section_ids are rendered with a friendlier label.
 *
 * The optional accept/reject toggle is purely visual — the user-facing
 * commit path is `set_active` against the entire revision (the C.2
 * contract). Per-section accept/reject would require slicing a new
 * snapshot client-side, which the brief explicitly placed in C.3 scope.
 * Implemented as a state hint that filters which sections survive into
 * the persisted revision when the user clicks `set_active` — we don't
 * have a server-side per-section partial-accept (the C.2 design is
 * whole-revision), so the toggle here records the user's intent and
 * shows the aggregate "X sections accepted of Y" line. When the user
 * rejects ANY section, the bottom action shows a clear note that the
 * Set-Active still applies the whole revision; the spec for C.4 would
 * be the place to add per-section partial accept on the server side.
 */
import React, { useState } from "react";
import { ChevronDown, ChevronRight, Check, X as XIcon } from "lucide-react";

function envelopeLabel(sid) {
  if (!sid?.startsWith("__envelope:")) return sid;
  const key = sid.slice("__envelope:".length);
  return ({
    title: "Cover · Title",
    subtitle: "Cover · Subtitle",
    cover_lead_paragraph: "Cover · Lead paragraph",
    closing_recap: "Closing · Recap",
    framework_spine: "Framework spine",
  }[key]) || `Cover · ${key}`;
}

function changeChip(t) {
  const map = {
    modified: { color: "bg-sky-50 text-sky-800 border-sky-100", label: "modified" },
    added:    { color: "bg-emerald-50 text-emerald-800 border-emerald-100", label: "added" },
    removed:  { color: "bg-rose-50 text-rose-800 border-rose-100", label: "removed" },
  };
  const x = map[t] || map.modified;
  return (
    <span className={`inline-flex items-center text-[10.5px] uppercase tracking-[0.14em] font-mono border rounded-sm px-1.5 py-[2px] ${x.color}`}>
      {x.label}
    </span>
  );
}

function DiffCard({ entry, accepted, onToggle, expanded, onToggleExpanded }) {
  const sid = entry.section_id;
  const label = sid?.startsWith("__envelope:") ? envelopeLabel(sid) : (sid || "section");
  const before = entry.before || "";
  const after = entry.after || "";
  return (
    <li
      className="border border-[var(--rule)] bg-white rounded-md"
      data-testid={`diff-card-${sid}`}
    >
      <header className="flex items-center gap-3 px-4 py-3 border-b border-[var(--rule)]/70">
        <button
          type="button"
          onClick={onToggleExpanded}
          aria-label={expanded ? "Collapse section diff" : "Expand section diff"}
          className="text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid={`diff-card-${sid}-toggle`}
        >
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
        <p className="akki-serif text-[14px] text-[var(--ink)] font-medium flex-1 truncate">{label}</p>
        {changeChip(entry.change_type)}
        <button
          type="button"
          onClick={onToggle}
          className={`ml-1 text-[11.5px] font-medium px-2 py-1 rounded-sm border transition-colors ${
            accepted
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
          data-testid={`diff-card-${sid}-${accepted ? "accepted" : "rejected"}`}
        >
          {accepted
            ? <span className="inline-flex items-center gap-1"><Check className="w-3 h-3" /> Accepted</span>
            : <span className="inline-flex items-center gap-1"><XIcon className="w-3 h-3" /> Rejected</span>}
        </button>
      </header>
      {expanded && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-x divide-[var(--rule)]/70">
          <div className="px-4 py-3 bg-[var(--cream-deep)]/30">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">Before</p>
            {before ? (
              <pre className="akki-serif text-[13.5px] text-[var(--deep)] leading-[1.6] whitespace-pre-wrap font-[Georgia] m-0">{before}</pre>
            ) : (
              <p className="text-[12.5px] text-[var(--muted)] italic">(empty)</p>
            )}
          </div>
          <div className="px-4 py-3">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">After</p>
            {after ? (
              <pre className="akki-serif text-[13.5px] text-[var(--ink)] leading-[1.6] whitespace-pre-wrap font-[Georgia] m-0">{after}</pre>
            ) : (
              <p className="text-[12.5px] text-[var(--muted)] italic">(empty)</p>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export default function DiffView({ diff = [], onAcceptanceChange }) {
  const [accepted, setAccepted] = useState(
    () => Object.fromEntries((diff || []).map((e) => [e.section_id, true])),
  );
  const [expanded, setExpanded] = useState(
    () => Object.fromEntries((diff || []).slice(0, 3).map((e) => [e.section_id, true])),
  );

  const toggleAccept = (sid) => {
    setAccepted((prev) => {
      const next = { ...prev, [sid]: !prev[sid] };
      onAcceptanceChange?.(next);
      return next;
    });
  };
  const toggleExpand = (sid) => {
    setExpanded((prev) => ({ ...prev, [sid]: !prev[sid] }));
  };

  if (!diff || diff.length === 0) {
    return (
      <p className="text-[12.5px] text-[var(--muted)] italic px-1 py-2" data-testid="diff-empty">
        No section changes between these revisions.
      </p>
    );
  }
  const acceptedCount = Object.values(accepted).filter(Boolean).length;

  return (
    <div data-testid="diff-view">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="akki-serif text-[15px] text-[var(--ink)] font-medium">Section diffs</h3>
        <span className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
          {acceptedCount} of {diff.length} {diff.length === 1 ? "section" : "sections"} marked accepted
        </span>
      </div>
      <ul className="space-y-3" data-testid="diff-list">
        {diff.map((entry) => (
          <DiffCard
            key={entry.section_id}
            entry={entry}
            accepted={accepted[entry.section_id] !== false}
            onToggle={() => toggleAccept(entry.section_id)}
            expanded={!!expanded[entry.section_id]}
            onToggleExpanded={() => toggleExpand(entry.section_id)}
          />
        ))}
      </ul>
    </div>
  );
}
