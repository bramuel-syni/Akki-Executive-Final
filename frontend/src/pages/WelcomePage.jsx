/**
 * Phase P4.D (2026-02) — Cohort magic-link landing page.
 *
 * Route: /welcome/:token (public, no auth).
 *
 * States:
 *   - loading      : fetching /api/auth/magic-link/preview/{token}
 *   - valid        : show 3 CTAs (set password / Google / Microsoft)
 *   - expired      : 410 from preview with code=expired
 *   - consumed     : 410 from preview with code=consumed
 *   - not_found    : 404 from preview
 *   - consumed_ok  : after consume succeeds, briefly shown before redirect
 *
 * Voice-clean copy. 1280/1024/820/414 layout pass. No flex-wrap breaks.
 */
import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import WebsiteShell from "@/website/WebsiteShell";
import { Loader2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

export default function WelcomePage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState("loading");
  const [data, setData] = useState(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API}/api/auth/magic-link/preview/${token}`,
          { withCredentials: true },
        );
        if (cancelled) return;
        setData(r.data);
        setState("valid");
      } catch (err) {
        if (cancelled) return;
        const code = err?.response?.data?.detail?.code;
        if (err?.response?.status === 410 && code === "expired") setState("expired");
        else if (err?.response?.status === 410 && code === "consumed") setState("consumed");
        else setState("not_found");
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  // Pull CSRF cookie for the consume POST.
  async function ensureCsrf() {
    const m = (document.cookie || "").match(/csrf_token=([^;]+)/);
    if (m) return decodeURIComponent(m[1]);
    const r = await axios.get(`${API}/api/csrf`, { withCredentials: true });
    return r?.data?.csrf_token || "";
  }

  async function submitPassword(e) {
    e.preventDefault();
    if (!password || password.length < 10) {
      toast.error("Password must be at least 10 characters.");
      return;
    }
    if (password !== confirm) {
      toast.error("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const csrf = await ensureCsrf();
      const r = await axios.post(
        `${API}/api/auth/magic-link/consume`,
        { token, mode: "password", password },
        { withCredentials: true, headers: { "X-CSRF-Token": csrf } },
      );
      setState("consumed_ok");
      // Phase P5.2 (2026-02) — full-page nav (not react-router navigate)
      // so the AuthContext re-initialises with the newly-set cookies.
      // `navigate(...)` keeps the SPA mounted; the existing
      // AuthContext snapshot still has `account === false` from when
      // the user landed on /welcome unauthenticated, and the
      // <Gated> wrapper on /app/work-studio would bounce to /signin.
      // window.location.href forces a fresh boot.
      const target = r?.data?.redirect || "/app/work-studio";
      window.location.href = target;
    } catch (err) {
      const code = err?.response?.data?.detail?.code;
      const msg = err?.response?.data?.detail?.message || String(err?.message || err);
      if (code === "invalid_or_consumed") setState("consumed");
      else toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  function withMagicLinkOAuth(provider) {
    const base = `${API}/api/auth/oauth/${provider}/start?magic_link_token=${encodeURIComponent(token)}`;
    window.location.href = base;
  }

  // ─── States ─────────────────────────────────────────────────────
  if (state === "loading") {
    return (
      <WebsiteShell title="Welcome — Akki" pathname={`/welcome/${token}`}>
        <section className="website-section section-reveal" data-testid="welcome-loading">
          <div className="flex items-center gap-2 text-[var(--muted)] text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        </section>
      </WebsiteShell>
    );
  }

  if (state === "valid") {
    return (
      <WebsiteShell title="Welcome — Akki" pathname={`/welcome/${token}`}>
        <section className="website-section section-reveal" data-testid="welcome-valid">
          <p className="kicker">EARLY ACCESS</p>
          <h1
            className="akki-serif text-4xl sm:text-5xl text-[var(--ink)] mb-2 break-words"
            data-testid="welcome-heading"
          >
            Welcome, {data?.first_name || "friend"}.
          </h1>
          <p className="dek mb-8 break-words" style={{ maxWidth: "60ch" }}>
            Pick how you'd like to sign in. The link is good once and
            stops working when you do.
          </p>

          <div className="max-w-md flex flex-col gap-3">
            {!showPasswordForm && (
              <Button
                onClick={() => setShowPasswordForm(true)}
                className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 text-sm"
                data-testid="welcome-set-password-btn"
              >
                Set a password
              </Button>
            )}
            {showPasswordForm && (
              <form onSubmit={submitPassword} className="flex flex-col gap-3 mb-2" data-testid="welcome-password-form">
                <div>
                  <Label htmlFor="pw" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                    New password
                  </Label>
                  <Input
                    id="pw" type="password" autoComplete="new-password"
                    value={password} onChange={(e) => setPassword(e.target.value)}
                    className="h-9 text-sm rounded-sm" minLength={10}
                    data-testid="welcome-password-input" required
                  />
                  <p className="text-[11px] text-slate-500 mt-1">Minimum 10 characters.</p>
                </div>
                <div>
                  <Label htmlFor="pw2" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                    Confirm password
                  </Label>
                  <Input
                    id="pw2" type="password" autoComplete="new-password"
                    value={confirm} onChange={(e) => setConfirm(e.target.value)}
                    className="h-9 text-sm rounded-sm" minLength={10}
                    data-testid="welcome-password-confirm" required
                  />
                </div>
                <Button
                  type="submit" disabled={busy}
                  className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 text-sm"
                  data-testid="welcome-password-submit"
                >
                  {busy ? "Setting up…" : "Open my workspace"}
                </Button>
              </form>
            )}
            <Button
              variant="outline"
              onClick={() => withMagicLinkOAuth("google")}
              className="rounded-sm h-10 text-sm"
              data-testid="welcome-google-btn"
            >
              Continue with Google
            </Button>
            <Button
              variant="outline"
              onClick={() => withMagicLinkOAuth("microsoft")}
              className="rounded-sm h-10 text-sm"
              data-testid="welcome-microsoft-btn"
            >
              Continue with Microsoft
            </Button>
          </div>

          <p className="text-[12px] text-[var(--muted)] mt-8 font-mono">
            Link expires {data?.expires_at ? new Date(data.expires_at).toLocaleDateString() : "in 14 days"}.
          </p>
        </section>
      </WebsiteShell>
    );
  }

  if (state === "expired") {
    return (
      <WebsiteShell title="Link expired — Akki" pathname={`/welcome/${token}`}>
        <section className="website-section section-reveal" data-testid="welcome-expired">
          <h1 className="akki-serif text-4xl text-[var(--ink)] mb-2" data-testid="welcome-expired-h1">
            This link expired.
          </h1>
          <p className="dek mb-6 break-words" style={{ maxWidth: "60ch" }}>
            Magic links work for 14 days. Apply again and we'll send a
            fresh one.
          </p>
          <Button
            onClick={() => navigate("/cohort-apply")}
            className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 text-sm"
            data-testid="welcome-expired-apply-btn"
          >
            Apply again
          </Button>
        </section>
      </WebsiteShell>
    );
  }

  if (state === "consumed") {
    return (
      <WebsiteShell title="Link already used — Akki" pathname={`/welcome/${token}`}>
        <section className="website-section section-reveal" data-testid="welcome-consumed">
          <h1 className="akki-serif text-4xl text-[var(--ink)] mb-2" data-testid="welcome-consumed-h1">
            This link was already used.
          </h1>
          <p className="dek mb-6 break-words" style={{ maxWidth: "60ch" }}>
            Magic links are single-use. Sign in below with the
            credentials you set, or apply for a fresh link.
          </p>
          <div className="flex gap-2">
            <Button
              onClick={() => navigate("/signin")}
              className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 text-sm"
              data-testid="welcome-consumed-signin-btn"
            >
              Sign in
            </Button>
          </div>
        </section>
      </WebsiteShell>
    );
  }

  if (state === "consumed_ok") {
    return (
      <WebsiteShell title="Welcome — Akki" pathname={`/welcome/${token}`}>
        <section className="website-section section-reveal" data-testid="welcome-consumed-ok">
          <h1 className="akki-serif text-4xl text-[var(--ink)] mb-2">You're in.</h1>
          <p className="dek">Opening your workspace…</p>
        </section>
      </WebsiteShell>
    );
  }

  // not_found
  return (
    <WebsiteShell title="Link not found — Akki" pathname={`/welcome/${token}`}>
      <section className="website-section section-reveal" data-testid="welcome-not-found">
        <h1 className="akki-serif text-4xl text-[var(--ink)] mb-2">We can't find that link.</h1>
        <p className="dek mb-6 break-words" style={{ maxWidth: "60ch" }}>
          Check the link in your email. If you don't have one, apply
          for a fresh link below.
        </p>
        <Button
          onClick={() => navigate("/cohort-apply")}
          className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-10 text-sm"
          data-testid="welcome-not-found-apply-btn"
        >
          Apply
        </Button>
      </section>
    </WebsiteShell>
  );
}
