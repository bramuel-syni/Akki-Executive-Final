# Phase C — audit panel regressions (20 May 2026)

Tracking doc for the Phase C deliverable regressions surfaced in the 20 May 2026 QA pass. Spec source: original Phase C closeout in `/app/memory/sprints/PHASE_C_CLOSEOUT.md`. Screenshot evidence persisted at `/app/memory/screenshots/audit_panel_*_20MAY2026.{jpg,md}`.

## Symptom matrix

| Symptom | Surface | Pre-fix observed | Root cause | Fix | Status |
|---|---|---|---|---|---|
| **Sx1** | Inline audit panel beneath an AI message | `AxiosError: Request failed with status code 404` rendered verbatim | Backend correctly returns 404 when `message_id` isn't in chat's `assistant_msgs` array (or audit row hasn't materialised yet). Frontend leaks raw axios error. | Frontend-only: `components/chat/AuditPanel.jsx` `catch` block detects `e?.response?.status === 404` and renders friendly copy ("Audit data isn’t available for this message yet — it usually appears within a few seconds of the response. Refresh once it has settled."). Non-404 errors keep the existing `{name}: {message[:200]}` format. | DONE (Chunk-9.5) |
| **Sx2** | Trust Panel header + counter row | "Nothing has needed redaction in this conversation yet — Synisense Shield is on standby." with `0 / 0 / 0` counters DESPITE the chat containing the financial identifier `account number 4565789845`. Audit-panel endpoint for the same message returned identifiers_shielded > 0, confirming Shield DID redact. | **`chats.created_at` is a STRING; `synisense_runs.ts` is a BSON DATETIME.** `$gte` between mismatched BSON types silently returns nothing. Only the chat-scoped endpoint had this shape — the context-windowed and per-message endpoints aren't affected. | Backend-only: `routers/synisense_metrics.py` adds `_coerce_to_datetime()` helper (accepts datetime / str / None → UTC-aware datetime) and applies it to `chat.created_at` before the `$gte` filter. | DONE (Chunk-9.5) |
| **Sx3** | Audit trail rows in the audit dialog | QA author reported "CHAT.CREATED payload missing `at` field" and "MESSAGE.SENT JSON ends abruptly at `\"char_len\": 100,`" | Misread. Backend produces complete payloads (verified via direct curl: every row has top-level `action, at, payload, entry_hash, prev_hash`; payloads have all expected keys). The `at` field is a TOP-LEVEL row field rendered ABOVE the payload `<pre>`, not inside the payload JSON. The `char_len: 100` "truncation" is just the alphabetical key order of the payload object — keys after it (`content_sha256, identifiers_detected, message_id, policy, shielded_for_llm`) are present and rendered. | None required. Documented in `CHUNK_9_5_STATE.md §6` to prevent re-investigation. | RESOLVED-NO-BUG |

## Sx2 reproduction (pre-fix)

```python
from motor.motor_asyncio import AsyncIOMotorClient
import os; from dotenv import load_dotenv; load_dotenv()
cli = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = cli[os.environ['DB_NAME']]

# A real chat from production (bramuel):
chat = await db.chats.find_one({'id': '85802bff-bfc7-4388-8f7e-218980ab6169'})
print(type(chat['created_at']))  # → <class 'str'>

# A real synisense_runs row for that chat:
run = await db.synisense_runs.find_one(
    {'account_id': chat['account_id'], 'surface': 'chat'},
)
print(type(run['ts']))  # → <class 'datetime.datetime'>

# Filter that the endpoint runs:
query = {
    'account_id': chat['account_id'],
    'surface': {'$in': ['chat', 'chat_classifier', 'chat_four_check', 'chat_evidence_list']},
    'ts': {'$gte': chat['created_at']},  # ← STRING vs DATETIME mismatch
}
print(await db.synisense_runs.count_documents(query))      # → 0  (the bug)

# Drop the ts filter:
del query['ts']
print(await db.synisense_runs.count_documents(query))      # → 1  (the data exists)
```

## Regression test

`backend/tests/test_qa_chunk_9_5.py::test_symptom2_ts_string_chat_created_at_still_aggregates_runs` — inserts a chat with `created_at` as STRING and a `synisense_runs` row with `ts` as DATETIME, then asserts the metrics endpoint returns non-zero counts and storyline doesn't include "on standby".

Companion test `test_symptom2_ts_datetime_chat_created_at_still_works` belt-and-braces the path where `created_at` is already a datetime (the eventual correct shape).

## Related schema-cleanup follow-up

`chats.created_at` should be stored as a BSON DATETIME consistently with `synisense_runs.ts` and most other timestamp columns. Migration shape:
1. Add a one-time `migrate_chats_created_at_to_datetime` admin endpoint that scans `chats` for `{ created_at: { $type: "string" } }` rows and rewrites them with `datetime.fromisoformat(...)`.
2. Switch the chat-creation code path to insert datetime directly.
3. Run the migration.
4. Once verified zero string-typed rows remain, remove `_coerce_to_datetime` (or keep as a defensive guard — net cost is negligible).

Queued for Track-4 (infra). Not blocking Chunk 10+.
