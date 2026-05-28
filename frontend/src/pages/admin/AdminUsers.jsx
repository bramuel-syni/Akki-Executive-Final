/**
 * Phase V (2026-05-27) — Admin user CRUD portal.
 *
 * Superadmin-only page at `/app/admin/users` that closes the W7
 * stock-take #1 gap. Features:
 *   - Paginated list (50/page) of all accounts across all orgs
 *   - Filters: cohort_tag, trial_status, role, status, free-text search
 *   - Create user (manual, NOT magic-link) — email, first_name,
 *     logo_name, role, cohort_tag, optional initial password
 *   - Suspend / Restore per row
 *   - Timeline drill-down per user (telemetry only — NO content)
 *   - CSV export of the filtered set
 *
 * Data-safety contract surfaced visibly in the timeline panel: the
 * drilldown says "Telemetry only — never your typed content" so the
 * superadmin knows what they're looking at.
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Users, UserPlus, Search, Download, Shield, ShieldOff,
  Activity, X, Loader2, RefreshCw,
} from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";

const PAGE_SIZE = 50;

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

export default function AdminUsers() {
  const [items,    setItems]    = useState([]);
  const [total,    setTotal]    = useState(0);
  const [page,     setPage]     = useState(1);
  const [loading,  setLoading]  = useState(false);

  // Filters
  const [q,            setQ]            = useState("");
  const [cohortTag,    setCohortTag]    = useState("");
  const [trialStatus,  setTrialStatus]  = useState("");
  const [roleFilter,   setRoleFilter]   = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Dialogs
  const [createOpen, setCreateOpen] = useState(false);
  const [timelineUser, setTimelineUser] = useState(null);

  const queryString = useMemo(() => {
    const sp = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (q)            sp.set("q", q);
    if (cohortTag)    sp.set("cohort_tag", cohortTag);
    if (trialStatus)  sp.set("trial_status", trialStatus);
    if (roleFilter)   sp.set("role", roleFilter);
    if (statusFilter) sp.set("status", statusFilter);
    return sp.toString();
  }, [page, q, cohortTag, trialStatus, roleFilter, statusFilter]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/admin/users?${queryString}`);
      setItems(data?.items || []);
      setTotal(data?.total || 0);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  useEffect(() => { load(); }, [load]);

  const onSuspend = async (u) => {
    if (!window.confirm(`Suspend ${u.email}? They'll be signed out and bounced from auth-gated routes.`)) return;
    try {
      await api.post(`/admin/users/${u.id}/suspend`);
      toast.success(`Suspended ${u.email}`);
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  const onRestore = async (u) => {
    try {
      await api.post(`/admin/users/${u.id}/restore`);
      toast.success(`Restored ${u.email}`);
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onExportCsv = async () => {
    try {
      const sp = new URLSearchParams();
      if (q)            sp.set("q", q);
      if (cohortTag)    sp.set("cohort_tag", cohortTag);
      if (trialStatus)  sp.set("trial_status", trialStatus);
      if (roleFilter)   sp.set("role", roleFilter);
      if (statusFilter) sp.set("status", statusFilter);
      const res = await api.get(`/admin/users/export.csv?${sp.toString()}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `akki-users-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Exported.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AppShell>
      <div className="px-8 py-6 max-w-7xl mx-auto" data-testid="admin-users-page">
        <header className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="akki-serif text-[28px] text-[var(--ink)] flex items-center gap-2" data-testid="admin-users-h1">
              <Users className="w-6 h-6 text-[var(--accent)]" strokeWidth={1.7} />
              Users
            </h1>
            <p className="akki-meta mt-1 text-[13px] text-[var(--muted)]">
              Manage all accounts across all orgs. Telemetry drill-down available; no content visible.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm" variant="outline"
              onClick={onExportCsv}
              data-testid="admin-users-export-csv"
              className="border-[var(--rule)]"
            >
              <Download className="w-3.5 h-3.5 mr-1.5" /> Export CSV
            </Button>
            <Button
              size="sm"
              onClick={() => setCreateOpen(true)}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]"
              data-testid="admin-users-create"
            >
              <UserPlus className="w-3.5 h-3.5 mr-1.5" /> Create user
            </Button>
          </div>
        </header>

        {/* Filters */}
        <div className="mb-4 flex flex-wrap gap-2 items-center" data-testid="admin-users-filters">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
            <Input
              type="text" value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }}
              placeholder="Search email, name, company…"
              className="pl-8 h-9 text-[13px]"
              data-testid="admin-users-search"
            />
          </div>
          <Input
            type="text" value={cohortTag}
            onChange={(e) => { setCohortTag(e.target.value); setPage(1); }}
            placeholder="Cohort tag"
            className="h-9 text-[13px] max-w-[180px]"
            data-testid="admin-users-filter-cohort"
          />
          <select
            value={trialStatus}
            onChange={(e) => { setTrialStatus(e.target.value); setPage(1); }}
            className="h-9 text-[13px] px-2 border border-[var(--rule)] rounded-sm bg-white"
            data-testid="admin-users-filter-trial"
          >
            <option value="">Any trial status</option>
            <option value="active_trial">Active trial</option>
            <option value="expired">Expired</option>
            <option value="paid">Paid</option>
          </select>
          <select
            value={roleFilter}
            onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
            className="h-9 text-[13px] px-2 border border-[var(--rule)] rounded-sm bg-white"
            data-testid="admin-users-filter-role"
          >
            <option value="">Any role</option>
            <option value="ned">NED</option>
            <option value="executive">Executive</option>
            <option value="dept_head">Dept head</option>
            <option value="group_exec">Group exec</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-9 text-[13px] px-2 border border-[var(--rule)] rounded-sm bg-white"
            data-testid="admin-users-filter-status"
          >
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </select>
          <Button
            type="button" size="sm" variant="ghost"
            onClick={load} disabled={loading}
            className="text-[12.5px]"
            data-testid="admin-users-refresh"
          >
            {loading
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <RefreshCw className="w-3.5 h-3.5" />}
          </Button>
        </div>

        {/* List */}
        <div className="bg-white border border-[var(--rule)] rounded-sm overflow-hidden" data-testid="admin-users-table-wrapper">
          {loading && items.length === 0 ? (
            <p className="p-6 text-[13px] text-[var(--muted)]" data-testid="admin-users-loading">
              Loading users…
            </p>
          ) : items.length === 0 ? (
            <p className="p-6 text-[13px] text-[var(--muted)]" data-testid="admin-users-empty">
              No users match these filters.
            </p>
          ) : (
            <table className="w-full" data-testid="admin-users-table">
              <thead className="border-b border-[var(--rule)] bg-[var(--cream-deep)]/40">
                <tr>
                  <th className="text-left px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--muted)]">User</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--muted)]">Cohort / Role</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--muted)]">Trial</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--muted)]">Status</th>
                  <th className="text-left px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--muted)]">Last login</th>
                  <th className="text-right px-4 py-2.5 text-[11px] font-mono uppercase tracking-[0.12em] text-[var(--muted)]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((u) => {
                  const suspended = u.status === "suspended";
                  return (
                    <tr
                      key={u.id}
                      className="border-b border-[var(--rule)] last:border-b-0 hover:bg-[var(--cream-deep)]/30"
                      data-testid={`admin-users-row-${u.id}`}
                    >
                      <td className="px-4 py-2.5 align-top">
                        <p className="text-[13px] text-[var(--ink)] font-medium" data-testid={`admin-users-row-email-${u.id}`}>
                          {u.email}
                          {u.is_superadmin && (
                            <span className="ml-2 text-[10px] font-mono uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm bg-[var(--ned-purple)]/10 text-[var(--ned-purple)]">
                              superadmin
                            </span>
                          )}
                        </p>
                        <p className="text-[11.5px] text-[var(--muted)] mt-0.5">
                          {[u.first_name, u.logo_name].filter(Boolean).join(" · ") || "—"}
                        </p>
                      </td>
                      <td className="px-4 py-2.5 align-top text-[12px] text-[var(--deep)]">
                        <p>{u.cohort_tag || "—"}</p>
                        <p className="text-[11px] text-[var(--muted)]">{u.declared_role || "—"}</p>
                      </td>
                      <td className="px-4 py-2.5 align-top text-[12px] text-[var(--deep)]">
                        {u.trial_status || "—"}
                      </td>
                      <td className="px-4 py-2.5 align-top">
                        <span
                          className={
                            "inline-flex items-center gap-1 text-[11px] font-mono uppercase tracking-[0.12em] px-1.5 py-0.5 rounded-sm " +
                            (suspended
                              ? "bg-[var(--oxblood)]/10 text-[var(--oxblood)]"
                              : "bg-emerald-50 text-emerald-700")
                          }
                          data-testid={`admin-users-row-status-${u.id}`}
                        >
                          {suspended ? <ShieldOff className="w-3 h-3" /> : <Shield className="w-3 h-3" />}
                          {u.status || "active"}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 align-top text-[11.5px] text-[var(--muted)]">
                        {fmtDate(u.last_login_at)}
                      </td>
                      <td className="px-4 py-2.5 align-top text-right whitespace-nowrap">
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => setTimelineUser(u)}
                          className="text-[11.5px] h-7 px-2"
                          data-testid={`admin-users-row-timeline-${u.id}`}
                        >
                          <Activity className="w-3 h-3 mr-1" /> Timeline
                        </Button>
                        {suspended ? (
                          <Button
                            size="sm" variant="ghost"
                            onClick={() => onRestore(u)}
                            className="text-[11.5px] h-7 px-2 text-emerald-700"
                            data-testid={`admin-users-row-restore-${u.id}`}
                          >
                            <Shield className="w-3 h-3 mr-1" /> Restore
                          </Button>
                        ) : (
                          <Button
                            size="sm" variant="ghost"
                            onClick={() => onSuspend(u)}
                            className="text-[11.5px] h-7 px-2 text-[var(--oxblood)]"
                            data-testid={`admin-users-row-suspend-${u.id}`}
                          >
                            <ShieldOff className="w-3 h-3 mr-1" /> Suspend
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--rule)] bg-[var(--cream-deep)]/30 text-[12px]" data-testid="admin-users-pagination">
              <p className="text-[var(--muted)] font-mono">
                Page {page} of {totalPages} · {total} users
              </p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} data-testid="admin-users-prev-page">
                  Previous
                </Button>
                <Button size="sm" variant="outline" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} data-testid="admin-users-next-page">
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <CreateUserDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => { setCreateOpen(false); load(); }}
      />

      <TimelineDialog
        user={timelineUser}
        onClose={() => setTimelineUser(null)}
      />
    </AppShell>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Create-user dialog
