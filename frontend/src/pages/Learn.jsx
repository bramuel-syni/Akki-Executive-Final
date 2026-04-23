import React, { useMemo, useState, useEffect } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import VideoModal from "@/components/learn/VideoModal";
import { LEARN_ARTICLES, LEARN_VIDEOS, TOPIC_LABEL } from "@/lib/learnContent";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  ArrowLeft, ArrowRight, BookOpen, ExternalLink, GraduationCap, Search,
  HelpCircle, Clock, Play, Sparkles, Loader2, FileText, Video as VideoIcon,
} from "lucide-react";

const MEDIA_FILTERS = [
  { key: "all", label: "All", icon: BookOpen },
  { key: "articles", label: "Articles", icon: FileText },
  { key: "videos", label: "Videos", icon: VideoIcon },
];

function formatMeta(item) {
  return `${TOPIC_LABEL[item.topic] || item.topic} · ${item.audience.map(a => a === "ned" ? "NED" : a).map(s => s[0].toUpperCase()+s.slice(1)).join(" · ")}`;
}

/** Article card — opens reader. */
function ArticleCard({ a }) {
  return (
    <Link
      to={`/app/learn/${a.id}`}
      className="block akki-stream-card group akki-fade-up"
      data-severity="neutral"
      data-testid={`learn-article-${a.id}`}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="akki-type-badge inline-flex items-center gap-1.5">
          <FileText className="w-3 h-3" strokeWidth={2.2} /> Article
        </span>
        <span className="text-[12px] text-[var(--muted)]">{a.kicker.replace(/^[^·]+·\s*/, "").split("·")[0].trim()}</span>
        {a.generated && (
          <span className="ml-auto text-[10px] uppercase tracking-wider text-[var(--accent)] bg-[var(--accent-soft)] px-1.5 py-0.5 rounded">
            On-demand
          </span>
        )}
      </div>
      <h3 className="akki-title-22 mb-3 leading-snug">{a.title}</h3>
      <p className="akki-serif text-[14px] text-[var(--deep)] leading-relaxed mb-4">{a.summary}</p>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-wrap gap-2">
          <span className="akki-context-chip">{TOPIC_LABEL[a.topic] || a.topic}</span>
          {a.audience.slice(0, 2).map((x) => (
            <span key={x} className="akki-context-chip capitalize">{x === "ned" ? "NED" : x}</span>
          ))}
        </div>
        <span className="akki-gesture text-[13px]">
          Read <ArrowRight className="w-3.5 h-3.5" />
        </span>
      </div>
    </Link>
  );
}

