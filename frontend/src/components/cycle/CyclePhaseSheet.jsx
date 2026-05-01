/**
 * CyclePhaseSheet — side panel that opens when a user clicks a phase
 * pill in the strip. Shows the artefact summary for that phase against
 * the current cycle window.
 *
 * Desktop: slides in from the right (Sheet `side="right"`).
 * Mobile : slides in from the bottom (Sheet `side="bottom"`).
 *
 * Empty sections collapse — we never render “0 documents”.
 */
import React, { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { ArrowRight, Calendar } from "lucide-react";

const SECTION_LABEL = {
  documents: "Documents",
  signals: "Signals",
  ask_messages: "Ask answers",
  briefings: "Briefings",
  decks: "Decks",
  walkin: "Walk-in sessions",
  reports: "Reports",
  signal_actions: "Signal actions",
};

const RECENT_TITLE_KEY = {
  documents: "name",
  signals: "headline",
  ask_messages: "question",
  briefings: "title",
  decks: "title",
  walkin: "title",
  reports: "title",
  signal_actions: "label",
};

function prettyDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  } catch (_) {
    return iso;
  }
}

export default function CyclePhaseSheet({
  open,
  onOpenChange,
  phase,
  emphasis = "upcoming",
  loadSummary,
  isMobile = false,
}) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || !phase) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSummary(null);
    (async () => {
      try {
        const data = await loadSummary(phase.id, 0);
        if (!cancelled) setSummary(data);
      } catch (err) {
        if (!cancelled) setError("AKKI couldn’t load this phase summary.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, phase, loadSummary]);

  const subtitle =
    emphasis === "current" ? "Current phase"
      : emphasis === "past" ? "Past phase"
        : "Upcoming phase";

  const sections = summary && summary.artefacts ? Object.entries(summary.artefacts) : [];
  const nonEmptySections = sections.filter(([, v]) => (v?.count || 0) > 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isMobile ? "bottom" : "right"}
        className={`bg-white border-[var(--rule)] p-0 ${
          isMobile ? "max-h-[85vh] overflow-hidden" : "w-full sm:max-w-[440px] overflow-hidden"
        }`}
        data-testid="cycle-phase-sheet"
      >
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-[var(--rule)] text-left">
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-1">
            {subtitle}
          </p>
          <SheetTitle className="akki-serif text-[20px] font-normal text-[var(--ink)]">
            {phase?.name || "—"}
          </SheetTitle>
          {summary?.phase_window ? (
            <SheetDescription className="text-[12px] text-[var(--muted)] flex items-center gap-1.5">
              <Calendar className="w-3 h-3" />
              {prettyDate(summary.phase_window.start)} → {prettyDate(summary.phase_window.end)}
            </SheetDescription>
          ) : null}
        </SheetHeader>

        <div className={`overflow-y-auto px-6 py-5 ${isMobile ? "max-h-[calc(85vh-128px)]" : "max-h-[calc(100vh-160px)]"}`}>
          {loading ? (
            <p className="text-[12px] italic text-[var(--muted)]">Reading the cycle…</p>
          ) : null}
          {error ? (
            <p className="text-[13px] text-[var(--ink)]">{error}</p>
          ) : null}
          {!loading && !error && summary?.error ? (
            <p className="text-[13px] text-[var(--muted)] italic">{summary.error}</p>
          ) : null}
          {!loading && !error && nonEmptySections.length === 0 && !summary?.error ? (
            <p
              className="text-[13px] italic text-[var(--muted)] leading-[1.55]"
              data-testid="cycle-phase-sheet-empty"
            >
              Nothing has landed in this phase yet.
            </p>
          ) : null}

          {!loading && !error
            ? nonEmptySections.map(([key, value]) => (
                <section key={key} className="mb-6 last:mb-0">
                  <div className="flex items-baseline justify-between mb-2.5">
                    <h3 className="akki-overline text-[10px] tracking-[0.18em] text-[var(--ink)]">
                      {SECTION_LABEL[key] || key}
                    </h3>
                    <span className="text-[11px] text-[var(--muted)]">{value.count} total</span>
                  </div>
                  <ul className="divide-y divide-[var(--rule)] border-t border-b border-[var(--rule)]">
                    {(value.recent || []).slice(0, 3).map((item) => (
                      <li key={item.id} className="py-2.5">
                        <p className="akki-serif text-[13.5px] leading-[1.4] text-[var(--ink)]">
                          {item[RECENT_TITLE_KEY[key]] || item.title || item.name || item.id}
                        </p>
                        {item.created_at ? (
                          <p className="text-[11px] text-[var(--muted)] mt-0.5">{prettyDate(item.created_at)}</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ))
            : null}

          {!loading && !error && nonEmptySections.length > 0 ? (
            <div className="mt-6 pt-4 border-t border-[var(--rule)]">
              <span className="inline-flex items-center gap-1 text-[11px] italic text-[var(--muted)]">
                Filtered view ships in v2 <ArrowRight className="w-3 h-3" />
              </span>
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
