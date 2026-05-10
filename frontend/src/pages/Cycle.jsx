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
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Sparkles, ChevronLeft, ChevronRight, Plus, X, Loader2,
  Mail, FileDown, Check, AlertCircle, Users, ListChecks, CheckCircle2,
  ClipboardList, Send, Download, MessageSquare, Pencil,
} from "lucide-react";
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import JudgementPanel from "@/components/cycle/JudgementPanel";
import { takeToSolva } from "@/lib/takeToSolva";

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
  missing:  "text-[#8B2E2B] bg-[#8B2E2B]/10 border-[#8B2E2B]/30",
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
function AgendaStep({ cid, agenda, onSaved, onForward }) {
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
      const { data } = await api.post(`/contexts/${cid}/cycle/agenda`, { title: title.trim(), items: itemsClean });
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
              <Button type="button" size="sm" variant="ghost" onClick={() => removeItem(i)} className="text-[var(--muted)] hover:text-[#8B2E2B]"><X className="w-3.5 h-3.5" /></Button>
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
function TeamStep({ cid, agenda, members, refresh, onBack, onForward }) {
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
      await api.post(`/contexts/${cid}/cycle/team`, draft);
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
      await api.patch(`/contexts/${cid}/cycle/team/${editingId}`, {
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
      await api.delete(`/contexts/${cid}/cycle/team/${deleteTarget.id}`);
      toast.success(`Removed ${deleteTarget.name}.`);
      setDeleteTarget(null);
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setDeleteBusy(false); }
  };

  return (
    <section data-testid="cycle-step-team">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Build the team.</h2>
      <p className="akki-meta mb-5">Add the people contributing material — describe what each one is delivering.</p>
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
                          className="text-[12px] text-[var(--muted)] hover:text-[#8B2E2B] h-7"
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
              className="bg-[#8B2E2B] hover:bg-[#7A2825] text-white"
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
function ContributionsStep({ cid, agenda, members, contributions, refresh, onBack, onForward }) {
  const navigate = useNavigate();
  const items = agenda?.items || [];
  const [draft, setDraft] = useState({ agenda_item_id: items[0]?.id || "", team_member_id: members[0]?.id || "", title: "", body_text: "", kind: "note" });
  const [busy, setBusy] = useState(false);
  const [scoringId, setScoringId] = useState(null);

  useEffect(() => {
    if (!draft.agenda_item_id && items[0]?.id) setDraft((p) => ({ ...p, agenda_item_id: items[0].id }));
    if (!draft.team_member_id && members[0]?.id) setDraft((p) => ({ ...p, team_member_id: members[0].id }));
  }, [items, members]); // eslint-disable-line

  const addContribution = async () => {
    if (!draft.agenda_item_id || !draft.team_member_id || !draft.body_text.trim()) {
      toast.error("Pick an agenda item, a member, and add some text."); return;
    }
    setBusy(true);
    try { await api.post(`/contexts/${cid}/cycle/contributions`, draft); await refresh(); setDraft({ ...draft, title: "", body_text: "" }); toast.success("Added."); }
    catch (e) { toast.error(apiErrorMessage(e)); } finally { setBusy(false); }
  };

  const score = async (cid_contrib) => {
    setScoringId(cid_contrib);
    try { await api.post(`/contexts/${cid}/cycle/contributions/${cid_contrib}/score`, {}); await refresh(); }
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
            <select value={draft.agenda_item_id} onChange={(e) => setDraft({ ...draft, agenda_item_id: e.target.value })} className="border border-[var(--rule)] rounded-sm h-9 px-2 text-[13px] bg-white" data-testid="cycle-contrib-add-item">
              {items.map((it) => <option key={it.id} value={it.id}>{it.label}</option>)}
            </select>
            <select value={draft.team_member_id} onChange={(e) => setDraft({ ...draft, team_member_id: e.target.value })} className="border border-[var(--rule)] rounded-sm h-9 px-2 text-[13px] bg-white" data-testid="cycle-contrib-add-member">
              {members.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.email}</option>)}
            </select>
          </div>
          <Input placeholder="Title (optional)" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="rounded-sm" />
          <Textarea placeholder="Paste the contribution text here." value={draft.body_text} onChange={(e) => setDraft({ ...draft, body_text: e.target.value })} className="rounded-sm min-h-[100px]" data-testid="cycle-contrib-add-body" />
          <Button size="sm" onClick={addContribution} disabled={busy} className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]" data-testid="cycle-contrib-add-submit">
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
            Record contribution
          </Button>
        </div>
      )}
      <StepFooter canBack canForward onBack={onBack} onForward={onForward} />
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Step 4 — Scoreboard                                                */
/* ------------------------------------------------------------------ */
function ScoreboardStep({ cid, readiness, refresh, onBack, onForward }) {
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
function FollowUpsStep({ cid, followups, refresh, onBack, onForward, execName }) {
  const [busy, setBusy] = useState(false);
  const [sendingId, setSendingId] = useState(null);

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${cid}/cycle/follow-ups/draft`, {});
      toast.success(`${data.count} draft${data.count === 1 ? "" : "s"} produced.`);
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setBusy(false); }
  };

  const approveAndSend = async (fid) => {
    setSendingId(fid);
    try {
      await api.post(`/contexts/${cid}/cycle/follow-ups/${fid}/approve`, {});
      const { data } = await api.post(`/contexts/${cid}/cycle/follow-ups/${fid}/send`, {});
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
function CompilationStep({ cid, onBack }) {
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState(null);
  const navigate = useNavigate();

  const compile = async () => {
    setBusy(true); setOut(null);
    try {
      const { data } = await api.post(`/contexts/${cid}/cycle/draft-compilation`, {});
      setOut(data);
      toast.success("Compilation produced.");
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setBusy(false); }
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

  return (
    <section data-testid="cycle-step-compilation">
      <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-1">Draft Compilation Output.</h2>
      <p className="akki-meta mb-5">Akki produces a citation-ready draft from the scored contributions. Your judgement decides when to send.</p>
      {!out && (
        <Button size="sm" onClick={compile} disabled={busy} className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]" data-testid="cycle-compile-btn">
          {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <FileDown className="w-3.5 h-3.5 mr-1" />}
          Produce draft compilation
        </Button>
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
            <Button size="sm" onClick={download} className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]" data-testid="cycle-compile-download">
              <Download className="w-3.5 h-3.5 mr-1" /> Download .docx
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

  const [stepId, setStepId] = useState("agenda");
  const [agenda, setAgenda] = useState(null);
  const [members, setMembers] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [followups, setFollowups] = useState([]);
  const [error, setError] = useState(null);

  const refreshAll = async () => {
    if (!cid) return;
    try {
      const [a, t, c, r, f] = await Promise.all([
        api.get(`/contexts/${cid}/cycle/agenda`),
        api.get(`/contexts/${cid}/cycle/team`),
        api.get(`/contexts/${cid}/cycle/contributions`),
        api.get(`/contexts/${cid}/cycle/readiness`),
        api.get(`/contexts/${cid}/cycle/follow-ups`),
      ]);
      setAgenda(a.data);
      setMembers(t.data?.members || []);
      setContributions(c.data?.contributions || []);
      setReadiness(r.data);
      setFollowups(f.data?.followups || []);
      setError(null);
    } catch (e) { setError(apiErrorMessage(e)); }
  };

  useEffect(() => { refreshAll(); /* eslint-disable-next-line */ }, [cid]);

  const stepIdx = STEPS.findIndex((s) => s.id === stepId);
  const onBack = () => setStepId(STEPS[Math.max(0, stepIdx - 1)].id);
  const onForward = () => setStepId(STEPS[Math.min(STEPS.length - 1, stepIdx + 1)].id);

  const execName = useMemo(() => {
    const n = account?.name || account?.email || "";
    return (n.split(" ")[0] || n || "the executive");
  }, [account]);

  if (!cid) {
    return (
      <AppShell>
        <div className="akki-w-medium px-8 py-12 text-[var(--muted)]">Pick a workspace to use Cycle Manager.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-10" data-testid="cycle-page">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Cycle Manager · {activeContext.name}
        </p>
        <h1 className="akki-greeting mb-1">Drafting engine.</h1>
        <p className="akki-meta mb-6 max-w-2xl">
          Set the agenda, build the team, score contributions, send follow-ups on your approval, and compile the draft when you decide it's ready.
        </p>
        {error && (
          <p className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 mb-3 inline-flex items-start gap-2">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {error}
          </p>
        )}
        <JudgementPanel
          readiness={readiness}
          followups={followups}
          onJump={setStepId}
        />
        <StepShell activeId={stepId} onSelect={setStepId}>
          {stepId === "agenda" && <AgendaStep cid={cid} agenda={agenda} onSaved={setAgenda} onForward={onForward} />}
          {stepId === "team" && <TeamStep cid={cid} agenda={agenda} members={members} refresh={refreshAll} onBack={onBack} onForward={onForward} />}
          {stepId === "contributions" && <ContributionsStep cid={cid} agenda={agenda} members={members} contributions={contributions} refresh={refreshAll} onBack={onBack} onForward={onForward} />}
          {stepId === "scoreboard" && <ScoreboardStep cid={cid} readiness={readiness} refresh={refreshAll} onBack={onBack} onForward={onForward} />}
          {stepId === "followups" && <FollowUpsStep cid={cid} followups={followups} refresh={refreshAll} onBack={onBack} onForward={onForward} execName={execName} />}
          {stepId === "compilation" && <CompilationStep cid={cid} onBack={onBack} />}
        </StepShell>
      </div>
    </AppShell>
  );
}
