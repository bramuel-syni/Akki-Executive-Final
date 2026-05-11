import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Upload, Camera, FileText, X, Loader2, Sparkles, AtSign, Link2,
  Shield, Check,
} from "lucide-react";

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

  const [file, setFile] = useState(null);
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
    const f = e.dataTransfer?.files?.[0];
    if (f) onFileSelected(f);
  }, []);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [trust, setTrust] = useState("mixed");
  const [mentionId, setMentionId] = useState("");
  const [relatedDocId, setRelatedDocId] = useState("");
  const [relationType, setRelationType] = useState("update");

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
    setFile(null); setName(""); setDescription(""); setTrust("mixed");
    setMentionId(""); setRelatedDocId(""); setRelationType("update");
    setGenerating(false); setUploading(false);
  }, [open]);

  const onFileSelected = (f) => {
    if (!f) return;
    setFile(f);
    // Seed the display name from the filename stem — user can override
    if (!name) {
      const stem = f.name.replace(/\.[^.]+$/, "").slice(0, 60);
      setName(stem);
    }
  };

  const generateMeta = async () => {
    if (!file) {
      toast.message("Pick a file first so AKKI has something to read.");
      return;
    }
    setGenerating(true);
    try {
      // For AI-generation we send the filename + a short text sample for
      // legible file types. For PDFs/images we just send the filename.
      let previewText = null;
      if (/^text\/|\.txt$|\.md$|\.csv$/i.test(file.name + " " + (file.type || ""))) {
        previewText = await file.slice(0, 4000).text().catch(() => null);
      }
      const { data } = await api.post(
        `/contexts/${contextId}/documents/generate-meta`,
        { filename: file.name, preview_text: previewText },
        { timeout: 60000 },
      );
      if (data.display_name) setName(data.display_name);
      if (data.description) setDescription(data.description);
      toast.success("AKKI named and described the document.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setGenerating(false); }
  };

  const onUpload = async () => {
    if (!file) { toast.message("Select a file first."); return; }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      if (name.trim()) form.append("display_name", name.trim());
      if (description.trim()) form.append("description", description.trim());
      form.append("data_trust", trust);
      if (mentionId) form.append("mentioned_account_ids", mentionId);
      if (relatedDocId) {
        form.append("related_doc_id", relatedDocId);
        form.append("relation_type", relationType);
      }
      // API_BASE already ends with `/api` (see frontend/src/lib/api.js:4),
      // so the path here MUST NOT re-add `/api`. Doing so produces
      // `${BACKEND_URL}/api/api/contexts/...` which is unrouted and
      // returns 404 — the symptom users hit when "the homepage upload
      // button does nothing". Audit the other API_BASE call-sites if
      // copying this pattern.
      const res = await fetch(`${API_BASE}/contexts/${contextId}/documents`, {
        method: "POST", credentials: "include", body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Upload failed (${res.status})`);
      }
      const doc = await res.json();
      toast.success(`${doc.name} added to the journal.`);
      onUploaded?.(doc);
      onClose();
    } catch (e) { toast.error(e.message || "Upload failed"); }
    finally { setUploading(false); }
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
            <label className="akki-overline block mb-2">File</label>
            {file ? (
              <div className="bg-white border border-[var(--rule)] rounded-sm p-3 flex items-center gap-3" data-testid="upload-file-selected">
                <FileText className="w-4 h-4 text-[var(--accent)] shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-[13.5px] font-medium text-[var(--ink)] truncate">{file.name}</p>
                  <p className="text-[11px] text-[var(--muted)]">{(file.size / 1024).toFixed(1)} KB · {file.type || "file"}</p>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="text-[var(--muted)] hover:text-red-600"
                  data-testid="upload-file-clear"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
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
                    Drop the file here
                  </p>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={() => fileInput.current?.click()}
                    variant="outline"
                    className="flex-1 rounded-sm h-10 border-[var(--rule)] text-[var(--deep)]"
                    data-testid="upload-pick-file-btn"
                  >
                    <Upload className="w-3.5 h-3.5 mr-2" /> Choose file or drop
                  </Button>
                  <Button
                    onClick={() => cameraInput.current?.click()}
                    variant="outline"
                    className="rounded-sm h-10 border-[var(--rule)] text-[var(--deep)]"
                    data-testid="upload-camera-btn"
                  >
                    <Camera className="w-3.5 h-3.5 mr-2" /> Camera
                  </Button>
                  <input ref={fileInput} type="file" accept={ACCEPT} className="hidden"
                    onChange={(e) => onFileSelected(e.target.files?.[0])}
                    data-testid="upload-file-input" />
                  <input ref={cameraInput} type="file" accept="image/*" capture="environment" className="hidden"
                    onChange={(e) => onFileSelected(e.target.files?.[0])}
                    data-testid="upload-modal-camera-input" />
                </div>
              </div>
            )}
          </div>

          {/* Display name */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="akki-overline">Display name</label>
              <button
                onClick={generateMeta}
                disabled={!file || generating}
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
          <p className="text-[11px] text-[var(--muted)]">
            {file ? "Ready to add to the journal." : "Pick a file to start."}
          </p>
          <div className="flex gap-2">
            <Button onClick={() => !uploading && onClose()} variant="ghost" className="rounded-sm h-9 text-[12.5px]" data-testid="upload-cancel-btn">
              Cancel
            </Button>
            <Button
              onClick={onUpload}
              disabled={!file || uploading}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-5 text-[12.5px] font-medium"
              data-testid="upload-submit-btn"
            >
              {uploading
                ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Uploading…</>
                : <>Add to journal <Upload className="w-3 h-3 ml-1.5" /></>}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
