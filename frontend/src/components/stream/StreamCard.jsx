import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FileText, Sparkles, CalendarDays, ScrollText, AlertTriangle, TrendingUp, CircleSlash } from "lucide-react";

const SEVERITY_BY_TYPE = {
  risk: "risk",
  opportunity: "opportunity",
  gap: "gap",
  briefing: "neutral",
  document: "neutral",
  meeting: "meeting",
};

const TYPE_ICON = {
  risk: AlertTriangle,
  opportunity: TrendingUp,
  gap: CircleSlash,
  briefing: ScrollText,
  document: FileText,
  meeting: CalendarDays,
  signal: Sparkles,
};

const TYPE_LABEL = {
  risk: "Risk",
  opportunity: "Opportunity",
  gap: "Gap",
  briefing: "Briefing",
  document: "Document",
  meeting: "Meeting",
  signal: "Signal",
};

function formatRelative(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  try { return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  catch { return iso; }
}

/**
 * StreamCard — the single card pattern used on Home & Highlights per v4.2.
 * Props:
 *   type: risk | opportunity | gap | briefing | document | meeting | signal
 *   lead: the Georgia 18px sentence (the "what to notice")
 *   timestamp: ISO string
 *   chips: [{label, tone?}]   // context chips (sector, severity, committee, etc.)
 *   gesture: {label, to}       // primary CTA
 *   secondary: [{label, onClick}]  // optional secondary gestures (visible on hover)
 *   to: click target for the whole card
 *   severity: optional override, defaults from type
 */
export default function StreamCard({
  type,
  lead,
  timestamp,
  chips = [],
  gesture,
  secondary = [],
  to,
  severity,
  source,   // optional left-chip: { label: "TULI" | "SHARED BY RUTH", tone?: "context" | "share" }
  "data-testid": testId,
}) {
  const sev = severity || SEVERITY_BY_TYPE[type] || "neutral";
  const Icon = TYPE_ICON[type] || FileText;
  const label = TYPE_LABEL[type] || type;

  const cardInner = (
    <>
      {/* Row 1: (optional source chip) + type badge + timestamp */}
      <div className="flex items-center gap-3 mb-3">
        {source?.label && (
          <span
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-[0.14em] font-medium border ${
              source.tone === "share"
                ? "bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent)]/30"
                : "bg-[var(--cream-deep)] text-[var(--muted)] border-[var(--rule)]"
            }`}
            title={source.title || source.label}
          >
            {source.label}
          </span>
        )}
        <span className="akki-type-badge inline-flex items-center gap-1.5">
          <Icon className="w-3 h-3" strokeWidth={2.2} />
          {label}
        </span>
        <span className="text-[12px] text-[var(--muted)]">{formatRelative(timestamp)}</span>
      </div>

      {/* Row 2: Georgia 18px lead sentence */}
      <p className="akki-lead mb-4">{lead}</p>

      {/* Row 3: context chips + primary gesture.
          When the whole card is already a <Link>, we render the gesture
          as a span to avoid nested <a> tags (HTML/React forbids it). */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-wrap gap-2">
          {chips.map((c, i) => (
            <span key={i} className="akki-context-chip">{c.label}</span>
          ))}
        </div>
        {gesture && (
          to ? (
            <span className="akki-gesture">
              {gesture.label} <ArrowRight className="w-3.5 h-3.5" strokeWidth={2} />
            </span>
          ) : (
            <Link
              to={gesture.to}
              className="akki-gesture"
              onClick={(e) => e.stopPropagation()}
            >
              {gesture.label} <ArrowRight className="w-3.5 h-3.5" strokeWidth={2} />
            </Link>
          )
        )}
      </div>

      {/* Secondary gestures visible on hover */}
      {secondary.length > 0 && (
        <div className="flex gap-4 mt-3 pt-3 border-t border-[var(--rule)] opacity-0 group-hover:opacity-100 transition-opacity">
          {secondary.map((s, i) => (
            <button
              key={i}
              onClick={(e) => { e.stopPropagation(); s.onClick?.(); }}
              className="text-[13px] text-[var(--muted)] hover:text-[var(--accent)] transition-colors"
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className="block akki-stream-card group akki-fade-up"
        data-severity={sev}
        data-testid={testId}
      >
        {cardInner}
      </Link>
    );
  }
  return (
    <div
      className="akki-stream-card group akki-fade-up"
      data-severity={sev}
      data-testid={testId}
    >
      {cardInner}
    </div>
  );
}
