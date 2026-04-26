import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import Sparkline from "@/components/monitor/Sparkline";
import {
  Target, Sparkles, FileText, ChevronRight, ChevronDown, Loader2, X,
  TrendingUp, AlertTriangle, CheckCircle2, Pencil, Plus,
} from "lucide-react";

/**
 * StrategicGoalsPanel — the centerpiece of the Monitor surface.
 *
 * Shows board-level KPIs (e.g. "Migrate to new ERP by Dec 2026") with
 * current score, target, owner, and probability of success. Goals are
 * either entered manually OR extracted from an uploaded strategic
 * document by the LLM.
 *
 * Rendering modes:
 *   • Executive (CEO/CFO/COO/Commercial): rows scoped to their dept +
 *     all 'board' or 'ceo' goals (since they're cross-functional).
 *     Inline edit on score/probability/status.
 *   • NED: read-only scorecard view of every department's goals.
 *
 * Empty state: friendly upload-strategy prompt with document picker.
 */

const STATUS_STYLE = {
  on_track:  { label: "On track",   tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  at_risk:   { label: "At risk",    tone: "text-amber-700 bg-amber-50 border-amber-200" },
  off_track: { label: "Off track",  tone: "text-red-700 bg-red-50 border-red-200" },
  achieved:  { label: "Achieved",   tone: "text-blue-700 bg-blue-50 border-blue-200" },
  abandoned: { label: "Abandoned",  tone: "text-slate-600 bg-slate-100 border-slate-200" },
};

const DEPT_LABEL = {
  ceo: "CEO", cfo: "CFO", coo: "COO", commercial: "Commercial", board: "Board",
};

function visibleGoalsForFunction(goals, fn, isNED) {
  if (isNED || fn === "ceo") return goals;
  // Each function sees its own department + 'board' + 'ceo' (cross-cutting)
  const allowed = new Set([fn, "board", "ceo"]);
  return goals.filter((g) => allowed.has(g.department));
}

function groupByDepartment(goals) {
  const groups = {};
  for (const g of goals) {
    const k = g.department || "ceo";
    if (!groups[k]) groups[k] = [];
    groups[k].push(g);
  }
  return groups;
}

export default function StrategicGoalsPanel({ contextId, fn, isNED, onChange }) {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [extractOpen, setExtractOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/strategic-goals`);
      setGoals(data.goals || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  const visible = useMemo(() => visibleGoalsForFunction(goals, fn, isNED), [goals, fn, isNED]);
  const groups = useMemo(() => groupByDepartment(visible), [visible]);

  const orderedDepartments = ["board", "ceo", "cfo", "coo", "commercial"]
    .filter((d) => groups[d]?.length > 0);

  const refresh = () => { load(); onChange?.(); };

  if (loading) {
    return (
      <div className="bg-white border border-[var(--rule)] rounded-md p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">
        Reading the strategy…
      </div>
    );
  }

  if (visible.length === 0) {
    return (
      <EmptyState
        contextId={contextId}
        onExtractOpen={() => setExtractOpen(true)}
        onChange={refresh}
        fn={fn}
        isNED={isNED}
        modalOpen={extractOpen}
        onModalClose={() => setExtractOpen(false)}
      />
    );
  }

  return (
    <section data-testid="strategic-goals-panel">
      <div className="flex items-end justify-between mb-3 flex-wrap gap-3">
        <div>
          <p className="akki-overline mb-1 flex items-center gap-2">
            <Target className="w-3 h-3 text-[var(--accent)]" /> Strategic goals
          </p>
          <h2 className="akki-serif text-[19px] text-[var(--ink)] leading-snug">
            {isNED
              ? "Board scorecard."
              : `${visible.length} goal${visible.length === 1 ? "" : "s"} on your function's plate.`}
          </h2>
        </div>
        {!isNED && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setExtractOpen(true)}
            className="border-[var(--rule)] text-[12px] h-8"
            data-testid="strategic-goals-add"
          >
            <Sparkles className="w-3 h-3 mr-1.5" /> Read from a strategy doc
          </Button>
        )}
      </div>

      <div className="space-y-5" data-testid="strategic-goals-groups">
        {orderedDepartments.map((dept) => (
          <div key={dept}>
            <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mb-2">
              {DEPT_LABEL[dept] || dept}
            </p>
            <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden">
              {groups[dept].map((g, i) => (
                <GoalRow
                  key={g.id}
                  goal={g}
                  isLast={i === groups[dept].length - 1}
                  isNED={isNED}
                  isEditing={editingId === g.id}
                  onEdit={() => setEditingId(g.id)}
                  onCancel={() => setEditingId(null)}
                  onSaved={() => { setEditingId(null); refresh(); }}
                  contextId={contextId}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {extractOpen && (
        <ExtractFromDocModal
          contextId={contextId}
          onClose={() => setExtractOpen(false)}
          onExtracted={() => { setExtractOpen(false); refresh(); }}
        />
      )}
    </section>
  );
}

function GoalRow({ goal, isLast, isNED, isEditing, onEdit, onCancel, onSaved, contextId }) {
  const status = STATUS_STYLE[goal.status] || STATUS_STYLE.on_track;
  const score = typeof goal.current_score === "number" ? goal.current_score : null;
  const prob = typeof goal.probability === "number" ? goal.probability : null;

  if (isEditing) {
    return <EditGoalRow goal={goal} contextId={contextId} onCancel={onCancel} onSaved={onSaved} isLast={isLast} />;
  }

  return (
    <div
      className={`px-5 py-4 ${!isLast ? "border-b border-[var(--rule)]" : ""} hover:bg-[var(--cream-deep)]/30`}
      data-testid={`strategic-goal-${goal.id}`}
    >
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="text-[14.5px] text-[var(--ink)] font-medium">{goal.title}</h3>
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wider border ${status.tone}`}>
              {goal.status === "on_track" ? <CheckCircle2 className="w-2.5 h-2.5" /> :
               goal.status === "achieved" ? <CheckCircle2 className="w-2.5 h-2.5" /> :
               goal.status === "at_risk" || goal.status === "off_track" ? <AlertTriangle className="w-2.5 h-2.5" /> : null}
              {status.label}
            </span>
          </div>
          {goal.description && (
            <p className="text-[12.5px] text-[var(--muted)] italic mb-2 leading-relaxed">{goal.description}</p>
          )}
          <div className="flex items-center gap-4 text-[11.5px] text-[var(--deep)] flex-wrap">
            {goal.target_metric && goal.target_value && (
              <span><span className="text-[var(--muted)]">Target:</span> <strong>{goal.target_value}</strong> {goal.target_metric}</span>
            )}
            {goal.target_date && <span><span className="text-[var(--muted)]">By:</span> {goal.target_date}</span>}
            {goal.owner_name && <span><span className="text-[var(--muted)]">Owner:</span> {goal.owner_name}</span>}
            {goal.current_value && <span><span className="text-[var(--muted)]">Now:</span> {goal.current_value}</span>}
            {goal.source_doc_id && (
              <Link to={`/app/documents/${goal.source_doc_id}`} className="text-[var(--accent)] hover:underline inline-flex items-center gap-1">
                <FileText className="w-3 h-3" /> source
              </Link>
            )}
          </div>
        </div>

        {/* Score + probability dials + sparkline */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex flex-col items-center" data-testid={`goal-score-block-${goal.id}`}>
            <ScoreDial label="Score" value={score} />
            <Sparkline history={goal.score_history} />
          </div>
          <ScoreDial label="Probability" value={prob} />
          {!isNED && (
            <button
              onClick={onEdit}
              className="text-[var(--muted)] hover:text-[var(--accent)] p-1"
              data-testid={`goal-edit-${goal.id}`}
              aria-label="Edit goal"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ScoreDial({ label, value }) {
  if (value === null || value === undefined) {
    return (
      <div className="text-center w-16" data-testid="score-dial-empty">
        <div className="w-10 h-10 rounded-full border-2 border-dashed border-[var(--rule)] flex items-center justify-center mx-auto">
          <span className="text-[12px] text-[var(--muted)]">—</span>
        </div>
        <p className="text-[9.5px] uppercase tracking-wider text-[var(--muted)] mt-1">{label}</p>
      </div>
    );
  }
  // Banded thresholds per user spec:
  //   < 65   → red (off-track)
  //   65-80  → amber (at-risk)
  //   > 80   → green (on-track)
  const { ring, text, bg } = value > 80
    ? { ring: "#047857", text: "text-emerald-700", bg: "bg-emerald-50" }
    : value >= 65
      ? { ring: "#b45309", text: "text-amber-700",  bg: "bg-amber-50" }
      : { ring: "#b91c1c", text: "text-red-700",    bg: "bg-red-50" };
  // Conic gradient gives a clean ring without an extra <svg>.
  return (
    <div className="text-center w-16" data-testid={`score-dial-${value > 80 ? "green" : value >= 65 ? "amber" : "red"}`}>
      <div
        className={`w-10 h-10 rounded-full mx-auto flex items-center justify-center ${bg}`}
        style={{
          background: `conic-gradient(${ring} ${value * 3.6}deg, rgba(0,0,0,0.06) 0)`,
        }}
        title={`${value}% — ${value > 80 ? "on track" : value >= 65 ? "at risk" : "off track"}`}
      >
        <div className="w-[30px] h-[30px] rounded-full bg-white flex items-center justify-center">
          <span className={`akki-serif text-[12px] leading-none ${text}`}>{value}</span>
        </div>
      </div>
      <p className="text-[9.5px] uppercase tracking-wider text-[var(--muted)] mt-1">{label}</p>
    </div>
  );
}

function EditGoalRow({ goal, contextId, onCancel, onSaved, isLast }) {
  const [score, setScore] = useState(goal.current_score ?? "");
  const [prob, setProb] = useState(goal.probability ?? "");
  const [currentValue, setCurrentValue] = useState(goal.current_value || "");
  const [status, setStatus] = useState(goal.status || "on_track");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const payload = { status };
      if (score !== "" && !isNaN(parseInt(score))) payload.current_score = parseInt(score);
      if (prob !== "" && !isNaN(parseInt(prob))) payload.probability = parseInt(prob);
      if (currentValue.trim()) payload.current_value = currentValue.trim();
      await api.patch(`/contexts/${contextId}/strategic-goals/${goal.id}`, payload);
      toast.success("Goal updated.");
      onSaved();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className={`px-5 py-4 bg-[var(--cream-deep)]/40 ${!isLast ? "border-b border-[var(--rule)]" : ""}`} data-testid={`goal-edit-row-${goal.id}`}>
      <p className="text-[14.5px] text-[var(--ink)] font-medium mb-3">{goal.title}</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <NumField label="Score (0-100)" value={score} onChange={setScore} testid={`goal-edit-score-${goal.id}`} />
        <NumField label="Probability (0-100)" value={prob} onChange={setProb} testid={`goal-edit-prob-${goal.id}`} />
        <div>
          <label className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] block mb-1">Current value</label>
          <input value={currentValue} onChange={(e) => setCurrentValue(e.target.value)} className="w-full px-2 py-1 border border-[var(--rule)] rounded-sm text-[12.5px]" data-testid={`goal-edit-current-${goal.id}`} />
        </div>
        <div>
          <label className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] block mb-1">Status</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full px-2 py-1 border border-[var(--rule)] rounded-sm text-[12.5px] bg-white" data-testid={`goal-edit-status-${goal.id}`}>
            {Object.entries(STATUS_STYLE).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
          </select>
        </div>
      </div>
      <div className="flex items-center justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel} className="text-[12px] h-7" data-testid={`goal-edit-cancel-${goal.id}`}>Cancel</Button>
        <Button size="sm" onClick={save} disabled={busy} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] h-7" data-testid={`goal-edit-save-${goal.id}`}>
          {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : "Save"}
        </Button>
      </div>
    </div>
  );
}

function NumField({ label, value, onChange, testid }) {
  return (
    <div>
      <label className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] block mb-1">{label}</label>
      <input type="number" min={0} max={100} value={value} onChange={(e) => onChange(e.target.value)} className="w-full px-2 py-1 border border-[var(--rule)] rounded-sm text-[12.5px]" data-testid={testid} />
    </div>
  );
}

function EmptyState({ contextId, onExtractOpen, modalOpen, onModalClose, onChange, fn, isNED }) {
  return (
    <section data-testid="strategic-goals-empty">
      <div className="bg-gradient-to-br from-white to-[var(--cream-deep)] border border-[var(--accent)]/20 rounded-md p-8 relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Target className="w-3 h-3 text-[var(--accent)]" /> Strategic goals
        </p>
        <h2 className="akki-serif text-[22px] text-[var(--ink)] leading-snug mb-3 max-w-2xl">
          {isNED
            ? "No strategic goals are being tracked yet."
            : "Upload your strategic plan. AKKI will surface the board-level goals tied to your function."}
        </h2>
        <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-6 max-w-2xl">
          Each goal becomes a row with a target, a current score, and a probability. {isNED
            ? "Once your executive team uploads the strategy document, the scorecard will populate here."
            : "Update the score weekly. Update the probability when assumptions change. The board will read the same view."}
        </p>
        {!isNED && (
          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={onExtractOpen} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white" data-testid="strategic-goals-empty-cta">
              <Sparkles className="w-3.5 h-3.5 mr-2" /> Read goals from a document
            </Button>
            <Link to="/app/workspace" className="text-[13px] text-[var(--accent)] hover:underline inline-flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" /> Upload a strategy doc first
            </Link>
          </div>
        )}
      </div>
      {modalOpen && (
        <ExtractFromDocModal
          contextId={contextId}
          onClose={onModalClose}
          onExtracted={() => { onModalClose(); onChange?.(); }}
        />
      )}
    </section>
  );
}

function ExtractFromDocModal({ contextId, onClose, onExtracted }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pickedId, setPickedId] = useState("");
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/documents`);
        setDocs(data || []);
      } catch (e) { toast.error(apiErrorMessage(e)); }
      finally { setLoading(false); }
    })();
  }, [contextId]);

  const submit = async () => {
    if (!pickedId) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/strategic-goals/extract`, {
        doc_id: pickedId, replace_existing: replace,
      }, { timeout: 90000 });
      if (!data.count) {
        toast.message("AKKI couldn't find board-level goals in that document. Try a strategic plan, three-year roadmap, or a board OKR pack.");
        setBusy(false);
        return;
      }
      toast.success(`AKKI surfaced ${data.count} goal${data.count === 1 ? "" : "s"} from the strategy.`);
      onExtracted();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-md shadow-xl border border-[var(--rule)] w-full max-w-lg mx-4 p-6" onClick={(e) => e.stopPropagation()} data-testid="goals-extract-modal">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Strategic goals</p>
            <h2 className="akki-serif text-[18px] text-[var(--ink)]">Read the goals from your strategy.</h2>
          </div>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--ink)]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-[12.5px] text-[var(--muted)] italic mb-4 leading-relaxed">
          Pick the strategic plan, board pack, or three-year roadmap. AKKI extracts measurable goals tied to deadlines, assigns them to a function, and seeds the tracker. You can edit each goal afterwards.
        </p>

        <div className="mb-4">
          <label className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] block mb-2">Strategy document</label>
          {loading ? (
            <p className="text-[12px] text-[var(--muted)]">Loading documents…</p>
          ) : docs.length === 0 ? (
            <p className="text-[12.5px] text-[var(--muted)] italic">
              No documents on this context yet. <Link to="/app/workspace" className="text-[var(--accent)] hover:underline">Upload one →</Link>
            </p>
          ) : (
            <div className="border border-[var(--rule)] rounded-sm max-h-60 overflow-y-auto">
              {docs.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setPickedId(d.id)}
                  className={`w-full text-left px-3 py-2 border-b border-[var(--rule)] last:border-b-0 hover:bg-[var(--cream-deep)]/40 ${pickedId === d.id ? "bg-[var(--cream-deep)] border-l-2 border-l-[var(--accent)]" : ""}`}
                  data-testid={`goals-extract-doc-${d.id}`}
                >
                  <p className="text-[13px] text-[var(--ink)] truncate">{d.name}</p>
                  <p className="text-[10.5px] text-[var(--muted)]">{(d.extracted_chars / 1000).toFixed(1)}k chars</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <label className="flex items-center gap-2 text-[12.5px] text-[var(--deep)] mb-4">
          <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} data-testid="goals-extract-replace" />
          Replace existing goals (otherwise new goals are added alongside)
        </label>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} className="text-[12px] h-8">Cancel</Button>
          <Button onClick={submit} disabled={busy || !pickedId} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] h-8" data-testid="goals-extract-submit">
            {busy ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Reading…</> : <><Sparkles className="w-3 h-3 mr-1.5" /> Extract goals</>}
          </Button>
        </div>
      </div>
    </div>
  );
}
