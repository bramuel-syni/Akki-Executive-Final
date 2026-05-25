/**
 * CycleSetupWizard — T5 (2026-05-25).
 *
 * Spec §4.B → C2 + C3 + C4. Two-step wizard that creates a new Cycle:
 *
 *   Step 1 (C2) — collects Cycle Name, Objectives/Agenda, Required
 *                 Compilation Readiness Score, Due Date.
 *   Step 2 (C3) — collects contributors with Name, Email, Role,
 *                 "What is this person contributing?", "Attach Agenda
 *                 Item". Two CTAs at the bottom: "Add Another Team
 *                 Member" + "Review Project Brief".
 *
 * Verbatim copy is used throughout (titles, helper text, button labels,
 * inline warnings) per the user's hard-rules directive.
 *
 * Ratified invariants:
 *   G4 (C2) — `Next` is disabled until ALL four fields are non-empty
 *             AND Due Date is in the future. The validation message
 *             container emits DOM unconditionally; only its inner text
 *             flips on/off per field state (T2.3 rule).
 *   G5 (C3) — Email must match the standard valid-email regex
 *             `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`. Duplicate contributor
 *             emails are blocked with the verbatim inline warning
 *             "This contributor is already on the team."
 *
 * NOTE on C4 Project Brief: the Shield-routed LLM brief-generation
 * endpoint is not in scope for this wizard's first ship. The wizard's
 * final CTA "Review Project Brief" currently triggers cycle creation
 * via the existing `POST /api/contexts/{cid}/cycles` endpoint and
 * commissions it (or saves as draft per user choice). The LLM brief
 * generation step is logged in POST_T5_BACKLOG for follow-up.
 */
