/**
 * DocumentJournalStats — top-line numbers for the Document Journal.
 *
 * Replaces the upload-form hero per user feedback. Surfaces:
 *   - Total documents
 *   - Trust split (trusted / mixed / weak as % of total)
 *   - Status split (extracted / failed / empty)
 *   - Last addition timestamp
 *
 * The "Add a document" button drops to the corner so upload is still
 * one click away — it's just no longer the centerpiece.
 */
import React, { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Upload, ShieldCheck, FileText, AlertTriangle, CheckCircle2, Camera } from "lucide-react";

function StatChip({ label, n, total, tone }) {
  const pct = total === 0 ? 0 : Math.round((n / total) * 100);
  const toneCls =
    tone === "good"  ? "text-emerald-700" :
    tone === "warn"  ? "text-amber-700" :
    tone === "alert" ? "text-red-700" : "text-[var(--ink)]";
  return (
    <div className="flex flex-col" data-testid={`docs-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono">{label}</p>
      <p className={`akki-serif text-[18px] tabular-nums leading-none mt-1 ${toneCls}`}>
        {n}
        <span className="text-[11.5px] text-[var(--muted)] ml-1.5 italic">{total > 0 ? `· ${pct}%` : ""}</span>
      </p>
    </div>
  );
}

export default function DocumentJournalStats({ docs = [], onUploadClick, onCameraClick, uploading }) {
  const stats = useMemo(() => {
    const total = docs.length;
    const trust = { trusted: 0, mixed: 0, weak: 0 };
    const status = { extracted: 0, empty: 0, failed: 0, uploaded: 0 };
    for (const d of docs) {
      if (trust[d.data_trust] !== undefined) trust[d.data_trust] += 1;
      if (status[d.status] !== undefined) status[d.status] += 1;
    }
    const lastAt = docs.length
      ? docs.reduce((latest, d) => {
          const t = d.created_at;
          return t && (!latest || t > latest) ? t : latest;
        }, null)
      : null;
    return { total, trust, status, lastAt };
  }, [docs]);

  const lastRel = useMemo(() => {
    if (!stats.lastAt) return "—";
    try {
      const d = new Date(stats.lastAt);
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 60) return "just now";
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
      return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
    } catch { return "—"; }
  }, [stats.lastAt]);

  return (
    <div className="bg-white border border-[#E1E6ED] rounded-md p-5 mx-6 mt-5 mb-3" data-testid="docs-journal-stats">
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <p className="akki-overline mb-1">Document journal · at a glance</p>
          <h2 className="akki-serif text-[20px] text-[var(--ink)] leading-snug">
            {stats.total === 0 ? "No documents yet." : `${stats.total} document${stats.total === 1 ? "" : "s"} on file.`}
          </h2>
          <p className="text-[12px] text-[var(--muted)] mt-1">
            Last addition · <span className="text-[var(--deep)]">{lastRel}</span>
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            onClick={onCameraClick}
            disabled={uploading}
            variant="outline"
            className="rounded-md h-9 text-[12px] border-[#E1E6ED]"
            data-testid="docs-camera-btn"
            title="Capture a page with your device camera"
          >
            <Camera className="w-3.5 h-3.5 mr-1.5" /> Camera
          </Button>
          <Button
            onClick={onUploadClick}
            disabled={uploading}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-9 text-[12px]"
            data-testid="docs-upload-btn"
          >
            <Upload className="w-3.5 h-3.5 mr-1.5" />
            {uploading ? "Uploading…" : "Add a document"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-3 pt-4 border-t border-[#E1E6ED]">
        <StatChip label="Trusted" n={stats.trust.trusted} total={stats.total} tone="good" />
        <StatChip label="Mixed trust" n={stats.trust.mixed} total={stats.total} tone="warn" />
        <StatChip label="Weak trust" n={stats.trust.weak} total={stats.total} tone="alert" />
        <StatChip label="Extracted" n={stats.status.extracted} total={stats.total} tone="good" />
      </div>
    </div>
  );
}
