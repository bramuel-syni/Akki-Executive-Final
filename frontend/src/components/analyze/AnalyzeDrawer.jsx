/**
 * AnalyzeDrawer — Track A Phase 2 (2026-06-04).
 *
 * Mirrors DocumentDrawer chrome (Sheet + Tabs). Three tabs:
 *
 *   Bottom Line · Sources · Export
 *
 * (Solva narration tabs land in Phase 3.)
 *
 * Topline statistics + objective input + auto-saved notes — same
 * shape as the Documents drawer's header + notes pattern.
 *
 * Opened from the Analyze Journal listing via `?aid=<id>` URL contract.
 * Closed by setting `aid` to null on the parent.
 */
import React, { useEffect, useState, useCallback, useRef } from "react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  FileSpreadsheet, FileText, FileDown, Layers, Loader2, MessageSquare, X,
} from "lucide-react";

const AUTOSAVE_DEBOUNCE_MS = 800;

function fmtRel(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const diffH = (Date.now() - d.getTime()) / 36e5;
    if (diffH < 1) return `${Math.max(1, Math.round(diffH * 60))} min ago`;
    if (diffH < 24) return `${Math.round(diffH)}h ago`;
    return d.toLocaleDateString();
  } catch { return "—"; }
}

export default function AnalyzeDrawer({ aid, onClose }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("bottom-line");
  const [synthesizing, setSynthesizing] = useState(false);

  // Objective + notes scratchpads (controlled inputs; debounced save).
  const [objective, setObjective] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const objectiveTimer = useRef(null);
  const [savingObjective, setSavingObjective] = useState(false);
  const [postingNote, setPostingNote] = useState(false);

  const open = !!aid;

  // Load the Analysis whenever the URL aid changes.
  const load = useCallback(async () => {
    if (!aid) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/workbook/v2/analyses/${aid}`);
      setAnalysis(data);
      setObjective(data?.objective || "");
    } catch (e) {
      toast.error(apiErrorMessage(e));
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  }, [aid]);

  useEffect(() => { load(); }, [load]);

  // Auto-save objective via PATCH.
  const onChangeObjective = (val) => {
    setObjective(val);
    if (objectiveTimer.current) clearTimeout(objectiveTimer.current);
    objectiveTimer.current = setTimeout(async () => {
      if (!aid) return;
      setSavingObjective(true);
      try {
        const { data } = await api.patch(`/workbook/v2/analyses/${aid}/objective`, {
          objective: val,
        });
        setAnalysis(data);
      } catch (e) {
        toast.error(apiErrorMessage(e));
      } finally {
        setSavingObjective(false);
      }
    }, AUTOSAVE_DEBOUNCE_MS);
  };

  // Post a new note.
  const onSubmitNote = async () => {
    const body = (noteDraft || "").trim();
    if (!body || !aid) return;
    setPostingNote(true);
    try {
      await api.post(`/workbook/v2/analyses/${aid}/notes`, { body });
      setNoteDraft("");
      await load();
      toast.success("Note saved");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setPostingNote(false);
    }
  };

  // Export — hit Phase 1 endpoints.
  const onExport = (ext) => {
    if (!aid) return;
    const url = `/api/workbook/analyses/${aid}/report.${ext}`;
    // Use a transient anchor so the browser triggers the download.
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  // Track A Phase 3 (2026-06-04) — trigger Solva v2 synthesis.
  const onSynthesize = async () => {
    if (!aid) return;
    setSynthesizing(true);
    try {
      await api.post(`/workbook/v2/analyses/${aid}/synthesize`);
      toast.success("Synthesis complete");
      await load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setSynthesizing(false);
    }
  };

  // Split observations by tab.
  const obsByTab = (analysis?.observations || []).reduce((acc, o) => {
    const k = o.kind || "synthesis";
    (acc[k] ||= []).push(o);
    return acc;
  }, {});

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent
        side="right"
        className="!w-[60vw] !max-w-[60vw] p-0 flex flex-col"
        data-testid="analyze-drawer"
        data-aid={aid || ""}
      >
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-[var(--muted)]" />
          </div>
        ) : !analysis ? (
          <div className="flex-1 flex items-center justify-center px-6">
            <div className="text-center">
              <p className="text-[13px] text-[var(--ink)]" data-testid="analyze-drawer-load-error">
                Could not load this analysis.
              </p>
              <Button onClick={onClose} size="sm" variant="outline" className="mt-3">Close</Button>
            </div>
          </div>
        ) : (
          <>
            {/* Header — topline statistics */}
            <header
              className="border-b border-[var(--rule)] px-6 py-4 flex items-start gap-3"
              data-testid="analyze-drawer-header"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span
                    className={`text-[10px] uppercase tracking-[0.16em] font-mono px-2 py-0.5 rounded-sm text-white ${
                      analysis.status === "purged"
                        ? "bg-[var(--muted)]"
                        : analysis.status === "ready"
                          ? "bg-emerald-700"
                          : "bg-[color:var(--oxblood)]"
                    }`}
                    data-testid="analyze-drawer-status-badge"
                  >
                    {String(analysis.status || "draft").toUpperCase()}
                  </span>
                  <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                    {(analysis.sources || []).length} source{(analysis.sources || []).length === 1 ? "" : "s"}
                  </span>
                </div>
                <h2 className="text-[18px] text-[var(--ink)] truncate" data-testid="analyze-drawer-title">
                  {analysis.title || "Untitled analysis"}
                </h2>
                <p className="text-[11px] text-[var(--muted)] mt-0.5">
                  Created {fmtRel(analysis.created_at)} · Updated {fmtRel(analysis.updated_at)}
                </p>
              </div>
              <button
                onClick={onClose}
                aria-label="Close"
                className="text-[var(--muted)] hover:text-[var(--ink)]"
                data-testid="analyze-drawer-close"
              >
                <X className="w-4 h-4" />
              </button>
            </header>

            {/* Objective — single-line scratchpad above the tabs */}
            <section className="px-6 py-3 border-b border-[var(--rule)] bg-[var(--cream-deep)]/30">
              <label className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] block mb-1">
                Objective
                {savingObjective && (
                  <span className="ml-2 inline-flex items-center text-[var(--muted)]">
                    <Loader2 className="w-3 h-3 animate-spin" />
                  </span>
                )}
              </label>
              <Textarea
                value={objective}
                onChange={(e) => onChangeObjective(e.target.value)}
                placeholder="What are you trying to learn from these files?"
                className="resize-none text-[13px] min-h-[44px]"
                rows={2}
                data-testid="analyze-drawer-objective-input"
              />
            </section>

            <div className="flex-1 overflow-hidden flex flex-col min-h-0">
              <Tabs value={tab} onValueChange={setTab} className="flex-1 flex flex-col min-h-0">
                <TabsList
                  className="px-6 border-b border-[var(--rule)] rounded-none justify-start bg-transparent h-auto"
                  data-testid="analyze-drawer-tabs"
                >
                  <TabsTrigger
                    value="bottom-line"
                    className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]"
                    data-testid="analyze-drawer-tab-bottom-line"
                  >
                    <MessageSquare className="w-3 h-3 mr-1.5" /> Bottom Line
                  </TabsTrigger>
                  <TabsTrigger
                    value="what-changed"
                    className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]"
                    data-testid="analyze-drawer-tab-what-changed"
                  >
                    What changed
                  </TabsTrigger>
                  <TabsTrigger
                    value="whats-likely-next"
                    className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]"
                    data-testid="analyze-drawer-tab-whats-likely-next"
                  >
                    What's likely next
                  </TabsTrigger>
                  <TabsTrigger
                    value="whats-odd"
                    className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]"
                    data-testid="analyze-drawer-tab-whats-odd"
                  >
                    What's odd
                  </TabsTrigger>
                  <TabsTrigger
                    value="sources"
                    className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]"
                    data-testid="analyze-drawer-tab-sources"
                  >
                    <Layers className="w-3 h-3 mr-1.5" /> Sources
                  </TabsTrigger>
                  <TabsTrigger
                    value="export"
                    className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]"
                    data-testid="analyze-drawer-tab-export"
                  >
                    <FileDown className="w-3 h-3 mr-1.5" /> Export
                  </TabsTrigger>
                </TabsList>

                {/* Bottom Line — Solva headline + first observations */}
                <TabsContent
                  value="bottom-line"
                  className="flex-1 overflow-y-auto px-6 py-5 space-y-5"
                  data-testid="analyze-drawer-bottom-line"
                >
                  {!analysis.headline && !(analysis.observations || []).length && (
                    <section data-testid="analyze-drawer-synthesize-prompt">
                      <p className="text-[13px] text-[var(--ink)] mb-3">
                        Run synthesis to produce the executive read-out.
                      </p>
                      <Button
                        onClick={onSynthesize}
                        disabled={synthesizing}
                        data-testid="analyze-drawer-synthesize-btn"
                      >
                        {synthesizing
                          ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Synthesizing…</>
                          : "Run synthesis"}
                      </Button>
                    </section>
                  )}
                  {analysis.headline && (
                    <section data-testid="analyze-drawer-headline">
                      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">
                        Bottom line
                      </p>
                      <p className="akki-serif text-[17px] text-[var(--ink)] leading-snug">
                        {analysis.headline}
                      </p>
                    </section>
                  )}
                  {(analysis.observations || []).slice(0, 3).map((o) => (
                    <section
                      key={o.id}
                      className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                      data-testid={`analyze-drawer-bottom-line-obs-${o.id}`}
                    >
                      <p className="text-[13.5px] text-[var(--ink)] font-semibold mb-1">{o.title}</p>
                      <p className="text-[12.5px] text-[var(--ink)] leading-relaxed">{o.detail}</p>
                      {(o.citations || []).length > 0 && (
                        <p className="text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--muted)] mt-1.5">
                          Citation: {o.citations[0]?.cell_range || ""}
                        </p>
                      )}
                    </section>
                  ))}
                  <section>
                    <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">
                      Your notes
                    </p>
                    {(analysis.notes_history || []).length === 0 ? (
                      <p className="text-[12px] italic text-[var(--muted)]">No notes yet.</p>
                    ) : (
                      <ul className="space-y-2" data-testid="analyze-drawer-notes-list">
                        {(analysis.notes_history || []).map((n) => (
                          <li
                            key={n.id}
                            className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                            data-testid={`analyze-drawer-note-${n.id}`}
                          >
                            <p className="text-[13px] text-[var(--ink)] whitespace-pre-wrap">{n.body}</p>
                            <p className="text-[10px] text-[var(--muted)] mt-1.5 font-mono uppercase tracking-[0.12em]">
                              {fmtRel(n.created_at)}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="mt-3 flex items-start gap-2">
                      <Textarea
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        placeholder="Add a note…"
                        rows={2}
                        className="text-[13px] flex-1"
                        data-testid="analyze-drawer-note-input"
                      />
                      <Button
                        onClick={onSubmitNote}
                        disabled={!noteDraft.trim() || postingNote}
                        size="sm"
                        data-testid="analyze-drawer-note-save"
                      >
                        {postingNote ? "Saving…" : "Save note"}
                      </Button>
                    </div>
                  </section>
                </TabsContent>

                {/* What changed — signal-kind observations */}
                <TabsContent
                  value="what-changed"
                  className="flex-1 overflow-y-auto px-6 py-5 space-y-3"
                  data-testid="analyze-drawer-what-changed"
                >
                  {(obsByTab.what_changed || []).length === 0 ? (
                    <p className="text-[12px] italic text-[var(--muted)]">
                      No signals narrated yet. Run synthesis on the Bottom Line tab.
                    </p>
                  ) : (obsByTab.what_changed || []).map((o) => (
                    <section
                      key={o.id}
                      className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                      data-testid={`analyze-drawer-what-changed-obs-${o.id}`}
                    >
                      <p className="text-[13.5px] text-[var(--ink)] font-semibold mb-1">{o.title}</p>
                      <p className="text-[12.5px] text-[var(--ink)] leading-relaxed">{o.detail}</p>
                      {(o.citations || []).map((c, i) => (
                        <span key={i} className="inline-block text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--muted)] mt-1.5 mr-2">
                          📎 {c.cell_range}
                        </span>
                      ))}
                    </section>
                  ))}
                </TabsContent>

                {/* What's likely next — forecast + monte carlo */}
                <TabsContent
                  value="whats-likely-next"
                  className="flex-1 overflow-y-auto px-6 py-5 space-y-3"
                  data-testid="analyze-drawer-whats-likely-next"
                >
                  {/* Track A Phase 6 (2026-06-04) — read partial flag
                      from runs[-1] directly. Top-level narration BC
                      mirror dropped in Phase 6 BC removal sweep;
                      runs[-1] is the canonical source. */}
                  {(() => {
                    const latestRun = (analysis?.runs || []).slice(-1)[0] || {};
                    return latestRun.partial_narration_missing_forecast_low_signal && (
                    <div
                      className="border border-amber-300 bg-amber-50/70 rounded-sm p-3 text-[12px] text-amber-900"
                      data-testid="analyze-drawer-low-signal-banner"
                    >
                      The forecast model fit this data weakly (R² below 0.30).
                      Treat the forward-looking read as exploratory, not a
                      planning baseline.
                    </div>
                    );
                  })()}
                  {(obsByTab.whats_likely_next || []).length === 0 ? (
                    <p className="text-[12px] italic text-[var(--muted)]">
                      No forecast narration yet. Run synthesis on the Bottom Line tab.
                    </p>
                  ) : (obsByTab.whats_likely_next || []).map((o) => (
                    <section
                      key={o.id}
                      className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                      data-testid={`analyze-drawer-whats-likely-next-obs-${o.id}`}
                    >
                      <p className="text-[13.5px] text-[var(--ink)] font-semibold mb-1">{o.title}</p>
                      <p className="text-[12.5px] text-[var(--ink)] leading-relaxed">{o.detail}</p>
                      {(o.citations || []).map((c, i) => (
                        <span key={i} className="inline-block text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--muted)] mt-1.5 mr-2">
                          📎 {c.cell_range}
                        </span>
                      ))}
                    </section>
                  ))}
                </TabsContent>

                {/* What's odd — anomaly narration */}
                <TabsContent
                  value="whats-odd"
                  className="flex-1 overflow-y-auto px-6 py-5 space-y-3"
                  data-testid="analyze-drawer-whats-odd"
                >
                  {(obsByTab.whats_odd || []).length === 0 ? (
                    <p className="text-[12px] italic text-[var(--muted)]">
                      No anomaly narration yet. Run synthesis on the Bottom Line tab.
                    </p>
                  ) : (obsByTab.whats_odd || []).map((o) => (
                    <section
                      key={o.id}
                      className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                      data-testid={`analyze-drawer-whats-odd-obs-${o.id}`}
                    >
                      <p className="text-[13.5px] text-[var(--ink)] font-semibold mb-1">{o.title}</p>
                      <p className="text-[12.5px] text-[var(--ink)] leading-relaxed">{o.detail}</p>
                      {(o.citations || []).map((c, i) => (
                        <span key={i} className="inline-block text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--muted)] mt-1.5 mr-2">
                          📎 {c.cell_range}
                        </span>
                      ))}
                    </section>
                  ))}
                </TabsContent>

                {/* Sources — per-file stage timing record */}
                <TabsContent
                  value="sources"
                  className="flex-1 overflow-y-auto px-6 py-5 space-y-3"
                  data-testid="analyze-drawer-sources"
                >
                  {(analysis.sources || []).map((src) => (
                    <div
                      key={src.source_id}
                      className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                      data-testid={`analyze-drawer-source-${src.source_id}`}
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-[13px] text-[var(--ink)]">{src.filename}</p>
                        <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                          {src.file_format} · {(src.file_size_bytes / 1024).toFixed(1)} KB
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--muted)] font-mono uppercase tracking-[0.12em] mt-1">
                        Uploaded {fmtRel(src.uploaded_at)}
                        {src.blob_purged ? " · binary purged on session-close" : ""}
                      </p>
                    </div>
                  ))}
                  {(analysis.runs || []).length > 0 && (
                    <section className="mt-5" data-testid="analyze-drawer-runs-history">
                      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">
                        Synthesis history
                      </p>
                      <ul className="space-y-1.5">
                        {(analysis.runs || []).map((r) => (
                          <li
                            key={r.run_id}
                            className="text-[12px] text-[var(--ink)] flex items-center gap-2 border-l-2 border-[var(--rule)] pl-2"
                            data-testid={`analyze-drawer-run-${r.run_id}`}
                          >
                            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
                              {r.refused ? "refused" : "run"}
                            </span>
                            <span className="truncate flex-1">
                              {r.headline || "(no headline)"}
                            </span>
                            <span className="text-[10px] text-[var(--muted)] ml-auto whitespace-nowrap">
                              {fmtRel(r.created_at)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {(analysis.refresh_history || []).length > 0 && (
                    <section className="mt-5">
                      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">
                        Refresh history
                      </p>
                      <ul className="space-y-1.5">
                        {(analysis.refresh_history || []).map((r) => (
                          <li key={r.refresh_id} className="text-[12px] text-[var(--ink)] flex items-center gap-2">
                            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
                              {r.triggered_by}
                            </span>
                            <span>{r.note}</span>
                            <span className="text-[10px] text-[var(--muted)] ml-auto">{fmtRel(r.ran_at)}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                </TabsContent>

                {/* Export — 3 buttons to Phase 1 endpoints */}
                <TabsContent
                  value="export"
                  className="flex-1 overflow-y-auto px-6 py-5"
                  data-testid="analyze-drawer-export"
                >
                  <p className="text-[12px] text-[var(--muted)] mb-4">
                    Download a report containing the analysis content + source inventory.
                    Solva narration arrives in Phase 3; the present exports carry the
                    deterministic content available today.
                  </p>
                  <div className="flex flex-col gap-2 max-w-md">
                    <Button
                      onClick={() => onExport("xlsx")}
                      variant="outline"
                      className="justify-start"
                      data-testid="analyze-drawer-export-xlsx"
                    >
                      <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel workbook (.xlsx)
                    </Button>
                    <Button
                      onClick={() => onExport("docx")}
                      variant="outline"
                      className="justify-start"
                      data-testid="analyze-drawer-export-docx"
                    >
                      <FileText className="w-4 h-4 mr-2" /> Word document (.docx)
                    </Button>
                    <Button
                      onClick={() => onExport("pptx")}
                      variant="outline"
                      className="justify-start"
                      data-testid="analyze-drawer-export-pptx"
                    >
                      <FileDown className="w-4 h-4 mr-2" /> PowerPoint deck (.pptx)
                    </Button>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
