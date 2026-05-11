/**
 * StudioComposerPage — Phase 8 / Advisory 9.
 *
 * Wraps `BlockComposer` in the standard editorial chrome (AppShell).
 * URL: /app/studio/composer/:kind/:artefactId
 *   kind ∈ { briefing, deck, report }
 *
 * Decks render in slide mode (BlockComposer handles the slide tray
 * internally based on Heading 1 boundaries). Briefings carry the soft
 * 2-page visual guide, Reports are unconstrained.
 */
import React from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import AppShell from "@/components/layout/AppShell";
import BlockComposer from "@/components/studio/BlockComposer";

const KIND_LABEL = {
  briefing: "Briefing",
  deck:     "Deck",
  report:   "Report",
};

export default function StudioComposerPage() {
  const { kind, artefactId } = useParams();
  const navigate = useNavigate();

  if (!["briefing", "deck", "report"].includes(kind)) {
    return (
      <AppShell>
        <div className="akki-w-narrow p-6">
          <p className="text-[#8B2E2B] text-sm">Unknown artefact kind: <code>{kind}</code></p>
        </div>
      </AppShell>
    );
  }

  const isDeck = kind === "deck";
  const isBriefing = kind === "briefing";

  return (
    <AppShell>
      {/* Phase H — composer is a two-column workspace surface; uses
          the medium width token regardless of artefact kind. */}
      <div className="akki-w-medium px-4 lg:px-8 py-6">
        {/* Editorial header. No marketing fluff. No emojis. */}
        <div className="flex items-center gap-2 mb-4">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1 text-[11px] uppercase tracking-[0.14em] text-[#7C6A4F] hover:text-[#0F1419]"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back
          </button>
          <span className="text-[11px] uppercase tracking-[0.16em] text-[#7C6A4F]">·</span>
          <span className="text-[11px] uppercase tracking-[0.16em] text-[#0F1419]">
            Work Studio composer · {KIND_LABEL[kind]}
          </span>
        </div>

        {isBriefing && (
          <p className="text-[11.5px] text-[#7C6A4F] italic mb-3 max-w-prose" style={{ fontFamily: "Georgia, serif" }}>
            Briefings sit best around two printed pages. The soft guide is editorial, not enforced — long briefings still ship.
          </p>
        )}

        <BlockComposer kind={kind} artefactId={artefactId} />
      </div>
    </AppShell>
  );
}
