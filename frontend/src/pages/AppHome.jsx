/**
 * AppHome — Phase 5 flag-reader wrapper.
 *
 * Contract:
 *   ?home=v2 AND !account.is_sandbox  →  render <HomeV2 />
 *   otherwise                         →  render <LegacyAppHome /> (pre-Phase-5,
 *                                        byte-identical to the previous file)
 *
 * The FirstSessionGuard (see `App.js`) has already run by the time this
 * component mounts, so a brand-new user never reaches either branch —
 * they get redirected to `/app/first-session` first. That means this
 * wrapper is safe to branch on the URL flag without any additional
 * redirect protection.
 *
 * Sandbox accounts are explicitly pinned to v1 so the sandbox-specific
 * cards (SandboxTutorial, SandboxSampleDoc, etc.) keep rendering. The
 * v2 river is a cross-board change-tracking surface and has no sensible
 * semantics inside a single frozen sandbox context.
 *
 * Docs: /app/memory/HOME_AUDIT.md (Part A audit) · /app/docs/ux-advisories-v1.md (v1.5).
 */
import React from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import LegacyAppHome from "@/pages/LegacyAppHome";
import HomeV2 from "@/pages/HomeV2";

export default function AppHome() {
  const { account } = useAuth();
  const location = useLocation();
  const params = new URLSearchParams(location.search || "");
  const flag = (params.get("home") || "").toLowerCase();
  const useV2 = flag === "v2" && !account?.is_sandbox;
  return useV2 ? <HomeV2 /> : <LegacyAppHome />;
}
