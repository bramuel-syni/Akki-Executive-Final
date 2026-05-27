import React from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { ShieldCheck, Lock, Eye, FileCheck, ArrowRight } from "lucide-react";

const PROMISES = [
  {
    n: "01", icon: Lock, title: "Your data stays yours",
    headline: "AKKI cannot train on your board pack. Period.",
    detail: "Your documents and signals never join a public training set. We use a private LLM gateway with a private contract — no logging of your content, no model fine-tuning, no \"you sent it to us, you said we could.\" Every read and write is scoped to the company you're working in. Cross-company leakage isn't a setting; it's a query-time impossibility.",
    proof: "Audit log: every read and write, with actor and timestamp. Export it any time.",
  },
  {
    n: "02", icon: ShieldCheck, title: "Identities are scrubbed",
    headline: "The model never sees your CEO's name. Or yours.",
    detail: "Before any prompt leaves the AKKI backend, the in-house Synisense engine walks the text through a regex fast-path (emails, phone numbers, IBAN, card numbers, SSNs, NHS numbers, IPs, URLs, dates, and board codenames like \"Project Falcon\"), then a Presidio NER pass on a locally-loaded spaCy model with custom recognisers for executive titles, chair names, and financial figures, then — for the narrow band of spans the first two layers can't classify confidently — a capped, timeout-bounded Gemini 2.5 Flash classifier. The model reasons over masked text. The mapping back to the originals is encrypted at rest (AES-GCM, per-record data key, key version pinned) and never leaves the backend. If the LLM provider is breached tomorrow, the breach isn't yours.",
    proof: "Settings → Trust panel logs every run: span count, entity types, engine version. The shielding sits across six surfaces today (chat, document ingest, briefings, decks, reports, Solva synthesis). Any document shared externally is refused with HTTP 410 until it has passed through the engine.",
  },
  {
    n: "03", icon: FileCheck, title: "Receipts on every claim",
    headline: "Every number cites the page it came from.",
    detail: "Signals, briefings, lens runs and Ask answers all carry [doc:xxx] citations inline. Click any citation, the source opens at the exact section. Nothing AKKI tells you is unsourceable. That alone disqualifies the \"AI hallucination\" defence in a board meeting.",
    proof: "Export the briefing PDF — the citations travel with it. Ready for the audit committee.",
  },
  {
    n: "04", icon: Eye, title: "Leave clean, any time",
    headline: "One button deletes everything.",
    detail: "Settings → Danger zone gives you JSON export of your whole company workspace — documents, signals, reports, audit log — and a hard delete. No retention bargains. No support ticket required. The Sandbox auto-deletes on day 22 with no human in the loop.",
    proof: "No \"call sales to delete\" flow. The button does what it says.",
  },
];

const POSTURE_ITEMS = [
  ["We don't email your team without you reading the email first.", "Every cycle email is reviewed and approved by you. The sender header reads 'AKKI for [your name]' so your reportees know it's authorised. Replies go to your real inbox."],
  ["MFA, lockouts, and bcrypt — the boring stuff done right.", "Custom JWT with bcrypt-hashed passwords. Brute-force lockout per-account. Optional TOTP MFA. Cookies are httpOnly and samesite=none. No \"reset by SMS\" social-engineering surface."],
  ["What you turn on costs money. What's off doesn't.", "Stripe billing, vector DBs, virus scanners — every paid integration stays mocked until you explicitly opt in. You'll never see a charge for something you didn't ask for."],
  ["The data residency answer your CISO wants.", "Database in Atlas, region of your choice. Backups encrypted at rest. We're happy to share architecture docs and run a security review with your team before you onboard real boards."],
];

export default function Security() {
  return (
    <MarketingShell>
      <section className="max-w-[1100px] mx-auto px-6 lg:px-10 py-20" data-testid="security-page">
        <p className="akki-overline mb-3 text-[var(--accent)]">Security · Why you can trust this</p>
        <h1 className="akki-serif text-[44px] sm:text-[52px] leading-[1.1] tracking-tight text-[var(--ink)] mb-6 font-normal max-w-3xl">
          Four things you should be able to verify yourself.
        </h1>
        <p className="akki-serif text-[18px] leading-relaxed text-[var(--deep)] mb-12 italic max-w-2xl">
          You ask your CFO for receipts. You ask your auditor for working papers. Ask the same of the tool that prepares you for the boardroom.
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
                <h2 className="akki-serif text-[20px] text-[var(--ink)] font-normal leading-snug mb-3">{p.headline}</h2>
                <p className="text-[14px] text-[var(--deep)] leading-[1.65] mb-4">{p.detail}</p>
                <div className="border-t border-[var(--rule)] pt-3 mt-4">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--muted)] mb-1">How you verify</p>
                  <p className="text-[12.5px] text-[var(--deep)] italic leading-relaxed">{p.proof}</p>
                </div>
              </div>
            );
          })}
        </div>

        <h2 className="akki-serif text-[28px] font-normal text-[var(--ink)] mt-20 mb-8" id="security-followups">If you asked me face-to-face, here's what else I'd tell you</h2>
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
