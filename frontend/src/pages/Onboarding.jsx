import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowRight, Landmark, Briefcase, Layers } from "lucide-react";
import { toast } from "sonner";

const ART = "https://static.prod-images.emergentagent.com/jobs/0441d610-5908-43db-b746-3ec05187ba11/images/45ea328e6111fa06c7b3530f0bd66291c809bf1519364c126f09302bc02b65f2.png";

const ROLES = [
  {
    value: "ned",
    title: "Non-Executive Director",
    subtitle: "You serve on one or more boards as a NED.",
    icon: Landmark,
    features: [
      "Board cards with pack status and urgent flags",
      "Cross-Board Pulse across your personal boards",
      "Open Threads from minutes & briefings",
    ],
  },
  {
    value: "executive",
    title: "Operating Executive",
    subtitle: "You report into a board or lead an operating team.",
    icon: Briefcase,
    features: [
      "Next board meeting + Pre-Board Prep flow",
      "Direct reports and organisation Highlights",
      "Post-Board Follow-up tracking",
    ],
  },
  {
    value: "dual",
    title: "Both — NED and Executive",
    subtitle: "You hold both roles. Switch any time.",
    icon: Layers,
    features: [
      "Persistent role switcher top-right",
      "Context-primary data isolation between roles",
      "Cross-role Ask threads (personal contexts only)",
    ],
  },
];

export default function Onboarding() {
  const { account, bootstrap } = useAuth();
  const navigate = useNavigate();
  const [selected, setSelected] = useState(
    account?.declared_role && account.declared_role !== "undeclared" ? account.declared_role : null
  );
  const [busy, setBusy] = useState(false);

  const isDeclared = account?.declared_role && account.declared_role !== "undeclared";

  const declare = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await api.post("/auth/declare-role", { declared_role: selected });
      await bootstrap();
      toast.success("Role declared");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <AppShell>
      <div className="p-8 md:p-12 max-w-5xl mx-auto">
        <div className="mb-10">
          <p className="akki-overline mb-3">Module M2 · Board-focused audit</p>
          <h1 className="text-4xl font-light tracking-tight text-[#0A1F44] mb-3">
            {isDeclared ? "Your role is set." : "Declare your role."}
          </h1>
          <p className="text-base text-slate-500 max-w-2xl leading-relaxed">
            {isDeclared
              ? `You're registered as ${account.declared_role === "dual" ? "NED + Executive" : account.declared_role}. The 7-question audit that tunes AKKI to your boards and reports ships with the next module build.`
              : "Choose how you act — this shapes your Home, your suggested onboarding questions, and which surfaces are emphasised."}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-10">
          {ROLES.map((r) => {
            const I = r.icon;
            const active = selected === r.value;
            return (
              <button
                key={r.value}
                type="button"
                onClick={() => !isDeclared && setSelected(r.value)}
                disabled={isDeclared}
                className={`text-left border p-6 rounded-sm transition-all disabled:opacity-60 disabled:cursor-not-allowed ${active ? "border-[#C9A961] bg-amber-50/30 ring-1 ring-[#C9A961]/40 -translate-y-0.5 shadow-sm" : "border-[#E1E6ED] bg-white hover:border-slate-300"}`}
                data-testid={`role-option-${r.value}`}
              >
                <I className={`w-5 h-5 mb-4 ${active ? "text-[#C9A961]" : "text-slate-400"}`} strokeWidth={1.6} />
                <p className="text-sm font-medium text-[#0A1F44] mb-1">{r.title}</p>
                <p className="text-xs text-slate-500 leading-relaxed mb-4">{r.subtitle}</p>
                <ul className="space-y-1.5">
                  {r.features.map((f) => (
                    <li key={f} className="text-[11px] text-slate-500 flex items-start gap-2">
                      <span className={`mt-1.5 w-1 h-1 rounded-full ${active ? "bg-[#C9A961]" : "bg-slate-300"}`} />
                      {f}
                    </li>
                  ))}
                </ul>
              </button>
            );
          })}
        </div>

        {!isDeclared && (
          <Button
            onClick={declare}
            disabled={!selected || busy}
            className="bg-[#0A1F44] hover:bg-[#0E2958] rounded-sm h-11 px-6 group"
            data-testid="declare-role-btn"
          >
            {busy ? "Saving…" : "Confirm role"}
            {!busy && <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />}
          </Button>
        )}

        {/* Next-steps teaser */}
        <div className="relative overflow-hidden bg-[#0A1F44] text-white rounded-sm border border-[#0A1F44] mt-14">
          <div
            className="absolute right-0 top-0 w-[540px] h-full opacity-45"
            style={{ backgroundImage: `url(${ART})`, backgroundSize: "cover", backgroundPosition: "center" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0A1F44] via-[#0A1F44]/95 to-[#0A1F44]/50" />
          <div className="relative z-10 px-10 py-12 max-w-2xl">
            <p className="akki-overline mb-3">Coming in the next build</p>
            <h2 className="text-2xl font-light tracking-tight mb-4">
              Seven questions. One <span className="text-[#C9A961]">Context Object.</span>
            </h2>
            <p className="text-white/65 leading-relaxed mb-6">
              Role-specific audit questions will establish industry, jurisdiction, board cadence,
              reportee scope, and data trust ratings. The answers flow into every Highlight,
              Ask response, and Lens Room session.
            </p>
            <Link to="/app">
              <Button className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-11 px-6 font-medium" data-testid="back-to-home-btn">
                Back to home <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
