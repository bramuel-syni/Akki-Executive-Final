import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Eye, Sparkles, Loader2, Brain, ArrowRight, MessageCircle,
  Layers, Lightbulb, Coins, Users, Heart, ChevronDown, Trash2, HelpCircle, Send,
} from "lucide-react";
import { useAIStageTicker } from "@/hooks/useAIStageTicker";
import CompositionStrip from "@/components/trace/CompositionStrip";
import CommentThread from "@/components/collab/CommentThread";

/**
 * In the Lens — the redesigned single-line picker.
 *
 *   ┌───────────────────────┬───────────────────┬──────────┐
 *   │  In the Lens (mode ▾) │  Test us (kind ▾) │  Apply  │
 *   └───────────────────────┴───────────────────┴──────────┘
 *
 *   • Mode dropdown picks WHAT lens you want to read your subject through
 *     — first principles, capital discipline, etc.
 *   • Test-us dropdown picks WHAT KIND of subject — signal, claim,
 *     proposal, question — OR coach-mode for a back-and-forth.
 *   • Apply runs it; a clean Observation → Implication → Action drops
 *     into the canvas below.
 *
 *   The page is shaped around the user's mental model:
 *     1. What do I do?     → drop a subject in the box
 *     2. What kind?        → choose lens + kind in the dropdowns above
 *     3. Where do I get it?→ canvas immediately below
 *     4. What do I get?    → Observation, Implication, Action, Question
 */

const LENS_ICON = {
  first_principles: Brain,
  customer_obsession: Heart,
  systems_thinking: Layers,
  capital_discipline: Coins,
  stakeholder_integration: Users,
  organisational_culture: Lightbulb,
};

// "Test us" kinds — what is the user putting into AKKI?
// 'coach' is the multi-turn chat mode.
const KIND_OPTIONS = [
  { id: "signal",   label: "A signal — pressure-test the framing",        kind: "stress" },
  { id: "claim",    label: "A claim — verify it through the lens",         kind: "stress" },
  { id: "proposal", label: "A proposal — should the board approve it?",    kind: "stress" },
  { id: "question", label: "A question — sharpen what to ask",             kind: "stress" },
  { id: "coach",    label: "Coach me — talk it through, multi-turn",       kind: "coach"  },
];

