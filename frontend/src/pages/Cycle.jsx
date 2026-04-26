import React, { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Users, MessageCircleQuestion, Send, Inbox, Plus, Trash2, Sparkles,
  Loader2, ArrowRight, Clock, CheckCircle2, Mail, Copy, ExternalLink, Edit3,
  FileText, CalendarClock,
} from "lucide-react";
import ReportsTab from "@/components/cycle/ReportsTab";
import CycleTracker from "@/components/cycle/CycleTracker";
import { Eye } from "lucide-react";

const CATS = [
  "audit", "risk", "operational", "strategic",
  "people", "financial", "regulatory", "general",
];

function shortDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }); } catch { return iso; }
}

// ---------- Question Bank ----------
function QuestionBank({ contextId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("open");
  const [text, setText] = useState("");
  const [cat, setCat] = useState("general");
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const params = filter === "all" ? "" : `?status=${filter}`;
      const { data } = await api.get(`/contexts/${contextId}/questions${params}`);
      setItems(data.questions || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId, filter]);

  useEffect(() => { load(); }, [load]);

  const onAdd = async () => {
    if (text.trim().length < 8) { toast.message("A question needs at least 8 characters."); return; }
    try {
      await api.post(`/contexts/${contextId}/questions`, { text: text.trim(), category: cat });
      setText("");
      toast.success("Added to the Question Bank.");
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onSeed = async () => {
    setSeeding(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/questions/seed-from-briefings`);
      toast.success(`Seeded ${data.seeded} question${data.seeded === 1 ? "" : "s"} from past briefings.`);
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSeeding(false); }
  };

  const onRetire = async (qid) => {
    try {
      await api.patch(`/contexts/${contextId}/questions/${qid}`, { status: "retired" });
      toast.success("Question retired.");
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white border border-[var(--rule)] rounded-lg p-5" data-testid="question-bank-add">
        <p className="akki-overline mb-2">Add a question</p>
        <div className="flex gap-2 flex-wrap">
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What hasn't the board got an answer to yet?"
            className="flex-1 min-w-[280px] h-10 bg-[var(--cream)] border-[var(--rule)] text-sm"
            data-testid="question-input"
          />
          <Select value={cat} onValueChange={setCat}>
            <SelectTrigger className="w-44 h-10 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="question-cat">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button onClick={onAdd} className="h-10 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="question-add-btn">
            <Plus className="w-3.5 h-3.5 mr-1.5" /> Add
          </Button>
          <Button onClick={onSeed} disabled={seeding} variant="outline" className="h-10 border-[var(--rule)]" data-testid="question-seed-btn">
            {seeding
              ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Seeding…</>
              : <><Sparkles className="w-3.5 h-3.5 mr-1.5 text-[var(--accent)]" /> Seed from briefings</>}
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-1 border-b border-[var(--rule)]">
        {["open", "answered", "retired", "all"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 text-[13px] capitalize ${filter === f ? "text-[var(--ink)] font-medium border-b-2 border-[var(--accent)]" : "text-[var(--muted)] hover:text-[var(--deep)]"}`}
            data-testid={`question-filter-${f}`}
          >{f}</button>
        ))}
      </div>

      {loading ? (
        <p className="p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
      ) : items.length === 0 ? (
        <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-10 text-center" data-testid="question-bank-empty">
          <MessageCircleQuestion className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
          <p className="akki-lead mb-2">No {filter === "all" ? "" : filter} questions yet.</p>
          <p className="text-[13px] text-[var(--muted)] max-w-md mx-auto">
            Click <span className="text-[var(--accent)] font-medium">Seed from briefings</span> to pull every "question to take into the room" from your past briefings into the bank.
          </p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="question-list">
          {items.map((q) => (
            <div key={q.id} className="bg-white border border-[var(--rule)] rounded-lg p-4 flex items-start gap-3" data-testid={`question-${q.id}`}>
              <div className="flex-1 min-w-0">
                <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug mb-1.5">{q.text}</p>
                <div className="flex flex-wrap gap-2 text-[11px] text-[var(--muted)]">
                  <span className="akki-context-chip">{q.category}</span>
                  {q.times_asked > 0 && <span>asked {q.times_asked}×</span>}
                  {q.last_asked_at && <span>last {shortDate(q.last_asked_at)}</span>}
                  <span className="text-[var(--muted)]/70">{q.source}</span>
                </div>
              </div>
              {q.status === "open" && (
                <button onClick={() => onRetire(q.id)} className="text-[12px] text-[var(--muted)] hover:text-[var(--accent)]" data-testid={`question-retire-${q.id}`}>
                  Retire
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Reportees ----------
function Reportees({ contextId }) {
  const [items, setItems] = useState([]);
  const [committees, setCommittees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [title, setTitle] = useState("");
  const [areas, setAreas] = useState([]);
  const [committeeId, setCommitteeId] = useState("");
  const [filterCommittee, setFilterCommittee] = useState("all");

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const [r, c] = await Promise.all([
        api.get(`/contexts/${contextId}/reportees`),
        api.get(`/contexts/${contextId}/cycle/committees`),
      ]);
      setItems(r.data.reportees || []);
      setCommittees(c.data.committees || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  const onAdd = async () => {
    if (!name.trim() || !email.trim() || !title.trim()) { toast.message("Name, email and title are required."); return; }
    try {
      await api.post(`/contexts/${contextId}/reportees`, {
        name: name.trim(), email: email.trim(), title: title.trim(), areas,
        committee_id: committeeId || null,
      });
      setName(""); setEmail(""); setTitle(""); setAreas([]); setCommitteeId("");
      toast.success("Reportee added.");
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onRemove = async (rid) => {
    try {
      await api.delete(`/contexts/${contextId}/reportees/${rid}`);
      toast.success("Reportee removed.");
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const visible = items.filter((r) => {
    if (filterCommittee === "all") return true;
    if (filterCommittee === "none") return !r.committee_id;
    return r.committee_id === filterCommittee;
  });
  const committeeName = (cid) => committees.find((c) => c.id === cid)?.name;

  return (
    <div className="space-y-6">
      <div className="bg-white border border-[var(--rule)] rounded-lg p-5" data-testid="reportee-add">
        <p className="akki-overline mb-3">Add a reportee</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <Input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} className="h-10 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="reportee-name" />
          <Input placeholder="email@company.com" value={email} onChange={(e) => setEmail(e.target.value)} className="h-10 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="reportee-email" />
          <Input placeholder="Title (e.g. Head of Credit)" value={title} onChange={(e) => setTitle(e.target.value)} className="h-10 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="reportee-title" />
        </div>
        <div className="mt-3">
          <p className="text-[11px] uppercase tracking-wider text-[var(--muted)] mb-2">Areas they own (toggle)</p>
          <div className="flex flex-wrap gap-1.5">
            {CATS.map((c) => {
              const on = areas.includes(c);
              return (
                <button
                  key={c}
                  onClick={() => setAreas((prev) => prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c])}
                  className={`px-2.5 py-1 text-[12px] rounded-full border transition-colors ${on ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"}`}
                  data-testid={`reportee-area-${c}`}
                >{c}</button>
              );
            })}
          </div>
        </div>
        {committees.length > 0 && (
          <div className="mt-3">
            <p className="text-[11px] uppercase tracking-wider text-[var(--muted)] mb-2">Committee (optional)</p>
            <Select value={committeeId || "none"} onValueChange={(v) => setCommitteeId(v === "none" ? "" : v)}>
              <SelectTrigger className="w-72 h-10 bg-[var(--cream)] border-[var(--rule)] text-sm" data-testid="reportee-committee-trigger">
                <SelectValue placeholder="Not committee-scoped" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">— Not committee-scoped —</SelectItem>
                {committees.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}{c.kind ? ` · ${c.kind}` : ""}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="mt-4">
          <Button onClick={onAdd} className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="reportee-add-btn">
            <Plus className="w-3.5 h-3.5 mr-1.5" /> Add reportee
          </Button>
        </div>
      </div>

      {committees.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap" data-testid="reportee-filter-strip">
          <span className="text-[11px] uppercase tracking-wider text-[var(--muted)]">Filter:</span>
          <button onClick={() => setFilterCommittee("all")} className={`px-2.5 py-1 text-[12px] rounded-full border ${filterCommittee === "all" ? "bg-[var(--ink)] text-white border-[var(--ink)]" : "bg-white border-[var(--rule)] text-[var(--deep)]"}`}>All</button>
          <button onClick={() => setFilterCommittee("none")} className={`px-2.5 py-1 text-[12px] rounded-full border ${filterCommittee === "none" ? "bg-[var(--ink)] text-white border-[var(--ink)]" : "bg-white border-[var(--rule)] text-[var(--deep)]"}`}>Unscoped</button>
          {committees.map((c) => (
            <button key={c.id} onClick={() => setFilterCommittee(c.id)} className={`px-2.5 py-1 text-[12px] rounded-full border ${filterCommittee === c.id ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-white border-[var(--rule)] text-[var(--deep)]"}`}>{c.name}</button>
          ))}
        </div>
      )}

      {loading ? (
        <p className="p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-10 text-center" data-testid="reportee-empty">
          <Users className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
          <p className="akki-lead mb-2">{items.length === 0 ? "No reportees yet." : "No reportees match this filter."}</p>
          <p className="text-[13px] text-[var(--muted)]">{items.length === 0 ? "Add the people who report into you so AKKI can run reporting cycles for them." : "Try a different filter, or add one for this committee."}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="reportee-list">
          {visible.map((r) => (
            <div key={r.id} className="bg-white border border-[var(--rule)] rounded-lg p-4" data-testid={`reportee-${r.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="akki-serif text-[15px] text-[var(--ink)]">{r.name}</p>
                  <p className="text-[12.5px] text-[var(--deep)]">{r.title}</p>
                  <p className="text-[12px] text-[var(--muted)] mt-1 font-mono">{r.email}</p>
                </div>
                <button onClick={() => onRemove(r.id)} className="text-[var(--muted)] hover:text-[var(--accent)]" data-testid={`reportee-remove-${r.id}`}>
                  <Trash2 className="w-4 h-4" strokeWidth={1.6} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1 mt-2.5">
                {r.committee_id && committeeName(r.committee_id) && (
                  <span className="akki-context-chip bg-[var(--chrome)]/10 text-[var(--chrome)] border-[var(--chrome)]/20">
                    {committeeName(r.committee_id)}
                  </span>
                )}
                {r.areas?.map((a) => <span key={a} className="akki-context-chip">{a}</span>)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Schedule modal ----------
function ScheduleModal({ open, onClose, contextId, committees, current, onSaved, onCleared }) {
  const [cadence, setCadence] = useState(current?.cadence || "weekly");
  const [weekday, setWeekday] = useState(current?.weekday || "mon");
  const [tpl, setTpl] = useState(current?.cycle_name_template || "{month} report");
  const [offset, setOffset] = useState(current?.deadline_offset_days || 10);
  const [committeeId, setCommitteeId] = useState(current?.committee_id || "");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setCadence(current?.cadence || "weekly");
      setWeekday(current?.weekday || "mon");
      setTpl(current?.cycle_name_template || "{month} report");
      setOffset(current?.deadline_offset_days || 10);
      setCommitteeId(current?.committee_id || "");
    }
  }, [open, current]);

  const onSave = async () => {
    setBusy(true);
    try {
      const { data } = await api.put(`/contexts/${contextId}/cycle/schedule`, {
        cadence, weekday, cycle_name_template: tpl,
        deadline_offset_days: Number(offset) || 10,
        committee_id: committeeId || null, enabled: true,
      });
      toast.success(`Scheduled — next run ${new Date(data.schedule.next_run_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}.`);
      onSaved(data.schedule);
      onClose();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const onClear = async () => {
    if (!confirm("Stop the recurring cycle? You can re-schedule any time.")) return;
    setBusy(true);
    try {
      await api.delete(`/contexts/${contextId}/cycle/schedule`);
      toast.success("Schedule cleared.");
      onCleared();
      onClose();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  const days = [["mon","Mon"],["tue","Tue"],["wed","Wed"],["thu","Thu"],["fri","Fri"],["sat","Sat"],["sun","Sun"]];
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg bg-[var(--cream)] border border-[var(--rule)]" data-testid="schedule-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[22px] font-normal">Schedule recurring cycle</DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            AKKI auto-drafts checklists on your cadence — they land in <em>Pending your approval</em>.
            You still gate every dispatch.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <p className="akki-overline mb-1.5">Cadence</p>
            <div className="flex gap-1.5">
              {[["weekly","Weekly"],["monthly","Monthly"]].map(([v,l]) => (
                <button key={v} onClick={() => setCadence(v)}
                  className={`px-3 py-1.5 text-[13px] rounded-full border ${cadence === v ? "bg-[var(--ink)] text-white border-[var(--ink)]" : "bg-white border-[var(--rule)] text-[var(--deep)]"}`}
                  data-testid={`schedule-cadence-${v}`}>{l}</button>
              ))}
            </div>
          </div>
          <div>
            <p className="akki-overline mb-1.5">Day of week</p>
            <div className="flex gap-1 flex-wrap">
              {days.map(([v, l]) => (
                <button key={v} onClick={() => setWeekday(v)}
                  className={`px-2.5 py-1 text-[12px] rounded-full border min-w-[44px] ${weekday === v ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-white border-[var(--rule)] text-[var(--deep)]"}`}
                  data-testid={`schedule-weekday-${v}`}>{l}</button>
              ))}
            </div>
          </div>
          <div>
            <p className="akki-overline mb-1.5">Cycle name template</p>
            <Input value={tpl} onChange={(e) => setTpl(e.target.value)}
              placeholder="e.g. {month} report"
              className="h-10 bg-white border-[var(--rule)] text-sm"
              data-testid="schedule-template-input" />
            <p className="text-[11px] text-[var(--muted)] mt-1.5">
              Tokens: <code>{"{month}"}</code>, <code>{"{date}"}</code>, <code>{"{iso_week}"}</code>, <code>{"{year}"}</code>.
            </p>
          </div>
          <div>
            <p className="akki-overline mb-1.5">Deadline offset (days after draft)</p>
            <Input type="number" min={2} max={60} value={offset}
              onChange={(e) => setOffset(e.target.value)}
              className="h-10 bg-white border-[var(--rule)] text-sm w-32"
              data-testid="schedule-offset-input" />
          </div>
          {committees.length > 0 && (
            <div>
              <p className="akki-overline mb-1.5">Scope (optional)</p>
              <Select value={committeeId || "none"} onValueChange={(v) => setCommitteeId(v === "none" ? "" : v)}>
                <SelectTrigger className="h-10 bg-white border-[var(--rule)] text-sm" data-testid="schedule-committee-trigger">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— Whole context —</SelectItem>
                  {committees.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}{c.kind ? ` · ${c.kind}` : ""}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rule)]">
          {current && (
            <Button variant="outline" onClick={onClear} disabled={busy} className="border-red-200 text-red-700 hover:bg-red-50 mr-auto" data-testid="schedule-clear-btn">
              <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Clear schedule
            </Button>
          )}
          <Button variant="outline" onClick={onClose} className="border-[var(--rule)]">Cancel</Button>
          <Button onClick={onSave} disabled={busy} className="bg-[var(--chrome)] text-white" data-testid="schedule-save-btn">
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save schedule"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------- Checklists ----------
function Checklists({ contextId }) {
  const [items, setItems] = useState([]);
  const [committees, setCommittees] = useState([]);
  const [scopedCommitteeId, setScopedCommitteeId] = useState(""); // "" = whole context
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [cycleName, setCycleName] = useState("");
  const [deadline, setDeadline] = useState("");
  const [skipped, setSkipped] = useState([]);
  const [reviewing, setReviewing] = useState(null); // checklist being edited
  const [dispatching, setDispatching] = useState(false);
  const [dispatchResult, setDispatchResult] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const [cl, com, sc] = await Promise.all([
        api.get(`/contexts/${contextId}/checklists`),
        api.get(`/contexts/${contextId}/cycle/committees`),
        api.get(`/contexts/${contextId}/cycle/schedule`).catch(() => ({ data: { schedule: null } })),
      ]);
      setItems(cl.data.checklists || []);
      setCommittees(com.data.committees || []);
      setSchedule(sc.data.schedule || null);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  const onGenerate = async () => {
    if (cycleName.trim().length < 3 || deadline.trim().length < 4) {
      toast.message("Cycle name and deadline date are required."); return;
    }
    setGenerating(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/checklists/generate`, {
        cycle_name: cycleName.trim(), deadline_date: deadline.trim(),
        committee_id: scopedCommitteeId || null,
      });
      setSkipped(data.skipped || []);
      toast.success(`Drafted ${data.drafts.length} checklist${data.drafts.length === 1 ? "" : "s"}. Review before dispatching.`);
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setGenerating(false); }
  };

  const pending = items.filter((c) => c.status === "pending_approval");
  const dispatched = items.filter((c) => c.status === "dispatched");
  const responded = items.filter((c) => c.status === "responded");

  const onDispatchAll = async () => {
    if (pending.length === 0) { toast.message("Nothing pending to dispatch."); return; }
    setDispatching(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/checklists/dispatch`, {
        checklist_ids: pending.map((c) => c.id),
      });
      setDispatchResult(data);
      const sentN = data.sent?.length || 0;
      const fbN = data.fallback_mailtos?.length || 0;
      toast.success(`Dispatched ${sentN} via email${fbN ? `, ${fbN} as mailto fallback` : ""}.`);
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setDispatching(false); }
  };

  const onSaveEdit = async (cl, newQuestions, newNote) => {
    try {
      await api.patch(`/contexts/${contextId}/checklists/${cl.id}`, {
        questions: newQuestions, note_to_reportee: newNote,
      });
      setReviewing(null);
      toast.success("Checklist updated.");
      load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <div className="space-y-6">
      {committees.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap" data-testid="checklist-committee-strip">
          <span className="text-[11px] uppercase tracking-wider text-[var(--muted)]">Run cycle for:</span>
          <button
            onClick={() => setScopedCommitteeId("")}
            className={`px-2.5 py-1 text-[12px] rounded-full border transition-colors ${scopedCommitteeId === "" ? "bg-[var(--ink)] text-white border-[var(--ink)]" : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"}`}
            data-testid="checklist-scope-all"
          >Whole context</button>
          {committees.map((c) => (
            <button
              key={c.id}
              onClick={() => setScopedCommitteeId(c.id)}
              className={`px-2.5 py-1 text-[12px] rounded-full border transition-colors ${scopedCommitteeId === c.id ? "bg-[var(--accent)] text-white border-[var(--accent)]" : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"}`}
              data-testid={`checklist-scope-${c.id}`}
            >{c.name}{c.kind ? ` · ${c.kind}` : ""}</button>
          ))}
          {scopedCommitteeId && (
            <span className="text-[11.5px] text-[var(--muted)] italic ml-1">
              Only reportees scoped to this committee will receive checklists.
            </span>
          )}
        </div>
      )}

      <div className="bg-white border border-[var(--rule)] rounded-lg p-5" data-testid="checklist-generate">
        <div className="flex items-start justify-between gap-3 mb-3">
          <p className="akki-overline">Draft checklists for the next cycle</p>
          <button
            onClick={() => setScheduleOpen(true)}
            className={`text-[12px] inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-colors ${schedule?.enabled ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"}`}
            data-testid="schedule-toggle-btn"
          >
            <CalendarClock className="w-3.5 h-3.5" />
            {schedule?.enabled
              ? `${schedule.cadence === "weekly" ? "Weekly" : "Monthly"} · ${schedule.weekday}`
              : "Schedule recurring"}
          </button>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <Input
            value={cycleName}
            onChange={(e) => setCycleName(e.target.value)}
            placeholder="Cycle name — e.g. Q2 2026 board pack"
            className="flex-1 min-w-[240px] h-10 bg-[var(--cream)] border-[var(--rule)] text-sm"
            data-testid="cycle-name-input"
          />
          <Input
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            placeholder="Deadline (e.g. 15 May 2026)"
            className="w-56 h-10 bg-[var(--cream)] border-[var(--rule)] text-sm"
            data-testid="cycle-deadline-input"
          />
          <Button onClick={onGenerate} disabled={generating} className="h-10 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white" data-testid="generate-checklists-btn">
            {generating
              ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Drafting…</>
              : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Draft checklists</>}
          </Button>
        </div>
        <p className="text-[11.5px] text-[var(--muted)] mt-3 leading-relaxed">
          AKKI matches open questions from your bank to each reportee's areas. Anti-spam: a reportee can't be re-prompted within 14 days.
        </p>
        {skipped.length > 0 && (
          <div className="mt-3 text-[12px] bg-[var(--cream-deep)] border border-[var(--rule)] rounded-md p-3" data-testid="checklist-skipped">
            <p className="text-[var(--ink)] font-medium mb-1">Skipped {skipped.length}:</p>
            <ul className="space-y-0.5 text-[var(--deep)]">
              {skipped.map((s, i) => <li key={i}>· <strong>{s.name}</strong> — {s.reason}</li>)}
            </ul>
          </div>
        )}
      </div>

      {pending.length > 0 && (
        <section data-testid="checklist-pending">
          <div className="flex items-center justify-between mb-3">
            <p className="akki-overline">Pending your approval ({pending.length})</p>
            <Button onClick={onDispatchAll} disabled={dispatching} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white" data-testid="dispatch-all-btn">
              {dispatching
                ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Dispatching…</>
                : <><Send className="w-3.5 h-3.5 mr-1.5" /> Approve & dispatch all</>}
            </Button>
          </div>
          <div className="space-y-2">
            {pending.map((c) => (
              <div key={c.id} className="bg-white border border-[var(--accent)]/30 rounded-lg p-4" data-testid={`checklist-${c.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="akki-serif text-[15px] text-[var(--ink)] mb-0.5">{c.reportee_name} · {c.cycle_name}</p>
                    <p className="text-[12px] text-[var(--muted)] font-mono">{c.reportee_email} · due {c.deadline_date}</p>
                    <ul className="mt-3 space-y-1.5">
                      {c.questions.map((q, i) => (
                        <li key={i} className="text-[13px] text-[var(--deep)] flex gap-2">
                          <span className="text-[var(--accent)] flex-none">{i + 1}.</span>
                          <span className="flex-1">{q.text} <span className="text-[10.5px] uppercase tracking-wider text-[var(--muted)]">· {q.category}</span></span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <button onClick={() => setReviewing(c)} className="akki-gesture text-[12px] shrink-0" data-testid={`checklist-edit-${c.id}`}>
                    <Edit3 className="w-3.5 h-3.5" /> Edit
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {dispatchResult && dispatchResult.fallback_mailtos?.length > 0 && (
        <section className="bg-[var(--cream-deep)] border border-[var(--rule)] rounded-lg p-5" data-testid="dispatch-fallback">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Mail className="w-3 h-3 text-[var(--accent)]" /> Mailto fallback
          </p>
          <p className="text-[12.5px] text-[var(--deep)] mb-3">
            Resend isn't configured for this deployment. Click to open each in your email client:
          </p>
          <div className="space-y-1.5">
            {dispatchResult.fallback_mailtos.map((f) => (
              <a key={f.checklist_id} href={f.mailto} className="flex items-center gap-2 text-[13px] text-[var(--accent)] hover:underline" data-testid={`mailto-${f.checklist_id}`}>
                <ExternalLink className="w-3 h-3" /> {f.to}
              </a>
            ))}
          </div>
        </section>
      )}

      {dispatched.length > 0 && (
        <section data-testid="checklist-dispatched">
          <p className="akki-overline mb-3">Awaiting response ({dispatched.length})</p>
          <div className="space-y-2">
            {dispatched.map((c) => (
              <div key={c.id} className="bg-white border border-[var(--rule)] rounded-lg p-3 flex items-center gap-3 text-[13px]">
                <Clock className="w-4 h-4 text-[var(--muted)]" />
                <span className="text-[var(--ink)]">{c.reportee_name}</span>
                <span className="text-[var(--muted)] font-mono">· dispatched {shortDate(c.dispatched_at)} · due {c.deadline_date}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {responded.length > 0 && (
        <section data-testid="checklist-responded">
          <p className="akki-overline mb-3 flex items-center gap-2">
            <CheckCircle2 className="w-3 h-3 text-emerald-700" /> Responded ({responded.length})
          </p>
          <div className="space-y-2">
            {responded.map((c) => (
              <div key={c.id} className="bg-white border border-emerald-200 rounded-lg p-3 flex items-center gap-3 text-[13px]">
                <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                <span className="text-[var(--ink)]">{c.reportee_name}</span>
                <span className="text-[var(--muted)]">· returned {shortDate(c.responded_at)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!loading && items.length === 0 && (
        <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-10 text-center" data-testid="checklist-empty">
          <Send className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
          <p className="akki-lead mb-2">No checklists yet.</p>
          <p className="text-[13px] text-[var(--muted)]">Add reportees, seed your Question Bank, then draft a cycle above.</p>
        </div>
      )}

      <ReviewModal
        cl={reviewing}
        onClose={() => setReviewing(null)}
        onSave={onSaveEdit}
      />
      <ScheduleModal
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        contextId={contextId}
        committees={committees}
        current={schedule}
        onSaved={(s) => setSchedule(s)}
        onCleared={() => setSchedule(null)}
      />
    </div>
  );
}

function ReviewModal({ cl, onClose, onSave }) {
  const [questions, setQuestions] = useState([]);
  const [note, setNote] = useState("");
  useEffect(() => {
    if (cl) {
      setQuestions(cl.questions || []);
      setNote(cl.note_to_reportee || "");
    }
  }, [cl]);
  if (!cl) return null;
  return (
    <Dialog open={!!cl} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl bg-[var(--cream)] border border-[var(--rule)]" data-testid="review-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[20px] font-normal">{cl.reportee_name}</DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            {cl.cycle_name} · due {cl.deadline_date} · {cl.reportee_email}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 max-h-[55vh] overflow-y-auto pr-2">
          {questions.map((q, i) => (
            <div key={i} className="bg-white border border-[var(--rule)] rounded-md p-3">
              <div className="flex items-start gap-2 mb-2">
                <span className="text-[var(--accent)] text-[13px] font-medium">{i + 1}.</span>
                <textarea
                  value={q.text}
                  onChange={(e) => setQuestions((prev) => prev.map((x, ix) => ix === i ? { ...x, text: e.target.value } : x))}
                  className="flex-1 text-[14px] text-[var(--ink)] bg-transparent resize-none focus:outline-none border-b border-transparent focus:border-[var(--accent)]/40"
                  rows={2}
                  data-testid={`review-q-${i}`}
                />
                <button onClick={() => setQuestions((prev) => prev.filter((_, ix) => ix !== i))} className="text-[var(--muted)] hover:text-[var(--accent)]">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
          <div>
            <p className="akki-overline mb-1.5">Personal note (optional)</p>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="A line in your voice — context, urgency, thank-you…"
              rows={3}
              className="w-full text-[13px] bg-white border border-[var(--rule)] rounded-md p-3 focus:outline-none focus:border-[var(--accent)]"
              data-testid="review-note"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--rule)]">
          <Button variant="outline" onClick={onClose} className="border-[var(--rule)]">Cancel</Button>
          <Button onClick={() => onSave(cl, questions, note)} className="bg-[var(--chrome)] text-white" data-testid="review-save-btn">
            Save edits
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------- Inbox ----------
function SubmissionsInbox({ contextId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/submissions`);
      setItems(data.submissions || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>;
  if (items.length === 0) return (
    <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-10 text-center" data-testid="submissions-empty">
      <Inbox className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
      <p className="akki-lead mb-2">No submissions yet.</p>
      <p className="text-[13px] text-[var(--muted)]">When reportees respond, their answers land here.</p>
    </div>
  );
  return (
    <div className="space-y-3" data-testid="submissions-list">
      {items.map((s) => (
        <div key={s.id} className="bg-white border border-[var(--rule)] rounded-lg p-5" data-testid={`submission-${s.id}`}>
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="akki-serif text-[16px] text-[var(--ink)]">{s.reportee_name}</p>
              <p className="text-[12px] text-[var(--muted)] font-mono">{s.cycle_name} · {shortDate(s.submitted_at)}</p>
            </div>
            <span className="akki-context-chip">{s.answers?.length || 0} answers</span>
          </div>
          <ul className="space-y-3">
            {(s.answers || []).map((a, i) => (
              <li key={i} className="border-l-2 border-[var(--accent)]/40 pl-3">
                <p className="text-[12.5px] text-[var(--muted)] mb-0.5">{a.question_text || a.question_id}</p>
                <p className="akki-serif text-[14px] text-[var(--deep)] whitespace-pre-wrap">{a.answer || "—"}</p>
              </li>
            ))}
          </ul>
          {s.notes && (
            <div className="mt-3 pt-3 border-t border-[var(--rule)]">
              <p className="text-[11px] uppercase tracking-wider text-[var(--muted)] mb-1">Their note</p>
              <p className="text-[13px] text-[var(--deep)] italic">{s.notes}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------- Page ----------
export default function Cycle() {
  const { activeContext, account } = useAuth();
  const cid = activeContext?.id;
  const [cycleNames, setCycleNames] = useState([]);
  useEffect(() => {
    (async () => {
      if (!cid) return;
      try {
        const { data } = await api.get(`/contexts/${cid}/checklists`);
        const names = Array.from(new Set((data.checklists || []).map((c) => c.cycle_name))).filter(Boolean);
        setCycleNames(names);
      } catch { /* silent */ }
    })();
  }, [cid]);
  if (!cid) return <AppShell><div className="p-12 text-center text-[var(--muted)] text-sm">No context selected.</div></AppShell>;
  return (
    <AppShell>
      <div className="max-w-[1200px] mx-auto px-8 py-10">
        <div className="mb-8 akki-fade-up">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Send className="w-3 h-3 text-[var(--accent)]" /> Reporting cycle · §12 · {activeContext.name}
          </p>
          <h1 className="akki-greeting mb-2">Receive · Consolidate · Send up.</h1>
          <p className="akki-meta max-w-2xl">
            The reporting cycle, in five clean steps. Manage your team, the questions worth asking, the checklists AKKI sends on your behalf, the submissions that come back, and the report you send up the chain — all for <strong className="text-[var(--ink)]">{activeContext.name}</strong>.
          </p>
        </div>

        <Tabs defaultValue="tracker" className="w-full">
          <TabsList className="bg-transparent border-b border-[var(--rule)] w-full justify-start h-auto p-0 rounded-none mb-8 overflow-x-auto">
            {[
              ["tracker",    "Overview",          Eye],
              ["reportees",  "1 · Your team",     Users],
              ["bank",       "2 · Question bank", MessageCircleQuestion],
              ["checklists", "3 · Send checklists", Send],
              ["inbox",      "4 · Receive submissions", Inbox],
              ["reports",    "5 · Consolidate & send up", FileText],
            ].map(([v, l, I]) => (
              <TabsTrigger
                key={v} value={v}
                className="bg-transparent data-[state=active]:shadow-none data-[state=active]:bg-transparent rounded-none text-sm text-[var(--muted)] data-[state=active]:text-[var(--ink)] py-3 px-5 border-b-2 border-transparent data-[state=active]:border-[var(--accent)] data-[state=active]:font-medium"
                data-testid={`cycle-tab-${v}`}
              >
                <I className="w-4 h-4 mr-2" strokeWidth={1.7} /> {l}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="tracker"><CycleTracker contextId={cid} /></TabsContent>
          <TabsContent value="checklists"><Checklists contextId={cid} /></TabsContent>
          <TabsContent value="bank"><QuestionBank contextId={cid} /></TabsContent>
          <TabsContent value="reportees"><Reportees contextId={cid} /></TabsContent>
          <TabsContent value="inbox"><SubmissionsInbox contextId={cid} /></TabsContent>
          <TabsContent value="reports"><ReportsTab contextId={cid} currentEmail={account?.email} cycleNames={cycleNames} /></TabsContent>
        </Tabs>
      </div>
    </AppShell>
  );
}
