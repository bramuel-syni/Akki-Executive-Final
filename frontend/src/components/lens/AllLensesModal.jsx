import React, { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import {
  Dialog, DialogContent, DialogDescription, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Eye, Loader2, HelpCircle, Check, Sparkles, X,
  Scale, UsersRound, TrendingUp, Brain, Globe2, Network,
} from "lucide-react";

const LENS_ICON = {
  first_principles:        Brain,
  customer_obsession:      UsersRound,
  systems_thinking:        Network,
  capital_discipline:      Scale,
  stakeholder_integration: Globe2,
  organisational_culture:  TrendingUp,
};

/**
 * Fires every lens in the catalog against a single signal in parallel and
 * presents the six O-I-A reads as a scrollable deck. Backed by the existing
 * `/contexts/{id}/lens/run` endpoint — so no new backend required.
 */
export default function AllLensesModal({ signal, open, onClose }) {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;
  const [catalog, setCatalog] = useState([]);
  const [runs, setRuns] = useState([]);       // [{lens, run_or_error, state}]
  const [started, setStarted] = useState(false);

  // Initialise the lens catalog once the modal opens
  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const { data } = await api.get("/lens/catalog");
        setCatalog(data || []);
      } catch (e) { toast.error(apiErrorMessage(e)); }
    })();
  }, [open]);

  const runAll = useCallback(async () => {
    if (!contextId || !signal || catalog.length === 0) return;
    setStarted(true);
    setRuns(catalog.map((l) => ({ lens: l, run: null, error: null, state: "pending" })));

    const subject = signal.headline + (signal.summary ? `\n\n${signal.summary}` : "");

    // Mark each in-flight as we start, then settle when each returns.
    await Promise.all(catalog.map(async (l, idx) => {
      setRuns((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], state: "running" };
        return next;
      });
      try {
        const { data } = await api.post(
          `/contexts/${contextId}/lens/run`,
          { lens: l.id, subject, signal_id: signal.id },
          { timeout: 180000 },
        );
        setRuns((prev) => {
          const next = [...prev];
          next[idx] = { lens: l, run: data, error: null, state: "done" };
          return next;
        });
      } catch (e) {
        setRuns((prev) => {
          const next = [...prev];
          next[idx] = { lens: l, run: null, error: apiErrorMessage(e), state: "error" };
          return next;
        });
      }
    }));
  }, [catalog, contextId, signal]);

  // Kick off automatically once catalog has loaded.
  useEffect(() => {
    if (open && catalog.length > 0 && !started) runAll();
  }, [open, catalog, started, runAll]);

  // Reset when the modal closes so next open is a fresh run.
  useEffect(() => {
    if (!open) {
      setStarted(false);
      setRuns([]);
    }
  }, [open]);

  const completed = runs.filter((r) => r.state === "done").length;
  const erroring = runs.filter((r) => r.state === "error").length;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent
        className="max-w-[900px] max-h-[90vh] overflow-hidden flex flex-col bg-[var(--cream)] border-[var(--rule)] p-0"
        data-testid="all-lenses-modal"
      >
        <DialogTitle className="sr-only">Run signal through every lens</DialogTitle>
        <DialogDescription className="sr-only">
          Applies all six AKKI lenses to the selected signal in parallel and presents the structured Observation, Implication, Action and Question for Management for each.
        </DialogDescription>

        {/* Header */}
        <div className="px-7 py-5 border-b border-[var(--rule)] bg-white flex items-start justify-between">
          <div className="flex-1 min-w-0 pr-4">
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> All six lenses · in parallel
            </p>
            <h2 className="akki-serif text-[22px] font-normal text-[var(--ink)] leading-snug mb-1">
              {signal?.headline}
            </h2>
            <p className="text-[11.5px] text-[var(--muted)]">
              {started
                ? erroring > 0
                  ? `${completed} of ${catalog.length} complete · ${erroring} errored`
                  : `${completed} of ${catalog.length} complete`
                : "Preparing…"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-[var(--muted)] hover:text-[var(--ink)]"
            data-testid="all-lenses-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress strip */}
        {started && completed < catalog.length && (
          <div className="h-[3px] bg-[var(--rule)]">
            <div
              className="h-full bg-[var(--accent)] transition-all duration-500"
              style={{ width: `${(completed / Math.max(catalog.length, 1)) * 100}%` }}
            />
          </div>
        )}

        {/* Results deck */}
        <div className="flex-1 overflow-y-auto px-7 py-6 space-y-5" data-testid="all-lenses-deck">
          {runs.length === 0 && (
            <div className="py-10 text-center">
              <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)] mx-auto mb-3" />
              <p className="text-[12.5px] text-[var(--muted)] italic">Loading lens catalog…</p>
            </div>
          )}
          {runs.map((entry) => {
            const Icon = LENS_ICON[entry.lens.id] || Eye;
            return (
              <section
                key={entry.lens.id}
                className="bg-white border border-[var(--rule)] rounded-md p-5 akki-fade-up"
                data-testid={`all-lenses-slide-${entry.lens.id}`}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 bg-[var(--accent-soft)] rounded-md flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="akki-serif text-[16px] text-[var(--ink)] leading-snug">{entry.lens.name}</p>
                    <p className="text-[11px] text-[var(--muted)] italic">{entry.lens.hint}</p>
                  </div>
                  {entry.state === "running" && <Loader2 className="w-4 h-4 animate-spin text-[var(--accent)]" />}
                  {entry.state === "done" && <Check className="w-4 h-4 text-emerald-700" strokeWidth={2.2} />}
                  {entry.state === "error" && <span className="text-[10px] uppercase tracking-wider text-red-600">errored</span>}
                </div>

                {entry.state === "done" && entry.run ? (
                  <div className="space-y-4">
                    <div>
                      <p className="akki-overline mb-1">Observation</p>
                      <p className="akki-serif text-[14px] leading-[1.7] text-[var(--deep)]">{entry.run.observation}</p>
                    </div>
                    <div>
                      <p className="akki-overline mb-1">Implication</p>
                      <p className="akki-serif text-[14px] leading-[1.7] text-[var(--deep)]">{entry.run.implication}</p>
                    </div>
                    <div className="relative pl-4">
                      <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-[var(--accent)] rounded-full" />
                      <p className="akki-overline mb-1">Action</p>
                      <p className="akki-serif text-[14px] leading-[1.7] text-[var(--deep)]">{entry.run.action}</p>
                    </div>
                    {entry.run.question_for_management && (
                      <div className="bg-[var(--accent-soft)]/60 border border-[var(--accent)]/25 rounded-md p-3">
                        <div className="flex items-center gap-1.5 mb-1">
                          <HelpCircle className="w-3 h-3 text-[var(--accent)]" />
                          <p className="akki-overline">Question for management</p>
                        </div>
                        <p className="akki-serif italic text-[13.5px] text-[var(--ink)]">
                          "{entry.run.question_for_management}"
                        </p>
                      </div>
                    )}
                  </div>
                ) : entry.state === "error" ? (
                  <p className="text-[12.5px] text-red-600 italic">{entry.error}</p>
                ) : (
                  <div className="space-y-3 opacity-40">
                    <div className="h-3 bg-[var(--rule)] rounded w-1/4" />
                    <div className="h-2 bg-[var(--rule)] rounded w-full" />
                    <div className="h-2 bg-[var(--rule)] rounded w-[85%]" />
                  </div>
                )}
              </section>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-7 py-4 border-t border-[var(--rule)] bg-white flex items-center justify-between">
          <p className="text-[11px] text-[var(--muted)]">
            Each lens opens in <a href="/app/lens" className="text-[var(--accent)] hover:underline">Lens Room</a> for a full read.
          </p>
          <Button
            onClick={onClose}
            className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-white rounded-sm h-9 px-4 text-[12.5px]"
            data-testid="all-lenses-done-btn"
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
