/**
 * AddDocumentCard — Phase M.1 Quick Action card on Home.
 *
 * Renders a single editorial card titled "Add a document". Clicking the card
 * dispatches the global `akki:open-upload-modal` event which AppShell
 * listens for and uses to open the shared UploadModal. Both the topbar
 * "+" icon and these home cards funnel through the same modal — there is
 * intentionally no second instance of the modal rendered here.
 */
import React from "react";
import { Plus, ArrowRight } from "lucide-react";

export default function AddDocumentCard({ className = "" }) {
  const onClick = () => {
    window.dispatchEvent(new CustomEvent("akki:open-upload-modal"));
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <button
      type="button"
      onClick={onClick}
      onKeyDown={onKeyDown}
      data-testid="home-add-document-card"
      aria-label="Add a document"
      className={`group block w-full text-left p-5 border border-[var(--accent)]/35 bg-[var(--accent)]/[0.04] hover:bg-[var(--accent)]/[0.08] hover:border-[var(--accent)]/60 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 ${className}`}
    >
      <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-1.5">
        <Plus className="w-3 h-3" strokeWidth={2.4} /> Quick action
      </p>
      <p className="akki-serif text-[18px] text-[var(--ink)] mb-1 leading-snug">
        Add a document
      </p>
      <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-3">
        Drop in a board pack, a memo, or a paper. Akki reads it.
      </p>
      <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">
        Open the uploader
        <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
      </span>
    </button>
  );
}
