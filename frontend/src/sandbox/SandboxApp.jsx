import React, { useState, useCallback } from "react";
import "./style.css";
import SandboxIntro from "./components/Intro";
import SandboxForm from "./components/Form";
import SandboxLoading from "./components/Loading";
import SandboxWelcome from "./components/Welcome";
import SandboxStep from "./components/Step";
import SandboxClose from "./components/Close";

/**
 * SandboxApp — Phase J Generative Sandbox MVP.
 *
 * Single client-side state machine drives the seven phases:
 *   intro → form → loading → welcome → step1 → step2 → step3 → step4 → close
 *
 * Step order is reordered per the visitor's Q6 emphasis (Brief v6 §2).
 * No runtime LLM between steps — everything renders from persisted state.
 */
export default function SandboxApp() {
  const [phase, setPhase] = useState("intro");
  const [sessionId, setSessionId] = useState(null);
  const [session, setSession] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);

  const onIntroComplete = useCallback(() => setPhase("form"), []);
  const onFormSubmit = useCallback((sid) => {
    setSessionId(sid);
    setPhase("loading");
  }, []);
  const onSessionReady = useCallback((data) => {
    setSession(data);
    setPhase("welcome");
  }, []);
  const onWelcomeDone = useCallback(() => {
    setStepIndex(0);
    setPhase("step");
  }, []);
  const onStepNext = useCallback(() => {
    setStepIndex((i) => {
      const next = i + 1;
      if (next >= 4) {
        setPhase("close");
        return i;
      }
      return next;
    });
  }, []);
  const onRestart = useCallback(() => {
    setPhase("intro"); setSessionId(null); setSession(null); setStepIndex(0);
  }, []);

  return (
    <div className="akki-sandbox" data-testid="sandbox-root">
      {phase === "intro" && <SandboxIntro onBegin={onIntroComplete} />}
      {phase === "form" && <SandboxForm onSubmit={onFormSubmit} />}
      {phase === "loading" && (
        <SandboxLoading sessionId={sessionId} onReady={onSessionReady} />
      )}
      {phase === "welcome" && session && (
        <SandboxWelcome session={session} onContinue={onWelcomeDone} />
      )}
      {phase === "step" && session && (
        <SandboxStep
          session={session}
          stepIndex={stepIndex}
          onNext={onStepNext}
        />
      )}
      {phase === "close" && session && (
        <SandboxClose session={session} onRestart={onRestart} />
      )}
    </div>
  );
}
