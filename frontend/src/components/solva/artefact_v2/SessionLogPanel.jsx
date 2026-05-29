/**
 * Solva v2 — Session Log Side-Panel (Slice 7, 2026-05-29).
 *
 * Trust-pillar 3 polish: re-opens from the topbar's Session Log icon
 * stub (previously dead) and gives the founder a full audit of the
 * reasoning stream:
 *   • The complete SSE event timeline (layer.start, slide.ready,
 *     session.complete, etc.) with absolute timestamps
 *   • The per-slide ready-at timestamps stamped by the hook
 *   • Stream meta — total events received / total emitted, status,
 *     replay mode, completion state
 *
 * Render contract — every interactive + verification-relevant element
 * carries a `data-testid`. The panel itself is a fixed-position
 * right-aligned drawer using the same brand tokens as the artefact
 * (parchment background, ned-purple accents).
 *
 * Sub-1024 viewport behaviour: the drawer collapses to a 90vw width
 * so the founder can still close it from the right edge.
 */
import React from "react";
import { X, History, CheckCircle2 } from "lucide-react";


function formatShortIso(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    // hh:mm:ss.SSS  in 24h (locale-independent)
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    const ms = String(d.getMilliseconds()).padStart(3, "0");
    return `${hh}:${mm}:${ss}.${ms}`;
  } catch {
    return "—";
  }
}


export default function SessionLogPanel({ open, onClose, stream }) {
  if (!open) return null;

  const events = stream?.events || [];
  const slideReadyAtMap = stream?.slideReadyAtMap || {};
  const slideReadyMap = stream?.slideReadyMap || {};
  const totalEvents = stream?.totalEvents || 0;
  const receivedEvents = events.length;
  const status = stream?.status || "idle";
  const replayMode = stream?.replayMode || "replay";
  const isComplete = !!stream?.isComplete;

  // Order slide rows by the canonical deck order. Pull from the keys
  // of the ready-at map.
  const slideKinds = Object.keys(slideReadyAtMap);

  return (
    <>
      {/* Scrim. Closes the panel when clicked. Uses Tailwind brand-
          purple at allowlisted /20 opacity instead of arbitrary-value
          bg-[var(--token)]/N which silently fails on hex CSS
          variables per Wave 4.2.followup.2. */}
      <div
        className="fixed inset-0 z-40 bg-ned-purple/20"
        data-testid="solva-v2-session-log-scrim"
        onClick={onClose}
      />
      <aside
        className="fixed top-0 right-0 bottom-0 z-50 w-[480px] max-w-[90vw] bg-[var(--parchment)] border-l border-ned-purple/30 shadow-lg flex flex-col"
        data-testid="solva-v2-session-log-panel"
        data-solva-v2-session-log-open="true"
        role="dialog"
        aria-label="Solva session log"
      >
        {/* Header */}
        <header className="flex items-center justify-between px-5 py-4 border-b border-[var(--rule)]">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-[var(--ned-purple)]" />
            <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--ink)]">
              Session log
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-ned-purple/10 transition-colors"
            data-testid="solva-v2-session-log-close"
            aria-label="Close session log"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        {/* Stream meta */}
        <div className="px-5 py-3 border-b border-[var(--rule)] bg-white/40">
          <dl
            className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]"
            data-testid="solva-v2-session-log-meta"
          >
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Status</dt>
            <dd
              className="text-[var(--ink)] font-mono text-[11px]"
              data-testid="solva-v2-session-log-status"
            >
              {status}
              {isComplete && (
                <CheckCircle2 className="inline w-3 h-3 ml-1.5 text-[var(--ned-purple)]" />
              )}
            </dd>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Mode</dt>
            <dd
              className="text-[var(--ink)] font-mono text-[11px]"
              data-testid="solva-v2-session-log-mode"
            >
              {replayMode}
            </dd>
            <dt className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">Events</dt>
            <dd
              className="text-[var(--ink)] font-mono text-[11px] tabular-nums"
              data-testid="solva-v2-session-log-events-count"
            >
              {receivedEvents} received · {totalEvents} total
            </dd>
          </dl>
        </div>

        {/* Per-slide ready-at table */}
        <div className="flex-1 overflow-y-auto">
          <section className="px-5 py-4 border-b border-[var(--rule)]">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] mb-2.5">
              Per-slide ready-at
            </p>
            <table
              className="w-full text-[12px]"
              data-testid="solva-v2-session-log-slide-table"
            >
              <tbody>
                {slideKinds.map((kind) => {
                  const ts = slideReadyAtMap[kind];
                  const ready = slideReadyMap[kind];
                  return (
                    <tr
                      key={kind}
                      data-testid={`solva-v2-session-log-slide-row-${kind}`}
                      data-solva-v2-session-log-slide-kind={kind}
                      data-solva-v2-session-log-slide-ready-at={ts || ""}
                      className="border-b border-[var(--rule)] last:border-b-0"
                    >
                      <td className="py-1.5 pr-3 font-mono text-[10.5px] text-[var(--ink)] tracking-tight">
                        {kind}
                      </td>
                      <td className="py-1.5 pr-3 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
                        {ready ? "ready" : "loading"}
                      </td>
                      <td className="py-1.5 font-mono text-[10.5px] tabular-nums text-[var(--ink)] text-right">
                        {formatShortIso(ts)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>

          {/* SSE event timeline */}
          <section className="px-5 py-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] mb-2.5">
              SSE event timeline
            </p>
            <ol
              className="space-y-1"
              data-testid="solva-v2-session-log-event-list"
            >
              {events.length === 0 && (
                <li className="text-[12px] text-[var(--muted)] italic">
                  No events received yet.
                </li>
              )}
              {events.map((ev, idx) => (
                <li
                  key={idx}
                  className="grid grid-cols-[56px_1fr] gap-x-3 py-1 border-b border-[var(--rule)] last:border-b-0"
                  data-testid={`solva-v2-session-log-event-${idx}`}
                  data-solva-v2-session-log-event-kind={ev?.step_kind || ""}
                >
                  <span className="font-mono text-[10px] text-[var(--muted)] tabular-nums">
                    #{String(idx + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <p className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-[var(--ned-purple)]">
                      {ev?.step_kind || "unknown"}
                      {ev?.slide_kind && (
                        <span className="text-[var(--muted)] normal-case ml-1.5 tracking-tight">
                          → {ev.slide_kind}
                        </span>
                      )}
                    </p>
                    {ev?.step_description && (
                      <p className="text-[11.5px] text-[var(--deep)] leading-snug mt-0.5">
                        {ev.step_description}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </aside>
    </>
  );
}
