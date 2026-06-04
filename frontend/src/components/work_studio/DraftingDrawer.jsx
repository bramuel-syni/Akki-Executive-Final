/**
 * DraftingDrawer — Track A Phase 5 (2026-06-04)
 *
 * W5 "Save and start drafting" landing surface + W6 Report/Deck blank
 * route target. Near-full-screen Sheet with:
 *
 *   • Editable title (click → input, Enter/blur → save)
 *   • Long-form rich-text body via tiptap, scrollable
 *   • Saving… / Saved status indicator (G6 1s debounce pattern)
 *   • Footer: [Save] (persists work_studio_exports row), [Enhance]
 *     (opens fig 60-style enhance modal targeting the new artefact)
 *
 * Idempotency (Tightening 5): a stable `draft_session_id` (uuid4) is
 * minted when the drawer opens and threaded on every POST. Backend
 * `/work-studio/documents/save-draft` collapses near-simultaneous
 * POSTs with the same id into ONE row.
 *
 * Props:
 *   - open: bool
 *   - onClose: () => void
 *   - contextId: string
 *   - kind: "report" | "deck" | "minutes" | ...   ← determines doc format
 *   - documentId?: string          ← optional source document id (W5 from /manual-create)
 *   - initialTitle?: string
 *   - initialBody?: string
 *   - onSaved?: (exportId) => void
 *   - onEnhance?: (exportId) => void  ← fires once we have an export_id
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Loader2, FileText, Sparkles, Save as SaveIcon, X } from "lucide-react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

const AUTOSAVE_DEBOUNCE_MS = 1000;

function _uuid4() {
  // Fallback for environments where crypto.randomUUID isn't present.
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export default function DraftingDrawer({
  open,
  onClose,
  contextId,
  kind = "report",
  documentId = null,
  initialTitle = "Untitled draft",
  initialBody = "",
  onSaved,
  onEnhance,
}) {
  const [title, setTitle] = useState(initialTitle);
  const [titleEditing, setTitleEditing] = useState(false);
  const [savingState, setSavingState] = useState("idle"); // "idle" | "saving" | "saved" | "error"
  const [exportId, setExportId] = useState(null);
  const draftSessionIdRef = useRef(null);
  const debounceRef = useRef(null);

  // Mint a stable draft_session_id on open (Tightening 5). Persists for
  // the lifetime of this drawer; closes-and-reopens get a fresh id.
  useEffect(() => {
    if (open) {
      draftSessionIdRef.current = _uuid4();
      setExportId(null);
      setSavingState("idle");
      setTitle(initialTitle || "Untitled draft");
    } else {
      // Closed — flush any pending debounce.
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    }
  }, [open, initialTitle]);

  const editor = useEditor(
    {
      extensions: [StarterKit],
      content: initialBody || "<p></p>",
      editable: true,
      onUpdate: ({ editor: ed }) => {
        if (!open) return;
        scheduleSave(title, ed.getHTML());
      },
    },
    [open],
  );

  // ── Save scheduling ─────────────────────────────────────────────
  const scheduleSave = (nextTitle, nextBody) => {
    if (!contextId || !draftSessionIdRef.current) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setSavingState("saving");
    debounceRef.current = setTimeout(async () => {
      await performSave(nextTitle, nextBody);
    }, AUTOSAVE_DEBOUNCE_MS);
  };

  const performSave = async (titleVal, bodyVal) => {
    if (!contextId || !draftSessionIdRef.current) return;
    try {
      const r = await api.post(
        `/contexts/${contextId}/work-studio/documents/save-draft`,
        {
          draft_session_id: draftSessionIdRef.current,
          title: titleVal,
          structured_content: { html: bodyVal, plain_text: stripHtml(bodyVal) },
          kind,
          document_id: documentId,
        },
      );
      setExportId(r.data?.export_id || null);
      setSavingState("saved");
      // Fire pulse so the cards section refetches.
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("akki:document-card-pulse"));
      }
      if (onSaved) onSaved(r.data?.export_id);
    } catch (e) {
      setSavingState("error");
      toast.error(apiErrorMessage(e));
    }
  };

  const handleSaveClick = async () => {
    // Force-flush any pending debounce.
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    await performSave(title, editor ? editor.getHTML() : "");
  };

  const handleEnhanceClick = async () => {
    // Ensure the draft is saved at least once so an export_id exists.
    if (!exportId) {
      await handleSaveClick();
    }
    if (onEnhance && exportId) onEnhance(exportId);
  };

  const handleTitleCommit = (newTitle) => {
    setTitle(newTitle);
    setTitleEditing(false);
    scheduleSave(newTitle, editor ? editor.getHTML() : "");
  };

  const savingPill = useMemo(() => {
    if (savingState === "saving") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] text-[var(--muted)] font-mono uppercase tracking-[0.12em]"
              data-testid="drafting-drawer-saving">
          <Loader2 className="h-3 w-3 animate-spin" /> Saving…
        </span>
      );
    }
    if (savingState === "saved") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-mono uppercase tracking-[0.12em]"
              data-testid="drafting-drawer-saved">
          Saved
        </span>
      );
    }
    if (savingState === "error") {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] text-red-600 font-mono uppercase tracking-[0.12em]"
              data-testid="drafting-drawer-save-error">
          Save failed
        </span>
      );
    }
    return null;
  }, [savingState]);

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose && onClose(); }}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[720px] p-0 flex flex-col"
        data-testid="drafting-drawer"
      >
        <SheetTitle className="sr-only">Drafting drawer</SheetTitle>

        {/* Header */}
        <div className="flex items-center gap-3 border-b border-[var(--rule)] px-5 py-3">
          <FileText className="h-4 w-4 text-slate-500 shrink-0" />
          {titleEditing ? (
            <input
              type="text"
              defaultValue={title}
              autoFocus
              onBlur={(e) => handleTitleCommit(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTitleCommit(e.currentTarget.value);
                if (e.key === "Escape") setTitleEditing(false);
              }}
              data-testid="drafting-drawer-title-input"
              className="flex-1 text-[14px] font-medium text-slate-900 bg-transparent outline-none border-b border-dashed border-slate-300 focus:border-slate-500"
            />
          ) : (
            <button
              type="button"
              onClick={() => setTitleEditing(true)}
              data-testid="drafting-drawer-title-button"
              className="flex-1 text-left text-[14px] font-medium text-slate-900 truncate hover:border-b hover:border-dashed hover:border-slate-300"
            >
              {title || "Untitled draft"}
            </button>
          )}
          {savingPill}
          <button
            type="button"
            onClick={onClose}
            data-testid="drafting-drawer-close"
            className="shrink-0 inline-flex items-center justify-center h-7 w-7 rounded-sm hover:bg-slate-100"
            aria-label="Close drafting drawer"
          >
            <X className="h-3.5 w-3.5 text-slate-500" />
          </button>
        </div>

        {/* Body — tiptap editor */}
        <div
          className="flex-1 overflow-y-auto px-5 py-4"
          data-testid="drafting-drawer-body"
        >
          <EditorContent
            editor={editor}
            className="prose prose-sm max-w-none focus:outline-none [&_*]:focus:outline-none min-h-[400px]"
          />
        </div>

        {/* Footer */}
        <div className="border-t border-[var(--rule)] px-5 py-3 flex items-center gap-2">
          <Button
            type="button"
            onClick={handleSaveClick}
            disabled={savingState === "saving"}
            data-testid="drafting-drawer-save"
            className="bg-slate-900 hover:bg-slate-800 text-white"
          >
            <SaveIcon className="h-3.5 w-3.5 mr-1.5" /> Save
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={handleEnhanceClick}
            data-testid="drafting-drawer-enhance"
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" /> Enhance
          </Button>
          <div className="flex-1" />
          <span className="text-[10.5px] text-[var(--muted)] font-mono uppercase tracking-[0.1em]">
            {kind === "deck" ? "PPTX format" : "DOCX format"}
          </span>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function stripHtml(html) {
  if (!html) return "";
  if (typeof document === "undefined") return html.replace(/<[^>]*>/g, "");
  const el = document.createElement("div");
  el.innerHTML = html;
  return el.textContent || el.innerText || "";
}
