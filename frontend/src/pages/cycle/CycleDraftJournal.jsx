/**
 * CycleDraftJournal — T5 (2026-05-25).
 *
 * Spec §4.B → C6. The Draft Journal lists every agent-cycle-drafted
 * follow-up email across all active cycles in this context. Two CTAs
 * per entry: "Approve and Send" → sends via SendGrid + badge flips
 * to `Sent`; "Decline" → badge flips to `Declined`.
 *
 * Entry points (spec C6 step 1):
 *   • `View More` on the Cycle Manager landing side panel.
 *   • The "Follow Up" CTA in §4.3 Section 3 of the Cycle Page — when
 *     opened from there, the journal is pre-filtered to that specific
 *     cycle via the `?cycle_id=<id>` query string.
 *
 * DOM-unconditional rule: the page emits the empty state ("No drafts
 * waiting for you.") with the same scaffolding as the populated state.
 *
 * This page is the C6 Draft Journal scaffold. The list itself is
 * driven by the existing follow-up endpoint inventory; if no entries
 * are returned, the page renders the empty state with the verbatim
 * spec copy ("Drafts Waiting for You").
 */
import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { ArrowLeft, Mail, Send, X } from "lucide-react";
import { toast } from "sonner";

export default function CycleDraftJournal() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [search] = useSearchParams();
  const cycleFilter = search.get("cycle_id") || "";
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!cid) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const resp = await api.get(`/contexts/${cid}/cycles/follow-ups`, {
          params: cycleFilter ? { cycle_id: cycleFilter } : undefined,
        }).catch(() => ({ data: { followups: [] } }));
        if (!alive) return;
        setDrafts(resp.data?.followups || resp.data?.drafts || []);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [cid, cycleFilter]);

  const onApprove = async (id) => {
    try {
      await api.post(`/contexts/${cid}/cycles/follow-ups/${id}/send`);
      toast.success("Follow-up sent.");
      setDrafts((rows) => rows.map((r) => r.id === id ? { ...r, status: "sent" } : r));
    } catch (e) {
      toast.error("Failed to send. Please try again.");
    }
  };

  const onDecline = async (id) => {
    try {
      await api.post(`/contexts/${cid}/cycles/follow-ups/${id}/decline`);
      toast.success("Follow-up declined.");
      setDrafts((rows) => rows.map((r) => r.id === id ? { ...r, status: "declined" } : r));
    } catch (e) {
      toast.error("Failed to decline. Please try again.");
    }
  };

  return (
    <AppShell>
      <div className="px-6 py-4 border-b border-[var(--rule)] bg-white flex items-center gap-3"
           data-testid="cycle-draft-journal-header">
        <Link
          to="/app/cycle"
          className="text-[12px] inline-flex items-center gap-1.5 text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="cycle-draft-journal-back"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.7} />
          Cycle Manager
        </Link>
        <span className="text-[var(--muted)]">/</span>
        <span className="text-[12px] text-[var(--ink)] akki-serif">Drafts Waiting for You</span>
      </div>
      <section className="px-6 py-6" data-testid="cycle-draft-journal-body">
        {loading && (
          <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="cycle-draft-journal-loading">
            Loading drafts…
          </p>
        )}
        {!loading && drafts.length === 0 && (
          <div
            className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-12 text-center"
            data-testid="cycle-draft-journal-empty"
          >
            <p className="akki-serif text-[16px] text-[var(--ink)]">No drafts waiting for you.</p>
            <p className="text-[12px] text-[var(--muted)] mt-2 max-w-prose mx-auto">
              When Agent Cycle drafts a follow-up email, it'll appear here for your approval.
            </p>
          </div>
        )}
        {!loading && drafts.length > 0 && (
          <ul className="space-y-3" data-testid="cycle-draft-journal-list">
            {drafts.map((d) => (
              <li
                key={d.id}
                className="border border-[var(--rule)] rounded-sm bg-white px-4 py-3"
                data-testid={`cycle-draft-row-${d.id}`}
              >
                <div className="flex items-start gap-2">
                  <Mail className="w-4 h-4 mt-1 text-[var(--muted)]" strokeWidth={1.7} />
                  <div className="flex-1 min-w-0">
                    <p className="akki-serif text-[13.5px] text-[var(--ink)] truncate">
                      {d.subject || "(no subject)"}
                    </p>
                    <p className="text-[11.5px] text-[var(--muted)] mt-0.5 font-mono">
                      To: {d.recipient_name || d.recipient_email || "Contributor"} · Cycle: {d.cycle_title || d.cycle_id || "—"}
                      {d.agenda_item ? ` · For: ${d.agenda_item}` : ""}
                    </p>
                  </div>
                  <span
                    className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] px-1.5 py-0.5 border border-[var(--rule)] rounded-sm"
                    data-testid={`cycle-draft-row-${d.id}-status`}
                  >
                    {(d.status || "draft").toUpperCase()}
                  </span>
                </div>
                {(d.status || "draft") === "draft" && (
                  <div className="flex gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => onApprove(d.id)}
                      className="text-[12px] inline-flex items-center gap-1.5 px-2.5 py-1 bg-[var(--ink)] text-[var(--parchment)] rounded-sm"
                      data-testid={`cycle-draft-row-${d.id}-approve`}
                    >
                      <Send className="w-3 h-3" /> Approve and Send
                    </button>
                    <button
                      type="button"
                      onClick={() => onDecline(d.id)}
                      className="text-[12px] inline-flex items-center gap-1.5 px-2.5 py-1 border border-[var(--rule)] rounded-sm"
                      data-testid={`cycle-draft-row-${d.id}-decline`}
                    >
                      <X className="w-3 h-3" /> Decline
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}