/** Video card — opens modal. */
function VideoCard({ v, onPlay }) {
  const thumb = `https://i.ytimg.com/vi/${v.youtube_id}/hqdefault.jpg`;
  return (
    <button
      type="button"
      onClick={onPlay}
      className="text-left akki-stream-card group akki-fade-up w-full"
      data-severity="neutral"
      data-testid={`learn-video-${v.id}`}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video mb-4 -mx-6 -mt-6 overflow-hidden">
        <img
          src={thumb}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/10 transition-colors">
          <div className="w-14 h-14 rounded-full bg-[var(--accent)] flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
            <Play className="w-5 h-5 text-white ml-0.5" fill="currentColor" strokeWidth={0} />
          </div>
        </div>
        {v.duration && (
          <div className="absolute bottom-2 right-2 text-[11px] font-mono bg-black/80 text-white px-1.5 py-0.5 rounded">
            {v.duration}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className="akki-type-badge inline-flex items-center gap-1.5">
          <VideoIcon className="w-3 h-3" strokeWidth={2.2} /> Video
        </span>
        <span className="text-[12px] text-[var(--muted)]">{v.source_name}</span>
      </div>
      <h3 className="akki-title-22 mb-2 leading-snug text-[19px]">{v.title}</h3>
      <p className="akki-serif text-[13.5px] text-[var(--deep)] leading-relaxed mb-4 italic">{v.summary}</p>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-wrap gap-2">
          <span className="akki-context-chip">{TOPIC_LABEL[v.topic] || v.topic}</span>
        </div>
        <span className="akki-gesture text-[13px]">
          Watch <Play className="w-3.5 h-3.5" strokeWidth={2} />
        </span>
      </div>
    </button>
  );
}

function ArticleReader({ article }) {
  const navigate = useNavigate();
  return (
    <div className="max-w-3xl mx-auto px-8 py-10 akki-fade-up">
      <button
        onClick={() => navigate("/app/learn")}
        className="akki-gesture text-[13px] mb-6"
        data-testid="learn-back-btn"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> All articles
      </button>

      <p className="akki-overline mb-3">{article.kicker}</p>
      <h1 className="akki-serif text-[34px] leading-[1.2] tracking-tight text-[var(--ink)] mb-4 font-normal">
        {article.title}
      </h1>
      <p className="akki-lead text-[var(--deep)] mb-8 italic">{article.summary}</p>

      <article className="akki-serif text-[17px] leading-[1.75] text-[var(--deep)] whitespace-pre-wrap mb-12">
        {article.body}
      </article>

      {article.questions_to_ask?.length > 0 && (
        <div className="bg-white border border-[var(--rule)] rounded-lg p-6 mb-10 relative">
          <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)] rounded-l-lg" />
          <div className="flex items-center gap-2 mb-4">
            <HelpCircle className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
            <p className="akki-overline">Questions to take into the room</p>
          </div>
          <ol className="space-y-3 akki-serif text-[16px] leading-[1.65] text-[var(--ink)] pl-0">
            {article.questions_to_ask.map((q, i) => (
              <li key={i} className="flex gap-3">
                <span className="text-[var(--accent)] font-semibold flex-none w-5">{i + 1}.</span>
                <span>{q}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="border-t border-[var(--rule)] pt-6 flex items-center justify-between text-[13px] text-[var(--muted)]">
        <span>
          {article.generated ? "Synthesised on demand by AKKI · primary source below" : `Sourced from: ${article.source_name}`}
        </span>
        {article.source_url && (
          <a
            href={article.source_url}
            target="_blank"
            rel="noreferrer"
            className="akki-gesture"
            data-testid="learn-source-link"
          >
            Open source <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    </div>
  );
}

export default function Learn() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("all");
  const [media, setMedia] = useState("all");
  const [videoPlaying, setVideoPlaying] = useState(null);
  const [researching, setResearching] = useState(false);
  const [adHocCache, setAdHocCache] = useState([]); // session-scoped on-demand articles

  // Library metadata
  const topics = useMemo(() => {
    const seen = new Map();
    [...LEARN_ARTICLES, ...LEARN_VIDEOS, ...adHocCache].forEach((a) => {
      if (!a.topic) return;
      seen.set(a.topic, (seen.get(a.topic) || 0) + 1);
    });
    return [["all", "All", LEARN_ARTICLES.length + LEARN_VIDEOS.length + adHocCache.length],
            ...Array.from(seen).map(([k, c]) => [k, TOPIC_LABEL[k] || k[0].toUpperCase()+k.slice(1), c])];
  }, [adHocCache]);

  const matchesQuery = (item, needle) => {
    if (!needle) return true;
    return (
      (item.title || "").toLowerCase().includes(needle) ||
      (item.summary || "").toLowerCase().includes(needle) ||
      (item.body || "").toLowerCase().includes(needle) ||
      (item.speaker || "").toLowerCase().includes(needle)
    );
  };

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const articles = [...adHocCache, ...LEARN_ARTICLES].filter(
      (a) => (topic === "all" || a.topic === topic) && matchesQuery(a, needle)
    );
    const videos = LEARN_VIDEOS.filter(
      (v) => (topic === "all" || v.topic === topic) && matchesQuery(v, needle)
    );
    if (media === "articles") return { articles, videos: [] };
    if (media === "videos")   return { articles: [], videos };
    return { articles, videos };
  }, [q, topic, media, adHocCache]);

  const totalFiltered = filtered.articles.length + filtered.videos.length;

  // Article reader view
  if (id) {
    const article = [...LEARN_ARTICLES, ...adHocCache].find((a) => a.id === id);
    if (!article) {
      return (
        <AppShell>
          <div className="max-w-xl mx-auto p-12 text-center">
            <BookOpen className="w-8 h-8 text-[var(--muted)] mx-auto mb-3" />
            <p className="akki-lead mb-4">Article not found.</p>
            <Link to="/app/learn" className="akki-gesture">Back to library <ArrowRight className="w-3.5 h-3.5" /></Link>
          </div>
        </AppShell>
      );
    }
    return <AppShell><ArticleReader article={article} /></AppShell>;
  }

  const onResearch = async () => {
    const needle = q.trim();
    if (!needle) {
      toast.message("Type a topic in the search box first.");
      return;
    }
    setResearching(true);
    try {
      const { data } = await api.post("/learn/research", { topic: needle }, { timeout: 120000 });
      setAdHocCache((prev) => [data, ...prev]);
      toast.success("AKKI researched that for you.");
      navigate(`/app/learn/${data.id}`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setResearching(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-[1280px] mx-auto px-8 py-10 grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-10">
        {/* Left rail — vertical filters */}
        <aside className="hidden lg:block" data-testid="learn-rail">
          <div className="sticky top-[88px] space-y-6">
            <div>
              <p className="akki-overline mb-3">Library</p>
              <h1 className="akki-serif text-[20px] leading-snug text-[var(--ink)] mb-2 font-normal">
                Curated & on-demand learning.
              </h1>
              <p className="text-[12.5px] text-[var(--muted)] leading-relaxed">
                For the board table. Article, video, or research the topic yourself if it isn't here.
              </p>
            </div>

            <div>
              <p className="akki-overline mb-3">Media</p>
              <div className="space-y-0.5">
                {MEDIA_FILTERS.map((m) => {
                  const Icon = m.icon;
                  const active = media === m.key;
                  return (
                    <button
                      key={m.key}
                      onClick={() => setMedia(m.key)}
                      className={`w-full text-left flex items-center gap-2.5 px-2.5 py-2 text-[13px] rounded-sm transition-colors ${
                        active
                          ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium border-l-2 border-[var(--accent)]"
                          : "text-[var(--deep)] hover:bg-[var(--cream-deep)]/60 border-l-2 border-transparent"
                      }`}
                      data-testid={`learn-media-${m.key}`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${active ? "text-[var(--accent)]" : "text-[var(--muted)]"}`} strokeWidth={1.8} />
                      {m.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="akki-overline mb-3">Topic</p>
              <div className="space-y-0.5">
                {topics.map(([key, label, count]) => {
                  const active = topic === key;
                  return (
                    <button
                      key={key}
                      onClick={() => setTopic(key)}
                      className={`w-full text-left flex items-center justify-between gap-2 px-2.5 py-2 text-[13px] rounded-sm transition-colors ${
                        active
                          ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium border-l-2 border-[var(--accent)]"
                          : "text-[var(--deep)] hover:bg-[var(--cream-deep)]/60 border-l-2 border-transparent"
                      }`}
                      data-testid={`learn-topic-${key}`}
                    >
                      <span>{label}</span>
                      <span className="text-[11px] text-[var(--muted)]">{count}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="pt-5 border-t border-[var(--rule)] text-[11px] text-[var(--muted)] leading-relaxed">
              <Clock className="w-3 h-3 inline mr-1.5" />
              Curated from NACD, IoD, Deloitte, Stanford HAI, Wharton, NIST, European Commission, FCA, ICO. Reviewed quarterly.
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="min-w-0">
          {/* Header + search */}
          <div className="mb-8 akki-fade-up">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <GraduationCap className="w-3 h-3 text-[var(--accent)]" /> Learn · Module M9
            </p>
            <h1 className="akki-greeting mb-2">A library curated for the board table.</h1>
            <p className="akki-meta max-w-2xl mb-5">
              Short reads and reputable talks on AI governance. Can't find what you need? AKKI will research any topic on demand.
            </p>

            {/* Search */}
            <div className="relative max-w-2xl">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && totalFiltered === 0) onResearch(); }}
                placeholder="Search — or ask about a topic that isn't here yet…"
                className="w-full pl-9 pr-36 py-2.5 text-[14px] bg-white border border-[var(--rule)] rounded-md focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
                data-testid="learn-search"
              />
              {q.trim() && (
                <Button
                  onClick={onResearch}
                  disabled={researching}
                  className="absolute right-1 top-1 h-[38px] bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm text-xs px-3"
                  data-testid="learn-research-btn"
                >
                  {researching
                    ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Researching…</>
                    : <><Sparkles className="w-3 h-3 mr-1.5" /> Research this</>}
                </Button>
              )}
            </div>
            {q.trim() && totalFiltered > 0 && (
              <p className="text-[12px] text-[var(--muted)] mt-2 max-w-2xl">
                {totalFiltered} match{totalFiltered === 1 ? "" : "es"} in the library. If none are right, click <span className="text-[var(--accent)] font-medium">Research this</span> and AKKI will compose a fresh article.
              </p>
            )}
          </div>

          {/* Empty state — with research CTA */}
          {totalFiltered === 0 ? (
            <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center" data-testid="learn-empty">
              <BookOpen className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
              <p className="akki-lead mb-2">Nothing in the library on that yet.</p>
              <p className="text-[13px] text-[var(--muted)] mb-5 max-w-md mx-auto">
                {q.trim()
                  ? <>Ask AKKI to research "<span className="text-[var(--ink)] font-medium">{q.trim()}</span>" and draft you a board-ready article in under a minute.</>
                  : <>Try a topic like "AI in insurance", "auditing LLM outputs", or "shadow AI risk".</>}
              </p>
              {q.trim() && (
                <Button
                  onClick={onResearch}
                  disabled={researching}
                  className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium"
                  data-testid="learn-research-empty-btn"
                >
                  {researching
                    ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Researching…</>
                    : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Research this for me</>}
                </Button>
              )}
            </div>
          ) : (
            <div className="space-y-8" data-testid="learn-grid">
              {filtered.articles.length > 0 && (
                <section>
                  {media === "all" && (
                    <p className="akki-overline mb-4">Articles · {filtered.articles.length}</p>
                  )}
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                    {filtered.articles.map((a) => <ArticleCard key={a.id} a={a} />)}
                  </div>
                </section>
              )}

              {filtered.videos.length > 0 && (
                <section>
                  {media === "all" && (
                    <p className="akki-overline mb-4">Videos · {filtered.videos.length}</p>
                  )}
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                    {filtered.videos.map((v) => (
                      <VideoCard key={v.id} v={v} onPlay={() => setVideoPlaying(v)} />
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </main>
      </div>

      <VideoModal
        open={!!videoPlaying}
        onOpenChange={(o) => { if (!o) setVideoPlaying(null); }}
        video={videoPlaying}
      />
    </AppShell>
  );
}
