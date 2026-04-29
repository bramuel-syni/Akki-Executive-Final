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
import PrepareStatsDock from "@/components/prepare/PrepareStatsDock";
import PrepareSideRail from "@/components/prepare/PrepareSideRail";
import WalkInCard from "@/components/walkin/WalkInCard";
import HighlightsStats from "@/components/highlights/HighlightsStats";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Sparkles, Loader2, ScrollText, Activity, FileText, ArrowRight,
} from "lucide-react";

const TABS = [
  { id: "brief",    label: "Brief",    icon: ScrollText },
  { id: "signals",  label: "Signals",  icon: Activity },
  { id: "minutes",  label: "Minutes",  icon: FileText },
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
  minutes: {
    kicker: "Meeting Minutes",
    blurb:
      "Past meeting minutes uploaded to this company. AKKI lists them here " +
      "so you can read in, recall decisions, and spot open actions. " +
      "(Structured extraction — participants, decisions, actions — is on the way.)",
  },
};

export default function Prepare() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  // Honour ?tab=signals deep-link so the Quick Actions "Surface signals
  // on something" tile lands on the Signals tab instead of Brief.
  const initialTab = (() => {
    if (typeof window === "undefined") return "brief";
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t === "signals" || t === "minutes" || t === "brief") return t;
    return "brief";
  })();
  const [tab, setTab] = useState(initialTab);

  // Shared rail data — hoisted so the right rail can refresh after a
  // generate happens inside a tab.
  const [briefs, setBriefs] = useState([]);
  const [signals, setSignals] = useState([]);
  const [minutes, setMinutes] = useState([]);
  const [loadingBriefs, setLoadingBriefs] = useState(true);
  const [loadingSignals, setLoadingSignals] = useState(true);
  const [loadingMinutes, setLoadingMinutes] = useState(true);
  const [openBrief, setOpenBrief] = useState(null);
  const [openSignal, setOpenSignal] = useState(null);

  const loadBriefs = useCallback(async () => {
    if (!cid) return;
    setLoadingBriefs(true);
    try {
      const { data } = await api.get(`/contexts/${cid}/briefs?limit=50`);
      setBriefs(data?.items || []);
    } catch { /* silent */ }
    finally { setLoadingBriefs(false); }
  }, [cid]);

  const loadSignals = useCallback(async () => {
    if (!cid) return;
    setLoadingSignals(true);
    try {
      const { data } = await api.get(`/contexts/${cid}/signals`);
      setSignals(Array.isArray(data) ? data : (data?.signals || []));
    } catch { /* silent */ }
    finally { setLoadingSignals(false); }
  }, [cid]);

  const loadMinutes = useCallback(async () => {
    if (!cid) return;
    setLoadingMinutes(true);
    try {
      const { data } = await api.get(`/contexts/${cid}/minutes?limit=50`);
      setMinutes(data?.items || []);
    } catch { /* silent */ }
    finally { setLoadingMinutes(false); }
  }, [cid]);

  useEffect(() => { loadBriefs(); loadSignals(); loadMinutes(); }, [loadBriefs, loadSignals, loadMinutes]);

  // Iter66 — hash anchor handler: /app/prepare#brief-{id} (set by Studio
  // history strip when user clicks a briefing row) auto-switches to the
  // Brief tab and opens the briefing in its modal.
  useEffect(() => {
    if (typeof window === "undefined" || !cid) return;
    const hash = window.location.hash || "";
    const m = hash.match(/^#brief-([\w-]+)$/);
    if (!m) return;
    const briefId = m[1];
    setTab("brief");
    openBriefById(briefId);
    // Strip the hash so reloads don't re-trigger the modal.
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }, [cid, openBriefById]);

  const openBriefById = useCallback(async (idOrItem) => {
    const id = typeof idOrItem === "string" ? idOrItem : idOrItem?.id;
    if (!id || !cid) return;
    try {
      const { data } = await api.get(`/contexts/${cid}/briefs/${id}`);
      setOpenBrief(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  }, [cid]);

  const removeBrief = useCallback(async (id) => {
    try {
      await api.delete(`/contexts/${cid}/briefs/${id}`);
      setBriefs((xs) => xs.filter((x) => x.id !== id));
    } catch (e) { toast.error(apiErrorMessage(e)); }
  }, [cid]);

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
      <div className="max-w-[1280px] mx-auto px-6 py-10">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Catch-up · {activeContext.name}
        </p>
        <h1 className="akki-greeting">Catch up on what's next.</h1>
        <p className="akki-meta mt-2 max-w-xl">
          Short, focused, on-demand. Tell AKKI what you want to be ready for, and AKKI drafts it.
        </p>

        {/* Stats dock — Signals tab gets the richer signal-specific
            HighlightsStats (sparkline + breakdown bars + confidence
            footer); Brief tab keeps the calmer three-card progress dock.
            Apr-2026: brought back the standalone-Signals visual the user
            asked for. */}
        {tab === "signals" && signals.length > 0 ? (
          <div className="mt-6">
            <HighlightsStats signals={signals} />
          </div>
        ) : (
          <PrepareStatsDock contextId={cid} />
        )}

        {/* 2-column layout: form column (left) + history side rail (right) */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-8">
          <div className="min-w-0">
            {/* Line tabs — labels only. Description moves below into a section
                header so it has room to breathe. */}
            <div className="border-b border-[var(--rule)] flex items-stretch gap-0" data-testid="prepare-line-tabs">
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

            {/* Section header for the active tab */}
            <div className="mt-8 mb-5" data-testid={`prepare-section-${tab}`}>
              <p className="akki-overline mb-1.5">{TAB_INTRO[tab].kicker}</p>
              <p className="akki-serif text-[15.5px] text-[var(--ink)] leading-[1.55] max-w-2xl">
                {TAB_INTRO[tab].blurb}
              </p>
            </div>

            {tab === "brief" && (
              <BriefTab
                contextId={cid}
                onCreated={(b) => { setOpenBrief(b); loadBriefs(); }}
              />
            )}
            {tab === "signals" && (
              <SignalsTab
                contextId={cid}
                contextName={activeContext.name}
                onCreated={() => loadSignals()}
              />
            )}
            {tab === "minutes" && (
              <MinutesTab
                minutes={minutes}
                loading={loadingMinutes}
                contextId={cid}
                onRefresh={loadMinutes}
              />
            )}
          </div>

          <PrepareSideRail
            tab={tab}
            briefs={briefs}
            signals={signals}
            minutes={minutes}
            loadingBriefs={loadingBriefs}
            loadingSignals={loadingSignals}
            loadingMinutes={loadingMinutes}
            onOpenBrief={openBriefById}
            onOpenSignal={(s) => setOpenSignal(s)}
          />
        </div>

        <BriefDetailModal
          brief={openBrief}
          contextId={cid}
          onClose={() => setOpenBrief(null)}
          onDelete={removeBrief}
        />
        <SignalDetailModal signal={openSignal} onClose={() => setOpenSignal(null)} />
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Brief tab — Brief me on [kind] · objective → generate → save with title.
// Self-fetched history was lifted to the page level; this tab now owns
// just the form + onCreated callback to its parent.
// ---------------------------------------------------------------------------
function BriefTab({ contextId, onCreated }) {
  const [kinds, setKinds] = useState([]);
  const [kind, setKind] = useState("topic");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [deep, setDeep] = useState(false);
  const [briefQuota, setBriefQuota] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/prepare/brief-kinds`);
        setKinds(data?.kinds || []);
      } catch { /* silent */ }
      try {
        const { data } = await api.get(`/llm/quota?surface=brief`);
        setBriefQuota(data);
      } catch { /* silent */ }
    })();
  }, []);

  const generate = async (e) => {
    e?.preventDefault?.();
    if (objective.trim().length < 8 || busy) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/briefs`, {
        kind, objective: objective.trim(), deep,
      });
      if (data?.quota?.downgraded) {
        toast.info("Deep capacity is full for today — drafted with the standard model.");
      } else {
        toast.success(deep ? "Deep brief saved." : "Brief saved.");
      }
      if (data?.quota) {
        setBriefQuota({
          surface: "brief",
          used: data.quota.used ?? briefQuota?.used,
          limit: data.quota.limit ?? briefQuota?.limit,
          remaining: data.quota.remaining ?? briefQuota?.remaining,
          reset_at: data.quota.reset_at ?? briefQuota?.reset_at,
        });
      }
      setObjective("");
      onCreated?.(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
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

        {/* ACTION — validated badge + deep toggle + submit. */}
        <div className="px-6 py-4 bg-[var(--cream-deep)]/30 border-t border-[var(--rule)]/60 flex items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <ValidatedBadge size="compact" />
            <label
              className="flex items-center gap-2 cursor-pointer select-none"
              data-testid="prepare-brief-deep-toggle"
              title={
                briefQuota
                  ? `Deep mode uses Claude Opus for richer narrative. ${briefQuota.remaining}/${briefQuota.limit} deep briefs remaining today.`
                  : "Deep mode uses Claude Opus for richer narrative."
              }
            >
              <input
                type="checkbox"
                checked={deep}
                onChange={(e) => setDeep(e.target.checked)}
                disabled={busy || (briefQuota && briefQuota.remaining === 0)}
                className="accent-[var(--accent)] w-3.5 h-3.5"
                data-testid="prepare-brief-deep-checkbox"
              />
              <span className="text-[12px] tracking-[0.06em] text-[var(--deep)]">
                Deep mode
              </span>
              {briefQuota && (
                <span
                  className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] tabular-nums"
                  data-testid="prepare-brief-deep-quota"
                >
                  {briefQuota.remaining}/{briefQuota.limit} today
                </span>
              )}
            </label>
          </div>
          <Button
            type="submit"
            disabled={objective.trim().length < 8 || busy}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-10 px-5 text-[13px]"
            data-testid="prepare-brief-generate"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
            {busy ? "Drafting…" : (deep ? "Generate Deep Brief" : "Generate Brief")} {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
          </Button>
        </div>
      </form>
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

function SignalsTab({ contextId, contextName, onCreated }) {
  const [filter, setFilter] = useState("general");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);

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
      onCreated?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

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
    </div>
  );
}

// ---------------------------------------------------------------------------
// MinutesTab — listing v1. Surfaces past meeting minutes uploaded to this
// company. Click a row to open the source document. Structured extraction
// (participants, decisions, actions) lands in a follow-up session.
// ---------------------------------------------------------------------------
function MinutesTab({ minutes, loading, contextId, onRefresh }) {
  const [busy, setBusy] = useState(null);
  const [open, setOpen] = useState({}); // doc_id -> bool

  const extractOne = async (docId) => {
    setBusy(docId);
    try {
      await api.post(`/contexts/${contextId}/minutes/${docId}/extract`);
      toast.success("Minutes extracted");
      await onRefresh?.();
      setOpen((s) => ({ ...s, [docId]: true }));
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="px-5 py-10 text-center text-[12.5px] text-[var(--muted)] italic" data-testid="prepare-minutes-tab">
        Loading meeting minutes…
      </div>
    );
  }
  if (!minutes || minutes.length === 0) {
    return (
      <div
        className="bg-white border border-[var(--rule)] rounded-md px-6 py-10 text-center"
        data-testid="prepare-minutes-tab"
      >
        <FileText className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" strokeWidth={1.5} />
        <p className="akki-serif text-[15px] text-[var(--ink)] mb-1.5">
          No meeting minutes yet.
        </p>
        <p className="text-[12.5px] text-[var(--muted)] italic max-w-sm mx-auto leading-snug">
          Upload a minutes document in the Document Journal — name it
          something with "minutes" in it and AKKI will list it here for
          quick recall before your next meeting.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden" data-testid="prepare-minutes-tab">
      <ul className="divide-y divide-[var(--rule)]">
        {minutes.map((m) => {
          const meta = m.minutes_meta;
          const isOpen = !!open[m.id];
          return (
            <li key={m.id}>
              <div
                className="flex items-start gap-3 px-5 py-3.5 hover:bg-[var(--cream-deep)]/30 transition-colors"
                data-testid={`prepare-minutes-item-${m.id}`}
              >
                <FileText className="w-3.5 h-3.5 mt-0.5 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
                <div className="flex-1 min-w-0">
                  <a
                    href={`/app/documents/${m.id}`}
                    className="akki-serif text-[14.5px] text-[var(--ink)] leading-snug truncate hover:text-[var(--accent)] transition-colors block"
                  >
                    {m.title}
                  </a>
                  <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mt-0.5">
                    {m.created_at ? new Date(m.created_at).toLocaleDateString() : "—"}
                    {m.trust_level && ` · ${m.trust_level}`}
                    {meta?.meeting_date && ` · ${meta.meeting_date}`}
                  </p>
                </div>
                {meta ? (
                  <button
                    type="button"
                    onClick={() => setOpen((s) => ({ ...s, [m.id]: !isOpen }))}
                    className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] hover:text-[var(--accent)] px-2 py-1"
                    data-testid={`prepare-minutes-toggle-${m.id}`}
                  >
                    {isOpen ? "Hide" : "Show"} extract
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy === m.id}
                    onClick={() => extractOne(m.id)}
                    className="text-[11px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline px-2 py-1 disabled:opacity-50"
                    data-testid={`prepare-minutes-extract-${m.id}`}
                  >
                    {busy === m.id ? "Extracting…" : "Extract"}
                  </button>
                )}
              </div>
              {meta && isOpen && (
                <MinutesExtractDetail
                  meta={meta}
                  narrative={m.minutes_narrative}
                  docId={m.id}
                  contextId={contextId}
                  onMutated={onRefresh}
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function MinutesExtractDetail({ meta, narrative: narrativeProp, docId, contextId, onMutated }) {
  const [busy, setBusy] = useState(null);
  const [narrative, setNarrative] = useState(narrativeProp || null);
  const [cycleResult, setCycleResult] = useState(null);

  const toCycle = async () => {
    setBusy("cycle");
    try {
      const { data } = await api.post(`/contexts/${contextId}/minutes/${docId}/to_cycle`);
      setCycleResult(data);
      const total = (data.seeded?.length || 0) + (data.unmatched?.length || 0);
      if (total === 0) {
        toast.info("All actions already in the Question Bank.");
      } else {
        toast.success(`${total} action${total === 1 ? "" : "s"} added to the Question Bank.`);
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const writeNarrative = async () => {
    if (narrative && !window.confirm("This replaces the existing narrative summary. Continue?")) {
      return;
    }
    setBusy("narrative");
    try {
      const { data } = await api.post(`/contexts/${contextId}/minutes/${docId}/narrative`);
      setNarrative(data?.narrative || null);
      if (data?.quota?.downgraded) {
        toast.info("Deep capacity full — used the standard model.");
      } else {
        toast.success("Narrative drafted.");
      }
      onMutated?.();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      className="px-5 pb-5 pl-12 bg-[var(--cream)]/40"
      data-testid={`prepare-minutes-detail-${docId}`}
    >
      <div className="grid md:grid-cols-2 gap-x-8 gap-y-4">
        <ExtractList label="Attendees" items={meta.attendees} />
        <ExtractList label="Decisions" items={meta.decisions} />
        <ExtractList
          label="Actions"
          items={(meta.actions || []).map((a) =>
            `${a.who ? `${a.who}: ` : ""}${a.what}${a.when ? ` (by ${a.when})` : ""}`
          )}
        />
        <ExtractList label="Open questions" items={meta.questions} />
      </div>

      {(meta.actions || []).length > 0 && (
        <div className="mt-5 pt-4 border-t border-[var(--rule)]/60 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy === "cycle"}
            onClick={toCycle}
            className="text-[11.5px] uppercase tracking-[0.14em] px-3 py-1.5 rounded-sm border border-[var(--accent)] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-white transition-colors disabled:opacity-50"
            data-testid={`prepare-minutes-to-cycle-${docId}`}
          >
            {busy === "cycle" ? "Adding…" : "Turn into checklist →"}
          </button>
          <button
            type="button"
            disabled={busy === "narrative"}
            onClick={writeNarrative}
            className="text-[11.5px] uppercase tracking-[0.14em] px-3 py-1.5 rounded-sm border border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors disabled:opacity-50"
            data-testid={`prepare-minutes-narrative-${docId}`}
          >
            {busy === "narrative" ? "Drafting…" : (narrative ? "Re-draft narrative" : "Draft narrative summary")}
          </button>
          {cycleResult && (
            <span
              className="text-[11px] text-[var(--muted)]"
              data-testid={`prepare-minutes-cycle-result-${docId}`}
            >
              {cycleResult.seeded.length} matched · {cycleResult.unmatched.length} unassigned ·{" "}
              <a href={cycleResult.next} className="text-[var(--accent)] hover:underline">
                Continue to Cycle →
              </a>
            </span>
          )}
        </div>
      )}

      {narrative && (
        <div
          className="mt-5 pt-4 border-t border-[var(--rule)]/60"
          data-testid={`prepare-minutes-narrative-body-${docId}`}
        >
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-2">
            Narrative summary{narrative.tier === "deep" && " · deep"}
          </p>
          <div className="akki-serif text-[14.5px] text-[var(--ink)] leading-relaxed whitespace-pre-wrap">
            {narrative.body}
          </div>
          <div className="mt-4">
            <WalkInCard kind="minutes" contextId={contextId} artefactId={docId} />
          </div>
        </div>
      )}
    </div>
  );
}

function ExtractList({ label, items }) {
  const arr = Array.isArray(items) ? items.filter(Boolean) : [];
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1.5">{label}</p>
      {arr.length === 0 ? (
        <p className="text-[12.5px] italic text-[var(--muted)]">— none extracted</p>
      ) : (
        <ul className="space-y-1 list-disc list-inside marker:text-[var(--accent)]">
          {arr.map((it, i) => (
            <li key={i} className="text-[13px] text-[var(--ink)] leading-snug">{it}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// BriefDetailModal — read the saved brief in place. Markdown rendered as
// pre-wrap text (calm, editorial) so we don't pull in another dependency.
// ---------------------------------------------------------------------------
function BriefDetailModal({ brief, contextId, onClose, onDelete }) {
  const open = Boolean(brief);
  const [shareOpen, setShareOpen] = useState(false);
  const continueInChat = () => {
    if (!brief?.body) return;
    // Seed the chat composer with the brief body so the executive can
    // pressure-test it conversationally — full Synisense shielding still
    // applies because the chat surface owns the policy.
    const seed = `Continuing from a saved brief — "${brief.title}". The brief read:\n\n${brief.body}\n\nMy follow-up: `;
    const params = new URLSearchParams({
      prompt: seed,
      new: "1",
      seed_title: `Brief: ${brief.title}`.slice(0, 110),
    });
    window.location.assign(`/app/chat?${params.toString()}`);
  };
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
          <ValidatedBadge size="compact" validation={brief?.validation} />
          <div className="flex items-center gap-2">
            {brief?.id && onDelete && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  onDelete(brief.id);
                  onClose?.();
                }}
                className="h-8 text-[12.5px] border-[var(--rule)] hover:border-red-700 hover:text-red-700 text-[var(--muted)]"
                data-testid="prepare-brief-delete"
              >
                Delete
              </Button>
            )}
            {brief?.id && (
              <Button
                variant="outline"
                size="sm"
                onClick={continueInChat}
                className="h-8 text-[12.5px] border-[var(--rule)] hover:border-[var(--accent)] text-[var(--ink)]"
                data-testid="prepare-brief-continue-chat"
              >
                Continue in Chat
              </Button>
            )}
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
        </div>
        <div className="mt-3 max-h-[60vh] overflow-y-auto akki-serif text-[15px] leading-[1.7] text-[var(--ink)] whitespace-pre-wrap">
          {brief?.body}
        </div>

        {brief?.id && contextId && brief?.body && brief.body.length > 80 && (
          <div className="mt-5">
            <WalkInCard
              kind="brief"
              contextId={contextId}
              artefactId={brief.id}
              initial={brief.walkin_question}
            />
          </div>
        )}

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
