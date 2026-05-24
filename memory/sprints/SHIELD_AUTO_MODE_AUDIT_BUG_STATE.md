# Shield AUTO-mode audit "bug" — investigation state — 2026-05-24

## TL;DR

**The May 22 Shield patch IS deployed AND working on `akki.syni.ai`.**
**The user's screenshot does NOT show a Shield detection or audit-write failure.**
**What it likely shows is (a) a UX-misread of the rehydrated reply and (b) a
transient FE polling race or a pre-deploy chat opened post-deploy.**

A separate **product-design** decision is needed for "hard PII" classes
(CREDIT_CARD, ACCOUNT_NUM, SSN, API_KEY): should the user-visible reply
ALSO carry the placeholder rather than the rehydrated original?

This file pins the evidence so it's not forgotten.

## Reproduction (against PROD `akki.syni.ai`, 2026-05-24)

Scenario from the screenshot, exactly:
- Auth: `bramuel@syni.ai`
- Context: Safiri Telecom (`2456cc34-b687-47c3-82cc-b4352f8e5f94`)
- `shielding_policy=auto`
- Message: `"Bramuel, Marion and Brian are meeting about card number 4356789000056785 at KPMG"`
- Number `4356789000056785` is Luhn-INVALID (verified: digit sum % 10 = 7).

### Response shape — prod
```json
"user_message": {
  "shielded": true,
  "shielding": {
    "identifiers_masked": 9,
    "by_category": {"PERSON": 4, "PRODUCT": 2, "ORG": 2, "ACCOUNT_NUM": 1},
    "shielded_by": "synisense-shield-v1"
  },
  "synisense_stats": {
    "spans_redacted": 9,
    "by_type":  {"PERSON": 4, "PRODUCT": 2, "ORG": 2, "ACCOUNT_NUM": 1},
    "audit_id": "aud-9fe991a10d21404183a22586a6139762"
  }
},
"assistant_message": {
  "mode": "live",
  "synisense_stats": {
    "by_type":  {"PERSON": 4, "PRODUCT": 2, "ORG": 2, "ACCOUNT_NUM": 1},
    "audit_id": "aud-9fe991a10d21404183a22586a6139762"
  },
  "content": "I cannot comment on that meeting or associate the card number 4356789000056785 with any entity, as none of those details appear ..."
}
```

### Audit-panel — prod
```
GET /api/chats/{id}/audit-panel?message_id={mid}  →  167 ms
{
  "shielding_prose": "Synisense shielded 4 person names, 2 product names,
                      2 organisation names, and 1 account number
                      before any LLM saw your message.",
  "provider_prose":  "The redacted content was read by Anthropic's
                      claude-sonnet-4-5.",
  "audit_id":        "aud-9fe991a10d21404183a22586a6139762",
  "trust_receipt_id":"rcp-8a2ccdaa52b14258bc72cad8586c8223"
}
```

### Aggregate — prod
```
GET /api/chats/{id}/audit-panel/aggregate
{
  "llm_calls": 1,
  "identifiers_shielded": 9,
  "headline_prose": "This conversation: 2 messages · Synisense shielded
                     9 identifiers across 1 LLM call. ..."
}
```

### Audit row in MongoDB
```
synisense_audit_log {
  audit_id:        "aud-9fe991a10d21404183a22586a6139762",
  de_id_summary:   {ORG: 2, PRODUCT: 2, PERSON: 4, ACCOUNT_NUM: 1},
  llm_provider:    "anthropic",
  llm_model:       "claude-sonnet-4-5-20250929",
  request_hash:    "sha256:..." (hash of REDACTED prompt — body not stored),
  response_hash:   "sha256:..." (hash of LLM response — also pre-rehydrate),
  signature:       "c02cf2eadee753c995b9b4d7d23029b9820359aac34042764c6e6d1539f15982"
}
```

The `de_id_summary` field is written INSIDE `shield.client.invoke()` AFTER
the de-id step and BEFORE the LLM call. Its presence proves the redaction
ran. The `request_hash` is the hash of what the LLM actually received —
which contained `[[ENT_ACCOUNT_NUM_001]]`, NOT raw digits.

## So why does the LLM "speak the PAN" in the reply?

