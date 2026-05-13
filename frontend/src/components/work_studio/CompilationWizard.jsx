/**
 * CompilationWizard — Patch 2B.2.
 *
 * 4-step modal:
 *   1. Choose artefact type + template
 *   2. Select source items (multi-select, with "Select all ready" shortcut)
 *   3. Confirm contributors + deterministic Agent Cycle preview
 *   4. Cadence + format + title → confirm POSTs to
 *      /api/contexts/{cid}/work-studio/compilations
 *
 * Open from:
 *   • Primary CTA in the rail
 *   • A "Ready" row in the rail (pre-selects artefact type + source on Step 2)
 *
 * Verbatim toast on success:
 *   "{title} is being compiled. Agent Cycle will surface progress in the rail."
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  CheckCircle2, Circle, Loader2, ScrollText, FileText, FolderOpen,
  Presentation, BookOpen, ChevronLeft, ChevronRight,
} from "lucide-react";
import { agentCyclePreview } from "@/components/work_studio/agentCyclePreview";


// Artefact type ↔ aggregate kind. Locked by SYSTEM_STATE §2.2.
const ARTEFACT_TYPES = [
  { key: "board_pack",     label: "Board Pack",     kind: "cycle_board_pack",     icon: ScrollText },
  { key: "minutes",        label: "Minutes",        kind: "cycle_minutes",        icon: FileText },
  { key: "committee_pack", label: "Committee Pack", kind: "cycle_committee_pack", icon: FolderOpen },
  { key: "deck",           label: "Deck",           kind: "deck",                 icon: Presentation },
  { key: "report",         label: "Report",         kind: "report",               icon: FileText },
  { key: "briefing",       label: "Briefing",       kind: "briefing",             icon: BookOpen },
];

const STANDARD_TEMPLATE = { key: "standard", label: "Standard" };
const FORMATS = ["docx", "pptx", "pdf"];
const STEPS = ["1 Choose", "2 Sources", "3 Contributors", "4 Cadence"];


function shortAge(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const ms = Date.now() - d.getTime();
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch { return "—"; }
}


function StepIndicator({ step }) {
  return (
    <div className="flex items-center gap-2 mb-5 text-[11px] uppercase tracking-[0.16em] font-mono" data-testid="wizard-step-indicator">
      {STEPS.map((s, i) => {
        const idx = i + 1;
        const active = step === idx;
        const done = step > idx;
        return (
          <span
            key={s}
            className={[
              "px-2 py-1",
              active ? "text-[var(--ink)] border-b border-[color:var(--oxblood)]" : done ? "text-[var(--ink)]" : "text-[var(--muted)]",
            ].join(" ")}
            data-testid={`wizard-step-${idx}${active ? "-active" : ""}`}
          >
            {s}
          </span>
        );
      })}
    </div>
  );
}


// Chunk 4 (2026-05-13) — per-artefact-type default output format.
// Pre-fix every wizard run defaulted to `["docx"]` which made a Deck
// compilation get marked as DOCX-only on Step 4 (wrong; PowerPoint is
// the obvious primary). The user could still tick PPTX, but the
// default mismatched intent for half the types. Map below:
const DEFAULT_FORMAT_BY_TYPE = {
  board_pack:     ["docx"],
  minutes:        ["docx"],
  committee_pack: ["docx"],
  deck:           ["pptx"],
  report:         ["docx"],
  briefing:       ["docx"],
};

export default function CompilationWizard({ open, onClose, contextId,
                                            preselectArtefactType = null,
                                            preselectSourceId = null,
                                            onCreated }) {
  const [step, setStep] = useState(1);

  // Step 1 state
  const [artefactType, setArtefactType] = useState(preselectArtefactType || "");
  const [templateKey, setTemplateKey] = useState("standard");

  // Step 2 state
  const [sourceItems, setSourceItems] = useState([]);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [selectedSourceIds, setSelectedSourceIds] = useState(new Set());

  // Step 3 state — contributors derived from sources + manual exclusions
  const [excludedContribIds, setExcludedContribIds] = useState(new Set());

  // Step 4 state
  const [cadenceKind, setCadenceKind] = useState("one_off");
  const [recurringInterval, setRecurringInterval] = useState("monthly");
  const [scheduledAt, setScheduledAt] = useState("");
  const [formats, setFormats] = useState(["docx"]);
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Reset state when the modal closes.
  //
  // Chunk 4 (2026-05-13, WS-R02/R07/R08) — pre-fix the wizard auto-
  // skipped Step 1 when a `preselectArtefactType` was provided
  // (`setStep(preselectArtefactType ? 2 : 1)`). The Compile-XXX
  // buttons in WorkStudio pass a preselect type now (Chunk 4 fixed
  // them to pass the correct type), but the user must STILL confirm
  // the type on Step 1 — every wizard run begins on Step 1, the
  // preselect just sets the radio default. This matches QA's
  // expectation in WS-R02/R07/R08.
  //
  // Chunk 4 (2026-05-13, WS-R04 sub-fix) — the default `formats` is
  // now keyed off the preselected artefact type, so opening Compile
  // Deck → Step 4 shows PPTX ticked by default instead of DOCX.
  useEffect(() => {
    if (open) {
      setStep(1);
      setArtefactType(preselectArtefactType || "");
      setTemplateKey("standard");
      setSelectedSourceIds(new Set(preselectSourceId ? [preselectSourceId] : []));
      setExcludedContribIds(new Set());
      setCadenceKind("one_off");
      setRecurringInterval("monthly");
      setScheduledAt("");
      setFormats(DEFAULT_FORMAT_BY_TYPE[preselectArtefactType] || ["docx"]);
      setTitle("");
    }
  }, [open, preselectArtefactType, preselectSourceId]);

  // Chunk 4 — when the user changes the artefact type radio on Step 1,
  // also flip the format default so they don't have to manually
  // un-tick DOCX + tick PPTX every time they pick Deck. Only triggers
  // when the type actually changes (not on every render).
  useEffect(() => {
    if (!open || !artefactType) return;
    const wantedDefault = DEFAULT_FORMAT_BY_TYPE[artefactType] || ["docx"];
    setFormats(wantedDefault);
    // Title is regenerated whenever the type changes (next effect),
    // so we reset that too when the user explicitly switches type.
    setTitle("");
  }, [artefactType, open]);

  // Derive the aggregate `kind` for the chosen artefact type.
  const artefact = useMemo(
    () => ARTEFACT_TYPES.find((t) => t.key === artefactType) || null,
    [artefactType],
  );

  // Generated default title once artefact + first source are known.
  useEffect(() => {
    if (!artefact || title) return;
    const now = new Date();
    const q = Math.floor(now.getMonth() / 3) + 1;
    const yr = now.getFullYear();
    setTitle(`Q${q} ${yr} — ${artefact.label}`);
  }, [artefact, title]);

  // Fetch candidate sources whenever we land on step 2.
  useEffect(() => {
    if (!open || step !== 2 || !artefact || !contextId) return undefined;
    let dead = false;
    setSourceLoading(true);
    api
      .get(`/contexts/${contextId}/briefings/aggregates`, {
        params: { kind: artefact.kind, sort: "recent", page_size: 50 },
      })
      .then(({ data }) => {
        if (dead) return;
        const items = data?.items || [];
        // Attach a synthetic readiness for sort/UI. Existing aggregate rows
        // don't carry a readiness field today — Patch 2B.1 left this to a
        // follow-up. We compute a deterministic placeholder based on
        // document_count (more docs → higher readiness) as a stand-in.
        const enriched = items.map((it) => ({
          ...it,
          readiness_pct: typeof it.readiness_pct === "number"
            ? it.readiness_pct
            : Math.min(100, (it.document_count || 0) * 12 + (it.contributor_count || 0) * 10),
        }));
        enriched.sort((a, b) => (b.readiness_pct || 0) - (a.readiness_pct || 0));
        setSourceItems(enriched);
      })
      .catch(() => { if (!dead) setSourceItems([]); })
      .finally(() => { if (!dead) setSourceLoading(false); });
    return () => { dead = true; };
  }, [open, step, artefact, contextId]);

  const selectAllReady = () => {
    const ready = sourceItems.filter((it) => (it.readiness_pct || 0) >= 80);
    setSelectedSourceIds(new Set(ready.map((it) => it.id)));
  };

  const toggleSource = (id) => {
    setSelectedSourceIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // Contributors derived from the selected sources (deduplicated by id).
  const candidateContributors = useMemo(() => {
    const seen = new Map();
    for (const it of sourceItems) {
      if (!selectedSourceIds.has(it.id)) continue;
      const list = it.contributors || it.contributor_list || [];
      for (const c of list) {
        const cid = c?.id || c?.account_id || c?.email;
        if (!cid || seen.has(cid)) continue;
        seen.set(cid, {
          id: cid,
          name: c.name || c.display_name || c.email || cid,
          role: c.role,
        });
      }
    }
    // Fallback: if the rows don't carry a contributors array, surface
    // contributor_count as opaque placeholder rows. This keeps the surface
    // useful even before the aggregates expose individual contributors.
    if (seen.size === 0) {
      const totalAcrossSelected = sourceItems
        .filter((it) => selectedSourceIds.has(it.id))
        .reduce((acc, it) => acc + (it.contributor_count || 0), 0);
      for (let i = 0; i < totalAcrossSelected; i += 1) {
        const k = `placeholder-${i}`;
        seen.set(k, { id: k, name: `Contributor ${i + 1}`, role: null });
      }
    }
    return [...seen.values()];
  }, [sourceItems, selectedSourceIds]);

  const finalContributorIds = useMemo(
    () => candidateContributors.filter((c) => !excludedContribIds.has(c.id)).map((c) => c.id),
    [candidateContributors, excludedContribIds],
  );

  const cadencePayload = useMemo(() => {
    if (cadenceKind === "recurring") return { interval: recurringInterval };
    if (cadenceKind === "scheduled" && scheduledAt) return { scheduled_at: new Date(scheduledAt).toISOString() };
    return {};
  }, [cadenceKind, recurringInterval, scheduledAt]);

  const previewBullets = useMemo(() => agentCyclePreview({
    sources: sourceItems.filter((it) => selectedSourceIds.has(it.id)),
    contributors: candidateContributors.filter((c) => !excludedContribIds.has(c.id)),
    templateName: STANDARD_TEMPLATE.label,
    cadenceKind,
    cadencePayload,
    formats,
  }), [sourceItems, selectedSourceIds, candidateContributors, excludedContribIds, cadenceKind, cadencePayload, formats]);

  const canStepForward = (() => {
    if (step === 1) return !!artefactType && !!templateKey;
    if (step === 2) return selectedSourceIds.size > 0;
    if (step === 3) return true;
    if (step === 4) {
      if (!title.trim()) return false;
      if (formats.length === 0) return false;
      if (cadenceKind === "scheduled" && !scheduledAt) return false;
      return true;
    }
    return false;
  })();

  const submit = async () => {
    if (!canStepForward) return;
    setSubmitting(true);
    try {
      const body = {
        title: title.trim(),
        artefact_type: artefactType,
        template_key: templateKey,
        source_ids: [...selectedSourceIds],
        contributor_ids: finalContributorIds,
        cadence_kind: cadenceKind,
        cadence_payload: cadencePayload,
        formats,
      };
      const { data } = await api.post(
        `/contexts/${contextId}/work-studio/compilations`,
        body,
      );
      toast.success(`${body.title} is being compiled. Agent Cycle will surface progress in the rail.`);
      onCreated && onCreated(data);
      onClose && onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Could not commission Agent Cycle."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !submitting && onClose && onClose()}>
      <DialogContent className="max-w-2xl bg-[var(--parchment)]" data-testid="compilation-wizard">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[20px] text-[var(--ink)]">Compile with Agent Cycle</DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Four steps. We hold for your confirmation on each.
          </DialogDescription>
        </DialogHeader>

        <StepIndicator step={step} />

        {/* Step 1 — Artefact type + template */}
        {step === 1 && (
          <div className="space-y-4" data-testid="wizard-step-1">
            <div>
              <Label className="text-[12px] mb-2 block">Artefact type</Label>
              <div className="grid grid-cols-2 gap-2">
                {ARTEFACT_TYPES.map((t) => {
                  const Icon = t.icon;
                  const sel = artefactType === t.key;
                  return (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => setArtefactType(t.key)}
                      className={[
                        "text-left px-3 py-2.5 border rounded-sm flex items-center gap-2 text-[13px] transition-colors",
                        sel
                          ? "border-[var(--ink)] bg-white text-[var(--ink)]"
                          : "border-[var(--rule)] text-[var(--ink)] hover:border-[var(--ink)]/50",
                      ].join(" ")}
                      data-testid={`wizard-artefact-type-${t.key}${sel ? "-selected" : ""}`}
                    >
                      <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <Label className="text-[12px] mb-2 block">Template</Label>
              <button
                type="button"
                onClick={() => setTemplateKey("standard")}
                className={[
                  "w-full text-left px-3 py-2.5 border rounded-sm flex items-center justify-between text-[13px]",
                  templateKey === "standard"
                    ? "border-[var(--ink)] bg-white"
                    : "border-[var(--rule)] hover:border-[var(--ink)]/50",
                ].join(" ")}
                data-testid="wizard-template-standard"
              >
                <span>{STANDARD_TEMPLATE.label}</span>
                {templateKey === "standard"
                  ? <CheckCircle2 className="w-4 h-4 text-[var(--ink)]" />
                  : <Circle className="w-4 h-4 text-[var(--muted)]" />}
              </button>
              <p className="text-[11.5px] text-[var(--muted)] italic mt-1">
                More templates land in a future patch.
              </p>
            </div>
          </div>
        )}

        {/* Step 2 — Sources */}
        {step === 2 && (
          <div className="space-y-3" data-testid="wizard-step-2">
            <div className="flex items-center justify-between">
              <Label className="text-[12px]">Select source items</Label>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={selectAllReady}
                className="text-[12px] rounded-sm border-[var(--rule)]"
                data-testid="wizard-select-all-ready"
              >
                Select all ready
              </Button>
            </div>
            {sourceLoading && (
              <p className="text-[12.5px] text-[var(--muted)] inline-flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading sources…
              </p>
            )}
            {!sourceLoading && sourceItems.length === 0 && (
              <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="wizard-no-sources">
                No source items in this context yet. Create one first.
              </p>
            )}
            <div className="max-h-72 overflow-y-auto space-y-1.5" data-testid="wizard-source-list">
              {sourceItems.map((it) => {
                const sel = selectedSourceIds.has(it.id);
                const r = it.readiness_pct || 0;
                return (
                  <label
                    key={it.id}
                    className={[
                      "flex items-center gap-3 px-3 py-2 border rounded-sm cursor-pointer text-[13px]",
                      sel ? "border-[var(--ink)] bg-white" : "border-[var(--rule)] hover:border-[var(--ink)]/40",
                    ].join(" ")}
                    data-testid={`wizard-source-row${sel ? "-selected" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={sel}
                      onChange={() => toggleSource(it.id)}
                      data-testid={`wizard-source-checkbox-${it.id}`}
                    />
                    <span className="flex-1 truncate text-[var(--ink)]">{it.name || "Untitled"}</span>
                    <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
                      {it.kind?.replace("cycle_", "")?.replace(/_/g, " ") || "—"}
                    </span>
                    <span className="font-mono text-[12px] tabular-nums text-[var(--ink)] w-12 text-right">{r}%</span>
                    <span className="text-[11px] font-mono text-[var(--muted)] w-12 text-right">
                      {shortAge(it.meeting_date || it.created_at)}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 3 — Contributors + preview */}
        {step === 3 && (
          <div className="space-y-4" data-testid="wizard-step-3">
            <div>
              <Label className="text-[12px] mb-2 block">Contributors</Label>
              {candidateContributors.length === 0 ? (
                <p className="text-[12.5px] text-[var(--muted)] italic">
                  No contributors implied by the selected sources.
                </p>
              ) : (
                <div className="max-h-40 overflow-y-auto space-y-1" data-testid="wizard-contributor-list">
                  {candidateContributors.map((c) => {
                    const excluded = excludedContribIds.has(c.id);
                    return (
                      <label key={c.id} className="flex items-center gap-2 px-2 py-1 text-[13px] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={!excluded}
                          onChange={() => {
                            setExcludedContribIds((prev) => {
                              const n = new Set(prev);
                              if (n.has(c.id)) n.delete(c.id); else n.add(c.id);
                              return n;
                            });
                          }}
                          data-testid={`wizard-contributor-checkbox-${c.id}`}
                        />
                        <span className="text-[var(--ink)]">{c.name}</span>
                        {c.role && <span className="text-[11px] font-mono text-[var(--muted)]">· {c.role}</span>}
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            <div
              className="border border-[var(--rule)] rounded-sm bg-white px-4 py-3"
              data-testid="wizard-agent-preview"
            >
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2">
                Agent Cycle preview
              </p>
              <ul className="space-y-1 text-[13px] text-[var(--ink)]">
                {previewBullets.map((b, i) => (
                  <li key={i} className="leading-snug" data-testid={`wizard-agent-preview-bullet-${i}`}>
                    · {b}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Step 4 — Cadence + format + title */}
        {step === 4 && (
          <div className="space-y-4" data-testid="wizard-step-4">
            <div>
              <Label className="text-[12px]" htmlFor="wizard-title">Output title</Label>
              <Input
                id="wizard-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="rounded-sm text-[13.5px] mt-1"
                data-testid="wizard-title"
              />
            </div>

            <div>
              <Label className="text-[12px] mb-2 block">Cadence</Label>
              <div className="space-y-1.5">
                {[
                  { k: "one_off",   label: "One-off" },
                  { k: "recurring", label: "Recurring" },
                  { k: "scheduled", label: "Scheduled" },
                ].map((c) => (
                  <label
                    key={c.k}
                    className={[
                      "flex items-center gap-2 px-3 py-2 border rounded-sm cursor-pointer text-[13px]",
                      cadenceKind === c.k ? "border-[var(--ink)] bg-white" : "border-[var(--rule)]",
                    ].join(" ")}
                  >
                    <input
                      type="radio"
                      checked={cadenceKind === c.k}
                      onChange={() => setCadenceKind(c.k)}
                      data-testid={`wizard-cadence-${c.k}`}
                    />
                    {c.label}
                  </label>
                ))}
              </div>
              {cadenceKind === "recurring" && (
                <select
                  value={recurringInterval}
                  onChange={(e) => setRecurringInterval(e.target.value)}
                  className="mt-2 w-full border border-[var(--rule)] rounded-sm px-2 py-2 text-[13px] bg-white"
                  data-testid="wizard-cadence-interval"
                >
                  {["weekly", "fortnightly", "monthly", "quarterly"].map((i) => (
                    <option key={i} value={i}>{i}</option>
                  ))}
                </select>
              )}
              {cadenceKind === "scheduled" && (
                <Input
                  type="date"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  className="mt-2 rounded-sm text-[13.5px]"
                  data-testid="wizard-cadence-date"
                />
              )}
            </div>

            <div>
              <Label className="text-[12px] mb-2 block">Format</Label>
              <div className="flex flex-wrap gap-2">
                {FORMATS.map((f) => {
                  const on = formats.includes(f);
                  return (
                    <button
                      key={f}
                      type="button"
                      onClick={() => {
                        setFormats((prev) => {
                          if (prev.includes(f)) return prev.filter((x) => x !== f);
                          return [...prev, f];
                        });
                      }}
                      className={[
                        "px-3 py-1.5 text-[12px] uppercase tracking-[0.16em] font-mono rounded-sm border",
                        on
                          ? "bg-[var(--ink)] text-[var(--parchment)] border-[var(--ink)]"
                          : "bg-white text-[var(--ink)] border-[var(--rule)]",
                      ].join(" ")}
                      data-testid={`wizard-format-${f}${on ? "-on" : ""}`}
                    >
                      {f}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="flex items-center justify-between gap-2 mt-2">
          {step > 1 ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              disabled={submitting}
              data-testid="wizard-back"
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Back
            </Button>
          ) : (
            <span className="flex-1" />
          )}

          {step < 4 ? (
            <Button
              type="button"
              onClick={() => setStep((s) => Math.min(4, s + 1))}
              disabled={!canStepForward || submitting}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
              data-testid="wizard-next"
            >
              Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          ) : (
            <Button
              type="button"
              onClick={submit}
              disabled={!canStepForward || submitting}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
              data-testid="wizard-submit"
            >
              {submitting && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
              Commission Agent Cycle
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
