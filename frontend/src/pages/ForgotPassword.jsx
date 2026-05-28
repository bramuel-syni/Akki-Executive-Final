/**
 * Phase S (2026-05-27) — Forgot-password form.
 *
 * Public page at `/forgot-password`. Single field (email), single
 * submission. Always lands on the same "Check your inbox" message
 * regardless of whether the email exists (anti-enumeration). The
 * actual email send happens server-side in a BackgroundTask.
 */
import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail, ArrowLeft, Loader2, Send } from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy,  setBusy]  = useState(false);
  const [done,  setDone]  = useState(false);
  const [err,   setErr]   = useState(null);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (!email) return;
    setBusy(true); setErr(null);
    try {
      await api.post("/auth/forgot-password", { email });
      setDone(true);
    } catch (e2) {
      setErr(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--parchment)] flex items-center justify-center px-4" data-testid="forgot-password-page">
      <div className="w-full max-w-md bg-white border border-[var(--rule)] rounded-sm p-8">
        <header className="mb-6">
          <button
            type="button"
            onClick={() => navigate("/sign-in")}
            className="inline-flex items-center gap-1.5 text-[12px] text-[var(--muted)] hover:text-[var(--ink)] mb-4 transition-colors"
            data-testid="forgot-password-back"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to sign-in
          </button>
          <h1 className="akki-serif text-[26px] text-[var(--ink)] flex items-center gap-2" data-testid="forgot-password-h1">
            <Mail className="w-5 h-5 text-[var(--accent)]" strokeWidth={1.7} />
            Reset your password
          </h1>
          <p className="text-[13px] text-[var(--muted)] mt-2">
            Enter your email address. We'll send a link to set a new password.
          </p>
        </header>

        {done ? (
          <div className="py-6" data-testid="forgot-password-success">
            <p className="text-[14px] text-[var(--ink)] mb-3">
              Check your inbox.
            </p>
            <p className="text-[13px] text-[var(--muted)] leading-relaxed">
              If that email is on file, a reset link is on its way. The link
              is valid for 1 hour. If you don't see it within a few minutes,
              check your spam folder or{" "}
              <Link to="/forgot-password" className="text-[var(--accent)] underline">
                try again
              </Link>.
            </p>
            <Button
              type="button"
              onClick={() => navigate("/sign-in")}
              className="mt-6 w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]"
              data-testid="forgot-password-return-signin"
            >
              Return to sign-in
            </Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4" data-testid="forgot-password-form">
            <Input
              type="email"
              placeholder="email@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              data-testid="forgot-password-email"
            />
            {err && (
              <p className="text-[12px] text-[var(--oxblood)]" data-testid="forgot-password-error">
                {err}
              </p>
            )}
            <Button
              type="submit"
              disabled={busy || !email}
              className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]"
              data-testid="forgot-password-submit"
            >
              {busy
                ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                : <Send className="w-3.5 h-3.5 mr-1.5" />}
              Send reset link
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
