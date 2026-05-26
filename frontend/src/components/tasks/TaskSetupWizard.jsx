/**
 * TaskSetupWizard — Phase F.2 (2026-05-26).
 *
 * 4-step wizard:
 *   Step 1 — Name + Objective + Success criteria (agent pre-fill)
 *   Step 2 — Output specification (template gallery OR free text)
 *   Step 3 — Team + Contributions
 *   Step 4 — Preview + Save Draft / Commission
 *
 * Pre-fill is best-effort via /api/tasks/agent-prefill (Shield-bounded);
 * if it fails the user can still fill manually.
 *
 * F.5 (contributor modes — magic link, email reply) is queued — for
 * F.2, contribution_mode is captured as a per-row dropdown that
 * persists into the task record; magic-link generation + email-reply
 * ingestion ship later.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Wand2, X, Plus, ChevronLeft, ChevronRight, FileText, Check } from "lucide-react";
import { toast } from "sonner";


// Template gallery — used by Step 2.
const TEMPLATES = [
  { id: "board_pack",     name: "Board Pack",      desc: "Performance, risk, strategy progress, governance updates.", formats: ["pdf", "docx"] },
  { id: "committee_pack", name: "Committee Pack",  desc: "Reading, recommendations, and decisions for a sitting.",    formats: ["pdf", "docx"] },
  { id: "strategy_deck",  name: "Strategy Deck",   desc: "Decision-ready narrative the board can challenge.",         formats: ["pptx"] },
  { id: "financial_model",name: "Financial Model", desc: "Driver-based model with sensitivities.",                    formats: ["xlsx", "pdf"] },
  { id: "fundraising",    name: "Fundraising Deck",desc: "Investor deck + supporting model.",                         formats: ["pptx", "pdf"] },
  { id: "briefing",       name: "Briefing",        desc: "Single-page concise brief for a stakeholder.",              formats: ["pdf"] },
  { id: "custom",         name: "Custom",          desc: "Describe your own output.",                                 formats: ["pdf"] },
];


// Default team rosters per template — used as Step 3 pre-fill.
const TEMPLATE_ROSTERS = {
  board_pack: [
    { name: "", role: "CFO", email: "", contribution: "Financial performance + balance-sheet update" },
    { name: "", role: "General Counsel", email: "", contribution: "Governance update + legal risks" },
    { name: "", role: "CEO", email: "", contribution: "Executive summary + strategy review" },
    { name: "", role: "Board Chair", email: "", contribution: "Chair foreword + sign-off" },
  ],
  committee_pack: [
    { name: "", role: "Committee Chair", email: "", contribution: "Foreword + chair sign-off" },
    { name: "", role: "Subject lead", email: "", contribution: "Topic deep-dive + recommendation" },
  ],
  strategy_deck: [
    { name: "", role: "Strategy Lead", email: "", contribution: "Narrative arc + assumptions" },
    { name: "", role: "CFO", email: "", contribution: "Financial implications" },
  ],
  fundraising: [
    { name: "", role: "CEO", email: "", contribution: "Founder vision + traction" },
    { name: "", role: "CFO", email: "", contribution: "Model + use of funds" },
  ],
  financial_model: [
    { name: "", role: "FP&A", email: "", contribution: "Driver inputs + sensitivities" },
  ],
  briefing: [{ name: "", role: "Author", email: "", contribution: "One-page brief" }],
  custom: [],
};


function StepHeader({ step }) {
  const steps = [
    { n: 1, label: "Define" },
    { n: 2, label: "Output" },
    { n: 3, label: "Team" },
    { n: 4, label: "Commission" },
  ];
  return (
    <div className="flex items-center gap-3 mb-6" data-testid="task-wizard-step-header">
      {steps.map((s, i) => (
        <React.Fragment key={s.n}>
          <div className={`flex items-center gap-1.5 ${step === s.n ? "text-[var(--ink)]" : "text-[var(--muted)]"}`}>
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono ${
                step >= s.n ? "bg-[var(--ink)] text-white" : "bg-[var(--parchment)] text-[var(--muted)]"
              }`}
              data-testid={`task-wizard-step-pip-${s.n}`}
            >
              {step > s.n ? <Check className="w-3 h-3" /> : s.n}
            </span>
            <span className="text-[11px] uppercase tracking-[0.14em] font-mono">{s.label}</span>
          </div>
          {i < steps.length - 1 && (
            <span className="flex-1 h-px bg-[var(--rule)]" />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}


export default function TaskSetupWizard({ open, onClose, onCreated, contextId }) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [criteria, setCriteria] = useState("");
  const [prefillState, setPrefillState] = useState({ loading: false, source: null });
  // Step 2
  const [outputKind, setOutputKind] = useState("template"); // "template" | "free_text"
  const [templateId, setTemplateId] = useState(null);
  const [freeText, setFreeText] = useState("");
  const [formats, setFormats] = useState(["pdf"]);
  const [dueDate, setDueDate] = useState("");
  // Step 3
  const [team, setTeam] = useState([]);
  // Step 4
  const [committing, setCommitting] = useState(false);

  // Reset on open/close.
  useEffect(() => {
    if (open) {
      setStep(1); setName(""); setObjective(""); setCriteria("");
      setOutputKind("template"); setTemplateId(null); setFreeText("");
      setFormats(["pdf"]); setDueDate(""); setTeam([]);
      setPrefillState({ loading: false, source: null });
    }
  }, [open]);

  // When user picks a template, seed formats + the team roster.
  useEffect(() => {
    if (!templateId) return;
    const tpl = TEMPLATES.find((t) => t.id === templateId);
    if (tpl) setFormats(tpl.formats);
    setTeam(TEMPLATE_ROSTERS[templateId] || []);
  }, [templateId]);

  const onAgentPrefill = async () => {
    if (!name.trim()) return;
    setPrefillState({ loading: true, source: null });
    try {
      const { data } = await api.post("/tasks/agent-prefill", { name: name.trim() });
      if (data.objective && !objective) setObjective(data.objective);
      if (data.success_criteria && !criteria) setCriteria(data.success_criteria);
      setPrefillState({ loading: false, source: data.source || "none" });
    } catch (e) {
      setPrefillState({ loading: false, source: null });
      toast.error(apiErrorMessage(e));
    }
  };

  const canAdvance = useMemo(() => {
    if (step === 1) return name.trim().length > 0;
    if (step === 2) {
      if (outputKind === "template") return !!templateId;
      return freeText.trim().length > 5;
    }
    if (step === 3) return true;     // Team is optional; can be filled later.
    return true;
  }, [step, name, outputKind, templateId, freeText]);

  const addRow = () => setTeam((rows) => [
    ...rows,
    { name: "", role: "", email: "", contribution: "", due_date: "", contribution_mode: "akki_account" },
  ]);
  const updateRow = (i, patch) => setTeam((rows) => rows.map((r, idx) => idx === i ? { ...r, ...patch } : r));
  const removeRow = (i) => setTeam((rows) => rows.filter((_, idx) => idx !== i));

  const submit = async (commission) => {
    setCommitting(true);
    const payload = {
      name: name.trim(),
      objective: objective.trim(),
      success_criteria: criteria.trim(),
      output_spec: {
        kind:           outputKind,
        template_id:    outputKind === "template" ? templateId : null,
        free_text:      outputKind === "free_text" ? freeText.trim() : null,
        formats,
        final_due_date: dueDate || null,
      },
      team,
      state: commission ? "active" : "draft",
      due_date: dueDate || null,
      context_id: contextId || null,
    };
    try {
      const { data } = await api.post("/tasks", payload);
      toast.success(commission ? "Task commissioned." : "Saved as draft.");
      onCreated?.(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setCommitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent
        className="max-w-3xl w-[92vw] max-h-[90vh] overflow-y-auto p-6"
        data-testid="task-wizard-modal"
      >
        <button
          type="button" onClick={() => onClose?.()}
          className="absolute right-4 top-4 text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="task-wizard-close"
        >
          <X className="w-4 h-4" />
        </button>
        <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-1">
          New task
        </p>
        <h2 className="akki-serif text-[22px] text-[var(--ink)] mb-5">Set up a new task</h2>
        <StepHeader step={step} />

        {/* ── Step 1: Define ──────────────────────────────────────── */}
        {step === 1 && (
          <div className="space-y-4" data-testid="task-wizard-step-1">
            <div>
              <label className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                Task name
              </label>
              <div className="flex gap-2 mt-1">
                <Input
                  value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Q4 Board Pack"
                  data-testid="task-wizard-name-input"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onAgentPrefill}
                  disabled={!name.trim() || prefillState.loading}
                  data-testid="task-wizard-prefill"
                >
                  {prefillState.loading
                    ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" />
                    : <Wand2 className="w-3 h-3 mr-1.5" />}
                  Pre-fill
                </Button>
              </div>
              {prefillState.source && (
                <p
                  className="text-[10.5px] font-mono text-[var(--muted)] mt-1"
                  data-testid="task-wizard-prefill-source"
                >
                  Source: {prefillState.source}
                </p>
              )}
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                Objective
              </label>
              <Textarea
                value={objective} onChange={(e) => setObjective(e.target.value)}
                rows={3}
                placeholder="What does this task achieve?"
                data-testid="task-wizard-objective-input"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                Success criteria
              </label>
              <Textarea
                value={criteria} onChange={(e) => setCriteria(e.target.value)}
                rows={3}
                placeholder="How will you know it's done well?"
                data-testid="task-wizard-criteria-input"
                className="mt-1"
              />
            </div>
          </div>
        )}

        {/* ── Step 2: Output ──────────────────────────────────────── */}
        {step === 2 && (
          <div className="space-y-4" data-testid="task-wizard-step-2">
            <p className="text-[12.5px] text-[var(--ink)]">What does done look like?</p>
            <div className="flex gap-2 text-[11px] font-mono">
              <button
                type="button" onClick={() => setOutputKind("template")}
                className={`px-2.5 py-1 rounded-sm border ${outputKind === "template" ? "border-[var(--ink)] text-[var(--ink)]" : "border-[var(--rule)] text-[var(--muted)]"}`}
                data-testid="task-wizard-output-mode-template"
              >Template gallery</button>
              <button
                type="button" onClick={() => setOutputKind("free_text")}
                className={`px-2.5 py-1 rounded-sm border ${outputKind === "free_text" ? "border-[var(--ink)] text-[var(--ink)]" : "border-[var(--rule)] text-[var(--muted)]"}`}
                data-testid="task-wizard-output-mode-free"
              >Free text</button>
            </div>

            {outputKind === "template" ? (
              <div className="grid grid-cols-2 gap-2" data-testid="task-wizard-template-gallery">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTemplateId(t.id)}
                    className={`text-left p-3 rounded-sm border transition-colors ${
                      templateId === t.id
                        ? "border-[var(--ink)] bg-[var(--cream-deep)]"
                        : "border-[var(--rule)] hover:border-[var(--ink)]"
                    }`}
                    data-testid={`task-wizard-template-${t.id}`}
                  >
                    <p className="text-[13px] text-[var(--ink)] mb-1">{t.name}</p>
                    <p className="text-[11.5px] text-[var(--muted)] leading-relaxed">{t.desc}</p>
                  </button>
                ))}
              </div>
            ) : (
              <Textarea
                value={freeText} onChange={(e) => setFreeText(e.target.value)}
                rows={5}
                placeholder="Describe the output in your own words…"
                data-testid="task-wizard-free-text"
              />
            )}

            {(templateId || (outputKind === "free_text" && freeText.trim())) && (
              <div className="border-t border-[var(--rule)] pt-3 grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                    Final due date
                  </label>
                  <Input
                    type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)}
                    data-testid="task-wizard-due-date" className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                    Formats
                  </label>
                  <div className="flex gap-2 mt-2" data-testid="task-wizard-formats">
                    {["pdf", "docx", "pptx", "xlsx"].map((f) => (
                      <label
                        key={f}
                        className="inline-flex items-center gap-1 text-[12px] font-mono cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={formats.includes(f)}
                          onChange={(e) => {
                            if (e.target.checked) setFormats((p) => [...new Set([...p, f])]);
                            else setFormats((p) => p.filter((x) => x !== f));
                          }}
                          data-testid={`task-wizard-format-${f}`}
                        />
                        {f.toUpperCase()}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Step 3: Team ────────────────────────────────────────── */}
        {step === 3 && (
          <div className="space-y-4" data-testid="task-wizard-step-3">
            <p className="text-[12.5px] text-[var(--ink)]">Who's involved?</p>
            <div className="border border-[var(--rule)] rounded-sm overflow-hidden">
              <table className="w-full text-[12px]" data-testid="task-wizard-team-table">
                <thead className="bg-[var(--parchment)] text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                  <tr>
                    <th className="text-left p-2">Name</th>
                    <th className="text-left p-2">Role</th>
                    <th className="text-left p-2">Email</th>
                    <th className="text-left p-2">Mode</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {team.map((r, i) => (
                    <tr key={i} className="border-t border-[var(--rule)]" data-testid={`task-wizard-team-row-${i}`}>
                      <td className="p-1.5"><Input value={r.name || ""} onChange={(e) => updateRow(i, { name: e.target.value })} className="h-7 text-[12px]" /></td>
                      <td className="p-1.5"><Input value={r.role || ""} onChange={(e) => updateRow(i, { role: e.target.value })} className="h-7 text-[12px]" /></td>
                      <td className="p-1.5"><Input value={r.email || ""} onChange={(e) => updateRow(i, { email: e.target.value })} className="h-7 text-[12px]" /></td>
                      <td className="p-1.5">
                        <select
                          value={r.contribution_mode || "akki_account"}
                          onChange={(e) => updateRow(i, { contribution_mode: e.target.value })}
                          className="h-7 text-[11.5px] border border-[var(--rule)] rounded-sm px-1"
                          data-testid={`task-wizard-team-mode-${i}`}
                        >
                          <option value="akki_account">Akki account</option>
                          <option value="magic_link">Magic link</option>
                          <option value="email_reply">Email reply</option>
                        </select>
                      </td>
                      <td className="p-1.5 text-right">
                        <button type="button" onClick={() => removeRow(i)} className="text-[var(--muted)] hover:text-[var(--oxblood)]">
                          <X className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Button variant="outline" size="sm" onClick={addRow} data-testid="task-wizard-add-team-member">
              <Plus className="w-3 h-3 mr-1.5" /> Add team member
            </Button>
          </div>
        )}

        {/* ── Step 4: Commission ──────────────────────────────────── */}
        {step === 4 && (
          <div className="space-y-4" data-testid="task-wizard-step-4">
            <p className="text-[12.5px] text-[var(--ink)]">Preview</p>
            <div className="border border-[var(--rule)] rounded-sm p-4 space-y-3 bg-[var(--parchment)]">
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">Task</p>
                <p className="akki-serif text-[16px] text-[var(--ink)]">{name || "—"}</p>
              </div>
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">Objective</p>
                <p className="text-[12.5px] text-[var(--ink)]">{objective || "—"}</p>
              </div>
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">Output</p>
                <p className="text-[12.5px] text-[var(--ink)]">
                  {outputKind === "template"
                    ? (TEMPLATES.find((t) => t.id === templateId)?.name || "—")
                    : (freeText || "—")}{" "}
                  · <span className="font-mono text-[11px]">{formats.join(", ").toUpperCase()}</span>
                  {dueDate ? ` · Due ${dueDate}` : ""}
                </p>
              </div>
              <div>
                <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">Team</p>
                <p className="text-[12.5px] text-[var(--ink)]">
                  {team.length === 0 ? "—" : team.map((m) => `${m.name || m.email || "?"}${m.role ? ` (${m.role})` : ""}`).join(", ")}
                </p>
              </div>
            </div>
            <p className="text-[11.5px] italic text-[var(--muted)]">
              Save as Draft now to come back later. Commission to begin agent monitoring and notify contributors.
            </p>
          </div>
        )}

        {/* ── Footer nav ──────────────────────────────────────────── */}
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-[var(--rule)]">
          {step > 1 ? (
            <Button variant="ghost" size="sm" onClick={() => setStep((s) => s - 1)} data-testid="task-wizard-back">
              <ChevronLeft className="w-3 h-3 mr-1" /> Back
            </Button>
          ) : <span />}
          {step < 4 ? (
            <Button
              size="sm"
              onClick={() => setStep((s) => s + 1)}
              disabled={!canAdvance}
              data-testid="task-wizard-next"
            >
              Next <ChevronRight className="w-3 h-3 ml-1" />
            </Button>
          ) : (
            <div className="flex gap-2">
              <Button
                variant="outline" size="sm"
                onClick={() => submit(false)}
                disabled={committing}
                data-testid="task-wizard-save-draft"
              >
                {committing ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : null}
                Save as Draft
              </Button>
              <Button
                size="sm"
                onClick={() => submit(true)}
                disabled={committing}
                className="bg-[var(--oxblood)] hover:bg-[var(--oxblood-deep)] text-white"
                data-testid="task-wizard-commission"
              >
                {committing ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : null}
                Commission
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
