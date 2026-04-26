import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Brain, Heart, Layers, Coins, Users, Lightbulb, Loader2 } from "lucide-react";

/**
 * DocLensRail — a row of lens chips inside the DocumentViewer outline rail.
 * Tapping a chip opens a Lens coach session pre-loaded with this document's
 * name as the subject and a kickoff that asks AKKI to read the document
 * through the chosen lens.
 *
 * The chips deliberately match the editorial cadence — no badges, no
 * gamification, just a quiet "read this through" affordance.
 */
const LENSES = [
  { id: "first_principles", name: "First principles", icon: Brain },
  { id: "customer_obsession", name: "Customer obsession", icon: Heart },
  { id: "systems_thinking", name: "Systems thinking", icon: Layers },
  { id: "capital_discipline", name: "Capital discipline", icon: Coins },
  { id: "stakeholder_integration", name: "Stakeholders", icon: Users },
  { id: "organisational_culture", name: "Org culture", icon: Lightbulb },
];

export default function DocLensRail({ contextId, doc }) {
  const navigate = useNavigate();
  const [busyLens, setBusyLens] = useState(null);

  const onPickLens = async (lensId) => {
    if (busyLens) return;
    setBusyLens(lensId);
    try {
      const subject = `Read "${(doc?.name || "document").slice(0, 140)}" through ${LENSES.find((l) => l.id === lensId)?.name}`;
      const { data: session } = await api.post(
        `/contexts/${contextId}/lens/coach/sessions`,
        { lens: lensId, subject: subject.slice(0, 180) },
      );
      const kickoff =
        `I'm reading the document "${doc?.name || "this document"}" and want to test it through ${LENSES.find((l) => l.id === lensId)?.name}. ` +
        `What should I be looking for? What's the one question this document doesn't answer that I should be asking?`;
      // Best-effort kickoff message — if it fails the session is still usable.
      await api.post(
        `/contexts/${contextId}/lens/coach/sessions/${session.id}/messages`,
        { lens: lensId, message: kickoff },
        { timeout: 90000 },
      ).catch(() => {});
      toast.success("Lens opened.");
      navigate(`/app/lens?session=${session.id}`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusyLens(null);
    }
  };

  if (!contextId || !doc) return null;

  return (
    <div className="px-4 py-5 border-t border-[#E1E6ED]" data-testid="doc-lens-rail">
      <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold mb-3">
        Read through a lens
      </p>
      <div className="flex flex-wrap gap-1.5">
        {LENSES.map((l) => {
          const Icon = l.icon;
          const isBusy = busyLens === l.id;
          return (
            <button
              key={l.id}
              onClick={() => onPickLens(l.id)}
              disabled={!!busyLens}
              className="inline-flex items-center gap-1 px-2 py-1 text-[11px] rounded-full bg-white border border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40 hover:text-[var(--accent)] disabled:opacity-50 transition-colors"
              data-testid={`doc-lens-${l.id}`}
              title={`Open Lens coaching through ${l.name}`}
            >
              {isBusy ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Icon className="w-2.5 h-2.5" strokeWidth={2} />}
              {l.name}
            </button>
          );
        })}
      </div>
      <p className="text-[10.5px] text-slate-400 italic mt-2 leading-snug">
        Opens a coaching thread pre-loaded with this document's title.
      </p>
    </div>
  );
}
