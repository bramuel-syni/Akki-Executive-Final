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

        <div className="bg-white border border-[var(--accent)]/20 rounded-lg p-6 mb-14 max-w-2xl" data-testid="subscribe-card">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Mail className="w-3 h-3 text-[var(--accent)]" /> Subscribe
          </p>
          <p className="text-[14px] text-[var(--deep)] leading-relaxed mb-4">
            One short editorial in your inbox each week. Unsubscribe in one click.
          </p>
          <SubscribeForm />
        </div>

        {loading ? (
          <p className="text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</p>
        ) : posts.length === 0 ? (
          <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-12 text-center" data-testid="blog-empty">
            <p className="akki-serif text-[20px] text-[var(--ink)] mb-2">The first Exco360 issue is coming.</p>
            <p className="text-[13.5px] text-[var(--muted)]">Subscribe above and you'll be the first to read it.</p>
          </div>
        ) : (
          <div className="space-y-12" data-testid="blog-list">
            {posts.map((p) => (
              <Link
                key={p.slug}
                to={`/blog/${p.slug}`}
                className="block group border-b border-[var(--rule)] pb-12 last:border-0"
                data-testid={`blog-post-${p.slug}`}
              >
                <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-3">{p.kicker}</p>
                <h2 className="akki-serif text-[28px] sm:text-[34px] leading-[1.15] text-[var(--ink)] font-normal mb-3 group-hover:text-[var(--accent)] transition-colors max-w-3xl">
                  {p.title}
                </h2>
                {p.dek && (
                  <p className="akki-serif text-[16.5px] leading-relaxed text-[var(--deep)] italic mb-4 max-w-2xl">{p.dek}</p>
                )}
                <div className="flex items-center gap-4 text-[12px] text-[var(--muted)] font-mono">
                  <span>{shortDate(p.published_at)}</span>
                  <span>· {p.read_minutes} min read</span>
                  <span className="ml-auto inline-flex items-center gap-1.5 text-[var(--accent)] font-sans">
                    Read <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </MarketingShell>
  );
}
