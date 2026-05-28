/**
 * AA.followup.4 (2026-02 fork-resume) — Extraction Activity admin view.
 *
 * Superadmin-only read-only page at `/app/admin/extractions` that lists
 * recent LLM-extraction runs from `db.extractions_log`, joined with
 * `documents` (title + category) and `tasks_initiatives` (per-doc
 * persisted count). Helps the operator audit per-doc extraction
 * quality without diving into raw collections.
 *
 * Strict read-only — no mutations.
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Sparkles, Loader2, RefreshCw, CheckCircle2, AlertTriangle, XCircle, X,
} from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";

const PAGE_LIMIT = 50;

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function OutcomeBadge({ outcome, count, failures }) {
  if (outcome === "all_passed") {
    return (
      <span
        className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm bg-emerald-50 text-emerald-700 border border-emerald-200"
        data-testid="extraction-outcome-all_passed"
      >
        <CheckCircle2 className="w-3 h-3" /> {count} passed
      </span>
    );
  }
  if (outcome === "partial") {
    return (
      <span
        className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm bg-amber-50 text-amber-700 border border-amber-200"
        data-testid="extraction-outcome-partial"
      >
        <AlertTriangle className="w-3 h-3" /> {count}/{count + failures} partial
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm bg-rose-50 text-rose-700 border border-rose-200"
      data-testid="extraction-outcome-all_failed"
    >
      <XCircle className="w-3 h-3" /> {failures} failed
    </span>
  );
}

export default function ExtractionsActivity() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tenantId = searchParams.get("tenant_id") || "";  // Phase W.followup.1

  // Phase W.followup.1 hotfix (2026-02 fork-resume) — clear tenant scope.
  const clearTenantFilter = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    next.delete("tenant_id");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [kindFilter, setKindFilter] = useState("");

  const queryString = useMemo(() => {
    const sp = new URLSearchParams({ limit: String(PAGE_LIMIT) });
    if (kindFilter) sp.set("kind", kindFilter);
    if (tenantId)   sp.set("tenant_id", tenantId);
    return sp.toString();
  }, [kindFilter, tenantId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/extractions?${queryString}`);
      setItems(data?.items || []);
      setTotal(data?.total || 0);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  useEffect(() => { load(); }, [load]);

  return (
    <AppShell>
      <div
        className="min-h-screen bg-[var(--cream)] py-12 px-6"
        data-testid="admin-extractions-page"
      >
        <div className="akki-w-narrow">
          <header className="mb-8 flex items-start justify-between gap-4">
            <div>
              <p className="akki-overline mb-2">Control room · superadmin</p>
              <h1 className="akki-greeting mb-2">Extraction activity.</h1>
              <p className="akki-meta max-w-xl">
                Recent LLM extraction runs across every account. Read-only — surfaces
                the per-doc validation outcome and how many tasks each doc actually
                produced.
              </p>
            </div>
            <button
              type="button"
              onClick={load}
              className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
              data-testid="extractions-refresh-btn"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </header>

          {/* Filter strip */}
          <div className="flex items-center gap-2 mb-6" data-testid="extractions-filter-strip">
            {tenantId && (
              <span
                className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] px-3 py-1 rounded-sm bg-[#6B46C1]/10 text-[#6B46C1] border border-[#6B46C1]/30 mr-2"
                data-testid="extractions-tenant-scope-pill"
              >
                Tenant: {tenantId.slice(0, 8)}…
                <button
                  type="button"
                  onClick={clearTenantFilter}
                  className="ml-0.5 -mr-1 hover:bg-[#6B46C1]/15 rounded-sm p-0.5 transition-colors"
                  data-testid="extractions-tenant-scope-clear-btn"
                  aria-label="Clear tenant filter"
                  title="Clear tenant filter"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}
            {[
              { id: "",      label: "All"   },
              { id: "tasks", label: "Tasks" },
              { id: "goals", label: "Goals" },
            ].map((opt) => (
              <button
                key={opt.id || "all"}
                type="button"
                onClick={() => setKindFilter(opt.id)}
                className={`text-[11px] uppercase tracking-[0.14em] px-3 py-1 rounded-sm border transition-colors ${
                  kindFilter === opt.id
                    ? "bg-[var(--ned-purple)]/10 text-[var(--ned-purple)] border-[var(--ned-purple)]/20"
                    : "bg-white text-[var(--muted)] border-[var(--rule)] hover:border-[var(--ned-purple)]/30"
                }`}
                data-testid={`extractions-filter-${opt.id || "all"}`}
              >
                {opt.label}
              </button>
            ))}
            <span className="ml-3 text-[11px] text-[var(--muted)]" data-testid="extractions-total">
              {total} {total === 1 ? "run" : "runs"} total
            </span>
          </div>

          {/* Table */}
          <div className="bg-white border border-[var(--rule)] rounded-sm overflow-hidden">
            <table className="w-full text-[12.5px]" data-testid="extractions-table">
              <thead className="bg-[var(--paper)] text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                <tr className="border-b border-[var(--rule)]">
                  <th className="text-left px-4 py-2 font-normal">Document</th>
                  <th className="text-left px-4 py-2 font-normal">Category</th>
                  <th className="text-left px-4 py-2 font-normal">Kind</th>
                  <th className="text-left px-4 py-2 font-normal">Outcome</th>
                  <th className="text-left px-4 py-2 font-normal">Tasks live</th>
                  <th className="text-left px-4 py-2 font-normal">Model</th>
                  <th className="text-left px-4 py-2 font-normal">When</th>
                </tr>
              </thead>
              <tbody>
                {loading && items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-[var(--muted)]">
                      <Loader2 className="w-4 h-4 animate-spin inline-block mr-2" />
                      Loading…
                    </td>
                  </tr>
                )}
                {!loading && items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-[var(--muted)]" data-testid="extractions-empty">
                      No extraction runs yet.
                    </td>
                  </tr>
                )}
                {items.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b border-[var(--rule)] last:border-b-0 hover:bg-[var(--paper)]/40 transition-colors"
                    data-testid={`extraction-row-${row.id}`}
                  >
                    <td className="px-4 py-3">
                      <span className="text-[var(--ink)]" data-testid={`extraction-doc-title-${row.id}`}>
                        {row.document_title || <em className="text-[var(--muted)]">(deleted document)</em>}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]" data-testid={`extraction-doc-category-${row.id}`}>
                      {row.document_category || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-[10.5px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm bg-[var(--ned-purple)]/10 text-[var(--ned-purple)] border border-[var(--ned-purple)]/20">
                        <Sparkles className="w-3 h-3" /> {row.kind}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <OutcomeBadge
                        outcome={row.validation_outcome}
                        count={row.count}
                        failures={row.failures}
                      />
                    </td>
                    <td className="px-4 py-3 text-[var(--ink)]" data-testid={`extraction-tasks-persisted-${row.id}`}>
                      {row.tasks_persisted}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)] text-[11.5px]">
                      {row.model || "—"}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)] text-[11.5px]">
                      {fmtDate(row.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
