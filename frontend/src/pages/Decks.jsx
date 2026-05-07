import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  Sparkles, FileText, Check, AlertTriangle, Loader2, ThumbsUp, ThumbsDown,
  ChevronRight, RefreshCw, Pencil, ArrowRight, Send,
} from "lucide-react";
import WalkInCard from "@/components/walkin/WalkInCard";
import ShareArtefactModal from "@/components/studio/ShareArtefactModal";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import HandoffActions from "@/components/shell/HandoffActions";

/**
 * Decks — three-step flow that keeps the user from burning Opus on weak prompts.
 *
 *   Step 1 · Outline   — STANDARD tier, free of deep budget.
 *   Step 2 · Generate  — DEEP tier, consumes 1 of 3 daily slots.
 *   Step 3 · Review    — FAST-tier quality check + thumbs feedback.
 */
const REGEN_REASON_LABEL = {
  audience_drift:         "Audience drift",
  weak_research_question: "Weak question",
  missing_evidence:       "Missing evidence",
  wrong_tone:             "Wrong tone",
  other:                  "Other",
};

export default function Decks() {
  const { activeContext, switchContext } = useAuth();
  const cid = activeContext?.id;
  const { deckId: deepLinkDeckId } = useParams();

  const [view, setView] = useState("intent"); // intent | outline | deck
  const [outline, setOutline] = useState(null);
  const [deck, setDeck] = useState(null);
  const [quota, setQuota] = useState(null);
  const [history, setHistory] = useState([]);
  const [studioHistory, setStudioHistory] = useState([]);
  const [activePlays, setActivePlays] = useState([]);

  useEffect(() => {
    if (!cid) return;
    // Iter62 fix — context switch must clear stale outline/deck/view from
    // the previously-active context. iter65: skip the reset when a deep-link
    // deckId is present so the [cid, deepLinkDeckId] effect can win the race.
    if (deepLinkDeckId) {
      refreshState();
      return;
    }
    setView("intent");
    setOutline(null);
    setDeck(null);
    setHistory([]);
    setStudioHistory([]);
    setActivePlays([]);
    refreshState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid, deepLinkDeckId]);

  // Iter58/iter65 — deep-link support: /app/decks/:deckId opens that deck's
  // review surface directly. iter65 fix: if the deck belongs to a context
  // OTHER than the active one, resolve and switch active context first.
  useEffect(() => {
    if (!cid || !deepLinkDeckId) return;
    let live = true;
    api.get(`/contexts/${cid}/decks/${deepLinkDeckId}`)
      .then((r) => { if (live) { setDeck(r.data); setView("deck"); } })
      .catch(async () => {
        // Deck not in active context — try resolving its real context and
        // switch active context if the user has membership.
        try {
          const { data } = await api.get(`/decks/${deepLinkDeckId}/context`);
          if (!live || !data?.context_id || data.context_id === cid) return;
          switchContext(data.context_id);
          // After switching, the cid will change and this effect re-fires.
        } catch (_) { /* silent — leaves user on intent screen */ }
      });
    return () => { live = false; };
  }, [cid, deepLinkDeckId]);

  const refreshState = async () => {
    try {
      const [{ data: q }, { data: list }, { data: studio }, { data: plays }] = await Promise.all([
        api.get(`/llm/quota?surface=deck`),
        api.get(`/contexts/${cid}/decks?limit=10`),
        api.get(`/contexts/${cid}/studio/history?limit=20`).catch(() => ({ data: { items: [] } })),
        api.get(`/contexts/${cid}/plays`).catch(() => ({ data: { plays: [] } })),
      ]);
      setQuota(q);
      setHistory(list?.items || []);
      setStudioHistory(studio?.items || []);
      setActivePlays((plays?.plays || []).filter((p) => ["active", "paused"].includes(p.status)));
    } catch (e) { /* silent */ }
  };

  if (!cid) {
    return (
      <AppShell>
        <div className="akki-w-narrow px-6 py-12 text-[var(--muted)] italic">
          Select a company to start drafting decks.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="akki-w-medium px-6 py-10" data-testid="decks-page">
        <header className="mb-8">
          <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--accent)] mb-2">
            Decks + Reports · Work Studio
          </p>
          <h1 className="akki-serif text-4xl text-[var(--ink)] tracking-tight leading-[1.05]">
            Produce board-grade material with your own data.
          </h1>
          <p className="text-[14px] text-slate-600 mt-3 leading-relaxed max-w-2xl">
            Decks + Reports is the secure place you draft material that
            leaves your hands. Every saved artefact is auto-classified —
            Public · Internal · Confidential · Restricted — and tracks
            who's read it so you know your information exposure before
            you share. Decks consume one of {quota?.limit ?? 3} deep
            slots a day; outlines stay free.
          </p>
          {quota && (
            <div className="mt-4 flex items-center gap-3 text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] tabular-nums">
              <span data-testid="decks-quota-indicator">
                {quota.remaining} of {quota.limit} deep slots remaining today
              </span>
              <span className="opacity-30">·</span>
              <span>resets at 00:00 UTC</span>
            </div>
          )}
        </header>

        <Stepper view={view} />

        {view === "intent" && (
          <>
            <IntentStep
              contextId={cid}
              onDrafted={(o) => { setOutline(o); setView("outline"); }}
              history={history}
              onResume={(deckId) => loadDeck(cid, deckId, setDeck, setView)}
            />
            {activePlays.length > 0 && (
              <ActiveWorkflowsRail plays={activePlays} />
            )}
            {studioHistory.length > 0 && (
              <StudioHistoryStrip
                items={studioHistory}
                contextId={cid}
                onOpenDeck={(deckId) => loadDeck(cid, deckId, setDeck, setView)}
              />
            )}
          </>
        )}

        {view === "outline" && outline && (
          <OutlineStep
            outline={outline}
            contextId={cid}
            onIterate={(o) => setOutline(o)}
            onGenerated={async (d) => {
              setDeck(d);
              setView("deck");
              await refreshState();
            }}
            onCancel={() => { setOutline(null); setView("intent"); }}
          />
        )}

        {view === "deck" && deck && (
          <DeckStep
            deck={deck}
            contextId={cid}
            onUpdated={setDeck}
            onNew={() => { setDeck(null); setOutline(null); setView("intent"); refreshState(); }}
          />
        )}
      </div>
    </AppShell>
  );
}

