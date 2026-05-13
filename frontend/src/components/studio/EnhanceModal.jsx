/**
 * EnhanceModal — Two paths share the same modal shape.
 *
 *   Path A — UPLOAD (legacy Phase 13).  Default when `briefId` is not
 *            supplied. The user uploads a .docx/.pptx/.pdf and writes
 *            instructions; we POST multipart to
 *            /api/contexts/{cid}/work-studio/enhance/{kind} and poll
 *            for the rendered binary. Same lifecycle as today.
 *
 *   Path B — C.2 BRIEF ENHANCE (Phase C.3).  Activated when the
 *            consumer passes `briefId` (i.e. opening Enhance on a
 *            Solva-originated artefact whose row carries a brief_id).
 *            The user types an instruction + scope; we POST to
 *            /api/work_studio/briefs/{brief_id}/enhance, render a
 *            section diff with refusal banner, and offer Set Active.
 *            Refusal cases keep Set Active disabled and surface the
 *            verbatim validator reason.
 *
 * Restraint copy throughout — no banned words from MEMO Item 8.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, apiErrorMessage } from "@/lib/api";
import {
  Loader2, Download, AlertCircle, Wand2, Upload, MessageSquare,
  AlertTriangle, Check, ChevronRight, ChevronDown, GitBranch, Eye,
} from "lucide-react";
import { toast } from "sonner";

const FORMAT_OPTIONS = {
  deck:   [["pptx", "PPTX"], ["pdf", "PDF"], ["auto", "Auto"]],   // PDF soft-forks to PPTX server-side
  report: [["docx", "DOCX"], ["pdf", "PDF"], ["auto", "Auto"]],
  briefing: [["docx", "DOCX"], ["pdf", "PDF"], ["auto", "Auto"]],
  brief:    [["docx", "DOCX"], ["pdf", "PDF"], ["auto", "Auto"]],
};

const ACCEPT_BY_KIND = {
  deck:    ".pptx,.pdf",
  report:  ".docx,.pdf",
  // Chunk 3 (2026-05-13, WS-R06) — Minutes added as a first-class
  // enhance kind. Minutes are a narrative artefact identical in
  // shape to a Report (sections + paragraphs) so the backend routes
  // them through the same Report renderer (docx-only output).
  // `.txt` is accepted alongside `.docx`/`.pdf` because draft
  // minutes are commonly pasted from notes apps as plain text.
  minutes: ".docx,.pdf,.txt",
};

const KIND_LABEL = {
  deck:     "Deck",
  report:   "Report",
  minutes:  "Minutes",
  briefing: "Brief",
  brief:    "Brief",
};

const SCOPE_OPTIONS = [
  { value: "whole_brief",    label: "Whole brief",        hint: "Edit any field; sections may be added or removed." },
  { value: "exec_summary",   label: "Executive summary",  hint: "Cover and the framing section only." },
  { value: "recommendations", label: "Recommendations",    hint: "Recommendation rows and the action grid only." },
];

// =============================================================================
// C2DiffCard — compact section diff card for the C.2 enhance result.
// Two-column before/after, collapsible, with a coloured change-type chip.
// Lives inside this file so the existing studio/ folder gets exactly one
// new module (SourceStep.jsx) — no broader proliferation.
// =============================================================================
function envelopeLabel(sid) {
  if (!sid?.startsWith("__envelope:")) return sid;
  const key = sid.slice("__envelope:".length);
  return ({
    title: "Cover · Title",
    subtitle: "Cover · Subtitle",
    cover_lead_paragraph: "Cover · Lead paragraph",
    closing_recap: "Closing · Recap",
    framework_spine: "Framework spine",
  }[key]) || `Cover · ${key}`;
}

function changeChip(t) {
  const map = {
    modified: { color: "bg-sky-50 text-sky-800 border-sky-100", label: "modified" },
    added:    { color: "bg-emerald-50 text-emerald-800 border-emerald-100", label: "added" },
    removed:  { color: "bg-rose-50 text-rose-800 border-rose-100", label: "removed" },
  };
  const x = map[t] || map.modified;
  return (
    <span className={`inline-flex items-center text-[10.5px] uppercase tracking-[0.14em] font-mono border rounded-sm px-1.5 py-[2px] ${x.color}`}>
      {x.label}
    </span>
  );
}

function C2DiffCard({ entry, defaultExpanded = false }) {
  const [open, setOpen] = useState(!!defaultExpanded);
  const sid = entry.section_id;
  const label = sid?.startsWith("__envelope:") ? envelopeLabel(sid) : (sid || "section");
  return (
    <li className="border border-[var(--rule)] bg-white rounded-md" data-testid={`c2-diff-${sid}`}>
      <header className="flex items-center gap-3 px-3 py-2 border-b border-[var(--rule)]/70">
        <button type="button" onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Collapse" : "Expand"}
          className="text-[var(--muted)] hover:text-[var(--ink)]">
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
        <p className="akki-serif text-[13.5px] text-[var(--ink)] font-medium flex-1 truncate">{label}</p>
        {changeChip(entry.change_type)}
      </header>
      {open && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-x divide-[var(--rule)]/70">
          <div className="px-3 py-2.5 bg-[var(--cream-deep)]/30">
            <p className="text-[10px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Before</p>
            {entry.before
              ? <pre className="akki-serif text-[12.5px] text-[var(--deep)] leading-[1.55] whitespace-pre-wrap font-[Georgia] m-0">{entry.before}</pre>
              : <p className="text-[12px] text-[var(--muted)] italic">(empty)</p>}
          </div>
          <div className="px-3 py-2.5">
            <p className="text-[10px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">After</p>
            {entry.after
              ? <pre className="akki-serif text-[12.5px] text-[var(--ink)] leading-[1.55] whitespace-pre-wrap font-[Georgia] m-0">{entry.after}</pre>
              : <p className="text-[12px] text-[var(--muted)] italic">(empty)</p>}
          </div>
        </div>
      )}
    </li>
  );
}

export default function EnhanceModal({ open, onClose, kind, contextId, briefId = null, mode = "default" }) {
  const navigate = useNavigate();
  const isC2 = !!briefId;
  // Phase F.6 — Compile-a-Report shares Path A's upload+enhance plumbing
  // but reframes the heading and helper copy. Only relevant when we're
  // not in C.2 mode (briefId === null).
  const isCompile = !isC2 && mode === "compile";

  // ---------------- shared state ----------------
  const [phase, setPhase] = useState("compose"); // compose | running | complete | failed
  const [errMsg, setErrMsg] = useState(null);

  // ---------------- Path A — upload state ----------------
  const [file, setFile] = useState(null);
  const [instructions, setInstructions] = useState("");
  const [outputFormat, setOutputFormat] = useState("auto");
  const [exportId, setExportId] = useState(null);
  const [status, setStatus] = useState(null);
  const [refusalText, setRefusalText] = useState(null);
  const [downloadToken, setDownloadToken] = useState(null);
  const [fileName, setFileName] = useState(null);
  const [continueChatId, setContinueChatId] = useState(null);
  const [continueDocId, setContinueDocId] = useState(null);

  // ---------------- Path B — C.2 enhance state ----------------
  const [c2Instruction, setC2Instruction] = useState("");
  const [c2Scope, setC2Scope] = useState("whole_brief");
  const [c2Result, setC2Result] = useState(null);          // {revision_id, diff, validation, ...}
  const [c2SetActiveBusy, setC2SetActiveBusy] = useState(false);
  const [c2Sections, setC2Sections] = useState([]);        // [{section_id, title}]
  const [c2Revisions, setC2Revisions] = useState([]);
  const [c2Active, setC2Active] = useState(null);          // active_revision_id

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
      setC2Instruction("");
      setC2Scope("whole_brief");
      setC2Result(null);
      setC2SetActiveBusy(false);
      setC2Sections([]);
      setC2Revisions([]);
      setC2Active(null);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [open]);

  // -------------------------------------------------------------------
  // Path B — load brief metadata when in C.2 mode
  // -------------------------------------------------------------------
  useEffect(() => {
    if (!open || !isC2 || !briefId) return;
    let cancelled = false;
    (async () => {
      try {
        const [m, r] = await Promise.all([
          api.get(`/work_studio/briefs/${briefId}`),
          api.get(`/work_studio/briefs/${briefId}/revisions`),
        ]);
        if (cancelled) return;
        const snap = m.data?.active_revision?.snapshot || {};
        setC2Sections((snap.sections || []).map((s) => ({ section_id: s.section_id, title: s.title })));
        setC2Revisions(r.data?.items || []);
        setC2Active(m.data?.brief?.active_revision_id || null);
      } catch (e) {
        if (!cancelled) setErrMsg(apiErrorMessage(e));
      }
    })();
    return () => { cancelled = true; };
  }, [open, isC2, briefId]);

  const onSubmitC2 = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    if (!c2Instruction.trim()) {
      setErrMsg("Write what you want tightened, sharpened, or added.");
      return;
    }
    setPhase("running");
    setErrMsg(null);
    setC2Result(null);
    startedAtRef.current = Date.now();
    try {
      const { data } = await api.post(`/work_studio/briefs/${briefId}/enhance`, {
        instruction: c2Instruction.trim(),
        scope: c2Scope,
      });
      setC2Result(data);
      // Refresh revisions list (the new revision is now persisted).
      try {
        const r = await api.get(`/work_studio/briefs/${briefId}/revisions`);
        setC2Revisions(r.data?.items || []);
      } catch { /* non-fatal */ }
      const v = data?.validation?.verdict;
      if (v === "refused") {
        toast.error("Refused.", { description: data?.validation?.reason || "" });
      } else if (v === "qualified") {
        toast("Qualified.", { description: "Section diffs ready below." });
      } else {
        toast.success("Validated.", { description: "Section diffs ready below." });
      }
      setPhase("complete");
    } catch (err) {
      setErrMsg(apiErrorMessage(err));
      setPhase("failed");
    }
  };

  const onSetActiveC2 = async () => {
    if (!c2Result?.revision_id) return;
    setC2SetActiveBusy(true);
    try {
      await api.post(`/work_studio/briefs/${briefId}/set_active`, {
        revision_id: c2Result.revision_id,
      });
      toast.success("Active revision updated.");
      setC2Active(c2Result.revision_id);
    } catch (err) {
      toast.error("Set active failed", { description: apiErrorMessage(err) });
    } finally {
      setC2SetActiveBusy(false);
    }
  };

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
  const c2Verdict = c2Result?.validation?.verdict;
  const c2Refused = c2Verdict === "refused";

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent
        className={isC2 ? "max-w-3xl max-h-[88vh] overflow-y-auto" : "max-w-md"}
        data-testid="work-studio-enhance-modal"
      >
        <DialogHeader>
          <DialogTitle className="akki-serif text-[var(--ink)]">
            {isC2
              ? `Refine ${KIND_LABEL[kind] || "Brief"}`
              : isCompile
                ? "Compile Report"
                : `Improve a ${KIND_LABEL[kind] || "Report"} you already have`}
          </DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            {isC2
              ? "Two-pass enhance against the persisted Brief. The validator refuses revisions that introduce uncited claims; refused revisions are kept for inspection but cannot be set active."
              : isCompile
                ? "Pull together documents you've received outside Akki — emails, attachments, PDFs — into one structured report."
                : `Upload an existing Word, PowerPoint, or PDF ${(KIND_LABEL[kind] || "report").toLowerCase()} and write what you want changed. The composer keeps citations intact and applies the instructions.`}
          </DialogDescription>
        </DialogHeader>

        {/* C.2 path — instruction + scope + diff + refusal banner + set-active */}
        {isC2 && phase === "compose" && (
          <form onSubmit={onSubmitC2} className="space-y-4" data-testid="work-studio-enhance-c2-form">
            <div>
              <Label className="text-[12px]" htmlFor="ws-enh-c2-instruction">Instruction</Label>
              <Textarea
                id="ws-enh-c2-instruction"
                value={c2Instruction}
                onChange={(e) => setC2Instruction(e.target.value)}
                placeholder="e.g. Tighten the opening. Make the central call sharper."
                className="rounded-sm min-h-[88px] akki-serif text-[14px] bg-white"
                required
                data-testid="ws-enh-c2-instruction"
              />
            </div>
            <div>
              <Label className="text-[12px] mb-1 block">Scope</Label>
              <div className="space-y-1.5" data-testid="ws-enh-c2-scope">
                {[...SCOPE_OPTIONS, ...c2Sections.map((s) => ({
                  value: `section:${s.section_id}`,
                  label: `Section · ${s.title || s.section_id}`,
                  hint: "Edit only this section.",
                }))].map((s) => (
                  <button
                    key={s.value}
                    type="button"
                    onClick={() => setC2Scope(s.value)}
                    className={`w-full text-left border rounded-sm px-3 py-2 text-[12.5px] flex items-start gap-3 transition-colors ${
                      c2Scope === s.value
                        ? "border-[var(--accent)] bg-[var(--cream-deep)]/40"
                        : "border-[var(--rule)] bg-white hover:border-[var(--accent)]"
                    }`}
                    data-testid={`ws-enh-c2-scope-${s.value.replace(/[^a-z0-9_-]/gi, "-")}${c2Scope === s.value ? "-active" : ""}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-[var(--ink)] font-medium">{s.label}</p>
                      <p className="text-[var(--muted)] text-[11.5px]">{s.hint}</p>
                    </div>
                    <div className={`shrink-0 w-3 h-3 rounded-full border ${c2Scope === s.value ? "border-[var(--accent)] bg-[var(--accent)]" : "border-[var(--rule)]"}`} aria-hidden />
                  </button>
                ))}
              </div>
            </div>
            {errMsg && (
              <p className="text-[12px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-2 py-1.5">
                {errMsg}
              </p>
            )}
            <DialogFooter className="gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose} className="text-[12.5px]">Cancel</Button>
              <Button type="submit"
                className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px]"
                data-testid="ws-enh-c2-submit"
              >
                <Wand2 className="w-3.5 h-3.5 mr-1.5" /> Refine
              </Button>
            </DialogFooter>
            <p className="text-[11px] text-[var(--muted)]">Round-trip is typically 45–60s.</p>
          </form>
        )}

        {isC2 && phase === "running" && (
          <div className="py-12 text-center" data-testid="ws-enh-c2-running">
            <Loader2 className="w-5 h-5 animate-spin text-[var(--muted)] mx-auto mb-3" />
            <p className="akki-serif text-[15px] text-[var(--ink)]">Refining.</p>
            <p className="text-[12px] text-[var(--muted)] mt-1">
              Reading the parent revision · composing the change · validating with an independent family.
            </p>
          </div>
        )}

        {isC2 && phase === "complete" && c2Result && (
          <div className="space-y-4" data-testid="ws-enh-c2-result">
            {c2Refused ? (
              <div
                className="border border-rose-200 bg-rose-50 rounded-md px-4 py-3"
                data-testid="ws-enh-c2-refusal"
                role="alert"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-4 h-4 text-rose-700 shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-rose-800 mb-1">
                      Refused {c2Result.drafter_refused ? "· by drafter" : "· by validator"}
                    </p>
                    <p className="akki-serif text-[14px] text-rose-900 leading-[1.55]">
                      {c2Result.validation?.reason || "The validator declined this revision."}
                    </p>
                    <p className="text-[12px] text-rose-800 mt-2">
                      The revision is preserved so you can inspect what the model tried to do, but it cannot be set active. Try a tighter instruction — one that doesn't ask for sources outside the brief's existing evidence.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="border border-emerald-200 bg-emerald-50 rounded-md px-4 py-3" data-testid="ws-enh-c2-validated">
                <div className="flex items-start gap-3">
                  <Check className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-emerald-800 mb-1">
                      {c2Verdict || "validated"}
                    </p>
                    <p className="akki-serif text-[13.5px] text-emerald-900 leading-[1.55]">
                      {c2Result.validation?.reason || "No uncited claims introduced."}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Section diffs */}
            <div data-testid="ws-enh-c2-diff">
              <h3 className="akki-serif text-[15px] text-[var(--ink)] font-medium mb-2">Section diffs</h3>
              {(c2Result.diff && c2Result.diff.length > 0) ? (
                <ul className="space-y-3">
                  {c2Result.diff.map((entry, idx) => (
                    <C2DiffCard key={`${entry.section_id}-${idx}`} entry={entry} defaultExpanded={idx < 2} />
                  ))}
                </ul>
              ) : (
                <p className="text-[12.5px] text-[var(--muted)] italic">No section changes between revisions.</p>
              )}
            </div>

            {/* Aggregate metrics */}
            <div className="grid grid-cols-3 gap-3 text-center" data-testid="ws-enh-c2-metrics">
              <div className="border border-[var(--rule)] bg-white rounded-md px-3 py-3">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Sections changed</p>
                <p className="akki-serif text-[20px] text-[var(--ink)]">{c2Result.claims_changed ?? 0}</p>
              </div>
              <div className="border border-[var(--rule)] bg-white rounded-md px-3 py-3">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Uncited claims</p>
                <p className={`akki-serif text-[20px] ${c2Result.claims_added_without_citation > 0 ? "text-rose-800" : "text-[var(--ink)]"}`}>
                  {c2Result.claims_added_without_citation ?? 0}
                </p>
              </div>
              <div className="border border-[var(--rule)] bg-white rounded-md px-3 py-3">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Verdict</p>
                <p className={`akki-serif text-[20px] ${c2Refused ? "text-rose-800" : c2Verdict === "qualified" ? "text-sky-800" : "text-emerald-800"}`}>
                  {c2Verdict || "—"}
                </p>
              </div>
            </div>

            {/* Revision strip */}
            {c2Revisions.length > 0 && (
              <div data-testid="ws-enh-c2-revstrip">
                <div className="flex items-center gap-2 mb-2">
                  <GitBranch className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.7} />
                  <h4 className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
                    Revision history · {c2Revisions.length}
                  </h4>
                </div>
                <ol className="flex items-stretch gap-2 overflow-x-auto pb-2">
                  {c2Revisions.map((r, idx) => {
                    const isActive = r.id === c2Active;
                    const isRefused = r.validation?.verdict === "refused";
                    const isJustCreated = r.id === c2Result.revision_id;
                    return (
                      <li key={r.id} className="shrink-0">
                        <div className={`w-[200px] border rounded-md bg-white px-2.5 py-2 ${
                          isJustCreated
                            ? "border-[var(--accent)] ring-2 ring-[var(--accent)] ring-offset-1"
                            : isActive
                              ? "border-[var(--accent)] ring-1 ring-[var(--accent)]"
                              : "border-[var(--rule)]"
                        }`} data-testid={`ws-enh-c2-revcard-${r.id}`}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="text-[10px] uppercase tracking-[0.16em] font-mono text-[var(--ink)]">
                              {r.parent_revision_id ? `Rev ${idx}` : "Original"}
                            </span>
                            {isActive && (
                              <span className="text-[9.5px] uppercase tracking-[0.14em] font-mono text-[var(--accent-dark)] inline-flex items-center gap-0.5">
                                <Check className="w-2.5 h-2.5" /> active
                              </span>
                            )}
                          </div>
                          <p
                            className={`akki-serif text-[12px] text-[var(--ink)] leading-snug line-clamp-2 ${isRefused ? "line-through opacity-70" : ""}`}
                            title={r.instruction}
                          >
                            {r.instruction || "(no instruction)"}
                          </p>
                          {isRefused && (
                            <span className="inline-flex items-center text-[9.5px] uppercase tracking-[0.14em] font-mono text-rose-700 mt-1 gap-0.5">
                              <AlertTriangle className="w-2.5 h-2.5" /> refused
                            </span>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}

            <DialogFooter className="gap-2 pt-2">
              <Button type="button" variant="outline" onClick={onClose} className="text-[12.5px]">Close</Button>
              <Button
                type="button"
                onClick={onSetActiveC2}
                disabled={c2Refused || c2SetActiveBusy}
                className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12.5px] disabled:bg-[var(--rule)] disabled:text-[var(--muted)]"
                data-testid="ws-enh-c2-set-active"
              >
                {c2SetActiveBusy
                  ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> Setting active…</>
                  : <>Set as active revision <ChevronRight className="w-3.5 h-3.5 ml-1" /></>}
              </Button>
            </DialogFooter>
          </div>
        )}

        {isC2 && phase === "failed" && (
          <div className="space-y-3" data-testid="ws-enh-c2-failed">
            <div className="border border-rose-200 bg-rose-50 rounded-md px-3 py-3 text-[12.5px] text-rose-900 flex items-start gap-2">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>{errMsg || "Refine failed."}</span>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} className="text-[12.5px]">Close</Button>
              <Button type="button" onClick={() => { setPhase("compose"); setErrMsg(null); }} className="text-[12.5px]">Try again</Button>
            </DialogFooter>
          </div>
        )}

        {/* Path A — legacy upload (unchanged behaviour, only renders when not in C.2 mode) */}
        {!isC2 && phase === "compose" && (
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
              />
              {/*
                Chunk 3 (2026-05-13, WS-R06 sub-bug) — "Adjust and retry"
                preserves the previously-selected `file` in React state,
                but the browser's <input type="file"> visually shows
                "No file chosen" after re-render (HTML inputs can't be
                programmatically re-populated for security reasons). The
                `required` HTML attribute was therefore *blocking* form
                submission on retry even though `file` state was intact,
                producing the "previously attached document is lost" UX
                that QA reported. We drop the HTML `required` and rely
                on the JS `if (!file)` check at submit time (see
                handleSubmit) — the React state IS the source of truth.
                When a previously-attached file is in state but the input
                shows empty, the file-name line below makes it clear the
                file IS still attached.
              */}
              {file && (
                <p className="text-[11px] text-[var(--muted)] mt-1 font-mono break-all" data-testid="work-studio-enhance-file-current">
                  Using: {file.name} · {Math.round(file.size / 1024)} KB
                  {phase === "compose" && (
                    <button
                      type="button"
                      onClick={() => setFile(null)}
                      className="ml-2 text-[var(--ink)] underline underline-offset-2 hover:opacity-80"
                      data-testid="work-studio-enhance-file-clear"
                    >
                      clear
                    </button>
                  )}
                </p>
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

        {!isC2 && phase === "running" && (
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

        {!isC2 && phase === "complete" && (
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

        {!isC2 && phase === "failed" && (
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
