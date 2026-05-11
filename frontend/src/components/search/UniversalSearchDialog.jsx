/**
 * Phase F0 — UniversalSearchDialog.
 *
 * Replaces the F0.0 hijack where Cmd+K opened a context switcher.
 * Now Cmd+K opens THIS dialog. The dialog:
 *
 *  - federates `GET /api/search?q=...` across the user's memberships
 *  - groups results by company, then by surface
 *  - shows a "Here" chip on rows whose context_id === activeContext.id
 *  - shows the company name as a coloured chip on cross-context rows
 *  - on row click:
 *      same-context  → navigate directly to deep_link, close dialog
 *      cross-context → open <ConfirmContextSwitchModal /> (parent owns it)
 *
 * Event contract
 * --------------
 * Listens for the global `akki:open-search` custom event. AppShell
 * mounts exactly ONE instance. The `useKeyboardShortcuts` hook
 * dispatches `akki:open-search` on Cmd/Ctrl+K. The legacy
 * `akki:open-palette` event is still listened to as an alias so any
 * stale callers don't break, but the *intended* event is the new one.
 *
 * Empty-state copy is spec-mandated; do not edit without a spec update.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Search, ArrowRight, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { SearchResultRow } from "@/components/search/SearchResultRow";

const DEBOUNCE_MS = 300;
const RESULTS_LIMIT = 25;

export default function UniversalSearchDialog({ onCrossContextRequest }) {
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  // Open via global event (Cmd+K or top-nav button).
  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("akki:open-search", onOpen);
    // Back-compat — accept the legacy event name too. Phase F0 has
    // re-pointed the keyboard shortcut to the new name, but any
    // stale third-party code that still fires the old event will
    // open THIS dialog now (not the hijack).
    window.addEventListener("akki:open-palette", onOpen);
    return () => {
      window.removeEventListener("akki:open-search", onOpen);
      window.removeEventListener("akki:open-palette", onOpen);
    };
  }, []);

  // Focus input on open; clear state on close.
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQ("");
      setData(null);
      setErr(null);
      setActiveIdx(0);
    }
  }, [open]);

  // Debounced fetch.
  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q || q.trim().length < 2) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const { data: payload } = await api.get(`/search`, {
          params: { q: q.trim(), limit: RESULTS_LIMIT },
        });
        setData(payload);
        setErr(null);
        setActiveIdx(0);
      } catch (e) {
        setErr(e?.response?.data?.detail?.message || "Search failed.");
        setData(null);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [q, open]);

  // Group results by context, then list each in render order.
  const groupedByContext = useMemo(() => {
    if (!data?.results) return [];
    const groups = new Map();
    for (const r of data.results) {
      if (!groups.has(r.context_id)) {
        groups.set(r.context_id, { context_id: r.context_id,
          context_name: r.context_name, rows: [] });
      }
      groups.get(r.context_id).rows.push(r);
    }
    // Active context first; rest alphabetical for stable order.
    const arr = Array.from(groups.values());
    arr.sort((a, b) => {
      if (a.context_id === activeContext?.id) return -1;
      if (b.context_id === activeContext?.id) return 1;
      return (a.context_name || "").localeCompare(b.context_name || "");
    });
    return arr;
  }, [data, activeContext]);

  const flatRows = useMemo(
    () => groupedByContext.flatMap((g) => g.rows),
    [groupedByContext],
  );

  const handleResultClick = useCallback((row) => {
    if (!row) return;
    if (row.context_id === activeContext?.id) {
      setOpen(false);
      navigate(row.deep_link);
      return;
    }
    // Hand off to parent's confirm-switch modal. Keep search dialog
    // open behind so the user can cancel and keep browsing.
    setOpen(false);
    onCrossContextRequest?.(row);
  }, [activeContext, navigate, onCrossContextRequest]);

  // Keyboard nav within results.
  const onKeyDown = (e) => {
    if (!flatRows.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(flatRows.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleResultClick(flatRows[activeIdx]);
    }
  };

  const hasQuery = q.trim().length >= 2;
  const noResults = hasQuery && !loading && data && data.total === 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="rounded-sm max-w-2xl p-0 overflow-hidden"
        onKeyDown={onKeyDown}
        data-testid="universal-search-dialog"
      >
        <DialogHeader className="sr-only">
          <DialogTitle>Search across your companies</DialogTitle>
          <DialogDescription>
            Search across your companies. Results from other companies
            will ask before opening.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-3 border-b border-[#E1E6ED] px-4 py-3">
          <Search className="w-4 h-4 text-slate-400" strokeWidth={1.8} />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search documents, chats, signals, goals…"
            className="flex-1 bg-transparent outline-none text-sm placeholder:text-slate-400"
            data-testid="universal-search-input"
          />
          {loading && <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />}
          <kbd className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-sm">
            esc
          </kbd>
        </div>

        <div className="max-h-[28rem] overflow-y-auto" data-testid="universal-search-results">
          {!hasQuery && (
            <p className="px-4 py-6 text-[12px] text-slate-500 akki-sans" data-testid="universal-search-empty-hint">
              Search across your companies. Results from other companies
              will ask before opening.
            </p>
          )}
          {err && (
            <p className="px-4 py-4 text-[12px] text-red-700" data-testid="universal-search-error">
              {err}
            </p>
          )}
          {noResults && (
            <p className="px-4 py-6 text-[12px] text-slate-600 akki-sans" data-testid="universal-search-no-results">
              No results found for &ldquo;{q.trim()}&rdquo;. Try different
              keywords, or switch company to search elsewhere.
            </p>
          )}
          {groupedByContext.map((g) => (
            <div key={g.context_id} className="border-b border-[#F0F2F5] last:border-b-0">
              <div className="px-4 pt-3 pb-1 flex items-center gap-2">
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400 akki-sans">
                  {g.context_name}
                </p>
                {g.context_id === activeContext?.id && (
                  <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-[var(--accent)]/10 text-[var(--accent)]">
                    Here
                  </span>
                )}
                <span className="text-[10px] text-slate-400 ml-auto">
                  {g.rows.length} {g.rows.length === 1 ? "result" : "results"}
                </span>
              </div>
              {g.rows.map((r) => (
                <SearchResultRow
                  key={`${r.context_id}:${r.surface}:${r.id}`}
                  row={r}
                  isCurrentContext={r.context_id === activeContext?.id}
                  active={flatRows[activeIdx] === r}
                  onClick={() => handleResultClick(r)}
                />
              ))}
            </div>
          ))}
        </div>

        {hasQuery && data && data.total > 0 && (
          <div className="border-t border-[#E1E6ED] px-4 py-2.5 flex items-center justify-between bg-[var(--cream)]/40">
            <span className="text-[11px] text-slate-500 akki-sans">
              {data.total} {data.total === 1 ? "result" : "results"} across {data.per_context.length} {data.per_context.length === 1 ? "company" : "companies"} · {data.latency_ms}ms
            </span>
            <button
              onClick={() => {
                setOpen(false);
                navigate(`/app/search?q=${encodeURIComponent(q.trim())}`);
              }}
              className="text-[11px] text-[var(--accent)] hover:underline flex items-center gap-1 akki-sans"
              data-testid="universal-search-see-all"
            >
              See all results <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
