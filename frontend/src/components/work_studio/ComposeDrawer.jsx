/**
 * Phase C.3 — Compose drawer.
 *
 * Right-side Sheet (NOT a modal). User picks Format / Depth / Fidelity
 * from inline-rendered picker rows, fills three metadata fields
 * (`company_label`, `document_type`, `programme`), and hits Generate.
 *
 * Reads option labels and FT-toned insight strings from
 * `GET /api/work_studio/picker`. Falls back to local copy if the call
 * fails (the option set is a closed enum so a fallback is safe).
 *
 * On success, calls `onComposed({brief_id, revision_id, export_id,
 * download_url, filename, source_type, source_id})`.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  X as XIcon, Loader2, FileText, Presentation, FileType, AlertCircle,
  Layers, Brain, MessageSquare, ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import {
  FORMAT_ORDER, DEPTH_ORDER, FIDELITY_ORDER, FALLBACK_INSIGHT,
  FORMAT_LABEL, DEPTH_LABEL, FIDELITY_LABEL,
} from "./tokens";

const FORMAT_ICON = { docx: FileText, pptx: Presentation, pdf: FileType };

function PickerRow({ active, onPick, label, insight, icon: Icon, testId }) {
  return (
    <button
      type="button"
      onClick={onPick}
      data-testid={testId}
      aria-pressed={active}
      className={`w-full text-left border rounded-md px-4 py-3 flex items-start gap-3 transition-colors ${
        active
          ? "border-[var(--accent)] bg-[var(--cream-deep)]/40"
          : "border-[var(--rule)] bg-white hover:border-[var(--accent)]"
      }`}
    >
      {Icon && <Icon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1" strokeWidth={1.7} />}
      <div className="min-w-0 flex-1">
        <p className="akki-serif text-[14.5px] text-[var(--ink)] font-medium">{label}</p>
        {insight && (
          <p className="text-[12.5px] text-[var(--deep)] leading-[1.55] mt-1">{insight}</p>
        )}
      </div>
      <div
        className={`shrink-0 w-3 h-3 rounded-full border ${active ? "border-[var(--accent)] bg-[var(--accent)]" : "border-[var(--rule)]"}`}
        aria-hidden
      />
    </button>
  );
}

export default function ComposeDrawer({
  open, onClose, onComposed,
  source,                  // {source_type, source_id, label, sub_label}
  contextId, contextName,
}) {
  const [picker, setPicker] = useState(null);
  const [pickerErr, setPickerErr] = useState(null);

  const [format, setFormat] = useState("docx");
  const [depth, setDepth] = useState("board_summary");
  const [fidelity, setFidelity] = useState("high");

  const [companyLabel, setCompanyLabel] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [programme, setProgramme] = useState("");

  const [generating, setGenerating] = useState(false);
  const [genErr, setGenErr] = useState(null);

  // Pre-fill metadata from active context + source.
  useEffect(() => {
    if (!open) return;
    setCompanyLabel(contextName || "Akki");
    if (source?.source_type === "solva_session") {
      const sub = source.sub_label || "";
      const map = {
        "Develop Strategy": "Strategy Memo",
        "Seek Clarity": "Clarity Read",
        "Simulate Hypothesis": "Hypothesis Stress Test",
        "See Different Perspectives": "Perspectives Read",
      };
      setDocumentType(map[sub] || "Board Briefing");
    } else if (source?.source_type === "chat_artefact") {
      setDocumentType("Memo");
    } else {
      setDocumentType("Board Briefing");
    }
    setProgramme("");
    setGenErr(null);
    setGenerating(false);
  }, [open, source, contextName]);

  // Load picker payload (FT-toned insights).
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setPicker(null); setPickerErr(null);
    api.get("/work_studio/picker")
      .then(({ data }) => { if (!cancelled) setPicker(data); })
      .catch((e) => { if (!cancelled) setPickerErr(apiErrorMessage(e)); });
    return () => { cancelled = true; };
  }, [open]);

  const insightFor = useMemo(() => {
    function find(group, key) {
      const items = picker?.[group] || [];
      const it = items.find((x) => x.key === key);
      return it?.insight || FALLBACK_INSIGHT[group][key] || "";
    }
    function lab(group, key) {
      const items = picker?.[group] || [];
      const it = items.find((x) => x.key === key);
      return it?.label || ({ format: FORMAT_LABEL, depth: DEPTH_LABEL, fidelity: FIDELITY_LABEL }[group] || {})[key] || key;
    }
    return { find, lab };
  }, [picker]);

  const handleGenerate = async () => {
    if (!source) return;
    setGenerating(true);
    setGenErr(null);
    try {
      const { data } = await api.post("/work_studio/exports", {
        source_id: source.source_id,
        source_type: source.source_type,
        format, depth, fidelity,
        company_label: companyLabel || "Akki",
        document_type: documentType || "Board Briefing",
        programme: programme || null,
      });
      toast.success("Composed.", { description: `${data.filename} · ${(data.size_bytes / 1024).toFixed(1)} KB` });
      onComposed?.({
        brief_id: data.brief_id,
        revision_id: data.revision_id,
        export_id: data.export_id,
        download_url: data.download_url,
        filename: data.filename,
        size_bytes: data.size_bytes,
        source_type: source.source_type,
        source_id: source.source_id,
        source_label: source.label,
        format, depth, fidelity,
        company_label: companyLabel || "Akki",
        document_type: documentType || "Board Briefing",
        programme: programme || null,
      });
    } catch (e) {
      const msg = apiErrorMessage(e);
      setGenErr(msg);
      toast.error("Compose failed", { description: msg });
    } finally {
      setGenerating(false);
    }
  };

  const sourceIcon = source?.source_type === "solva_session" ? Brain : MessageSquare;
  const SourceIcon = sourceIcon;

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v && !generating) onClose(); }}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[640px] sm:w-[640px] overflow-y-auto bg-[var(--paper)] p-0"
        data-testid="compose-drawer"
      >
        <div className="px-6 py-5 border-b border-[var(--rule)] flex items-start gap-3 sticky top-0 bg-[var(--paper)] z-10">
          <div className="min-w-0 flex-1">
            <SheetHeader className="text-left">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">
                Compose
              </p>
              <SheetTitle className="akki-serif text-[20px] text-[var(--ink)] leading-snug">
                Generate a board-grade artefact.
              </SheetTitle>
              <SheetDescription className="text-[12.5px] text-[var(--muted)]">
                Format, depth, fidelity. Three knobs. Generate produces a real download and persists the underlying brief.
              </SheetDescription>
            </SheetHeader>
          </div>
          <button
            onClick={onClose}
            disabled={generating}
            type="button"
            className="text-[var(--muted)] hover:text-[var(--ink)] p-1 disabled:opacity-50"
            aria-label="Close drawer"
            data-testid="compose-drawer-close"
          >
            <XIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-7">
          {source && (
            <div className="border border-[var(--rule)] bg-white rounded-md px-4 py-3 flex items-start gap-3" data-testid="compose-source-summary">
              <SourceIcon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1" strokeWidth={1.7} />
              <div className="min-w-0">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">
                  Source · {source.sub_label}
                </p>
                <p className="akki-serif text-[14.5px] text-[var(--ink)] leading-snug">{source.label}</p>
              </div>
            </div>
          )}

          {pickerErr && (
            <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5" /> Picker insights unavailable — using fallback labels.
            </div>
          )}

          {/* Format */}
          <div>
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">Format</p>
            <div className="space-y-2" data-testid="compose-picker-format">
              {FORMAT_ORDER.map((f) => (
                <PickerRow
                  key={f}
                  active={format === f}
                  onPick={() => setFormat(f)}
                  label={insightFor.lab("format", f)}
                  insight={insightFor.find("format", f)}
                  icon={FORMAT_ICON[f]}
                  testId={`compose-format-${f}${format === f ? "-active" : ""}`}
                />
              ))}
            </div>
          </div>

          {/* Depth */}
          <div>
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">Depth</p>
            <div className="space-y-2" data-testid="compose-picker-depth">
              {DEPTH_ORDER.map((d) => (
                <PickerRow
                  key={d}
                  active={depth === d}
                  onPick={() => setDepth(d)}
                  label={insightFor.lab("depth", d)}
                  insight={insightFor.find("depth", d)}
                  icon={Layers}
                  testId={`compose-depth-${d}${depth === d ? "-active" : ""}`}
                />
              ))}
            </div>
          </div>

          {/* Fidelity */}
          <div>
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">Fidelity</p>
            <div className="space-y-2" data-testid="compose-picker-fidelity">
              {FIDELITY_ORDER.map((f) => (
                <PickerRow
                  key={f}
                  active={fidelity === f}
                  onPick={() => setFidelity(f)}
                  label={insightFor.lab("fidelity", f)}
                  insight={insightFor.find("fidelity", f)}
                  testId={`compose-fidelity-${f}${fidelity === f ? "-active" : ""}`}
                />
              ))}
            </div>
          </div>

          {/* Metadata fields */}
          <div className="space-y-3" data-testid="compose-metadata">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">Cover labels</p>
            <div>
              <Label htmlFor="company-label" className="text-[12px] text-[var(--deep)]">Company / context</Label>
              <Input
                id="company-label"
                value={companyLabel}
                onChange={(e) => setCompanyLabel(e.target.value)}
                placeholder="e.g. Lemasy"
                disabled={generating}
                data-testid="compose-input-company"
                className="bg-white"
              />
            </div>
            <div>
              <Label htmlFor="document-type" className="text-[12px] text-[var(--deep)]">Document type</Label>
              <Input
                id="document-type"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                placeholder="e.g. Strategy Memo"
                disabled={generating}
                data-testid="compose-input-doctype"
                className="bg-white"
              />
            </div>
            <div>
              <Label htmlFor="programme" className="text-[12px] text-[var(--deep)]">Programme (optional)</Label>
              <Input
                id="programme"
                value={programme}
                onChange={(e) => setProgramme(e.target.value)}
                placeholder="e.g. Q3 Board Cycle"
                disabled={generating}
                data-testid="compose-input-programme"
                className="bg-white"
              />
            </div>
          </div>

          {genErr && (
            <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-start gap-2" data-testid="compose-error">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {genErr}
            </div>
          )}

          <div className="pt-2 flex items-center gap-3 sticky bottom-0 bg-[var(--paper)] py-3 -mx-6 px-6 border-t border-[var(--rule)]">
            <Button
              type="button"
              onClick={handleGenerate}
              disabled={generating || !source}
              className="akki-cta bg-[var(--accent-dark)] hover:bg-[var(--accent)] text-white"
              data-testid="compose-generate"
            >
              {generating ? (
                <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Generating…</>
              ) : (
                <>Generate <ChevronRight className="w-3.5 h-3.5 ml-1" /></>
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={generating}
              className="text-[var(--muted)] hover:text-[var(--ink)]"
            >
              Cancel
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
