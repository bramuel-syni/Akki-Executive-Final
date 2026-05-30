/**
 * Z2.8 (2026-02) — On-screen chair-readable speaker-notes strip.
 *
 * Rendered beneath each slide when the topbar `Notes` toggle is ON
 * (parent owns the toggle state). Reads from
 * `GET /api/solva/sessions/{sid}/v2/chair_notes` once per session.
 * Hidden in print. Reuses existing typographic register — no new
 * fonts, no new colour tokens.
 */
import React, { useEffect, useState } from "react";
import { api } from "../../../lib/api";

export default function ChairNotesStrip({ sessionId, slideKind, visible }) {
  const [byKind, setByKind] = useState(null);
  useEffect(() => {
    if (!visible || !sessionId || byKind) return;
    let cancelled = false;
    api.get(`/solva/sessions/${sessionId}/v2/chair_notes`)
      .then(({ data }) => { if (!cancelled) setByKind(data?.notes || {}); })
      .catch(() => { if (!cancelled) setByKind({}); });
    return () => { cancelled = true; };
  }, [visible, sessionId, byKind]);
  if (!visible) return null;
  const lines = (byKind || {})[slideKind] || [];
  return (
    <aside
      className="chair-notes-strip print:hidden mt-2 mb-4 mx-auto max-w-[68ch] border-l-2 pl-3 py-2"
      style={{
        borderColor: "color-mix(in srgb, var(--ned-purple) 40%, transparent)",
        backgroundColor: "color-mix(in srgb, var(--parchment) 40%, transparent)",
      }}
      role="note" aria-live="polite"
      aria-label={`Chair notes for ${slideKind.replace(/_/g, " ")}`}
      data-testid={`solva-v2-chair-notes-strip-${slideKind}`}
      data-solva-v2-chair-notes-slide={slideKind}
    >
      {lines.length === 0 ? (
        <p className="text-[11px] text-[var(--muted)] italic">Loading chair notes…</p>
      ) : (
        <ul className="space-y-1">
          {lines.map((ln, i) => (
            <li
              key={`${slideKind}-note-${i}`}
              className="text-[12px] leading-snug font-mono"
              style={{ color: "color-mix(in srgb, var(--ink) 85%, transparent)" }}
              data-testid="solva-v2-chair-notes-line"
            >{ln}</li>
          ))}
        </ul>
      )}
    </aside>
  );
}
