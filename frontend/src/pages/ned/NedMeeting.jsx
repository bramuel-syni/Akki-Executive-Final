/**
 * NedMeeting — Phase E per-meeting Pre/In/Post page.
 *
 * Spec §5: three-act flow.
 *   Pre  — read pack, ask Akki Chat, take to Solva, review prior decisions,
 *          formulate questions for the meeting.
 *   In   — note-taking ONLY. Hard rule: ZERO LLM calls on this surface.
 *          The Q&A / Decisions / Open notes sections are pure DB writes.
 *   Post — review notes, register positions on decisions, draft follow-ups
 *          (which can be sent via the Phase D.2 Resend infrastructure).
 *
 * Privacy: every API call is account-scoped via the meeting's account_id.
 * Cross-board reads are not possible from this page by construction.
 */
import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  ChevronLeft, FileText, MessageSquare, Sparkles, ListChecks,
  CheckCircle2, MessageCircle, FileEdit, Send, Loader2, Plus,
  ArrowLeft, ShieldCheck, Pencil, Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { takeToSolva } from "@/lib/takeToSolva";

const ACTS = [
  { id: "pre",  label: "Pre",  subtitle: "Read · ask · prepare" },
  { id: "in",   label: "In",   subtitle: "Notes only · no AI" },
  { id: "post", label: "Post", subtitle: "Positions · follow-ups" },
];

