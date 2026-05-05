/**
 * HomeUndeclared — Phase 13.3 prompt for users who haven't yet told
 * AKKI which side of the boardroom they sit on.
 *
 * Quick inline 3-button picker (NED · Executive · Both) that calls
 * POST /api/auth/declare-role and refreshes the session. We don't
 * detour to /app/first-session because most undeclared users have
 * already been through onboarding (declared_role lands as `executive`
 * by default; "undeclared" only exists as a deliberate reset). For
 * those who want the full intake, the link to /app/first-session is
 * preserved as the secondary path.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Briefcase, Landmark, ArrowRight, Loader2 } from "lucide-react";
import AddDocumentCard from "@/components/home/AddDocumentCard";

export default function HomeUndeclared() {
  const { account, refreshAuth } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(null);

  const declare = async (role) => {
    setBusy(role);
    try {
      await api.post("/auth/declare-role", { declared_role: role });
      if (refreshAuth) await refreshAuth();
      toast.success("Role saved.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <AppShell>
      <div className="max-w-[760px] mx-auto px-8 py-20" data-testid="home-undeclared">
        <p className="akki-overline mb-3">Akki for {account?.name || "you"}</p>
        <h1 className="akki-serif text-[40px] sm:text-[52px] leading-[1.08] tracking-[-0.018em] text-[var(--ink)] mb-5 font-normal max-w-[24ch]">
          Tell AKKI whether you sit in the boardroom, run the business, or both.
        </h1>
        <p className="akki-serif text-[16.5px] leading-[1.7] text-[var(--deep)] max-w-[58ch] mb-10">
          AKKI shapes the home page, default surfaces, and Cycle Manager defaults around what you
          actually do. You can change this anytime from the avatar menu → Settings.
        </p>

        {/* Phase M.1 — "Running the business" Quick Action. Even before
            the user picks a role, uploading a board pack is a useful
            first move; AKKI can read it and use it to seed signals. */}
        <section className="mb-10" data-testid="home-undeclared-running-the-business">
          <h2 className="akki-serif text-[18px] text-[var(--ink)] inline-flex items-center gap-2 mb-3">
            <Briefcase className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Running the business
          </h2>
          <div className="max-w-[560px]">
            <AddDocumentCard />
          </div>
        </section>

        <div className="grid sm:grid-cols-2 gap-3 max-w-[560px]">
          <button
            onClick={() => declare("ned")}
            disabled={!!busy}
            className="text-left p-5 border border-[var(--rule)] hover:border-[var(--accent)]/40 hover:bg-[var(--cream-deep)]/30 rounded-md transition-colors"
            data-testid="home-undeclared-ned"
          >
            <div className="flex items-center gap-2 mb-2">
              <Landmark className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} />
              <p className="akki-serif text-[18px] text-[var(--ink)]">I'm a NED</p>
            </div>
            <p className="text-[12.5px] text-[var(--muted)] leading-snug">
              I sit on boards as a non-executive director. My time on AKKI is mostly catching up
              between meetings.
            </p>
          </button>
          <button
            onClick={() => declare("executive")}
            disabled={!!busy}
            className="text-left p-5 border border-[var(--rule)] hover:border-[var(--accent)]/40 hover:bg-[var(--cream-deep)]/30 rounded-md transition-colors"
            data-testid="home-undeclared-executive"
          >
            <div className="flex items-center gap-2 mb-2">
              <Briefcase className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} />
              <p className="akki-serif text-[18px] text-[var(--ink)]">I run the business</p>
            </div>
            <p className="text-[12.5px] text-[var(--muted)] leading-snug">
              CEO, ExCo member, or running a function. Decks, briefings, and the operating cycle
              are my default home.
            </p>
          </button>
          <button
            onClick={() => declare("dual")}
            disabled={!!busy}
            className="text-left p-5 border border-[var(--rule)] hover:border-[var(--accent)]/40 hover:bg-[var(--cream-deep)]/30 rounded-md transition-colors sm:col-span-2"
            data-testid="home-undeclared-dual"
          >
            <div className="flex items-center gap-2 mb-2">
              <Briefcase className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} />
              <Landmark className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} />
              <p className="akki-serif text-[18px] text-[var(--ink)]">Both — I do executive work and I sit on boards.</p>
            </div>
            <p className="text-[12.5px] text-[var(--muted)] leading-snug">
              Common in founder-led growth, family business, and post-IPO transitions. AKKI splits
              the home so neither side gets buried.
            </p>
          </button>
        </div>
        <p className="text-[11px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mt-10">
          Want the full first-session intake?{" "}
          <button onClick={() => navigate("/app/first-session")} className="underline underline-offset-4 text-[var(--deep)] hover:text-[var(--ink)]">
            Run that instead
          </button>
          .
        </p>
        {busy && (
          <div className="flex items-center gap-2 mt-6 text-[12px] text-[var(--muted)]">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving …
          </div>
        )}
      </div>
    </AppShell>
  );
}
