/**
 * SandboxGenerating — the 60-second streaming reveal moment.
 *
 * The user picked the "hybrid streaming reveal" aesthetic: live code-stream
 * pacing, but the content reads like an editorial paragraph in serif/italic.
 * No monospace, no terminal styling. Each stage has a serif headline + 1-3
 * italic Georgia sublines that reveal one by one as time elapses inside the
 * stage window. The cumulative narrative scrolls upward like a paper tape.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SandboxGenerating() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { bootstrap } = useAuth();

  const [stages, setStages] = useState([]);
  const [stageIdx, setStageIdx] = useState(0);
  const [revealedSubs, setRevealedSubs] = useState(0);  // sublines shown for current stage
  const [tape, setTape] = useState([]);                 // full accumulated stream
  const [ready, setReady] = useState(false);
  const [accessToken, setAccessToken] = useState(null);
  const [errored, setErrored] = useState(null);
  const companyNameRef = useRef("");
  const tapeEndRef = useRef(null);

  // bootstrap: fetch status once to get stages + intake metadata
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${API_BASE}/sandbox/generate/${sessionId}/status`);
        if (cancelled) return;
        setStages(data.stages || []);
        const s2 = (data.stages || []).find((s) => s.index === 2);
        if (s2?.headline) {
          const m = s2.headline.match(/Building (.+?) —/);
          companyNameRef.current = m ? m[1] : "";
        }
        if (data.ready) {
          setReady(true);
          setAccessToken(data.access_token);
        }
      } catch (err) {
        setErrored(err.response?.data?.detail || "Sandbox session not found. Please start again.");
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId]);

  // Poll status until ready
  useEffect(() => {
    if (ready || errored) return;
    const h = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API_BASE}/sandbox/generate/${sessionId}/status`);
        if (data.status === "error") {
          setErrored(data.error || "Something went wrong generating your sandbox.");
          return;
        }
        if (data.ready) {
          setReady(true);
          setAccessToken(data.access_token);
        }
      } catch { /* silent */ }
    }, 1200);
    return () => clearInterval(h);
  }, [sessionId, ready, errored]);

  // Stage advance — when a stage starts, push its headline onto the tape
  // and then reveal each subline at a steady cadence inside the stage window.
  useEffect(() => {
    if (!stages.length || errored) return;
    const s = stages[stageIdx];
    if (!s) return;

    // Push headline as a tape entry of kind "head"
    setTape((prev) => [...prev, { kind: "head", text: s.headline, key: `h-${stageIdx}` }]);
    setRevealedSubs(0);

    const sublines = s.sublines || [];
    const stageMs = Math.max(2400, s.max_ms - s.min_ms);
    // Reserve the last 600ms for the stage transition; spread sublines evenly across the rest.
    const subStartDelay = 350;
    const subInterval = sublines.length > 0
      ? Math.max(700, Math.floor((stageMs - subStartDelay - 600) / sublines.length))
      : 0;

    const timers = [];
    sublines.forEach((sub, i) => {
      const t = setTimeout(() => {
        setTape((prev) => [...prev, { kind: "sub", text: sub, key: `s-${stageIdx}-${i}` }]);
        setRevealedSubs((n) => n + 1);
      }, subStartDelay + i * subInterval);
      timers.push(t);
    });

    // Stage advance — but hold on the last stage until backend is ready
    const isFinal = stageIdx >= stages.length - 1;
    const isHold = stageIdx === stages.length - 2;  // hold on penultimate
    const advance = setTimeout(() => {
      if (isFinal) return;
      if (isHold && !ready) return;
      setStageIdx((i) => Math.min(i + 1, stages.length - 1));
    }, stageMs);
    timers.push(advance);

    return () => timers.forEach((t) => clearTimeout(t));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stageIdx, stages, errored]);

  // If we're holding on penultimate and ready becomes true, push to final
  useEffect(() => {
    if (ready && stages.length && stageIdx === stages.length - 2) {
      const t = setTimeout(() => setStageIdx(stages.length - 1), 600);
      return () => clearTimeout(t);
    }
  }, [ready, stageIdx, stages.length]);

  // Auto-scroll tape to bottom whenever we add a line
  useEffect(() => {
    tapeEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [tape.length]);

  // When final stage reached AND ready, hand off to the app
  const handoffDone = useRef(false);
  useEffect(() => {
    if (!ready || !accessToken || handoffDone.current) return;
    if (stageIdx < stages.length - 1) return;
    handoffDone.current = true;
    (async () => {
      try { localStorage.setItem("akki_access_token", accessToken); } catch { /* noop */ }
      await new Promise((r) => setTimeout(r, 900));
      if (bootstrap) await bootstrap();
      navigate("/app?tutorial=1");
    })();
  }, [ready, accessToken, stageIdx, stages.length, bootstrap, navigate]);

  const currentStage = stages[stageIdx];
  const progressPct = stages.length
    ? Math.round(((stageIdx + 1) / stages.length) * 100)
    : 0;
  const companyName = companyNameRef.current || "your sandbox";

  if (errored) {
    return (
      <div className="min-h-screen bg-[var(--cream)] flex flex-col items-center justify-center px-6">
        <p className="akki-overline mb-3">Something stumbled</p>
        <h1 className="akki-serif text-[26px] text-[var(--ink)] mb-3">We couldn't finish your sandbox.</h1>
        <p className="text-[14px] text-[var(--muted)] mb-6 text-center max-w-md">{errored}</p>
        <button
          onClick={() => navigate("/sandbox")}
          className="akki-gesture text-[14px]"
          data-testid="sandbox-error-retry"
        >
          Start over
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--cream)] flex flex-col items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center max-w-[680px] w-full"
        data-testid="sandbox-generating"
      >
        {/* Hero: company name */}
        <motion.h1
          className="akki-serif text-[30px] md:text-[40px] leading-tight text-[var(--ink)] mb-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
          data-testid="sandbox-generating-company"
        >
          Creating <span className="text-[var(--accent)]">{companyName}</span>…
        </motion.h1>

        {/* Current stage headline (the live "now" line) */}
        <div className="h-[28px] mb-6">
          <AnimatePresence mode="wait">
            {currentStage && (
              <motion.p
                key={currentStage.index}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.25 }}
                className="text-[13px] uppercase tracking-[0.18em] text-[var(--accent)] font-medium"
                data-testid={`sandbox-stage-${currentStage.index}`}
              >
                {currentStage.headline}
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        {/* Streaming paper-tape — serif headlines + italic sublines, scrolls upward */}
        <div
          className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-md mx-auto mb-8 overflow-hidden"
          style={{ height: 220 }}
          data-testid="sandbox-stream-tape"
        >
          <div className="h-full overflow-y-auto px-6 py-5 text-left scroll-smooth"
               style={{ scrollbarWidth: "none" }}>
            <AnimatePresence initial={false}>
              {tape.map((line) => (
                <motion.div
                  key={line.key}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: line.kind === "head" ? 1 : 0.78, y: 0 }}
                  transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
                  className={
                    line.kind === "head"
                      ? "akki-serif text-[15.5px] text-[var(--ink)] leading-snug mt-3 first:mt-0"
                      : "akki-serif italic text-[13.5px] text-[var(--muted)] leading-relaxed pl-4 mt-1.5 border-l border-[var(--rule)]"
                  }
                  data-testid={line.kind === "head" ? "tape-head" : "tape-sub"}
                >
                  {line.text}
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={tapeEndRef} />
          </div>
        </div>

        {/* Slim progress bar */}
        <div className="w-full max-w-[380px] mx-auto h-[4px] rounded-sm bg-[var(--cream-deep)] overflow-hidden relative" data-testid="sandbox-progress">
          <motion.div
            className="h-full bg-[var(--accent)]"
            initial={{ width: "0%" }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.7, ease: [0.2, 0.8, 0.2, 1] }}
          />
          <motion.div
            className="absolute top-0 left-0 h-full w-[40%] bg-gradient-to-r from-transparent via-white/40 to-transparent"
            initial={{ x: "-100%" }}
            animate={{ x: "250%" }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "linear" }}
          />
        </div>

        <p className="text-[11.5px] text-[var(--muted)]/60 uppercase tracking-[0.2em] mt-5">
          Stage {stageIdx + 1} / {stages.length || 10}
        </p>
      </motion.div>
    </div>
  );
}
