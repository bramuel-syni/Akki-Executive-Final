/**
 * AcrossBoardsPanel — Phase E.0.3 frontend surface.
 *
 * Renders the "Across other boards" cross-board metadata patterns
 * sourced from GET /api/contexts/{cid}/pulse/across-boards.
 *
 * Privacy contract: this component renders ONLY metadata fields
 * returned by the aggregator (signature_kind, signature_value,
 * other_boards_count, active_board_count, first/last_seen_other).
 * The aggregator NEVER returns source_artefact_id, source-board
 * name, or any payload — by construction the side-drawer cannot
 * leak those because they are not in the response.
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  Globe2, Building2, Loader2, ChevronRight, ShieldCheck,
  Scale, Briefcase, AlertTriangle, Users,
} from "lucide-react";

const KIND_LABEL = {
  regulatory_ref:    "Regulatory reference",
  governance_theme:  "Governance theme",
  pulse_class:       "Pulse class",
};

const KIND_ICON = {
  regulatory_ref:    Scale,
  governance_theme:  Briefcase,
  pulse_class:       AlertTriangle,
};

const PULSE_VALUE_LABEL = {
  capital:    "Capital",
  succession: "Succession",
  regulatory: "Regulatory",
  cyber:      "Cyber",
};

const GOVERNANCE_VALUE_LABEL = {
  audit:        "Audit",
  risk:         "Risk",
  remuneration: "Remuneration",
  nomination:   "Nomination",
};

function patternLabel(p) {
  if (p.signature_kind === "pulse_class") {
    return PULSE_VALUE_LABEL[p.signature_value] || p.signature_value;
  }
  if (p.signature_kind === "governance_theme") {
    return GOVERNANCE_VALUE_LABEL[p.signature_value] || p.signature_value;
  }
  return p.signature_value;
}

function relTime(iso) {
  if (!iso) return "";
  const t = new Date(iso);
  const now = Date.now();
  const days = Math.floor((now - t.getTime()) / 86400000);
  if (days < 1) return "today";
  if (days < 2) return "yesterday";
  if (days < 14) return `${days} days ago`;
  return `${Math.floor(days / 7)} weeks ago`;
}

export default function AcrossBoardsPanel({ contextId }) {
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [drawerPattern, setDrawerPattern] = useState(null);

  useEffect(() => {
    if (!contextId) return;
    let alive = true;
    setLoading(true);
    setErr(null);
    api
      .get(`/contexts/${contextId}/pulse/across-boards?window_days=30&limit=24`)
      .then(({ data }) => {
        if (!alive) return;
        setPatterns(data?.patterns || []);
      })
      .catch((e) => { if (alive) setErr(apiErrorMessage(e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [contextId]);

  if (loading) {
    return (
      <section
        className="border border-[var(--rule)] bg-[var(--cream-deep)]/30 rounded-md px-5 py-4 mb-5"
        data-testid="pulse-across-boards-loading"
      >
        <div className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
          <Globe2 className="w-3 h-3" /> Across other boards
        </div>
        <div className="py-3 text-center">
          <Loader2 className="w-3.5 h-3.5 mx-auto animate-spin text-[var(--accent)]" />
        </div>
      </section>
    );
  }
  if (err) return null; // honest-render — silent on error
  if (!patterns || patterns.length === 0) {
    return (
      <section
        className="border border-[var(--rule)] bg-[var(--cream-deep)]/30 rounded-md px-5 py-4 mb-5"
        data-testid="pulse-across-boards-empty"
      >
        <div className="akki-overline text-[var(--muted)] mb-1.5 inline-flex items-center gap-1.5">
          <Globe2 className="w-3 h-3" /> Across other boards
        </div>
        <p className="text-[12.5px] text-[var(--muted)]">
          No patterns shared between this board and other boards yet. Patterns surface when ≥ 2 boards share the same regulatory reference, governance theme, or signal class.
        </p>
      </section>
    );
  }

  return (
    <>
      <section
        className="border border-[var(--rule)] bg-[var(--cream-deep)]/30 rounded-md px-5 py-4 mb-5"
        data-testid="pulse-across-boards"
        aria-label="Patterns appearing on other boards"
      >
        <div className="flex items-baseline justify-between gap-3 mb-3 flex-wrap">
          <p className="akki-overline text-[var(--muted)] inline-flex items-center gap-1.5">
            <Globe2 className="w-3 h-3" /> Across other boards
          </p>
          <p className="text-[11px] text-[var(--muted)] font-mono inline-flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" /> metadata only · 30 days
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5" data-testid="pulse-across-boards-tiles">
          {patterns.map((p, idx) => {
            const Icon = KIND_ICON[p.signature_kind] || AlertTriangle;
            return (
              <button
                key={`${p.signature_kind}::${p.signature_value}::${idx}`}
                type="button"
                onClick={() => setDrawerPattern(p)}
                className="text-left border border-[var(--rule)] bg-white rounded-md px-4 py-3 hover:border-[var(--accent)] transition-colors group"
                data-testid={`pulse-across-boards-tile-${p.signature_kind}-${p.signature_value.replace(/[^a-z0-9]/gi, "-").toLowerCase()}`}
              >
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <p className="akki-serif text-[13.5px] text-[var(--ink)] inline-flex items-center gap-1.5">
                    <Icon className="w-3 h-3 text-[var(--muted)]" strokeWidth={1.7} />
                    {patternLabel(p)}
                  </p>
                  <ChevronRight className="w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--accent)]" />
                </div>
                <p className="text-[11.5px] text-[var(--muted)]">
                  <strong className="text-[var(--ink)] font-medium">{p.other_boards_count}</strong>{" "}
                  other board{p.other_boards_count === 1 ? "" : "s"} · last seen {relTime(p.last_seen_other)}
                  {p.active_board_count > 0 && (
                    <> · <span className="text-[var(--accent)]">{p.active_board_count} on this board</span></>
                  )}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Side-drawer detail. Renders ONLY metadata. The aggregator
          response carries no source-board name, no artefact id, no
          payload — by construction the drawer cannot leak. */}
      <Sheet open={!!drawerPattern} onOpenChange={(v) => !v && setDrawerPattern(null)}>
        <SheetContent
          className="w-full sm:max-w-[480px] bg-[var(--cream)]"
          data-testid="pulse-across-boards-drawer"
        >
          {drawerPattern && (
            <>
              <SheetHeader>
                <SheetTitle className="akki-serif text-[var(--ink)]">
                  {patternLabel(drawerPattern)}
                </SheetTitle>
                <SheetDescription>
                  {KIND_LABEL[drawerPattern.signature_kind] || "Pattern"}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-5 space-y-4">
                <div className="border border-[var(--rule)] bg-white rounded-md px-4 py-3">
                  <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
                    <Building2 className="w-3 h-3" /> Spread
                  </p>
                  <p className="akki-serif text-[15px] text-[var(--ink)]" data-testid="pulse-across-boards-drawer-other-count">
                    <strong className="text-[20px]">{drawerPattern.other_boards_count}</strong> other board{drawerPattern.other_boards_count === 1 ? "" : "s"}
                  </p>
                  {drawerPattern.active_board_count > 0 && (
                    <p className="text-[12.5px] text-[var(--muted)] mt-1">
                      Plus <strong className="text-[var(--ink)]">{drawerPattern.active_board_count}</strong> match{drawerPattern.active_board_count === 1 ? "" : "es"} on this board.
                    </p>
                  )}
                </div>
                <div className="border border-[var(--rule)] bg-white rounded-md px-4 py-3">
                  <p className="akki-overline text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
                    <Users className="w-3 h-3" /> Recency
                  </p>
                  <p className="text-[12.5px] text-[var(--ink)] leading-[1.55]">
                    First seen {relTime(drawerPattern.first_seen_other)} · last seen {relTime(drawerPattern.last_seen_other)}.
                  </p>
                </div>
                <div className="border border-amber-200 bg-amber-50 rounded-md px-4 py-3">
                  <p className="text-[11.5px] text-amber-900 leading-[1.55]" data-testid="pulse-across-boards-drawer-privacy-note">
                    <ShieldCheck className="w-3 h-3 inline-block mr-1" />
                    By design we never name which boards. We only show that the same regulatory reference, governance theme, or signal class is on more than one of your boards.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => setDrawerPattern(null)}
                  data-testid="pulse-across-boards-drawer-close"
                >Close</Button>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}
