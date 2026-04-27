import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  FileText, Send, Loader2, Plus, Trash2, ArrowRight, CheckCircle2,
  Clock, Users, RotateCcw, ShieldCheck, Sparkles, Download, Layers,
} from "lucide-react";
import PolishDiffModal from "@/components/cycle/PolishDiffModal";

function shortDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
}

/**
 * ComposeReportTile — tile-style entry point with contextual notes that tell
 * the user whether AKKI is ready or whether reportees still owe a response.
 * Replaces the iter34 small "Compose report" corner button per April-2026
 * user-testing feedback.
 */
function ComposeReportTile({ readiness, reportCount, onCompose }) {
  const pending = readiness?.pending_reportees ?? 0;
  const total = readiness?.total_reportees ?? 0;
  const ready = total > 0 && pending === 0;
  const hasNoTeam = total === 0;

  const status = hasNoTeam
    ? { tone: "neutral", line: "No reportees set up yet. Compose a freeform report or seed your team in 1 · Your team." }
    : ready
      ? { tone: "ready", line: "AKKI has all the information you need." }
      : { tone: "waiting",
          line: `${pending} direct ${pending === 1 ? "report hasn't" : "reports haven't"} responded to AKKI yet.` };

  return (
    <div
      className="bg-white border border-[var(--rule)] rounded-md p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4"
      data-testid="compose-report-tile"
    >
      <div className="min-w-0 flex-1">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" />
          Compose your report
        </p>
        <h3 className="akki-serif text-[20px] text-[var(--ink)] leading-snug mb-1">
          {ready
            ? "Everyone's in. Time to draft."
            : hasNoTeam
              ? "Compose from what you have."
              : "Almost ready — chase the gaps first."}
        </h3>
        <p
          className={
            "text-[13px] leading-relaxed " +
            (status.tone === "ready"
              ? "text-emerald-700"
              : status.tone === "waiting"
                ? "text-amber-700"
                : "text-[var(--muted)]")
          }
          data-testid="compose-report-tile-status"
        >
          {status.line}
        </p>
        {reportCount > 0 && (
          <p className="text-[11.5px] text-[var(--muted)] italic mt-1">
            {reportCount} report{reportCount === 1 ? "" : "s"} on this context already.
          </p>
        )}
      </div>
      <Button
        onClick={onCompose}
        className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white h-11 px-6 shrink-0"
        data-testid="compose-report-btn"
      >
        <Plus className="w-3.5 h-3.5 mr-1.5" /> Compose report
      </Button>
    </div>
  );
}


const STATUS_PILL = {
  draft:       { bg: "bg-slate-100",   fg: "text-slate-700",  label: "Draft" },
  in_review:   { bg: "bg-amber-50",    fg: "text-amber-800",  label: "In review" },
  finalised:   { bg: "bg-emerald-50",  fg: "text-emerald-700",label: "Finalised" },
  withdrawn:   { bg: "bg-slate-100",   fg: "text-slate-500",  label: "Withdrawn" },
};

