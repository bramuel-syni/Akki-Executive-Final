/**
 * Phase ZZ.2 (2026-02 fork-resume v2) — Tier 1 + Tier 2 Solva
 * governance signals on every assistant chat bubble.
 *
 *  • Bias chips — `[anchoring · Q4 number]` style tags surfaced as
 *    inline chips so the user can see what reasoning pattern the
 *    model flagged in itself.
 *  • Unsourced-claim warning — when the backend validator flags a
 *    numeric claim without a source, render an inline italic note.
 *  • Solva escalation CTA — when the message was a recommendation
 *    request AND stakes language was present, render a single-line
 *    CTA at the bottom of the bubble. Routes to /app/solva.
 *  • Adversarial nudge — backend prompt instructs the model to
 *    OPEN with the counter-case; we don't render a visual flag for
 *    that (it's in the text itself).
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { resolveBackendOrigin } from "@/lib/api";

// Phase P5.6.1 (2026-02) — same-origin guard. See lib/api.js.
const API = resolveBackendOrigin();

export default function GovernanceSignals({ governance, chatId, messageId }) {
  const navigate = useNavigate();
  if (!governance) return null;
  const {
    bias_flags = [],
    numeric_claims_unsourced = 0,
    escalate_to_solva = false,
  } = governance || {};

  if (!bias_flags.length && !numeric_claims_unsourced && !escalate_to_solva) return null;

  async function handleEscalationClick(e) {
    e.preventDefault();
    try {
      if (chatId) {
        const token = localStorage.getItem("akki_token");
        await axios.post(
          `${API}/api/chats/${chatId}/governance/solva-escalation-clicked`,
          { message_id: messageId || null },
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
      }
    } catch (_err) { /* non-fatal — navigation still proceeds */ }
    navigate("/app/solva");
  }

  return (
    <div className="chat-governance mt-2 flex flex-col gap-1.5" data-testid="chat-governance-signals" data-testid-zz2="zz2-governance-signals">
      {bias_flags.length > 0 && (
        <div className="flex flex-wrap gap-1.5" data-testid="chat-governance-bias-chips">
          {bias_flags.map((tag, i) => {
            const kind = String(tag).split(" · ")[0].trim();
            return (
              <span key={`bias-${i}`}
                className="inline-flex items-center font-mono text-[10px] uppercase tracking-[0.10em] px-2 py-[2px] rounded-sm border border-[var(--ned-purple)]/30 text-[var(--ned-purple)] bg-[var(--ned-purple)]/5"
                data-testid="zz2-bias-chip"
                data-bias-kind={kind}
                title="Reasoning pattern surfaced by Akki on its own draft"
              >
                [{tag}]
              </span>
            );
          })}
        </div>
      )}
      {numeric_claims_unsourced > 0 && (
        <p className="text-[11.5px] italic text-[color:var(--oxblood)]" data-testid="zz2-unsourced-warning">
          {numeric_claims_unsourced === 1
            ? "Akki flagged 1 numeric claim it could not source against your attached documents."
            : `Akki flagged ${numeric_claims_unsourced} numeric claims it could not source against your attached documents.`}
        </p>
      )}
      {escalate_to_solva && (
        <button
          type="button"
          onClick={handleEscalationClick}
          className="inline-flex items-center self-start font-mono text-[10.5px] uppercase tracking-[0.10em] px-2.5 py-1 rounded-sm border border-[var(--ned-purple)]/30 text-[var(--ned-purple)] hover:bg-[var(--ned-purple)]/5 transition-colors"
          data-testid="zz2-solva-escalation"
          aria-label="Run this through Solva for the full 16-slide diagnostic"
        >
          Run this through Solva for the full 16-slide diagnostic →
        </button>
      )}
    </div>
  );
}
