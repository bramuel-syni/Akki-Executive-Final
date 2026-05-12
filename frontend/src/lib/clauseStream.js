/**
 * clauseStream — Patch 12 Streaming v3.
 *
 * Variable-cadence token grouping for the streaming render layer.
 *
 * Philosophy: authenticity over theatre. We DO NOT pad with artificial
 * delay if the model isn't producing. We ALSO do not rip characters
 * across the page one-by-one — that looks fake. We group arriving
 * tokens into clauses, emit each clause at a natural cadence, and let
 * the model's actual pace drive the rest.
 *
 * Public API:
 *   const fb = createClauseBuffer({ onFlush: clause => …, opts? });
 *   fb.push(token);          // feed tokens as they arrive
 *   fb.flush();              // force-flush remaining content
 *   fb.cancel();              // stop any pending timers
 *
 * Behaviour:
 *   - Plain text mode: group tokens into clauses by detecting boundary
 *     punctuation (`,`, `;`, `:`, `—`, `. `, `! `, `? `, newline, end-of-heading).
 *     Emit when boundary hit OR 80ms elapsed since last flush.
 *   - Heading mode (markdown `#`/`##`/`###` at start of line, or a `<h1>`..`<h3>` tag):
 *     buffer the entire heading, emit at once on the terminating newline.
 *   - Code-block mode (triple backtick fences): stream line-by-line, no
 *     clause grouping inside.
 *   - List mode (`- ` or `* ` at line start): emit item-by-item.
 *
 * Inter-clause pacing is the consumer's responsibility — `createClausePacer`
 * (below) is the helper that schedules onClause callbacks with the 60–140ms
 * micro-delay and the 180–260ms end-of-sentence pause.
 */

export const DEFAULTS = Object.freeze({
  flushMs: 80,           // force-flush stale buffer
  clauseMinMs: 60,       // min inter-clause delay
  clauseMaxMs: 140,      // max inter-clause delay
  sentenceMinMs: 180,    // min end-of-sentence pause
  sentenceMaxMs: 260,    // max end-of-sentence pause
  listItemPauseMs: 100,
});


// Detect whether a buffer ends in a clause boundary.
//   Returns { kind: "clause"|"sentence"|"list"|"heading_end"|"none", idx }
//   where idx is the inclusive end index of the matched boundary.
export function detectClauseBoundary(buf) {
  if (!buf) return { kind: "none", idx: -1 };

  // End-of-sentence has highest priority.
  const sentenceEnd = buf.search(/[.!?](?:\s|$)/);
  if (sentenceEnd >= 0 && (sentenceEnd === buf.length - 1 || /\s/.test(buf[sentenceEnd + 1]))) {
    // Include the trailing whitespace if present.
    const lastIdx = sentenceEnd + 1 < buf.length ? sentenceEnd + 1 : sentenceEnd;
    return { kind: "sentence", idx: lastIdx };
  }

  // Newline → either heading end (when buffer starts with #) or paragraph break.
  const nl = buf.indexOf("\n");
  if (nl >= 0) {
    if (/^\s*#{1,3}\s/.test(buf)) {
      return { kind: "heading_end", idx: nl };
    }
    return { kind: "sentence", idx: nl };
  }

  // List-item boundary — `- ` or `* ` after the previous newline.
  if (/^[\-*]\s/.test(buf)) {
    // Only treat as a list item if it's a freshly-started line; otherwise
    // it's just punctuation in the middle of prose.
    return { kind: "list", idx: 1 };
  }

  // Soft clause boundary — commas, semicolons, colons, em-dashes.
  const softMatch = buf.match(/[,;:—]/);
  if (softMatch && softMatch.index !== undefined && softMatch.index >= 4) {
    return { kind: "clause", idx: softMatch.index };
  }

  return { kind: "none", idx: -1 };
}


