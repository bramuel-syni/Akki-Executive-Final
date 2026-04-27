/**
 * Prepare — combined Signals + Brief at /app/prepare with line tabs.
 *
 * Per Apr-2026 user feedback:
 *   "Combine Signal and Briefing into one section. Use line tabs to
 *   separate the two. When loading these pages, do NOT pre-populate
 *   them with data. Prompt the user to generate."
 *
 * Structure:
 *   ┌────────────────────────────────────────────────────────────┐
 *   │ Prepare — short, focused, on-demand                         │
 *   ├────────────────────────────────────────────────────────────┤
 *   │  [ Brief ]    Signals                                       │
 *   │ ──────                                                      │
 *   │                                                              │
 *   │  Brief me on:  ( Claim · Proposal · Topic · Period · Report )│
 *   │  Objective:    [────────────────────────]                    │
 *   │                                  [ Generate brief →]         │
 *   │                                                              │
 *   │  Recent briefs · 3                                           │
 *   │   - Underwriting margin in Q2 — Apr 24                       │
 *   │   - …                                                        │
 *   └────────────────────────────────────────────────────────────┘
 *
 * Signals tab follows the same pattern: filter + objective → generate
 * → save. No pre-population.
 */
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Sparkles, Loader2, ScrollText, Activity, FileText, Clock, Trash2,
  ArrowRight,
} from "lucide-react";

const TABS = [
  { id: "brief",    label: "Brief",    icon: ScrollText,
    blurb: "Quick orientation on a claim, proposal, topic, period or report." },
  { id: "signals",  label: "Signals",  icon: Activity,
    blurb: "What does the board need to notice? Generate, then act." },
];

