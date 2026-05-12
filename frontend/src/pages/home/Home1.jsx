/**
 * Home1 — Portfolio entry. Patch 3.
 *
 * Calm, multi-company landing. Six vertical sections:
 *   1. Greeting band (time-of-day + last visit)
 *   2. Portfolio chips strip
 *   3. Continue where you left off (last 3 surfaces via /api/me/recent-views)
 *   4. Calendar peek (placeholder until we wire real cycle ship dates)
 *   5. News strip — MOCKED IN DEV — from /src/data/mock_news.json
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
import mockNews from "@/data/mock_news.json";
import releaseNotes from "@/data/release_notes.json";


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
  const role = (ctx.my_role || "—").toLowerCase();
  return (
    <button
      type="button"
      onClick={() => onPick(ctx)}
      className="text-left border border-[var(--rule)] rounded-sm px-4 py-3 bg-white hover:border-[var(--ink)] transition-colors min-w-[200px]"
      data-testid={`home1-chip-${ctx.id}`}
    >
      <p className="akki-serif text-[15px] text-[var(--ink)] truncate">{ctx.name}</p>
      <div className="flex items-center justify-between mt-1.5">
        <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
          {role === "owner" ? "Executive" : role.charAt(0).toUpperCase() + role.slice(1)}
        </span>
        {/* Health dot — grey when no signal data wired yet */}
        <span
          className="w-2 h-2 rounded-full bg-[var(--muted)]/40"
          data-testid={`home1-chip-${ctx.id}-dot`}
          aria-label="No signal yet"
        />
      </div>
    </button>
  );
}


export default function Home1() {
  const { account, contexts, switchContext } = useAuth();
  const navigate = useNavigate();
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    api.get("/me/recent-views", { params: { limit: 3 } })
      .then(({ data }) => setRecent(data?.items || []))
      .catch(() => setRecent([]));
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

        {/* 2. Portfolio chips */}
        <section className="mb-12" data-testid="home1-portfolio">
          <h2 className="akki-serif text-[15px] text-[var(--ink)] mb-3">Your companies</h2>
          {contexts.length === 0 ? (
            <p className="akki-meta italic">No companies yet.</p>
          ) : (
            <div className="flex gap-3 flex-wrap" data-testid="home1-portfolio-strip">
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

        {/* 5. News strip — MOCKED */}
        <section className="mb-12" data-testid="home1-news">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="akki-serif text-[15px] text-[var(--ink)] inline-flex items-center gap-2">
              <Newspaper className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> What's moving in your world
            </h2>
            <span
              className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]"
              data-testid="home1-news-mock-badge"
            >
              Curated · sample feed
            </span>
          </div>
          <ul className="space-y-3" data-testid="home1-news-list">
            {mockNews.items.map((n) => (
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
                <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug">{n.headline}</p>
                <p className="text-[12.5px] text-[var(--muted)] leading-snug mt-1">{n.summary}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* 6. New features card */}
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
    </AppShell>
  );
}
