import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Eye, Sparkles, Loader2, Brain, ArrowRight, MessageCircle,
  Layers, Lightbulb, Coins, Users, Heart, ChevronRight, Trash2, HelpCircle, Send,
} from "lucide-react";
import { useAIStageTicker } from "@/hooks/useAIStageTicker";
import CompositionStrip from "@/components/trace/CompositionStrip";
import CommentThread from "@/components/collab/CommentThread";

/**
 * The Lens — redesigned.
 *
 *   Two modes share the same lens picker:
 *     · Stress-test  — paste a signal/claim/proposal/question, AKKI returns a
 *                       structured Observation → Implication → Action through
 *                       the chosen lens.
 *     · Coach        — multi-turn chat. AKKI replies in the voice of the
 *                       chosen lens. The user can switch lenses mid-chat
 *                       to compare framings without losing the thread.
 *
 *   Pattern adopted from 2026 best-practice persona-switcher chat UIs:
 *   compact lens-pill row above the input, always visible; one-click
 *   switching; stress-test history and coach sessions live in one
 *   timeline so the user keeps a single record of "thinking with AKKI".
 */

const LENS_ICON = {
  first_principles: Brain,
  customer_obsession: Heart,
  systems_thinking: Layers,
  capital_discipline: Coins,
  stakeholder_integration: Users,
  organisational_culture: Lightbulb,
};

const INPUT_KIND_OPTIONS = [
  { id: "signal", label: "Signal" },
  { id: "claim", label: "Claim" },
  { id: "proposal", label: "Proposal" },
  { id: "question", label: "Question" },
];

const MODE_OPTIONS = [
  { id: "stress", label: "Stress-test", hint: "Run a structured Observation → Implication → Action through the lens." },
  { id: "coach", label: "Coach", hint: "Talk through your thinking. AKKI replies in the lens's voice." },
];

