/**
 * ReadingTopBar — sticky header for the Reading Viewer.
 *
 * Slots:
 *   - Document title (truncate, full title in tooltip)
 *   - Sensitivity badge (trust band styles, no new tokens)
 *   - Primary action: "Generate brief" — single primary action per the
 *     rules doc.
 *   - Secondary icon-only actions: download original, close (back to
 *     /app/workspace).
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Download, FileText, Loader2, ShieldCheck, X } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";  // Patch 28C — switched from API_BASE href to api blob download

const TRUST_STYLE = {
  trusted: "text-emerald-700 bg-emerald-50 border-emerald-200",
  internal: "text-amber-700 bg-amber-50 border-amber-200",
  mixed: "text-amber-700 bg-amber-50 border-amber-200",
  confidential: "text-red-700 bg-red-50 border-red-200",
  weak: "text-red-700 bg-red-50 border-red-200",
  restricted: "text-red-700 bg-red-50 border-red-200",
};

export default function ReadingTopBar({
  doc,
  contextId,
  contextName,
  onGenerateBrief,
  generatingBrief = false,
}) {
  const navigate = useNavigate();
  if (!doc) return null;
  const trust = doc.data_trust;
  const trustClass = TRUST_STYLE[trust] || TRUST_STYLE.mixed;

  return (
    <header
      className="sticky top-0 z-30 border-b border-[var(--rule)] bg-[var(--cream)]/95 backdrop-blur-sm"
      data-testid="reading-topbar"
    >
      <div className="max-w-[1280px] mx-auto px-6 md:px-8 py-3.5 flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="rounded-sm h-8 px-2 text-slate-600 hover:text-[var(--ink)] hidden md:inline-flex"
          onClick={() => navigate("/app/workspace")}
          data-testid="reading-back-btn"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Workspace
        </Button>

        <div className="flex-1 min-w-0">
          <p className="akki-overline text-[10px] mb-0.5 text-[var(--muted)]">
            Reading {contextName ? `· ${contextName}` : ""}
          </p>
          <div className="flex items-center gap-3 min-w-0">
            <TooltipProvider delayDuration={250}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <h1
                    className="akki-serif text-[18px] md:text-[20px] font-normal text-[var(--ink)] truncate"
                    data-testid="reading-doc-title"
                  >
                    {doc.name}
                  </h1>
                </TooltipTrigger>
                <TooltipContent side="bottom">{doc.name}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            {trust ? (
              <span
                className={`hidden md:inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wider border ${trustClass}`}
                data-testid="reading-trust-badge"
              >
                <ShieldCheck className="w-3 h-3" /> {trust}
              </span>
            ) : null}
          </div>
          {/* Mobile-only sensitivity row sits below the title (per brief). */}
          {trust ? (
            <div className="md:hidden mt-1.5">
              <span
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wider border ${trustClass}`}
                data-testid="reading-trust-badge-mobile"
              >
                <ShieldCheck className="w-3 h-3" /> {trust}
              </span>
            </div>
          ) : null}
        </div>

        <Button
          onClick={onGenerateBrief}
          disabled={generatingBrief}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white akki-overline tracking-[0.16em] text-[11px] h-8 px-3.5 rounded-sm"
          data-testid="reading-generate-brief-btn"
        >
          {generatingBrief ? (
            <span className="inline-flex items-center gap-1.5">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading the pack…
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" /> Generate brief
            </span>
          )}
        </Button>

        <div className="hidden md:flex items-center gap-1">
          {/* Patch 28C — Download document button.
              Previously a plain <a href={API_BASE}/contexts/…/download>
              which (a) renders as an icon-only "empty button" (one of
              the issues the user flagged) and (b) bypasses the axios
              `api` bearer-token interceptor — same regression class
              as Patch 23. Now downloads via api.get blob + Object URL
              so it works regardless of cookie scope, and carries an
              explicit "Download" label on hover for clarity. */}
          <button
            type="button"
            onClick={async () => {
              try {
                const { data: blob, headers } = await api.get(
                  `/contexts/${contextId}/documents/${doc.id}/download`,
                  { responseType: "blob" },
                );
                const disp = headers["content-disposition"] || "";
                const m = /filename="([^"]+)"/.exec(disp);
                const fname = m ? m[1] : (doc.original_filename || doc.title || "document");
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = fname;
                a.click();
                setTimeout(() => URL.revokeObjectURL(url), 60_000);
              } catch (e) {
                /* eslint-disable no-console */
                console.error("download failed:", e);
                /* eslint-enable no-console */
              }
            }}
            title="Download original"
            aria-label="Download original"
            className="inline-flex items-center justify-center w-8 h-8 rounded-sm text-slate-500 hover:text-[var(--ink)] hover:bg-white border border-transparent hover:border-[var(--rule)]"
            data-testid="reading-download-btn"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => navigate("/app/workspace")}
            title="Close"
            className="inline-flex items-center justify-center w-8 h-8 rounded-sm text-slate-500 hover:text-[var(--ink)] hover:bg-white border border-transparent hover:border-[var(--rule)]"
            data-testid="reading-close-btn"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
