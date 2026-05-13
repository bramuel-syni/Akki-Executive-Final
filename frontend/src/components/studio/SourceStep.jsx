/**
 * Phase C.3 — SourceStep.
 *
 * The Source row that prepends the existing ExportModal flow. Three
 * radio options:
 *   ⊙ From this system            (default — keeps the existing 3-field path)
 *   ⊙ From a Solva session        (new — picks a session, fires C.1)
 *   ⊙ From a chat artefact        (new — picks a chat, fires C.1)
 *
 * When a non-default source is picked, this component takes over the
 * modal body and renders:
 *   - A scrollable session/chat picker
 *   - A small metadata block (Company / Programme; Document type comes
 *     from the kind so the user doesn't double-enter it)
 *   - A C.1 picker grid: Format · Depth · Fidelity, with FT-toned
 *     insight strings inline (NOT tooltips). Reads /api/work_studio/picker.
 *   - Two CTAs at the bottom:
 *       · Open in composer       — fires from-source ONLY, redirects to
 *                                   /app/studio/composer/{kind}/{artefact_id}
 *       · Generate document now  — fires from-source AND immediately
 *                                   posts /api/work_studio/exports with
 *                                   source_type=work_studio_brief, returning
 *                                   a real download.
 *
 * onSeeded({artefact_id, brief_id, kind, redirect_url}) — Open in composer path.
 * onGenerated({export_id, download_url, filename, brief_id, kind, artefact_id}) — Generate path.
 *
 * Visual style follows the existing ExportModal: same Dialog body
 * width, same labels, same border + cream surface, same uppercase
 * mono kicker. NO new design tokens.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft, Brain, MessageSquare, Sparkles, Loader2, AlertCircle,
  ChevronRight, FileText, Presentation, FileType, Layers,
} from "lucide-react";
import { toast } from "sonner";

const FORMAT_ORDER   = ["docx", "pptx", "pdf"];
const DEPTH_ORDER    = ["executive_brief", "board_summary", "deep_dive"];
const FIDELITY_ORDER = ["low", "high"];
const FORMAT_ICON    = { docx: FileText, pptx: Presentation, pdf: FileType };

const SUBMODULE_LABEL = {
  seek_clarity: "Seek Clarity",
  develop_strategy: "Develop Strategy",
  simulate_hypothesis: "Simulate Hypothesis",
  get_perspective: "See Different Perspectives",
};

function shortDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch { return "—"; }
}

function firstLine(s) {
  if (!s) return "";
  const t = String(s).trim();
  const i = t.indexOf("\n");
  return i === -1 ? t : t.slice(0, i);
}

// Picker insight fallbacks — synced with backend/work_studio/brief.py::PICKER.
const FALLBACK_INSIGHT = {
  format: {
    docx: "Word — narrative prose with two-tier headings. The native form for governance memos and board narrative.",
    pptx: "PowerPoint — 16:9 slides with persistent left sidebar. The native form for board read-outs and committee briefings.",
    pdf:  "PDF — programmatic HTML rendered to a fixed page. The native form for shareable, print-ready output.",
  },
  depth: {
    executive_brief: "One-page distillation. The most consequential sentence first; everything else compresses around it.",
    board_summary:   "Three-to-five page board read-out. The standard length for a tabled paper.",
    deep_dive:       "Long-form analysis with supporting tables. For working sessions and committee briefings.",
  },
  fidelity: {
    low:  "Draft fidelity. Bullets and short paragraphs. For circulation under embargo or pre-read.",
    high: "Board-grade fidelity. Structured tables, KPI contracts, action grids. Production-ready output.",
  },
};

const FORMAT_LABEL   = { docx: "Word document", pptx: "PowerPoint deck", pdf: "PDF" };
const DEPTH_LABEL    = { executive_brief: "Executive Brief", board_summary: "Board Summary", deep_dive: "Deep Dive" };
const FIDELITY_LABEL = { low: "Low Fidelity (Draft)", high: "High Fidelity (Board Grade)" };

// =============================================================================
// Source choice radio (top of the modal)
// =============================================================================
function SourceChoiceRow({ active, onPick, label, hint, icon: Icon, testId }) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-pressed={active}
      data-testid={testId}
      className={`w-full text-left border rounded-md px-4 py-3 flex items-start gap-3 transition-colors ${
        active
          ? "border-[var(--accent)] bg-[var(--cream-deep)]/40"
          : "border-[var(--rule)] bg-white hover:border-[var(--accent)]"
      }`}
    >
      <Icon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="akki-serif text-[14px] text-[var(--ink)] font-medium">{label}</p>
        <p className="text-[12px] text-[var(--deep)] leading-[1.55] mt-0.5">{hint}</p>
      </div>
      <div
        className={`shrink-0 w-3 h-3 rounded-full border ${active ? "border-[var(--accent)] bg-[var(--accent)]" : "border-[var(--rule)]"}`}
        aria-hidden
      />
    </button>
  );
}

export function SourceChoice({ value, onChange }) {
  return (
    <div className="space-y-2 mb-4" data-testid="source-step-choices">
      <SourceChoiceRow
        active={value === "system"}
        onPick={() => onChange("system")}
        icon={Sparkles}
        label="From this system"
        hint="Akki composes from the documents, signals, and cycle data already in your context."
        testId={`source-choice-system${value === "system" ? "-active" : ""}`}
      />
      <SourceChoiceRow
        active={value === "solva_session"}
        onPick={() => onChange("solva_session")}
        icon={Brain}
        label="From a Solva session"
        hint="Pick a completed Solva session — Seek Clarity, Develop Strategy, Simulate Hypothesis, or See Different Perspectives — and seed a brief from its synthesis."
        testId={`source-choice-solva_session${value === "solva_session" ? "-active" : ""}`}
      />
      <SourceChoiceRow
        active={value === "chat_artefact"}
        onPick={() => onChange("chat_artefact")}
        icon={MessageSquare}
        label="From a chat artefact"
        hint="Pick a chat with assistant content; we'll compose its narrative into a kind-aware draft."
        testId={`source-choice-chat_artefact${value === "chat_artefact" ? "-active" : ""}`}
      />
    </div>
  );
}

// =============================================================================
// Inline session / chat picker
// =============================================================================
function InlinePicker({ sourceType, value, onPick, contextId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setErr(null); setItems([]);
    // Privacy fix (WS-R16, 2026-05-13) — the Solva session picker MUST
    // pass `context_id` so the backend can scope results to the active
    // workspace. Before this fix, the picker leaked sessions from every
    // workspace the user belonged to. The backend now also requires
    // `context_id` (422 if missing), so this is belt-and-braces.
    const path = sourceType === "solva_session"
      ? { url: "/solva/v2/sessions", params: { status: "completed", context_id: contextId } }
      : { url: "/chats", params: { limit: 25 } };
    api.get(path.url, { params: path.params })
      .then(({ data }) => {
        if (cancelled) return;
        const arr = sourceType === "solva_session"
          ? (data?.items || [])
          : ((data?.items || data?.chats || data || []).filter((c) => !c.deleted_at && (c.title || "").trim().length > 0));
        setItems(arr.slice(0, 25));
        setLoading(false);
      })
      .catch((e) => { if (!cancelled) { setErr(apiErrorMessage(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [sourceType]);

  if (loading) {
    return <div className="text-[var(--muted)] text-[13px] flex items-center gap-2 py-3">
      <Loader2 className="w-4 h-4 animate-spin" /> Loading {sourceType === "solva_session" ? "sessions" : "chats"}…
    </div>;
  }
  if (err) {
    return <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-center gap-2">
      <AlertCircle className="w-3.5 h-3.5" /> {err}
    </div>;
  }
  if (items.length === 0) {
    return <p className="text-[12.5px] text-[var(--muted)] italic py-3">
      {sourceType === "solva_session"
        ? "No completed Solva sessions yet. Run one through synthesis and reflection first."
        : "No chats with assistant content yet."}
    </p>;
  }

  return (
    <ul className="space-y-1.5 max-h-[260px] overflow-y-auto pr-1" data-testid={`inline-picker-${sourceType}`}>
      {items.map((it) => {
        const id = it.id;
        const active = value?.id === id;
        const title = sourceType === "solva_session"
          ? (firstLine(it.intent) || "(no intent)")
          : (it.title || "Untitled chat");
        const sub = sourceType === "solva_session"
          ? `${SUBMODULE_LABEL[it.submodule] || it.submodule} · ${shortDate(it.completed_at || it.updated_at)}${it.context_name ? ` · ${it.context_name}` : ""}`
          : `${it.model || "Chat"} · ${shortDate(it.updated_at || it.created_at)}`;
        return (
          <li key={id}>
            <button
              type="button"
              onClick={() => onPick({ id, label: title, sub_label: sub })}
              className={`w-full text-left border rounded-sm px-3 py-2 transition-colors ${
                active
                  ? "border-[var(--accent)] bg-[var(--cream-deep)]/40"
                  : "border-[var(--rule)] bg-white hover:border-[var(--accent)]"
              }`}
              data-testid={`inline-picker-${sourceType}-${id}${active ? "-active" : ""}`}
            >
              <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug truncate">{title}</p>
              <p className="text-[11px] text-[var(--muted)] mt-0.5 truncate">{sub}</p>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

// =============================================================================
// C.1 picker grid (Format / Depth / Fidelity, inline insight strings)
// =============================================================================
function PickerOption({ active, onPick, label, insight, icon: Icon, testId }) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-pressed={active}
      data-testid={testId}
      className={`w-full text-left border rounded-sm px-3 py-2 flex items-start gap-2 transition-colors ${
        active
          ? "border-[var(--accent)] bg-[var(--cream-deep)]/40"
          : "border-[var(--rule)] bg-white hover:border-[var(--accent)]"
      }`}
    >
      {Icon && <Icon className="w-3.5 h-3.5 text-[var(--deep)] shrink-0 mt-0.5" strokeWidth={1.7} />}
      <div className="min-w-0 flex-1">
        <p className="text-[13px] text-[var(--ink)] font-medium">{label}</p>
        {insight && <p className="text-[11.5px] text-[var(--deep)] leading-[1.5] mt-0.5">{insight}</p>}
      </div>
      <div className={`shrink-0 w-2.5 h-2.5 rounded-full border mt-0.5 ${active ? "border-[var(--accent)] bg-[var(--accent)]" : "border-[var(--rule)]"}`} aria-hidden />
    </button>
  );
}

function C1PickerGrid({ picker, format, depth, fidelity, onChange }) {
  const lab = (group, key) => {
    const it = (picker?.[group] || []).find((x) => x.key === key);
    return it?.label || ({ format: FORMAT_LABEL, depth: DEPTH_LABEL, fidelity: FIDELITY_LABEL }[group] || {})[key] || key;
  };
  const ins = (group, key) => {
    const it = (picker?.[group] || []).find((x) => x.key === key);
    return it?.insight || FALLBACK_INSIGHT[group][key] || "";
  };
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="c1-picker-grid">
      <div>
        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1.5">Format</p>
        <div className="space-y-1.5">
          {FORMAT_ORDER.map((f) => (
            <PickerOption key={f} active={format === f}
              onPick={() => onChange({ format: f })}
              label={lab("format", f)} insight={ins("format", f)} icon={FORMAT_ICON[f]}
              testId={`c1-format-${f}${format === f ? "-active" : ""}`} />
          ))}
        </div>
      </div>
      <div>
        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1.5">Depth</p>
        <div className="space-y-1.5">
          {DEPTH_ORDER.map((d) => (
            <PickerOption key={d} active={depth === d}
              onPick={() => onChange({ depth: d })}
              label={lab("depth", d)} insight={ins("depth", d)} icon={Layers}
              testId={`c1-depth-${d}${depth === d ? "-active" : ""}`} />
          ))}
        </div>
      </div>
      <div>
        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1.5">Fidelity</p>
        <div className="space-y-1.5">
          {FIDELITY_ORDER.map((f) => (
            <PickerOption key={f} active={fidelity === f}
              onPick={() => onChange({ fidelity: f })}
              label={lab("fidelity", f)} insight={ins("fidelity", f)}
              testId={`c1-fidelity-${f}${fidelity === f ? "-active" : ""}`} />
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Source-driven body — renders when sourceChoice ∈ {solva_session, chat_artefact}
// =============================================================================
export default function SourceStep({
  contextId, contextName, kind,
  sourceChoice, onSourceChange,
  onSeeded, onGenerated,
}) {
  const [picked, setPicked] = useState(null);
  const [companyLabel, setCompanyLabel] = useState(contextName || "Akki");
  const [programme, setProgramme] = useState("");
  const documentType = useMemo(() => ({
    briefing: "Board Briefing", deck: "Board Deck", report: "Report",
  }[kind] || "Board Briefing"), [kind]);

  const formatDefault = kind === "deck" ? "pptx" : "docx";
  const [format, setFormat]     = useState(formatDefault);
  const [depth, setDepth]       = useState("board_summary");
  const [fidelity, setFidelity] = useState("high");

  const [picker, setPicker] = useState(null);
  const [busy, setBusy] = useState(null);  // null | "open" | "generate"
  const [err, setErr] = useState(null);

  // Reset picked source on choice change
  useEffect(() => { setPicked(null); setErr(null); }, [sourceChoice]);

  // Load picker insights once.
  useEffect(() => {
    if (sourceChoice === "system") return;
    let cancelled = false;
    api.get("/work_studio/picker")
      .then(({ data }) => { if (!cancelled) setPicker(data); })
      .catch(() => { /* silent — fallback copy will render */ });
    return () => { cancelled = true; };
  }, [sourceChoice]);

  const handleOpenInComposer = async () => {
    if (!picked) return;
    setBusy("open"); setErr(null);
    try {
      const { data } = await api.post(`/contexts/${contextId}/work-studio/from-source`, {
        source_type: sourceChoice,
        source_id: picked.id,
        kind,
        company_label: companyLabel || "Akki",
        document_type: documentType,
        programme: programme || null,
      });
      toast.success("Seeded.", { description: `${kind} ready in composer.` });
      onSeeded?.(data);
    } catch (e) {
      const msg = apiErrorMessage(e);
      setErr(msg);
      toast.error("Seed failed", { description: msg });
    } finally {
      setBusy(null);
    }
  };

  const handleGenerateNow = async () => {
    if (!picked) return;
    setBusy("generate"); setErr(null);
    try {
      // Step A — seed the kind-row + brief
      const seedResp = await api.post(`/contexts/${contextId}/work-studio/from-source`, {
        source_type: sourceChoice,
        source_id: picked.id,
        kind,
        company_label: companyLabel || "Akki",
        document_type: documentType,
        programme: programme || null,
      });
      const { artefact_id, brief_id } = seedResp.data;
      // Step B — fire the C.1 export against the persisted brief.
      const exp = await api.post(`/work_studio/exports`, {
        source_id: brief_id,
        source_type: "work_studio_brief",
        format, depth, fidelity,
        company_label: companyLabel || "Akki",
        document_type: documentType,
        programme: programme || null,
      });
      toast.success("Composed.", { description: `${exp.data.filename} · ${(exp.data.size_bytes / 1024).toFixed(1)} KB` });
      onGenerated?.({
        ...exp.data,
        kind,
        artefact_id,
        brief_id,
        redirect_url: seedResp.data.redirect_url,
      });
    } catch (e) {
      const msg = apiErrorMessage(e);
      setErr(msg);
      toast.error("Generate failed", { description: msg });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div data-testid="source-step-body">
      <SourceChoice value={sourceChoice} onChange={onSourceChange} />
      {sourceChoice !== "system" && (
        <>
          <div className="mb-4">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1.5">
              {sourceChoice === "solva_session" ? "Pick a Solva session" : "Pick a chat"}
            </p>
            <InlinePicker sourceType={sourceChoice} value={picked} onPick={setPicked} contextId={contextId} />
          </div>

          {picked && (
            <>
              <div className="border border-[var(--rule)] bg-[var(--cream-deep)]/40 rounded-md px-3 py-2 mb-4 flex items-start gap-2">
                <ChevronRight className="w-3.5 h-3.5 text-[var(--accent)] mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-0.5">Selected</p>
                  <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug truncate">{picked.label}</p>
                  <p className="text-[11px] text-[var(--muted)] mt-0.5 truncate">{picked.sub_label}</p>
                </div>
              </div>

              {/* Cover labels */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4" data-testid="source-step-metadata">
                <div>
                  <Label htmlFor="src-company" className="text-[12px] text-[var(--deep)]">Company / context</Label>
                  <Input id="src-company" value={companyLabel} onChange={(e) => setCompanyLabel(e.target.value)}
                    placeholder="e.g. Lemasy" disabled={!!busy}
                    data-testid="source-step-company" className="bg-white" />
                </div>
                <div>
                  <Label htmlFor="src-programme" className="text-[12px] text-[var(--deep)]">Programme (optional)</Label>
                  <Input id="src-programme" value={programme} onChange={(e) => setProgramme(e.target.value)}
                    placeholder="e.g. Q3 Board Cycle" disabled={!!busy}
                    data-testid="source-step-programme" className="bg-white" />
                </div>
              </div>

              {/* C.1 Format · Depth · Fidelity grid */}
              <C1PickerGrid
                picker={picker}
                format={format} depth={depth} fidelity={fidelity}
                onChange={(p) => {
                  if (p.format)   setFormat(p.format);
                  if (p.depth)    setDepth(p.depth);
                  if (p.fidelity) setFidelity(p.fidelity);
                }}
              />

              {err && (
                <div className="mt-3 text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-center gap-2">
                  <AlertCircle className="w-3.5 h-3.5" /> {err}
                </div>
              )}

              {/* Two CTAs */}
              <div className="mt-5 pt-4 border-t border-[var(--rule)] flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline"
                  onClick={handleOpenInComposer}
                  disabled={!!busy}
                  data-testid="source-step-open"
                  className="rounded-sm border-[var(--rule)] text-[12.5px]">
                  {busy === "open"
                    ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Seeding…</>
                    : <>Open in composer</>}
                </Button>
                <Button type="button"
                  onClick={handleGenerateNow}
                  disabled={!!busy}
                  data-testid="source-step-generate"
                  className="akki-cta bg-[var(--accent-dark)] hover:bg-[var(--accent)] text-white">
                  {busy === "generate"
                    ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Generating…</>
                    : <>Generate document now <ChevronRight className="w-3.5 h-3.5 ml-1" /></>}
                </Button>
                <span className="text-[11.5px] text-[var(--muted)]">
                  Open: seed-and-edit. Generate: seed and produce a downloadable {format.toUpperCase()}.
                </span>
              </div>
            </>
          )}

          {!picked && (
            <button
              type="button"
              onClick={() => onSourceChange("system")}
              className="mt-3 text-[12px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1"
              data-testid="source-step-back-to-system"
            >
              <ArrowLeft className="w-3 h-3" /> Use the existing Akki-from-system flow instead
            </button>
          )}
        </>
      )}
    </div>
  );
}
