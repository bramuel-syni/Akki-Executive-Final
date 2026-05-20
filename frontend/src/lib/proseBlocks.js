/**
 * proseBlocks.js — minimal markdown-light rendering helpers.
 *
 * Chunk 14 (SV-06, 2026-05-21) — Solva responses currently render
 * raw text inside a `<pre whitespace-pre-wrap>`. The QA brief asks
 * for structured paragraphs, bullet / numbered lists, and bold key
 * terms — WITHOUT introducing a markdown dependency (per dispatch
 * scope guard). This module provides the parsing primitives and is
 * also exportable to Pulse (which already inlines comparable
 * `stripCitations` + `splitToBullets` helpers — promotion to this
 * shared module is queued for a future cleanup pass; for now we
 * leave the Pulse inline copy in place and just provide a parallel
 * helper here).
 *
 * Scope:
 *   - Paragraphs:     split on `\n\n`
 *   - Bullet list:    lines starting with `- ` or `* `
 *   - Numbered list:  lines starting with `\d+\. `
 *   - Bold inline:    `**text**` → <strong>text</strong>
 *
 * Out of scope (per dispatch — "document the gap, don't add a dep"):
 *   - Tables (markdown `|`)
 *   - Code blocks (triple-backtick fence)
 *   - Headings (`#`, `##`, …)
 *   - Inline italic, links, images
 *
 * The output is an array of typed block objects ready to render via
 * the React `ProseRenderer` component (see SolvaPhaseDSession.jsx).
 *
 * Block shapes:
 *   {type: "paragraph", inlines: Inline[]}
 *   {type: "bullets",   items: Inline[][]}      // each item is an inline array
 *   {type: "numbered",  items: Inline[][]}
 *
 * Inline shapes:
 *   {kind: "text", text: string}
 *   {kind: "bold", text: string}
 */

const BULLET_LINE = /^\s*[-*]\s+(.+)$/;
const NUMBERED_LINE = /^\s*\d+\.\s+(.+)$/;
const BOLD = /\*\*([^*]+?)\*\*/g;

/** Tokenise a single line into an inline array, honouring `**bold**`. */
export function parseInlines(line) {
  if (!line) return [{ kind: "text", text: "" }];
  const out = [];
  let cursor = 0;
  let match;
  // Re-anchor each call (BOLD has /g flag).
  BOLD.lastIndex = 0;
  while ((match = BOLD.exec(line)) !== null) {
    if (match.index > cursor) {
      out.push({ kind: "text", text: line.slice(cursor, match.index) });
    }
    out.push({ kind: "bold", text: match[1] });
    cursor = match.index + match[0].length;
  }
  if (cursor < line.length) {
    out.push({ kind: "text", text: line.slice(cursor) });
  }
  // Empty bold-only inputs collapse to a single empty text node.
  return out.length > 0 ? out : [{ kind: "text", text: line }];
}

/**
 * Parse a markdown-light string into a flat array of typed blocks.
 *
 * Algorithm:
 *   1. Split on blank lines (\n\s*\n) to get paragraph candidates.
 *   2. For each candidate:
 *      a. Inspect line shapes. If all (or most) lines are bullet/
 *         numbered list items, emit a bullets/numbered block.
 *      b. Otherwise emit a paragraph block carrying inline tokens.
 *
 * Lists are NOT broken across paragraphs — the spec just asks that
 * bullets render as bullets and numbered lists render as numbered
 * lists; nested lists / multi-paragraph items are explicitly out of
 * scope.
 */
export function parseProseBlocks(text) {
  if (!text || typeof text !== "string") return [];
  const trimmed = text.trim();
  if (!trimmed) return [];
  const paragraphs = trimmed.split(/\n\s*\n+/).map((p) => p.trim()).filter(Boolean);
  const blocks = [];
  for (const para of paragraphs) {
    const lines = para.split(/\n/).map((l) => l.replace(/\s+$/, ""));
    const bullets = lines.map((l) => l.match(BULLET_LINE)).map((m) => m && m[1]);
    const numbers = lines.map((l) => l.match(NUMBERED_LINE)).map((m) => m && m[1]);
    if (bullets.length > 0 && bullets.every(Boolean)) {
      blocks.push({
        type: "bullets",
        items: bullets.map((line) => parseInlines(line)),
      });
      continue;
    }
    if (numbers.length > 0 && numbers.every(Boolean)) {
      blocks.push({
        type: "numbered",
        items: numbers.map((line) => parseInlines(line)),
      });
      continue;
    }
    // Default: paragraph. Multi-line paragraphs collapse with a
    // single space between lines (markdown convention).
    const joined = lines.join(" ").replace(/\s{2,}/g, " ");
    blocks.push({ type: "paragraph", inlines: parseInlines(joined) });
  }
  return blocks;
}
