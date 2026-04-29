/**
 * AppSolve — `/app/solve`. In-app placeholder for the AKKI Solve module.
 *
 * The full module ships in waves (see Iter58 plan). This page is the
 * entry point users will see in the sidebar — calm, honest "in build"
 * state with the framework on display, plus a "Notify me when ready"
 * affordance that records intent.
 */
import React, { useEffect, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowRight, Sparkles, Bell, Check } from "lucide-react";

const PHASES = [
  ["Surface",  "Name the problem the way a board chair would. One sentence."],
  ["Depth",    "Pressure-test the framing. Solve asks the questions a sharp counterpart would."],
  ["Synthesis","A diagnosis grounded in evidence and triangulation."],
  ["Lock-in",  "Decide what changes Monday — what you'll do, what you'll watch, what you'll walk in with."],
];

export default function AppSolve() {
  const [notified, setNotified] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/solve/interest/me")
      .then((r) => { if (r.data?.submitted) setNotified(true); })
      .catch(() => {});
  }, []);

  const notify = async () => {
    setBusy(true);
    try {
      await api.post("/solve/interest", {});
      setNotified(true);
      toast.success("We'll let you know the moment Solve is ready.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-12" data-testid="app-solve-placeholder">
        <header className="mb-12">
          <p className="akki-overline mb-2 flex items-center gap-1.5 text-[var(--accent)]">
            <Sparkles className="w-3 h-3" /> Akki Solve · in build
          </p>
          <h1 className="akki-serif text-4xl sm:text-5xl text-[var(--ink)] tracking-tight leading-[1.05] mb-5">
            For the board problems that don't have tidy answers.
          </h1>
          <p className="akki-serif text-[16px] text-[var(--deep)] leading-relaxed max-w-[58ch]">
            Solve is the structured pause we're building inside AKKI for the
            problems a chat thread won't get you to. It walks you through
            four phases — Surface, Depth, Synthesis, Lock-in — until the
            room moves from confusion to a diagnosis you can act on.
          </p>
        </header>

        <section className="bg-white border border-[var(--rule)] rounded-sm p-7 mb-8" data-testid="app-solve-phases">
          <p className="akki-overline mb-5">The framework</p>
          <ol className="space-y-4">
            {PHASES.map(([t, body], i) => (
              <li key={t} className="flex gap-5">
                <span className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-[var(--accent)] mt-1 min-w-[28px]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <p className="akki-serif text-[18px] text-[var(--ink)]">{t}</p>
                  <p className="text-[13px] text-[var(--deep)] leading-relaxed mt-0.5 max-w-[58ch]">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm p-7" data-testid="app-solve-notify">
          {notified ? (
            <div className="flex items-start gap-4">
              <Check className="w-6 h-6 text-[var(--accent)] mt-1" strokeWidth={1.7} />
              <div>
                <h3 className="akki-serif text-[20px] text-[var(--ink)] mb-1">Noted.</h3>
                <p className="text-[14px] text-[var(--deep)] leading-relaxed">
                  We'll let you know the moment your Solve seat is live. In
                  the meantime, your existing AKKI surfaces — Prepare, Chat,
                  Decks — keep you covered for everything except the
                  open-ended diagnoses Solve is built for.
                </p>
              </div>
            </div>
          ) : (
            <>
              <h3 className="akki-serif text-[22px] text-[var(--ink)] mb-2">
                Want a seat when Solve opens?
              </h3>
              <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-5 max-w-[58ch]">
                Solve is being shipped in private preview, then to Pro accounts.
                One click here puts you on the early-access list — no commitments.
              </p>
              <Button
                onClick={notify}
                disabled={busy}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-10 px-6"
                data-testid="app-solve-notify-btn"
              >
                <Bell className="w-3.5 h-3.5 mr-1.5" />
                {busy ? "Saving…" : "Notify me when Solve is ready"}
                {!busy && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
              </Button>
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