async function loadDeck(cid, deckId, setDeck, setView) {
  try {
    const { data } = await api.get(`/contexts/${cid}/decks/${deckId}`);
    setDeck(data);
    setView("deck");
  } catch (e) { toast.error(apiErrorMessage(e)); }
}

// ---------------------------------------------------------------------------
function Stepper({ view }) {
  const steps = [
    { id: "intent", n: 1, label: "Intent" },
    { id: "outline", n: 2, label: "Outline" },
    { id: "deck", n: 3, label: "Deck" },
  ];
  const idx = steps.findIndex((s) => s.id === view);
  return (
    <ol className="flex items-center gap-2 mb-8" data-testid="decks-stepper">
      {steps.map((s, i) => {
        const active = i === idx;
        const done = i < idx;
        return (
          <React.Fragment key={s.id}>
            <li
              className={`flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] ${
                active ? "text-[var(--accent)]" : done ? "text-[var(--ink)]" : "text-[var(--muted)]"
              }`}
              data-testid={`decks-step-${s.id}${active ? "-active" : ""}`}
            >
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono border ${
                active ? "border-[var(--accent)] text-[var(--accent)]" :
                done ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--cream)]" :
                "border-[var(--rule)] text-[var(--muted)]"
              }`}>
                {done ? "✓" : s.n}
              </span>
              {s.label}
            </li>
            {i < steps.length - 1 && (
              <ChevronRight className="w-3 h-3 text-[var(--muted)]" />
            )}
          </React.Fragment>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// STEP 1 · Intent
// ---------------------------------------------------------------------------
function IntentStep({ contextId, onDrafted, history, onResume }) {
  const [intent, setIntent] = useState("");
  const [audience, setAudience] = useState("");
  const [slides, setSlides] = useState("8");
  const [busy, setBusy] = useState(false);

  const draft = async () => {
    if (intent.trim().length < 12 || busy) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/decks/outline`, {
        intent: intent.trim(),
        audience: audience.trim() || null,
        target_slides: Number(slides),
      });
      onDrafted(data);
      toast.success("Outline drafted — review before we commit a deep slot.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <>
      <section
        className="bg-white border border-[var(--rule)] rounded-sm p-6 mb-8"
        data-testid="decks-intent-card"
      >
        <h2 className="akki-serif text-[20px] text-[var(--ink)] mb-1">What's the deck for?</h2>
        <p className="text-[12.5px] text-[var(--muted)] mb-5">
          One sentence is fine. We'll plan it for you and surface gaps before generating.
        </p>
        <div className="space-y-4">
          <div>
            <Label className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
              Intent
            </Label>
            <Textarea
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder="e.g. brief the audit committee on emerging AI risks at our scale and what we need to harden over the next two quarters"
              className="mt-1.5 min-h-[100px]"
              data-testid="decks-intent-input"
            />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <Label className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                Audience (optional)
              </Label>
              <Input
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="Audit committee · Tuli Financial Group"
                className="mt-1.5"
                data-testid="decks-audience-input"
              />
            </div>
            <div>
              <Label className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                Target length
              </Label>
              <Select value={slides} onValueChange={setSlides}>
                <SelectTrigger className="mt-1.5" data-testid="decks-slides-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[6, 8, 10, 12, 15, 18].map((n) => (
                    <SelectItem key={n} value={String(n)}>{n} slides</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end pt-2">
            <Button
              onClick={draft}
              disabled={intent.trim().length < 12 || busy}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-10 px-6"
              data-testid="decks-draft-outline-btn"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
              {busy ? "Planning…" : "Draft outline"}
              {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
            </Button>
          </div>
          <p className="text-[11px] text-[var(--muted)] italic pt-1">
            This step uses the standard tier — it does not consume a deep slot.
          </p>
        </div>
      </section>

      {history.length > 0 && (
        <section data-testid="decks-history">
          <h3 className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
            Recent decks
          </h3>
          <ul className="bg-white border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)]">
            {history.map((d) => (
              <li
                key={d.id}
                className="px-5 py-3 flex items-center justify-between gap-4 hover:bg-[var(--cream-deep)]/30 cursor-pointer"
                onClick={() => onResume(d.id)}
                data-testid={`decks-history-item-${d.id}`}
              >
                <div className="min-w-0 flex-1">
                  <p className="akki-serif text-[14.5px] text-[var(--ink)] truncate">
                    {d.title}
                  </p>
                  <p className="text-[11px] text-[var(--muted)] mt-0.5">
                    {new Date(d.created_at).toLocaleDateString()}
                    {d.tier === "deep" && " · deep"}
                    {d.quality_check?.score != null && ` · q ${d.quality_check.score}`}
                    {d.user_feedback?.rating === "up" && " · 👍"}
                    {d.user_feedback?.rating === "down" && " · 👎"}
                  </p>
                </div>
                {/* Phase 11 ITEM B — independent-validator badge on the
                    Recent Decks row. Rendered ONLY when a real validation
                    payload (with a non-null verdict) is present on the
                    list response — preserves the ValidatedBadge invariant
                    (zero unconditional renders). */}
                {d.validation && d.validation.verdict && (
                  <ValidatedBadge size="compact" validation={d.validation} />
                )}
                <ChevronRight className="w-4 h-4 text-[var(--muted)] shrink-0" />
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// STEP 2 · Outline review
// ---------------------------------------------------------------------------
function OutlineStep({ outline, contextId, onIterate, onGenerated, onCancel }) {
  const [busy, setBusy] = useState(null);
  const [editingRQ, setEditingRQ] = useState(false);
  const [rq, setRq] = useState(outline.research_question || "");

  const sufficiency = outline.context_sufficiency || "partial";
  const sufficiencyTone = {
    sufficient: { color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200", label: "Context looks sufficient" },
    partial:    { color: "text-amber-700",   bg: "bg-amber-50 border-amber-200",     label: "Partial context — review gaps below" },
    insufficient: { color: "text-rose-700",  bg: "bg-rose-50 border-rose-200",       label: "Insufficient context — generating now will likely waste a slot" },
  }[sufficiency] || {};

  const iterate = async () => {
    setBusy("iterate");
    try {
      const { data } = await api.post(`/contexts/${contextId}/decks/outline`, {
        intent: outline.intent,
        audience: outline.audience,
        target_slides: outline.target_slides,
        parent_outline_id: outline.id,
      });
      onIterate(data);
      toast.success("Re-planned — still no deep slot used.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(null); }
  };

  const generate = async () => {
    if (sufficiency === "insufficient" &&
        !window.confirm(
          "The planner thinks context is insufficient — generation may waste a deep slot. Continue anyway?"
        )) {
      return;
    }
    setBusy("generate");
    try {
      const edits = rq && rq !== outline.research_question
        ? { research_question: rq } : null;
      const { data } = await api.post(
        `/contexts/${contextId}/decks/${outline.id}/generate`,
        { outline_id: outline.id, confirmed: true, edits },
      );
      onGenerated(data);
      if (data?.quota?.downgraded) {
        toast.info("Deep budget exhausted today — generated with the standard tier.");
      } else {
        toast.success("Deck generated. Quality check ready.");
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(null); }
  };

  return (
    <section className="space-y-6" data-testid="decks-outline-card">
      {outline.iteration && outline.iteration > 1 && (
        <div className="bg-[var(--cream-deep)]/30 border border-[var(--rule)] rounded-sm px-4 py-2.5 flex items-center justify-between gap-3" data-testid="decks-outline-iteration-chip">
          <p className="text-[11.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
            Iteration <span className="text-[var(--accent)] font-medium tabular-nums">{outline.iteration}</span> ·
            still no deep slot used
          </p>
          {outline.learning_hint_used && (
            <p className="text-[11px] italic text-[var(--accent)] truncate max-w-[60%]" title={outline.learning_hint_used}>
              Tightened from your last feedback
            </p>
          )}
        </div>
      )}
      <div className={`border rounded-sm px-5 py-3 ${sufficiencyTone.bg}`}>
        <p className={`text-[12.5px] tracking-[0.04em] ${sufficiencyTone.color}`} data-testid="decks-sufficiency-banner">
          {sufficiency === "insufficient" && <AlertTriangle className="w-3.5 h-3.5 inline mr-1.5" />}
          {sufficiency !== "insufficient" && <Check className="w-3.5 h-3.5 inline mr-1.5" />}
          {sufficiencyTone.label}
        </p>
      </div>

      <div className="bg-white border border-[var(--rule)] rounded-sm p-6">
        <div className="flex items-start justify-between gap-4 mb-3">
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
            Research question
          </p>
          <button
            onClick={() => setEditingRQ((v) => !v)}
            className="text-[11px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline"
            data-testid="decks-edit-rq-btn"
          >
            <Pencil className="w-3 h-3 inline mr-1" />
            {editingRQ ? "Done" : "Edit"}
          </button>
        </div>
        {editingRQ ? (
          <Textarea
            value={rq}
            onChange={(e) => setRq(e.target.value)}
            className="min-h-[80px] akki-serif text-[18px]"
            data-testid="decks-rq-input"
          />
        ) : (
          <p className="akki-serif text-[20px] text-[var(--ink)] leading-snug" data-testid="decks-rq-display">
            {rq || "(planner did not return a research question)"}
          </p>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white border border-[var(--rule)] rounded-sm p-5">
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-3">
            Evidence to be used ({outline.evidence_used.length})
          </p>
          {outline.evidence_used.length === 0 ? (
            <p className="text-[12.5px] italic text-[var(--muted)]">No evidence selected.</p>
          ) : (
            <ul className="space-y-2 text-[13px] text-[var(--ink)] leading-snug">
              {outline.evidence_used.slice(0, 8).map((e, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] mt-1 min-w-[40px]">
                    {e.kind}
                  </span>
                  <span>{e.why}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="bg-white border border-[var(--rule)] rounded-sm p-5">
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-3">
            Missing context ({(outline.missing_context || []).length})
          </p>
          {(outline.missing_context || []).length === 0 ? (
            <p className="text-[12.5px] italic text-emerald-700">No gaps flagged.</p>
          ) : (
            <ul className="space-y-2 text-[13px] text-[var(--ink)] leading-snug list-disc list-inside marker:text-amber-600">
              {outline.missing_context.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="bg-white border border-[var(--rule)] rounded-sm p-6">
        <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-3">
          Proposed slides ({outline.slides.length})
        </p>
        <ol className="space-y-3">
          {outline.slides.map((s) => (
            <li key={s.n} className="flex gap-3" data-testid={`decks-slide-${s.n}`}>
              <span className="font-mono text-[11px] text-[var(--muted)] min-w-[28px] mt-1">
                {String(s.n).padStart(2, "0")}
              </span>
              <div className="flex-1 min-w-0">
                <p className="akki-serif text-[15px] text-[var(--ink)]">{s.title}</p>
                {s.purpose && (
                  <p className="text-[12px] text-[var(--muted)] italic">{s.purpose}</p>
                )}
                {(s.key_points || []).length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-[12.5px] text-[var(--deep)]">
                    {s.key_points.map((p, i) => (
                      <li key={i}>· {p}</li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
        <Button
          variant="ghost"
          onClick={onCancel}
          className="text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="decks-outline-cancel"
        >
          Start over
        </Button>
        <Button
          variant="outline"
          onClick={iterate}
          disabled={busy === "iterate"}
          className="border-[var(--rule)]"
          data-testid="decks-outline-iterate"
        >
          {busy === "iterate" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
          Re-plan (free)
        </Button>
        <Button
          onClick={generate}
          disabled={busy === "generate"}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-10 px-6"
          data-testid="decks-outline-confirm-generate"
        >
          {busy === "generate" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
          {busy === "generate" ? "Generating…" : "Confirm & generate (uses 1 slot)"}
        </Button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// STEP 3 · Deck review
// ---------------------------------------------------------------------------
function DeckStep({ deck, contextId, onUpdated, onNew }) {
  const [busy, setBusy] = useState(null);
  const [showReasonChips, setShowReasonChips] = useState(false);
  const [engagement, setEngagement] = useState(null);
  const [shareOpen, setShareOpen] = useState(false);
  const qc = deck.quality_check;
  const fb = deck.user_feedback;

  // iter64 — record-view + fetch engagement once per mount. Owner views get
  // tracked too but don't count toward unique_readers (the engine de-dups).
  React.useEffect(() => {
    if (!deck?.id || !contextId) return;
    let live = true;
    api.post(`/contexts/${contextId}/studio/deck/${deck.id}/view`).catch(() => {});
    api.get(`/contexts/${contextId}/studio/deck/${deck.id}/engagement`)
      .then((r) => { if (live) setEngagement(r.data); })
      .catch(() => {});
    return () => { live = false; };
  }, [deck?.id, contextId]);

  const refreshEngagement = async () => {
    try {
      const { data } = await api.get(`/contexts/${contextId}/studio/deck/${deck.id}/engagement`);
      setEngagement(data);
    } catch (_) { /* silent */ }
  };

  const runQuality = async () => {
    setBusy("quality");
    try {
      const { data } = await api.post(`/contexts/${contextId}/decks/${deck.id}/quality_check`);
      onUpdated({ ...deck, quality_check: data.quality_check });
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(null); }
  };

  const submitFeedback = async (rating, regenReason = null) => {
    setBusy("feedback");
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/decks/${deck.id}/feedback`,
        {
          rating,
          regen_reason: regenReason,
          will_regenerate: !!regenReason,
        },
      );
      onUpdated({ ...deck, user_feedback: data.feedback });
      setShowReasonChips(false);
      if (regenReason) {
        toast.success("Noted — your next outline will fold this in.");
      } else {
        toast.success("Thanks for the signal.");
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(null); }
  };

  return (
    <section className="space-y-6" data-testid="decks-deck-card">
      {deck.quota?.downgraded && (
        <div
          className="bg-amber-50 border border-amber-200 rounded-sm px-4 py-3 text-[12.5px] text-amber-700"
          data-testid="decks-downgraded-banner"
        >
          <AlertTriangle className="w-3.5 h-3.5 inline mr-1.5" />
          Daily deep capacity was full when this deck generated — used the standard
          tier instead. Tomorrow's slots reset at 00:00 UTC.
        </div>
      )}
      <div className="bg-white border border-[var(--rule)] rounded-sm p-6">
        <div className="flex items-start justify-between gap-4 mb-2">
          <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)]">
            {deck.tier === "deep" ? "Deep tier · " : "Standard tier · "}
            {deck.slides?.length || 0} slides
          </p>
          <div className="flex flex-wrap items-center gap-1.5 shrink-0">
            <SensitivityChip sensitivity={deck.sensitivity} />
            {deck.validation && <ValidatedBadge size="compact" validation={deck.validation} />}
            <ExposurePill exposure={engagement?.exposure} />
            <button
              type="button"
              onClick={() => setShareOpen(true)}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-[var(--accent)] text-[10px] uppercase tracking-[0.14em] text-[var(--accent)] hover:bg-[var(--accent)] hover:text-white transition-colors"
              data-testid="deck-share-btn"
            >
              <Send className="w-3 h-3" /> Share
            </button>
          </div>
        </div>
        <h2 className="akki-serif text-[28px] text-[var(--ink)] leading-tight mb-1.5" data-testid="decks-title">
          {deck.title}
        </h2>
        {deck.subtitle && (
          <p className="text-[14.5px] text-[var(--deep)]">{deck.subtitle}</p>
        )}
        <p className="text-[12px] text-[var(--muted)] italic mt-3">
          Research question: {deck.research_question}
        </p>
        {engagement?.readers?.length > 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--rule)]" data-testid="decks-readers">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] mb-2">
              Read by
            </p>
            <ul className="flex flex-wrap gap-2 text-[11.5px]">
              {engagement.readers.slice(0, 6).map((r) => (
                <li key={r.account_id} className="bg-[var(--cream-deep)]/30 border border-[var(--rule)] rounded-sm px-2 py-1">
                  {r.name} <span className="text-[var(--muted)]">· {new Date(r.last_viewed_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                </li>
              ))}
              {engagement.readers.length > 6 && (
                <li className="text-[var(--muted)] italic">+{engagement.readers.length - 6} more</li>
              )}
            </ul>
          </div>
        )}
        {engagement?.readers_locked && engagement?.unique_readers > 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--rule)]" data-testid="decks-readers-locked">
            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1.5">
              Read by
            </p>
            <p className="text-[12.5px] text-[var(--deep)] leading-relaxed">
              <span className="text-[var(--accent)] tabular-nums font-medium">{engagement.unique_readers}</span>
              {" "}unique reader{engagement.unique_readers === 1 ? "" : "s"} so far ·{" "}
              <a href="/app/settings?tab=billing" className="text-[var(--accent)] hover:underline" data-testid="decks-readers-upgrade-link">
                Upgrade to Pro to see who
              </a>
            </p>
          </div>
        )}
      </div>

      {/* Quality check */}
      {!qc && (
        <div className="bg-[var(--cream-deep)]/30 border border-[var(--rule)] rounded-sm px-5 py-4 flex items-center justify-between gap-4">
          <p className="text-[13px] text-[var(--deep)]">
            Run a free quality check before deciding whether to regenerate?
          </p>
          <Button
            onClick={runQuality}
            disabled={busy === "quality"}
            variant="outline"
            className="border-[var(--accent)] text-[var(--accent)]"
            data-testid="decks-run-quality-btn"
          >
            {busy === "quality" ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 mr-1.5" />}
            Run quality check
          </Button>
        </div>
      )}
      {qc && (
        <div className="bg-white border border-[var(--rule)] rounded-sm p-5" data-testid="decks-quality-card">
          <div className="flex items-baseline justify-between mb-3">
            <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
              Quality check
            </p>
            <p className="akki-serif text-[28px] tabular-nums text-[var(--accent)]" data-testid="decks-quality-score">
              {qc.score}<span className="text-[14px] text-[var(--muted)]">/100</span>
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-4 text-[12px] text-[var(--deep)] mb-4">
            <Pill label="Coherence" value={qc.narrative_coherence} />
            <Pill label="Evidence" value={qc.evidence_density} />
            <Pill label="Audience fit" value={qc.audience_fit} />
          </div>
          {qc.free_refinements?.length > 0 && (
            <div className="mb-3">
              <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1.5">
                Free refinements (no slot needed)
              </p>
              <ul className="text-[13px] text-[var(--ink)] space-y-1 list-disc list-inside marker:text-[var(--accent)]">
                {qc.free_refinements.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
          {qc.recommend_regenerate && (
            <p className="text-[12.5px] text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5 inline mr-1.5" />
              Regenerate suggested: {qc.regenerate_reason}
            </p>
          )}
        </div>
      )}

      {/* Slides */}
      <div className="space-y-4">
        {(deck.slides || []).map((s, i) => (
          <div
            key={s.n || i}
            className="bg-white border border-[var(--rule)] rounded-sm p-5"
            data-testid={`decks-slide-rendered-${s.n || i+1}`}
          >
            <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
              Slide {String(s.n || i+1).padStart(2, "0")}
            </p>
            <h3 className="akki-serif text-[18px] text-[var(--ink)] mt-1 mb-2">
              {s.title}
            </h3>
            <div className="text-[14px] text-[var(--deep)] leading-relaxed whitespace-pre-wrap">
              {s.body_md}
            </div>
            {deck.speaker_notes?.[i] && (
              <p className="text-[11.5px] text-[var(--muted)] italic mt-3 pl-3 border-l-2 border-[var(--rule)]">
                Speaker note: {deck.speaker_notes[i]}
              </p>
            )}
          </div>
        ))}
      </div>

      <WalkInCard kind="deck" contextId={contextId} artefactId={deck.id} initial={deck.walkin_question} />

      {/* Phase 13.3 — cross-module handoff buttons on a deck. Take the
          deck into Solva for a structured pause, send it to Work
          Studio (lands the user there with the deck in scope), or
          drop a follow-up question into the Cycle question bank. */}
      {deck?.id && contextId && (
        <div className="pt-3 border-t border-[var(--rule)]">
          <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-2">
            Hand this off
          </p>
          <HandoffActions kind="deck" id={deck.id} contextId={contextId} title={deck.title} />
        </div>
      )}

      {/* Feedback + new */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {!fb && !showReasonChips && (
              <>
                <Button
                  variant="outline" size="sm"
                  onClick={() => submitFeedback("up")}
                  className="border-[var(--rule)]"
                  data-testid="decks-feedback-up"
                >
                  <ThumbsUp className="w-3.5 h-3.5 mr-1.5" /> Useful
                </Button>
                <Button
                  variant="outline" size="sm"
                  onClick={() => setShowReasonChips(true)}
                  className="border-[var(--rule)]"
                  data-testid="decks-feedback-down"
                >
                  <ThumbsDown className="w-3.5 h-3.5 mr-1.5" /> Off
                </Button>
              </>
            )}
            {fb && (
              <p className="text-[12px] text-[var(--muted)]" data-testid="decks-feedback-recorded">
                Feedback: {fb.rating === "up" ? "useful 👍" : "off 👎"}
                {fb.regen_reason && ` · ${REGEN_REASON_LABEL[fb.regen_reason] || fb.regen_reason}`}
              </p>
            )}
          </div>
          <Button
            onClick={onNew}
            variant="outline"
            className="border-[var(--rule)]"
            data-testid="decks-new-btn"
          >
            <FileText className="w-3.5 h-3.5 mr-1.5" /> New deck
          </Button>
        </div>

        {showReasonChips && !fb && (
          <div
            className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm px-4 py-3"
            data-testid="decks-regen-reason-panel"
          >
            <p className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] mb-2">
              Why didn't this work? (We'll fold this into your next outline — free.)
            </p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(REGEN_REASON_LABEL).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  disabled={busy === "feedback"}
                  onClick={() => submitFeedback("down", k)}
                  className="text-[11.5px] uppercase tracking-[0.14em] px-3 py-1.5 rounded-sm border border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors disabled:opacity-50"
                  data-testid={`decks-regen-reason-${k}`}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setShowReasonChips(false)}
                className="text-[11.5px] uppercase tracking-[0.14em] px-3 py-1.5 text-[var(--muted)] hover:text-[var(--ink)]"
                data-testid="decks-regen-reason-cancel"
              >
                Skip
              </button>
            </div>
          </div>
        )}
      </div>

      <ShareArtefactModal
        open={shareOpen}
        onOpenChange={setShareOpen}
        contextId={contextId}
        kind="deck"
        artefactId={deck.id}
        artefactTitle={deck.title}
        sensitivityLabel={deck.sensitivity?.label}
        onShared={refreshEngagement}
      />
    </section>
  );
}

function Pill({ label, value }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">{label}</p>
      <p className="text-[var(--ink)] mt-0.5">{value || "—"}</p>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Studio history strip — Decks + Reports merged history with sensitivity
// chip + exposure score per row. iter64.
// ---------------------------------------------------------------------------
const SENS_TONE = {
  public:       { bg: "bg-emerald-50",   border: "border-emerald-200",   text: "text-emerald-800" },
  internal:     { bg: "bg-amber-50",     border: "border-amber-200",     text: "text-amber-900" },
  confidential: { bg: "bg-orange-50",    border: "border-orange-200",    text: "text-orange-900" },
  restricted:   { bg: "bg-red-50",       border: "border-red-200",       text: "text-red-900" },
};

export function SensitivityChip({ sensitivity }) {
  if (!sensitivity) return null;
  const tone = SENS_TONE[sensitivity.classification] || SENS_TONE.internal;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-[0.14em] ${tone.bg} ${tone.border} ${tone.text}`}
      title={(sensitivity.reasons || []).join(" · ") || "No specific signals"}
      data-testid={`studio-sensitivity-${sensitivity.classification}`}
    >
      {sensitivity.label}
    </span>
  );
}

export function ExposurePill({ exposure }) {
  if (!exposure) return null;
  const band = exposure.band || "low";
  const tone =
    band === "high"     ? "text-red-900 bg-red-50 border-red-200" :
    band === "moderate" ? "text-amber-900 bg-amber-50 border-amber-200" :
                          "text-[var(--muted)] bg-white border-[var(--rule)]";
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-[0.14em] ${tone}`}
      title={`Unique readers: ${exposure.inputs?.unique_readers ?? 0} · Shares: ${exposure.inputs?.share_count ?? 0}`}
      data-testid={`studio-exposure-${band}`}
    >
      Exposure {exposure.score}
    </span>
  );
}

function StudioHistoryStrip({ items, contextId, onOpenDeck }) {
  const [busy, setBusy] = useState(false);
  const [list, setList] = useState(items);
  const [shareTarget, setShareTarget] = useState(null); // { kind, id, title, sensitivity_label }

  React.useEffect(() => { setList(items); }, [items]);

  const handleRowClick = (it) => {
    if (it.kind === "deck") {
      onOpenDeck?.(it.id);
    } else if (it.kind === "briefing") {
      // Briefings (formal, db.briefings) are exported as PDF/DOCX. Open
      // the PDF export in a new tab — it carries the same shielding,
      // citations and sensitivity record the Studio history strip already
      // shows.
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/contexts/${contextId}/briefings/${it.id}/export?format=pdf`;
      const tok = localStorage.getItem("akki_access_token");
      // Authenticated download in a new tab — fetch as blob, open via object URL.
      fetch(url, {
        headers: tok ? { Authorization: `Bearer ${tok}` } : {},
        credentials: "include",
      })
        .then((r) => {
          if (!r.ok) throw new Error("Couldn't open the briefing.");
          return r.blob();
        })
        .then((blob) => {
          const u = URL.createObjectURL(blob);
          window.open(u, "_blank", "noopener,noreferrer");
          // Don't revoke immediately — the new tab needs the URL alive.
          setTimeout(() => URL.revokeObjectURL(u), 60_000);
        })
        .catch((e) => toast.error(e.message || "Couldn't open the briefing."));
    }
  };

  const rescore = async () => {
    setBusy(true);
    try {
      await api.post(`/contexts/${contextId}/studio/backfill_sensitivity`);
      const { data } = await api.get(`/contexts/${contextId}/studio/history?limit=20`);
      setList(data.items || []);
      toast.success("Work Studio history re-scored.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-12" data-testid="studio-history">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--accent)]">
            Work Studio history
          </p>
          <p className="akki-serif text-2xl text-[var(--ink)] mt-1">
            What you've produced
          </p>
        </div>
        <button
          type="button"
          onClick={rescore}
          disabled={busy}
          className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] hover:text-[var(--accent)] disabled:opacity-50"
          data-testid="studio-rescore-btn"
        >
          {busy ? "Re-scoring…" : "Re-score sensitivity"}
        </button>
      </div>
      <p className="text-[12.5px] text-slate-600 leading-relaxed mb-6 max-w-[64ch]">
        Every artefact is auto-classified for confidentiality and tracks reader engagement so
        you know your information exposure before sharing. Higher exposure scores mean
        more eyes have seen it.
      </p>
      <ul className="bg-white border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)]" data-testid="studio-history-list">
        {list.map((it) => (
          <li
            key={`${it.kind}-${it.id}`}
            className="px-5 py-4 hover:bg-[var(--cream-deep)]/30 cursor-pointer transition-colors"
            data-testid={`studio-history-row-${it.kind}-${it.id}`}
            onClick={() => handleRowClick(it)}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">
                    {it.kind === "deck" ? "Deck" : "Brief / Report"}
                  </span>
                  <span className="opacity-30">·</span>
                  <span className="text-[10.5px] text-[var(--muted)] tabular-nums">
                    {new Date(it.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  </span>
                </div>
                <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug truncate">
                  {it.title || it.intent || "(Untitled)"}
                </p>
                {it.subtitle && (
                  <p className="text-[12px] text-[var(--muted)] mt-1 line-clamp-1">
                    {it.subtitle}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                <SensitivityChip sensitivity={it.sensitivity} />
                <ExposurePill exposure={it.exposure} />
                <a
                  href={`/app/studio/composer/${it.kind}/${it.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-[var(--rule)] text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
                  data-testid={`studio-history-compose-${it.kind}-${it.id}`}
                >
                  Compose
                </a>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShareTarget({
                      kind: it.kind,
                      id: it.id,
                      title: it.title || it.intent || "(Untitled)",
                      sensitivity_label: it.sensitivity?.label,
                    });
                  }}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-[var(--rule)] text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors"
                  data-testid={`studio-history-share-${it.kind}-${it.id}`}
                >
                  Share
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
      {shareTarget && (
        <ShareArtefactModal
          open={!!shareTarget}
          onOpenChange={(v) => { if (!v) setShareTarget(null); }}
          contextId={contextId}
          kind={shareTarget.kind}
          artefactId={shareTarget.id}
          artefactTitle={shareTarget.title}
          sensitivityLabel={shareTarget.sensitivity_label}
        />
      )}
    </section>
  );
}


// ---------------------------------------------------------------------------
// ActiveWorkflowsRail — iter66 workflows-as-journeys fold-in.
// Surfaces in-progress Plays (Board Pack journey, etc.) on the Studio
// surface so users see their active production workflows alongside
// finished artefacts. Click → /app/plays/{play_id} deep link.
// ---------------------------------------------------------------------------
function ActiveWorkflowsRail({ plays }) {
  return (
    <section className="mt-12 mb-2" data-testid="studio-active-workflows">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--accent)]">
            Active workflows
          </p>
          <p className="akki-serif text-2xl text-[var(--ink)] mt-1">
            Journeys in progress
          </p>
        </div>
        <a
          href="/app/plays"
          className="text-[11px] uppercase tracking-[0.16em] text-[var(--muted)] hover:text-[var(--accent)]"
          data-testid="studio-active-workflows-all"
        >
          View all
        </a>
      </div>
      <ul className="grid sm:grid-cols-2 gap-3" data-testid="studio-active-workflows-list">
        {plays.slice(0, 4).map((p) => (
          <li
            key={p.id}
            className="bg-white border border-[var(--rule)] rounded-sm px-5 py-4 hover:border-[var(--accent)] cursor-pointer transition-colors"
            data-testid={`studio-active-play-${p.id}`}
            onClick={() => window.location.assign(`/app/plays/${p.id}`)}
          >
            <div className="flex items-center justify-between gap-3 mb-1.5">
              <span className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">
                {p.play_type?.replace(/_/g, " ") || "Workflow"}
              </span>
              <span
                className={`text-[10px] uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm ${
                  p.status === "paused"
                    ? "bg-amber-50 text-amber-900 border border-amber-200"
                    : "bg-emerald-50 text-emerald-800 border border-emerald-200"
                }`}
              >
                {p.status}
              </span>
            </div>
            <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug truncate">
              {p.title || p.name || "(Untitled play)"}
            </p>
            {p.current_step_label && (
              <p className="text-[11.5px] text-[var(--muted)] mt-1 line-clamp-1">
                Currently: {p.current_step_label}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
