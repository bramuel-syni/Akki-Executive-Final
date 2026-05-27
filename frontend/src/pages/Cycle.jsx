/**
 * Cycle.jsx — Phase D rewire (MEMO Item 3, D-001).
 *
 * The Executive Cycle Manager is a six-step drafting engine:
 *
 *     Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation
 *
 * Each step is a self-contained editor inside a single-column
 * akki-w-medium frame. Forward/back navigation is explicit; the user
 * can jump to any step that has prerequisites met. State is server-
 * persisted via /api/contexts/{cid}/cycle/* — refreshing the page
 * never loses work.
 *
 * Restraint copy throughout — banned-word grep clean.
 */
import React, { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
// Phase E.3 (2026-05-26) — Universal Document Drawer.
import DocumentDrawer from "@/components/documents/DocumentDrawer";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { pollJob } from "@/lib/pollJob";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Sparkles, ChevronLeft, ChevronRight, Plus, X, Loader2,
  Mail, FileDown, Check, AlertCircle, Users, ListChecks, CheckCircle2,
  ClipboardList, Send, Download, MessageSquare, Pencil,
  Paperclip, FileText,
} from "lucide-react";
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import JudgementPanel from "@/components/cycle/JudgementPanel";
// Phase L.b.2 (2026-05-27) — StreamingLogScene driver for the Compile step.
import StreamingLogScene from "@/components/transitions/StreamingLogScene";
import usePhasedTimer from "@/hooks/usePhasedTimer";
import BoardSubmitPanel from "@/components/cycle/BoardSubmitPanel";
import CycleBreadcrumb from "@/components/cycle/CycleBreadcrumb";
import CycleStepNav from "@/components/cycle/CycleStepNav";
import AddTeamMemberDialog from "@/components/cycle/AddTeamMemberDialog";
import TeamCatalogueDialog from "@/components/cycle/TeamCatalogueDialog";
// Chunk 9 (2026-05-18) — Add-a-Contribution attach feature
// (QA-2026-05-16-017…-021). Inlined per dispatch decision #2.
import ContributionAttachPicker from "@/components/cycle/ContributionAttachPicker";
import { activateCycle, closeCycle, getCycle, listEligibleContributors } from "@/lib/cycleApi";
import { takeToSolva } from "@/lib/takeToSolva";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";

/** Returns `?cycle_id=...` (or `&cycle_id=...`) when cycleId is set. */
function qcid(cycleId, leading = "?") {
  if (!cycleId) return "";
  return `${leading}cycle_id=${encodeURIComponent(cycleId)}`;
}

const STEPS = [
  { id: "agenda",        label: "Agenda",        icon: ClipboardList, act: "setup" },
  { id: "team",          label: "Team",          icon: Users,         act: "setup" },
  { id: "contributions", label: "Contributions", icon: ListChecks,    act: "run"   },
  { id: "scoreboard",    label: "Scoreboard",    icon: CheckCircle2,  act: "run"   },
  { id: "followups",     label: "Follow-ups",    icon: Mail,          act: "run"   },
  { id: "compilation",   label: "Compilation",   icon: FileDown,      act: "ship"  },
];

// Phase D.3 — three-act grouping above the six-step strip.
// Setup = define the cycle (agenda, team).
// Run   = execute it (gather, score, chase).
// Ship  = produce the deliverable (compile).
const ACTS = [
  { id: "setup", label: "Setup", subtitle: "Agenda · Team" },
  { id: "run",   label: "Run",   subtitle: "Contributions · Scoreboard · Follow-ups" },
  { id: "ship",  label: "Ship",  subtitle: "Compilation" },
];

const STATUS_TONE = {
  ready:    "text-emerald-800 bg-emerald-50 border-emerald-200",
  thin:     "text-amber-900 bg-amber-50 border-amber-200",
  weak:     "text-amber-900 bg-amber-50 border-amber-200",
  missing:  "text-[color:var(--oxblood)] bg-[color:var(--oxblood)]/10 border-[color:var(--oxblood)]/30",
};

