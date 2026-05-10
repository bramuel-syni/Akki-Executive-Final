/**
 * EnhanceModal — Phase C.3 wiring for the two Enhance buttons on
 * Work Studio. The user uploads a source file (.docx for report or
 * .pptx for deck — .pdf accepted as a fallback) and writes a short
 * instructions string. The modal POSTs as multipart/form-data to
 * /api/contexts/{cid}/work-studio/enhance/{kind} and polls the same
 * status endpoint as Export. On `complete` a Download button calls
 * the per-export download endpoint and a "Continue in chat" button
 * navigates to /app/chat with the new chat preloaded and the
 * enhanced artefact attached as a chip.
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
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, apiErrorMessage } from "@/lib/api";
import { Loader2, Download, AlertCircle, Wand2, Upload, MessageSquare } from "lucide-react";

const FORMAT_OPTIONS = {
  deck:   [["pptx", "PPTX"], ["pdf", "PDF"], ["auto", "Auto"]],   // PDF soft-forks to PPTX server-side
  report: [["docx", "DOCX"], ["pdf", "PDF"], ["auto", "Auto"]],
};

const ACCEPT_BY_KIND = {
  deck:   ".pptx,.pdf",
  report: ".docx,.pdf",
};

const KIND_LABEL = {
  deck:   "Deck",
  report: "Report",
};

export default function EnhanceModal({ open, onClose, kind, contextId }) {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [instructions, setInstructions] = useState("");
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

  const pollRef = useRef(null);
  const startedAtRef = useRef(null);

  // Reset on open/close.
  useEffect(() => {
    if (open) {
      setFile(null);
      setInstructions("");
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
    if (!file) {
      setErrMsg("Pick a source file to enhance.");
      return;
    }
    if (!instructions.trim()) {
      setErrMsg("Write a short instructions line.");
      return;
    }
    setPhase("running");
    setErrMsg(null);
    setRefusalText(null);
    startedAtRef.current = Date.now();
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("instructions", instructions.trim());
      fd.append("output_format", outputFormat);
      // Workstream B.8 — browser sets multipart boundary itself.
      const { data } = await api.post(
        `/contexts/${contextId}/work-studio/enhance/${kind}`,
        fd,
      );
      setExportId(data.export_id);
      setStatus(data);
      // Server may have already failed (thin-input deterministic refusal).
      if (data.status === "failed") {
        // Fetch the row once more to pull refusal_text in.
        try {
          const r2 = await api.get(
            `/contexts/${contextId}/work-studio/exports/${data.export_id}`,
          );
          setStatus(r2.data);
          setErrMsg(r2.data.error || "Enhance refused.");
          setRefusalText(r2.data.refusal_text || null);
        } catch (_e) {
          setErrMsg(data.error || "Enhance refused.");
        }
        setPhase("failed");
        return;
      }
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
            setErrMsg(r.data.error || "Enhance failed.");
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
    if (!exportId || !downloadToken) return;
    try {
      const resp = await api.get(`/contexts/${contextId}/work-studio/exports/${exportId}/download`, {
        params: { token: downloadToken },
        responseType: "blob",
      });
      const blob = new Blob([resp.data], { type: resp.headers?.["content-type"] || "application/octet-stream" });
      const a = document.createElement("a");
      a.href = window.URL.createObjectURL(blob);
      a.download = fileName || `akki-enhance-${exportId}.bin`;
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

  const formatChoices = FORMAT_OPTIONS[kind] || FORMAT_OPTIONS.report;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md" data-testid="work-studio-enhance-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[var(--ink)]">
            Enhance my {KIND_LABEL[kind] || "Report"}
          </DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Upload an existing {KIND_LABEL[kind].toLowerCase()} and write what you want changed. The composer keeps citations intact and applies the instructions.
          </DialogDescription>
        </DialogHeader>

        {phase === "compose" && (
          <form onSubmit={onSubmit} className="space-y-3" data-testid="work-studio-enhance-form">
            <div>
              <Label className="text-[12px]" htmlFor="ws-enhance-file">Source file</Label>
              <input
                id="ws-enhance-file"
                type="file"
                accept={ACCEPT_BY_KIND[kind] || ".docx,.pptx,.pdf"}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-[12.5px] mt-1 file:mr-3 file:py-1.5 file:px-3 file:rounded-sm file:border file:border-[var(--rule)] file:bg-white file:text-[12px] file:cursor-pointer"
                data-testid="work-studio-enhance-file"
                required
              />
              {file && (
                <p className="text-[11px] text-[var(--muted)] mt-1 font-mono break-all">{file.name} · {Math.round(file.size / 1024)} KB</p>
              )}
            </div>
            <div>
              <Label className="text-[12px]" htmlFor="ws-enhance-instructions">Instructions</Label>
              <Textarea
                id="ws-enhance-instructions"
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder='What should change — e.g. "Tighten the executive summary, drop the conclusion section."'
                className="rounded-sm min-h-[96px]"
                required
                data-testid="work-studio-enhance-instructions"
              />
            </div>
            <div>
              <Label className="text-[12px]">Output format</Label>
              <RadioGroup
                value={outputFormat}
                onValueChange={setOutputFormat}
                className="flex flex-wrap gap-3 mt-1.5"
                data-testid="work-studio-enhance-format"
              >
                {formatChoices.map(([val, label]) => (
                  <div key={val} className="flex items-center gap-1.5">
                    <RadioGroupItem id={`ws-enh-fmt-${val}`} value={val} />
                    <Label htmlFor={`ws-enh-fmt-${val}`} className="text-[12.5px] cursor-pointer">{label}</Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
            {errMsg && (
              <p className="text-[12px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-2 py-1.5">
                {errMsg}
              </p>
            )}
            <DialogFooter className="gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose} className="text-[12.5px]">
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!file || !instructions.trim()}
                className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
                data-testid="work-studio-enhance-submit"
              >
                <Wand2 className="w-3.5 h-3.5 mr-1.5" /> Enhance
              </Button>
            </DialogFooter>
          </form>
        )}

        {phase === "running" && (
          <div className="py-6 text-center" data-testid="work-studio-enhance-running">
            <Loader2 className="w-5 h-5 mx-auto animate-spin text-[var(--accent)] mb-3" />
            <p className="text-[14px] text-[var(--ink)] font-medium">Enhancing the {KIND_LABEL[kind].toLowerCase()}…</p>
            <p className="text-[11.5px] text-[var(--muted)] mt-1">
              About 30–60 seconds. Pass 1 reasoning runs first, then the deliverable.
            </p>
            {elapsedSec !== null && (
              <p className="text-[11px] text-[var(--muted)] mt-3 font-mono">{elapsedSec}s</p>
            )}
            {exportId && (
              <p className="text-[10px] text-[var(--muted)] mt-1 font-mono break-all">{exportId}</p>
            )}
          </div>
        )}

        {phase === "complete" && (
          <div className="py-4" data-testid="work-studio-enhance-complete">
            <p className="text-[14px] text-[var(--ink)] font-medium mb-2">Enhancement complete.</p>
            <p className="text-[12.5px] text-[var(--muted)] mb-1">
              File: <span className="font-mono text-[var(--ink)]">{fileName}</span>
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
                data-testid="work-studio-enhance-download"
              >
                <Download className="w-3.5 h-3.5 mr-1.5" /> Download
              </Button>
              {continueChatId && (
                <Button
                  variant="outline"
                  onClick={onContinueChat}
                  className="text-[12.5px] border-[var(--rule)] hover:border-[var(--accent)]"
                  data-testid="work-studio-enhance-continue-chat"
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
          <div className="py-4" data-testid="work-studio-enhance-failed">
            <div className="flex items-start gap-2 text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 mb-3">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <div className="text-[12.5px]">
                <p className="font-medium mb-1">Enhancement did not complete.</p>
                <p className="font-mono text-[11px] break-all">{errMsg || "unknown error"}</p>
              </div>
            </div>
            {refusalText && (
              <div
                className="bg-[var(--cream-deep)] border border-[var(--rule)] rounded-sm px-3 py-2 mb-3"
                data-testid="work-studio-enhance-refusal"
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
