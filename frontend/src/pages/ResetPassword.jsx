/**
 * Phase S (2026-05-27) — Reset-password page.
 *
 * Public page at `/reset-password/:token`. On mount:
 *   1. Calls GET /api/auth/reset-password/{token} to validate.
 *   2. If valid, shows the new-password form with masked email.
 *   3. If 410 (expired): shows expired state + "Request a new link".
 *   4. If 401 (invalid/tampered/already-used): same expired-style screen.
 *
 * On submit (POST): clears the token + sets the password + revokes
 * prior sessions. Redirects to `/sign-in` on success.
 */
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Lock, ArrowLeft, Loader2, Check, AlertCircle } from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ResetPassword() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [stage, setStage]     = useState("validating");  // validating | form | success | invalid | expired
  const [email, setEmail]     = useState("");
  const [pw1,    setPw1]      = useState("");
  const [pw2,    setPw2]      = useState("");
  const [busy,   setBusy]     = useState(false);
  const [err,    setErr]      = useState(null);

  // Validate token on mount.
  useEffect(() => {
    if (!token) { setStage("invalid"); return; }
    let dead = false;
    (async () => {
      try {
        const { data } = await api.get(`/auth/reset-password/${token}`);
        if (dead) return;
        if (data?.valid) {
          setEmail(data.email_masked || "");
          setStage("form");
        } else {
          setStage("invalid");
        }
      } catch (e) {
        if (dead) return;
        const code = e?.response?.status;
        if (code === 410)      setStage("expired");
        else                   setStage("invalid");
      }
    })();
    return () => { dead = true; };
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    if (pw1.length < 10) {
      setErr("Password must be at least 10 characters.");
      return;
    }
    if (pw1 !== pw2) {
      setErr("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.post(`/auth/reset-password/${token}`, { new_password: pw1 });
      setStage("success");
    } catch (e2) {
      const code = e2?.response?.status;
      if (code === 410)      setStage("expired");
      else if (code === 401) setStage("invalid");
      else                   setErr(apiErrorMessage(e2));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--parchment)] flex items-center justify-center px-4" data-testid="reset-password-page">
      <div className="w-full max-w-md bg-white border border-[var(--rule)] rounded-sm p-8">
        <header className="mb-6">
          <button
            type="button"
            onClick={() => navigate("/sign-in")}
            className="inline-flex items-center gap-1.5 text-[12px] text-[var(--muted)] hover:text-[var(--ink)] mb-4 transition-colors"
            data-testid="reset-password-back"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to sign-in
          </button>
          <h1 className="akki-serif text-[26px] text-[var(--ink)] flex items-center gap-2" data-testid="reset-password-h1">
            <Lock className="w-5 h-5 text-[var(--accent)]" strokeWidth={1.7} />
            Set a new password
          </h1>
        </header>

        {stage === "validating" && (
          <p className="text-[13px] text-[var(--muted)] py-6" data-testid="reset-password-validating">
            Validating link…
          </p>
        )}

        {stage === "expired" && (
          <div className="py-6" data-testid="reset-password-expired">
            <p className="text-[14px] text-[var(--ink)] mb-3 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-[var(--oxblood)]" /> Link expired
            </p>
            <p className="text-[13px] text-[var(--muted)] mb-6 leading-relaxed">
              This reset link has expired or already been used. Request a new one
              and we'll send you a fresh link.
            </p>
            <Link to="/forgot-password" data-testid="reset-password-request-new">
              <Button className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]">
                Request a new link
              </Button>
            </Link>
          </div>
        )}

        {stage === "invalid" && (
          <div className="py-6" data-testid="reset-password-invalid">
            <p className="text-[14px] text-[var(--ink)] mb-3 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-[var(--oxblood)]" /> Invalid link
            </p>
            <p className="text-[13px] text-[var(--muted)] mb-6 leading-relaxed">
              This reset link is not valid. It may have been tampered with or
              already used. Request a fresh link below.
            </p>
            <Link to="/forgot-password" data-testid="reset-password-request-new">
              <Button className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]">
                Request a new link
              </Button>
            </Link>
          </div>
        )}

        {stage === "form" && (
          <form onSubmit={submit} className="space-y-4" data-testid="reset-password-form">
            {email && (
              <p className="text-[13px] text-[var(--muted)]" data-testid="reset-password-email-masked">
                Setting password for <span className="font-mono text-[var(--ink)]">{email}</span>
              </p>
            )}
            <div>
              <label className="block text-[12px] text-[var(--ink)] mb-1.5">New password (min 10 characters)</label>
              <Input
                type="password" value={pw1}
                onChange={(e) => setPw1(e.target.value)}
                required minLength={10}
                autoFocus
                data-testid="reset-password-new"
              />
            </div>
            <div>
              <label className="block text-[12px] text-[var(--ink)] mb-1.5">Confirm new password</label>
              <Input
                type="password" value={pw2}
                onChange={(e) => setPw2(e.target.value)}
                required
                data-testid="reset-password-confirm"
              />
            </div>
            {err && (
              <p className="text-[12px] text-[var(--oxblood)]" data-testid="reset-password-error">
                {err}
              </p>
            )}
            <Button
              type="submit" disabled={busy || pw1.length < 10 || pw1 !== pw2}
              className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]"
              data-testid="reset-password-submit"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
              Update password
            </Button>
          </form>
        )}

        {stage === "success" && (
          <div className="py-6" data-testid="reset-password-success">
            <p className="text-[14px] text-[var(--ink)] mb-3 flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-700" /> Password updated
            </p>
            <p className="text-[13px] text-[var(--muted)] mb-6 leading-relaxed">
              Your password has been updated and all existing sessions have
              been signed out for security. Sign in with the new password.
            </p>
            <Button
              type="button"
              onClick={() => navigate("/sign-in")}
              className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)]"
              data-testid="reset-password-go-signin"
            >
              Go to sign-in
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