export default function Prepare() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [tab, setTab] = useState("brief");

  if (!cid) {
    return (
      <AppShell>
        <div className="p-12 text-center text-[var(--muted)] text-sm">
          No context selected. Pick one from the rail to start preparing.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-[920px] mx-auto px-6 py-10">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Prepare · {activeContext.name}
        </p>
        <h1 className="akki-greeting">Prepare for what's next.</h1>
        <p className="akki-meta mt-2 max-w-xl">
          Short, focused, on-demand. Tell AKKI what you want to be ready for, and AKKI drafts it.
        </p>

        {/* Line tabs */}
        <div className="mt-8 mb-6 border-b border-[var(--rule)] flex items-stretch gap-0" data-testid="prepare-line-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-5 py-3 text-[13px] inline-flex items-center gap-2 border-b-2 transition-colors ${
                  active
                    ? "border-[var(--accent)] text-[var(--ink)]"
                    : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
                }`}
                data-testid={`prepare-tab-${t.id}${active ? "-active" : ""}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {t.label}
                <span className="text-[10.5px] uppercase tracking-wider text-[var(--muted)]/70 ml-1 hidden md:inline">
                  · {t.blurb}
                </span>
              </button>
            );
          })}
        </div>

        {tab === "brief"   && <BriefTab   contextId={cid} />}
        {tab === "signals" && <SignalsTab contextId={cid} contextName={activeContext.name} />}
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Brief tab — Brief me on [kind] · objective → generate → save with title.
// ---------------------------------------------------------------------------
function BriefTab({ contextId }) {
  const navigate = useNavigate();
  const [kinds, setKinds] = useState([]);
  const [kind, setKind] = useState("topic");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState([]);
  const [loadingItems, setLoadingItems] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/prepare/brief-kinds`);
        setKinds(data?.kinds || []);
      } catch { /* silent */ }
    })();
  }, []);

  const loadHistory = useCallback(async () => {
    setLoadingItems(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/briefs?limit=20`);
      setItems(data?.items || []);
    } catch { /* silent — empty history is the empty state */ }
    finally { setLoadingItems(false); }
  }, [contextId]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const generate = async (e) => {
    e?.preventDefault?.();
    if (objective.trim().length < 8 || busy) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/briefs`, {
        kind, objective: objective.trim(),
      });
      toast.success("Brief saved.");
      setObjective("");
      navigate(`/app/prepare/brief/${data.id}`);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/contexts/${contextId}/briefs/${id}`);
      setItems((xs) => xs.filter((x) => x.id !== id));
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <div data-testid="prepare-brief-tab">
      <form
        onSubmit={generate}
        className="bg-white border border-[var(--rule)] rounded-md p-5 mb-8"
        data-testid="prepare-brief-form"
      >
        <p className="akki-overline mb-3">Brief me on…</p>
        <div className="flex flex-wrap gap-2 mb-4" data-testid="prepare-brief-kinds">
          {kinds.map((k) => {
            const active = kind === k.id;
            return (
              <button
                key={k.id}
                type="button"
                onClick={() => setKind(k.id)}
                className={`px-3 py-1.5 rounded-md border text-[13px] transition-colors ${
                  active
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                title={k.blurb}
                data-testid={`prepare-brief-kind-${k.id}${active ? "-active" : ""}`}
              >
                {k.label}
              </button>
            );
          })}
        </div>

        <p className="akki-overline mb-2">My objective</p>
        <Textarea
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder="What do you want to be quickly oriented on? Be specific — e.g., 'Walk me through the underwriting margin question for Q2 in two paragraphs.'"
          rows={3}
          maxLength={600}
          className="bg-[var(--cream-deep)]/30 rounded-md text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] resize-none mb-3"
          data-testid="prepare-brief-objective"
        />
        <div className="flex items-center justify-between gap-3">
          <ValidatedBadge size="compact" />
          <Button
            type="submit"
            disabled={objective.trim().length < 8 || busy}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 px-5 text-[13px]"
            data-testid="prepare-brief-generate"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
            {busy ? "Drafting…" : "Generate brief"} {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
          </Button>
        </div>
      </form>

      <SavedHistory
        items={items}
        loading={loadingItems}
        emptyText="Nothing yet. Generate your first brief above — it'll appear here for next time."
        labelTotal="briefs"
        onOpen={(it) => navigate(`/app/prepare/brief/${it.id}`)}
        onRemove={remove}
        testId="prepare-brief-history"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signals tab — filter + objective → generate. Reuses the existing
// /signals/generate endpoint; saves via the existing signals collection.
// We just don't pre-load the stream — user comes here with intent.
// ---------------------------------------------------------------------------
const SIGNAL_FILTERS = [
  { id: "general",  label: "Anything I should know" },
  { id: "period",   label: "A specific period" },
  { id: "cycle",    label: "A cycle (Q2 2026, etc.)" },
  { id: "report",   label: "A specific report" },
  { id: "risk",     label: "Risks the board should notice" },
];

function SignalsTab({ contextId, contextName }) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState("general");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState([]);
  const [loadingRecent, setLoadingRecent] = useState(true);

  // We load recent signals — but only as a HISTORY rail (not stream). The
  // primary action is "Generate signals based on what you want to look at".
  const loadHistory = useCallback(async () => {
    setLoadingRecent(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/signals?limit=20`);
      setRecent(Array.isArray(data) ? data : (data?.signals || []));
    } catch { /* silent */ }
    finally { setLoadingRecent(false); }
  }, [contextId]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const generate = async (e) => {
    e?.preventDefault?.();
    if (objective.trim().length < 4 || busy) return;
    setBusy(true);
    try {
      const filterLabel = SIGNAL_FILTERS.find((f) => f.id === filter)?.label || filter;
      const focus = `[${filterLabel}] ${objective.trim()}`;
      await api.post(`/contexts/${contextId}/signals/generate`, { focus });
      toast.success("Signals surfaced.");
      setObjective("");
      navigate(`/app/highlights`);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <div data-testid="prepare-signals-tab">
      <form
        onSubmit={generate}
        className="bg-white border border-[var(--rule)] rounded-md p-5 mb-8"
        data-testid="prepare-signals-form"
      >
        <p className="akki-overline mb-3">Surface signals on…</p>
        <div className="flex flex-wrap gap-2 mb-4" data-testid="prepare-signals-filters">
          {SIGNAL_FILTERS.map((f) => {
            const active = filter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={`px-3 py-1.5 rounded-md border text-[13px] transition-colors ${
                  active
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`prepare-signals-filter-${f.id}${active ? "-active" : ""}`}
              >
                {f.label}
              </button>
            );
          })}
        </div>

        <p className="akki-overline mb-2">My focus</p>
        <Input
          value={objective}
          onChange={(e) => setObjective(e.target.value)}
          placeholder={`What in ${contextName} are we looking at? e.g. "Loss ratio drift in marine business."`}
          maxLength={400}
          className="bg-[var(--cream-deep)]/30 h-11 text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] mb-3"
          data-testid="prepare-signals-objective"
        />
        <div className="flex items-center justify-between gap-3">
          <ValidatedBadge size="compact" />
          <Button
            type="submit"
            disabled={objective.trim().length < 4 || busy}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 px-5 text-[13px]"
            data-testid="prepare-signals-generate"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
            {busy ? "Reading…" : "Surface signals"} {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
          </Button>
        </div>
      </form>

      <SavedHistory
        items={recent.map((s) => ({
          id: s.id,
          title: s.headline || s.title,
          kind: s.type || s.tone,
          created_at: s.created_at,
        }))}
        loading={loadingRecent}
        emptyText="No signals yet. Tell AKKI what to look at and they'll appear here."
        labelTotal="signals"
        onOpen={() => navigate(`/app/highlights`)}
        testId="prepare-signals-history"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// SavedHistory — shared list block under both tabs.
// ---------------------------------------------------------------------------
function SavedHistory({ items, loading, emptyText, labelTotal, onOpen, onRemove, testId }) {
  return (
    <section data-testid={testId}>
      <p className="akki-overline mb-3 flex items-center gap-2">
        <Clock className="w-3 h-3 text-[var(--accent)]" />
        Recent {labelTotal} · {loading ? "…" : items.length}
      </p>
      <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden">
        {loading ? (
          <p className="px-5 py-6 text-center text-[12.5px] text-[var(--muted)] italic">
            Loading…
          </p>
        ) : items.length === 0 ? (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)] italic">
            {emptyText}
          </p>
        ) : (
          items.map((it) => (
            <div
              key={it.id}
              className="border-b border-[var(--rule)] last:border-b-0 px-5 py-3 flex items-center gap-3 hover:bg-[var(--cream-deep)]/30 cursor-pointer"
              onClick={() => onOpen?.(it)}
              data-testid={`prepare-history-item-${it.id}`}
            >
              <FileText className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="akki-serif text-[14px] text-[var(--ink)] truncate">{it.title}</p>
                <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mt-0.5">
                  {it.kind} {it.created_at && `· ${new Date(it.created_at).toLocaleDateString()}`}
                </p>
              </div>
              {onRemove && (
                <button
                  onClick={(e) => { e.stopPropagation(); onRemove(it.id); }}
                  className="text-[var(--muted)] hover:text-red-700 shrink-0"
                  aria-label="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
