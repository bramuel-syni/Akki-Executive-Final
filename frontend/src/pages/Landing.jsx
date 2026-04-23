import React from "react";
import { Link } from "react-router-dom";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { ArrowRight, Radar, FileText, LineChart, MessageSquareText, GraduationCap, Layers } from "lucide-react";

const BG = "https://static.prod-images.emergentagent.com/jobs/0441d610-5908-43db-b746-3ec05187ba11/images/45ea328e6111fa06c7b3530f0bd66291c809bf1519364c126f09302bc02b65f2.png";

const MODULES = [
  { i: Radar, t: "Highlights", d: "Synisense-verified signals across your boards" },
  { i: FileText, t: "Workspace", d: "Co-author with AKKI. Stress-test with the Lens Room" },
  { i: LineChart, t: "Briefings", d: "Pack summaries that cite their sources" },
  { i: MessageSquareText, t: "Ask", d: "Persistent threads with inline source citations" },
  { i: GraduationCap, t: "Learn", d: "Role-tuned curriculum + curated intelligence" },
  { i: Layers, t: "Contexts", d: "One account · many boards · data-isolated" },
];

export default function Landing() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-white">
      {/* Header */}
      <header className="bg-[var(--ink)] text-white border-b border-black/20 h-16 flex items-center px-6 md:px-12 justify-between">
        <Logo inverted />
        <nav className="flex items-center gap-3 text-sm">
          {user ? (
            <Link to="/app">
              <Button className="bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-9 font-medium" data-testid="landing-go-to-app">
                Go to workspace <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </Link>
          ) : (
            <>
              <Link to="/signin" className="text-white/80 hover:text-white px-3 py-1.5 text-sm" data-testid="landing-signin-link">Sign in</Link>
              <Link to="/signup">
                <Button className="bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-9 font-medium" data-testid="landing-signup-btn">
                  Request access <ArrowRight className="w-4 h-4 ml-1.5" />
                </Button>
              </Link>
            </>
          )}
        </nav>
      </header>

      {/* Hero */}
      <section className="relative bg-[var(--ink)] text-white overflow-hidden border-b border-black/30">
        <div
          className="absolute inset-0 opacity-55"
          style={{ backgroundImage: `url(${BG})`, backgroundSize: "cover", backgroundPosition: "center" }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[var(--ink)]/70 via-[var(--ink)]/80 to-[var(--ink)]" />
        <div className="akki-grid-bg absolute inset-0 opacity-10" />

        <div className="relative z-10 max-w-6xl mx-auto px-6 md:px-12 py-24 md:py-32">
          <p className="akki-overline mb-5">Executive intelligence platform · Confidential</p>
          <h1 className="text-4xl md:text-6xl lg:text-7xl font-light tracking-tight leading-[1.02] mb-8 max-w-4xl">
            Decisions grounded <br />
            in <span className="text-[var(--accent)]">verified data.</span>
          </h1>
          <p className="text-lg text-white/65 max-w-2xl leading-relaxed mb-10">
            AKKI is the intelligence layer for non-executive directors and operating executives.
            Read board packs sharper, prepare reports that hold up to scrutiny, stress-test ideas
            through named frameworks — all within context-isolated workspaces protected by
            Synisense identity shielding. Every claim traceable. Nothing fabricated.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/signup">
              <Button className="bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--ink)] rounded-sm h-11 px-6 font-medium tracking-wide" data-testid="hero-signup-btn">
                Create workspace <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/signin">
              <Button variant="outline" className="bg-transparent border-white/30 text-white hover:bg-white/10 rounded-sm h-11 px-6" data-testid="hero-signin-btn">
                Sign in
              </Button>
            </Link>
          </div>

          <div className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-px bg-white/10 max-w-4xl">
            {[
              ["Dual-role", "NED + Executive in one account"],
              ["6", "Named frameworks in the Lens Room"],
              ["Synisense", "Identity shielding on every LLM call"],
              ["0", "Hallucinated numbers tolerated"],
            ].map(([n, l]) => (
              <div key={l} className="bg-[var(--ink)] px-6 py-6">
                <p className="text-2xl lg:text-3xl font-light tracking-tight text-[var(--accent)]">{n}</p>
                <p className="text-xs text-white/55 mt-1 tracking-wide">{l}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modules strip */}
      <section className="max-w-6xl mx-auto px-6 md:px-12 py-20">
        <div className="flex items-end justify-between mb-10">
          <div>
            <p className="akki-overline mb-3">Modules</p>
            <h2 className="text-3xl md:text-4xl font-light tracking-tight text-[var(--ink)]">
              One workspace, six disciplined surfaces.
            </h2>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-[#E1E6ED] border border-[#E1E6ED]">
          {MODULES.map(({ i: I, t, d }) => (
            <div key={t} className="bg-white p-8 hover:bg-slate-50/60 transition-colors group">
              <I className="w-5 h-5 text-[var(--accent)] mb-5" strokeWidth={1.8} />
              <p className="text-sm font-semibold text-[var(--ink)] mb-1">{t}</p>
              <p className="text-sm text-slate-500 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-[#E1E6ED] bg-white px-6 md:px-12 py-6 flex items-center justify-between text-xs text-slate-400">
        <p>© 2026 Syni.ai · AKKI Sandbox · v1.0</p>
        <p className="uppercase tracking-[0.25em]">Confidential — internal</p>
      </footer>
    </div>
  );
}
