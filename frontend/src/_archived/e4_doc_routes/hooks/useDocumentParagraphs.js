/**
 * useDocumentParagraphs — fetch the paragraph anchors for a document.
 *
 * Lazy-on-read on the backend (see `routers/documents.py`); this hook just
 * wraps GET /api/contexts/{cid}/documents/{doc_id}/paragraphs and exposes
 * the loading/error states the Reading Viewer needs.
 *
 * Response shape: { doc_id, paragraphs[], page_count, computed_at, version }.
 * Paragraph: { id, page, paragraph_number, text, char_start, char_end }.
 */
import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";

export default function useDocumentParagraphs(contextId, docId) {
  const [paragraphs, setParagraphs] = useState([]);
  const [pageCount, setPageCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [unavailable, setUnavailable] = useState(false); // true if 409

  useEffect(() => {
    let cancelled = false;
    if (!contextId || !docId) return undefined;
    setLoading(true);
    setError(null);
    setUnavailable(false);
    (async () => {
      try {
        const { data } = await api.get(
          `/contexts/${contextId}/documents/${docId}/paragraphs`,
        );
        if (cancelled) return;
        setParagraphs(Array.isArray(data?.paragraphs) ? data.paragraphs : []);
        setPageCount(data?.page_count || 0);
      } catch (err) {
        if (cancelled) return;
        if (err?.response?.status === 409) {
          // Extraction not yet complete — UI falls back to flat extracted_text.
          setUnavailable(true);
        } else {
          setError(apiErrorMessage(
            err,
            "AKKI couldn’t reach the document. The source link may have expired.",
          ));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [contextId, docId]);

  return { paragraphs, pageCount, loading, error, unavailable };
}
