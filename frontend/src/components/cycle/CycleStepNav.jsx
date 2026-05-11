/**
 * CycleStepNav — Layer 2 Back / Next strip.
 *
 * On the Compilation tab for an active cycle, Next becomes "Close Cycle".
 * On the Compilation tab for a completed cycle, Next is replaced with
 * a disabled "Cycle Completed" label.
 */
import React from "react";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Lock } from "lucide-react";


const TAB_ORDER = ["agenda", "team", "contributions", "scoreboard", "followups", "compilation"];


export default function CycleStepNav({ tab, status, onChange, onClose }) {
  const idx = TAB_ORDER.indexOf(tab);
  const back = idx > 0 ? TAB_ORDER[idx - 1] : null;
  const next = idx < TAB_ORDER.length - 1 ? TAB_ORDER[idx + 1] : null;
  const isCompilation = tab === "compilation";
  const isCompleted = status === "completed";

  return (
    <div
      className="flex items-center justify-between mt-8 pt-4 border-t border-[var(--rule)]"
      data-testid="cycle-step-nav"
    >
      <Button
        size="sm" variant="outline"
        disabled={!back}
        onClick={() => back && onChange(back)}
        className="text-[12.5px]"
        data-testid="cycle-step-nav-back"
      >
        <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Back
      </Button>

      {isCompilation ? (
        isCompleted ? (
          <Button
            size="sm" variant="outline" disabled
            className="text-[12.5px] uppercase tracking-[0.1em] font-mono"
            data-testid="cycle-step-nav-completed"
          >
            <Lock className="w-3.5 h-3.5 mr-1" /> Cycle Completed
          </Button>
        ) : (
          <Button
            size="sm"
            onClick={() => onClose && onClose()}
            className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white text-[12.5px]"
            data-testid="cycle-step-nav-close"
          >
            Close Cycle
          </Button>
        )
      ) : (
        <Button
          size="sm" variant="outline"
          disabled={!next}
          onClick={() => next && onChange(next)}
          className="text-[12.5px]"
          data-testid="cycle-step-nav-next"
        >
          Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      )}
    </div>
  );
}
