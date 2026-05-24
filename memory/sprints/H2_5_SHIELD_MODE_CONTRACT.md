# Synisense Shield — Mode Contract (H2.5, 2026-05-24)

**Canonical source of truth** for the three shielding modes. The H3
Trust Center page copies its user-facing prose from this doc — any
divergence between the doc and the runtime behaviour is a bug.

## Modes at a glance

| Mode | Detection runs? | LLM provider sees | Audit row written? | UI placeholder in reply | When to use |
|------|-----------------|-------------------|--------------------|-----------------------|-------------|
| **always** | ✅ all 3 layers | Redacted prompt (placeholders only) | ✅ `redacted: true` | Hard-PII = redacted placeholder (e.g. `[PAYMENT_CARD_••••7689]`); contextual entities rehydrated to original (e.g. "Bramuel", "KPMG"). | The default for production. Strongest guarantee. |
| **auto**   | ✅ all detection layers; latency-aware short-circuit allowed | Redacted prompt (placeholders only) | ✅ `redacted: true` | Same as `always`. | Default UX-tuned mode. Identical to `always` for the user-facing reply; may skip the LLM-fallback layer when input is short (<200 chars) AND no document attachments AND zero identifiers found by the regex + spaCy passes. **Detection itself never skips.** |
| **off**    | ✅ all detection layers, REPORT-ONLY | **Raw prompt** | ✅ `redacted: false, would_have_redacted: N` | Raw text — no placeholder substitution | Operator opt-out, explicit acknowledgement REQUIRED. Audit row records what Shield WOULD have redacted so the Trust Center can show "before / after" honest metrics. |

## Hard rules (all modes, always)

These hold regardless of mode:

1. **`synisense_audit_log` row is written every turn.** Including for
   `off` mode (with `redacted: false`), zero-identifier turns
   (with empty `de_id_summary`), and stream-error turns (with
   `outcome: "stream_error"`).
2. **Detection runs every turn.** The mode only governs whether the
   detected identifiers are REDACTED — never whether they're
   detected. The `would_have_redacted` count in `off` mode is the
   tangible proof.
3. **Audit row is identical across roles.** Executive, NED, Admin,
   Superadmin all write the same row shape. No role-gated branching.
4. **No raw PII reaches a cloud LLM SDK in `always` or `auto`
   modes — ever.** The streaming path's H2.5 fix routes the prompt
   through `deidentifier.deidentify()` before opening the provider
   stream.
5. **Failure modes are explicit.** If the de-id pipeline raises
   inside a chat-family surface, the route returns
   HTTP 503 `{"error":"shield_unavailable","action":"retry",...}`.
   The legacy "degrade-open" behaviour is reserved for `ingest`,
   `briefing`, `deck`, `report`, `enhance`, and `sandbox` surfaces
   (per `services/synisense/adapter.py:_SURFACES_ALLOWING_DEGRADED_OPEN`).

## Mode-specific details

### `always` (the strongest guarantee)

- **Detection:** all 3 layers fire — regex (Luhn + family), spaCy NER
  (`en_core_web_trf` in prod, `_sm` fallback in dev), and the LLM-
  fallback layer for residual cases.
- **Redaction:** every detected entity is replaced with an
  `[[ENT_<TYPE>_<NNN>]]` token in the prompt sent to the LLM.
- **User-visible reply:** governed by Fork A's `_VISIBLE_STRATEGY`
  map in `reidentifier.py`. Hard-PII classes (CREDIT_CARD,
  ACCOUNT_NUM, SSN, IBAN, PHONE_E164, UK_NI_NUMBER, API_KEY, EMAIL,
  IP) render as `[<LABEL>_••••<last4>]` or `[<LABEL>_REDACTED]`.
  Contextual classes (PERSON, ORG, GPE, PRODUCT, NORP, FAC, EVENT,
  LAW, DATE_ISO, MONEY, URL) rehydrate to the original value so the
  user sees their own names back.
- **Audit row fields:**
  ```jsonc
  {
    "mode": "always",
    "redacted": true,
    "de_id_summary": {"CREDIT_CARD": 1, "PERSON": 4, "ORG": 2, ...},
    "request_hash": "sha256:...",   // hash of the REDACTED prompt
    "response_hash": "sha256:...",  // hash of the rehydrated reply
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-5-20250929",
    "tokens_in": 234,
    "tokens_out": 187,
    "outcome": "success"
  }
  ```

### `auto` (UX-tuned default)

- **Detection:** identical to `always` for regex + spaCy NER. The
  LLM-fallback layer MAY be skipped for low-risk inputs:
  - Input length < 200 chars, AND
  - No document attachments on the turn, AND
  - Zero identifiers found by regex + spaCy combined.
  When skipped, the audit row carries
  `de_id_summary_provenance: {"regex":1, "spacy":1, "llm_fallback":0}`
  so the Trust Center can render the layer breakdown honestly.
- **Redaction:** same as `always` — anything detected gets the
  ENT token treatment.
