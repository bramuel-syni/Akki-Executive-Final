/**
 * Solva v2 — PPTX export toolbar (queue position 4, 2026-05-29).
 *
 * Single CTA: "Download .pptx" — fetches the native PowerPoint binary
 * from `GET /api/solva/sessions/{sid}/v2/export.pptx`, parses out the
 * Content-Disposition filename, and triggers a download via a
 * synthetic `<a>` click.
 *
 * Stays disabled until the session is complete — the .pptx mirrors
 * the on-screen state so we don't ship half-rendered decks.
 *
 * `print:hidden` keeps the toolbar out of the printed paper artefact.
 */
import React, { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "../../../lib/api";


function _filenameFromContentDisposition(headerValue) {
  if (!headerValue) return null;
  const m = /filename="?([^"]+)"?/.exec(headerValue);
  return m ? m[1] : null;
}


export default function SolvaPptxToolbar({ sessionId, isComplete }) {
  const [downloading, setDownloading] = useState(false);

  const onDownload = async () => {
    if (downloading || !isComplete) return;
    setDownloading(true);
    const toastId = toast.loading("Rendering .pptx…");
    try {
      const resp = await api.get(
        `/solva/sessions/${sessionId}/v2/export.pptx`,
        { responseType: "blob" },
      );
      const blob = resp.data;
      if (!blob || blob.size === 0) {
        throw new Error("Empty .pptx body");
      }
      const filename =
        _filenameFromContentDisposition(resp.headers?.["content-disposition"])
        || `solva-${sessionId.slice(0, 8)}.pptx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      // Allow the browser a tick to start the download before revoking.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.dismiss(toastId);
      toast.success(`Downloaded ${filename}.`);
    } catch (e) {
      toast.dismiss(toastId);
      toast.error(
        e?.response?.data?.detail || e?.message || "Failed to download .pptx"
      );
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      className="solva-v2-pptx-toolbar print:hidden flex justify-end mb-3"
      data-testid="solva-v2-pptx-toolbar"
      data-solva-v2-pptx-toolbar="true"
    >
      <button
        type="button"
        onClick={onDownload}
        disabled={downloading || !isComplete}
        title={
          !isComplete
            ? "Available once the session is complete"
            : "Download a native .pptx with all 16 slides"
        }
        className={[
          "inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5",
          "font-mono text-[10.5px] uppercase tracking-[0.14em] transition-colors",
          (downloading || !isComplete)
            ? "border-[var(--rule)] text-[var(--muted)] cursor-not-allowed"
            : "border-ned-purple/30 text-[var(--ned-purple)] hover:bg-ned-purple/10 cursor-pointer",
        ].join(" ")}
        data-testid="solva-v2-pptx-download"
        data-solva-v2-pptx-download="true"
        aria-disabled={downloading || !isComplete}
      >
        {downloading ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : (
          <Download className="w-3 h-3" />
        )}
        {downloading ? "Rendering…" : "Download .pptx"}
      </button>
    </div>
  );
}