/* ------------------------------------------------------------------ */
/* Step header — shared shell for each step                           */
/* ------------------------------------------------------------------ */
function StepShell({ activeId, onSelect, children, busy }) {
  const activeAct = STEPS.find((s) => s.id === activeId)?.act || "setup";
  return (
    <>
      {/* Phase D.3 — Setup/Run/Ship act-pill bar wrapping the existing
          six-step strip. Clicking a pill jumps to that act's first
          unfinished step (or its first step, if all are pristine). */}
      <nav
        className="flex items-center gap-2 mb-3"
        data-testid="cycle-act-bar"
        aria-label="Cycle acts"
      >
        {ACTS.map((act) => {
          const isActive = activeAct === act.id;
          const firstStepInAct = STEPS.find((s) => s.act === act.id);
          return (
            <button
              key={act.id}
              type="button"
              onClick={() => firstStepInAct && onSelect(firstStepInAct.id)}
              disabled={busy}
              className={`px-3.5 py-1.5 rounded-full border text-[12.5px] inline-flex items-center gap-2 transition-colors ${
                isActive
                  ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                  : "border-[var(--rule)] bg-white text-[var(--ink)] hover:border-[var(--accent)]"
              }`}
              data-testid={`cycle-act-pill-${act.id}${isActive ? "-active" : ""}`}
              aria-current={isActive ? "step" : undefined}
              title={act.subtitle}
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] opacity-80">
                {act.id === "setup" ? "01" : act.id === "run" ? "02" : "03"}
              </span>
              <span className="font-medium">{act.label}</span>
              <span className={`hidden md:inline text-[11px] ${isActive ? "opacity-90" : "text-[var(--muted)]"}`}>
                · {act.subtitle}
              </span>
            </button>
          );
        })}
      </nav>

      <nav className="flex items-stretch gap-0 mb-6 border-b border-[var(--rule)]" data-testid="cycle-stepper" role="tablist">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const isActive = activeId === s.id;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelect(s.id)}
              disabled={busy}
              className={`flex-1 px-3 py-3 text-[13px] inline-flex items-center justify-center gap-2 border-b-2 -mb-px transition-colors ${
                isActive
                  ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              data-testid={`cycle-step-tab-${s.id}${isActive ? "-active" : ""}`}
            >
              <span className="font-mono text-[10px] tracking-[0.18em] text-[var(--muted)]">0{i + 1}</span>
              <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
              {s.label}
            </button>
          );
        })}
      </nav>
      {children}
    </>
  );
}

function StepFooter({ canBack, canForward, onBack, onForward, primaryLabel, onPrimary, primaryBusy }) {
  return (
    <div className="flex items-center justify-between mt-8 pt-4 border-t border-[var(--rule)]" data-testid="cycle-step-footer">
      <Button variant="ghost" size="sm" onClick={onBack} disabled={!canBack} className="text-[12.5px]" data-testid="cycle-step-back">
        <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Back
      </Button>
      <div className="flex gap-2">
        {primaryLabel && (
          <Button
            size="sm" onClick={onPrimary} disabled={primaryBusy}
            className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
            data-testid="cycle-step-primary"
          >
            {primaryBusy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
            {primaryLabel}
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onForward} disabled={!canForward} className="text-[12.5px]" data-testid="cycle-step-forward">
          Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Step 1 — Agenda                                                    */
/* ------------------------------------------------------------------ */
function AgendaStep({ cid, cycleId, agenda, onSaved, onForward }) {
  const [title, setTitle] = useState(agenda?.title || "Main board reporting cycle");
  const [items, setItems] = useState(agenda?.items?.length ? agenda.items : [
    { id: null, label: "", owner_label: "" },
  ]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setTitle(agenda?.title || "Main board reporting cycle");
    setItems(agenda?.items?.length ? agenda.items : [{ id: null, label: "", owner_label: "" }]);
  }, [agenda?.id]);

  const addItem = () => setItems((p) => [...p, { id: null, label: "", owner_label: "" }]);
  const removeItem = (idx) => setItems((p) => p.filter((_, i) => i !== idx));
  const updateItem = (idx, key, val) => setItems((p) => p.map((it, i) => i === idx ? { ...it, [key]: val } : it));

  const onSave = async () => {
    if (!title.trim()) { toast.error("Title is required."); return; }
    const itemsClean = items.map((it) => ({ id: it.id, label: it.label.trim(), owner_label: (it.owner_label || "").trim() })).filter((it) => it.label);
    if (!itemsClean.length) { toast.error("Add at least one agenda item."); return; }
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${cid}/cycle/agenda${qcid(cycleId)}`, { title: title.trim(), items: itemsClean });
      toast.success("Agenda saved.");
      onSaved(data);
      onForward();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <section data-testid="cycle-step-agenda">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Set the reporting agenda.</h2>
      <p className="akki-meta mb-5">Pick the items the board needs in front of them. Two to five works for most cycles.</p>
      <div className="space-y-4">
        <div>
          <Label className="text-[12px]" htmlFor="cycle-agenda-title">Cycle title</Label>
          <Input id="cycle-agenda-title" value={title} onChange={(e) => setTitle(e.target.value)} className="rounded-sm mt-1" data-testid="cycle-agenda-title" />
        </div>
        <div className="space-y-3" data-testid="cycle-agenda-items">
          {items.map((it, i) => (
            <div key={i} className="flex gap-2 items-start" data-testid={`cycle-agenda-item-${i}`}>
              <Input
                value={it.label}
                onChange={(e) => updateItem(i, "label", e.target.value)}
                placeholder="e.g. Covenant headroom review"
                className="rounded-sm flex-1"
              />
              <Input
                value={it.owner_label}
                onChange={(e) => updateItem(i, "owner_label", e.target.value)}
                placeholder="Owner (optional)"
                className="rounded-sm w-[200px]"
              />
              <Button type="button" size="sm" variant="ghost" onClick={() => removeItem(i)} className="text-[var(--muted)] hover:text-[color:var(--oxblood)]"><X className="w-3.5 h-3.5" /></Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={addItem} className="text-[12.5px] rounded-sm" data-testid="cycle-agenda-add-item">
            <Plus className="w-3.5 h-3.5 mr-1" /> Add item
          </Button>
        </div>
      </div>
      <StepFooter canBack={false} canForward={true} onForward={onForward} primaryLabel="Save agenda" onPrimary={onSave} primaryBusy={busy} />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Step 2 — Team                                                      */
/* ------------------------------------------------------------------ */
function TeamStep({ cid, cycleId, agenda, members, refresh, onBack, onForward }) {
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({ name: "", email: "", role: "", contribution_description: "", owns_item_ids: [] });
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState(null);
  const [editBusy, setEditBusy] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);  // {id, name} when AlertDialog is open
  const [deleteBusy, setDeleteBusy] = useState(false);
  const items = agenda?.items || [];

  const toggleItem = (id) => setDraft((p) => ({
    ...p,
    owns_item_ids: p.owns_item_ids.includes(id) ? p.owns_item_ids.filter((x) => x !== id) : [...p.owns_item_ids, id],
  }));

  const toggleEditItem = (id) => setEditDraft((p) => ({
    ...p,
    owns_item_ids: p.owns_item_ids.includes(id) ? p.owns_item_ids.filter((x) => x !== id) : [...p.owns_item_ids, id],
  }));

  const onAdd = async () => {
    if (!draft.name.trim() || !draft.email.trim() || !draft.contribution_description.trim()) {
      toast.error("Name, email, and contribution description are required."); return;
    }
    setBusy(true);
    try {
      await api.post(`/contexts/${cid}/cycle/team${qcid(cycleId)}`, draft);
      toast.success("Member added.");
      setDraft({ name: "", email: "", role: "", contribution_description: "", owns_item_ids: [] });
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setBusy(false); }
  };

  const startEdit = (m) => {
    setEditingId(m.id);
    setEditDraft({
      name: m.name || "",
      email: m.email || "",
      role: m.role || "",
      contribution_description: m.contribution_description || "",
      owns_item_ids: Array.isArray(m.owns_item_ids) ? [...m.owns_item_ids] : [],
    });
  };
  const cancelEdit = () => { setEditingId(null); setEditDraft(null); };

  const saveEdit = async () => {
    if (!editDraft) return;
    if (!editDraft.name.trim() || !editDraft.email.trim() || !editDraft.contribution_description.trim()) {
      toast.error("Name, email, and contribution description are required."); return;
    }
    setEditBusy(true);
    try {
      await api.patch(`/contexts/${cid}/cycle/team/${editingId}${qcid(cycleId)}`, {
        name: editDraft.name.trim(),
        email: editDraft.email.trim(),
        role: editDraft.role.trim() || null,
        contribution_description: editDraft.contribution_description.trim(),
        owns_item_ids: editDraft.owns_item_ids,
      });
      toast.success("Member updated.");
      cancelEdit();
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setEditBusy(false); }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    try {
      await api.delete(`/contexts/${cid}/cycle/team/${deleteTarget.id}${qcid(cycleId)}`);
      toast.success(`Removed ${deleteTarget.name}.`);
      setDeleteTarget(null);
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setDeleteBusy(false); }
  };

  const [addOpen, setAddOpen] = useState(false);
  const [catOpen, setCatOpen] = useState(false);

  return (
    <section data-testid="cycle-step-team">
      <div className="flex items-end justify-between gap-3 mb-5">
        <div className="flex-1">
          <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Build the team.</h2>
          <p className="akki-meta">Add the people contributing material — describe what each one is delivering.</p>
        </div>
        {cycleId && (
          <div className="flex items-center gap-2">
            <Button
              type="button" size="sm" variant="outline"
              onClick={() => setCatOpen(true)}
              className="text-[12.5px]"
              data-testid="cycle-team-manage-catalogue"
            >
              Manage Catalogue
            </Button>
            <Button
              type="button" size="sm"
              onClick={() => setAddOpen(true)}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white text-[12.5px]"
              data-testid="cycle-team-add-dialog"
            >
              + Add Team Member
            </Button>
          </div>
        )}
      </div>
      {cycleId && (
        <>
          <AddTeamMemberDialog
            open={addOpen}
            onOpenChange={setAddOpen}
            contextId={cid}
            cycleId={cycleId}
            agendaItems={items}
            agendaItemId={null}
            onAdded={refresh}
          />
          <TeamCatalogueDialog
            open={catOpen}
            onOpenChange={setCatOpen}
            contextId={cid}
          />
        </>
      )}
      {members.length > 0 && (
        <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-md bg-white mb-5" data-testid="cycle-team-list">
          {members.map((m) => {
            const isEditing = editingId === m.id;
            return (
              <li key={m.id} className="px-4 py-3" data-testid={`cycle-team-row-${m.id}`}>
                {!isEditing ? (
                  <>
                    <div className="flex items-baseline justify-between gap-3 mb-1 flex-wrap">
                      <p className="akki-serif text-[14px] text-[var(--ink)]">{m.name} <span className="text-[12px] text-[var(--muted)] font-mono">· {m.email}</span></p>
                      <div className="flex items-center gap-1">
                        <Button
                          type="button" size="sm" variant="ghost"
                          onClick={() => startEdit(m)}
                          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] h-7"
                          data-testid={`cycle-team-edit-${m.id}`}
                          aria-label={`Edit ${m.name}`}
                        ><Pencil className="w-3.5 h-3.5" /></Button>
                        <Button
                          type="button" size="sm" variant="ghost"
                          onClick={() => setDeleteTarget({ id: m.id, name: m.name })}
                          className="text-[12px] text-[var(--muted)] hover:text-[color:var(--oxblood)] h-7"
                          data-testid={`cycle-team-remove-${m.id}`}
                          aria-label={`Remove ${m.name}`}
                        ><X className="w-3.5 h-3.5" /></Button>
                      </div>
                    </div>
                    {m.role && <p className="text-[11.5px] text-[var(--muted)] mb-1">{m.role}</p>}
                    <p className="text-[12.5px] text-[var(--ink)] leading-[1.55]">{m.contribution_description}</p>
                    {m.owns_item_ids?.length > 0 && (
                      <p className="text-[11px] text-[var(--muted)] mt-1 font-mono">Owns: {m.owns_item_ids.map((id) => items.find((it) => it.id === id)?.label || "(missing)").join(" · ")}</p>
                    )}
                  </>
                ) : (
                  <div className="space-y-2.5" data-testid={`cycle-team-edit-form-${m.id}`}>
                    <p className="akki-overline text-[var(--muted)]">Edit member</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <Input placeholder="Name" value={editDraft.name} onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })} className="rounded-sm" data-testid={`cycle-team-edit-name-${m.id}`} />
                      <Input placeholder="Email" type="email" value={editDraft.email} onChange={(e) => setEditDraft({ ...editDraft, email: e.target.value })} className="rounded-sm" data-testid={`cycle-team-edit-email-${m.id}`} />
                      <Input placeholder="Role (optional)" value={editDraft.role} onChange={(e) => setEditDraft({ ...editDraft, role: e.target.value })} className="rounded-sm" data-testid={`cycle-team-edit-role-${m.id}`} />
                    </div>
                    <Textarea
                      value={editDraft.contribution_description}
                      onChange={(e) => setEditDraft({ ...editDraft, contribution_description: e.target.value })}
                      className="rounded-sm min-h-[64px]"
                      data-testid={`cycle-team-edit-desc-${m.id}`}
                    />
                    {items.length > 0 && (
                      <div>
                        <p className="text-[11px] text-[var(--muted)] mb-1.5">Owns agenda items:</p>
                        <div className="flex flex-wrap gap-1.5">
                          {items.map((it) => {
                            const on = editDraft.owns_item_ids.includes(it.id);
                            return (
                              <button key={it.id} type="button" onClick={() => toggleEditItem(it.id)}
                                className={`text-[11.5px] px-2.5 py-1 rounded-full border ${on ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-white text-[var(--ink)] border-[var(--rule)] hover:border-[var(--accent)]"}`}>
                                {it.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <Button
                        type="button" size="sm" onClick={saveEdit} disabled={editBusy}
                        className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
                        data-testid={`cycle-team-edit-save-${m.id}`}
                      >
                        {editBusy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Check className="w-3.5 h-3.5 mr-1" />}
                        Save
                      </Button>
                      <Button
                        type="button" size="sm" variant="ghost" onClick={cancelEdit}
                        disabled={editBusy} className="text-[12.5px]"
                        data-testid={`cycle-team-edit-cancel-${m.id}`}
                      >Cancel</Button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Delete-confirm AlertDialog — shadcn primitive. */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => { if (!v && !deleteBusy) setDeleteTarget(null); }}>
        <AlertDialogContent data-testid="cycle-team-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this team member?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget ? (
                <>{deleteTarget.name} will be removed from this cycle's team. Contributions they recorded stay on record; they just won't appear in the team list, scoreboard, or follow-up routing.</>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cycle-team-delete-cancel" disabled={deleteBusy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); confirmDelete(); }}
              disabled={deleteBusy}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
              data-testid="cycle-team-delete-confirm"
            >
              {deleteBusy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <div className="border border-[var(--rule)] rounded-md bg-[var(--cream-deep)]/30 p-4 space-y-3" data-testid="cycle-team-add">
        <p className="akki-overline text-[var(--muted)]">Add a member</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input placeholder="Name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="rounded-sm" data-testid="cycle-team-add-name" />
          <Input placeholder="Email" type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} className="rounded-sm" data-testid="cycle-team-add-email" />
          <Input placeholder="Role (optional)" value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} className="rounded-sm" />
        </div>
        <Textarea
          placeholder='What is this person contributing? E.g. "Sarah owns the credit risk update."'
          value={draft.contribution_description}
          onChange={(e) => setDraft({ ...draft, contribution_description: e.target.value })}
          className="rounded-sm min-h-[64px]"
          data-testid="cycle-team-add-desc"
        />
        {items.length > 0 && (
          <div>
            <p className="text-[11px] text-[var(--muted)] mb-1.5">Owns agenda items:</p>
            <div className="flex flex-wrap gap-1.5">
              {items.map((it) => {
                const on = draft.owns_item_ids.includes(it.id);
                return (
                  <button key={it.id} type="button" onClick={() => toggleItem(it.id)}
                    className={`text-[11.5px] px-2.5 py-1 rounded-full border ${on ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-white text-[var(--ink)] border-[var(--rule)] hover:border-[var(--accent)]"}`}>
                    {it.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        <Button type="button" size="sm" onClick={onAdd} disabled={busy}
          className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
          data-testid="cycle-team-add-submit"
        >
          {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
          Add member
        </Button>
      </div>
      <StepFooter canBack canForward onBack={onBack} onForward={onForward} />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Step 3 — Contributions                                             */
/* ------------------------------------------------------------------ */
function ContributionsStep({ cid, cycleId, agenda, members, contributions, refresh, onBack, onForward }) {
  const navigate = useNavigate();
  const items = agenda?.items || [];
  const [draft, setDraft] = useState({
    agenda_item_id: items[0]?.id || "",
    team_member_id: members[0]?.id || "",
    title: "",
    body_text: "",
    kind: "note",
    // QA-2026-05-16-017 / -018 (Chunk-9 2026-05-18) — attachment state.
    source_doc_id: null,
    attached_doc: null,
    titleEditedByUser: false,
  });
  const [busy, setBusy] = useState(false);
  const [scoringId, setScoringId] = useState(null);
  // QA-2026-05-16-017 attach-picker modal state.
  const [attachPickerOpen, setAttachPickerOpen] = useState(false);

  useEffect(() => {
    // Cycle v2 contributions tab opens at "Select an agenda item"
    // (PO decision #2 — contributor dropdown stays empty until the
    // user explicitly picks an agenda item). The legacy default-to-
    // first-item behaviour is preserved when no v2 cycleId is set.
    if (cycleId) return;
    if (!draft.agenda_item_id && items[0]?.id) setDraft((p) => ({ ...p, agenda_item_id: items[0].id }));
    if (!draft.team_member_id && members[0]?.id) setDraft((p) => ({ ...p, team_member_id: members[0].id }));
  }, [items, members]); // eslint-disable-line

  // Cycle v2 — PO decision #2: contributor dropdown is FILTERED by
  // the selected agenda item. When the item changes, refresh the
  // eligible-contributors list from the backend.
  const [eligible, setEligible] = useState([]);
  useEffect(() => {
    if (!cycleId || !draft.agenda_item_id) { setEligible([]); return; }
    let alive = true;
    (async () => {
      try {
        const d = await listEligibleContributors(cid, cycleId, draft.agenda_item_id);
        if (!alive) return;
        setEligible(d.contributors || []);
        // If the currently-selected member isn't eligible, reset.
        const eligibleIds = new Set((d.contributors || []).map((m) => m.id));
        if (draft.team_member_id && !eligibleIds.has(draft.team_member_id)) {
          setDraft((p) => ({ ...p, team_member_id: (d.contributors || [])[0]?.id || "" }));
        }
      } catch { if (alive) setEligible([]); }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid, cycleId, draft.agenda_item_id]);
  // Fall back to ALL members if no v2 cycle (legacy path) — keeps the
  // pre-v2 UX intact for contexts that haven't started a fresh cycle.
  const contributorPool = cycleId ? eligible : members;

  const addContribution = async () => {
    // QA-2026-05-16-021 (Chunk-9): same gating rule as the CTA
    // disabled state — at least one input method MUST be present.
    if (!draft.agenda_item_id || !draft.team_member_id) {
      toast.error("Pick an agenda item and a contributor."); return;
    }
    if (!draft.body_text.trim() && !draft.attached_doc) {
      toast.error("Add text or attach a document."); return;
    }
    setBusy(true);
    try {
      // QA-2026-05-16-017 + -020: backend `ContributionIn` accepts
      // `source_doc_id` (Chunk-7 -005 fix). When the user has only
      // attached a doc (no body_text), we send kind="document"; when
      // both or text-only we send kind="note" so the scorer treats
      // the body_text as primary + attached doc as augmentation.
      const payload = {
        agenda_item_id: draft.agenda_item_id,
        team_member_id: draft.team_member_id,
        title: draft.title || null,
        body_text: draft.body_text || null,
        source_doc_id: draft.source_doc_id || null,
        kind: (draft.attached_doc && !draft.body_text.trim())
          ? "document"
          : "note",
      };
      await api.post(`/contexts/${cid}/cycle/contributions${qcid(cycleId)}`, payload);
      await refresh();
      setDraft((p) => ({
        ...p,
        title: "",
        body_text: "",
        source_doc_id: null,
        attached_doc: null,
        titleEditedByUser: false,
      }));
      toast.success("Added.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const score = async (cid_contrib) => {
    setScoringId(cid_contrib);
    try { await api.post(`/contexts/${cid}/cycle/contributions/${cid_contrib}/score${qcid(cycleId)}`, {}); await refresh(); }
    catch (e) { toast.error(apiErrorMessage(e)); } finally { setScoringId(null); }
  };

  return (
    <section data-testid="cycle-step-contributions">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Track contributions.</h2>
      <p className="akki-meta mb-5">Capture what each owner has sent in. Score each entry on relevance, fullness, and readiness.</p>
      {contributions.length > 0 && (
        <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-md bg-white mb-5" data-testid="cycle-contributions-list">
          {contributions.map((c) => {
            const item = items.find((it) => it.id === c.agenda_item_id);
            const member = members.find((m) => m.id === c.team_member_id);
            return (
              <li key={c.id} className="px-4 py-3" data-testid={`cycle-contrib-row-${c.id}`}>
                <p className="akki-meta text-[11px] mb-0.5 font-mono text-[var(--muted)]">{item?.label || "(item missing)"} · {member?.name || "(unknown)"}</p>
                {c.title && <p className="akki-serif text-[14px] text-[var(--ink)]">{c.title}</p>}
                <p className="text-[13px] text-[var(--ink)] leading-[1.55] mt-1 line-clamp-3">{c.body_text}</p>
                {c.scores ? (
                  <div className="flex gap-3 text-[11.5px] font-mono text-[var(--muted)] mt-2">
                    <span>relevance <strong className="text-[var(--ink)]">{c.scores.relevance}</strong></span>
                    <span>fullness <strong className="text-[var(--ink)]">{c.scores.fullness}</strong></span>
                    <span>readiness <strong className="text-[var(--ink)]">{c.scores.readiness}</strong></span>
                  </div>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => score(c.id)} disabled={scoringId === c.id} className="mt-2 text-[12px]" data-testid={`cycle-contrib-score-${c.id}`}>
                    {scoringId === c.id ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
                    Score
                  </Button>
                )}
                {/* Wave 3.1 (UAT pack 2026-05-10) — Take to Solva.
                    Mints a Solva session with the contribution body
                    as framing seed. The picker reads the seed via
                    SolvaApp's useSearchParams plumbing (Wave 1.1). */}
                <button
                  type="button"
                  onClick={() => takeToSolva({ navigate, kind: "cycle_contribution", id: c.id })}
                  data-testid={`cycle-contrib-take-to-solva-${c.id}`}
                  className="mt-2 ml-2 text-[11px] text-[var(--muted)] hover:text-[var(--accent)] underline inline-flex items-center"
                  title="Open this contribution as Solva framing"
                >
                  Take to Solva
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {members.length === 0 ? (
        <p className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2">
          Add at least one team member first.
        </p>
      ) : (
        <div className="border border-[var(--rule)] rounded-md bg-[var(--cream-deep)]/30 p-4 space-y-3" data-testid="cycle-contrib-add">
          <p className="akki-overline text-[var(--muted)]">Add a contribution</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <select
              value={draft.agenda_item_id || ""}
              onChange={(e) => setDraft({ ...draft, agenda_item_id: e.target.value, team_member_id: "" })}
              className="border border-[var(--rule)] rounded-sm h-9 px-2 text-[13px] bg-white"
              data-testid="cycle-contrib-add-item"
            >
              <option value="">Select an agenda item</option>
              {items.map((it) => <option key={it.id} value={it.id}>{it.label}</option>)}
            </select>
            <select
              value={draft.team_member_id || ""}
              onChange={(e) => setDraft({ ...draft, team_member_id: e.target.value })}
              disabled={!draft.agenda_item_id || contributorPool.length === 0}
              className="border border-[var(--rule)] rounded-sm h-9 px-2 text-[13px] bg-white disabled:opacity-50"
              data-testid="cycle-contrib-add-member"
            >
              <option value="">
                {!draft.agenda_item_id
                  ? "Pick an agenda item first"
                  : contributorPool.length === 0
                    ? "No team member assigned to this item"
                    : "Select a contributor"}
              </option>
              {contributorPool.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.email}</option>)}
            </select>
          </div>
          <Input
            placeholder="Title (optional)"
            value={draft.title}
            onChange={(e) => {
              // QA-2026-05-16-018 (Chunk-9): track whether the user
              // has manually edited the title so removing the
              // attachment later doesn't wipe their work.
              setDraft({ ...draft, title: e.target.value, titleEditedByUser: true });
            }}
            className="rounded-sm"
            data-testid="cycle-contrib-add-title"
          />

          {/* QA-2026-05-16-017 / -018 / -019 (Chunk-9 2026-05-18):
              attach icon + chip rendered above the paste textbox so
              the user sees attachment options before deciding to type.
              The paste textbox below remains available alongside any
              attachment (per -019). */}
          <div className="flex items-center gap-2" data-testid="cycle-contrib-add-attach-row">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setAttachPickerOpen(true)}
              className="rounded-sm text-[12px] border-[var(--rule)] hover:border-[var(--ink)]"
              data-testid="cycle-contrib-add-attach-btn"
              aria-label="Attach a document"
            >
              <Paperclip className="w-3.5 h-3.5 mr-1" />
              {draft.attached_doc ? "Change attachment" : "Attach document"}
            </Button>
            {draft.attached_doc && (
              <div
                className="flex items-center gap-1.5 px-2 py-1 bg-[var(--cream-deep)] border border-[var(--rule)] rounded-sm text-[12px]"
                data-testid="cycle-contrib-add-attachment-chip"
              >
                <FileText className="w-3.5 h-3.5 text-[var(--muted)]" />
                <span className="truncate max-w-[260px]" data-testid="cycle-contrib-add-attachment-name">
                  {draft.attached_doc.name}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    // QA-2026-05-16-018: clear the attachment AND
                    // clear the auto-populated title ONLY if the user
                    // hasn't manually edited it since attach.
                    setDraft((p) => ({
                      ...p,
                      source_doc_id: null,
                      attached_doc: null,
                      title: p.titleEditedByUser ? p.title : "",
                    }));
                  }}
                  className="text-[var(--muted)] hover:text-rose-700"
                  aria-label="Remove attachment"
                  data-testid="cycle-contrib-add-attachment-remove"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          <Textarea
            placeholder="Paste the contribution text here."
            value={draft.body_text}
            onChange={(e) => setDraft({ ...draft, body_text: e.target.value })}
            className="rounded-sm min-h-[100px]"
            data-testid="cycle-contrib-add-body"
          />
          <Button
            size="sm"
            onClick={addContribution}
            // QA-2026-05-16-021 (Chunk-9): CTA inactive until at least
            // one input method is used (attachment OR pasted text).
            disabled={busy || (!draft.body_text.trim() && !draft.attached_doc)}
            className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
            data-testid="cycle-contrib-add-submit"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
            Record contribution
          </Button>
        </div>
      )}
      <StepFooter canBack canForward onBack={onBack} onForward={onForward} />

      {/* QA-2026-05-16-017 picker modal. */}
      <ContributionAttachPicker
        open={attachPickerOpen}
        onClose={() => setAttachPickerOpen(false)}
        contextId={cid}
        onAttached={(att) => {
          // -017 + -018: attach the doc, auto-populate Title ONLY if
          // the user hasn't typed in the Title field. `titleEditedByUser`
          // tracks intent — set on every Title onChange.
          setDraft((p) => ({
            ...p,
            source_doc_id: att.id,
            attached_doc: att,
            title: (!p.titleEditedByUser && !(p.title || "").trim())
              ? att.name
              : p.title,
          }));
        }}
      />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Step 4 — Scoreboard                                                */
/* ------------------------------------------------------------------ */
function ScoreboardStep({ cid, cycleId, readiness, refresh, onBack, onForward }) {
  if (!readiness) return <p className="text-[12.5px] text-[var(--muted)]">Loading…</p>;
  return (
    <section data-testid="cycle-step-scoreboard">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Readiness scoreboard.</h2>
      <p className="akki-meta mb-5">Where the cycle stands. Use this to decide whether to send follow-ups or compile now.</p>
      <div className="border border-[var(--rule)] bg-white rounded-md px-5 py-4 mb-5">
        <div className="flex items-baseline gap-4 mb-3">
          <p className="akki-serif text-[28px] text-[var(--ink)] leading-none" data-testid="cycle-scoreboard-overall">{readiness.overall}<span className="text-[16px] text-[var(--muted)]">%</span></p>
          <p className="akki-meta text-[var(--muted)]">overall readiness</p>
        </div>
        {readiness.storyline?.length > 0 && (
          <ul className="space-y-1 text-[13.5px] text-[var(--ink)] leading-[1.6]" data-testid="cycle-scoreboard-storyline">
            {readiness.storyline.map((s, i) => <li key={i}>· {s}</li>)}
          </ul>
        )}
      </div>
      <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-md bg-white" data-testid="cycle-scoreboard-items">
        {readiness.items.map((row) => (
          <li key={row.item_id} className="px-4 py-3" data-testid={`cycle-scoreboard-row-${row.item_id}`}>
            <div className="flex items-baseline justify-between gap-3 flex-wrap">
              <p className="akki-serif text-[14px] text-[var(--ink)]">{row.label}</p>
              <span className={`text-[10.5px] uppercase tracking-[0.12em] font-mono px-2 py-0.5 rounded-full border ${STATUS_TONE[row.status] || ""}`}>{row.status}</span>
            </div>
            <div className="flex gap-4 text-[11.5px] font-mono text-[var(--muted)] mt-1.5">
              <span>relevance <strong className="text-[var(--ink)]">{row.avg_relevance}</strong></span>
              <span>fullness <strong className="text-[var(--ink)]">{row.avg_fullness}</strong></span>
              <span>readiness <strong className="text-[var(--ink)]">{row.avg_readiness}</strong></span>
              <span className="ml-auto">overall <strong className="text-[var(--ink)]">{row.overall}</strong></span>
            </div>
            {row.owners?.length > 0 && (
              <p className="text-[11px] text-[var(--muted)] mt-1 font-mono">Owners: {row.owners.map((o) => o.name).join(" · ")}</p>
            )}
          </li>
        ))}
      </ul>
      <StepFooter canBack canForward onBack={onBack} onForward={onForward} primaryLabel="Refresh" onPrimary={refresh} />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Step 5 — Follow-ups                                                */
/* ------------------------------------------------------------------ */
function FollowUpsStep({ cid, cycleId, followups, refresh, onBack, onForward, execName }) {
  const [busy, setBusy] = useState(false);
  const [sendingId, setSendingId] = useState(null);

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${cid}/cycle/follow-ups/draft${qcid(cycleId)}`, {});
      toast.success(`${data.count} draft${data.count === 1 ? "" : "s"} produced.`);
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setBusy(false); }
  };

  const approveAndSend = async (fid) => {
    setSendingId(fid);
    try {
      await api.post(`/contexts/${cid}/cycle/follow-ups/${fid}/approve${qcid(cycleId)}`, {});
      const { data } = await api.post(`/contexts/${cid}/cycle/follow-ups/${fid}/send${qcid(cycleId)}`, {});
      if (data?.mode === "test_mode_restricted") {
        toast.message("Resend is in test mode — recipient skipped, follow-up logged.");
      } else if (data?.ok) {
        toast.success("Sent.");
      } else {
        toast.error(`Send mode: ${data?.mode || "unknown"}`);
      }
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setSendingId(null); }
  };

  return (
    <section data-testid="cycle-step-followups">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Akki for {execName}.</h2>
      <p className="akki-meta mb-5">Drafts go out only on your approval — no autonomous mass sends. Per-draft preview + approve.</p>
      <Button size="sm" onClick={generate} disabled={busy} className="mb-4 bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]" data-testid="cycle-followups-generate">
        {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Mail className="w-3.5 h-3.5 mr-1" />}
        Draft follow-ups for unmet items
      </Button>
      {followups.length === 0 ? (
        <p className="text-[12.5px] text-[var(--muted)] py-6 text-center" data-testid="cycle-followups-empty">No drafts yet.</p>
      ) : (
        <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-md bg-white" data-testid="cycle-followups-list">
          {followups.map((f) => (
            <li key={f.id} className="px-4 py-3" data-testid={`cycle-followup-row-${f.id}`}>
              <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
                <p className="akki-serif text-[14px] text-[var(--ink)]">{f.draft_subject}</p>
                <span className="text-[10.5px] uppercase tracking-[0.12em] font-mono px-2 py-0.5 rounded-full border bg-stone-50 text-stone-700 border-stone-200">{f.status}</span>
              </div>
              <p className="text-[11.5px] text-[var(--muted)] font-mono mb-2">to {f.to_email}{f.to_name ? ` · ${f.to_name}` : ""} · for {f.agenda_item_label}</p>
              <pre className="text-[12.5px] text-[var(--ink)] leading-[1.55] whitespace-pre-wrap font-sans border-l-2 border-[var(--rule)] pl-3 py-1 mb-2">{f.draft_body}</pre>
              {f.status === "draft" && (
                <Button size="sm" onClick={() => approveAndSend(f.id)} disabled={sendingId === f.id} className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px]" data-testid={`cycle-followup-send-${f.id}`}>
                  {sendingId === f.id ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1" />}
                  Approve & send
                </Button>
              )}
              {f.send_mode && (
                <p className="text-[11px] text-[var(--muted)] font-mono mt-1">send_mode: {f.send_mode}</p>
              )}
            </li>
          ))}
        </ul>
      )}
      <StepFooter canBack canForward onBack={onBack} onForward={onForward} />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Step 6 — Compilation                                               */
/* ------------------------------------------------------------------ */
function CompilationStep({ cid, cycleId, cycle, onBack }) {
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const [progress, setProgress] = useState(null);
  const navigate = useNavigate();
  // Phase L.b.2 (2026-05-27) — Streaming-log progress driver during
  // the async compile. Walks the locked `task-manager-compile` script
  // while the existing pollJob loop drives the job-queue worker.
  const { state: lbState, start: lbStart, complete: lbComplete, error: lbError, reset: lbReset } = usePhasedTimer();

  // Blocker 2 (2026-05-25, backlog-b) — pre-populate `out` from the
  // backend's defensive linkage lookup so the DOCX/PDF/PPTX chips
  // surface for cycles that were compiled in a prior session (or
  // seeded). The cycles.GET endpoint computes `compilation` from up to
  // three linkage paths; we use whichever one resolved.
  useEffect(() => {
    if (out || busy) return;
    const compilation = cycle?.compilation;
    if (compilation?.export_id) {
      setOut({
        export_id: compilation.export_id,
        file_name: compilation.file_name,
        output_format: compilation.output_format,
        byte_len: 0,
        sha256: "",
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycle?.compilation?.export_id]);

  const compile = async () => {
    setBusy(true); setOut(null); setProgress(null);
    lbReset();
    lbStart("task-manager-compile", { stepMs: 9000 });
    try {
      // Chunk 2 (2026-05-13, CM-R04) — async pattern. The endpoint
      // returns 202 + { job_id } immediately. The two-pass LLM compile
      // (drafter Sonnet 4.5 → validator Gemini 2.5 Flash) runs in the
      // background; we poll until terminal. Progress label updates so
      // the user sees we're still working.
      const { data: enq } = await api.post(
        `/contexts/${cid}/cycle/draft-compilation${qcid(cycleId)}`, {},
      );
      const job = await pollJob(enq.job_id, {
        onProgress: (status, elapsedS) => {
          setProgress(`Compiling… ${elapsedS}s`);
        },
      });
      if (job.status === "failed") {
        lbError("compilation_failed", job.error || "Compilation failed.");
        throw new Error(job.error || "Compilation failed.");
      }
      setOut(job.result || {});
      lbComplete(job.result || {});
      toast.success("Compilation produced.");
    } catch (e) {
      lbError("compile_exception", apiErrorMessage(e));
      toast.error(apiErrorMessage(e));
    }
    finally { setBusy(false); setProgress(null); }
  };

  const download = async () => {
    if (!out?.export_id) return;
    try {
      // Reuse the work_studio_export download endpoint via the standard
      // pin-token flow.
      const status = await api.get(`/contexts/${cid}/work-studio/exports/${out.export_id}`);
      const tok = status.data?.download_token;
      const resp = await api.get(`/contexts/${cid}/work-studio/exports/${out.export_id}/download`, {
        params: { token: tok }, responseType: "blob",
      });
      const blob = new Blob([resp.data], { type: resp.headers?.["content-type"] || "application/octet-stream" });
      const a = document.createElement("a");
      a.href = window.URL.createObjectURL(blob);
      a.download = out.file_name || `cycle-compilation.docx`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(a.href);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  // T5 (2026-05-25) — C5 + G6 parity: per-format download wired to the
  // T4.1 on-the-fly render endpoint. The cycle compile result's
  // `export_id` IS the same identifier as `work_studio_exports.id`
  // (the row schema is shared — verified in work_studio_export.py
  // L243 + L596). Each click streams a server-produced binary.
  const downloadFormat = async (fmt) => {
    if (!out?.export_id) return;
    const format = (fmt || "docx").toLowerCase();
    try {
      const resp = await api.get(
        `/contexts/${cid}/work-studio/documents/${out.export_id}/render`,
        { params: { format }, responseType: "blob" }
      );
      const blob = new Blob([resp.data], {
        type: resp.headers?.["content-type"] || "application/octet-stream",
      });
      const url = window.URL.createObjectURL(blob);
      const cd = resp.headers?.["content-disposition"] || "";
      const match = cd.match(/filename="?([^";]+)"?/);
      const a = document.createElement("a");
      a.href = url;
      a.download = match ? match[1] : `cycle-compilation.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 409) {
        toast.error("This artefact has no compiled content yet.");
      } else {
        toast.error(apiErrorMessage(e, `Couldn't download ${format.toUpperCase()} file.`));
      }
    }
  };

  return (
    <section data-testid="cycle-step-compilation">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Draft Compilation Output.</h2>
      <p className="akki-meta mb-5" data-testid="cycle-compilation-subtitle">
        When every item is ready, Agent Cycle compiles your output to executive cadence.
      </p>
      {!out && (
        <>
          <Button size="sm" onClick={compile} disabled={busy} className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]" data-testid="cycle-compile-btn">
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <FileDown className="w-3.5 h-3.5 mr-1" />}
            {busy ? "Compiling…" : "Produce draft compilation"}
          </Button>
          {busy && (
            <div className="mt-4 max-w-md" data-testid="cycle-compile-progress">
              <StreamingLogScene
                surfaceId="streaming-log-task-manager-compile"
                state={lbState}
                emptyHint="Preparing the compile…"
              />
              {progress && (
                <p className="akki-meta mt-2 text-[11px] text-[var(--muted)] font-mono">
                  {progress} — you can keep working; this finishes in the background.
                </p>
              )}
            </div>
          )}
        </>
      )}
      {out && (
        <div className="border border-[var(--rule)] bg-white rounded-md px-5 py-4" data-testid="cycle-compile-result">
          <div className="flex items-start gap-3 mb-3">
            <Check className="w-5 h-5 text-emerald-700 mt-0.5" />
            <div>
              <p className="akki-serif text-[14.5px] text-[var(--ink)]">Compilation ready.</p>
              <p className="akki-meta text-[11.5px] mt-0.5 font-mono break-all">
                {out.file_name} · {Math.round((out.byte_len || 0) / 1024)} KB · sha256 {out.sha256?.slice(0, 16)}…
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {/* T5 (2026-05-25) — C5 + G6 parity: replace the single
                "Download .docx" button with the three G6-ratified
                format buttons (DOCX/PDF/PPTX). All three call the
                T4.1 on-the-fly render endpoint at
                `/work-studio/documents/{export_id}/render?format=...`
                which already verifies Content-Type, Content-Disposition,
                and X-AKKI-Sensitivity-Band on each response. Buttons
                emit DOM unconditionally per T2.3 rule; disable only
                while the original compile is busy. */}
            <Button
              size="sm"
              onClick={() => downloadFormat("docx")}
              disabled={busy}
              className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
              data-testid="cycle-compile-download-docx"
              aria-label="Download DOCX"
            >
              <Download className="w-3.5 h-3.5 mr-1" /> DOCX
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => downloadFormat("pdf")}
              disabled={busy}
              className="text-[12.5px]"
              data-testid="cycle-compile-download-pdf"
              aria-label="Download PDF"
            >
              <Download className="w-3.5 h-3.5 mr-1" /> PDF
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => downloadFormat("pptx")}
              disabled={busy}
              className="text-[12.5px]"
              data-testid="cycle-compile-download-pptx"
              aria-label="Download PPTX"
            >
              <Download className="w-3.5 h-3.5 mr-1" /> PPTX
            </Button>
            {/* Workstream B.7 — Continue in Chat. The compilation
                endpoint mints a chat tethered to the active context
                with the DOCX pre-attached as a `cycle_compilation`
                document. Surfaces only when the backend returned a
                continue_chat_id (older clients / failed handoffs
                degrade gracefully). */}
            {out.continue_chat_id && (
              <Button
                size="sm" variant="outline"
                onClick={() => navigate(`/app/chat?chat_id=${encodeURIComponent(out.continue_chat_id)}`)}
                className="text-[12.5px]"
                data-testid="cycle-compile-continue-in-chat"
              >
                <MessageSquare className="w-3.5 h-3.5 mr-1" /> Continue in Chat
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={() => { setOut(null); compile(); }} className="text-[12.5px]">
              Compile again
            </Button>
          </div>
          <BoardSubmitPanel
            cid={cid}
            cycleId={out.cycle_id || out.agenda_id}
            briefId={out.brief_id}
            briefStatus={out.board_status || "draft"}
          />
        </div>
      )}
      <StepFooter canBack canForward={false} onBack={onBack} />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                               */
/* ------------------------------------------------------------------ */
export default function Cycle() {
  const { activeContext, account } = useAuth();
  const cid = activeContext?.id;
  // Cycle v2 — cycle id from URL params + tab state in query string.
  const { cycleId: routeCycleId } = useParams();
  const [search, setSearch] = useSearchParams();
  const cycleId = routeCycleId || null;
  const navigate = useNavigate();
  const [cycle, setCycle] = useState(null);
  const [closeOpen, setCloseOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const [activating, setActivating] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  // Patch 10 — Expected close date (Home 2 "cycles closing this week" insight).
  // Default = today + 30 days, in ISO YYYY-MM-DD format. Reset on each dialog open.
  const [expectedCloseAt, setExpectedCloseAt] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  });

  // Default tab: URL ?tab=… > "agenda".
  const initialTab = (search.get("tab") || "agenda").toLowerCase();
  const [stepId, setStepId] = useState(STEPS.find((s) => s.id === initialTab) ? initialTab : "agenda");
  const setStepIdSynced = (id) => {
    setStepId(id);
    const next = new URLSearchParams(search);
    next.set("tab", id);
    setSearch(next, { replace: true });
  };

  const [agenda, setAgenda] = useState(null);
  const [members, setMembers] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [followups, setFollowups] = useState([]);
  const [error, setError] = useState(null);

  const isCompleted = cycle?.status === "completed";
  const isDraft = cycle?.status === "draft";
  const isActive = cycle?.status === "active";
  // Active-cycle gating for the activate button (Agenda tab).
  const canActivate = isDraft && (agenda?.title || cycle?.title || "").trim().length > 0
                      && (agenda?.items || []).length > 0;

  // Load the cycle row whenever the id changes (or once when no id —
  // legacy path, just leaves `cycle` null).
  useEffect(() => {
    let alive = true;
    (async () => {
      if (!cid || !cycleId) { setCycle(null); return; }
      try {
        const c = await getCycle(cid, cycleId);
        if (alive) setCycle(c);
      } catch (e) {
        if (alive) { setError("Cycle not found."); }
      }
    })();
    return () => { alive = false; };
  }, [cid, cycleId]);

  const refreshAll = async () => {
    if (!cid) return;
    try {
      const [a, t, c, r, f] = await Promise.all([
        api.get(`/contexts/${cid}/cycle/agenda${qcid(cycleId)}`),
        api.get(`/contexts/${cid}/cycle/team${qcid(cycleId)}`),
        api.get(`/contexts/${cid}/cycle/contributions${qcid(cycleId)}`),
        api.get(`/contexts/${cid}/cycle/readiness${qcid(cycleId)}`),
        api.get(`/contexts/${cid}/cycle/follow-ups${qcid(cycleId)}`),
      ]);
      setAgenda(a.data);
      setMembers(t.data?.members || []);
      setContributions(c.data?.contributions || []);
      setReadiness(r.data);
      setFollowups(f.data?.followups || []);
      setError(null);
    } catch (e) { setError(apiErrorMessage(e)); }
  };

  useEffect(() => { refreshAll(); /* eslint-disable-next-line */ }, [cid, cycleId]);

  const stepIdx = STEPS.findIndex((s) => s.id === stepId);
  const onBack = () => setStepIdSynced(STEPS[Math.max(0, stepIdx - 1)].id);
  const onForward = () => setStepIdSynced(STEPS[Math.min(STEPS.length - 1, stepIdx + 1)].id);

  const execName = useMemo(() => {
    const n = account?.name || account?.email || "";
    return (n.split(" ")[0] || n || "the executive");
  }, [account]);

  const doActivate = async () => {
    setActivating(true);
    try {
      const c = await activateCycle(cid, cycleId, {
        expected_close_at: expectedCloseAt || undefined,
      });
      setCycle(c);
      setActivateOpen(false);
      toast.success("Cycle activated.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to activate cycle.");
    } finally { setActivating(false); }
  };
  const doClose = async () => {
    setClosing(true);
    try {
      const c = await closeCycle(cid, cycleId);
      setCycle(c);
      setCloseOpen(false);
      toast.success("Cycle closed. You can still re-download the compilation document from the Compilation tab.");
      navigate("/app/cycle");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to close cycle.");
    } finally { setClosing(false); }
  };

  if (!cid) {
    return (
      <AppShell>
        <div className="akki-w-medium px-8 py-12 text-[var(--muted)]">Pick a workspace to use Cycle Manager.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="cycle">
      <div
        className="akki-w-medium px-8 py-10"
        data-testid="cycle-page"
        aria-disabled={isCompleted ? "true" : "false"}
      >
        {cycleId && (
          <CycleBreadcrumb
            title={cycle?.title || agenda?.title}
            status={cycle?.status}
          />
        )}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Cycle Manager · {activeContext.name}
            </p>
            <h1 className="akki-greeting mb-1">{cycle?.title || "Drafting engine."}</h1>
            <p className="akki-meta mb-6 max-w-2xl" data-testid="cycle-detail-status-sentence">
              {isCompleted
                ? "Closed agenda. Read-only. You can regenerate the compilation from the Compilation tab."
                : isActive
                  ? "Active agenda. Agent Cycle is tracking readiness per item and chasing contributors."
                  : isDraft
                    ? "Draft agenda. Add items and team, then activate to begin contributions."
                    : "Set the agenda, build the team, score contributions, send follow-ups on your approval, and compile the draft when you decide it's ready."}
            </p>
          </div>
          {isDraft && stepId === "agenda" && cycleId && (
            <Button
              size="sm"
              onClick={() => setActivateOpen(true)}
              disabled={!canActivate}
              title={canActivate ? undefined : "Title + at least one agenda item required."}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
              data-testid="cycle-activate-open"
            >
              Activate Cycle
            </Button>
          )}
        </div>
        {isCompleted && (
          <p
            className="text-[12px] text-[var(--muted)] bg-[var(--parchment)] border border-[var(--rule)] rounded-sm px-3 py-2 mb-3 font-mono"
            data-testid="cycle-readonly-banner"
          >
            This cycle is closed and read-only. The Compilation tab can still re-generate the document.
          </p>
        )}
        {error && (
          <p className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 mb-3 inline-flex items-start gap-2">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {error}
          </p>
        )}
        <fieldset disabled={isCompleted} className={isCompleted ? "opacity-95" : ""}>
        <JudgementPanel
          readiness={readiness}
          followups={followups}
          onJump={setStepIdSynced}
        />
        <StepShell activeId={stepId} onSelect={setStepIdSynced}>
          {stepId === "agenda" && <AgendaStep cid={cid} cycleId={cycleId} agenda={agenda} onSaved={setAgenda} onForward={onForward} />}
          {stepId === "team" && <TeamStep cid={cid} cycleId={cycleId} agenda={agenda} members={members} refresh={refreshAll} onBack={onBack} onForward={onForward} />}
          {stepId === "contributions" && <ContributionsStep cid={cid} cycleId={cycleId} agenda={agenda} members={members} contributions={contributions} refresh={refreshAll} onBack={onBack} onForward={onForward} />}
          {stepId === "scoreboard" && <ScoreboardStep cid={cid} cycleId={cycleId} readiness={readiness} refresh={refreshAll} onBack={onBack} onForward={onForward} />}
          {stepId === "followups" && <FollowUpsStep cid={cid} cycleId={cycleId} followups={followups} refresh={refreshAll} onBack={onBack} onForward={onForward} execName={execName} />}
          {stepId === "compilation" && <CompilationStep cid={cid} cycleId={cycleId} cycle={cycle} onBack={onBack} />}
        </StepShell>
        </fieldset>
        {cycleId && (
          <CycleStepNav
            tab={stepId}
            status={cycle?.status}
            onChange={setStepIdSynced}
            onClose={() => setCloseOpen(true)}
          />
        )}

        <AlertDialog open={activateOpen} onOpenChange={setActivateOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="akki-serif">Activate this cycle?</AlertDialogTitle>
              <AlertDialogDescription className="akki-meta">
                Once active, it appears as active on the cycle list and contributors can begin work.
              </AlertDialogDescription>
            </AlertDialogHeader>
            {/* Patch 10 — Expected close date. Default = activated_at + 30 days.
                Drives the Home 2 "cycles closing this week" insight count. */}
            <div className="space-y-1.5 py-2" data-testid="cycle-activate-expected-close-row">
              <label className="text-[11px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]" htmlFor="cycle-activate-expected-close-input">
                Expected close date
              </label>
              <input
                id="cycle-activate-expected-close-input"
                type="date"
                value={expectedCloseAt}
                onChange={(e) => setExpectedCloseAt(e.target.value)}
                className="w-full border border-[var(--rule)] rounded-sm px-2 py-2 text-[13.5px] bg-white"
                data-testid="cycle-activate-expected-close-input"
              />
              <p className="text-[11.5px] text-[var(--muted)] leading-snug">
                Used by Home 2 to surface cycles closing this week. You can change it later.
              </p>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={activating} data-testid="cycle-activate-cancel">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => { e.preventDefault(); doActivate(); }}
                disabled={activating}
                className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                data-testid="cycle-activate-confirm"
              >
                {activating ? "Activating…" : "Activate"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <AlertDialog open={closeOpen} onOpenChange={setCloseOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="akki-serif">Close this cycle?</AlertDialogTitle>
              <AlertDialogDescription className="akki-meta">
                Are you sure you want to close this cycle? Once closed, the cycle will be read-only and cannot be edited. Make sure you have downloaded the compilation document before closing.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={closing} data-testid="cycle-close-cancel">Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => { e.preventDefault(); doClose(); }}
                disabled={closing}
                className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                data-testid="cycle-close-confirm"
              >
                {closing ? "Closing…" : "Close cycle"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
      {/* Phase E.3 (2026-05-26) — Universal Document Drawer.
          Cycle surfaces doc refs across the agenda + contributions
          tabs; appending `?doc_id=` opens the drawer here. */}
      <DocumentDrawer contextId={cid} />
      </WorkspaceEntryGate>
    </AppShell>
  );
}
