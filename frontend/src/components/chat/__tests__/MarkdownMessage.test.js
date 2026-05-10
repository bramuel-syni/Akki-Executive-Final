/**
 * Phase A — MarkdownMessage block-parser regression suite.
 *
 * AC #1 / AC #2 lock-in: the streaming-flicker fix relies on
 * `splitIntoBlocks` producing a stable list of CLOSED blocks plus a
 * single TAIL block. Once a block is committed to `closed`, its
 * content must be value-stable across all subsequent calls (the
 * append-only invariant the React render depends on for
 * identity-stable DOM).
 *
 * If any of these tests fail the streaming bubble will flicker —
 * react-markdown will rebuild AST for previously-rendered blocks.
 */
import { splitIntoBlocks } from "../markdownStream";

describe("splitIntoBlocks — closed/tail partition", () => {
  test("empty content → no blocks", () => {
    expect(splitIntoBlocks("")).toEqual({ closed: [], tail: "" });
  });

  test("single in-progress paragraph stays in tail", () => {
    expect(splitIntoBlocks("Hello, partial")).toEqual({
      closed: [],
      tail: "Hello, partial",
    });
  });

  test("paragraph followed by blank line closes it", () => {
    expect(splitIntoBlocks("Para one\n\nPara two")).toEqual({
      closed: ["Para one"],
      tail: "Para two",
    });
  });

  test("multiple closed paragraphs accumulate", () => {
    expect(splitIntoBlocks("a\n\nb\n\nc")).toEqual({
      closed: ["a", "b"],
      tail: "c",
    });
  });

  test("complete fenced code block is a single closed block", () => {
    expect(splitIntoBlocks("```py\nx = 1\n```\n\ntail")).toEqual({
      closed: ["```py\nx = 1\n```"],
      tail: "tail",
    });
  });

  test("incomplete fence stays in tail (must NOT split)", () => {
    expect(splitIntoBlocks("```py\npartial...")).toEqual({
      closed: [],
      tail: "```py\npartial...",
    });
  });

  test("blank line INSIDE an open fence is NOT a boundary", () => {
    // Critical: if we naively split on blank lines inside a fence,
    // closed blocks would contain the half-open fence and the markdown
    // would render as malformed.
    expect(
      splitIntoBlocks("```js\nconst x = 1;\n\nconst y = 2;\n```\n\nafter"),
    ).toEqual({
      closed: ["```js\nconst x = 1;\n\nconst y = 2;\n```"],
      tail: "after",
    });
  });

  test("trailing blank line closes the buffer (tail empty)", () => {
    expect(splitIntoBlocks("- a\n- b\n\n")).toEqual({
      closed: ["- a\n- b"],
      tail: "",
    });
  });

  test("APPEND-ONLY INVARIANT (the streaming-flicker contract)", () => {
    // Simulate streaming by appending one character at a time. After
    // each append, the previously-committed `closed` blocks must be
    // VALUE-IDENTICAL to what they were on the previous step. This is
    // exactly what React.memo will short-circuit on.
    const fullStream =
      "Para one is here.\n" +
      "\n" +
      "```py\n" +
      "def f():\n" +
      "    return 1\n" +
      "```\n" +
      "\n" +
      "Final paragraph.";
    let prevClosed = [];
    for (let i = 1; i <= fullStream.length; i += 1) {
      const partial = fullStream.slice(0, i);
      const { closed } = splitIntoBlocks(partial);
      // Whatever was already closed at step (i-1) must remain identical.
      for (let j = 0; j < prevClosed.length; j += 1) {
        expect(closed[j]).toBe(prevClosed[j]);
      }
      prevClosed = closed;
    }
    // Final state covers every block.
    const final = splitIntoBlocks(fullStream);
    expect(final.closed).toEqual([
      "Para one is here.",
      "```py\ndef f():\n    return 1\n```",
    ]);
    expect(final.tail).toBe("Final paragraph.");
  });

  test("table block renders as one closed unit", () => {
    const table = "| h1 | h2 |\n| --- | --- |\n| a  | b  |\n\nAfter";
    expect(splitIntoBlocks(table)).toEqual({
      closed: ["| h1 | h2 |\n| --- | --- |\n| a  | b  |"],
      tail: "After",
    });
  });

  test("nested lists accumulate into one closed block", () => {
    const list = "- top\n  - nested\n- top2\n\nNext";
    expect(splitIntoBlocks(list)).toEqual({
      closed: ["- top\n  - nested\n- top2"],
      tail: "Next",
    });
  });

  test("AC #6 long-message stress — 3 fenced blocks + table + lists + inline marks", () => {
    const long = [
      "# Engineering memo",
      "",
      "Here is the **first** section with `inline code` and *italic*.",
      "",
      "```python",
      "def retry(fn, attempts=3):",
      "    for i in range(attempts):",
      "        try:",
      "            return fn()",
      "        except Exception:",
      "            continue",
      "```",
      "",
      "And then some JSON:",
      "",
      "```json",
      '{"db": {"host": "localhost", "port": 5432}}',
      "```",
      "",
      "Plus a bash example:",
      "",
      "```bash",
      "kubectl apply -f deploy.yaml",
      "kubectl rollout status deploy/api",
      "```",
      "",
      "Comparison table:",
      "",
      "| Broker | Order | Throughput |",
      "| --- | --- | --- |",
      "| Kafka | yes | 1M/s |",
      "| Rabbit | yes | 50K/s |",
      "",
      "Trade-offs:",
      "",
      "- top a",
      "  - nested a1",
      "  - nested a2",
      "- top b",
      "",
      "Final paragraph closes the memo.",
    ].join("\n");

    const { closed, tail } = splitIntoBlocks(long);
    // Expect distinct closed blocks for: heading, intro para, py fence,
    // intro JSON, json fence, intro bash, bash fence, intro table,
    // table, intro list, list. Tail = final paragraph.
    expect(closed.length).toBeGreaterThanOrEqual(8);
    expect(closed.some((b) => b.startsWith("```python"))).toBe(true);
    expect(closed.some((b) => b.startsWith("```json"))).toBe(true);
    expect(closed.some((b) => b.startsWith("```bash"))).toBe(true);
    expect(closed.some((b) => b.includes("| Broker"))).toBe(true);
    expect(closed.some((b) => b.includes("- top a"))).toBe(true);
    expect(tail).toBe("Final paragraph closes the memo.");

    // The streaming-flicker contract: simulate the same content
    // arriving 32 chars at a time. After EVERY step, every previously-
    // closed block must remain value-identical (this is what React.memo
    // short-circuits on, and is what AC #1 demands).
    let prev = [];
    for (let i = 1; i <= long.length; i += 32) {
      const partial = long.slice(0, Math.min(i, long.length));
      const { closed: cur } = splitIntoBlocks(partial);
      for (let j = 0; j < prev.length; j += 1) {
        expect(cur[j]).toBe(prev[j]);
      }
      prev = cur;
    }
  });
});
