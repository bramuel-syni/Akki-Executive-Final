import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Upload, Camera, FileText, X, Loader2, Sparkles, AtSign, Link2,
  Shield, Check, FolderOpen,
} from "lucide-react";
import { UPLOAD_CATEGORY_OPTIONS } from "@/lib/origins";

/** File types mirror the backend ACCEPT_EXT. Kept in-sync by convention.
 *  Phase H1 (2026-05-11) — added .pptx (presentations) and .doc/.ppt
 *  binary legacy forms so users can drop board decks straight in.
 *  Backend ACCEPT_EXT must mirror this list. */
const ACCEPT =
  ".pdf,.docx,.pptx,.txt,.md,.csv,.xlsx,.png,.jpg,.jpeg,.webp,.heic,.heif," +
  "application/pdf," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document," +
  "application/vnd.openxmlformats-officedocument.presentationml.presentation," +
  "text/plain,text/markdown,text/csv," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,image/*";

const TRUST_OPTS = [
  { value: "trusted", label: "Trusted", hint: "Issued by us or a regulator — no adjustment." },
  { value: "mixed",   label: "Mixed",   hint: "Standard board pack — reasonable confidence." },
  { value: "weak",    label: "Weak",    hint: "Leaked / unverified / third-party claim." },
];

const RELATION_OPTS = [
  { value: "update",             label: "Update to" },
  { value: "follow_up",          label: "Follow-up to" },
  { value: "additional_context", label: "Additional context on" },
  { value: "correction",         label: "Correction to" },
];

/**
 * Universal Document-Journal upload modal — opened from the floating + button
 * in AppShell. Collects: file (picker or camera), display name (user or AI-
 * generated), 300-char description (user or AI-generated), trust level, one
 * optional team-member tag, and an optional link to another document in the
 * same context.
 */
