/**
 * TaskDrawer — Phase F.3 (2026-05-26).
 *
 * Universal Task surface. Mounts on Task Manager (replacing F.2's
 * placeholder) AND any other surface that wants to open a task via
 * `?task_id=<uuid>`. Mirrors the DocumentDrawer pattern from E.3.
 *
 * Five tabs:
 *   Plan          — task name / objective / success criteria / output spec / team roster
 *   Contributions — per-row status changes, approve / request-revision / re-invite
 *   Drafts        — task-linked docs; opening one stacks the DocumentDrawer on top
 *   Intelligence  — readiness breakdown + blockers + gaps + roadmap + recommendations
 *   Compile       — F.3 placeholder; lights up when F.4 lands
 *
 * Five footer CTAs (canonical `?ctx_type=task&ctx_id=<id>` URL contract):
 *   Use in Solva · Use in Chat · Generate brief · Test hypothesis · Share task
 */
import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Loader2, Pencil, Save, Check, X, MessageCircle, Layers, FileText,
  Brain, Sparkles, Send, ChevronLeft, AlertTriangle, Clock,
  ArrowUpRight, Share2, Mail, Hammer, RefreshCw, Calendar, Users,
} from "lucide-react";
import { toast } from "sonner";


// ─────────────────────────────────────────────────────────────────────
// Local helpers
// ─────────────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

function daysUntil(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    const today = new Date(); today.setHours(0, 0, 0, 0);
    return Math.floor((d - today) / (1000 * 60 * 60 * 24));
  } catch { return null; }
}

