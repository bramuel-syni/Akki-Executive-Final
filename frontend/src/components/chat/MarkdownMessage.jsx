/**
 * MarkdownMessage — streaming-safe markdown renderer for chat assistant
 * bubbles.
 *
 * 2026-05-10: rewritten to fix the streaming-flicker bug a UAT user
 * reported. The original version re-ran `react-markdown` on every
 * delta, which (a) rebuilt the AST per token and (b) ran
 * `rehype-highlight` on partial code blocks, producing flash-of-
 * unhighlighted-text + a perceptible flicker in the chat bubble.
 *
 * Fixes shipped here (Workstream A):
 *   1. **Throttle re-renders to ~30 fps via `requestAnimationFrame`**.
 *      We coalesce rapid `content` changes into one render per frame.
 *      On the boundary (streaming flips false), we drain instantly so
 *      the canonical text lands without delay.
 *   2. **`React.memo`** on the inner body so identical content
 *      strings are short-circuited (no AST rebuild).
 *   3. **Stable `components` and `plugin` arrays** via module-level
 *      consts — re-using react-markdown's `useMemo` for them was
 *      actually preventing the AST cache from working.
 *   4. **Skip `rehype-highlight` while streaming**. Partial code
 *      blocks are the worst offender for visible flicker. We apply
 *      highlighting only on the canonical (post-stream) render. On
 *      `streaming=false` we re-render once with highlight on.
 *   5. **No `will-change: contents`** — that hint was hurting.
 *      Removed from the CSS file too.
 *   6. **CSS containment** (`contain: layout style`) is set on the
 *      outer div so the chat list above the streaming message doesn't
 *      reflow when the bubble grows.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import "./MarkdownMessage.css";

// Module-level constants — referential stability. React-markdown
// caches its parser based on plugin identity; recreating arrays per
// render busts that cache.
const REMARK_PLUGINS = [remarkGfm];
const REHYPE_PLUGINS_WITH_HIGHLIGHT = [rehypeHighlight];
const REHYPE_PLUGINS_NONE = [];

const DISALLOWED = ["script", "iframe", "style", "form"];

const COMPONENTS = {
  a: ({ node: _node, ...props }) => (
    <a {...props} target="_blank" rel="noreferrer noopener" />
  ),
  table: ({ node: _node, ...props }) => (
    <div className="akki-chat-md-table-wrap" style={{ overflowX: "auto" }}>
      <table {...props} />
    </div>
  ),
  code: ({ node: _node, inline, ...props }) =>
    // Inline vs block — both use the same default <code> render but
    // we keep the function so future targeted styling has a place to
    // live without restructuring callers.
    inline ? <code {...props} /> : <code {...props} />,
  pre: ({ node: _node, ...props }) => <pre {...props} />,
  img: ({ node: _node, ...props }) => (
    <img {...props} alt={props.alt || ""} loading="lazy" />
  ),
};

/**
 * Inner memo'd body. Pure function of (content, streaming). React
 * skips the render when both are referentially equal — which, for
 * `content` (a string), is value-equal.
 */
const MarkdownBody = React.memo(function MarkdownBody({ content, streaming }) {
  // Skip rehype-highlight while streaming — partial code blocks
  // cause flash-of-unhighlighted-text on every chunk. Apply on the
  // canonical (post-stream) render only. The user sees highlighting
  // when the message lands, which is the same UX claude.ai uses.
  const rehypePlugins = streaming ? REHYPE_PLUGINS_NONE : REHYPE_PLUGINS_WITH_HIGHLIGHT;
  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      rehypePlugins={rehypePlugins}
      disallowedElements={DISALLOWED}
      unwrapDisallowed
      components={COMPONENTS}
    >
      {content || ""}
    </ReactMarkdown>
  );
});


/**
 * Throttle the visible content to one update per animation frame.
 * Returns the throttled value. On `streaming=false` we drain
 * immediately so the canonical text is exact at the moment the
 * bubble lands.
 */
function useRafThrottledContent(content, streaming) {
  const [shown, setShown] = useState(content);
  const pendingRef = useRef(content);
  const rafRef = useRef(null);

  useEffect(() => {
    pendingRef.current = content;
    if (!streaming) {
      // Stream just ended — drain instantly, cancel any pending RAF.
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      setShown(content);
      return undefined;
    }
    if (rafRef.current) return undefined; // already scheduled
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      setShown(pendingRef.current);
    });
    return undefined;
  }, [content, streaming]);

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }, []);

  return shown;
}


export default function MarkdownMessage({ content, streaming = false }) {
  const throttled = useRafThrottledContent(content, streaming);
  // Memo the testid so the outer div doesn't churn its data attr.
  const testid = useMemo(
    () => (streaming ? "chat-msg-assistant-streaming" : "chat-msg-assistant-md"),
    [streaming],
  );
  return (
    <div className="akki-chat-md" data-testid={testid}>
      <MarkdownBody content={throttled} streaming={streaming} />
      {streaming && (
        <span className="akki-chat-md-cursor" aria-hidden="true">
          ▌
        </span>
      )}
    </div>
  );
}
