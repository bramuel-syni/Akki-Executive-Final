/**
 * SandboxGenerating — the 60-second wow-factor moment.
 *
 * The frontend drives the 10-stage narrative (stages come from the server
 * pre-substituted with the user's company name, sector, region, role).
 * We poll /status every 1.2s in parallel; as soon as the backend marks
 * ready and the final stage has completed, we stamp the sandbox JWT into
 * the auth context and navigate to /app.
 *
 * Visual language:
 *  - cream background (#F7F3EA), no gradients / particles
 *  - company name in serif Georgia, fades in once
 *  - status line 300ms cross-fade between stages
 *  - slim oxblood progress bar (4px), non-linear advance per stage
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import axios from "axios";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";

const API_BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SandboxGenerating() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { bootstrap } = useAuth();

  const [stages, setStages] = useState([]);
  const [stageIdx, setStageIdx] = useState(0);
  const [ready, setReady] = useState(false);
  const [accessToken, setAccessToken] = useState(null);
  const [contextId, setContextId] = useState(null);
  const [errored, setErrored] = useState(null);
  const companyNameRef = useRef("");

  // --- bootstrap: fetch status once to get stages + intake metadata ---
  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        const { data } = await axios.get(`${API_BASE}/sandbox/generate/${sessionId}/status`);
        if (cancelled) return;
        setStages(data.stages || []);
        // Extract the company name from stage text for the hero display
        const s2 = (data.stages || []).find((s) => s.index === 2);
        if (s2?.text) {
          const match = s2.text.match(/Building (.+?) —/);
          companyNameRef.current = match ? match[1] : "";
        }
        if (data.ready) {
          setReady(true);
          setAccessToken(data.access_token);
          setContextId(data.context_id);
        }
      } catch (err) {
        setErrored(err.response?.data?.detail || "Sandbox session not found. Please start again.");
      }
    };
    init();
    return () => { cancelled = true; };
  }, [sessionId]);

  // --- poll status every 1.2s until ready ---
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
          setContextId(data.context_id);
        }
      } catch {
        /* silent — next poll will retry */
      }
    }, 1200);
    return () => clearInterval(h);
  }, [sessionId, ready, errored]);

  // --- stage advance — each stage sits for (max_ms - min_ms) with 300ms crossfade ---
  useEffect(() => {
    if (!stages.length || errored) return;
    if (stageIdx >= stages.length - 1) return;
    const s = stages[stageIdx];
    // Hold on stage 9 (index 8) until backend is ready if it's taking longer
    const isHoldStage = stageIdx === 8;
    const dwell = isHoldStage && !ready ? 2000 : Math.max(2500, s.max_ms - s.min_ms);
    const h = setTimeout(() => {
      // Only advance past stage 8 when backend is ready
      if (stageIdx === 8 && !ready) return;
      setStageIdx((i) => Math.min(i + 1, stages.length - 1));
    }, dwell);
    return () => clearTimeout(h);
  }, [stageIdx, stages, ready, errored]);

  // When we're on the final stage AND ready, hand off to the app
  const handoffDone = useRef(false);
  useEffect(() => {
    if (!ready || !accessToken || handoffDone.current) return;
    if (stageIdx < stages.length - 1) return;
    handoffDone.current = true;
    (async () => {
      // Store the sandbox JWT so the AuthProvider can pick it up on bootstrap
      try {
        localStorage.setItem("akki_access_token", accessToken);
      } catch { /* noop */ }
      await new Promise((r) => setTimeout(r, 700));  // brief beat on "Ready. Taking you in."
      if (bootstrap) await bootstrap();
      navigate("/app");
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
        className="text-center max-w-[640px]"
        data-testid="sandbox-generating"
      >
        {/* Company name — Georgia 36px, pulses softly once when it first appears */}
        <motion.h1
          className="akki-serif text-[30px] md:text-[40px] leading-tight text-[var(--ink)] mb-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
          data-testid="sandbox-generating-company"
        >
          Creating <span className="text-[var(--accent)]">{companyName}</span>…
        </motion.h1>

        {/* Streaming status line */}
        <div className="h-[56px] flex items-center justify-center mb-10">
          <AnimatePresence mode="wait">
            {currentStage && (
              <motion.p
                key={currentStage.index}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.3 }}
                className="text-[15px] md:text-[16px] text-[var(--muted)] leading-relaxed"
                data-testid={`sandbox-stage-${currentStage.index}`}
              >
                {currentStage.text}
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        {/* Slim progress bar with ambient pulse between step advances */}
        <div className="w-full max-w-[380px] mx-auto h-[4px] rounded-sm bg-[var(--cream-deep)] overflow-hidden relative" data-testid="sandbox-progress">
          <motion.div
            className="h-full bg-[var(--accent)]"
            initial={{ width: "0%" }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.7, ease: [0.2, 0.8, 0.2, 1] }}
          />
          {/* Ambient pulse — subtle shimmer during each stage to suggest ongoing work */}
          <motion.div
            className="absolute top-0 left-0 h-full w-[40%] bg-gradient-to-r from-transparent via-white/40 to-transparent"
            initial={{ x: "-100%" }}
            animate={{ x: "250%" }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "linear" }}
          />
        </div>

        <p className="text-[11.5px] text-[var(--muted)]/60 uppercase tracking-[0.2em] mt-6">
          Stage {stageIdx + 1} / {stages.length || 10}
        </p>
      </motion.div>
    </div>
  );
}
