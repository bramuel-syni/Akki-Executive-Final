/**
 * Phase F0.5 — Universal Search full results page.
 *
 * Route: /app/search?q=...
 *
 * Layout:
 *  - Search input prefilled from ?q, live-editable, debounced 300 ms.
 *  - Category tabs: All, Documents, Signals, Goals, Chats.
 *    (Cycle / Work Studio / Briefs are tab-disabled today — Phase 2.)
 *  - Context filter dropdown: All companies (default) or one company.
 *  - Sort: Relevance (default) or Recent first.
 *  - Pagination: 25 per page, server-side `offset`.
 *  - Same confirm-before-switch behaviour on row click as the dialog.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { Search, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { SearchResultRow } from "@/components/search/SearchResultRow";
import ConfirmContextSwitchModal from "@/components/search/ConfirmContextSwitchModal";

const PAGE_SIZE = 25;
const DEBOUNCE_MS = 300;

const TABS = [
  { id: "all", label: "All", surface: null, enabled: true },
  { id: "documents", label: "Documents", surface: "documents", enabled: true },
  { id: "pulse", label: "Signals", surface: "pulse", enabled: true },
  { id: "monitor", label: "Goals", surface: "monitor", enabled: true },
  { id: "chats", label: "Chats", surface: "chats", enabled: true },
  { id: "cycle", label: "Cycle", surface: "cycle", enabled: false },
  { id: "work_studio", label: "Work Studio", surface: "work_studio", enabled: false },
  { id: "briefs", label: "Briefs", surface: "briefs", enabled: false },
];

export default function SearchResults() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { activeContext, contexts } = useAuth();
  const [q, setQ] = useState(params.get("q") || "");
  const [tab, setTab] = useState("all");
  const [scopeContext, setScopeContext] = useState("");   // "" = all
  const [sort, setSort] = useState("relevance");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [pending, setPending] = useState(null);
  const debounceRef = useRef(null);

  // Keep ?q= in sync with the input.
  useEffect(() => {
    const current = params.get("q") || "";
    if (current !== q) {
      const next = new URLSearchParams(params);
      if (q) next.set("q", q); else next.delete("q");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const surface = useMemo(() => {
    const t = TABS.find((x) => x.id === tab);
    return t?.surface || null;
  }, [tab]);

  // Fetch on q/tab/scope/sort/offset change. Debounce only the q
  // typing path.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q || q.trim().length < 2) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const queryParams = {
          q: q.trim(),
          limit: PAGE_SIZE,
          offset,
        };
        if (surface) queryParams.surface = surface;
        if (scopeContext) queryParams.context_id = scopeContext;
        const { data: payload } = await api.get(`/search`, { params: queryParams });
        // Client-side date sort if "recent" requested.
        if (sort === "recent" && payload?.results) {
          payload.results = [...payload.results].sort(
            (a, b) => (b.date || "").localeCompare(a.date || ""),
          );
        }
        setData(payload);
        setErr(null);
      } catch (e) {
        setErr(e?.response?.data?.detail?.message || "Search failed.");
        setData(null);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [q, surface, scopeContext, sort, offset]);

  // Reset offset when filter dimensions change.
  useEffect(() => { setOffset(0); }, [q, tab, scopeContext, sort]);

  const handleClick = useCallback((row) => {
    if (row.context_id === activeContext?.id) {
      navigate(row.deep_link);
      return;
    }
    setPending({
      from_context_id: activeContext?.id,
      from_context_name: activeContext?.name,
      to_context_id: row.context_id,
      to_context_name: row.context_name,
      surface: row.surface,
      result_id: row.id,
      deep_link: row.deep_link,
      type: row.type,
    });
  }, [activeContext, navigate]);

  const scopeLabel = scopeContext
    ? (contexts?.find((c) => c.id === scopeContext)?.name || "this company")
    : "your companies";
  const hasQuery = q.trim().length >= 2;
  const noResults = hasQuery && !loading && data && data.total === 0;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-6">
        <h1 className="text-2xl akki-serif text-[var(--navy)] mb-4">Search</h1>

        <div className="bg-white border border-[var(--rule)] rounded-sm">
          <div className="flex items-center gap-3 border-b border-[#E1E6ED] px-4 py-3">
            <Search className="w-4 h-4 text-slate-400" strokeWidth={1.8} />
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search documents, chats, signals, goals…"
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-slate-400"
              data-testid="search-results-input"
            />
            {loading && <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />}
          </div>

          {/* Tabs + filters */}
          <div className="border-b border-[#E1E6ED] px-4 py-2.5 flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1" data-testid="search-results-tabs">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => t.enabled && setTab(t.id)}
                  disabled={!t.enabled}
                  data-testid={`search-results-tab-${t.id}`}
                  className={[
                    "px-2.5 py-1 text-[12px] rounded-sm akki-sans",
                    tab === t.id
                      ? "bg-[var(--accent)]/10 text-[var(--accent)]"
                      : "text-slate-600 hover:bg-slate-50",
                    !t.enabled && "opacity-40 cursor-not-allowed",
                  ].join(" ")}
                >
                  {t.label}
                  {!t.enabled && <span className="ml-1 text-[9px] uppercase">soon</span>}
                </button>
              ))}
            </div>
            <div className="ml-auto flex items-center gap-2">
              <label className="text-[11px] text-slate-500 akki-sans">Company</label>
              <select
                value={scopeContext}
                onChange={(e) => setScopeContext(e.target.value)}
                data-testid="search-results-scope-select"
                className="text-[12px] border border-[var(--rule)] rounded-sm px-2 py-1 bg-white"
              >
                <option value="">All companies</option>
                {(contexts || []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <label className="text-[11px] text-slate-500 akki-sans">Sort</label>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                data-testid="search-results-sort-select"
                className="text-[12px] border border-[var(--rule)] rounded-sm px-2 py-1 bg-white"
              >
                <option value="relevance">Relevance</option>
                <option value="recent">Recent first</option>
              </select>
            </div>
          </div>

          <div className="min-h-[8rem]">
            {!hasQuery && (
              <p className="px-4 py-6 text-[12px] text-slate-500 akki-sans">
                Type at least 2 characters to search.
              </p>
            )}
            {err && (
              <p className="px-4 py-4 text-[12px] text-red-700" data-testid="search-results-error">
                {err}
              </p>
            )}
            {noResults && (
              <p className="px-4 py-6 text-[12px] text-slate-600 akki-sans" data-testid="search-results-empty">
                No results found for &ldquo;{q.trim()}&rdquo; in {scopeLabel}.
                Try different keywords, or change the company filter to search elsewhere.
              </p>
            )}
            {data?.results?.map((r) => (
              <SearchResultRow
                key={`${r.context_id}:${r.surface}:${r.id}`}
                row={r}
                isCurrentContext={r.context_id === activeContext?.id}
                onClick={() => handleClick(r)}
              />
            ))}
          </div>

          {hasQuery && data && data.total > PAGE_SIZE && (
            <div className="border-t border-[#E1E6ED] px-4 py-2.5 flex items-center justify-between bg-[var(--cream)]/40">
              <span className="text-[11px] text-slate-500 akki-sans">
                Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                  disabled={offset === 0}
                  className="text-[11px] px-2 py-1 border border-[var(--rule)] rounded-sm hover:bg-slate-50 disabled:opacity-40 akki-sans"
                  data-testid="search-results-prev"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset((o) => o + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= (data.total || 0)}
                  className="text-[11px] px-2 py-1 border border-[var(--rule)] rounded-sm hover:bg-slate-50 disabled:opacity-40 akki-sans"
                  data-testid="search-results-next"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
      <ConfirmContextSwitchModal pending={pending} onClose={() => setPending(null)} />
    </AppShell>
  );
}
