/**
 * Phase P4.B (2026-02) — Admin cohort applications surface.
 *
 * Lists rows from `cohort_applications` and surfaces approve / decline /
 * hold actions per row. Approve issues a magic link + (if the feature
 * flag is on) sends the approval email. Decline sends the decline email.
 * Hold sends no email.
 *
 * Confirmation modal on approve + decline. Success toast carries the
 * magic-link URL on approve so the admin can copy/paste it out of band
 * when the email flag is still off.
 */
import React, { useEffect, useState, useCallback } from "react";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, Check, Pause, X, Copy } from "lucide-react";

const STATUS_FILTERS = [
  { value: "all",        label: "All" },
  { value: "received",   label: "Received" },
  { value: "held",       label: "Held" },
  { value: "approved",   label: "Approved" },
  { value: "approved_redeemed", label: "Redeemed" },
  { value: "declined",   label: "Declined" },
];

export default function AdminCohortApplications() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  // Confirmation dialog state.
  const [confirm, setConfirm] = useState(null);    // { app, action }
  const [note, setNote] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter === "all" ? {} : { status: filter };
      const { data } = await api.get("/admin/cohort/applications", { params });
      setItems(data.items || []);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    if (!confirm) return;
    const { app, action } = confirm;
    setBusyId(app.id);
    try {
      const { data } = await api.post(
        `/admin/cohort/applications/${app.id}/${action}`,
        { note: note?.trim() || null },
      );
      if (action === "approve" && data.magic_url) {
        try { await navigator.clipboard.writeText(data.magic_url); } catch (_e) { /* clip best-effort */ }
        toast.success(
          `Approved ${app.email}. Magic link copied to clipboard.`,
          { description: data.email?.status === "flag_off" ? "Email skipped (COHORT_EMAILS_ENABLED=false)" : `Email status: ${data.email?.status}` },
        );
      } else if (action === "decline") {
        toast.success(`Declined ${app.email}.`,
          { description: data.email?.status === "flag_off" ? "Email skipped (COHORT_EMAILS_ENABLED=false)" : `Email status: ${data.email?.status}` },
        );
      } else if (action === "hold") {
        toast.success(`Held ${app.email}.`);
      }
      setConfirm(null);
      setNote("");
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-6 py-8" data-testid="admin-cohort-applications">
        <h1 className="text-2xl font-semibold text-[var(--ink)] mb-2">Cohort applications</h1>
        <p className="text-sm text-slate-500 mb-6">
          Read the use-case field first. Approve, hold, or decline; the
          row carries the audit.
        </p>

        <div className="flex flex-wrap gap-2 mb-4" data-testid="admin-cohort-filters">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={
                "text-xs px-3 py-1.5 rounded-sm border " +
                (filter === f.value
                  ? "bg-[var(--ink)] text-white border-[var(--ink)]"
                  : "bg-white text-[var(--ink)] border-[#E1E6ED] hover:bg-slate-50")
              }
              data-testid={`admin-cohort-filter-${f.value}`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading && (
          <div className="text-sm text-slate-500 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        )}

        {!loading && items.length === 0 && (
          <p className="text-sm text-slate-500" data-testid="admin-cohort-empty">
            No applications in this status.
          </p>
        )}

        {!loading && items.length > 0 && (
          <div className="border border-[#E1E6ED] rounded-sm bg-white divide-y divide-[#E1E6ED]">
            {items.map((app) => (
              <div
                key={app.id}
                className="p-4 flex flex-col md:flex-row md:items-start md:justify-between gap-3"
                data-testid={`admin-cohort-row-${app.id}`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-3 mb-1 flex-wrap">
                    <p className="font-medium text-sm text-[var(--ink)]" data-testid={`admin-cohort-row-${app.id}-name`}>
                      {app.name || app.email}
                    </p>
                    <span
                      className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-slate-100 text-slate-600"
                      data-testid={`admin-cohort-row-${app.id}-status`}
                    >
                      {app.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mb-1">{app.email} · {app.organisation} · {app.role}</p>
                  <p className="text-xs text-[var(--ink)] mt-1 leading-relaxed break-words" data-testid={`admin-cohort-row-${app.id}-use-case`}>
                    {app.use_case}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5 shrink-0">
                  {app.status !== "approved" && app.status !== "approved_redeemed" && (
                    <Button
                      size="sm" variant="ghost"
                      onClick={() => { setConfirm({ app, action: "approve" }); setNote(""); }}
                      disabled={busyId === app.id}
                      className="text-[11.5px] h-7 px-2 text-emerald-700 hover:bg-emerald-50"
                      data-testid={`admin-cohort-row-${app.id}-approve`}
                    >
                      <Check className="w-3 h-3 mr-1" /> Approve
                    </Button>
                  )}
                  {app.status !== "held" && app.status !== "approved_redeemed" && (
                    <Button
                      size="sm" variant="ghost"
                      onClick={() => { setConfirm({ app, action: "hold" }); setNote(""); }}
                      disabled={busyId === app.id}
                      className="text-[11.5px] h-7 px-2 text-slate-700 hover:bg-slate-100"
                      data-testid={`admin-cohort-row-${app.id}-hold`}
                    >
                      <Pause className="w-3 h-3 mr-1" /> Hold
                    </Button>
                  )}
                  {app.status !== "declined" && app.status !== "approved_redeemed" && (
                    <Button
                      size="sm" variant="ghost"
                      onClick={() => { setConfirm({ app, action: "decline" }); setNote(""); }}
                      disabled={busyId === app.id}
                      className="text-[11.5px] h-7 px-2 text-[var(--oxblood)] hover:bg-red-50"
                      data-testid={`admin-cohort-row-${app.id}-decline`}
                    >
                      <X className="w-3 h-3 mr-1" /> Decline
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <Dialog open={!!confirm} onOpenChange={(o) => { if (!o) setConfirm(null); }}>
          <DialogContent className="bg-white rounded-sm max-w-md" data-testid="admin-cohort-confirm-modal">
            <DialogHeader>
              <DialogTitle className="text-lg font-semibold capitalize">
                {confirm?.action} {confirm?.app?.email}?
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-slate-600">
                {confirm?.action === "approve" && "Issues a single-use magic link valid 14 days and queues the approval email."}
                {confirm?.action === "decline" && "Marks the application declined and queues the decline email."}
                {confirm?.action === "hold" && "Marks the application held. No email sent."}
              </p>
              <div>
                <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                  Internal note (optional)
                </label>
                <Input
                  value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. 'Strong use case — green-light.'"
                  className="h-9 text-sm mt-1 rounded-sm"
                  data-testid="admin-cohort-confirm-note"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setConfirm(null)} data-testid="admin-cohort-confirm-cancel">
                Cancel
              </Button>
              <Button
                onClick={submit}
                disabled={busyId === confirm?.app?.id}
                className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-9 capitalize"
                data-testid="admin-cohort-confirm-submit"
              >
                {busyId === confirm?.app?.id ? "Working…" : `${confirm?.action || "do it"}`}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
