/**
 * SandboxSampleDoc — first-touch upload UX.
 *
 * Apr-2026 user feedback iter48: "In the sandbox journey, AKKI generates
 * a document for the user to 'accept upload' so it is intuitive and the
 * experience flows seamlessly."
 *
 * Behaviour:
 *  - Renders only when context.type === 'sandbox' AND the prospect hasn't
 *    yet accepted (sandbox_metadata.sample_doc_accepted = false).
 *  - Shows a tailored "this could be your board pack" preview the user
 *    can read in place. One click "Accept upload" materialises it as a
 *    real document and the card hides itself.
 */
import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Sparkles, Loader2, Check, ChevronDown, ChevronUp, FileText,
} from "lucide-react";

export default function SandboxSampleDoc({ onAccepted }) {
  const { activeContext } = useAuth();
  const isSandbox = activeContext?.type === "sandbox";
  const cid = activeContext?.id;
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [hidden, setHidden] = useState(false);

  const load = useCallback(async () => {
    if (!isSandbox || !cid) return;
    try {
      const { data } = await api.get(`/sandbox/contexts/${cid}/sample-doc`);
      if (data?.already_accepted) { setHidden(true); return; }
      setData(data);
    } catch { setHidden(true); }
  }, [isSandbox, cid]);
  useEffect(() => { load(); }, [load]);

  const accept = async () => {
    if (!data || accepting) return;
    setAccepting(true);
    try {
      await api.post(`/sandbox/contexts/${cid}/sample-doc/accept`, {
        title: data.title,
        filename: data.filename,
        preview: data.preview,
      });
      toast.success("Sample pack added — AKKI is reading it now.");
      setHidden(true);
      onAccepted?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setAccepting(false); }
  };

  if (!isSandbox || hidden || !data) return null;

  const previewLines = data.preview.split("\n").slice(0, 8).join("\n");

  return (
    <div
      className="bg-white border border-[var(--accent)]/30 rounded-lg overflow-hidden mb-5 shadow-sm"
      data-testid="sandbox-sample-doc"
    >
      {/* Header strip */}
      <div className="px-5 py-3 bg-[var(--accent-soft)]/40 border-b border-[var(--accent)]/15 flex items-center gap-3">
        <Sparkles className="w-4 h-4 text-[var(--accent)] shrink-0" strokeWidth={1.7} />
        <div className="flex-1 min-w-0">
          <p className="akki-overline text-[var(--accent)]">AKKI prepared a sample for you</p>
          <p className="text-[12px] text-[var(--deep)] italic">
            One tap to bring it in — no upload, no friction. AKKI will read it and surface signals.
          </p>
        </div>
      </div>

      {/* Preview */}
      <div className="px-5 py-4">
        <div className="flex items-start gap-3">
          <FileText className="w-4 h-4 text-[var(--muted)] mt-1 shrink-0" strokeWidth={1.7} />
          <div className="flex-1 min-w-0">
            <p className="akki-serif text-[16px] text-[var(--ink)] leading-tight mb-1">{data.title}</p>
            <p className="text-[11px] uppercase tracking-wider text-[var(--muted)]">
              {data.filename} · {data.word_count} words
            </p>
          </div>
        </div>

        <div className="mt-4 bg-[var(--cream-deep)]/30 border border-[var(--rule)] rounded-md px-4 py-3">
          <pre className="akki-serif text-[12.5px] text-[var(--deep)] whitespace-pre-wrap leading-snug font-sans">
            {expanded ? data.preview : previewLines}
            {!expanded && "\n…"}
          </pre>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 text-[11px] uppercase tracking-wider text-[var(--accent)] inline-flex items-center gap-1 hover:underline"
            data-testid="sandbox-sample-toggle"
          >
            {expanded
              ? <>Collapse <ChevronUp className="w-3 h-3" /></>
              : <>Read full preview <ChevronDown className="w-3 h-3" /></>}
          </button>
        </div>
      </div>

      {/* Action bar */}
      <div className="px-5 py-3 bg-[var(--cream-deep)]/20 border-t border-[var(--rule)] flex items-center justify-between gap-3">
        <p className="text-[11.5px] text-[var(--muted)] italic">
          You can also drop your real pack below — both work the same way.
        </p>
        <Button
          onClick={accept}
          disabled={accepting}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white h-9 px-4 text-[12.5px]"
          data-testid="sandbox-sample-accept"
        >
          {accepting
            ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Adding…</>
            : <><Check className="w-3.5 h-3.5 mr-1.5" /> Accept upload</>}
        </Button>
      </div>
    </div>
  );
}
