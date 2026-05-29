/**
 * Solva v2 — SolvaArtefactV2 orchestrator (Slice 2b, 2026-05-29).
 *
 * Fetches the structured artefact payload from
 *   GET /api/solva/sessions/{sid}/v2/payload
 * (feature-flag gated; returns 404 when v2 is OFF for the account).
 *
 * Renders the 15-element slide-paginated artefact by walking a
 * `slides[]` array derived from the payload. The shape of each slide
 * entry is `{ kind, render }`.
 *
 * Slice 2b composes the full 13 slide kinds + section dividers:
 *   • cover
 *   • headline
 *   • section_divider → tensions_overview → per_tension (×N)
 *   • section_divider → scenarios_overview → per_scenario_confidence_table → sensitivity
 *   • section_divider → reflection
 *   • section_divider → pathway → decision_logic → risk_mitigation
 *   • section_divider → methodological_honesty → in_closing
 *
 * Print-to-PDF: every slide carries `print:break-after-page` so a
 * browser print produces one slide per page. The global print stylesheet
 * (index.css) hides the AppShell sidebar / topbar / banners so the
 * printed output is a clean deck.
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Loader2, AlertCircle } from "lucide-react";
import SectionDivider from "./SectionDivider";
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
import MethodologicalHonestySlide from "./slides/MethodologicalHonestySlide";
import InClosingSlide from "./slides/InClosingSlide";


/**
 * Compose the slide sequence from the payload. Returns an array of
 * `{ kind, render }` entries the JSX loop renders below. Section
 * dividers are interleaved so the deck reads in 5 narrative arcs:
 *   1. Cover + Headline
 *   2. Tensions (overview + per-tension deep dives)
 *   3. Scenarios + Confidence table + Sensitivity
 *   4. Reflection
 *   5. Pathway + Decision logic + Risk register
 *   6. Methodological honesty + In closing
 */
function composeSlides(payload) {
  const slides = [];

  // 1 — Cover
  slides.push({
    kind: "cover",
    render: (shared) => <CoverSlide cover={payload.cover} {...shared} />,
  });

  // 2 — Headline
  slides.push({
    kind: "headline",
    render: (shared) => <HeadlineSlide headline={payload.headline} {...shared} />,
  });

  // 3 — Tensions
  const tensions = payload.tensions || [];
  const deepDives = payload.per_tension_deep_dive || [];
  if (tensions.length > 0) {
    slides.push({
      kind: "section_divider_tensions",
      render: (shared) => (
        <SectionDivider
          kind="section_divider"
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
    // Per-tension deep-dive slide per tension
    tensions.forEach((t) => {
      const dd = deepDives.find((d) => d.tension_number === t.number) || null;
      slides.push({
        kind: "per_tension",
        render: (shared) => (
          <PerTensionSlide tension={t} deepDive={dd} {...shared} />
        ),
      });
    });
  }

  // 4 — Scenarios + Confidence table + Sensitivity
  const scenarios = payload.scenarios || [];
  const confTable = payload.per_scenario_confidence_table || { rows: [] };
  const sensitivity = payload.sensitivity_inputs || [];
  if (scenarios.length > 0 || sensitivity.length > 0) {
    slides.push({
      kind: "section_divider_scenarios",
      render: (shared) => (
        <SectionDivider
          kind="section_divider"
          sectionLabel="Scenarios"
          sectionSubtitle="How the evidence distributes — weights, confidence, sensitivity."
          {...shared}
        />
      ),
    });
    if (scenarios.length > 0) {
      slides.push({
        kind: "scenarios_overview",
        render: (shared) => (
          <ScenariosOverviewSlide scenarios={scenarios} {...shared} />
        ),
      });
      slides.push({
        kind: "per_scenario_confidence_table",
        render: (shared) => (
          <PerScenarioConfidenceTable table={confTable} {...shared} />
        ),
      });
    }
    if (sensitivity.length > 0) {
      slides.push({
        kind: "sensitivity",
        render: (shared) => (
          <SensitivitySlide sensitivity={sensitivity} {...shared} />
        ),
      });
    }
  }

  // 5 — Reflection (always present — schema requires exactly 3 questions)
  if (payload.reflection_section) {
    slides.push({
      kind: "section_divider_reflection",
      render: (shared) => (
        <SectionDivider
          kind="section_divider"
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
          reflection={payload.reflection_section}
          {...shared}
        />
      ),
    });
  }

  // 6 — Pathway + Decision logic + Risk register
  const pathway = payload.pathway || [];
  const decisions = payload.decision_logic || [];
  const risks = payload.risk_mitigation || [];
  if (pathway.length > 0 || decisions.length > 0 || risks.length > 0) {
    slides.push({
      kind: "section_divider_pathway",
      render: (shared) => (
        <SectionDivider
          kind="section_divider"
          sectionLabel="Pathway"
          sectionSubtitle="What the weighted picture supports as next moves."
          {...shared}
        />
      ),
    });
    if (pathway.length > 0) {
      slides.push({
        kind: "pathway",
        render: (shared) => <PathwaySlide pathway={pathway} {...shared} />,
      });
    }
    if (decisions.length > 0) {
      slides.push({
        kind: "decision_logic",
        render: (shared) => (
          <DecisionLogicSlide branches={decisions} {...shared} />
        ),
      });
    }
    if (risks.length > 0) {
      slides.push({
        kind: "risk_mitigation",
        render: (shared) => (
          <RiskMitigationSlide pairs={risks} {...shared} />
        ),
      });
    }
  }

  // 7 — Methodological honesty + In closing (always present)
  if (payload.methodological_honesty || payload.in_closing) {
    slides.push({
      kind: "section_divider_honesty",
      render: (shared) => (
        <SectionDivider
          kind="section_divider"
          sectionLabel="Honesty"
          sectionSubtitle="What this report is — and isn't."
          {...shared}
        />
      ),
    });
    if (payload.methodological_honesty) {
      slides.push({
        kind: "methodological_honesty",
        render: (shared) => (
          <MethodologicalHonestySlide
            honesty={payload.methodological_honesty}
            {...shared}
          />
        ),
      });
    }
    if (payload.in_closing) {
      slides.push({
        kind: "in_closing",
        render: (shared) => (
          <InClosingSlide inClosing={payload.in_closing} {...shared} />
        ),
      });
    }
  }

  return slides;
}


export default function SolvaArtefactV2({ sessionId }) {
  const [state, setState] = useState({ status: "loading", payload: null, error: null });

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
        // 404 = flag off or session missing; 422 = integrity validators failed.
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

  return (
    <article
      className="solva-v2-artefact max-w-[860px] mx-auto solva-v2-print-root"
      data-testid="solva-v2-artefact-root"
      data-solva-v2-schema-version={payload.schema_version || ""}
      data-solva-v2-slide-count={String(total)}
    >
      {slides.map((s, idx) =>
        s.render({
          slideNumber: idx + 1,
          totalSlides: total,
          number: idx + 1,
          total,
          contextName,
          key: `${s.kind}-${idx}`,
        }),
      )}
    </article>
  );
}
