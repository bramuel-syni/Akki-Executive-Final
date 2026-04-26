import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Eye, Send, Link2, Mail, ArrowRight, Loader2, X,
} from "lucide-react";

/**
 * DocumentEngagement — read receipts, share counter, linked-document map.
 *
 * Renders inside the DocumentViewer outline rail. Composes three primitives:
 *   • Who's read it (deduped per account; owner views excluded)
 *   • Where it's been shared (recorded share intents)
 *   • What it's linked to (ancestor + descendant docs in the related_doc_id graph)
 *
 * Editorial cadence: no progress bars or notification badges; just the
 * counts and the people behind them.
 */

function fmtRelativeOrDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  } catch { return "—"; }
}

export default function DocumentEngagement({ contextId, docId }) {
  const [data, setData] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);

  const load = useCallback(async () => {
    if (!contextId || !docId) return;
    try {
      const { data: d } = await api.get(`/contexts/${contextId}/documents/${docId}/engagement`);
      setData(d);
    } catch { setData(null); }
    finally { setLoaded(true); }
  }, [contextId, docId]);
  useEffect(() => { load(); }, [load]);

  if (!loaded) return null;
  const d = data || { view_count: 0, unique_readers: 0, readers: [], share_count: 0, shares: [], linked_count: 0, linked_documents: [] };

  return (
    <div className="px-4 py-5 border-t border-[#E1E6ED]" data-testid="doc-engagement">
      <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold mb-3">
        Engagement
      </p>

      {/* Stat row */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <Stat icon={Eye} label="reads" value={d.unique_readers} testid="doc-eng-reads" />
        <Stat icon={Send} label="shares" value={d.share_count} testid="doc-eng-shares" />
        <Stat icon={Link2} label="linked" value={d.linked_count} testid="doc-eng-linked" />
      </div>

      {/* Readers */}
      {d.readers.length > 0 && (
        <div className="mb-4" data-testid="doc-eng-readers">
          <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Read by</p>
          <ul className="space-y-1.5">
            {d.readers.slice(0, 6).map((r) => (
              <li key={r.account_id} className="flex items-start gap-2 text-[11.5px]">
                <span className="w-5 h-5 rounded-full bg-[var(--cream-deep)] flex items-center justify-center shrink-0 text-[10px] text-[var(--accent)] font-medium">
                  {(r.name || "?").split(" ").map(s => s[0]).join("").slice(0, 2).toUpperCase()}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="text-slate-700 truncate block">{r.name}</span>
                  <span className="text-slate-400 text-[10.5px]">
                    {fmtRelativeOrDate(r.last_viewed_at)}
                    {r.view_count > 1 && ` · ${r.view_count}×`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Shares */}
      {d.shares.length > 0 && (
        <div className="mb-4" data-testid="doc-eng-shares-list">
          <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Shared with</p>
          <ul className="space-y-1.5">
            {d.shares.slice(0, 5).map((s) => (
              <li key={s.id} className="text-[11.5px]">
                <span className="text-slate-700 block truncate">{s.shared_with_name}</span>
                <span className="text-slate-400 text-[10.5px] truncate block">
                  {s.shared_with_email} · {fmtRelativeOrDate(s.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Linked documents */}
      {d.linked_documents.length > 0 && (
        <div className="mb-4" data-testid="doc-eng-linked-list">
          <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Linked documents</p>
          <ul className="space-y-1.5">
            {d.linked_documents.slice(0, 6).map((l) => (
              <li key={l.id} className="text-[11.5px]">
                <Link
                  to={`/app/documents/${l.id}`}
                  className="text-slate-700 hover:text-[var(--accent)] flex items-start gap-1.5"
                >
                  <ArrowRight className="w-3 h-3 mt-0.5 shrink-0" />
                  <span className="flex-1 min-w-0">
                    <span className="block truncate">{l.name}</span>
                    <span className="text-slate-400 text-[10.5px] italic">{l.relation}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button
        size="sm"
        variant="outline"
        onClick={() => setShareOpen(true)}
        className="w-full border-[var(--rule)] text-[12px] h-8"
        data-testid="doc-eng-share-btn"
      >
        <Mail className="w-3 h-3 mr-1.5" /> Share by email
      </Button>

      {shareOpen && (
        <ShareDocumentModal
          contextId={contextId}
          docId={docId}
          onClose={() => setShareOpen(false)}
          onShared={() => { setShareOpen(false); load(); }}
        />
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, testid }) {
  return (
    <div className="bg-white border border-[var(--rule)] rounded-sm px-2 py-2 text-center" data-testid={testid}>
      <Icon className="w-3 h-3 text-[var(--accent)] mx-auto mb-1" strokeWidth={1.6} />
      <p className="akki-serif text-[16px] text-[var(--ink)] leading-none">{value}</p>
      <p className="text-[9.5px] uppercase tracking-wider text-slate-400 mt-1">{label}</p>
    </div>
  );
}

function ShareDocumentModal({ contextId, docId, onClose, onShared }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    try {
      await api.post(`/contexts/${contextId}/documents/${docId}/share`, {
        to_email: email.trim(), to_name: name.trim() || null, message: message.trim() || null,
      });
      toast.success(`Recorded share with ${email.trim()}.`);
      onShared();
    } catch (err) { toast.error(apiErrorMessage(err)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <form
        onSubmit={submit}
        className="bg-white rounded-md shadow-xl border border-[var(--rule)] w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
        data-testid="doc-share-modal"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="akki-serif text-[18px] text-[var(--ink)]">Share this document</h2>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[12px] text-slate-500 mb-4 italic">
          We'll record who you sent it to so you can track who's read it.
        </p>
        <div className="space-y-3">
          <input
            type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="Recipient email"
            className="w-full px-3 py-2 border border-[var(--rule)] rounded-sm text-[13px]"
            data-testid="doc-share-email"
          />
          <input
            type="text" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Recipient name (optional)"
            className="w-full px-3 py-2 border border-[var(--rule)] rounded-sm text-[13px]"
            data-testid="doc-share-name"
          />
          <textarea
            value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder="Message (optional)"
            rows={3}
            className="w-full px-3 py-2 border border-[var(--rule)] rounded-sm text-[13px] resize-none"
            data-testid="doc-share-message"
          />
        </div>
        <div className="flex items-center justify-end gap-2 mt-5">
          <Button type="button" variant="ghost" onClick={onClose} className="text-[12px] h-8">
            Cancel
          </Button>
          <Button
            type="submit" disabled={busy || !email.trim()}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] h-8"
            data-testid="doc-share-submit"
          >
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : "Record share"}
          </Button>
        </div>
      </form>
    </div>
  );
}