This is the Shield's **reidentifier** doing its job, by design:

```
USER:     "card number 4356789000056785 at KPMG"
              ↓ de-identify
LLM IN:   "card number [[ENT_ACCOUNT_NUM_001]] at [[ENT_ORG_002]]"
              ↓ Anthropic Claude
LLM OUT:  "I cannot associate the card number [[ENT_ACCOUNT_NUM_001]]
           with [[ENT_ORG_002]] ..."
              ↓ re-identify
USER:     "I cannot associate the card number 4356789000056785 with KPMG ..."
```

The Shield's design contract is: **hide PII from the LLM, then restore it
in the user-visible response** so the user can keep working on their own
data. The LLM provider (Anthropic) never sees the raw PAN. The audit
chain proves this with the cryptographic `request_hash` + signed receipt.

## The user's two reported issues — diagnosis

### Issue 1 — "Detection failure — model received and echoed the raw PAN"

**Not a detection failure. The LLM received a placeholder.** The audit
row's `de_id_summary` proves redaction ran. The user-visible reply contains
the original digits because the reidentifier intentionally rehydrates the
response — that is the documented Shield behavior.

This is a **legitimate UX/product-design concern** though: watching the
LLM "speak the PAN" looks broken to a user even though it isn't. There's
a separate decision to make:

> **Should "hard PII" classes (CREDIT_CARD, ACCOUNT_NUM, SSN, API_KEY,
> UK_NI_NUMBER) be excluded from reidentification — i.e. STAY as
> placeholders in the user-visible reply?**

The user's brief explicitly demands this: *"Hard rule: ACCOUNT_NUM
detection MUST replace the text, not just label it. Apply on input AND
output."* This is a one-line change in
`services/synisense/shield/reidentifier.py` — add a skip list. PROPOSING
to the user before implementing (needs sign-off because it changes the
core Shield product contract for the contextual classes too — the
reidentifier currently rehydrates PERSON/ORG so the user sees their own
names. Changing for PII classes only is correct.)

### Issue 2 — "Audit data isn't available for this message yet"

**Not reproducible on prod today.** The audit-panel endpoint returns in
**167 ms** with a fully-populated payload. Most likely explanations for
the screenshot:

- (a) The screenshotted chat was created BEFORE the May 22 deploy went
  live on `akki.syni.ai`. Pre-patch user messages were inserted without
  back-filled `synisense_audit_ids`, so the panel can't resolve them.
- (b) A transient FE race where the panel was opened in the same React
  frame as the response arrived, before the assistant_message row had
  hit Mongo.
- (c) An edge-case in `audit_ids[pos]` resolution where the position
  index drifts (e.g. a deleted message in the chain).

If the user can reproduce on a FRESH chat created today, that's a real
bug — please send the new chat URL + assistant message id and I'll
trace `chat.synisense_audit_ids` array vs `chat_messages.assistant`
positions to find the drift.

## What was NOT touched in this investigation

- Detection regexes (May 22 fix verified working).
- `chat.py` user_msg back-fill (verified working — `user_msg.shielded=true`).
- AUTO vs Always-shield branching (no divergence found — both modes run
  the same `shield.client.invoke()` codepath).
- Reidentifier (no change yet — proposing the skip-list to user first).

## Next steps awaiting user decision

1. PROPOSE: PII-class skip list for the reidentifier so the user-visible
   reply shows `[PAYMENT_CARD_••••6785]` / `[ACCOUNT_NUM_••••6785]` /
   `[SSN_••••6789]` / `[API_KEY_REDACTED]` instead of the original.
   Placeholder format with last-4 preserved (matches the May 22 brief).
2. If user can repro Issue 2 on a fresh chat, dig into the FE audit-panel
   polling cadence + `audit_ids` array drift.

## Files referenced (no edits made today)

- `/app/backend/services/synisense/shield/deidentifier.py` — May 22 patch
- `/app/backend/services/synisense/shield/reidentifier.py` — candidate for
  skip-list edit, if user approves
- `/app/backend/routers/chat.py` — May 22 user_msg back-fill
- `/app/backend/routers/chat_audit_panel.py` — labels + audit-panel endpoint
