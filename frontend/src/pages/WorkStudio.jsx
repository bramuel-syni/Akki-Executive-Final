/**
 * WorkStudio — Phase C.3 (memo: Work Studio frontend, final phase of C series).
 *
 * Three modes via internal state:
 *   - `picker`     : the user picks a source to compose from
 *   - `composing`  : a Compose drawer is open over the picker
 *   - `workspace`  : after Generate, the page transitions to a brief
 *                    workspace (revision strip + diff + actions). The
 *                    Refine drawer opens over this view.
 *
 * Reads from existing endpoints (no backend change in C.3):
 *   GET /api/solva/v2/sessions?status=completed
 *   GET /api/chats?limit=…
 *   GET /api/work_studio/picker
 *   POST /api/work_studio/exports
 *   GET /api/work_studio/briefs/{bid}
 *   GET /api/work_studio/briefs/{bid}/revisions
 *   GET /api/work_studio/briefs/{bid}/revisions/{rid}/diff
 *   POST /api/work_studio/briefs/{bid}/enhance
 *   POST /api/work_studio/briefs/{bid}/set_active
 *
 * Phase 13 surfaces (legacy aggregates + ExportModal + EnhanceModal)
 * have been retired in this phase per the C.3 brief — they posted to
 * obsolete endpoints and the C.3 source-picker → compose → refine flow
 * supersedes them entirely.
 */
import React, { useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Sparkles } from "lucide-react";
import SourcePicker from "@/components/work_studio/SourcePicker";
import ComposeDrawer from "@/components/work_studio/ComposeDrawer";
import BriefWorkspace from "@/components/work_studio/BriefWorkspace";

export default function WorkStudio() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const cname = activeContext?.name;

  // mode ∈ "picker" | "workspace"
  const [mode, setMode] = useState("picker");

  // Picked source (passed to ComposeDrawer).
  const [source, setSource] = useState(null);
  const [composeOpen, setComposeOpen] = useState(false);

  // After compose, what we know about the resulting brief + first export.
  const [briefId, setBriefId] = useState(null);
  const [initialExport, setInitialExport] = useState(null);

  if (!cid) {
    return (
      <AppShell>
        <div className="p-12 text-center text-[var(--muted)] text-sm">No company selected.</div>
      </AppShell>
    );
  }

  const onPick = (s) => {
    setSource(s);
    setComposeOpen(true);
  };

  const onComposed = (composed) => {
    setComposeOpen(false);
    setSource(null);
    setBriefId(composed.brief_id);
    setInitialExport({
      download_url: composed.download_url,
      filename: composed.filename,
      size_bytes: composed.size_bytes,
      export_id: composed.export_id,
      revision_id: composed.revision_id,
      format: composed.format,
      depth: composed.depth,
      fidelity: composed.fidelity,
    });
    setMode("workspace");
  };

  const onBack = () => {
    setMode("picker");
    setBriefId(null);
    setInitialExport(null);
  };

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-10" data-testid="work-studio">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Work Studio · {cname}
        </p>

        {mode === "picker" && (
          <>
            <h1 className="akki-greeting mb-2">Compose a board-grade artefact.</h1>
            <p className="akki-meta max-w-2xl mb-8">
              Pick a Solva session or a chat to compose into a Brief. Two-pass refine works on the
              persisted Brief; section-level diffs and revision history are preserved across attempts.
            </p>
            <SourcePicker contextId={cid} onPick={onPick} />
          </>
        )}

        {mode === "workspace" && briefId && (
          <BriefWorkspace
            briefId={briefId}
            initialExport={initialExport}
            onBack={onBack}
          />
        )}
      </div>

      <ComposeDrawer
        open={composeOpen}
        onClose={() => { setComposeOpen(false); setSource(null); }}
        onComposed={onComposed}
        source={source}
        contextId={cid}
        contextName={cname}
      />
    </AppShell>
  );
}
