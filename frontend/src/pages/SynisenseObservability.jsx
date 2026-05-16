/**
 * Synisense Observability — admin-only dashboard.
 *
 * Phase E Sub-task D (2026-05-16). KPI tiles + tables. No fancy
 * charts — Bank QA wants clarity, not visualization.
 *
 * Backed by `GET /api/admin/synisense/observability?window_days=...`.
 */
import React, { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, ShieldCheck } from "lucide-react";


const WINDOWS = [7, 30, 90];


export default function SynisenseObservability() {
  const [windowDays, setWindowDays] = useState(7);
  const [snap, setSnap] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (days) => {
    setBusy(true); setError(null);
    try {
      const { data } = await api.get(
        `/admin/synisense/observability?window_days=${days}`,
      );
      setSnap(data);
    } catch (e) {
      setError(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(windowDays); }, [load, windowDays]);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl space-y-6 p-6" data-testid="synisense-observability-page">
        <header className="space-y-1">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
            <ShieldCheck className="h-4 w-4 text-emerald-600" /> Admin · Synisense
          </div>
          <h1 className="text-3xl font-semibold text-slate-900">Synisense Observability</h1>
          <p className="text-sm text-slate-600">
            Aggregate Shield invokes, refusal rates, and audit anomalies across all consumers.
          </p>
        </header>

        <div className="flex flex-wrap items-center gap-2">
          {WINDOWS.map((w) => (
            <Button
              key={w}
              variant={w === windowDays ? "default" : "outline"}
              size="sm"
              onClick={() => setWindowDays(w)}
              data-testid={`syn-obs-window-${w}`}
            >Last {w} days</Button>
          ))}
          <Button
            variant="ghost" size="sm" onClick={() => load(windowDays)}
            disabled={busy}
            data-testid="syn-obs-reload"
          >{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Reload"}</Button>
          {snap && (
            <span className="ml-auto text-xs text-slate-500">
              as of {new Date(snap.as_of).toLocaleString()}
            </span>
          )}
        </div>

        {error && (
          <div
            data-testid="syn-obs-error"
            className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700"
          >{error}</div>
        )}

        {snap && (
          <>
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="syn-obs-kpis">
              <Kpi label="Total invokes" value={snap.total_invokes} />
              <Kpi label="Consumers" value={(snap.per_consumer || []).length} />
              <Kpi
                label="Re-id partial rate"
                value={`${(snap.reidentification_partial_rate * 100).toFixed(2)}%`}
              />
              <Kpi
                label="Guardrail blocks"
                value={Object.values(snap.guardrail_block_counts || {}).reduce((a, b) => a + b, 0)}
              />
            </section>

            <Table
              testId="syn-obs-consumers"
              title="Per-consumer breakdown"
              cols={[
                "Consumer", "Invokes", "Success", "Refused", "Unavailable",
                "Exp. reduction", "Dilution",
              ]}
              rows={(snap.per_consumer || []).map((c) => [
                c.consumer_id, c.total_invokes,
                pct(c.success_rate), pct(c.refusal_rate), pct(c.unavailable_rate),
                c.average_exposure_reduction != null ? `${c.average_exposure_reduction}%` : "—",
                c.average_dilution != null ? `${c.average_dilution}%` : "—",
              ])}
            />

            <Table
              testId="syn-obs-purposes"
              title="Top 10 purposes"
              cols={["Purpose", "Count"]}
              rows={(snap.top_purposes || []).map((p) => [p.purpose, p.count])}
            />

            <Table
              testId="syn-obs-refusal-reasons"
              title="Solva refusal reasons (Phase D path)"
              cols={["Reason", "Count"]}
              rows={Object.entries(snap.solva_refusal_reasons || {}).map(([k, v]) => [k, v])}
              emptyMessage="No refused sessions in this window."
            />
          </>
        )}
      </div>
    </AppShell>
  );
}


function Kpi({ label, value }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}


function pct(v) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}


function Table({ title, cols, rows, testId, emptyMessage }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white shadow-sm">
      <h2 className="border-b border-slate-200 px-4 py-2 text-sm font-semibold text-slate-800">{title}</h2>
      {rows.length === 0 ? (
        <p className="px-4 py-3 text-sm text-slate-500" data-testid={`${testId}-empty`}>
          {emptyMessage || "No data."}
        </p>
      ) : (
        <table className="w-full text-sm" data-testid={testId}>
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/50 text-left text-xs uppercase tracking-wide text-slate-500">
              {cols.map((c) => <th key={c} className="px-4 py-2">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-slate-50">
                {r.map((cell, j) => (
                  <td key={j} className="px-4 py-2 text-slate-700">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
