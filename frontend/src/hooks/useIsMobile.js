/**
 * useIsMobile — tiny matchMedia hook so components can pick a mobile
 * variant without dragging in a heavier responsive lib.
 */
import { useEffect, useState } from "react";

export default function useIsMobile(maxWidth = 767) {
  const query = `(max-width: ${maxWidth}px)`;
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const mql = window.matchMedia(query);
    const onChange = (e) => setIsMobile(e.matches);
    mql.addEventListener?.("change", onChange);
    return () => mql.removeEventListener?.("change", onChange);
  }, [query]);

  return isMobile;
}
