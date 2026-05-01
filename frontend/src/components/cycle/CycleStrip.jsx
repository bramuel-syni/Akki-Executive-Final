/**
 * CycleStrip — Phase 2 (Advisory 6).
 *
 * Horizontal timeline of the 6 board cycle phases pinned at the top of
 * Home + /app/cycle. Each phase is a clickable pill that opens a side
 * panel showing the artefact summary for that phase against the current
 * cycle window.
 *
 * Visual rules (binding via /app/docs/ux-advisories-v1.md):
 *  - Current phase  → oxblood pill, white text, akki-overline label
 *  - Past phases    → cream pill, muted text
 *  - Future phases  → faded cream pill + dashed border, muted/50 text
 *
 * Mobile: the row becomes scroll-snap horizontal (touch-friendly), and
 * the side panel becomes a bottom Sheet (handled by CyclePhaseSheet).
 *
 * Collapse arrow toggles the strip to a single-line breadcrumb summary.
 */
import React, { useCallback, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, ChevronUp, Settings } from "lucide-react";
import useCycleConfig from "@/hooks/useCycleConfig";
import { useAuth } from "@/contexts/AuthContext";
import CyclePhaseSheet from "@/components/cycle/CyclePhaseSheet";
import { Button } from "@/components/ui/button";

function emphasisFor(phase, currentPhase) {
  if (!phase || !currentPhase) return "upcoming";
  if (phase.id === currentPhase.id) return "current";
  if ((phase.order ?? 0) < (currentPhase.order ?? 0)) return "past";
  return "upcoming";
}

function prettyDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  } catch (_) {
    return iso;
  }
}

