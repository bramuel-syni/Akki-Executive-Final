/**
 * ContributorPortal — Phase F.5 (2026-05-26).
 *
 * Public magic-link landing page for Mode 2 contributors. No Akki
 * account required, no AppShell, no auth wall. The URL token IS the
 * credential.
 *
 * Mounted at /contribute/:token.
 *
 * Reads/writes via:
 *   GET    /api/tasks/contribute/{token}                — landing data
 *   POST   /api/tasks/contribute/{token}/upload         — file submission
 *   POST   /api/tasks/contribute/{token}/comment        — clarifications
 *   POST   /api/tasks/contribute/{token}/submit         — finalize
 */
import React, { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { toast, Toaster } from "sonner";
import { Loader2, Upload, Send, FileText, Check, MessageCircle } from "lucide-react";


function api(path, opts = {}) {
  const base = process.env.REACT_APP_BACKEND_URL || "";
  // eslint-disable-next-line no-restricted-syntax -- ContributorPortal is a PUBLIC page; the magic-link token IS the credential, no bearer/X-Active-Context wanted (would 401 here).
  return fetch(`${base}${path}`, opts);
}


export default function ContributorPortal() {
  const { token } = useParams();
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [comment, setComment] = useState("");
  const [postingComment, setPostingComment] = useState(false);
  const fileRef = useRef(null);

  const reload = async () => {
    setState((s) => ({ ...s, loading: true }));
    try {
      const r = await api(`/api/tasks/contribute/${encodeURIComponent(token)}`);
      if (r.status === 404 || r.status === 410) {
        setState({ loading: false, data: null, error: r.status === 410 ? "expired" : "invalid" });
        return;
      }
      const data = await r.json();
      setState({ loading: false, data, error: null });
    } catch (e) {
      setState({ loading: false, data: null, error: "network" });
    }
  };
  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [token]);

  const onPickFile = () => fileRef.current?.click();

  const onUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await api(`/api/tasks/contribute/${encodeURIComponent(token)}/upload`, {
        method: "POST", body: fd,
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || "Upload failed");
      }
      toast.success("Uploaded.");
      await reload();
    } catch (e) { toast.error(e.message || "Upload failed"); }
    finally { setUploading(false); e.target.value = ""; }
  };

  const onComment = async () => {
    if (!comment.trim() || postingComment) return;
    setPostingComment(true);
    try {
      const r = await api(`/api/tasks/contribute/${encodeURIComponent(token)}/comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: comment.trim() }),
      });
      if (!r.ok) throw new Error("Comment failed");
      toast.success("Comment added.");
      setComment("");
    } catch (e) { toast.error(e.message); }
    finally { setPostingComment(false); }
  };

  const onSubmit = async () => {
    setSubmitting(true);
    try {
      const r = await api(`/api/tasks/contribute/${encodeURIComponent(token)}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!r.ok) throw new Error("Submit failed");
      toast.success("Submitted. The task owner has been notified.");
      await reload();
    } catch (e) { toast.error(e.message); }
    finally { setSubmitting(false); }
  };

  if (state.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--parchment)]" data-testid="contributor-portal-loading">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--muted)]" />
      </div>
    );
  }

  if (state.error || !state.data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--parchment)] p-6" data-testid="contributor-portal-error">
        <div className="max-w-md text-center">
          <p className="akki-serif text-[22px] text-[var(--ink)] mb-2">Link not valid</p>
          <p className="text-[13px] text-[var(--muted)]">
            {state.error === "expired"
              ? "This invitation has expired. Ask the task owner to re-send."
              : "We couldn't find that invitation. The link may have been revoked or is malformed."}
          </p>
        </div>
      </div>
    );
  }

  const { data } = state;
  const submitted = data.your_status === "submitted" || data.your_status === "approved";

  return (
    <div className="min-h-screen bg-[var(--parchment)] py-10" data-testid="contributor-portal">
      <Toaster />
      <main className="max-w-2xl mx-auto px-6">
        <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-1">
          You've been asked to contribute
        </p>
        <h1 className="akki-serif text-[26px] text-[var(--ink)] mb-1" data-testid="contributor-portal-task-name">
          {data.task.name || "Untitled task"}
        </h1>
        {data.task.due_date && (
          <p className="text-[12px] text-[var(--muted)] mb-5" data-testid="contributor-portal-due">
            Final task due {data.task.due_date}
          </p>
        )}

        <section className="border border-[var(--rule)] bg-white rounded-sm p-5 mb-5">
          <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1">Objective</p>
          <p className="text-[13.5px] text-[var(--ink)] mb-3" data-testid="contributor-portal-objective">
            {data.task.objective || "—"}
          </p>
          {data.task.success_criteria && (
            <>
              <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1">Success criteria</p>
              <p className="text-[13px] text-[var(--ink)] mb-3" data-testid="contributor-portal-success-criteria">
                {data.task.success_criteria}
              </p>
            </>
          )}
          <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1">
            Your specific contribution
          </p>
          <p className="text-[13px] text-[var(--ink)]" data-testid="contributor-portal-contribution">
            {data.contribution || "(See task brief — open question.)"}
          </p>
          {data.your_due_date && (
            <p className="text-[11.5px] text-[var(--oxblood)] mt-2 font-mono">
              Your due date: {data.your_due_date}
            </p>
          )}
        </section>

        {data.peers?.length > 0 && (
          <section className="mb-5" data-testid="contributor-portal-peers">
            <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">
              Also contributing
            </p>
            <ul className="text-[12px] text-[var(--muted)] space-y-0.5">
              {data.peers.map((p, i) => (
                <li key={i}>
                  {p.name || "Unknown"}{p.role ? ` — ${p.role}` : ""}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Uploads */}
        <section className="border border-[var(--rule)] bg-white rounded-sm p-5 mb-5" data-testid="contributor-portal-uploads-section">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
              Your uploads
            </p>
            <button
              type="button"
              onClick={onPickFile}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[12.5px] text-white bg-[var(--oxblood)] hover:bg-[var(--oxblood-deep)] disabled:opacity-60"
              data-testid="contributor-portal-upload-button"
            >
              {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
              {uploading ? "Uploading…" : "Upload my work"}
            </button>
            <input ref={fileRef} type="file" className="hidden" onChange={onUpload}
                   accept={(data.task.output_formats || []).map((f) => "." + f).join(",") || undefined}
                   data-testid="contributor-portal-upload-input" />
          </div>
          {(data.docs || []).length === 0 ? (
            <p className="text-[12px] italic text-[var(--muted)]" data-testid="contributor-portal-uploads-empty">
              No files uploaded yet.
            </p>
          ) : (
            <ul className="space-y-1" data-testid="contributor-portal-uploads-list">
              {data.docs.map((d) => (
                <li key={d.id} className="text-[12.5px] text-[var(--ink)] inline-flex items-center gap-1.5"
                    data-testid={`contributor-portal-upload-${d.id}`}>
                  <FileText className="w-3 h-3 text-[var(--muted)]" />
                  <span className="truncate flex-1">{d.original_filename || d.name || d.id}</span>
                  <Check className="w-3 h-3 text-emerald-600" />
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Clarifications */}
        <section className="border border-[var(--rule)] bg-white rounded-sm p-5 mb-5" data-testid="contributor-portal-comment-section">
          <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">
            Clarifications for the task owner
          </p>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            placeholder="Anything the task owner should know about your submission?"
            className="w-full border border-[var(--rule)] rounded-sm px-3 py-2 text-[13px] focus:outline-none focus:border-[var(--ink)]"
            data-testid="contributor-portal-comment-input"
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button" onClick={onComment} disabled={postingComment || !comment.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[12.5px] border border-[var(--rule)] hover:border-[var(--ink)] disabled:opacity-60"
              data-testid="contributor-portal-comment-send"
            >
              {postingComment ? <Loader2 className="w-3 h-3 animate-spin" /> : <MessageCircle className="w-3 h-3" />}
              Send comment
            </button>
          </div>
        </section>

        {/* Submit */}
        <section className="text-center" data-testid="contributor-portal-submit-section">
          {submitted ? (
            <p className="inline-flex items-center gap-1.5 text-[14px] text-emerald-700 font-medium"
               data-testid="contributor-portal-submitted">
              <Check className="w-4 h-4" /> You've submitted — thank you.
            </p>
          ) : (
            <button
              type="button" onClick={onSubmit}
              disabled={submitting || (data.docs || []).length === 0}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-sm text-[14px] text-white bg-[var(--ink)] hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="contributor-portal-submit-button"
              title={(data.docs || []).length === 0 ? "Upload at least one file before submitting" : ""}
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Submit my contribution
            </button>
          )}
          {!submitted && (
            <p className="text-[11px] text-[var(--muted)] mt-2">
              Once submitted, the task owner is notified and your status flips to "submitted".
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
