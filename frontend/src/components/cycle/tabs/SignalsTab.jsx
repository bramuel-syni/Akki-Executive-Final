/**
 * SignalsTab — Cycle Manager → Signals.
 *
 * Phase 13.2 — thin wrapper around <Prepare embedded forceTab="signals" />.
 * Reuses the existing signals engine (`GET /api/contexts/{cid}/signals`,
 * `POST /api/contexts/{cid}/signals/generate`) and the HighlightsStats
 * sparkline + breakdown bars + confidence footer. The Phase 11
 * citation-chip convention is honoured by the underlying SignalDetailModal.
 */
import React from "react";
import Prepare from "@/pages/Prepare";

export default function SignalsTab() {
  return <Prepare embedded forceTab="signals" />;
}
