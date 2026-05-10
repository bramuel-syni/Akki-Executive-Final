/**
 * NedCommittee — Phase E.3 per-committee through-line view.
 *
 * Spec §6: vertical timeline of meetings reverse-chrono, with the
 * NED's position trail and the questions log running alongside.
 * Pure read; account-scoped + context-scoped; no LLM.
 */
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft, ListChecks, Calendar, MessageCircle, ArrowRight, Loader2,
} from "lucide-react";

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function NedCommittee() {
  const { cid, committee } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.get(`/ned/committee/${cid}/${encodeURIComponent(committee)}`)
      .then(({ data }) => { if (alive) setData(data); })
      .catch((e) => { if (alive) setErr(apiErrorMessage(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [cid, committee]);

  if (loading) {
    return (
      <AppShell>
        <div className="max-w-5xl mx-auto px-6 py-12 text-center text-[var(--muted)]">
          <Loader2 className="w-4 h-4 animate-spin mx-auto" />
        </div>
      </AppShell>
    );
  }
  if (err || !data) {
    return (
      <AppShell>
        <div className="max-w-5xl mx-auto px-6 py-12">
          <p className="text-[13px] text-amber-900">{err || "Committee not found."}</p>
          <Button variant="outline" onClick={() => navigate("/app")} className="mt-4">Back to home</Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-6 py-6" data-testid="ned-committee-page">
        <button type="button" onClick={() => navigate("/app")}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1 mb-3"
          data-testid="ned-committee-back">
          <ChevronLeft className="w-3 h-3" /> Back to home
        </button>
        <p className="akki-overline text-[var(--muted)] mb-1">Committee through-line</p>
        <h1 className="akki-serif text-[22px] text-[var(--ink)] mb-1">{data.committee}</h1>
        <p className="akki-meta">{data.meeting_count} meeting{data.meeting_count === 1 ? "" : "s"} on record</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-6">
          {/* Main column — meetings timeline */}
          <div className="md:col-span-2 space-y-3" data-testid="ned-committee-meetings">
            <h2 className="akki-overline text-[var(--muted)] inline-flex items-center gap-1.5 mb-2">
              <Calendar className="w-3 h-3" /> Meetings (reverse-chronological)
            </h2>
            {(data.meetings || []).length === 0 ? (
              <p className="text-[12.5px] text-[var(--muted)] italic">No meetings on record yet.</p>
            ) : (
              <ul className="space-y-2">
                {data.meetings.map((m) => (
                  <li key={m.id}>
                    <button type="button" onClick={() => navigate(`/app/ned/meeting/${m.id}`)}
                      className="w-full text-left border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[var(--accent)] transition-colors"
                      data-testid={`ned-committee-meeting-${m.id}`}>
                      <div className="flex items-baseline justify-between gap-3 mb-1 flex-wrap">
                        <p className="akki-serif text-[13.5px] text-[var(--ink)]">{m.title}</p>
                        <p className="text-[11.5px] font-mono text-[var(--muted)]">{fmtDate(m.scheduled_at)}</p>
                      </div>
                      {m.formulated_question && (
                        <p className="text-[12px] text-[var(--ink)] italic">"{m.formulated_question.slice(0, 200)}"</p>
                      )}
                      <p className="text-[11px] font-mono text-[var(--muted)] mt-1">state: {m.state}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Right column — positions + questions */}
          <aside className="space-y-5" data-testid="ned-committee-aside">
            <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3"
                     data-testid="ned-committee-positions">
              <h2 className="akki-overline text-[var(--muted)] inline-flex items-center gap-1.5 mb-2">
                <ListChecks className="w-3 h-3" /> Position trail
              </h2>
              {(data.positions || []).length === 0 ? (
                <p className="text-[12.5px] text-[var(--muted)] italic">No positions registered yet.</p>
              ) : (
                <ul className="divide-y divide-[var(--rule)]">
                  {data.positions.slice(0, 12).map((p) => (
                    <li key={p.id} className="py-2">
                      <p className="text-[12.5px] text-[var(--ink)]">{p.decision_text}</p>
                      <p className={`text-[11px] font-mono mt-0.5 ${
                        p.position === "for" ? "text-emerald-800" :
                        p.position === "against" ? "text-rose-800" :
                        "text-amber-800"
                      }`}>{p.position} · {fmtDate(p.created_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3"
                     data-testid="ned-committee-questions">
              <h2 className="akki-overline text-[var(--muted)] inline-flex items-center gap-1.5 mb-2">
                <MessageCircle className="w-3 h-3" /> Questions log
              </h2>
              {(data.questions_log || []).length === 0 ? (
                <p className="text-[12.5px] text-[var(--muted)] italic">No questions captured yet.</p>
              ) : (
                <ul className="space-y-1.5 max-h-72 overflow-y-auto">
                  {data.questions_log.slice(0, 30).map((q, i) => (
                    <li key={i} className="text-[12px] text-[var(--ink)] leading-[1.45]">· {q}</li>
                  ))}
                </ul>
              )}
            </section>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
