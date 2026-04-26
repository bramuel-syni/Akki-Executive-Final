import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  ArrowRight, CalendarClock, ExternalLink, Inbox, Sparkles, Loader2,
  Send, FileText,
} from "lucide-react";

/**
 * BoardPackStages — six stage renderers for the Board Pack Play.
 *
 * Each stage receives {play, contextId, onAdvance, onPatchState} and lays
 * out the 60/40 split (left: primary content, right: working set). They
 * REUSE the existing Cycle/Reports/Schedule/Submissions UI by pointing to
 * the live routes — no domain duplication.
 */

function StageFrame({ left, right }) {
  return (
    <>
      <main className="bg-[var(--cream)] p-10 lg:border-r border-[var(--rule)] overflow-y-auto" data-testid="stage-primary">
        {left}
      </main>
      <aside className="bg-white p-8 overflow-y-auto" data-testid="stage-working-set">
        {right}
      </aside>
    </>
  );
}

function ObservationLead({ kicker, headline, body }) {
  return (
    <header className="mb-8 max-w-2xl">
      {kicker && <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-3">{kicker}</p>}
      <h2 className="akki-serif text-[28px] text-[var(--ink)] leading-tight mb-3">{headline}</h2>
      {body && <p className="akki-serif text-[15px] text-[var(--deep)] leading-relaxed italic">{body}</p>}
    </header>
  );
}

// ---------------------------------------------------------------------------
// Stage 0 — Setting the cycle
// ---------------------------------------------------------------------------
function StageSettingCycle({ play, contextId, onAdvance, onPatchState }) {
  const [schedule, setSchedule] = useState(undefined);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/cycle/schedule`);
        setSchedule(data.schedule);
      } catch { setSchedule(null); }
    })();
  }, [contextId]);

  const ready = !!schedule?.enabled;

  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="Decide who reports, and how often."
            body="Your team's submissions feed the rest of the Play. AKKI will dispatch checklists on your cadence; you gate every send."
          />
          <div className="space-y-4 max-w-xl">
            <div className="bg-white border border-[var(--rule)] rounded-md p-5 flex items-start gap-3" data-testid="stage-cycle-card">
              <CalendarClock className="w-4 h-4 text-[var(--accent)] mt-1" strokeWidth={1.7} />
              <div className="flex-1">
                <p className="akki-serif text-[16px] text-[var(--ink)] mb-1">Reporting cadence</p>
                {schedule === undefined ? (
                  <p className="text-[13px] text-[var(--muted)]">Reading your context…</p>
                ) : ready ? (
                  <p className="text-[13px] text-[var(--deep)]">
                    <strong className="text-[var(--ink)] capitalize">{schedule.cadence}</strong> on <strong className="text-[var(--ink)] uppercase">{schedule.weekday}</strong>.
                    Template: <em>"{schedule.cycle_name_template}"</em>.
                    Next run: {new Date(schedule.next_run_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}.
                  </p>
                ) : (
                  <p className="text-[13px] text-[var(--muted)] italic">No recurring cadence yet. Set one, or run this cycle manually.</p>
                )}
                <Link
                  to="/app/cycle"
                  className="text-[12px] text-[var(--accent)] hover:underline mt-2 inline-flex items-center gap-1"
                  data-testid="stage-cycle-link"
                >
                  Open Cycle to {ready ? "edit" : "set up"} <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
            </div>
            <Button onClick={onAdvance} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-advance-btn">
              {ready ? "Move on to where the gaps are" : "Skip ahead — I'll do it manually"} <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">What this stage covers</p>
          <ul className="space-y-3 text-[13px] text-[var(--deep)] leading-relaxed">
            <li><strong className="text-[var(--ink)]">Reportees</strong> — who answers each cycle.</li>
            <li><strong className="text-[var(--ink)]">Question bank</strong> — what AKKI asks them.</li>
            <li><strong className="text-[var(--ink)]">Schedule</strong> — when to dispatch.</li>
            <li><strong className="text-[var(--ink)]">Committee scope</strong> — narrow if you chair Audit or Risk.</li>
          </ul>
          <p className="text-[11.5px] text-[var(--muted)] italic mt-6 leading-relaxed">
            Set this once. AKKI will draft each cycle for your approval; nothing leaves until you say so.
          </p>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 1 — Where the gaps are
// ---------------------------------------------------------------------------
function StageGaps({ contextId, onAdvance }) {
  const [submissions, setSubmissions] = useState([]);
  const [checklists, setChecklists] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, c] = await Promise.all([
          api.get(`/contexts/${contextId}/submissions`),
          api.get(`/contexts/${contextId}/checklists`),
        ]);
        setSubmissions(s.data.submissions || []);
        setChecklists(c.data.checklists || []);
      } catch (e) { toast.error(apiErrorMessage(e)); }
      finally { setLoading(false); }
    })();
  }, [contextId]);

  const dispatched = checklists.filter((c) => c.status === "dispatched");
  const responded = checklists.filter((c) => c.status === "responded");
  const submittedNames = new Set(submissions.map((s) => s.reportee_name));
  const outstanding = dispatched.filter((c) => !submittedNames.has(c.reportee_name));

  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="Your team's submissions are in. Time to look at what's there."
            body="AKKI doesn't fill the gaps for you. It tells you where they are."
          />
          {loading ? <p className="text-[12px] uppercase tracking-widest text-[var(--muted)]">Reading the inbox…</p> : (
            <div className="space-y-6 max-w-2xl">
              <section data-testid="stage-gaps-received">
                <p className="akki-overline mb-2">What's arrived ({submissions.length})</p>
                {submissions.length === 0 ? (
                  <p className="text-[13px] text-[var(--muted)] italic">Nothing yet for this cycle.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {submissions.map((s) => (
                      <li key={s.id} className="text-[13.5px] text-[var(--deep)] flex items-baseline gap-2" data-testid={`gap-received-${s.id}`}>
                        <span className="w-1 h-1 rounded-full bg-emerald-700" />
                        <span><strong className="text-[var(--ink)]">{s.reportee_name}</strong> — {s.answers?.length || 0} answers, {s.cycle_name}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section data-testid="stage-gaps-outstanding">
                <p className="akki-overline mb-2 text-amber-700">Still outstanding ({outstanding.length})</p>
                {outstanding.length === 0 ? (
                  <p className="text-[13px] text-[var(--muted)] italic">Everyone has reported.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {outstanding.map((c) => (
                      <li key={c.id} className="text-[13.5px] text-[var(--deep)] flex items-baseline gap-2" data-testid={`gap-outstanding-${c.id}`}>
                        <span className="w-1 h-1 rounded-full bg-amber-600" />
                        <span><strong className="text-[var(--ink)]">{c.reportee_name}</strong> — due {c.deadline_date}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <Button onClick={onAdvance} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-advance-btn">
                Consolidate what's here <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </div>
          )}
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Working set</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-4">
            <strong>{submissions.length}</strong> submissions, <strong>{responded.length}</strong> responded checklists, <strong>{outstanding.length}</strong> still out.
          </p>
          <Link to="/app/cycle" className="text-[12.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1" data-testid="stage-gaps-open-inbox">
            Open the full inbox <ExternalLink className="w-3 h-3" />
          </Link>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 2 — Consolidation
// ---------------------------------------------------------------------------
function StageConsolidation({ play, contextId, onAdvance, onPatchState }) {
  const [composing, setComposing] = useState(false);
  const [reportId, setReportId] = useState(play.state?.report_id || null);
  const [title, setTitle] = useState("");
  const [cycleName, setCycleName] = useState("");

  const compose = async () => {
    if (!cycleName.trim() || !title.trim()) {
      toast.message("Pick a cycle and give the report a title.");
      return;
    }
    setComposing(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/reports/compose`,
        {
          cycle_name: cycleName.trim(), title: title.trim(),
          chain: [{ name: "Board chair", title: "Chair", email: "chair@example.com" }],
        },
        { timeout: 180000 },
      );
      setReportId(data.id);
      await onPatchState({ report_id: data.id, report_title: data.title });
      toast.success("AKKI drafted from your team's submissions. Review next.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setComposing(false); }
  };

  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="AKKI is reading what your team sent."
            body="A starter draft. Not the final word. You'll edit it next."
          />
          <div className="space-y-4 max-w-xl">
            {!reportId ? (
              <>
                <div>
                  <p className="akki-overline mb-1.5">Cycle</p>
                  <Input value={cycleName} onChange={(e) => setCycleName(e.target.value)}
                    placeholder="e.g. Q2 2026 board pack"
                    className="h-10 bg-white border-[var(--rule)] text-sm"
                    data-testid="stage-consolidate-cycle" />
                </div>
                <div>
                  <p className="akki-overline mb-1.5">Report title</p>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Q2 2026 management report to board"
                    className="h-10 bg-white border-[var(--rule)] text-sm"
                    data-testid="stage-consolidate-title" />
                </div>
                <Button onClick={compose} disabled={composing} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-consolidate-btn">
                  {composing
                    ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Reading submissions…</>
                    : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Draft the consolidation</>}
                </Button>
              </>
            ) : (
              <div className="bg-white border border-[var(--rule)] rounded-md p-5">
                <p className="akki-serif text-[16px] text-[var(--ink)] mb-1">Draft ready</p>
                <p className="text-[12.5px] text-[var(--muted)] mb-3 font-mono">report id: {reportId}</p>
                <Button onClick={onAdvance} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-advance-btn">
                  Open it for review <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
              </div>
            )}
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">What you'll get</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed">
            A markdown body assembled from submissions, with each contributor named.
            You'll be able to <em>polish, edit, or rewrite</em> in the next stage,
            then send it up your chain.
          </p>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 3 — Your review
// ---------------------------------------------------------------------------
function StageReview({ play, onAdvance }) {
  const reportId = play.state?.report_id;
  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="The draft is yours. Edit. Accept. Or rewrite."
          />
          <div className="space-y-4 max-w-xl">
            {reportId ? (
              <>
                <p className="text-[13.5px] text-[var(--deep)] leading-relaxed">
                  Open the Report editor to read AKKI's draft, polish it,
                  add your synthesis, and commit.
                </p>
                <Link
                  to={`/app/cycle?tab=reports&open=${encodeURIComponent(reportId)}`}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white rounded-md text-[13px]"
                  data-testid="stage-review-open"
                >
                  <FileText className="w-3.5 h-3.5" /> Open the report editor
                </Link>
                <div>
                  <Button onClick={onAdvance} variant="outline" className="border-[var(--rule)]" data-testid="stage-advance-btn">
                    I've reviewed it — move to distribution <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                </div>
              </>
            ) : (
              <p className="text-[13px] text-[var(--muted)] italic">No draft yet — go back to consolidation first.</p>
            )}
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Editor capabilities</p>
          <ul className="space-y-2 text-[13px] text-[var(--deep)]">
            <li><strong className="text-[var(--ink)]">Polish with AKKI</strong> — side-by-side diff before accept.</li>
            <li><strong className="text-[var(--ink)]">Save edits</strong> — your hand on every word.</li>
            <li><strong className="text-[var(--ink)]">Download PDF</strong> — for offline read.</li>
          </ul>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 4 — Distribution
// ---------------------------------------------------------------------------
function StageDistribution({ play, onAdvance }) {
  const reportId = play.state?.report_id;
  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="Send it up the chain when you're ready."
            body="AKKI delivers the email under your name. Each tier reviews, comments, then approves."
          />
          <div className="space-y-4 max-w-xl">
            <Link
              to={`/app/cycle?tab=reports${reportId ? `&open=${encodeURIComponent(reportId)}` : ""}`}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md text-[13px]"
              data-testid="stage-distribute-open"
            >
              <Send className="w-3.5 h-3.5" /> Open the report and send up
            </Link>
            <div>
              <Button onClick={onAdvance} variant="outline" className="border-[var(--rule)]" data-testid="stage-advance-btn">
                I've sent it <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </div>
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Your chain</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed">
            Author → CEO → Board chair (or whatever shape your governance takes).
            Each tier sees what came before; nobody's read is wasted.
          </p>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 5 — Done
// ---------------------------------------------------------------------------
function StageDone({ play }) {
  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="Committed. Distributed."
            body="A board pack you've reviewed and committed to. Your team's submissions are filed; the chain is moving."
          />
          <div className="space-y-3 max-w-xl">
            <p className="text-[13.5px] text-[var(--deep)] leading-relaxed">
              When the next cycle comes around, AKKI will surface a fresh trigger
              on your Home stream. You don't have to do anything in the meantime.
            </p>
            <Link to="/app" className="text-[13px] text-[var(--accent)] hover:underline" data-testid="stage-done-home">
              Back to Home →
            </Link>
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Outcome</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed italic">
            A board pack you've reviewed and committed to.
          </p>
          <p className="text-[11.5px] text-[var(--muted)] italic mt-4">
            Started {play.started_at ? new Date(play.started_at).toLocaleDateString() : "—"}.
            {play.completed_at && <> Completed {new Date(play.completed_at).toLocaleDateString()}.</>}
          </p>
        </>
      }
    />
  );
}

export function boardPackStageView() {
  return [
    StageSettingCycle,
    StageGaps,
    StageConsolidation,
    StageReview,
    StageDistribution,
    StageDone,
  ];
}
