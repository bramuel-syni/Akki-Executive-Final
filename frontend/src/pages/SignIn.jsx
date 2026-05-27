import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Logo from "@/components/brand/Logo";
import { ArrowRight, ShieldCheck, Quote } from "lucide-react";

/**
 * SignIn — editorial-grade entry point. Cream background, Georgia headline,
 * single-column on mobile, two-column on desktop. The left column carries an
 * editorial pull-quote in the same voice as the marketing site, NOT a dark
 * marketing photo. Connects visually to /, /about, /security so the signed-in
 * experience feels continuous with the brand.
 */
export default function SignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { afterAuth } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      afterAuth(data);
      // Phase H.5 (2026-05-27) — post-login default is `/app`.
      // The AppHome dispatcher routes the no-active-context branch
      // to the new Portfolio Landing. Once the user picks a company,
      // switchContext() leaves `/app` mounted, AppHome re-resolves
      // the active-context branch, and Home2 (→ Phase I CompanyHome)
      // takes over.
      //
      // Deep-link callers that set `location.state.from` (e.g. visiting
      // a protected URL then bouncing through signin) still resolve to
      // their target — they bypass the portfolio default.
      const to = location.state?.from || "/app";
      navigate(to, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Unable to sign in"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--cream)] flex flex-col" data-testid="signin-page">
      {/* Top bar — quiet, brand-only */}
      <header className="px-6 lg:px-10 h-16 flex items-center border-b border-[var(--rule)]">
        <Link to="/" data-testid="signin-logo-link"><Logo size="md" /></Link>
        <Link to="/" className="ml-auto text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] transition-colors" data-testid="signin-back-home">
          ← Back to akki.ai
        </Link>
      </header>

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] max-w-[1200px] w-full mx-auto">
        {/* Editorial column */}
        <aside className="hidden lg:flex flex-col justify-between p-12 lg:p-16 border-r border-[var(--rule)]">
          <div>
            <p className="akki-overline mb-4 text-[var(--accent)]">Welcome back</p>
            <h1 className="akki-serif text-[44px] leading-[1.1] tracking-tight text-[var(--ink)] mb-7 font-normal">
              The colleague who reads with you.
            </h1>
            <p className="akki-serif text-[16.5px] leading-[1.7] text-[var(--deep)] italic max-w-md">
              AKKI is the third party in the conversation — a sharp, sober
              colleague who reads every pack, remembers what the board has
              already asked, and prepares you without taking the floor.
            </p>
          </div>

          <div className="border-l-2 border-[var(--accent)] pl-5 max-w-md mt-12">
            <Quote className="w-5 h-5 text-[var(--accent)] mb-3" strokeWidth={1.6} />
            <p className="akki-serif italic text-[17px] leading-[1.6] text-[var(--deep)] mb-3">
              "It's not that we don't read the pack. It's that the pack
              doesn't read us back. AKKI does — and remembers what we asked
              the last six meetings."
            </p>
            <p className="text-[10.5px] uppercase tracking-[0.22em] text-[var(--muted)]">
              — Audit-committee chair, FTSE 250
            </p>
          </div>

          <div className="text-[10px] uppercase tracking-[0.3em] text-[var(--muted)] flex items-center gap-2">
            <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" strokeWidth={2} />
            Synisense-shielded · Confidential
          </div>
        </aside>

        {/* Form column */}
        <section className="flex items-center justify-center p-8 lg:p-16">
          <div className="w-full max-w-sm akki-fade-up">
            <p className="akki-overline mb-3">Access your workspace</p>
            <h2 className="akki-serif text-[36px] font-normal text-[var(--ink)] mb-2 leading-tight">Sign in.</h2>
            <p className="text-[13.5px] text-[var(--muted)] mb-9">
              Don't have an account?{" "}
              <Link to="/sandbox" className="text-[var(--accent)] underline underline-offset-4 hover:text-[var(--ink)]" data-testid="go-to-sandbox-link">
                Try AKKI in 60 seconds
              </Link>
              {" "}— no signup needed.
            </p>

            <form onSubmit={onSubmit} className="space-y-5" data-testid="signin-form">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold">
                  Work email
                </Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="rounded-sm h-11 bg-white border-[var(--rule)] text-[14px]"
                  placeholder="you@company.com"
                  data-testid="signin-email-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-semibold">
                  Password
                </Label>
                <Input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="rounded-sm h-11 bg-white border-[var(--rule)] text-[14px]"
                  placeholder="••••••••"
                  data-testid="signin-password-input"
                />
              </div>

              {error && (
                <div
                  className="bg-[var(--accent-soft)] border border-[var(--accent)]/30 text-[var(--accent)] px-4 py-2.5 text-[13px] rounded-sm"
                  data-testid="signin-error"
                >
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="w-full h-12 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white rounded-sm text-[14px] font-medium tracking-wide transition-colors group"
                data-testid="signin-submit-btn"
              >
                <span>{loading ? "Authenticating…" : "Sign in"}</span>
                {!loading && (
                  <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
                )}
              </Button>
            </form>

            <div className="mt-9 pt-5 border-t border-[var(--rule)]">
              <p className="text-[11.5px] text-[var(--muted)] flex items-center gap-1.5">
                <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" strokeWidth={2} />
                Protected workspace · Synisense-shielded LLM calls
              </p>
              <p className="text-[11.5px] text-[var(--muted)] mt-2">
                New to AKKI?{" "}
                <Link to="/signup" className="hover:text-[var(--ink)] underline-offset-2 hover:underline" data-testid="go-to-signup-link">
                  Request a team workspace
                </Link>
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
