/**
 * Solva v2 — SolvaArtefactV2 orchestrator (Slice 2b correction, 2026-05-29).
 *
 * CORRECTION FROM PRIOR CLOSE-OUT (tester contract verification):
 *  - Locked enum has EXACTLY 16 kinds (Slice 4 added bias_inventory;
 *    Slice 5 added pre_mortem; Slice 6 added cost_asymmetry). Section
 *    dividers are NOT slides — they're visual separators carrying
 *    `data-solva-v2-section-divider="true"` (no `data-solva-v2-slide`
 *    / no `data-solva-v2-slide-kind`).
 *  - All 16 kinds render UNCONDITIONALLY so the kind inventory is
 *    consistent across sessions regardless of payload data presence.
 *    Empty arrays surface as empty-state copy inside the slide, not as a
 *    missing slide.
 *  - Locked kind value is `per_scenario_table` (spec used the short form),
 *    not the longer Pydantic field name `per_scenario_confidence_table`.
 *  - Body-level class `solva-v2-printing-context` mounted via useEffect
 *    for the print stylesheet — replaces the prior `body:has()` selector
 *    which is unreliable in older Chromium and some Playwright pipelines.
 *
 * The 16 locked slide kinds:
 *   cover · headline · tensions_overview · per_tension · scenarios_overview
 *   · per_scenario_table · sensitivity · reflection · bias_inventory
 *   · pathway · pre_mortem · decision_logic · cost_asymmetry
 *   · risk_mitigation · methodological_honesty · in_closing
 *
 * Section dividers interleave between the 6 narrative arcs but DO NOT
 * appear in the slide-kind inventory.
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Loader2, AlertCircle } from "lucide-react";
import SectionDivider from "./SectionDivider";
import SolvaReasoningTicker from "./SolvaReasoningTicker";
import useSolvaReasoningStream from "@/hooks/useSolvaReasoningStream";
import CoverSlide from "./slides/CoverSlide";
import HeadlineSlide from "./slides/HeadlineSlide";
import TensionsOverviewSlide from "./slides/TensionsOverviewSlide";
import PerTensionSlide from "./slides/PerTensionSlide";
import ScenariosOverviewSlide from "./slides/ScenariosOverviewSlide";
import PerScenarioConfidenceTable from "./slides/PerScenarioConfidenceTable";
import SensitivitySlide from "./slides/SensitivitySlide";
import ReflectionSlide from "./slides/ReflectionSlide";
import PathwaySlide from "./slides/PathwaySlide";
import DecisionLogicSlide from "./slides/DecisionLogicSlide";
import RiskMitigationSlide from "./slides/RiskMitigationSlide";
import BiasInventorySlide from "./slides/BiasInventorySlide";
import PreMortemSlide from "./slides/PreMortemSlide";
import CostAsymmetrySlide from "./slides/CostAsymmetrySlide";
import MethodologicalHonestySlide from "./slides/MethodologicalHonestySlide";
// Slice 7 (2026-05-29) — session-log side-panel re-opens from the
// topbar's icon stub. Mounted alongside the artefact root so close-
// click + ESC interactions live alongside the deck.
import SessionLogPanel from "./SessionLogPanel";
import InClosingSlide from "./slides/InClosingSlide";


/**
 * Compose the slide sequence from the payload. All 16 locked slide
 * kinds render every time — empty arrays surface as empty-state copy
 * inside the slide, NOT as a skipped slide. Section dividers (which
 * are NOT slides) interleave between narrative arcs.
 */
