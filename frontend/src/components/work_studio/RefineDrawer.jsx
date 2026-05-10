/**
 * Phase C.3 — Refine drawer.
 *
 * Right-side Sheet. Two-column layout (sections list left, instruction
 * + scope + refine right). On submit, calls
 *   POST /api/work_studio/briefs/{brief_id}/enhance
 * shows the preparing interstitial during the ≈45-60s LLM round-trip,
 * then renders a section-by-section diff with a refusal banner if the
 * validator returned `verdict: refused`.
 *
 * Set Active is enabled only when the verdict is validated or qualified.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  X as XIcon, Loader2, AlertCircle, AlertTriangle, Check, Wand2, ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import { SCOPE_OPTIONS } from "./tokens";
import DiffView from "./DiffView";
import WorkStudioPreparing from "./PreparingInterstitial";

const PROMPTS = [
  "Tighten the opening; put the most consequential sentence first.",
  "Sharpen the recommendations — each must name an owner and a date.",
  "Add a 90-day monitoring plan as a new recommendation.",
  "Convert the framework spine into an OBSERVE / DIAGNOSE / DECIDE rhythm.",
  "Make the closing recap punchier; cut filler verbs.",
];

export default function RefineDrawer({
  open, onClose,
  briefId,
  briefSnapshotSections = [],   // [{section_id, title}]
  onRefined,                    // ({revision}) => void  — caller refreshes history & active
}) {
  const [instruction, setInstruction] = useState("");
  const [scope, setScope] = useState("whole_brief");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);   // {revision_id, diff, validation, claims_changed, claims_added_without_citation, drafter_refused}
  const [setActiveBusy, setSetActiveBusy] = useState(false);

  // Reset when the drawer opens.
  useEffect(() => {
    if (!open) return;
    setInstruction(""); setScope("whole_brief"); setBusy(false);
    setError(null); setResult(null); setSetActiveBusy(false);
  }, [open]);

  const sectionScopes = useMemo(
    () => (briefSnapshotSections || []).map((s) => ({
      value: `section:${s.section_id}`,
      label: `Section · ${s.title || s.section_id}`,
      hint: "Edit only this section.",
    })),
    [briefSnapshotSections],
  );

  const allScopes = [...SCOPE_OPTIONS, ...sectionScopes];

  const handleRefine = async () => {
    if (!briefId || !instruction.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const { data } = await api.post(`/work_studio/briefs/${briefId}/enhance`, {
        instruction: instruction.trim(),
        scope,
      });
      setResult(data);
      onRefined?.({ revision: data });
      const v = data?.validation?.verdict;
      if (v === "refused") {
        toast.error("Refused.", { description: data?.validation?.reason || "" });
      } else if (v === "qualified") {
        toast("Qualified.", { description: "Section diffs ready below." });
      } else {
        toast.success("Validated.", { description: "Section diffs ready below." });
      }
    } catch (e) {
      const msg = apiErrorMessage(e);
      setError(msg);
      toast.error("Refine failed", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  const handleSetActive = async () => {
    if (!result?.revision_id) return;
    setSetActiveBusy(true);
    try {
      await api.post(`/work_studio/briefs/${briefId}/set_active`, {
        revision_id: result.revision_id,
      });
      toast.success("Active revision updated.");
      onRefined?.({ revision: result, activated: true });
      onClose?.();
    } catch (e) {
      toast.error("Set active failed", { description: apiErrorMessage(e) });
    } finally {
      setSetActiveBusy(false);
    }
  };

  const verdict = result?.validation?.verdict;
  const refused = verdict === "refused";
  const canSetActive = result && !refused;

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v && !busy) onClose(); }}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[860px] sm:w-[860px] overflow-y-auto bg-[var(--paper)] p-0"
        data-testid="refine-drawer"
      >
        <div className="px-6 py-5 border-b border-[var(--rule)] flex items-start gap-3 sticky top-0 bg-[var(--paper)] z-10">
          <div className="min-w-0 flex-1">
            <SheetHeader className="text-left">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">
                Refine
              </p>
              <SheetTitle className="akki-serif text-[20px] text-[var(--ink)] leading-snug">
                Tell me what to tighten, sharpen, or add.
              </SheetTitle>
              <SheetDescription className="text-[12.5px] text-[var(--muted)]">
                Two-pass enhance. The validator refuses revisions that introduce uncited claims; refused revisions are kept for inspection but cannot be set active.
              </SheetDescription>
            </SheetHeader>
          </div>
          <button
            onClick={onClose}
            disabled={busy}
            type="button"
            className="text-[var(--muted)] hover:text-[var(--ink)] p-1 disabled:opacity-50"
            aria-label="Close drawer"
            data-testid="refine-drawer-close"
          >
            <XIcon className="w-4 h-4" />
          </button>
        </div>

        {busy ? (
          <div className="px-6">
            <WorkStudioPreparing testId="refine-preparing" />
          </div>
        ) : (
          <div className="px-6 py-5">
            <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6">
              {/* Left: section list */}
              <aside data-testid="refine-sections">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">
                  Brief sections
                </p>
                {briefSnapshotSections.length === 0 ? (
                  <p className="text-[12.5px] text-[var(--muted)] italic">No sections loaded yet.</p>
                ) : (
                  <ul className="space-y-1" data-testid="refine-section-list">
                    {briefSnapshotSections.map((s) => (
                      <li key={s.section_id}>
                        <button
                          type="button"
                          onClick={() => setScope(`section:${s.section_id}`)}
                          className={`w-full text-left text-[12.5px] px-2 py-1.5 rounded-sm border transition-colors ${
                            scope === `section:${s.section_id}`
                              ? "border-[var(--accent)] bg-[var(--cream-deep)]/40 text-[var(--ink)]"
                              : "border-transparent text-[var(--deep)] hover:bg-[var(--cream-deep)]/30"
                          }`}
                          data-testid={`refine-section-${s.section_id}`}
                        >
                          {s.title || s.section_id}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </aside>

              {/* Right: instruction + scope + refine */}
              <div className="space-y-4">
                <div>
                  <Label htmlFor="refine-instruction" className="text-[12px] text-[var(--deep)]">
                    Instruction
                  </Label>
                  <Textarea
                    id="refine-instruction"
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="e.g. Tighten the opening. Make the central call sharper."
                    rows={4}
                    disabled={busy}
                    data-testid="refine-instruction"
                    className="akki-serif text-[14px] bg-white"
                  />
                  <div className="flex flex-wrap gap-1.5 mt-2" data-testid="refine-prompt-suggestions">
                    {PROMPTS.map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setInstruction(p)}
                        className="text-[11.5px] text-[var(--deep)] border border-[var(--rule)] rounded-sm px-2 py-1 hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>

                <div data-testid="refine-scope">
                  <Label className="text-[12px] text-[var(--deep)] mb-1 block">Scope</Label>
                  <div className="space-y-1.5">
                    {allScopes.map((s) => (
                      <button
                        key={s.value}
                        type="button"
                        onClick={() => setScope(s.value)}
                        className={`w-full text-left border rounded-sm px-3 py-2 text-[12.5px] flex items-start gap-3 transition-colors ${
                          scope === s.value
                            ? "border-[var(--accent)] bg-[var(--cream-deep)]/40"
                            : "border-[var(--rule)] bg-white hover:border-[var(--accent)]"
                        }`}
                        data-testid={`refine-scope-${s.value.replace(/[^a-z0-9_-]/gi, "-")}${scope === s.value ? "-active" : ""}`}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-[var(--ink)] font-medium">{s.label}</p>
                          <p className="text-[var(--muted)] text-[11.5px]">{s.hint}</p>
                        </div>
                        <div
                          className={`w-3 h-3 rounded-full border ${scope === s.value ? "border-[var(--accent)] bg-[var(--accent)]" : "border-[var(--rule)]"}`}
                          aria-hidden
                        />
                      </button>
                    ))}
                  </div>
                </div>

                {error && (
                  <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-start gap-2">
                    <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {error}
                  </div>
                )}

                <div className="flex items-center gap-3">
                  <Button
                    type="button"
                    onClick={handleRefine}
                    disabled={busy || !instruction.trim()}
                    className="akki-cta bg-[var(--accent-dark)] hover:bg-[var(--accent)] text-white"
                    data-testid="refine-submit"
                  >
                    <Wand2 className="w-3.5 h-3.5 mr-2" /> Refine <ChevronRight className="w-3.5 h-3.5 ml-1" />
                  </Button>
                  <span className="text-[11.5px] text-[var(--muted)]">
                    Round-trip is typically 45–60s.
                  </span>
                </div>
              </div>
            </div>

            {/* Result */}
            {result && (
              <div className="mt-8 pt-6 border-t border-[var(--rule)]" data-testid="refine-result">
                {refused ? (
                  <div
                    className="border border-rose-200 bg-rose-50 rounded-md px-4 py-3 mb-5"
                    data-testid="refine-refusal-banner"
                    role="alert"
                  >
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-rose-800 mb-1">
                          Refused {result.drafter_refused ? "· by drafter" : "· by validator"}
                        </p>
                        <p className="akki-serif text-[14px] text-rose-900 leading-[1.55]">
                          {result.validation?.reason || "The validator declined this revision."}
                        </p>
                        <p className="text-[12px] text-rose-800 mt-2">
                          The revision is preserved so you can inspect what the model tried to do, but it cannot be set active. Try a tighter instruction — one that doesn't ask for sources outside the brief's existing evidence.
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div
                    className="border border-emerald-200 bg-emerald-50 rounded-md px-4 py-3 mb-5"
                    data-testid="refine-validated-banner"
                  >
                    <div className="flex items-start gap-3">
                      <Check className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-emerald-800 mb-1">
                          {verdict || "validated"}
                        </p>
                        <p className="akki-serif text-[13.5px] text-emerald-900 leading-[1.55]">
                          {result.validation?.reason || "No uncited claims introduced."}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <DiffView diff={result.diff || []} />

                {/* Aggregate metrics */}
                <div className="grid grid-cols-3 gap-3 mt-6 text-center" data-testid="refine-metrics">
                  <div className="border border-[var(--rule)] bg-white rounded-md px-3 py-3">
                    <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Sections changed</p>
                    <p className="akki-serif text-[20px] text-[var(--ink)]">{result.claims_changed ?? 0}</p>
                  </div>
                  <div className="border border-[var(--rule)] bg-white rounded-md px-3 py-3">
                    <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Uncited claims</p>
                    <p className={`akki-serif text-[20px] ${result.claims_added_without_citation > 0 ? "text-rose-800" : "text-[var(--ink)]"}`}>
                      {result.claims_added_without_citation ?? 0}
                    </p>
                  </div>
                  <div className="border border-[var(--rule)] bg-white rounded-md px-3 py-3">
                    <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Verdict</p>
                    <p className={`akki-serif text-[20px] ${refused ? "text-rose-800" : verdict === "qualified" ? "text-sky-800" : "text-emerald-800"}`}>
                      {verdict || "—"}
                    </p>
                  </div>
                </div>

                <div className="mt-6 flex items-center gap-3 sticky bottom-0 bg-[var(--paper)] py-3 -mx-6 px-6 border-t border-[var(--rule)]">
                  <Button
                    type="button"
                    onClick={handleSetActive}
                    disabled={!canSetActive || setActiveBusy}
                    className="akki-cta bg-[var(--accent-dark)] hover:bg-[var(--accent)] text-white disabled:bg-[var(--rule)] disabled:text-[var(--muted)]"
                    data-testid="refine-set-active"
                  >
                    {setActiveBusy ? (
                      <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Setting active…</>
                    ) : (
                      <>Set as active revision <ChevronRight className="w-3.5 h-3.5 ml-1" /></>
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={onClose}
                    className="text-[var(--muted)] hover:text-[var(--ink)]"
                  >
                    Close
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
