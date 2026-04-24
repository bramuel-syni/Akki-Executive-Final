import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import AskPanel from "@/components/ask/AskPanel";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  Upload, FileText, Trash2, Download, ShieldCheck, AlertTriangle,
  CheckCircle2, Loader2, ArrowLeft, List, GripVertical, Camera,
} from "lucide-react";

const TRUST_STYLE = {
  trusted: { label: "Trusted", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  mixed:   { label: "Mixed",   cls: "bg-amber-50 text-amber-700 border-amber-200" },
  weak:    { label: "Weak",    cls: "bg-red-50 text-red-700 border-red-200" },
};
const STATUS_STYLE = {
  extracted: { label: "Extracted", cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2 },
  empty:     { label: "Empty",     cls: "bg-slate-100 text-slate-500 border-slate-200", icon: FileText },
  failed:    { label: "Failed",    cls: "bg-red-50 text-red-700 border-red-200", icon: AlertTriangle },
  uploaded:  { label: "Uploaded",  cls: "bg-slate-100 text-slate-600 border-slate-200", icon: FileText },
};
const ACCEPT = ".pdf,.docx,.txt,.md,.rtf";

function formatSize(b) {
  if (b == null) return "—";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}
function formatDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
}

function parseOutline(text) {
  if (!text) return [];
  const lines = text.split(/\n/);
  const items = [];
  let buf = [];
  const flushPara = () => {
    const joined = buf.join(" ").trim();
    if (joined) items.push({ type: "p", text: joined });
    buf = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const line = (lines[i] || "").trim();
    if (!line) { flushPara(); continue; }
    const next = (lines[i + 1] || "").trim();
    const isShort = line.length <= 80 && line.length > 2;
    const isUpper = line === line.toUpperCase() && /[A-Z]/.test(line);
    const startsNumbered = /^(\d+(\.\d+)*)\s+\S/.test(line);
    const nextLonger = next && next.length > 80;
    if (isShort && (isUpper || startsNumbered || nextLonger)) {
      flushPara();
      items.push({ type: "h", text: line, id: `h-${items.length}` });
    } else {
      buf.push(line);
    }
  }
  flushPara();
  return items;
}

function TrustChip({ trust, onChange, disabled }) {
  const cfg = TRUST_STYLE[trust] || TRUST_STYLE.mixed;
  if (disabled || !onChange) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${cfg.cls}`}>
        <ShieldCheck className="w-3 h-3" /> {cfg.label}
      </span>
    );
  }
  return (
    <Select value={trust} onValueChange={onChange}>
      <SelectTrigger className={`h-6 w-auto rounded-sm text-[10px] uppercase tracking-wider font-medium border px-2 gap-1 ${cfg.cls}`}>
        <ShieldCheck className="w-3 h-3" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="rounded-sm">
        <SelectItem value="trusted">Trusted</SelectItem>
        <SelectItem value="mixed">Mixed</SelectItem>
        <SelectItem value="weak">Weak</SelectItem>
      </SelectContent>
    </Select>
  );
}

function StatusChip({ status }) {
  const cfg = STATUS_STYLE[status] || STATUS_STYLE.uploaded;
  const I = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${cfg.cls}`}>
      <I className="w-3 h-3" /> {cfg.label}
    </span>
  );
}

