/**
 * useReadingScrollSync — bidirectional scroll-sync between the document
 * body and the commentary rail. Desktop only.
 *
 * Returns:
 *   activeParagraphId  — id of the paragraph currently dominant in the
 *                        viewport, derived via IntersectionObserver. The
 *                        rail uses this for a quiet `data-active` accent.
 *   scrollBodyTo(id)   — programmatic scroll to a paragraph in the body,
 *                        with a 1500ms `data-flash` ring on the target.
 *   scrollRailTo(id)   — same in reverse: scrolls the rail to whichever
 *                        item references the given paragraph_id.
 *
 * The hook attaches listeners to `bodyRef.current` so the page is free to
 * own its own scroll container. The rail listener walks the DOM looking
 * for `[data-rail-paragraph-id="..."]` matches.
 */
import { useCallback, useEffect, useState } from "react";

const FLASH_MS = 1500;

function flash(node) {
  if (!node) return;
  node.setAttribute("data-flash", "true");
  window.setTimeout(() => {
    if (node && node.isConnected) node.removeAttribute("data-flash");
  }, FLASH_MS);
}

export default function useReadingScrollSync(bodyRef) {
  const [activeParagraphId, setActiveParagraphId] = useState(null);

  // IntersectionObserver — track which body paragraph is most prominent.
  useEffect(() => {
    if (!bodyRef?.current) return undefined;
    const root = bodyRef.current;
    const targets = root.querySelectorAll("[data-anchor-id]");
    if (!targets || !targets.length) return undefined;
    let visible = new Map(); // id -> intersectionRatio

    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          const id = e.target.getAttribute("data-anchor-id");
          if (!id) return;
          if (e.isIntersecting) {
            visible.set(id, e.intersectionRatio);
          } else {
            visible.delete(id);
          }
        });
        if (visible.size === 0) return;
        // Pick the most-visible one — ties broken by document order.
        let bestId = null;
        let bestRatio = -1;
        visible.forEach((ratio, id) => {
          if (ratio > bestRatio) {
            bestRatio = ratio;
            bestId = id;
          }
        });
        if (bestId !== null) setActiveParagraphId(bestId);
      },
      { root, threshold: [0.25, 0.5, 0.75], rootMargin: "0px 0px -40% 0px" },
    );
    targets.forEach((t) => obs.observe(t));
    return () => obs.disconnect();
  }, [bodyRef]);

  const scrollBodyTo = useCallback((paragraphId) => {
    if (!paragraphId) return;
    const node = document.querySelector(
      `[data-anchor-id="${CSS.escape(paragraphId)}"]`,
    );
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    flash(node);
  }, []);

  const scrollRailTo = useCallback((paragraphId) => {
    if (!paragraphId) return;
    const matches = document.querySelectorAll(
      `[data-rail-paragraph-id="${CSS.escape(paragraphId)}"]`,
    );
    matches.forEach((node, i) => {
      if (i === 0) {
        node.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      flash(node);
    });
  }, []);

  return { activeParagraphId, scrollBodyTo, scrollRailTo };
}
