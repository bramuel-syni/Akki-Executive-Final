/**
 * InboundQueueCard — Home surface for Tier-C (unknown-sender) inbound
 * emails awaiting the owner's review.
 *
 * Behaviour:
 *  - Renders a compact pending-count card when count > 0.
 *  - Renders a dashed-outline "quiet" state when count === 0 (so the
 *    WorkflowsHub inbound tab doesn't look empty).
 *  - Link navigates to /app/inbound-queue for triage.
 *
 * Trust provenance is the product headline here — the copy reads as
 * an editorial observation, not a notification badge.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Inbox, ArrowRight, ShieldCheck } from "lucide-react";

export default function InboundQueueCard() {
  const [state, setState] = useState({ total: 0, byContext: [], loaded: false });

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const { data } = await api.get("/me/inbound-queue/counts");
        if (!live) return;
        setState({
          total: data.total_pending || 0,
          byContext: data.by_context || [],
          loaded: true,
        });
      } catch {
        if (live) setState({ total: 0, byContext: [], loaded: true });
      }
    })();
    return () => { live = false; };
  }, []);

  if (!state.loaded) return null;

  if (state.total === 0) {
    return (
      <article
        className="bg-white border border-dashed border-[var(--rule)] rounded-md p-4"
        data-testid="home-inbound-queue-empty"
      >
        <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mb-1.5 flex items-center gap-1.5">
          <Inbox className="w-3 h-3" /> Inbound review
        </p>
        <p className="text-[13px] text-[var(--muted)] italic leading-relaxed">
          Nothing waiting. Emails from you and your reportees file themselves —
          emails from unknown senders land here for review before anything is ingested.
        </p>
      </article>
    );
  }

  return (
    <article
      className="bg-white border border-[var(--rule)] rounded-md p-4"
      data-testid="home-inbound-queue-card"
    >
      <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-2 flex items-center gap-1.5">
        <Inbox className="w-3 h-3" /> Inbound review · {state.total} waiting
      </p>
      <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-3">
        {state.total === 1
          ? "An email from an unknown sender is waiting for your review before AKKI ingests it."
          : `${state.total} emails from unknown senders are waiting for your review before AKKI ingests anything.`}
      </p>

      {state.byContext.length > 0 && (
        <ul className="mb-3 space-y-1 text-[12px]" data-testid="home-inbound-queue-breakdown">
          {state.byContext.slice(0, 4).map((c) => (
            <li
              key={c.context_id}
              className="flex items-center justify-between gap-2 text-[var(--deep)]"
            >
              <span className="truncate">{c.context_name || "Untitled workspace"}</span>
              <span className="font-mono tabular-nums text-[var(--accent)] shrink-0">
                {c.pending}
              </span>
            </li>
          ))}
          {state.byContext.length > 4 && (
            <li className="text-[11px] italic text-[var(--muted)]">
              + {state.byContext.length - 4} more
            </li>
          )}
        </ul>
      )}

      <div className="flex items-center justify-between gap-2 pt-2 border-t border-[var(--rule)]">
        <span className="text-[10.5px] text-[var(--muted)] flex items-center gap-1">
          <ShieldCheck className="w-3 h-3" /> Quarantined — nothing ingested yet
        </span>
        <Link
          to="/app/inbound-queue"
          className="inline-flex items-center gap-1 text-[11.5px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline"
          data-testid="home-inbound-queue-review-link"
        >
          Review <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </article>
  );
}
