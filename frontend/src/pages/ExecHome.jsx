import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  CalendarDays, Users, FileText, Sparkles, ArrowRight, CheckCircle2,
  Clock, AlertTriangle, TrendingUp, CircleSlash, ShieldCheck, Briefcase,
  MessageSquareText, ScrollText,
} from "lucide-react";

function daysUntilNextMeeting(id) {
  let h = 0;
  for (let i = 0; i < (id || "").length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return (h % 21) + 1;
}
function formatMeetingDate(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

const TYPE_ICON = { risk: AlertTriangle, opportunity: TrendingUp, gap: CircleSlash };
const TYPE_CLS = {
  risk: "bg-red-50 text-red-700 border-red-200",
  opportunity: "bg-emerald-50 text-emerald-700 border-emerald-200",
  gap: "bg-amber-50 text-amber-700 border-amber-200",
};
const TRUST_COLOR = {
  trusted: "text-emerald-700",
  mixed: "text-amber-700",
  weak: "text-red-700",
  unrated: "text-slate-500",
};

export default function ExecHome({ welcome }) {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [docs, setDocs] = useState([]);
  const [signals, setSignals] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!contextId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [d, s, m] = await Promise.all([
          api.get(`/contexts/${contextId}/documents`),
          api.get(`/contexts/${contextId}/signals`),
          api.get(`/contexts/${contextId}/members`),
        ]);
        if (!cancelled) {
          setDocs(d.data || []);
          setSignals(s.data || []);
          setMembers(m.data || []);
        }
      } catch {
        // silent — empty bands will show
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [contextId]);

  // Cadence detection — drives visual weighting of the 4 bands
  const daysToMeeting = contextId ? daysUntilNextMeeting(contextId) : 14;
  const meetingDate = formatMeetingDate(daysToMeeting);
  const cadenceState = daysToMeeting <= 7 ? "approaching" : daysToMeeting <= 14 ? "mid-cycle" : "post-meeting";

  const highlightSignals = useMemo(() => signals.slice(0, 3), [signals]);
  const reportees = useMemo(
    () => members.filter((m) => m.role === "reportee" || m.sub_role === "reportee").slice(0, 4),
    [members]
  );
  const packReady = docs.length > 0;

  if (!contextId) {
    return (
      <div className="p-12 text-center text-sm text-slate-500">
        No context selected. Use the context switcher at the top right.
      </div>
    );
  }

  // Ordering / weighting by cadence:
  // approaching → Pre-Board Prep largest, then Team Reporting, Org Highlights, Follow-up
  // mid-cycle   → Org Highlights largest, then Team Reporting, Pre-Board Prep, Follow-up
  // post-meeting→ Follow-up largest, then Org Highlights, Team Reporting, Pre-Board Prep
  const bandOrder = {
    approaching: ["prep", "team", "org", "followup"],
    "mid-cycle": ["org", "team", "prep", "followup"],
    "post-meeting": ["followup", "org", "team", "prep"],
  }[cadenceState];

  const bands = {
    prep: (
      <section
        key="prep"
        className="bg-white border border-[#E1E6ED] rounded-sm p-6"
        data-testid="band-prep"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Band 1 · Pre-Board Prep</p>
            <h3 className="text-lg font-medium tracking-tight text-[#0A1F44]">
              Next board meeting · <span className="text-[#C9A961]">{meetingDate}</span>
            </h3>
          </div>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border bg-[#0A1F44]/5 text-[#0A1F44] border-[#0A1F44]/20">
            <Clock className="w-3 h-3" /> in {daysToMeeting} day{daysToMeeting === 1 ? "" : "s"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-start gap-3 bg-slate-50/60 border border-[#E1E6ED] rounded-sm p-3">
            <FileText className="w-4 h-4 text-[#C9A961] mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-[#0A1F44]">Pack status</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {packReady ? `${docs.length} document${docs.length === 1 ? "" : "s"} uploaded` : "No pack yet"}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 bg-slate-50/60 border border-[#E1E6ED] rounded-sm p-3">
            <Sparkles className="w-4 h-4 text-[#C9A961] mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-[#0A1F44]">Signals</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {signals.length > 0 ? `${signals.length} ready to brief` : "Upload a pack to generate"}
              </p>
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <Link to="/app/workspace">
            <Button className="bg-[#0A1F44] hover:bg-[#0E2958] text-white rounded-sm h-9 text-sm" data-testid="prep-upload-btn">
              <FileText className="w-3.5 h-3.5 mr-1.5" /> {packReady ? "Update pack" : "Upload pack"}
            </Button>
          </Link>
          {packReady && (
            <Link to="/app/highlights">
              <Button variant="outline" className="rounded-sm h-9 text-sm border-[#E1E6ED]">
                <Sparkles className="w-3.5 h-3.5 mr-1.5 text-[#C9A961]" /> Generate signals
              </Button>
            </Link>
          )}
          {signals.length > 0 && (
            <Link to="/app/briefings">
              <Button variant="outline" className="rounded-sm h-9 text-sm border-[#E1E6ED]">
                <ScrollText className="w-3.5 h-3.5 mr-1.5 text-[#C9A961]" /> Compose briefing
              </Button>
            </Link>
          )}
        </div>
      </section>
    ),

    team: (
      <section
        key="team"
        className="bg-white border border-[#E1E6ED] rounded-sm p-6"
        data-testid="band-team"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Band 2 · Team Reporting</p>
            <h3 className="text-lg font-medium tracking-tight text-[#0A1F44]">Your team</h3>
          </div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400">
            {members.length} member{members.length === 1 ? "" : "s"}
          </span>
        </div>
        {reportees.length === 0 ? (
          <div className="bg-slate-50/60 border border-dashed border-[#E1E6ED] rounded-sm p-5 text-center">
            <Users className="w-6 h-6 text-slate-300 mx-auto mb-2" strokeWidth={1.5} />
            <p className="text-xs text-slate-500">
              Invite reportees from <Link to="/app/settings" className="text-[#C9A961] hover:underline">Settings</Link> to track their report submissions here.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {reportees.map((m) => (
              <div key={m.account_id} className="flex items-center gap-3 bg-slate-50/60 border border-[#E1E6ED] rounded-sm p-3">
                <div className="w-8 h-8 bg-[#0A1F44] text-[#C9A961] flex items-center justify-center rounded-sm text-xs font-semibold shrink-0">
                  {(m.name || m.email || "?").charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-[#0A1F44] truncate">{m.name || m.email}</p>
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">{m.role}</p>
                </div>
                <CheckCircle2 className="w-3.5 h-3.5 text-slate-300" title="Submission tracking — M6" />
              </div>
            ))}
          </div>
        )}
      </section>
    ),

    org: (
      <section
        key="org"
        className="bg-white border border-[#E1E6ED] rounded-sm p-6"
        data-testid="band-org"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Band 3 · Organisation Highlights</p>
            <h3 className="text-lg font-medium tracking-tight text-[#0A1F44]">
              {signals.length} live signal{signals.length === 1 ? "" : "s"} this cycle
            </h3>
          </div>
          <Link to="/app/highlights" className="text-[11px] text-[#C9A961] hover:underline inline-flex items-center gap-1">
            See all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        {highlightSignals.length === 0 ? (
          <p className="text-xs text-slate-500 italic bg-slate-50/60 border border-dashed border-[#E1E6ED] rounded-sm p-4 text-center">
            No signals yet. Upload a pack, then generate from Highlights.
          </p>
        ) : (
          <div className="space-y-2">
            {highlightSignals.map((s) => {
              const I = TYPE_ICON[s.type] || AlertTriangle;
              return (
                <Link
                  to="/app/highlights"
                  key={s.id}
                  className="block bg-slate-50/50 border border-[#E1E6ED] rounded-sm p-3 hover:border-[#C9A961]/60 transition-colors"
                  data-testid={`org-signal-${s.id}`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] font-medium uppercase tracking-wider border ${TYPE_CLS[s.type]}`}>
                      <I className="w-2.5 h-2.5" /> {s.type}
                    </span>
                    <span className={`text-[10px] uppercase tracking-wider ${TRUST_COLOR[s.data_trust]}`}>
                      <ShieldCheck className="w-2.5 h-2.5 inline mr-0.5" />
                      {s.data_trust || "unrated"}
                    </span>
                  </div>
                  <p className="text-xs font-medium text-[#0A1F44] line-clamp-2">{s.headline}</p>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    ),

    followup: (
      <section
        key="followup"
        className="bg-white border border-[#E1E6ED] rounded-sm p-6"
        data-testid="band-followup"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Band 4 · Post-Board Follow-up</p>
            <h3 className="text-lg font-medium tracking-tight text-[#0A1F44]">Actions owed</h3>
          </div>
          <span className="text-[10px] uppercase tracking-wider text-slate-400">Detected from minutes</span>
        </div>
        <div className="bg-slate-50/60 border border-dashed border-[#E1E6ED] rounded-sm p-5 text-center">
          <CheckCircle2 className="w-6 h-6 text-slate-300 mx-auto mb-2" strokeWidth={1.5} />
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Post-board actions are auto-extracted from uploaded minutes (M6 · Integrations). Until then, use{" "}
            <Link to="/app/ask" className="text-[#C9A961] hover:underline">Ask AKKI</Link>{" "}
            to list unresolved items from your latest minutes document.
          </p>
        </div>
      </section>
    ),
  };

  // Visual weight: first band spans 2 columns on lg
  return (
    <div className="p-8 max-w-7xl mx-auto" data-testid="exec-home">
      {welcome}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" data-testid={`exec-home-cadence-${cadenceState}`}>
        <div className="lg:col-span-2">{bands[bandOrder[0]]}</div>
        <div>{bands[bandOrder[1]]}</div>
        <div>{bands[bandOrder[2]]}</div>
        <div className="lg:col-span-2">{bands[bandOrder[3]]}</div>
      </div>
    </div>
  );
}