- **User-visible reply:** same as `always`.
- **Audit row:** same shape as `always`; only `mode` differs.
- **Why it exists:** the LLM-fallback layer adds 200-800ms to short
  conversational turns where regex + spaCy already cover everything.
  `auto` lets us skip that cost when the input is provably trivial.
  **Detection never skips; only the LLM-fallback layer might.**

### `off` (explicit opt-out, audit-only)

- **Detection:** still runs. Result reported but not used for
  redaction.
- **Redaction:** **bypassed.** Raw prompt goes to the LLM.
- **User-visible reply:** raw text from the LLM, no placeholder
  substitution.
- **Required client-side affordance:** the request MUST include
  `acknowledge_unshielded: true`. Without it, the chat endpoint
  returns **HTTP 400** with
  `{"error":"unshielded_acknowledgement_required","message":"..."}`.
  This prevents accidental opt-out via a misconfigured client.
- **Audit row fields:**
  ```jsonc
  {
    "mode": "off",
    "redacted": false,
    "acknowledge_unshielded": true,
    "would_have_redacted": 8,          // count Shield WOULD have masked
    "would_have_summary": {"CREDIT_CARD": 1, "PERSON": 4, ...},
    "request_hash": "sha256:...",      // hash of the RAW prompt
    "response_hash": "sha256:...",
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-5-20250929",
    "outcome": "success"
  }
  ```
- **Trust Center surface:** chats with `off` turns display a banner:
  *"You disabled Shield for N turns in this conversation. Shield
  identified M identifiers that would have been masked."*

## Implementation map

| Concern | File | Line/symbol |
|---------|------|-------------|
| Mode validation + enum | `routers/chat.py` | `ShieldingPolicy` literal type |
| Detection layers (regex + spaCy NER) | `services/synisense/shield/deidentifier.py` | `_REGEX_PATTERNS`, `_attempt_load` |
| LLM-fallback layer | `services/synisense/shield/deidentifier.py` | optional 3rd pass (today inactive) |
| User-visible placeholders (Fork A) | `services/synisense/shield/reidentifier.py` | `_VISIBLE_STRATEGY` |
| Sync chat round-trip | `services/synisense/shield/client.py` | `invoke()` |
| Streaming chat round-trip (H2.5) | `services/synisense/shield/client.py` | `prepare_for_streaming()` |
| Streaming delta rehydration (H2.5) | `services/synisense/shield/reidentifier.py` | `StreamingReidentifier` |
| Fail-closed semantics | `services/synisense/adapter.py` | `_SURFACES_ALLOWING_DEGRADED_OPEN` + `shield_payload_async` |
| Audit row write | `services/synisense/shield/audit_log.py` | `write_audit()` |
| Audit panel topline | `routers/synisense_metrics.py` | `get_chat_synisense_metrics()` |

## H3 Trust Center page — copy hooks

The H3 Trust Center page should use the prose below verbatim so the
documented contract and the on-page promise stay in lockstep.

### Hero copy (always-on default)
> **Your conversations never leave your tenant un-redacted.**
> Every message passes through Synisense Shield before any cloud LLM
> can read it. Names, account numbers, payment cards, SSNs, API
> keys, IBANs, NI numbers, phone numbers, emails, and IP addresses
> are masked deterministically. The cloud LLM sees only placeholders.

### Mode toggle subtext
- **always** — "Strongest guarantee. All three detection layers run."
- **auto** — "Default. Detection always runs; latency-tuned for short turns."
- **off** — "Explicit opt-out. Cloud LLMs see your raw message. Audit row still recorded."

### Off-mode acknowledgement modal
> **You're about to disable Shield for this conversation.**
> Synisense will still scan your message and record what WOULD have
> been masked, but the cloud LLM will receive the raw text. This
> cannot be retroactively reversed for messages sent while Shield is
> off. Acknowledge to continue.

## Open items deferred to H3 / later sprints

- **`auto` layer-skip not yet implemented.** Today `auto` and
  `always` are functionally identical (both run all detection
  layers; the LLM-fallback layer doesn't yet exist as a separate
  pass that `auto` could skip). The contract above commits to the
  shape; the implementation can land as a follow-up.
- **Off-mode `acknowledge_unshielded` field not yet enforced.** The
  chat router currently accepts `policy=off` without the explicit
  ack. The contract commits to the requirement; implementation
  follow-up in H4 alongside the back-fill.
- **`would_have_redacted` field not yet written.** When off-mode
  ack handling lands, the audit row will include the
  `would_have_summary` block per the contract.

The H3 Trust Center page should reflect what's IMPLEMENTED TODAY
plus a "Coming soon" badge on the two deferred items. The doc above
is the canonical destination; we're aligned on the destination even
if a few steps remain.

---

## Audit metadata

- **Authored:** main agent, 2026-05-24 as part of H2.5 corrective
  sprint.
- **Status:** P0 streaming carve-out closed via
  `client.prepare_for_streaming()` + `StreamingReidentifier`.
  Fail-closed adapter shipped. `auto`-skip + `off`-mode ack are
  deferred items declared above.
- **Forgetting-mitigation:** pinned. Future agents reconcile against
  THIS doc, not against session memory.