export default function LensRoom() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [params] = useSearchParams();
  const initialSessionId = params.get("session");

  const [catalog, setCatalog] = useState([]);
  const [lens, setLens] = useState("first_principles");
  const [kindId, setKindId] = useState("signal");
  const kindCfg = useMemo(() => KIND_OPTIONS.find((k) => k.id === kindId) || KIND_OPTIONS[0], [kindId]);
  const mode = kindCfg.kind;

  // Subject is the user's input — used by both stress (single-shot) and
  // coach (seed message) flows.
  const [subject, setSubject] = useState("");

  // Stress-test state
  const [running, setRunning] = useState(false);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);

  // Coach state
  const [coachSessions, setCoachSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
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
      if (initialSessionId && !activeSession) {
        const found = (s.data || []).find((x) => x.id === initialSessionId);
        if (found) {
          setKindId("coach");
          try {
            const { data: full } = await api.get(`/contexts/${cid}/lens/coach/sessions/${initialSessionId}`);
            setActiveSession(full);
            setLens(full.lens || "first_principles");
          } catch { /* ignore */ }
        }
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
  }, [cid, initialSessionId, activeSession]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelectedRun(null); setActiveSession(null); }, [cid]);

  // ── Stress-test run ───────────────────────────────────────────────────
  const stageScript = useMemo(() => {
    const name = catalog.find((l) => l.id === lens)?.name || "the lens";
    return [
      { at: 0, text: `Reading your ${kindCfg.id} against ${name}…` },
      { at: 6000, text: "Pulling supporting evidence from your documents…" },
      { at: 14000, text: "Drafting Observation → Implication → Action…" },
      { at: 26000, text: "Landing the single question for management…" },
      { at: 42000, text: "Still thinking — deep subjects take a moment longer…" },
    ];
  }, [catalog, lens, kindCfg.id]);
  const runStage = useAIStageTicker(running, stageScript);

  const onApplyStress = async () => {
    const text = subject.trim();
    if (text.length < 10) { toast.message("Give AKKI something to chew on (≥10 chars)."); return; }
    setRunning(true);
    try {
      const fullSubject = `[${kindCfg.id.toUpperCase()}] ${text}`;
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
  const onApplyCoach = async () => {
    const seed = subject.trim();
    if (seed.length < 4) { toast.message("Type the topic on your mind (a sentence is enough)."); return; }
    try {
      const { data } = await api.post(
        `/contexts/${cid}/lens/coach/sessions`,
        { lens, subject: seed.slice(0, 180) },
      );
      setActiveSession(data);
      setCoachSessions((prev) => [{
        ...data, message_count: 0, last_message_preview: "",
      }, ...prev]);
      setSubject("");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onApply = () => {
    if (mode === "coach") return onApplyCoach();
    return onApplyStress();
  };

  const onOpenSession = async (s) => {
    try {
      const { data } = await api.get(`/contexts/${cid}/lens/coach/sessions/${s.id}`);
      setActiveSession(data);
      setLens(data.lens || lens);
      setKindId("coach");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onSelectRun = (r) => {
    setSelectedRun(r);
    setActiveSession(null);
    setKindId("signal"); // arbitrary — keep stress-mode active
  };

  const onSendCoach = async () => {
    const text = coachInput.trim();
    if (!text || !activeSession) return;
    setSending(true);
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
        ...prev, lens,
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
        {/* LEFT — history rail */}
        <aside className="border-r border-[var(--rule)] bg-[var(--cream)] flex flex-col min-h-0">
          <div className="px-5 py-5 border-b border-[var(--rule)] bg-white">
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <Eye className="w-3 h-3 text-[var(--accent)]" /> The Lens
            </p>
            <h1 className="akki-serif text-[19px] font-normal text-[var(--ink)] mb-1">
              Pressure-test what's coming to the board.
            </h1>
            <p className="text-[11.5px] text-[var(--muted)] leading-relaxed">
              Pick a lens, drop your text, hit Apply.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto" data-testid="lens-history">
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
                    onClick={() => onSelectRun(r)}
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
                    onClick={() => onOpenSession(s)}
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

        {/* RIGHT — picker + canvas */}
        <main className="overflow-y-auto bg-[var(--cream)]" data-testid="lens-detail">
          <div className="max-w-3xl mx-auto px-8 py-8">
            {/* PICKER ROW — In the Lens (lens) · Test us (kind) · Apply */}
            <div className="bg-white border border-[var(--rule)] rounded-md p-3 mb-4 flex flex-wrap items-stretch gap-2" data-testid="lens-picker-row">
              <LensDropdown
                catalog={catalog}
                value={lens}
                onChange={setLens}
              />
              <KindDropdown
                value={kindId}
                onChange={(v) => {
                  setKindId(v);
                  // Switching INTO coach mode keeps the active session if any;
                  // switching OUT clears it so the stress canvas takes over.
                  if (KIND_OPTIONS.find((k) => k.id === v)?.kind !== "coach") {
                    setActiveSession(null);
                  }
                }}
              />
              <div className="flex-1 min-w-[100px]" />
              <Button
                onClick={onApply}
                disabled={running || !subject.trim() || (mode === "coach" && !!activeSession)}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[13px] h-10 px-5"
                data-testid="lens-apply-btn"
                title={mode === "coach" && activeSession ? "A coaching thread is already open below — reply there" : ""}
              >
                {running
                  ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Reading…</>
                  : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Apply</>}
              </Button>
            </div>

            {/* INPUT — single textarea, what the user is putting in. */}
            <div className="bg-white border border-[var(--rule)] rounded-md p-4 mb-6" data-testid="lens-input-card">
              <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mb-2">
                {mode === "coach" ? "Topic on your mind" : `Your ${kindCfg.id}`}
              </p>
              <textarea
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder={
                  mode === "coach"
                    ? `e.g. We're considering raising prices in Q2. Walk me through it via ${activeLens?.name || "the lens"}.`
                    : `Paste the ${kindCfg.id} the board needs to react to. AKKI will read it through ${activeLens?.name || "the lens"}.`
                }
                rows={mode === "coach" ? 2 : 4}
                disabled={running || (mode === "coach" && !!activeSession)}
                className="w-full bg-transparent text-[14.5px] resize-none focus:outline-none akki-serif leading-relaxed"
                data-testid="lens-input"
              />
              <div className="flex items-center justify-between mt-1 pt-2 border-t border-[var(--rule)]">
                <p className="text-[11px] text-[var(--muted)] italic">
                  {activeLens?.hint || ""}
                </p>
                <p className="text-[10.5px] text-[var(--muted)]">
                  {mode === "coach"
                    ? activeSession ? "Thread open below — reply there." : "Apply starts the conversation."
                    : "Apply returns Observation → Implication → Action."}
                </p>
              </div>
            </div>

            {/* CANVAS — output / coach thread / placeholder */}
            {mode === "coach" ? (
              <CoachCanvas
                activeSession={activeSession}
                onSend={onSendCoach}
                onArchive={onArchiveSession}
                input={coachInput} setInput={setCoachInput}
                sending={sending}
                activeLens={activeLens}
                messagesEndRef={messagesEndRef}
              />
            ) : running ? (
              <div className="bg-white border border-[var(--rule)] rounded-md p-12 text-center" data-testid="stress-running">
                <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)] mx-auto mb-4" />
                {runStage && <p className="text-[13px] text-[var(--deep)] italic max-w-md mx-auto">{runStage}</p>}
              </div>
            ) : selectedRun ? (
              <RunViewer run={selectedRun} onArchive={onArchiveRun} />
            ) : (
              <EmptyHelp activeLens={activeLens} kindCfg={kindCfg} />
            )}
          </div>
        </main>
      </div>
    </AppShell>
  );
}

/** Reusable dropdown — accessible <details>/<summary> wouldn't carry the
 *  hover state styles we want, so this is a controlled popover with a
 *  click-outside handler. */
function NativeDropdown({ label, value, options, onChange, testid, kicker }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const active = options.find((o) => o.id === value);
  return (
    <div className="relative" ref={ref} data-testid={testid}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="h-10 inline-flex items-center gap-2 px-3 rounded-md border border-[var(--rule)] bg-white hover:border-[var(--accent)]/40 text-left transition-colors"
        data-testid={`${testid}-trigger`}
      >
        <div className="flex flex-col items-start leading-tight">
          <span className="text-[9.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono">{kicker}</span>
          <span className="text-[13px] text-[var(--ink)] truncate max-w-[260px]">
            {active?.label || label}
          </span>
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-[var(--muted)] ml-1 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div
          className="absolute z-30 mt-1 left-0 min-w-[320px] bg-white border border-[var(--rule)] rounded-md shadow-lg py-1 max-h-80 overflow-y-auto"
          data-testid={`${testid}-menu`}
        >
          {options.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => { onChange(o.id); setOpen(false); }}
              className={`w-full text-left px-3 py-2 hover:bg-[var(--cream-deep)]/40 ${
                o.id === value ? "bg-[var(--cream-deep)]/30" : ""
              }`}
              data-testid={`${testid}-opt-${o.id}`}
            >
              <div className="flex items-center gap-2">
                {o.icon ? <o.icon className="w-3 h-3 text-[var(--accent)] shrink-0" /> : null}
                <span className="text-[13px] text-[var(--ink)]">{o.label}</span>
              </div>
              {o.hint && <p className="text-[11px] text-[var(--muted)] italic mt-0.5 ml-5 leading-relaxed">{o.hint}</p>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LensDropdown({ catalog, value, onChange }) {
  const options = catalog.map((l) => ({
    id: l.id,
    label: l.name,
    hint: l.hint,
    icon: LENS_ICON[l.id] || Eye,
  }));
  return (
    <NativeDropdown
      kicker="In the Lens"
      label="Pick a lens…"
      value={value}
      options={options}
      onChange={onChange}
      testid="lens-mode-dropdown"
    />
  );
}

function KindDropdown({ value, onChange }) {
  return (
    <NativeDropdown
      kicker="Test us"
      label="Pick what you're testing…"
      value={value}
      options={KIND_OPTIONS}
      onChange={onChange}
      testid="lens-kind-dropdown"
    />
  );
}

function CoachCanvas({ activeSession, onSend, onArchive, input, setInput, sending, activeLens, messagesEndRef }) {
  if (!activeSession) {
    return (
      <div className="bg-white border border-dashed border-[var(--rule)] rounded-md p-8 text-center" data-testid="coach-empty">
        <MessageCircle className="w-7 h-7 text-[var(--muted)]/40 mx-auto mb-3" strokeWidth={1.2} />
        <p className="akki-serif text-[15.5px] text-[var(--ink)] mb-2 max-w-md mx-auto leading-snug">
          Type your topic above. Apply starts the conversation through <strong>{activeLens?.name || "the chosen lens"}</strong>.
        </p>
        <p className="text-[11.5px] text-[var(--muted)] italic">
          Switch lenses any time using the dropdown to reframe the next reply.
        </p>
      </div>
    );
  }

  const messages = activeSession.messages || [];

  return (
    <div className="bg-white border border-[var(--rule)] rounded-md flex flex-col" style={{ minHeight: "55vh" }} data-testid="coach-thread">
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
        <p className="akki-serif text-[14.5px] leading-[1.65] text-[var(--ink)] whitespace-pre-wrap">{m.content}</p>
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
    <section className={`bg-white border border-[var(--rule)] rounded-md p-5 relative`}>
      {accent && <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)] rounded-l-md" />}
      <p className="akki-overline mb-2">{label}</p>
      <p className="akki-serif text-[14.5px] leading-[1.7] text-[var(--deep)]">{body}</p>
    </section>
  );
}

function EmptyHelp({ activeLens, kindCfg }) {
  return (
    <div className="bg-white border border-dashed border-[var(--rule)] rounded-md p-8 text-center" data-testid="lens-empty-help">
      <Eye className="w-8 h-8 text-[var(--muted)]/40 mx-auto mb-3" strokeWidth={1.2} />
      <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug max-w-md mx-auto mb-2">
        Ready when you are.
      </p>
      <p className="text-[12.5px] text-[var(--muted)] leading-relaxed max-w-md mx-auto">
        Drop your {kindCfg.id} above. Apply runs it through {activeLens?.name || "the lens"} and returns Observation → Implication → Action plus the single question for management.
      </p>
    </div>
  );
}
