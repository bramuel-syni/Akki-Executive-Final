/**
 * Phase H2 (2026-05-11) — Document routing actions.
 *
 * Three CTAs surfaced from the document side-drawer + Reading View
 * footer:
 *   1) Add to Cycle      → opens an agenda-item picker → POST contribution
 *   2) Add to Work Studio → routes to /app/work-studio + preloads source
 *   3) Take into Solva   → opens a 4-mode picker → POST solva session
 *
 * All three write an audit row server-side. Continue in Chat /
 * Ask in Chat are left in place — this component adds the missing
 * three.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Layers, FileText, Compass, Loader2, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const SOLVA_MODES = [
  { id: "seek_clarity",       label: "Seek Clarity",      desc: "Tease the question apart." },
  { id: "develop_strategy",   label: "Develop Strategy",  desc: "Build a working option." },
  { id: "simulate_hypothesis",label: "Simulate Hypothesis", desc: "Stress-test a position." },
  { id: "get_perspective",    label: "Get Perspective",   desc: "Sit with a senior counter-view." },
];

export default function DocumentRoutingActions({ contextId, doc, onActionDone }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(null);   // 'cycle' | 'solva' | null
  const [working, setWorking] = useState(false);
  const [agenda, setAgenda] = useState(null);
  const [chosenItem, setChosenItem] = useState(null);

  // Lazy-load the current cycle's agenda when the cycle modal opens.
  useEffect(() => {
    if (open !== "cycle" || !contextId) return;
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/cycle/agenda`);
        if (!alive) return;
        setAgenda(data?.agenda || data);
      } catch (e) {
        toast.error("Couldn't load cycle agenda.");
      }
    })();
    return () => { alive = false; };
  }, [open, contextId]);

  // ---------------- Action handlers ----------------
  const onAddToCycle = async (agendaItemId) => {
    setWorking(true);
    try {
      const payload = {
        agenda_item_id: agendaItemId || null,
        kind: "contribution",
        title: doc?.name || "Document",
        source_doc_id: doc?.id,
        body_text: (doc?.preview || (doc?.extracted_text || "").slice(0, 400)) || null,
      };
      await api.post(`/contexts/${contextId}/cycle/contributions`, payload);
      toast.success("Added to cycle", {
        action: { label: "Open cycle", onClick: () => navigate("/app/cycle") },
      });
      setOpen(null);
      onActionDone?.();
    } catch (e) {
      toast.error("Couldn't add to cycle.");
    } finally {
      setWorking(false);
    }
  };

  const onAddToWorkStudio = () => {
    // Defer the actual artefact-creation to the Work Studio composer.
    // Pre-populating the source via query string is the same pattern
    // used by Solva → Cycle handoff.
    navigate(`/app/work-studio?from_doc=${encodeURIComponent(doc?.id || "")}`);
    onActionDone?.();
  };

  const onTakeIntoSolva = async (submodule) => {
    setWorking(true);
    try {
      const { data } = await api.post(`/solva/v2/sessions`, {
        submodule,
        framing_text: doc?.name ? `Working from: ${doc.name}` : "",
        attached_document_id: doc?.id,
      });
      setOpen(null);
      onActionDone?.();
      const sid = data?.session?.id || data?.id;
      if (sid) navigate(`/app/solva/session/${sid}`);
      else toast.success("Solva session created.");
    } catch (e) {
      toast.error("Couldn't start a Solva session.");
    } finally {
      setWorking(false);
    }
  };

  // ---------------- Render ----------------
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen("cycle")}
        className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] inline-flex items-center gap-1.5"
        data-testid="doc-action-add-to-cycle"
      >
        <Layers className="w-3.5 h-3.5" strokeWidth={1.8} /> Add to Cycle
      </button>
      <button
        type="button"
        onClick={onAddToWorkStudio}
        className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] inline-flex items-center gap-1.5"
        data-testid="doc-action-add-to-work-studio"
      >
        <FileText className="w-3.5 h-3.5" strokeWidth={1.8} /> Add to Work Studio
      </button>
      <button
        type="button"
        onClick={() => setOpen("solva")}
        className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] inline-flex items-center gap-1.5"
        data-testid="doc-action-take-into-solva"
      >
        <Compass className="w-3.5 h-3.5" strokeWidth={1.8} /> Take into Solva
      </button>

      {/* Add-to-Cycle modal — agenda-item picker */}
      <Dialog open={open === "cycle"} onOpenChange={(v) => !v && setOpen(null)}>
        <DialogContent className="rounded-sm max-w-lg" data-testid="add-to-cycle-modal">
          <DialogHeader>
            <DialogTitle>Add to current cycle</DialogTitle>
            <DialogDescription>
              Choose which agenda item this document contributes to.
              You can re-assign later from the Cycle tab.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-72 overflow-y-auto -mx-2">
            {(agenda?.items || []).map((it) => (
              <button
                key={it.id}
                onClick={() => { setChosenItem(it.id); onAddToCycle(it.id); }}
                disabled={working}
                data-testid={`add-to-cycle-item-${it.id}`}
                className="w-full text-left px-3 py-2 hover:bg-slate-50 border-b border-[#F0F2F5] last:border-b-0 disabled:opacity-50 flex items-start gap-2"
              >
                <Layers className="w-3.5 h-3.5 mt-1 text-slate-400" strokeWidth={1.6} />
                <div>
                  <p className="text-sm text-[var(--ink)]">{it.title || "(untitled item)"}</p>
                  {it.summary && (
                    <p className="text-[11.5px] text-slate-500 mt-0.5">{it.summary}</p>
                  )}
                </div>
              </button>
            ))}
            {(!agenda || !(agenda.items || []).length) && (
              <p className="text-[12px] text-slate-500 px-3 py-4 italic">
                {agenda ? "No agenda items yet — open the Cycle tab to set up." : "Loading agenda…"}
              </p>
            )}
          </div>
          <DialogFooter>
            <button
              onClick={() => { setOpen(null); }}
              className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:bg-slate-50"
              data-testid="add-to-cycle-cancel"
            >
              Cancel
            </button>
            <button
              onClick={() => onAddToCycle(null)}
              disabled={working}
              className="text-[12.5px] px-3 py-1.5 bg-[var(--accent)] text-white rounded-sm hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="add-to-cycle-skip-item"
            >
              {working ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />}
              Attach to cycle (no specific item)
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Take-into-Solva modal — 4-mode picker */}
      <Dialog open={open === "solva"} onOpenChange={(v) => !v && setOpen(null)}>
        <DialogContent className="rounded-sm max-w-lg" data-testid="take-into-solva-modal">
          <DialogHeader>
            <DialogTitle>Which Solva mode?</DialogTitle>
            <DialogDescription>
              This document will be attached as grounding material.
              Pick the mode that fits the question you're trying to work.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-2">
            {SOLVA_MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => onTakeIntoSolva(m.id)}
                disabled={working}
                data-testid={`take-into-solva-${m.id}`}
                className="text-left p-3 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)] disabled:opacity-50"
              >
                <p className="text-sm text-[var(--ink)] font-medium">{m.label}</p>
                <p className="text-[11.5px] text-slate-500 mt-0.5">{m.desc}</p>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
