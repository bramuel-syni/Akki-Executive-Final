import React from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import {
  Sparkles, ScrollText, Eye, Target, Send, MessageCircleQuestion,
  ShieldCheck, Layers, Users, FileText, ArrowRight,
} from "lucide-react";

const FEATURES = [
  {
    icon: Sparkles, name: "Signals",
    headline: "Risks, opportunities, and gaps surfaced from your pack.",
    body: "AKKI reads every document in the context and generates board-ready signals with confidence ratings, page-level citations, and a sharpest question for each. Filter by committee, by trust, by confidence.",
  },
  {
    icon: ScrollText, name: "Briefings",
    headline: "Pre-board briefing composed in under a minute.",
    body: "Bundle the signals that matter into a 1-2 page printable briefing for the meeting. Speaking notes are LLM-drafted in your voice; the PDF carries a Receipts page citing every source.",
  },
  {
    icon: Target, name: "Simulate",
    headline: "Best, base, and stress paths for any decision.",
    body: "Pose a strategic question and AKKI runs Best / Base / Stress with watchlist triggers, committee routing, and the one question to take into the room.",
  },
  {
    icon: Eye, name: "The Lens",
    headline: "Six frameworks, one structured read.",
    body: "First Principles, Customer Obsession, Systems Thinking, Capital Discipline, Stakeholder Integration, Organisational Culture. Each lens lands Observation → Implication → Action plus a question for management.",
  },
  {
    icon: Send, name: "Reporting Cycle (§12)",
    headline: "AKKI runs the cycle; you gate the conversation.",
    body: "Question Bank seeded from past minutes. AKKI drafts a tailored checklist per reportee. You review and approve. AKKI sends, collects, and surfaces the consolidated submissions ready for the report draft.",
  },
  {
    icon: MessageCircleQuestion, name: "Question Bank",
    headline: "The board's open threads in one place.",
    body: "Every 'question to take into the room' from every past briefing. AKKI tracks which have been asked, when, by whom, and what was answered. Recurring questions are flagged automatically.",
  },
  {
    icon: Layers, name: "Context Portfolio",
    headline: "All your boards, one reading post.",
    body: "NEDs serving on multiple boards switch contexts in one click. The aggregated stream surfaces the highest-priority signals across every active membership.",
  },
  {
    icon: Users, name: "Human Collaboration",
    headline: "@mentions, comments, shared briefings.",
    body: "Loop in your audit-committee chair on a single signal. Share a briefing externally with a one-click link. Reply threads, mention inbox, share inbox — the conversation lives where the artefact lives.",
  },
  {
    icon: FileText, name: "Document Journal",
    headline: "Upload, extract, ask.",
    body: "PDF, DOCX, TXT. AKKI extracts and chunks every pack you upload. Ask in natural language; answers cite the exact page. Mobile camera capture for ad-hoc minutes.",
  },
  {
    icon: ShieldCheck, name: "Trust posture",
    headline: "Receipts on every action.",
    body: "Synisense identity shielding before any LLM call. Per-context residency. Audit log surfaces every action. Export everything, delete everything — your call, your timeline.",
  },
];

export default function Features() {
  return (
    <MarketingShell>
      <section className="max-w-[1100px] mx-auto px-6 lg:px-10 py-20" data-testid="features-page">
        <p className="akki-overline mb-3 text-[var(--accent)]">Features</p>
        <h1 className="akki-serif text-[44px] sm:text-[52px] leading-[1.1] tracking-tight text-[var(--ink)] mb-6 font-normal max-w-3xl">
          What AKKI does for the executive.
        </h1>
        <p className="akki-serif text-[18px] leading-relaxed text-[var(--deep)] mb-14 max-w-2xl italic">
          Ten capabilities that compose into a single posture: read everything, surface what matters, run the cycle, gate the conversation.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-12">
          {FEATURES.map((f) => {
            const I = f.icon;
            return (
              <div key={f.name} className="flex gap-5" data-testid={`feature-${f.name.toLowerCase().replace(/\s|§|\(|\)/g, "-")}`}>
                <div className="w-10 h-10 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                  <I className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="akki-overline mb-1.5">{f.name}</p>
                  <h3 className="akki-serif text-[19px] text-[var(--ink)] mb-2 leading-snug font-normal">{f.headline}</h3>
                  <p className="text-[14.5px] text-[var(--deep)] leading-[1.65]">{f.body}</p>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-16 pt-10 border-t border-[var(--rule)] flex flex-wrap items-center gap-4">
          <p className="akki-serif text-[18px] text-[var(--ink)] flex-1 min-w-[260px]">Make it real on your own context.</p>
          <Link to="/sandbox" className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white text-[14px] rounded-md transition-colors" data-testid="features-sandbox-cta">
            Try the sandbox <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}
