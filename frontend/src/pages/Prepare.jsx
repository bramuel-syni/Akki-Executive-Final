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
import AppShell from "@/components/layout/AppShell";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import ShareModal from "@/components/share/ShareModal";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Sparkles, Loader2, ScrollText, Activity, FileText, Clock, Trash2,
  ArrowRight,
} from "lucide-react";

const TABS = [
  { id: "brief",    label: "Brief",    icon: ScrollText },
  { id: "signals",  label: "Signals",  icon: Activity },
];

const TAB_INTRO = {
  brief: {
    kicker: "Generate Brief",
    blurb:
      "A short orientation on a claim, proposal, topic, period or report. " +
      "Around 250–400 words, saved here for next time.",
  },
  signals: {
    kicker: "Generate Signals",
    blurb:
      "What the board needs to notice — risks, opportunities, gaps. " +
      "Generated on demand against a focus you choose.",
  },
};

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

        {/* Line tabs — labels only. Description moves below into a section
            header so it has room to breathe. */}
        <div className="mt-8 border-b border-[var(--rule)] flex items-stretch gap-0" data-testid="prepare-line-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-5 py-3 text-[13.5px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
                  active
                    ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                    : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
                }`}
                data-testid={`prepare-tab-${t.id}${active ? "-active" : ""}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Section header for the active tab — the description lives here,
            with room to read, instead of being squeezed into the tab label. */}
        <div className="mt-8 mb-5" data-testid={`prepare-section-${tab}`}>
          <p className="akki-overline mb-1.5">{TAB_INTRO[tab].kicker}</p>
          <p className="akki-serif text-[15.5px] text-[var(--ink)] leading-[1.55] max-w-2xl">
            {TAB_INTRO[tab].blurb}
          </p>
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
  const [kinds, setKinds] = useState([]);
  const [kind, setKind] = useState("topic");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState([]);
  const [loadingItems, setLoadingItems] = useState(true);
  const [openBrief, setOpenBrief] = useState(null);

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
      setOpenBrief(data);
      loadHistory();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const openItem = async (it) => {
    try {
      const { data } = await api.get(`/contexts/${contextId}/briefs/${it.id}`);
      setOpenBrief(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
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
        className="bg-white border border-[var(--rule)] rounded-md overflow-hidden mb-10"
        data-testid="prepare-brief-form"
      >
        {/* INPUT — kind picker. */}
        <div className="px-6 pt-5 pb-4 border-b border-[var(--rule)]/60">
          <p className="akki-overline mb-3">Step 1 · Pick a kind</p>
          <div className="flex flex-wrap gap-2" data-testid="prepare-brief-kinds">
            {kinds.map((k) => {
              const active = kind === k.id;
              return (
                <button
                  key={k.id}
                  type="button"
                  onClick={() => setKind(k.id)}
                  className={`px-3.5 py-1.5 rounded-full border text-[13px] transition-colors ${
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
          {kinds.find((k) => k.id === kind)?.blurb && (
            <p className="text-[12.5px] text-[var(--muted)] italic mt-3">
              {kinds.find((k) => k.id === kind).blurb}
            </p>
          )}
        </div>

        {/* INPUT — objective. */}
        <div className="px-6 pt-5 pb-4">
          <p className="akki-overline mb-2">Step 2 · Your objective</p>
          <Textarea
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="What do you want to be oriented on? e.g., 'Walk me through the underwriting margin question for Q2 in two paragraphs.'"
            rows={3}
            maxLength={600}
            className="bg-[var(--cream-deep)]/30 rounded-md text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)] resize-none"
            data-testid="prepare-brief-objective"
          />
          <div className="flex items-center justify-between mt-1.5">
            <p className="text-[11px] text-[var(--muted)] tabular-nums">
              {objective.trim().length} / 600
            </p>
            <p className="text-[11px] text-[var(--muted)] italic">
              {objective.trim().length < 8 ? "Tell AKKI a little more — at least 8 characters." : " "}
            </p>
          </div>
        </div>

        {/* ACTION — validated badge + submit. */}
        <div className="px-6 py-4 bg-[var(--cream-deep)]/30 border-t border-[var(--rule)]/60 flex items-center justify-between gap-3">
          <ValidatedBadge size="compact" />
          <Button
            type="submit"
            disabled={objective.trim().length < 8 || busy}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 px-5 text-[13px]"
            data-testid="prepare-brief-generate"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
            {busy ? "Drafting…" : "Generate Brief"} {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
          </Button>
        </div>
      </form>

      <SavedHistory
        items={items}
        loading={loadingItems}
        emptyText="Nothing yet. Generate your first brief above — it will appear here for next time."
        labelTotal="briefs"
        onOpen={openItem}
        onRemove={remove}
        testId="prepare-brief-history"
      />

      <BriefDetailModal
        brief={openBrief}
        contextId={contextId}
        onClose={() => setOpenBrief(null)}
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
      loadHistory();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const [openSignal, setOpenSignal] = useState(null);

  return (
    <div data-testid="prepare-signals-tab">
      <form
        onSubmit={generate}
        className="bg-white border border-[var(--rule)] rounded-md overflow-hidden mb-10"
        data-testid="prepare-signals-form"
      >
        {/* INPUT — filter. */}
        <div className="px-6 pt-5 pb-4 border-b border-[var(--rule)]/60">
          <p className="akki-overline mb-3">Step 1 · Pick a focus area</p>
          <div className="flex flex-wrap gap-2" data-testid="prepare-signals-filters">
            {SIGNAL_FILTERS.map((f) => {
              const active = filter === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFilter(f.id)}
                  className={`px-3.5 py-1.5 rounded-full border text-[13px] transition-colors ${
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
        </div>

        {/* INPUT — focus query. */}
        <div className="px-6 pt-5 pb-4">
          <p className="akki-overline mb-2">Step 2 · Your focus</p>
          <Input
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder={`What in ${contextName} are we looking at? e.g. "Loss ratio drift in marine business."`}
            maxLength={400}
            className="bg-[var(--cream-deep)]/30 h-11 text-[14px] text-[var(--ink)] placeholder:text-[var(--muted)] border-[var(--rule)] focus:border-[var(--accent)]"
            data-testid="prepare-signals-objective"
          />
          <p className="text-[11px] text-[var(--muted)] tabular-nums mt-1.5">
            {objective.trim().length} / 400
          </p>
        </div>

        {/* ACTION — validated badge + submit. */}
        <div className="px-6 py-4 bg-[var(--cream-deep)]/30 border-t border-[var(--rule)]/60 flex items-center justify-between gap-3">
          <ValidatedBadge size="compact" />
          <Button
            type="submit"
            disabled={objective.trim().length < 4 || busy}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 px-5 text-[13px]"
            data-testid="prepare-signals-generate"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
            {busy ? "Reading…" : "Generate Signals"} {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
          </Button>
        </div>
      </form>

      <SavedHistory
        items={recent.map((s) => ({
          id: s.id,
          title: s.headline || s.title,
          kind: s.type || s.tone,
          created_at: s.created_at,
          _raw: s,
        }))}
        loading={loadingRecent}
        emptyText="No signals yet. Tell AKKI what to look at and they will appear here."
        labelTotal="signals"
        onOpen={(it) => setOpenSignal(it._raw)}
        testId="prepare-signals-history"
      />

      <SignalDetailModal signal={openSignal} onClose={() => setOpenSignal(null)} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// SavedHistory — shared list block under both tabs.
// ---------------------------------------------------------------------------
function SavedHistory({ items, loading, emptyText, labelTotal, onOpen, onRemove, testId }) {
  return (
    <section data-testid={testId}>
      <div className="flex items-baseline justify-between mb-3 pb-2 border-b border-[var(--rule)]">
        <p className="akki-overline flex items-center gap-2">
          <Clock className="w-3 h-3 text-[var(--accent)]" />
          Recent {labelTotal}
        </p>
        <p className="text-[11px] text-[var(--muted)] tabular-nums">
          {loading ? "—" : `${items.length} saved`}
        </p>
      </div>
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

// ---------------------------------------------------------------------------
// BriefDetailModal — read the saved brief in place. Markdown rendered as
// pre-wrap text (calm, editorial) so we don't pull in another dependency.
// ---------------------------------------------------------------------------
function BriefDetailModal({ brief, contextId, onClose }) {
  const open = Boolean(brief);
  const [shareOpen, setShareOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose?.(); }}>
      <DialogContent className="max-w-2xl bg-[var(--cream)]" data-testid="prepare-brief-detail">
        <DialogHeader>
          <p className="akki-overline mb-1">
            Brief · {brief?.kind} · {brief?.created_at ? new Date(brief.created_at).toLocaleString() : ""}
          </p>
          <DialogTitle className="akki-serif text-[22px] leading-snug text-[var(--ink)]">
            {brief?.title}
          </DialogTitle>
          <DialogDescription className="text-[12px] italic text-[var(--muted)]">
            {brief?.objective}
          </DialogDescription>
        </DialogHeader>
        <div className="mt-2 flex items-center justify-between gap-3">
          <ValidatedBadge size="compact" />
          {brief?.id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShareOpen(true)}
              className="h-8 text-[12.5px] border-[var(--rule)] hover:border-[var(--accent)] text-[var(--ink)]"
              data-testid="prepare-brief-share"
            >
              Send to a colleague
            </Button>
          )}
        </div>
        <div className="mt-3 max-h-[60vh] overflow-y-auto akki-serif text-[15px] leading-[1.7] text-[var(--ink)] whitespace-pre-wrap">
          {brief?.body}
        </div>

        {brief?.id && contextId && (
          <ShareModal
            open={shareOpen}
            onClose={() => setShareOpen(false)}
            contextId={contextId}
            itemType="brief"
            item={brief}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// SignalDetailModal — quick read-in-place for a generated signal. We don't
// re-implement Act / Share here; the signal lives in the existing collection
// and any deep workflow continues from there.
// ---------------------------------------------------------------------------
function SignalDetailModal({ signal, onClose }) {
  const open = Boolean(signal);
  if (!signal) return null;
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose?.(); }}>
      <DialogContent className="max-w-2xl bg-[var(--cream)]" data-testid="prepare-signal-detail">
        <DialogHeader>
          <p className="akki-overline mb-1">
            Signal · {signal.type || signal.tone} · {signal.created_at ? new Date(signal.created_at).toLocaleDateString() : ""}
          </p>
          <DialogTitle className="akki-serif text-[20px] leading-snug text-[var(--ink)]">
            {signal.headline || signal.title}
          </DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <ValidatedBadge size="compact" />
        </div>
        {signal.summary && (
          <p className="mt-3 akki-serif text-[15px] leading-[1.7] text-[var(--ink)]">
            {signal.summary}
          </p>
        )}
        {Array.isArray(signal.evidence) && signal.evidence.length > 0 && (
          <div className="mt-4">
            <p className="akki-overline mb-2">Evidence</p>
            <ul className="text-[13px] text-[var(--ink)] space-y-1.5 list-disc pl-5">
              {signal.evidence.slice(0, 5).map((e, i) => (
                <li key={i}>{typeof e === "string" ? e : (e.text || e.quote || JSON.stringify(e))}</li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
