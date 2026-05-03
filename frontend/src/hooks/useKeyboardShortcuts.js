/**
 * useKeyboardShortcuts — Phase 13.3 global keyboard shortcuts.
 *
 * Mounted ONCE at the AppShell level. Provides:
 *
 *   ⌘/Ctrl-K  — open the global command palette (delegated via the
 *               `akki:open-palette` custom event so AppShell stays the
 *               single source of truth for the existing palette state).
 *   ⌘/Ctrl-J  — "take into Solva". If the focused page has an element
 *               with `[data-solva-seed="kind:id"]`, that artefact is
 *               passed to /app/solva as `?seed_kind=...&seed_id=...`.
 *               Otherwise we fall through to the Solva landing.
 *   ⌘/Ctrl-S  — "save". Dispatches the `akki:save` custom event;
 *               components that own a save action (BlockComposer,
 *               report editor, brief form, etc.) listen and act. The
 *               browser's "Save Page" default is suppressed.
 *   ?         — open the discoverable help overlay listing every
 *               shortcut (the same overlay AppShell renders).
 *
 * The hook ALWAYS suppresses ⌘/Ctrl-S (otherwise the browser would
 * try to save the HTML page and produce a horrible UX). For typing-
 * sensitive keys (J, ?), it skips when an input/textarea/contenteditable
 * has focus, so users can type "?" naturally inside form fields.
 */
import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

function isTypingTarget(el) {
  if (!el) return false;
  const tag = (el.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  return false;
}

function findSolvaSeed() {
  if (typeof document === "undefined") return null;
  // Prefer a seed in the active focus tree (a detail panel within a
  // larger list page) so e.g. opening a single brief inside the
  // Briefs tab seeds Solva from THAT brief, not the first one in the
  // DOM. Fall back to the first seed on the page if no tree match.
  const active = document.activeElement;
  if (active && active !== document.body) {
    const inTree = active.closest?.("[data-solva-seed]");
    if (inTree) return inTree.getAttribute("data-solva-seed");
  }
  const any = document.querySelector("[data-solva-seed]");
  return any ? any.getAttribute("data-solva-seed") : null;
}

export default function useKeyboardShortcuts({ openHelp } = {}) {
  const navigate = useNavigate();

  const onKey = useCallback((e) => {
    const meta = e.metaKey || e.ctrlKey;
    const key = (e.key || "").toLowerCase();
    const target = e.target;

    // ⌘/Ctrl-S — always suppress browser "Save Page" and dispatch our
    // own save event. We do NOT skip on typing-targets here; saving
    // from inside a form is the entire point.
    if (meta && key === "s") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("akki:save", { detail: {
        ts: Date.now(),
        path: typeof window !== "undefined" ? window.location.pathname : null,
      }}));
      return;
    }

    // ⌘/Ctrl-K — open palette. AppShell owns the palette state, so we
    // dispatch a request event rather than wiring state through a
    // context. Do not skip on typing-targets — Cmd-K is universal.
    if (meta && key === "k") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("akki:open-palette"));
      return;
    }

    // ⌘/Ctrl-J — take into Solva. Skip when typing into a form so
    // ⌘-J inside a textarea doesn't yank the user away.
    if (meta && key === "j") {
      if (isTypingTarget(target)) return;
      e.preventDefault();
      const seed = findSolvaSeed();
      if (seed && seed.includes(":")) {
        const [kind, id] = seed.split(":", 2);
        navigate(`/app/solva?seed_kind=${encodeURIComponent(kind)}&seed_id=${encodeURIComponent(id)}`);
        toast.success("Taking this into Solva.");
      } else {
        navigate("/app/solva");
        toast.message("Opened Solva.", { description: "Pick a cluster to start a session." });
      }
      return;
    }

    // ?  — open help overlay (Shift-? on most US/EU keyboards renders
    // as "?"). Skip when typing.
    if (key === "?" && !meta && !isTypingTarget(target)) {
      e.preventDefault();
      if (typeof openHelp === "function") openHelp();
      return;
    }
  }, [navigate, openHelp]);

  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);
}
