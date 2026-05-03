/**
 * MinutesTab — Cycle Manager → Minutes.
 *
 * Phase 13.2 — thin wrapper around <Prepare embedded forceTab="minutes" />.
 * Surfaces the past meeting-minutes documents uploaded to the active
 * context, with extract / narrative / to_cycle endpoints used by the
 * underlying minutes UI.
 */
import React from "react";
import Prepare from "@/pages/Prepare";

export default function MinutesTab() {
  return <Prepare embedded forceTab="minutes" />;
}
