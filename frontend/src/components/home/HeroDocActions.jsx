/**
 * HeroDocActions — compact button pair anchored in the Home hero band.
 *
 * Replaces the previous full-width "Add a document" Quick Action card +
 * the bigger "All documents" link. Renders two adjacent buttons:
 *
 *   [ + Add document ]   [ All documents · N → ]
 *
 * Primary (ink-on-parchment / oxblood) on the left, outline secondary
 * on the right. Hug-content widths.
 *
 * + Add document  → opens the Universal Uploader (same target as the
 *                   previous AddDocumentCard).
 * All documents   → routes to /app/workspace, the canonical Document
 *                   Journal listing per spec §4.A → D2 (D2 ratified
 *                   24 May 2026). Previously routed to /app/work-studio
 *                   (Work Studio listing), which is a different surface.
 */
import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Plus, FolderOpen, ArrowRight } from "lucide-react";


function bumpUploader() {
  try { window.dispatchEvent(new CustomEvent("akki:open-upload-modal")); }
  catch (e) { /* SSR/no-window — silent */ }
}


export default function HeroDocActions() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  // The documents endpoint does not expose a fast total-count today
  // (it returns the items it has). Per spec, we never invent counts —
  // render the button without a numeric badge for now. If a count
  // endpoint surfaces in the future, wire it here. `cid` is referenced
  // so the eslint-react-hooks dep-array stays honest.
  const _cid = cid;  // eslint-disable-line no-unused-vars

  return (
    <div
      className="flex flex-wrap items-center gap-2 mb-8"
      data-testid="home-hero-doc-actions"
    >
      <button
        type="button"
        onClick={bumpUploader}
        data-testid="home-hero-add-document"
        className="
          inline-flex items-center gap-1.5
          px-3.5 py-2 rounded-sm text-[13px] font-medium
          bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)]
          text-white transition-colors
          focus:outline-none focus:ring-2 focus:ring-[color:var(--oxblood)] focus:ring-offset-1
        "
      >
        <Plus className="w-3.5 h-3.5" strokeWidth={2} />
        Add document
      </button>

      <Link
        to="/app/workspace"
        data-testid="home-hero-all-documents"
        className="
          inline-flex items-center gap-1.5
          px-3.5 py-2 rounded-sm text-[13px]
          border border-[var(--rule)] bg-white text-[var(--ink)]
          hover:border-[color:var(--oxblood)] hover:bg-[var(--parchment)]
          transition-colors
          focus:outline-none focus:ring-2 focus:ring-[color:var(--oxblood)] focus:ring-offset-1
          no-underline
        "
      >
        <FolderOpen className="w-3.5 h-3.5 text-[color:var(--oxblood)]" strokeWidth={1.7} />
        <span>All documents</span>
        <ArrowRight className="w-3 h-3 text-[var(--muted)] ml-0.5" strokeWidth={1.7} />
      </Link>
    </div>
  );
}
