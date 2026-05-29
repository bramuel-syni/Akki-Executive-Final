/**
 * Solva v2 — SolvaArtefactV2 orchestrator (Slice 2a, 2026-05-29).
 *
 * Fetches the structured artefact payload from
 *   GET /api/solva/sessions/{sid}/v2/payload
 * (feature-flag gated; returns 404 when v2 is OFF for the account).
 *
 * Renders the 15-element slide-paginated artefact by walking a
 * `slides[]` array derived from the payload. The shape of each slide
 * entry is `{ kind, component, props }`.
 *
 * Slice 2a ships 4 core slide kinds + 1 section divider:
 *   • cover
 *   • headline
 *   • tensions_overview
 *   • pathway
 *   • (section_divider transitions interleave the above)
 *
 * Slice 2b will add the remaining 9 slide kinds (per_tension,
 * scenarios_overview, per_scenario_confidence_table, sensitivity,
 * reflection, decision_logic, risk_mitigation, methodological_honesty,
 * in_closing). Slices not yet built are LOGGED as a backlog hint in
 * the rendered DOM so the founder can see what's coming.
 *
 * Print-to-PDF: every slide carries `print:break-after-page` so a
 * browser print produces one slide per page. No server-side dependency.
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Loader2, AlertCircle } from "lucide-react";
import SectionDivider from "./SectionDivider";
import CoverSlide from "./slides/CoverSlide";
import HeadlineSlide from "./slides/HeadlineSlide";
import TensionsOverviewSlide from "./slides/TensionsOverviewSlide";
import PathwaySlide from "./slides/PathwaySlide";


/**
 * Compose the slide sequence from the payload. Each entry pairs a
 * kind with a render function — keeps the orchestrator's JSX tight
 * and Slice 2b's incremental additions a single-array-entry change.
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

  // 3 — Tensions section divider + overview
  if ((payload.tensions || []).length > 0) {
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
        <TensionsOverviewSlide tensions={payload.tensions} {...shared} />
      ),
    });
  }

  // 9 — Pathway section divider + slide
  if ((payload.pathway || []).length > 0) {
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
    slides.push({
      kind: "pathway",
      render: (shared) => <PathwaySlide pathway={payload.pathway} {...shared} />,
    });
  }

  // Slice 2b backlog hint — render a placeholder so the founder sees
  // what's coming without a confusing gap.
  slides.push({
    kind: "slice_2b_backlog_hint",
    render: (shared) => (
      <SectionDivider
        kind="slice_2b_backlog_hint"
        sectionLabel="More to come"
        sectionSubtitle="Per-tension deep dives, scenarios, sensitivity, reflection, decision logic, methodological honesty, and the in-closing reframing land in the next dispatch."
        {...shared}
      />
    ),
  });

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
      className="solva-v2-artefact max-w-[860px] mx-auto"
      data-testid="solva-v2-artefact-root"
      data-solva-v2-schema-version={payload.schema_version || ""}
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
