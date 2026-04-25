import React from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { ShieldCheck, Lock, Eye, FileCheck, ArrowRight } from "lucide-react";

const PROMISES = [
  {
    n: "01", icon: Lock, title: "Residency",
    headline: "Your context never leaves this account.",
    detail: "Documents, signals, briefings, and lens outputs are scoped to the active context and visible only to its members. Cross-tenant leakage is impossible by construction — enforced at query time, not by a configuration toggle.",
    proof: "Audit log shows every read and write per actor. Memberships are exclusive per context.",
  },
  {
    n: "02", icon: ShieldCheck, title: "Shielding",
    headline: "Identities are masked before any LLM call.",
    detail: "Synisense rewrites names, emails, organisation identifiers, and other identity tokens to opaque references before the prompt leaves the server. Responses are rehydrated server-side. The model never sees your principals.",
    proof: "Every LLM-backed response surfaces a `shielding` receipt — masked count, by category, shielded-by service tag.",
  },
  {
    n: "03", icon: FileCheck, title: "Provenance",
    headline: "Every signal cites the exact page it came from.",
    detail: "Briefings ship with a Receipts page. Lens runs expose Observation → Implication → Action with their sources. Ask answers carry [doc:xxx] inline citations. Nothing gets asserted without traceable evidence.",
    proof: "Click any citation to open the source document at the exact section. Export the briefing PDF — receipts travel with it.",
  },
  {
    n: "04", icon: Eye, title: "Control",
    headline: "Export or delete everything, any time.",
    detail: "The Audit log shows every action ever taken on this context. The Danger zone in Settings exports the full context as JSON or archives it. Sandbox data is hard-deleted on day 22 automatically.",
    proof: "No retention bargains, no hidden tiers. The 'Delete' button does what it says.",
  },
];

const POSTURE_ITEMS = [
  ["AKKI never sends external communications without your approval.", "When AKKI emails a reportee, you reviewed and approved the checklist first. The sender header reads 'AKKI for [your name]' so the role is explicit. Replies route to your real inbox, not AKKI's."],
  ["Mock-by-default for paid integrations until you opt in.", "Stripe billing, real virus scanning, vector DBs — all of these stay mocked until you explicitly turn them on. We ship value before we ship spend."],
  ["Custom JWT auth with bcrypt + optional TOTP MFA.", "Brute-force lockout keyed on email (not IP, since Kubernetes ingress rotates). MFA can be enabled per-account. Cookies are httpOnly + samesite=none."],
  ["Open-source LLM key managed by Emergent.", "We use Anthropic's Claude Sonnet via the Emergent universal key — a single entry point with rotation, rate limits, and cost telemetry under our control."],
];

export default function Security() {
  return (
    <MarketingShell>
      <section className="max-w-[1100px] mx-auto px-6 lg:px-10 py-20" data-testid="security-page">
        <p className="akki-overline mb-3 text-[var(--accent)]">Security & Trust</p>
        <h1 className="akki-serif text-[44px] sm:text-[52px] leading-[1.1] tracking-tight text-[var(--ink)] mb-6 font-normal max-w-3xl">
          Four promises. Each enforced in code.
        </h1>
        <p className="akki-serif text-[18px] leading-relaxed text-[var(--deep)] mb-12 italic max-w-2xl">
          Boards that hold their managers to a standard of "trust but verify" deserve the same posture from the tool that prepares them.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8" data-testid="security-promises">
          {PROMISES.map((p) => {
            const I = p.icon;
            return (
              <div key={p.n} className="bg-white border border-[var(--rule)] rounded-lg p-7 relative overflow-hidden">
                <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--chrome)]" />
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-md bg-[var(--chrome)]/10 flex items-center justify-center">
                    <I className="w-4 h-4 text-[var(--chrome)]" strokeWidth={1.8} />
                  </div>
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--chrome)] font-bold font-mono">{p.n} · {p.title}</p>
                </div>
                <h3 className="akki-serif text-[20px] text-[var(--ink)] font-normal leading-snug mb-3">{p.headline}</h3>
                <p className="text-[14px] text-[var(--deep)] leading-[1.65] mb-4">{p.detail}</p>
                <div className="border-t border-[var(--rule)] pt-3 mt-4">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--muted)] mb-1">How you verify</p>
                  <p className="text-[12.5px] text-[var(--deep)] italic leading-relaxed">{p.proof}</p>
                </div>
              </div>
            );
          })}
        </div>

        <h2 className="akki-serif text-[28px] font-normal text-[var(--ink)] mt-20 mb-8">Posture details we'd flag if you asked us in person</h2>
        <div className="space-y-6 max-w-3xl">
          {POSTURE_ITEMS.map(([h, b], i) => (
            <div key={i} className="border-l-2 border-[var(--accent)]/40 pl-5">
              <p className="akki-serif text-[16.5px] text-[var(--ink)] mb-1.5 font-medium">{h}</p>
              <p className="text-[13.5px] text-[var(--deep)] leading-[1.7]">{b}</p>
            </div>
          ))}
        </div>

        <div className="mt-16 pt-10 border-t border-[var(--rule)] bg-[var(--cream-deep)]/40 -mx-6 lg:-mx-10 px-6 lg:px-10 py-10">
          <h3 className="akki-serif text-[24px] text-[var(--ink)] font-normal mb-4 max-w-2xl">Concerns we haven't addressed yet?</h3>
          <p className="text-[14.5px] text-[var(--deep)] leading-relaxed max-w-2xl mb-5">
            Send them. We'd rather have a hard conversation up front than ship a posture we can't defend in front of an audit committee.
          </p>
          <a href="mailto:security@akki.ai" className="inline-flex items-center gap-2 text-[14px] text-[var(--accent)] hover:underline" data-testid="security-contact-link">
            security@akki.ai <ArrowRight className="w-4 h-4" />
          </a>
        </div>
      </section>
    </MarketingShell>
  );
}
