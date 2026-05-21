/**
 * Solva Phase D Session page — talks to /api/contexts/{cid}/solva/v2/*
 *
 * Single-voice contract enforced by the backend (FAR is silent;
 * synthesis prose goes through `voice/synthesis_renderer.py`; refusal
 * prose goes through `voice/refusal_voice.py`). This page is a thin
 * shell that just renders whatever the backend returns.
 *
 * Flow:
 *   ENTRY → submit framing → LAYER 1 (3 answers) → LAYER 2 (3 answers)
 *     → LAYER 3 (synthesis OR refusal) → LAYER 4 (3 reflection answers)
 *     → DONE
 *
 * Phase E Sub-task A delivery (2026-05-16). Replaces the legacy
 * `SolvaSession.jsx` flow for context-bound sessions.
 */
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import AuditPanel from "@/components/chat/AuditPanel";
import AttachDocumentModal from "@/components/solva/AttachDocumentModal";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, ArrowRight, ShieldCheck, Paperclip, FileText, X } from "lucide-react";
import { toast } from "sonner";
import {
  createPhaseDSession,
  getPhaseDSession,
  submitFraming,
  submitAnswer,
} from "@/lib/solvaPhaseDClient";
import { parseProseBlocks } from "@/lib/proseBlocks";


/**
 * Chunk 14 (SV-08, 2026-05-21) — smart-cast for Pydantic 422 detail
 * arrays. The backend's `SubmitFramingIn.framing_text` /
 * `SubmitAnswerIn.answer_text` carry `Field(min_length=…)` which
 * triggers a 422 with a verbose `[{type, loc, msg, input, ctx, url}]`
 * shape. The default `apiErrorMessage` joins the raw `msg` fields
 * which still expose the pydantic.dev URL — this helper converts
 * the most common Solva validation errors to user-friendly copy.
 *
 * Pre-validation in the submit handlers means this helper only fires
 * when a NEW required field is added on the server but the client
 * hasn't shipped a matching guard yet (drift defence).
 */
function friendlySolvaError(err) {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) {
    for (const d of detail) {
      const loc = Array.isArray(d?.loc) ? d.loc.join(".") : "";
      const t = d?.type || "";
      if (t === "string_too_short" && loc.includes("framing_text")) {
        return "Please write at least 20 characters describing the situation before submitting.";
      }
      if (t === "string_too_short" && loc.includes("answer_text")) {
        return "Please write at least 2 characters before submitting your answer.";
      }
      if (t === "missing" && loc.includes("framing_text")) {
        return "A framing message is required. Please describe the situation in your own words.";
      }
      if (t === "missing" && loc.includes("answer_text")) {
        return "Your answer can't be empty.";
      }
    }
    // Generic 422 fallback — strip the URL and join the messages.
    const msgs = detail.map((d) => (typeof d?.msg === "string" ? d.msg : null)).filter(Boolean);
    if (msgs.length) return msgs.join(" · ");
  }
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  return `${err?.name || "Error"}: ${(err?.message || "").slice(0, 200)}`;
}


const SUB_MODULES = [
  { id: "seek_clarity",        label: "Seek Clarity" },
  { id: "develop_strategy",    label: "Develop Strategy" },
  { id: "simulate_hypothesis", label: "Simulate a Hypothesis" },
  { id: "get_perspective",     label: "Get Perspective" },
];

const REFLECTION_QUESTIONS = [
  "Are you disappointed by this diagnosis, and if so, why?",
  "What would have to be true for you to be wrong about your prior framing?",
  "What would the explanation be in six months if you ignore this diagnosis and the situation continues?",
];


