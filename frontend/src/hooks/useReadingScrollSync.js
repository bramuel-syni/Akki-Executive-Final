/**
 * useReadingScrollSync — bidirectional scroll-sync between body + rail.
 *
 * After the v1 tester FAIL on body→rail visual flash, this hook now
 * exposes React state for `flashedBodyId` and `flashedRailIds` (a Set,
 * because one paragraph can map to multiple rail items: a Risk signal
 * and an Ask answer can both anchor on the same paragraph). The
 * components consume the state directly via props — no more reliance
 * on DOM mutation for the visual treatment. The DOM `data-flash`
 * attribute is still set as a belt-and-braces fallback for any consumer
 * that prefers attribute selectors.
 *
 * Returns:
 *   activeParagraphId        — currently dominant paragraph in viewport
 *                              (IntersectionObserver). For quiet `data-active`
 *                              accent on the rail.
 *   flashedBodyId            — paragraph id with a 1500ms flash highlight,
 *                              triggered by chip-click in the rail.
 *   flashedRailIds           — Set<paragraph_id> of rail items currently
 *                              flashing, triggered by body-paragraph click.
 *   scrollBodyTo(id)         — programmatic body scroll + flash.
 *   scrollRailTo(id)         — programmatic rail scroll + flash for ALL
 *                              items that match the paragraph_id.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const FLASH_MS = 1500;

export default function useReadingScrollSync(bodyRef) {
  const [activeParagraphId, setActiveParagraphId] = useState(null);
  const [flashedBodyId, setFlashedBodyId] = useState(null);
  const [flashedRailIds, setFlashedRailIds] = useState(() => new Set());

  // Timers so a fresh flash cancels the previous one cleanly.
  const bodyTimerRef = useRef(null);
  const railTimerRef = useRef(null);

  // IntersectionObserver — track most-prominent visible paragraph.
  useEffect(() => {
    if (!bodyRef?.current) return undefined;
    const root = bodyRef.current;
    const targets = root.querySelectorAll("[data-anchor-id]");
    if (!targets || !targets.length) return undefined;
    const visible = new Map(); // id -> ratio

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

  // Cleanup timers on unmount.
  useEffect(() => () => {
    if (bodyTimerRef.current) window.clearTimeout(bodyTimerRef.current);
    if (railTimerRef.current) window.clearTimeout(railTimerRef.current);
  }, []);

  const scrollBodyTo = useCallback((paragraphId) => {
    if (!paragraphId) return;
    const node = document.querySelector(
      `[data-anchor-id="${CSS.escape(paragraphId)}"]`,
    );
    if (node) {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
      // Also set the DOM attribute (belt-and-braces) so attribute-driven
      // tailwind variants on the body paragraph kick in immediately even
      // before React re-renders.
      node.setAttribute("data-flash", "true");
      window.setTimeout(() => {
        if (node && node.isConnected) node.removeAttribute("data-flash");
      }, FLASH_MS);
    }
    setFlashedBodyId(paragraphId);
    if (bodyTimerRef.current) window.clearTimeout(bodyTimerRef.current);
    bodyTimerRef.current = window.setTimeout(() => {
      setFlashedBodyId((curr) => (curr === paragraphId ? null : curr));
    }, FLASH_MS);
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
    });
    // Lift to React state so the rail items re-render with the
    // strong-flash class (bg tint + ring + shadow). DOM attr is still
    // set as a fallback for any attribute-selector consumer.
    setFlashedRailIds((prev) => {
      const next = new Set(prev);
      next.add(paragraphId);
      return next;
    });
    matches.forEach((node) => {
      node.setAttribute("data-flash", "true");
    });
    if (railTimerRef.current) window.clearTimeout(railTimerRef.current);
    railTimerRef.current = window.setTimeout(() => {
      setFlashedRailIds((prev) => {
        const next = new Set(prev);
        next.delete(paragraphId);
        return next;
      });
      matches.forEach((node) => {
        if (node && node.isConnected) node.removeAttribute("data-flash");
      });
    }, FLASH_MS);
  }, []);

  return {
    activeParagraphId,
    flashedBodyId,
    flashedRailIds,
    scrollBodyTo,
    scrollRailTo,
  };
}
