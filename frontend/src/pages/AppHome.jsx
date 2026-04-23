import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import NedHome from "@/pages/NedHome";
import ExecHome from "@/pages/ExecHome";
import { ArrowRight, Landmark, Briefcase, Sparkles } from "lucide-react";

const ART = "https://static.prod-images.emergentagent.com/jobs/0441d610-5908-43db-b746-3ec05187ba11/images/45ea328e6111fa06c7b3530f0bd66291c809bf1519364c126f09302bc02b65f2.png";

/**
 * Role-routing Home:
 *  - Before onboarding: shows audit CTA hero
 *  - After onboarding: renders NedHome or ExecHome based on activeRole
 */
export default function AppHome() {
  const { account, activeContext, activeRole } = useAuth();
  const isDeclared = account?.declared_role && account.declared_role !== "undeclared";
  const auditComplete = !!activeContext?.progress_state?.onboarding_completed;
  const contextObjectVersion = activeContext?.progress_state?.context_object_version;
  const firstName = (account?.name || "executive").split(" ")[0];
  const isNED = activeRole === "ned";
  const RoleIcon = isNED ? Landmark : Briefcase;

  // Always-visible welcome header
  const welcome = (
    <div className="mb-8 akki-fade-up" data-testid="home-welcome">
      <div className="flex items-center gap-2 mb-3">
        <p className="akki-overline">Home · {activeContext?.name || "—"}</p>
        <span className="text-slate-300">·</span>
        <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-[#C9A961]">
          <RoleIcon className="w-3 h-3" strokeWidth={2} />
          Acting as {isNED ? "Non-Executive Director" : "Executive"}
        </span>
      </div>
      <h1 className="text-3xl md:text-4xl font-light tracking-tight text-[#0A1F44] mb-2">
        Good day, <span className="text-[#0A1F44]">{firstName}.</span>
      </h1>
      <p className="text-sm text-slate-500 max-w-2xl">
        {!isDeclared
          ? "Your workspace is ready. Declare your role and run the 7-question audit to unlock signals and briefings."
          : !auditComplete
            ? "Your role is set. Complete the 7-question audit to finalise your Context Object."
            : isNED
              ? "Your boards, open threads, and cross-board patterns are summarised below. Upload a pack to let AKKI surface signals."
              : "Your upcoming meeting, team reporting, and organisation highlights are summarised below."}
      </p>
      {auditComplete && (
        <div className="mt-5 inline-flex items-center gap-3 bg-white border border-[#C9A961]/40 rounded-sm px-4 py-2" data-testid="context-object-status">
          <Sparkles className="w-4 h-4 text-[#C9A961]" strokeWidth={1.7} />
          <p className="text-[12px] text-[#0A1F44]">
            Context Object <span className="text-[#C9A961] font-mono">v{contextObjectVersion || 1}</span> · active
          </p>
          <span className="text-slate-300">·</span>
          <Link to="/onboarding" className="text-[11px] text-[#C9A961] hover:underline" data-testid="review-audit-btn">
            Review answers
          </Link>
        </div>
      )}
    </div>
  );

  // Pre-onboarding state: show the big audit hero instead of role-specific home
  if (!isDeclared || !auditComplete) {
    return (
      <AppShell>
        <div className="p-8 max-w-7xl mx-auto">
          {welcome}
          <div className="relative overflow-hidden bg-[#0A1F44] text-white rounded-sm border border-[#0A1F44]">
            <div
              className="absolute right-0 top-0 w-[420px] h-full opacity-40"
              style={{ backgroundImage: `url(${ART})`, backgroundSize: "cover", backgroundPosition: "center" }}
            />
            <div className="absolute inset-0 bg-gradient-to-r from-[#0A1F44] via-[#0A1F44]/95 to-[#0A1F44]/60" />
            <div className="relative z-10 px-10 py-12 max-w-3xl">
              <div className="flex items-center gap-2 mb-5">
                <span className="akki-overline">Next · 7 minutes</span>
                <span className="text-white/20">·</span>
                <span className="text-[10px] uppercase tracking-[0.2em] text-white/40">Module M2</span>
              </div>
              <h2 className="text-3xl font-light tracking-tight mb-4">
                {!isDeclared
                  ? <>Declare your role. Run the <span className="text-[#C9A961]">board-focused audit.</span></>
                  : <>Finish the <span className="text-[#C9A961]">board-focused audit.</span></>}
              </h2>
              <p className="text-white/65 leading-relaxed mb-8 max-w-xl">
                Seven role-specific questions establish your Context Object — the foundation for every signal, briefing, and lens session.
              </p>
              <Link to="/onboarding">
                <Button className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-11 px-6 font-medium" data-testid="start-onboarding-btn">
                  {!isDeclared ? "Begin audit" : "Resume audit"} <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  // Role-specific home
  return (
    <AppShell>
      {isNED ? <NedHome welcome={welcome} /> : <ExecHome welcome={welcome} />}
    </AppShell>
  );
}
