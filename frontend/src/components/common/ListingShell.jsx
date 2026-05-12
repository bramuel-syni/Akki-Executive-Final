/**
 * ListingShell — shared list surface for Work Studio, Cycle Manager,
 * and Monitor.
 *
 * Layers (top → bottom):
 *   1. Header row: title + subtitle (editorial) + headerRight slot
 *   2. Controls row: search input (debounced 250ms) + optional sort dropdown
 *   3. Filter tabs (editorial strip — ink-on-parchment active, graphite inactive)
 *   4. Body slot — caller renders the card grid / list
 *   5. Footer: pagination "Page N of M" + prev/next (hidden when total<=pageSize)
 *
 * Behaviour:
 *   • Search input is debounced — typing fires onSearchChange after 250ms idle.
 *   • Page change preserves search + filter + sort (caller-owned URL params).
 *   • Loading state: skeleton rows in the body area.
 *   • Empty state: rendered when totalCount===0 AND not loading.
 *   • Keyboard: `/` focuses search (when not already in an input); Esc clears.
 *
 * v7 palette only; no hex literals.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, ChevronLeft, ChevronRight, ArrowUpDown } from "lucide-react";


function SkeletonRow({ i }) {
  return (
    <div
      className="border border-[var(--rule)] rounded-sm bg-white px-4 py-3 animate-pulse"
      data-testid={`listing-skeleton-${i}`}
      aria-hidden="true"
    >
      <div className="h-3 bg-[var(--parchment)] rounded w-2/3 mb-2" />
      <div className="h-2 bg-[var(--parchment)] rounded w-1/3" />
    </div>
  );
}


function FilterTabs({ filterTabs, activeFilterKey, onFilterChange }) {
  return (
    <nav
      className="flex items-center gap-0 border-b border-[var(--rule)] -mb-px"
      data-testid="listing-filter-tabs"
      aria-label="Filter"
    >
      {filterTabs.map((t) => {
        const active = activeFilterKey === t.key;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onFilterChange(t.key)}
            aria-current={active ? "page" : undefined}
            className={[
              "px-4 py-2.5 text-[12.5px] uppercase tracking-[0.10em] font-mono transition-colors border-b-2 -mb-px inline-flex items-center gap-1.5",
              active
                ? "text-[var(--ink)] border-[color:var(--oxblood)] font-medium"
                : "text-[var(--muted)] border-transparent hover:text-[var(--ink)]",
            ].join(" ")}
            data-testid={`listing-filter-tab-${t.key}${active ? "-active" : ""}`}
          >
            {t.label}
            {typeof t.count === "number" && (
              <span
                className={[
                  "text-[10px] font-mono ml-0.5",
                  active ? "text-[var(--muted)]" : "text-[var(--muted)]/70",
                ].join(" ")}
              >
                · {t.count}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}


export default function ListingShell({
  title,
  subtitle,
  headerRight,
  searchValue,
  onSearchChange,
  searchPlaceholder = "Search…",
  filterTabs = [],
  activeFilterKey,
  onFilterChange,
  sortOptions,
  activeSortKey,
  onSortChange,
  pageSize,
  page,
  totalCount,
  onPageChange,
  isLoading = false,
  emptyState,
  children,
  testId = "listing-shell",
}) {
  // Debounced search — fires onSearchChange after 250ms idle.
  const [localSearch, setLocalSearch] = useState(searchValue || "");
  const searchRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    // Keep local in sync when caller resets the value (e.g. clear filter).
    if (searchValue !== localSearch) setLocalSearch(searchValue || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchValue]);

  const onLocalChange = (v) => {
    setLocalSearch(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearchChange && onSearchChange(v);
    }, 250);
  };

  // Keyboard shortcuts: `/` focus, Esc clear.
  useEffect(() => {
    const onKey = (e) => {
      const inField = e.target && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
      if (e.key === "/" && !inField) {
        e.preventDefault();
        searchRef.current && searchRef.current.focus();
      } else if (e.key === "Escape" && document.activeElement === searchRef.current) {
        onLocalChange("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((totalCount || 0) / Math.max(1, pageSize))),
    [totalCount, pageSize],
  );
  const showPagination = (totalCount || 0) > pageSize;
  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <section data-testid={testId}>
      {/* Header */}
      {(title || subtitle || headerRight) && (
        <header className="flex items-end justify-between gap-4 mb-5" data-testid={`${testId}-header`}>
          <div className="flex-1 min-w-0">
            {title && (
              <h2
                className="akki-serif text-[22px] text-[var(--ink)] leading-tight"
                data-testid={`${testId}-title`}
              >
                {title}
              </h2>
            )}
            {subtitle && (
              <p
                className="akki-meta text-[12.5px] mt-1.5 max-w-prose"
                data-testid={`${testId}-subtitle`}
              >
                {subtitle}
              </p>
            )}
          </div>
          {headerRight && (
            <div className="shrink-0" data-testid={`${testId}-header-right`}>
              {headerRight}
            </div>
          )}
        </header>
      )}

      {/* Controls row */}
      <div
        className="flex items-center gap-3 mb-3"
        data-testid={`${testId}-controls`}
      >
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)] pointer-events-none" />
          <Input
            ref={searchRef}
            value={localSearch}
            onChange={(e) => onLocalChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="rounded-sm pl-9 text-[13.5px]"
            data-testid={`${testId}-search`}
            aria-label="Search"
          />
        </div>
        {sortOptions && sortOptions.length > 0 && (
          <div className="relative">
            <ArrowUpDown className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)] pointer-events-none" />
            <select
              value={activeSortKey || sortOptions[0]?.key}
              onChange={(e) => onSortChange && onSortChange(e.target.value)}
              className="text-[12.5px] font-mono uppercase tracking-[0.08em] pl-7 pr-7 py-2 border border-[var(--rule)] rounded-sm bg-white text-[var(--ink)] cursor-pointer"
              data-testid={`${testId}-sort`}
              aria-label="Sort"
            >
              {sortOptions.map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Filter tabs */}
      {filterTabs.length > 0 && (
        <FilterTabs
          filterTabs={filterTabs}
          activeFilterKey={activeFilterKey}
          onFilterChange={onFilterChange}
        />
      )}

      {/* Body */}
      <div className="mt-4" data-testid={`${testId}-body`}>
        {isLoading ? (
          <div className="space-y-2" data-testid={`${testId}-loading`}>
            {[0, 1, 2].map((i) => <SkeletonRow key={i} i={i} />)}
          </div>
        ) : (totalCount || 0) === 0 ? (
          emptyState || (
            <div
              className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-10 text-center"
              data-testid={`${testId}-empty`}
            >
              <p className="akki-serif text-[15px] text-[var(--ink)]">Nothing here yet.</p>
              <p className="akki-meta text-[12.5px] mt-1">Try clearing the search or switching tabs.</p>
            </div>
          )
        ) : (
          children
        )}
      </div>

      {/* Pagination */}
      {showPagination && !isLoading && (
        <div
          className="flex items-center justify-between mt-5 pt-4 border-t border-[var(--rule)]"
          data-testid={`${testId}-pagination`}
        >
          <p className="akki-meta text-[11.5px] font-mono">
            Page {page} of {totalPages} · {totalCount} total
          </p>
          <div className="flex gap-2">
            <Button
              size="sm" variant="outline"
              disabled={!canPrev}
              onClick={() => canPrev && onPageChange(page - 1)}
              className="text-[12.5px]"
              data-testid={`${testId}-prev`}
            >
              <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Previous
            </Button>
            <Button
              size="sm" variant="outline"
              disabled={!canNext}
              onClick={() => canNext && onPageChange(page + 1)}
              className="text-[12.5px]"
              data-testid={`${testId}-next`}
            >
              Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
