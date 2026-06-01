/**
 * Phase P5.8.2 (2026-02) — Admin "Akki Inbox" surface.
 * Phase P5.16 (2026-02) — Email Akki auto-routing extensions.
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
 *
 * P5.16 adds:
 *   - Route-kind status chip per row (auto-routed / suggested /
 *     unclassified / manually routed).
 *   - Row-action affordances on the detail panel: Classify /
 *     Route to task / Route to cycle / Route to signal / Dismiss.
 *   - Routing-log modal showing every audit-log row for the message.
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

// P5.16 — route-kind chip labels + tones.
const ROUTE_KIND_LABELS = {
  task_create:     "Task",
  cycle_update:    "Cycle",
  signal_post:     "Signal",
  discussion_only: "Discussion",
  unclassified:    "Unclassified",
};

function routeKindChip(classification) {
  if (!classification) {
    return (
      <span
        className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm border bg-slate-50 text-slate-400 border-slate-200"
        data-testid="inbox-routekind-chip-pending"
      >
        Pending
      </span>
    );
  }
  const rk = classification.route_kind || "unclassified";
  const conf = classification.confidence || "low";
  const tone = {
    high:   "bg-emerald-100 text-emerald-800 border-emerald-300",
    medium: "bg-amber-100 text-amber-800 border-amber-300",
    low:    "bg-slate-100 text-slate-600 border-slate-300",
  }[conf] || "bg-slate-100 text-slate-600";
  return (
    <span
      className={`text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${tone}`}
      data-testid={`inbox-routekind-chip-${rk}`}
      title={`Confidence: ${conf}`}
    >
      {ROUTE_KIND_LABELS[rk] || rk} · {conf}
    </span>
  );
}

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

  // ── P5.16 ─────────────────────────────────────────────────
  const [routingLog, setRoutingLog] = useState(null);
  const [routingLogLoading, setRoutingLogLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);

  const classify = async (id) => {
    setActionBusy(true);
    try {
      const { data } = await api.post(`/admin/inbox/messages/${id}/classify`);
      setItems((prev) => prev.map((m) => (m.id === id ? { ...m, classification: data.classification } : m)));
      if (selectedDetail && selectedDetail.id === id) {
        setSelectedDetail({ ...selectedDetail, classification: data.classification });
      }
      toast.success(`Classified: ${data.classification.route_kind} (${data.classification.confidence}).`);
    } catch {
      toast.error("Classification failed.");
    } finally {
      setActionBusy(false);
    }
  };

  const route = async (id, route_kind, extraHint = {}) => {
    setActionBusy(true);
    try {
      const hint = { ...(selectedDetail?.classification?.target_hint || {}), ...extraHint };
      const { data } = await api.post(`/admin/inbox/messages/${id}/route`, {
        route_kind,
        target_hint: hint,
      });
      toast.success(`Routed → ${route_kind} (${data.result.target_kind || "log"}).`);
      // Re-fetch the detail so the chip updates.
      await openMessage(id);
    } catch (e) {
      toast.error("Route failed.");
    } finally {
      setActionBusy(false);
    }
  };

  const dismiss = async (id) => {
    setActionBusy(true);
    try {
      await api.post(`/admin/inbox/messages/${id}/dismiss`);
      setItems((prev) => prev.map((m) => (m.id === id ? { ...m, status: "dismissed" } : m)));
      if (selectedDetail && selectedDetail.id === id) {
        setSelectedDetail({ ...selectedDetail, status: "dismissed" });
      }
      toast.success("Dismissed.");
    } catch {
      toast.error("Dismiss failed.");
    } finally {
      setActionBusy(false);
    }
  };

  const openRoutingLog = async (id) => {
    setRoutingLog([]);
    setRoutingLogLoading(true);
    try {
      const { data } = await api.get(`/admin/inbox/messages/${id}/routing-log`);
      setRoutingLog(data.items || []);
    } catch {
      toast.error("Couldn't load routing log.");
      setRoutingLog([]);
    } finally {
      setRoutingLogLoading(false);
    }
  };

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
                    <div className="flex items-center gap-1.5 shrink-0">
                      {routeKindChip(m.classification)}
                      {statusPill(m.status)}
                    </div>
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
                  <div className="flex items-center gap-1.5 shrink-0">
                    {routeKindChip(selectedDetail.classification)}
                    {statusPill(selectedDetail.status)}
                  </div>
                </div>
                {selectedDetail.classification && selectedDetail.classification.rationale && (
                  <p
                    className="text-xs text-slate-600 italic mb-3"
                    data-testid="admin-inbox-detail-rationale"
                  >
                    {selectedDetail.classification.rationale}
                  </p>
                )}
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

                {/* P5.16 — routing affordances */}
                <div
                  className="flex items-center gap-2 mt-3 flex-wrap pt-3 border-t border-slate-100"
                  data-testid="admin-inbox-routing-actions"
                >
                  <button
                    onClick={() => classify(selectedDetail.id)}
                    disabled={actionBusy}
                    className="text-xs px-2.5 py-1 border border-slate-300 rounded-sm hover:bg-slate-50 disabled:opacity-40"
                    data-testid="admin-inbox-action-classify"
                  >
                    {selectedDetail.classification ? "Re-classify" : "Classify"}
                  </button>
                  <button
                    onClick={() => route(selectedDetail.id, "task_create")}
                    disabled={actionBusy || !(selectedDetail.classification?.target_hint?.account_id)}
                    className="text-xs px-2.5 py-1 border border-indigo-300 bg-indigo-50 text-indigo-800 rounded-sm hover:bg-indigo-100 disabled:opacity-40"
                    data-testid="admin-inbox-action-route-task"
                    title={!(selectedDetail.classification?.target_hint?.account_id) ? "Classify first (or the sender has no account on file)" : ""}
                  >
                    Route → Task
                  </button>
                  <button
                    onClick={() => route(selectedDetail.id, "cycle_update")}
                    disabled={actionBusy || !(selectedDetail.classification?.target_hint?.account_id)}
                    className="text-xs px-2.5 py-1 border border-indigo-300 bg-indigo-50 text-indigo-800 rounded-sm hover:bg-indigo-100 disabled:opacity-40"
                    data-testid="admin-inbox-action-route-cycle"
                  >
                    Route → Cycle
                  </button>
                  <button
                    onClick={() => route(selectedDetail.id, "signal_post")}
                    disabled={actionBusy || !(selectedDetail.classification?.target_hint?.account_id)}
                    className="text-xs px-2.5 py-1 border border-indigo-300 bg-indigo-50 text-indigo-800 rounded-sm hover:bg-indigo-100 disabled:opacity-40"
                    data-testid="admin-inbox-action-route-signal"
                  >
                    Route → Signal
                  </button>
                  <button
                    onClick={() => dismiss(selectedDetail.id)}
                    disabled={actionBusy}
                    className="text-xs px-2.5 py-1 border border-slate-300 rounded-sm hover:bg-slate-50 disabled:opacity-40"
                    data-testid="admin-inbox-action-mark-discussion"
                  >
                    Mark discussion only
                  </button>
                  <button
                    onClick={() => openRoutingLog(selectedDetail.id)}
                    className="text-xs px-2.5 py-1 border border-slate-300 rounded-sm hover:bg-slate-50 ml-auto"
                    data-testid="admin-inbox-action-routing-log"
                  >
                    Routing log
                  </button>
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

      {/* P5.16 — Routing-log modal */}
      {routingLog !== null && (
        <div
          className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4"
          data-testid="admin-inbox-routing-log-modal"
          onClick={(e) => { if (e.target === e.currentTarget) setRoutingLog(null); }}
        >
          <div className="bg-white rounded-sm border border-slate-200 max-w-2xl w-full max-h-[80vh] overflow-auto">
            <header className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
              <h3 className="text-sm font-serif text-slate-900">Routing log</h3>
              <button
                onClick={() => setRoutingLog(null)}
                className="text-xs text-slate-500 hover:text-slate-900"
                data-testid="admin-inbox-routing-log-close"
              >
                Close
              </button>
            </header>
            <div className="p-5">
              {routingLogLoading ? (
                <p className="text-xs text-slate-500" data-testid="admin-inbox-routing-log-loading">Loading…</p>
              ) : routingLog.length === 0 ? (
                <p
                  className="text-xs text-slate-500"
                  data-testid="admin-inbox-routing-log-empty"
                >
                  No routing decisions recorded for this message yet.
                </p>
              ) : (
                <ol className="space-y-3" data-testid="admin-inbox-routing-log-list">
                  {routingLog.map((row) => (
                    <li
                      key={row.id}
                      className="border border-slate-200 rounded-sm p-3"
                      data-testid={`admin-inbox-routing-log-row-${row.id}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-[11px] font-mono uppercase tracking-wider text-slate-600">
                          {row.route_kind} · {row.confidence} · {row.decision_source}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {new Date(row.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700">{row.rationale}</p>
                      {row.target_id && (
                        <p className="text-[11px] font-mono text-slate-500 mt-1">
                          Target: {row.target_kind} · {row.target_id}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
