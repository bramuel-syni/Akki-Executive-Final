/**
 * NedInbox — NED-side view of pending / accepted / declined assignments.
 *
 * Strict whitelist enforcement is server-side (NedInboxItemOut in
 * backend/routers/cycle_assignments.py). This page is a pure consumer
 * of GET /api/ned/inbox/assignments + accept/decline endpoints.
 *
 * v7 palette only; no hex literals.
 */
import React, { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Check, X, Inbox, FileText, ShieldCheck } from "lucide-react";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import CycleStatusBadge from "@/components/cycle/CycleStatusBadge";


function fmtWhen(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}


function Tabs({ value, onChange, counts }) {
  const tabs = [
    { id: "pending",  label: "Pending"  },
    { id: "accepted", label: "Accepted" },
    { id: "declined", label: "Declined" },
  ];
  return (
    <div
      className="flex items-center gap-6 border-b border-[var(--rule)] mb-5"
      data-testid="ned-inbox-tabs"
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={[
            "py-2 text-[12px] uppercase tracking-[0.14em] font-mono transition-colors",
            value === t.id
              ? "text-[var(--ink)] border-b-2 border-[color:var(--oxblood)] -mb-px"
              : "text-[var(--muted)] hover:text-[var(--ink)] border-b-2 border-transparent -mb-px",
          ].join(" ")}
          data-testid={`ned-inbox-tab-${t.id}`}
        >
          {t.label} <span className="ml-1 text-[10px] opacity-70">({counts[t.id] || 0})</span>
        </button>
      ))}
    </div>
  );
}


function AssignmentCard({ item, onAccept, onDecline, busy }) {
  return (
    <article
      className="border border-[var(--rule)] bg-white rounded-sm px-5 py-4"
      data-testid={`ned-inbox-card-${item.assignment_id}`}
    >
      <header className="flex items-start justify-between gap-4 mb-2">
        <div className="flex-1 min-w-0">
          <p className="akki-meta text-[11px] uppercase tracking-[0.12em]">
            From {item.submitter_display_name}
          </p>
          <h3 className="akki-serif text-[17px] text-[var(--ink)] mt-1">
            {item.cycle_title}
          </h3>
          {item.cohort_label && (
            <p className="akki-meta text-[11.5px] mt-1">
              Cohort: <span className="font-mono">{item.cohort_label}</span>
            </p>
          )}
        </div>
        <CycleStatusBadge status={item.status} />
      </header>
      {item.note && (
        <p
          className="text-[13.5px] text-[var(--ink)] mt-2 italic"
          data-testid={`ned-inbox-card-note-${item.assignment_id}`}
        >
          “{item.note}”
        </p>
      )}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--rule)]">
        <p className="akki-meta text-[11.5px] font-mono">
          {fmtWhen(item.submitted_at)} · ref <span className="opacity-70">{item.assignment_id.slice(0, 8)}…</span>
        </p>
        {item.status === "pending" && (
          <div className="flex gap-2">
            <Button
              size="sm" variant="ghost"
              onClick={() => onDecline(item)}
              disabled={busy}
              className="text-[12.5px] text-[var(--muted)] hover:text-[color:var(--oxblood)]"
              data-testid={`ned-inbox-decline-${item.assignment_id}`}
            >
              <X className="w-3.5 h-3.5 mr-1" /> Decline
            </Button>
            <Button
              size="sm"
              onClick={() => onAccept(item)}
              disabled={busy}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white text-[12.5px]"
              data-testid={`ned-inbox-accept-${item.assignment_id}`}
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Check className="w-3.5 h-3.5 mr-1" />}
              Accept
            </Button>
          </div>
        )}
        {item.status === "accepted" && (
          <p className="akki-meta text-[11.5px] flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
            In your durable record.
          </p>
        )}
        {item.status === "declined" && (
          <p className="akki-meta text-[11.5px]">Declined; not in your record.</p>
        )}
      </div>
    </article>
  );
}