function StatusBadge({ state }) {
  const map = {
    active: "bg-[var(--cream-deep)] text-[var(--ink)]",
    draft:  "bg-[rgba(122,46,46,0.10)] text-[var(--oxblood)]",
    closed: "bg-[var(--parchment)] text-[var(--muted)]",
  };
  return (
    <span
      className={`px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-[0.14em] font-mono ${map[state] || map.active}`}
      data-testid="task-drawer-state-badge"
    >
      {state || "draft"}
    </span>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Drawer mount — listens to `?task_id=…`
// ═════════════════════════════════════════════════════════════════════
export default function TaskDrawer() {
  const [params, setParams] = useSearchParams();
  const tid = params.get("task_id") || null;
  const compileStageParam = params.get("compile_stage") || null;
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("plan");

  useEffect(() => {
    if (!tid) { setTask(null); return; }
    let dead = false;
    setLoading(true);
    api.get(`/tasks/${tid}`)
      .then(({ data }) => { if (!dead) setTask(data); })
      .catch((e) => { if (!dead) { setTask(null); toast.error(apiErrorMessage(e)); } })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [tid]);

  // Phase F.5 enhancement #2 — Resume-from-stage URL param. If the URL
  // carries `?compile_stage=<stage>` AND the task has an active compile
  // session at THAT stage, jump to the Compile tab. Otherwise the param
  // is ignored and the drawer opens on Plan.
  useEffect(() => {
    if (!task || !compileStageParam) return;
    const sessionStage = task.compile_session?.current_stage || null;
    if (sessionStage && compileStageParam === sessionStage) {
      setTab("compile");
    }
  }, [task, compileStageParam]);

  const onClose = () => {
    const next = new URLSearchParams(params);
    next.delete("task_id");
    setParams(next, { replace: true });
    setTab("plan");
  };

  const reload = async () => {
    if (!tid) return;
    try {
      const { data } = await api.get(`/tasks/${tid}`);
      setTask(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const open = !!tid;

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[60vw] p-0 flex flex-col"
        data-testid="task-drawer"
      >
        {loading ? (
          <div className="flex-1 flex items-center justify-center" data-testid="task-drawer-loading">
            <Loader2 className="w-5 h-5 animate-spin text-[var(--muted)]" />
          </div>
        ) : task ? (
          <>
            <DrawerHeader task={task} onClose={onClose} onPatched={reload} />
            <TabBar tab={tab} onTab={setTab} />
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {tab === "plan"          && <PlanTab          task={task} onPatched={reload} />}
              {tab === "contributions" && <ContributionsTab task={task} onPatched={reload} />}
              {tab === "drafts"        && <DraftsTab        task={task} />}
              {tab === "intelligence"  && <IntelligenceTab  task={task} onJumpTab={setTab} />}
              {tab === "compile"       && <CompileTab       task={task} />}
            </div>
            <FooterCTAs task={task} />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center" data-testid="task-drawer-missing">
            <p className="text-[12px] italic text-[var(--muted)]">Task not found.</p>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Header
// ═════════════════════════════════════════════════════════════════════
function DrawerHeader({ task, onClose, onPatched }) {
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(task.name || "");
  useEffect(() => { setName(task.name || ""); }, [task.id, task.name]);
  const onSaveName = async () => {
    if (!name.trim() || name.trim() === task.name) { setEditingName(false); return; }
    try {
      await api.patch(`/tasks/${task.id}`, { name: name.trim() });
      toast.success("Saved.");
      setEditingName(false);
      onPatched?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  const d = daysUntil(task.due_date);
  return (
    <header className="px-6 py-4 border-b border-[var(--rule)] flex items-start gap-4">
      <button
        type="button" onClick={onClose}
        className="text-[var(--muted)] hover:text-[var(--ink)] mt-1"
        data-testid="task-drawer-close"
        title="Close"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>
      <div className="flex-1 min-w-0">
        <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-0.5">
          Task
        </p>
        {editingName ? (
          <Input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={onSaveName}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSaveName();
              if (e.key === "Escape") { setName(task.name || ""); setEditingName(false); }
            }}
            className="text-[20px] akki-serif border-b border-[var(--ink)] border-x-0 border-t-0 rounded-none px-0"
            data-testid="task-drawer-name-input"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditingName(true)}
            className="text-left akki-serif text-[20px] text-[var(--ink)] inline-flex items-center gap-2 group"
            data-testid="task-drawer-name"
          >
            <span>{task.name || "—"}</span>
            <Pencil className="w-3 h-3 text-[var(--muted)] opacity-0 group-hover:opacity-100" />
          </button>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <StatusBadge state={task.state} />
        <span
          className="px-1.5 py-0.5 rounded-sm text-[10.5px] font-mono bg-[var(--parchment)] text-[var(--ink)]"
          data-testid="task-drawer-readiness-chip"
          title="Readiness"
        >
          {task.readiness_score ?? 0}%
        </span>
        {task.due_date && (
          <span
            className={`px-1.5 py-0.5 rounded-sm text-[10.5px] font-mono inline-flex items-center gap-1 ${
              d !== null && d < 0
                ? "bg-[rgba(122,46,46,0.10)] text-[var(--oxblood)]"
                : d !== null && d <= 3
                  ? "bg-amber-50 text-amber-700"
                  : "bg-[var(--parchment)] text-[var(--ink)]"
            }`}
            data-testid="task-drawer-due-pill"
          >
            <Calendar className="w-2.5 h-2.5" />
            {fmtDate(task.due_date)}
          </span>
        )}
      </div>
    </header>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Tab bar
// ═════════════════════════════════════════════════════════════════════
function TabBar({ tab, onTab }) {
  const tabs = [
    { key: "plan",          label: "Plan",          icon: FileText },
    { key: "contributions", label: "Contributions", icon: Users },
    { key: "drafts",        label: "Drafts",        icon: Layers },
    { key: "intelligence",  label: "Intelligence",  icon: Brain },
    { key: "compile",       label: "Compile",       icon: Hammer },
  ];
  return (
    <div
      className="flex gap-5 px-6 border-b border-[var(--rule)]"
      data-testid="task-drawer-tabs"
    >
      {tabs.map((t) => {
        const Icon = t.icon;
        const active = tab === t.key;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onTab(t.key)}
            className={`py-2 pb-2.5 inline-flex items-center gap-1.5 text-[12.5px] transition-colors border-b-2 ${
              active
                ? "border-[var(--ink)] text-[var(--ink)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
            data-testid={`task-drawer-tab-${t.key}`}
          >
            <Icon className="w-3 h-3" strokeWidth={1.7} />
            {t.label}
          </button>
        );
      })}
    </div>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Tab 1 — Plan
// ═════════════════════════════════════════════════════════════════════
function PlanTab({ task, onPatched }) {
  return (
    <div className="space-y-5" data-testid="task-drawer-tab-plan-body">
      <PlanField field="objective"        label="Objective"        task={task} onPatched={onPatched} long />
      <PlanField field="success_criteria" label="Success criteria" task={task} onPatched={onPatched} long />
      <section data-testid="task-drawer-plan-output">
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1">Output</p>
        <p className="text-[13px] text-[var(--ink)]">
          {(task.output_spec?.kind === "template" && task.output_spec?.template_id)
            ? task.output_spec.template_id.replace(/_/g, " ")
            : (task.output_spec?.free_text || "—")}
          {task.output_spec?.formats?.length ? (
            <span className="ml-2 font-mono text-[11px] text-[var(--muted)]">
              · {task.output_spec.formats.join(", ").toUpperCase()}
            </span>
          ) : null}
        </p>
      </section>
      <section data-testid="task-drawer-plan-team">
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">Team</p>
        {(task.team || []).length === 0 ? (
          <p className="text-[12px] italic text-[var(--muted)]">No team members yet.</p>
        ) : (
          <ul className="space-y-1 text-[12.5px] text-[var(--ink)]">
            {(task.team || []).map((m, i) => (
              <li key={i} data-testid={`task-drawer-plan-team-row-${i}`}>
                <span className="font-medium">{m.name || m.email || "—"}</span>
                {m.role ? <span className="text-[var(--muted)]"> · {m.role}</span> : null}
                {m.contribution ? <span className="text-[var(--muted)]"> · {m.contribution}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}


function PlanField({ field, label, task, onPatched, long }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(task[field] || "");
  useEffect(() => { setValue(task[field] || ""); }, [task.id, task[field]]);
  const save = async () => {
    if (value.trim() === (task[field] || "")) { setEditing(false); return; }
    try {
      await api.patch(`/tasks/${task.id}`, { [field]: value });
      toast.success("Saved.");
      setEditing(false);
      onPatched?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  return (
    <section data-testid={`task-drawer-plan-${field}`}>
      <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1">{label}</p>
      {editing ? (
        <div className="space-y-2">
          {long ? (
            <Textarea
              value={value} onChange={(e) => setValue(e.target.value)}
              rows={3} autoFocus
              data-testid={`task-drawer-plan-${field}-input`}
            />
          ) : (
            <Input
              value={value} onChange={(e) => setValue(e.target.value)}
              autoFocus
              data-testid={`task-drawer-plan-${field}-input`}
            />
          )}
          <div className="flex gap-2">
            <Button onClick={save} size="sm" data-testid={`task-drawer-plan-${field}-save`}>
              <Save className="w-3 h-3 mr-1.5" /> Save
            </Button>
            <Button
              variant="outline" size="sm"
              onClick={() => { setValue(task[field] || ""); setEditing(false); }}
              data-testid={`task-drawer-plan-${field}-cancel`}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="text-left text-[13px] text-[var(--ink)] inline-flex items-start gap-2 group w-full"
          data-testid={`task-drawer-plan-${field}-display`}
        >
          <span className="flex-1">{task[field] || <span className="italic text-[var(--muted)]">— click to edit</span>}</span>
          <Pencil className="w-3 h-3 text-[var(--muted)] opacity-0 group-hover:opacity-100 shrink-0 mt-0.5" />
        </button>
      )}
    </section>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Tab 2 — Contributions
// ═════════════════════════════════════════════════════════════════════
const STATUS_LABEL = {
  not_started:     "Not started",
  in_progress:     "In progress",
  submitted:       "Submitted",
  approved:        "Approved",
  needs_revision:  "Needs revision",
};

function ContributionsTab({ task, onPatched }) {
  const [revisionFor, setRevisionFor] = useState(null);
  const [revisionNote, setRevisionNote] = useState("");
  const [working, setWorking] = useState(null);
  const [reinviting, setReinviting] = useState(null);
  // Phase F.5 — highlight the logged-in user's row.
  const { account } = useAuth();
  const meEmail = (account?.email || "").toLowerCase();

  const team = task.team || [];

  const patch = async (contributorId, status, note) => {
    setWorking(contributorId + status);
    try {
      await api.patch(`/tasks/${task.id}/contributions/${encodeURIComponent(contributorId)}`, { status, note });
      toast.success("Updated.");
      setRevisionFor(null);
      setRevisionNote("");
      onPatched?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setWorking(null); }
  };

  const reinvite = async (contributorId) => {
    setReinviting(contributorId);
    try {
      const { data } = await api.post(`/tasks/${task.id}/contributors/${encodeURIComponent(contributorId)}/reinvite`);
      const label = data.delivery_status === "send_failed"
        ? "Invite re-sent (email delivery failed — link rotated; share manually)."
        : "Invite re-sent.";
      toast.success(label);
      onPatched?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setReinviting(null); }
  };

  if (team.length === 0) {
    return (
      <p className="text-[12.5px] italic text-[var(--muted)]" data-testid="task-drawer-contributions-empty">
        No contributors yet. Add team members from the Plan tab's wizard.
      </p>
    );
  }

  return (
    <div className="space-y-3" data-testid="task-drawer-tab-contributions-body">
      <ul className="space-y-2">
        {team.map((m, i) => {
          const cid = m.email || m.name || `contributor-${i}`;
          const d = daysUntil(m.due_date);
          const overdue = d !== null && d < 0 && !["submitted", "approved"].includes(m.status);
          const dueSoon = d !== null && d >= 0 && d <= 3 && !["submitted", "approved"].includes(m.status);
          const isMe = !!meEmail && (m.email || "").toLowerCase() === meEmail;
          return (
            <li
              key={cid}
              className={`border rounded-sm p-3 ${
                isMe
                  ? "border-[var(--oxblood)] bg-[rgba(122,46,46,0.04)]"
                  : "border-[var(--rule)] bg-white"
              }`}
              data-testid={`task-drawer-contributions-row-${i}`}
            >
              {isMe && (
                <p
                  className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--oxblood)] mb-1"
                  data-testid={`task-drawer-contributions-your-row-${i}`}
                >
                  Your contribution
                </p>
              )}
              <div className="flex items-start justify-between gap-3 mb-2">
                <div>
                  <p className="text-[13px] text-[var(--ink)]">
                    {m.name || m.email || "—"}
                    {m.role ? <span className="text-[var(--muted)]"> · {m.role}</span> : null}
                  </p>
                  <p className="text-[11.5px] text-[var(--muted)]">{m.email}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] bg-[var(--parchment)] px-1.5 py-0.5 rounded-sm"
                    data-testid={`task-drawer-contributions-mode-${i}`}
                  >
                    {(m.contribution_mode || "akki_account").replace("_", " ")}
                  </span>
                  <span
                    className={`text-[10.5px] uppercase tracking-[0.14em] font-mono px-1.5 py-0.5 rounded-sm ${
                      m.status === "approved"      ? "bg-emerald-50 text-emerald-700" :
                      m.status === "needs_revision" ? "bg-[rgba(122,46,46,0.10)] text-[var(--oxblood)]" :
                      m.status === "submitted"     ? "bg-blue-50 text-blue-700" :
                      m.status === "in_progress"   ? "bg-amber-50 text-amber-700" :
                                                     "bg-[var(--parchment)] text-[var(--muted)]"
                    }`}
                    data-testid={`task-drawer-contributions-status-${i}`}
                  >
                    {STATUS_LABEL[m.status] || STATUS_LABEL.not_started}
                  </span>
                </div>
              </div>
              {m.contribution && (
                <p className="text-[12px] text-[var(--ink)] mb-2">{m.contribution}</p>
              )}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[11px] font-mono text-[var(--muted)]">
                  {m.due_date && (
                    <span className={`inline-flex items-center gap-1 ${overdue ? "text-[var(--oxblood)]" : dueSoon ? "text-amber-700" : ""}`}>
                      <Clock className="w-3 h-3" />
                      {overdue ? `${Math.abs(d)}d overdue` : dueSoon ? `Due in ${d}d` : `Due ${fmtDate(m.due_date)}`}
                    </span>
                  )}
                </div>
                <div className="flex gap-1.5">
                  <Button
                    size="sm" variant="outline"
                    onClick={() => patch(cid, "approved")}
                    disabled={working === cid + "approved" || m.status === "approved"}
                    data-testid={`task-drawer-contributions-approve-${i}`}
                  >
                    <Check className="w-3 h-3 mr-1" /> Approve
                  </Button>
                  <Button
                    size="sm" variant="outline"
                    onClick={() => setRevisionFor(cid)}
                    data-testid={`task-drawer-contributions-request-revision-${i}`}
                  >
                    <RefreshCw className="w-3 h-3 mr-1" /> Request revision
                  </Button>
                  <Button
                    size="sm" variant="ghost"
                    onClick={() => reinvite(cid)}
                    disabled={reinviting === cid}
                    data-testid={`task-drawer-contributions-reinvite-${i}`}
                    title="Re-send invitation (rotates magic-link token if applicable)"
                  >
                    {reinviting === cid ? <Loader2 className="w-3 h-3 animate-spin" /> : <Mail className="w-3 h-3" />}
                  </Button>
                </div>
              </div>
              {revisionFor === cid && (
                <div className="mt-3 border-t border-[var(--rule)] pt-3" data-testid={`task-drawer-contributions-revision-pane-${i}`}>
                  <Textarea
                    value={revisionNote}
                    onChange={(e) => setRevisionNote(e.target.value)}
                    placeholder="What needs to change?"
                    rows={2}
                    data-testid={`task-drawer-contributions-revision-note-${i}`}
                  />
                  <div className="flex gap-1.5 mt-2">
                    <Button
                      size="sm"
                      onClick={() => patch(cid, "needs_revision", revisionNote.trim())}
                      disabled={!revisionNote.trim() || working === cid + "needs_revision"}
                      data-testid={`task-drawer-contributions-revision-send-${i}`}
                    >
                      Send revision request
                    </Button>
                    <Button
                      size="sm" variant="ghost"
                      onClick={() => { setRevisionFor(null); setRevisionNote(""); }}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Tab 3 — Drafts (task-linked docs)
// ═════════════════════════════════════════════════════════════════════
function DraftsTab({ task }) {
  const [params, setParams] = useSearchParams();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let dead = false;
    setLoading(true);
    api.get(`/tasks/${task.id}/drafts`)
      .then(({ data }) => { if (!dead) setDocs(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setDocs([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [task.id]);
  const openInDrawer = (docId) => {
    // Stack pattern: add `doc_id` on top of `task_id`. The
    // <DocumentDrawer> mounted on the host page opens stacked above
    // this Task Drawer.
    const next = new URLSearchParams(params);
    next.set("doc_id", docId);
    setParams(next, { replace: false });
  };
  return (
    <div data-testid="task-drawer-tab-drafts-body">
      {loading ? (
        <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" /> Loading…
        </p>
      ) : docs.length === 0 ? (
        <p className="text-[12.5px] italic text-[var(--muted)]" data-testid="task-drawer-drafts-empty">
          No documents linked to this task yet.
        </p>
      ) : (
        <ul className="space-y-1" data-testid="task-drawer-drafts-list">
          {docs.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                onClick={() => openInDrawer(d.id)}
                className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] inline-flex items-center gap-2"
                data-testid={`task-drawer-drafts-row-${d.id}`}
              >
                <FileText className="w-3 h-3 text-[var(--muted)] shrink-0" />
                <span className="text-[12.5px] text-[var(--ink)] truncate flex-1">
                  {d.name || d.original_filename || d.id}
                </span>
                <span className="text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--muted)]">
                  {d.state || "—"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Tab 4 — Intelligence
// ═════════════════════════════════════════════════════════════════════
function IntelligenceTab({ task, onJumpTab }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [dismissed, setDismissed] = useState(new Set());

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/tasks/${task.id}/intelligence`);
      setData(data);
    } catch (e) {
      setData(null);
      toast.error(apiErrorMessage(e));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [task.id]);

  const regen = async () => {
    setRegenerating(true);
    try {
      await api.post(`/tasks/${task.id}/intelligence/regenerate`);
      // Poll once after a short delay.
      setTimeout(load, 1500);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setRegenerating(false); }
  };

  if (loading) {
    return (
      <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5">
        <Loader2 className="w-3 h-3 animate-spin" /> Loading intelligence…
      </p>
    );
  }
  if (!data) {
    return (
      <p className="text-[12.5px] italic text-[var(--muted)]">Could not load intelligence.</p>
    );
  }

  const rb = data.readiness || { score: 0, components: [] };
  return (
    <div className="space-y-5" data-testid="task-drawer-tab-intelligence-body">
      {/* Readiness breakdown */}
      <section data-testid="task-drawer-intelligence-readiness">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
            Readiness breakdown
          </p>
          <Button
            variant="ghost" size="sm"
            onClick={regen} disabled={regenerating}
            data-testid="task-drawer-intelligence-regen"
          >
            {regenerating ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <RefreshCw className="w-3 h-3 mr-1.5" />}
            Refresh
          </Button>
        </div>
        <div className="border border-[var(--rule)] rounded-sm p-3 bg-[var(--parchment)]">
          <p className="text-[28px] akki-serif text-[var(--ink)] mb-2" data-testid="task-drawer-intelligence-score">
            {rb.score}%
          </p>
          <ul className="space-y-1">
            {(rb.components || []).map((c) => (
              <li key={c.key} className="text-[11.5px] text-[var(--muted)] flex items-center gap-2"
                  data-testid={`task-drawer-intelligence-component-${c.key}`}>
                <span className="font-mono text-[var(--ink)] w-9">{c.weight}%</span>
                <span className="flex-1">{c.label}</span>
                <span className="font-mono text-[var(--ink)]">{c.value}%</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Blockers */}
      <section data-testid="task-drawer-intelligence-blockers">
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">
          Blockers
        </p>
        {data.blockers?.length ? (
          <ul className="space-y-1.5">
            {data.blockers.map((b, i) => (
              <li
                key={i}
                className="text-[12.5px] text-[var(--ink)] inline-flex items-start gap-2"
                data-testid={`task-drawer-intelligence-blocker-${i}`}
              >
                <AlertTriangle
                  className={`w-3 h-3 mt-0.5 shrink-0 ${b.severity === "high" ? "text-[var(--oxblood)]" : "text-amber-600"}`}
                />
                <span>{b.message}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] italic text-[var(--muted)]" data-testid="task-drawer-intelligence-blockers-empty">
            No active blockers.
          </p>
        )}
      </section>

      {/* Gaps */}
      <section data-testid="task-drawer-intelligence-gaps">
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">
          Gaps
        </p>
        {data.gaps?.length ? (
          <ul className="space-y-1.5">
            {data.gaps.map((g, i) => (
              <li
                key={i}
                className="text-[12.5px] text-[var(--ink)]"
                data-testid={`task-drawer-intelligence-gap-${i}`}
              >
                {g.message}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] italic text-[var(--muted)]" data-testid="task-drawer-intelligence-gaps-empty">
            No gaps detected.
          </p>
        )}
      </section>

      {/* Completion roadmap */}
      <section data-testid="task-drawer-intelligence-roadmap">
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">
          Completion roadmap
        </p>
        {data.roadmap?.length ? (
          <ol className="space-y-1.5 list-decimal pl-4">
            {data.roadmap.map((step, i) => (
              <li
                key={i}
                className="text-[12.5px] text-[var(--ink)]"
                data-testid={`task-drawer-intelligence-roadmap-step-${i}`}
              >
                {step.target?.type === "contributor" ? (
                  <button
                    type="button" onClick={() => onJumpTab?.("contributions")}
                    className="text-left hover:underline"
                  >
                    {step.label}
                  </button>
                ) : (
                  <span>{step.label}</span>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[12px] italic text-[var(--muted)]">No steps remaining.</p>
        )}
      </section>

      {/* Recommendations */}
      <section data-testid="task-drawer-intelligence-recommendations">
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <Sparkles className="w-3 h-3" /> Recommendations
        </p>
        {(data.recommendations || []).filter((r) => !dismissed.has(r.id)).length === 0 ? (
          <p className="text-[12px] italic text-[var(--muted)]">All recommendations addressed.</p>
        ) : (
          <ul className="space-y-2">
            {(data.recommendations || []).filter((r) => !dismissed.has(r.id)).map((r) => (
              <li
                key={r.id}
                className="border border-[var(--rule)] rounded-sm p-3 bg-white"
                data-testid={`task-drawer-intelligence-rec-${r.id}`}
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="text-[12.5px] text-[var(--ink)]">{r.title}</p>
                  <span className="text-[9.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                    {r.source}
                  </span>
                </div>
                {r.action && (
                  <p className="text-[11.5px] text-[var(--muted)] mb-2">{r.action}</p>
                )}
                <div className="flex gap-1.5">
                  <Button
                    size="sm" variant="outline"
                    onClick={() => onJumpTab?.("contributions")}
                    data-testid={`task-drawer-intelligence-rec-apply-${r.id}`}
                  >
                    Open
                  </Button>
                  <Button
                    size="sm" variant="ghost"
                    onClick={() => setDismissed((p) => new Set(p).add(r.id))}
                    data-testid={`task-drawer-intelligence-rec-dismiss-${r.id}`}
                  >
                    Dismiss
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Tab 5 — Compile (Phase F.4 · 2026-05-26)
// ═════════════════════════════════════════════════════════════════════
//
// 5-stage compile flow rendered as a horizontal progress strip + a
// stage-specific body panel. The Start Compile / Resume Compile
// button is ALWAYS enabled (per user directive — readiness is
// informational, not a lock). At <80% readiness the start path opens
// a non-blocking confirmation modal that the user can dismiss.
//
const COMPILE_STAGES = [
  { key: "drafting",         label: "Drafting" },
  { key: "review",           label: "Review" },
  { key: "circulation",      label: "Circulation" },
  { key: "final_production", label: "Final" },
  { key: "commit",           label: "Commit" },
];

function CompileTab({ task }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [warnLow, setWarnLow] = useState(false);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const loadSession = async () => {
    try {
      const { data } = await api.get(`/tasks/${task.id}/compile`);
      setSession(data);
    } catch { /* tolerate */ }
    setLoading(false);
  };
  useEffect(() => { loadSession(); /* eslint-disable-next-line */ }, [task.id]);

  const stage = session?.current_stage || null;
  const sessionActive = !!session?.active;

  const startCompile = async () => {
    setBusy(true);
    try {
      await api.post(`/tasks/${task.id}/compile/draft`);
      toast.success("Drafting started.");
      await loadSession();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };
  const onStartClick = () => {
    if ((task.readiness_score ?? 0) < 80 && !sessionActive) {
      setWarnLow(true);
    } else {
      startCompile();
    }
  };

  if (loading) {
    return <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5">
      <Loader2 className="w-3 h-3 animate-spin" /> Loading compile state…
    </p>;
  }

  return (
    <div className="space-y-5" data-testid="task-drawer-tab-compile-body">
      {/* Header — Start/Resume button + readiness chip (informational) */}
      <div className="flex items-center justify-between gap-3" data-testid="task-drawer-compile-header">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={onStartClick}
            disabled={busy}
            className="bg-[var(--oxblood)] hover:bg-[var(--oxblood-deep)] text-white"
            data-testid="task-drawer-compile-start"
          >
            {busy && <Loader2 className="w-3 h-3 animate-spin mr-1.5" />}
            {sessionActive ? "Resume Compile" : "Start Compile"}
          </Button>
          <span
            className="text-[11px] font-mono text-[var(--muted)] inline-flex items-center gap-1"
            data-testid="task-drawer-compile-readiness-chip"
            title="Readiness — informational only, does not gate the compile button"
          >
            <span className="text-[var(--ink)]">{task.readiness_score ?? 0}%</span>
            <span>readiness</span>
          </span>
        </div>
      </div>

      {/* Progress strip */}
      <div className="flex items-center gap-2" data-testid="task-drawer-compile-progress">
        {COMPILE_STAGES.map((s, i) => {
          const reached = stage && COMPILE_STAGES.findIndex((x) => x.key === stage) >= i;
          const isCurrent = stage === s.key;
          const stageCompleted = stage && COMPILE_STAGES.findIndex((x) => x.key === stage) > i;
          return (
            <React.Fragment key={s.key}>
              <div
                className={`flex items-center gap-1.5 ${isCurrent ? "text-[var(--ink)]" : reached ? "text-[var(--muted)]" : "text-[var(--muted)]"}`}
                data-testid={`task-drawer-compile-stage-${s.key}`}
              >
                <span
                  className={`w-5 h-5 rounded-full text-[10px] font-mono flex items-center justify-center ${
                    isCurrent ? "bg-[var(--oxblood)] text-white" :
                    stageCompleted ? "bg-[var(--ink)] text-white" :
                    "bg-[var(--parchment)] text-[var(--muted)]"
                  }`}
                  data-testid={`task-drawer-compile-stage-pip-${s.key}`}
                >
                  {stageCompleted ? <Check className="w-3 h-3" /> : (i + 1)}
                </span>
                <span className="text-[11px] uppercase tracking-[0.14em] font-mono">{s.label}</span>
              </div>
              {i < COMPILE_STAGES.length - 1 && <span className="flex-1 h-px bg-[var(--rule)]" />}
            </React.Fragment>
          );
        })}
      </div>

      {/* Per-stage panels */}
      {!sessionActive && stage !== "commit" && (
        <div
          className="border border-[var(--rule)] rounded-sm p-4 bg-[var(--parchment)]"
          data-testid="task-drawer-compile-idle"
        >
          <p className="text-[12.5px] text-[var(--ink)]">
            Ready to compile. {((task.team || []).filter((m) => m.status === "approved").length)} of {(task.team || []).length} contributors approved.
          </p>
          <p className="text-[11.5px] italic text-[var(--muted)] mt-1">
            The compile button is always enabled — readiness is informational.
          </p>
        </div>
      )}

      {stage === "drafting" && sessionActive && (
        <CompileDraftingPanel task={task} session={session} onAdvance={loadSession} />
      )}
      {stage === "review" && sessionActive && (
        <CompileReviewPanel task={task} session={session} onAdvance={loadSession} navigate={navigate} setParams={setParams} params={params} />
      )}
      {stage === "circulation" && sessionActive && (
        <CompileCirculationPanel task={task} session={session} onAdvance={loadSession} />
      )}
      {stage === "final_production" && sessionActive && (
        <CompileFinalPanel task={task} session={session} onAdvance={loadSession} navigate={navigate} setParams={setParams} params={params} />
      )}
      {stage === "commit" && (
        <CompileCommitPanel task={task} session={session} onAdvance={loadSession} navigate={navigate} setParams={setParams} params={params} />
      )}

      {/* Non-blocking low-readiness warning modal */}
      {warnLow && (
        <div
          className="fixed inset-0 bg-black/30 z-[60] flex items-center justify-center"
          data-testid="task-drawer-compile-low-readiness-modal"
        >
          <div className="bg-white border border-[var(--rule)] rounded-sm p-5 max-w-md">
            <p className="text-[14px] text-[var(--ink)] mb-2">
              Your readiness is {task.readiness_score ?? 0}%.
            </p>
            <p className="text-[12.5px] text-[var(--muted)] mb-4">
              Some contributions are still pending. You can compile anyway — Akki will draft from what's submitted and flag the gaps.
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => setWarnLow(false)} data-testid="task-drawer-compile-low-readiness-cancel">
                Cancel
              </Button>
              <Button
                size="sm"
                className="bg-[var(--oxblood)] hover:bg-[var(--oxblood-deep)] text-white"
                onClick={() => { setWarnLow(false); startCompile(); }}
                data-testid="task-drawer-compile-low-readiness-continue"
              >
                Compile anyway
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function CompileDraftingPanel({ task, session, onAdvance }) {
  return (
    <div className="space-y-3" data-testid="task-drawer-compile-panel-drafting">
      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
        Stage 1 · Drafting
      </p>
      <p className="text-[12.5px] text-[var(--ink)]">
        Akki is drafting from {(task.team || []).filter((m) => ["submitted", "approved"].includes(m.status)).length} contribution{(task.team || []).filter((m) => ["submitted", "approved"].includes(m.status)).length === 1 ? "" : "s"} + your output spec.
      </p>
      <ul className="space-y-1" data-testid="task-drawer-compile-drafts-list">
        {(session.draft_artefact_ids || []).map((did) => (
          <li key={did} className="px-2 py-1.5 rounded-sm bg-[var(--parchment)] text-[12px] font-mono text-[var(--ink)]"
              data-testid={`task-drawer-compile-draft-${did}`}>
            {did}
          </li>
        ))}
      </ul>
      <Button
        size="sm"
        onClick={async () => {
          try {
            await api.post(`/tasks/${task.id}/compile/review/complete`, { skip_circulation: false });
            toast.success("Advanced to Review.");
            // Actually, drafting → review requires we just keep drafts;
            // but the brief flow is Draft → Review → Circulation. The
            // "Next: Review" button here marks the drafting visible
            // panel done; the user actually edits drafts in Review.
            onAdvance?.();
          } catch (e) { toast.error(apiErrorMessage(e)); }
        }}
        data-testid="task-drawer-compile-next-review"
        disabled={(session.draft_artefact_ids || []).length === 0}
      >
        Next: Review <ArrowUpRight className="w-3 h-3 ml-1" />
      </Button>
    </div>
  );
}


function CompileReviewPanel({ task, session, onAdvance, setParams, params }) {
  const openDraft = (did) => {
    const next = new URLSearchParams(params);
    next.set("doc_id", did);
    setParams(next, { replace: false });
  };
  const advance = async (skipCirc) => {
    try {
      await api.post(`/tasks/${task.id}/compile/review/complete`, { skip_circulation: skipCirc });
      toast.success(skipCirc ? "Skipped to Final production." : "Advanced to Circulation.");
      onAdvance?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  return (
    <div className="space-y-3" data-testid="task-drawer-compile-panel-review">
      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
        Stage 2 · Review &amp; Editing
      </p>
      <p className="text-[12.5px] text-[var(--ink)]">
        Open each draft to edit inline or via the prompted-edit composer.
      </p>
      <ul className="space-y-1" data-testid="task-drawer-compile-review-list">
        {(session.draft_artefact_ids || []).map((did) => (
          <li key={did}>
            <button
              type="button" onClick={() => openDraft(did)}
              className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] text-[12.5px] inline-flex items-center gap-1.5"
              data-testid={`task-drawer-compile-review-row-${did}`}
            >
              <FileText className="w-3 h-3" /> {did}
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2 pt-2 border-t border-[var(--rule)]">
        <Button size="sm" onClick={() => advance(false)} data-testid="task-drawer-compile-next-circulation">
          Send for circulation <ArrowUpRight className="w-3 h-3 ml-1" />
        </Button>
        <Button size="sm" variant="outline" onClick={() => advance(true)} data-testid="task-drawer-compile-skip-circulation">
          Skip circulation, go to Final
        </Button>
      </div>
    </div>
  );
}


function CompileCirculationPanel({ task, session, onAdvance }) {
  const [emails, setEmails] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const send = async () => {
    const list = emails.split(/[,\s]+/).map((e) => e.trim()).filter(Boolean);
    if (list.length === 0) { toast.error("Add at least one reviewer email."); return; }
    setSending(true);
    try {
      const { data } = await api.post(`/tasks/${task.id}/compile/circulation/send`, {
        reviewer_emails: list,
        message: message || null,
        base_url: window.location.origin,
      });
      const failed = (data.sent || []).filter((s) => s.status.includes("fail")).length;
      if (failed === 0) toast.success(`Sent ${list.length} invite${list.length === 1 ? "" : "s"}.`);
      else toast.warning(`Sent with ${failed} delivery failure${failed === 1 ? "" : "s"} — links still valid.`);
      setEmails(""); setMessage("");
      onAdvance?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSending(false); }
  };
  const close = async () => {
    try {
      await api.post(`/tasks/${task.id}/compile/circulation/close`);
      toast.success("Circulation closed.");
      onAdvance?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  const comments = session.circulation?.comments || [];
  const sent = session.circulation?.sent_status || [];
  return (
    <div className="space-y-3" data-testid="task-drawer-compile-panel-circulation">
      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
        Stage 3 · Circulation
      </p>
      {sent.length === 0 ? (
        <>
          <Input
            value={emails} onChange={(e) => setEmails(e.target.value)}
            placeholder="reviewer1@org.com, reviewer2@org.com"
            data-testid="task-drawer-compile-circulation-emails"
          />
          <Textarea
            value={message} onChange={(e) => setMessage(e.target.value)}
            rows={2} placeholder="Optional note (e.g., 'Please focus on the risk section')"
            data-testid="task-drawer-compile-circulation-message"
          />
          <Button size="sm" onClick={send} disabled={sending}
            data-testid="task-drawer-compile-circulation-send">
            {sending ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <Mail className="w-3 h-3 mr-1.5" />}
            Send for review
          </Button>
        </>
      ) : (
        <>
          <ul className="space-y-1" data-testid="task-drawer-compile-circulation-recipients">
            {sent.map((s, i) => (
              <li key={i} className="text-[12px] text-[var(--ink)] flex items-center gap-2"
                  data-testid={`task-drawer-compile-circulation-recipient-${i}`}>
                <Mail className="w-3 h-3 text-[var(--muted)]" />
                <span className="flex-1 truncate">{s.email}</span>
                <span className={`text-[10px] font-mono uppercase tracking-[0.14em] ${s.status.includes("fail") ? "text-[var(--oxblood)]" : "text-[var(--muted)]"}`}>
                  {s.status}
                </span>
              </li>
            ))}
          </ul>
          <div className="border-t border-[var(--rule)] pt-2">
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">
              Comments received ({comments.length})
            </p>
            {comments.length === 0 ? (
              <p className="text-[11.5px] italic text-[var(--muted)]"
                 data-testid="task-drawer-compile-circulation-comments-empty">
                Waiting on reviewers.
              </p>
            ) : (
              <ul className="space-y-2" data-testid="task-drawer-compile-circulation-comments">
                {comments.map((c) => (
                  <li key={c.id} className="border border-[var(--rule)] rounded-sm p-2 bg-white"
                      data-testid={`task-drawer-compile-circulation-comment-${c.id}`}>
                    <p className="text-[11px] font-mono text-[var(--muted)] mb-1">{c.reviewer}</p>
                    <p className="text-[12.5px] text-[var(--ink)]">{c.comment}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Button size="sm" onClick={close} data-testid="task-drawer-compile-circulation-close">
            Close circulation <ArrowUpRight className="w-3 h-3 ml-1" />
          </Button>
        </>
      )}
    </div>
  );
}


function CompileFinalPanel({ task, session, onAdvance, setParams, params }) {
  const [applying, setApplying] = useState(null);
  const openDraft = (did) => {
    const next = new URLSearchParams(params);
    next.set("doc_id", did);
    setParams(next, { replace: false });
  };
  const applyAction = async (cid, action) => {
    setApplying(cid + action);
    try {
      await api.post(`/tasks/${task.id}/compile/final-production/apply-comment`, { comment_id: cid, action });
      toast.success(`Comment ${action === "apply" ? "applied" : action === "discard" ? "discarded" : "marked for manual edit"}.`);
      onAdvance?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setApplying(null); }
  };
  const complete = async () => {
    try {
      await api.post(`/tasks/${task.id}/compile/final-production/complete`);
      toast.success("Advanced to Commit.");
      onAdvance?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };
  const comments = session.circulation?.comments || [];
  const pending = comments.filter((c) => !c.status);
  return (
    <div className="space-y-3" data-testid="task-drawer-compile-panel-final">
      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
        Stage 4 · Final production
      </p>
      <p className="text-[12.5px] text-[var(--ink)]">
        {comments.length === 0
          ? "No reviewer comments to apply. Mark complete to move to Commit."
          : `${pending.length} of ${comments.length} comments pending. Apply or discard each.`}
      </p>
      {comments.length > 0 && (
        <ul className="space-y-2" data-testid="task-drawer-compile-final-comments">
          {comments.map((c) => (
            <li
              key={c.id}
              className="border border-[var(--rule)] rounded-sm p-3 bg-white"
              data-testid={`task-drawer-compile-final-comment-${c.id}`}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-[11px] font-mono text-[var(--muted)]">{c.reviewer}</p>
                {c.status && (
                  <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
                    {c.status}
                  </span>
                )}
              </div>
              <p className="text-[12.5px] text-[var(--ink)] mb-2">{c.comment}</p>
              {!c.status && (
                <div className="flex gap-1.5">
                  <Button size="sm" variant="outline" onClick={() => applyAction(c.id, "apply")}
                          disabled={applying === c.id + "apply"}
                          data-testid={`task-drawer-compile-final-apply-${c.id}`}>
                    {applying === c.id + "apply"
                      ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" />
                      : <Check className="w-3 h-3 mr-1.5" />}
                    Apply
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => applyAction(c.id, "discard")}
                          data-testid={`task-drawer-compile-final-discard-${c.id}`}>
                    Discard
                  </Button>
                  {c.doc_id && (
                    <Button size="sm" variant="ghost" onClick={() => openDraft(c.doc_id)}
                            data-testid={`task-drawer-compile-final-edit-manual-${c.id}`}>
                      Edit manually
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      <Button size="sm" onClick={complete} data-testid="task-drawer-compile-final-complete">
        Mark final production complete <ArrowUpRight className="w-3 h-3 ml-1" />
      </Button>
    </div>
  );
}


function CompileCommitPanel({ task, session, onAdvance, setParams, params }) {
  const [committing, setCommitting] = useState(false);
  const drafts = session.final_artefact_ids?.length ? session.final_artefact_ids : (session.draft_artefact_ids || []);
  const openDraft = (did) => {
    const next = new URLSearchParams(params);
    next.set("doc_id", did);
    setParams(next, { replace: false });
  };
  const commit = async () => {
    setCommitting(true);
    try {
      const { data } = await api.post(`/tasks/${task.id}/compile/commit`);
      toast.success(`Committed ${data.committed?.length || 0} draft${(data.committed?.length || 0) === 1 ? "" : "s"}.`);
      if (data.task_closed) toast.success("Task auto-closed.");
      onAdvance?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setCommitting(false); }
  };
  return (
    <div className="space-y-3" data-testid="task-drawer-compile-panel-commit">
      <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
        Stage 5 · Commit
      </p>
      <p className="text-[12.5px] text-[var(--ink)]">
        Final review — committing lifts the DRAFT watermark and locks the deliverable.
      </p>
      <ul className="space-y-1" data-testid="task-drawer-compile-commit-list">
        {drafts.map((did) => (
          <li key={did}>
            <button type="button" onClick={() => openDraft(did)}
                    className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] text-[12.5px] inline-flex items-center gap-1.5"
                    data-testid={`task-drawer-compile-commit-row-${did}`}>
              <FileText className="w-3 h-3" /> {did}
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2 pt-2 border-t border-[var(--rule)]">
        <Button size="sm" onClick={commit} disabled={committing || drafts.length === 0}
                className="bg-[var(--oxblood)] hover:bg-[var(--oxblood-deep)] text-white"
                data-testid="task-drawer-compile-commit-final">
          {committing ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <Check className="w-3 h-3 mr-1.5" />}
          Commit final
        </Button>
      </div>
    </div>
  );
}


// ═════════════════════════════════════════════════════════════════════
// Footer CTAs
// ═════════════════════════════════════════════════════════════════════
function FooterCTAs({ task }) {
  const navigate = useNavigate();
  const id = encodeURIComponent(task.id);
  const buildSolva     = () => `/app/solva?ctx_type=task&ctx_id=${id}`;
  const buildChat      = () => `/app/chat?ctx_type=task&ctx_id=${id}`;
  const buildBrief     = () => `/app/solva?ctx_type=task&ctx_id=${id}&submodule=develop_strategy&starter=${encodeURIComponent(task.name || "")}`;
  const buildHypothesis = () => `/app/solva?ctx_type=task&ctx_id=${id}&submodule=simulate_hypothesis&starter=${encodeURIComponent(task.objective || "")}`;

  const onShare = async () => {
    const url = `${window.location.origin}/app/task-manager?task_id=${task.id}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Share link copied.");
      // Audit row via existing tasks PATCH-by-no-op pattern would require
      // a dedicated endpoint; the audit lives implicitly via the
      // PATCH/copy combination — F.5 will add an explicit `task.shared`
      // audit event when the share-tracking endpoint lands.
    } catch (e) {
      toast.error("Could not copy share link.");
    }
  };

  return (
    <footer className="px-6 py-4 border-t border-[var(--rule)] bg-[var(--parchment)] flex flex-wrap gap-2" data-testid="task-drawer-footer">
      <Button
        size="sm" variant="outline"
        onClick={() => navigate(buildSolva())}
        data-testid="task-drawer-cta-solva"
      >
        <Layers className="w-3 h-3 mr-1.5" /> Use in Solva
      </Button>
      <Button
        size="sm" variant="outline"
        onClick={() => navigate(buildChat())}
        data-testid="task-drawer-cta-chat"
      >
        <MessageCircle className="w-3 h-3 mr-1.5" /> Use in Chat
      </Button>
      <Button
        size="sm" variant="outline"
        onClick={() => navigate(buildBrief())}
        data-testid="task-drawer-cta-brief"
      >
        <ArrowUpRight className="w-3 h-3 mr-1.5" /> Generate brief
      </Button>
      <Button
        size="sm" variant="outline"
        onClick={() => navigate(buildHypothesis())}
        data-testid="task-drawer-cta-hypothesis"
      >
        <Send className="w-3 h-3 mr-1.5" /> Test hypothesis
      </Button>
      <Button
        size="sm" variant="outline"
        onClick={onShare}
        data-testid="task-drawer-cta-share"
        className="ml-auto"
      >
        <Share2 className="w-3 h-3 mr-1.5" /> Share task
      </Button>
    </footer>
  );
}
