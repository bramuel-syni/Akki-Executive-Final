/**
 * Streaming markdown block parser — pure, no react/markdown imports.
 *
 * Phase A (2026-05-10) — extracted from MarkdownMessage.jsx so it can
 * be unit-tested under jest without pulling in the ESM-only
 * react-markdown package. The streaming-flicker fix depends on this
 * function being correct and APPEND-ONLY: once a block is committed
 * to `closed`, every subsequent call with a longer prefix must
 * return the same `closed[i]` for that index. React.memo short-
 * circuits identical-content blocks; if this invariant breaks, the
 * bubble flickers.
 *
 * Closed-block boundary = a blank line ("") OUTSIDE any unclosed
 * code fence. Fence state is tracked by toggling on lines matching
 * `/^\s*```/` — the same heuristic CommonMark uses for fence
 * detection.
 */

/**
 * Split streaming content into closed blocks + a tail block.
 *
 * @param {string} content  Accumulated streamed text.
 * @returns {{closed: string[], tail: string}}
 *
 * Examples:
 *   ""                                → { closed: [], tail: "" }
 *   "para"                             → { closed: [], tail: "para" }
 *   "para1\n\npara2"                   → { closed: ["para1"], tail: "para2" }
 *   "```py\nx=1\n```\n\ntail"          → { closed: ["```py\nx=1\n```"], tail: "tail" }
 *   "```py\npartial..."                → { closed: [], tail: "```py\npartial..." }
 *   "- a\n- b\n\n"                     → { closed: ["- a\n- b"], tail: "" }
 */
export function splitIntoBlocks(content) {
  if (!content) return { closed: [], tail: "" };
  const lines = content.split("\n");
  const closed = [];
  let buf = [];
  let inFence = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (/^\s*```/.test(line)) inFence = !inFence;
    if (line === "" && !inFence && buf.length > 0) {
      closed.push(buf.join("\n"));
      buf = [];
      continue;
    }
    buf.push(line);
  }
  return { closed, tail: buf.join("\n") };
}
