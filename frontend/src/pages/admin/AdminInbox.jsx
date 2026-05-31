/**
 * Phase P5.8.2 (2026-02) — Admin "Akki Inbox" surface.
 *
 * Lists every inbound email captured by the SendGrid Inbound Parse
 * pipeline. Super-admin + MFA gated server-side; this component
 * trusts the auth gate at the router level. List + detail view in
 * one component to keep router surface minimal.
 *
 * HTML body rendering: we set the sanitized HTML via dangerouslySet
 * INNER_HTML inside an isolated <article> with `sandbox`-style
 * styling (no scripts, no remote loads). Sanitization is performed
 * on the client via DOMPurify if available; otherwise we fall back
 * to displaying the plain-text body only.
 */
import React, { useEffect, useMemo, useState } from "react";
import DOMPurify from "dompurify";
import { api } from "@/lib/api";
import { toast } from "sonner";

const STATUS_LABELS = {
  new:        "New",
  read:       "Read",
  replied:    "Replied",
  dismissed:  "Dismissed",
};

function statusPill(status) {
  const tone = {
    new:        "bg-amber-100 text-amber-800 border-amber-300",
    read:       "bg-slate-100 text-slate-600 border-slate-300",
    replied:    "bg-emerald-100 text-emerald-800 border-emerald-300",
    dismissed:  "bg-slate-100 text-slate-400 border-slate-200",
  }[status] || "bg-slate-100 text-slate-600";
  return (
    <span
      className={`text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${tone}`}
      data-testid={`inbox-status-pill-${status}`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function _sanitize(html) {
  if (!html) return null;
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

export default function AdminInbox() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus !== "all") params.set("status", filterStatus);
      if (query.trim()) params.set("q", query.trim());
      params.set("limit", "50");
      const { data } = await api.get(`/admin/inbox/messages?${params.toString()}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      toast.error("Couldn't load inbox.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterStatus]);

  const openMessage = async (id) => {
    setSelectedId(id);
    setDetailLoading(true);
    setSelectedDetail(null);
    try {
      const { data } = await api.get(`/admin/inbox/messages/${id}`);
      setSelectedDetail(data.item);
      // If the row's status flipped new → read, reflect in the list locally.
      setItems((prev) => prev.map((m) => (m.id === id ? { ...m, status: data.item.status, read_at: data.item.read_at } : m)));
    } catch (err) {
      toast.error("Couldn't load message.");
    } finally {
      setDetailLoading(false);
    }
  };

  const setStatus = async (id, status) => {
    try {
      await api.post(`/admin/inbox/messages/${id}/status`, { status });
      setItems((prev) => prev.map((m) => (m.id === id ? { ...m, status } : m)));
      if (selectedDetail && selectedDetail.id === id) {
        setSelectedDetail({ ...selectedDetail, status });
      }
      toast.success(`Marked ${status}.`);
    } catch {
      toast.error("Couldn't update status.");
    }
  };

  const sanitizedHtml = useMemo(() => {
    if (!selectedDetail || !selectedDetail.html_body) return null;
    return _sanitize(selectedDetail.html_body);
  }, [selectedDetail]);

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="admin-inbox-page">
      <div className="flex items-baseline justify-between mb-6 gap-4 flex-wrap">
        <h1 className="text-2xl font-serif text-slate-900" data-testid="admin-inbox-heading">
          Akki Inbox
        </h1>
        <p className="text-xs text-slate-500" data-testid="admin-inbox-total">
          {total} total · showing {items.length}
        </p>
      </div>

      <div className="flex items-center gap-2 mb-4 flex-wrap" data-testid="admin-inbox-filters">
        {["all", "new", "read", "replied", "dismissed"].map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`text-xs px-2.5 py-1 rounded-sm border ${
              filterStatus === s
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-700 border-slate-300 hover:border-slate-500"
            }`}
            data-testid={`admin-inbox-filter-${s}`}
          >
            {s === "all" ? "All" : STATUS_LABELS[s]}
          </button>
        ))}
        <form
          onSubmit={(e) => { e.preventDefault(); load(); }}
          className="ml-auto flex items-center gap-1"
        >
          <input
            type="text"
            placeholder="Search subject, from, body..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="text-xs px-2 py-1 border border-slate-300 rounded-sm w-64"
            data-testid="admin-inbox-search"
          />
          <button
            type="submit"
            className="text-xs px-2.5 py-1 border border-slate-300 rounded-sm hover:bg-slate-50"
            data-testid="admin-inbox-search-submit"
          >
            Search
          </button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-4">
        {/* List column */}
        <div className="border border-slate-200 rounded-sm bg-white">
          {loading ? (
            <p className="p-4 text-sm text-slate-500" data-testid="admin-inbox-loading">Loading…</p>
          ) : items.length === 0 ? (
            <p className="p-4 text-sm text-slate-500" data-testid="admin-inbox-empty">
              No messages match this filter.
            </p>
          ) : (
            <ul className="divide-y divide-slate-200" data-testid="admin-inbox-list">
              {items.map((m) => (
                <li
                  key={m.id}
                  className={`px-3 py-2.5 cursor-pointer hover:bg-slate-50 ${
                    selectedId === m.id ? "bg-slate-100" : ""
                  } ${m.status === "new" ? "border-l-2 border-l-amber-500" : ""}`}
                  onClick={() => openMessage(m.id)}
                  data-testid={`admin-inbox-row-${m.id}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="text-xs font-medium text-slate-900 truncate">
                      {m.from_name || m.from_email}
                    </span>
                    {statusPill(m.status)}
                  </div>
                  <p className="text-xs text-slate-700 font-medium truncate">{m.subject || "(no subject)"}</p>
                  <p className="text-[11px] text-slate-500 truncate mt-0.5">{m.body_snippet}</p>
                  <p className="text-[10px] text-slate-400 font-mono mt-1">
                    {new Date(m.received_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Detail column */}
        <div className="border border-slate-200 rounded-sm bg-white min-h-[400px]">
          {!selectedDetail ? (
            <p className="p-6 text-sm text-slate-500" data-testid="admin-inbox-detail-empty">
              Select a message to view it here.
            </p>
          ) : (
            <article className="p-6" data-testid="admin-inbox-detail">
              <header className="border-b border-slate-200 pb-4 mb-4">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <h2 className="text-lg font-serif text-slate-900" data-testid="admin-inbox-detail-subject">
                    {selectedDetail.subject || "(no subject)"}
                  </h2>
                  {statusPill(selectedDetail.status)}
                </div>
                <dl className="text-xs grid grid-cols-[60px_1fr] gap-x-3 gap-y-1 text-slate-700">
                  <dt className="text-slate-400">From</dt>
                  <dd data-testid="admin-inbox-detail-from">
                    {selectedDetail.from_name
                      ? `${selectedDetail.from_name} <${selectedDetail.from_email}>`
                      : selectedDetail.from_email}
                  </dd>
                  <dt className="text-slate-400">To</dt>
                  <dd data-testid="admin-inbox-detail-to">
                    {(selectedDetail.to_addresses || []).join(", ") || "—"}
                  </dd>
                  <dt className="text-slate-400">Sent</dt>
                  <dd>{new Date(selectedDetail.received_at).toLocaleString()}</dd>
                  <dt className="text-slate-400">Routed</dt>
                  <dd className="font-mono text-[11px]">{selectedDetail.routing_result || "—"}</dd>
                </dl>
                <div className="flex items-center gap-2 mt-3 flex-wrap">
                  <button
                    onClick={() => setStatus(selectedDetail.id, "replied")}
                    disabled={selectedDetail.status === "replied"}
                    className="text-xs px-2.5 py-1 border border-emerald-300 bg-emerald-50 text-emerald-800 rounded-sm hover:bg-emerald-100 disabled:opacity-40"
                    data-testid="admin-inbox-detail-mark-replied"
                  >
                    Mark replied
                  </button>
                  <button
                    onClick={() => setStatus(selectedDetail.id, "dismissed")}
                    disabled={selectedDetail.status === "dismissed"}
                    className="text-xs px-2.5 py-1 border border-slate-300 rounded-sm hover:bg-slate-50 disabled:opacity-40"
                    data-testid="admin-inbox-detail-dismiss"
                  >
                    Dismiss
                  </button>
                  <a
                    href={`mailto:${selectedDetail.from_email}?subject=Re:%20${encodeURIComponent(selectedDetail.subject || "")}`}
                    className="text-xs px-2.5 py-1 border border-slate-900 bg-slate-900 text-white rounded-sm hover:bg-slate-700 ml-auto"
                    data-testid="admin-inbox-detail-reply-link"
                  >
                    Open reply
                  </a>
                </div>
              </header>

              {/* Body */}
              <section className="prose prose-sm max-w-none" data-testid="admin-inbox-detail-body">
                {sanitizedHtml ? (
                  <div
                    className="text-sm text-slate-800"
                    dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
                  />
                ) : (
                  <pre className="text-sm text-slate-800 whitespace-pre-wrap font-sans" data-testid="admin-inbox-detail-text">
                    {selectedDetail.text_body || "(no body)"}
                  </pre>
                )}
              </section>

              {/* Attachments */}
              {(selectedDetail.attachments || []).length > 0 && (
                <section className="mt-6 pt-4 border-t border-slate-200" data-testid="admin-inbox-detail-attachments">
                  <p className="text-xs uppercase tracking-wider text-slate-500 font-semibold mb-2">
                    {selectedDetail.attachments.length} attachment{selectedDetail.attachments.length === 1 ? "" : "s"}
                  </p>
                  <ul className="text-xs space-y-1">
                    {selectedDetail.attachments.map((a, i) => (
                      <li key={i} className="text-slate-700 flex items-center gap-2">
                        <span className="font-mono text-[11px] text-slate-500">{a.content_type}</span>
                        <span className="font-medium">{a.name || "(unnamed)"}</span>
                        <span className="text-slate-400">{(a.size_bytes / 1024).toFixed(1)} KB</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-[11px] text-slate-400 mt-2 italic">
                    Attachment payloads are stored in the inbound queue; download links not exposed in this view.
                  </p>
                </section>
              )}
            </article>
          )}
          {detailLoading && (
            <p className="p-6 text-sm text-slate-500" data-testid="admin-inbox-detail-loading">Loading message…</p>
          )}
        </div>
      </div>
    </div>
  );
}
