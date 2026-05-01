/**
 * TrustPanel — Phase 7 / Advisory 7.
 *
 * Quiet system-utility panel anchored off the top-right user menu. Five
 * sections, read-only:
 *
 *   1. Audit log (filterable + ZIP export)
 *   2. De-identification status
 *   3. Inbound email
 *   4. Connected models
 *   5. Sensitivity at a glance
 *
 * Desktop: Sheet from the right, ~520px. Mobile: full-screen sheet from
 * the bottom. Cream surface, akki-overline headers, no oxblood emphasis.
 * Loading copy is editorial ("Reading your trust ledger…"). No spinners.
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  Copy as CopyIcon, Download, Filter,
} from "lucide-react";
import useIsMobile from "@/hooks/useIsMobile";

const BUCKET_LABELS = {
  public: "Public", internal: "Internal",
  confidential: "Confidential", restricted: "Restricted",
};

function Overline({ children, className = "" }) {
  return (
    <p className={`akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] ${className}`}>
      {children}
    </p>
  );
}

function formatStamp(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  } catch {
    return iso;
  }
}

function SectionHeader({ label, subtitle }) {
  return (
    <div className="mb-3">
      <Overline>{label}</Overline>
      {subtitle ? (
        <p className="text-[12px] text-[var(--muted)] mt-1 max-w-[56ch]">{subtitle}</p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 1 — Audit log
// ---------------------------------------------------------------------------
function AuditLogSection({ data, refreshRecent }) {
  const [filterAction, setFilterAction] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [rows, setRows] = useState(data?.recent || []);
  const [filtered, setFiltered] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setRows(data?.recent || []);
    setFiltered(false);
  }, [data]);

  const applyFilter = useCallback(async () => {
    setFetching(true);
    try {
      const qp = new URLSearchParams();
      qp.set("limit", "25");
      if (filterAction && filterAction !== "__all__") qp.set("action", filterAction);
      if (since) qp.set("since", new Date(since).toISOString());
      if (until) qp.set("until", new Date(until).toISOString());
      const { data: resp } = await api.get(`/me/governance/audit?${qp.toString()}`);
      setRows(resp.items || []);
      setFiltered(true);
    } catch {
      toast.error("Couldn't load filtered audit entries.");
    } finally {
      setFetching(false);
    }
  }, [filterAction, since, until]);

  const clearFilter = useCallback(() => {
    setFilterAction("");
    setSince("");
    setUntil("");
    setRows(data?.recent || []);
    setFiltered(false);
    refreshRecent?.();
  }, [data, refreshRecent]);

  const exportZip = useCallback(async () => {
    setExporting(true);
    try {
      const body = {};
      if (filterAction && filterAction !== "__all__") body.action = filterAction;
      if (since) body.since = new Date(since).toISOString();
      if (until) body.until = new Date(until).toISOString();
      const resp = await api.post("/me/governance/audit/export", body, {
        responseType: "blob",
      });
      const blob = resp.data instanceof Blob ? resp.data : new Blob([resp.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `akki-audit-${new Date().toISOString().replace(/[:.-]/g, "").slice(0, 15)}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.message("Export ready.");
    } catch {
      toast.error("Export failed.");
    } finally {
      setExporting(false);
    }
  }, [filterAction, since, until]);

  return (
    <section data-testid="trust-section-audit" className="mb-8">
      <SectionHeader
        label="AUDIT LOG"
        subtitle="Every action AKKI takes for you, with timestamps and signatures."
      />
      <div className="flex items-center justify-between mb-3">
        <p className="text-[13px] text-[var(--ink)]">
          <span className="akki-serif text-[18px] mr-1">{data?.total_entries ?? 0}</span>
          <span className="text-[var(--muted)]">total entries</span>
        </p>
      </div>

      {/* Filter + export bar */}
      <div className="border border-[var(--border,#e2d9cf)] bg-white p-3 mb-3 flex flex-col gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={12} className="text-[var(--muted)]" />
          <Select value={filterAction || "__all__"} onValueChange={setFilterAction}>
            <SelectTrigger className="h-8 min-w-[180px] text-[12px]" data-testid="trust-audit-action-filter">
              <SelectValue placeholder="All actions" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All actions</SelectItem>
              {(data?.available_actions || []).map((a) => (
                <SelectItem key={a} value={a}>{a}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="date"
            value={since}
            onChange={(e) => setSince(e.target.value)}
            className="h-8 text-[12px] w-auto"
            placeholder="Since"
            aria-label="Since"
            data-testid="trust-audit-since"
          />
          <Input
            type="date"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
            className="h-8 text-[12px] w-auto"
            placeholder="Until"
            aria-label="Until"
            data-testid="trust-audit-until"
          />
          <button
            type="button"
            onClick={applyFilter}
            disabled={fetching}
            className="akki-overline tracking-[0.16em] text-[10.5px] text-[var(--ink)] border border-[var(--border,#e2d9cf)] px-3 py-1.5 hover:bg-[var(--cream-deep)] disabled:opacity-50"
            data-testid="trust-audit-apply"
          >
            {fetching ? "READING…" : "APPLY"}
          </button>
          {filtered && (
            <button
              type="button"
              onClick={clearFilter}
              className="text-[11px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
              data-testid="trust-audit-clear"
            >
              clear
            </button>
          )}
          <div className="ml-auto">
            <button
              type="button"
              onClick={exportZip}
              disabled={exporting}
              className="akki-overline tracking-[0.16em] text-[10.5px] text-white bg-[var(--ink)] hover:bg-[var(--ink)]/90 px-3 py-1.5 inline-flex items-center gap-1 disabled:opacity-50"
              data-testid="trust-audit-export"
            >
              <Download size={11} /> {exporting ? "PREPARING…" : "EXPORT ZIP"}
            </button>
          </div>
        </div>
      </div>

      {/* Rows */}
      <div className="border border-[var(--border,#e2d9cf)] bg-white divide-y divide-[var(--border,#e2d9cf)]/60">
        {rows.length === 0 ? (
          <p className="text-[12px] text-[var(--muted)] p-3">No audit entries match the filter.</p>
        ) : (
          rows.slice(0, 25).map((r) => (
            <div key={r.id || r.timestamp + r.action} className="px-3 py-2 text-[12.5px]" data-testid="trust-audit-row">
              <div className="flex items-baseline justify-between gap-2">
                <span className="akki-overline text-[9.5px] tracking-[0.18em] text-[var(--muted)]">
                  {formatStamp(r.timestamp)}
                </span>
                {r.context_name ? (
                  <span className="text-[11px] text-[var(--muted)]/80 truncate">{r.context_name}</span>
                ) : null}
              </div>
              <p className="text-[var(--ink)] font-mono text-[12px] truncate">
                {r.action}
              </p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 2 — De-identification
// ---------------------------------------------------------------------------
function DeidentSection({ shielding, sensitivity }) {
  return (
    <section data-testid="trust-section-deident" className="mb-8">
      <SectionHeader
        label="DE-IDENTIFICATION"
        subtitle="Identifying data (emails, names, account numbers) is masked from the model before any LLM call."
      />
      <div className="flex items-center gap-3 mb-3">
        <span
          className="akki-overline tracking-[0.16em] text-[10.5px] bg-[var(--cream-deep)] text-[var(--ink)] px-2.5 py-1 border border-[var(--border,#e2d9cf)]"
          data-testid="trust-shielding-chip"
        >
          SHIELDED · {shielding?.mode?.toUpperCase() || "REGEX"}
        </span>
        <span className="text-[11px] text-[var(--muted)] italic">
          Live status badge ships when the Synisense service replaces the local masker.
        </span>
      </div>
      <div className="text-[12.5px] text-[var(--ink)] flex items-center gap-2">
        <span className="text-[var(--muted)]">Auto-classify on save:</span>
        <span className="akki-overline text-[10px] tracking-[0.18em] text-[var(--ink)]">
          {sensitivity?.auto_classify ? "ON" : "OFF"}
        </span>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 3 — Inbound email
// ---------------------------------------------------------------------------
function InboundSection({ inbound }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    if (!inbound?.address) return;
    try {
      await navigator.clipboard.writeText(inbound.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.message("Couldn't copy — select manually.");
    }
  };
  return (
    <section data-testid="trust-section-inbound" className="mb-8">
      <SectionHeader
        label="INBOUND EMAIL"
        subtitle="Forward anything to AKKI. It files automatically."
      />
      {inbound?.address ? (
        <div
          className="flex items-center gap-2 bg-[var(--cream-deep)] border border-[var(--border,#e2d9cf)] px-3 py-2"
          data-testid="trust-inbound-address"
        >
          <code className="text-[13px] font-mono text-[var(--ink)] break-all flex-1">
            {inbound.address}
          </code>
          <button
            type="button"
            onClick={onCopy}
            className="text-[11px] akki-overline tracking-[0.16em] text-[var(--muted)] hover:text-[var(--ink)] flex items-center gap-1"
            data-testid="trust-inbound-copy"
          >
            <CopyIcon size={12} />
            {copied ? "COPIED" : "COPY"}
          </button>
        </div>
      ) : (
        <p className="text-[12px] text-[var(--muted)]">No inbound address yet.</p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 4 — Connected models
// ---------------------------------------------------------------------------
function ModelsSection({ models }) {
  return (
    <section data-testid="trust-section-models" className="mb-8">
      <SectionHeader
        label="CONNECTED MODELS"
        subtitle="AKKI uses these models. Each call is shielded before transmission."
      />
      <div className="border border-[var(--border,#e2d9cf)] bg-white divide-y divide-[var(--border,#e2d9cf)]/60">
        {(models || []).map((m) => (
          <div key={m.id} className="px-3 py-2.5" data-testid={`trust-model-${m.id}`}>
            <div className="flex items-baseline justify-between gap-2">
              <p className="akki-serif text-[14px] text-[var(--ink)]">{m.label}</p>
              <p className="akki-overline text-[9.5px] tracking-[0.18em] text-[var(--muted)]">
                {m.provider?.toUpperCase()}
              </p>
            </div>
            {m.used_in && m.used_in.length > 0 && (
              <p className="text-[11.5px] text-[var(--muted)] mt-0.5">
                Used in · {m.used_in.join(" · ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Section 5 — Sensitivity at a glance
// ---------------------------------------------------------------------------
function SensitivitySection({ sensitivity }) {
  const breakdown = sensitivity?.classification_breakdown || {};
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  return (
    <section data-testid="trust-section-sensitivity" className="mb-4">
      <SectionHeader
        label="SENSITIVITY"
        subtitle="Every artefact you've created, classified."
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
        {Object.entries(BUCKET_LABELS).map(([k, lbl]) => (
          <div
            key={k}
            className="bg-white border border-[var(--border,#e2d9cf)] p-3"
            data-testid={`trust-sensitivity-${k}`}
          >
            <p className="akki-serif text-[22px] text-[var(--ink)]">{breakdown[k] || 0}</p>
            <p className="akki-overline text-[9.5px] tracking-[0.18em] text-[var(--muted)] mt-0.5">{lbl}</p>
          </div>
        ))}
      </div>
      {total === 0 ? (
        <p className="text-[11.5px] text-[var(--muted)] italic">
          No artefacts classified yet. Counts populate as you save decks, reports, and briefings.
        </p>
      ) : (
        <p className="text-[11.5px] text-[var(--muted)]">
          {sensitivity?.last_classified_at ? `Last classified · ${formatStamp(sensitivity.last_classified_at)}` : null}
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------
export default function TrustPanel({ open, onOpenChange }) {
  const isMobile = useIsMobile();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const { data: resp } = await api.get("/me/governance");
      setData(resp);
    } catch {
      setData(null);
      toast.error("Couldn't load trust panel.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) fetchData();
  }, [open, fetchData]);

  const refreshRecent = useCallback(() => {
    // Re-fetch just the panel. Cheap.
    fetchData();
  }, [fetchData]);

  const side = isMobile ? "bottom" : "right";
  const widthCls = isMobile ? "h-[92vh] max-h-[92vh]" : "w-[520px] max-w-[92vw]";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={side}
        className={`bg-[var(--cream)] overflow-y-auto p-0 ${widthCls}`}
        data-testid="trust-panel"
      >
        <div className="sticky top-0 bg-[var(--cream)] z-10 border-b border-[var(--border,#e2d9cf)] px-5 py-4">
          <SheetHeader>
            <SheetTitle className="akki-serif text-[20px] font-normal text-[var(--ink)]">
              Trust
            </SheetTitle>
          </SheetHeader>
          <p className="text-[12px] text-[var(--muted)] mt-1">
            Audit, shielding, and the models AKKI uses for you.
          </p>
        </div>

        <div className="px-5 py-5">
          {loading && !data ? (
            <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse">
              Reading your trust ledger…
            </p>
          ) : !data ? (
            <p className="text-[13px] text-[var(--muted)]">
              Couldn&apos;t load the trust panel. Please try again.
            </p>
          ) : (
            <>
              <AuditLogSection data={data.audit_log} refreshRecent={refreshRecent} />
              <DeidentSection shielding={data.shielding} sensitivity={data.sensitivity} />
              <InboundSection inbound={data.inbound} />
              <ModelsSection models={data.connected_models} />
              <SensitivitySection sensitivity={data.sensitivity} />
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
