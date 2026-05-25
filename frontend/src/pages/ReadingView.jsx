/**
 * ReadingView — Reading Viewer (Advisory 2, default since Phase 2).
 *
 * Canonical document surface at `/app/documents/:id`. The legacy
 * DocumentViewer was retired in Phase 3. See
 * `/app/docs/ux-advisories-v1.md` for the binding rules.
 *
 * Composition:
 *   AppShell (auth + nav)
 *   └─ ReadingTopBar              (sticky)
 *   └─ ReadingBody  +  ReadingRail   (desktop, 1fr | 360px)
 *   └─ ReadingBody  +  CommentaryDrawer (<md, full width + bottom sheet)
 *
 * Data:
 *   - GET /contexts/:cid/documents/:id           (existing)
 *   - GET /contexts/:cid/documents/:id/paragraphs  (Reading Viewer v1)
 *   - GET /contexts/:cid/signals?committee_id=…  (filtered to this doc)
 *   - GET /contexts/:cid/briefings               (filtered to this doc)
 *   - GET /contexts/:cid/ask                     (filtered to this doc)
 *
 * Commentary items are normalised at the page level so CommentaryItem
 * can stay dumb. References are passed through the new `references[]`
 * shape on the backend; if a reference carries a `paragraph_id` we wire
 * scroll-sync, otherwise the chip falls back to page-level.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { pollJob } from "@/lib/pollJob";

import ReadingTopBar from "@/components/reading/ReadingTopBar";
import ReadingBody from "@/components/reading/ReadingBody";
import HandoffActions from "@/components/shell/HandoffActions";
import ReadingRail from "@/components/reading/ReadingRail";
import CommentaryDrawer from "@/components/reading/CommentaryDrawer";
import useDocumentParagraphs from "@/hooks/useDocumentParagraphs";
import useReadingScrollSync from "@/hooks/useReadingScrollSync";

const TONE_WORD = {
  risk: "RISK",
  gap: "GAP",
  opportunity: "OPP",
};

function pickFirstReference(references, sources, fallbackTitle) {
  // Prefer the new `references[]` shape from the backend; fall back to
  // legacy `sources[]` when reading documents written before Phase 1.
  if (Array.isArray(references) && references.length > 0) return references[0];
  if (Array.isArray(sources) && sources.length > 0) {
    const s = sources[0];
    return {
      doc_id: s.doc_id,
      doc_title: s.doc_name || s.doc_title || fallbackTitle || s.doc_id,
      page: s.page || null,
      paragraph_id: s.paragraph_id || null,
      paragraph_number: s.paragraph_number || null,
    };
  }
  return null;
}

export default function ReadingView() {
  const { id: docId } = useParams();
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [doc, setDoc] = useState(null);
  const [docLoading, setDocLoading] = useState(true);
  const [docError, setDocError] = useState(null);

  const [signals, setSignals] = useState([]);
  const [briefings, setBriefings] = useState([]);
  const [askMessages, setAskMessages] = useState([]);
  const [commentaryLoading, setCommentaryLoading] = useState(true);

  const [generatingBrief, setGeneratingBrief] = useState(false);
  const [generatingSignals, setGeneratingSignals] = useState(false);
  // QA-2026-05-16-007 (2026-05-18, fix-pass) — long-running status copy
  // for the Generate-signals action. Empty string until the job runs
  // past 4 s; then the verbatim spec line. A separate inline-error
  // state is kept so a job failure leaves a human-readable error
  // visible inside the commentary panel even after `generatingSignals`
  // flips back to false (the toast alone wasn't reliable per QA).
  const [signalsStatusMessage, setSignalsStatusMessage] = useState("");
  const [signalsErrorMessage, setSignalsErrorMessage] = useState("");
  // QA-2026-05-16-007 (2026-05-18, fix-pass #2) — Path A from the
  // tester's hypothesis (verified live): the job succeeds but the
  // backend generated 0 signals referencing THIS doc (signals are
  // context-scoped, doc-filter on the rail can return empty). Without
  // this persistent info copy the button silently resets — looks like
  // a no-op to the user. Surfaced as an "info" not an "error".
  const [signalsInfoMessage, setSignalsInfoMessage] = useState("");

  const bodyRef = useRef(null);
  const { paragraphs, loading: paragraphsLoading, error: paragraphsError, unavailable: paragraphsUnavailable } =
    useDocumentParagraphs(contextId, docId);
  const {
    activeParagraphId,
    flashedBodyId,
    flashedRailIds,
    scrollBodyTo,
    scrollRailTo,
  } = useReadingScrollSync(bodyRef);

  // Fetch doc.
  const loadDoc = useCallback(async () => {
    if (!contextId || !docId) return;
    setDocLoading(true);
    setDocError(null);
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents/${docId}`);
      setDoc(data);
    } catch (err) {
      setDocError(
        apiErrorMessage(
          err,
          "AKKI couldn’t reach the document. The source link may have expired.",
        ),
      );
    } finally {
      setDocLoading(false);
    }
  }, [contextId, docId]);

  // Fetch commentary.
  const loadCommentary = useCallback(async () => {
    if (!contextId || !docId) return { perDocCount: 0 };
    setCommentaryLoading(true);
    // QA-2026-05-16-007 (2026-05-18, fix-pass #2) — return the per-doc
    // item count so handleGenerateSignals can branch on "ran fine but
    // surfaced nothing for THIS document" (Path A — verified live:
    // backend generates context-scoped signals; if none cite the
    // current doc, the rail filter strips them all).
    let perDocCount = 0;
    try {
      const [sigRes, briefRes, askRes] = await Promise.allSettled([
        api.get(`/contexts/${contextId}/signals?limit=200`),
        api.get(`/contexts/${contextId}/briefings?limit=80`),
        api.get(`/contexts/${contextId}/ask?limit=80`),
      ]);
      if (sigRes.status === "fulfilled") {
        const list = Array.isArray(sigRes.value.data) ? sigRes.value.data : [];
        const perDoc = list.filter((s) =>
          (s.references || s.sources || []).some((r) => r.doc_id === docId),
        );
        perDocCount += perDoc.length;
        setSignals(perDoc);
      }
      if (briefRes.status === "fulfilled") {
        const list = Array.isArray(briefRes.value.data) ? briefRes.value.data : [];
        const perDoc = list.filter((b) =>
          (b.references || []).some((r) => r.doc_id === docId)
            || (b.source_doc_ids || []).includes(docId),
        );
        perDocCount += perDoc.length;
        setBriefings(perDoc);
      }
      if (askRes.status === "fulfilled") {
        const list = Array.isArray(askRes.value.data) ? askRes.value.data : [];
        const perDoc = list.filter((m) =>
          (m.references || m.sources || []).some((r) => r.doc_id === docId),
        );
        perDocCount += perDoc.length;
        setAskMessages(perDoc);
      }
    } finally {
      setCommentaryLoading(false);
    }
    return { perDocCount };
  }, [contextId, docId]);

  useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  useEffect(() => {
    loadCommentary();
  }, [loadCommentary]);

  // Build a paragraph_id -> paragraph map for citation excerpts.
  const paragraphLookup = useMemo(() => {
    const map = {};
    paragraphs.forEach((p) => {
      map[p.id] = p;
    });
    return map;
  }, [paragraphs]);

  // Normalise commentary items into the rail/drawer shape.
  const commentaryItems = useMemo(() => {
    const items = [];
    signals.forEach((s) => {
      const tone = ["risk", "gap", "opportunity"].includes(s.type) ? s.type : "risk";
      const ref = pickFirstReference(s.references, s.sources, doc?.name);
      items.push({
        id: s.id,
        kind: "signal",
        tone,
        toneWord: TONE_WORD[tone] || tone.toUpperCase(),
        headline: s.headline,
        body: s.summary,
        reference: ref,
        paragraphId: ref?.paragraph_id || null,
      });
    });
    briefings.forEach((b) => {
      // Each briefing has multiple items, but we want one rail entry per
      // briefing item that touches this doc. We use refs from the item if
      // present, otherwise the briefing-level union.
      const briefItems = Array.isArray(b.items) ? b.items : [];
      briefItems.forEach((it) => {
        const refs = it.references || [];
        const docRef = refs.find((r) => r.doc_id === docId) || pickFirstReference(refs, it.sources, doc?.name);
        if (!docRef) return;
        items.push({
          id: `${b.id}__${it.signal_id || items.length}`,
          kind: "briefing",
          tone: "note",
          toneWord: "BRIEF",
          headline: it.signal_headline || b.title,
          body: it.evidence || b.opening_paragraph,
          reference: docRef,
          paragraphId: docRef?.paragraph_id || null,
        });
      });
    });
    askMessages.forEach((m) => {
      const ref = pickFirstReference(m.references, m.sources, doc?.name);
      items.push({
        id: m.id,
        kind: "ask",
        tone: "note",
        toneWord: "ASK",
        headline: m.question,
        body: m.answer,
        reference: ref,
        paragraphId: ref?.paragraph_id || null,
      });
    });
    return items;
  }, [signals, briefings, askMessages, doc, docId]);

  // Scroll-sync wiring.
  const handleParagraphClick = useCallback(
    (paragraphId) => {
      scrollRailTo(paragraphId);
    },
    [scrollRailTo],
  );

  const handleJumpToParagraph = useCallback(
    (paragraphId) => {
      scrollBodyTo(paragraphId);
    },
    [scrollBodyTo],
  );

  // Primary action: Generate brief.
  // Chunk 2 (2026-05-13, DJ-R03) — async pattern. The endpoint returns
  // 202 + { job_id } immediately and the heavy LLM work runs in the
  // background. We poll until terminal, then route the user to Prepare
  // with the resulting briefing id. The Generate-Brief button stays
  // "working" the whole time but the user can navigate away — the job
  // continues server-side.
  const handleGenerateBrief = useCallback(async () => {
    if (!contextId || !doc) return;
    setGeneratingBrief(true);
    try {
      const { data: enqueueResp } = await api.post(`/contexts/${contextId}/briefings`, {
        title: `Briefing on ${doc.name}`,
      });
      const jobId = enqueueResp?.job_id;
      if (!jobId) throw new Error("Backend did not return a job_id");
      const job = await pollJob(jobId, {
        onProgress: (status, elapsedS) => {
          if (status === "running" && elapsedS > 5) {
            // Re-toast every ~20 s so the user sees progress.
            if (elapsedS % 20 === 0) {
              toast.message(`Drafting briefing… ${elapsedS}s elapsed.`);
            }
          }
        },
      });
      if (job.status === "failed") {
        throw new Error(job.error || "Briefing job failed.");
      }
      toast.success("Briefing drafted. Opening Catch-up.");
      const briefingId = job?.result?.id;
      if (briefingId) {
        navigate(`/app/prepare?briefing=${briefingId}`);
      } else {
        navigate("/app/prepare");
      }
    } catch (err) {
      // T1.4 (2026-05-25) — G3-ratified failure copy: spec §4.A → D8.
      // The button is re-enabled in the `finally` block below (loading
      // state dismissed) so the user can immediately retry.
      toast.error("We couldn't generate a brief from this document. Please try again.");
    } finally {
      setGeneratingBrief(false);
    }
  }, [contextId, doc, navigate]);

  // Secondary action: Generate signals (when rail is empty).
  const handleGenerateSignals = useCallback(async () => {
    if (!contextId || generatingSignals) return;
    setGeneratingSignals(true);
    setSignalsStatusMessage("");
    setSignalsErrorMessage("");
    setSignalsInfoMessage("");
    // QA-2026-05-16-007 (2026-05-18, fix-pass) — long-running status
    // is driven off a real setTimeout, not a stale closure inside
    // pollJob.onProgress (which only fires every 1.5-5s and depended
    // on a value captured at click time). The verbatim spec line
    // appears 4 s after the click and persists until the job ends.
    const statusTimer = setTimeout(() => {
      setSignalsStatusMessage(
        "Akki is analysing your document. This may take a moment."
      );
    }, 4000);
    try {
      const { data: enq } = await api.post(`/contexts/${contextId}/signals/generate`, {});
      const job = await pollJob(enq.job_id);
      if (job.status === "failed") {
        throw new Error(job.error || "Signal refresh failed.");
      }
      // QA-2026-05-16-007 (2026-05-18, fix-pass #2) — Path A guard.
      // Backend signals are context-scoped; if none of the newly
      // generated signals reference THIS doc, loadCommentary's
      // doc-filter strips them all and the rail stays empty. Surface
      // a persistent inline info so the button does NOT silently
      // reset.
      const { perDocCount } = (await loadCommentary()) || { perDocCount: 0 };
      if (perDocCount === 0) {
        setSignalsInfoMessage(
          "Akki refreshed signals across this context but didn't surface "
          + "anything new for this document. Try a more substantive document, "
          + "or revisit after more context has been added."
        );
      } else {
        toast.success("Signals refreshed.");
      }
    } catch (err) {
      // QA-2026-05-16-007 (2026-05-18, fix-pass) — surface the error
      // inline as well as via toast. fix-pass #2: defensive Path B —
      // if apiErrorMessage returns falsy (the reducer can collapse
      // structured Error payloads to empty string), fall back to a
      // hardcoded copy so the inline state is NEVER empty after a
      // failure.
      const reduced = apiErrorMessage(err, "Could not refresh signals.");
      const msg = (typeof reduced === "string" && reduced.trim())
        ? reduced
        : "Signal generation failed. Please try again or contact support if this persists.";
      setSignalsErrorMessage(msg);
      toast.error(msg);
    } finally {
      clearTimeout(statusTimer);
      setGeneratingSignals(false);
      setSignalsStatusMessage("");
    }
  }, [contextId, generatingSignals, loadCommentary]);

  // Loading / error / empty states (per the rules doc: editorial copy only).
  if (docLoading) {
    return (
      <AppShell>
        <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-[var(--cream)]">
          <p
            className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse"
            data-testid="reading-loading"
          >
            Reading the pack…
          </p>
        </div>
      </AppShell>
    );
  }

  if (docError || !doc) {
    return (
      <AppShell>
        <div className="h-[calc(100vh-4rem)] flex flex-col items-center justify-center bg-[var(--cream)] px-6">
          <p className="akki-serif text-[18px] text-[var(--ink)] mb-2 text-center max-w-[40ch]" data-testid="reading-error">
            {docError || "AKKI couldn’t reach the document. The source link may have expired."}
          </p>
          <button
            type="button"
            onClick={loadDoc}
            className="mt-4 text-[12px] text-[var(--accent)] hover:underline underline-offset-2"
            data-testid="reading-error-retry"
          >
            Try again
          </button>
        </div>
      </AppShell>
    );
  }

  const fallbackText = paragraphs.length === 0 ? doc.extracted_text : null;

  return (
    <AppShell>
      <div
        className="flex flex-col h-[calc(100vh-4rem)] bg-[var(--cream)]"
        data-testid="reading-view"
        data-version="2"
      >
        <ReadingTopBar
          doc={doc}
          contextId={contextId}
          contextName={activeContext?.name}
          onGenerateBrief={handleGenerateBrief}
          generatingBrief={generatingBrief}
        />

        {/* Phase 13.3 — cross-module handoffs from a document detail
            view. Lives directly under the topbar so it's always
            visible without scrolling, and so ⌘J finds the
            data-solva-seed without having to scroll the body. */}
        {doc?.id && contextId && (
          <div className="px-6 md:px-8 pt-3 pb-2 max-w-[1100px] mx-auto w-full">
            <HandoffActions
              kind="document"
              id={doc.id}
              contextId={contextId}
              title={doc.title || doc.filename}
            />
          </div>
        )}

        {paragraphsLoading ? (
          <div className="px-6 md:px-8 pt-8">
            <p
              className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse max-w-[720px] mx-auto"
              data-testid="reading-paragraphs-loading"
            >
              Reading the pack…
            </p>
            <div className="max-w-[720px] mx-auto mt-6 space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-3 bg-[var(--rule)]/60 rounded animate-pulse" />
              ))}
            </div>
          </div>
        ) : null}

        {paragraphsError ? (
          <div className="px-6 md:px-8 py-8 max-w-[720px] mx-auto">
            <p className="akki-serif text-[15px] text-[var(--ink)] mb-2">{paragraphsError}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="text-[12px] text-[var(--accent)] hover:underline underline-offset-2"
            >
              Try again
            </button>
          </div>
        ) : null}

        {!paragraphsLoading && !paragraphsError ? (
          <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[1fr_360px]">
            <ReadingBody
              bodyRef={bodyRef}
              paragraphs={paragraphs}
              fallbackText={fallbackText}
              paragraphsUnavailable={paragraphsUnavailable}
              onParagraphClick={handleParagraphClick}
            />
            <ReadingRail
              items={commentaryItems}
              loading={commentaryLoading}
              activeParagraphId={activeParagraphId}
              flashedRailIds={flashedRailIds}
              onJump={handleJumpToParagraph}
              paragraphLookup={paragraphLookup}
              onGenerateSignals={handleGenerateSignals}
              canGenerateSignals
              generatingSignals={generatingSignals}
              signalsStatusMessage={signalsStatusMessage}
              signalsErrorMessage={signalsErrorMessage}
              signalsInfoMessage={signalsInfoMessage}
              onDismissSignalsError={() => setSignalsErrorMessage("")}
              onDismissSignalsInfo={() => setSignalsInfoMessage("")}
            />
          </div>
        ) : null}

        {/* Mobile drawer (always rendered, hidden on md+ via the trigger). */}
        <CommentaryDrawer
          items={commentaryItems}
          flashedRailIds={flashedRailIds}
          onJump={handleJumpToParagraph}
          paragraphLookup={paragraphLookup}
          onGenerateSignals={handleGenerateSignals}
          canGenerateSignals
          generatingSignals={generatingSignals}
          signalsStatusMessage={signalsStatusMessage}
          signalsErrorMessage={signalsErrorMessage}
          signalsInfoMessage={signalsInfoMessage}
          onDismissSignalsError={() => setSignalsErrorMessage("")}
          onDismissSignalsInfo={() => setSignalsInfoMessage("")}
        />
      </div>
    </AppShell>
  );
}
