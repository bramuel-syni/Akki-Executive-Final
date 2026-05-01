/**
 * §2 “60-second proof” — three stylised mock blocks (intake → workspace →
 * signal with citation). Stills, not a loop. Stack on mobile.
 *
 * Replaces the prior inline FirstRunDemo component which shipped a single
 * animated CSS keyframe loop. Per the homepage rules, these are 3 distinct
 * frames so a reader can absorb each in turn.
 */
import React from "react";
import { FileText, Loader2, AlertTriangle } from "lucide-react";

function Frame({ label, children }) {
  return (
    <div className="flex flex-col">
      <p className="akki-overline mb-3 text-[var(--muted)]">{label}</p>
      <div className="bg-white border border-[var(--rule)] rounded-sm p-5 md:p-6 flex-1">
        {children}
      </div>
    </div>
  );
}

function IntakeRow({ label, value }) {
  return (
    <div className="border-b border-[var(--rule)] py-2 last:border-b-0">
      <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1">{label}</p>
      <p className="text-[13px] text-[var(--ink)]/40 font-mono">{value}</p>
    </div>
  );
}

function DocRow({ name }) {
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      <FileText className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" strokeWidth={1.6} />
      <span className="text-[12px] font-mono text-[var(--deep)] truncate">{name}</span>
    </div>
  );
}

export default function SixtySecondProof() {
  return (
    <section
      className="border-b border-[var(--rule)] bg-[var(--cream)]"
      data-testid="sixty-second-proof"
    >
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-16 md:py-24">
        <p className="akki-overline mb-3">What 60 seconds looks like</p>
        <h2 className="akki-serif text-[28px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-3 max-w-[24ch]">
          A minute with a real pack
        </h2>
        <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] max-w-[60ch] mb-12">
          Four questions. Sixty seconds. Every claim cites the paragraph.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Frame 1 — Intake */}
          <Frame label="01 · Intake">
            <div data-testid="proof-frame-intake">
              <IntakeRow label="Company name" value="——————————" />
              <IntakeRow label="Sector" value="————————" />
              <IntakeRow label="Your role" value="——————" />
              <IntakeRow label="What's on your mind" value="————————————" />
            </div>
          </Frame>

          {/* Frame 2 — Workspace */}
          <Frame label="02 · Workspace">
            <div className="flex gap-4 h-full" data-testid="proof-frame-workspace">
              <div className="w-[40%] border-r border-[var(--rule)] pr-3 space-y-1">
                <p className="akki-overline text-[9px] mb-2">Documents</p>
                <DocRow name="Q4_Audit_Pack.pdf" />
                <DocRow name="Risk_Register_Nov.pdf" />
                <DocRow name="Minutes_Oct_29.docx" />
              </div>
              <div className="flex-1 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-[11.5px] text-[var(--muted)] italic mb-3">
                  <Loader2 className="w-3 h-3 text-[var(--accent)]" strokeWidth={1.8} />
                  <span>AKKI is reading…</span>
                </div>
                <div className="h-[2px] bg-[var(--cream-deep)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--accent)]" style={{ width: "68%" }} />
                </div>
                <p className="text-[10.5px] text-[var(--muted)] mt-2 font-mono">28 / 42 pages</p>
              </div>
            </div>
          </Frame>

          {/* Frame 3 — Signal with citation */}
          <Frame label="03 · Signal">
            <div
              className="border-l-2 border-red-300/70 bg-red-50/60 rounded-sm p-4 h-full flex flex-col"
              data-testid="proof-frame-signal"
            >
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-3.5 h-3.5 text-red-700" strokeWidth={1.8} />
                <span className="text-[10.5px] uppercase tracking-[0.16em] text-red-800 font-medium">
                  Risk
                </span>
              </div>
              <p className="text-[14px] leading-[1.5] text-red-950 mb-4">
                ERP migration 90% complete for six months — schedule risk on Q1 close.
              </p>
              <div className="mt-auto pt-3 border-t border-red-200/60">
                <p className="text-[11px] text-red-900/80 italic mb-2 leading-relaxed">
                  Evidence: “the rollout has been at 90% completion since May…”
                </p>
                <span
                  className="inline-block text-[10.5px] font-mono px-2 py-0.5 rounded-sm bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/25"
                  data-testid="proof-citation"
                >
                  [doc:Q4_Audit_Pack.pdf · p.14]
                </span>
              </div>
            </div>
          </Frame>
        </div>
      </div>
    </section>
  );
}
