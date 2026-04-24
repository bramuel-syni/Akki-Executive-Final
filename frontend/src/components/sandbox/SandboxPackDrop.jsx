/**
 * SandboxPackDrop — the "wait, this works on my stuff?" moment.
 *
 * Surfaces only inside a sandbox context, tucked onto the AppHome canvas.
 * The prospect drops a PDF of THEIR actual board pack; we upload it to the
 * sandbox context, then trigger a signal-generation run against it. New
 * signals carry a "from your pack" badge in the stream.
 *
 * Design: navy chrome pill, cream panel, oxblood "new" chip once signals
 * are fresh. Progressive disclosure — collapsed by default, expands on
 * click. Never nags.
 */
import React, { useCallback, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  UploadCloud, FileUp, Loader2, CheckCircle2, ChevronDown,
  ChevronUp, Sparkles,
} from "lucide-react";

const ACCEPT = ".pdf,.docx,.doc,.txt,.md";
const MAX_MB = 20;

export default function SandboxPackDrop({ onSignalsReady }) {
  const { activeContext } = useAuth();
  const isSandbox = activeContext?.type === "sandbox";
  const [expanded, setExpanded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const inputRef = useRef(null);

  const onFile = useCallback(async (file) => {
    if (!file) return;
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`That file is over ${MAX_MB}MB — try a lighter PDF.`);
      return;
    }

    setUploading(true);
    try {
      // 1. Upload to the sandbox context via the existing documents endpoint
      const fd = new FormData();
      fd.append("file", file);
      fd.append("display_name", file.name.replace(/\.[^.]+$/, ""));
      fd.append("description", "Uploaded by the prospect during sandbox exploration.");
      fd.append("data_trust", "mixed");
      const up = await api.post(
        `/contexts/${activeContext.id}/documents`, fd,
        { headers: { "Content-Type": "multipart/form-data" }, timeout: 120000 },
      );
      if (up.data.status !== "extracted") {
        toast.error(
          "We uploaded your file but couldn't extract readable text from it. " +
          "Try a PDF with selectable text rather than a scan."
        );
        setUploading(false);
        return;
      }
      toast.success("Uploaded. Asking AKKI to read it…");
      setUploading(false);

      // 2. Trigger signal generation against the whole sandbox (it will
      //    include this doc alongside the pre-seeded ones)
      setGenerating(true);
      const { data } = await api.post(
        `/contexts/${activeContext.id}/signals/generate`,
        { focus: `From the document "${up.data.name}", what does the board need to notice?` },
        { timeout: 120000 },
      );
      const count = (data.signals || []).length;
      setLastResult({
        doc_name: up.data.name,
        signals_count: count,
        mode: data.mode,
      });
      toast.success(
        count === 0
          ? "Read your pack — nothing new stood out."
          : `${count} fresh signal${count === 1 ? "" : "s"} from your pack.`,
        count > 0 ? { description: "Scroll down — they're at the top of your stream." } : undefined,
      );
      onSignalsReady && onSignalsReady();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Couldn't read that one. Try another pack."));
    } finally {
      setUploading(false);
      setGenerating(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }, [activeContext, onSignalsReady]);

  if (!isSandbox) return null;

  const busy = uploading || generating;

  return (
    <div
      className="relative bg-gradient-to-br from-white to-[var(--chrome-soft)]/60 border border-[var(--chrome)]/20 rounded-lg overflow-hidden mb-6"
      data-testid="sandbox-pack-drop"
    >
      {/* Collapsed state — just the nudge */}
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-[var(--chrome-soft)]/30 transition-colors"
        data-testid="sandbox-pack-drop-toggle"
      >
        <div className="w-8 h-8 rounded-full bg-[var(--chrome)] flex items-center justify-center shrink-0">
          <Sparkles className="w-3.5 h-3.5 text-white" strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="akki-serif text-[15px] text-[var(--ink)] leading-tight">
            Want to see AKKI on <em>your</em> pack?
          </p>
          <p className="text-[12px] text-[var(--muted)] mt-0.5">
            Drop any PDF — we'll read it alongside the fictional data. Stays inside your sandbox, vanishes with it.
          </p>
        </div>
        {lastResult ? (
          <span
            className="inline-flex items-center gap-1 text-[10.5px] uppercase tracking-[0.16em] text-[var(--accent)] bg-[var(--accent-soft)] border border-[var(--accent)]/30 rounded-sm px-2 py-1 shrink-0"
            data-testid="sandbox-pack-result-chip"
          >
            <CheckCircle2 className="w-3 h-3" />
            {lastResult.signals_count} new
          </span>
        ) : (
          <span className="shrink-0 text-[var(--muted)]">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }}
            className="overflow-hidden border-t border-[var(--chrome)]/15"
          >
            <div className="px-5 py-5 bg-[var(--cream)]/40">
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
                className="hidden"
                data-testid="sandbox-pack-drop-input"
                disabled={busy}
              />

              <div
                onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                onDrop={(e) => {
                  e.preventDefault(); e.stopPropagation();
                  if (busy) return;
                  const f = e.dataTransfer.files?.[0];
                  if (f) onFile(f);
                }}
                className="border-2 border-dashed border-[var(--chrome)]/25 rounded-md py-8 px-6 text-center bg-white/60 hover:border-[var(--chrome)]/50 transition-colors"
              >
                {busy ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-6 h-6 text-[var(--chrome)] animate-spin" strokeWidth={1.5} />
                    <p className="akki-serif text-[15px] text-[var(--ink)]">
                      {uploading ? "Uploading…" : "AKKI is reading your pack…"}
                    </p>
                    <p className="text-[11.5px] text-[var(--muted)]">This takes 10–30 seconds.</p>
                  </div>
                ) : lastResult ? (
                  <div className="flex flex-col items-center gap-2" data-testid="sandbox-pack-result">
                    <CheckCircle2 className="w-6 h-6 text-[var(--accent)]" strokeWidth={1.5} />
                    <p className="akki-serif text-[15px] text-[var(--ink)]">
                      {lastResult.signals_count === 0
                        ? "Read it — nothing fresh stood out."
                        : `${lastResult.signals_count} new signal${lastResult.signals_count === 1 ? "" : "s"} from "${lastResult.doc_name}".`}
                    </p>
                    <button
                      type="button"
                      onClick={() => { setLastResult(null); inputRef.current?.click(); }}
                      className="text-[12px] text-[var(--chrome)] hover:underline underline-offset-2 mt-1"
                    >
                      Try another pack
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <UploadCloud className="w-7 h-7 text-[var(--chrome)]" strokeWidth={1.4} />
                    <p className="akki-serif text-[15.5px] text-[var(--ink)]">Drop a PDF, DOCX, or TXT here</p>
                    <p className="text-[11.5px] text-[var(--muted)] mb-2">
                      or{" "}
                      <button
                        type="button"
                        onClick={() => inputRef.current?.click()}
                        className="text-[var(--chrome)] hover:underline underline-offset-2"
                        data-testid="sandbox-pack-drop-browse"
                      >
                        browse your files
                      </button>
                    </p>
                    <p className="text-[10.5px] text-[var(--muted)]/80 uppercase tracking-[0.14em]">
                      Up to {MAX_MB}MB · stays in your sandbox
                    </p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