function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// ─────────────────── Pre phase ────────────────────────
function PrePhase({ meeting, refresh }) {
  const navigate = useNavigate();
  const [questionDraft, setQuestionDraft] = useState(meeting.formulated_question || "");
  const [savingQ, setSavingQ] = useState(false);

  const saveQuestion = async () => {
    setSavingQ(true);
    try {
      await api.patch(`/ned/meetings/${meeting.id}`, { formulated_question: questionDraft });
      toast.success("Question saved.");
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setSavingQ(false); }
  };

  const askChatAboutPaper = (paper) => {
    // Deep-link into a chat tethered to the document.
    // Phase D.3 post-test fix (2026-05-26) — emit canonical
    // `?ctx_type=document&ctx_id=…` so the chat persists a
    // linked_context row + renders the "Reading: <title>" chip,
    // not the legacy attachment-style `?doc_id=…` path.
    navigate(`/app/chat?new=1&ctx_type=document&ctx_id=${encodeURIComponent(paper.id)}&context_id=${encodeURIComponent(meeting.context_id)}`);
  };
  const takeToSolvaPaper = (paper) => {
    // Phase F.2.A — unified journey. Lands on the framing surface
    // with the document seed pre-populated.
    takeToSolva({ navigate, kind: "document", id: paper.id });
  };

  return (
    <div className="space-y-5" data-testid="ned-meeting-pre">
      {/* Pack list */}
      <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3" data-testid="ned-meeting-papers">
        <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <FileText className="w-3 h-3" /> Pack ({meeting.papers?.length || 0})
        </p>
        {(meeting.papers?.length || 0) === 0 ? (
          <p className="text-[12.5px] text-[var(--muted)] italic">No papers attached. Edit the meeting to add some from the document journal.</p>
        ) : (
          <ul className="divide-y divide-[var(--rule)]">
            {meeting.papers.map((p) => (
              <li key={p.id} className="py-2.5">
                <div className="flex items-baseline justify-between gap-3 mb-1.5 flex-wrap">
                  <p className="akki-serif text-[13.5px] text-[var(--ink)]">{p.name || p.filename}</p>
                  {p.sensitivity_band && (
                    <span className="text-[11px] font-mono text-[var(--muted)]">{p.sensitivity_band}</span>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button type="button" size="sm" variant="outline"
                    onClick={() => askChatAboutPaper(p)}
                    className="text-[11.5px] rounded-sm"
                    data-testid={`ned-paper-ask-chat-${p.id}`}>
                    <MessageSquare className="w-3 h-3 mr-1" /> Ask Akki Chat
                  </Button>
                  <Button type="button" size="sm" variant="outline"
                    onClick={() => takeToSolvaPaper(p)}
                    className="text-[11.5px] rounded-sm"
                    data-testid={`ned-paper-take-solva-${p.id}`}>
                    <Sparkles className="w-3 h-3 mr-1" /> Take to Solva
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Through-line */}
      <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3">
        <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <ListChecks className="w-3 h-3" /> Prior decisions on this committee
        </p>
        <Button type="button" size="sm" variant="outline"
          onClick={() => navigate(`/app/ned/committee/${meeting.context_id}/${encodeURIComponent(meeting.committee)}`)}
          className="text-[12px] rounded-sm"
          data-testid="ned-pre-through-line">
          Open committee through-line <ArrowLeft className="w-3 h-3 ml-1 rotate-180" />
        </Button>
      </section>

      {/* Formulate question */}
      <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3" data-testid="ned-formulate-question">
        <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <Pencil className="w-3 h-3" /> Formulate your question for the chair
        </p>
        <Textarea value={questionDraft}
          onChange={(e) => setQuestionDraft(e.target.value)}
          placeholder="What is the question you want answered in this meeting? Keep it sharp and decisional."
          className="rounded-sm min-h-[90px]"
          data-testid="ned-formulate-question-textarea" />
        <div className="mt-2 flex justify-end">
          <Button type="button" onClick={saveQuestion} disabled={savingQ}
            className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px]"
            data-testid="ned-formulate-question-save">
            {savingQ && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
            Save
          </Button>
        </div>
      </section>
    </div>
  );
}

// ─────────────────── In phase (LLM-FREE) ────────────────────────
function InPhase({ meeting, refresh }) {
  // PRIVACY-CONTRACT: ned-in-phase-llm-free=true
  // ⚠️ HARD RULE PER NED SPEC §5.2.1 — DO NOT add LLM calls in this
  // component. No chat handoff, no summarisation, no transcription.
  // The In phase is a notes-only ceiling.
  const [draftKind, setDraftKind] = useState("qna");
  const [draftBody, setDraftBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const addNote = async (e) => {
    e.preventDefault();
    if (!draftBody.trim()) return;
    setBusy(true);
    try {
      await api.post(`/ned/meetings/${meeting.id}/notes`, {
        kind: draftKind, body: draftBody.trim(),
      });
      setDraftBody("");
      await refresh();
    } catch (err) { toast.error(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const removeNote = async (nid) => {
    try {
      await api.delete(`/ned/meetings/${meeting.id}/notes/${nid}`);
      setConfirmDelete(null);
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const sections = useMemo(() => {
    const s = { qna: [], decision: [], open: [] };
    for (const n of (meeting.notes || [])) (s[n.kind] || []).push(n);
    return s;
  }, [meeting.notes]);

  const SectionList = ({ title, kind, items, icon: Icon, emptyText }) => (
    <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3" data-testid={`ned-in-section-${kind}`}>
      <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
        <Icon className="w-3 h-3" /> {title} ({items.length})
      </p>
      {items.length === 0 ? (
        <p className="text-[12.5px] text-[var(--muted)] italic">{emptyText}</p>
      ) : (
        <ul className="divide-y divide-[var(--rule)]">
          {items.map((n) => (
            <li key={n.id} className="py-2 flex items-start gap-2 group" data-testid={`ned-in-note-${n.id}`}>
              <p className="text-[13px] text-[var(--ink)] leading-[1.55] flex-1 whitespace-pre-wrap">{n.body}</p>
              <button type="button" onClick={() => setConfirmDelete(n)}
                className="opacity-0 group-hover:opacity-100 text-[var(--muted)] hover:text-[color:var(--oxblood)]"
                aria-label="Remove note" data-testid={`ned-in-note-remove-${n.id}`}>
                <Trash2 className="w-3 h-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );

  return (
    <div className="space-y-5" data-testid="ned-meeting-in">
      {/* Privacy banner — explicit no-AI signpost */}
      <div className="border border-amber-200 bg-amber-50 rounded-md px-4 py-2 inline-flex items-center gap-2 text-[11.5px] text-amber-900"
           data-testid="ned-in-no-ai-banner">
        <ShieldCheck className="w-3.5 h-3.5" />
        Notes only. No AI in the meeting. By design.
      </div>

      <SectionList title="Q & A" kind="qna" icon={MessageCircle}
        items={sections.qna} emptyText="No Q&A captured yet." />
      <SectionList title="Decisions" kind="decision" icon={CheckCircle2}
        items={sections.decision} emptyText="No decisions captured yet." />
      <SectionList title="Open notes" kind="open" icon={FileEdit}
        items={sections.open} emptyText="No open notes yet." />

      {/* Quick-add form */}
      <form onSubmit={addNote} className="border border-[var(--rule)] bg-[var(--cream-deep)]/30 rounded-md px-4 py-3 space-y-2"
            data-testid="ned-in-add-note">
        <div className="flex gap-2 flex-wrap">
          {[
            { id: "qna",      label: "Q & A" },
            { id: "decision", label: "Decision" },
            { id: "open",     label: "Open note" },
          ].map((k) => (
            <button key={k.id} type="button" onClick={() => setDraftKind(k.id)}
              className={`text-[11.5px] px-3 py-1 rounded-full border ${
                draftKind === k.id
                  ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                  : "bg-white text-[var(--ink)] border-[var(--rule)] hover:border-[var(--accent)]"
              }`} data-testid={`ned-in-add-kind-${k.id}`}>
              {k.label}
            </button>
          ))}
        </div>
        <Textarea value={draftBody} onChange={(e) => setDraftBody(e.target.value)}
          placeholder="Capture the moment. No formatting needed."
          className="rounded-sm min-h-[68px]"
          data-testid="ned-in-add-textarea" />
        <div className="flex justify-end">
          <Button type="submit" disabled={busy || !draftBody.trim()}
            className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px]"
            data-testid="ned-in-add-submit">
            {busy ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Plus className="w-3 h-3 mr-1" />}
            Add
          </Button>
        </div>
      </form>

      <AlertDialog open={!!confirmDelete} onOpenChange={(v) => !v && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this note?</AlertDialogTitle>
            <AlertDialogDescription>It can't be recovered. Notes from the meeting are part of the record — only delete if it's wrong, not if you've changed your mind.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); removeNote(confirmDelete.id); }}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ─────────────────── Post phase ────────────────────────
function PostPhase({ meeting, refresh }) {
  const decisions = (meeting.notes || []).filter((n) => n.kind === "decision");

  // Position registration
  const [posDraft, setPosDraft] = useState({ decision_text: "", position: "for", private_note: "" });
  const [posBusy, setPosBusy] = useState(false);
  const submitPosition = async (e) => {
    e.preventDefault();
    if (!posDraft.decision_text.trim()) { toast.error("Decision text is required."); return; }
    setPosBusy(true);
    try {
      await api.post(`/ned/meetings/${meeting.id}/positions`, posDraft);
      toast.success("Position registered.");
      setPosDraft({ decision_text: "", position: "for", private_note: "" });
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setPosBusy(false); }
  };

  // Follow-up draft
  const [fuDraft, setFuDraft] = useState({ to_email: "", to_name: "", subject: "", body_md: "" });
  const [fuBusy, setFuBusy] = useState(false);
  const submitFollowup = async (e) => {
    e.preventDefault();
    if (!fuDraft.to_email.trim() || !fuDraft.subject.trim() || !fuDraft.body_md.trim()) {
      toast.error("Email, subject, and body are required."); return;
    }
    setFuBusy(true);
    try {
      await api.post(`/ned/meetings/${meeting.id}/followups`, fuDraft);
      toast.success("Follow-up drafted.");
      setFuDraft({ to_email: "", to_name: "", subject: "", body_md: "" });
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); } finally { setFuBusy(false); }
  };
  const sendFollowup = async (fid) => {
    try {
      await api.post(`/ned/meetings/${meeting.id}/followups/${fid}/send`);
      toast.success("Follow-up sent.");
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <div className="space-y-5" data-testid="ned-meeting-post">
      {/* Register positions */}
      <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3" data-testid="ned-post-positions">
        <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <CheckCircle2 className="w-3 h-3" /> Register your positions
        </p>
        {(meeting.positions || []).length > 0 && (
          <ul className="divide-y divide-[var(--rule)] mb-3" data-testid="ned-post-positions-list">
            {meeting.positions.map((p) => (
              <li key={p.id} className="py-2.5" data-testid={`ned-position-${p.id}`}>
                <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
                  <p className="text-[13px] text-[var(--ink)]">{p.decision_text}</p>
                  <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full ${
                    p.position === "for" ? "bg-emerald-100 text-emerald-900" :
                    p.position === "against" ? "bg-rose-100 text-rose-900" :
                    "bg-amber-100 text-amber-900"
                  }`}>{p.position}</span>
                </div>
                {p.private_note && (
                  <p className="text-[11.5px] text-[var(--muted)] italic">private: {p.private_note}</p>
                )}
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={submitPosition} className="space-y-2 border-t border-[var(--rule)] pt-3">
          {decisions.length > 0 && (
            <div className="text-[11.5px] text-[var(--muted)] mb-1">
              Decisions captured in this meeting (click to copy):
              <ul className="mt-1 space-y-1">
                {decisions.map((d) => (
                  <li key={d.id}>
                    <button type="button" onClick={() => setPosDraft({ ...posDraft, decision_text: d.body })}
                      className="text-left text-[12px] text-[var(--ink)] hover:text-[var(--accent)] underline-offset-2 hover:underline">
                      · {d.body.slice(0, 100)}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Input value={posDraft.decision_text}
            onChange={(e) => setPosDraft({ ...posDraft, decision_text: e.target.value })}
            placeholder="The decision you're registering a position on…"
            className="rounded-sm" data-testid="ned-post-position-decision" />
          <div className="flex gap-3 items-center">
            <Label className="text-[12px]">Your position</Label>
            <select value={posDraft.position}
              onChange={(e) => setPosDraft({ ...posDraft, position: e.target.value })}
              className="border border-[var(--rule)] rounded-sm px-2 py-1 text-[12.5px] bg-white"
              data-testid="ned-post-position-vote">
              <option value="for">For</option>
              <option value="against">Against</option>
              <option value="abstained">Abstained</option>
            </select>
          </div>
          <Textarea value={posDraft.private_note}
            onChange={(e) => setPosDraft({ ...posDraft, private_note: e.target.value })}
            placeholder="Private note · only you see this. Why this position?"
            className="rounded-sm min-h-[60px]"
            data-testid="ned-post-position-private-note" />
          <div className="flex justify-end">
            <Button type="submit" disabled={posBusy}
              className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px]"
              data-testid="ned-post-position-submit">
              {posBusy && <Loader2 className="w-3 h-3 mr-1 animate-spin" />} Register position
            </Button>
          </div>
        </form>
      </section>

      {/* Follow-ups */}
      <section className="border border-[var(--rule)] bg-white rounded-md px-4 py-3" data-testid="ned-post-followups">
        <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <Send className="w-3 h-3" /> Draft a follow-up
        </p>
        {(meeting.followups || []).length > 0 && (
          <ul className="divide-y divide-[var(--rule)] mb-3" data-testid="ned-post-followups-list">
            {meeting.followups.map((f) => (
              <li key={f.id} className="py-2.5" data-testid={`ned-followup-${f.id}`}>
                <div className="flex items-baseline justify-between gap-3 flex-wrap">
                  <p className="text-[13px] text-[var(--ink)]">{f.subject} <span className="text-[11px] text-[var(--muted)] font-mono">→ {f.to_email}</span></p>
                  <span className="text-[11px] font-mono text-[var(--muted)]">{f.status}{f.send_mode ? ` · ${f.send_mode}` : ""}</span>
                </div>
                {f.status === "draft" && (
                  <Button type="button" size="sm" variant="outline" className="mt-1.5 text-[11.5px] rounded-sm"
                    onClick={() => sendFollowup(f.id)}
                    data-testid={`ned-followup-send-${f.id}`}>
                    <Send className="w-3 h-3 mr-1" /> Send via Akki
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={submitFollowup} className="space-y-2 border-t border-[var(--rule)] pt-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Input value={fuDraft.to_email}
              onChange={(e) => setFuDraft({ ...fuDraft, to_email: e.target.value })}
              placeholder="Recipient email" className="rounded-sm"
              data-testid="ned-post-followup-to-email" />
            <Input value={fuDraft.to_name}
              onChange={(e) => setFuDraft({ ...fuDraft, to_name: e.target.value })}
              placeholder="Name (optional)" className="rounded-sm"
              data-testid="ned-post-followup-to-name" />
          </div>
          <Input value={fuDraft.subject}
            onChange={(e) => setFuDraft({ ...fuDraft, subject: e.target.value })}
            placeholder="Subject" className="rounded-sm"
            data-testid="ned-post-followup-subject" />
          <Textarea value={fuDraft.body_md}
            onChange={(e) => setFuDraft({ ...fuDraft, body_md: e.target.value })}
            placeholder="Body. Plain text or markdown."
            className="rounded-sm min-h-[120px]"
            data-testid="ned-post-followup-body" />
          <div className="flex justify-end">
            <Button type="submit" disabled={fuBusy}
              className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px]"
              data-testid="ned-post-followup-submit">
              {fuBusy && <Loader2 className="w-3 h-3 mr-1 animate-spin" />} Save draft
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

// ─────────────────── Page shell ────────────────────────
export default function NedMeeting() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [meeting, setMeeting] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [act, setAct] = useState("pre");

  const refresh = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/ned/meetings/${id}`);
      setMeeting(data);
      // Auto-advance display: if state is in/post/closed, jump there.
      if (data?.state && data.state !== "pre") setAct(data.state === "closed" ? "post" : data.state);
    } catch (e) { setErr(apiErrorMessage(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, [id]);

  const advanceState = async (next) => {
    try {
      await api.patch(`/ned/meetings/${id}`, { state: next });
      await refresh();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="max-w-4xl mx-auto px-6 py-12 text-center text-[var(--muted)]">
          <Loader2 className="w-4 h-4 animate-spin mx-auto" />
        </div>
      </AppShell>
    );
  }
  if (err || !meeting) {
    return (
      <AppShell>
        <div className="max-w-4xl mx-auto px-6 py-12">
          <p className="text-[13px] text-amber-900">{err || "Meeting not found."}</p>
          <Button variant="outline" onClick={() => navigate("/app")} className="mt-4">Back to home</Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-6" data-testid="ned-meeting-page">
        <button type="button" onClick={() => navigate("/app")}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1 mb-3"
          data-testid="ned-meeting-back">
          <ChevronLeft className="w-3 h-3" /> Back to home
        </button>
        <div className="flex items-baseline justify-between gap-3 flex-wrap mb-3">
          <div>
            <p className="akki-overline text-[var(--muted)] mb-1">{meeting.committee} · {fmtDateTime(meeting.scheduled_at)}</p>
            <h1 className="akki-serif text-[22px] text-[var(--ink)]">{meeting.title}</h1>
          </div>
        </div>

        {/* Three-act bar */}
        <nav className="flex items-center gap-2 mb-5" data-testid="ned-act-bar" aria-label="Meeting acts">
          {ACTS.map((a) => {
            const active = act === a.id;
            return (
              <button key={a.id} type="button" onClick={() => setAct(a.id)}
                className={`px-3.5 py-1.5 rounded-full border text-[12.5px] inline-flex items-center gap-2 transition-colors ${
                  active
                    ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                    : "border-[var(--rule)] bg-white text-[var(--ink)] hover:border-[var(--accent)]"
                }`}
                data-testid={`ned-act-pill-${a.id}${active ? "-active" : ""}`}
                aria-current={active ? "step" : undefined}>
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] opacity-80">
                  {a.id === "pre" ? "01" : a.id === "in" ? "02" : "03"}
                </span>
                <span className="font-medium">{a.label}</span>
                <span className="hidden md:inline text-[11px] opacity-90">· {a.subtitle}</span>
              </button>
            );
          })}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] font-mono text-[var(--muted)]">state: {meeting.state}</span>
            {meeting.state !== act && (
              <Button size="sm" variant="outline" className="text-[11px] rounded-sm h-7"
                onClick={() => advanceState(act)}
                data-testid="ned-meeting-advance-state">
                Set state to {act}
              </Button>
            )}
          </div>
        </nav>

        {act === "pre"  && <PrePhase  meeting={meeting} refresh={refresh} />}
        {act === "in"   && <InPhase   meeting={meeting} refresh={refresh} />}
        {act === "post" && <PostPhase meeting={meeting} refresh={refresh} />}
      </div>
    </AppShell>
  );
}