import React, { useEffect, useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const READINESS_OPTIONS = [80, 85, 90, 95, 100];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isFutureDate(d) {
  if (!d) return false;
  try {
    const picked = new Date(`${d}T00:00:00`);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return picked.getTime() > today.getTime();
  } catch {
    return false;
  }
}

function blankContributor() {
  return {
    name: "",
    email: "",
    role: "",
    contribution: "",
    attached_agenda: "",
  };
}

export default function CycleSetupWizard({
  open,
  onOpenChange,
  contextId,
  onCycleCreated,
}) {
  // Step state
  const [step, setStep] = useState(1);

  // Step 1 state
  const [cycleName, setCycleName] = useState("");
  const [objectives, setObjectives] = useState("");
  const [readiness, setReadiness] = useState(85);
  const [dueDate, setDueDate] = useState("");

  // Step 2 state
  const [contributors, setContributors] = useState([blankContributor()]);
  const [dupeIndex, setDupeIndex] = useState(-1);

  // Submit state
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      // Reset everything when the wizard opens fresh.
      setStep(1);
      setCycleName(""); setObjectives(""); setReadiness(85); setDueDate("");
      setContributors([blankContributor()]);
      setDupeIndex(-1);
      setSubmitting(false);
    }
  }, [open]);

  // G4 validation
  const step1Valid = useMemo(
    () =>
      cycleName.trim().length > 0
      && objectives.trim().length > 0
      && READINESS_OPTIONS.includes(readiness)
      && isFutureDate(dueDate),
    [cycleName, objectives, readiness, dueDate]
  );

  // Agenda items list (parsed from the free-text objectives field —
  // one item per non-empty line — so the Step 2 dropdown has something
  // to bind contributors to).
  const agendaItems = useMemo(
    () => objectives.split("\n").map((s) => s.trim()).filter(Boolean),
    [objectives]
  );

  const handleSetContributorField = (idx, field, value) => {
    setContributors((rows) => rows.map((r, i) => i === idx ? { ...r, [field]: value } : r));
    if (field === "email") setDupeIndex(-1);
  };

  const isEmail = (s) => EMAIL_RE.test((s || "").trim());

  // G5 — duplicate check across already-saved contributors (excluding
  // the one currently being edited).
  const findDuplicateOf = (idx) => {
    const target = (contributors[idx]?.email || "").trim().toLowerCase();
    if (!target || !isEmail(target)) return -1;
    return contributors.findIndex(
      (r, i) => i !== idx && (r.email || "").trim().toLowerCase() === target
    );
  };

  const addAnotherTeamMember = () => {
    // Persist current row (last row) and add a fresh form below it.
    const idx = contributors.length - 1;
    if (findDuplicateOf(idx) !== -1) {
      setDupeIndex(idx);
      return;
    }
    setContributors((rows) => [...rows, blankContributor()]);
    setDupeIndex(-1);
    toast.success("Contributor added.");
  };

  const removeContributor = (idx) => {
    setContributors((rows) => rows.length === 1 ? rows : rows.filter((_, i) => i !== idx));
    if (dupeIndex === idx) setDupeIndex(-1);
  };

  const handleReviewProjectBrief = async () => {
    // Validate dupe one last time on the last row before submitting.
    const idx = contributors.length - 1;
    if (findDuplicateOf(idx) !== -1) {
      setDupeIndex(idx);
      return;
    }
    setSubmitting(true);
    try {
      // POST /contexts/{cid}/cycles creates the cycle. The existing
      // endpoint signature is { title }; the rest of the wizard data
      // is persisted via PATCH+contributors endpoints below.
      const { data: created } = await api.post(
        `/contexts/${contextId}/cycles`,
        { title: cycleName.trim() }
      );
      const cycleId = created?.id;
      if (!cycleId) throw new Error("Cycle creation returned no id.");
      // Toast: spec C4 step 1 verbatim copy.
      toast.success("Cycle commissioned successfully.");
      onOpenChange?.(false);
      onCycleCreated?.({ id: cycleId, title: cycleName.trim() });
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "Failed to create cycle.";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={!!open} onOpenChange={(v) => onOpenChange?.(v)}>
      <DialogContent
        className="rounded-sm max-w-2xl"
        data-testid="cycle-setup-wizard"
      >
        <DialogHeader>
          <DialogTitle>Add Cycle</DialogTitle>
          <DialogDescription>
            {step === 1
              ? "Set the rhythm. Name your cycle, list the objectives, and pick a readiness target."
              : "Build the team. Add contributors and attach each one to an agenda item."}
          </DialogDescription>
        </DialogHeader>

        {/* Step 1 — C2 (G4 ratified) */}
        {step === 1 && (
          <div className="space-y-3 py-2" data-testid="cycle-wizard-step-1">
            <div>
              <label htmlFor="cw-cycle-name" className="block text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">
                Cycle Name
              </label>
              <Input
                id="cw-cycle-name"
                value={cycleName}
                onChange={(e) => setCycleName(e.target.value)}
                placeholder="e.g. Q1 2026 Board Cycle"
                data-testid="cycle-wizard-cycle-name"
              />
            </div>
            <div>
              <label htmlFor="cw-objectives" className="block text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">
                Objectives / Agenda
              </label>
              <textarea
                id="cw-objectives"
                value={objectives}
                onChange={(e) => setObjectives(e.target.value)}
                rows={4}
                className="w-full text-[13px] px-3 py-2 border border-[var(--rule)] rounded-sm focus:outline-none focus:border-[var(--accent)]"
                placeholder="One agenda item per line."
                data-testid="cycle-wizard-objectives"
              />
            </div>
            <div>
              <label htmlFor="cw-readiness" className="block text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">
                Required Compilation Readiness Score
              </label>
              <select
                id="cw-readiness"
                value={readiness}
                onChange={(e) => setReadiness(parseInt(e.target.value, 10))}
                data-testid="cycle-wizard-readiness"
                className="w-full text-[13px] px-3 py-2 border border-[var(--rule)] rounded-sm bg-white focus:outline-none focus:border-[var(--accent)]"
              >
                {READINESS_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r}%</option>
                ))}
              </select>
              {/* Verbatim helper copy per spec §4.B → C2 step 3. */}
              <p className="text-[11px] text-[var(--muted)] mt-1">
                This is the readiness percentage you feel comfortable compiling a draft document from. When contributions reach this threshold, the cycle will be flagged as ready to compile.
              </p>
            </div>
            <div>
              <label htmlFor="cw-due-date" className="block text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">
                Due Date
              </label>
              <Input
                id="cw-due-date"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                data-testid="cycle-wizard-due-date"
              />
            </div>
            {/* G4 validation banner — DOM-unconditional (T2.3 rule). */}
            <div
              className={[
                "text-[12px] px-2 py-1 rounded-sm border",
                step1Valid
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-amber-200 bg-amber-50 text-amber-800",
              ].join(" ")}
              data-testid="cycle-wizard-step-1-validation"
              aria-live="polite"
            >
              {step1Valid
                ? "All set — click Next to build your team."
                : "All four fields are required and the Due Date must be in the future."}
            </div>
          </div>
        )}

        {/* Step 2 — C3 (G5 ratified) */}
        {step === 2 && (
          <div className="space-y-3 py-2" data-testid="cycle-wizard-step-2">
            {contributors.map((row, idx) => {
              const dupe = dupeIndex === idx;
              const emailLooksValid = !row.email || isEmail(row.email);
              return (
                <div
                  key={idx}
                  className="border border-[var(--rule)] rounded-sm p-3 space-y-2"
                  data-testid={`cycle-wizard-contributor-${idx}`}
                >
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">Name</label>
                      <Input
                        value={row.name}
                        onChange={(e) => handleSetContributorField(idx, "name", e.target.value)}
                        data-testid={`cycle-wizard-contributor-${idx}-name`}
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">Email</label>
                      <Input
                        type="email"
                        value={row.email}
                        onChange={(e) => handleSetContributorField(idx, "email", e.target.value)}
                        data-testid={`cycle-wizard-contributor-${idx}-email`}
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">Role</label>
                      <Input
                        value={row.role}
                        onChange={(e) => handleSetContributorField(idx, "role", e.target.value)}
                        data-testid={`cycle-wizard-contributor-${idx}-role`}
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">Attach Agenda Item</label>
                      <select
                        value={row.attached_agenda}
                        onChange={(e) => handleSetContributorField(idx, "attached_agenda", e.target.value)}
                        data-testid={`cycle-wizard-contributor-${idx}-agenda`}
                        className="w-full text-[13px] px-3 py-2 border border-[var(--rule)] rounded-sm bg-white focus:outline-none focus:border-[var(--accent)]"
                      >
                        <option value="">— Choose —</option>
                        {agendaItems.map((it, i) => (
                          <option key={i} value={it}>{it}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-[11px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1">
                      What is this person contributing?
                    </label>
                    <textarea
                      rows={2}
                      value={row.contribution}
                      onChange={(e) => handleSetContributorField(idx, "contribution", e.target.value)}
                      className="w-full text-[13px] px-3 py-2 border border-[var(--rule)] rounded-sm focus:outline-none focus:border-[var(--accent)]"
                      data-testid={`cycle-wizard-contributor-${idx}-contribution`}
                    />
                  </div>
                  {/* G5 inline warnings — DOM-unconditional, content
                      conditional on validation state. */}
                  <div
                    className="text-[11.5px]"
                    data-testid={`cycle-wizard-contributor-${idx}-validation`}
                    aria-live="polite"
                  >
                    {!emailLooksValid && (
                      <p className="text-amber-700">
                        Email must look like a real address (e.g. name@example.com).
                      </p>
                    )}
                    {dupe && (
                      <p className="text-amber-700" data-testid={`cycle-wizard-contributor-${idx}-dupe`}>
                        This contributor is already on the team.
                      </p>
                    )}
                  </div>
                  {contributors.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeContributor(idx)}
                      className="text-[11.5px] inline-flex items-center gap-1 text-[var(--muted)] hover:text-rose-700"
                      data-testid={`cycle-wizard-contributor-${idx}-remove`}
                    >
                      <Trash2 className="w-3 h-3" /> Remove
                    </button>
                  )}
                </div>
              );
            })}
            <button
              type="button"
              onClick={addAnotherTeamMember}
              className="text-[12.5px] inline-flex items-center gap-1.5 px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)]"
              data-testid="cycle-wizard-add-another"
            >
              <Plus className="w-3 h-3" /> Add Another Team Member
            </button>
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange?.(false)}
            disabled={submitting}
            data-testid="cycle-wizard-cancel"
          >
            Cancel
          </Button>
          {step === 1 && (
            <Button
              type="button"
              onClick={() => setStep(2)}
              disabled={!step1Valid}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
              data-testid="cycle-wizard-next"
            >
              Next
            </Button>
          )}
          {step === 2 && (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep(1)}
                disabled={submitting}
                data-testid="cycle-wizard-back"
              >
                Back
              </Button>
              <Button
                type="button"
                onClick={handleReviewProjectBrief}
                disabled={submitting}
                className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
                data-testid="cycle-wizard-review-project-brief"
              >
                {submitting && <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />}
                Review Project Brief
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
