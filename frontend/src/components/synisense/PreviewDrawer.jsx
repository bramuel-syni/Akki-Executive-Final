/**
 * Synisense — first-save Preview Drawer.
 *
 * Phase 12.2 ITEM C. Opens once on the first non-empty save of a
 * Studio artefact (briefing / deck / report) and, again, exactly
 * once whenever a *new* entity type is detected since the user's
 * last accept. Subsequent saves are silent.
 *
 * The component renders the ORIGINAL artefact text with the spans
 * Synisense flagged highlighted via `<mark>`; the proposed
 * replacement token appears as a superscript. A sidebar legend
 * shows the entity-type histogram. Two actions: "Accept & save"
 * (persists the redacted version + first-accept timestamp via
 * `POST /api/studio/{kind}/{artefactId}/synisense-accept`) and
 * "Cancel" (closes the drawer without persisting the accept).
 *
 * Honest contract:
 *   - Original text comes from the parent (the editor source of truth).
 *   - Spans come from the save response (`synisense.spans`).
 *   - Replacement tokens are visible inline; this is intended.
 *   - The shield_map itself NEVER comes through this component —
 *     the drawer never makes a server call for cleartext.
 */
import React, { useMemo } from "react";
import { ShieldCheck, X, FileLock2 } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

const BACKEND_URL =
  import.meta?.env?.REACT_APP_BACKEND_URL ||
  process.env.REACT_APP_BACKEND_URL ||
  "";

/**
 * Render the original text with `<mark>` highlights at every span
 * boundary. Outside-of-span text is rendered as plain children to
 * preserve whitespace and line breaks.
 */
function renderHighlighted(originalText, spans) {
  if (!originalText) return null;
  const sorted = (spans || []).slice().sort((a, b) => a.start - b.start);
  const out = [];
  let cursor = 0;
  sorted.forEach((s, i) => {
    if (s.start > cursor) {
      out.push(
        <span key={`pre-${i}`}>{originalText.slice(cursor, s.start)}</span>
      );
    }
    out.push(
      <mark
        key={`mark-${i}`}
        className="bg-amber-100 text-[var(--ink)] border-b border-amber-400 px-0.5"
        title={`${s.entity_type} · source: ${s.source} · ${s.replacement}`}
        data-testid="syn-preview-mark"
      >
        {originalText.slice(s.start, s.end)}
        <sup className="ml-0.5 font-mono text-[9px] text-amber-900 px-1 py-px rounded-sm bg-amber-200/70">
          {s.replacement}
        </sup>
      </mark>
    );
    cursor = s.end;
  });
  if (cursor < originalText.length) {
    out.push(<span key="tail">{originalText.slice(cursor)}</span>);
  }
  return out;
}

export default function PreviewDrawer({
  open,
  kind,
  artefactId,
  originalText,
  spans = [],
  stats = {},
  hasNewSensitiveContent = false,
  onAccepted,
  onCancel,
}) {
  const histogram = useMemo(() => {
    const h = {};
    for (const s of spans || []) {
      const t = s.entity_type || "UNKNOWN";
      h[t] = (h[t] || 0) + 1;
    }
    return Object.entries(h).sort((a, b) => b[1] - a[1]);
  }, [spans]);

  const handleAccept = async () => {
    try {
      const r = await fetch(
        `${BACKEND_URL}/api/studio/${kind}/${artefactId}/synisense-accept`,
        { method: "POST", credentials: "include" }
      );
      if (!r.ok) throw new Error(`accept HTTP ${r.status}`);
      const body = await r.json().catch(() => ({}));
      onAccepted && onAccepted(body);
    } catch (e) {
      // Bubble up so the parent can surface a toast; we don't dismiss
      // the drawer on error so the user can retry.
      console.error("Synisense accept failed:", e);
      alert(
        "Could not record your acceptance. The redacted version is " +
          "still saved; please retry."
      );
    }
  };

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onCancel && onCancel()}>
      <SheetContent
        side="right"
        className="w-[680px] max-w-[95vw] sm:max-w-[680px] bg-[var(--cream)] border-l border-[var(--rule)] overflow-y-auto"
        data-testid="syn-preview-drawer"
      >
        <SheetHeader>
          <SheetTitle className="akki-serif text-[20px] font-normal flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-[var(--accent)]" />
            Content screening preview
          </SheetTitle>
          <p className="text-[12px] text-[var(--muted)] mt-1">
            {hasNewSensitiveContent
              ? "New sensitive content detected since your last accept. Review the highlights below before saving."
              : "First-time save — review what AKKI proposes to redact before sending downstream. Subsequent saves are silent unless new sensitive content appears."}
          </p>
        </SheetHeader>

        <div className="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_180px] gap-5">
          <article
            className="akki-serif text-[14px] leading-[1.65] text-[var(--ink)] whitespace-pre-wrap bg-white border border-[var(--rule)] rounded-sm p-4"
            data-testid="syn-preview-body"
          >
            {renderHighlighted(originalText, spans)}
          </article>

          <aside className="text-[12px] text-[var(--ink)]">
            <p className="akki-overline text-[10px] tracking-[0.18em] text-[var(--muted)] mb-2">
              ENTITY TYPES
            </p>
            <ul className="space-y-1.5 mb-5" data-testid="syn-preview-legend">
              {histogram.length === 0 ? (
                <li className="italic text-[var(--muted)]">
                  Nothing flagged. Saving this artefact silently.
                </li>
              ) : (
                histogram.map(([t, n]) => (
                  <li
                    key={t}
                    className="flex items-center justify-between gap-2 border-b border-[var(--rule)] pb-1"
                  >
                    <span className="font-mono text-[11px]">{t}</span>
                    <span className="font-mono tabular-nums text-[11px] text-[var(--muted)]">
                      {n}
                    </span>
                  </li>
                ))
              )}
            </ul>

            <p className="akki-overline text-[10px] tracking-[0.18em] text-[var(--muted)] mb-2">
              PIPELINE
            </p>
            <p className="text-[11px] italic text-[var(--muted)] mb-3">
              Regex {stats?.regex_hits ?? 0} · Presidio {stats?.presidio_hits ?? 0}{" "}
              · LLM {stats?.llm_calls ?? 0} ({stats?.llm_skipped_cap || 0} skipped)
            </p>
            <p className="text-[11px] text-[var(--muted)]">
              Latency: <span className="font-mono">{stats?.elapsed_ms ?? 0}ms</span>
            </p>
          </aside>
        </div>

        <div className="mt-6 flex items-center justify-end gap-3 border-t border-[var(--rule)] pt-4">
          <Button
            variant="ghost"
            onClick={onCancel}
            data-testid="syn-preview-cancel"
            className="text-[var(--muted)] hover:text-[var(--ink)]"
          >
            <X className="w-4 h-4 mr-1.5" /> Cancel
          </Button>
          <Button
            onClick={handleAccept}
            data-testid="syn-preview-accept"
            className="bg-[var(--accent)] text-white hover:bg-[var(--accent)]/90"
          >
            <FileLock2 className="w-4 h-4 mr-1.5" /> Accept &amp; save
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
