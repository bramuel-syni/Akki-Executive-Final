/**
 * HandoffActions — Phase 13.3 cross-module handoff buttons.
 *
 * One reusable button row that mounts inside any artefact detail view
 * (briefing detail, deck detail, signal detail, document detail) and
 * gives the user three escape hatches:
 *
 *   - Take into Solva    → /app/solva?seed_kind=&seed_id=
 *   - Send to Work Studio→ /app/work-studio?seed_kind=&seed_id=
 *   - Add to Cycle       → POST /api/contexts/{cid}/cycle/questions and navigate
 *
 * The component renders the data-solva-seed attribute on its host span
 * so the global ⌘-J keyboard shortcut also picks the artefact up
 * automatically when this row is on screen.
 *
 * Caller responsibilities:
 *   - Pass `kind` (one of: briefing, deck, signal, document)
 *   - Pass `id`   (the artefact's stable id)
 *   - Pass `contextId` (so the "Add to Cycle" call can target the
 *     correct board / company seat)
 *   - Optionally pass `title` for nicer Cycle question seeding.
 */
import React, { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api, apiErrorMessage } from "@/lib/api";
import { takeToSolva } from "@/lib/takeToSolva";
import { Sparkles, Presentation, ListPlus, Loader2, MessageSquare } from "lucide-react";
import AddToCycleModal from "@/components/shared/AddToCycleModal";

export default function HandoffActions({ kind, id, contextId, title, className = "" }) {
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  // T3.2 (2026-05-25) — for the document case, the Add-to-Cycle CTA
  // now uses the shared G1 Select-Cycle modal. For other artefact
  // kinds (briefing / deck / signal) the existing question-bank flow
  // is preserved — those are a different journey (cycle dispatch
  // seeding) and G1 doesn't apply.
  const [cycleModalOpen, setCycleModalOpen] = useState(false);
  const seed = kind && id ? `${kind}:${id}` : null;

  // Workstream B.6 (2026-05-10) — Ask in Chat handoff. Only meaningful
  // when the seed is a `document`; the chat surface needs a doc id to
  // pre-attach for grounded conversation.
  const onAskInChat = useCallback(() => {
    if (kind !== "document" || !id) return;
    navigate(`/app/chat?doc=${encodeURIComponent(id)}`);
    toast.success("Opened a chat tethered to this document.");
  }, [kind, id, navigate]);

  const onSolva = useCallback(() => {
    if (!seed) {
      navigate("/app/solva");
      return;
    }
    // Phase F.2.A — unified journey via takeToSolva helper.
    takeToSolva({ navigate, kind, id });
    toast.success("Taking this into Solva.");
  }, [kind, id, seed, navigate]);

  const onWorkStudio = useCallback(() => {
    if (!seed) {
      navigate("/app/work-studio");
      return;
    }
    navigate(`/app/work-studio?seed_kind=${encodeURIComponent(kind)}&seed_id=${encodeURIComponent(id)}`);
    toast.success("Opened Work Studio with this artefact in scope.");
  }, [kind, id, seed, navigate]);

  const onAddToCycle = useCallback(async () => {
    // T3.2 (2026-05-25) — G1 parity fix. For documents, route through
    // the shared Select-Cycle modal that posts to /cycle/contributions
    // with G1's verbatim wire format. For other kinds we keep the
    // pre-T3 question-bank flow (a different journey, not a G1 use case).
    if (kind === "document" && id) {
      setCycleModalOpen(true);
      return;
    }
    if (!contextId) {
      toast.error("No active context — pick one before adding to a cycle.");
      return;
    }
    setAdding(true);
    try {
      const seedTitle = title || `Follow up on ${kind || "this artefact"}`;
      await api.post(`/contexts/${contextId}/questions`, {
        text: seedTitle,
        area_tags: [],
        notes: `Seeded from ${kind || "artefact"} ${id || ""} via Cycle Manager handoff.`,
      });
      toast.success("Added to the question bank.", {
        description: "It'll appear in the next Cycle dispatch you assemble.",
      });
      navigate(`/app/cycle?tab=overview`);
    } catch (e) {
      toast.error(apiErrorMessage(e) || "Could not add to Cycle.");
    } finally {
      setAdding(false);
    }
  }, [contextId, kind, id, title, navigate]);

  return (
    <div
      className={`flex flex-wrap items-center gap-2 ${className}`}
      data-solva-seed={seed || undefined}
      data-testid="handoff-actions"
    >
      {/* Workstream B.6 — Ask in Chat. Document-only for now; the
          chat surface needs a doc id to pre-attach. */}
      {kind === "document" && id && (
        <Button
          type="button" size="sm" variant="outline"
          onClick={onAskInChat}
          className="rounded-sm border-[var(--rule)] text-[12.5px] hover:bg-[var(--cream-deep)]"
          data-testid="handoff-ask-in-chat"
        >
          <MessageSquare className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} />
          Ask in Chat
        </Button>
      )}
      <Button
        type="button" size="sm" variant="outline"
        onClick={onSolva}
        className="rounded-sm border-[var(--rule)] text-[12.5px] hover:bg-[var(--cream-deep)]"
        data-testid="handoff-take-into-solva"
      >
        <Sparkles className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} />
        Take into Solva
      </Button>
      <Button
        type="button" size="sm" variant="outline"
        onClick={onWorkStudio}
        className="rounded-sm border-[var(--rule)] text-[12.5px] hover:bg-[var(--cream-deep)]"
        data-testid="handoff-send-to-work-studio"
      >
        <Presentation className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} />
        Send to Work Studio
      </Button>
      <Button
        type="button" size="sm" variant="outline"
        disabled={adding}
        onClick={onAddToCycle}
        className="rounded-sm border-[var(--rule)] text-[12.5px] hover:bg-[var(--cream-deep)]"
        data-testid="handoff-add-to-cycle"
      >
        {adding ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ListPlus className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} />}
        Add to Cycle
      </Button>
      {kind === "document" && id && (
        <AddToCycleModal
          open={cycleModalOpen}
          onOpenChange={setCycleModalOpen}
          contextId={contextId}
          doc={{ id, name: title }}
        />
      )}
    </div>
  );
}
