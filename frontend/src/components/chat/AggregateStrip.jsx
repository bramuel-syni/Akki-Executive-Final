/**
 * AggregateStrip — pinned banner at the top of the chat surface
 * showing per-conversation Synisense protection KPIs.
 *
 * Phase C (2026-05-13). Re-fetches the aggregate via the backend's
 * `/api/chats/{cid}/audit-panel/aggregate` endpoint after every
 * assistant turn (parent passes a `refreshNonce` that bumps on each
 * new assistant message).
 *
 * Phase E Sub-task H (2026-05-16) — Adds a "Privacy report" download
 * button that streams the chat's privacy PDF via
 * `/api/chats/{cid}/privacy-report.pdf`.
 */
import React, { useState, useEffect } from "react";
import { api } from "../../lib/api";
import { ShieldCheck, FileDown } from "lucide-react";

export default function AggregateStrip({ chatId, refreshNonce = 0 }) {
  const [agg, setAgg] = useState(null);
  const [err, setErr] = useState(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!chatId) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(
          `/chats/${chatId}/audit-panel/aggregate`
        );
        if (!cancelled) setAgg(data);
      } catch (e) {
        if (!cancelled)
          setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chatId, refreshNonce]);

  const onDownload = async () => {
    if (!chatId) return;
    setDownloading(true);
    try {
      const res = await api.get(`/chats/${chatId}/privacy-report.pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `privacy-report-${chatId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally {
      setDownloading(false);
    }
  };

  if (!chatId) return null;
  if (err) {
    return (
      <div className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
        Audit aggregate unavailable: {err}
      </div>
    );
  }
  if (!agg) return null;
  if ((agg.llm_calls ?? 0) === 0) return null;

  return (
    <div
      data-testid="chat-audit-aggregate-strip"
      className="mb-3 flex flex-col gap-1 rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-xs text-emerald-900 sm:flex-row sm:items-center sm:gap-3"
    >
      <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-700" />
      <span className="leading-snug">{agg.headline_prose}</span>
      <button
        type="button"
        onClick={onDownload}
        disabled={downloading}
        data-testid="chat-privacy-report-download"
        className="ml-auto flex items-center gap-1 rounded border border-emerald-300 px-2 py-1 text-emerald-800 hover:bg-emerald-100/70 disabled:opacity-60"
      >
        <FileDown className="h-3 w-3" />
        {downloading ? "Generating…" : "Privacy report PDF"}
      </button>
    </div>
  );
}
