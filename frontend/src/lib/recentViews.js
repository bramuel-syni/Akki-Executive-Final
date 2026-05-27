/**
 * useTrackRecentView — Phase H.4.1 client hook (2026-05-27).
 *
 * Records a "recent view" of an artefact so the Portfolio Landing
 * ("Where you left off" resume card) can deep-link back into it.
 *
 * Backend route: POST /api/me/recent-views (upsert keyed on
 * account_id + surface_path).
 *
 * Usage:
 *   useTrackRecentView({
 *     surfacePath: location.pathname + location.search,
 *     label: doc.title,
 *     contextId: activeContext?.id,
 *     artefactId: doc.id,
 *     artefactKind: "document",
 *     deepLink: `/app/work-studio?doc_id=${doc.id}`,
 *   });
 *
 * Idempotent on (account, surface_path) — multiple calls upsert.
 * Network failures are silent (non-critical telemetry).
 */
import { useEffect } from "react";
import { api } from "@/lib/api";

export function useTrackRecentView({
  surfacePath,
  label,
  contextId,
  artefactId,
  artefactKind,
  deepLink,
  enabled = true,
}) {
  useEffect(() => {
    if (!enabled) return;
    if (!surfacePath || !label) return;
    let canceled = false;
    (async () => {
      try {
        await api.post("/me/recent-views", {
          surface_path: surfacePath,
          label,
          context_id: contextId || null,
          artefact_id: artefactId || null,
          artefact_kind: artefactKind || null,
          deep_link: deepLink || surfacePath,
        });
      } catch (err) {
        if (!canceled) {
          // Silent — non-critical telemetry.
          // eslint-disable-next-line no-console
          console.warn("[recent-views] track failed:", err?.message);
        }
      }
    })();
    return () => { canceled = true; };
  }, [surfacePath, label, contextId, artefactId, artefactKind, deepLink, enabled]);
}