export function createClauseBuffer({ onFlush, opts = {} } = {}) {
  const o = { ...DEFAULTS, ...opts };
  let buf = "";
  let mode = "text";       // "text" | "code" | "heading"
  let codeFence = "";
  let flushTimer = null;
  let cancelled = false;

  const scheduleFlush = () => {
    if (flushTimer) return;
    flushTimer = setTimeout(() => {
      flushTimer = null;
      if (!cancelled && buf) {
        const out = buf;
        buf = "";
        onFlush && onFlush({ text: out, kind: "stale", mode });
      }
    }, o.flushMs);
  };

  const push = (token) => {
    if (cancelled || token == null) return;
    buf += String(token);

    // Code-fence detection — switch mode on encountering ```.
    while (true) {
      if (mode === "text") {
        const fenceIdx = buf.indexOf("```");
        if (fenceIdx < 0) break;
        // Flush any text BEFORE the fence as a sentence boundary.
        if (fenceIdx > 0) {
          const out = buf.slice(0, fenceIdx);
          onFlush && onFlush({ text: out, kind: "sentence", mode: "text" });
        }
        buf = buf.slice(fenceIdx + 3);
        mode = "code";
        codeFence = "```";
        continue;
      }
      if (mode === "code") {
        const fenceIdx = buf.indexOf("```");
        if (fenceIdx < 0) {
          // Stream complete code lines as they accumulate.
          const nl = buf.indexOf("\n");
          if (nl < 0) break;
          const line = buf.slice(0, nl + 1);
          buf = buf.slice(nl + 1);
          onFlush && onFlush({ text: line, kind: "code_line", mode: "code" });
          continue;
        }
        // Close-fence reached.
        const tail = buf.slice(0, fenceIdx);
        buf = buf.slice(fenceIdx + 3);
        if (tail) onFlush && onFlush({ text: tail, kind: "code_line", mode: "code" });
        onFlush && onFlush({ text: codeFence, kind: "code_close", mode: "code" });
        mode = "text";
        codeFence = "";
        continue;
      }
      break;
    }

    if (mode !== "text") {
      scheduleFlush();
      return;
    }

    // Plain text — emit on the deepest boundary in the buffer.
    while (true) {
      const b = detectClauseBoundary(buf);
      if (b.kind === "none") break;
      const slice = buf.slice(0, b.idx + 1);
      buf = buf.slice(b.idx + 1);
      onFlush && onFlush({ text: slice, kind: b.kind, mode: "text" });
    }
    scheduleFlush();
  };

  const flush = () => {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    if (!cancelled && buf) {
      const out = buf;
      buf = "";
      onFlush && onFlush({ text: out, kind: "final", mode });
    }
  };

  const cancel = () => {
    cancelled = true;
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
  };

  return { push, flush, cancel };
}


function _rand(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}


/**
 * Schedule onClause callbacks with the locked inter-clause pacing.
 * Used by the StreamingShell renderer to convert clause flushes
 * (from createClauseBuffer) into the visible cadence.
 */
export function createClausePacer({ onClause, opts = {} } = {}) {
  const o = { ...DEFAULTS, ...opts };
  const queue = [];
  let running = false;
  let cancelled = false;

  const run = async () => {
    if (running) return;
    running = true;
    while (queue.length && !cancelled) {
      const clause = queue.shift();
      onClause && onClause(clause);
      // Decide the delay based on the boundary kind.
      let ms = _rand(o.clauseMinMs, o.clauseMaxMs);
      if (clause.kind === "sentence") ms = _rand(o.sentenceMinMs, o.sentenceMaxMs);
      else if (clause.kind === "list") ms = o.listItemPauseMs;
      else if (clause.kind === "heading_end") ms = 200;
      // If the model produced this clause as a single flush after the
      // backend had already buffered the rest, queue depth grows fast.
      // Compress the delay so we never feel sluggish — cap effective
      // wait when the queue is deep (authenticity rule: don't dwell).
      if (queue.length > 6) ms = Math.min(ms, 40);
      // eslint-disable-next-line no-await-in-loop
      await new Promise((res) => setTimeout(res, ms));
    }
    running = false;
  };

  const enqueue = (clause) => {
    queue.push(clause);
    if (!running) run();
  };

  const cancel = () => {
    cancelled = true;
    queue.length = 0;
  };

  return { enqueue, cancel };
}