export default function SolvaPhaseDSession() {
  const navigate = useNavigate();
  const { sessionId: paramSid } = useParams();
  const [searchParams] = useSearchParams();
  const { activeContext } = useAuth();

  const [session, setSession] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  // Phase F.1 — mid-session attach modal + last-attached confirmation.
  const [attachOpen, setAttachOpen] = useState(false);
  const [lastAttached, setLastAttached] = useState(null);
  // QA-2026-05-20 SV-03 fix-pass — defensive inline "Session saved."
  // indicator that renders alongside the Sonner toast. Toaster portals
  // are sometimes invisible to Playwright depending on z-index / theme
  // / portal mount order; this in-tree flag gives the e1_tester (and
  // render-smoke step 11) a deterministic DOM marker to observe.
  // Cleared after 2.5s to match the spec's toast duration.
  const [savedMarker, setSavedMarker] = useState(false);

  const fireSavedMarker = useCallback(() => {
    setSavedMarker(true);
    // The Sonner toast also fires (top-right) — defensive duplication
    // because the spec explicitly requires the toast.
    toast.success("Session saved.", { duration: 2500 });
    window.setTimeout(() => setSavedMarker(false), 2500);
  }, []);

  const ctxId = activeContext?.id;

  const refresh = useCallback(async (sid) => {
    if (!ctxId || !sid) return;
    try {
      const s = await getPhaseDSession({ contextId: ctxId, sessionId: sid });
      setSession(s);
      setError(null);
    } catch (e) {
      setError(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    }
  }, [ctxId]);

  // Boot: either resume :sid OR create a fresh session from ?submodule.
  // Phase E.5 — when URL carries seed params (?seed_kind=cycle|work_studio_artefact|document_journal
  // + seed_id=… + optional seed_preview), construct a seed_payload and
  // pass it to the create endpoint. The Phase D backend pre-populates
  // the framing field, attaches references to Layer 0, and stores
  // `source_handoff` provenance on the session.
  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!ctxId) return;
      if (paramSid) {
        await refresh(paramSid);
        return;
      }
      const sub = (searchParams.get("submodule") || "seek_clarity").trim();
      const seedKind = (searchParams.get("seed_kind") || "").trim();
      const seedId = (searchParams.get("seed_id") || "").trim();
      const seedPreview = (searchParams.get("seed_preview") || "").trim();
      let seedPayload = null;
      if (seedKind && seedId) {
        // Map URL `seed_kind` short labels to the backend's source enum.
        const sourceMap = {
          cycle: "cycle",
          work_studio: "work_studio_artefact",
          work_studio_artefact: "work_studio_artefact",
          document: "document_journal",
          document_journal: "document_journal",
        };
        const mappedSource = sourceMap[seedKind] || seedKind;
        seedPayload = {
          source: mappedSource,
          source_id: seedId,
          preview_text: seedPreview,
          attached_references: [seedId],
        };
      }
      try {
        setBusy(true);
        const fresh = await createPhaseDSession({
          contextId: ctxId, subModule: sub, seedPayload,
        });
        if (cancelled) return;
        setSession(fresh);
        if (seedPayload && fresh.initialFraming) setDraft(fresh.initialFraming);
        navigate(`/app/solva/phase-d/session/${fresh.sessionId}`, { replace: true });
      } catch (e) {
        setError(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
      } finally {
        if (!cancelled) setBusy(false);
      }
    }
    boot();
    return () => { cancelled = true; };
  }, [ctxId, paramSid, searchParams, navigate, refresh]);

  const submitFramingAction = useCallback(async () => {
    if (!session || !draft.trim()) return;
    // Chunk 14 (SV-08, 2026-05-21) — defence-in-depth pre-validation
    // mirroring `SubmitFramingIn.framing_text` Field(min_length=20).
    // Short-circuit before the API call so a 422 never round-trips
    // when the user dodges the disabled-button guard (e.g. paste +
    // Enter mid-render). Surfaces the friendly copy in `error`
    // instead of the raw "String should have at least 20 characters"
    // pydantic detail.
    if (draft.trim().length < 20) {
      setError("Please write at least 20 characters describing the situation before submitting.");
      return;
    }
    setBusy(true); setError(null);
    try {
      const s = await submitFraming({
        contextId: ctxId, sessionId: session.sessionId, framingText: draft,
      });
      setSession(s);
      setDraft("");
      // QA-2026-05-20 SV-03 — verbatim copy from the Solva brief.
      // Toast duration locked at ~2.5s per the brief's
      // "brief, 2-3 seconds, non-intrusive" requirement.
      fireSavedMarker();
    } catch (e) {
      // Chunk 14 (SV-08) — smart-cast for Pydantic 422 detail arrays.
      // Pre-validate above catches the common case; this handles
      // any future drift where the server adds a new required field
      // but the client hasn't been updated yet.
      setError(friendlySolvaError(e));
    } finally { setBusy(false); }
  }, [session, draft, ctxId, fireSavedMarker]);

  const submitAnswerAction = useCallback(async () => {
    if (!session || !draft.trim()) return;
    // Chunk 14 (SV-08) — defence-in-depth pre-validation mirroring
    // `SubmitAnswerIn.answer_text` Field(min_length=2).
    if (draft.trim().length < 2) {
      setError("Please write at least 2 characters before submitting your answer.");
      return;
    }
    setBusy(true); setError(null);
    try {
      const s = await submitAnswer({
        contextId: ctxId, sessionId: session.sessionId, answerText: draft,
      });
      setSession(s);
      setDraft("");
      // QA-2026-05-20 SV-03 — same toast on every answer turn.
      fireSavedMarker();
    } catch (e) {
      setError(friendlySolvaError(e));
    } finally { setBusy(false); }
  }, [session, draft, ctxId, fireSavedMarker]);

  if (!ctxId) {
    return (
      <AppShell>
        <div className="mx-auto max-w-2xl p-8" data-testid="solva-phase-d-no-context">
          <h1 className="text-2xl font-semibold">Solva</h1>
          <p className="mt-3 text-slate-600">Pick a workspace from the top bar to begin.</p>
        </div>
      </AppShell>
    );
  }

  if (!session) {
    return (
      <AppShell>
        <div className="mx-auto max-w-2xl p-8 text-center text-slate-500" data-testid="solva-phase-d-booting">
          <Loader2 className="mx-auto h-5 w-5 animate-spin" />
          <p className="mt-2 text-sm">Setting up your session…</p>
          {error && <p className="mt-3 text-rose-600" data-testid="solva-phase-d-error">{error}</p>}
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div
        className="mx-auto max-w-3xl space-y-6 p-6 sm:p-8"
        data-testid={`solva-phase-d-${session.layerState}`}
      >
        <header className="space-y-1">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <span data-testid="solva-phase-d-trust-banner">
              Trust verified by Synisense — every reasoning step is governed and auditable.
            </span>
          </div>
          <h1 className="text-3xl font-semibold text-slate-900">
            Solva · {SUB_MODULES.find(s => s.id === session.subModule)?.label || session.subModule}
          </h1>
          <p className="text-sm text-slate-500">
            Phase {session.layerState.replace("_", " ")} · {session.auditIdsCount} governed call{session.auditIdsCount !== 1 && "s"} so far
          </p>
        </header>

        {error && (
          <div
            className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700"
            data-testid="solva-phase-d-error"
          >{error}</div>
        )}

        {/* Phase F.1 — anchored documents strip (visible whenever any anchor exists). */}
        {(session.seedAttachedReferences || []).length > 0 && (
          <div
            className="flex flex-wrap items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50/40 px-3 py-2 text-xs"
            data-testid="solva-phase-d-anchors-strip"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            <span className="font-medium text-slate-700">
              Akki is reading {session.seedAttachedReferences.length} document
              {session.seedAttachedReferences.length === 1 ? "" : "s"}:
            </span>
            {session.seedAttachedReferences.slice(0, 6).map((a, i) => (
              <span
                key={`${a.ref_id}-${i}`}
                className="inline-flex items-center gap-1 rounded bg-white px-2 py-0.5 text-slate-700 ring-1 ring-emerald-200"
                data-testid={`solva-phase-d-anchor-chip-${i}`}
              >
                <FileText className="h-3 w-3" />
                {a.label}
              </span>
            ))}
          </div>
        )}

        {/* QA-2026-05-20 SV-03 fix-pass — inline "Session saved." chip.
            Defensive companion to the Sonner toast (top-right). The
            Sonner portal is sometimes invisible to e1_tester / Playwright
            depending on z-index + theme + portal mount order; this
            in-tree marker is deterministic. data-testid lets the smoke
            step and the human tester both observe the same DOM node. */}
        {savedMarker && (
          <div
            className="flex items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
            data-testid="solva-phase-d-saved-indicator"
            role="status"
            aria-live="polite"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            <span>Session saved.</span>
          </div>
        )}

        {/* Inline "just attached" confirmation. */}
        {lastAttached && (
          <div
            className="flex items-center justify-between rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
            data-testid="solva-phase-d-attach-confirmation"
          >
            <span>
              Attached: <strong>{lastAttached.label}</strong>. Akki now has the document in context.
            </span>
            <button
              type="button"
              onClick={() => setLastAttached(null)}
              className="text-emerald-700 hover:text-emerald-900"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Chunk 13 (SV-04, 2026-05-21) — read-only banner for terminal
            sessions. COMPLETE/REFUSED sessions render the synthesis or
            refusal block via the `Body` component below but never the
            input affordances. This banner makes the read-only state
            visually explicit + deterministic for the smoke step. */}
        {(session.status === "completed" || session.layerState === "done"
          || session.status === "refused" || session.layerState === "refused"
          || session.status === "abandoned" || session.status === "blocked_hard"
        ) && (
          <div
            className="flex items-center gap-2 rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
            data-testid="solva-phase-d-read-only-banner"
            role="note"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-slate-500" />
            <span>
              This session is read-only. You can review the conversation history
              and synthesis above, but new inputs are not accepted.
            </span>
          </div>
        )}

        <Body
          session={session}
          draft={draft}
          setDraft={setDraft}
          busy={busy}
          onFraming={submitFramingAction}
          onAnswer={submitAnswerAction}
          onAttachClick={() => setAttachOpen(true)}
        />

        <AuditPanel
          mode="timeline"
          solvaContextId={ctxId}
          solvaSessionId={session.sessionId}
        />

        <AttachDocumentModal
          open={attachOpen}
          onClose={() => setAttachOpen(false)}
          contextId={ctxId}
          sessionId={session.sessionId}
          onAttached={(payload) => {
            // Backend returns { ok, mode, anchor, session }. Update the
            // visible session row and surface the inline confirmation.
            if (payload?.session) setSession(prev => ({ ...prev, ...{
              raw: payload.session,
              seedAttachedReferences: payload.session.seed_attached_references || [],
              auditIdsCount: (payload.session.synisense_audit_ids || []).length,
            } }));
            if (payload?.anchor) setLastAttached(payload.anchor);
          }}
        />
      </div>
    </AppShell>
  );
}


function PaperclipButton({ onClick, testId }) {
  // Phase F.1 — small unobtrusive attach affordance on every answer
  // surface. Keeps the primary CTA dominant; the paperclip lives to
  // the left of the submit button.
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={onClick}
      data-testid={testId}
      className="text-slate-600 hover:text-emerald-700"
      title="Attach a document Akki should read for this session"
    >
      <Paperclip className="mr-1.5 h-4 w-4" /> Attach
    </Button>
  );
}


