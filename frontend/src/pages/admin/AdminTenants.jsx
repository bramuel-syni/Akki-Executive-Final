/**
 * Phase W (2026-02 fork-resume) — Multi-tenant org list view (superadmin).
 *
 * Read-only page at `/app/admin/tenants` that lists every context in
 * the system with member-count, doc-count, last-activity. Drill-down
 * drawer per row surfaces the memberships (account-id + role) and
 * total counts — never doc bodies or chat content.
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Building2, Loader2, RefreshCw, Search, X, Users, FileText, Clock,
} from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const PAGE_LIMIT = 50;

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function TypePill({ value }) {
  const label = (value || "—").replace(/_/g, " ");
  return (
    <span className="inline-flex items-center text-[10.5px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm bg-[var(--ned-purple)]/10 text-[var(--ned-purple)] border border-[var(--ned-purple)]/20">
      {label}
    </span>
  );
}

export default function AdminTenants() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [drillCid, setDrillCid] = useState(null);
  const [drill, setDrill] = useState(null);
  const [drillLoading, setDrillLoading] = useState(false);

  const queryString = useMemo(() => {
    const sp = new URLSearchParams({ limit: String(PAGE_LIMIT) });
    if (q) sp.set("q", q);
    if (type) sp.set("type", type);
    return sp.toString();
  }, [q, type]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/tenants?${queryString}`);
      setItems(data?.items || []);
      setTotal(data?.total || 0);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  useEffect(() => { load(); }, [load]);

  const openDrill = useCallback(async (cid) => {
    setDrillCid(cid);
    setDrillLoading(true);
    try {
      const { data } = await api.get(`/admin/tenants/${cid}`);
      setDrill(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
      setDrill(null);
    } finally {
      setDrillLoading(false);
    }
  }, []);

  const closeDrill = useCallback(() => {
    setDrillCid(null);
    setDrill(null);
  }, []);

  return (
    <AppShell>
      <div
        className="min-h-screen bg-[var(--cream)] py-12 px-6"
        data-testid="admin-tenants-page"
      >
        <div className="akki-w-narrow">
          <header className="mb-8 flex items-start justify-between gap-4">
            <div>
              <p className="akki-overline mb-2">Control room · superadmin</p>
              <h1 className="akki-greeting mb-2">Tenants & orgs.</h1>
              <p className="akki-meta max-w-xl">
                Read-only view of every context across the platform — members,
                documents, and last activity. Drill-down shows the membership
                roster. No content, no chat, no doc bodies.
              </p>
            </div>
            <button
              type="button"
              onClick={load}
              className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
              data-testid="tenants-refresh-btn"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </header>

          {/* Filter strip */}
          <div className="flex items-center gap-3 mb-6" data-testid="tenants-filter-strip">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
              <Input
                placeholder="Search by name…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="pl-9 h-9 text-[13px]"
                data-testid="tenants-search-input"
              />
            </div>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="h-9 px-3 text-[12.5px] bg-white border border-[var(--rule)] rounded-sm text-[var(--ink)] focus:outline-none focus:border-[var(--ned-purple)]"
              data-testid="tenants-type-filter"
            >
              <option value="">All types</option>
              <option value="ned_personal">NED — Personal</option>
              <option value="ned_sponsored">NED — Sponsored</option>
              <option value="executive_personal">Executive — Personal</option>
              <option value="executive_enterprise">Executive — Enterprise</option>
            </select>
            <span className="text-[11px] text-[var(--muted)]" data-testid="tenants-total">
              {total} {total === 1 ? "tenant" : "tenants"}
            </span>
          </div>

          {/* Table */}
          <div className="bg-white border border-[var(--rule)] rounded-sm overflow-hidden">
            <table className="w-full text-[12.5px]" data-testid="tenants-table">
              <thead className="bg-[var(--paper)] text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                <tr className="border-b border-[var(--rule)]">
                  <th className="text-left px-4 py-2 font-normal">Tenant</th>
                  <th className="text-left px-4 py-2 font-normal">Type</th>
                  <th className="text-left px-4 py-2 font-normal">Members</th>
                  <th className="text-left px-4 py-2 font-normal">Docs</th>
                  <th className="text-left px-4 py-2 font-normal">Last activity</th>
                  <th className="text-left px-4 py-2 font-normal">Created</th>
                </tr>
              </thead>
              <tbody>
                {loading && items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-[var(--muted)]">
                      <Loader2 className="w-4 h-4 animate-spin inline-block mr-2" />
                      Loading…
                    </td>
                  </tr>
                )}
                {!loading && items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-[var(--muted)]" data-testid="tenants-empty">
                      No tenants match.
                    </td>
                  </tr>
                )}
                {items.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => openDrill(t.id)}
                    className="border-b border-[var(--rule)] last:border-b-0 cursor-pointer hover:bg-[var(--paper)]/40 transition-colors"
                    data-testid={`tenant-row-${t.id}`}
                  >
                    <td className="px-4 py-3 text-[var(--ink)]" data-testid={`tenant-name-${t.id}`}>
                      <span className="inline-flex items-center gap-2">
                        <Building2 className="w-3.5 h-3.5 text-[var(--muted)]" />
                        {t.name}
                      </span>
                    </td>
                    <td className="px-4 py-3"><TypePill value={t.type} /></td>
                    <td className="px-4 py-3 text-[var(--ink)]" data-testid={`tenant-members-${t.id}`}>
                      {t.member_count}
                    </td>
                    <td className="px-4 py-3 text-[var(--ink)]" data-testid={`tenant-docs-${t.id}`}>
                      {t.doc_count}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)] text-[11.5px]">
                      {fmtDate(t.last_activity)}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)] text-[11.5px]">
                      {fmtDate(t.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Drilldown drawer (Dialog) */}
        <Dialog open={!!drillCid} onOpenChange={(open) => !open && closeDrill()}>
          <DialogContent className="max-w-2xl" data-testid="tenant-drill-dialog">
            <DialogHeader>
              <DialogTitle data-testid="tenant-drill-title">
                {drill?.name || "Tenant detail"}
              </DialogTitle>
            </DialogHeader>
            {drillLoading && (
              <div className="py-12 text-center text-[var(--muted)]">
                <Loader2 className="w-4 h-4 animate-spin inline-block mr-2" /> Loading…
              </div>
            )}
            {!drillLoading && drill && (
              <div className="space-y-5" data-testid="tenant-drill-body">
                <div className="flex items-center gap-3">
                  <TypePill value={drill.type} />
                  <span className="text-[11px] text-[var(--muted)] uppercase tracking-[0.14em]">
                    Status · {drill.status || "active"}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-[var(--paper)] border border-[var(--rule)] rounded-sm p-3">
                    <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1 flex items-center gap-1">
                      <Users className="w-3 h-3" /> Members
                    </p>
                    <p className="text-[22px] text-[var(--ink)]" data-testid="tenant-drill-members">
                      {drill.member_count}
                    </p>
                  </div>
                  <div className="bg-[var(--paper)] border border-[var(--rule)] rounded-sm p-3">
                    <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1 flex items-center gap-1">
                      <FileText className="w-3 h-3" /> Docs
                    </p>
                    <p className="text-[22px] text-[var(--ink)]" data-testid="tenant-drill-docs">
                      {drill.doc_count}
                    </p>
                  </div>
                  <div className="bg-[var(--paper)] border border-[var(--rule)] rounded-sm p-3">
                    <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> Last activity
                    </p>
                    <p className="text-[11.5px] text-[var(--ink)] leading-tight" data-testid="tenant-drill-last-activity">
                      {fmtDate(drill.last_activity)}
                    </p>
                  </div>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] mb-2">
                    Memberships ({(drill.memberships || []).length})
                  </p>
                  <div className="bg-white border border-[var(--rule)] rounded-sm max-h-72 overflow-y-auto" data-testid="tenant-drill-memberships">
                    {(drill.memberships || []).length === 0 ? (
                      <p className="px-3 py-6 text-center text-[var(--muted)] text-[12px]">No memberships.</p>
                    ) : (
                      <table className="w-full text-[12px]">
                        <thead className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] bg-[var(--paper)]">
                          <tr className="border-b border-[var(--rule)]">
                            <th className="text-left px-3 py-1.5 font-normal">Account ID</th>
                            <th className="text-left px-3 py-1.5 font-normal">Role</th>
                            <th className="text-left px-3 py-1.5 font-normal">Created</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(drill.memberships || []).map((m) => (
                            <tr key={m.id} className="border-b border-[var(--rule)] last:border-b-0">
                              <td className="px-3 py-1.5 font-mono text-[11px] text-[var(--ink)]">{m.account_id}</td>
                              <td className="px-3 py-1.5 text-[var(--muted)]">{m.role || "—"}</td>
                              <td className="px-3 py-1.5 text-[var(--muted)] text-[11px]">{fmtDate(m.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
                <p className="text-[10.5px] text-[var(--muted)] italic">
                  Telemetry only — surface, count, when. We never show what users typed.
                </p>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
