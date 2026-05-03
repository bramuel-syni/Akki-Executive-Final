/**
 * ActionsTab — Cycle Manager → Actions.
 *
 * Phase 13.2 — "Action Items progress" surface aggregating three
 * data sources via the new `/api/contexts/{cid}/cycle/actions`
 * endpoint:
 *
 *   1. signal_actions   — open/in-progress actions logged against
 *                         signals (Risk / Gap / Opportunity)
 *   2. plays in-flight  — running play instances (Workflows) that
 *                         have not been completed
 *   3. cycle_pending    — cycle submissions whose status is not
 *                         "complete" (drafted, in-review, sent-back)
 *
 * No new collections — this is a thin aggregator over existing data.
 * Each item shows title, source context, status, owner (if set), due
 * (if set). Clicking an item routes the user to the source artefact.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Activity, Workflow, Inbox, ArrowRight, Loader2, CheckCircle2,
  AlertCircle, Clock,
} from "lucide-react";

function shortDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short", day: "numeric",
    });
  } catch { return null; }
}

const SECTION_META = {
  signal_actions: {
    icon: Activity,
    label: "Signal Actions",
    blurb: "Open and in-progress actions you've logged against board signals.",
  },
  plays: {
    icon: Workflow,
    label: "In-Flight Plays",
    blurb: "Workflows you've started in Plays that haven't yet been closed out.",
  },
  cycle_pending: {
    icon: Inbox,
    label: "Pending Submissions",
    blurb: "Cycle submissions that are still drafted, in review, or sent back for changes.",
  },
};

function StatusBadge({ status }) {
  if (!status) return null;
  const s = String(status).toLowerCase();
  const cls =
    s === "complete" || s === "approved" || s === "closed"
      ? "text-emerald-700 bg-emerald-50 border-emerald-100"
      : s.includes("send_back") || s.includes("rejected") || s === "at_risk"
        ? "text-rose-700 bg-rose-50 border-rose-100"
        : "text-[var(--deep)] bg-[var(--cream-deep)] border-[var(--rule)]";
  return (
    <span className={`inline-flex items-center text-[10.5px] uppercase tracking-[0.14em] font-medium border rounded-sm px-1.5 py-[2px] ${cls}`}>
      {s.replace(/_/g, " ")}
    </span>
  );
}

function ActionRow({ item }) {
  const due = shortDate(item.due_at);
  return (
    <li className="border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between" data-testid="actions-row">
      <div className="min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <p className="text-[14px] text-[var(--ink)] truncate">{item.title || "Untitled"}</p>
          <StatusBadge status={item.status} />
        </div>
        <p className="text-[12px] text-[var(--muted)] flex flex-wrap items-center gap-x-3 gap-y-0.5">
          {item.context_name && <span>{item.context_name}</span>}
          {item.owner_email && <span>· {item.owner_email}</span>}
          {due && <span className="inline-flex items-center gap-1"><Clock className="w-3 h-3" /> {due}</span>}
        </p>
      </div>
      {item.href && (
        <Link to={item.href} className="shrink-0">
          <Button variant="ghost" size="sm" className="text-[12.5px] text-[var(--accent)] hover:bg-[var(--accent-soft)]">
            Open <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </Link>
      )}
    </li>
  );
}

export default function ActionsTab({ contextId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    setErr(null);
    try {
      const { data } = await api.get(`/contexts/${contextId}/cycle/actions`);
      setData(data);
    } catch (e) {
      setErr(apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  const sectionOrder = useMemo(() => ["signal_actions", "plays", "cycle_pending"], []);
  const totalCount = (data?.counts && Object.values(data.counts).reduce((a, b) => a + (b || 0), 0)) || 0;

  if (loading) {
    return (
      <div className="p-12 text-center text-[var(--muted)] text-sm flex items-center justify-center gap-2" data-testid="actions-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading action items…
      </div>
    );
  }

  if (err && !data) {
    return (
      <div className="p-8 text-center text-[var(--muted)] text-sm flex items-center justify-center gap-2 border border-[var(--rule)] rounded-md" data-testid="actions-error">
        <AlertCircle className="w-4 h-4 text-amber-600" /> Couldn't load actions — {err}
      </div>
    );
  }

  if (totalCount === 0) {
    return (
      <div className="p-12 text-center border border-[var(--rule)] rounded-md bg-white" data-testid="actions-empty">
        <CheckCircle2 className="w-6 h-6 text-emerald-600 mx-auto mb-3" />
        <p className="text-[14px] text-[var(--ink)] font-medium">No open action items.</p>
        <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
          Action Items aggregate signal actions, in-flight plays, and pending
          cycle submissions for this context. There's nothing on the board.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10" data-testid="actions-tab">
      {sectionOrder.map((key) => {
        const items = (data?.sections && data.sections[key]) || [];
        if (items.length === 0) return null;
        const Meta = SECTION_META[key];
        const Icon = Meta.icon;
        return (
          <section key={key} data-testid={`actions-section-${key}`}>
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} />
              <h2 className="akki-serif text-[18px] text-[var(--ink)]">{Meta.label}</h2>
              <span className="text-[12px] text-[var(--muted)]">· {items.length}</span>
            </div>
            <p className="text-[12.5px] text-[var(--muted)] mb-4 max-w-[60ch]">{Meta.blurb}</p>
            <ul className="space-y-2">
              {items.map((item) => <ActionRow key={`${key}-${item.id}`} item={item} />)}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
