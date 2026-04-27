/**
 * ContinueWithPill — top-bar pill that takes the user back to the last
 * document they used in QuickResults.
 *
 * Tier-B (Apr-2026): the executive uploads a doc, gets a Quick-Results
 * read, then wanders into Cycle / Monitor / Prepare to keep working. The
 * pill is the persistent thread back to that document so they don't
 * lose the context of "I was reading X".
 *
 * Storage shape: localStorage key `akki_continue_with` =
 *   { context_id, doc_id, doc_name, viewed_at }
 *
 * Hidden on:
 *  - the QuickResults page itself (would be redundant)
 *  - the Document Journal (the doc is already there)
 *  - when the pill is older than 7 days (stale = forget about it)
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { FileText, X, ArrowRight } from "lucide-react";

const STORAGE_KEY = "akki_continue_with";
const STALE_AFTER_MS = 7 * 24 * 60 * 60 * 1000;

export function recordContinueWith({ contextId, docId, docName }) {
  if (!contextId || !docId) return;
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        context_id: contextId,
        doc_id: docId,
        doc_name: docName || "your document",
        viewed_at: Date.now(),
      })
    );
    window.dispatchEvent(new Event("akki-continue-with-changed"));
  } catch {
    /* localStorage disabled — silently no-op */
  }
}

function readContinueWith() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.context_id || !parsed?.doc_id) return null;
    if (Date.now() - (parsed.viewed_at || 0) > STALE_AFTER_MS) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function clearContinueWith() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new Event("akki-continue-with-changed"));
  } catch {
    /* no-op */
  }
}

export default function ContinueWithPill() {
  const [pill, setPill] = useState(() => readContinueWith());
  const navigate = useNavigate();
  const location = useLocation();

  const refresh = useCallback(() => setPill(readContinueWith()), []);
  useEffect(() => {
    window.addEventListener("akki-continue-with-changed", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("akki-continue-with-changed", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [refresh]);

  if (!pill) return null;

  // Hidden on surfaces where the pill would be redundant.
  const path = location.pathname;
  if (
    path.startsWith("/app/quick-results") ||
    path.startsWith("/app/workspace")
  ) {
    return null;
  }

  const open = () => {
    navigate(`/app/quick-results/${pill.context_id}/${pill.doc_id}`);
  };

  const dismiss = (e) => {
    e.stopPropagation();
    clearContinueWith();
  };

  const truncated =
    pill.doc_name.length > 28 ? `${pill.doc_name.slice(0, 26)}…` : pill.doc_name;

  return (
    <button
      onClick={open}
      className="hidden lg:inline-flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-full text-[12.5px] bg-[var(--cream-deep)] hover:bg-[var(--accent)]/10 border border-[var(--rule)] hover:border-[var(--accent)] text-[var(--ink)] transition-colors max-w-[320px]"
      data-testid="continue-with-pill"
      title={`Continue reading ${pill.doc_name}`}
    >
      <FileText className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" strokeWidth={1.8} />
      <span className="text-[var(--muted)] text-[10.5px] uppercase tracking-wider shrink-0">
        Continue with
      </span>
      <span className="akki-serif italic truncate">{truncated}</span>
      <ArrowRight className="w-3 h-3 text-[var(--muted)] shrink-0" />
      <span
        role="button"
        tabIndex={0}
        onClick={dismiss}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && dismiss(e)}
        className="ml-1 p-0.5 rounded-full hover:bg-[var(--rule)] text-[var(--muted)] hover:text-[var(--ink)]"
        aria-label="Dismiss"
        data-testid="continue-with-pill-dismiss"
      >
        <X className="w-3 h-3" strokeWidth={2} />
      </span>
    </button>
  );
}
