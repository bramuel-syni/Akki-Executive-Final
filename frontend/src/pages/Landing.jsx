/**
 * Landing — iter65 redesign per /app/design_guidelines.json.
 *
 * Three-pillar conversion architecture:
 *   1. Solve (the strongest feature) — leads ThreePillars
 *   2. Cross Board Pulse — secondary in ThreePillars
 *   3. Decks + Reports Studio — full-bleed navy EnterpriseFeature with
 *      live sensitivity demo
 *
 * Cream/oxblood preserved. Navy #0A1F44 introduced on:
 *   - Primary Sandbox CTA (hero)
 *   - Quote attributions
 *   - Enterprise full-width band
 *
 * Removed from prior version:
 *   - "Five surfaces" propositions list (too long)
 *   - Closing call section (folded into Enterprise + final inline CTA)
 *   - Dark assurance block (folded into rubric strip)
 *   - Photo strip with three classy stills (one image lives in Hero now)
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import HeroSection from "@/components/marketing/HeroSection";
import ThreePillars from "@/components/marketing/ThreePillars";
import EnterpriseFeature from "@/components/marketing/EnterpriseFeature";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import {
  ArrowRight, Sparkles, Quote, Check, Upload, Loader2, AlertTriangle, TrendingUp,
} from "lucide-react";

const NAVY = "#0A1F44";

// ─── First-run animation ──────────────────────────────────────────────
// Kept from prior version — quiet CSS-only loop showing what AKKI does
// on a board pack. Lives between hero and three pillars as visual proof.
const FAKE_SIGNALS = [
  { icon: AlertTriangle, tone: "risk", label: "Risk", headline: "ERP migration 90% complete for six months — schedule risk on Q1 close." },
  { icon: AlertTriangle, tone: "gap",  label: "Gap",  headline: "No succession plan filed for the CFO — board-reserved matter unaddressed." },
  { icon: TrendingUp,    tone: "opp",  label: "Opportunity", headline: "Top-5 borrowers concentration easing — credit committee can widen exposure limits." },
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

      <div className="akki-fru-thinking flex items-center gap-2 mb-5 text-[11.5px] text-[var(--muted)] italic">
        <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
        AKKI is reading the pack the way an audit chair would…
      </div>

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
              <Icon className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.8} />
              <div className="flex-1 min-w-0">
                <p className="text-[10.5px] uppercase tracking-[0.16em] mb-1 opacity-70">
                  {s.label}
                </p>
                <p className="text-[13px] leading-snug">{s.headline}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


export default function Landing() {
  return (
    <div className="min-h-screen bg-[var(--cream)] text-[var(--ink)] flex flex-col" data-testid="landing-page">
      {/* ─── Masthead (shared MarketingNav) ─────────────────────── */}
      <MarketingNav />

      {/* ─── Hero — tightened value-promise + navy primary CTA ─── */}
      <HeroSection />

      {/* ─── First-run demo — visual proof of "AKKI reads the pack" ─── */}
      <section className="border-b border-[var(--rule)] bg-[var(--cream)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-14 md:py-20 grid md:grid-cols-12 gap-10 md:gap-16 items-center">
          <div className="md:col-span-5">
            <p className="akki-overline mb-4">What a first run looks like</p>
            <h2 className="akki-serif text-[28px] md:text-[36px] leading-[1.12] tracking-[-0.015em] text-[var(--ink)] font-normal mb-4">
              Drop in the pack. Read the signals.
            </h2>
            <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] max-w-[48ch]">
              90 seconds on a 40-page audit pack. Three to six things a sharp
              non-executive would notice — each one cited to the document it
              came from.
            </p>
          </div>
          <div className="md:col-span-7" data-testid="landing-first-run-demo">
            <FirstRunDemo />
          </div>
        </div>
      </section>

      {/* ─── Three Pillars — Solve hero + Pulse + Decks preview ─── */}
      <div id="solve-pillar">
        <ThreePillars />
      </div>

      {/* ─── Enterprise Decks + Reports Studio — full-bleed navy ─── */}
      <div id="enterprise">
        <EnterpriseFeature />
      </div>

      {/* ─── Editorial pull-quote — Exco360 voice ─── */}
      <section
        className="border-b border-[var(--rule)] bg-[var(--cream-deep)]/40"
        data-testid="landing-editorial-quote"
      >
        <div className="max-w-[1100px] mx-auto px-6 md:px-12 py-20 md:py-24 text-center">
          <Quote className="w-8 h-8 text-[var(--accent)] mx-auto mb-6" strokeWidth={1.4} />
          <p className="akki-serif italic text-[26px] md:text-[34px] leading-[1.35] tracking-[-0.01em] text-[var(--ink)] max-w-[28ch] mx-auto mb-7">
            Adopting tools that preserve value isn't operational —
            it is a fiduciary duty.
          </p>
          <div className="flex items-center justify-center gap-3 mb-8">
            <span
              className="inline-flex items-center px-3 py-1 rounded-sm text-[10.5px] uppercase tracking-[0.2em] font-medium"
              style={{ backgroundColor: NAVY, color: "#F7F3EA" }}
              data-testid="landing-quote-attribution"
            >
              Exco360
            </span>
            <span className="text-[var(--muted)] text-[12.5px] uppercase tracking-[0.16em]">
              AKKI's editorial voice
            </span>
          </div>
          <Link
            to="/blog"
            className="inline-flex items-center gap-2 text-[12.5px] uppercase tracking-[0.18em] text-[var(--accent)] hover:underline"
            data-testid="landing-blog-link"
          >
            Read the Exco360 Blog <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </section>

      {/* ─── Trust strip — three guarantees, condensed ─── */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-12 md:py-16 grid md:grid-cols-3 gap-8 md:divide-x divide-[var(--rule)]">
          {[
            ["Every claim cites a document.", "No unsourced numbers. No fabricated facts."],
            ["Every context stays sealed.", "Your boards never see each other. Your exec company never sees your NED work."],
            ["Every signal is verified.", "A four-stage pipeline rejects anything not supported by evidence."],
          ].map(([t, s], i) => (
            <div key={i} className="md:px-8 first:md:pl-0 last:md:pr-0" data-testid={`trust-strip-${i}`}>
              <Check className="w-4 h-4 text-[var(--accent)] mb-3" strokeWidth={2.2} />
              <p className="akki-serif text-[19px] leading-snug text-[var(--ink)] mb-1.5">{t}</p>
              <p className="text-[13px] text-[var(--muted)] leading-relaxed">{s}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Audience cards — NED + Exec, condensed ─── */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-16 md:py-24">
          <p className="akki-overline mb-3">Who it's for</p>
          <h2 className="akki-serif text-[30px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-12 max-w-[28ch]">
            Built for the rooms where capital decisions are made.
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            {[
              {
                chip: "For Non-Executive Directors",
                h: "Sitting on five boards at once.",
                body:
                  "Each board gets its own sealed context. The Audit pack you read at 7am can't bleed into the Risk pack at 10am. Each pack arrives pre-read with the three things to raise in the room.",
                testid: "audience-ned",
              },
              {
                chip: "For Operating Executives",
                h: "Running the quarter.",
                body:
                  "Bring in your management committee. Tag signals by sub-committee. Run scenarios. The Ask panel is a colleague who has read everything and cites the paragraph when you ask.",
                testid: "audience-exec",
              },
            ].map((c) => (
              <article
                key={c.testid}
                className="bg-white border border-[var(--rule)] rounded-sm p-8 md:p-10 flex flex-col"
                data-testid={c.testid}
              >
                <p className="akki-overline mb-4 text-[var(--accent)]">{c.chip}</p>
                <h3 className="akki-serif text-[22px] md:text-[26px] leading-[1.18] text-[var(--ink)] font-normal mb-4 max-w-[28ch]">
                  {c.h}
                </h3>
                <p className="akki-serif text-[15.5px] leading-[1.7] text-[var(--deep)] max-w-[50ch]">
                  {c.body}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Final inline CTA — restrained, navy primary ─── */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-16 md:py-20 text-center">
          <h2 className="akki-serif text-[28px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-4 max-w-[28ch] mx-auto">
            Open a context. Upload a pack. See what AKKI sees.
          </h2>
          <p className="akki-serif text-[15.5px] leading-[1.65] text-[var(--muted)] max-w-[52ch] mx-auto mb-8">
            Setup takes under two minutes. The first run on a board pack
            runs while you pour a coffee.
          </p>
          <div className="flex flex-wrap justify-center gap-3" data-testid="cta-final">
            <Link to="/sandbox">
              <Button
                className="rounded-sm h-12 px-7 text-[14px] font-medium tracking-wide bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
                data-testid="cta-final-sandbox"
              >
                Try AKKI in 60 seconds <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/signup">
              <Button
                variant="outline"
                className="bg-transparent border-[var(--rule)] text-[var(--deep)] hover:bg-[var(--cream-deep)] rounded-sm h-12 px-7 text-[14px]"
                data-testid="cta-final-signup"
              >
                Request a team workspace
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Footer (shared MarketingFooter) ─── */}
      <MarketingFooter />
    </div>
  );
}
