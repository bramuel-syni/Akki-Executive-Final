import React, { useMemo, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import VideoModal from "@/components/learn/VideoModal";
import LearnMoreModal from "@/components/learn/LearnMoreModal";
import { useAuth } from "@/contexts/AuthContext";
import {
  LEARN_ARTICLES, LEARN_VIDEOS, LEARN_NEWS, TOPIC_LABEL, CONTENT_TYPE_LABEL,
} from "@/lib/learnContent";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  ArrowLeft, ArrowRight, BookOpen, ExternalLink, GraduationCap, Search,
  HelpCircle, Clock, Play, Sparkles, Loader2, FileText, Video as VideoIcon,
  Newspaper, Briefcase, ChevronRight,
} from "lucide-react";

/**
 * Mini-tabs for content type — matches Feedback #1:
 * "Learn should have mini-tabs (News · TL Articles · Videos · Case Studies)."
 */
const TABS = [
  { key: "news",       label: "News",         icon: Newspaper },
  { key: "tl_article", label: "TL Articles",  icon: FileText },
  { key: "video",      label: "Videos",       icon: VideoIcon },
  { key: "case_study", label: "Case Studies", icon: Briefcase },
];

/** Article card — opens reader. Compact horizontal tile (50% reduced height). */
function ArticleCard({ a }) {
  const kickerSource = (a.kicker || "").split("·").slice(1).join("·").trim();
  return (
    <Link
      to={`/app/learn/${a.id}`}
      className="block bg-white border border-[var(--rule)] rounded-md px-4 py-3 hover:border-[var(--accent)]/40 transition-colors group akki-fade-up"
      data-severity="neutral"
      data-testid={`learn-article-${a.id}`}
    >
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <span className="akki-type-badge inline-flex items-center gap-1.5">
          <FileText className="w-3 h-3" strokeWidth={2.2} />
          {a.content_type === "case_study" ? "Case" : a.content_type === "news" ? "News" : "Article"}
        </span>
        <span className="text-[11.5px] text-[var(--muted)]">{kickerSource}</span>
        {a.generated && (
          <span className="ml-auto text-[10px] uppercase tracking-wider text-[var(--accent)] bg-[var(--accent-soft)] px-1.5 py-0.5 rounded">
            On-demand
          </span>
        )}
      </div>
      <h3 className="akki-serif text-[16px] text-[var(--ink)] leading-snug font-normal mb-1.5">{a.title}</h3>
      <p className="akki-serif text-[12.5px] text-[var(--deep)] leading-relaxed mb-2 line-clamp-2">{a.summary}</p>
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div className="flex flex-wrap gap-1.5">
          <span className="akki-context-chip">{TOPIC_LABEL[a.topic] || a.topic}</span>
          {a.audience.slice(0, 2).map((x) => (
            <span key={x} className="akki-context-chip capitalize">{x === "ned" ? "NED" : x}</span>
          ))}
        </div>
        <span className="akki-gesture text-[12px]">
          Read <ArrowRight className="w-3 h-3" />
        </span>
      </div>
    </Link>
  );
}

