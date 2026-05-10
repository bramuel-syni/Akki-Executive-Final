"""Platform knowledge corpus.

A hand-curated, deterministic block describing AKKI's surfaces. Injected
into the chat system prompt by `services.two_pass.build_system_prompt`
so the model can answer 'what is X?' / 'how do I Y?' platform questions
without hallucinating from generic priors.

This is intentionally NOT RAG — for MVP, a static block keeps the audit
trail clean and the latency floor at zero. The delimiter pair lets us
swap to retrieval later without rewriting the prompt assembly.

When the user asks about a feature not listed here, the existing refusal
templates (`thin_input`, `unsourced_claim`) handle it: the closing line
of the block tells the model to refuse rather than invent.

Keep the block under ~2 KB so we don't burn tokens on platform context
for every substantive turn. If more depth is needed, swap to retrieval.
"""
from __future__ import annotations

PLATFORM_KB_BLOCK = """=== PLATFORM REFERENCE ===
You are answering questions about AKKI itself when relevant. Use this
reference verbatim. Do not invent features. If asked about anything
not listed here, say so plainly and suggest the user check the
Product page or ask their account admin.

Auto-Shield (Synisense Shield)
  What it does: redacts personally-identifiable and commercially
    sensitive content (names, emails, phone numbers, financial figures,
    legal entities) before any LLM call leaves the boundary, then
    rehydrates the original values locally on the response. Single
    chokepoint at the LLM gateway; runs on every chat turn, every
    document ingest, every Work Studio generation.
  Three policy levels (set per-chat in the header picker):
    auto    — redact when sensitivity is detected (default)
    always  — redact every message regardless of detection
    off     — send raw; user must acknowledge per send via dialog
  Audit: every Synisense run logs an input SHA-256 (never raw text)
    and a span count by entity type. Encrypted shield maps expire on
    a TTL set per surface (1h public, 24h default, 7d hard max).

Cycle Manager (boards & cycles)
  Six-step flow for the operating executive: Agenda → Team →
    Contributions → Scoreboard → Follow-ups → Draft Compilation.
  Executive flow is live; NED-side is design-only today.
  Each step is independently saveable; the cycle FSM at
    `cycle-config` advances phases.

Work Studio (briefings, decks, reports)
  Five-button bar on every aggregate: Export Brief (DOCX/PDF), Export
    Deck (PPTX/PDF), Export Report (DOCX/PDF), Enhance (deck/report),
    Continue in Chat.
  Every export persists deterministically: same inputs → same bytes,
    every render returns a SHA-256, every row carries a sensitivity
    band and the LLM provider used per pass.
  Continue in Chat mints a chat tethered to the artefact and the
    active company context, with the rendered file pre-attached.

Solva (decision-support reasoning)
  Four sub-modules: seek_clarity, develop_strategy,
    simulate_hypothesis, get_perspective.
  State machine: framing → grounding → synthesis → reflection
    (simulate_hypothesis adds a hypothesis layer).
  Refusal-by-design: when the grounding contract cannot be satisfied,
    Solva emits a refusal artefact rather than fabricating synthesis.
  PDF and DOCX exports of the final artefact.

Document Journal
  Drop-zone upload (DOCX, PDF, TXT, images), ClamAV-scanned, BM25
    search across the company's library, paragraph-anchor reading
    view, on-read commentary generated lazily.
  Ask-in-Chat from any document opens a chat tethered to the doc.

Pulse
  Same-context signal feed: comment, share, save, resolve,
    take-to-Solva. Cross-context aggregation is on the roadmap
    behind the Privacy Wall §2c lift.

Refusal taxonomy (server-authored, not LLM-improvised)
  thin_input — deterministic; fires when input is too thin to
    reason responsibly (≤280 chars, decision/strategy phrasing,
    no attached docs, no prior substantive turn).
  unsourced_claim — deterministic; fires when the assistant reply
    asserts a numeric or attribution claim with no [[cite:...]]
    token AND no grounding context.
  named_assumption — deterministic; fires when the reply makes a
    definitive statement about a named individual's intent or
    position without citation.

Audit posture
  Every chat turn is hash-chained: row_hash = SHA256(prev_hash +
    canonical_payload), genesis row prev_hash = GENESIS-AKKI-CHAT-AUDIT-2026.
  Verifiable export available at
    GET /api/chats/{chat_id}/audit/export.zip — returns the chain
    plus a verifier script.
  30-day retention on archived chats; the audit chain is preserved
    even after hard-delete.

When asked about features not listed above, say so — do not invent.
=== END PLATFORM REFERENCE ==="""


def get_platform_kb_block() -> str:
    """Return the platform reference block. Single-line wrapper kept so
    callers don't import a module-level string directly — future RAG
    swaps land here without touching `two_pass.build_system_prompt`."""
    return PLATFORM_KB_BLOCK
