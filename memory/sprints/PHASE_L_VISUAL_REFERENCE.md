# Phase L — Visual Reference (LOCKED 2026-05-27)

**Status:** Locked spec doc. Future agents who think the Phase L visual treatment
is "monospace terminal log" or "single-line fade" are **WRONG**. Reference the
Claude screenshot below.

**Source:** `https://customer-assets.emergentagent.com/job_feature-docs/artifacts/26ggzk4h_Screenshot_20260527_214736_Chrome.jpg`

---

## Locked visual properties (Claude-reference)

- **Layout:** multi-line, progressive reveal. Each phase appears as a distinct
  line/block as it starts. Completed phases REMAIN visible with a completion
  indicator (checkmark or similar). **NOT single-line-fade.**

- **Font:** sans-serif. Use the app's existing body font stack.

- **Colour:** muted greys on near-white. Dark grey text. Ample whitespace.

- **Animation:** subtle fade-in for new phase lines (200ms). NO spinners,
  NO progress bars, NO percentages, NO typing animations.

- **Icons:** subtle, semantically meaningful per phase where applicable (e.g.
  globe for fetch/search, doc for read/load, sparkle for compose, checkmark
  for done). NOT decorative.

- **Aesthetic:** conversational composition feel, NOT terminal/system-log.
  Closer to "I'm watching it think through this in sentences" than "I'm
  watching a console scroll."

- **Reduced motion:** collapses to final state without transitions.

---

## Why this doc exists (forgetting mitigation)

Sprint was circling on the visual treatment because the original PHASE_LEDGER
row L said "Direction B muted system-log" — no standalone spec doc backed it.
The pre-build brief recovered no spec but flagged monospace/terminal as the
agent's interpretation. The user OVERRODE that interpretation 2026-05-27 with
the Claude reference above. This file is the durable artifact that prevents
agents from re-interpreting away from the lock.

**If you (future agent) think the loader should be monospace / terminal / single-
line / typewriter / scroll-up / progress-bar — STOP. Re-read this doc.**

---

## Phase script per surface (locked in PHASE_LEDGER L row)

Each surface declares an ordered list of 5–8 phase labels. The frontend
`StreamingLogScene` renders them progressively as the backend SSE pipe
emits phase-index advances. The voice carries the Phase K signature:

- "Reading your framing." (or "Reading the cycle inputs." etc.)
- "Checking the grounding contract."
- "Composing." / "Drafting the outline." / "Rendering the artefact."
- "Validating."
- "Almost there."

Per-surface scripts live in `backend/services/streaming/progress.py` (`PHASE_SCRIPTS`
dict). When R.5 / future phases add new long-ops, they MUST update that dict
AND this file's surface table.

---

## Linked artifacts

- `backend/services/streaming/sse.py` — server-side SSE helper.
- `backend/services/streaming/progress.py` — `PhaseEmitter` + `PHASE_SCRIPTS`.
- `frontend/src/hooks/useStreamingProgress.js` — EventSource client.
- `frontend/src/components/transitions/StreamingLogScene.jsx` — Claude-style multi-line progressive reveal.
- `backend/tests/test_phase_la_streaming_loader.py` — CI lockdown on visual contract + SSE behaviour.
