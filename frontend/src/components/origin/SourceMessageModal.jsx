/**
 * Phase P5.17 (2026-02) — Source-message modal.
 *
 * Loads + renders the tenant-scoped read-only preview of an inbox
 * message that seeded a routed item. Fetches from
 * GET /api/inbox/messages/{message_id}/preview.
 *
 * Cross-tenant or missing message → 404 from the backend → renders
 * a polite empty-state.
 *
 * Reverse-navigation links:
 *   • Superadmin → `/app/admin/inbox#message-<id>` (deep link into
 *     the admin inbox surface).
 *   • Non-admin (this case) sees the read-only preview INLINE —
 *     no additional navigation; the modal IS the surface.
 */
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function SourceMessageModal({ origin, onClose, isSuperadmin }) {
  const [loading, setLoading] = useState(false);
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    if (!origin?.message_id) return;
    setLoading(true);
    setError(null);
    api
      .get(`/inbox/messages/${origin.message_id}/preview`)
      .then(({ data }) => { if (alive) setItem(data.item); })
      .catch((err) => {
        if (!alive) return;
        const status = err?.response?.status;
        setError(status === 404 ? "not_found" : "error");
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [origin?.message_id]);

  const handleBackdrop = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4"
      data-testid="source-message-modal"
      onClick={handleBackdrop}
    >
      <div className="bg-white rounded-sm border border-slate-200 max-w-2xl w-full max-h-[80vh] overflow-auto">
        <header className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <h3 className="text-sm font-serif text-slate-900">Source email</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-slate-500 hover:text-slate-900"
            data-testid="source-message-modal-close"
          >
            Close
          </button>
        </header>
        <div className="p-5">
          {loading && (
            <p className="text-xs text-slate-500" data-testid="source-message-modal-loading">
              Loading source message…
            </p>
          )}
          {error === "not_found" && (
            <p className="text-xs text-slate-500" data-testid="source-message-modal-empty">
              This source message is no longer available, or you do not have access.
            </p>
          )}
          {error === "error" && (
            <p className="text-xs text-red-600" data-testid="source-message-modal-error">
              Could not load the source message.
            </p>
          )}
          {item && (
            <article className="space-y-3" data-testid="source-message-modal-body">
              <dl className="text-xs grid grid-cols-[60px_1fr] gap-x-3 gap-y-1 text-slate-700">
                <dt className="text-slate-400">From</dt>
                <dd data-testid="source-message-modal-from">
                  {item.from_name
                    ? `${item.from_name} <${item.from_email}>`
                    : item.from_email}
                </dd>
                <dt className="text-slate-400">Subject</dt>
                <dd data-testid="source-message-modal-subject">{item.subject || "(no subject)"}</dd>
                <dt className="text-slate-400">Received</dt>
                <dd>{item.received_at ? new Date(item.received_at).toLocaleString() : "—"}</dd>
                {item.classification && (
                  <>
                    <dt className="text-slate-400">Route</dt>
                    <dd className="font-mono text-[11px]">
                      {item.classification.route_kind} · {item.classification.confidence}
                    </dd>
                  </>
                )}
              </dl>
              {item.classification?.rationale && (
                <p className="text-xs text-slate-600 italic">
                  {item.classification.rationale}
                </p>
              )}
              <section className="border-t border-slate-100 pt-3">
                <pre
                  className="text-xs text-slate-800 whitespace-pre-wrap font-sans"
                  data-testid="source-message-modal-text"
                >
                  {item.body_text || "(empty body)"}
                </pre>
              </section>
              {isSuperadmin && (
                <a
                  href={`/app/admin/inbox#message-${item.id}`}
                  className="inline-block text-xs px-2.5 py-1 border border-slate-900 bg-slate-900 text-white rounded-sm hover:bg-slate-700"
                  data-testid="source-message-modal-admin-link"
                >
                  View in admin inbox →
                </a>
              )}
            </article>
          )}
        </div>
      </div>
    </div>
  );
}

export default SourceMessageModal;
