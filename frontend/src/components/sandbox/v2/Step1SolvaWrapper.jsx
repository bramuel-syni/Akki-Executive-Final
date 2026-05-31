/**
 * Phase J.2 — Step 1 Solva wrapper (Sandbox v2).
 *
 * Wraps the Phase I Solva v3 flow with sandbox-specific tweaks per the
 * brief §4:
 *
 *   - Sub-module forced to `develop_strategy`. Picker is invisible.
 *   - Opening question pre-loaded, calibrated to role from Welcome
 *     (GET /api/sandbox/v2/sessions/{sid}/opening-question).
 *   - Compresses to 3 Layer-1 questions only (no DEPTH_Q1..DEPTH_Q3).
 *   - Empty-framing fallback per §4.5: a representative situation
 *     calibrated to role+org_type (GET /sandbox/v2/sessions/{sid}/fallback-situation).
 *   - sandbox=true on POST /api/solva/v2/sessions.
 *   - Refusal artefact already supported by Phase I — surfaced via
 *     SolvaRefusalArtefact.jsx.
 *
 * Composition:
 *
 *     state           render
 *     -----           ------
 *     framing-here    FramingScreen with pre-loaded opening question
 *     Q1 .. Q3        QuestionScreen (sandbox-compressed, 3 turns only)
 *     PREPARING       PreparingInterstitial
 *     ARTEFACT        SolvaArtefact (no "Reflect on this" CTA in sandbox)
 *     ARTEFACT_REFUSAL SolvaRefusalArtefact
 *
 * Reflection (REFLECT_1..3) is intentionally OFF in sandbox — the brief
 * routes the user to the Step 1 reveal after the artefact, not into a
 * second reasoning loop.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";

import FramingScreen from "@/components/solva/flow/FramingScreen";
import QuestionScreen from "@/components/solva/flow/QuestionScreen";
import PreparingInterstitial from "@/components/solva/flow/PreparingInterstitial";
import SolvaArtefact from "@/components/solva/artefact/SolvaArtefact";
import SolvaRefusalArtefact from "@/components/solva/artefact/SolvaRefusalArtefact";
import { TOKEN, FONT } from "@/components/solva/flow/tokens";

import { Actions as SbxActions } from "@/lib/sandboxV2Flow";

import { resolveBackendOrigin } from "@/lib/api";
const API = resolveBackendOrigin();

// Pre-auth axios — relies on the cookie the welcome step minted.
const api = axios.create({
  baseURL: `${API}/api`,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

// 3-question Sandbox v3 micro-state-machine (subset of Phase I).
const SBX_STATES = ["FRAMING", "Q1", "Q2", "Q3", "PREPARING", "ARTEFACT", "ARTEFACT_REFUSAL"];

export default function Step1SolvaWrapper({ flow, dispatch, onComplete }) {
  const [innerState, setInnerState] = useState("FRAMING");
  const [openingQuestion, setOpeningQuestion] = useState("");
  const [fallbackSituation, setFallbackSituation] = useState("");
  const [framingDraft, setFramingDraft] = useState("");
  const [answerDraft, setAnswerDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [solvaSession, setSolvaSession] = useState(null);

  const sandboxSid = flow.sessionId;

  /* Fetch the calibrated opening question + the role-aware fallback
   * situation as soon as we mount. Both are deterministic on the
   * server side, so we never re-fetch.                                  */
  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!sandboxSid) return;
      try {
        const [oq, fb] = await Promise.all([
          api.get(`/sandbox/v2/sessions/${sandboxSid}/opening-question`),
          api.get(`/sandbox/v2/sessions/${sandboxSid}/fallback-situation`),
        ]);
        if (cancelled) return;
        setOpeningQuestion(oq.data.question || "");
        setFallbackSituation(fb.data.situation || "");
      } catch (e) {
        if (cancelled) return;
        setErr("Could not load Sandbox starting question.");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [sandboxSid]);

  /* Last solva-emitted prompt (the "what's the next question for the
   * user" copy that QuestionScreen renders).                             */
  const lastSolvaTurnText = useMemo(() => {
    const turns = solvaSession?.turns || [];
    for (let i = turns.length - 1; i >= 0; i -= 1) {
      const t = turns[i];
      if (t?.role === "solva") {
        return (t.text || "").replace(/\[T:[a-zA-Z_]+\]/g, "").trim();
      }
    }
    return "";
  }, [solvaSession]);

  const refreshSolvaSession = useCallback(async (sid) => {
    if (!sid) return null;
    try {
      const r = await api.get(`/solva/v2/sessions/${sid}`);
      setSolvaSession(r.data);
      return r.data;
    } catch (_e) { return null; }
  }, []);

  /* FRAMING → Q1 :: POST /api/solva/v2/sessions */
  const submitFraming = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const text = framingDraft.trim() || fallbackSituation;
      const body = {
        intent: text,
        submodule: "develop_strategy",
        auto_cluster: true,
        sandbox: true,
      };
      const r = await api.post("/solva/v2/sessions", body);
      setSolvaSession(r.data);
      dispatch(SbxActions.attachSolvaSession(r.data.id));
      setInnerState("Q1");
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || "Could not start.");
    } finally {
      setBusy(false);
    }
  }, [framingDraft, fallbackSituation, dispatch]);

  /* Q1..Q3 :: POST /api/solva/v2/sessions/{sid}/turn */
  const submitAnswer = useCallback(async () => {
    if (!solvaSession?.id) return;
    setBusy(true);
    setErr(null);
    try {
      try {
        await api.post(`/solva/v2/sessions/${solvaSession.id}/turn`, {
          user_text: answerDraft.trim() || "(no further detail provided)",
        });
      } catch (eTurn) {
        // 409 = Solva v2 refusal ladder has hard-blocked further turns.
        // 422 = orchestrator detected refusal at the current turn.
        // BOTH are valid demo punch-lines for the Sandbox: the brief
        // explicitly bills refusal as part of the experience ("the
        // refusal IS the demo"). Route into ARTEFACT_REFUSAL rather
        // than dead-ending with a raw error string.
        const status = eTurn?.response?.status;
        if (status === 409 || status === 422) {
          const after = await refreshSolvaSession(solvaSession.id);
          dispatch(SbxActions.setSolvaRefusal(true));
          setInnerState("ARTEFACT_REFUSAL");
          // Force a refresh of the snapshot so refusal artefact has data
          // to render even if the server didn't promote synthesis.
          void after;
          return;
        }
        // Anything else — surface the message but keep the user on the
        // current question so they can retry.
        throw eTurn;
      }
      const srv = await refreshSolvaSession(solvaSession.id);
      setAnswerDraft("");

      // Compressed flow: Q1 → Q2 → Q3 → PREPARING (no depth round).
      const seq = ["Q1", "Q2", "Q3", "PREPARING"];
      const idx = seq.indexOf(innerState);
      const nextStep = seq[Math.min(idx + 1, seq.length - 1)];
      setInnerState(nextStep);

      if (nextStep === "PREPARING") {
        // Fire one more turn to push the orchestrator into synthesis.
        try {
          await api.post(`/solva/v2/sessions/${solvaSession.id}/turn`, {
            user_text: "(continue to synthesis)",
          });
        } catch (e2) {
          // 409 / 422 = refusal — treat as the demo's refusal artefact.
          const status2 = e2?.response?.status;
          if (status2 === 409 || status2 === 422) {
            const after = await refreshSolvaSession(solvaSession.id);
            dispatch(SbxActions.setSolvaRefusal(true));
            setInnerState("ARTEFACT_REFUSAL");
            void after;
            return;
          }
        }
        const after = await refreshSolvaSession(solvaSession.id);
        const refusal = ["refused", "blocked_hard", "blocked_soft"].includes((after?.status || "").toLowerCase())
          || (after?.synthesis == null);
        dispatch(SbxActions.setSolvaRefusal(refusal));
        setInnerState(refusal ? "ARTEFACT_REFUSAL" : "ARTEFACT");
      }

      // Avoid the unused-var warning.
      void srv;
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || "Could not submit answer.");
    } finally {
      setBusy(false);
    }
  }, [solvaSession, answerDraft, innerState, refreshSolvaSession, dispatch]);

  /* Once on ARTEFACT or ARTEFACT_REFUSAL, the user can advance to the
   * Step 1 reveal via the parent page (a dedicated CTA below).          */

  /* RENDER                                                              */
  if (err) {
    return (
      <div role="alert" style={{ padding: 24, fontFamily: FONT.CALIBRI, color: TOKEN.ACCENT_DARK, border: `1px solid ${TOKEN.ACCENT_DARK}`, background: TOKEN.LIGHT, borderRadius: 2 }}>
        {err}
      </div>
    );
  }

  switch (innerState) {
    case "FRAMING":
      return (
        <>
          {/* Pre-loaded opening question — calibrated to role */}
          {openingQuestion && (
            <div
              style={{
                fontFamily: FONT.GEORGIA,
                fontSize: 13,
                fontStyle: "italic",
                color: TOKEN.DEEP,
                textAlign: "center",
                marginBottom: 24,
                lineHeight: 1.55,
              }}
            >
              {openingQuestion}
            </div>
          )}
          <FramingScreen
            submodule="develop_strategy"
            persona={null}
            framingDraft={framingDraft}
            setFramingDraft={setFramingDraft}
            onSubmit={submitFraming}
            onBack={() => dispatch(SbxActions.goBack())}
            onPersonaChange={() => {}}
            busy={busy}
            error={null}
          />
          {/* Brief §4.5 — the empty-framing fallback voiceover. */}
          <div
            style={{
              marginTop: 18,
              padding: 14,
              fontFamily: FONT.CALIBRI,
              fontSize: 12,
              color: TOKEN.MUTED,
              borderTop: `1px dotted ${TOKEN.RULE}`,
              textAlign: "center",
              lineHeight: 1.6,
            }}
          >
            Empty? No problem — we'll show you Akki working on a situation a {humanRole(flow.welcome.role)} at a {humanOrg(flow.welcome.org_type)} organisation might encounter.
          </div>
        </>
      );

    case "Q1":
    case "Q2":
    case "Q3":
      return (
        <QuestionScreen
          state={innerState}
          questionText={lastSolvaTurnText || "Loading question…"}
          draft={answerDraft}
          setDraft={setAnswerDraft}
          onContinue={submitAnswer}
          onBack={() => {}}
          canBack={false}
          busy={busy}
          error={null}
        />
      );

    case "PREPARING":
      return <PreparingInterstitial />;

    case "ARTEFACT":
      return (
        <>
          <SolvaArtefact session={solvaSession} />
          <ContinueCTA onClick={onComplete} label="See what just happened →" />
        </>
      );

    case "ARTEFACT_REFUSAL":
      return (
        <>
          <SolvaRefusalArtefact session={solvaSession} />
          {/* Brief §4.5 voice — refusal moment is the point, not a bug. */}
          <div
            style={{
              maxWidth: 560,
              margin: "32px auto 0",
              fontFamily: FONT.GEORGIA,
              fontStyle: "italic",
              fontSize: 16,
              color: TOKEN.DEEP,
              lineHeight: 1.55,
              textAlign: "center",
            }}
          >
            Notice what just happened. Solva refused to weight scenarios because the evidence was thin. This is what you can trust.
          </div>
          <ContinueCTA onClick={onComplete} label="Continue →" />
        </>
      );

    default:
      return null;
  }
}

function ContinueCTA({ onClick, label }) {
  return (
    <div style={{ marginTop: 40, textAlign: "center" }}>
      <button
        type="button"
        onClick={onClick}
        data-testid="sandbox-v2-step1-continue"
        style={{
          fontFamily: FONT.CALIBRI,
          fontSize: 14,
          background: TOKEN.ACCENT_DARK,
          color: TOKEN.LIGHT,
          border: "none",
          padding: "12px 28px",
          cursor: "pointer",
          borderRadius: 2,
          letterSpacing: 0.5,
        }}
      >
        {label}
      </button>
    </div>
  );
}

function humanRole(r) {
  return ({
    ceo: "CEO",
    ned: "non-executive director",
    company_secretary: "Company Secretary",
    exco_member: "Exco member",
    government_executive: "government executive",
    regulator: "regulator",
    investor: "investor",
    other: "leader",
  })[r] || "leader";
}

function humanOrg(o) {
  return ({
    bank: "bank",
    healthcare: "healthcare",
    logistics: "logistics",
    saas: "SaaS",
    government: "government",
    pre_ipo: "pre-IPO",
    listed_corporate: "listed corporate",
    other: "complex",
  })[o] || "complex";
}
