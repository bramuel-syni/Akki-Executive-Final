/**
 * KeyboardHelp — Phase 13.3 discoverable shortcut overlay.
 *
 * Press `?` anywhere in the app (when not typing) to bring this up.
 * One panel, FT-voice, no marketing copy. Lists every shortcut
 * `useKeyboardShortcuts` registers. The hook delegates the open call
 * via the `openHelp` prop wired in AppShell.
 */
import React from "react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const SHORTCUTS = [
  { keys: ["⌘", "K"], label: "Open the command palette — search contexts and surfaces." },
  { keys: ["⌘", "J"], label: "Take the focused artefact into a new Solva session." },
  { keys: ["⌘", "S"], label: "Save the active editor (block composer, brief, report draft)." },
  { keys: ["?"],      label: "Show this overlay." },
];

export default function KeyboardHelp({ open, onOpenChange }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-sm max-w-md p-0 overflow-hidden" data-testid="keyboard-help-overlay">
        <DialogHeader className="px-6 pt-6 pb-3">
          <DialogTitle className="akki-serif text-[20px] text-[var(--ink)]">Keyboard shortcuts</DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Available everywhere inside the app. On Windows / Linux, swap ⌘ for Ctrl.
          </DialogDescription>
        </DialogHeader>
        <ul className="divide-y divide-[var(--rule)] border-t border-[var(--rule)]">
          {SHORTCUTS.map((s) => (
            <li key={s.keys.join("+")} className="flex items-center gap-4 px-6 py-3" data-testid={`shortcut-${s.keys.join("-")}`}>
              <div className="flex items-center gap-1">
                {s.keys.map((k, i) => (
                  <kbd key={i} className="font-mono text-[11px] bg-[var(--cream-deep)] border border-[var(--rule)] rounded-sm px-1.5 py-0.5 min-w-[24px] text-center">
                    {k}
                  </kbd>
                ))}
              </div>
              <p className="text-[13px] text-[var(--deep)] flex-1">{s.label}</p>
            </li>
          ))}
        </ul>
        <div className="px-6 py-3 bg-[var(--cream-deep)]/40 border-t border-[var(--rule)]">
          <p className="text-[11px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
            More shortcuts in subsequent phases.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
