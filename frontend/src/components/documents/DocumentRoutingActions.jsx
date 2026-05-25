/**
 * Phase H2 (2026-05-11) — Document routing actions.
 *
 * Three CTAs surfaced from the document side-drawer + Reading View
 * footer:
 *   1) Add to Cycle      → opens a Select-Cycle dropdown → POST contribution
 *   2) Add to Work Studio → routes to /app/work-studio + preloads source
 *   3) Take into Solva   → opens a 4-mode picker → POST solva session
 *
 * All three write an audit row server-side. Continue in Chat /
 * Ask in Chat are left in place — this component adds the missing
 * three.
 *
 * T1.6 (2026-05-25) — Add to Cycle rebuilt per spec §4.A → D6 with
 * G1-ratified wire format: the modal lists Active + Draft cycles for
 * the active context (GET /contexts/{cid}/cycles), the user picks one,
 * and the frontend POSTs `{cycle_id, kind:"document", source_doc_id,
 * title}` to /contexts/{cid}/cycle/contributions?cycle_id=<selected>.
 * Document attaches at the cycle root (no agenda/contributor binding).
 * Backend errors (400/422/423) surface as human-readable toasts.
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

// T1.6 (2026-05-25) — D6 step 2 lists Active and Draft cycles only.
const CYCLE_SELECTABLE_STATUSES = ["active", "draft"];

export default function DocumentRoutingActions({ contextId, doc, onActionDone }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(null);   // 'cycle' | 'solva' | null
  const [working, setWorking] = useState(false);
  const [cycles, setCycles] = useState(null); // null=loading, []=empty, [...]=loaded
  const [selectedCycleId, setSelectedCycleId] = useState("");
  const [cyclesError, setCyclesError] = useState(null);

  // T1.6 (2026-05-25) — Load Active + Draft cycles when the Add to
  // Cycle modal opens. Spec D6 step 2: dropdown lists ALL Active and
  // Draft cycles for the active context. We issue two parallel GETs
  // (one per status filter) and merge — the cycles endpoint accepts a
  // single `status` filter at a time.
  useEffect(() => {
    if (open !== "cycle" || !contextId) return;
    let alive = true;
    setCycles(null);
    setCyclesError(null);
    setSelectedCycleId("");
    (async () => {
      try {
        const [activeResp, draftResp] = await Promise.all([
          api.get(`/contexts/${contextId}/cycles`, { params: { status: "active", page_size: 60 } }),
          api.get(`/contexts/${contextId}/cycles`, { params: { status: "draft",  page_size: 60 } }),
        ]);
        if (!alive) return;
        const merged = [
          ...((activeResp.data?.cycles) || []),
          ...((draftResp.data?.cycles)  || []),
        ];
        setCycles(merged);
      } catch (e) {
        if (!alive) return;
        setCyclesError(true);
        setCycles([]);
      }
    })();
    return () => { alive = false; };
  }, [open, contextId]);

  // ---------------- Action handlers ----------------
  const onAddToCycle = async () => {
    if (!selectedCycleId) return;
    setWorking(true);
    const cycle = (cycles || []).find((c) => c.id === selectedCycleId);
    const cycleName = cycle?.title || "the cycle";
    try {
      // T1.6 (2026-05-25) — G1 ratified wire format (verbatim from
      // spec §4.A → D6 → ratification block): body carries `cycle_id`,
      // `kind: "document"`, `source_doc_id`, `title`; the same
      // `cycle_id` is also passed as the query param so the backend
      // `_get_or_init_agenda` resolver picks up the right cycle row.
      // `agenda_item_id` and `team_member_id` are intentionally
      // omitted — the document attaches at the cycle root with no
      // agenda-item / contributor binding, per the Select-Cycle-only
      // flow D6 specifies.
      const payload = {
        cycle_id: selectedCycleId,
        kind: "document",
        source_doc_id: doc?.id,
        title: doc?.name || "Document",
      };
      await api.post(
        `/contexts/${contextId}/cycle/contributions?cycle_id=${encodeURIComponent(selectedCycleId)}`,
        payload,
      );
      // D6 step 3 — success toast (verbatim copy from spec).
      toast.success(`Your document has been added to Cycle Manager in ${cycleName}.`);
      setOpen(null);
      onActionDone?.();
      // D6 step 5 — navigate to the Cycle Manager listing All tab,
      // passing the attached cycle id so the listing can pulse the
      // matching card per the highlight rule.
      navigate(`/app/cycle?attached=${encodeURIComponent(selectedCycleId)}`);
    } catch (e) {
      // T1.6 — surface backend errors (422 validation, 423 cycle
      // locked, 400 generic) with human-readable toasts. Per spec D6
      // step 4 the generic failure copy is verbatim.
      const status = e?.response?.status;
      if (status === 423) {
        toast.error("This cycle is locked and can't accept new contributions.");
      } else if (status === 422) {
        toast.error("This document can't be added — required details are missing.");
      } else if (status === 400) {
        toast.error("This document can't be added to the selected cycle.");
      } else {
        toast.error("We couldn't add this document to the cycle. Please try again.");
      }
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
      // QA-2026-05-16-006 (2026-05-18) — payload aligned to backend
      // StartV2In: `intent` is required (min 20 chars). We compose a
      // canonical doc-anchored intent and pass `intake_seed` so the
      // session intake screen knows to render the source document.
      const docTitle = (doc?.name || doc?.original_filename || "this document").trim();
      const intent = `Work this question against ${docTitle}: what should a sharp non-executive notice on a careful read?`;
      const payload = {
        submodule,
        intent,
        intake_seed: doc?.id ? { kind: "document", id: doc.id } : undefined,
      };
      const { data } = await api.post(`/solva/v2/sessions`, payload);
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

      {/* Add-to-Cycle modal — Select-Cycle dropdown (G1 ratified, D6) */}
      <Dialog open={open === "cycle"} onOpenChange={(v) => !v && setOpen(null)}>
        <DialogContent className="rounded-sm max-w-lg" data-testid="add-to-cycle-modal">
          <DialogHeader>
            <DialogTitle>Add to Cycle</DialogTitle>
            <DialogDescription>
              Choose which cycle this document contributes to.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <label
              htmlFor="add-to-cycle-select"
              className="block text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5"
            >
              Select cycle
            </label>
            {cycles === null ? (
              <p className="text-[12px] text-slate-500 italic py-2" data-testid="add-to-cycle-loading">
                Loading cycles…
              </p>
            ) : cyclesError ? (
              <p className="text-[12px] text-red-700 py-2" data-testid="add-to-cycle-error">
                Couldn't load your cycles. Please try again.
              </p>
            ) : cycles.length === 0 ? (
              <p className="text-[12px] text-slate-500 italic py-2" data-testid="add-to-cycle-empty">
                You have no active or draft cycles. Create one from the Cycle Manager first.
              </p>
            ) : (
              <select
                id="add-to-cycle-select"
                value={selectedCycleId}
                onChange={(e) => setSelectedCycleId(e.target.value)}
                disabled={working}
                data-testid="add-to-cycle-select"
                className="w-full text-[13px] px-3 py-2 border border-[var(--rule)] rounded-sm bg-white text-[var(--ink)] focus:outline-none focus:border-[var(--accent)]"
              >
                <option value="">— Choose a cycle —</option>
                {cycles.map((c) => (
                  <option key={c.id} value={c.id} data-testid={`add-to-cycle-option-${c.id}`}>
                    {c.title}
                    {CYCLE_SELECTABLE_STATUSES.includes((c.status || "").toLowerCase())
                      ? ` (${(c.status || "").toLowerCase()})`
                      : ""}
                  </option>
                ))}
              </select>
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
              onClick={onAddToCycle}
              disabled={working || !selectedCycleId}
              className="text-[12.5px] px-3 py-1.5 bg-[var(--accent)] text-white rounded-sm hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
              data-testid="add-to-cycle-attach"
            >
              {working ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />}
              Attach to cycle
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
