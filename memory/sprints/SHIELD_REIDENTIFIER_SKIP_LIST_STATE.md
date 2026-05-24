# Shield reidentifier — PII-class skip list (Fork A) — DONE on preview, READY for redeploy

**2026-05-24** · Implemented per the user's Fork A brief.

## TL;DR

The Shield reidentifier now distinguishes between **contextual classes**
(rehydrate as before so the user reads back their own names/orgs) and
**hard-PII classes** (stay redacted in the user-visible reply with a
last-4 or fully-redacted placeholder). This ends the "the LLM
echoed my PAN" perception complaint permanently while keeping the
cryptographic audit trail unchanged.

**Status:** preview-green. Awaits user redeploy to push to prod.

## Acceptance gates

| Gate | Status |
|---|---|
| Reidentifier swaps hard-PII tokens for placeholders (last-4 or REDACTED) | ✅ |
| Reidentifier still rehydrates contextual tokens (PERSON/ORG/...) | ✅ |
| 27/27 new pytest cases in `test_reidentifier_skip_list.py` pass | ✅ |
| Cross-suite regression (78/78 across PAN, Shield, chat, route smoke) | ✅ |
| Live preview — Scenario A (Luhn-valid PAN) shows `[PAYMENT_CARD_••••7689]` | ✅ |
| Live preview — Scenario B (Luhn-invalid 16-digit) shows `[ACCOUNT_NUM_••••6785]` | ✅ |
| Live preview — Scenario C (SSN + API key) shows `[SSN_••••6789]` + `[API_KEY_REDACTED]` | ✅ |
| Contextual entities (Bramuel, KPMG) still rehydrate in live reply | ✅ |
| No raw PII (16-digit PAN, 9-digit SSN, 20-char AWS key) anywhere in reply | ✅ |
| Audit trail (de_id_summary, request_hash) unchanged | ✅ (single-file change, no audit-row touch) |
| Lint clean | ✅ ruff `All checks passed!` |

## Per-class strategy (locked in `reidentifier._VISIBLE_STRATEGY`)

| Class | Strategy | User-visible string | Rationale |
|-------|----------|--------------------|-----------|
| `CREDIT_CARD`   | `last4`    | `[PAYMENT_CARD_••••<last4>]` | Standard card-display convention; preserves recognisability |
| `ACCOUNT_NUM`   | `last4`    | `[ACCOUNT_NUM_••••<last4>]`  | Catches Luhn-invalid 13-19 digit runs and other account ids |
| `SSN`           | `last4`    | `[SSN_••••<last4>]`          | Common SSN display convention |
| `IBAN`          | `last4`    | `[IBAN_••••<last4>]`         | Last 4 of IBAN is the local check digit suffix |
| `PHONE_E164`    | `last4`    | `[PHONE_••••<last4>]`        | Recognisable without leaking the rest |
| `UK_NI_NUMBER`  | `redacted` | `[UK_NI_REDACTED]`           | NI is 9 chars total; last-4 is 30 possibilities — too leaky |
| `API_KEY`       | `redacted` | `[API_KEY_REDACTED]`         | Tokens leak structure / family; no portion exposed |
| `EMAIL`         | `redacted` | `[EMAIL_REDACTED]`           | Domain leak is itself sensitive (employer signal) |
| `IP`            | `redacted` | `[IP_REDACTED]`              | Network identifier; full redaction safest |
| Everything else | rehydrate  | original text                | PERSON, ORG, GPE, PRODUCT, NORP, FAC, EVENT, LAW, DATE_ISO, MONEY, URL |

## How it works (single-file change)

```python
# services/synisense/shield/reidentifier.py
_TOKEN_RE = re.compile(r"\[\[ENT_([A-Z0-9_]+)_(\d{3,})\]\]")  # captures TYPE

def _sub(m):
    tok = m.group(0)
    entity_type = m.group(1)
    original = token_map.get(tok)
    if original is None:
        return tok  # unknown — leave bare (caught by smoke tests)
    visible = _visible_placeholder(entity_type, original)
    if visible is not None:
        return visible   # hard PII → render placeholder
    return original      # contextual → rehydrate as before
```