function composeSlides(payload) {
  const slides = [];

  // ── Arc 1: Cover + Headline ────────────────────────────────────
  slides.push({
    kind: "cover",
    render: (shared) => <CoverSlide cover={payload.cover} {...shared} />,
  });
  slides.push({
    kind: "headline",
    render: (shared) => <HeadlineSlide headline={payload.headline} {...shared} />,
  });

  // ── Arc 2: Tensions ────────────────────────────────────────────
  const tensions = payload.tensions || [];
  const deepDives = payload.per_tension_deep_dive || [];
  slides.push({
    kind: "section_divider",
    isSectionDivider: true,
    render: (shared) => (
      <SectionDivider
        sectionLabel="Tensions"
        sectionSubtitle="What the evidence flags as worth pressure-testing."
        {...shared}
      />
    ),
  });
  slides.push({
    kind: "tensions_overview",
    render: (shared) => (
      <TensionsOverviewSlide tensions={tensions} {...shared} />
    ),
  });
  // Per-tension deep-dive: at least one slide of this kind ALWAYS
  // surfaces. If no tensions, a placeholder slide with empty-state
  // copy renders so the kind inventory stays complete.
  if (tensions.length > 0) {
    tensions.forEach((t) => {
      const dd = deepDives.find((d) => d.tension_number === t.number) || null;
      slides.push({
        kind: "per_tension",
        render: (shared) => (
          <PerTensionSlide tension={t} deepDive={dd} {...shared} />
        ),
      });
    });
  } else {
    slides.push({
      kind: "per_tension",
      isPlaceholder: true,
      render: (shared) => (
        <PerTensionSlide
          tension={{
            number: "—",
            title: "No tension was surfaced in this session",
            prevailing_framing:
              "The 5-layer pass did not flag any contradictions worth pressure-testing for this submission.",
            implication:
              "This is itself an outcome — it does not mean nothing is at stake; it means the evidence the session received did not point to a contradiction.",
            severity: "low",
            contradiction_source: "user_vs_corpus",
            evidence_block: null,
          }}
          deepDive={null}
          {...shared}
        />
      ),
    });
  }

  // ── Arc 3: Scenarios overview + Confidence table + Sensitivity ─
  const scenarios = payload.scenarios || [];
  const confTable = (
    payload.per_scenario_confidence_table ||
    payload.per_scenario_table ||
    { rows: [] }
  );
  const sensitivity = payload.sensitivity_inputs || [];
  slides.push({
    kind: "section_divider",
    isSectionDivider: true,
    render: (shared) => (
      <SectionDivider
        sectionLabel="Scenarios"
        sectionSubtitle="How the evidence distributes — weights, confidence, sensitivity."
        {...shared}
      />
    ),
  });
  slides.push({
    kind: "scenarios_overview",
    render: (shared) => (
      <ScenariosOverviewSlide scenarios={scenarios} {...shared} />
    ),
  });
  slides.push({
    kind: "per_scenario_table",
    render: (shared) => (
      <PerScenarioConfidenceTable table={confTable} {...shared} />
    ),
  });
  slides.push({
    kind: "sensitivity",
    render: (shared) => (
      <SensitivitySlide sensitivity={sensitivity} {...shared} />
    ),
  });

  // ── Arc 4: Reflection ──────────────────────────────────────────
  slides.push({
    kind: "section_divider",
    isSectionDivider: true,
    render: (shared) => (
      <SectionDivider
        sectionLabel="Reflection"
        sectionSubtitle="Three closing questions. Every diagnosis carries provisional weight."
        {...shared}
      />
    ),
  });
  slides.push({
    kind: "reflection",
    render: (shared) => (
      <ReflectionSlide
        reflection={payload.reflection_section || {
          title: "Reflection — what could be wrong, what would change, what to watch",
          intro_copy: "Three closing questions. Every diagnosis carries provisional weight.",
          questions: [],
        }}
        {...shared}
      />
    ),
  });

  // ── Arc 5: Pathway + Decision logic + Risk register ────────────
  const pathway = payload.pathway || [];
  const decisions = payload.decision_logic || [];
  const risks = payload.risk_mitigation || [];

  // ── Bias inventory (Slice 4, Trust pillar 2) — sits between
  //    reflection and pathway: after the founder reflects on
  //    uncomfortable questions, surface bias landscape, then move
  //    to recommendations. REQUIRED on every artefact per Slice 4
  //    `bias_inventory_present` validator.
  slides.push({
    kind: "bias_inventory",
    render: (shared) => (
      <BiasInventorySlide
        biasInventory={payload.bias_inventory}
        {...shared}
      />
    ),
  });

  slides.push({
    kind: "section_divider",
    isSectionDivider: true,
    render: (shared) => (
      <SectionDivider
        sectionLabel="Pathway"
        sectionSubtitle="What the weighted picture supports as next moves."
        {...shared}
      />
    ),
  });
  slides.push({
    kind: "pathway",
    render: (shared) => <PathwaySlide pathway={pathway} {...shared} />,
  });
  // ── Pre-mortem (Slice 5, Trust pillar 4) — sits between pathway and
  //    decision_logic: after the founder reads the recommended next
  //    moves, surface the imagined-regret framing so adversarial debate
  //    is in view BEFORE the conditional branches. REQUIRED on every
  //    artefact per Slice 5 `pre_mortem_present` validator.
  slides.push({
    kind: "pre_mortem",
    render: (shared) => (
      <PreMortemSlide preMortem={payload.pre_mortem} {...shared} />
    ),
  });
  slides.push({
    kind: "decision_logic",
    render: (shared) => (
      <DecisionLogicSlide branches={decisions} {...shared} />
    ),
  });
  // ── Cost asymmetry (Slice 6, Trust pillar 5) — sits between
  //    decision_logic and risk_mitigation: after the founder reads
  //    the conditional branches, surface the if-correct vs if-wrong
  //    asymmetry for each branch BEFORE the risk register lands.
  //    REQUIRED on every artefact per Slice 6 `cost_asymmetry_present`
  //    validator.
  slides.push({
    kind: "cost_asymmetry",
    render: (shared) => (
      <CostAsymmetrySlide costAsymmetry={payload.cost_asymmetry} {...shared} />
    ),
  });
  slides.push({
    kind: "risk_mitigation",
    render: (shared) => (
      <RiskMitigationSlide pairs={risks} {...shared} />
    ),
  });

  // ── Arc 6: Methodological honesty + In closing ─────────────────
  slides.push({
    kind: "section_divider",
    isSectionDivider: true,
    render: (shared) => (
      <SectionDivider
        sectionLabel="Honesty"
        sectionSubtitle="What this report is — and isn't."
        {...shared}
      />
    ),
  });
  slides.push({
    kind: "methodological_honesty",
    render: (shared) => (
      <MethodologicalHonestySlide
        honesty={payload.methodological_honesty}
        {...shared}
      />
    ),
  });
  slides.push({
    kind: "in_closing",
    render: (shared) => (
      <InClosingSlide inClosing={payload.in_closing} {...shared} />
    ),
  });

  return slides;
}


