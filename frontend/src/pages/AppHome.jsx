import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import {
  ArrowRight, FileText, Sparkles, MessageSquareText, GraduationCap,
  Lock, CalendarDays, Users, Landmark, Briefcase,
} from "lucide-react";

const ART = "https://static.prod-images.emergentagent.com/jobs/0441d610-5908-43db-b746-3ec05187ba11/images/45ea328e6111fa06c7b3530f0bd66291c809bf1519364c126f09302bc02b65f2.png";

const SURFACES = [
  { i: FileText, t: "Workspace", module: "M8", s: "Documents · Lens Room · Simulation" },
  { i: Sparkles, t: "Highlights", module: "M7", s: "Verified signals · Briefings · Recommendations" },
  { i: MessageSquareText, t: "Ask", module: "M7", s: "Persistent threads with source citations" },
  { i: GraduationCap, t: "Learn", module: "M9", s: "Role-tuned curriculum · Curated intelligence" },
];

const NED_PREVIEW = [
  { i: CalendarDays, t: "Board cards", s: "Each board, next meeting, pack status, urgent flags" },
  { i: Users, t: "Cross-Board Pulse", s: "Patterns across your personal boards (2+ contexts)" },
  { i: FileText, t: "Open Threads", s: "Unresolved items auto-detected from minutes & briefings" },
];

const EXEC_PREVIEW = [
  { i: CalendarDays, t: "Next board meeting", s: "Pack status · Pre-Board Prep entry" },
  { i: Users, t: "Direct reports", s: "Report submission status across your team" },
  { i: FileText, t: "Post-Board Follow-up", s: "Actions owed to the board, with owners and dates" },
];

export default function AppHome() {
  const { account, activeContext, activeRole } = useAuth();
  const isDeclared = account?.declared_role && account.declared_role !== "undeclared";
  const firstName = (account?.name || "executive").split(" ")[0];
  const isNED = activeRole === "ned";
  const preview = isNED ? NED_PREVIEW : EXEC_PREVIEW;
  const RoleIcon = isNED ? Landmark : Briefcase;

  return (
    <AppShell>
      <div className="p-8 max-w-7xl mx-auto">
        {/* Welcome */}
        <div className="mb-10 akki-fade-up">
          <div className="flex items-center gap-2 mb-3">
            <p className="akki-overline">Home · {activeContext?.name || "—"}</p>
            <span className="text-slate-300">·</span>
            <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] text-[#C9A961]">
              <RoleIcon className="w-3 h-3" strokeWidth={2} />
              Acting as {isNED ? "Non-Executive Director" : "Executive"}
            </span>
          </div>
          <h1 className="text-4xl font-light tracking-tight text-[#0A1F44] mb-3">
            Good day, <span className="text-[#0A1F44]">{firstName}.</span>
          </h1>
          <p className="text-base text-slate-500 max-w-2xl">
            {isDeclared
              ? isNED
                ? "Your boards, open threads, and cross-board patterns surface here. Upload a pack to let AKKI draft your briefing."
                : "Your next board meeting, team reports, and organisation Highlights surface here. Upload a draft pack to run pre-board prep."
              : "Your workspace is ready. Declare your role and run the 7-question audit to unlock Highlights and Briefings."}
          </p>
        </div>

        {/* Onboarding hero (role declaration + audit) */}
        {!isDeclared && (
          <div className="relative overflow-hidden bg-[#0A1F44] text-white rounded-sm border border-[#0A1F44] mb-12">
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
                Declare your role. Run the <span className="text-[#C9A961]">board-focused audit.</span>
              </h2>
              <p className="text-white/65 leading-relaxed mb-8 max-w-xl">
                Tell AKKI whether you act as a non-executive director, operating executive, or both.
                Seven questions establish your Context Object — the foundation for every signal,
                briefing, and lens session.
              </p>
              <Link to="/onboarding">
                <Button className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-11 px-6 font-medium" data-testid="start-onboarding-btn">
                  Begin audit <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Role-specific preview */}
        <div className="mb-12">
          <div className="flex items-end justify-between mb-5">
            <div>
              <p className="akki-overline mb-2">{isNED ? "NED Home" : "Executive Home"} · preview</p>
              <h3 className="text-xl font-medium tracking-tight text-[#0A1F44]">
                {isNED ? "Across your boards" : "Around this week's meeting"}
              </h3>
            </div>
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Unlocks at M6</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {preview.map(({ i: I, t, s }) => (
              <div
                key={t}
                className="relative bg-white border border-[#E1E6ED] rounded-sm p-6 hover:border-slate-300 transition-colors group"
                data-testid={`home-preview-${t.toLowerCase().replace(/\s+/g, "-")}`}
              >
                <div className="flex items-start justify-between mb-4">
                  <I className="w-5 h-5 text-slate-400 group-hover:text-[#C9A961] transition-colors" strokeWidth={1.5} />
                  <Lock className="w-3.5 h-3.5 text-slate-300" strokeWidth={1.8} />
                </div>
                <p className="text-[#0A1F44] font-medium mb-2">{t}</p>
                <p className="text-sm text-slate-500 leading-relaxed">{s}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Surfaces */}
        <div>
          <div className="flex items-end justify-between mb-5">
            <div>
              <p className="akki-overline mb-2">Surfaces</p>
              <h3 className="text-xl font-medium tracking-tight text-[#0A1F44]">One workspace, six disciplined surfaces</h3>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#E1E6ED] border border-[#E1E6ED]">
            {SURFACES.map(({ i: I, t, module, s }) => (
              <div
                key={t}
                className="bg-white p-6 hover:bg-slate-50/60 transition-colors cursor-not-allowed"
                data-testid={`surface-card-${t.toLowerCase()}`}
                title={`Unlocks at ${module}`}
              >
                <div className="flex items-start justify-between mb-4">
                  <I className="w-5 h-5 text-slate-400" strokeWidth={1.5} />
                  <Lock className="w-3 h-3 text-slate-300" strokeWidth={1.8} />
                </div>
                <p className="text-[#0A1F44] font-medium text-sm">{t}</p>
                <p className="text-xs text-slate-500 mt-1">{s}</p>
                <span className="inline-block mt-4 text-[9px] uppercase tracking-[0.25em] text-slate-400">{module}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
