# H2.5 Follow-Up — Three-Failure Closeout

**Status:** READY FOR e1_tester RE-RUN · **Date:** 2026-05-24

After the H2.5 corrective sprint landed with 18/18 pytest GREEN, an
independent `e1_tester` pass against the live preview surfaced 3
failures pytest didn't cover. This document is the closeout for the
follow-up sprint that fixed all three.

---

## What was broken (independent tester evidence)

### Failure #1 — `synisense-metrics` still returned 0

```text
GET /api/chats/{id}/synisense-metrics → identifiers_redacted: 0
```

…even though `chat_audit_log` AND `synisense_audit_log` agreed at
least one identifier had been redacted on the same turn. Same class
of "lying audit" defect as the H2.5 sprint addressed for Shield,
just on a different surface.

**Root cause.** The streaming pre-pass at `chat.py:1708` called
`adapter.shield_payload_async(..., message_id=PHANTOM_uuid)` with
NO `account_id` and NO `chat_id`. That meant the `synisense_runs`
row landed with `account_id=None` and a message id nothing else
referenced. The metrics aggregation query
(`{account_id, surface IN [chat_*], ts >= chat.created_at}`) never
matched the row, so the topline read 0.

### Failure #2 — Sync and stream had different vocabularies

Same input `"My card is 4111111111111111…"`:

| Surface | Count | Vocabulary | `shielded_by` |
|---|---|---|---|
| Sync `/messages` | 5 | UPPERCASE `CREDIT_CARD` | `synisense-shield-v1` |
| Stream envelope | 1 | **lowercase `card`** | **`synisense-pipeline`** |
| Stream Shield audit | 2 | UPPERCASE `CREDIT_CARD` | `synisense-shield-v1` |

Three different counts for the same input, two different vocabularies.

**Root cause.** Stream path's pre-pass used `adapter.shield_payload_async`
→ `pipeline.run` (lowercase tokens like `[CARD_1]`, summary key
`card`, `shielded_by="synisense-pipeline"`). Stream's LLM-bound de-id
used `prepare_for_streaming` → `shield.deidentifier.deidentify`
(UPPERCASE tokens like `[[ENT_CREDIT_CARD_001]]`, summary key
`CREDIT_CARD`, `shielded_by="synisense-shield-v1"`). Two engines, two
vocabularies, by design — exactly the failure mode the H2.5 contract
named.

### Failure #3 — Fix #6 admin endpoint didn't exist

```
GET /api/admin/audit-invariant-violations → 404
```

The H2.5 brief required a post-shield Luhn canary that hard-fails
when `shielded_text` still contains a Luhn-valid PAN, plus an
`audit_invariant_violations` Mongo collection AND
`GET /api/admin/audit-invariant-violations` admin endpoint. The
canary + collection were built (chat.py:2494-2519); the admin
endpoint was never wired.

---

## What the fix does

### F#1 + F#2 — Canonical `ChatShieldOutcome` mint

New module **`services/synisense/shield/canonical.py`**. Exposes
`mint_chat_outcome()` which:

1. Runs **one** `deidentifier.deidentify(user_text)` pass (UPPERCASE
   `de_id_summary`, `shielded_by="synisense-shield-v1"`).
2. Persists ONE `synisense_runs` row keyed on the actual
   `(account_id, chat_id, message_id, surface="chat")` so
   `/synisense-metrics` and `/synisense-runs` aggregate over the
   same data as the chat envelope.
3. Returns a frozen `ChatShieldOutcome` whose `envelope()` matches
   the legacy `_syn_report()` contract — so the chat UI keeps
   rendering unchanged.

Both `chat.py` send paths (sync `/messages` and stream `/messages/stream`)
now mint this outcome upfront, BEFORE writing the chat_audit row or
the user_msg envelope, and BEFORE the LLM call. The chat_audit row,
the user_msg envelope, the synisense_runs row, AND
`/synisense-metrics` all derive from the same single source of truth.

The Shield audit row that `shield_invoke()` / `prepare_for_streaming.finalize()`
writes later is built from the LLM-bound full prompt (user text +
history + grounding), so its numeric count is a SUPERSET of the
per-turn count — but the boolean *"did Shield detect anything this
turn?"* agrees across all four surfaces.

### F#3 — Admin endpoint built

New module **`routers/admin_audit_invariant.py`** wired into
`server.py`. Two endpoints, both superadmin-gated:

* `GET /api/admin/audit-invariant-violations?hours=N&kind=…`
  Recent rows with totals and per-kind counts.
* `GET /api/admin/audit-invariant-violations/summary?hours=N`
  Lightweight rollup for the Admin Health tile.

---

## Pytest evidence (21/21 GREEN)

