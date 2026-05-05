/**
 * Solva — production landing surface (post Phase I.1 cutover).
 *
 * Mounted at `/app/solva`. Renders the 4-card centred picker plus the
 * collapsible Recent Sessions block. Picker click → navigate to
 * `/app/solva/session/new?submodule=<key>` (Phase I.2). Resume click →
 * navigate to `/app/solva/session/:sessionId`.
 *
 * The legacy multi-panel session UI (clusters list, in-page synthesis
 * stream, audit drawer) is retired; that surface now lives in
 * `frontend/src/pages/SolvaSession.jsx` as a linear Guided Flow.
 */
import React from "react";
import AppShell from "@/components/layout/AppShell";
import SolvaLanding from "@/components/solva/SolvaLanding";
import { useAuth } from "@/contexts/AuthContext";

export default function SolvaApp() {
  const { account } = useAuth();
  if (!account) return null;

  return (
    <AppShell>
      <SolvaLanding variant="auth" />
    </AppShell>
  );
}