/** Video card — horizontal layout with very compact thumbnail (halved). */
function VideoCard({ v, onPlay }) {
  const thumb = `https://i.ytimg.com/vi/${v.youtube_id}/mqdefault.jpg`;
  return (
    <button
      type="button"
      onClick={onPlay}
      className="text-left bg-white border border-[var(--rule)] rounded-md px-4 py-3 hover:border-[var(--accent)]/40 transition-colors group akki-fade-up w-full flex gap-4 items-start"
      data-severity="neutral"
      data-testid={`learn-video-${v.id}`}
    >
      <div className="relative w-20 aspect-video shrink-0 overflow-hidden rounded-sm">
        <img src={thumb} alt="" className="w-full h-full object-cover" loading="lazy" />
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/10 transition-colors">
          <div className="w-5 h-5 rounded-full bg-[var(--accent)] flex items-center justify-center shadow-sm">
            <Play className="w-2 h-2 text-white ml-0.5" fill="currentColor" strokeWidth={0} />
          </div>
        </div>
        {v.duration && (
          <div className="absolute bottom-0.5 right-0.5 text-[8.5px] font-mono bg-black/80 text-white px-1 py-px rounded-sm">
            {v.duration}
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="akki-type-badge inline-flex items-center gap-1.5">
            <VideoIcon className="w-3 h-3" strokeWidth={2.2} /> Video
          </span>
          <span className="text-[11.5px] text-[var(--muted)]">{v.source_name}</span>
        </div>
        <h3 className="akki-serif text-[15px] leading-snug text-[var(--ink)] mb-1 font-normal">{v.title}</h3>
        <p className="akki-serif text-[12px] text-[var(--deep)] leading-relaxed mb-1.5 italic line-clamp-1">{v.summary}</p>
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div className="flex flex-wrap gap-1.5">
            <span className="akki-context-chip">{TOPIC_LABEL[v.topic] || v.topic}</span>
          </div>
          <span className="akki-gesture text-[12px]">
            Watch <Play className="w-3 h-3" strokeWidth={2} />
          </span>
        </div>
      </div>
    </button>
  );
}

function ArticleReader({ article }) {
  const navigate = useNavigate();
  return (
    <div className="h-[calc(100vh-4rem)] overflow-y-auto">
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
    </div>
  );
}

export default function Learn() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const [q, setQ] = useState("");
  const [activeTab, setActiveTab] = useState("tl_article");
  const [topic, setTopic] = useState("all");
  const [videoPlaying, setVideoPlaying] = useState(null);
  const [researching, setResearching] = useState(false);
  const [adHocCache, setAdHocCache] = useState([]);
  const [moreOpen, setMoreOpen] = useState(false);
  // Recency tab — "fresh" (≤ 5 days) | "stayed" (> 5 days) | "all"
  const [recency, setRecency] = useState("all");

  const FIVE_DAYS_MS = 5 * 24 * 60 * 60 * 1000;
  // Deterministic synthetic published_at when seed items lack one — so the
  // Fresh / Stayed buckets are non-empty on day one. Hashes the item id
  // into a stable offset within the last 30 days, with a slight bias
  // toward freshness so at least ~1-in-3 items land inside the 5-day
  // window. Runtime-only; the underlying static seed file stays evergreen.
  const synthesizedAge = (id) => {
    if (!id) return 30 * 24 * 60 * 60 * 1000;
    let h = 0;
    for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    // Bucket the hash so ~33% land 0-4 days, ~33% 5-14 days, ~33% 15-29 days
    const bucket = h % 30;
    if (bucket < 10) return (bucket % 5) * 24 * 60 * 60 * 1000;       // 0-4d (Fresh)
    if (bucket < 20) return (5 + bucket % 10) * 24 * 60 * 60 * 1000;  // 5-14d (Stayed)
    return (15 + bucket % 15) * 24 * 60 * 60 * 1000;                   // 15-29d (Stayed)
  };
  const itemAgeMs = (item) => {
    const iso = item.published_at || item.created_at;
    if (iso) {
      const t = new Date(iso).getTime();
      if (!isNaN(t)) return Date.now() - t;
    }
    return synthesizedAge(item.id);
  };
  const matchesRecency = (item) => {
    if (recency === "all") return true;
    const age = itemAgeMs(item);
    if (recency === "fresh") return age <= FIVE_DAYS_MS;
    return age > FIVE_DAYS_MS;
  };

  // Tab counts — what's available in each bucket (pre-topic/query filter)
  const tabCounts = useMemo(() => ({
    news:       LEARN_NEWS.length,
    tl_article: LEARN_ARTICLES.filter((a) => a.content_type === "tl_article").length + adHocCache.length,
    video:      LEARN_VIDEOS.length,
    case_study: LEARN_ARTICLES.filter((a) => a.content_type === "case_study").length,
  }), [adHocCache]);

  // Items for currently-selected tab (before topic/query filter)
  const tabItems = useMemo(() => {
    if (activeTab === "news")       return LEARN_NEWS;
    if (activeTab === "tl_article") return [...adHocCache, ...LEARN_ARTICLES.filter((a) => a.content_type === "tl_article")];
    if (activeTab === "video")      return LEARN_VIDEOS;
    if (activeTab === "case_study") return LEARN_ARTICLES.filter((a) => a.content_type === "case_study");
    return [];
  }, [activeTab, adHocCache]);

  // Topic pills for the CURRENT tab only
  const topicsInTab = useMemo(() => {
    const map = new Map();
    tabItems.forEach((item) => {
      if (!item.topic) return;
      map.set(item.topic, (map.get(item.topic) || 0) + 1);
    });
    return [["all", "All", tabItems.length],
            ...Array.from(map).map(([k, c]) => [k, TOPIC_LABEL[k] || k, c])];
  }, [tabItems]);

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
    return tabItems.filter(
      (item) => (topic === "all" || item.topic === topic) && matchesQuery(item, needle) && matchesRecency(item)
    );
  }, [tabItems, topic, q, recency]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Reader view
  if (id) {
    const article = [...LEARN_ARTICLES, ...LEARN_NEWS, ...adHocCache].find((a) => a.id === id);
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
      // Personalise on server by passing the active context id — so a Kenyan
      // bank NED gets CBK-flavoured sources, a UK exec gets FCA/PRA ones.
      const payload = { topic: needle };
      if (activeContext?.id) payload.context_id = activeContext.id;
      const { data } = await api.post("/learn/research", payload, { timeout: 120000 });
      setAdHocCache((prev) => [{ ...data, content_type: "tl_article" }, ...prev]);
      if (data.personalised) {
        toast.success(`AKKI researched that, weighted to ${data.personalisation_from?.jurisdiction || "your company"}.`);
      } else {
        toast.success("AKKI researched that for you.");
      }
      navigate(`/app/learn/${data.id}`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setResearching(false);
    }
  };

  // Reset topic when tab changes
  const handleTabChange = (key) => {
    setActiveTab(key);
    setTopic("all");
  };

  return (
    <AppShell>
      {/* Fixed-height page: only the grid area scrolls */}
      <div className="h-[calc(100vh-4rem)] max-w-[1280px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-10 overflow-hidden">
        {/* Left rail — intro + topic pills for current tab */}
        <aside className="hidden lg:flex flex-col pt-10 pb-8 overflow-y-auto" data-testid="learn-rail">
          <div className="space-y-6">
            <div>
              <p className="akki-overline mb-3">Library</p>
              <h2 className="akki-serif text-[20px] leading-snug text-[var(--ink)] mb-2 font-normal">
                Curated & on-demand learning.
              </h2>
              <p className="text-[12.5px] text-[var(--muted)] leading-relaxed">
                For the board table. Article, video, or research the topic yourself if it isn't here.
              </p>
            </div>

            <div>
              <p className="akki-overline mb-3">Topic</p>
              <div className="space-y-0.5">
                {topicsInTab.map(([key, label, count]) => {
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

        {/* Main — sticky header (intro + tabs + search), scrolling body below */}
        <main className="flex flex-col min-w-0 min-h-0 pt-10 pb-8">
          {/* Header — stays put */}
          <div className="shrink-0 mb-6 akki-fade-up">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <GraduationCap className="w-3 h-3 text-[var(--accent)]" /> Learn · Module M9
            </p>
            <h1 className="akki-greeting mb-2">A library curated for the board table.</h1>
            <p className="akki-meta max-w-2xl">
              Short reads, case studies, videos, and news on AI governance. Can't find what you need? AKKI will research any topic on demand.
            </p>
          </div>

          {/* Mini-tabs — stays put */}
          <div className="shrink-0 flex items-center gap-1 border-b border-[var(--rule)] mb-5" data-testid="learn-tabs">
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = activeTab === t.key;
              return (
                <button
                  key={t.key}
                  onClick={() => handleTabChange(t.key)}
                  className={`relative flex items-center gap-2 px-4 py-2.5 text-[13.5px] transition-colors ${
                    active
                      ? "text-[var(--ink)] font-medium"
                      : "text-[var(--muted)] hover:text-[var(--deep)]"
                  }`}
                  data-testid={`learn-tab-${t.key}`}
                >
                  <Icon className={`w-3.5 h-3.5 ${active ? "text-[var(--accent)]" : ""}`} strokeWidth={1.8} />
                  <span>{t.label}</span>
                  <span className={`text-[11px] ${active ? "text-[var(--accent)]" : "text-[var(--muted)]/70"}`}>
                    {tabCounts[t.key]}
                  </span>
                  {active && (
                    <span className="absolute left-0 right-0 -bottom-px h-[2px] bg-[var(--accent)]" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Search — stays put */}
          <div className="shrink-0 mb-5">
            <div className="relative max-w-2xl">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && filtered.length === 0) onResearch(); }}
                placeholder={`Search ${CONTENT_TYPE_LABEL[activeTab]?.toLowerCase() || "library"} — or ask about a topic that isn't here…`}
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
            {q.trim() && filtered.length > 0 && (
              <p className="text-[12px] text-[var(--muted)] mt-2 max-w-2xl">
                {filtered.length} match{filtered.length === 1 ? "" : "es"} in this tab. If none are right, click <span className="text-[var(--accent)] font-medium">Research this</span> and AKKI will compose a fresh article.
              </p>
            )}

            {/* Recency mini-tabs — Fresh (≤5 days) | Stayed a bit (>5 days) | All */}
            <div className="flex items-center gap-1 mt-3 text-[12px]" data-testid="learn-recency-tabs">
              {[
                ["all", "All"],
                ["fresh", "Fresh"],
                ["stayed", "Stayed a bit"],
              ].map(([k, label]) => {
                const count = tabItems.filter((it) => {
                  if (k === "all") return true;
                  const age = itemAgeMs(it);
                  if (k === "fresh") return age <= FIVE_DAYS_MS;
                  return age > FIVE_DAYS_MS;
                }).length;
                const active = recency === k;
                return (
                  <button
                    key={k}
                    onClick={() => setRecency(k)}
                    className={`px-3 py-1 rounded-full border transition-colors inline-flex items-center gap-1.5 ${
                      active
                        ? "bg-[var(--ink)] text-white border-[var(--ink)]"
                        : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"
                    }`}
                    data-testid={`learn-recency-${k}`}
                  >
                    {label}
                    <span className={`text-[10px] font-mono ${active ? "text-white/70" : "text-[var(--muted)]"}`}>{count}</span>
                  </button>
                );
              })}
              <span className="text-[11px] text-[var(--muted)] italic ml-2">Refreshed within 5 days · or longer.</span>
            </div>
          </div>

          {/* Scrolling grid — the only part that scrolls */}
          <div className="flex-1 min-h-0 overflow-y-auto pr-2 -mr-2" data-testid="learn-scroll">
            {filtered.length === 0 ? (
              <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center" data-testid="learn-empty">
                <BookOpen className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
                <p className="akki-lead mb-2">
                  {q.trim()
                    ? "Nothing in this tab matches that yet."
                    : `No ${CONTENT_TYPE_LABEL[activeTab]?.toLowerCase() || "items"} yet in this tab.`}
                </p>
                <p className="text-[13px] text-[var(--muted)] mb-5 max-w-md mx-auto">
                  {q.trim()
                    ? <>Ask AKKI to research "<span className="text-[var(--ink)] font-medium">{q.trim()}</span>" and draft you a board-ready article in under a minute.</>
                    : <>Try a topic like "AI in insurance", "auditing LLM outputs", or "shadow AI risk" in the search above.</>}
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
            ) : activeTab === "video" ? (
              <div className="space-y-2 max-w-2xl pb-4" data-testid="learn-grid">
                {filtered.map((v) => <VideoCard key={v.id} v={v} onPlay={() => setVideoPlaying(v)} />)}
              </div>
            ) : (
              <div className="space-y-2 max-w-2xl pb-4" data-testid="learn-grid">
                {filtered.map((a) => <ArticleCard key={a.id} a={a} />)}
              </div>
            )}

            {/* "View more" — opens a medium modal with editor-curated further
                reading for the active tab (and current topic filter). */}
            {filtered.length > 0 && (
              <div className="pb-6 pt-2 flex justify-center">
                <button
                  type="button"
                  onClick={() => setMoreOpen(true)}
                  className="group inline-flex items-center gap-2 px-5 py-2.5 text-[13px] border border-[var(--rule)] bg-white hover:bg-[var(--cream-deep)] hover:border-[var(--accent)]/40 rounded-full transition-colors text-[var(--deep)] hover:text-[var(--ink)]"
                  data-testid="learn-view-more-btn"
                >
                  <BookOpen className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
                  <span>View more {CONTENT_TYPE_LABEL[activeTab]?.toLowerCase() || "reading"}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" strokeWidth={1.8} />
                </button>
              </div>
            )}
          </div>
        </main>
      </div>

      <VideoModal
        open={!!videoPlaying}
        onOpenChange={(o) => { if (!o) setVideoPlaying(null); }}
        video={videoPlaying}
      />

      <LearnMoreModal
        open={moreOpen}
        onOpenChange={setMoreOpen}
        tab={activeTab}
        topic={topic}
      />
    </AppShell>
  );
}
