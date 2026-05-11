/**
 * STUDIO sprint (2026-05-12) — PerArtefactSynisenseBadge.
 *
 * Mirrors the CHAT + SOLVA badges. Renders inline at the top of the
 * artefact detail drawer, beneath the kicker. Reads from
 * `/api/work_studio/artefacts/{kind}/{id}/synisense-breakdown`.
 *
 * Visual: mono 10px, oxblood text on oxblood-6% bg, 2px radius, 1px 6px
 * padding. Single-line summary: `N IDENTIFIERS · BRIEFING X · ENHANCE Y`.
 * Hover shows the three-layer breakdown.
 *
 * Honours `prefers-reduced-motion`.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";

export default function PerArtefactSynisenseBadge({ kind, artefactId, testId }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const reducedRef = useRef(false);
  useEffect(() => {
    reducedRef.current =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    if (!kind || !artefactId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const { data: d } = await api.get(`/work_studio/artefacts/${kind}/${artefactId}/synisense-breakdown`);
        if (!cancelled) setData(d);
      } catch {
        if (!cancelled) setData(null);
      }
    })();
    return () => { cancelled = true; };
  }, [kind, artefactId]);

  const summary = useMemo(() => {
    if (!data) return null;
    const total = data.total_identifiers_count || 0;
    const head = total === 0 ? "—" : total === 1 ? "1 IDENTIFIER" : `${total} IDENTIFIERS`;
    const parts = (data.per_surface || [])
      .filter((p) => (p.identifiers_count || 0) > 0)
      .map((p) => `${p.surface.toUpperCase()} ${p.identifiers_count}`);
    return parts.length ? `${head} · ${parts.join(" · ")}` : head;
  }, [data]);

  const totalLayers = useMemo(() => {
    if (!data) return { regex: 0, presidio: 0, llm: 0 };
    const acc = { regex: 0, presidio: 0, llm: 0 };
    (data.per_surface || []).forEach((p) => {
      acc.regex += p.layers?.regex || 0;
      acc.presidio += p.layers?.presidio || 0;
      acc.llm += p.layers?.llm || 0;
    });
    return acc;
  }, [data]);

  if (!summary) return null;
  const total = data?.total_identifiers_count || 0;

  return (
    <div data-testid={testId || `studio-synisense-${kind}-${artefactId}`}>
      <span
        className="relative inline-flex items-center"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <span
          tabIndex={0}
          className="font-mono text-[10px] uppercase tracking-[0.14em] px-[6px] py-[1px] rounded-sm bg-[rgba(122,46,46,0.06)] text-[var(--oxblood)] cursor-default"
          data-testid="studio-artefact-synisense-badge"
        >
          {summary}
        </span>
        {open && total > 0 && (
          <span
            role="tooltip"
            className="absolute left-0 top-full mt-1 z-30 whitespace-nowrap font-mono text-[10px] tracking-wide px-2 py-1 rounded-sm bg-[var(--ink)] text-[var(--parchment)]"
            style={{ transition: reducedRef.current ? "none" : "opacity 150ms ease" }}
          >
            Layer 1 regex · {totalLayers.regex} · Layer 2 Presidio · {totalLayers.presidio} · Layer 3 fallback · {totalLayers.llm}
          </span>
        )}
      </span>
      {data?.storyline && (
        <p
          className="italic text-[13px] mt-3 max-w-[60ch]"
          style={{
            fontFamily: "var(--font-display)",
            color: "var(--graphite)",
            lineHeight: 1.55,
          }}
          data-testid="studio-artefact-synisense-storyline"
        >
          {data.storyline}
        </p>
      )}
    </div>
  );
}
