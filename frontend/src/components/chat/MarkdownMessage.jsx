/**
 * MarkdownMessage — streaming-safe markdown renderer for chat assistant
 * bubbles. Wraps `react-markdown` with the same plugin set the chat
 * surface used inline (remarkGfm + rehypeHighlight) and adds the
 * Workstream B.1 polish:
 *
 *   - Blinking cursor `▌` while `streaming === true` (CSS keyframe,
 *     not JS interval, so it survives heavy DOM diffing).
 *   - Custom code/link/table/pre/img renderers in one place.
 *   - `disallowedElements` to neutralise any LLM that tries to emit
 *     <script>/<iframe>/<style>/<form> tags.
 *   - The wrapper is a div with `data-testid` so the existing test
 *     selectors (`chat-msg-assistant-md` / `chat-msg-assistant-streaming`)
 *     keep matching.
 *
 * Citation rendering stays out of this component on purpose. The
 * citation-bearing path in Chat.jsx still uses `renderInlineCitations`
 * because mixing react-markdown's string parser with React node
 * substitutions for `[n]` markers is brittle. The two paths share the
 * same outer container styles via `akki-chat-md`.
 */
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import "./MarkdownMessage.css";

const COMPONENTS = {
  a: ({ node: _node, ...props }) => (
    <a
      {...props}
      target="_blank"
      rel="noreferrer noopener"
    />
  ),
  table: ({ node: _node, ...props }) => (
    <div className="akki-chat-md-table-wrap" style={{ overflowX: "auto" }}>
      <table {...props} />
    </div>
  ),
  code: ({ node: _node, inline, ...props }) =>
    inline
      ? <code {...props} />
      : <code {...props} />,
  pre: ({ node: _node, ...props }) => <pre {...props} />,
  img: ({ node: _node, ...props }) => (
    <img {...props} alt={props.alt || ""} loading="lazy" />
  ),
};

const DISALLOWED = ["script", "iframe", "style", "form"];

export default function MarkdownMessage({ content, streaming = false }) {
  return (
    <div
      className="akki-chat-md"
      data-testid={streaming ? "chat-msg-assistant-streaming" : "chat-msg-assistant-md"}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        disallowedElements={DISALLOWED}
        unwrapDisallowed
        components={COMPONENTS}
      >
        {content || ""}
      </ReactMarkdown>
      {streaming && (
        <span
          className="akki-chat-md-cursor"
          aria-hidden="true"
        >
          ▌
        </span>
      )}
    </div>
  );
}
