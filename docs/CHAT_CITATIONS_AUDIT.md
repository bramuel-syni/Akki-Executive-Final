# Chat Citation Chips — Audit

_Phase 8 / Advisory 9 audit. Read-only inspection of the existing chat response shape end-to-end. No code changes were made for this audit._

## Question (a) — do backend chat responses already return structured citations?

**No.**

The single chat-completion endpoint is:

- `POST /api/chats/{chat_id}/messages` — implemented in `/app/backend/routers/chat.py:270`.

The response body returned to the client is:

```jsonc
{
  "user_message":      { "id", "chat_id", "role": "user",      "content", ... },
  "assistant_message": { "id", "chat_id", "role": "assistant", "content", "model_id", "model_label", "mode", "latency_ms", ... },
  "shielding":         { "identifiers_masked", "by_category", "shielded_by" },
  "will_shield":       true|false,
  "bypass_reason":     "..." | null
}
```

There is no `references[]`, `citations[]`, `sources[]` or `paragraph_id` field on either the user or the assistant message. A repo-wide grep for `citation`, `references`, `doc_id` and `paragraph_id` inside `/app/backend/routers/chat.py` returns zero matches.

**Why** — chat is a multi-turn conversation surface. The implementation in `routers/chat.py:362–395` replays the prior message history into a single text prompt and sends it to the chosen model. There is no document retrieval step (no BM25 call, no `gather_documents_for_grounding`), no reference resolution, and no post-processing that could attach citations to the assistant turn. The persisted `db.chat_messages` doc does not carry a citation field either.

For comparison, surfaces that **do** return citations:

- Briefings (`routers/briefings.py`) — every item carries `sources[] = [{doc_id, doc_name, paragraph_id?}]`.
- Ask (`routers/signals_ask.py`) — answers carry `references[]`.
- Signals (`routers/signals_ask.py`) — every signal carries `references[]`.

The chat surface is the **only** grounded-text-producing surface in the product that does not expose citation provenance.

## Question (b) — if yes, sufficient to render chips with click-through?

Not applicable.

## Question (c) — refactor brief

A focused refactor to bring chat to the same citation contract as Briefings and Ask. Approximate effort: one engineer-day to ship behind `?chat=v2`, half a day more to flip the default.

### 1. Data shape (additive — does not break existing clients)

Extend the assistant-message schema to carry citation provenance. The chat response becomes:

```jsonc
{
  "user_message":      { ... unchanged ... },
  "assistant_message": {
    ...,
    "references": [
      {
        "id":            "ref_<uuid8>",     // stable id for cross-referencing
        "doc_id":        "<documents.id>",
        "doc_name":      "Q3 board pack.pdf",
        "page":          12,
        "paragraph_id":  "p_3a8c…" | null,  // resolves into ReadingView
        "quote":         "<≤200 char extract>",
        "score":         0.41                // BM25 score, optional
      }
    ],
    "citation_markers": [                    // optional inline anchors
      { "ref_id": "ref_a3", "char_start": 248, "char_end": 261 }
    ]
  },
  ...
}
```

Persistence: store `references` and `citation_markers` on the same `db.chat_messages` doc so `GET /api/chats/{id}` and the audit-pack export carry the same provenance.

### 2. Endpoints to change

- `POST /api/chats/{chat_id}/messages` — gain a retrieval step before the LLM call, attach references to the assistant message, and persist them.
- `GET /api/chats/{chat_id}` — already returns messages; references will flow automatically once they're on the document.
- `GET /api/chats/{chat_id}/audit/export.zip` — already SHA-256 chains every message; chain shape stays the same. The exported `messages.jsonl` carries `references[]` for free.

No schema migration: `references` is an additive optional array on the existing message doc.

### 3. Backend logic — three steps inside `send_message`

Insert between lines 396 (full prompt assembly) and 400 (LLM call):

1. **Retrieval.** If the chat has a `context_id` (already on `db.chats`), call `gather_documents_for_grounding(context_id)` from `core.py` and run BM25 over `text` (the user message) using `bm25.py`. Top-5, score ≥ 0.1 floor.
2. **Prompt augmentation.** Inject the matched passages as a `[SOURCES]` block in `system_msg` with stable IDs (`[doc:X p.Y ¶Z]`) and instruct the model to cite using those tokens (the same convention briefings already use).
3. **Post-processing.** After the model reply lands, parse the reply for `[doc:… p.… ¶…]` tokens, resolve each to a `references[]` entry by looking up the document and the paragraph anchor (the `paragraphs[]` collection populated by Phase 1's anchor sweep), and produce `citation_markers` from token positions. Strip the bracketed tokens from the user-visible reply (or render them as chips client-side).

This is the same retrieval-and-cite shape briefings already implement in `briefings_service.py`. The work is to lift that shape into chat without duplicating the helper.

### 4. Frontend impact

- `pages/Chat.jsx` — render `assistant_message.references` as a row of chips at the foot of each assistant turn. Reuse `components/reading/CitationChip.jsx`. Click → `/app/documents/{doc_id}#{paragraph_id}` (the existing Reading-Viewer deep-link target).
- `components/chat/ModelAvatar.jsx` — no change.
- The chat audit pack export already lists every message; once `references` exists on the message, `audit/export.zip` carries it without code change.

### 5. Caveats and trade-offs

- **Scope.** Chat without a `context_id` (e.g. cross-context Solve-style sessions) cannot ground. The refactor must guard the retrieval step on `chat.context_id` being present and gracefully render no chips when absent. This is honest and matches the rest of the product.
- **Latency.** A BM25 retrieval over a context's docs costs single-digit milliseconds; the retrieval step adds at most one document read per turn. Not a real cost.
- **Validator.** Chat does not currently run the second-LLM countercheck. The honest fix in Phase 8 (already shipped — see `ValidatedBadge.jsx`) means the chip will not appear on chat responses until the second pass is wired. That is intentional and parallel work; the citations refactor does not block it.
- **Multi-turn drift.** When the user references an earlier turn ("explain the third point"), the retrieval window must include the previous assistant turn's referenced docs. Cheap solution: union the docs from the last two assistant turns' references into the BM25 corpus filter. Not strictly required for v1.

### 6. Recommended sequencing

1. Ship retrieval + persistence of `references[]` (no UI change).
2. Ship Chat.jsx chip render + click-through.
3. Flip default-on.
4. Backfill: run a one-off migration to compute `references[]` for the last 90 days of assistant turns where `chat.context_id` is set, so the audit pack benefits retroactively.

End of audit.