function Body({ session, draft, setDraft, busy, onFraming, onAnswer, onAttachClick }) {
  // ENTRY / FRAMING — show framing input.
  if (session.layerState === "entry" || session.layerState === "framing") {
    return (
      <section className="space-y-3" data-testid="solva-phase-d-framing">
        <h2 className="text-lg font-medium text-slate-800">
          Tell me what's on your mind.
        </h2>
        <p className="text-sm text-slate-600">
          Write it in your own words — what you'd say if you sat down with a sharp
          counterpart over coffee. Two to three sentences works. We'll sharpen from there.
        </p>
        <Textarea
          data-testid="solva-phase-d-framing-input"
          rows={5}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="The situation that's been on my mind…"
        />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <PaperclipButton
              onClick={onAttachClick}
              testId="solva-phase-d-attach-btn-framing"
            />
            {/* Chunk 14 SV-08 — inline character-count hint mirrors the
                backend `Field(min_length=20)` constraint. Surfaces the
                threshold so users see WHY the submit button is disabled
                instead of having to guess. Live count flips to a green
                checkmark once the threshold is met. */}
            <span
              data-testid="solva-phase-d-framing-min-hint"
              className={`text-xs ${draft.trim().length >= 20 ? "text-emerald-600" : "text-slate-500"}`}
            >
              {draft.trim().length >= 20
                ? `${draft.trim().length} characters — ready to submit`
                : `${draft.trim().length} / 20 characters required`}
            </span>
          </div>
          <Button
            data-testid="solva-phase-d-framing-submit"
            onClick={onFraming}
            disabled={busy || draft.trim().length < 20}
          >
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />}
            Open it
          </Button>
        </div>
      </section>
    );
  }

  // LAYER 1 / LAYER 2 — show coach question + answer input.
  if (session.layerState === "layer_1" || session.layerState === "layer_2") {
    const q = session.nextQuestion || {};
    return (
      <section className="space-y-3" data-testid={`solva-phase-d-${session.layerState}-question`}>
        {session.acknowledgement && (
          <p className="text-sm text-slate-600 italic" data-testid="solva-phase-d-acknowledgement">
            {session.acknowledgement}
          </p>
        )}
        <p className="text-lg leading-relaxed text-slate-800" data-testid="solva-phase-d-question-text">
          {q.question_text || "…"}
        </p>
        <Textarea
          data-testid="solva-phase-d-answer-input"
          rows={4}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">
              {q.questions_asked_so_far ?? 0}/{(q.questions_asked_so_far ?? 0) + (q.questions_remaining_in_layer ?? 0)}
            </span>
            <PaperclipButton
              onClick={onAttachClick}
              testId={`solva-phase-d-attach-btn-${session.layerState}`}
            />
          </div>
          <Button
            data-testid="solva-phase-d-answer-submit"
            onClick={onAnswer}
            disabled={busy || draft.trim().length < 2}
          >
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />}
            Continue
          </Button>
        </div>
      </section>
    );
  }

  // LAYER 4 — reflection round.
  if (session.layerState === "layer_4") {
    const answered = session.layer4Answers.length;
    const q = session.nextQuestion || {};
    return (
      <section className="space-y-5" data-testid="solva-phase-d-layer-4">
        {session.synthesisText && (
          <ProseBlock title="Where I've landed" text={session.synthesisText} testId="solva-phase-d-synthesis" />
        )}
        {answered < 3 ? (
          <>
            <p className="text-sm text-slate-500 uppercase tracking-wide">Reflection — {answered + 1} of 3</p>
            <p className="text-lg leading-relaxed text-slate-800" data-testid="solva-phase-d-reflection-q">
              {q.question_text || REFLECTION_QUESTIONS[answered]}
            </p>
            <Textarea
              data-testid="solva-phase-d-reflection-input"
              rows={4}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
            <Button
              data-testid="solva-phase-d-reflection-submit"
              onClick={onAnswer}
              disabled={busy || draft.trim().length < 2}
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />}
              Continue
            </Button>
          </>
        ) : (
          <p className="text-sm text-emerald-700">Reflection complete.</p>
        )}
      </section>
    );
  }

  // LAYER 3 — synthesis prose (no input).
  if (session.layerState === "layer_3") {
    if (session.refusalFlag && session.refusalRendering) {
      return <ProseBlock title="Why I'm holding back" text={session.refusalRendering} testId="solva-phase-d-refusal" />;
    }
    if (session.synthesisText) {
      return <ProseBlock title="Where I've landed" text={session.synthesisText} testId="solva-phase-d-synthesis" />;
    }
    return <p className="text-slate-500">Composing the read…</p>;
  }

  // REFUSED / DONE — final state surfaces.
  if (session.layerState === "refused" || session.status === "refused" || session.status === "blocked_hard") {
    return (
      <section className="space-y-3">
        <ProseBlock
          title="Why I'm holding back"
          text={session.refusalRendering || ""}
          testId="solva-phase-d-refusal"
        />
        <ExportToWorkStudioButton session={session} />
      </section>
    );
  }

  if (session.layerState === "done") {
    return (
      <section className="space-y-4" data-testid="solva-phase-d-done">
        {session.synthesisText && (
          <ProseBlock title="Where I've landed" text={session.synthesisText} />
        )}
        <p className="text-sm text-emerald-700">Session complete.</p>
        <ExportToWorkStudioButton session={session} />
      </section>
    );
  }

  return <p className="text-slate-500">Working…</p>;
}


