/**
 * WorkStudioDocumentPage — T3.3 (2026-05-25).
 *
 * Spec §4.C → W3 + G8 ratified: dedicated full-page surface for
 * Board Pack and Committee Pack artefacts. Lives at:
 *
 *   /app/work-studio/document/:aid
 *
 * Reuses the existing DocumentOverlay component (Chunk 8 read-only
 * consumer of work_studio_exports rows) as a full-bleed page. The
 * close affordance navigates back to the Work Studio listing.
 *
 * G8 ratification: this page is the canonical surface for Board
 * Packs and Committee Packs ONLY. Minutes / Decks / Reports open
 * the same component as a side drawer overlay from WorkStudio.jsx.
 *
 * AppShell + Gated context wrappers ride at the route level in App.js,
 * not inside this page, so the surface is consistent with sibling
 * pages.
 */
import React from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import AppShell from "@/components/layout/AppShell";
import DocumentOverlay from "@/components/work_studio/overlay/DocumentOverlay";
import { ArrowLeft } from "lucide-react";

export default function WorkStudioDocumentPage() {
  const { artefactId } = useParams();
  const aid = artefactId;
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const cid = activeContext?.id;

  return (
    <AppShell>
      <div className="px-6 py-4 border-b border-[var(--rule)] bg-white flex items-center gap-3"
           data-testid="work-studio-document-page-header">
        <button
          type="button"
          onClick={() => navigate("/app/work-studio")}
          className="text-[12px] inline-flex items-center gap-1.5 text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="work-studio-document-page-back"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.7} />
          Work Studio
        </button>
        <span className="text-[var(--muted)]">/</span>
        <span className="text-[12px] text-[var(--ink)] akki-serif">Document</span>
      </div>
      {/* DocumentOverlay was originally built as a sheet overlay
          (open + onClose props). On this page it stays mounted with
          open=true; closing it routes back to the Work Studio listing. */}
      <DocumentOverlay
        open={!!aid && !!cid}
        onClose={() => navigate("/app/work-studio")}
        contextId={cid}
        artefactId={aid}
        renderMode="page"
      />
      {!aid && (
        <div className="px-6 py-12 text-center" data-testid="work-studio-document-page-missing">
          <p className="akki-serif text-[16px] text-[var(--ink)] mb-1">No document selected.</p>
          <Link
            to="/app/work-studio"
            className="text-[12.5px] text-[var(--accent)] hover:underline underline-offset-2"
          >
            ← Back to Work Studio
          </Link>
        </div>
      )}
    </AppShell>
  );
}
