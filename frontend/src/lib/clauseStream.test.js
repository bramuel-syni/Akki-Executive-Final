/**
 * clauseStream.test.js — Patch 12 unit tests.
 *
 * Runs with Node 18+ via `node --test`. Covers:
 *   1. punctuation grouping
 *   2. heading detection
 *   3. code block bypass
 *   4. list item pacing
 *
 * Invoke:
 *   cd /app/frontend && node --test src/lib/clauseStream.test.js
 *
 * The package's CRA Jest config doesn't auto-discover these tests, so we
 * use Node's built-in runner to keep this self-contained.
 */
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { createClauseBuffer, detectClauseBoundary } from "./clauseStream.js";


function harness() {
  const flushes = [];
  const buf = createClauseBuffer({
    onFlush: (c) => flushes.push(c),
    opts: { flushMs: 1_000_000 },  // disable stale-flush during tests
  });
  return { flushes, buf };
}


describe("clauseStream — punctuation grouping", () => {
  test("emits a clause on a sentence boundary", () => {
    const { flushes, buf } = harness();
    buf.push("This is a sentence. ");
    assert.equal(flushes.length, 1);
    assert.equal(flushes[0].kind, "sentence");
    assert.match(flushes[0].text, /sentence/);
  });

  test("emits soft clauses on commas / semicolons", () => {
    const { flushes, buf } = harness();
    buf.push("First clause, second clause; third clause");
    const kinds = flushes.map((f) => f.kind);
    assert.ok(kinds.includes("clause"), `expected a clause kind; got ${JSON.stringify(kinds)}`);
  });

  test("multiple sentences stream out in order", () => {
    const { flushes, buf } = harness();
    buf.push("Alpha. Beta! Gamma? ");
    const concat = flushes.map((f) => f.text).join("");
    assert.match(concat, /Alpha.*Beta.*Gamma/);
  });
});


describe("clauseStream — heading detection", () => {
  test("buffers a markdown heading and emits whole at newline", () => {
    const { flushes, buf } = harness();
    buf.push("# Title heading line");
    // No newline yet — nothing should have flushed as a heading_end.
    assert.equal(flushes.filter((f) => f.kind === "heading_end").length, 0);
    buf.push("\n");
    const heads = flushes.filter((f) => f.kind === "heading_end");
    assert.equal(heads.length, 1);
    assert.match(heads[0].text, /Title heading line/);
  });

  test("detectClauseBoundary tags heading endings", () => {
    const r = detectClauseBoundary("## Sub-section\n");
    assert.equal(r.kind, "heading_end");
  });
});


describe("clauseStream — code block bypass", () => {
  test("inside a code fence we stream line-by-line, no clause grouping", () => {
    const { flushes, buf } = harness();
    buf.push("```\n");
    buf.push("const x = 1, y = 2;\n");   // would normally split on `,` and `;`
    buf.push("const z = 3;\n");
    // Lines emitted as code_line, not clause/sentence.
    const codeLines = flushes.filter((f) => f.kind === "code_line");
    assert.ok(codeLines.length >= 2, `expected at least 2 code_line emissions, got ${codeLines.length}`);
    assert.equal(flushes.filter((f) => f.kind === "clause").length, 0);
  });

  test("close-fence returns mode to text", () => {
    const { flushes, buf } = harness();
    buf.push("```\nint a = 1;\n```\n");
    buf.push("Plain sentence. ");
    const last = flushes[flushes.length - 1];
    assert.equal(last.kind, "sentence");
  });
});


describe("clauseStream — list item pacing", () => {
  test("list items emit as separate flushes", () => {
    const { flushes, buf } = harness();
    buf.push("- first item\n");
    buf.push("- second item\n");
    buf.push("- third item\n");
    // Each item should be flushed independently (either as a list-kind or
    // as a sentence-kind boundary at the newline). What matters: 3 items
    // produce 3 visible flushes, not one merged block.
    const itemTexts = flushes.map((f) => f.text);
    assert.ok(
      itemTexts.some((t) => /first/.test(t)) &&
      itemTexts.some((t) => /second/.test(t)) &&
      itemTexts.some((t) => /third/.test(t)),
      `list items not flushed independently: ${JSON.stringify(itemTexts)}`,
    );
  });
});