/** Left pane when no document is selected: upload + list. */
function DocumentsBrowser({
  docs, loading, uploading, dragging, setDragging, queued, onFiles,
  displayName, setDisplayName, trust, setTrust, fileInput, cameraInput,
  onSelect, onArchive, onTrustChange, accountEmail, isAdmin,
}) {
  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-6 py-5 border-b border-[#E1E6ED] bg-white">
        <p className="akki-overline mb-1.5">Workspace · Module M3</p>
        <h1 className="text-2xl font-light tracking-tight text-[var(--ink)]">Documents</h1>
        <p className="text-xs text-slate-500 mt-1">
          Upload board packs, minutes, reports. AKKI extracts text, shields identifiers, and grounds every Ask response.
        </p>
      </div>

      {/* Dropzone */}
      <div
        className={`mx-6 mt-5 border-2 border-dashed rounded-sm transition-colors ${dragging ? "border-[var(--accent)] bg-amber-50/50" : "border-[#E1E6ED] bg-white"}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (e.dataTransfer?.files) onFiles(e.dataTransfer.files); }}
        data-testid="upload-dropzone"
      >
        <div className="p-5 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-end">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[var(--ink)]/5 border border-[var(--ink)]/10 flex items-center justify-center rounded-sm shrink-0">
              <Upload className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.6} />
            </div>
            <div>
              <p className="text-[var(--ink)] font-medium text-sm mb-0.5">Drop files to upload</p>
              <p className="text-[11px] text-slate-500">PDF · DOCX · TXT · MD · RTF · up to 25MB</p>
            </div>
          </div>
          <div className="flex items-end gap-2 flex-wrap">
            <div className="space-y-1">
              <Label className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Display name</Label>
              <Input
                value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                placeholder="optional"
                className="rounded-sm h-8 w-44 text-xs"
                data-testid="upload-display-name"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Trust</Label>
              <Select value={trust} onValueChange={setTrust}>
                <SelectTrigger className="rounded-sm h-8 w-28 text-xs" data-testid="upload-trust-select"><SelectValue /></SelectTrigger>
                <SelectContent className="rounded-sm">
                  <SelectItem value="trusted">Trusted</SelectItem>
                  <SelectItem value="mixed">Mixed</SelectItem>
                  <SelectItem value="weak">Weak</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => fileInput.current?.click()} disabled={uploading}
              className="bg-[var(--ink)] hover:bg-[#0E2958] rounded-sm h-8 text-xs"
              data-testid="upload-choose-btn"
            >
              {uploading ? "Uploading…" : "Choose files"}
            </Button>
            <Button
              onClick={() => cameraInput.current?.click()} disabled={uploading}
              variant="outline"
              className="rounded-sm h-8 text-xs border-[#E1E6ED]"
              data-testid="upload-camera-btn"
              title="Capture a document page with your device camera"
            >
              <Camera className="w-3.5 h-3.5 mr-1" /> Camera
            </Button>
            <input
              ref={fileInput} type="file" multiple accept={ACCEPT}
              className="hidden"
              onChange={(e) => onFiles(e.target.files)}
              data-testid="upload-file-input"
            />
            <input
              ref={cameraInput} type="file" accept="image/*" capture="environment"
              className="hidden"
              onChange={(e) => onFiles(e.target.files)}
              data-testid="upload-camera-input"
            />
          </div>
        </div>
        {queued.length > 0 && (
          <div className="border-t border-[#E1E6ED] px-5 py-3 space-y-1.5">
            {queued.map((q, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px]">
                {q.error ? <AlertTriangle className="w-3.5 h-3.5 text-red-500" /> :
                  q.progress === 100 ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> :
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--accent)]" />}
                <span className="text-slate-700 truncate">{q.name}</span>
                {q.error && <span className="text-red-600 ml-auto">{q.error}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Doc list */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {loading ? (
          <div className="p-10 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
        ) : docs.length === 0 ? (
          <div className="p-12 text-center bg-white border border-[#E1E6ED] rounded-sm" data-testid="docs-empty-state">
            <FileText className="w-8 h-8 text-slate-300 mx-auto mb-3" strokeWidth={1.3} />
            <p className="text-sm text-slate-500 mb-1">No documents yet</p>
            <p className="text-[11px] text-slate-400">Upload your first board pack or report to give AKKI something to work with.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {docs.map((d) => {
              const canDelete = d.uploaded_by_email === accountEmail || isAdmin;
              return (
                <div
                  key={d.id}
                  className="group bg-white border border-[#E1E6ED] rounded-sm p-3 hover:border-[var(--accent)]/50 hover:bg-slate-50/40 transition-colors flex items-center gap-3"
                  data-testid={`doc-row-${d.id}`}
                >
                  <div
                    onClick={() => onSelect(d.id)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(d.id); } }}
                    role="button"
                    tabIndex={0}
                    className="flex-1 min-w-0 text-left cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm"
                    data-testid={`doc-open-${d.id}`}
                  >
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <p className="text-sm font-medium text-[var(--ink)] group-hover:text-[var(--accent)] transition-colors truncate max-w-[40ch]">
                        {d.name}
                      </p>
                      <StatusChip status={d.status} />
                      <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                        <TrustChip trust={d.data_trust} onChange={(v) => onTrustChange(d, v)} disabled={!canDelete} />
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 font-mono truncate">{d.original_filename}</p>
                    {d.preview && <p className="text-[11px] text-slate-500 mt-1 line-clamp-1">{d.preview}</p>}
                    <div className="flex items-center gap-3 text-[10px] text-slate-400 mt-1.5">
                      <span>{formatSize(d.size_bytes)}</span>
                      <span>·</span>
                      <span>{formatDate(d.created_at)}</span>
                      <span>·</span>
                      <span>{d.uploaded_by_email}</span>
                    </div>
                  </div>
                  <a
                    href={`${API_BASE}/contexts/${d.context_id}/documents/${d.id}/download`}
                    target="_blank" rel="noreferrer"
                    className="text-slate-400 hover:text-[var(--ink)] shrink-0"
                    data-testid={`doc-download-${d.id}`}
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                  {canDelete && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <button className="text-slate-400 hover:text-red-600 shrink-0" data-testid={`doc-archive-${d.id}`} title="Archive">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </AlertDialogTrigger>
                      <AlertDialogContent className="rounded-sm">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Archive {d.name}?</AlertDialogTitle>
                          <AlertDialogDescription>
                            The document will be removed from this context and its source file deleted. Audit log is preserved.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
                          <AlertDialogAction className="bg-red-600 hover:bg-red-700 rounded-sm" onClick={() => onArchive(d)} data-testid={`doc-confirm-archive-${d.id}`}>
                            Archive
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/** Left pane when a document is selected: viewer with outline. */
function DocumentPane({ contextId, docId, onBack, onArchive, accountEmail, isAdmin, scrollTargetRef }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const bodyRef = useRef(null);

  useEffect(() => {
    setLoading(true); setDoc(null);
    api.get(`/contexts/${contextId}/documents/${docId}`)
      .then(({ data }) => setDoc(data))
      .catch((e) => toast.error(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [contextId, docId]);

  const items = useMemo(() => parseOutline(doc?.extracted_text), [doc]);
  const headings = items.filter((x) => x.type === "h");

  // Expose scroll target to parent (for citation click → scroll)
  useEffect(() => {
    if (scrollTargetRef) scrollTargetRef.current = bodyRef.current;
  }, [scrollTargetRef, loading]);

  const scrollTo = (id) => {
    const el = bodyRef.current?.querySelector(`[data-outline-id="${id}"]`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const canDelete = doc && (doc.uploaded_by_email === accountEmail || isAdmin);

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-6 py-4 border-b border-[#E1E6ED] bg-white flex items-center gap-3">
        <Button
          variant="ghost" size="sm"
          onClick={onBack}
          className="rounded-sm h-8 px-2 text-slate-600 hover:text-[var(--ink)] shrink-0"
          data-testid="doc-back-btn"
        >
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Documents
        </Button>
        <div className="flex-1 min-w-0">
          {loading ? (
            <p className="text-xs text-slate-500 flex items-center gap-2">
              <Loader2 className="w-3 h-3 animate-spin" /> Loading…
            </p>
          ) : doc ? (
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-medium tracking-tight text-[var(--ink)] truncate max-w-[40ch]" data-testid="doc-title">
                {doc.name}
              </h2>
              <StatusChip status={doc.status} />
              <TrustChip trust={doc.data_trust} />
              <span className="text-[10px] text-slate-400">{(doc.extracted_chars || 0).toLocaleString()} chars</span>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Document not found</p>
          )}
        </div>
        {doc && (
          <>
            <a
              href={`${API_BASE}/contexts/${contextId}/documents/${doc.id}/download`}
              target="_blank" rel="noreferrer"
              className="text-slate-500 hover:text-[var(--ink)] shrink-0"
              data-testid="doc-download-btn"
              title="Download original"
            >
              <Download className="w-4 h-4" />
            </a>
            {canDelete && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <button className="text-slate-500 hover:text-red-600 shrink-0" title="Archive" data-testid="doc-archive-btn">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </AlertDialogTrigger>
                <AlertDialogContent className="rounded-sm">
                  <AlertDialogHeader>
                    <AlertDialogTitle>Archive {doc.name}?</AlertDialogTitle>
                    <AlertDialogDescription>
                      The document will be removed from this context and its source file deleted.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
                    <AlertDialogAction className="bg-red-600 hover:bg-red-700 rounded-sm" onClick={() => onArchive(doc)}>
                      Archive
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </>
        )}
      </div>

      <div className="flex-1 min-h-0 grid grid-cols-[1fr_220px]">
        <div ref={bodyRef} className="overflow-y-auto bg-white px-8 py-8" data-testid="doc-body">
          {loading ? null : !doc ? null : doc.error ? (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-sm p-4 max-w-2xl mx-auto">
              <strong>Extraction failed:</strong> {doc.error}
            </div>
          ) : !doc.extracted_text ? (
            <p className="text-sm text-slate-400 italic text-center py-16">No extracted text available.</p>
          ) : (
            <article className="max-w-2xl mx-auto">
              {items.map((it, i) =>
                it.type === "h" ? (
                  <h3 key={i} data-outline-id={it.id} className="text-base font-medium text-[var(--ink)] tracking-tight mt-6 mb-2 scroll-mt-4">
                    {it.text}
                  </h3>
                ) : (
                  <p key={i} className="text-[14px] leading-[1.7] text-slate-700 mb-3.5 whitespace-pre-wrap">
                    {it.text}
                  </p>
                )
              )}
            </article>
          )}
        </div>
        <aside className="hidden md:block border-l border-[#E1E6ED] bg-slate-50/40 overflow-y-auto" data-testid="doc-outline-rail">
          <div className="px-3 py-3 sticky top-0 bg-slate-50/90 backdrop-blur-sm border-b border-[#E1E6ED]">
            <div className="flex items-center gap-1.5">
              <List className="w-3 h-3 text-[var(--accent)]" />
              <p className="text-[9px] uppercase tracking-[0.2em] text-slate-500 font-semibold">Outline</p>
            </div>
          </div>
          <div className="p-1.5">
            {headings.length === 0 ? (
              <p className="text-[10px] text-slate-400 px-2 py-3">No headings detected.</p>
            ) : (
              headings.map((h) => (
                <button
                  key={h.id}
                  onClick={() => scrollTo(h.id)}
                  className="w-full text-left px-2 py-1.5 text-[11px] text-slate-600 hover:bg-white hover:text-[var(--ink)] rounded-sm transition-colors border-l-2 border-transparent hover:border-[var(--accent)]"
                  data-testid={`outline-${h.id}`}
                >
                  <span className="line-clamp-2">{h.text}</span>
                </button>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function Workspace() {
  const { account, activeContext } = useAuth();
  const contextId = activeContext?.id;
  const accountEmail = account?.email;
  const isAdmin = activeContext?.my_sub_role === "admin";

  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [trust, setTrust] = useState("mixed");
  const [queued, setQueued] = useState([]);
  const fileInput = useRef(null);
  const cameraInput = useRef(null);

  const [selectedDocId, setSelectedDocId] = useState(null);

  // 60/40 split with persistent Ask panel. Divider is draggable.
  const [leftPct, setLeftPct] = useState(60);
  const splitRef = useRef(null);
  const draggingRef = useRef(false);
  const onMouseDown = (e) => {
    e.preventDefault();
    draggingRef.current = true;
  };
  useEffect(() => {
    const move = (e) => {
      if (!draggingRef.current || !splitRef.current) return;
      const rect = splitRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      const clamped = Math.max(35, Math.min(75, pct));
      setLeftPct(clamped);
    };
    const up = () => { draggingRef.current = false; };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
  }, []);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents`);
      setDocs(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  const uploadOne = async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    if (displayName) fd.append("display_name", displayName);
    fd.append("data_trust", trust);
    const res = await fetch(`${API_BASE}/contexts/${contextId}/documents`, {
      method: "POST", body: fd, credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed (${res.status})`);
    }
    return await res.json();
  };

  const onFiles = async (files) => {
    const list = Array.from(files || []);
    if (!list.length) return;
    setUploading(true);
    setQueued(list.map((f) => ({ name: f.name, progress: 0, error: null })));
    for (let i = 0; i < list.length; i++) {
      try {
        await uploadOne(list[i]);
        setQueued((q) => q.map((x, idx) => idx === i ? { ...x, progress: 100 } : x));
      } catch (err) {
        setQueued((q) => q.map((x, idx) => idx === i ? { ...x, error: err.message } : x));
        toast.error(`${list[i].name}: ${err.message}`);
      }
    }
    setUploading(false);
    setDisplayName("");
    await load();
    setTimeout(() => setQueued([]), 2500);
  };

  const onArchive = async (doc) => {
    try {
      await api.delete(`/contexts/${contextId}/documents/${doc.id}`);
      toast.success(`${doc.name} archived`);
      if (selectedDocId === doc.id) setSelectedDocId(null);
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onTrustChange = async (doc, newTrust) => {
    try {
      const { data } = await api.patch(`/contexts/${contextId}/documents/${doc.id}`, { data_trust: newTrust });
      setDocs((prev) => prev.map((d) => d.id === doc.id ? { ...d, data_trust: data.data_trust } : d));
      toast.success("Trust updated");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  // Clicking a [doc:xxx] chip in Ask panel → load the document on the left
  const onCitationClick = (docId) => {
    const exists = docs.some((d) => d.id === docId);
    if (exists) setSelectedDocId(docId);
    else toast.message("That document is no longer in this context.");
  };

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  const askHeader = (
    <div className="border-b border-[#E1E6ED] bg-white px-4 py-3">
      <p className="akki-overline mb-0.5">Ask · persistent</p>
      <h2 className="text-sm font-medium text-[var(--ink)]">Grounded in your workspace</h2>
      <p className="text-[11px] text-slate-500 mt-0.5">
        Click any <span className="font-mono">[doc:…]</span> citation to open the document on the left.
      </p>
    </div>
  );

  return (
    <AppShell>
      <div
        ref={splitRef}
        className="h-[calc(100vh-4rem)] flex bg-[#FAFBFC] relative"
        data-testid="workspace-split"
      >
        {/* Left pane */}
        <div className="border-r border-[#E1E6ED] bg-white overflow-hidden" style={{ width: `${leftPct}%` }}>
          {selectedDocId ? (
            <DocumentPane
              contextId={contextId}
              docId={selectedDocId}
              onBack={() => setSelectedDocId(null)}
              onArchive={onArchive}
              accountEmail={accountEmail}
              isAdmin={isAdmin}
            />
          ) : (
            <DocumentsBrowser
              docs={docs} loading={loading} uploading={uploading}
              dragging={dragging} setDragging={setDragging}
              queued={queued} onFiles={onFiles}
              displayName={displayName} setDisplayName={setDisplayName}
              trust={trust} setTrust={setTrust}
              fileInput={fileInput}
              cameraInput={cameraInput}
              onSelect={setSelectedDocId}
              onArchive={onArchive}
              onTrustChange={onTrustChange}
              accountEmail={accountEmail}
              isAdmin={isAdmin}
            />
          )}
        </div>

        {/* Draggable divider */}
        <div
          onMouseDown={onMouseDown}
          className="w-1.5 cursor-col-resize bg-[#E1E6ED] hover:bg-[var(--accent)] transition-colors relative group shrink-0"
          data-testid="workspace-divider"
          title="Drag to resize"
        >
          <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
            <GripVertical className="w-3 h-3 text-white" />
          </div>
        </div>

        {/* Right pane: persistent Ask */}
        <div className="flex-1 bg-[#FAFBFC] overflow-hidden" data-testid="workspace-ask-pane">
          <AskPanel
            contextId={contextId}
            accountName={account?.name}
            onCitationClick={onCitationClick}
            dense
            header={askHeader}
          />
        </div>
      </div>
    </AppShell>
  );
}
