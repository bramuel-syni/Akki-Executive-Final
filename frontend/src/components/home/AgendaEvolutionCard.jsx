import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Calendar, ArrowRight } from "lucide-react";

/**
 * AgendaEvolutionCard — sister card to "Ready for you". Shows what
 * happened at (or since) the last cycle / meeting, plus what's next.
 *
 * Composes from existing data (last committed report + submissions
 * since + outstanding checklists + drafted reports + briefings).
 * The narrative is rendered as a few editorial line items, not a
 * timeline graphic.
 */

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  } catch { return "—"; }
}

const TONE_DOT = {
  positive: "bg-emerald-700",
  warning: "bg-amber-600",
  neutral: "bg-[var(--muted)]/50",
};

export default function AgendaEvolutionCard() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [data, setData] = useState(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const { data: d } = await api.get(`/contexts/${cid}/agenda-evolution`);
      setData(d);
    } catch { setData(null); }
    finally { setLoaded(true); }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  if (!loaded) return (
    <div className="bg-white border border-[var(--rule)] rounded-md p-4 min-h-[200px] flex items-center justify-center">
      <p className="text-[11px] uppercase tracking-widest text-[var(--muted)]">…</p>
    </div>
  );

  const { last_meeting, since_then, next_up } = data || {};
  const hasContent = last_meeting || (since_then && since_then.length > 0);

  if (!hasContent) {
    return (
      <article className="bg-white border border-[var(--rule)] rounded-md p-4" data-testid="agenda-evolution-empty">
        <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1.5 flex items-center gap-1.5">
          <Calendar className="w-3 h-3" /> Agenda evolution
        </p>
        <p className="text-[13px] text-[var(--muted)] italic leading-relaxed">
          No board cycle has closed on this context yet. Once a report is committed, this card will track what's evolved since.
        </p>
      </article>
    );
  }

  return (
    <article className="bg-white border border-[var(--rule)] rounded-md p-4" data-testid="agenda-evolution">
      <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1.5 flex items-center gap-1.5">
        <Calendar className="w-3 h-3" /> Since the last meeting
      </p>
      {last_meeting && (
        <h3 className="akki-serif text-[17px] text-[var(--ink)] leading-snug mb-1" data-testid="agenda-last-meeting">
          {last_meeting.cycle_name}
          <span className="text-[12px] text-[var(--muted)] font-normal ml-2">· {fmtDate(last_meeting.happened_at)}</span>
        </h3>
      )}
      {last_meeting?.agenda?.length > 0 && (
        <p className="text-[12px] text-[var(--muted)] italic mb-3" data-testid="agenda-items">
          On the agenda: {last_meeting.agenda.slice(0, 3).join(" · ")}
        </p>
      )}

      {since_then && since_then.length > 0 ? (
        <ul className="space-y-1.5 mb-3" data-testid="agenda-since">
          {since_then.slice(0, 4).map((e, i) => (
            <li key={i} className="text-[12.5px] text-[var(--deep)] flex items-start gap-2 leading-snug">
              <span className={`w-1 h-1 rounded-full mt-2 shrink-0 ${TONE_DOT[e.tone] || TONE_DOT.neutral}`} />
              <span>
                <strong className="text-[var(--ink)]">{e.actor}</strong>{" "}
                <em className="text-[var(--muted)]">{e.verb}</em>{" "}
                {e.object}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[12.5px] text-[var(--muted)] italic mb-3">Nothing new since.</p>
      )}

      {next_up && (
        <div className="border-t border-[var(--rule)] pt-2.5 mt-2.5">
          <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mb-0.5">Next up</p>
          <Link
            to="/app/cycle"
            className="text-[12.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1"
            data-testid="agenda-next-up"
          >
            {next_up} <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}
    </article>
  );
}