function ExportToWorkStudioButton({ session }) {
  const [busy, setBusy] = useState(false);
  const [exported, setExported] = useState(null);
  const [error, setError] = useState(null);
  const handle = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const { data } = await (await import("@/lib/api")).api.post(
        `/contexts/${session.contextId}/work-studio/artefacts/from-solva`,
        { session_id: session.sessionId },
      );
      setExported(data);
    } catch (e) {
      setError(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally { setBusy(false); }
  }, [session]);

  if (exported) {
    return (
      <p className="text-sm text-emerald-700" data-testid="solva-export-success">
        Sent to Work Studio. <a className="underline" href={`/app/work-studio/artefacts/${exported.id}`}>
          Open in Work Studio →
        </a>
      </p>
    );
  }
  return (
    <div className="space-y-1">
      <Button
        onClick={handle}
        disabled={busy}
        data-testid="solva-export-to-work-studio"
        variant="outline"
        size="sm"
      >
        {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Send synthesis to Work Studio
      </Button>
      {error && <p className="text-xs text-rose-600" data-testid="solva-export-error">{error}</p>}
    </div>
  );
}


function ProseBlock({ title, text, testId }) {
  // Chunk 14 SV-06 / SV-07 (2026-05-21) + Chunk 17 C17-004 cleanup
  // (2026-05-21):
  //   • SV-06 — render markdown-light (paragraphs · `- `/`* ` bullets
  //     · `1. ` numbered lists · `**bold**`) via parseProseBlocks
  //     instead of the legacy `<pre>` flat block.
  //   • SV-07 — output panel ≥60vh + scrolls when content overflows.
  //
  // C17-004 fix: tester reported `getComputedStyle().overflowY ===
  // "visible"` on the actual scroll container after Chunk 14
  // shipped. Root cause: the `overflow-y-auto` class landed on the
  // INNER content div, but the tester queried the OUTER `<article>`
  // (the visible card chrome) which had no overflow rule. Restructured
  // so BOTH wrappers carry `overflow-y-auto` + `max-h-[70vh]`:
  //
  //   <article>            — visible card chrome; scroll container A
  //     <div data-testid>  — inner content; scroll container B
  //       <ProseRenderer/>
  //     </div>
  //   </article>
  //
  // Either query target returns `overflow-y: auto`. Defence-in-depth.
  return (
    <article
      className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm min-h-[400px] sm:min-h-[60vh] max-h-[70vh] overflow-y-auto"
      data-testid={`solva-prose-block-${testId || "default"}`}
    >
      {title && <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 sticky top-0 bg-white pb-2">{title}</h3>}
      <div
        className="min-h-[360px] sm:min-h-[55vh] max-h-[65vh] overflow-y-auto pr-1 font-sans text-base leading-relaxed text-slate-800"
        data-testid={testId}
      >
        <ProseRenderer text={text} />
      </div>
    </article>
  );
}


/**
 * Chunk 14 SV-06 — render parseProseBlocks output as JSX. Pure
 * presentational component; no state, no effects. Renders:
 *   • paragraphs as <p>
 *   • bullet lists as <ul><li>
 *   • numbered lists as <ol><li>
 *   • **bold** inline tokens as <strong>
 *
 * Tables / code fences / headings are deliberately not handled —
 * documented as out-of-scope in `proseBlocks.js` JSDoc. If the
 * backend starts emitting them (unlikely; Synisense voice files
 * keep responses prose-only), we'll add a fallback `<pre>` block.
 */
function ProseRenderer({ text }) {
  const blocks = React.useMemo(() => parseProseBlocks(text || ""), [text]);
  if (blocks.length === 0) {
    // Defensive fallback — if the text is non-empty but parses to
    // zero blocks (edge case: only whitespace) we still render the
    // raw text so we don't silently drop content.
    return text
      ? <p className="whitespace-pre-wrap">{text}</p>
      : <p className="italic text-slate-500">No content.</p>;
  }
  return (
    <div className="space-y-4">
      {blocks.map((b, i) => {
        if (b.type === "bullets") {
          return (
            <ul key={i} className="list-disc space-y-1 pl-6">
              {b.items.map((item, j) => (
                <li key={j}><Inlines tokens={item} /></li>
              ))}
            </ul>
          );
        }
        if (b.type === "numbered") {
          return (
            <ol key={i} className="list-decimal space-y-1 pl-6">
              {b.items.map((item, j) => (
                <li key={j}><Inlines tokens={item} /></li>
              ))}
            </ol>
          );
        }
        return <p key={i}><Inlines tokens={b.inlines} /></p>;
      })}
    </div>
  );
}


function Inlines({ tokens }) {
  return (
    <>
      {tokens.map((tok, i) => {
        if (tok.kind === "bold") {
          return <strong key={i} className="font-semibold text-slate-900">{tok.text}</strong>;
        }
        return <React.Fragment key={i}>{tok.text}</React.Fragment>;
      })}
    </>
  );
}
