import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle2, Clock, AlertTriangle, Mail, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * CycleTracker — the operational table the user asked for.
 *
 * One row per reportee × current cycle, with columns the executive can
 * scan in five seconds:
 *
 *   • Reportee (name + areas)
 *   • Latest checklist (cycle name + dispatched date + deadline)
 *   • Status         (pending_approval | dispatched | responded | overdue | not_dispatched)
 *   • What AKKI's missing  (count of unanswered Qs OR "—")
 *   • Action          (Resend / Nudge / Open submission)
 *
 * The objective is intervention triggers — when AKKI is stuck, the
 * executive can see why and unblock with one click.
 */
export default function CycleTracker({ contextId }) {
  const [reportees, setReportees] = useState([]);
  const [checklists, setChecklists] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(null);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const [r, c, s] = await Promise.all([
        api.get(`/contexts/${contextId}/reportees`),
        api.get(`/contexts/${contextId}/checklists`),
        api.get(`/contexts/${contextId}/submissions`),
      ]);
      setReportees(r.data.reportees || []);
      setChecklists(c.data.checklists || []);
      setSubmissions(s.data.submissions || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  const rows = useMemo(() => {
    const subByReportee = submissions.reduce((acc, s) => {
      const k = s.reportee_id || s.reportee_name;
      if (k) acc[k] = s;
      return acc;
    }, {});
    return reportees.filter((r) => r.status === "active").map((r) => {
      const myChecklists = checklists.filter((c) => c.reportee_id === r.id);
      const latest = myChecklists.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))[0];
      const submission = subByReportee[r.id] || subByReportee[r.name];

      let statusKey = "not_dispatched";
      let statusLabel = "Not dispatched";
      let statusTone = "text-[var(--muted)]";
      let statusIcon = Clock;

      if (submission) {
        statusKey = "responded";
        statusLabel = "Responded";
        statusTone = "text-emerald-700";
        statusIcon = CheckCircle2;
      } else if (latest?.status === "pending_approval") {
        statusKey = "pending_approval";
        statusLabel = "Awaiting your sign-off";
        statusTone = "text-amber-700";
        statusIcon = AlertTriangle;
      } else if (latest?.status === "dispatched") {
        statusKey = "dispatched";
        statusLabel = "Sent — awaiting reply";
        statusTone = "text-[var(--deep)]";
        statusIcon = Mail;
        // overdue check
        if (latest?.deadline_date) {
          try {
            const dd = new Date(latest.deadline_date);
            if (!isNaN(dd) && dd < new Date()) {
              statusKey = "overdue";
              statusLabel = "Overdue";
              statusTone = "text-red-700";
              statusIcon = AlertTriangle;
            }
          } catch { /* ignore */ }
        }
      }

      const gapCount = latest && latest.questions ? latest.questions.length : 0;
      const answeredCount = submission?.answers?.length || 0;
      const missing = latest && submission ? Math.max(0, gapCount - answeredCount)
                    : latest ? gapCount
                    : null;

      return {
        reportee: r,
        latest,
        submission,
        statusKey, statusLabel, statusTone, statusIcon,
        missing,
      };
    });
  }, [reportees, checklists, submissions]);

  const onResend = async (row) => {
    if (!row.latest?.id) return;
    setActing(row.reportee.id);
    try {
      await api.post(`/contexts/${contextId}/checklists/dispatch`, {
        checklist_ids: [row.latest.id], force: true,
      });
      toast.success(`Resent to ${row.reportee.name}.`);
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setActing(null); }
  };

  if (loading) {
    return <div className="bg-white border border-[var(--rule)] rounded-lg p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Reading the cycle…</div>;
  }

  if (rows.length === 0) {
    return <div className="bg-white border border-[var(--rule)] rounded-lg p-8 text-[13px] text-[var(--muted)] italic" data-testid="cycle-tracker">No active reportees on this context yet. Add one in the Reportees tab.</div>;
  }

  return (
    <div className="bg-white border border-[var(--rule)] rounded-lg overflow-hidden" data-testid="cycle-tracker">
      <div className="px-5 pt-4 pb-2 border-b border-[var(--rule)] bg-[var(--cream-deep)]/40">
        <p className="akki-overline mb-1">Cycle tracker</p>
        <p className="text-[12px] text-[var(--muted)] italic leading-relaxed">
          One row per reportee. <strong className="text-[var(--deep)] not-italic">Awaiting your sign-off</strong> means AKKI has drafted a checklist for this person; nothing leaves until you approve it. <strong className="text-[var(--deep)] not-italic">Sent — awaiting reply</strong> means the email is out and the deadline still has time. <strong className="text-[var(--deep)] not-italic">Overdue</strong> = past deadline; click <em>Nudge</em> to resend.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead className="bg-[var(--cream-deep)]/60 border-b border-[var(--rule)]">
            <tr>
              <th className="text-left px-5 py-2.5 akki-overline font-normal">Reportee</th>
              <th className="text-left px-3 py-2.5 akki-overline font-normal">Latest cycle</th>
              <th className="text-left px-3 py-2.5 akki-overline font-normal">Status</th>
              <th className="text-left px-3 py-2.5 akki-overline font-normal">AKKI is missing</th>
              <th className="text-left px-3 py-2.5 akki-overline font-normal">Intervention</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const Icon = row.statusIcon;
              return (
                <tr key={row.reportee.id} className="border-b border-[var(--rule)] last:border-b-0 hover:bg-[var(--cream-deep)]/30" data-testid={`tracker-row-${row.reportee.id}`}>
                  <td className="px-5 py-3">
                    <p className="text-[var(--ink)] font-medium leading-tight">{row.reportee.name}</p>
                    <p className="text-[11.5px] text-[var(--muted)] mt-0.5">{(row.reportee.areas || []).join(" · ") || row.reportee.title || "—"}</p>
                  </td>
                  <td className="px-3 py-3">
                    {row.latest ? (
                      <>
                        <p className="text-[var(--deep)] truncate max-w-[180px]">{row.latest.cycle_name}</p>
                        <p className="text-[11px] text-[var(--muted)] mt-0.5">due {row.latest.deadline_date}</p>
                      </>
                    ) : <span className="text-[var(--muted)] italic">—</span>}
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-flex items-center gap-1.5 ${row.statusTone}`} data-testid={`tracker-status-${row.reportee.id}`}>
                      <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                      {row.statusLabel}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    {row.missing === null ? <span className="text-[var(--muted)] italic">—</span>
                     : row.missing === 0 ? <span className="text-emerald-700">All answered</span>
                     : <span className="text-amber-700"><strong>{row.missing}</strong> {row.missing === 1 ? "answer" : "answers"} outstanding</span>}
                  </td>
                  <td className="px-3 py-3">
                    {row.statusKey === "overdue" || (row.statusKey === "dispatched" && row.missing > 0) ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onResend(row)}
                        disabled={acting === row.reportee.id}
                        className="border-[var(--rule)] text-[12px] h-7 px-2.5"
                        data-testid={`tracker-resend-${row.reportee.id}`}
                      >
                        {acting === row.reportee.id ? <Loader2 className="w-3 h-3 animate-spin" /> : "Nudge"}
                      </Button>
                    ) : row.statusKey === "responded" ? (
                      <span className="text-[11.5px] text-[var(--muted)] italic">No action needed</span>
                    ) : row.statusKey === "pending_approval" ? (
                      <Link
                        to="/app/cycle?tab=checklists"
                        className="inline-flex items-center gap-1 text-[12px] text-amber-700 hover:underline"
                        data-testid={`tracker-approve-${row.reportee.id}`}
                      >
                        Sign off the draft AKKI prepared →
                      </Link>
                    ) : (
                      <span className="text-[11.5px] text-[var(--muted)] italic">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-5 py-2.5 text-[11px] text-[var(--muted)] italic border-t border-[var(--rule)] bg-[var(--cream-deep)]/30">
        {rows.length} reportee{rows.length === 1 ? "" : "s"} · last refreshed {new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
      </p>
    </div>
  );
}