export default function SolvaArtefactV2({ sessionId }) {
  const [state, setState] = useState({ status: "loading", payload: null, error: null });
  // Slice 7 (2026-05-29) — session-log side-panel open state. Hooked
  // up to the topbar Session-Log icon stub (was previously dead).
  const [logPanelOpen, setLogPanelOpen] = useState(false);

  // Slice 3b — subscribe to the live reasoning stream. Hook must run
  // unconditionally before any early-return branches so React's rules-
  // of-hooks invariant holds. The hook itself short-circuits when
  // sessionId is falsy.
  const stream = useSolvaReasoningStream(sessionId, { enabled: true });

  // Mount a body-level class so the @media print stylesheet can scope
  // its chrome-strip rules without relying on `body:has(...)`. The
  // `:has()` selector is supported in modern Chromium, but some
  // browser/Playwright combinations don't resolve it under
  // emulate_media("print"). Body class is the reliable path.
  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    document.body.classList.add("solva-v2-printing-context");
    return () => {
      document.body.classList.remove("solva-v2-printing-context");
    };
  }, []);

  useEffect(() => {
    let dead = false;
    setState({ status: "loading", payload: null, error: null });
    api
      .get(`/solva/sessions/${sessionId}/v2/payload`)
      .then(({ data }) => {
        if (dead) return;
        setState({ status: "ready", payload: data.payload, error: null });
      })
      .catch((err) => {
        if (dead) return;
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail;
        if (status === 422 && detail && typeof detail === "object") {
          setState({
            status: "integrity_failed",
            payload: null,
            error: detail,
          });
          return;
        }
        setState({
          status: "error",
          payload: null,
          error: apiErrorMessage(err),
        });
      });
    return () => {
      dead = true;
    };
  }, [sessionId]);

  if (state.status === "loading") {
    return (
      <div
        className="flex items-center gap-2 text-[12.5px] text-[var(--muted)] py-12"
        data-testid="solva-v2-loading"
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading session output…
      </div>
    );
  }

  if (state.status === "integrity_failed") {
    return (
      <div
        className="border border-[var(--rule)] bg-[var(--parchment)] p-6 rounded-sm"
        data-testid="solva-v2-integrity-failed"
      >
        <div className="flex items-center gap-2 mb-3 text-[13px] text-[var(--oxblood)]">
          <AlertCircle className="w-4 h-4" />
          <strong>Report under integrity review.</strong>
        </div>
        <p className="text-[12.5px] text-[var(--deep)] mb-4">
          One or more integrity validators flagged the rendered output before release.
          This is the system pausing on its own behalf, not your data being wrong.
        </p>
        <ul className="text-[11.5px] font-mono space-y-1 text-[var(--muted)]">
          {(state.error?.blocking_offenders || []).map((o, i) => (
            <li key={i}>
              [{o.validator}] {o.location}: {o.message}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (state.status === "error" || !state.payload) {
    return (
      <div
        className="text-[12.5px] text-[var(--oxblood)] py-12"
        data-testid="solva-v2-error"
      >
        {state.error || "Unable to load Solva session output."}
      </div>
    );
  }

  const payload = state.payload;
  const contextName = payload?.cover?.prepared_for || "Context";
  const slides = composeSlides(payload);
  const total = slides.length;
  // Slide-count for the kind inventory (excludes section dividers).
  const slideOnlyCount = slides.filter((s) => !s.isSectionDivider).length;

  return (
    <>
    <article
      className="solva-v2-artefact w-full max-w-[860px] mx-auto solva-v2-print-root"
      data-testid="solva-v2-artefact-root"
      data-solva-v2-schema-version={payload.schema_version || ""}
      data-solva-v2-slide-count={String(slideOnlyCount)}
      data-solva-v2-identity-stamp="solva-canonical"
      data-solva-v2-stream-status={stream.status}
      data-solva-v2-replay-mode={stream.replayMode}
      data-solva-v2-events-received={String(stream.events.length)}
      data-solva-v2-events-total={String(stream.totalEvents)}
      data-solva-v2-is-complete={String(!!stream.isComplete)}
    >
      {/* Stream host element — always mounted alongside the artefact so
          any test can deterministically locate the reasoning-stream
          subsystem regardless of which ticker stage is currently
          visible. The visible ticker (active / pill / icon) is mounted
          immediately below. */}
      <div
        data-testid="solva-v2-reasoning-stream-host"
        data-solva-v2-current-layer={stream.currentLayer || ""}
        data-solva-v2-current-layer-name={stream.currentLayerName || ""}
        data-solva-v2-current-step={stream.currentStep || ""}
        data-solva-v2-stream-status={stream.status}
        className="sr-only"
        aria-live="polite"
      >
        {stream.currentStep || ""}
      </div>
      <SolvaReasoningTicker
        currentLayer={stream.currentLayer}
        currentLayerName={stream.currentLayerName}
        currentStep={stream.currentStep}
        isComplete={stream.isComplete}
        totalEvents={stream.totalEvents}
        receivedEvents={stream.events.length}
        onLogIconClick={() => setLogPanelOpen(true)}
      />
      {slides.map((s, idx) => {
        // Compute per-slide state attribute from the stream's
        // slideReadyMap. Section dividers are not slides; they keep
        // their own attribute set. Placeholder slides (empty-arc
        // observational copy) get slideState="placeholder" once the
        // slide.ready event arrives — no skeleton transition.
        let slideState = "loading";
        if (s.isSectionDivider) {
          slideState = "ready";
        } else if (stream.slideReadyMap[s.kind]) {
          slideState = s.isPlaceholder ? "placeholder" : "ready";
        }
        // Slice 7 (2026-05-29) — forward the wallclock instant the
        // slide first became authoritative. SlideShell surfaces this
        // verbatim on the slide root via `data-solva-v2-slide-ready-at`
        // so verification probes can audit per-slide timing.
        const readyAt = (
          s.isSectionDivider ? null : (stream.slideReadyAtMap?.[s.kind] || null)
        );
        return s.render({
          slideNumber: idx + 1,
          totalSlides: total,
          number: idx + 1,
          total,
          contextName,
          slideState,
          readyAt,
          key: `${s.kind}-${idx}`,
        });
      })}
    </article>
    {/* Slice 7 session log side-panel — currently the topbar's `Log` icon
        only set a state stub. The panel now renders the SSE event
        timeline + per-slide ready-at timestamps for verification. */}
    <SessionLogPanel
      open={logPanelOpen}
      onClose={() => setLogPanelOpen(false)}
      stream={stream}
    />
    </>
  );
}
