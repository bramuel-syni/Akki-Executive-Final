import React from "react";
import { Link } from "react-router-dom";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import {
  ArrowRight, Sparkles, ScrollText, Eye, FileText, Target, GraduationCap,
  Quote, Check, Upload, Loader2, AlertTriangle, TrendingUp,
} from "lucide-react";

/**
 * Executive-editorial landing page. Cream canvas, serif headlines, left-aligned
 * magazine rhythm. Navy reserved for AKKI wordmark only. No stock imagery — the
 * copy does the work. The audience is NEDs and senior executives; restraint
 * over decoration, typography over hero shots.
 */

const FAKE_SIGNALS = [
  { icon: AlertTriangle, tone: "risk", label: "Risk", delay: 0, headline: "ERP migration 90% complete for six months — schedule risk on Q1 close." },
  { icon: AlertTriangle, tone: "gap",  label: "Gap",  delay: 1, headline: "No succession plan filed for the CFO — board-reserved matter unaddressed." },
  { icon: TrendingUp,    tone: "opp",  label: "Opportunity", delay: 2, headline: "Top-5 borrowers concentration easing — credit committee can widen exposure limits." },
];

function FirstRunDemo() {
  return (
    <div className="relative bg-white border border-[var(--rule)] rounded-md p-6 md:p-8 overflow-hidden" style={{ minHeight: 280 }}>
      <style>{`
        @keyframes akki-fru-upload  { 0%,5%{opacity:0;transform:translateY(6px)} 10%,28%{opacity:1;transform:translateY(0)} 32%,100%{opacity:0.3;transform:translateY(0)} }
        @keyframes akki-fru-progress{ 0%,10%{width:0%}  28%{width:100%} 32%,100%{width:100%} }
        @keyframes akki-fru-thinking{ 0%,28%{opacity:0} 30%,38%{opacity:1} 40%,100%{opacity:0} }
        @keyframes akki-fru-sig-1   { 0%,38%{opacity:0;transform:translateY(4px)} 42%,100%{opacity:1;transform:translateY(0)} }
        @keyframes akki-fru-sig-2   { 0%,48%{opacity:0;transform:translateY(4px)} 52%,100%{opacity:1;transform:translateY(0)} }
        @keyframes akki-fru-sig-3   { 0%,58%{opacity:0;transform:translateY(4px)} 62%,100%{opacity:1;transform:translateY(0)} }
        .akki-fru-upload   { animation: akki-fru-upload 12s ease-in-out infinite; }
        .akki-fru-progress { animation: akki-fru-progress 12s ease-in-out infinite; }
        .akki-fru-thinking { animation: akki-fru-thinking 12s ease-in-out infinite; }
        .akki-fru-s1       { animation: akki-fru-sig-1 12s ease-in-out infinite; opacity:0; }
        .akki-fru-s2       { animation: akki-fru-sig-2 12s ease-in-out infinite; opacity:0; }
        .akki-fru-s3       { animation: akki-fru-sig-3 12s ease-in-out infinite; opacity:0; }
        @media (prefers-reduced-motion: reduce) {
          .akki-fru-upload, .akki-fru-progress, .akki-fru-thinking,
          .akki-fru-s1, .akki-fru-s2, .akki-fru-s3 { animation: none; opacity: 1; }
          .akki-fru-progress { width: 100%; }
        }
      `}</style>

      {/* Upload line */}
      <div className="akki-fru-upload flex items-center gap-3 mb-3">
        <div className="w-8 h-8 bg-[var(--cream-deep)] rounded-sm flex items-center justify-center">
          <Upload className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[12px] font-medium text-[var(--ink)]">Q4_Audit_Committee_Pack_Nov2025.pdf</p>
          <p className="text-[10px] text-[var(--muted)]">2.4 MB · 42 pages · shielded by Synisense</p>
        </div>
      </div>
      <div className="h-[2px] bg-[var(--cream-deep)] rounded-full mb-5 overflow-hidden">
        <div className="akki-fru-progress h-full bg-[var(--accent)]" style={{ width: 0 }} />
      </div>

      {/* Thinking marker */}
      <div className="akki-fru-thinking flex items-center gap-2 mb-5 text-[11.5px] text-[var(--muted)] italic">
        <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
        AKKI is reading the pack the way an audit chair would…
      </div>

      {/* Signals appear, staggered */}
      <div className="space-y-2.5">
        {FAKE_SIGNALS.map((s, i) => {
          const Icon = s.icon;
          const anim = ["akki-fru-s1", "akki-fru-s2", "akki-fru-s3"][i];
          const toneClass =
            s.tone === "risk" ? "border-red-300/70 bg-red-50/60 text-red-900"
            : s.tone === "gap" ? "border-amber-300/70 bg-amber-50/60 text-amber-900"
            : "border-emerald-300/70 bg-emerald-50/60 text-emerald-900";
          return (
            <div
              key={i}
              className={`${anim} border-l-2 ${toneClass} rounded-sm px-4 py-3 flex items-start gap-3`}
            >
              <Icon className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={1.8} />
              <div className="flex-1 min-w-0">
                <p className="text-[10px] uppercase tracking-[0.2em] opacity-70 mb-0.5">{s.label} · cited</p>
                <p className="text-[13px] text-[var(--ink)] leading-snug">{s.headline}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const PROPOSITIONS = [
  {
    kicker: "01 · The read",
    icon: ScrollText,
    title: "Board packs, read for you — with citations.",
    body:
      "AKKI reads your pack as a sharp audit chair would — naming the 3–6 things a non-executive should notice on a first read, each cited to the exact document it came from. Every claim is traceable. Nothing fabricated.",
  },
  {
    kicker: "02 · The stress-test",
    icon: Eye,
    title: "Six named frameworks. One disciplined output.",
    body:
      "First Principles. Customer Obsession. Systems Thinking. Capital Discipline. Stakeholder Integration. Organisational Culture. Pick a lens, feed it a subject — and get a structured Observation → Implication → Action, plus the single question to put to management.",
  },
  {
    kicker: "03 · The forecast",
    icon: Target,
    title: "Qualitative scenarios over one and three years.",
    body:
      "Stress-test a hypothesis and AKKI will walk you through best, base and stress trajectories for the horizon you care about — with an early-warning watchlist your audit or risk committee can table at the next meeting.",
  },
  {
    kicker: "04 · The briefing",
    icon: FileText,
    title: "From signals to a printable page.",
    body:
      "Compose a briefing from the signals AKKI has surfaced, export it as a cleanly typeset PDF or DOCX, and take it into the room. Versioned. Evidence-anchored. Ready for a 9am start.",
  },
];

const ASSURANCES = [
  "Context-isolated data — every board, every company, a sealed room.",
  "Synisense identity shielding on every LLM call — nothing personally identifying leaves the pod.",
  "Every signal carries the doc_id that evidenced it. Every briefing cites its sources by line.",
  "A 4-stage pipeline validates each signal before it reaches the board paper. Candidates that cannot be supported by a cited doc are rejected before persistence.",
];

const VOICE_QUOTE = {
  body:
    "I have been on five boards for a decade. I have never once had tooling that could honestly say: here is what you missed on the first read, and here is the document that proves it. AKKI is the first thing that reads a pack the way I would.",
  attribution: "Prototype reader, sitting NED · Kenya · financial services",
};

export default function Landing() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[var(--cream)] text-[var(--ink)] flex flex-col" data-testid="landing-page">
      {/* ─── Masthead ─────────────────────────────────────────── */}
      <header className="border-b border-[var(--rule)] bg-[var(--cream)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 h-16 flex items-center justify-between">
          <Logo />
          <nav className="flex items-center gap-1 md:gap-4 text-[13px]">
            <a href="#proposition" className="hidden md:inline text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
              What it does
            </a>
            <a href="#assurance" className="hidden md:inline text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
              How it's trustworthy
            </a>
            {user ? (
              <Link to="/app">
                <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-4 text-[13px] font-medium" data-testid="landing-go-to-app">
                  Go to workspace <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
              </Link>
            ) : (
              <>
                <Link to="/signin" className="text-[var(--deep)] hover:text-[var(--ink)] px-3 py-1.5" data-testid="landing-signin-link">
                  Sign in
                </Link>
                <Link to="/signup">
                  <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-4 text-[13px] font-medium" data-testid="landing-signup-btn">
                    Request access <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* ─── Hero — editorial title page ──────────────────────── */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 grid md:grid-cols-12 gap-12 md:gap-16 items-start">
          <div className="md:col-span-8">
            <p className="akki-overline mb-8" data-testid="hero-overline">
              Executive intelligence · for non-executive directors and operating executives
            </p>
            <h1
              className="akki-serif text-[40px] sm:text-[56px] md:text-[72px] leading-[1.04] tracking-[-0.02em] text-[var(--ink)] font-normal mb-10"
              data-testid="hero-headline"
            >
              Read sharper.
              <br />
              Challenge better.
              <br />
              <span className="text-[var(--accent)] italic">Decide with receipts.</span>
            </h1>
            <p className="akki-serif text-[18px] md:text-[20px] leading-[1.7] text-[var(--deep)] max-w-[52ch] mb-10">
              AKKI is an intelligence layer for directors and executives sitting on
              multiple boards. It reads your pack the way a seasoned audit-committee
              chair would — naming what you would otherwise miss, stress-testing
              what management is asking you to accept, and citing every number back
              to the exact document it came from.
            </p>
            <div className="flex flex-col items-start gap-5 max-w-md" data-testid="hero-cta">
              {/* Primary — single prominent button. The whole funnel collapses
                  to "try it without commitment, see if it earns the conversation." */}
              <Link to="/sandbox" className="group" data-testid="hero-sandbox-btn">
                <Button
                  className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white rounded-sm h-14 px-8 text-[15px] font-medium tracking-wide shadow-sm"
                >
                  Try AKKI in 60 seconds <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
                </Button>
              </Link>
              <p className="text-[12.5px] text-[var(--muted)] -mt-2 leading-relaxed">
                <strong className="text-[var(--deep)]">The Sandbox</strong> is AKKI loaded with sample data for a fictional company in your sector. No signup. Yours for 14 days, then it deletes itself.
              </p>

              {/* Secondary — quiet, side-by-side, styled as gestures not buttons */}
              <div className="flex items-center gap-5 pt-3 mt-1 border-t border-[var(--rule)] w-full">
                <Link to="/signin" className="text-[13px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors" data-testid="hero-signin-btn">
                  Sign in to your workspace
                </Link>
                <span className="text-[var(--rule)]">·</span>
                <Link to="/signup" className="text-[13px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors" data-testid="hero-signup-btn">
                  Request a team workspace
                </Link>
              </div>
            </div>
          </div>

          {/* Right-hand pull quote — editorial sidebar */}
          <aside className="md:col-span-4 md:pt-8 md:border-l md:border-[var(--rule)] md:pl-10">
            <Quote className="w-5 h-5 text-[var(--accent)] mb-4" strokeWidth={1.6} />
            <p
              className="akki-serif italic text-[17px] md:text-[19px] leading-[1.6] text-[var(--deep)] mb-5"
              data-testid="hero-quote"
            >
              "{VOICE_QUOTE.body}"
            </p>
            <p className="text-[11px] uppercase tracking-[0.2em] text-[var(--muted)]">
              — {VOICE_QUOTE.attribution}
            </p>
          </aside>
        </div>
      </section>

      {/* ─── First-run animation — quiet, CSS-only, loops every 12s ───── */}
      <section className="border-b border-[var(--rule)] bg-[var(--cream)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-14 md:py-20 grid md:grid-cols-12 gap-10 md:gap-16 items-center">
          <div className="md:col-span-5">
            <p className="akki-overline mb-4">What a first run looks like</p>
            <h2 className="akki-serif text-[28px] md:text-[36px] leading-[1.12] tracking-[-0.015em] text-[var(--ink)] font-normal mb-4">
              Upload the pack. Pour the coffee. Read the signals.
            </h2>
            <p className="akki-serif text-[16px] leading-[1.75] text-[var(--deep)] max-w-[48ch]">
              The average first run on a 40-page audit pack completes in under 90
              seconds. AKKI surfaces the three to six things a sharp non-executive
              would notice — each cited to the document it came from, each
              defensible in the room.
            </p>
          </div>

          <div className="md:col-span-7" data-testid="landing-first-run-demo">
            <FirstRunDemo />
          </div>
        </div>
      </section>

      {/* ─── Rubric strip — the three guarantees ──────────────── */}
      <section className="border-b border-[var(--rule)] bg-[var(--cream-deep)]/60">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-10 grid md:grid-cols-3 gap-8 md:divide-x divide-[var(--rule)]">
          {[
            ["Every claim cites a document.", "No unsourced numbers. No hallucinated facts."],
            ["Every context is sealed.", "Your boards never see each other. Your exec company never sees your NED work."],
            ["Every signal is verified.", "A 4-stage pipeline rejects candidates that cannot be supported by evidence."],
          ].map(([t, s], i) => (
            <div key={i} className="md:px-8 first:md:pl-0 last:md:pr-0">
              <p className="akki-serif text-[18px] leading-snug text-[var(--ink)] mb-1">{t}</p>
              <p className="text-[13px] text-[var(--muted)] leading-relaxed">{s}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── What it does — editorial body, proper measure ────── */}
      <section id="proposition" className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28">
          <div className="grid md:grid-cols-12 gap-12 md:gap-16 mb-16">
            <div className="md:col-span-4">
              <p className="akki-overline mb-4">The proposition</p>
              <h2 className="akki-serif text-[32px] md:text-[44px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal">
                Four surfaces. One discipline.
              </h2>
            </div>
            <p className="md:col-span-8 akki-serif text-[17px] md:text-[18px] leading-[1.8] text-[var(--deep)] max-w-[62ch]">
              AKKI is not a chatbot pointed at your documents. It is a set of
              purpose-built surfaces, each with a narrow, defensible remit.
              You move between them the way you move between sections of a
              board paper — because that's the work.
            </p>
          </div>

          <ol className="divide-y divide-[var(--rule)]">
            {PROPOSITIONS.map((p, i) => {
              const Icon = p.icon;
              return (
                <li
                  key={p.kicker}
                  className="grid md:grid-cols-12 gap-6 md:gap-10 py-10 md:py-12"
                  data-testid={`prop-item-${i}`}
                >
                  <div className="md:col-span-4 flex md:flex-col items-start gap-4 md:gap-3">
                    <div className="w-10 h-10 bg-[var(--cream-deep)] rounded-sm flex items-center justify-center shrink-0">
                      <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                    </div>
                    <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--muted)] mt-2">
                      {p.kicker}
                    </p>
                  </div>
                  <div className="md:col-span-8 max-w-[58ch]">
                    <h3 className="akki-serif text-[24px] md:text-[28px] leading-[1.2] text-[var(--ink)] mb-4 font-normal tracking-[-0.01em]">
                      {p.title}
                    </h3>
                    <p className="akki-serif text-[16px] md:text-[17px] leading-[1.75] text-[var(--deep)]">
                      {p.body}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      {/* ─── Assurance — trust signals in a dark serif block ───── */}
      <section id="assurance" className="bg-[var(--ink)] text-[var(--cream)] border-b border-black/30">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 grid md:grid-cols-12 gap-12">
          <div className="md:col-span-4">
            <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--accent)]/80 mb-4">
              What makes this defensible
            </p>
            <h2 className="akki-serif text-[32px] md:text-[40px] leading-[1.1] font-normal tracking-[-0.015em] text-[var(--cream)]">
              A director's instinct to distrust AI — met halfway.
            </h2>
          </div>
          <ul className="md:col-span-8 space-y-6 max-w-[62ch]">
            {ASSURANCES.map((a, i) => (
              <li key={i} className="flex gap-4 akki-fade-up">
                <Check className="w-4 h-4 text-[var(--accent)] shrink-0 mt-1.5" strokeWidth={2.2} />
                <p className="akki-serif text-[16px] md:text-[17px] leading-[1.75] text-[var(--cream)]/85">
                  {a}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ─── Who it's for ─────────────────────────────────────── */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 grid md:grid-cols-2 gap-px bg-[var(--rule)]">
          {[
            {
              chip: "For Non-Executive Directors",
              h: "For the board member sitting on five things at once.",
              body:
                "Every board gets its own sealed context. The Audit pack you read at 7am can't bleed into the Risk pack you read at 10am — or the competitor intelligence you keep in your personal research context. Each pack arrives pre-read, with the three things you should raise in the room.",
              testid: "audience-ned",
            },
            {
              chip: "For Operating Executives",
              h: "For the CEO, CFO or Chief-of-Staff running the quarter.",
              body:
                "Bring in your management committee, tag signals and briefings by sub-committee, run scenarios on your hypothesis and keep the resulting watchlist in one place. The Ask panel is a colleague who has read everything and cites the paragraph when you ask.",
              testid: "audience-exec",
            },
          ].map((c, i) => (
            <article
              key={i}
              className="bg-[var(--cream)] p-10 md:p-14 flex flex-col"
              data-testid={c.testid}
            >
              <p className="akki-overline mb-5">{c.chip}</p>
              <h3 className="akki-serif text-[24px] md:text-[28px] leading-[1.22] text-[var(--ink)] font-normal mb-5 max-w-[32ch]">
                {c.h}
              </h3>
              <p className="akki-serif text-[16px] leading-[1.75] text-[var(--deep)] max-w-[54ch]">
                {c.body}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* ─── Closing call — restrained, confident ─────────────── */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 text-center">
          <p className="akki-overline mb-6">Access</p>
          <h2 className="akki-serif text-[36px] md:text-[56px] leading-[1.08] tracking-[-0.015em] text-[var(--ink)] font-normal mb-6 max-w-[26ch] mx-auto">
            Open a context. Upload a pack. See what a sharp reader sees.
          </h2>
          <p className="akki-serif text-[17px] leading-[1.7] text-[var(--muted)] max-w-[56ch] mx-auto mb-10">
            Access is by invitation during the sandbox period. Setup takes under two
            minutes, and the first signal run on a board pack usually completes while
            you're pouring a coffee.
          </p>
          <div className="flex flex-wrap justify-center gap-4" data-testid="cta-final">
            <Link to="/signup">
              <Button
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-12 px-7 text-[14px] font-medium tracking-wide"
                data-testid="cta-final-signup"
              >
                Request your workspace <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/signin">
              <Button
                variant="outline"
                className="bg-transparent border-[var(--rule)] text-[var(--deep)] hover:bg-[var(--cream-deep)] rounded-sm h-12 px-7 text-[14px]"
                data-testid="cta-final-signin"
              >
                Sign in
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Colophon ─────────────────────────────────────────── */}
      <footer className="bg-[var(--cream)] px-6 md:px-12 py-8 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-6 text-[11px] uppercase tracking-[0.2em] text-[var(--muted)]">
          <span>© 2026 Syni.ai</span>
          <span className="hidden md:inline">·</span>
          <span>AKKI</span>
          <span className="hidden md:inline">·</span>
          <span>v1.0</span>
        </div>
        <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--accent)] flex items-center gap-1.5">
          <Sparkles className="w-3 h-3" /> Confidential · by invitation
        </p>
      </footer>
    </div>
  );
}
