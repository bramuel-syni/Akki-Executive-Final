import React, { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import CommentThread from "@/components/collab/CommentThread";
import CompositionStrip from "@/components/trace/CompositionStrip";
import {
  Eye, Loader2, Trash2, HelpCircle, Sparkles,
  Scale, UsersRound, TrendingUp, Brain, Globe2, Network,
  Clock, ChevronRight,
} from "lucide-react";

// Icon per lens — mapping keeps the Cream/Oxblood palette pure.
const LENS_ICON = {
  first_principles:        Brain,
  customer_obsession:      UsersRound,
  systems_thinking:        Network,
  capital_discipline:      Scale,
  stakeholder_integration: Globe2,
  organisational_culture:  TrendingUp,
};

function LensPickerCard({ lens, active, onClick }) {
  const Icon = LENS_ICON[lens.id] || Eye;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left border rounded-md p-4 transition-all bg-white ${
        active
          ? "border-[var(--accent)] shadow-sm"
          : "border-[var(--rule)] hover:border-[var(--ink)]/30"
      }`}
      data-testid={`lens-card-${lens.id}`}
    >
      <div className="flex items-start gap-3">
        <div className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${
          active ? "bg-[var(--accent-soft)]" : "bg-[var(--cream-deep)]"
        }`}>
          <Icon className={`w-4 h-4 ${active ? "text-[var(--accent)]" : "text-[var(--deep)]"}`} strokeWidth={1.8} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="akki-serif text-[15px] font-normal text-[var(--ink)] leading-snug mb-1">{lens.name}</p>
          <p className="text-[11.5px] text-[var(--muted)] leading-relaxed">{lens.hint}</p>
        </div>
      </div>
    </button>
  );
}

function RunViewer({ run, onArchive }) {
  const Icon = LENS_ICON[run.lens] || Eye;
  return (
    <article className="akki-fade-up space-y-8" data-testid={`lens-run-${run.id}`}>
      <header>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 bg-[var(--accent-soft)] rounded-md flex items-center justify-center">
            <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
          </div>
          <div>
            <p className="akki-overline">{run.lens_name} · {new Date(run.created_at).toLocaleDateString()}</p>
          </div>
        </div>
        <h1 className="akki-serif text-[26px] leading-[1.25] text-[var(--ink)] font-normal mb-3">
          {run.subject}
        </h1>
        <span className="akki-context-chip capitalize">{run.confidence} confidence</span>
      </header>

      <section className="bg-white border border-[var(--rule)] rounded-md p-5">
        <p className="akki-overline mb-2">Observation</p>
        <p className="akki-serif text-[15px] leading-[1.7] text-[var(--deep)]">{run.observation}</p>
      </section>

      <section className="bg-white border border-[var(--rule)] rounded-md p-5">
        <p className="akki-overline mb-2">Implication</p>
        <p className="akki-serif text-[15px] leading-[1.7] text-[var(--deep)]">{run.implication}</p>
      </section>

      <section className="bg-white border border-[var(--rule)] rounded-md p-5 relative">
        <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)] rounded-l-md" />
        <p className="akki-overline mb-2">Action</p>
        <p className="akki-serif text-[15px] leading-[1.7] text-[var(--deep)]">{run.action}</p>
      </section>

      {run.question_for_management && (
        <section className="bg-[var(--accent-soft)]/60 border border-[var(--accent)]/30 rounded-md p-5">
          <div className="flex items-center gap-2 mb-2">
            <HelpCircle className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
            <p className="akki-overline">Question for management</p>
          </div>
          <p className="akki-serif text-[16px] leading-[1.6] text-[var(--ink)] italic">
            "{run.question_for_management}"
          </p>
        </section>
      )}

      <div className="pt-4 border-t border-[var(--rule)] flex items-center justify-between text-[12px] text-[var(--muted)]">
        <span>AKKI synthesis · mode: {run.mode || "synth"}</span>
        <button
          onClick={() => onArchive(run)}
          className="akki-gesture text-[12.5px]"
          data-testid={`lens-archive-${run.id}`}
        >
          <Trash2 className="w-3.5 h-3.5" /> Archive
        </button>
      </div>

      <CompositionStrip artefact={run} kind="lens" />
      <CommentThread artefactType="signal" artefactId={run.signal_id || run.id} />
    </article>
  );
}

