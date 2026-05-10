/**
 * MarkdownMessage — append-only streaming markdown renderer.
 *
 * 2026-05-10 — Phase A re-rewrite. The previous version (rAF-throttle +
 * single ReactMarkdown over the entire accumulated string) still
 * flickered because react-markdown rebuilt the AST and replaced DOM
 * nodes for prior tokens on every chunk. Even with rehype-highlight
 * disabled mid-stream, the final swap "to highlight on" caused all
 * code blocks to re-style at once.
 *
 * Phase A acceptance:
 *   - Once a token is rendered it must NOT re-mount or re-style.
 *   - Markdown blocks render progressively; partial fences/lists/tables
 *     show as plain prose until they close, then upgrade in-place
 *     without disturbing earlier content.
 *   - rehype-highlight is allowed (per closed block) without flash.
 *
 * Strategy:
 *   1. Split `content` into a list of CLOSED blocks + 1 TAIL block.
 *      A closed block is a markdown unit (paragraph, fenced code,
 *      list, table) that has been fully delimited by a blank line
 *      OUTSIDE any unclosed code fence.
 *   2. Each closed block renders via a memoised `<MarkdownBlock>` that
 *      keys on the block's final string. Because closed[i] is value-
 *      stable across deltas, React.memo short-circuits the render and
 *      the underlying DOM nodes keep their identity (verifiable via
 *      `data-block-idx`).
 *   3. The tail block is the only piece that re-renders per chunk.
 *      It renders WITHOUT rehype-highlight (so partial code doesn't
 *      flash). When the next blank-line boundary arrives, the tail
 *      becomes a new closed block — at which point it gets the full
 *      ReactMarkdown + rehype-highlight render once, in place.
 *   4. CSS containment isolates the bubble so growing the tail does
 *      not reflow earlier blocks.
 *
 * AC #1 verifier: pages can `querySelectorAll('[data-block-idx]')` and
 * compare element identity (or innerHTML) at t=2s vs t=8s of an 8000+
 * token stream. Closed blocks must be identical.
 */
import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import "./MarkdownMessage.css";
import { splitIntoBlocks } from "./markdownStream";

// Module-level constants — referential stability so react-markdown's
// internal cache keys hold across renders.
const REMARK_PLUGINS = [remarkGfm];
const REHYPE_HIGHLIGHT = [rehypeHighlight];
const REHYPE_NONE = [];
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
    inline ? <code {...props} /> : <code {...props} />,
  pre: ({ node: _node, ...props }) => <pre {...props} />,
  img: ({ node: _node, ...props }) => (
    <img {...props} alt={props.alt || ""} loading="lazy" />
  ),
};

/**
 * Split streaming content into closed blocks + a tail block.
 *
 * Implementation lives in `./markdownStream` so it can be unit-tested
 * without pulling in react-markdown's ESM chain. Re-exported here for
 * backwards-compatibility with any caller that imports from the
 * component module.
 */
export { splitIntoBlocks };

/**
 * Render one closed markdown block. React.memo keys on `content` —
 * because closed[i] is value-stable across the whole stream once it
 * commits, the memo short-circuits every subsequent render and the
 * underlying DOM nodes keep their identity.
 */
const MarkdownBlock = React.memo(function MarkdownBlock({ content, idx }) {
  return (
    <div data-block-idx={idx} data-block-state="closed">
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={REHYPE_HIGHLIGHT}
        disallowedElements={DISALLOWED}
        unwrapDisallowed
        components={COMPONENTS}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}, (prev, next) => prev.content === next.content && prev.idx === next.idx);

/**
 * Tail block — the only piece that re-renders per chunk. We disable
 * rehype-highlight here because it re-themes a partial fence on every
 * keystroke and produces visible flicker. The moment the fence closes
 * (next \n\n), the tail becomes a closed block and gets the full
 * ReactMarkdown + rehype-highlight render once, in place.
 *
 * When `streaming=false` and the tail is the final piece, we DO apply
 * rehype-highlight (the user is no longer watching deltas land).
 */
function TailBlock({ content, streaming, idx }) {
  if (!content) return null;
  const rehype = streaming ? REHYPE_NONE : REHYPE_HIGHLIGHT;
  return (
    <div data-block-idx={idx} data-block-state={streaming ? "tail-live" : "tail-final"}>
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={rehype}
        disallowedElements={DISALLOWED}
        unwrapDisallowed
        components={COMPONENTS}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default function MarkdownMessage({ content, streaming = false }) {
  const { closed, tail } = useMemo(() => splitIntoBlocks(content || ""), [content]);
  return (
    <div
      className="akki-chat-md"
      data-testid={streaming ? "chat-msg-assistant-streaming" : "chat-msg-assistant-md"}
      data-block-count={closed.length + (tail ? 1 : 0)}
    >
      {closed.map((blk, i) => (
        // key is the (index, content) pair so React preserves the same
        // DOM node for the same closed block across renders. Using just
        // `i` would be safe too because closed[i] is value-stable, but
        // including the content slice makes the keying obvious in
        // React DevTools.
        <MarkdownBlock
          key={`b${i}-${blk.length}-${blk.charCodeAt(0) || 0}`}
          idx={i}
          content={blk}
        />
      ))}
      <TailBlock content={tail} streaming={streaming} idx={closed.length} />
      {streaming && (
        <span className="akki-chat-md-cursor" aria-hidden="true">
          ▌
        </span>
      )}
    </div>
  );
}
