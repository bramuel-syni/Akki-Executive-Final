/**
 * Phase F0.4 — CompanySwitcherDialog.
 *
 * This is the F0.0 hijack's body, lifted into its own component and
 * unhooked from the search affordance. It is now reachable ONLY by:
 *   - The dedicated "company switcher" button in the top nav (the
 *     active-company name pill).
 *   - The optional Cmd+Shift+K shortcut (different from Cmd+K).
 *
 * Cmd+K and the "Search" launcher button are NO LONGER bound to this.
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Search, Layers, CheckCircle2, Sparkles, Settings } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { isSponsoredContext } from "@/lib/sponsorship";

export default function CompanySwitcherDialog() {
  const navigate = useNavigate();
  const { contexts, activeContext, switchContext } = useAuth();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  // Open on the dedicated event. The legacy `akki:open-palette` event
  // has been re-pointed to Universal Search; this component listens
  // for a NEW event name so the two affordances cannot collide.
  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("akki:open-company-switcher", onOpen);
    return () => window.removeEventListener("akki:open-company-switcher", onOpen);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
    else setQuery("");
  }, [open]);

  const filtered = (contexts || []).filter(
    (c) => !query || (c.name || "").toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="rounded-sm max-w-xl p-0 overflow-hidden"
        data-testid="company-switcher-dialog"
      >
        <DialogHeader className="sr-only">
          <DialogTitle>Switch company</DialogTitle>
          <DialogDescription>
            Choose another company you have access to. Search is a separate affordance — press ⌘K.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-3 border-b border-[#E1E6ED] px-4 py-3">
          <Search className="w-4 h-4 text-slate-400" strokeWidth={1.8} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter companies…"
            className="flex-1 bg-transparent outline-none text-sm placeholder:text-slate-400"
            data-testid="company-switcher-input"
          />
          <kbd className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-sm">
            esc
          </kbd>
        </div>
        <div className="max-h-80 overflow-y-auto py-2">
          <p className="px-4 py-1.5 text-[10px] uppercase tracking-[0.2em] text-slate-400">
            Companies
          </p>
          {filtered.map((c) => {
            const active = c.id === activeContext?.id;
            return (
              <button
                key={c.id}
                onClick={() => { switchContext(c.id); setOpen(false); }}
                className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 text-left group"
                data-testid={`company-switcher-row-${c.id}`}
              >
                <div className="flex items-center gap-3">
                  <Layers className={`w-4 h-4 ${active ? "text-[var(--accent)]" : "text-slate-400"}`} strokeWidth={1.6} />
                  <div>
                    <p className="text-sm text-[var(--ink)] font-medium">{c.name}</p>
                    <p className="text-[10px] uppercase tracking-wider text-slate-400">
                      {c.my_role || "member"}
                      {isSponsoredContext(c) && <span className="ml-2 text-[var(--accent)]">sponsored</span>}
                    </p>
                  </div>
                </div>
                {active && <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />}
              </button>
            );
          })}
          <p className="px-4 py-1.5 mt-2 text-[10px] uppercase tracking-[0.2em] text-slate-400">
            Actions
          </p>
          <button
            onClick={() => { setOpen(false); navigate("/app/contexts/new"); }}
            className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 text-left"
            data-testid="company-switcher-new-context-btn"
          >
            <Sparkles className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.6} />
            <span className="text-sm text-[var(--ink)]">Add a company…</span>
          </button>
          <button
            onClick={() => { setOpen(false); navigate("/app/settings"); }}
            className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 text-left"
            data-testid="company-switcher-settings-btn"
          >
            <Settings className="w-4 h-4 text-slate-400" strokeWidth={1.6} />
            <span className="text-sm text-[var(--ink)]">Open settings</span>
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
