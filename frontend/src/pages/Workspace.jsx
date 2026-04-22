import React, { useCallback, useEffect, useRef, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  Upload, FileText, Trash2, Download, ShieldCheck, AlertTriangle,
  Eye, FileQuestion, CheckCircle2, Loader2, X,
} from "lucide-react";

const TRUST_CONFIG = {
  trusted: { label: "Trusted", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  mixed: { label: "Mixed", cls: "bg-amber-50 text-amber-700 border-amber-200" },
  weak: { label: "Weak", cls: "bg-red-50 text-red-700 border-red-200" },
};
const STATUS_CONFIG = {
  extracted: { label: "Extracted", cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2 },
  empty: { label: "Empty", cls: "bg-slate-100 text-slate-500 border-slate-200", icon: FileQuestion },
  failed: { label: "Failed", cls: "bg-red-50 text-red-700 border-red-200", icon: AlertTriangle },
  uploaded: { label: "Uploaded", cls: "bg-slate-100 text-slate-600 border-slate-200", icon: FileText },
  processing: { label: "Processing", cls: "bg-blue-50 text-blue-700 border-blue-200", icon: Loader2 },
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

function TrustChip({ trust, onChange, disabled }) {
  const cfg = TRUST_CONFIG[trust] || TRUST_CONFIG.mixed;
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
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.uploaded;
  const I = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${cfg.cls}`}>
      <I className={`w-3 h-3 ${status === "processing" ? "animate-spin" : ""}`} /> {cfg.label}
    </span>
  );
}

export default function Workspace() {
  const { account, activeContext } = useAuth();
  const contextId = activeContext?.id;
  const isAdmin = activeContext?.my_sub_role === "admin";

  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [trust, setTrust] = useState("mixed");
  const [queued, setQueued] = useState([]); // [{name, progress, error}]
  const fileInput = useRef(null);

  const [detailDoc, setDetailDoc] = useState(null); // {id,...} for drawer
  const [detailLoading, setDetailLoading] = useState(false);

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
    try {
      const res = await fetch(`${API_BASE}/contexts/${contextId}/documents`, {
        method: "POST", body: fd, credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Upload failed (${res.status})`);
      }
      return await res.json();
    } catch (e) { throw e; }
  };

  const onFiles = async (files) => {
    const list = Array.from(files || []);
    if (!list.length) return;
    setUploading(true);
    const nextQueued = list.map((f) => ({ name: f.name, progress: 0, error: null }));
    setQueued(nextQueued);
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

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false);
    if (e.dataTransfer?.files) onFiles(e.dataTransfer.files);
  };

  const onArchive = async (doc) => {
    try {
      await api.delete(`/contexts/${contextId}/documents/${doc.id}`);
      toast.success(`${doc.name} archived`);
      await load();
      if (detailDoc?.id === doc.id) setDetailDoc(null);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onTrustChange = async (doc, newTrust) => {
    try {
      const { data } = await api.patch(`/contexts/${contextId}/documents/${doc.id}`, { data_trust: newTrust });
      setDocs((prev) => prev.map((d) => d.id === doc.id ? { ...d, data_trust: data.data_trust } : d));
      toast.success("Trust updated");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const openDetail = async (doc) => {
    setDetailLoading(true);
    setDetailDoc({ ...doc, extracted_text: "" });
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents/${doc.id}`);
      setDetailDoc(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setDetailLoading(false); }
  };

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="mb-8">
          <p className="akki-overline mb-2">Workspace · Module M3</p>
          <h1 className="text-3xl font-light tracking-tight text-[#0A1F44]">Documents</h1>
          <p className="text-sm text-slate-500 mt-2">
            Upload board packs, minutes, reports. AKKI extracts text, applies Synisense shielding, and uses them to ground every downstream response.
          </p>
        </div>

        {/* Uploader */}
        <div
          className={`relative mb-6 border-2 border-dashed rounded-sm transition-colors ${dragging ? "border-[#C9A961] bg-amber-50/50" : "border-[#E1E6ED] bg-white"}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          data-testid="upload-dropzone"
        >
          <div className="p-8 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-center">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-[#0A1F44]/5 border border-[#0A1F44]/10 flex items-center justify-center rounded-sm">
                <Upload className="w-5 h-5 text-[#C9A961]" strokeWidth={1.6} />
              </div>
              <div>
                <p className="text-[#0A1F44] font-medium text-sm mb-1">Drop files to upload</p>
                <p className="text-xs text-slate-500">
                  PDF, DOCX, TXT, MD, RTF · up to 25MB · files are context-isolated and virus-scanned
                </p>
              </div>
            </div>
            <div className="flex items-end gap-3">
              <div className="space-y-1.5">
                <Label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Display name (optional)</Label>
                <Input
                  value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Overrides the filename"
                  className="rounded-sm h-9 w-52"
                  data-testid="upload-display-name"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Data trust</Label>
                <Select value={trust} onValueChange={setTrust}>
                  <SelectTrigger className="rounded-sm h-9 w-36" data-testid="upload-trust-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="rounded-sm">
                    <SelectItem value="trusted">Trusted</SelectItem>
                    <SelectItem value="mixed">Mixed</SelectItem>
                    <SelectItem value="weak">Weak</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={() => fileInput.current?.click()} disabled={uploading}
                className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-9"
                data-testid="upload-choose-btn"
              >
                {uploading ? "Uploading…" : "Choose files"}
              </Button>
              <input
                ref={fileInput} type="file" multiple accept={ACCEPT}
                className="hidden"
                onChange={(e) => onFiles(e.target.files)}
                data-testid="upload-file-input"
              />
            </div>
          </div>
          {queued.length > 0 && (
            <div className="border-t border-[#E1E6ED] px-8 py-4 space-y-2">
              {queued.map((q, i) => (
                <div key={i} className="flex items-center gap-3 text-xs">
                  {q.error ? <AlertTriangle className="w-4 h-4 text-red-500" /> :
                    q.progress === 100 ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> :
                    <Loader2 className="w-4 h-4 animate-spin text-[#C9A961]" />}
                  <span className="text-slate-700">{q.name}</span>
                  {q.error && <span className="text-red-600 ml-auto">{q.error}</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Document list */}
        <div className="bg-white border border-[#E1E6ED] rounded-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-[#E1E6ED] flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-[#0A1F44]">
                Documents <span className="text-slate-400 font-normal">({docs.length})</span>
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Everything uploaded here is context-isolated and shielded before reaching any LLM.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="p-12 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
          ) : docs.length === 0 ? (
            <div className="p-16 text-center" data-testid="docs-empty-state">
              <FileText className="w-10 h-10 text-slate-300 mx-auto mb-4" strokeWidth={1.3} />
              <p className="text-sm text-slate-500 mb-1">No documents yet</p>
              <p className="text-xs text-slate-400">Upload your first board pack or report to give AKKI something to work with.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-50 border-b border-[#E1E6ED]">
                    <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Document</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Status</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Trust</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Size</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Uploaded</th>
                    <th className="text-right px-6 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500"></th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => {
                    const canDelete = d.uploaded_by_email === account?.email || isAdmin;
                    return (
                      <tr key={d.id} className="border-b border-[#E1E6ED] hover:bg-slate-50/50" data-testid={`doc-row-${d.id}`}>
                        <td className="px-6 py-3">
                          <button onClick={() => openDetail(d)} className="text-left group" data-testid={`doc-open-${d.id}`}>
                            <p className="text-sm font-medium text-[#0A1F44] group-hover:text-[#C9A961] transition-colors">{d.name}</p>
                            <p className="text-[10px] text-slate-400 mt-0.5 font-mono">{d.original_filename}</p>
                            {d.preview && <p className="text-xs text-slate-500 mt-1 max-w-md line-clamp-1">{d.preview}</p>}
                          </button>
                        </td>
                        <td className="px-6 py-3"><StatusChip status={d.status} /></td>
                        <td className="px-6 py-3">
                          <TrustChip trust={d.data_trust} onChange={(v) => onTrustChange(d, v)} disabled={!canDelete} />
                        </td>
                        <td className="px-6 py-3 text-xs text-slate-500">{formatSize(d.size_bytes)}</td>
                        <td className="px-6 py-3 text-xs text-slate-500">
                          <p>{formatDate(d.created_at)}</p>
                          <p className="text-[10px] text-slate-400">{d.uploaded_by_email}</p>
                        </td>
                        <td className="px-6 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="sm" className="h-8 px-2 rounded-sm text-slate-500 hover:text-[#0A1F44]" onClick={() => openDetail(d)} data-testid={`doc-view-${d.id}`}>
                              <Eye className="w-4 h-4" />
                            </Button>
                            <a
                              href={`${API_BASE}/contexts/${contextId}/documents/${d.id}/download`}
                              target="_blank" rel="noreferrer"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-sm text-slate-500 hover:text-[#0A1F44] hover:bg-slate-100"
                              data-testid={`doc-download-${d.id}`}
                            >
                              <Download className="w-4 h-4" />
                            </a>
                            {canDelete && (
                              <AlertDialog>
                                <AlertDialogTrigger asChild>
                                  <Button variant="ghost" size="sm" className="h-8 px-2 rounded-sm text-red-600 hover:bg-red-50 hover:text-red-700" data-testid={`doc-archive-${d.id}`}>
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
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
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Preview drawer */}
        <Dialog open={!!detailDoc} onOpenChange={(v) => !v && setDetailDoc(null)}>
          <DialogContent className="rounded-sm sm:max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle className="font-light tracking-tight text-xl text-[#0A1F44] flex items-center gap-3">
                {detailDoc?.name}
                {detailDoc && <StatusChip status={detailDoc.status} />}
                {detailDoc && <TrustChip trust={detailDoc.data_trust} />}
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500 font-mono">
                {detailDoc?.original_filename} · {formatSize(detailDoc?.size_bytes)} · {detailDoc?.extracted_chars?.toLocaleString()} chars extracted
              </DialogDescription>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto mt-4 border border-[#E1E6ED] rounded-sm p-5 bg-slate-50/50">
              {detailLoading ? (
                <p className="text-xs uppercase tracking-widest text-slate-400 text-center py-10">Loading…</p>
              ) : detailDoc?.error ? (
                <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-sm p-3">
                  <strong>Extraction failed:</strong> {detailDoc.error}
                </div>
              ) : !detailDoc?.extracted_text ? (
                <p className="text-sm text-slate-400 italic text-center py-10">No extracted text available.</p>
              ) : (
                <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed">{detailDoc.extracted_text}</pre>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  );
}
