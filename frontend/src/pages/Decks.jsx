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
  ChevronRight, RefreshCw, Pencil, ArrowRight,
} from "lucide-react";
import WalkInCard from "@/components/walkin/WalkInCard";

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
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const { deckId: deepLinkDeckId } = useParams();

  const [view, setView] = useState("intent"); // intent | outline | deck
  const [outline, setOutline] = useState(null);
  const [deck, setDeck] = useState(null);
  const [quota, setQuota] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!cid) return;
    refreshState();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid]);

  // Iter58 — deep-link support: /app/decks/:deckId opens that deck's review
  // surface directly. Required for shareable links AND for QA. Falls back
  // silently to the intent screen if the deck isn't accessible.
  useEffect(() => {
    if (!cid || !deepLinkDeckId) return;
    let live = true;
    api.get(`/contexts/${cid}/decks/${deepLinkDeckId}`)
      .then((r) => { if (live) { setDeck(r.data); setView("deck"); } })
      .catch(() => { /* silent — leaves user on intent screen */ });
    return () => { live = false; };
  }, [cid, deepLinkDeckId]);

  const refreshState = async () => {
    try {
      const [{ data: q }, { data: list }] = await Promise.all([
        api.get(`/llm/quota?surface=deck`),
        api.get(`/contexts/${cid}/decks?limit=10`),
      ]);
      setQuota(q);
      setHistory(list?.items || []);
    } catch (e) { /* silent */ }
  };

  if (!cid) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto px-6 py-12 text-[var(--muted)] italic">
          Select a context to start drafting decks.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-10" data-testid="decks-page">
        <header className="mb-8">
          <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--accent)] mb-2">
            Decks · narrative
          </p>
          <h1 className="akki-serif text-4xl text-[var(--ink)] tracking-tight leading-[1.05]">
            Plan first. Generate once.
          </h1>
          <p className="text-[14px] text-slate-600 mt-3 leading-relaxed max-w-2xl">
            Decks use the deep model — one of {quota?.limit ?? 3} a day. We draft
            a free outline first so you can sharpen the question and confirm the
            sources before we commit a slot.
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
          <IntentStep
            contextId={cid}
            onDrafted={(o) => { setOutline(o); setView("outline"); }}
            history={history}
            onResume={(deckId) => loadDeck(cid, deckId, setDeck, setView)}
          />
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
                <div className="min-w-0">
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
                <ChevronRight className="w-4 h-4 text-[var(--muted)]" />
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
  const qc = deck.quality_check;
  const fb = deck.user_feedback;

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
        <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mb-1">
          {deck.tier === "deep" ? "Deep tier · " : "Standard tier · "}
          {deck.slides?.length || 0} slides
        </p>
        <h2 className="akki-serif text-[28px] text-[var(--ink)] leading-tight mb-1.5" data-testid="decks-title">
          {deck.title}
        </h2>
        {deck.subtitle && (
          <p className="text-[14.5px] text-[var(--deep)]">{deck.subtitle}</p>
        )}
        <p className="text-[12px] text-[var(--muted)] italic mt-3">
          Research question: {deck.research_question}
        </p>
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
