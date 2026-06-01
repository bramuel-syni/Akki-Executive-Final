/**
 * Phase P5.14 — Work Studio · Analyze tab.
 *
 * End-to-end workbook analysis surface:
 *   1. Upload .xlsx or .csv
 *   2. Sheet preview (parsed metadata + column kinds)
 *   3. Run signal extraction
 *   4. Run a Monte Carlo simulation on a chosen numeric column
 *   5. Run a linear forecast on a chosen date + value column pair
 *   6. Detect anomalies on a chosen sheet
 *   7. Download the cited PPTX report
 *
 * Every state-changing call carries `X-CSRF-Token` (P5.10 lesson —
 * the axios interceptor injects it on axios-wrapped calls; this
 * page uses the `api` wrapper so the header rides automatically).
 */
import React, { useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import WorkStudioMasterTabs from "@/components/work_studio/WorkStudioMasterTabs";
import useAnalyzeStages from "@/components/work_studio/useAnalyzeStages";
import AnalyzeStageStrip from "@/components/work_studio/AnalyzeStageStrip";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function WorkStudioAnalyze() {
  const [analysis, setAnalysis] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(null); // "signals" | "simulate" | "forecast" | "anomalies" | "report"
  const stagesApi = useAnalyzeStages();

  // ── Upload ────────────────────────────────────────────────────
  const onFile = async (file) => {
    if (!file) return;
    setUploading(true);
    stagesApi.reset();
    stagesApi.start("parse");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/workbook/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      // Fetch the full row (model_dump includes empty arrays).
      const { data: full } = await api.get(`/workbook/analyses/${data.id}`);
      setAnalysis(full);
      stagesApi.success("parse");
      toast.success(`Parsed ${full.filename} — ${full.sheets.length} sheet(s)`);
    } catch (e) {
      stagesApi.error("parse", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    } finally {
      setUploading(false);
    }
  };

  const refresh = async () => {
    if (!analysis?.id) return;
    const { data } = await api.get(`/workbook/analyses/${analysis.id}`);
    setAnalysis(data);
  };

  const runSignals = async () => {
    setBusy("signals");
    stagesApi.start("signals");
    try {
      await api.post(`/workbook/analyses/${analysis.id}/signals/extract`);
      stagesApi.success("signals");
      await refresh();
    } catch (e) {
      stagesApi.error("signals", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    }
    finally { setBusy(null); }
  };

  const runSimulate = async (sheet, column) => {
    setBusy("simulate");
    stagesApi.start("simulate");
    try {
      const col = sheet.columns.find((c) => c.name === column);
      const mean = Number(col?.mean ?? 0);
      const stddev = Math.max(Number(col?.stddev ?? 1), 1e-6);
      await api.post(`/workbook/analyses/${analysis.id}/simulate`, {
        sheet: sheet.name,
        column,
        distribution: "normal",
        params: { mean, stddev },
        iterations: 5000,
        formula: "=x",
        seed: 42,
      });
      stagesApi.success("simulate");
      await refresh();
    } catch (e) {
      stagesApi.error("simulate", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    }
    finally { setBusy(null); }
  };

  const runForecast = async (sheet, dateCol, valueCol) => {
    setBusy("forecast");
    stagesApi.start("forecast");
    try {
      await api.post(`/workbook/analyses/${analysis.id}/forecast`, {
        sheet: sheet.name,
        date_column: dateCol,
        value_column: valueCol,
        horizon_periods: 8,
      });
      stagesApi.success("forecast");
      await refresh();
    } catch (e) {
      stagesApi.error("forecast", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    }
    finally { setBusy(null); }
  };

  const runAnomalies = async (sheet) => {
    setBusy("anomalies");
    stagesApi.start("anomalies");
    try {
      await api.post(`/workbook/analyses/${analysis.id}/anomalies`, {
        sheet: sheet.name,
      });
      stagesApi.success("anomalies");
      await refresh();
    } catch (e) {
      stagesApi.error("anomalies", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    }
    finally { setBusy(null); }
  };

  const downloadPptx = async () => {
    setBusy("report");
    stagesApi.start("report");
    try {
      // Fetch the bytes via the api wrapper so we capture the
      // real status / duration for the stage strip, then trigger
      // the download via a Blob URL — the response is a real
      // wire event, not a synthetic anchor click.
      const r = await api.get(
        `/workbook/analyses/${analysis.id}/report.pptx`,
        { responseType: "blob" },
      );
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.setAttribute("download", `${analysis.filename}_analysis.pptx`);
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      stagesApi.success("report");
    } catch (e) {
      stagesApi.error("report", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    }
    finally { setBusy(null); }
  };

  return (
    <AppShell>
      <div className="akki-w-medium px-8 pt-10 pb-12" data-testid="work-studio-analyze-page">
        <WorkStudioMasterTabs />

        <h1 className="text-3xl font-medium tracking-tight" data-testid="analyze-h1">
          Analyze
        </h1>
        <p className="mt-2 text-[var(--muted)] text-sm max-w-2xl">
          Upload a workbook. Akki reads the numbers, surfaces signals with cell-range citations,
          runs Monte Carlo simulations on a numeric column, projects forward with linear regression,
          and lists anomalies. Then download a cited PPTX brief.
        </p>

        {/* Upload zone */}
        {!analysis && (
          <div
            data-testid="analyze-upload-zone"
            className="mt-10 border border-dashed border-[var(--rule)] rounded-lg p-10 text-center"
          >
            <label className="cursor-pointer inline-block">
              <input
                type="file"
                accept=".xlsx,.csv"
                onChange={(e) => onFile(e.target.files?.[0])}
                disabled={uploading}
                className="hidden"
                data-testid="analyze-upload-input"
              />
              <span
                className="inline-block px-5 py-2 rounded-full bg-[color:var(--oxblood)] text-white text-sm"
                data-testid="analyze-upload-cta"
              >
                {uploading ? "Uploading…" : "Choose .xlsx or .csv"}
              </span>
            </label>
            <p className="mt-3 text-xs text-[var(--muted)]">
              Up to 25 MB. Akki only sees column metadata and a representative sample of rows —
              the full dataset never crosses the LLM boundary.
            </p>
            {/* During upload, show the stage strip so the parse stage
                is visible while it's in flight (the parsed-view branch
                below renders the strip in steady-state). */}
            <AnalyzeStageStrip stages={stagesApi.stages} defs={stagesApi.defs} />
          </div>
        )}

        {/* Parsed view */}
        {analysis && (
          <div className="mt-10 space-y-10" data-testid="analyze-parsed-view">
            <header className="flex items-baseline justify-between">
              <div>
                <h2 className="text-xl">{analysis.filename}</h2>
                <p className="text-xs text-[var(--muted)] mt-1">
                  {analysis.file_format.toUpperCase()} · {analysis.sheets.length} sheet(s) ·
                  status {analysis.status}
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => setAnalysis(null)}
                data-testid="analyze-reset-btn"
              >Start over</Button>
            </header>

            {/* Sheet preview */}
            <section data-testid="analyze-sheet-preview">
              <h3 className="text-sm tracking-[0.16em] uppercase text-[var(--muted)]">Sheet preview</h3>
              <div className="mt-3 space-y-6">
                {analysis.sheets.map((sheet) => (
                  <div
                    key={sheet.name}
                    className="border border-[var(--rule)] rounded p-4"
                    data-testid={`analyze-sheet-card-${sheet.name}`}
                  >
                    <div className="flex items-baseline justify-between">
                      <div className="font-medium">{sheet.name}</div>
                      <div className="text-xs text-[var(--muted)]">
                        {sheet.n_rows} rows · {sheet.n_columns} columns
                      </div>
                    </div>
                    <ul className="mt-3 text-xs text-[var(--muted)] grid grid-cols-2 gap-x-6 gap-y-1">
                      {sheet.columns.slice(0, 12).map((c) => (
                        <li key={c.name} className="truncate">
                          <span className="text-[var(--ink)]">{c.name}</span>
                          <span className="ml-2 opacity-70">({c.kind})</span>
                          {c.kind === "numeric" && c.mean != null ? (
                            <span className="ml-2 opacity-70">mean {c.mean.toFixed(2)}</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>

            {/* Actions */}
            <section className="flex flex-wrap gap-3" data-testid="analyze-actions">
              <Button
                onClick={runSignals}
                disabled={busy !== null}
                data-testid="analyze-run-signals-btn"
              >{busy === "signals" ? "Running…" : "Extract signals"}</Button>

              {analysis.sheets[0] && analysis.sheets[0].columns.some((c) => c.kind === "numeric") && (
                <Button
                  variant="outline"
                  onClick={() => {
                    const sheet = analysis.sheets[0];
                    const col = sheet.columns.find((c) => c.kind === "numeric");
                    runSimulate(sheet, col.name);
                  }}
                  disabled={busy !== null}
                  data-testid="analyze-run-simulate-btn"
                >{busy === "simulate" ? "Simulating…" : "Run Monte Carlo (P10/P50/P90)"}</Button>
              )}

              {/* Forecast — show only when sheet has a date column + numeric column. */}
              {analysis.sheets[0] && (() => {
                const sheet = analysis.sheets[0];
                const dateCol = sheet.columns.find((c) => c.kind === "date");
                const numCol = sheet.columns.find((c) => c.kind === "numeric");
                if (!dateCol || !numCol) return null;
                return (
                  <Button
                    variant="outline"
                    onClick={() => runForecast(sheet, dateCol.name, numCol.name)}
                    disabled={busy !== null}
                    data-testid="analyze-run-forecast-btn"
                  >{busy === "forecast" ? "Forecasting…" : "Forecast forward (8 periods)"}</Button>
                );
              })()}

              {analysis.sheets[0] && analysis.sheets[0].columns.some((c) => c.kind === "numeric") && (
                <Button
                  variant="outline"
                  onClick={() => runAnomalies(analysis.sheets[0])}
                  disabled={busy !== null}
                  data-testid="analyze-run-anomalies-btn"
                >{busy === "anomalies" ? "Scanning…" : "Detect anomalies"}</Button>
              )}

              <Button
                variant="default"
                onClick={downloadPptx}
                disabled={busy !== null}
                data-testid="analyze-download-pptx-btn"
              >{busy === "report" ? "Preparing…" : "Download PPTX report"}</Button>
            </section>

            {/* Stage strip — real-wire status of the most recent
                run of each analysis stage. Hidden until the first
                stage transitions out of idle. */}
            <AnalyzeStageStrip stages={stagesApi.stages} defs={stagesApi.defs} />

            {/* Signals */}
            {analysis.signals.length > 0 && (
              <section data-testid="analyze-signals-list">
                <h3 className="text-sm tracking-[0.16em] uppercase text-[var(--muted)]">Signals</h3>
                <div className="mt-3 space-y-3">
                  {analysis.signals.map((s, i) => (
                    <div
                      key={i}
                      className="border border-[var(--rule)] rounded p-4"
                      data-testid={`analyze-signal-${i}`}
                    >
                      <div className="text-xs uppercase tracking-[0.14em] text-[var(--muted)]">{s.kind}</div>
                      <div className="font-medium">{s.title}</div>
                      <div className="text-sm mt-1">{s.detail}</div>
                      <div className="text-xs text-[var(--muted)] mt-2">
                        {s.citations.map((c, ci) => (
                          <span key={ci} className="inline-block mr-3" data-testid={`analyze-signal-cite-${i}-${ci}`}>
                            cited cells <code className="text-[var(--ink)]">{c.cell_range}</code>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Simulations */}
            {analysis.simulations.length > 0 && (
              <section data-testid="analyze-simulations-list">
                <h3 className="text-sm tracking-[0.16em] uppercase text-[var(--muted)]">Simulations</h3>
                <div className="mt-3 space-y-3">
                  {analysis.simulations.map((mc, i) => (
                    <div
                      key={mc.id}
                      className="border border-[var(--rule)] rounded p-4"
                      data-testid={`analyze-simulation-${i}`}
                    >
                      <div className="font-medium">{mc.column} — {mc.distribution}</div>
                      <div className="text-xs text-[var(--muted)] mt-1">
                        iterations {mc.iterations} · seed {mc.seed} ·
                        reproducer <code>{mc.reproducer_hash.slice(0, 12)}…</code>
                      </div>
                      <div className="mt-2 text-sm grid grid-cols-5 gap-2">
                        <div><div className="text-xs text-[var(--muted)]">P10</div>{mc.p10.toFixed(2)}</div>
                        <div><div className="text-xs text-[var(--muted)]">P25</div>{mc.p25.toFixed(2)}</div>
                        <div><div className="text-xs text-[var(--muted)]">P50</div>{mc.p50.toFixed(2)}</div>
                        <div><div className="text-xs text-[var(--muted)]">P75</div>{mc.p75.toFixed(2)}</div>
                        <div><div className="text-xs text-[var(--muted)]">P90</div>{mc.p90.toFixed(2)}</div>
                      </div>
                      {mc.narration && (
                        <p className="mt-2 text-sm">{mc.narration.text}</p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Forecasts */}
            {analysis.forecasts.length > 0 && (
              <section data-testid="analyze-forecasts-list">
                <h3 className="text-sm tracking-[0.16em] uppercase text-[var(--muted)]">Forecasts</h3>
                <div className="mt-3 space-y-3">
                  {analysis.forecasts.map((fc, i) => (
                    <div
                      key={fc.id}
                      className="border border-[var(--rule)] rounded p-4"
                      data-testid={`analyze-forecast-${i}`}
                    >
                      <div className="font-medium">{fc.value_column} vs {fc.date_column}</div>
                      <div className="text-xs text-[var(--muted)] mt-1">
                        {fc.method} · R² {fc.r2.toFixed(3)} · {fc.n_historical} pairs ·
                        horizon {fc.horizon_periods}
                      </div>
                      <ul className="mt-2 text-sm grid grid-cols-4 gap-x-3 gap-y-1">
                        {fc.projections.slice(0, 8).map((p, pi) => (
                          <li key={pi}>
                            <div className="text-xs text-[var(--muted)]">+{p.period_index}</div>
                            {p.value.toFixed(2)}
                          </li>
                        ))}
                      </ul>
                      {fc.narration && <p className="mt-2 text-sm">{fc.narration.text}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Anomalies */}
            {analysis.anomalies.length > 0 && (
              <section data-testid="analyze-anomalies-list">
                <h3 className="text-sm tracking-[0.16em] uppercase text-[var(--muted)]">Anomalies</h3>
                <ul className="mt-3 space-y-2 text-sm">
                  {analysis.anomalies.map((a, i) => (
                    <li
                      key={i}
                      className="border-l-2 border-[color:var(--oxblood)] pl-3"
                      data-testid={`analyze-anomaly-${i}`}
                    >
                      <div className="text-xs text-[var(--muted)]">
                        {a.sheet} · {a.column} · row {a.row_index}
                      </div>
                      {a.rationale}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
