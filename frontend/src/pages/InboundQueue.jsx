/**
 * InboundQueue — review surface for Tier-C (unknown-sender) inbound emails.
 *
 * Every row carries:
 *   - Sender + subject + preview
 *   - Attachment summary
 *   - Accept (→ promotes into the documents library with trust_tier=unknown_promoted)
 *   - Reject (→ archives silently, per product direction 3c)
 *
 * Multi-context: the current page defaults to the active workspace, but a
 * workspace picker lets the NED review queues across every context they
 * belong to in one place.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Inbox, Check, X, ShieldAlert, Mail, Loader2, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Link } from "react-router-dom";
import { toast } from "sonner";

export default function InboundQueue() {
  const { activeContext, contexts } = useAuth();
  const defaultCid = activeContext?.id;
  const [selectedCid, setSelectedCid] = useState(defaultCid);
  const [userPickedCid, setUserPickedCid] = useState(false);
  useEffect(() => { if (!userPickedCid) setSelectedCid(defaultCid); }, [defaultCid, userPickedCid]);

  const [counts, setCounts] = useState({ total_pending: 0, by_context: [] });
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [busyAction, setBusyAction] = useState(null);
  const [acceptNote, setAcceptNote] = useState("");
  const [acceptOpen, setAcceptOpen] = useState(false);

  const loadCounts = useCallback(async () => {
    try {
      const { data } = await api.get("/me/inbound-queue/counts");
      setCounts(data);
      // iter70 UX polish — if the active workspace has no pending items but
      // another workspace does, auto-select the busiest one on first load
      // only. Once the user picks a workspace explicitly, we respect that.
      if (!userPickedCid) {
        const byCtx = data.by_context || [];
        const activeHasPending = byCtx.some(
          (c) => c.context_id === defaultCid && c.pending > 0,
        );
        if (!activeHasPending && byCtx.length > 0) {
          const busiest = [...byCtx].sort((a, b) => b.pending - a.pending)[0];
          if (busiest?.context_id && busiest.context_id !== defaultCid) {
            setSelectedCid(busiest.context_id);
          }
        }
      }
    } catch { /* noop */ }
  }, [defaultCid, userPickedCid]);

  const loadItems = useCallback(async () => {
    if (!selectedCid) { setItems([]); setLoading(false); return; }
    setLoading(true);
    try {
      const { data } = await api.get(`/contexts/${selectedCid}/inbound-queue?status=all&limit=80`);
      setItems(data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCid]);

  useEffect(() => { loadCounts(); }, [loadCounts]);
  useEffect(() => { loadItems(); }, [loadItems]);

  const openDetail = async (id) => {
    setDetailId(id);
    setDetail(null);
    try {
      const { data } = await api.get(`/contexts/${selectedCid}/inbound-queue/${id}`);
      setDetail(data);
    } catch (err) {
      toast.error(apiErrorMessage(err));
      setDetailId(null);
    }
  };

  const acceptItem = async () => {
    if (!detailId) return;
    setBusyAction("accept");
    try {
      const { data } = await api.post(
        `/contexts/${selectedCid}/inbound-queue/${detailId}/accept`,
        { note: acceptNote.trim() || null },
      );
      toast.success("Ingested — the document is now in the library.");
      await Promise.all([loadCounts(), loadItems()]);
      setAcceptOpen(false);
      setDetailId(null);
      setDetail(null);
      setAcceptNote("");
      // Offer quick link to the promoted doc
      if (data.doc_id) {
        toast("Open the promoted document", {
          action: {
            label: "Open",
            onClick: () => {
              window.location.href = `/app/documents/${data.doc_id}`;
            },
          },
        });
      }
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusyAction(null);
    }
  };

  const rejectItem = async () => {
    if (!detailId) return;
    setBusyAction("reject");
    try {
      await api.post(
        `/contexts/${selectedCid}/inbound-queue/${detailId}/reject`,
        { reason: rejectReason.trim() || "not_relevant" },
      );
      toast.success("Rejected and archived.");
      await Promise.all([loadCounts(), loadItems()]);
      setRejectOpen(false);
      setDetailId(null);
      setDetail(null);
      setRejectReason("");
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusyAction(null);
    }
  };

  const ctxOptions = useMemo(() => {
    // Merge workspaces with non-zero pending counts first, then other
    // workspaces the user belongs to.
    const withCount = new Set((counts.by_context || []).map((c) => c.context_id));
    const sorted = [...(contexts || [])].sort((a, b) => {
      const ap = (counts.by_context || []).find((c) => c.context_id === a.id)?.pending || 0;
      const bp = (counts.by_context || []).find((c) => c.context_id === b.id)?.pending || 0;
      if (ap !== bp) return bp - ap;
      return (a.name || "").localeCompare(b.name || "");
    });
    return { sorted, withCount };
  }, [contexts, counts]);

  const pendingHere = items.filter((i) => i.status === "pending_review");
  const processedHere = items.filter((i) => i.status !== "pending_review").slice(0, 20);

  return (
    <div className="akki-w-medium px-4 md:px-6 py-6" data-testid="inbound-queue-page">
      <div className="mb-5">
        <Link
          to="/app"
          className="inline-flex items-center gap-1 text-[11.5px] uppercase tracking-[0.16em] text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="inbound-queue-back"
        >
          <ArrowLeft className="w-3 h-3" /> Back to home
        </Link>
        <h1 className="akki-serif text-[30px] text-[var(--ink)] leading-tight mt-3">
          Inbound review
        </h1>
        <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mt-2 max-w-[60ch]">
          Emails from an unknown sender to your AKKI inbox land here first —
          never ingested silently. Review each item, then accept to file it,
          or reject to archive.
        </p>
      </div>

      {/* Workspace picker — only renders when the user has multiple contexts */}
      {ctxOptions.sorted.length > 1 && (
        <div className="mb-5 flex flex-wrap items-center gap-2" data-testid="inbound-queue-ctx-switcher">
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
            Workspace:
          </p>
          {ctxOptions.sorted.map((c) => {
            const pending = (counts.by_context || [])
              .find((x) => x.context_id === c.id)?.pending || 0;
            const active = c.id === selectedCid;
            return (
              <button
                key={c.id}
                onClick={() => { setUserPickedCid(true); setSelectedCid(c.id); }}
                data-testid={`inbound-queue-ctx-${c.id}`}
                className={`text-[12px] px-3 py-1.5 rounded-sm border transition-colors ${
                  active
                    ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                    : "border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                }`}
              >
                {c.name}
                {pending > 0 && (
                  <span className={`ml-2 font-mono text-[10.5px] ${active ? "text-white/90" : "text-[var(--accent)]"}`}>
                    {pending}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Pending list */}
      <section className="bg-white border border-[var(--rule)] rounded-md" data-testid="inbound-queue-pending">
        <div className="px-4 py-3 border-b border-[var(--rule)] flex items-center justify-between">
          <p className="akki-overline flex items-center gap-1.5">
            <Inbox className="w-3.5 h-3.5" /> Pending · {pendingHere.length}
          </p>
          {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--muted)]" />}
        </div>
        {!loading && pendingHere.length === 0 && (
          <div className="px-6 py-10 text-center" data-testid="inbound-queue-empty">
            <ShieldAlert className="w-6 h-6 text-[var(--muted)] mx-auto mb-2" />
            <p className="text-[13.5px] text-[var(--deep)] italic">
              Nothing waiting. You'll see items here whenever an email from an
              unknown sender reaches this workspace's AKKI inbox.
            </p>
          </div>
        )}
        <ul>
          {pendingHere.map((it) => (
            <QueueRow key={it.id} item={it} onClick={() => openDetail(it.id)} />
          ))}
        </ul>
      </section>

      {/* Recent decisions */}
      {processedHere.length > 0 && (
        <section className="mt-6 bg-white border border-[var(--rule)] rounded-md" data-testid="inbound-queue-processed">
          <div className="px-4 py-3 border-b border-[var(--rule)]">
            <p className="akki-overline">Recent decisions</p>
          </div>
          <ul>
            {processedHere.map((it) => (
              <QueueRow
                key={it.id} item={it}
                muted
                onClick={() => openDetail(it.id)}
              />
            ))}
          </ul>
        </section>
      )}

      {/* Detail dialog */}
      <Dialog open={!!detailId} onOpenChange={(v) => { if (!v) { setDetailId(null); setDetail(null); } }}>
        <DialogContent
          className="bg-[var(--cream)] max-w-2xl p-0 border-[var(--rule)] max-h-[85vh] overflow-hidden flex flex-col"
          data-testid="inbound-queue-detail"
        >
          <DialogHeader className="px-6 pt-5 pb-3 border-b border-[var(--rule)]">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] mb-1 flex items-center gap-1.5">
              <ShieldAlert className="w-3 h-3" /> Quarantined · not yet ingested
            </p>
            <DialogTitle className="akki-serif text-[20px] text-[var(--ink)] font-normal leading-tight">
              {detail?.inbound_subject || "(no subject)"}
            </DialogTitle>
            <DialogDescription className="text-[12.5px] text-[var(--muted)] mt-1">
              from {detail?.inbound_from_name || detail?.inbound_from_email || "unknown sender"}
              {detail?.inbound_from_name && detail?.inbound_from_email && (
                <span className="font-mono"> · {detail.inbound_from_email}</span>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {!detail && <Loader2 className="w-4 h-4 animate-spin text-[var(--muted)]" />}

            {detail?.body_preview && (
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">Email body</p>
                <div className="bg-white border border-[var(--rule)] rounded-sm p-3 text-[13px] text-[var(--deep)] leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                  {detail.body_preview}
                </div>
              </div>
            )}

            {detail?.attachment_extracted_preview && (
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">Attachment extract</p>
                <div className="bg-white border border-[var(--rule)] rounded-sm p-3 text-[13px] text-[var(--deep)] leading-relaxed whitespace-pre-wrap">
                  {detail.attachment_extracted_preview}
                </div>
              </div>
            )}

            {Array.isArray(detail?.inbound_attachment_summary) && detail.inbound_attachment_summary.length > 0 && (
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">Attachments</p>
                <ul className="text-[12.5px] text-[var(--deep)] space-y-0.5 font-mono">
                  {detail.inbound_attachment_summary.map((a, i) => (
                    <li key={i}>
                      {a.name}
                      {a.content_type && <span className="text-[var(--muted)]"> · {a.content_type}</span>}
                      {typeof a.size_bytes === "number" && (
                        <span className="text-[var(--muted)]"> · {formatBytes(a.size_bytes)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {detail && detail.status !== "pending_review" && (
              <div className="border border-[var(--rule)] rounded-sm p-3 bg-[var(--cream-deep)]/40">
                <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">
                  {detail.status === "accepted" ? "Accepted" : "Rejected"}
                </p>
                <p className="text-[12.5px] text-[var(--deep)]">
                  {detail.status === "accepted"
                    ? `Promoted to document${detail.accept_note ? ` · “${detail.accept_note}”` : ""}`
                    : `Reason: ${detail.reject_reason || "not specified"}`}
                </p>
              </div>
            )}
          </div>

          {detail?.status === "pending_review" && (
            <div className="px-6 py-4 border-t border-[var(--rule)] flex flex-wrap items-center justify-end gap-2 bg-[var(--cream-deep)]/30">
              <Button
                type="button"
                variant="outline"
                onClick={() => setRejectOpen(true)}
                className="border-[var(--rule)]"
                data-testid="inbound-queue-reject-open"
              >
                <X className="w-3.5 h-3.5 mr-1" /> Reject
              </Button>
              <Button
                type="button"
                onClick={() => setAcceptOpen(true)}
                className="bg-[var(--accent)] hover:bg-[var(--accent-deep)] text-white"
                data-testid="inbound-queue-accept-open"
              >
                <Check className="w-3.5 h-3.5 mr-1" /> Accept & ingest
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Accept confirm */}
      <Dialog open={acceptOpen} onOpenChange={setAcceptOpen}>
        <DialogContent className="bg-[var(--cream)] max-w-md border-[var(--rule)]" data-testid="inbound-queue-accept-modal">
          <DialogHeader>
            <DialogTitle className="akki-serif text-[20px] text-[var(--ink)] font-normal">
              Accept and ingest?
            </DialogTitle>
            <DialogDescription className="text-[13px] text-[var(--deep)]">
              AKKI will extract the content into your document library.
              A note helps future reviewers understand why you accepted it.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            rows={3}
            value={acceptNote}
            onChange={(e) => setAcceptNote(e.target.value)}
            placeholder="Why accept this? (optional)"
            className="bg-white border-[var(--rule)] resize-none"
            data-testid="inbound-queue-accept-note"
          />
          <div className="flex items-center justify-end gap-2 mt-2">
            <Button variant="outline" onClick={() => setAcceptOpen(false)} className="border-[var(--rule)]">
              Cancel
            </Button>
            <Button
              onClick={acceptItem}
              disabled={busyAction === "accept"}
              className="bg-[var(--accent)] hover:bg-[var(--accent-deep)] text-white"
              data-testid="inbound-queue-accept-confirm"
            >
              {busyAction === "accept" ? "Accepting…" : <><Check className="w-3.5 h-3.5 mr-1" /> Accept</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reject confirm */}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent className="bg-[var(--cream)] max-w-md border-[var(--rule)]" data-testid="inbound-queue-reject-modal">
          <DialogHeader>
            <DialogTitle className="akki-serif text-[20px] text-[var(--ink)] font-normal">
              Reject this email?
            </DialogTitle>
            <DialogDescription className="text-[13px] text-[var(--deep)]">
              The payload will be archived. No reply is sent to the sender.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Reason (optional) — e.g. phishing, not_relevant"
            className="bg-white border-[var(--rule)]"
            data-testid="inbound-queue-reject-reason"
          />
          <div className="flex items-center justify-end gap-2 mt-2">
            <Button variant="outline" onClick={() => setRejectOpen(false)} className="border-[var(--rule)]">
              Cancel
            </Button>
            <Button
              onClick={rejectItem}
              disabled={busyAction === "reject"}
              className="bg-[var(--ink)] hover:bg-black text-white"
              data-testid="inbound-queue-reject-confirm"
            >
              {busyAction === "reject" ? "Rejecting…" : <><X className="w-3.5 h-3.5 mr-1" /> Reject</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function QueueRow({ item, onClick, muted }) {
  const date = item.created_at
    ? new Date(item.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "";
  const status = item.status;
  const statusColor =
    status === "accepted" ? "text-emerald-700" :
    status === "rejected" ? "text-red-700" :
                             "text-[var(--accent)]";
  return (
    <li
      className={`px-4 py-3 border-b border-[var(--rule)] last:border-b-0 cursor-pointer hover:bg-[var(--cream-deep)]/30 transition-colors ${muted ? "opacity-80" : ""}`}
      onClick={onClick}
      data-testid={`inbound-queue-row-${item.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] font-mono mb-0.5 flex items-center gap-1.5">
            <Mail className="w-3 h-3" />
            {item.inbound_from_email || "(sender unknown)"}
            {date && <span className="text-[10.5px] text-[var(--muted)]">· {date}</span>}
          </p>
          <p className="text-[14px] text-[var(--ink)] leading-snug font-medium truncate">
            {item.inbound_subject || "(no subject)"}
          </p>
          {item.inbound_text_preview && (
            <p className="text-[12.5px] text-[var(--muted)] mt-1 line-clamp-2 leading-relaxed">
              {item.inbound_text_preview}
            </p>
          )}
        </div>
        <div className="shrink-0 flex flex-col items-end gap-1">
          <span className={`text-[10px] uppercase tracking-[0.14em] ${statusColor}`}>
            {status === "pending_review" ? "Pending" : status}
          </span>
          {item.inbound_attachment_count > 0 && (
            <span className="text-[10px] text-[var(--muted)] font-mono">
              {item.inbound_attachment_count} attachment{item.inbound_attachment_count === 1 ? "" : "s"}
            </span>
          )}
        </div>
      </div>
    </li>
  );
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
