/*
 * SolvaApp.jsx — authenticated /app/solva landing.
 *
 * Renders the picker (`<SolvaLanding variant="auth">`) and forwards
 * any `?seed_kind=&seed_id=` query params to the picker. Wave 1.1
 * (UAT pack) added the seed plumbing: when a sibling surface
 * (Document Journal, Pulse, Cycle Manager, an existing Solva
 * artefact) hands off via `<HandoffActions kind="..."/>`, the
 * picker reads the seed and forwards it to the session-create
 * POST so framing pre-population works end-to-end.
 *
 * URL is cleaned after capture (history.replace) so a refresh
 * doesn't re-seed.
 */
import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import SolvaLanding from "@/components/solva/SolvaLanding";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";

export default function SolvaApp() {
  const [params, setParams] = useSearchParams();
  // Capture once on mount so we don't keep re-reading after the URL
  // is cleaned. The seed flows through state, not URL.
  const initialSeed = useMemo(() => {
    const k = (params.get("seed_kind") || "").trim();
    const i = (params.get("seed_id") || "").trim();
    return k && i ? { kind: k, id: i } : null;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [seed] = useState(initialSeed);

  // Strip the params from the URL so refresh doesn't re-seed.
  useEffect(() => {
    if (initialSeed) {
      const next = new URLSearchParams(params);
      next.delete("seed_kind");
      next.delete("seed_id");
      setParams(next, { replace: true });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="solva">
        {/* Phase E Sub-task E (2026-05-16) — Trust verified by Synisense CTA */}
        <div
          data-testid="solva-trust-banner"
          className="mx-auto mb-6 mt-4 flex max-w-3xl items-center gap-3 rounded-md border border-emerald-200/70 bg-emerald-50/70 px-4 py-2 text-sm text-emerald-900"
        >
          <span className="text-emerald-600" aria-hidden>✓</span>
          <span>
            <strong>Trust verified by Synisense</strong> — every reasoning step
            is governed and auditable.
          </span>
          <a
            href="/app/solva/sessions"
            data-testid="solva-trust-banner-view-audit"
            className="ml-auto text-emerald-700 underline-offset-2 hover:underline"
          >
            View audit timeline →
          </a>
        </div>
        <SolvaLanding variant="auth" intakeSeed={seed} />
      </WorkspaceEntryGate>
    </AppShell>
  );
}
