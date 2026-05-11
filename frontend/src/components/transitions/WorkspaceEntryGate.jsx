/**
 * Phase K (2026-05-12) — WorkspaceEntryGate.
 *
 * Drop-in wrapper that defers rendering its `children` for ~3–5 seconds
 * the FIRST time a given workspace mounts in the browser session. After
 * the scene completes (or immediately when `prefers-reduced-motion` is
 * set), the children are revealed with a calm-fast cross-fade.
 *
 * Usage:
 *   <WorkspaceEntryGate workspace="solva">
 *     {/* actual workspace body * /}
 *   </WorkspaceEntryGate>
 *
 * Once-per-session memoisation uses sessionStorage so flipping between
 * tabs does NOT re-trigger the scene. Per-workspace key — Cycle and
 * Solva fire independently.
 *
 * Honours the K5 spec: calm-fast defaults (200ms fade), no progress
 * bars, no percentages, no step counters. The transition is a name +
 * editorial reveal.
 */
import React, { useEffect, useState } from "react";
import WorkspaceEntryScene from "./WorkspaceEntryScene";

const SESSION_KEY_PREFIX = "akki_workspace_entry_v1_";

function hasSeen(workspace) {
  try {
    return sessionStorage.getItem(SESSION_KEY_PREFIX + workspace) === "seen";
  } catch {
    return false;
  }
}

function markSeen(workspace) {
  try {
    sessionStorage.setItem(SESSION_KEY_PREFIX + workspace, "seen");
  } catch {
    /* sessionStorage unavailable — best-effort */
  }
}

export default function WorkspaceEntryGate({ workspace, children, testId }) {
  const [revealed, setRevealed] = useState(() => hasSeen(workspace));

  const onComplete = () => {
    markSeen(workspace);
    setRevealed(true);
  };

  // Safety: if the scene hangs for any reason, fall through after 6s.
  useEffect(() => {
    if (revealed) return undefined;
    const tid = setTimeout(() => {
      markSeen(workspace);
      setRevealed(true);
    }, 6000);
    return () => clearTimeout(tid);
  }, [revealed, workspace]);

  if (revealed) {
    return (
      <div
        data-testid={testId || `workspace-entry-gate-revealed-${workspace}`}
        style={{ animation: "akki-fade-up 0.25s ease-out both" }}
      >
        {children}
      </div>
    );
  }

  return (
    <WorkspaceEntryScene
      workspace={workspace}
      onComplete={onComplete}
      testId={testId || `workspace-entry-${workspace}`}
    />
  );
}
