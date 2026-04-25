import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { api } from "@/lib/api";
import { ArrowLeft, ExternalLink, Loader2 } from "lucide-react";

function shortDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" }); } catch { return iso; }
}

/** Lightweight markdown renderer — handles headings, bold/italic, lists,
 *  paragraphs, and blockquotes. Plain text otherwise. We deliberately avoid
 *  shipping a full md library for a single editorial surface. */
function MD({ text }) {
  if (!text) return null;
  const lines = text.split(/\r?\n/);
  const out = [];
  let buf = [];
  let listMode = null;
  const flushList = () => {
    if (listMode === "ul") {
      out.push(<ul key={`ul-${out.length}`} className="my-4 pl-6 list-disc space-y-1.5 akki-serif text-[16.5px] leading-relaxed text-[var(--deep)]">{buf}</ul>);
    } else if (listMode === "ol") {
      out.push(<ol key={`ol-${out.length}`} className="my-4 pl-6 list-decimal space-y-1.5 akki-serif text-[16.5px] leading-relaxed text-[var(--deep)]">{buf}</ol>);
    }
    buf = []; listMode = null;
  };
  const inline = (s) => {
    const html = s
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code class='bg-[var(--cream-deep)] px-1.5 py-0.5 rounded text-[14px] font-mono'>$1</code>");
    return <span dangerouslySetInnerHTML={{ __html: html }} />;
  };
  lines.forEach((raw, i) => {
    const line = raw.replace(/\s+$/, "");
    if (/^##\s+/.test(line)) { flushList(); out.push(<h2 key={i} className="akki-serif text-[26px] text-[var(--ink)] mt-12 mb-4 font-normal leading-tight">{line.replace(/^##\s+/, "")}</h2>); return; }
    if (/^#\s+/.test(line))  { flushList(); out.push(<h1 key={i} className="akki-serif text-[32px] text-[var(--ink)] mt-12 mb-4 font-normal">{line.replace(/^#\s+/, "")}</h1>); return; }
    if (/^>\s+/.test(line))  { flushList(); out.push(<blockquote key={i} className="my-6 border-l-2 border-[var(--accent)] pl-5 akki-serif text-[18px] italic text-[var(--ink)] leading-relaxed">{inline(line.replace(/^>\s+/, ""))}</blockquote>); return; }
    if (/^[-*]\s+/.test(line)) {
      if (listMode !== "ul") { flushList(); listMode = "ul"; }
      buf.push(<li key={i}>{inline(line.replace(/^[-*]\s+/, ""))}</li>); return;
    }
    if (/^\d+\.\s+/.test(line)) {
      if (listMode !== "ol") { flushList(); listMode = "ol"; }
      buf.push(<li key={i}>{inline(line.replace(/^\d+\.\s+/, ""))}</li>); return;
    }
    if (line.trim() === "") { flushList(); return; }
    flushList();
    out.push(<p key={i} className="akki-serif text-[16.5px] leading-[1.8] text-[var(--deep)] mb-5">{inline(line)}</p>);
  });
  flushList();
  return <>{out}</>;
}

export default function BlogPost() {
  const { slug } = useParams();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/blog/posts/${slug}`);
        setPost(data);
      } catch { setError("Article not found."); }
      finally { setLoading(false); }
    })();
  }, [slug]);

  if (loading) return <MarketingShell><div className="py-20 text-center"><Loader2 className="w-8 h-8 animate-spin text-[var(--accent)] mx-auto" /></div></MarketingShell>;
  if (error || !post) return (
    <MarketingShell>
      <section className="max-w-2xl mx-auto px-6 lg:px-10 py-20 text-center">
        <p className="akki-overline mb-3 text-[var(--accent)]">Not found</p>
        <p className="akki-serif text-[24px] text-[var(--ink)] mb-6">{error || "Article not found."}</p>
        <Link to="/blog" className="text-[var(--accent)] hover:underline">← Back to Exco360</Link>
      </section>
    </MarketingShell>
  );

  return (
    <MarketingShell>
      <article className="max-w-3xl mx-auto px-6 lg:px-10 py-16" data-testid="blog-post-page">
        <Link to="/blog" className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--muted)] hover:text-[var(--accent)] mb-8" data-testid="blog-back">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Exco360
        </Link>
        <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-4">{post.kicker}</p>
        <h1 className="akki-serif text-[40px] sm:text-[48px] leading-[1.1] text-[var(--ink)] font-normal mb-5">{post.title}</h1>
        {post.dek && <p className="akki-serif text-[20px] leading-relaxed text-[var(--deep)] italic mb-8">{post.dek}</p>}
        <div className="flex items-center gap-4 text-[12px] text-[var(--muted)] font-mono uppercase tracking-wider mb-10 pb-6 border-b border-[var(--rule)]">
          <span>{shortDate(post.published_at)}</span>
          <span>· {post.read_minutes} min read</span>
          {post.tags?.length > 0 && <span className="ml-auto flex flex-wrap gap-1.5">{post.tags.slice(0, 4).map((t) => <span key={t} className="text-[var(--deep)] normal-case">#{t}</span>)}</span>}
        </div>

        {post.hero_quote && (
          <p className="akki-serif text-[24px] leading-snug text-[var(--ink)] italic mb-12 pl-5 border-l-2 border-[var(--accent)]">
            "{post.hero_quote}"
          </p>
        )}

        <div className="mb-16">
          <MD text={post.body} />
        </div>

        {post.sources?.length > 0 && (
          <div className="border-t border-[var(--rule)] pt-8 mb-12">
            <p className="akki-overline mb-4">Sources</p>
            <ul className="space-y-2">
              {post.sources.map((s, i) => (
                <li key={i} className="text-[13px]">
                  <a href={s} target="_blank" rel="noreferrer" className="text-[var(--accent)] hover:underline inline-flex items-center gap-1.5 break-all">
                    {s} <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="border-t border-[var(--rule)] pt-10 text-center" data-testid="blog-post-cta">
          <p className="akki-serif text-[18px] text-[var(--ink)] mb-3">More like this, weekly.</p>
          <Link to="/blog" className="text-[var(--accent)] hover:underline text-[14px]">Subscribe to Exco360</Link>
        </div>
      </article>
    </MarketingShell>
  );
}
