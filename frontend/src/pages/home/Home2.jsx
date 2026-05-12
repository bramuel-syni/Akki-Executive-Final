/**
 * Home2 — Active-context home. Patch 3.
 *
 * Sections (vertical):
 *   1. Greeting band (time-of-day + welcome back to {company})
 *   2. Hero copy band — existing "Run the business on the left.…" headline
 *   3. HeroDocActions (Patch 2A; preserved)
 *   4. Leading-insight Quick Action cards — 7 cards, real backend counts
 *   5. What's new since last visit feed
 *   6. Running-the-business / Sitting-on-the-boards split — preserved from
 *      HomeDual.jsx (the closest existing pattern).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import HeroDocActions from "@/components/home/HeroDocActions";
import ExcoTeamsCard from "@/components/home/ExcoTeamsCard";
import { Button } from "@/components/ui/button";
import {
  Files, AlertTriangle, Briefcase, CheckCircle2, Calendar,
  Plus, MessageSquare, ChevronRight, History, ArrowLeft, ArrowRight, Sparkles,
} from "lucide-react";


function greetingFor(date = new Date()) {
  const h = date.getHours();
  if (h < 5)  return "Good night";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 21) return "Good evening";
  return "Good night";
}

function relTime(iso) {
  if (!iso) return "—";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return "moments ago";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch { return "—"; }
}


// Card config — key matches the backend insights map.
// `urgency` drives the default order; `count_weight` was set per spec.
const CARD_CONFIG = {
  pulse_critical: {
    title: "Pulse alerts", icon: AlertTriangle, urgency: 6,
    template: (n) => `${n} critical update${n === 1 ? "" : "s"}`,
    href: "/app/pulse",
  },
  signoffs_needed: {
    title: "Sign-offs needed", icon: CheckCircle2, urgency: 5,
    template: (n) => `${n} item${n === 1 ? "" : "s"} awaiting your decision`,
    href: "/app/ned-inbox",
  },
  cycles_closing: {
    title: "Cycles closing this week", icon: Calendar, urgency: 4,
    template: (n) => `${n} to ship`,
    href: "/app/cycle",
  },
  compile_ready: {
    title: "Compile report", icon: Files, urgency: 3,
    template: (n) => `${n} agenda${n === 1 ? "" : "s"} at ≥80% readiness`,
    href: "/app/work-studio",
    isCompileWizard: true,
  },
  open_questions: {
    title: "Open questions", icon: MessageSquare, urgency: 2,
    template: (n) => `${n} from NEDs awaiting your response`,
    href: "/app/questions?filter=open",
  },
  solva_waiting: {
    title: "Solva sessions waiting", icon: Sparkles, urgency: 1,
    template: (n) => `${n} draft${n === 1 ? "" : "s"} ready for review`,
    href: "/app/solva",
  },
  new_documents: {
    title: "New documents", icon: Plus, urgency: 0,
    template: (n) => `${n} added since your last visit by team`,
    href: "/app/work-studio?since=last_visit",
  },
};


// Patch 17 — Continue-onboarding band (parity preserve from
// legacy HomeExecutive.jsx). Renders only when the account's
// first-session journey is still open (NOT completed AND NOT
// skipped). Gated this way so we don't pester returning users
// who explicitly chose to skip.
function ContinueOnboardingBand({ account, navigate }) {
  const status = account?.first_session?.status;
  if (status === "completed" || status === "skipped") return null;
  return (
    <div
      className="mt-8 mb-2 bg-white border border-[var(--rule)] rounded-md p-6 relative overflow-hidden"
      data-testid="home2-continue-onboarding"
    >
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
      <p className="akki-overline mb-2">Next · 7 minutes</p>
      <h3 className="akki-serif text-[20px] mb-2 text-[var(--ink)] leading-snug">
        Finish your profile to start receiving signals.
      </h3>
      <p className="akki-meta max-w-2xl mb-5">
        Seven role-specific questions establish your profile — the foundation for every signal,
        briefing, and lens session AKKI runs on your behalf.
      </p>
      <Button
        onClick={() => navigate("/app/first-session")}
        className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-9 px-4 font-medium"
        data-testid="home2-continue-onboarding-cta"
        aria-label="Continue onboarding"
      >
        Continue onboarding <ArrowRight className="w-4 h-4 ml-2" />
      </Button>
    </div>
  );
}


function InsightCard({ keyName, count, onClick }) {  const cfg = CARD_CONFIG[keyName];
  if (!cfg) return null;
  const Icon = cfg.icon;
  const muted = count === 0;
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "text-left border rounded-sm px-4 py-3.5 bg-white transition-colors",
        muted
          ? "border-[var(--rule)] opacity-60 hover:opacity-80"
          : "border-[var(--rule)] hover:border-[var(--ink)]",
      ].join(" ")}
      data-testid={`home2-insight-${keyName}`}
    >
      <div className="flex items-start gap-3">
        <Icon className="w-4 h-4 text-[var(--deep)] mt-0.5" strokeWidth={1.7} />
        <div className="flex-1 min-w-0">
          <p className="akki-serif text-[15px] text-[var(--ink)] leading-tight">{cfg.title}</p>
          <p className="text-[12.5px] text-[var(--muted)] mt-1 leading-snug">
            {cfg.template(count)}
          </p>
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0 mt-1" />
      </div>
    </button>
  );
}


export default function Home2() {
  const { account, activeContext } = useAuth();
  const navigate = useNavigate();

  const cid = activeContext?.id;
  const isAdmin =
    activeContext?.my_sub_role === "admin" ||
    activeContext?.owner_account_id === account?.id;

  // Patch 28A — role-sensitive hero copy on Home 2.
  // The user's role on THIS active context is what matters here —
  // not the user's portfolio-level mix. We honour 3 variants:
  //   1. EXECUTIVE — operator framing
  //   2. NED — board framing
  //   3. DUAL — both seats on the same workspace (rare; keeps the
  //      original "side by side" framing).
  const roleHeroCopy = useMemo(() => {
    const role = (activeContext?.my_role || "").toLowerCase();
    const subRole = (activeContext?.my_sub_role || "").toLowerCase();
    const isExec = role === "executive" || role === "owner" || subRole === "executive";
    const isNed = role === "ned" || role === "non_executive_director" || role === "non-executive-director";
    if (isExec && isNed) {
      return {
        headline: "Two roles, one calm view.",
        sub: "AKKI keeps your operating cadence and your board cadence side by side.",
      };
    }
    if (isNed) {
      return {
        headline: "Sit on your boards with confidence.",
        sub: "Briefs, questions, and sign-offs — surfaced where you need them.",
      };
    }
    // Default = executive framing (covers explicit Executive role +
    // unrecognised role strings which historically defaulted to the
    // operator side).
    return {
      headline: "Run your business with clarity.",
      sub: "Cycles, signals, and decisions — all kept in one calm view.",
    };
  }, [activeContext?.my_role, activeContext?.my_sub_role]);

  const [insights, setInsights] = useState(null);
  const [whatsNew, setWhatsNew] = useState([]);
  const [loaded, setLoaded] = useState(false);

  // Fetch the insight counts (which records the visit as a side-effect).
  // Then fetch what's-new using the previous-visit timestamp that the
  // /home/insights endpoint returns.
  useEffect(() => {
    if (!activeContext?.id) return;
    let dead = false;
    api.get(`/contexts/${activeContext.id}/home/insights`)
      .then(({ data }) => {
        if (dead) return;
        setInsights(data);
        const since = data.previous_visit_at;
        return api.get(`/contexts/${activeContext.id}/home/whats-new`, {
          params: since ? { since } : {},
        });
      })
      .then((resp) => { if (!dead && resp) setWhatsNew(resp.data?.items || []); })
      .catch(() => { if (!dead) setInsights({ insights: {} }); })
      .finally(() => { if (!dead) setLoaded(true); });
    return () => { dead = true; };
  }, [activeContext?.id]);

  // Order the 7 cards by score = count * 1 + urgency. Cards with count 0
  // still render but at the end (urgency-only).
  // Patch 28B — role-sensitive card visibility. NEDs see a subset
  // tuned to board work (no `compile_ready`, no `new_documents` since
  // those are operator-facing). The `open_questions` template rewrites
  // to reflect the answer-side for NEDs.
  const isNedRole = useMemo(() => {
    const r = (activeContext?.my_role || "").toLowerCase();
    return r === "ned" || r === "non_executive_director" || r === "non-executive-director";
  }, [activeContext?.my_role]);

  const orderedCards = useMemo(() => {
    const map = insights?.insights || {};
    const NED_KEYS = ["signoffs_needed", "open_questions", "pulse_critical", "cycles_closing", "solva_waiting"];
    const allKeys = Object.keys(CARD_CONFIG);
    const keys = isNedRole ? allKeys.filter((k) => NED_KEYS.includes(k)) : allKeys;
    return keys
      .map((k) => ({
        key: k,
        count: (map[k]?.count) ?? 0,
        urgency: CARD_CONFIG[k].urgency,
      }))
      .sort((a, b) => {
        const score = (r) => (r.count > 0 ? (r.urgency + r.count * 2 + 10) : r.urgency);
        return score(b) - score(a);
      });
  }, [insights]);

  const greeting = useMemo(() => greetingFor(new Date()), []);
  const firstName = (account?.display_name || account?.name || "").split(" ")[0] || "there";

  const onCardClick = (keyName) => {
    const cfg = CARD_CONFIG[keyName];
    if (!cfg) return;
    if (cfg.isCompileWizard) {
      navigate("/app/work-studio?compile=1");
      return;
    }
    navigate(cfg.href);
  };

  const onBackToPortfolio = () => {
    // Switching to "no active context" is approximated by going to
    // /app/portfolio (Home1). We keep the same active context so users
    // don't lose their state — Home1 just shows the portfolio.
    navigate("/app/portfolio");
  };

  if (!activeContext) {
    return (
      <AppShell>
        <div className="p-12 text-center text-[var(--muted)] text-sm">No active company.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-12" data-testid="home2">
        {/* 1. Greeting band */}
        <section className="mb-2" data-testid="home2-greeting">
          <p className="akki-overline mb-1 flex items-center gap-2">
            <span>{activeContext.name}</span>
            <button
              onClick={onBackToPortfolio}
              className="inline-flex items-center gap-1 text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] hover:text-[var(--ink)]"
              data-testid="home2-back-to-portfolio"
            >
              <ArrowLeft className="w-3 h-3" strokeWidth={1.7} /> Back to portfolio
            </button>
          </p>
          <h1 className="akki-greeting">{greeting}, {firstName}.</h1>
          <p className="akki-meta mt-1">
            Welcome back to {activeContext.name}.
            {insights?.previous_visit_at && (
              <> Last seen here {relTime(insights.previous_visit_at)}.</>
            )}
          </p>
        </section>

        {/* Patch 17 — Continue-onboarding band (parity from HomeExecutive).
            Renders only when account.first_session is open. */}
        <ContinueOnboardingBand account={account} navigate={navigate} />

        {/* 2. Hero copy band — Patch 28A role-sensitive */}
        <section className="mt-8 mb-6" data-testid="home2-hero-copy" data-role={(activeContext?.my_role || "").toLowerCase()}>
          <h2 className="akki-serif text-[24px] text-[var(--ink)] leading-tight mb-2 font-normal" data-testid="home2-hero-headline">
            {roleHeroCopy.headline}
          </h2>
          <p className="akki-meta max-w-2xl" data-testid="home2-hero-sub">
            {roleHeroCopy.sub}
          </p>
        </section>

        {/* 3. HeroDocActions — preserved from Patch 2A */}
        <HeroDocActions />

        {/* 4. Leading-insight Quick Action cards — 7, dynamic order */}
        <section className="mt-10" data-testid="home2-insights">
          <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3">What's on your plate</h2>
          {!loaded ? (
            <p className="akki-meta italic">Reading the room…</p>
          ) : (
            <div className="grid sm:grid-cols-2 gap-3" data-testid="home2-insights-grid">
              {orderedCards.map((c) => (
                <InsightCard
                  key={c.key}
                  keyName={c.key}
                  count={c.count}
                  onClick={() => onCardClick(c.key)}
                />
              ))}
            </div>
          )}
        </section>

        {/* 5. What's new since last visit */}
        <section className="mt-12" data-testid="home2-whats-new">
          <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3 inline-flex items-center gap-2">
            <History className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> What's new since your last visit
          </h2>
          {whatsNew.length === 0 ? (
            <p className="akki-meta italic" data-testid="home2-whats-new-empty">
              You're all caught up since your last visit.
            </p>
          ) : (
            <ul className="space-y-2" data-testid="home2-whats-new-list">
              {whatsNew.map((it, i) => (
                <li
                  key={`${it.kind}-${it.ts}-${i}`}
                  className="border-l-2 border-[var(--rule)] pl-3 py-1"
                  data-testid={`home2-whats-new-${i}`}
                >
                  <button
                    type="button"
                    onClick={() => it.href && navigate(it.href)}
                    className="text-left w-full"
                  >
                    <p className="text-[13.5px] text-[var(--ink)] leading-snug">{it.label}</p>
                    <p className="text-[11px] text-[var(--muted)] font-mono mt-0.5">
                      {relTime(it.ts)} · {it.kind.replace(/_/g, " ")}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 6. Footer — Running the business / Sitting on the boards split */}
        <section className="mt-12 grid lg:grid-cols-2 gap-4" data-testid="home2-footer-split">
          <button
            onClick={() => navigate("/app/work-studio")}
            className="text-left border border-[var(--rule)] rounded-sm bg-white px-5 py-4 hover:border-[var(--ink)]"
            data-testid="home2-footer-running"
          >
            <div className="flex items-center gap-2 mb-1">
              <Briefcase className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} />
              <p className="akki-serif text-[16px] text-[var(--ink)]">Running the business</p>
            </div>
            <p className="text-[12.5px] text-[var(--muted)] leading-snug">
              Work Studio · Cycle Manager · Briefings.
            </p>
          </button>
          <button
            onClick={() => navigate("/app/ned-inbox")}
            className="text-left border border-[var(--rule)] rounded-sm bg-white px-5 py-4 hover:border-[var(--ink)]"
            data-testid="home2-footer-boards"
          >
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} />
              <p className="akki-serif text-[16px] text-[var(--ink)]">Sitting on the boards</p>
            </div>
            <p className="text-[12.5px] text-[var(--muted)] leading-snug">
              NED inbox · pending packs · open questions.
            </p>
          </button>
        </section>

        {/* Patch 17 — ExCo teams card parity (was on HomeDual + HomeExecutive).
            Renders the admin-only ExCo teams grouping function. */}
        <ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />
      </div>
    </AppShell>
  );
}
