---
source_url: https://customer-assets.emergentagent.com/job_feature-docs/artifacts/j8nw9xgh_Screenshot_20260520_221759_Chrome.jpg
original_filename: Screenshot_20260520_221759_Chrome.jpg
retrieved: 2026-05-20
persisted_by: e1_main (Chunk 9.5 dispatch pre-flight)
binary_path: /app/memory/screenshots/audit_panel_trust_view_broken_20MAY2026.jpg
binary_size_bytes: 728012
reproduction_context: Same chat as the inline-broken screenshot; user opened the full Trust Panel surface.
---

# Audit panel — full Trust Panel view broken state (20 May 2026)

## Verbatim text observed in screenshot

### Topline header
> **"Nothing has needed redaction in this conversation yet — Synisense Shield is on standby."**

### Counter row
- **IDENTIFIERS REDACTED:** `0`
- **MODEL CALLS:** `0`
- **LAYERS WON:** `0 regex / 0 Presidio / 0 LLM-fallback`

### Audit trail rows
Two audit entries visible with a hash chain (HMAC-SHA256 receipts):

1. **`CHAT.CREATED`** — JSON payload is **missing the `at` (timestamp) field**. Other fields render but the produced JSON is incomplete relative to the expected schema.
2. **`MESSAGE.SENT`** — JSON payload **ends abruptly at `"char_len": 100,`** — the JSON is truncated mid-object. No closing brace, no trailing fields, no `at` timestamp.

## Reproduction context

- **Account:** `bramuel@syni.ai`
- **Surface:** Akki Chat — full Trust Panel slide-over
- **Chat content:** same chat as the inline-broken screenshot; user message contains **account number 4565789845**
- **Observed state:** Trust Panel topline says "on standby" despite the chat containing a financial identifier; counter row is all zeros
- **Date observed:** 20 May 2026

## Why this matters for Chunk 9.5 Part 1

This screenshot is the primary evidence for **Symptoms 2 + 3** of the Phase C audit regression.

**Symptom 2 — Zero metrics despite chat containing PII.** Two competing hypotheses:
- **H1 — reporting gap:** Shield IS detecting and redacting, but the metrics aren't propagating to the audit aggregation that the panel reads.
- **H2 — detection gap:** Shield is NOT detecting the account number as PII at all (NER regex/Presidio/LLM-fallback all return zero matches).

Diagnostic must inspect `chats.synisense_audit_ids` for the affected chat, look up each audit row in Mongo, and confirm whether detection arrays are empty (H2) or populated-but-unreported (H1).

**Symptom 3 — Audit-trail JSON payloads truncated.** Could be:
- **Producer-side:** backend builds incomplete JSON before signing/storing
- **Display-side:** frontend truncates the rendered output

Diagnostic must hit the audit-trail endpoint directly via curl and inspect the raw response body before patching.
