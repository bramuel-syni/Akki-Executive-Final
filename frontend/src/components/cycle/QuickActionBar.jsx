/**
 * QuickActionBar — 4-tile editorial action strip anchored above the
 * Cycle Manager list. Always renders exactly 4 actions in the order
 * returned by GET /quick-actions/order.
 *
 * Action #1 (main_board) is fully functional — opens the
 * MainBoardTemplateModal which creates a cycle + applies the template.
 * The other 3 are coming-soon scaffolds — open a styled modal with a
 * "Coming soon" ribbon. Click telemetry fires for all 4.
 *
 * v7 palette only.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  Calendar, MessageSquareReply, FileText, Sparkles, Loader2, Construction,
} from "lucide-react";
import { toast } from "sonner";


function firstFridayOfNextMonth() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;          // next month index
  const ny = m === 12 ? y + 1 : y;
  const nm = m === 12 ? 0 : m;
  const first = new Date(ny, nm, 1);
  const dow = first.getDay();             // 0=Sun
  const offsetToFriday = (5 - dow + 7) % 7;
  const friday = new Date(ny, nm, 1 + offsetToFriday);
  return friday.toISOString().slice(0, 10); // YYYY-MM-DD
}

function defaultBoardTitle() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  const monthYear = d.toLocaleString(undefined, { month: "long", year: "numeric" });
  return `Main Board — ${monthYear}`;
}


const ACTION_META = {
  main_board: {
    label: "Prepare for Main Board",
    description: "Spin up a board cycle with a standard agenda and your ExCo team in one click.",
    icon: Calendar,
    available: true,
  },
  answer_questions: {
    label: "Answer Questions",
    description: "Batch-respond to pending questions raised on prior cycles.",
    icon: MessageSquareReply,
    available: false,
    previewItems: [
      "What's our position on the proposed merger timing?",
      "How are we responding to the audit committee's risk concerns?",
      "What's the rationale for the Q1 capex revision?",
    ],
  },
  project_proposal: {
    label: "Write a Project Proposal",
    description: "Start a new project proposal cycle with a structured agenda.",
    icon: FileText,
    available: false,
    previewSteps: [
      "Brief the proposal premise + the decision sought",
      "Compile context, options, recommendation, and approvals path",
    ],
  },
  fund_raising: {
    label: "Prepare for Fund Raising",
    description: "Compile a fund-raising readiness cycle with investor-grade structure.",
    icon: Sparkles,
    available: false,
    previewSteps: [
      "Investor narrative + traction + financial proof",
      "Compliance, term sheet, deal-room readiness",
    ],
  },
};


function QuickActionTile({ k, onClick }) {
  const meta = ACTION_META[k];
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={() => onClick(k)}
      data-testid={`quick-action-${k}`}
      className={[
        "group text-left border border-[var(--rule)] rounded-sm px-4 py-3.5",
        "bg-[var(--parchment)] hover:bg-white",
        "transition-colors transition-transform duration-150",
        "active:translate-y-[1px]",
        "focus:outline-none focus:border-[color:var(--oxblood)]",
      ].join(" ")}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className="w-4 h-4 text-[color:var(--oxblood)] shrink-0" strokeWidth={1.6} />
        <span className="akki-serif text-[14.5px] text-[var(--ink)] font-medium leading-tight">
          {meta.label}
        </span>
        {!meta.available && (
          <span className="ml-auto text-[9.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] border border-[var(--rule)] px-1.5 py-[1px] rounded-sm">
            Soon
          </span>
        )}
      </div>
      <p className="akki-meta text-[11.5px] leading-snug">
        {meta.description}
      </p>
    </button>
  );
}


function MainBoardTemplateModal({ open, onOpenChange, contextId }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState(defaultBoardTitle());
  const [meetingDate, setMeetingDate] = useState(firstFridayOfNextMonth());
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setTitle(defaultBoardTitle());
      setMeetingDate(firstFridayOfNextMonth());
      setNote("");
    }
  }, [open]);

  const submit = async () => {
    const t = title.trim();
    if (!t) { toast.error("Title is required."); return; }
    setBusy(true);
    try {
      const created = (await api.post(`/contexts/${contextId}/cycles`, { title: t })).data;
      const applied = (await api.post(
        `/contexts/${contextId}/cycles/${created.id}/apply-template`,
        { template_key: "main_board" },
      )).data;
      toast.success(
        `Main Board cycle ready. ${applied.agenda_items_added} agenda items and ${applied.team_members_added} team members added from your catalogue.`,
      );
      onOpenChange(false);
      navigate(`/app/cycle/${created.id}?tab=agenda`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setBusy(false); }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-testid="quick-action-main-board-modal">
        <AlertDialogHeader>
          <AlertDialogTitle className="akki-serif">Prepare for Main Board</AlertDialogTitle>
          <AlertDialogDescription className="akki-meta">
            Agent cycle will seed 6 standard agenda items and pull your ExCo team from the workspace catalogue. You'll land on the Agenda tab.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Cycle title</Label>
            <Input
              value={title} onChange={(e) => setTitle(e.target.value)}
              className="rounded-sm mt-1 text-[13.5px]"
              data-testid="quick-action-main-board-title"
              autoFocus
            />
          </div>
          <div>
            <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Meeting date</Label>
            <Input
              type="date" value={meetingDate}
              onChange={(e) => setMeetingDate(e.target.value)}
              className="rounded-sm mt-1 text-[13.5px] font-mono"
              data-testid="quick-action-main-board-date"
            />
          </div>
          <div>
            <Label className="akki-meta text-[11px] uppercase tracking-[0.12em]">Note (optional)</Label>
            <Textarea
              value={note} onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="e.g. Pre-read three days before the meeting."
              className="rounded-sm mt-1 text-[13px]"
              data-testid="quick-action-main-board-note"
            />
          </div>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy} data-testid="quick-action-main-board-cancel">Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => { e.preventDefault(); submit(); }}
            disabled={busy || !title.trim()}
            className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
            data-testid="quick-action-main-board-submit"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
            Spin up cycle
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}


function ComingSoonModal({ open, onOpenChange, actionKey }) {
  if (!actionKey) return null;
  const meta = ACTION_META[actionKey];
  if (!meta || meta.available) return null;
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-testid={`quick-action-coming-soon-modal-${actionKey}`}>
        <AlertDialogHeader>
          <div className="flex items-start justify-between gap-3">
            <AlertDialogTitle className="akki-serif">{meta.label}</AlertDialogTitle>
            <span
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] font-mono text-[color:var(--oxblood)] border border-[color:var(--oxblood)] px-2 py-[2px] rounded-sm"
              data-testid={`coming-soon-ribbon-${actionKey}`}
            >
              <Construction className="w-3 h-3" /> Coming soon
            </span>
          </div>
          <AlertDialogDescription className="akki-meta">
            {meta.description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {meta.previewItems && (
          <div data-testid={`coming-soon-preview-items-${actionKey}`}>
            <p className="akki-meta text-[11px] uppercase tracking-[0.12em] mb-2">Sample queue</p>
            <ul className="border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)] bg-white">
              {meta.previewItems.map((q, i) => (
                <li key={i} className="px-3 py-2 text-[12.5px] text-[var(--muted)] italic">{q}</li>
              ))}
            </ul>
          </div>
        )}
        {meta.previewSteps && (
          <div data-testid={`coming-soon-preview-steps-${actionKey}`}>
            <p className="akki-meta text-[11px] uppercase tracking-[0.12em] mb-2">Two-step shape</p>
            <ol className="border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)] bg-white">
              {meta.previewSteps.map((s, i) => (
                <li key={i} className="px-3 py-2 text-[12.5px] text-[var(--muted)]">
                  <span className="font-mono text-[11px] text-[color:var(--oxblood)] mr-2">Step {i + 1}</span>
                  {s}
                </li>
              ))}
            </ol>
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel data-testid={`coming-soon-close-${actionKey}`}>Close</AlertDialogCancel>
          <Button
            size="sm" disabled
            title="Available in a future release."
            className="bg-[var(--muted)]/30 text-[var(--muted)] cursor-not-allowed"
            data-testid={`coming-soon-cta-${actionKey}`}
          >
            Open
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}


export default function QuickActionBar({ contextId }) {
  const [order, setOrder] = useState([
    "main_board", "answer_questions", "project_proposal", "fund_raising",
  ]);
  const [mainBoardOpen, setMainBoardOpen] = useState(false);
  const [comingSoonKey, setComingSoonKey] = useState(null);

  useEffect(() => {
    if (!contextId) return;
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/quick-actions/order`);
        if (alive && Array.isArray(data?.order) && data.order.length === 4) {
          setOrder(data.order);
        }
      } catch { /* fall back to default order */ }
    })();
    return () => { alive = false; };
  }, [contextId]);

  const onClick = async (key) => {
    // Telemetry first (await — failure is silent).
    try { await api.post(`/contexts/${contextId}/quick-actions/${key}/clicked`); }
    catch { /* silent */ }
    if (key === "main_board") setMainBoardOpen(true);
    else setComingSoonKey(key);
  };

  return (
    <section
      className="mb-6 border border-[var(--rule)] rounded-sm bg-white px-4 py-4"
      data-testid="quick-action-bar"
      aria-label="Quick actions"
    >
      <p className="akki-meta text-[10.5px] uppercase tracking-[0.16em] mb-3">
        Agent cycle · Quick actions
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {order.map((k) => <QuickActionTile key={k} k={k} onClick={onClick} />)}
      </div>

      <MainBoardTemplateModal
        open={mainBoardOpen}
        onOpenChange={setMainBoardOpen}
        contextId={contextId}
      />
      <ComingSoonModal
        open={!!comingSoonKey}
        onOpenChange={(v) => { if (!v) setComingSoonKey(null); }}
        actionKey={comingSoonKey}
      />
    </section>
  );
}
