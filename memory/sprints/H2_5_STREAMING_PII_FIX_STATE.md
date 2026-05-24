# H2.5 — Streaming PII fix + audit-integrity invariant — DONE (2026-05-24)

Corrective sprint covering the three P0s from H2 audit PLUS the
audit-integrity violation surfaced by independent `e1_tester`
verification (which trumped my prose-only H2 claims).

## TL;DR — four hard outputs the user demanded

| Output | Result |
|---|---|
| **#1 `git diff --stat`** | `chat.py +86 / -2` · `adapter.py +20 / -5` · `client.py +124 / 0` · `reidentifier.py +131 / 0` · `exceptions.py +27 NEW` · `test_h2_5_shield_uniformity.py +535 NEW` · `H2_5_SHIELD_MODE_CONTRACT.md +180 NEW` · `test_chat_phase_b_p0_fix.py +18 / -8` |
| **#2 Live curl streaming PAN** | `grep -c '4356789800057689' /tmp/sse_body.txt = 0` · `grep -c 'PAYMENT_CARD' /tmp/sse_body.txt = 2` · reply reads *"Bramuel's card ending [PAYMENT_CARD_••••7689] was left at KPMG headquarters"* |
| **#3 Mongo audit row** | `synisense_audit_log.de_id_summary = {ORG:4, PRODUCT:1, PERSON:2, CREDIT_CARD:1}` · `outcome="success"` · `chat_audit_log.identifiers_detected=3, shielded_for_llm=true, channel=stream` — **both rows agree the boolean** |
| **#4 `audit_invariant_violations`** | 0 during normal flow (asserted by `test_wire_audit_invariant_violations_collection_empty_for_normal_flow`) · 2 entries total, both from the strict-raise tests' simulated Presidio failures (working as designed) |

## Root cause (Fix #7) — what was actually happening

The streaming endpoint's PRE-H2.5 code at `chat.py:1685` was:

```python
text = body.content.strip()
shield_map: Dict[str, str] = {}   # ← NEVER POPULATED
shielded_text = text              # ← raw, no detection step
detected = _syn_report(shield_map)        # ← reports 0 from empty map
has_identifiers = detected["identifiers_masked"] > 0   # ← always False
```

The `_syn_shield()` call that the sync path equivalent makes at
`chat.py:1429` was simply **omitted** in the streaming entry. The
sync path goes through `shield_invoke(...)` which de-identifies AND
audits in one round-trip. The streaming entry initialised the
result variables as if a Shield call had already happened, then
never ran one. From there:

- `chat_audit_log.message.sent` row writes
  `identifiers_detected=0, shielded_for_llm=false, bypass_reason="no_identifiers"`
- Later in the same turn, if the message classifies as
  `strategic_deliverable` or as `thin-input`, the dedicated
  branches DO call `shield_invoke` and DO write `synisense_audit_log`
  rows with the real detection (`de_id_summary={CREDIT_CARD:1,
  PERSON:1, ORG:1}`)

→ The two audit families **contradict each other on the same turn**.
A bank-QA reviewer querying the audit chain would see "Shield
redacted 1 credit card" alongside "Shield didn't run on this turn".
Hash-chained tamper-evidence is meaningless if the contents of
the chain are inconsistent with each other.

## The four fixes — exact wire-level evidence

### Fix #1 — Streaming carve-out plugged (`chat.py:2390-2540`)

The default streaming branch was sending raw `full_prompt` directly
to Anthropic / Gemini / OpenAI via `stream_llm_direct(user_text=
full_prompt)`. Now wraps `full_prompt` through
`shield.client.prepare_for_streaming()` which:

1. De-identifies the prompt → `shielded_prompt` + `token_map`
2. Reserves an `audit_id` (minted up-front so the audit row is
   committed-by-intent before the LLM call begins)
3. Returns an `async finalize(response_text, provider, model,
   usage, outcome)` closure the caller invokes after the stream
   completes

The streaming consumer then wraps each delta through a
`StreamingReidentifier` (new class in `reidentifier.py`) that
handles tokens split across delta boundaries:

```python
async for chunk in stream_llm_direct(user_text=shielded_prompt, ...):
    if chunk.kind == "delta":
        visible_delta = stream_reid.feed(chunk.text)
        if visible_delta:
            yield "data: " + json.dumps({"type": "delta", "text": visible_delta})
tail = stream_reid.flush()
await shield_finalize(response_text="".join(visible_parts), ...)
```

**Wire-level proof (Output #2):** the SSE body shows the assistant
reply `"Bramuel's card ending [PAYMENT_CARD_••••7689]"`. Zero raw
PAN occurrences in the SSE stream. The cloud LLM SDK received
`[[ENT_CREDIT_CARD_001]]` (proven by the matching `de_id_summary`
in the audit row and by `test_wire_streaming_llm_receives_redacted_
prompt_not_raw_pan` which monkeypatches `stream_llm_direct` and
asserts on the captured `user_text` argument).

### Fix #5 — Audit-integrity invariant (`chat.py:1683-1736`)

The streaming entry now calls `_syn_shield(text, surface="chat",
message_id=...)` BEFORE writing the chat_audit row. The single
detection step feeds:

1. The `chat_audit_log.message.sent` row's
   `identifiers_detected`, `shielded_for_llm`, `by_category`,
   `bypass_reason` fields.
2. The downstream Shield audit row written by
   `prepare_for_streaming.finalize(...)`.

Both audit families derive from a **single detection call**. They
cannot disagree on the boolean question of "did detection find
anything?".

**Wire-level proof (Output #3):** for the same turn,
`chat_audit_log.identifiers_detected=3, shielded_for_llm=true,
channel=stream, by_category={person:1, card:1, org:1}` AND
`synisense_audit_log.de_id_summary={ORG:4, PRODUCT:1, PERSON:2,
CREDIT_CARD:1}`. The counts differ by class (legacy adapter uses
Presidio, modern uses spaCy NER) but both unambiguously say
"detection happened, at least 1 CREDIT_CARD was found". The
boolean invariant — `chat_audit says X iff shield_audit says X` —
is enforced by `test_wire_audit_integrity_invariant_holds`.

### Fix #6 — Defense-in-depth Luhn-PAN canary (`chat.py:2480-2510`)

After `prepare_for_streaming()` returns `shielded_prompt` and
BEFORE the cloud LLM SDK is called, a Luhn-validated PAN regex
scans `shielded_prompt`. Any match is impossible-by-design (Shield's
regex pass MUST have caught it). If a hit occurs the route:

- Inserts a row into `audit_invariant_violations` with
  `kind="luhn_pan_in_shielded_prompt"`
- Yields an SSE `error` event with `code="shield_invariant_violation"`
- **Refuses to forward to the LLM** and returns from the generator

This is the canary that would have caught today's bug at runtime
instead of relying on weeks-later screenshot complaints.

### Fix #3 — Strict-raise for chat-family (`adapter.py:60-100`)

`shield_payload_async` previously degraded-open on Presidio pipeline
exception — returned raw text + empty map. The new
`_SURFACES_ALLOWING_DEGRADED_OPEN` frozenset is the **explicit**
allow-list (`ingest`, `briefing`, `deck`, `report`, `enhance`,
`sandbox`). Any surface NOT in this list — including all chat-family
surfaces — now raises `ShieldFailure` (new exception in
`shield/exceptions.py`). The chat streaming route catches it,
inserts a row into `audit_invariant_violations` with
`kind="shield_failure_at_entry"`, and returns HTTP 503 with the
documented body `{"error":"shield_unavailable","action":"retry",
"message":"Synisense Shield is temporarily unavailable..."}`.

**Wire-level proof:** `test_wire_shield_unavailable_returns_503`
monkeypatches `pipeline.run`/`dryrun` to raise, POSTs the streaming
endpoint, asserts 503 + the documented body + that
`audit_invariant_violations` grew by one row.

### Fix #7 — Diagnosis pinned

Documented above and inside `chat.py:1683-1707` as an inline comment
so future agents reconcile against the code, not against session
memory. The H2.5 mode contract doc carries the same explanation
under "Open items deferred to H3 / later sprints".

## Test discipline upgrade (per the user's binding requirement)

Every H2.5 test that exercises the streaming surface includes:

1. **Wire-level assertion** — `mock.patch.object(services.llm_streaming,
   "stream_llm_direct", side_effect=_fake_stream)` captures the
   `user_text` argument the route would have passed to the cloud
   SDK. The test asserts the raw PAN is NOT in that bytes and that
   `[[ENT_CREDIT_CARD_…]]` IS.
2. **Audit-integrity invariant assertion** — for every test that
   submits PII, asserts `chat_audit.identifiers_detected > 0 IFF
   shield_audit.de_id_summary is non-empty`.
3. **Both channels parity** — the same `_login_and_chat` fixture is
   used by sync + streaming tests; both must produce non-empty
   `de_id_summary` for the same PAN input.
4. **Independent re-run recipe** — `test_h2_5_shield_uniformity.py`
   ends with a multi-line bash recipe (commented at file end) that
   `e1_tester` or any auditor can paste verbatim into a terminal to
   reproduce the four key assertions outside pytest. See the
   "Independent re-run recipe" block in the test file.

## Test inventory (18 tests, all green)

| Test | What it asserts |
|------|-----------------|
| `test_streaming_reidentifier_placeholder_split_two_deltas` | Token split across deltas → final assembly has full placeholder, no partial leak |
| `test_streaming_reidentifier_split_three_deltas` | Three-way split same |
| `test_streaming_reidentifier_overflow_no_pii_leak` | Buffer overflow releases buffer chars but NEVER raw PII (which lives in `token_map`, not in the stream) |
| `test_streaming_reidentifier_empty_token_map_pass_through` | No-op when token_map empty |
| `test_shield_payload_async_raises_for_chat_on_pipeline_failure` | chat-family fails closed → ShieldFailure |
| `test_shield_payload_async_degrades_open_for_enhance` | `enhance` surface still degrades open |
| `test_shield_payload_async_degrades_open_for_ingest` | `ingest` surface still degrades open |
| `test_shield_payload_async_raises_for_unknown_surface` | Unknown surface fails closed by default (strict allow-list) |
| `test_prepare_for_streaming_minted_audit_id_and_returns_redacted` | The new Shield-streaming primitive returns redacted + audit row written |
| `test_prepare_for_streaming_finalize_writes_stream_error_outcome` | Mid-stream error path still writes an append-only audit row |
| `test_classifier_routes_through_shield` | H2 §9 closed — `_llm_classify_fallback` uses `shield_invoke` |
| `test_h2_5_mode_contract_doc_exists_and_has_three_modes` | Canonical mode contract doc has always/auto/off + ack + would_have_redacted |
| `test_h1_indicator_still_emits_pre_v1_storyline` | H1 cross-sprint regression |
| `test_fork_a_skip_list_still_redacts_pan_in_user_visible_reply` | Fork A cross-sprint regression |
| `test_wire_streaming_llm_receives_redacted_prompt_not_raw_pan` | **WIRE-LEVEL:** captures `stream_llm_direct.user_text`; asserts raw PAN absent, placeholder present |
| `test_wire_audit_integrity_invariant_holds` | **WIRE-LEVEL:** chat_audit and shield_audit agree on boolean |
| `test_wire_audit_invariant_violations_collection_empty_for_normal_flow` | **WIRE-LEVEL:** invariant-violation log stays at 0 |
| `test_wire_shield_unavailable_returns_503` | **WIRE-LEVEL:** mocked pipeline failure → 503 + invariant-violation log row |

Cross-sprint regression: **942 passed / 500 skipped / 0 failed** in
the full backend suite. +18 net new tests over yesterday's H1
baseline (924), zero regressions across all earlier sprints
(Phases A→F, H1, Fork A).

## Files touched

| File | Action | Why |
|------|--------|-----|
| `routers/chat.py` | EDIT (+86/-2 lines) | Streaming entry now calls `_syn_shield()` (Fix #5/#7); default streaming branch routes through `prepare_for_streaming` + `StreamingReidentifier` (Fix #1); Luhn-PAN canary before `stream_llm_direct` (Fix #6); 503 + invariant log on `ShieldFailure` (Fix #3) |
| `services/synisense/adapter.py` | EDIT (+20/-5) | `_SURFACES_ALLOWING_DEGRADED_OPEN` allow-list + strict-raise (Fix #3) |
| `services/synisense/shield/client.py` | EDIT (+124/0) | New `prepare_for_streaming()` primitive (Fix #1) |
| `services/synisense/shield/reidentifier.py` | EDIT (+131/0 from H2.5 alone; +Fork A from yesterday) | New `StreamingReidentifier` class with per-delta boundary handling (Fix #1) |
| `services/synisense/shield/exceptions.py` | NEW (+27) | `ShieldFailure` exception |
| `tests/test_h2_5_shield_uniformity.py` | NEW (+535) | 18 tests including 4 wire-level + independent re-run recipe |
| `tests/test_chat_phase_b_p0_fix.py` | EDIT (+18/-8) | Updated Phase B P0 test to recognise that H2.5 reintroduces `_syn_shield(...)` legitimately as the audit-integrity primitive (was previously forbidden after Phase B; the H2.5 motivation is documented in the test docstring) |
| `memory/sprints/H2_5_SHIELD_MODE_CONTRACT.md` | NEW (+180) | Canonical mode contract — single source of truth for H3 Trust Center copy |

## Independent re-run recipe (for `e1_tester` / human auditors)

The complete recipe is committed at the bottom of
`/app/backend/tests/test_h2_5_shield_uniformity.py` as a multi-line
shell-script comment. The four-output verification above was
generated by running it. Paste-friendly summary:

```bash
API=https://akki-executive.preview.emergentagent.com
TOKEN=$(curl ...auth/login... | jq -r .access_token)
CHAT=$(curl ...create chat... | jq -r .id)

curl -N "$API/api/chats/$CHAT/messages/stream" \
  -H "Authorization: Bearer $TOKEN" -H "X-Active-Context: $CTX" \
  -H "Content-Type: application/json" \
  -d '{"content":"Bramuel left his card no 4356789800057689 in KPMG head office.","shielding_policy":"always"}' \
  | tee /tmp/sse_body.txt

# Four objective assertions:
grep -c "4356789800057689" /tmp/sse_body.txt     # ===> 0   (no raw PAN in SSE)
grep -c "PAYMENT_CARD" /tmp/sse_body.txt          # ===> ≥1 (placeholder visible)
# Mongo assertions via the helper script in the test file…
```

## What's deferred (NOT in this sprint)

The H2.5 mode contract doc declares two follow-up items NOT
implemented today but committed-on-paper:

1. **`auto`-mode layer-skip.** Today `auto` and `always` are
   functionally identical — both run all detection layers. The
   contract commits to `auto` skipping the LLM-fallback layer for
   short low-risk inputs; implementation can land in H4 alongside
   the back-fill.
2. **`acknowledge_unshielded` enforcement for `off` mode.** The
   contract requires `off` mode to demand an explicit ack flag and
   write `would_have_redacted` counts; implementation deferred to H4.

The H3 Trust Center page should mark these as "Coming soon" — the
contract above is the destination both today's implementation and
H4's follow-up are aligned on.

## Audit metadata

- Authored: main agent, 2026-05-24
- Status: P0s #1, #2, #3, #5, #6 closed with wire-level evidence; P1 #4 (classifier path) closed read-only via H2 §9 reconciliation
- Independent verification: `e1_tester` re-pass pending. The four
  output blocks above use the exact recipe `e1_tester` will run.
- Forgetting-mitigation: this doc is the canonical state. Future
  agents reconcile against THIS doc, not against session memory.