// ─────────────────────────────────────────────────────────────────────

function CreateUserDialog({ open, onClose, onCreated }) {
  const [email,      setEmail]      = useState("");
  const [firstName,  setFirstName]  = useState("");
  const [logoName,   setLogoName]   = useState("");
  const [role,       setRole]       = useState("");
  const [cohortTag,  setCohortTag]  = useState("");
  const [password,   setPassword]   = useState("");
  const [busy,       setBusy]       = useState(false);

  useEffect(() => {
    if (open) {
      setEmail(""); setFirstName(""); setLogoName("");
      setRole(""); setCohortTag(""); setPassword("");
    }
  }, [open]);

  const submit = async () => {
    if (!email) { toast.error("Email is required."); return; }
    setBusy(true);
    try {
      await api.post("/admin/users", {
        email,
        first_name:        firstName || null,
        logo_name:         logoName || null,
        role:              role || null,
        cohort_tag:        cohortTag || null,
        initial_password:  password || null,
      });
      toast.success("User created.");
      onCreated();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md" data-testid="admin-users-create-dialog">
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <Input type="email" placeholder="email@example.com" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="admin-users-create-email" />
          <Input type="text"  placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} data-testid="admin-users-create-first-name" />
          <Input type="text"  placeholder="Company / logo name" value={logoName} onChange={(e) => setLogoName(e.target.value)} data-testid="admin-users-create-logo-name" />
          <Input type="text"  placeholder="Role (e.g. ned)" value={role} onChange={(e) => setRole(e.target.value)} data-testid="admin-users-create-role" />
          <Input type="text"  placeholder="Cohort tag (optional)" value={cohortTag} onChange={(e) => setCohortTag(e.target.value)} data-testid="admin-users-create-cohort" />
          <Input type="password" placeholder="Initial password (optional — defaults to passwordless)" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="admin-users-create-password" />
          <p className="text-[11.5px] text-[var(--muted)]">
            Leave password blank for passwordless mint — the user sets their own via magic-link or password-reset.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={submit} disabled={busy || !email} data-testid="admin-users-create-submit">
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Timeline drilldown dialog — telemetry only, NO content
// ─────────────────────────────────────────────────────────────────────

function TimelineDialog({ user, onClose }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user?.id) return;
    let dead = false;
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/admin/users/${user.id}/timeline`);
        if (!dead) setItems(data?.items || []);
      } catch (e) { toast.error(apiErrorMessage(e)); }
      finally { if (!dead) setLoading(false); }
    })();
    return () => { dead = true; };
  }, [user?.id]);

  if (!user) return null;

  return (
    <Dialog open={!!user} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg" data-testid="admin-users-timeline-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[var(--accent)]" /> Activity timeline
          </DialogTitle>
          <p className="text-[12px] text-[var(--muted)] mt-1" data-testid="admin-users-timeline-safety">
            Telemetry only — surface + action + when. We never show what the user typed.
          </p>
        </DialogHeader>
        <div className="py-2">
          <p className="text-[13px] text-[var(--ink)] mb-2">
            {user.email}
            {" · "}
            <span className="text-[var(--muted)] font-mono text-[11px]">{user.id}</span>
          </p>
          {loading ? (
            <p className="text-[12px] text-[var(--muted)] py-4">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-[12px] text-[var(--muted)] py-4" data-testid="admin-users-timeline-empty">
              No telemetry events recorded for this account.
            </p>
          ) : (
            <ul className="space-y-1.5 max-h-[50vh] overflow-y-auto" data-testid="admin-users-timeline-list">
              {items.map((ev) => (
                <li
                  key={ev.id}
                  className="px-3 py-2 border border-[var(--rule)] rounded-sm bg-white text-[12px] flex items-center justify-between gap-3"
                  data-testid={`admin-users-timeline-event-${ev.id}`}
                >
                  <div>
                    <span className="font-mono text-[12px] text-[var(--ink)]">{ev.event_type}</span>
                    {ev.surface && (
                      <span className="ml-2 text-[10.5px] uppercase tracking-[0.12em] text-[var(--muted)]">{ev.surface}</span>
                    )}
                  </div>
                  <span className="text-[11px] text-[var(--muted)] whitespace-nowrap">{fmtDate(ev.occurred_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            <X className="w-3.5 h-3.5 mr-1.5" /> Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
