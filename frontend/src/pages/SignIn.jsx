import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Logo from "@/components/brand/Logo";
import { ArrowRight, ShieldCheck, Radar, LineChart } from "lucide-react";

const BG = "https://static.prod-images.emergentagent.com/jobs/0441d610-5908-43db-b746-3ec05187ba11/images/708daea7b9b446b2eb96ba8c62c926559162b8b148c9d38a052037a00298cfbb.png";

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
      const to = location.state?.from || "/app";
      navigate(to, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "Unable to sign in"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] bg-white" data-testid="signin-page">
      {/* Left visual panel — navy with art */}
      <aside className="relative hidden lg:flex flex-col justify-between bg-[var(--ink)] text-white p-12 overflow-hidden">
        <div
          className="absolute inset-0 opacity-60"
          style={{ backgroundImage: `url(${BG})`, backgroundSize: "cover", backgroundPosition: "center" }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--ink)]/85 via-[var(--ink)]/70 to-[var(--ink)]/95" />
        <div className="absolute inset-0 akki-dots-bg opacity-20" />

        <div className="relative z-10">
          <Logo size="lg" inverted />
        </div>

        <div className="relative z-10 space-y-10 max-w-xl">
          <div>
            <p className="akki-overline mb-4">Executive intelligence · v1.0</p>
            <h1 className="text-4xl lg:text-5xl font-light tracking-tight leading-[1.1] mb-6">
              The intelligence layer <br />
              for <span className="text-[var(--accent)]">boardrooms.</span>
            </h1>
            <p className="text-white/65 text-base leading-relaxed max-w-md">
              AKKI is built for non-executive directors and operating executives —
              read board packs sharper, prepare reports that stand up to scrutiny,
              with every claim traceable via Synisense.
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-white/10">
            {[
              { i: Radar, t: "Signals", s: "Synisense-verified signals across your boards" },
              { i: LineChart, t: "Briefings", s: "Pack summaries that cite their sources" },
              { i: ShieldCheck, t: "Provable privacy", s: "Identity-shielded LLM calls via Synisense" },
            ].map(({ i: I, t, s }) => (
              <div key={t} className="flex items-start gap-3 text-sm">
                <I className="w-4 h-4 text-[var(--accent)] mt-0.5" strokeWidth={1.8} />
                <div>
                  <p className="text-white/90 font-medium">{t}</p>
                  <p className="text-white/50 text-xs">{s}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-[10px] uppercase tracking-[0.3em] text-white/30">
          Confidential · Internal · AKKI Sandbox
        </div>
      </aside>

      {/* Right form panel */}
      <section className="flex items-center justify-center p-8 lg:p-16">
        <div className="w-full max-w-sm akki-fade-up">
          <div className="lg:hidden mb-8"><Logo size="lg" /></div>
          <p className="akki-overline mb-3">Access your workspace</p>
          <h2 className="text-3xl font-light tracking-tight text-[var(--ink)] mb-2">Sign in</h2>
          <p className="text-sm text-slate-500 mb-10">
            New to AKKI?{" "}
            <Link to="/signup" className="akki-link" data-testid="go-to-signup-link">
              Create an executive workspace
            </Link>
          </p>

          <form onSubmit={onSubmit} className="space-y-5" data-testid="signin-form">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                Work email
              </Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-sm h-11 border-[#E1E6ED]"
                placeholder="you@company.com"
                data-testid="signin-email-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-sm h-11 border-[#E1E6ED]"
                placeholder="••••••••"
                data-testid="signin-password-input"
              />
            </div>

            {error && (
              <div
                className="bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 text-sm rounded-sm"
                data-testid="signin-error"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-[var(--ink)] hover:bg-[#0E2958] text-white rounded-sm text-sm font-medium tracking-wide transition-colors group"
              data-testid="signin-submit-btn"
            >
              <span>{loading ? "Authenticating…" : "Sign in to workspace"}</span>
              {!loading && (
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
              )}
            </Button>
          </form>

          <p className="mt-10 text-[10px] uppercase tracking-[0.2em] text-slate-400">
            Protected workspace · SAML/OIDC ready
          </p>
        </div>
      </section>
    </div>
  );
}
