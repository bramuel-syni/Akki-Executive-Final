import React, { useMemo, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { LEARN_ARTICLES, TOPIC_LABEL } from "@/lib/learnContent";
import {
  ArrowLeft, ArrowRight, BookOpen, ExternalLink, GraduationCap, Search,
  HelpCircle, Clock,
} from "lucide-react";

function ArticleCard({ a }) {
  return (
    <Link
      to={`/app/learn/${a.id}`}
      className="block akki-stream-card group akki-fade-up"
      data-severity="neutral"
      data-testid={`learn-article-${a.id}`}
    >
      <p className="akki-type-badge mb-2">{a.kicker}</p>
      <h3 className="akki-title-22 mb-3 leading-snug">{a.title}</h3>
      <p className="text-[14px] text-[var(--deep)] leading-relaxed mb-4 akki-serif">{a.summary}</p>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-wrap gap-2">
          <span className="akki-context-chip">{TOPIC_LABEL[a.topic] || a.topic}</span>
          {a.audience.map((x) => (
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
        <span>Sourced from: {article.source_name}</span>
        <a
          href={article.source_url}
          target="_blank"
          rel="noreferrer"
          className="akki-gesture"
          data-testid="learn-source-link"
        >
          Open source <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}

export default function Learn() {
  const { id } = useParams();
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("all");

  // Library computations — must run unconditionally to satisfy hook rules
  const topics = useMemo(() => {
    const seen = new Map();
    LEARN_ARTICLES.forEach((a) => seen.set(a.topic, (seen.get(a.topic) || 0) + 1));
    return [["all", "All", LEARN_ARTICLES.length], ...Array.from(seen).map(([k, c]) => [k, TOPIC_LABEL[k] || k, c])];
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return LEARN_ARTICLES.filter((a) => {
      if (topic !== "all" && a.topic !== topic) return false;
      if (!needle) return true;
      return (
        a.title.toLowerCase().includes(needle) ||
        a.summary.toLowerCase().includes(needle) ||
        a.body.toLowerCase().includes(needle)
      );
    });
  }, [q, topic]);

  // Detail view
  if (id) {
    const article = LEARN_ARTICLES.find((a) => a.id === id);
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

  return (
    <AppShell>
      <div className="max-w-[1280px] mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-8 akki-fade-up">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <GraduationCap className="w-3 h-3 text-[var(--accent)]" /> Learn · Module M9
          </p>
          <h1 className="akki-greeting mb-2">A library curated for the board table.</h1>
          <p className="akki-meta max-w-2xl">
            Short reads on AI governance, frameworks, and oversight — written for directors who need to be fluent, not technical. Each article closes with the questions to take into your next meeting.
          </p>
        </div>

        {/* Search + topic chips */}
        <div className="flex items-center gap-4 mb-6 flex-wrap">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search the library…"
              className="w-full pl-9 pr-3 py-2 text-[14px] bg-white border border-[var(--rule)] rounded-md focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
              data-testid="learn-search"
            />
          </div>
          <div className="flex items-center gap-5 border-b border-[var(--rule)] pb-1">
            {topics.map(([key, label, count]) => (
              <button
                key={key}
                data-selected={topic === key}
                onClick={() => setTopic(key)}
                className="akki-scope-chip"
                data-testid={`learn-topic-${key}`}
              >
                {label} <span className="text-[var(--muted)]/70 ml-1">{count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Articles */}
        {filtered.length === 0 ? (
          <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center">
            <BookOpen className="w-8 h-8 text-[var(--muted)]/40 mx-auto mb-3" />
            <p className="akki-lead mb-2">Nothing matches that filter.</p>
            <button onClick={() => { setQ(""); setTopic("all"); }} className="akki-gesture">
              Clear filters <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5" data-testid="learn-grid">
            {filtered.map((a) => <ArticleCard key={a.id} a={a} />)}
          </div>
        )}

        <div className="mt-12 border-t border-[var(--rule)] pt-6 text-[12px] text-[var(--muted)] max-w-3xl">
          <Clock className="w-3 h-3 inline mr-1.5" />
          Content curated from reputable governance authorities including NACD, IoD, Deloitte, Harvard Corporate Governance Forum, Stanford HAI, the WEF, NIST, and the European Commission. Each article links to its primary source. Articles are reviewed quarterly; last review: April 2026.
        </div>
      </div>
    </AppShell>
  );
}
