/**
 * BriefsTab — Cycle Manager → Briefs.
 *
 * Phase 13.2 — thin wrapper around <Prepare embedded forceTab="brief" />.
 * Preserves ALL existing Prepare functionality (catch-up brief list,
 * create form with deep-tier toggle + quota meter, validator badge,
 * minutes linkage, brief-detail modal). The only difference vs
 * standalone /app/prepare is the absence of the AppShell wrapper +
 * page H1 + inner line-tab nav, all of which Cycle Manager's outer
 * tab shell already provides.
 */
import React from "react";
import Prepare from "@/pages/Prepare";

export default function BriefsTab() {
  return <Prepare embedded forceTab="brief" />;
}
