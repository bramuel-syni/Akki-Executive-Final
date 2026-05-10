/**
 * JudgementPanel.jsx — Phase D.3 (Promise 4)
 *
 * Sits above the six-step strip in the Cycle Manager and surfaces, in
 * one glance, the three judgement signals that change what the
 * executive should do next:
 *
 *   1. N follow-ups awaiting approval        (pending judgement work)
 *   2. Readiness X% — {storyline first line}  (live cycle health)
 *   3. Compile readiness ✓ / ✗                (gate on the Ship act)
 *
 * Click-targets jump straight to the step that owns each signal so
 * the panel is also a covert navigator. The component is read-only:
 * all data is reused from props that the Cycle page already loads
 * (no extra API calls).
 */
import React from "react";
import { Mail, BarChart3, FileDown, CheckCircle2, AlertCircle } from "lucide-react";

export default function JudgementPanel({ readiness, followups = [], onJump }) {
  const pendingApprovals = followups.filter((f) => f.status === "draft").length;
  const overall = typeof readiness?.overall === "number" ? readiness.overall : null;
  const storylineLead =
    readiness?.storyline && readiness.storyline.length > 0
      ? readiness.storyline[0]
      : null;
  // Compile readiness mirrors the backend rule: ≥1 ready item and no
  // missing-status items (we surface a soft proxy here so the executive
  // doesn't have to drill into the Scoreboard).
  const items = readiness?.items || [];
  const readyCount = items.filter((i) => i.status === "ready").length;
  const missingCount = items.filter((i) => i.status === "missing").length;
  const compileReady = items.length > 0 && readyCount > 0 && missingCount === 0;

  return (
    <section
      data-testid="cycle-judgement-panel"
      aria-label="Wants your judgement"
      className="border border-[var(--rule)] bg-[var(--cream-deep)]/40 rounded-md px-5 py-4 mb-5"
    >
      <p className="akki-overline text-[var(--muted)] mb-3">Wants your judgement</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" data-testid="cycle-judgement-panel-tiles">
        {/* Tile 1 — pending follow-up approvals */}
        <button
          type="button"
          onClick={() => onJump && onJump("followups")}
          className="text-left border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[var(--accent)] transition-colors"
          data-testid="cycle-judgement-tile-followups"
        >
          <div className="flex items-center gap-2 mb-1">
            <Mail className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.7} />
            <span className="akki-overline text-[var(--muted)]">Follow-ups</span>
          </div>
          {pendingApprovals > 0 ? (
            <p className="akki-serif text-[15px] text-[var(--ink)]" data-testid="cycle-judgement-followups-count">
              <strong className="text-[20px]">{pendingApprovals}</strong> awaiting your approval
            </p>
          ) : (
            <p className="akki-serif text-[14px] text-[var(--muted)]" data-testid="cycle-judgement-followups-clear">
              No drafts pending approval.
            </p>
          )}
        </button>

        {/* Tile 2 — readiness storyline */}
        <button
          type="button"
          onClick={() => onJump && onJump("scoreboard")}
          className="text-left border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[var(--accent)] transition-colors"
          data-testid="cycle-judgement-tile-readiness"
        >
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.7} />
            <span className="akki-overline text-[var(--muted)]">Readiness</span>
          </div>
          {overall === null ? (
            <p className="akki-serif text-[14px] text-[var(--muted)]" data-testid="cycle-judgement-readiness-empty">
              No data yet.
            </p>
          ) : (
            <>
              <p className="akki-serif text-[15px] text-[var(--ink)]" data-testid="cycle-judgement-readiness-overall">
                <strong className="text-[20px]">{overall}%</strong> overall
              </p>
              {storylineLead && (
                <p
                  className="text-[12.5px] text-[var(--muted)] leading-[1.5] mt-1 line-clamp-2"
                  title={storylineLead}
                  data-testid="cycle-judgement-readiness-storyline"
                >
                  {storylineLead}
                </p>
              )}
            </>
          )}
        </button>

        {/* Tile 3 — compile readiness gate */}
        <button
          type="button"
          onClick={() => onJump && onJump("compilation")}
          className="text-left border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[var(--accent)] transition-colors"
          data-testid="cycle-judgement-tile-compile"
        >
          <div className="flex items-center gap-2 mb-1">
            <FileDown className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.7} />
            <span className="akki-overline text-[var(--muted)]">Compile</span>
          </div>
          {compileReady ? (
            <p
              className="akki-serif text-[15px] text-emerald-800 inline-flex items-center gap-1.5"
              data-testid="cycle-judgement-compile-ready"
            >
              <CheckCircle2 className="w-4 h-4" strokeWidth={1.8} />
              Ready to compile
            </p>
          ) : (
            <p
              className="akki-serif text-[14px] text-amber-900 inline-flex items-center gap-1.5"
              data-testid="cycle-judgement-compile-blocked"
            >
              <AlertCircle className="w-4 h-4" strokeWidth={1.8} />
              {items.length === 0
                ? "Add agenda items first."
                : missingCount > 0
                  ? `${missingCount} item${missingCount === 1 ? "" : "s"} still missing`
                  : "No item is ready yet."}
            </p>
          )}
        </button>
      </div>
    </section>
  );
}
