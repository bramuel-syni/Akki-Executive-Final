/**
 * ReadingView — Reading Viewer v2 (Advisory 2, Phase 1).
 *
 * Shipped behind `?v=2` on `/app/documents/:id`. The classic
 * DocumentViewer remains the default until the v2 flip in the next
 * release. See `/app/docs/ux-advisories-v1.md` for the binding rules.
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

import ReadingTopBar from "@/components/reading/ReadingTopBar";
import ReadingBody from "@/components/reading/ReadingBody";
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

  const bodyRef = useRef(null);
  const { paragraphs, loading: paragraphsLoading, error: paragraphsError, unavailable: paragraphsUnavailable } =
    useDocumentParagraphs(contextId, docId);
  const { activeParagraphId, scrollBodyTo, scrollRailTo } = useReadingScrollSync(bodyRef);

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
    if (!contextId || !docId) return;
    setCommentaryLoading(true);
    try {
      const [sigRes, briefRes, askRes] = await Promise.allSettled([
        api.get(`/contexts/${contextId}/signals?limit=200`),
        api.get(`/contexts/${contextId}/briefings?limit=80`),
        api.get(`/contexts/${contextId}/ask?limit=80`),
      ]);
      if (sigRes.status === "fulfilled") {
        const list = Array.isArray(sigRes.value.data) ? sigRes.value.data : [];
        setSignals(list.filter((s) =>
          (s.references || s.sources || []).some((r) => r.doc_id === docId),
        ));
      }
      if (briefRes.status === "fulfilled") {
        const list = Array.isArray(briefRes.value.data) ? briefRes.value.data : [];
        setBriefings(list.filter((b) =>
          (b.references || []).some((r) => r.doc_id === docId)
            || (b.source_doc_ids || []).includes(docId),
        ));
      }
      if (askRes.status === "fulfilled") {
        const list = Array.isArray(askRes.value.data) ? askRes.value.data : [];
        setAskMessages(list.filter((m) =>
          (m.references || m.sources || []).some((r) => r.doc_id === docId),
        ));
      }
    } finally {
      setCommentaryLoading(false);
    }
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
  const handleGenerateBrief = useCallback(async () => {
    if (!contextId || !doc) return;
    setGeneratingBrief(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/briefings`, {
        title: `Briefing on ${doc.name}`,
      });
      toast.success("Briefing drafted. Opening Catch-up.");
      // Navigate to Catch-up where the new briefing surfaces.
      const briefingId = data?.id;
      if (briefingId) {
        navigate(`/app/prepare?briefing=${briefingId}`);
      } else {
        navigate("/app/prepare");
      }
    } catch (err) {
      toast.error(
        apiErrorMessage(
          err,
          "AKKI couldn’t draft a briefing right now. Check your signals and try again.",
        ),
      );
    } finally {
      setGeneratingBrief(false);
    }
  }, [contextId, doc, navigate]);

  // Secondary action: Generate signals (when rail is empty).
  const handleGenerateSignals = useCallback(async () => {
    if (!contextId || generatingSignals) return;
    setGeneratingSignals(true);
    try {
      await api.post(`/contexts/${contextId}/signals/generate`, {});
      toast.success("Signals refreshed.");
      await loadCommentary();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not refresh signals."));
    } finally {
      setGeneratingSignals(false);
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
              onJump={handleJumpToParagraph}
              paragraphLookup={paragraphLookup}
              onGenerateSignals={handleGenerateSignals}
              canGenerateSignals
            />
          </div>
        ) : null}

        {/* Mobile drawer (always rendered, hidden on md+ via the trigger). */}
        <CommentaryDrawer
          items={commentaryItems}
          onJump={handleJumpToParagraph}
          paragraphLookup={paragraphLookup}
          onGenerateSignals={handleGenerateSignals}
          canGenerateSignals
        />
      </div>
    </AppShell>
  );
}
