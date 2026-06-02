/**
 * C1-revised Phase A (2026-02) — First-login password-set page.
 *
 * Route: /auth/set-password (auth-gated).
 *
 * Renders only when the signed-in account carries
 * `has_set_password === false` (strict bool). The SetPasswordGuard
 * wrapping `<Gated>` routes the user here from any /app/* destination
 * until they set a password.
 *
 * The form posts to `POST /api/auth/set-password`, which flips
 * `accounts.has_set_password = true` and refreshes
 * `last_activity_at`. On success we re-fetch /auth/me so the
 * AuthContext picks up the new flag and the guard drops, then
 * navigate to the post-set destination (default `/app/`).
 *
 * Voice-lint clean. 1280/1024/820/414 layout pass.
 */
import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { HelpCircle } from "lucide-react";
import { toast } from "sonner";
import WebsiteShell from "@/website/WebsiteShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function SetPasswordRequired() {
  const navigate = useNavigate();
  const location = useLocation();
  const { account, bootstrap } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Bounce legacy users (has_set_password is null/missing/true) back to
  // /app/. The server-side gate is the source of truth — this is a
  // UX nicety so a directly-typed URL doesn't show the form to someone
  // who doesn't need it.
  useEffect(() => {
    if (account && account.has_set_password !== false) {
      navigate("/app/", { replace: true });
    }
  }, [account, navigate]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!password || password.length < 10) {
      setError("Use at least 10 characters.");
      return;
    }
    if (password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/set-password", { password });
      // Re-fetch /auth/me so AuthContext picks up the new
      // has_set_password=true and the guard drops on next render.
      if (typeof bootstrap === "function") {
        try { await bootstrap(); } catch (_) { /* non-fatal */ }
      }
      toast.success("Password set. Welcome in.");
      const target = (location.state && location.state.from) || "/app/";
      navigate(target, { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (detail && typeof detail === "object" && detail.message) || String(err?.message || err);
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const firstName = (account?.first_name || account?.name || "").split(" ")[0] || "there";

  return (
    <WebsiteShell title="Set a password — Akki for Executives" pathname="/auth/set-password">
      <section className="website-section section-reveal" data-testid="set-password-required">
        <p className="kicker">ONE LAST STEP</p>
        <h1
          className="akki-serif text-4xl sm:text-5xl text-[var(--ink)] mb-2 break-words inline-flex items-baseline gap-3"
          data-testid="set-password-heading"
          id="set-password-heading-text"
        >
          Set a password, {firstName}.
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger
                type="button"
                aria-label="Why am I being asked to set a password?"
                aria-describedby="set-password-heading-text"
                className="inline-flex items-center text-[var(--muted)] hover:text-[var(--deep)] transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--oxblood)] rounded-sm"
                data-testid="set-password-tooltip-trigger"
              >
                <HelpCircle className="w-4 h-4" strokeWidth={1.5} aria-hidden="true" />
              </TooltipTrigger>
              <TooltipContent
                side="right"
                className="max-w-xs text-[12.5px] leading-snug bg-[var(--ink)] text-white px-3 py-2"
                data-testid="set-password-tooltip-content"
                role="tooltip"
              >
                Akki uses your password as a fallback if your Google or Microsoft account becomes unreachable.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </h1>
        <p className="dek mb-8 break-words" style={{ maxWidth: "60ch" }}>
          You signed in once. To get back in next time without your
          email link, set a password now. You can keep using
          Google or Microsoft to sign in — the password is your fallback.
        </p>

        <form
          onSubmit={onSubmit}
          className="max-w-md flex flex-col gap-4"
          data-testid="set-password-form"
          noValidate
        >
          <div>
            <Label
              htmlFor="set-pw"
              className="text-xs uppercase tracking-wider text-slate-500 font-semibold"
            >
              New password
            </Label>
            <Input
              id="set-pw"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-9 text-sm rounded-sm"
              minLength={10}
              data-testid="set-password-input"
              required
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Minimum 10 characters.
            </p>
          </div>
          <div>
            <Label
              htmlFor="set-pw2"
              className="text-xs uppercase tracking-wider text-slate-500 font-semibold"
            >
              Confirm password
            </Label>
            <Input
              id="set-pw2"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="h-9 text-sm rounded-sm"
              minLength={10}
              data-testid="set-password-confirm"
              required
            />
          </div>
          {error && (
            <p
              className="text-[12px] text-[var(--oxblood)]"
              data-testid="set-password-error"
            >
              {error}
            </p>
          )}
          <Button
            type="submit"
            disabled={busy}
            className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 text-sm"
            data-testid="set-password-submit"
          >
            {busy ? "Setting…" : "Set password and continue"}
          </Button>
        </form>
      </section>
    </WebsiteShell>
  );
}
