/**
 * CycleStepNav — Layer 2 page-exit strip.
 *
 * Sits below the in-form `StepFooter`. The in-form Back moves between
 * steps within the cycle; this Back EXITS the current cycle and
 * returns to the Cycle Manager section (/app/cycle, the cycle list
 * landing). Per QA-2026-05-16-016 the label is "Back to Cycle Manager"
 * so the destination is unambiguous when both bars are visible at
 * the bottom of the page.
 *
 * On the Compilation tab for an active cycle, Next becomes "Close Cycle".
 * On the Compilation tab for a completed cycle, Next is replaced with
 * a disabled "Cycle Completed" label.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Lock } from "lucide-react";


const TAB_ORDER = ["agenda", "team", "contributions", "scoreboard", "followups", "compilation"];


export default function CycleStepNav({ tab, status, onChange, onClose }) {
  const idx = TAB_ORDER.indexOf(tab);
  // `back` retained for parity with the in-form StepFooter's tab
  // ordering, but is not used as the destination — the bottom Back
  // bar always exits to /app/cycle per QA-2026-05-16-016.
  const next = idx < TAB_ORDER.length - 1 ? TAB_ORDER[idx + 1] : null;
  const isCompilation = tab === "compilation";
  const isCompleted = status === "completed";
  // Suppress eslint warnings — `idx` kept for readability of the
  // surrounding logic even though we don't read `back` anymore.
  void idx;

  return (
    <div
      className="flex items-center justify-between mt-8 pt-4 border-t border-[var(--rule)]"
      data-testid="cycle-step-nav"
    >
      <Button
        size="sm" variant="outline"
        asChild
        className="text-[12.5px]"
        data-testid="cycle-step-nav-back"
      >
        <Link to="/app/cycle">
          <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Back to Cycle Manager
        </Link>
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
