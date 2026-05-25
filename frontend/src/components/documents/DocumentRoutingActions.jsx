/**
 * DocumentRoutingActions — Document Journal CTAs.
 *
 * Three side-drawer / reader CTAs:
 *   1) Add to Cycle      → AddToCycleModal (shared, G1 ratified)
 *   2) Add to Work Studio → AddToWorkStudioModal (shared, T3.1 D5)
 *   3) Take into Solva   → 4-mode picker → /api/solva/v2/sessions
 *
 * T3.2 (2026-05-25) refactor — the Select-Cycle modal previously
 * inlined here was extracted into `components/shared/AddToCycleModal`
 * so other surfaces (HandoffActions, Reading View footer) can use
 * the same modal + the same G1 wire format without duplication.
 *
 * T3.1 (2026-05-25) refactor — the "Add to Work Studio" button used
 * to just navigate to `/app/work-studio?from_doc=<id>`. It now opens
 * the D5 modal which asks the user to choose the artefact type and
 * routes per G8 ratified.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Layers, FileText, Compass } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import AddToCycleModal from "@/components/shared/AddToCycleModal";
import AddToWorkStudioModal from "@/components/shared/AddToWorkStudioModal";

const SOLVA_MODES = [
  { id: "seek_clarity",       label: "Seek Clarity",      desc: "Tease the question apart." },
  { id: "develop_strategy",   label: "Develop Strategy",  desc: "Build a working option." },
  { id: "simulate_hypothesis",label: "Simulate Hypothesis", desc: "Stress-test a position." },
  { id: "get_perspective",    label: "Get Perspective",   desc: "Sit with a senior counter-view." },
];

export default function DocumentRoutingActions({ contextId, doc, onActionDone }) {
  const navigate = useNavigate();
  const [cycleOpen,     setCycleOpen]     = useState(false);
  const [workStudioOpen,setWorkStudioOpen]= useState(false);
  const [solvaOpen,     setSolvaOpen]     = useState(false);
  const [working,       setWorking]       = useState(false);

  const onTakeIntoSolva = async (submodule) => {
    setWorking(true);
    try {
      const docTitle = (doc?.name || doc?.original_filename || "this document").trim();
      const intent = `Work this question against ${docTitle}: what should a sharp non-executive notice on a careful read?`;
      const payload = {
        submodule,
        intent,
        intake_seed: doc?.id ? { kind: "document", id: doc.id } : undefined,
      };
      const { data } = await api.post(`/solva/v2/sessions`, payload);
      setSolvaOpen(false);
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

  return (
    <>
      <button
        type="button"
        onClick={() => setCycleOpen(true)}
        className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] inline-flex items-center gap-1.5"
        data-testid="doc-action-add-to-cycle"
      >
        <Layers className="w-3.5 h-3.5" strokeWidth={1.8} /> Add to Cycle
      </button>
      <button
        type="button"
        onClick={() => setWorkStudioOpen(true)}
        className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] inline-flex items-center gap-1.5"
        data-testid="doc-action-add-to-work-studio"
      >
        <FileText className="w-3.5 h-3.5" strokeWidth={1.8} /> Add to Work Studio
      </button>
      <button
        type="button"
        onClick={() => setSolvaOpen(true)}
        className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] inline-flex items-center gap-1.5"
        data-testid="doc-action-take-into-solva"
      >
        <Compass className="w-3.5 h-3.5" strokeWidth={1.8} /> Take into Solva
      </button>

      <AddToCycleModal
        open={cycleOpen}
        onOpenChange={setCycleOpen}
        contextId={contextId}
        doc={doc}
        onActionDone={onActionDone}
      />
      <AddToWorkStudioModal
        open={workStudioOpen}
        onOpenChange={setWorkStudioOpen}
        contextId={contextId}
        doc={doc}
        onActionDone={onActionDone}
      />

      {/* Take-into-Solva modal — 4-mode picker (unchanged from T1.6). */}
      <Dialog open={solvaOpen} onOpenChange={setSolvaOpen}>
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
