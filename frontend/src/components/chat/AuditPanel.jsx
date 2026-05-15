/**
 * AuditPanel — per-message collapsible expander rendering the
 * natural-language Synisense audit data for one assistant turn.
 *
 * Phase C (2026-05-13) Bank-QA demo centrepiece. Every string shown
 * here MUST be executive-readable — no raw enum values, no field
 * names. The backend `/api/chats/{cid}/audit-panel?message_id={mid}`
 * endpoint composes the prose; this component renders it.
 */
import React, { useState, useCallback } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Loader2, ShieldCheck, ChevronDown, ChevronUp } from "lucide-react";

export default function AuditPanel({ chatId, messageId }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const toggle = useCallback(async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (data || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const { data: panel } = await api.get(
        `/chats/${chatId}/audit-panel`,
        { params: { message_id: messageId } }
      );
      setData(panel);
    } catch (e) {
      setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally {
      setBusy(false);
    }
  }, [open, data, busy, chatId, messageId]);

  return (
    <div
      data-testid={`audit-panel-${messageId}`}
      className="mt-2 rounded-md border border-slate-200/70 bg-slate-50/50 text-sm"
    >
      <button
        type="button"
        onClick={toggle}
        data-testid={`audit-panel-toggle-${messageId}`}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-slate-600 hover:bg-slate-100/60"
      >
        <span className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          <span className="font-medium">Synisense audit</span>
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
          {data && (
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
                    {data.references?.purpose || "—"}
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
          )}
        </div>
      )}
    </div>
  );
}