```
tests/test_h2_5_shield_uniformity.py::test_wire_three_way_agreement_metrics_audit_chat              PASSED
tests/test_h2_5_shield_uniformity.py::test_wire_chat_envelope_uses_uppercase_shield_v1_vocabulary   PASSED
tests/test_h2_5_shield_uniformity.py::test_wire_admin_audit_invariant_violations_endpoint_exists    PASSED
+ 18 prior H2.5 wire-level + unit tests still PASSED
```

Each new test has an independent-rerun `curl` recipe in its
docstring — paste-ready.

Broader regression: 201/202 GREEN across all H2.5-adjacent suites
(H2.5 + PAN + reidentifier + H1 + chat-phase-B + synisense engine /
shield / e2e / surface / integration / security / regex / solva-v2
invariant / no-direct-LLM / patch-26-chat / phase-C-protective /
phase-A-unification). The 1 skip is pre-existing.

---

## Live curl evidence (preview URL)

### F#1 fix — `/synisense-metrics` now agrees

```text
GET /api/chats/<chat>/synisense-metrics
{
    "identifiers_redacted": 1,
    "model_calls": 1,
    "storyline": "This conversation passed through one layer of redaction…",
    "pre_shield_v1": false
}
```

### F#2 fix — Envelope vocabulary

```text
shielding.identifiers_masked = 1
shielding.by_category = {"CREDIT_CARD": 1}        # UPPERCASE
shielding.shielded_by = "synisense-shield-v1"     # NOT synisense-pipeline
```

### F#3 fix — Admin endpoint live

```text
GET /api/admin/audit-invariant-violations
{
    "since": "2026-05-23T10:12:59.933196+00:00",
    "total": 7,
    "by_kind": {"shield_failure_at_entry": 7},
    "rows": [ ... ]
}
```

### Mongo-level 3-way agreement (PAN turn)

```text
chat_audit_log.payload:
    identifiers_detected=1, by_category={'CREDIT_CARD': 1},
    shielded_for_llm=True, channel=stream
synisense_runs:
    spans=['CREDIT_CARD'], surface=chat, version=synisense-shield-v1
synisense_audit_log:
    de_id_summary={'ORG': 3, 'PRODUCT': 1, 'PERSON': 1, 'CREDIT_CARD': 1}
    (full-prompt superset; boolean agrees)
/synisense-metrics:
    identifiers_redacted=1
```

---

## Diff stat

```
 backend/routers/chat.py                      | 173 +++++++++------
 backend/server.py                            |   2 +
 backend/tests/test_h2_5_shield_uniformity.py | 306 ++++++++++++++++++++++++++-
 backend/routers/admin_audit_invariant.py     | 132 +++++++++++++ (NEW)
 backend/services/synisense/shield/canonical.py | 182 +++++++++++++++ (NEW)
 5 files changed, 721 insertions(+), 74 deletions(-)
```

---

## Non-goals / what NOT to expect

* **Numeric agreement on full-prompt counts.** `synisense_audit_log`
  carries de_id_summary computed on `full_prompt` (user_text +
  history + grounding) so it's a superset of the per-turn count.
  Boolean agrees; numeric doesn't. This is documented behaviour.
* **No frontend changes.** The fix is purely backend — UI keeps
  rendering from the existing envelope shape.

---

## Re-run recipe for `e1_tester`

```bash
API=$REACT_APP_BACKEND_URL
TOKEN=$(curl -s -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
    -d '{"email":"bramuel@syni.ai","password":"Bramuel2026!"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
CTX=$(curl -s "$API/api/auth/me" -H "Authorization: Bearer $TOKEN" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['contexts'][0]['id'])")
CHAT=$(curl -s -X POST "$API/api/chats" -H "Authorization: Bearer $TOKEN" \
    -H "X-Active-Context: $CTX" -H "Content-Type: application/json" \
    -d '{"title":"H2.5 follow-up verify"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -N -X POST "$API/api/chats/$CHAT/messages/stream" \
    -H "Authorization: Bearer $TOKEN" -H "X-Active-Context: $CTX" \
    -H "Content-Type: application/json" \
    -d '{"content":"My card is 4111111111111111 please charge it.","shielding_policy":"always"}' \
    > /tmp/sse.txt
grep -c "4111111111111111" /tmp/sse.txt              # expect 0
grep -c '"shielded_by": "synisense-shield-v1"' /tmp/sse.txt  # expect ≥ 1
grep -c '"CREDIT_CARD"' /tmp/sse.txt                 # expect ≥ 1
curl -s "$API/api/chats/$CHAT/synisense-metrics" \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# expect identifiers_redacted ≥ 1 and model_calls ≥ 1

ADMIN_TOKEN=$(curl -s -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
    -d '{"email":"admin@akki.ai","password":"AkkiAdmin2026!"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s "$API/api/admin/audit-invariant-violations?hours=24" \
    -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
# expect 200 + documented shape (NOT 404)
```
