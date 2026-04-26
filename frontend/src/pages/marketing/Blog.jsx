import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { ArrowRight, Mail, Loader2 } from "lucide-react";

function shortDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" }); } catch { return iso; }
}

function SubscribeForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const onSubmit = async (e) => {
    e.preventDefault();
    if (!email.includes("@")) { toast.message("That doesn't look like an email."); return; }
    setBusy(true);
    try {
      await api.post("/blog/subscribe", { email });
      setDone(true);
      toast.success("You're on the list. The next Exco360 lands in your inbox.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };
  if (done) {
    return (
      <div className="bg-white border border-emerald-200 rounded-lg p-6 text-[14px] text-[var(--deep)]" data-testid="subscribe-done">
        Thanks. <strong className="text-[var(--ink)]">Exco360 / Vol 1 · Issue 1</strong> lands when it's worth your time — never more than weekly.
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} className="flex gap-2 flex-wrap" data-testid="subscribe-form">
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        required
        className="flex-1 min-w-[260px] h-11 px-4 text-[14px] bg-white border border-[var(--rule)] rounded-md focus:outline-none focus:border-[var(--accent)]"
        data-testid="subscribe-email"
      />
      <button type="submit" disabled={busy} className="h-11 px-5 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white text-[14px] font-medium rounded-md transition-colors inline-flex items-center gap-2" data-testid="subscribe-submit">
        {busy ? <><Loader2 className="w-4 h-4 animate-spin" /> Subscribing…</> : <><Mail className="w-4 h-4" /> Subscribe</>}
      </button>
    </form>
  );
}

export default function Blog() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/blog/posts");
        setPosts(data.posts || []);
      } catch { /* silent */ }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <MarketingShell>
      <section className="max-w-[1100px] mx-auto px-6 lg:px-10 py-20" data-testid="blog-page">
        <p className="akki-overline mb-3 text-[var(--accent)]">Exco360</p>
        <h1 className="akki-serif text-[44px] sm:text-[56px] leading-[1.05] tracking-tight text-[var(--ink)] mb-4 font-normal max-w-3xl">
          AKKI's perspective on AI's role in modern executive success.
        </h1>
        <p className="akki-serif text-[19px] leading-relaxed text-[var(--deep)] mb-10 italic max-w-2xl">
          A weekly editorial. Research-driven. Specific. No hype. No tool-marketing. Written for the colleague at the board table.
        </p>

        <div className="bg-white border border-[var(--accent)]/20 rounded-lg p-6 mb-16 max-w-2xl" data-testid="subscribe-card">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Mail className="w-3 h-3 text-[var(--accent)]" /> Subscribe
          </p>
          <p className="text-[14px] text-[var(--deep)] leading-relaxed mb-4">
            One short editorial in your inbox each week. Unsubscribe in one click.
          </p>
          <SubscribeForm />
          <p className="text-[11px] text-[var(--muted)] mt-3 italic">
            Prefer Medium? <a href="/api/blog/rss" className="text-[var(--accent)] hover:underline" data-testid="blog-rss-link">Subscribe via RSS →</a>
          </p>
        </div>

        {loading ? (
          <p className="text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
        ) : posts.length === 0 ? (
          <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-12 text-center" data-testid="blog-empty">
            <p className="akki-serif text-[20px] text-[var(--ink)] mb-2">The first Exco360 issue is coming.</p>
            <p className="text-[13.5px] text-[var(--muted)]">Subscribe above and you'll be the first to read it.</p>
          </div>
        ) : (
          <MediumStyleList posts={posts} />
        )}
      </section>
    </MarketingShell>
  );
}

/* ────────────────────────────────────────────────────────────────────────
 * MediumStyleList — featured hero (latest) + 2-column reading list grid.
 * Patterns lifted from Medium's recommended-stories shelf:
 *   • ample serif typography
 *   • date + read-time + author byline on every row
 *   • compact card body, no gimmicks, plenty of whitespace
 * ──────────────────────────────────────────────────────────────────────── */
function MediumStyleList({ posts }) {
  const [featured, ...rest] = posts;
  return (
    <div data-testid="blog-list">
      <p className="akki-overline mb-5">Latest issue</p>
      <Link
        to={`/blog/${featured.slug}`}
        className="block group border-b border-[var(--rule)] pb-14 mb-14"
        data-testid={`blog-featured-${featured.slug}`}
      >
        <div className="grid md:grid-cols-12 gap-8">
          <div className="md:col-span-8">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-4">
              {featured.kicker}
            </p>
            <h2 className="akki-serif text-[34px] sm:text-[42px] leading-[1.12] text-[var(--ink)] font-normal mb-4 group-hover:text-[var(--accent)] transition-colors">
              {featured.title}
            </h2>
            {featured.dek && (
              <p className="akki-serif text-[18px] leading-[1.6] text-[var(--deep)] italic mb-5">
                {featured.dek}
              </p>
            )}
            <div className="flex items-center gap-3 text-[12.5px] text-[var(--muted)]">
              <span className="w-7 h-7 rounded-full bg-[var(--accent)] text-white inline-flex items-center justify-center akki-serif text-[12px]">A</span>
              <span><strong className="text-[var(--ink)] font-normal">AKKI</strong> · for executives</span>
              <span>·</span>
              <span>{shortDate(featured.published_at)}</span>
              <span>·</span>
              <span>{featured.read_minutes} min read</span>
            </div>
          </div>
          <div className="md:col-span-4 flex items-center">
            {featured.hero_quote && (
              <p className="akki-serif italic text-[15.5px] leading-[1.6] text-[var(--deep)] border-l-2 border-[var(--accent)] pl-5">
                "{featured.hero_quote}"
              </p>
            )}
          </div>
        </div>
      </Link>

      <p className="akki-overline mb-5">More from Exco360</p>
      <div className="grid md:grid-cols-2 gap-x-10 gap-y-12">
        {rest.map((p) => (
          <Link
            key={p.slug}
            to={`/blog/${p.slug}`}
            className="block group"
            data-testid={`blog-post-${p.slug}`}
          >
            <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mb-2">
              {p.kicker}
            </p>
            <h3 className="akki-serif text-[22px] leading-[1.22] text-[var(--ink)] font-normal mb-2 group-hover:text-[var(--accent)] transition-colors">
              {p.title}
            </h3>
            {p.dek && (
              <p className="akki-serif text-[14px] leading-[1.6] text-[var(--deep)] italic mb-3 line-clamp-2">{p.dek}</p>
            )}
            <div className="flex items-center gap-2.5 text-[11.5px] text-[var(--muted)] font-mono">
              <span>{shortDate(p.published_at)}</span>
              <span>·</span>
              <span>{p.read_minutes} min</span>
              {p.category && <><span>·</span><span className="capitalize">{p.category}</span></>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
