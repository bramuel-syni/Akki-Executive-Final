import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Logo from "@/components/brand/Logo";
import { ArrowRight } from "lucide-react";

const BG = "https://static.prod-images.emergentagent.com/jobs/0441d610-5908-43db-b746-3ec05187ba11/images/708daea7b9b446b2eb96ba8c62c926559162b8b148c9d38a052037a00298cfbb.png";

export default function SignUp() {
  const [form, setForm] = useState({ name: "", email: "", password: "", tenant_name: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { afterAuth } = useAuth();
  const navigate = useNavigate();

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/register", {
        name: form.name,
        email: form.email,
        password: form.password,
        context_name: form.tenant_name || undefined,
      });
      afterAuth(data);
      navigate("/onboarding");
    } catch (err) {
      setError(apiErrorMessage(err, "Unable to create workspace"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] bg-white">
      <aside className="relative hidden lg:flex flex-col justify-between bg-[var(--ink)] text-white p-12 overflow-hidden">
        <div
          className="absolute inset-0 opacity-60"
          style={{ backgroundImage: `url(${BG})`, backgroundSize: "cover", backgroundPosition: "center" }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--ink)]/85 via-[var(--ink)]/70 to-[var(--ink)]/95" />
        <div className="relative z-10"><Logo size="lg" inverted /></div>
        <div className="relative z-10 max-w-xl">
          <p className="akki-overline mb-4">New account · 2 minutes</p>
          <h1 className="text-4xl lg:text-5xl font-light tracking-tight leading-[1.1] mb-6">
            Create an <span className="text-[var(--accent)]">AKKI account.</span>
          </h1>
          <p className="text-white/65 text-base leading-relaxed max-w-md">
            One account holds many contexts — each board, each organisation.
            After signup, declare your role (NED / Executive / Both) and run the
            board-focused audit that tunes AKKI to you.
          </p>

          <div className="mt-10 space-y-3 pt-8 border-t border-white/10 text-sm">
            <div className="flex items-start gap-3">
              <span className="w-6 h-6 border border-[var(--accent)]/50 text-[var(--accent)] text-[10px] flex items-center justify-center tracking-wider">1</span>
              <div><p className="font-medium text-white/90">Create account</p><p className="text-white/45 text-xs">Your email, your first context</p></div>
            </div>
            <div className="flex items-start gap-3">
              <span className="w-6 h-6 border border-white/20 text-white/40 text-[10px] flex items-center justify-center tracking-wider">2</span>
              <div><p className="text-white/60">Declare role</p><p className="text-white/35 text-xs">NED · Executive · Both</p></div>
            </div>
            <div className="flex items-start gap-3">
              <span className="w-6 h-6 border border-white/20 text-white/40 text-[10px] flex items-center justify-center tracking-wider">3</span>
              <div><p className="text-white/60">Board-focused audit</p><p className="text-white/35 text-xs">7 questions, ships in next build</p></div>
            </div>
          </div>
        </div>
        <div className="relative z-10 text-[10px] uppercase tracking-[0.3em] text-white/30">
          Confidential · Internal · AKKI Sandbox
        </div>
      </aside>

      <section className="flex items-center justify-center p-8 lg:p-16">
        <div className="w-full max-w-sm akki-fade-up">
          <div className="lg:hidden mb-8"><Logo size="lg" /></div>
          <p className="akki-overline mb-3">Step 1 of 3 · Create account</p>
          <h2 className="text-3xl font-light tracking-tight text-[var(--ink)] mb-2">Get started</h2>
          <p className="text-sm text-slate-500 mb-10">
            Already have access?{" "}
            <Link to="/signin" className="akki-link" data-testid="go-to-signin-link">
              Sign in
            </Link>
          </p>

          <form onSubmit={onSubmit} className="space-y-4" data-testid="signup-form">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                Full name
              </Label>
              <Input id="name" required value={form.name} onChange={update("name")} className="rounded-sm h-11" placeholder="Amara Okafor" data-testid="signup-name-input" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                Work email
              </Label>
              <Input id="email" type="email" required value={form.email} onChange={update("email")} className="rounded-sm h-11" placeholder="you@company.com" data-testid="signup-email-input" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                Password
              </Label>
              <Input id="password" type="password" required minLength={8} value={form.password} onChange={update("password")} className="rounded-sm h-11" placeholder="At least 8 characters" data-testid="signup-password-input" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tenant_name" className="text-xs uppercase tracking-wider text-slate-500 font-semibold">
                First context name <span className="text-slate-400 font-normal normal-case tracking-normal">(optional)</span>
              </Label>
              <Input id="tenant_name" value={form.tenant_name} onChange={update("tenant_name")} className="rounded-sm h-11" placeholder="e.g. First National Bank Board" data-testid="signup-tenant-input" />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 text-sm rounded-sm" data-testid="signup-error">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-[var(--ink)] hover:bg-[#0E2958] text-white rounded-sm text-sm font-medium tracking-wide transition-colors group mt-2"
              data-testid="signup-submit-btn"
            >
              <span>{loading ? "Creating workspace…" : "Create workspace"}</span>
              {!loading && <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />}
            </Button>
          </form>

          <p className="mt-8 text-[10px] text-slate-400 leading-relaxed">
            By creating an account you accept AKKI's terms of service and acknowledge
            that data is processed within context-isolated containers with Synisense identity shielding.
          </p>
        </div>
      </section>
    </div>
  );
}