export default function LensRoom() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [params] = useSearchParams();
  const initialSignalId = params.get("signal");

  const [mode, setMode] = useState("stress");
  const [catalog, setCatalog] = useState([]);
  const [lens, setLens] = useState("first_principles");

  // Stress-test state
  const [inputKind, setInputKind] = useState("signal");
  const [subject, setSubject] = useState("");
  const [running, setRunning] = useState(false);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);

  // Coach state
  const [coachSessions, setCoachSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);  // hydrated session
  const [coachInput, setCoachInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  // ── Catalog + history fetch ───────────────────────────────────────────
  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const [c, r, s] = await Promise.all([
        api.get("/lens/catalog"),
        api.get(`/contexts/${cid}/lens/runs`),
        api.get(`/contexts/${cid}/lens/coach/sessions`),
      ]);
      setCatalog(c.data || []);
      setRuns(r.data || []);
      setCoachSessions(s.data || []);
      if (initialSignalId && (r.data || []).length > 0 && !selectedRun) {
        setSelectedRun(r.data[0]);
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
  }, [cid, initialSignalId, selectedRun]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelectedRun(null); setActiveSession(null); }, [cid]);

  // ── Stress-test run ───────────────────────────────────────────────────
  const stageScript = useMemo(() => {
    const name = catalog.find((l) => l.id === lens)?.name || "the lens";
    return [
      { at: 0, text: `Reading your ${inputKind} against ${name}…` },
      { at: 6000, text: "Pulling supporting evidence from your documents…" },
      { at: 14000, text: "Drafting Observation → Implication → Action…" },
      { at: 26000, text: "Landing the single question for management…" },
      { at: 42000, text: "Still thinking — deep subjects take a moment longer…" },
    ];
  }, [catalog, lens, inputKind]);
  const runStage = useAIStageTicker(running, stageScript);

  const onRunStress = async () => {
    const text = subject.trim();
    if (text.length < 10) { toast.message("Give AKKI something to chew on (≥10 chars)."); return; }
    setRunning(true);
    try {
      const fullSubject = `[${inputKind.toUpperCase()}] ${text}`;
      const { data } = await api.post(
        `/contexts/${cid}/lens/run`,
        { lens, subject: fullSubject },
        { timeout: 180000 },
      );
      toast.success("Lens applied");
      setSubject("");
      setSelectedRun(data);
      setRuns((prev) => [data, ...prev]);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setRunning(false); }
  };

  const onArchiveRun = async (run) => {
    try {
      await api.delete(`/contexts/${cid}/lens/runs/${run.id}`);
      setRuns((prev) => prev.filter((r) => r.id !== run.id));
      if (selectedRun?.id === run.id) setSelectedRun(null);
      toast.success("Archived");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  // ── Coach session lifecycle ───────────────────────────────────────────
  const onStartSession = async () => {
    const seed = subject.trim() || "What's on your mind?";
    try {
      const { data } = await api.post(
        `/contexts/${cid}/lens/coach/sessions`,
        { lens, subject: seed.slice(0, 180) },
      );
      setActiveSession(data);
      setCoachSessions((prev) => [{
        ...data,
        message_count: 0,
        last_message_preview: "",
      }, ...prev]);
      setSubject("");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onOpenSession = async (s) => {
    try {
      const { data } = await api.get(`/contexts/${cid}/lens/coach/sessions/${s.id}`);
      setActiveSession(data);
      setLens(data.lens || lens);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onSendCoach = async () => {
    const text = coachInput.trim();
    if (!text || !activeSession) return;
    setSending(true);
    // Optimistic append
    const optimistic = { role: "user", content: text, lens, at: new Date().toISOString() };
    setActiveSession((prev) => ({ ...prev, messages: [...(prev.messages || []), optimistic] }));
    setCoachInput("");
    try {
      const { data } = await api.post(
        `/contexts/${cid}/lens/coach/sessions/${activeSession.id}/messages`,
        { lens, message: text },
        { timeout: 120000 },
      );
      setActiveSession((prev) => ({
        ...prev,
        lens,
        messages: [...(prev.messages || []).slice(0, -1), data.user, data.akki],
      }));
      setCoachSessions((prev) => prev.map((s) =>
        s.id === activeSession.id
          ? { ...s, lens, message_count: (s.message_count || 0) + 2,
              last_message_preview: (data.akki.content || "").slice(0, 160), updated_at: data.akki.at }
          : s
      ));
    } catch (e) {
      toast.error(apiErrorMessage(e));
      // Rollback optimistic
      setActiveSession((prev) => ({ ...prev, messages: (prev.messages || []).slice(0, -1) }));
    } finally { setSending(false); }
  };

  const onArchiveSession = async (s) => {
    try {
      await api.delete(`/contexts/${cid}/lens/coach/sessions/${s.id}`);
      setCoachSessions((prev) => prev.filter((x) => x.id !== s.id));
      if (activeSession?.id === s.id) setActiveSession(null);
      toast.success("Conversation archived");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  // ── Auto-scroll coach messages
  useEffect(() => {
    if (mode === "coach") messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeSession?.messages?.length, mode]);

  if (!cid) {
    return <AppShell><div className="p-12 text-center text-sm text-[var(--muted)]">No company selected.</div></AppShell>;
  }

  const activeLens = catalog.find((l) => l.id === lens);

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-[300px_1fr] overflow-hidden" data-testid="lens-room">
        {/* LEFT — history rail (unified runs + coach sessions) */}
        <aside className="border-r border-[var(--rule)] bg-[var(--cream)] flex flex-col min-h-0">
          <div className="px-5 py-5 border-b border-[var(--rule)] bg-white">
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <Eye className="w-3 h-3 text-[var(--accent)]" /> The Lens
            </p>
            <h1 className="akki-serif text-[19px] font-normal text-[var(--ink)] mb-1">
              Test claims. Coach yourself.
            </h1>
            <p className="text-[11.5px] text-[var(--muted)] leading-relaxed">
              Pick a lens, drop in a signal/claim/proposal — or start a coaching chat through it.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto" data-testid="lens-history">
            {/* Stress-test history */}
            <div className="px-3 py-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono px-2 mb-2">
                Stress-tests
              </p>
              {runs.length === 0 ? (
                <p className="px-2 text-[11.5px] text-[var(--muted)] italic">None yet.</p>
              ) : runs.slice(0, 12).map((r) => {
                const Icon = LENS_ICON[r.lens] || Eye;
                const active = mode === "stress" && selectedRun?.id === r.id;
                return (
                  <button
                    key={r.id}
                    onClick={() => { setMode("stress"); setSelectedRun(r); setActiveSession(null); }}
                    className={`w-full text-left px-3 py-2 rounded-sm mb-1 transition-colors border ${
                      active ? "bg-white border-[var(--accent)]/60" : "border-transparent hover:bg-white"
                    }`}
                    data-testid={`lens-run-item-${r.id}`}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Icon className="w-2.5 h-2.5 text-[var(--accent)]" strokeWidth={2} />
                      <span className="text-[10px] text-[var(--muted)]">{r.lens_name}</span>
                    </div>
                    <p className="text-[12px] leading-snug line-clamp-2 text-[var(--deep)]">
                      {(r.subject || "").replace(/^\[\w+\]\s*/, "")}
                    </p>
                  </button>
                );
              })}
            </div>

            {/* Coach sessions */}
            <div className="px-3 py-3 border-t border-[var(--rule)]">
              <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono px-2 mb-2">
                Coaching threads
              </p>
              {coachSessions.length === 0 ? (
                <p className="px-2 text-[11.5px] text-[var(--muted)] italic">None yet.</p>
              ) : coachSessions.slice(0, 12).map((s) => {
                const Icon = LENS_ICON[s.lens] || MessageCircle;
                const active = mode === "coach" && activeSession?.id === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => { setMode("coach"); onOpenSession(s); }}
                    className={`w-full text-left px-3 py-2 rounded-sm mb-1 transition-colors border ${
                      active ? "bg-white border-[var(--accent)]/60" : "border-transparent hover:bg-white"
                    }`}
                    data-testid={`lens-session-item-${s.id}`}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Icon className="w-2.5 h-2.5 text-[var(--accent)]" strokeWidth={2} />
                      <span className="text-[10px] text-[var(--muted)] truncate">{s.subject}</span>
                    </div>
                    <p className="text-[11.5px] leading-snug line-clamp-1 text-[var(--muted)]">
                      {s.last_message_preview || `${s.message_count} messages`}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        {/* RIGHT — mode + canvas */}
        <main className="overflow-y-auto bg-[var(--cream)]" data-testid="lens-detail">
          <div className="max-w-3xl mx-auto px-8 py-8">
            {/* Mode tabs */}
            <div className="flex items-center gap-1 mb-6" data-testid="lens-mode-tabs">
              {MODE_OPTIONS.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  className={`px-4 py-1.5 text-[12.5px] rounded-full border transition-colors ${
                    mode === m.id
                      ? "bg-[var(--ink)] text-white border-[var(--ink)]"
                      : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"
                  }`}
                  data-testid={`lens-mode-${m.id}`}
                  title={m.hint}
                >
                  {m.label}
                </button>
              ))}
              <span className="text-[11.5px] text-[var(--muted)] italic ml-2">
                {MODE_OPTIONS.find((m) => m.id === mode)?.hint}
              </span>
            </div>

            {/* Lens chips — always visible, the operative selector */}
            <LensChipRow catalog={catalog} active={lens} onPick={setLens} />

            {mode === "stress" ? (
              <StressMode
                inputKind={inputKind} setInputKind={setInputKind}
                subject={subject} setSubject={setSubject}
                onRun={onRunStress} running={running} runStage={runStage}
                activeLens={activeLens}
                selectedRun={selectedRun}
                onArchive={onArchiveRun}
              />
            ) : (
              <CoachMode
                activeSession={activeSession}
                onStart={onStartSession}
                onSend={onSendCoach}
                onArchive={onArchiveSession}
                input={coachInput} setInput={setCoachInput}
                subject={subject} setSubject={setSubject}
                sending={sending}
                lens={lens}
                activeLens={activeLens}
                messagesEndRef={messagesEndRef}
              />
            )}
          </div>
        </main>
      </div>
    </AppShell>
  );
}

function LensChipRow({ catalog, active, onPick }) {
  if (catalog.length === 0) {
    return <div className="h-9 mb-5 text-[11.5px] text-[var(--muted)]">Loading lenses…</div>;
  }
  return (
    <div className="flex flex-wrap items-center gap-2 mb-5" data-testid="lens-chip-row">
      <span className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mr-1">Lens</span>
      {catalog.map((l) => {
        const Icon = LENS_ICON[l.id] || Eye;
        const isActive = l.id === active;
        return (
          <button
            key={l.id}
            onClick={() => onPick(l.id)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] rounded-full border transition-colors ${
              isActive
                ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"
            }`}
            data-testid={`lens-chip-${l.id}`}
            title={l.hint}
          >
            <Icon className="w-3 h-3" strokeWidth={2} /> {l.name}
          </button>
        );
      })}
    </div>
  );
}

function StressMode({ inputKind, setInputKind, subject, setSubject, onRun, running, runStage, activeLens, selectedRun, onArchive }) {
  return (
    <>
      {/* Input kind chips */}
      <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="stress-kind-row">
        <span className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mr-1">Test as</span>
        {INPUT_KIND_OPTIONS.map((k) => (
          <button
            key={k.id}
            onClick={() => setInputKind(k.id)}
            className={`px-2.5 py-1 text-[11.5px] rounded-full border ${
              inputKind === k.id
                ? "bg-[var(--ink)] text-white border-[var(--ink)]"
                : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"
            }`}
            data-testid={`stress-kind-${k.id}`}
          >
            {k.label}
          </button>
        ))}
      </div>

      <div className="bg-white border border-[var(--rule)] rounded-md p-4 mb-6" data-testid="stress-input-card">
        <textarea
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder={`Paste a ${inputKind} the board needs to decide on. AKKI will read it through ${activeLens?.name || "the lens"}…`}
          rows={4}
          disabled={running}
          className="w-full bg-transparent text-[14px] resize-none focus:outline-none akki-serif leading-relaxed"
          data-testid="stress-input"
        />
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-[var(--rule)]">
          <p className="text-[11px] text-[var(--muted)] italic">{activeLens?.hint || ""}</p>
          <Button
            onClick={onRun}
            disabled={running || !subject.trim()}
            size="sm"
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12.5px] h-8"
            data-testid="stress-run-btn"
          >
            {running
              ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Reading…</>
              : <><Sparkles className="w-3 h-3 mr-1.5" /> Apply lens</>}
          </Button>
        </div>
      </div>

      {running && !selectedRun ? (
        <div className="bg-white border border-[var(--rule)] rounded-md p-12 text-center" data-testid="stress-running">
          <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)] mx-auto mb-4" />
          {runStage && <p className="text-[13px] text-[var(--deep)] italic max-w-md mx-auto">{runStage}</p>}
        </div>
      ) : selectedRun ? (
        <RunViewer run={selectedRun} onArchive={onArchive} />
      ) : (
        <EmptyHelp text="Drop in your text above. Pick a lens. AKKI returns Observation → Implication → Action plus the single question to put to management." />
      )}
    </>
  );
}

function CoachMode({ activeSession, onStart, onSend, onArchive, input, setInput, subject, setSubject, sending, lens, activeLens, messagesEndRef }) {
  if (!activeSession) {
    return (
      <div className="bg-white border border-[var(--rule)] rounded-md p-6" data-testid="coach-empty">
        <p className="akki-overline mb-2">Start a coaching thread</p>
        <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-4">
          Type the topic on your mind. AKKI will reply through <strong>{activeLens?.name || "the chosen lens"}</strong>. Switch lenses any time using the chips above.
        </p>
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="e.g. We're considering raising prices in Q2."
          className="w-full bg-white border border-[var(--rule)] rounded-sm text-[14px] px-3 py-2 mb-3 focus:outline-none focus:border-[var(--accent)]"
          data-testid="coach-subject-input"
        />
        <Button
          onClick={onStart}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12.5px] h-8"
          data-testid="coach-start-btn"
        >
          <MessageCircle className="w-3 h-3 mr-1.5" /> Start the conversation
        </Button>
      </div>
    );
  }

  const messages = activeSession.messages || [];

  return (
    <div className="bg-white border border-[var(--rule)] rounded-md flex flex-col" style={{ minHeight: "60vh" }} data-testid="coach-thread">
      <div className="px-5 py-3 border-b border-[var(--rule)] flex items-center justify-between">
        <div className="min-w-0 flex-1">
          <p className="akki-overline mb-0.5">{activeLens?.name} · coaching</p>
          <p className="text-[13px] text-[var(--ink)] truncate">{activeSession.subject}</p>
        </div>
        <button
          onClick={() => onArchive(activeSession)}
          className="text-[11.5px] text-[var(--muted)] hover:text-red-700 inline-flex items-center gap-1 ml-3"
          data-testid="coach-archive"
        >
          <Trash2 className="w-3 h-3" /> Archive
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5" data-testid="coach-messages">
        {messages.length === 0 ? (
          <p className="text-[13px] text-[var(--muted)] italic text-center mt-12">
            Type your first thought below. AKKI is listening through {activeLens?.name}.
          </p>
        ) : messages.map((m, i) => (
          <CoachBubble key={i} m={m} />
        ))}
        {sending && (
          <div className="flex items-center gap-2 text-[12.5px] text-[var(--muted)] italic">
            <Loader2 className="w-3 h-3 animate-spin" /> AKKI is thinking through {activeLens?.name}…
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-[var(--rule)] p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onSend(); }
            }}
            rows={2}
            placeholder={`Reply through ${activeLens?.name}… (⌘/Ctrl+Enter to send)`}
            disabled={sending}
            className="flex-1 bg-[var(--cream)] border border-[var(--rule)] rounded-sm text-[13.5px] p-2.5 resize-none focus:outline-none focus:border-[var(--accent)] akki-serif leading-relaxed"
            data-testid="coach-input"
          />
          <Button
            onClick={onSend}
            disabled={sending || !input.trim()}
            size="sm"
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-9 w-10 p-0"
            data-testid="coach-send-btn"
            aria-label="Send message"
          >
            {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          </Button>
        </div>
        <p className="text-[10.5px] text-[var(--muted)] italic mt-1.5">
          Switch lenses with the chips above to reframe the next reply.
        </p>
      </div>
    </div>
  );
}

function CoachBubble({ m }) {
  const isUser = m.role === "user";
  const Icon = LENS_ICON[m.lens] || Eye;
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`} data-testid={`coach-msg-${m.role}`}>
      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center ${
        isUser ? "bg-[var(--ink)] text-white" : "bg-[var(--accent-soft)] text-[var(--accent)]"
      }`}>
        {isUser ? <span className="text-[11px] font-mono">YOU</span> : <Icon className="w-3.5 h-3.5" />}
      </div>
      <div className={`flex-1 ${isUser ? "text-right" : ""}`}>
        <p className={`akki-serif text-[14.5px] leading-[1.65] text-[var(--ink)] whitespace-pre-wrap ${
          isUser ? "" : ""
        }`}>{m.content}</p>
      </div>
    </div>
  );
}

function RunViewer({ run, onArchive }) {
  const Icon = LENS_ICON[run.lens] || Eye;
  return (
    <article className="akki-fade-up space-y-6" data-testid={`lens-run-${run.id}`}>
      <header>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-7 h-7 bg-[var(--accent-soft)] rounded-md flex items-center justify-center">
            <Icon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
          </div>
          <p className="akki-overline">{run.lens_name} · {new Date(run.created_at).toLocaleDateString()}</p>
        </div>
        <h2 className="akki-serif text-[22px] leading-[1.3] text-[var(--ink)] font-normal mb-2">
          {(run.subject || "").replace(/^\[\w+\]\s*/, "")}
        </h2>
        <span className="akki-context-chip capitalize">{run.confidence} confidence</span>
      </header>

      <Section label="Observation" body={run.observation} />
      <Section label="Implication" body={run.implication} />
      <Section label="Action" body={run.action} accent />

      {run.question_for_management && (
        <section className="bg-[var(--accent-soft)]/60 border border-[var(--accent)]/30 rounded-md p-5">
          <div className="flex items-center gap-2 mb-2">
            <HelpCircle className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
            <p className="akki-overline">Question for management</p>
          </div>
          <p className="akki-serif text-[15.5px] leading-[1.6] text-[var(--ink)] italic">"{run.question_for_management}"</p>
        </section>
      )}

      <div className="pt-4 border-t border-[var(--rule)] flex items-center justify-between text-[12px] text-[var(--muted)]">
        <span>AKKI synthesis</span>
        <button onClick={() => onArchive(run)} className="akki-gesture text-[12.5px]" data-testid={`lens-archive-${run.id}`}>
          <Trash2 className="w-3.5 h-3.5" /> Archive
        </button>
      </div>

      <CompositionStrip artefact={run} kind="lens" />
      <CommentThread artefactType="signal" artefactId={run.signal_id || run.id} />
    </article>
  );
}

function Section({ label, body, accent = false }) {
  return (
    <section className={`bg-white border border-[var(--rule)] rounded-md p-5 relative ${accent ? "" : ""}`}>
      {accent && <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)] rounded-l-md" />}
      <p className="akki-overline mb-2">{label}</p>
      <p className="akki-serif text-[14.5px] leading-[1.7] text-[var(--deep)]">{body}</p>
    </section>
  );
}

function EmptyHelp({ text }) {
  return (
    <div className="bg-white border border-dashed border-[var(--rule)] rounded-md p-8 text-center" data-testid="lens-empty-help">
      <Eye className="w-8 h-8 text-[var(--muted)]/40 mx-auto mb-3" strokeWidth={1.2} />
      <p className="text-[13.5px] text-[var(--deep)] leading-relaxed max-w-md mx-auto">{text}</p>
      <p className="text-[11px] text-[var(--muted)] mt-3 inline-flex items-center gap-1">
        Drop your text above <ChevronRight className="w-3 h-3" />
      </p>
    </div>
  );
}