No DeIdResult signature change. No `client.py` or `synisense_shield.py`
call-site change. The cryptographic `token_map` still holds the originals
so the audit row's `request_hash` / `response_hash` continue to cover
EXACTLY what the LLM saw (the redacted text).

## Files touched

| File | Lines | Change |
|------|-------|--------|
| `backend/services/synisense/shield/reidentifier.py` | rewrite (36 → 120 lines) | Add `_VISIBLE_STRATEGY` map, `_last_n_digits()`, `_visible_placeholder()`, update `reidentify()` to parse the token type and route through the strategy |
| `backend/tests/test_reidentifier_skip_list.py` | new (252 lines) | 27 tests covering: last4 placeholders, redacted placeholders, no partial leak, contextual rehydration regression, mixed message, unknown token, empty inputs, full-roundtrip on the 3 brief scenarios, audit-summary regression |

## Live preview verification (2026-05-24, against `https://akki-executive.preview.emergentagent.com`)

### Scenario A — Luhn-valid PAN
```
USER: "Bramuel left his card no 4356789800057689 in KPMG head office.
       Please acknowledge receipt."
LLM-> USER (Claude Sonnet 4.5):
  "I acknowledge receipt of your message stating that Bramuel left his card
   no [PAYMENT_CARD_••••7689] in KPMG head office."
  by_type: {ORG: 4, PRODUCT: 1, PERSON: 2, CREDIT_CARD: 1}
```
- `4356789800057689` absent ✅
- `[PAYMENT_CARD_••••7689]` present ✅
- `Bramuel`, `KPMG` rehydrated ✅

### Scenario B — Luhn-invalid 16-digit (the May 24 screenshot scenario)
```
USER: "Bramuel, Marion and Brian are meeting about card number
       4356789000056785 at KPMG. Please acknowledge."
LLM-> USER:
  "I acknowledge that Bramuel, Marion, and Brian are meeting about card
   number [ACCOUNT_NUM_••••6785] at KPMG."
  by_type: {ORG: 4, PRODUCT: 1, PERSON: 4, ACCOUNT_NUM: 1}
```
- `4356789000056785` absent ✅
- `[ACCOUNT_NUM_••••6785]` present ✅
- `Bramuel`, `Marion`, `Brian`, `KPMG` rehydrated ✅

### Scenario C — SSN + AWS API key
```
USER: "Johns SSN is 123-45-6789 and AWS key is AKIAIOSFODNN7EXAMPLE"
LLM-> USER:
  "I've received your message, but it appears to contain only opaque
   tokens (Johns SSN, [SSN_••••6789], AWS, [API_KEY_REDACTED]) ..."
  by_type: {PERSON: 1, GPE: 1, PRODUCT: 1, ORG: 2, SSN: 1, API_KEY: 1}
```
- `123-45-6789` absent ✅
- `AKIAIOSFODNN7EXAMPLE` absent ✅
- `[SSN_••••6789]` present ✅
- `[API_KEY_REDACTED]` present ✅

## What stays the same (unchanged surfaces)

- Audit-panel prose — still reads `"Synisense shielded ... 1 payment card
  number, 1 national identifier (US SSN), and 1 API key / credential
  token before any LLM saw your message"` (unchanged; the friendly
  labels in `chat_audit_panel.py:_ENTITY_LABEL` were already correct).
- `chat.synisense_audit_ids` array, `synisense_audit_log.de_id_summary`,
  trust-receipt signature — all untouched.
- AUTO vs Always shield branching — unchanged.
- LLM provider routing — unchanged.

## Next step

User redeploys to push to `https://akki.syni.ai`. The fix is preview-green;
no other action needed from the agent side.
