/**
 * Phase 15.3.5 cutover — `AppSolva` retired.
 *
 * The original 4-phase v1 Solva surface is archived under
 * `/app/_legacy/frontend/pages/AppSolva.jsx.bak`. This stub exists
 * only to keep `import AppSolva from "@/pages/AppSolva"` callsites
 * compiling during the transition. All routes that previously
 * pointed here now redirect to `/app/solva` (which renders the v2
 * surface).
 */
import React from "react";
import { Navigate } from "react-router-dom";

export default function AppSolva() {
  return <Navigate to="/app/solva" replace />;
}
