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
  Files, AlertTriangle, ClipboardCheck,
  MessageSquare, ChevronRight, History, ArrowLeft, ArrowRight, Mail,
  Calendar,
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


// Phase B Home cleanup (2026-05-26).  ── Plate redesign ──
// The legacy 6-tile mix (Pulse alerts / Sign-offs / Cycles closing /
// Compile report / Open questions / Solva sessions waiting) has been
// replaced by a 5-tile set rendered in this exact order:
//
//   1. drafts_ready        → cycle_followups (status ∈ {draft, approved})
//   2. compile_ready       → cycles (active + readiness_pct ≥ 80)
//   3. pulse_critical      → signals (severity = critical, open)
//   4. open_questions      → cycle_questions (assigned to me, open)
//   5. documents_to_review → DATA-SOURCE TODO (see HOME_CLEANUP_LOG.md)
//
// All counts come from /api/contexts/{cid}/home/insights — server-side
// keys preserved verbatim so existing tests + consumers stay green.
const CARD_CONFIG = {
  drafts_ready: {
    title: "Drafts Ready For You", icon: Mail, urgency: 6,
    template: (n) => `${n} draft${n === 1 ? "" : "s"} ready for review`,
    href: "/app/cycle?tab=drafts",
  },
  compile_ready: {
    title: "Reports Ready to Compile", icon: Files, urgency: 5,
    template: (n) => `${n} report${n === 1 ? "" : "s"} ready to compile`,
    href: "/app/work-studio",
    isCompileWizard: true,
  },
  pulse_critical: {
    title: "New Pulse Updates", icon: AlertTriangle, urgency: 4,
    template: (n) => `${n} new pulse update${n === 1 ? "" : "s"}`,
    href: "/app/pulse",
  },
  open_questions: {
    title: "Open Questions", icon: MessageSquare, urgency: 3,
    template: (n) => `${n} open question${n === 1 ? "" : "s"}`,
    href: "/app/questions?filter=open",
  },
  documents_to_review: {
    title: "Documents to Review", icon: ClipboardCheck, urgency: 2,
    template: (n) => `${n} document${n === 1 ? "" : "s"} to review`,
    href: null, // DATA-SOURCE TODO — disabled until wired.
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
  // Phase B Home cleanup — disabled-state for DATA-SOURCE TODO tiles
  // (cfg.href === null). Cursor + chevron are suppressed so the tile
  // reads as "informational only, no destination yet" without faking
  // a link.
  const disabled = !cfg.href;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        "text-left border rounded-sm px-4 py-3.5 bg-white transition-colors",
        muted
          ? "border-[var(--rule)] opacity-60"
          : "border-[var(--rule)]",
        disabled ? "cursor-default" : "hover:border-[var(--ink)] hover:opacity-100",
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
        {!disabled && (
          <ChevronRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0 mt-1" />
        )}
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

  // Phase B Home cleanup (2026-05-26): plate ordering is FIXED per
  // brief (not score-based). Cards still render with their count
  // (or 0 if the data source is unwired / returns no rows).
  // NED-specific subsetting from Patch 28B is dropped — the new
  // 5-tile set is universal per the user's directive.
  const PLATE_ORDER = [
    "drafts_ready",
    "compile_ready",
    "pulse_critical",
    "open_questions",
    "documents_to_review",
  ];
  const orderedCards = useMemo(() => {
    const map = insights?.insights || {};
    return PLATE_ORDER.map((k) => ({
      key: k,
      count: (map[k]?.count) ?? 0,
      urgency: CARD_CONFIG[k].urgency,
    }));
  }, [insights]);

  // Phase B Home cleanup — Coming up section data.
  const [comingUp, setComingUp] = useState([]);
  const [comingUpLoaded, setComingUpLoaded] = useState(false);
  useEffect(() => {
    if (!activeContext?.id) return;
    let dead = false;
    api.get(`/contexts/${activeContext.id}/home/coming-up`, { params: { days: 14 } })
      .then(({ data }) => { if (!dead) setComingUp(data?.items || []); })
      .catch(() => { if (!dead) setComingUp([]); })
      .finally(() => { if (!dead) setComingUpLoaded(true); });
    return () => { dead = true; };
  }, [activeContext?.id]);

  const greeting = useMemo(() => greetingFor(new Date()), []);
  const firstName = (account?.display_name || account?.name || "").split(" ")[0] || "there";

  const onCardClick = (keyName) => {
    const cfg = CARD_CONFIG[keyName];
    if (!cfg) return;
    // Phase B Home cleanup — DATA-SOURCE TODO tiles (href === null)
    // are no-op buttons; do not fake a navigation.
    if (!cfg.href) return;
    if (cfg.isCompileWizard) {
      navigate("/app/work-studio?compile=1");
      return;
    }
    navigate(cfg.href);
  };

  const onBackToPortfolio = () => {
    // Phase H.5 (2026-05-27) — `/app/portfolio` redirects to `/app`,
    // where the AppHome dispatcher's no-active-context branch renders
    // the new Portfolio Landing. We keep the same activeContext so the
    // user doesn't lose their state — to truly clear it, the user
    // taps a different company in the right rail.
    navigate("/app");
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
        {/* Chunk 6.5-REVISED (2026-05-13, Task B), revised by Phase B
            Home cleanup (2026-05-26):
            Hero (sections 1-3) and Plate (section 4) sit side-by-side
            at ≥1100px. Phase B widens the plate column from 2fr/3fr to
            3fr/2fr giving "What's on your plate" ~60% of the
            horizontal — was ~33% / 40% before. Below the breakpoint
            the grid collapses to a single column. */}
        <div
          className="grid grid-cols-1 min-[1100px]:grid-cols-[2fr_3fr] gap-x-10 gap-y-8 items-start"
          data-testid="home2-hero-plate-grid"
        >
          {/* ─── Left column: HERO ─── */}
          <div data-testid="home2-hero-block">
            {/* 1. Greeting band — Phase B Home cleanup restructure:
                "Back to portfolio" moved ABOVE the company name on
                its own line, with triple line-spacing between (mb-12
                ≈ 3em / 48px on the default 16px root). Company name
                size up 20% (text-[10.5px] → text-[12.5px] for the
                uppercase token; the company tile name follows the
                hero greeting). */}
            <section data-testid="home2-greeting">
              <button
                onClick={onBackToPortfolio}
                className="inline-flex items-center gap-1 text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] hover:text-[var(--ink)]"
                data-testid="home2-back-to-portfolio"
              >
                <ArrowLeft className="w-3 h-3" strokeWidth={1.7} /> Back to portfolio
              </button>
              <p
                className="akki-overline mb-1 mt-12"
                style={{ fontSize: "13px" }}
                data-testid="home2-company-name"
              >
                {activeContext.name}
              </p>
              <h1 className="akki-greeting">{greeting}, {firstName}.</h1>
              <p className="akki-meta mt-1">
                Welcome back to {activeContext.name}.
                {insights?.previous_visit_at && (
                  <> Last seen here {relTime(insights.previous_visit_at)}.</>
                )}
              </p>
            </section>

            {/* Patch 17 — Continue-onboarding band (kept in the hero
                column so the next-step prompt sits within the user's
                primary reading flow). */}
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

            {/* 3. HeroDocActions — preserved from Patch 2A.
                "+ Add document" + "All documents" CTAs. */}
            <HeroDocActions />

            {/* Phase B Home cleanup (2026-05-26), item #3:
                "Coming up" — next 14 days. Lives in the LEFT column
                below HeroDocActions so its right edge aligns with
                the plate column above it (both sit inside the same
                hero-plate grid; the left column is the same width
                top-to-bottom).
                Currently wired sub-source: cycle close dates. Other
                sub-sources (board / committee meetings, regulator
                filings) tracked in HOME_CLEANUP_LOG.md "Data source
                TODOs" and will surface here additively. */}
            <section className="mt-10" data-testid="home2-coming-up">
              <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3 inline-flex items-center gap-2">
                <Calendar className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Coming up
              </h2>
              {!comingUpLoaded ? (
                <p className="akki-meta italic">Reading the room…</p>
              ) : comingUp.length === 0 ? (
                <p
                  className="akki-meta italic"
                  data-testid="home2-coming-up-empty"
                >
                  No upcoming items in the next 14 days.
                </p>
              ) : (
                <ul className="space-y-2" data-testid="home2-coming-up-list">
                  {comingUp.map((it, i) => (
                    <li
                      key={`${it.kind}-${it.ts}-${i}`}
                      className="border-l-2 border-[var(--rule)] pl-3 py-1"
                      data-testid={`home2-coming-up-${i}`}
                    >
                      <button
                        type="button"
                        onClick={() => it.href && navigate(it.href)}
                        className="text-left w-full"
                      >
                        <p className="text-[13.5px] text-[var(--ink)] leading-snug">{it.label}</p>
                        <p className="text-[11px] text-[var(--muted)] font-mono mt-0.5">
                          {it.ts ? new Date(it.ts).toLocaleDateString() : "—"} · {String(it.kind || "").replace(/_/g, " ")}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          {/* ─── Right column: PLATE ─── */}
          <div data-testid="home2-plate-block">
            <section data-testid="home2-insights">
              <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3">
                What&apos;s on your plate
              </h2>
              {!loaded ? (
                <p className="akki-meta italic">Reading the room…</p>
              ) : (
                <div className="grid grid-cols-1 gap-3" data-testid="home2-insights-grid">
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
          </div>
        </div>

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

        {/* Phase B Home cleanup (2026-05-26), item #4: removed the
            two "Running the business" / "Sitting on the boards"
            footer tiles from this section. The "What's new since
            your last visit" header + caught-up empty-state above
            remain. */}

        {/* Patch 17 — ExCo teams card parity (was on HomeDual + HomeExecutive).
            Renders the admin-only ExCo teams grouping function. */}
        <ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />
      </div>
    </AppShell>
  );
}
