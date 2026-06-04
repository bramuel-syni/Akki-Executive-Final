/**
 * ExportModal — Phase C.2 wiring for the three Export buttons on
 * Work Studio. The user fills Description / Objective / Scope and
 * picks an output format; the modal POSTs to the export endpoint and
 * polls the status endpoint until complete or failed. On `complete`
 * a Download button calls the per-export download endpoint.
 *
 * Restraint copy throughout — no banned words from MEMO Item 8 or
 * WEBSITE_BRIEF_V3 §1.3.
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { Loader2, Download, AlertCircle, FileDown, MessageSquare } from "lucide-react";
import SourceStep from "./SourceStep";
import StreamingLogScene from "@/components/transitions/StreamingLogScene";
import useStreamingProgress from "@/hooks/useStreamingProgress";

const FORMAT_OPTIONS = {
  brief:  [["docx", "DOCX"], ["pdf", "PDF"], ["auto", "Auto"]],
  deck:   [["pptx", "PPTX"], ["pdf", "PDF"], ["auto", "Auto"]],   // PDF soft-forks to PPTX server-side
  report: [["docx", "DOCX"], ["pdf", "PDF"], ["auto", "Auto"]],
};

const KIND_LABEL = {
  brief: "Brief",
  deck: "Summary Deck",
  report: "Report",
};

export default function ExportModal({ open, onClose, kind, contextId, contextName }) {
  const navigate = useNavigate();
  const [sourceChoice, setSourceChoice] = useState("system");
  const [description, setDescription] = useState("");
  const [objective, setObjective] = useState("");
  const [scope, setScope] = useState("");
  const [outputFormat, setOutputFormat] = useState("auto");

  const [phase, setPhase] = useState("compose"); // compose | running | complete | failed
  const [exportId, setExportId] = useState(null);
  const [status, setStatus] = useState(null);
  const [errMsg, setErrMsg] = useState(null);
  const [refusalText, setRefusalText] = useState(null);
  const [downloadToken, setDownloadToken] = useState(null);
  const [fileName, setFileName] = useState(null);
  const [continueChatId, setContinueChatId] = useState(null);
  const [continueDocId, setContinueDocId] = useState(null);
  // Phase C.3 — when the source step's "Generate document now" returns,
  // we display the C.1 result inside this modal alongside the legacy
  // download-token path. C.1 returns a direct download_url; we reuse
  // the existing complete-phase UI without the token roundtrip.
  const [c1DirectDownload, setC1DirectDownload] = useState(null); // {url, filename}

  const pollRef = useRef(null);
  const startedAtRef = useRef(null);

  // Phase L.a (2026-05-27) — SSE observer stream against the export row.
  // Drives the `running` branch's StreamingLogScene; the legacy polling
  // path remains as a fallback if the stream errors out.
  const { state: streamState, stream, reset: resetStream } = useStreamingProgress();

  // Reset on open/close.
  useEffect(() => {
    if (open) {
      setSourceChoice("system");
      setDescription("");
      setObjective("");
      setScope("");
      setOutputFormat("auto");
      setPhase("compose");
      setExportId(null);
      setStatus(null);
      setErrMsg(null);
      setRefusalText(null);
      setDownloadToken(null);
      setFileName(null);
      setContinueChatId(null);
      setContinueDocId(null);
      setC1DirectDownload(null);
      resetStream();
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [open]);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!description.trim() || !objective.trim() || !scope.trim()) return;
    setPhase("running");
    setErrMsg(null);
    setRefusalText(null);
    startedAtRef.current = Date.now();
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/work-studio/export/${kind}`,
        {
          description: description.trim(),
          objective: objective.trim(),
          scope: scope.trim(),
          output_format: outputFormat,
        },
      );
      setExportId(data.export_id);
      setStatus(data);
      // Phase L.a (2026-05-27) — open the SSE observer stream.
      // Background worker writes phase markers; the observer translates
      // them into SSE events. The legacy polling loop still runs in
      // parallel as a defence-in-depth fallback.
      stream(
        `${API_BASE}/contexts/${contextId}/work-studio/exports/${data.export_id}/stream`,
        { method: "GET" },
      ).catch(() => { /* state.status flips */ });
      // Begin polling.
      pollRef.current = setInterval(async () => {
        try {
          const r = await api.get(
            `/contexts/${contextId}/work-studio/exports/${data.export_id}`,
          );
          setStatus(r.data);
          if (r.data.status === "complete") {
            setDownloadToken(r.data.download_token);
            setFileName(r.data.file_name);
            setContinueChatId(r.data.continue_chat_id || null);
            setContinueDocId(r.data.continue_doc_id || null);
            setPhase("complete");
            clearInterval(pollRef.current); pollRef.current = null;
          } else if (r.data.status === "failed") {
            setErrMsg(r.data.error || "Render failed.");
            setRefusalText(r.data.refusal_text || null);
            setPhase("failed");
            clearInterval(pollRef.current); pollRef.current = null;
          }
        } catch (pe) {
          setErrMsg(apiErrorMessage(pe));
          setPhase("failed");
          clearInterval(pollRef.current); pollRef.current = null;
        }
      }, 2500);
    } catch (e2) {
      setErrMsg(apiErrorMessage(e2));
      setPhase("failed");
    }
  };

  const onDownload = async () => {
    // Phase C.3 — when the source step's "Generate document now" path
    // populated `c1DirectDownload`, fetch via the C.1 endpoint (no token
    // parameter — that auth model is for the legacy Phase 13 path).
    if (c1DirectDownload?.url) {
      try {
        const path = c1DirectDownload.url.replace(/^\/api/, "");
        const resp = await api.get(path, { responseType: "blob" });
        const blob = new Blob([resp.data], { type: resp.headers?.["content-type"] || "application/octet-stream" });
        const a = document.createElement("a");
        a.href = window.URL.createObjectURL(blob);
        a.download = c1DirectDownload.filename || fileName || "akki-export.bin";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(a.href);
      } catch (e) {
        setErrMsg(apiErrorMessage(e));
      }
      return;
    }
    if (!exportId || !downloadToken) return;
    try {
      // Fetch with auth and trigger browser download (legacy Phase 13 path).
      const resp = await api.get(`/contexts/${contextId}/work-studio/exports/${exportId}/download`, {
        params: { token: downloadToken },
        responseType: "blob",
      });
      const blob = new Blob([resp.data], { type: resp.headers?.["content-type"] || "application/octet-stream" });
      const a = document.createElement("a");
      a.href = window.URL.createObjectURL(blob);
      a.download = fileName || `akki-export-${exportId}.bin`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(a.href);
    } catch (e) {
      setErrMsg(apiErrorMessage(e));
    }
  };

  const onContinueChat = () => {
    if (!continueChatId) return;
    const params = new URLSearchParams();
    params.set("chat_id", continueChatId);
    if (continueDocId) params.set("attach", continueDocId);
    navigate(`/app/chat?${params.toString()}`);
    onClose();
  };

  const elapsedSec = phase === "running" && startedAtRef.current
    ? Math.floor((Date.now() - startedAtRef.current) / 1000)
    : null;

  const formatChoices = FORMAT_OPTIONS[kind] || FORMAT_OPTIONS.brief;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent
        className="max-w-5xl max-h-[88vh] overflow-y-auto"
        data-testid="work-studio-export-modal"
      >
        <DialogHeader>
          <DialogTitle className="akki-serif text-[var(--ink)]">
            Export a {KIND_LABEL[kind] || "Brief"}
          </DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Pick where the source comes from. Akki composes from system info by default; you can also seed from a Solva session or a chat artefact.
          </DialogDescription>
        </DialogHeader>

        {phase === "compose" && (
          <div className="space-y-3" data-testid="work-studio-export-compose">
            <SourceStep
              contextId={contextId}
              contextName={contextName}
              kind={kind === "brief" ? "briefing" : kind}
              sourceChoice={sourceChoice}
              onSourceChange={setSourceChoice}
              onSeeded={(seed) => {
                // Open in composer — close modal and navigate.
                onClose?.();
                navigate(seed.redirect_url);
              }}
              onGenerated={(g) => {
                // Generate document now — surface the C.1 download
                // through the existing complete-phase chrome.
                setC1DirectDownload({ url: g.download_url, filename: g.filename });
                setFileName(g.filename);
                setStatus({ sensitivity_band: null });
                setPhase("complete");
              }}
            />
            {sourceChoice === "system" && (
              <form onSubmit={onSubmit} className="space-y-3 pt-2 border-t border-[var(--rule)]" data-testid="work-studio-export-form">
            {/* Phase F.3 — 3-column grid for the three "what" fields so
                the Compose CTA stays on-fold at 1024×768 (the legacy
                vertical stack pushed it below the viewport). Output
                format spans full width below. */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
              <Label className="text-[12px]" htmlFor="ws-export-desc">Description</Label>
              <Input
                id="ws-export-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What this is — e.g. Summary of Q1 risk posture"
                className="rounded-sm"
                required
                data-testid="work-studio-export-description"
              />
            </div>
            <div>
              <Label className="text-[12px]" htmlFor="ws-export-obj">Objective</Label>
              <Input
                id="ws-export-obj"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder="What you want the reader to do — e.g. Brief the audit committee"
                className="rounded-sm"
                required
                data-testid="work-studio-export-objective"
              />
            </div>
            <div>
              <Label className="text-[12px]" htmlFor="ws-export-scope">Scope</Label>
              <Input
                id="ws-export-scope"
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                placeholder="What to cover — e.g. All Q1 risk submissions and the ExCo decisions"
                className="rounded-sm"
                required
                data-testid="work-studio-export-scope"
              />
            </div>
            </div>
            <div>
              <Label className="text-[12px]">Output format</Label>
              <RadioGroup
                value={outputFormat}
                onValueChange={setOutputFormat}
                className="flex flex-wrap gap-3 mt-1.5"
                data-testid="work-studio-export-format"
              >
                {formatChoices.map(([val, label]) => (
                  <div key={val} className="flex items-center gap-1.5">
                    <RadioGroupItem id={`ws-fmt-${val}`} value={val} />
                    <Label htmlFor={`ws-fmt-${val}`} className="text-[12.5px] cursor-pointer">{label}</Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
            <DialogFooter className="gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose} className="text-[12.5px]">
                Cancel
              </Button>
              <Button type="submit" className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]" data-testid="work-studio-export-submit">
                <FileDown className="w-3.5 h-3.5 mr-1.5" /> Compose
              </Button>
            </DialogFooter>
          </form>
            )}
          </div>
        )}

        {phase === "running" && (
          <div className="py-6" data-testid="work-studio-export-running">
            <p className="text-[14px] text-[var(--ink)] font-medium mb-3 text-center">
              Composing the {KIND_LABEL[kind].toLowerCase()}…
            </p>
            <div className="max-w-md mx-auto">
              <StreamingLogScene
                surfaceId="streaming-log-work-studio-compile"
                state={streamState}
                emptyHint="Starting the composition…"
              />
            </div>
            {elapsedSec !== null && (
              <p className="text-[11px] text-[var(--muted)] mt-4 font-mono text-center">{elapsedSec}s</p>
            )}
            {exportId && (
              <p className="text-[10px] text-[var(--muted)] mt-1 font-mono break-all text-center">{exportId}</p>
            )}
          </div>
        )}

        {phase === "complete" && (
          <div className="py-4" data-testid="work-studio-export-complete">
            <p className="text-[14px] text-[var(--ink)] font-medium mb-2">Composition complete.</p>
            <p className="text-[12.5px] text-[var(--muted)] mb-1">
              File: <span className="font-mono text-[var(--ink)]">{fileName}</span>
            </p>
            {/* Track A Phase 5 (2026-06-04, W4) — saved-to-cards
                breadcrumb. The export was already persisted by the
                backend (work_studio_exports.insert_one); we just
                surface that fact in the success modal so the user
                doesn't perceive the file as ephemeral. */}
            <p
              className="text-[11.5px] text-emerald-700 mb-2"
              data-testid="work-studio-export-saved-breadcrumb"
            >
              Saved to Drafts &amp; Briefs as a new document card.
              {exportId && (
                <button
                  type="button"
                  onClick={() => {
                    if (typeof window !== "undefined") {
                      window.dispatchEvent(new CustomEvent("akki:open-document-overlay", {
                        detail: { artefactId: exportId },
                      }));
                      window.dispatchEvent(new Event("akki:document-card-pulse"));
                    }
                    onClose && onClose();
                  }}
                  className="ml-1.5 text-[var(--accent)] hover:text-[var(--accent-dark)] underline underline-offset-2"
                  data-testid="work-studio-export-open-card"
                >
                  Open card
                </button>
              )}
            </p>
            {status?.sensitivity_band && (
              <p className="text-[11.5px] text-[var(--muted)] mb-3">
                Sensitivity band: <span className="font-mono text-[var(--ink)]">{status.sensitivity_band}</span>
              </p>
            )}
            <div className="flex flex-wrap gap-2 mt-3">
              <Button
                onClick={onDownload}
                className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
                data-testid="work-studio-export-download"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" /> Download
              </Button>
              {continueChatId && (
                <Button
                  variant="outline"
                  onClick={onContinueChat}
                  className="text-[12.5px] border-[var(--rule)] hover:border-[var(--accent)]"
                  data-testid="work-studio-export-continue-chat"
                >
                  <MessageSquare className="w-3.5 h-3.5 mr-1.5" /> Continue in chat
                </Button>
              )}
              <Button variant="outline" onClick={onClose} className="text-[12.5px]">
                Close
              </Button>
            </div>
          </div>
        )}

        {phase === "failed" && (
          <div className="py-4" data-testid="work-studio-export-failed">
            <div className="flex items-start gap-2 text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 mb-3">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <div className="text-[12.5px]">
                <p className="font-medium mb-1">Composition did not complete.</p>
                <p className="font-mono text-[11px] break-all">{errMsg || "unknown error"}</p>
              </div>
            </div>
            {refusalText && (
              <div
                className="bg-[var(--cream-deep)] border border-[var(--rule)] rounded-sm px-3 py-2 mb-3"
                data-testid="work-studio-export-refusal"
              >
                <p className="text-[10px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">From AKKI</p>
                <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-[1.6]">{refusalText}</p>
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={() => setPhase("compose")} className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]">
                Adjust and try again
              </Button>
              <Button variant="outline" onClick={onClose} className="text-[12.5px]">
                Close
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
