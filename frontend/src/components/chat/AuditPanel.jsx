/**
 * AuditPanel — per-message collapsible expander rendering the
 * natural-language Synisense audit data for one assistant turn.
 *
 * Phase C (2026-05-13) Bank-QA demo centrepiece. Every string shown
 * here MUST be executive-readable — no raw enum values, no field
 * names. The backend `/api/chats/{cid}/audit-panel?message_id={mid}`
 * endpoint composes the prose; this component renders it.
 *
 * Phase D (2026-05-13) — Privacy Provenance timeline mode added.
 * When `mode="timeline"` + `solvaContextId` + `solvaSessionId` are
 * passed, the panel fetches
 * `/api/contexts/{cid}/solva/v2/sessions/{sid}/audit-panel/timeline`
 * and renders a vertical step-chart of every governed LLM call in the
 * session. Used on the Solva session detail surface.
 */
import React, { useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Loader2, ShieldCheck, ChevronDown, ChevronUp, ArrowDown } from "lucide-react";

export default function AuditPanel({
  chatId,
  messageId,
  mode = "message",        // "message" (default) | "timeline"
  solvaContextId,
  solvaSessionId,
  defaultOpen = false,
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const isTimeline = mode === "timeline";
  const testId = isTimeline
    ? `audit-panel-timeline-${solvaSessionId || "unknown"}`
    : `audit-panel-${messageId}`;

  const fetchData = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      if (isTimeline) {
        const { data: tl } = await api.get(
          `/contexts/${solvaContextId}/solva/v2/sessions/${solvaSessionId}/audit-panel/timeline`,
        );
        setData(tl);
      } else {
        const { data: panel } = await api.get(
          `/chats/${chatId}/audit-panel`,
          { params: { message_id: messageId } },
        );
        setData(panel);
      }
    } catch (e) {
      setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally {
      setBusy(false);
    }
  }, [isTimeline, chatId, messageId, solvaContextId, solvaSessionId]);

  const toggle = useCallback(async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (data || busy) return;
    await fetchData();
  }, [open, data, busy, fetchData]);

  return (
    <div
      data-testid={testId}
      className="mt-2 rounded-md border border-slate-200/70 bg-slate-50/50 text-sm"
    >
      <button
        type="button"
        onClick={toggle}
        data-testid={`${testId}-toggle`}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-slate-600 hover:bg-slate-100/60"
      >
        <span className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          <span className="font-medium">
            {isTimeline ? "Privacy provenance" : "Synisense audit"}
          </span>
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>
      {open && (
        <div className="space-y-3 border-t border-slate-200/70 px-4 py-3 text-slate-700">
          {busy && (
            <div className="flex items-center gap-2 text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading audit…</span>
            </div>
          )}
          {err && (
            <p className="text-rose-600" data-testid="audit-panel-error">
              {err}
            </p>
          )}
          {data && isTimeline && (
            <TimelineBody data={data} />
          )}
          {data && !isTimeline && (
            <SingleMessageBody data={data} />
          )}
        </div>
      )}
    </div>
  );
}


function SingleMessageBody({ data }) {
  return (
    <>
      <p data-testid="audit-panel-shielding-prose">
        {data.shielding_prose}
      </p>
      <p data-testid="audit-panel-provider-prose">
        {data.provider_prose}
      </p>
      <div className="rounded-md bg-white/70 p-3">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
          How well was your data protected for this turn?
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-2xl font-semibold text-emerald-700">
              {data.scores?.exposure_reduction != null
                ? `${Math.round(data.scores.exposure_reduction)}%`
                : "—"}
            </div>
            <div className="text-xs text-slate-600">
              Exposure reduction —{" "}
              {data.scores?.exposure_reduction_label || "no data"}
            </div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-sky-700">
              {data.scores?.dilution != null
                ? `${Math.round(data.scores.dilution)}%`
                : "—"}
            </div>
            <div className="text-xs text-slate-600">
              Dilution — {data.scores?.dilution_label || "no data"}
            </div>
          </div>
        </div>
      </div>
      <div className="rounded-md bg-white/70 p-3 text-xs text-slate-600">
        <div className="mb-1 font-semibold uppercase tracking-wide text-slate-500">
          Audit references
        </div>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1">
          <dt className="text-slate-500">Purpose</dt>
          <dd className="font-mono">
            {data.references?.purpose_label || data.references?.purpose || "—"}
          </dd>
          <dt className="text-slate-500">Audit ID</dt>
          <dd className="break-all font-mono">
            {data.references?.audit_id || "—"}
          </dd>
          <dt className="text-slate-500">Trust receipt</dt>
          <dd className="break-all font-mono">
            {data.references?.trust_receipt_id || "—"}
          </dd>
        </dl>
      </div>
      <div className="rounded-md bg-white/70 p-3">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Protective layer for this turn
        </div>
        <p
          className="text-slate-700"
          data-testid="audit-panel-protective-prose"
        >
          {data.protective_layer_prose}
        </p>
      </div>
    </>
  );
}


function TimelineBody({ data }) {
  const steps = data?.steps || [];
  const agg = data?.aggregate || {};
  if (steps.length === 0) {
    return (
      <p className="text-slate-500" data-testid="audit-panel-timeline-empty">
        {agg.headline_prose || "No governed LLM calls in this session yet."}
      </p>
    );
  }
  // Group consecutive steps with the same purpose_label to render one
  // row per layer with a (×N) count when the same call repeats.
  const grouped = [];
  for (const s of steps) {
    const last = grouped[grouped.length - 1];
    if (last && last.purpose_label === s.purpose_label) {
      last.count += 1;
      last.exposure_reduction = avg([last.exposure_reduction, s.exposure_reduction]);
      last.dilution = avg([last.dilution, s.dilution]);
    } else {
      grouped.push({
        purpose_label: s.purpose_label,
        purpose_raw: s.purpose_raw,
        count: 1,
        exposure_reduction: s.exposure_reduction,
        dilution: s.dilution,
        llm_provider: s.llm_provider,
        llm_model: s.llm_model,
      });
    }
  }
  return (
    <div data-testid="audit-panel-timeline-body" className="space-y-2">
      {grouped.map((row, idx) => (
        <div
          key={idx}
          data-testid={`audit-panel-timeline-row-${idx}`}
          className="rounded-md bg-white/70 p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <div className="font-medium text-slate-800">
              {row.purpose_label}
              {row.count > 1 && (
                <span className="ml-2 text-xs text-slate-500">
                  ({row.count} calls)
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500">
              {row.llm_provider ? `${row.llm_provider} · ${row.llm_model}` : ""}
            </div>
          </div>
          <div className="mt-1 text-xs text-slate-600">
            {fmtPct(row.exposure_reduction)} shielded · {fmtPct(row.dilution)} diluted
          </div>
          {idx < grouped.length - 1 && (
            <div className="mt-1 flex justify-center text-slate-300">
              <ArrowDown className="h-3 w-3" />
            </div>
          )}
        </div>
      ))}
      <p
        data-testid="audit-panel-timeline-headline"
        className="pt-2 text-xs text-slate-600"
      >
        {agg.headline_prose}
      </p>
    </div>
  );
}


function avg(arr) {
  const vals = (arr || []).filter((v) => typeof v === "number");
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}


function fmtPct(v) {
  if (v == null) return "—";
  return `${Math.round(v)}%`;
}
