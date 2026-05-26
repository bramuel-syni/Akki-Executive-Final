/**
 * CycleSettings — Phase 2, Part D.
 *
 * Owner/admin can rename, reorder, change durations of the cycle phases.
 * Non-owner sees a read-only view + an explanatory banner.
 *
 * Route: /app/settings/cycle (registered in App.js).
 *
 * Constraints (binding via /app/docs/ux-advisories-v1.md):
 *   - cream / oxblood / navy palette only
 *   - no spinners, no emojis, no exclamation marks
 *   - editorial empty / loading / error copy
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowLeft, ArrowUp, Plus, Trash2 } from "lucide-react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import useCycleConfig from "@/hooks/useCycleConfig";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { apiErrorMessage } from "@/lib/api";

function newDraftPhase(idx) {
  return {
    id: "",
    name: `Phase ${idx + 1}`,
    default_duration_days: 7,
    order: idx,
  };
}

export default function CycleSettings() {
  const navigate = useNavigate();
  const { account, activeContext } = useAuth();
  const cid = activeContext?.id;

  const isOwnerOrAdmin = useMemo(() => {
    if (!activeContext || !account) return false;
    return activeContext.owner_account_id === account.id
      || activeContext.my_sub_role === "admin";
  }, [activeContext, account]);

  const { config, loading, error, refetch, updateConfig, resetConfig, acting } =
    useCycleConfig(cid);

  const [draft, setDraft] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [resetOpen, setResetOpen] = useState(false);

  useEffect(() => {
    if (config?.phases) {
      setDraft({
        phases: config.phases.map((p) => ({ ...p })),
        current_phase_id: config.current_phase_id,
      });
      setDirty(false);
    }
  }, [config]);

  if (!cid) {
    return (
      <AppShell>
        <div className="max-w-[800px] mx-auto px-8 py-10">
          <p className="akki-overline mb-2">Cycle settings</p>
          <p className="text-[14px] italic text-[var(--muted)]">
            Pick a context from the portfolio to edit its cycle phases.
          </p>
        </div>
      </AppShell>
    );
  }

  const updatePhase = (idx, patch) => {
    setDraft((d) => {
      const next = { ...d, phases: d.phases.map((p, i) => (i === idx ? { ...p, ...patch } : p)) };
      return next;
    });
    setDirty(true);
  };

  const reorder = (idx, dir) => {
    setDraft((d) => {
      const phases = [...d.phases];
      const target = idx + dir;
      if (target < 0 || target >= phases.length) return d;
      const tmp = phases[idx];
      phases[idx] = phases[target];
      phases[target] = tmp;
      const reordered = phases.map((p, i) => ({ ...p, order: i }));
      return { ...d, phases: reordered };
    });
    setDirty(true);
  };

  const removePhase = (idx) => {
    setDraft((d) => {
      if (d.phases.length <= 1) return d;
      const phases = d.phases
        .filter((_, i) => i !== idx)
        .map((p, i) => ({ ...p, order: i }));
      const removed = d.phases[idx];
      const next_current = removed.id === d.current_phase_id ? phases[0]?.id : d.current_phase_id;
      return { ...d, phases, current_phase_id: next_current };
    });
    setDirty(true);
  };

  const addPhase = () => {
    setDraft((d) => {
      const next = { ...d, phases: [...d.phases, newDraftPhase(d.phases.length)] };
      return next;
    });
    setDirty(true);
  };

  const handleSave = async () => {
    if (!draft || !isOwnerOrAdmin) return;
    setSaveError(null);
    try {
      const body = {
        phases: draft.phases.map((p) => ({
          id: p.id || undefined,
          name: p.name,
          default_duration_days: Number(p.default_duration_days) || 0,
        })),
        current_phase_id: draft.current_phase_id,
      };
      await updateConfig(body);
      toast.success("Cycle phases saved.");
      setDirty(false);
      await refetch();
    } catch (err) {
      const msg = apiErrorMessage(err, "AKKI couldn’t save the cycle phases.");
      // Surface 409 helpfully — the brief asks for a polite modal.
      if (err?.response?.status === 409) {
        const detail = err?.response?.data?.detail || msg;
        setSaveError(detail);
        toast.error(detail);
        return;
      }
      setSaveError(msg);
      toast.error(msg);
    }
  };

  const handleReset = async () => {
    setResetOpen(false);
    try {
      await resetConfig();
      toast.success("Cycle phases reset to default.");
    } catch (err) {
      toast.error(apiErrorMessage(err, "Reset failed."));
    }
  };

  return (
    <AppShell>
      <div className="max-w-[860px] mx-auto px-6 md:px-8 py-10" data-testid="cycle-settings">
        <button
          type="button"
          onClick={() => navigate("/app")}
          className="text-[11px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1 mb-4"
        >
          <ArrowLeft className="w-3 h-3" /> Back to home
        </button>

        <p className="akki-overline mb-2">Settings · Cycle</p>
        <h1 className="akki-greeting mb-3">Cycle phases</h1>
        <p className="akki-meta max-w-2xl mb-8">
          Customise the cycle phases that AKKI surfaces in the timeline strip on Home and the
          reporting cycle page. Defaults work for most boards.
        </p>

        {!isOwnerOrAdmin ? (
          <div
            className="mb-6 px-4 py-3 border border-[var(--rule)] bg-[var(--cream)]/60 rounded-sm"
            data-testid="cycle-settings-readonly-banner"
          >
            <p className="text-[12.5px] italic text-[var(--muted)]">
              Only the context owner can edit cycle phases. You’re viewing this in read-only mode.
            </p>
          </div>
        ) : null}

        {error ? (
          <p className="text-[13px] text-[var(--ink)] italic mb-6">{error}</p>
        ) : null}

        {loading && !draft ? (
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse">
            Reading the cycle…
          </p>
        ) : null}

        {draft ? (
          <ol className="space-y-3 mb-6" data-testid="cycle-settings-phase-list">
            {draft.phases.map((phase, idx) => (
              <li
                key={`${phase.id || "new"}-${idx}`}
                className="flex items-center gap-3 px-3.5 py-3 bg-white border border-[var(--rule)] rounded-sm"
                data-phase-id={phase.id}
              >
                <span className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] w-6 text-right">
                  {idx + 1}
                </span>
                <Input
                  className="flex-1 h-9 text-[14px] akki-serif"
                  value={phase.name}
                  onChange={(e) => updatePhase(idx, { name: e.target.value })}
                  disabled={!isOwnerOrAdmin}
                  maxLength={60}
                  data-testid={`cycle-settings-phase-name-${idx}`}
                />
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    min={0}
                    max={365}
                    className="w-20 h-9 text-[13px] text-center"
                    value={phase.default_duration_days}
                    onChange={(e) => updatePhase(idx, { default_duration_days: Number(e.target.value) })}
                    disabled={!isOwnerOrAdmin}
                    data-testid={`cycle-settings-phase-duration-${idx}`}
                  />
                  <span className="text-[11px] text-[var(--muted)]">days</span>
                </div>
                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    onClick={() => reorder(idx, -1)}
                    disabled={!isOwnerOrAdmin || idx === 0}
                    className="inline-flex items-center justify-center w-7 h-7 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream)] disabled:opacity-30"
                    title="Move up"
                  >
                    <ArrowUp className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => reorder(idx, 1)}
                    disabled={!isOwnerOrAdmin || idx === draft.phases.length - 1}
                    className="inline-flex items-center justify-center w-7 h-7 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream)] disabled:opacity-30"
                    title="Move down"
                  >
                    <ArrowDown className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => removePhase(idx)}
                    disabled={!isOwnerOrAdmin || draft.phases.length <= 1}
                    className="inline-flex items-center justify-center w-7 h-7 rounded-sm text-[var(--muted)] hover:text-red-700 hover:bg-red-50 disabled:opacity-30"
                    title="Remove phase"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ol>
        ) : null}

        {isOwnerOrAdmin && draft ? (
          <button
            type="button"
            onClick={addPhase}
            className="text-[12px] text-[var(--accent)] hover:underline underline-offset-2 inline-flex items-center gap-1.5 mb-6"
            data-testid="cycle-settings-add-phase"
          >
            <Plus className="w-3.5 h-3.5" /> Add phase
          </button>
        ) : null}

        {saveError ? (
          <div className="mb-6 px-4 py-3 border border-red-200 bg-red-50 rounded-sm">
            <p className="text-[13px] text-red-800">{saveError}</p>
          </div>
        ) : null}

        {isOwnerOrAdmin ? (
          <div className="flex items-center gap-3 pt-6 border-t border-[var(--rule)]">
            <Button
              onClick={handleSave}
              disabled={!dirty || acting}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white akki-overline tracking-[0.16em] text-[11px] h-9 px-4 rounded-sm"
              data-testid="cycle-settings-save"
            >
              {acting ? "Saving…" : "Save"}
            </Button>
            <button
              type="button"
              onClick={() => setResetOpen(true)}
              className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
              data-testid="cycle-settings-reset"
            >
              Reset to defaults
            </button>
          </div>
        ) : null}

        <Dialog open={resetOpen} onOpenChange={setResetOpen}>
          <DialogContent className="bg-white border-[var(--rule)]">
            <DialogHeader>
              <DialogTitle className="akki-serif text-[18px] font-normal">
                Reset cycle phases?
              </DialogTitle>
              <DialogDescription className="text-[13px] text-[var(--muted)]">
                This restores the 6-phase default (Pack arriving · Reading week · Pre-board ·
                Meeting · Minutes · Follow-up). Custom phases will be lost. The current cycle
                resets to start today.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2">
              <Button variant="ghost" onClick={() => setResetOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleReset}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
                data-testid="cycle-settings-reset-confirm"
              >
                Reset
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
