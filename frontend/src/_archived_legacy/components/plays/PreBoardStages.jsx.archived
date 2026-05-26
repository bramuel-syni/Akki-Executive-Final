import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  ArrowRight, Sparkles, Loader2, FileText, BookOpen, MessageCircleQuestion, Printer,
} from "lucide-react";

/**
 * PreBoardStages — five stages of the NED's Pre-Board Play.
 *
 * Composes existing surfaces (Document Journal for the pack, Workspace
 * for thinking, Briefings for outputs) plus a thin LLM helper at
 * /pre_board/read that produces reading notes + standouts.
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

function ObservationLead({ headline, body }) {
  return (
    <header className="mb-8 max-w-2xl">
      <h2 className="akki-serif text-[28px] text-[var(--ink)] leading-tight mb-3">{headline}</h2>
      {body && <p className="akki-serif text-[15px] text-[var(--deep)] leading-relaxed italic">{body}</p>}
    </header>
  );
}

// ---------------------------------------------------------------------------
// Stage 0 — When the pack arrives
// ---------------------------------------------------------------------------
function StageArrival({ play, contextId, onAdvance, onPatchState }) {
  const [pack, setPack] = useState(play.state?.pack_text_excerpt || "");
  const [reading, setReading] = useState(false);

  const onRead = async () => {
    if (pack.trim().length < 200) {
      toast.message("Paste at least a couple of paragraphs of the pack.");
      return;
    }
    setReading(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/plays/${play.id}/pre_board/read`,
        { pack_text: pack },
        { timeout: 120000 },
      );
      // The endpoint already merged state; advance straight to "Reading the pack"
      onAdvance();
      toast.success("AKKI's read is ready.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setReading(false); }
  };

  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="Pull in the pack."
            body="Paste the body or the executive summary. AKKI keeps it on this Play; nothing leaves your account."
          />
          <textarea
            value={pack}
            onChange={(e) => setPack(e.target.value)}
            rows={16}
            placeholder="Paste the pack here…"
            className="w-full text-[14px] font-mono leading-relaxed bg-white border border-[var(--rule)] rounded-md p-4 focus:outline-none focus:border-[var(--accent)] mb-4 max-w-2xl"
            data-testid="preboard-pack-textarea"
          />
          <div className="flex items-center gap-3">
            <Button onClick={onRead} disabled={reading} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="preboard-read-btn">
              {reading
                ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Reading…</>
                : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Read it through</>}
            </Button>
            <Link to="/app/workspace" className="text-[12.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1">
              <FileText className="w-3 h-3" /> Or pick from Document Journal
            </Link>
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">What AKKI does here</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-3">
            Reads it once, the way a chair would. Writes a few observational notes
            and pulls out three or four things that deserve your attention.
          </p>
          <p className="text-[11.5px] text-[var(--muted)] italic leading-relaxed">
            No analysis runs against external systems. The pack stays in this Play.
          </p>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 1 — Reading the pack
// ---------------------------------------------------------------------------
function StageReading({ play, onAdvance }) {
  const notes = play.state?.reading_notes || [];
  const wc = play.state?.pack_word_count;
  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="A first read, kept brief."
            body="Five short observations. Take them in once before deciding what stands out."
          />
          {notes.length === 0 ? (
            <p className="text-[13px] text-[var(--muted)] italic">No notes yet — go back and have AKKI read the pack first.</p>
          ) : (
            <ol className="space-y-3 max-w-2xl mb-6 list-none counter-reset-akki" data-testid="preboard-notes">
              {notes.map((n, i) => (
                <li key={i} className="text-[14.5px] akki-serif text-[var(--ink)] leading-relaxed flex gap-3" data-testid={`preboard-note-${i}`}>
                  <span className="text-[var(--accent)] font-mono text-[12px] mt-1.5">—</span>
                  <span>{n}</span>
                </li>
              ))}
            </ol>
          )}
          <Button onClick={onAdvance} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-advance-btn">
            Move to what stands out <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Working set</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed">
            <strong>{wc ?? "—"}</strong> words read.
            {notes.length > 0 && <> AKKI surfaced <strong>{notes.length}</strong> notes and is ready with the standouts when you are.</>}
          </p>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 2 — What stands out
// ---------------------------------------------------------------------------
function StageStandouts({ play, onAdvance }) {
  const standouts = play.state?.standouts || [];
  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="What deserves your attention."
            body="AKKI's read on what the chair should not let pass without comment."
          />
          {standouts.length === 0 ? (
            <p className="text-[13px] text-[var(--muted)] italic">Nothing surfaced — this might be a quiet pack, or AKKI didn't find structured signals.</p>
          ) : (
            <ul className="space-y-5 max-w-2xl mb-8" data-testid="preboard-standouts">
              {standouts.map((s, i) => (
                <li key={i} className="border-l-2 border-[var(--accent)] pl-5" data-testid={`preboard-standout-${i}`}>
                  <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-1">{s.label}</p>
                  <p className="text-[15px] akki-serif text-[var(--ink)] leading-snug mb-1">{s.detail}</p>
                  <p className="text-[12.5px] text-[var(--muted)] italic">{s.why}</p>
                </li>
              ))}
            </ul>
          )}
          <Button onClick={onAdvance} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-advance-btn">
            Frame your questions <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Why this matters</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed">
            A NED's value at the table is in not letting the room move past
            something it should challenge. Pick one, two — or all of these — to
            bring into the meeting.
          </p>
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 3 — Your questions and challenges
// ---------------------------------------------------------------------------
function StageQuestions({ play, contextId, onAdvance, onPatchState }) {
  const [questions, setQuestions] = useState(play.state?.questions || "");
  const [saving, setSaving] = useState(false);

  const onSave = async () => {
    setSaving(true);
    try {
      await onPatchState({ questions });
      toast.success("Saved.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSaving(false); }
  };

  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="What you'll ask. What you'll push back on."
            body="Write the questions you intend to bring into the meeting. AKKI keeps them on the play; you take them in."
          />
          <textarea
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            rows={14}
            placeholder={"e.g. On the credit-quality slide — what's driving the divergence between disclosed NPL and the leading indicators?"}
            className="w-full text-[14.5px] font-mono leading-relaxed bg-white border border-[var(--rule)] rounded-md p-4 focus:outline-none focus:border-[var(--accent)] mb-4 max-w-2xl"
            data-testid="preboard-questions-textarea"
          />
          <div className="flex items-center gap-3">
            <Button onClick={onSave} disabled={saving} variant="outline" className="border-[var(--rule)]" data-testid="preboard-save-questions">
              {saving ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Saving…</> : <>Save</>}
            </Button>
            <Button onClick={onAdvance} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="stage-advance-btn">
              Take it into the room <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Standouts to draw on</p>
          {(play.state?.standouts || []).length === 0 ? (
            <p className="text-[13px] text-[var(--muted)] italic">No standouts saved on this play.</p>
          ) : (
            <ul className="space-y-3 text-[13px] text-[var(--deep)]">
              {(play.state.standouts || []).map((s, i) => (
                <li key={i}>
                  <strong className="text-[var(--ink)]">{s.label}.</strong> {s.detail}
                </li>
              ))}
            </ul>
          )}
        </>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Stage 4 — Walking in
// ---------------------------------------------------------------------------
function StageWalkingIn({ play }) {
  const standouts = play.state?.standouts || [];
  const notes = play.state?.reading_notes || [];
  const questions = play.state?.questions || "";

  const onPrint = () => window.print();

  return (
    <StageFrame
      left={
        <>
          <ObservationLead
            headline="Your one-page brief."
            body="Print it, screenshot it, or just keep this tab open beside you."
          />
          <article className="bg-white border border-[var(--rule)] rounded-md p-7 max-w-2xl shadow-[0_2px_24px_-12px_rgba(0,0,0,0.15)]" data-testid="preboard-brief">
            <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-2">Pre-Board Brief</p>
            <h3 className="akki-serif text-[20px] text-[var(--ink)] mb-4">{play.state?.cycle_name || "Board meeting"}</h3>

            {standouts.length > 0 && (
              <section className="mb-5">
                <p className="akki-overline mb-2">What deserves attention</p>
                <ul className="space-y-2 text-[13px] text-[var(--deep)]">
                  {standouts.map((s, i) => (
                    <li key={i}><strong className="text-[var(--ink)]">{s.label}.</strong> {s.detail}</li>
                  ))}
                </ul>
              </section>
            )}

            {notes.length > 0 && (
              <section className="mb-5">
                <p className="akki-overline mb-2">First read</p>
                <ol className="space-y-1 text-[13px] text-[var(--deep)]">
                  {notes.slice(0, 5).map((n, i) => <li key={i}>— {n}</li>)}
                </ol>
              </section>
            )}

            {questions.trim() && (
              <section>
                <p className="akki-overline mb-2">Your questions</p>
                <p className="text-[13px] text-[var(--deep)] whitespace-pre-wrap leading-relaxed">{questions}</p>
              </section>
            )}
          </article>

          <div className="flex gap-2 mt-5">
            <Button onClick={onPrint} variant="outline" className="border-[var(--rule)]" data-testid="preboard-print">
              <Printer className="w-3.5 h-3.5 mr-1.5" /> Print this page
            </Button>
            <Link to="/app" className="ml-auto text-[13px] text-[var(--accent)] hover:underline self-center" data-testid="preboard-home">
              Back to Home →
            </Link>
          </div>
        </>
      }
      right={
        <>
          <p className="akki-overline mb-3">Outcome</p>
          <p className="text-[13px] text-[var(--deep)] leading-relaxed italic">
            Walk into the meeting having read the pack the way a chair would.
          </p>
        </>
      }
    />
  );
}

export function preBoardStageView() {
  return [
    StageArrival,
    StageReading,
    StageStandouts,
    StageQuestions,
    StageWalkingIn,
  ];
}