export default function LensRoom() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;
  const committees = activeContext?.committees || [];

  const [catalog, setCatalog] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  // Composer state
  const [lens, setLens] = useState("first_principles");
  const [subject, setSubject] = useState("");
  const [committeeId, setCommitteeId] = useState("all");
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      setLoading(true);
      const [c, r] = await Promise.all([
        api.get("/lens/catalog"),
        api.get(`/contexts/${contextId}/lens/runs`),
      ]);
      setCatalog(c.data || []);
      setRuns(r.data || []);
      if ((r.data || []).length > 0 && !selected) setSelected(r.data[0]);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId, selected]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelected(null); }, [contextId]);

  const onRun = async () => {
    const text = subject.trim();
    if (text.length < 10) { toast.message("Give AKKI something to chew on (≥10 chars)."); return; }
    setRunning(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/lens/run`,
        {
          lens,
          subject: text,
          committee_id: committeeId === "all" ? null : committeeId,
        },
        { timeout: 180000 },
      );
      toast.success("Lens applied");
      setSubject("");
      setSelected(data);
      setRuns((prev) => [data, ...prev]);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setRunning(false); }
  };

  const onArchive = async (run) => {
    try {
      await api.delete(`/contexts/${contextId}/lens/runs/${run.id}`);
      toast.success("Archived");
      setRuns((prev) => prev.filter((r) => r.id !== run.id));
      if (selected?.id === run.id) setSelected(null);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const activeLens = useMemo(
    () => catalog.find((l) => l.id === lens) || catalog[0],
    [catalog, lens],
  );

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-sm text-[var(--muted)]">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-[320px_1fr] overflow-hidden">
        {/* LEFT — lens picker + composer + history */}
        <aside className="border-r border-[var(--rule)] bg-[var(--cream)] flex flex-col min-h-0" data-testid="lens-rail">
          <div className="px-5 py-6 border-b border-[var(--rule)] bg-white">
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <Eye className="w-3 h-3 text-[var(--accent)]" /> The Lens · Module M14
            </p>
            <h1 className="akki-serif text-[20px] font-normal text-[var(--ink)] mb-1">Six frameworks. One subject.</h1>
            <p className="text-[11.5px] text-[var(--muted)] leading-relaxed">
              Pick a lens, feed it a subject, get a structured Observation → Implication → Action read.
            </p>
          </div>

          {/* Lens grid */}
          <div className="px-4 py-4 border-b border-[var(--rule)] space-y-2" data-testid="lens-picker">
            <p className="akki-overline mb-1">Choose a lens</p>
            {catalog.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic py-2">Loading lenses…</p>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                {catalog.map((l) => (
                  <LensPickerCard
                    key={l.id}
                    lens={l}
                    active={lens === l.id}
                    onClick={() => setLens(l.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="px-4 py-4 space-y-3 border-b border-[var(--rule)]">
            <textarea
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder={`Subject to apply ${activeLens?.name || "the lens"} to…`}
              rows={3}
              disabled={running}
              className="w-full bg-white border border-[var(--rule)] rounded-sm text-[13px] p-3 resize-none focus:outline-none focus:border-[var(--accent)] akki-serif leading-relaxed"
              data-testid="lens-subject-input"
            />
            {committees.length > 0 && (
              <select
                value={committeeId}
                onChange={(e) => setCommitteeId(e.target.value)}
                className="w-full text-[12px] border border-[var(--rule)] rounded-sm bg-white px-2 py-1.5 focus:outline-none focus:border-[var(--accent)]"
                data-testid="lens-committee-select"
              >
                <option value="all">Full board</option>
                {committees.map((cm) => <option key={cm.id} value={cm.id}>{cm.name}</option>)}
              </select>
            )}
            <Button
              onClick={onRun}
              disabled={running || !subject.trim()}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 font-medium text-sm"
              data-testid="lens-run-btn"
            >
              {running
                ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Applying lens…</>
                : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Apply lens</>}
            </Button>
          </div>

          {/* History */}
          <div className="flex-1 overflow-y-auto" data-testid="lens-history">
            {loading ? (
              <p className="p-5 text-center text-[11px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
            ) : runs.length === 0 ? (
              <p className="p-6 text-center text-[11.5px] text-[var(--muted)] leading-relaxed italic">
                No lens runs yet. Pick a lens and apply it to a subject above.
              </p>
            ) : (
              <div className="p-2">
                {runs.map((r) => {
                  const active = selected?.id === r.id;
                  const Icon = LENS_ICON[r.lens] || Eye;
                  return (
                    <button
                      key={r.id}
                      onClick={() => setSelected(r)}
                      className={`w-full text-left px-3 py-2.5 rounded-sm mb-1 transition-colors border ${
                        active
                          ? "bg-white border-[var(--accent)]/60"
                          : "border-transparent hover:bg-white"
                      }`}
                      data-testid={`lens-run-item-${r.id}`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <Icon className="w-2.5 h-2.5 text-[var(--accent)]" strokeWidth={2} />
                        <span className="text-[10px] text-[var(--muted)]">{r.lens_name}</span>
                        <Clock className="w-2.5 h-2.5 text-[var(--muted)]/70 ml-auto" />
                        <span className="text-[10px] text-[var(--muted)]">{new Date(r.created_at).toLocaleDateString()}</span>
                      </div>
                      <p className={`text-[12.5px] font-medium leading-snug line-clamp-2 ${active ? "text-[var(--ink)]" : "text-[var(--deep)]"}`}>
                        {r.subject}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        {/* RIGHT — selected run */}
        <main className="overflow-y-auto bg-[var(--cream)]" data-testid="lens-detail">
          <div className="max-w-3xl mx-auto px-8 py-10">
            {running && !selected ? (
              <div className="bg-white border border-[var(--rule)] rounded-md p-16 text-center">
                <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)] mx-auto mb-4" />
                <p className="akki-lead mb-1">Applying {activeLens?.name || "the lens"}…</p>
              </div>
            ) : selected ? (
              <RunViewer run={selected} onArchive={onArchive} />
            ) : (
              <div className="bg-white border border-[var(--rule)] rounded-md p-16 text-center akki-fade-up" data-testid="lens-splash">
                <Eye className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-5" strokeWidth={1.2} />
                <h2 className="akki-serif text-[22px] font-normal text-[var(--ink)] mb-2">Pick a lens. Feed it a subject.</h2>
                <p className="text-[14px] text-[var(--muted)] leading-relaxed max-w-md mx-auto mb-6">
                  Six structured frameworks, one consistent output: Observation → Implication → Action, plus the single question to put to management.
                </p>
                {activeLens && (
                  <div className="text-left max-w-md mx-auto bg-[var(--cream)] border border-[var(--rule)] rounded-md p-4">
                    <p className="akki-overline mb-2">About {activeLens.name}</p>
                    <p className="text-[13px] text-[var(--deep)] akki-serif">{activeLens.hint}</p>
                  </div>
                )}
                <p className="text-[11px] text-[var(--muted)] mt-4 flex items-center justify-center gap-1">
                  Start typing a subject on the left <ChevronRight className="w-3 h-3" />
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </AppShell>
  );
}
