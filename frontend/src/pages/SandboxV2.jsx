/**
 * Sandbox v2 — top-level page (Phase J).
 *
 * Mounts the new linear, four-step pre-auth experience. The legacy
 * 60-second narrative remains accessible at /sandbox/legacy for 30
 * days as a forensic fallback.
 *
 * Step composition (J.1..J.4):
 *
 *   WELCOME           → WelcomeStep
 *   STEP_1_SOLVA      → Step1SolvaWrapper       (added in J.2)
 *   STEP_1_REVEAL     → StepReveal              (added in J.2)
 *   STEP_3_STUDIO     → Step3StudioWrapper      (added in J.3)
 *   STEP_3_REVEAL     → StepReveal              (added in J.3)
 *   STEP_4_CYCLE      → Step4CycleSnapshot      (added in J.4)
 *   STEP_4_REVEAL     → StepReveal              (added in J.4)
 *   CLOSING           → ClosingStep             (added in J.4)
 *
 * In J.1 only Welcome ships visibly — every other step renders a
 * placeholder so the flow is end-to-end testable. J.2+ replace each
 * placeholder with its real implementation.
 */
import React, { useCallback, useEffect, useReducer, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";

import {
  Actions,
  initialState,
  nextState,
  resumePoint,
  readResumeToken,
  writeResumeToken,
  readWelcomeCache,
  writeWelcomeCache,
  isRevealState,
  stepIndexForState,
} from "@/lib/sandboxV2Flow";

import StepShell from "@/components/sandbox/v2/StepShell";
import ProgressChrome from "@/components/sandbox/v2/ProgressChrome";
import WelcomeStep from "@/components/sandbox/v2/WelcomeStep";
import { TOKEN, FONT } from "@/components/sandbox/v2/tokens";

// J.2..J.4 components are imported lazily; J.1 falls back to a placeholder.
import Step1SolvaWrapper from "@/components/sandbox/v2/Step1SolvaWrapper";
import StepReveal from "@/components/sandbox/v2/StepReveal";
import Step3StudioWrapper from "@/components/sandbox/v2/Step3StudioWrapper";
import Step4CycleSnapshot from "@/components/sandbox/v2/Step4CycleSnapshot";
import ClosingStep from "@/components/sandbox/v2/ClosingStep";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// Plain axios (not the auth client) — sandbox is pre-auth.
const sbx = axios.create({
  baseURL: `${API_BASE}/api/sandbox/v2`,
  withCredentials: false,
  headers: { "Content-Type": "application/json" },
});

export default function SandboxV2Page() {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const [flow, dispatch] = useReducer(nextState, undefined, () => {
    const init = initialState();
    // Pre-fill welcome from cache (brief §9.2).
    const cached = readWelcomeCache();
    if (cached && typeof cached === "object") {
      init.welcome = { ...init.welcome, ...cached };
    }
    return init;
  });

  const [busy, setBusy] = useState(false);

  /* ----- BOOTSTRAP / RESUME ------------------------------------------*/
  useEffect(() => {
    let cancelled = false;
    async function init() {
      // ?token=<sid> takes precedence; localStorage is fallback.
      const tokFromUrl = search.get("token");
      const sid = tokFromUrl || readResumeToken();
      if (!sid) return;
      try {
        const r = await sbx.get(`/sessions/${sid}`);
        if (cancelled) return;
        const snap = resumePoint(r.data);
        dispatch(Actions.resume(snap));
      } catch (err) {
        // 404 / 410 → drop the stale token silently.
        writeResumeToken(null);
      }
    }
    init();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ----- HANDLERS ----------------------------------------------------*/
  const submitWelcome = useCallback(async () => {
    setBusy(true);
    try {
      const body = {
        name: flow.welcome.name,
        role: flow.welcome.role,
        org_type: flow.welcome.org_type,
        hope: (flow.welcome.hope || "").trim() || undefined,
      };
      writeWelcomeCache(flow.welcome);
      const r = await sbx.post("/sessions", body);
      const sid = r.data.session_id;
      writeResumeToken(sid);
      dispatch(Actions.attachSession(sid, r.data.expires_at));
      dispatch(Actions.submitWelcome());
    } catch (err) {
      const msg = err?.response?.data?.detail
        || err?.message
        || "Could not start sandbox session.";
      const detail = typeof msg === "string" ? msg : "Could not start sandbox session.";
      dispatch(Actions.setError(detail));
    } finally {
      setBusy(false);
    }
  }, [flow.welcome]);

  const persistState = useCallback(async (state, payload) => {
    if (!flow.sessionId) return;
    try {
      await sbx.patch(`/sessions/${flow.sessionId}`, { state, payload });
    } catch (_e) { /* non-fatal */ }
  }, [flow.sessionId]);

  const advance = useCallback(async () => {
    // Compute next state and persist.
    const after = nextState(flow, Actions.advance());
    if (after.state !== flow.state) {
      await persistState(after.state, null);
    }
    dispatch(Actions.advance());
  }, [flow, persistState]);

  const goBack = useCallback(() => {
    dispatch(Actions.goBack());
  }, []);

  const exitSandbox = useCallback(async () => {
    try {
      if (flow.sessionId) {
        await sbx.post(`/sessions/${flow.sessionId}/exit`, {});
      }
    } catch (_e) { /* ignore */ }
    writeResumeToken(null);
    navigate("/");
  }, [flow.sessionId, navigate]);

  /* ----- RENDER ------------------------------------------------------*/
  const showProgress = stepIndexForState(flow.state) !== null;
  const isReveal = isRevealState(flow.state);

  let body;
  switch (flow.state) {
    case "WELCOME":
      body = (
        <WelcomeStep
          welcome={flow.welcome}
          dispatch={dispatch}
          onSubmit={submitWelcome}
          busy={busy}
          error={flow.error}
        />
      );
      break;

    case "STEP_1_SOLVA":
      body = (
        <Step1SolvaWrapper
          flow={flow}
          dispatch={dispatch}
          onComplete={advance}
        />
      );
      break;

    case "STEP_1_REVEAL":
      body = (
        <StepReveal
          stepIndex={1}
          refusal={flow.solvaRefusal}
          onAdvance={advance}
          advanceLabel={flow.solvaRefusal ? "Continue \u2192" : "Continue \u2192"}
        />
      );
      break;

    case "STEP_3_STUDIO":
      body = (
        <Step3StudioWrapper
          flow={flow}
          dispatch={dispatch}
          onComplete={advance}
        />
      );
      break;

    case "STEP_3_REVEAL":
      body = (
        <StepReveal stepIndex={3} onAdvance={advance} advanceLabel="One more step \u2192" />
      );
      break;

    case "STEP_4_CYCLE":
      body = (
        <Step4CycleSnapshot
          flow={flow}
          dispatch={dispatch}
          onComplete={advance}
        />
      );
      break;

    case "STEP_4_REVEAL":
      body = <StepReveal stepIndex={4} onAdvance={advance} advanceLabel="Finish \u2192" />;
      break;

    case "CLOSING":
      body = <ClosingStep flow={flow} dispatch={dispatch} />;
      break;

    default:
      body = (
        <div style={{ fontFamily: FONT.GEORGIA, color: TOKEN.MUTED }}>
          Unknown state.
        </div>
      );
  }

  // Dynamic max-width: reveals + studio breathe wider than welcome.
  const maxWidth = isReveal ? 720 : (flow.state === "STEP_3_STUDIO" ? 1080 : 720);

  return (
    <>
      {showProgress && (
        <ProgressChrome state={flow.state} onExit={exitSandbox} />
      )}
      <StepShell state={flow.state} maxWidth={maxWidth}>
        {body}
      </StepShell>
    </>
  );
}