// ---------------- Compose modal ----------------
function ComposeModal({ open, onClose, contextId, cycleNames, onCreated }) {
  const [cycleName, setCycleName] = useState(cycleNames?.[0] || "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [chain, setChain] = useState([{ name: "", title: "", email: "" }]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open && cycleNames?.length && !cycleName) setCycleName(cycleNames[0]);
  }, [open, cycleNames, cycleName]);

  const onCreate = async () => {
    if (cycleName.length < 3 || title.length < 4) { toast.message("Pick a cycle and give the report a title."); return; }
    const cleanChain = chain.filter((c) => c.email && c.name && c.title);
    if (cleanChain.length === 0) { toast.message("Add at least one reviewer to the chain."); return; }
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/reports/compose`, {
        cycle_name: cycleName, title, chain: cleanChain,
        description: description.trim() || null,
      });
      toast.success("Report drafted from your team's submissions.");
      onCreated(data);
      onClose();
      setTitle(""); setDescription(""); setChain([{ name: "", title: "", email: "" }]);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl bg-[var(--cream)] border border-[var(--rule)]" data-testid="compose-report-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[22px] font-normal">Compose a report</DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            AKKI will stitch your team's submissions for this cycle into a starter draft you can edit before sending up the chain.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <p className="akki-overline mb-1.5">Cycle</p>
            {cycleNames?.length > 0 ? (
              <select
                value={cycleName}
                onChange={(e) => setCycleName(e.target.value)}
                className="w-full h-10 px-3 text-[14px] bg-white border border-[var(--rule)] rounded-md focus:outline-none focus:border-[var(--accent)]"
                data-testid="compose-cycle-select"
              >
                {cycleNames.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            ) : (
              <Input
                value={cycleName}
                onChange={(e) => setCycleName(e.target.value)}
                placeholder="e.g. Q2 2026 board pack"
                className="h-10 bg-white border-[var(--rule)] text-sm"
                data-testid="compose-cycle-input"
              />
            )}
          </div>
          <div>
            <p className="akki-overline mb-1.5">Report title</p>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. CFO submission to CEO — Q2 2026"
              className="h-10 bg-white border-[var(--rule)] text-sm"
              data-testid="compose-title-input"
            />
          </div>
          <div>
            <p className="akki-overline mb-1.5">Describe what you need <span className="text-[var(--muted)] normal-case font-mono text-[10px]">optional</span></p>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Audit committee deep-dive on revenue recognition. Pull the Q3 deltas vs Q2, highlight the three reportees flagging risk, recommend follow-up questions for the CEO."
              rows={3}
              className="w-full bg-white border border-[var(--rule)] rounded-md px-3 py-2 text-[13.5px] focus:outline-none focus:border-[var(--accent)] akki-serif leading-relaxed"
              data-testid="compose-description-input"
            />
            <p className="text-[11px] text-[var(--muted)] italic mt-1 leading-relaxed">
              Tell AKKI the angle. The starter draft will surface your steer at the top so the chain knows what shape this report is meant to take.
            </p>
          </div>
          <div>
            <p className="akki-overline mb-2">Review chain (escalation order)</p>
            <p className="text-[11.5px] text-[var(--muted)] mb-3 leading-relaxed">
              You're the author. List who reviews after you, in order. Example: <em>CFO → CEO → Board chair</em>.
              Each will receive an email when the previous tier approves.
            </p>
            <div className="space-y-2">
              {chain.map((c, i) => (
                <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-1.5" data-testid={`chain-row-${i}`}>
                  <Input value={c.name} onChange={(e) => setChain((p) => p.map((x, ix) => ix === i ? { ...x, name: e.target.value } : x))} placeholder="Name" className="h-9 bg-white border-[var(--rule)] text-[13px]" />
                  <Input value={c.title} onChange={(e) => setChain((p) => p.map((x, ix) => ix === i ? { ...x, title: e.target.value } : x))} placeholder="Title (CEO, Chair…)" className="h-9 bg-white border-[var(--rule)] text-[13px]" />
                  <Input value={c.email} onChange={(e) => setChain((p) => p.map((x, ix) => ix === i ? { ...x, email: e.target.value } : x))} placeholder="email@company.com" className="h-9 bg-white border-[var(--rule)] text-[13px]" />
                  <button onClick={() => setChain((p) => p.filter((_, ix) => ix !== i))} className="text-[var(--muted)] hover:text-[var(--accent)] px-2" disabled={chain.length === 1}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
              {chain.length < 5 && (
                <button
                  onClick={() => setChain((p) => [...p, { name: "", title: "", email: "" }])}
                  className="text-[12.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1"
                  data-testid="chain-add-btn"
                >
                  <Plus className="w-3 h-3" /> Add another reviewer
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rule)]">
          <Button variant="outline" onClick={onClose} className="border-[var(--rule)]">Cancel</Button>
          <Button onClick={onCreate} disabled={busy} className="bg-[var(--chrome)] text-white" data-testid="compose-create-btn">
            {busy ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Drafting…</> : <>Compose draft <ArrowRight className="w-3.5 h-3.5 ml-1.5" /></>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------- Chain visualizer ----------------
function ChainStrip({ chain }) {
  return (
    <ol className="flex items-stretch gap-1 overflow-x-auto py-2" data-testid="chain-strip">
      {chain.map((entry, i) => {
        const isCurrent = entry.status === "pending";
        const isApproved = entry.status === "approved";
        const isSentBack = entry.status === "sent_back";
        const tone =
          isApproved   ? "bg-emerald-50 border-emerald-200 text-emerald-800" :
          isCurrent    ? "bg-amber-50 border-amber-300 text-amber-900 ring-1 ring-amber-300" :
          isSentBack   ? "bg-red-50 border-red-200 text-red-800" :
                         "bg-slate-50 border-slate-200 text-slate-500";
        const Icon = isApproved ? CheckCircle2 : isSentBack ? RotateCcw : Clock;
        return (
          <li key={i} className={`flex-1 min-w-[140px] border rounded-md px-3 py-2 ${tone}`} data-testid={`chain-tier-${entry.tier}`}>
            <div className="flex items-center gap-1.5 mb-0.5">
              <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
              <p className="text-[10px] uppercase tracking-wider font-bold">Tier {entry.tier} · {entry.title}</p>
            </div>
            <p className="text-[13px] font-medium leading-tight">{entry.name}</p>
            {entry.email && <p className="text-[11px] font-mono opacity-75 truncate">{entry.email}</p>}
            {entry.acted_at && <p className="text-[10px] mt-1 opacity-70">{shortDate(entry.acted_at)}</p>}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------- Editor / reviewer modal ----------------
function ReportEditor({ open, onClose, report, contextId, currentEmail, onUpdated }) {
  const [body, setBody] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [polishing, setPolishing] = useState(false);
  const [polishDraft, setPolishDraft] = useState(null); // { original, polished }
  const [unsaved, setUnsaved] = useState(false);

  useEffect(() => {
    if (report) { setBody(report.body || ""); setTitle(report.title || ""); setNote(""); setPolishDraft(null); setUnsaved(false); }
  }, [report]);

  if (!report) return null;

  const chain = report.chain || [];
  const currentReviewerIdx = chain.findIndex((c) => c.status === "pending");
  const currentTier = currentReviewerIdx >= 0 ? chain[currentReviewerIdx] : null;
  const isAuthor = report.author_id && report.status === "draft";  // backend gates by current user too
  const isCurrentReviewer = currentTier && currentTier.email && currentReviewerIdx >= 0 && currentEmail && currentTier.email === currentEmail.toLowerCase();
  const canEdit = (report.status === "draft") || isCurrentReviewer;

  const onSave = async () => {
    setBusy(true);
    try {
      await api.patch(`/contexts/${contextId}/reports/${report.id}`, { title, body });
      toast.success("Saved.");
      setUnsaved(false);
      onUpdated();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const onSendUp = async () => {
    if (!confirm(`Send to ${currentTier?.name} (${currentTier?.title})?`)) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/reports/${report.id}/send_up`);
      toast.success(`Sent to ${data.to}.${data.send_id ? " Email dispatched." : " (Resend not configured — internal-only)"}`);
      onUpdated();
      onClose();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const onReview = async (action) => {
    if (action === "send_back" && note.trim().length < 4) {
      toast.message("Please add a note explaining what needs revision."); return;
    }
    setBusy(true);
    try {
      await api.post(`/contexts/${contextId}/reports/${report.id}/review`, { action, note: note || null });
      toast.success(action === "approve" ? "Approved & forwarded." : "Sent back to author.");
      onUpdated();
      onClose();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const onSaveNote = async () => {
    if (!note.trim()) { toast.message("Add a note first."); return; }
    setSavingNote(true);
    try {
      await api.patch(`/contexts/${contextId}/reports/${report.id}`, { note });
      toast.success("Note saved to the chain.");
      onUpdated();
      setNote("");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSavingNote(false); }
  };

  const onPolish = async () => {
    setPolishing(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/reports/${report.id}/polish`,
        {},
        { timeout: 180000 },
      );
      const polished = data.polished_body || "";
      if (!polished || polished.trim() === (body || "").trim()) {
        toast.message("AKKI didn't suggest any changes.");
        return;
      }
      setPolishDraft({ original: body, polished });
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setPolishing(false); }
  };

  const onAcceptPolish = () => {
    if (polishDraft?.polished) {
      setBody(polishDraft.polished);
      setUnsaved(true);
      toast.success("Polish accepted. Save edits to commit.");
    }
    setPolishDraft(null);
  };

  const onDownloadPdf = async () => {
    try {
      const resp = await api.get(
        `/contexts/${contextId}/reports/${report.id}/export.pdf`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(report.title || "report").replace(/[^a-zA-Z0-9-_ ]/g, "_").slice(0, 60)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Report PDF downloaded.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onDownloadDeck = async () => {
    try {
      const resp = await api.get(
        `/contexts/${contextId}/reports/${report.id}/export.deck.pdf`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(report.title || "report").replace(/[^a-zA-Z0-9-_ ]/g, "_").slice(0, 60)}_deck.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Board deck downloaded.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <>
    <Dialog open={open} onOpenChange={(o) => {
      if (!o) {
        if (unsaved && !confirm("You have unsaved changes. Discard and close?")) return;
        onClose();
      }
    }}>
      <DialogContent className="max-w-4xl max-h-[90vh] bg-[var(--cream)] border border-[var(--rule)] overflow-hidden flex flex-col" data-testid="report-editor-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[22px] font-normal">{title || report.title}</DialogTitle>
          <DialogDescription className="text-[12px] text-[var(--muted)]">
            {report.cycle_name} · author <strong className="text-[var(--ink)]">{report.author_name}</strong> · {STATUS_PILL[report.status]?.label}
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-y-auto pr-2 flex-1 space-y-5">
          <ChainStrip chain={chain} />

          {currentTier && isCurrentReviewer && (
            <div className="bg-amber-50 border border-amber-300 rounded-md p-3 text-[13px] text-amber-900 flex items-start gap-2" data-testid="reviewer-prompt">
              <Clock className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.8} />
              <div>
                <p className="font-medium mb-0.5">You're the current reviewer.</p>
                <p className="opacity-90">Edit if needed, add a note for the next tier, then approve & forward — or send back to {report.author_name} with revision notes.</p>
              </div>
            </div>
          )}

          {report.events?.length > 0 && (
            <details className="text-[12.5px]" data-testid="event-trail">
              <summary className="cursor-pointer akki-overline">Chain trail · {report.events.length} event{report.events.length === 1 ? "" : "s"}</summary>
              <ul className="mt-2 space-y-1 pl-4 border-l border-[var(--rule)]">
                {report.events.map((e, i) => (
                  <li key={i} className="text-[var(--deep)]">
                    <span className="font-mono text-[11px] text-[var(--muted)]">{shortDate(e.at)}</span> · <strong>{e.actor_name}</strong> · {e.action}
                    {e.to_name && <> → <strong>{e.to_name}</strong></>}
                    {e.note && <span className="italic block ml-4 text-[var(--muted)]">"{e.note}"</span>}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div>
            <p className="akki-overline mb-2">Title</p>
            <Input
              value={title}
              onChange={(e) => { setTitle(e.target.value); setUnsaved(true); }}
              disabled={!canEdit}
              className="h-10 bg-white border-[var(--rule)] text-sm"
              data-testid="report-title-input"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="akki-overline">Body (markdown)</p>
              {unsaved && (
                <span className="inline-flex items-center gap-1.5 text-[10.5px] uppercase tracking-wider px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-mono" data-testid="report-unsaved-badge">
                  <Clock className="w-3 h-3" /> Unsaved changes
                </span>
              )}
            </div>
            <textarea
              value={body}
              onChange={(e) => { setBody(e.target.value); setUnsaved(true); }}
              disabled={!canEdit}
              rows={18}
              className="w-full text-[14px] font-mono leading-relaxed bg-white border border-[var(--rule)] rounded-md p-4 focus:outline-none focus:border-[var(--accent)]"
              data-testid="report-body-textarea"
            />
          </div>

          {(isCurrentReviewer || canEdit) && (
            <div>
              <p className="akki-overline mb-2">Note for the chain (optional)</p>
              <div className="flex gap-2">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="A line for the next reviewer or the author…"
                  className="flex-1 text-[13px] bg-white border border-[var(--rule)] rounded-md p-2.5 focus:outline-none focus:border-[var(--accent)]"
                  data-testid="report-note-input"
                />
                <Button onClick={onSaveNote} disabled={savingNote} variant="outline" className="border-[var(--rule)] h-auto self-stretch">
                  {savingNote ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save note"}
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-[var(--rule)]">
          <p className="text-[11px] text-[var(--muted)] mr-auto inline-flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" /> Synisense-shielded · routed only to the named chain
          </p>
          <Button variant="outline" onClick={onClose} className="border-[var(--rule)]">Close</Button>
          {/* PDF available at any non-trivial state */}
          {report.status !== "withdrawn" && (
            <>
              <Button onClick={onDownloadPdf} variant="outline" className="border-[var(--rule)]" data-testid="report-pdf-btn">
                <Download className="w-3.5 h-3.5 mr-1.5" /> Download PDF
              </Button>
              <Button onClick={onDownloadDeck} variant="outline" className="border-[var(--rule)]" data-testid="report-deck-btn" title="One-section-per-slide landscape PDF for projecting in the boardroom">
                <Layers className="w-3.5 h-3.5 mr-1.5" /> Board deck
              </Button>
            </>
          )}
          {canEdit && (
            <Button onClick={onPolish} disabled={polishing || busy} variant="outline" className="border-[var(--rule)]" data-testid="report-polish-btn">
              {polishing
                ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Polishing…</>
                : <><Sparkles className="w-3.5 h-3.5 mr-1.5 text-[var(--accent)]" /> Polish with AKKI</>}
            </Button>
          )}
          {canEdit && (
            <Button onClick={onSave} disabled={busy} variant="outline" className="border-[var(--rule)]" data-testid="report-save-btn">
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save edits"}
            </Button>
          )}
          {report.status === "draft" && (
            <Button onClick={onSendUp} disabled={busy || !currentTier} className="bg-[var(--chrome)] text-white" data-testid="report-send-up-btn">
              <Send className="w-3.5 h-3.5 mr-1.5" /> Send to {currentTier?.name || "first reviewer"}
            </Button>
          )}
          {report.status === "in_review" && isCurrentReviewer && (
            <>
              <Button onClick={() => onReview("send_back")} disabled={busy} variant="outline" className="border-red-200 text-red-700 hover:bg-red-50" data-testid="report-send-back-btn">
                <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Send back
              </Button>
              <Button onClick={() => onReview("approve")} disabled={busy} className="bg-emerald-700 hover:bg-emerald-800 text-white" data-testid="report-approve-btn">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" /> Approve & forward
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
    <PolishDiffModal
      open={!!polishDraft}
      onClose={() => setPolishDraft(null)}
      original={polishDraft?.original || ""}
      polished={polishDraft?.polished || ""}
      onAccept={onAcceptPolish}
    />
    </>
  );
}

// ---------------- Reports tab (default export) ----------------
export default function ReportsTab({ contextId, currentEmail, cycleNames }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [composeOpen, setComposeOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [readiness, setReadiness] = useState(null);  // {pending_reportees, total_reportees, has_submissions}

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const [r, rep, sub, cl] = await Promise.all([
        api.get(`/contexts/${contextId}/reports`),
        api.get(`/contexts/${contextId}/reportees`).catch(() => ({ data: { reportees: [] } })),
        api.get(`/contexts/${contextId}/submissions`).catch(() => ({ data: { submissions: [] } })),
        api.get(`/contexts/${contextId}/checklists`).catch(() => ({ data: { checklists: [] } })),
      ]);
      setItems(r.data.reports || []);
      const reportees = rep.data?.reportees || [];
      const submissions = sub.data?.submissions || [];
      const checklists = cl.data?.checklists || [];
      // A reportee is "pending" if AKKI has dispatched a checklist to them
      // for the current cycle window AND they haven't submitted yet.
      const dispatchedReporteeIds = new Set(
        checklists.filter((c) => c.status === "dispatched" || c.status === "responded").map((c) => c.reportee_id)
      );
      const respondedReporteeIds = new Set(
        submissions.filter((s) => s.status === "submitted").map((s) => s.reportee_id)
      );
      const pending = [...dispatchedReporteeIds].filter((id) => !respondedReporteeIds.has(id));
      setReadiness({
        pending_reportees: pending.length,
        total_reportees: dispatchedReporteeIds.size || reportees.length,
        has_submissions: submissions.length > 0,
      });
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  const editing = useMemo(
    () => items.find((r) => r.id === editingId) || null,
    [items, editingId],
  );

  const drafts = items.filter((r) => r.status === "draft");
  const inReview = items.filter((r) => r.status === "in_review");
  const finalised = items.filter((r) => r.status === "finalised");

  return (
    <div className="space-y-6" data-testid="reports-tab">
      {/* Compose Report TILE — replaces the small inline button. Surfaces
          contextual notes ("AKKI has all the information you need." vs.
          "N reportees haven't responded yet.") so the next action is
          intuitive rather than hidden behind a corner button. */}
      <ComposeReportTile
        readiness={readiness}
        reportCount={items.length}
        onCompose={() => setComposeOpen(true)}
      />

      {loading ? (
        <p className="p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
      ) : items.length === 0 ? (
        <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-12 text-center" data-testid="reports-empty">
          <FileText className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
          <p className="akki-lead mb-2">No reports yet.</p>
          <p className="text-[13.5px] text-[var(--muted)] max-w-md mx-auto">
            Once your team submits responses to a cycle's checklists, you can compose a report and send it up your governance chain.
          </p>
        </div>
      ) : (
        <div className="space-y-7">
          {[
            ["Awaiting your review", inReview.filter((r) => r.current_reviewer_email && r.current_reviewer_email === currentEmail?.toLowerCase()), Clock, "amber"],
            ["Drafts", drafts, FileText, "slate"],
            ["In review (with others)", inReview.filter((r) => !(r.current_reviewer_email && r.current_reviewer_email === currentEmail?.toLowerCase())), Users, "slate"],
            ["Finalised", finalised, CheckCircle2, "emerald"],
          ].map(([label, list, Icon, tone]) =>
            list.length > 0 ? (
              <section key={label}>
                <p className={`akki-overline mb-3 flex items-center gap-2 ${tone === "amber" ? "text-amber-700" : tone === "emerald" ? "text-emerald-700" : ""}`}>
                  <Icon className="w-3 h-3" /> {label} ({list.length})
                </p>
                <div className="space-y-2">
                  {list.map((r) => {
                    const pill = STATUS_PILL[r.status];
                    return (
                      <button
                        key={r.id}
                        onClick={() => setEditingId(r.id)}
                        className="w-full text-left bg-white border border-[var(--rule)] hover:border-[var(--accent)]/40 rounded-lg p-4 transition-colors group"
                        data-testid={`report-card-${r.id}`}
                      >
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="min-w-0">
                            <p className="akki-serif text-[16px] text-[var(--ink)] mb-0.5 group-hover:text-[var(--accent)] transition-colors leading-snug">{r.title}</p>
                            <p className="text-[11.5px] text-[var(--muted)] font-mono">{r.cycle_name} · author {r.author_name} · updated {shortDate(r.updated_at)}</p>
                          </div>
                          <span className={`text-[10.5px] uppercase tracking-wider px-2 py-0.5 rounded ${pill.bg} ${pill.fg} font-mono shrink-0`}>{pill.label}</span>
                        </div>
                        <ChainStrip chain={r.chain} />
                      </button>
                    );
                  })}
                </div>
              </section>
            ) : null,
          )}
        </div>
      )}

      <ComposeModal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        contextId={contextId}
        cycleNames={cycleNames}
        onCreated={(rec) => { setItems((p) => [rec, ...p]); setEditingId(rec.id); }}
      />
      <ReportEditor
        open={!!editing}
        onClose={() => setEditingId(null)}
        report={editing}
        contextId={contextId}
        currentEmail={currentEmail}
        onUpdated={load}
      />
    </div>
  );
}
