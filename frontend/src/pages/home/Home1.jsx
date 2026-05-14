/**
 * Home1 — Portfolio entry. Patch 3.
 *
 * Calm, multi-company landing. Six vertical sections:
 *   1. Greeting band (time-of-day + last visit)
 *   2. Portfolio chips strip
 *   3. Continue where you left off (last 3 surfaces via /api/me/recent-views)
 *   4. Calendar peek (placeholder until we wire real cycle ship dates)
 *   5. News strip — Patch 21: real RSS aggregator from /api/news
 *   6. New features card — from /src/data/release_notes.json
 *
 * No company-specific data on Home 1 — that lives on Home 2.
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Newspaper, Calendar, History, ChevronRight, Sparkles } from "lucide-react";
import releaseNotes from "@/data/release_notes.json";

// Patch 25 — region code → label map. GLOBAL is intentionally
// rendered as a neutral live-feed label (no geographic tag) — honest
// fallback when the server couldn't resolve a meaningful region.
const REGION_LABELS = {
  UK: "United Kingdom",
  US: "United States",
  EU: "Europe",
  CA: "Canada",
  AU: "Australia",
  NZ: "New Zealand",
  IN: "India",
  IE: "Ireland",
  ZA: "South Africa",
  SG: "Singapore",
  HK: "Hong Kong",
  DE: "Germany",
  AT: "Austria",
  CH: "Switzerland",
  FR: "France",
  ES: "Spain",
  IT: "Italy",
  NL: "Netherlands",
  BE: "Belgium",
  PT: "Portugal",
  BR: "Brazil",
  MX: "Mexico",
  JP: "Japan",
  CN: "China",
  TW: "Taiwan",
  KR: "Korea",
  RU: "Russia",
  AF: "Africa",
};


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
    if (mins < 60) return `${mins} min ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} hour${hrs === 1 ? "" : "s"} ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
    return new Date(iso).toLocaleDateString();
  } catch { return "—"; }
}


function ChipCompany({ ctx, onPick }) {
  // Chunk 6.5-REVISED (2026-05-13, Task C): card refresh.
  // - Bold company name, single line, ellipsis on overflow.
  // - Role chip in muted neutral (NOT crimson — that's the v7
  //   token sweep rule too).
  // - Optional "Last seen Nh ago" — only when an upstream timestamp
  //   is available on the context payload.
  // - Hover: 1px border highlight + soft shadow lift. No translate.
  const role = (ctx.my_role || "—").toLowerCase();
  const roleLabel = role === "owner" ? "Executive"
                  : role === "ned" ? "NED"
                  : role.charAt(0).toUpperCase() + role.slice(1);
  const lastSeen = ctx.last_activity_at || ctx.last_seen_at || ctx.updated_at;
  return (
    <button
      type="button"
      onClick={() => onPick(ctx)}
      className="group text-left border border-[var(--rule)] rounded-md px-4 py-4 bg-white hover:border-[var(--ink)] hover:shadow-sm transition-all duration-150 flex flex-col gap-2 h-full"
      data-testid={`home1-chip-${ctx.id}`}
    >
      <p
        className="akki-serif text-[16px] text-[var(--ink)] font-medium truncate leading-tight"
        title={ctx.name}
      >
        {ctx.name}
      </p>
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] inline-flex items-center px-1.5 py-0.5 rounded-sm bg-[var(--cream-deep)]"
          data-testid={`home1-chip-${ctx.id}-role`}
        >
          {roleLabel}
        </span>
        {lastSeen && (
          <span
            className="text-[10.5px] text-[var(--muted)] font-mono shrink-0"
            data-testid={`home1-chip-${ctx.id}-lastseen`}
          >
            Last seen {relTime(lastSeen)}
          </span>
        )}
      </div>
    </button>
  );
}


export default function Home1() {
  const { account, contexts, switchContext } = useAuth();
  const navigate = useNavigate();
  const [recent, setRecent] = useState([]);
  // Patch 21 — real news from the curated RSS aggregator. The
  // aggregator runs every 30 min server-side; this fetch is cheap
  // (top-N from cache). Empty array on cold-start renders the
  // editorial fallback line below; never block render on this.
  const [news, setNews] = useState([]);
  // Patch 25 — server resolves region from profile/workspace/Accept-Language.
  const [regionApplied, setRegionApplied] = useState(null);

  useEffect(() => {
    api.get("/me/recent-views", { params: { limit: 3 } })
      .then(({ data }) => setRecent(data?.items || []))
      .catch(() => setRecent([]));
  }, []);

  useEffect(() => {
    api.get("/news", { params: { limit: 5 } })
      .then(({ data }) => {
        setNews(data?.items || []);
        setRegionApplied(data?.region_applied || null);
      })
      .catch(() => setNews([]));
  }, []);

  const greeting = useMemo(() => greetingFor(new Date()), []);
  const firstName = (account?.display_name || account?.name || "").split(" ")[0] || "there";

  const onChip = async (ctx) => {
    try { await switchContext(ctx.id); } catch { /* noop */ }
    navigate("/app");
  };

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-12" data-testid="home1">
        {/* 1. Greeting band */}
        <section className="mb-10" data-testid="home1-greeting">
          <p className="akki-overline mb-1">Portfolio</p>
          <h1 className="akki-greeting">{greeting}, {firstName}.</h1>
          {account?.last_login_at && (
            <p className="akki-meta mt-2">You were last here {relTime(account.last_login_at)}.</p>
          )}
        </section>

        {/* 2. Portfolio chips — responsive grid (Chunk 6.5-REVISED, Task C). */}
        <section className="mb-12" data-testid="home1-portfolio">
          <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3">Your companies</h2>
          {contexts.length === 0 ? (
            <p className="akki-meta italic">No companies yet.</p>
          ) : (
            <div
              className="grid grid-cols-1 sm:grid-cols-2 min-[1024px]:grid-cols-3 min-[1280px]:grid-cols-4 gap-3"
              data-testid="home1-portfolio-strip"
            >
              {contexts.map((c) => <ChipCompany key={c.id} ctx={c} onPick={onChip} />)}
            </div>
          )}
        </section>

        {/* 3. Continue where you left off */}
        <section className="mb-12" data-testid="home1-recent">
          <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3 inline-flex items-center gap-2">
            <History className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Continue where you left off
          </h2>
          {recent.length === 0 ? (
            <p className="akki-meta italic" data-testid="home1-recent-empty">
              Nothing to resume yet.
            </p>
          ) : (
            <div className="grid sm:grid-cols-3 gap-3" data-testid="home1-recent-grid">
              {recent.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => navigate(r.surface_path)}
                  className="text-left border border-[var(--rule)] rounded-sm px-4 py-3 bg-white hover:border-[var(--ink)]"
                  data-testid={`home1-recent-${r.id}`}
                >
                  <p className="akki-serif text-[14px] text-[var(--ink)] truncate">{r.label}</p>
                  <p className="text-[11px] text-[var(--muted)] font-mono mt-1">
                    {relTime(r.last_visited_at)}
                  </p>
                  <span className="inline-flex items-center gap-1 text-[11px] text-[var(--ink)] mt-2">
                    Resume <ChevronRight className="w-3 h-3" strokeWidth={1.7} />
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        {/* 4. Calendar peek */}
        <section className="mb-12" data-testid="home1-calendar">
          <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3 inline-flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Coming up
          </h2>
          <p className="akki-meta italic" data-testid="home1-calendar-empty">
            No upcoming events on your calendar.
          </p>
        </section>

        {/* Chunk 6.5-REVISED (2026-05-13, Task C):
            News strip + "New in AKKI" sit side-by-side at ≥1100px
            (3fr / 2fr). News column is a fixed-height scrollable
            container so the page total height doesn't blow up as
            the feed grows. Below the breakpoint they stack
            vertically (news first, release notes below). */}
        <div
          className="grid grid-cols-1 min-[1100px]:grid-cols-[3fr_2fr] gap-x-10 gap-y-12 items-start"
          data-testid="home1-news-release-grid"
        >
          {/* 5. News strip — Patch 21: real RSS feed via /api/news.
              Capped at ~480px and scrollable inside. */}
          <section data-testid="home1-news">
            <div className="flex items-baseline justify-between mb-3">
              <h2 className="akki-serif text-[15px] text-[var(--ink)] inline-flex items-center gap-2">
                <Newspaper className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> What&apos;s moving in your world
              </h2>
              <span
                className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]"
                data-testid="home1-news-source-label"
              >
                {regionApplied && regionApplied !== "GLOBAL" && REGION_LABELS[regionApplied]
                  ? `Curated for ${REGION_LABELS[regionApplied]}`
                  : "Curated · live feed"}
              </span>
            </div>
            {news.length === 0 ? (
              <p className="akki-meta italic" data-testid="home1-news-fallback">
                News updating — check back shortly.
              </p>
            ) : (
              <ul
                className="space-y-3 max-h-[480px] overflow-y-auto pr-2 akki-thin-scroll"
                data-testid="home1-news-list"
              >
                {news.map((n) => (
                  <li
                    key={n.id}
                    className="border-b border-[var(--rule)] pb-3 last:border-b-0"
                    data-testid={`home1-news-${n.id}`}
                  >
                    <div className="flex items-baseline gap-2 mb-1">
                      <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
                        {n.source}
                      </span>
                      <span className="text-[10.5px] font-mono text-[var(--muted)]">·</span>
                      <span className="text-[10.5px] font-mono text-[var(--muted)]">
                        {new Date(n.published_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                      </span>
                    </div>
                    <a
                      href={n.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="akki-serif text-[15px] text-[var(--ink)] leading-snug hover:text-[var(--accent)] no-underline block"
                    >
                      {n.title}
                    </a>
                    {n.summary && (
                      <p className="text-[12.5px] text-[var(--muted)] leading-snug mt-1">{n.summary}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* 6. New features card — right column at ≥1100px,
              stacks below news on narrow viewports. */}
          <section data-testid="home1-release-notes">
            <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3 inline-flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} /> New in AKKI
            </h2>
            <div className="border border-[var(--rule)] rounded-sm bg-white px-5 py-4 space-y-3">
              {releaseNotes.items.map((r) => (
                <div key={r.id} data-testid={`home1-release-${r.id}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="akki-serif text-[14px] text-[var(--ink)]">{r.title}</p>
                    <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] shrink-0">
                      {new Date(r.shipped_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                    </span>
                  </div>
                  <p className="text-[12.5px] text-[var(--muted)] leading-snug mt-1">{r.summary}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