export default function NedInbox() {
  const { account } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("pending");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [declineTarget, setDeclineTarget] = useState(null);
  const [declineReason, setDeclineReason] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/ned/inbox/assignments");
      setItems(data?.items || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const counts = useMemo(() => {
    const c = { pending: 0, accepted: 0, declined: 0 };
    for (const it of items) {
      if (c[it.status] !== undefined) c[it.status] += 1;
    }
    return c;
  }, [items]);

  const visible = useMemo(
    () => items.filter((it) => it.status === tab),
    [items, tab],
  );

  const accept = async (it) => {
    setBusyId(it.assignment_id);
    try {
      await api.post(`/ned/assignments/${it.assignment_id}/accept`);
      toast.success("Accepted. The brief is now in your durable record.");
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusyId(null); }
  };

  const decline = async () => {
    if (!declineTarget) return;
    setBusyId(declineTarget.assignment_id);
    try {
      await api.post(
        `/ned/assignments/${declineTarget.assignment_id}/decline`,
        { reason: declineReason || null },
      );
      toast.success("Declined.");
      setDeclineTarget(null);
      setDeclineReason("");
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusyId(null); }
  };

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="ned_inbox">
        <div
          className="akki-w-medium akki-vmedium"
          data-testid="ned-inbox-page"
        >
          <header className="mb-6">
            <p className="akki-meta text-[11px] uppercase tracking-[0.16em]">
              <Inbox className="inline w-3.5 h-3.5 mr-1" /> NED Inbox
            </p>
            <h1 className="akki-serif text-[26px] text-[var(--ink)] mt-1">
              Assignments waiting on you.
            </h1>
            <p className="akki-meta text-[12.5px] mt-2 max-w-prose">
              Each row is a brief an executive has assigned to you for board reporting.
              Accept to ingest the brief into your durable record. Decline to refuse — your
              choice is logged but the brief is not copied to your side.
            </p>
          </header>

          <Tabs value={tab} onChange={setTab} counts={counts} />

          {loading ? (
            <div
              className="flex items-center justify-center py-12 text-[var(--muted)]"
              data-testid="ned-inbox-loading"
            >
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Loading inbox…
            </div>
          ) : visible.length === 0 ? (
            <div
              className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-10 text-center"
              data-testid="ned-inbox-empty"
            >
              <FileText className="w-5 h-5 text-[var(--muted)] mx-auto mb-2" />
              <p className="akki-serif text-[15px] text-[var(--ink)]">
                Nothing in <span className="lowercase">{tab}</span>.
              </p>
              <p className="akki-meta text-[12.5px] mt-1">
                When an executive submits a brief and assigns it to you, it will appear here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3" data-testid="ned-inbox-list">
              {visible.map((it) => (
                <AssignmentCard
                  key={it.assignment_id}
                  item={it}
                  busy={busyId === it.assignment_id}
                  onAccept={accept}
                  onDecline={(item) => setDeclineTarget(item)}
                />
              ))}
            </div>
          )}

          <AlertDialog
            open={!!declineTarget}
            onOpenChange={(open) => { if (!open) { setDeclineTarget(null); setDeclineReason(""); } }}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle className="akki-serif">Decline this assignment?</AlertDialogTitle>
                <AlertDialogDescription className="akki-meta">
                  The brief will NOT be copied to your durable record. The submitter is notified
                  that you've declined. You may add an optional reason.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <Textarea
                value={declineReason}
                onChange={(e) => setDeclineReason(e.target.value)}
                placeholder="Optional reason (e.g. conflict of interest)"
                rows={3}
                className="rounded-sm text-[13px]"
                data-testid="ned-inbox-decline-reason"
              />
              <AlertDialogFooter>
                <AlertDialogCancel disabled={!!busyId} data-testid="ned-inbox-decline-cancel">
                  Keep pending
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={(e) => { e.preventDefault(); decline(); }}
                  disabled={!!busyId}
                  className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                  data-testid="ned-inbox-decline-confirm"
                >
                  {busyId ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
                  Decline
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </WorkspaceEntryGate>
    </AppShell>
  );
}
