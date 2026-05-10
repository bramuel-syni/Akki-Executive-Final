/**
 * Phase C.3 — Brief workspace.
 *
 * In-page surface that opens after Compose generates a brief, OR when
 * the user reopens an existing brief. Renders:
 *   - Header strip (title, source label, format, depth, fidelity)
 *   - Active revision actions (Refine, Re-export at active)
 *   - Revision strip (chronological cards, including refused)
 *   - Selected-revision diff view (vs the active revision)
 *
 * Re-export uses the C.1 endpoint with `source_type=work_studio_brief`
 * and the active `revision_id`. The download is streamed as a Blob and
 * triggered as a real file save.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft, Wand2, FileDown, RefreshCw, Loader2, AlertCircle, FileText,
  Presentation, FileType,
} from "lucide-react";
import { toast } from "sonner";
import RefineDrawer from "./RefineDrawer";
import RevisionStrip from "./RevisionStrip";
import DiffView from "./DiffView";

const FORMAT_ICON = { docx: FileText, pptx: Presentation, pdf: FileType };

function labelMap(picker, group, key) {
  const items = (picker?.[group]) || [];
  const it = items.find((x) => x.key === key);
  return it?.label || key;
}

async function streamDownload(downloadUrl, filename) {
  const resp = await api.get(downloadUrl.replace(/^\/api/, ""), { responseType: "blob" });
  const blob = resp.data;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "akki-brief";
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 200);
}

export default function BriefWorkspace({
  briefId,
  initialExport,        // {download_url, filename, format, depth, fidelity, ...} — from compose result
  onBack,
}) {
  const [meta, setMeta] = useState(null);          // {brief, active_revision}
  const [revisions, setRevisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refineOpen, setRefineOpen] = useState(false);

  const [selectedRevId, setSelectedRevId] = useState(null);
  const [comparison, setComparison] = useState(null);   // {left, right, diff}
  const [comparisonLoading, setComparisonLoading] = useState(false);

  const [reexporting, setReexporting] = useState(false);
  const [latestExport, setLatestExport] = useState(initialExport || null);

  const [picker, setPicker] = useState(null);

  const refresh = useCallback(async () => {
    if (!briefId) return;
    setLoading(true);
    setError(null);
    try {
      const [m, r, p] = await Promise.all([
        api.get(`/work_studio/briefs/${briefId}`),
        api.get(`/work_studio/briefs/${briefId}/revisions`),
        picker ? Promise.resolve({ data: picker }) : api.get("/work_studio/picker"),
      ]);
      setMeta(m.data);
      setRevisions(r.data?.items || []);
      setPicker(p.data);
      // Default selected revision = active revision (so the diff view is
      // empty initially — selecting active vs active is a no-op).
      const activeId = m.data?.brief?.active_revision_id;
      setSelectedRevId((prev) => prev || activeId || null);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [briefId, picker]);

  useEffect(() => { refresh(); }, [refresh]);

  // Load the diff whenever the user picks a different revision card.
  useEffect(() => {
    if (!briefId || !selectedRevId || !meta) return;
    const activeId = meta?.brief?.active_revision_id;
    if (selectedRevId === activeId) {
      setComparison({ left: activeId, right: activeId, diff: [] });
      return;
    }
    let cancelled = false;
    setComparisonLoading(true);
    api.get(`/work_studio/briefs/${briefId}/revisions/${selectedRevId}/diff`, {
      params: { against: activeId },
    })
      .then(({ data }) => { if (!cancelled) setComparison(data); })
      .catch((e) => { if (!cancelled) toast.error("Diff failed", { description: apiErrorMessage(e) }); })
      .finally(() => { if (!cancelled) setComparisonLoading(false); });
    return () => { cancelled = true; };
  }, [briefId, selectedRevId, meta]);

  const briefMeta = meta?.brief;
  const activeRev = meta?.active_revision;
  const activeSnapshot = useMemo(() => activeRev?.snapshot || {}, [activeRev]);
  const activeSections = useMemo(
    () => (activeSnapshot.sections || []).map((s) => ({ section_id: s.section_id, title: s.title })),
    [activeSnapshot],
  );

  const handleReexport = async () => {
    if (!briefMeta || !latestExport) return;
    setReexporting(true);
    try {
      const { data } = await api.post("/work_studio/exports", {
        source_id: briefMeta.id,
        source_type: "work_studio_brief",
        format: latestExport.format,
        depth: latestExport.depth,
        fidelity: latestExport.fidelity,
        company_label: briefMeta.company_label || "Akki",
        document_type: briefMeta.document_type || "Board Briefing",
        programme: briefMeta.programme || null,
      });
      setLatestExport({
        ...latestExport,
        download_url: data.download_url,
        filename: data.filename,
        size_bytes: data.size_bytes,
        export_id: data.export_id,
        revision_id: data.revision_id,
      });
      await streamDownload(data.download_url, data.filename);
      toast.success("Re-exported.", { description: data.filename });
    } catch (e) {
      toast.error("Re-export failed", { description: apiErrorMessage(e) });
    } finally {
      setReexporting(false);
    }
  };

  const handleDownloadCurrent = async () => {
    if (!latestExport?.download_url) return;
    try {
      await streamDownload(latestExport.download_url, latestExport.filename);
    } catch (e) {
      toast.error("Download failed", { description: apiErrorMessage(e) });
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-[var(--muted)] text-sm flex items-center justify-center gap-2" data-testid="workspace-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading brief…
      </div>
    );
  }
  if (error || !briefMeta) {
    return (
      <div className="p-6">
        <Button variant="ghost" size="sm" onClick={onBack} className="text-[var(--muted)] hover:text-[var(--ink)] mb-3">
          <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Back to sources
        </Button>
        <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5" /> {error || "Brief not found."}
        </div>
      </div>
    );
  }

  const FmtIcon = FORMAT_ICON[latestExport?.format] || FileText;

  return (
    <div data-testid="brief-workspace">
      <Button
        variant="ghost" size="sm" onClick={onBack}
        className="text-[var(--muted)] hover:text-[var(--ink)] mb-3 -ml-2"
        data-testid="workspace-back"
      >
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Back to sources
      </Button>

      {/* Brief header */}
      <div className="border border-[var(--rule)] bg-white rounded-md px-5 py-4 mb-5" data-testid="workspace-header">
        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">
          {briefMeta.company_label} · {briefMeta.document_type}{briefMeta.programme ? ` · ${briefMeta.programme}` : ""}
        </p>
        <h2 className="akki-serif text-[20px] text-[var(--ink)] leading-snug" data-testid="workspace-title">
          {activeSnapshot.title || briefMeta.title || "Untitled brief"}
        </h2>
        <p className="akki-serif text-[13.5px] text-[var(--deep)] mt-1">
          {activeSnapshot.subtitle || briefMeta.subtitle || ""}
        </p>
        <div className="flex items-center gap-2 mt-3 flex-wrap text-[11.5px] text-[var(--muted)]">
          <span className="font-mono uppercase tracking-[0.14em]">
            Active rev · {(briefMeta.active_revision_id || "").slice(0, 8)}
          </span>
          <span>·</span>
          <span>{revisions.length} revisions</span>
          {latestExport && (
            <>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <FmtIcon className="w-3 h-3" />
                {latestExport.format.toUpperCase()} · {labelMap(picker, "depth", latestExport.depth)} · {labelMap(picker, "fidelity", latestExport.fidelity)}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2 mt-4 flex-wrap">
          <Button
            type="button"
            onClick={() => setRefineOpen(true)}
            className="akki-cta bg-[var(--accent-dark)] hover:bg-[var(--accent)] text-white"
            data-testid="workspace-refine"
          >
            <Wand2 className="w-3.5 h-3.5 mr-2" /> Refine
          </Button>
          {latestExport && (
            <Button
              type="button"
              variant="outline"
              onClick={handleDownloadCurrent}
              className="rounded-sm border-[var(--rule)] text-[12.5px]"
              data-testid="workspace-download"
            >
              <FileDown className="w-3.5 h-3.5 mr-1.5" /> Download {latestExport.filename}
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={handleReexport}
            disabled={reexporting || !latestExport}
            className="rounded-sm border-[var(--rule)] text-[12.5px]"
            data-testid="workspace-reexport"
          >
            {reexporting ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
            Re-export at active revision
          </Button>
        </div>
      </div>

      {/* Revision strip */}
      <div className="mb-5">
        <RevisionStrip
          revisions={revisions}
          activeId={briefMeta.active_revision_id}
          selectedId={selectedRevId}
          onSelect={setSelectedRevId}
        />
      </div>

      {/* Selected-revision diff vs active */}
      <div className="mb-10" data-testid="workspace-diff-region">
        {comparisonLoading ? (
          <div className="text-[var(--muted)] text-[13px] flex items-center gap-2 px-1 py-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading diff…
          </div>
        ) : selectedRevId === briefMeta.active_revision_id ? (
          <p className="text-[12.5px] text-[var(--muted)] italic px-1 py-2" data-testid="workspace-diff-active-self">
            The active revision is selected — click any other revision card to compare it against active.
          </p>
        ) : comparison ? (
          <>
            <div className="flex items-baseline gap-2 mb-2">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
                Comparing
              </p>
              <p className="text-[12px] text-[var(--ink)] font-mono">
                {(comparison.left || "").slice(0, 8)} (active) → {(comparison.right || "").slice(0, 8)}
              </p>
            </div>
            <DiffView diff={comparison.diff || []} />
          </>
        ) : null}
      </div>

      {/* Refine drawer */}
      <RefineDrawer
        open={refineOpen}
        onClose={() => setRefineOpen(false)}
        briefId={briefId}
        briefSnapshotSections={activeSections}
        onRefined={() => { refresh(); }}
      />
    </div>
  );
}