export default function UploadModal({ open, onClose, onUploaded }) {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  // Z-slice-5 (2026-05-27) — multi-file upload. `files` is an array;
  // legacy single-file flows (drawer link, single drop, single pick)
  // append to it. One submit pass per file; the same category +
  // metadata are applied to all. The user can re-categorize
  // individually via the doc drawer later.
  const [files, setFiles] = useState([]);
  // Phase H1 (2026-05-11) — drag-and-drop. `dragOver` flips the
  // drop-zone visual treatment; `onDragOver` MUST call
  // preventDefault so the browser allows `onDrop` to fire.
  const [dragOver, setDragOver] = useState(false);
  const onDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);
  const onDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);
  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer?.files || []);
    if (dropped.length) onFilesSelected(dropped);
  }, []);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [trust, setTrust] = useState("mixed");
  const [mentionId, setMentionId] = useState("");
  const [relatedDocId, setRelatedDocId] = useState("");
  const [relationType, setRelationType] = useState("update");
  // Z-slice-5 (2026-05-27) — category dropdown. Empty string ==
  // "Uncategorized" (backend persists as null). Defaults to the
  // empty option per spec — submitting without picking yields an
  // uncategorized document.
  const [category, setCategory] = useState("");
  // AA-slice-3 (2026-05-27) — extraction prompt checkboxes. The
  // defaults depend on the chosen category: high-signal categories
  // (board_pack / report / briefing) default ON; everything else
  // (draft / deck / minutes / uncategorized) defaults OFF. The user
  // can still override either way. `extractionTouched` records
  // whether the user has manually toggled either checkbox so we
  // stop auto-recomputing defaults the moment they take control.
  const [extractGoals, setExtractGoals] = useState(false);
  const [extractTasks, setExtractTasks] = useState(false);
  const [extractionTouched, setExtractionTouched] = useState(false);

  const [members, setMembers] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [uploading, setUploading] = useState(false);

  const fileInput = useRef(null);
  const cameraInput = useRef(null);

  // Load members + existing docs on open
  useEffect(() => {
    if (!open || !contextId) return;
    (async () => {
      try {
        const [m, d] = await Promise.all([
          api.get(`/contexts/${contextId}/members`).catch(() => ({ data: [] })),
          api.get(`/contexts/${contextId}/documents?limit=50`).catch(() => ({ data: [] })),
        ]);
        setMembers(m.data || []);
        setDocuments(d.data || []);
      } catch { /* silent */ }
    })();
  }, [open, contextId]);

  // Reset state when the modal closes
  useEffect(() => {
    if (open) return;
    setFiles([]); setName(""); setDescription(""); setTrust("mixed");
    setMentionId(""); setRelatedDocId(""); setRelationType("update");
    setCategory("");
    setExtractGoals(false); setExtractTasks(false);
    setExtractionTouched(false);
    setGenerating(false); setUploading(false);
  }, [open]);

  // AA-slice-3 (2026-05-27) — recompute extraction defaults on
  // category change UNLESS the user has manually toggled either
  // checkbox. High-signal categories (board_pack / report /
  // briefing) default both ON. Everything else (draft / deck /
  // minutes / uncategorized) defaults OFF.
  useEffect(() => {
    if (extractionTouched) return;
    const high = ["board_pack", "report", "briefing"];
    const isHigh = high.includes(category);
    setExtractGoals(isHigh);
    setExtractTasks(isHigh);
  }, [category, extractionTouched]);

  // Z-slice-5 (2026-05-27) — multi-file selection handler. Accepts
  // an array (drag-drop, multi-pick) or a single File (legacy
  // single-pick / camera). De-dupes against the existing list by
  // `name + size` so re-dropping a file doesn't duplicate it.
  const onFilesSelected = (incoming) => {
    const arr = Array.isArray(incoming) ? incoming : [incoming];
    if (!arr.length) return;
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}::${f.size}`));
      const next = [...prev];
      for (const f of arr) {
        if (!f) continue;
        const key = `${f.name}::${f.size}`;
        if (!seen.has(key)) { next.push(f); seen.add(key); }
      }
      // Seed display name from the FIRST file's stem when single-file
      // and the name field is still untouched. Multi-file leaves the
      // name input empty so each backend-side fallback fills in the
      // per-file stem.
      if (!name && next.length === 1) {
        const stem = next[0].name.replace(/\.[^.]+$/, "").slice(0, 60);
        setName(stem);
      }
      return next;
    });
  };

  // Back-compat shim for single-file call sites still in this file
  // (camera input, single-pick fallback). Wraps the multi-file
  // handler so we don't duplicate logic.
  const onFileSelected = (f) => {
    if (!f) return;
    onFilesSelected([f]);
  };

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const generateMeta = async () => {
    const first = files[0];
    if (!first) {
      toast.message("Pick a file first so AKKI has something to read.");
      return;
    }
    if (files.length > 1) {
      toast.message("Generate names per file in the doc drawer after upload.");
      return;
    }
    setGenerating(true);
    try {
      // For AI-generation we send the filename + a short text sample for
      // legible file types. For PDFs/images we just send the filename.
      let previewText = null;
      if (/^text\/|\.txt$|\.md$|\.csv$/i.test(first.name + " " + (first.type || ""))) {
        previewText = await first.slice(0, 4000).text().catch(() => null);
      }
      const { data } = await api.post(
        `/contexts/${contextId}/documents/generate-meta`,
        { filename: first.name, preview_text: previewText },
        { timeout: 60000 },
      );
      if (data.display_name) setName(data.display_name);
      if (data.description) setDescription(data.description);
      toast.success("AKKI named and described the document.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setGenerating(false); }
  };

  const onUpload = async () => {
    if (!files.length) { toast.message("Select a file first."); return; }
    setUploading(true);
    let lastDoc = null;
    let successCount = 0;
    let failCount = 0;
    // AA-slice-3 (2026-05-27) — collect uploaded doc IDs so we can
    // fire the extraction trigger sequentially after the batch.
    const uploadedIds = [];
    try {
      // Z-slice-5 (2026-05-27) — sequential per-file POSTs. Each call
      // shares the same category / trust / mention / related-doc
      // metadata. `display_name` is only attached on the FIRST file
      // (and only when the user typed one), so subsequent files keep
      // their filename stems. Errors are accumulated; a partial
      // success surfaces a "M of N succeeded" toast.
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        const form = new FormData();
        form.append("file", f);
        if (i === 0 && name.trim() && files.length === 1) {
          form.append("display_name", name.trim());
        }
        if (description.trim()) form.append("description", description.trim());
        form.append("data_trust", trust);
        // Always send the category field — empty string means
        // "Uncategorized", which the backend normalizes to None.
        form.append("category", category || "");
        if (mentionId) form.append("mentioned_account_ids", mentionId);
        if (relatedDocId && i === 0) {
          // Relation only attaches to the FIRST file; chained doc
          // threading is one-to-one by design.
          form.append("related_doc_id", relatedDocId);
          form.append("relation_type", relationType);
        }
        // P0 fix (Patch 23) — use the shared axios `api` client so the
        // request gets the `Authorization: Bearer <token>` AND
        // `X-Active-Context` headers injected by the interceptor.
        try {
          const { data: doc } = await api.post(
            `/contexts/${contextId}/documents`,
            form,
          );
          lastDoc = doc;
          successCount += 1;
          if (doc?.id) uploadedIds.push(doc.id);
        } catch (e) {
          failCount += 1;
          // Surface per-file error with filename so the user can tell
          // which one failed in a batch upload.
          toast.error(`${f.name}: ${apiErrorMessage(e)}`);
        }
      }

      // AA-slice-3 (2026-05-27) — if either extraction checkbox is
      // ticked, fire the extract trigger for each successfully
      // uploaded doc. Sequential (not parallel) to keep LLM
      // rate-limit pressure low. Each call returns 202 immediately;
      // the actual Sonnet 4.5 round-trip happens in the background.
      // Failures are logged but DO NOT block subsequent files NOR
      // surface as upload errors — the upload itself succeeded.
      if ((extractGoals || extractTasks) && uploadedIds.length > 0) {
        for (const did of uploadedIds) {
          try {
            await api.post(
              `/contexts/${contextId}/documents/${did}/extract`,
              {
                extract_goals: !!extractGoals,
                extract_tasks: !!extractTasks,
              },
            );
          } catch (e) {
            // Surface a per-file warning so the user knows the
            // extraction didn't queue — but don't tear down the
            // upload success.
            const msg = apiErrorMessage(e);
            toast.warning(`Extraction couldn't start for one file: ${msg}`);
          }
        }
        toast.message(
          uploadedIds.length === 1
            ? "AKKI is reading the document — Monitor will populate when extraction finishes."
            : `AKKI is reading ${uploadedIds.length} documents — Monitor will populate as extractions complete.`,
        );
      }

      if (successCount > 0) {
        if (files.length === 1) {
          toast.success(`${lastDoc?.name || "Document"} added to the journal.`);
        } else {
          toast.success(`${successCount} of ${files.length} documents added.`);
        }
        // Only fire the parent callback for the last successful doc
        // (the existing contract). Future enhancement could pass the
        // full list.
        if (lastDoc) onUploaded?.(lastDoc);
        // Close only when every file succeeded; otherwise stay open so
        // the user can see which ones failed and retry.
        if (failCount === 0) onClose();
      }
    } finally { setUploading(false); }
  };

  const descLen = description.length;
  const descColor = descLen > 280 ? "text-amber-600" : descLen > 300 ? "text-red-600" : "text-[var(--muted)]";

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !uploading) onClose(); }}>
      <DialogContent
        className="max-w-[640px] max-h-[90vh] overflow-hidden flex flex-col bg-[var(--cream)] border-[var(--rule)] p-0"
        data-testid="upload-modal"
      >
        <DialogTitle className="sr-only">Add to Document Journal</DialogTitle>
        <DialogDescription className="sr-only">
          Upload a file to the current context. Optionally generate a display name and description,
          set the trust level, tag a colleague and link this document to an earlier one.
        </DialogDescription>

        <div className="px-7 py-5 border-b border-[var(--rule)] bg-white flex items-start justify-between">
          <div>
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <Upload className="w-3 h-3 text-[var(--accent)]" /> Add to Document Journal
            </p>
            <h2 className="akki-serif text-[20px] font-normal text-[var(--ink)] leading-snug">
              {activeContext?.name}
            </h2>
          </div>
          <button
            onClick={() => !uploading && onClose()}
            className="p-1 text-[var(--muted)] hover:text-[var(--ink)]"
            data-testid="upload-modal-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-7 py-5 space-y-5">
          {/* File pickers */}
          <div>
            <label className="akki-overline block mb-2">
              File{files.length > 1 ? "s" : ""}
              {files.length > 0 && (
                <span className="ml-1.5 text-[10px] text-[var(--muted)] normal-case tracking-normal">
                  · {files.length} selected
                </span>
              )}
            </label>
            {files.length > 0 ? (
              <div className="space-y-2" data-testid="upload-files-selected">
                {files.map((f, idx) => (
                  <div
                    key={`${f.name}::${f.size}::${idx}`}
                    className="bg-white border border-[var(--rule)] rounded-sm p-3 flex items-center gap-3"
                    data-testid={`upload-file-row-${idx}`}
                  >
                    <FileText className="w-4 h-4 text-[var(--accent)] shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[13.5px] font-medium text-[var(--ink)] truncate">{f.name}</p>
                      <p className="text-[11px] text-[var(--muted)]">{(f.size / 1024).toFixed(1)} KB · {f.type || "file"}</p>
                    </div>
                    <button
                      onClick={() => removeFile(idx)}
                      className="text-[var(--muted)] hover:text-red-600"
                      data-testid={`upload-file-clear-${idx}`}
                      aria-label={`Remove ${f.name}`}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {/* Z-slice-5 — let the user add more files to the
                    same batch without dismissing the modal. */}
                <Button
                  onClick={() => fileInput.current?.click()}
                  variant="ghost"
                  className="rounded-sm h-8 text-[12px] text-[var(--muted)] hover:text-[var(--ink)]"
                  data-testid="upload-add-more-btn"
                >
                  <Upload className="w-3 h-3 mr-1.5" /> Add another file
                </Button>
              </div>
            ) : (
              <div
                className={`flex flex-col gap-2 rounded-sm p-1 border-2 border-dashed transition-colors ${dragOver ? "border-[var(--accent)] bg-[var(--accent)]/5" : "border-transparent"}`}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                data-testid="upload-drop-zone"
              >
                {dragOver && (
                  <p className="text-[11px] text-[var(--accent)] akki-sans text-center py-1">
                    Drop the file{files.length === 0 ? "(s)" : ""} here
                  </p>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={() => fileInput.current?.click()}
                    variant="outline"
                    className="flex-1 rounded-sm h-10 border-[var(--rule)] text-[var(--deep)]"
                    data-testid="upload-pick-file-btn"
                  >
                    <Upload className="w-3.5 h-3.5 mr-2" /> Choose files or drop
                  </Button>
                  <Button
                    onClick={() => cameraInput.current?.click()}
                    variant="outline"
                    className="rounded-sm h-10 border-[var(--rule)] text-[var(--deep)]"
                    data-testid="upload-camera-btn"
                  >
                    <Camera className="w-3.5 h-3.5 mr-2" /> Camera
                  </Button>
                </div>
              </div>
            )}
            {/* Inputs live outside the conditional so refs stay stable
                across the empty/selected transitions — clicking
                "Add another file" reuses the same input. The picker
                accepts multiple files per Z-slice-5. */}
            <input
              ref={fileInput} type="file" accept={ACCEPT} multiple className="hidden"
              onChange={(e) => {
                onFilesSelected(Array.from(e.target.files || []));
                e.target.value = "";
              }}
              data-testid="upload-file-input"
            />
            <input
              ref={cameraInput} type="file" accept="image/*" capture="environment" className="hidden"
              onChange={(e) => {
                onFileSelected(e.target.files?.[0]);
                e.target.value = "";
              }}
              data-testid="upload-modal-camera-input"
            />
          </div>

          {/* Z-slice-5 (2026-05-27) — Category dropdown. REQUIRED in the
              sense that submitting without picking yields the
              "Uncategorized" sentinel (empty string), which the
              backend normalizes to null. The 6 canonical category
              values populate the rest of the list. */}
          <div>
            <label className="akki-overline block mb-2 flex items-center gap-1.5">
              <FolderOpen className="w-3 h-3" /> Category
              <span className="text-[10px] text-[var(--muted)] normal-case tracking-normal italic">
                · pick where this lives in Work Studio
              </span>
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full text-[13px] border border-[var(--rule)] rounded-sm bg-white px-3 py-2 focus:outline-none focus:border-[var(--accent)]"
              data-testid="upload-category-select"
            >
              {UPLOAD_CATEGORY_OPTIONS.map((opt) => (
                <option
                  key={opt.value || "uncategorized"}
                  value={opt.value}
                  data-testid={`upload-category-option-${opt.value || "uncategorized"}`}
                >
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* AA-slice-3 (2026-05-27) — Extraction prompt. Two
              checkboxes the user can opt in/out of. Defaults flip
              ON for board_pack / report / briefing categories
              (high-signal governance docs); OFF for everything
              else. Once the user manually toggles either checkbox,
              the recompute-on-category-change effect stops touching
              them (extractionTouched=true). */}
          <div
            className="bg-white border border-[var(--rule)] rounded-sm p-3"
            data-testid="upload-extraction-block"
          >
            <label className="akki-overline block mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> AI extraction
            </label>
            <div className="flex flex-col gap-2">
              <label className="flex items-start gap-2.5 text-[13px] text-[var(--ink)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={extractGoals}
                  onChange={(e) => {
                    setExtractionTouched(true);
                    setExtractGoals(e.target.checked);
                  }}
                  className="mt-[3px] accent-[var(--accent)]"
                  data-testid="upload-extract-goals-checkbox"
                />
                <span>Extract goals from this document</span>
              </label>
              <label className="flex items-start gap-2.5 text-[13px] text-[var(--ink)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={extractTasks}
                  onChange={(e) => {
                    setExtractionTouched(true);
                    setExtractTasks(e.target.checked);
                  }}
                  className="mt-[3px] accent-[var(--accent)]"
                  data-testid="upload-extract-tasks-checkbox"
                />
                <span>Extract tasks/initiatives from this document</span>
              </label>
            </div>
            <p
              className="text-[11.5px] italic text-[var(--muted)] mt-2.5 leading-relaxed"
              data-testid="upload-extraction-helper"
            >
              AI will scan for strategic goals and the specific work to deliver them.
              You can review and edit later in Monitor.
            </p>
          </div>

          {/* Display name — only meaningful for single-file uploads.
              Multi-file batches use each file's own filename stem so
              the user doesn't accidentally rename five files to the
              same string. */}
          {files.length <= 1 && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="akki-overline">Display name</label>
                <button
                  onClick={generateMeta}
                  disabled={files.length === 0 || generating}
                  className="text-[11px] text-[var(--accent)] hover:underline flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                  data-testid="upload-generate-meta-btn"
                >
                  {generating
                    ? <><Loader2 className="w-3 h-3 animate-spin" /> AKKI is naming it…</>
                    : <><Sparkles className="w-3 h-3" /> Let AKKI name & describe it</>}
                </button>
              </div>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value.slice(0, 80))}
                placeholder="e.g. Q4 Audit Committee Pack · November 2025"
                className="rounded-sm h-9 text-sm border-[var(--rule)]"
                data-testid="upload-name-input"
              />
            </div>
          )}

          {/* Description */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="akki-overline">Description</label>
              <span className={`text-[10.5px] tabular-nums ${descColor}`}>{descLen} / 300</span>
            </div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value.slice(0, 300))}
              placeholder="One or two sentences on what this document is and why it's here."
              rows={3}
              className="w-full bg-white border border-[var(--rule)] rounded-sm text-[13px] p-3 resize-none focus:outline-none focus:border-[var(--accent)] akki-serif leading-relaxed"
              data-testid="upload-description-input"
            />
          </div>

          {/* Trust */}
          <div>
            <label className="akki-overline block mb-2">Level of trust</label>
            <div className="grid grid-cols-3 gap-2" data-testid="upload-trust-row">
              {TRUST_OPTS.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTrust(t.value)}
                  data-selected={trust === t.value}
                  className={`text-left bg-white border rounded-sm p-3 transition-colors ${
                    trust === t.value
                      ? "border-[var(--accent)] ring-1 ring-[var(--accent)]/30"
                      : "border-[var(--rule)] hover:border-[var(--ink)]/30"
                  }`}
                  data-testid={`upload-trust-${t.value}`}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    {trust === t.value && <Check className="w-3 h-3 text-[var(--accent)]" strokeWidth={2.2} />}
                    <span className="text-[12.5px] font-medium text-[var(--ink)]">{t.label}</span>
                  </div>
                  <p className="text-[10.5px] text-[var(--muted)] leading-snug">{t.hint}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Mention a team member */}
          {members.length > 0 && (
            <div>
              <label className="akki-overline block mb-2 flex items-center gap-1.5">
                <AtSign className="w-3 h-3" /> Tag a team member (optional)
              </label>
              <select
                value={mentionId}
                onChange={(e) => setMentionId(e.target.value)}
                className="w-full text-[13px] border border-[var(--rule)] rounded-sm bg-white px-3 py-2 focus:outline-none focus:border-[var(--accent)]"
                data-testid="upload-mention-select"
              >
                <option value="">— nobody —</option>
                {members.map((m) => (
                  <option key={m.account_id || m.id} value={m.account_id || m.id}>
                    {m.name || m.email}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Link to an earlier document */}
          {documents.length > 0 && (
            <div>
              <label className="akki-overline block mb-2 flex items-center gap-1.5">
                <Link2 className="w-3 h-3" /> Link to an earlier document (optional)
              </label>
              <div className="flex gap-2">
                <select
                  value={relationType}
                  onChange={(e) => setRelationType(e.target.value)}
                  disabled={!relatedDocId}
                  className="text-[12.5px] border border-[var(--rule)] rounded-sm bg-white px-2 py-2 focus:outline-none focus:border-[var(--accent)] disabled:opacity-50"
                  data-testid="upload-relation-type"
                >
                  {RELATION_OPTS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
                <select
                  value={relatedDocId}
                  onChange={(e) => setRelatedDocId(e.target.value)}
                  className="flex-1 text-[12.5px] border border-[var(--rule)] rounded-sm bg-white px-2 py-2 focus:outline-none focus:border-[var(--accent)]"
                  data-testid="upload-related-select"
                >
                  <option value="">— standalone document —</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>
              <p className="text-[10.5px] text-[var(--muted)] mt-1.5 italic">
                Linked docs form a thread. AKKI will flag inconsistencies across the thread when it reasons on them.
              </p>
            </div>
          )}

          {/* Synisense badge — honest about what happens on upload */}
          <div className="bg-[var(--accent-soft)]/60 border border-[var(--accent)]/25 rounded-sm p-3 flex items-start gap-2">
            <Shield className="w-4 h-4 text-[var(--accent)] mt-0.5 shrink-0" strokeWidth={1.8} />
            <div className="text-[11.5px] text-[var(--deep)] leading-relaxed">
              <span className="font-medium text-[var(--ink)]">Shielded on upload.</span> Every time AKKI reads this document, Synisense first masks emails, phone numbers, national IDs, account numbers and personal names before anything reaches an LLM. You can <span className="text-[var(--accent)]">verify exactly what's masked</span> in Settings → Security.
            </div>
          </div>
        </div>

        <div className="px-7 py-4 border-t border-[var(--rule)] bg-white flex items-center justify-between gap-3">
          <p className="text-[11px] text-[var(--muted)]" data-testid="upload-ready-state">
            {files.length === 0
              ? "Pick a file to start."
              : files.length === 1
                ? "Ready to add to the journal."
                : `Ready to add ${files.length} files to the journal.`}
          </p>
          <div className="flex gap-2">
            <Button onClick={() => !uploading && onClose()} variant="ghost" className="rounded-sm h-9 text-[12.5px]" data-testid="upload-cancel-btn">
              Cancel
            </Button>
            <Button
              onClick={onUpload}
              disabled={files.length === 0 || uploading}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-5 text-[12.5px] font-medium"
              data-testid="upload-submit-btn"
            >
              {uploading
                ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Uploading…</>
                : <>{files.length > 1 ? `Add ${files.length} to journal` : "Add to journal"} <Upload className="w-3 h-3 ml-1.5" /></>}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
