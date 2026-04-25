import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ShieldCheck, Loader2, CheckCircle2, MessageCircleQuestion } from "lucide-react";

/**
 * RespondToChecklist — public page reached via the link AKKI emails to a
 * reportee. No auth. Token-scoped fetch. Submitting persists answers and
 * marks the reportee's open questions as 'answered' on the executive's
 * Question Bank.
 */
export default function RespondToChecklist() {
  const { token } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cl, setCl] = useState(null);
  const [answers, setAnswers] = useState({});
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/respond/${token}`);
        setCl(data);
        setDone(!!data.submitted);
      } catch (e) {
        setError(apiErrorMessage(e) || "This link is invalid or has expired.");
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const onSubmit = async () => {
    if (!cl) return;
    const payload = {
      answers: cl.questions.map((q) => ({
        question_id: q.question_id,
        question_text: q.text,
        answer: (answers[q.question_id] || "").trim(),
      })),
      notes: notes.trim() || null,
    };
    if (payload.answers.every((a) => !a.answer)) {
      toast.message("Please answer at least one question."); return;
    }
    setSubmitting(true);
    try {
      await api.post(`/respond/${token}`, payload);
      setDone(true);
      toast.success("Thanks — your response has been routed.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setSubmitting(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--cream)] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)]" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="min-h-screen bg-[var(--cream)] flex items-center justify-center p-8">
        <div className="bg-white border border-[var(--rule)] rounded-lg p-10 text-center max-w-md">
          <p className="akki-overline mb-3 text-[var(--accent)]">Link unavailable</p>
          <p className="akki-serif text-[18px] text-[var(--ink)] mb-2">{error}</p>
          <p className="text-[13px] text-[var(--muted)]">If this is unexpected, reply to the email AKKI sent you.</p>
        </div>
      </div>
    );
  }
  if (done) {
    return (
      <div className="min-h-screen bg-[var(--cream)] flex items-center justify-center p-8">
        <div className="bg-white border border-emerald-200 rounded-lg p-10 text-center max-w-md" data-testid="respond-thanks">
          <CheckCircle2 className="w-12 h-12 text-emerald-700 mx-auto mb-4" strokeWidth={1.5} />
          <p className="akki-serif text-[22px] text-[var(--ink)] mb-2">Thanks — that's been routed.</p>
          <p className="text-[13.5px] text-[var(--muted)]">Your responses are now in the executive's inbox. You can close this tab.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--cream)] py-10 px-4">
      <div className="max-w-2xl mx-auto" data-testid="respond-form">
        <div className="mb-8">
          <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-2">
            <MessageCircleQuestion className="w-3 h-3" /> Reporting checklist · {cl.cycle_name}
          </p>
          <h1 className="akki-greeting mb-3">Hi {cl.reportee_name}.</h1>
          <p className="akki-meta">Please respond by <strong className="text-[var(--ink)]">{cl.deadline_date}</strong>.</p>
          {cl.note_to_reportee && (
            <div className="mt-4 bg-white border-l-4 border-[var(--accent)] pl-4 py-3 pr-3 italic text-[14px] text-[var(--deep)]">
              "{cl.note_to_reportee}"
            </div>
          )}
        </div>

        <div className="space-y-5">
          {cl.questions.map((q, i) => (
            <div key={q.question_id || i} className="bg-white border border-[var(--rule)] rounded-lg p-5" data-testid={`respond-q-${i}`}>
              <p className="text-[10.5px] uppercase tracking-wider text-[var(--accent)] mb-1.5">Q{i + 1} · {q.category}</p>
              <p className="akki-serif text-[16px] text-[var(--ink)] mb-3 leading-snug">{q.text}</p>
              <textarea
                value={answers[q.question_id] || ""}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [q.question_id]: e.target.value }))}
                placeholder="Your response…"
                rows={4}
                className="w-full text-[14px] bg-[var(--cream)] border border-[var(--rule)] rounded-md p-3 focus:outline-none focus:border-[var(--accent)]"
                data-testid={`respond-answer-${i}`}
              />
            </div>
          ))}

          <div className="bg-white border border-[var(--rule)] rounded-lg p-5">
            <p className="akki-overline mb-2">Anything else worth flagging?</p>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional — items the questions didn't cover, context, asks…"
              rows={3}
              className="w-full text-[14px] bg-[var(--cream)] border border-[var(--rule)] rounded-md p-3 focus:outline-none focus:border-[var(--accent)]"
              data-testid="respond-notes"
            />
          </div>

          <div className="flex items-center justify-between gap-3 pt-2">
            <p className="text-[11.5px] text-[var(--muted)] flex items-center gap-1.5">
              <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" /> Synisense-shielded · routed only to your executive
            </p>
            <Button
              onClick={onSubmit}
              disabled={submitting}
              className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white px-6 h-11"
              data-testid="respond-submit-btn"
            >
              {submitting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Submitting…</> : "Submit response"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
