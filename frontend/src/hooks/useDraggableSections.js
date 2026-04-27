/**
 * useDraggableSections — tiny native HTML5 DnD helper for the home page.
 *
 * Persists the order of N keyed sections to localStorage so each user
 * gets the layout they prefer. No external DnD library; no animation
 * library. Just enough to let the user grab a handle and drop the
 * section above or below another.
 *
 * Usage:
 *   const { items, getDragProps } = useDraggableSections('home', [
 *     { key: 'summary', node: <InSummaryTiles /> },
 *     { key: 'workflows', node: <WorkflowsHub /> },
 *     { key: 'inbox', node: <ReviewInboxCard /> },
 *   ]);
 *   return items.map((it) => (
 *     <div key={it.key} {...getDragProps(it.key)}>
 *       <DragHandle />
 *       {it.node}
 *     </div>
 *   ));
 */
import { useCallback, useEffect, useMemo, useState } from "react";

const STORAGE_PREFIX = "akki:section-order:";

export default function useDraggableSections(scope, sections) {
  const storageKey = `${STORAGE_PREFIX}${scope}`;

  // Hydrate stored order, but always reconcile against the current
  // section list so freshly-added sections aren't lost.
  const computeOrdered = useCallback((stored) => {
    const list = sections.filter(Boolean);
    if (!Array.isArray(stored) || stored.length === 0) return list;
    const known = new Map(list.map((s) => [s.key, s]));
    const ordered = [];
    for (const k of stored) {
      const s = known.get(k);
      if (s) { ordered.push(s); known.delete(k); }
    }
    // Append any new sections at the end so additions don't disappear.
    for (const s of known.values()) ordered.push(s);
    return ordered;
  }, [sections]);

  const [items, setItems] = useState(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      const parsed = raw ? JSON.parse(raw) : null;
      return computeOrdered(parsed);
    } catch {
      return sections.filter(Boolean);
    }
  });

  // Re-reconcile if the *set* of sections changes (additions / removals).
  // Compare keys only — node identity will change every render and we
  // don't want that to wipe the user's order.
  const incomingKeys = useMemo(
    () => sections.filter(Boolean).map((s) => s.key).join("|"),
    [sections],
  );
  useEffect(() => {
    setItems((prev) => {
      const current = prev.map((s) => s.key).join("|");
      const wanted = sections.filter(Boolean).map((s) => s.key);
      const wantedSet = new Set(wanted);
      const prevSet = new Set(prev.map((s) => s.key));
      const added   = wanted.filter((k) => !prevSet.has(k));
      const removed = [...prevSet].filter((k) => !wantedSet.has(k));
      if (current === incomingKeys && added.length === 0 && removed.length === 0) {
        // Same shape — refresh nodes (latest props) without reordering.
        return prev.map((s) => sections.find((x) => x.key === s.key) || s);
      }
      // Re-derive from storage + new shape.
      try {
        const raw = localStorage.getItem(storageKey);
        const parsed = raw ? JSON.parse(raw) : null;
        return computeOrdered(parsed);
      } catch { return computeOrdered(null); }
    });
  }, [incomingKeys, sections, storageKey, computeOrdered]);

  const persist = useCallback((next) => {
    try { localStorage.setItem(storageKey, JSON.stringify(next.map((s) => s.key))); }
    catch { /* swallow quota errors */ }
  }, [storageKey]);

  // ── Drag handlers ──────────────────────────────────────────────────
  const [draggingKey, setDraggingKey] = useState(null);
  const [overKey, setOverKey] = useState(null);

  const onDragStart = (key) => (e) => {
    setDraggingKey(key);
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", key); } catch { /* IE */ }
  };

  const onDragOver = (key) => (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (overKey !== key) setOverKey(key);
  };

  const onDragLeave = () => setOverKey(null);

  const onDrop = (key) => (e) => {
    e.preventDefault();
    const fromKey = draggingKey || (() => {
      try { return e.dataTransfer.getData("text/plain"); } catch { return null; }
    })();
    if (!fromKey || fromKey === key) {
      setDraggingKey(null); setOverKey(null); return;
    }
    setItems((prev) => {
      const next = [...prev];
      const fromIdx = next.findIndex((s) => s.key === fromKey);
      const toIdx   = next.findIndex((s) => s.key === key);
      if (fromIdx < 0 || toIdx < 0) return prev;
      const [moved] = next.splice(fromIdx, 1);
      next.splice(toIdx, 0, moved);
      persist(next);
      return next;
    });
    setDraggingKey(null); setOverKey(null);
  };

  const onDragEnd = () => { setDraggingKey(null); setOverKey(null); };

  const reset = useCallback(() => {
    try { localStorage.removeItem(storageKey); } catch { /* noop */ }
    setItems(sections.filter(Boolean));
  }, [sections, storageKey]);

  const getDragProps = useCallback((key) => ({
    onDragOver: onDragOver(key),
    onDragLeave,
    onDrop: onDrop(key),
    "data-dragging": draggingKey === key ? "true" : undefined,
    "data-drag-over": overKey === key && draggingKey !== key ? "true" : undefined,
  }), [draggingKey, overKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const getHandleProps = useCallback((key) => ({
    draggable: true,
    onDragStart: onDragStart(key),
    onDragEnd,
    role: "button",
    "aria-label": "Drag to reorder",
    tabIndex: 0,
  }), []); // eslint-disable-line react-hooks/exhaustive-deps

  return { items, getDragProps, getHandleProps, reset, draggingKey, overKey };
}