export default function CycleStrip({ contextId, isMobile = false }) {
  const navigate = useNavigate();
  const { account, activeContext } = useAuth();
  const cid = contextId || activeContext?.id;
  const {
    config, loading, error, currentPhase, loadPhaseSummary, advancePhase, acting,
  } = useCycleConfig(cid);

  const [collapsed, setCollapsed] = useState(false);
  const [openPhase, setOpenPhase] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const isOwnerOrAdmin = useMemo(() => {
    if (!activeContext || !account) return false;
    return activeContext.owner_account_id === account.id
      || activeContext.my_sub_role === "admin";
  }, [activeContext, account]);

  const phases = useMemo(
    () => (config?.phases ? [...config.phases].sort((a, b) => a.order - b.order) : []),
    [config],
  );

  const handlePhaseClick = useCallback((phase) => {
    setOpenPhase(phase);
    setSheetOpen(true);
  }, []);

  const handleAdvance = useCallback(async () => {
    if (!isOwnerOrAdmin || acting) return;
    await advancePhase();
  }, [isOwnerOrAdmin, acting, advancePhase]);

  if (error) {
    return (
      <section className="border border-[var(--rule)] bg-white px-4 py-3 mb-6 rounded-sm">
        <p className="text-[12px] text-[var(--muted)] italic">{error}</p>
      </section>
    );
  }

  if (loading && !config) {
    return (
      <section className="border border-[var(--rule)] bg-white px-4 py-3 mb-6 rounded-sm">
        <p
          className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse"
          data-testid="cycle-strip-loading"
        >
          Reading the cycle…
        </p>
      </section>
    );
  }

  if (!config || phases.length === 0) return null;

  return (
    <section
      className="bg-white border border-[var(--rule)] rounded-sm mb-8 akki-fade-up"
      data-testid="cycle-strip"
      data-collapsed={collapsed ? "true" : "false"}
    >
      {/* Header chrome */}
      <header className="flex items-center justify-between px-4 md:px-5 py-3 border-b border-[var(--rule)]">
        <div className="min-w-0 flex-1">
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-0.5">
            Current board cycle
          </p>
          <p
            className="akki-serif text-[14px] text-[var(--ink)] truncate"
            data-testid="cycle-strip-cycle-started"
          >
            Cycle started {prettyDate(config.cycle_started_at)}
            {currentPhase ? (
              <span className="text-[var(--muted)]"> · currently in {currentPhase.name}</span>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-3">
          {isOwnerOrAdmin ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleAdvance}
              disabled={acting}
              className="h-8 px-2 text-[11px] text-[var(--muted)] hover:text-[var(--ink)] uppercase tracking-[0.16em]"
              data-testid="cycle-strip-advance"
            >
              {acting ? "Advancing…" : "Advance phase"}
            </Button>
          ) : null}
          <Link
            to="/app/settings/cycle"
            title="Cycle settings"
            className="inline-flex items-center justify-center w-8 h-8 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream)]"
            data-testid="cycle-strip-settings"
            onClick={(e) => {
              // Cleaner intent capture for analytics if added later.
              if (e.metaKey || e.ctrlKey) return;
              e.preventDefault();
              navigate("/app/settings/cycle");
            }}
          >
            <Settings className="w-3.5 h-3.5" />
          </Link>
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            className="inline-flex items-center justify-center w-8 h-8 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream)]"
            data-testid="cycle-strip-collapse"
            aria-label={collapsed ? "Expand cycle strip" : "Collapse cycle strip"}
          >
            {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </header>

      {/* Body — full strip OR collapsed breadcrumb */}
      {collapsed ? (
        <div
          className="px-4 md:px-5 py-3 text-[12px] text-[var(--muted)] truncate"
          data-testid="cycle-strip-breadcrumb"
        >
          {phases.map((p, i) => (
            <span key={p.id} className="inline-flex items-center">
              <span
                className={
                  p.id === currentPhase?.id
                    ? "text-[var(--accent)] akki-overline tracking-[0.16em]"
                    : ""
                }
              >
                {p.name}
              </span>
              {i < phases.length - 1 ? (
                <ChevronRight className="w-3 h-3 mx-1.5 text-[var(--rule)]" />
              ) : null}
            </span>
          ))}
        </div>
      ) : (
        <div
          className="px-3 md:px-5 py-4 overflow-x-auto"
          data-testid="cycle-strip-track"
          style={{ scrollSnapType: isMobile ? "x mandatory" : undefined }}
        >
          <ul className="flex items-stretch gap-0 min-w-max md:min-w-0 md:w-full">
            {phases.map((phase, idx) => {
              const e = emphasisFor(phase, currentPhase);
              const pillClass =
                e === "current"
                  ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                  : e === "past"
                    ? "bg-[var(--cream)] text-[var(--muted)] border-[var(--rule)]"
                    : "bg-[var(--cream)]/60 text-[var(--muted)]/60 border-dashed border-[var(--rule)]";
              return (
                <li
                  key={phase.id}
                  className="flex items-center md:flex-1 last:flex-none"
                  style={{ scrollSnapAlign: isMobile ? "start" : undefined }}
                >
                  <button
                    type="button"
                    onClick={() => handlePhaseClick(phase)}
                    data-phase-id={phase.id}
                    data-phase-emphasis={e}
                    data-testid={`cycle-strip-phase-${phase.id}`}
                    className={`group relative flex-1 md:w-full px-3 py-2.5 border min-h-[64px] min-w-[120px] text-left rounded-sm transition-all duration-150 hover:scale-[1.01] ${pillClass}`}
                    aria-current={e === "current" ? "step" : undefined}
                  >
                    <p className={`akki-overline text-[9.5px] tracking-[0.18em] mb-0.5 ${
                      e === "current" ? "text-white/80" : "text-[var(--muted)]"
                    }`}>
                      Phase {idx + 1}
                    </p>
                    <p className={`akki-serif text-[13px] leading-[1.25] font-normal ${
                      e === "current" ? "text-white" : ""
                    }`}>
                      {phase.name}
                    </p>
                    <p className={`text-[10.5px] mt-1 ${
                      e === "current" ? "text-white/70" : "text-[var(--muted)]/80"
                    }`}>
                      {phase.default_duration_days}d
                    </p>
                  </button>
                  {idx < phases.length - 1 ? (
                    <span
                      aria-hidden="true"
                      className={`hidden md:block h-px w-3 ${
                        e === "past" ? "bg-[var(--rule)]" : "bg-[var(--rule)]/60"
                      }`}
                    />
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <CyclePhaseSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        phase={openPhase}
        emphasis={emphasisFor(openPhase, currentPhase)}
        loadSummary={loadPhaseSummary}
        isMobile={isMobile}
      />
    </section>
  );
}
