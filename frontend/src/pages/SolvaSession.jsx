/**
 * Solva Session — Phase I.2 page. Mounted at:
 *   /app/solva/session/new          → start a new session (submodule from query)
 *   /app/solva/session/:sessionId   → resume an existing session
 *
 * Renders the Guided Flow state machine and stitches together every
 * Phase I component:
 *   - LANDING is owned by SolvaApp / SolvaLanding (not this page)
 *   - FRAMING → POST /api/solva/v2/sessions (auto_cluster=true)
 *   - Q1..DEPTH_Q3 → POST /api/solva/v2/sessions/{sid}/turn
 *   - PREPARING is the synthesis-running interstitial; we wait on the
 *     final turn's response which carries either synthesis or refusal
 *   - ARTEFACT / ARTEFACT_REFUSAL → SolvaArtefact / SolvaRefusalArtefact
 *   - REFLECT_1..REFLECT_3 → POST /api/solva/v2/sessions/{sid}/turn (layer=reflection)
 *   - COMPLETE → return to artefact with a "Session saved" toast
 */
import React, { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import AppShell from "@/components/layout/AppShell";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

import {
  Actions,
  initialState,
  isFlowState,
  nextState,
  resumePoint,
} from "@/lib/solvaFlow";

import SolvaShell from "@/components/solva/flow/Shell";
import FramingScreen from "@/components/solva/flow/FramingScreen";
import QuestionScreen from "@/components/solva/flow/QuestionScreen";
import PreparingInterstitial from "@/components/solva/flow/PreparingInterstitial";
import ReflectionScreen from "@/components/solva/flow/ReflectionScreen";
import SolvaArtefact from "@/components/solva/artefact/SolvaArtefact";
import SolvaRefusalArtefact from "@/components/solva/artefact/SolvaRefusalArtefact";
// Wave 1.6 / 1.8 / 2.1 (UAT pack 2026-05-10)
import SolvaHeader from "@/components/solva/flow/SolvaHeader";
import TransitionMessage from "@/components/solva/flow/TransitionMessage";
import FrameAuditScreen from "@/components/solva/flow/FrameAuditScreen";
import { TOKEN, FONT } from "@/components/solva/flow/tokens";

const ROUND2_QUESTION_STATES = ["DEPTH_Q1", "DEPTH_Q2", "DEPTH_Q3"];

function backgroundForState(state) {
  if (ROUND2_QUESTION_STATES.includes(state)) return TOKEN.CREAM_DEEP;
  if (["Q1", "Q2", "Q3", "FRAMING"].includes(state)) return TOKEN.CREAM;
  if (["ARTEFACT", "ARTEFACT_REFUSAL"].includes(state)) return TOKEN.PAPER;
  return TOKEN.PAPER;
}

export default function SolvaSession() {
  const { sessionId: sidParam } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { account, activeContext } = useAuth();

  // Reducer init
  const submoduleQuery = searchParams.get("submodule");
  const personaQuery = searchParams.get("persona");
  // Wave 1.1 (UAT pack 2026-05-10) — intake_seed forwarded by the
  // SolvaApp picker via URL params. Captured once on mount; sent
  // with the framing POST when the user submits.
  const seedKindQuery = (searchParams.get("seed_kind") || "").trim();
  const seedIdQuery = (searchParams.get("seed_id") || "").trim();
  const intakeSeed = useMemo(
    () => (seedKindQuery && seedIdQuery ? { kind: seedKindQuery, id: seedIdQuery } : null),
    [seedKindQuery, seedIdQuery],
  );
  const [flow, dispatch] = useReducer(
    nextState,
    initialState({
      submodule: submoduleQuery || "seek_clarity",
      persona: personaQuery || null,
    }),
  );

  // Server session row (full doc; refreshed on every turn).
  const [session, setSession] = useState(null);
  const [busy, setBusy] = useState(false);

  // Per-screen drafts
  const [framingDraft, setFramingDraft] = useState("");
  const [answerDraft, setAnswerDraft] = useState("");
  const [reflectionDraft, setReflectionDraft] = useState("");
  const [savedToast, setSavedToast] = useState(false);
  const [resumed, setResumed] = useState(false);

  /* ----- BOOTSTRAP -----------------------------------------------------*/
  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!account) return;

      // /app/solva/session/new — start fresh: jump to FRAMING via PICK_SUBMODULE
      if (!sidParam || sidParam === "new") {
        dispatch(
          Actions.pickSubmodule(submoduleQuery || "seek_clarity", personaQuery || null),
        );
        // Phase F.2.A — when the user arrived via takeToSolva()
        // (URL params seed_kind + seed_id), pre-fill the framing
        // textarea with a seed excerpt fetched from the new
        // /api/solva/v2/seed endpoint. Editable; cursor naturally
        // sits at the end of the textarea so the user can append
        // their own framing context.
        if (seedKindQuery && seedIdQuery) {
          try {
            const { data } = await api.get("/solva/v2/seed", {
              params: { kind: seedKindQuery, id: seedIdQuery },
            });
            if (!cancelled && data?.seed_text) {
              setFramingDraft(data.seed_text);
            }
          } catch {
            // Honest-render: if the seed can't be fetched (404, scope
            // refusal, kind unsupported), leave the textarea empty —
            // the user will still see the FramingScreen with the
            // submodule pre-selected.
          }
        }
        return;
      }

      // Idempotency guard — when handleFramingSubmit calls
      // navigate(replace) after creating a session, this useEffect re-runs
      // with the new :sessionId param. We must NOT re-fetch and overwrite
      // local state in that case (which would bounce the user back to
      // FRAMING because the freshly-created server session has layer=framing
      // and zero user turns). Detect this by comparing the URL param to the
      // sessionId already attached in flow state.
      if (flow.sessionId && flow.sessionId === sidParam) return;

      // /app/solva/session/:sid — resume from server
      try {
        const res = await api.get(`/solva/v2/sessions/${sidParam}`);
        if (cancelled) return;
        const srv = res.data;
        setSession(srv);
        const snap = resumePoint(srv);
        dispatch(Actions.resume(snap));
        // Pre-fill drafts where applicable
        setFramingDraft(snap.framing || "");
        setResumed(true);
      } catch (err) {
        if (cancelled) return;
        const detail = err?.response?.data?.detail || err.message || "Failed to load session.";
        dispatch(Actions.setError(typeof detail === "string" ? detail : "Failed to load session."));
      }
    }
    init();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sidParam, account]);

  /* ----- HELPERS -------------------------------------------------------*/
  const refreshSession = useCallback(async (sid) => {
    if (!sid) return null;
    try {
      const res = await api.get(`/solva/v2/sessions/${sid}`);
      setSession(res.data);
      return res.data;
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message;
      dispatch(Actions.setError(typeof detail === "string" ? detail : "Failed to refresh session."));
      return null;
    }
  }, []);

  const lastSolvaTurnText = useMemo(() => {
    const turns = session?.turns || [];
    for (let i = turns.length - 1; i >= 0; i -= 1) {
      const t = turns[i];
      if (t?.role === "solva") {
        // Strip [T:tier] markers — those belong to the synthesis layer.
        return (t.text || "").replace(/\[T:[a-zA-Z_]+\]/g, "").trim();
      }
    }
    return "";
  }, [session]);

  /* ----- ACTIONS -------------------------------------------------------*/
  const handleFramingSubmit = useCallback(async () => {
    setBusy(true);
    try {
      const body = {
        intent: framingDraft.trim(),
        submodule: flow.submodule,
        auto_cluster: true,
      };
      if (flow.persona) body.persona = flow.persona;
      // Wave 1.1 — pass the seed pointer through to the backend so
      // _resolve_intake_seed can hydrate it server-side.
      if (intakeSeed) body.intake_seed = intakeSeed;
      const res = await api.post("/solva/v2/sessions", body);
      const srv = res.data;
      setSession(srv);
      dispatch(Actions.attachSession(srv.id));
      dispatch(Actions.submitFraming(framingDraft.trim()));
      // Wave 2.1 — kick off the deterministic Frame Audit immediately
      // after the session row exists. Fire-and-forget here; the Frame
      // Audit screen itself will GET the result. Failures are logged
      // but never block the framing-submit happy path.
      api.post(`/solva/v2/sessions/${srv.id}/frame-audit`).catch(() => {});
      // Replace the URL so reload resumes the session.
      navigate(`/app/solva/session/${srv.id}`, { replace: true });
    } catch (err) {
      // 2026-05-10 A.0 fix — the previous handler only kept `detail`
      // when it was a plain string, falling through to a generic
      // "Could not start session." for every object-shape detail
      // (which is what FastAPI returns for structured validation +
      // domain errors like `too_many_active_sessions`). That hid
      // actionable copy from the user. Surface the real message.
      const detail = err?.response?.data?.detail;
      let message = "Could not start session.";
      if (typeof detail === "string" && detail.trim()) {
        message = detail;
      } else if (detail && typeof detail === "object") {
        // FastAPI domain errors: { error, message, ...meta }.
        if (typeof detail.message === "string" && detail.message.trim()) {
          message = detail.message;
        } else if (typeof detail.error === "string") {
          // Pretty-print the error code (e.g. "too_many_active_sessions"
          // → "Too many active sessions"). Not pretty but actionable
          // and never blank.
          message = detail.error.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
        } else if (Array.isArray(detail) && detail[0]?.msg) {
          // Pydantic validation array.
          message = detail.map((d) => d.msg).filter(Boolean).join("; ") || message;
        }
      } else if (err?.message) {
        message = err.message;
      }
      dispatch(Actions.setError(message));
    } finally {
      setBusy(false);
    }
  }, [framingDraft, flow.submodule, flow.persona, navigate, intakeSeed]);

  const handleAnswerSubmit = useCallback(async () => {
    if (!flow.sessionId) return;
    setBusy(true);
    try {
      await api.post(`/solva/v2/sessions/${flow.sessionId}/turn`, {
        user_text: answerDraft.trim() || "(no further detail provided)",
      });
      const srv = await refreshSession(flow.sessionId);
      // Decide next state purely from the new state machine
      dispatch(Actions.answerQuestion(answerDraft));
      setAnswerDraft("");

      // After DEPTH_Q3 the flow lands on PREPARING. The orchestrator's
      // synthesis happens on a NEXT turn (when the user answers the
      // grounding round). For the v3 page we mirror the orchestrator by
      // firing one more turn for synthesis.
      if (flow.state === "DEPTH_Q3" && srv) {
        // immediately fire the synthesis turn
        try {
          await api.post(`/solva/v2/sessions/${flow.sessionId}/turn`, {
            user_text: "(continue to synthesis)",
          });
          const after = await refreshSession(flow.sessionId);
          const refusal = ["refused", "blocked_hard", "blocked_soft"].includes((after?.status || "").toLowerCase())
            || (after?.synthesis == null);
          dispatch(Actions.preparingDone(refusal));
        } catch (err2) {
          const detail = err2?.response?.data?.detail || err2.message;
          // 422 with grounding/opinion violation → treat as refusal artefact
          if (err2?.response?.status === 422) {
            dispatch(Actions.preparingDone(true));
          } else {
            dispatch(Actions.setError(typeof detail === "string" ? detail : "Synthesis failed."));
          }
        }
      }
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message;
      dispatch(Actions.setError(typeof detail === "string" ? detail : "Could not submit answer."));
    } finally {
      setBusy(false);
    }
  }, [flow.sessionId, flow.state, answerDraft, refreshSession]);

  const handleReflectionSubmit = useCallback(async (skipped) => {
    const text = skipped ? "" : reflectionDraft.trim();
    setBusy(true);
    try {
      if (flow.sessionId && !skipped && text) {
        try {
          await api.post(`/solva/v2/sessions/${flow.sessionId}/turn`, {
            user_text: text,
          });
          await refreshSession(flow.sessionId);
        } catch (_e) {
          // Non-fatal — we still record the reflection in client state.
        }
      }
      dispatch(Actions.answerReflection(text, !!skipped));
      setReflectionDraft("");

      // If the user just answered REFLECT_3, show the saved toast and
      // bounce to the artefact view per brief §6.3.
      if (flow.state === "REFLECT_3") {
        setSavedToast(true);
        setTimeout(() => setSavedToast(false), 1500);
        // Navigate state back to artefact for the user to revisit downloads.
        // The reducer landed us on COMPLETE; we override the state here
        // by dispatching a no-op snapshot that points back to artefact.
        dispatch(Actions.resume({
          ...flow,
          state: flow.refusal ? "ARTEFACT_REFUSAL" : "ARTEFACT",
          reflections: { ...flow.reflections, REFLECT_3: { text, skipped: !!skipped } },
        }));
      }
    } finally {
      setBusy(false);
    }
  }, [flow, reflectionDraft, refreshSession]);

  const handleBackToLanding = useCallback(() => {
    navigate("/app/solva");
  }, [navigate]);

  const handleGoBack = useCallback(() => {
    dispatch(Actions.goBack());
    setAnswerDraft("");
  }, []);

  const handleStartReflection = useCallback(() => {
    // Reducer transition from ARTEFACT → REFLECT_1 isn't an action; we
    // call resume() with the state override. This preserves answers /
    // reflections state.
    dispatch(Actions.resume({ ...flow, state: "REFLECT_1" }));
  }, [flow]);

  /* ----- RENDER --------------------------------------------------------*/
  // Auth gate
  if (!account) return null;

  // Error banner
  const errorBanner = flow.error ? (
    <div
      role="alert"
      style={{
        margin: "0 auto 24px",
        maxWidth: 760,
        padding: 14,
        background: "#FFFFFF",
        border: `1px solid ${TOKEN.ACCENT}`,
        color: TOKEN.ACCENT,
        fontFamily: FONT.CALIBRI,
        fontSize: 13,
      }}
    >
      {flow.error}
    </div>
  ) : null;

  let body = null;
  switch (flow.state) {
    case "FRAMING":
      body = (
        <FramingScreen
          submodule={flow.submodule}
          persona={flow.persona}
          framingDraft={framingDraft}
          setFramingDraft={setFramingDraft}
          onSubmit={handleFramingSubmit}
          onBack={handleBackToLanding}
          onPersonaChange={(p) => dispatch(Actions.setPersona(p))}
          intakeSeed={intakeSeed}
          busy={busy}
          error={flow.error}
        />
      );
      break;
    case "FRAME_AUDIT":
      // Wave 2.1 (UAT pack) — Layer 0 audit screen.
      body = (
        <FrameAuditScreen
          sessionId={flow.sessionId || session?.id}
          onProceed={() => dispatch(Actions.frameAuditDecision("proceed"))}
          onGetMore={() => dispatch(Actions.frameAuditDecision("get_more"))}
          onPause={() => dispatch(Actions.frameAuditDecision("pause"))}
        />
      );
      break;
    case "Q1":
    case "Q2":
    case "Q3":
    case "DEPTH_Q1":
    case "DEPTH_Q2":
    case "DEPTH_Q3":
      body = (
        <QuestionScreen
          state={flow.state}
          questionText={lastSolvaTurnText || "Loading question…"}
          draft={answerDraft}
          setDraft={setAnswerDraft}
          onContinue={handleAnswerSubmit}
          onBack={handleGoBack}
          canBack={flow.state !== "Q1"}
          busy={busy}
          error={flow.error}
        />
      );
      break;
    case "PREPARING":
      body = <PreparingInterstitial />;
      break;
    case "ARTEFACT":
      body = (
        <SolvaArtefact
          session={session}
          onStartReflection={Object.keys(flow.reflections).length < 3 ? handleStartReflection : undefined}
          savedToast={savedToast}
        />
      );
      break;
    case "ARTEFACT_REFUSAL":
      body = (
        <SolvaRefusalArtefact
          session={session}
          onStartReflection={Object.keys(flow.reflections).length < 3 ? handleStartReflection : undefined}
        />
      );
      break;
    case "REFLECT_1":
    case "REFLECT_2":
    case "REFLECT_3":
      body = (
        <ReflectionScreen
          state={flow.state}
          refusal={flow.refusal}
          draft={reflectionDraft}
          setDraft={setReflectionDraft}
          onContinue={() => handleReflectionSubmit(false)}
          onSkip={() => handleReflectionSubmit(true)}
        />
      );
      break;
    case "COMPLETE":
    default:
      body = (
        <SolvaArtefact
          session={session}
          savedToast={savedToast}
        />
      );
  }

  const widthForState = (s) =>
    s === "ARTEFACT" || s === "ARTEFACT_REFUSAL" || s === "COMPLETE" ? 880 : 760;

  return (
    <AppShell>
      {/* Wave 1.6 (UAT pack 2026-05-10) — Solva header on every screen
          inside the session shell. Stays out of LANDING because that's
          the picker, which has its own page chrome. */}
      <SolvaHeader />
      <SolvaShell
        background={backgroundForState(flow.state)}
        topPadding={isFlowState(flow.state) ? 80 : 60}
        maxWidth={widthForState(flow.state)}
        testId={`solva-session-${flow.state}`}
      >
        {errorBanner}
        {body}
        {resumed && flow.state !== "FRAMING" && (
          <div
            style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 11,
              color: TOKEN.MUTED,
              textAlign: "center",
              marginTop: 32,
            }}
          >
            Resumed session · {(flow.sessionId || "").slice(0, 8)}
          </div>
        )}
      </SolvaShell>
      {/* Wave 1.8 (UAT pack 2026-05-10) — peer-voiced transition copy
          when the layer changes. Reads `flow.history` to detect the
          last layer crossed. The component fades itself out after
          ~1.5 s; doesn't block input. */}
      {flow.history && flow.history.length >= 2 && (
        <TransitionMessage
          submodule={flow.submodule}
          fromLayer={flow.history[flow.history.length - 2]}
          toLayer={flow.state}
        />
      )}
    </AppShell>
  );
}
