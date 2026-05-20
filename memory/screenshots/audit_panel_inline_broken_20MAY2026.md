---
source_url: https://customer-assets.emergentagent.com/job_feature-docs/artifacts/9dna18h7_Screenshot_20260520_221813_Chrome.jpg
original_filename: Screenshot_20260520_221813_Chrome.jpg
retrieved: 2026-05-20
persisted_by: e1_main (Chunk 9.5 dispatch pre-flight)
binary_path: /app/memory/screenshots/audit_panel_inline_broken_20MAY2026.jpg
binary_size_bytes: 772814
reproduction_context: Bramuel logged in, opened the chat titled "Bramuel and Udi are having dinner at Citi…", expanded the inline audit panel next to an AI message.
---

# Audit panel — inline view broken state (20 May 2026)

## Verbatim text observed in screenshot

The chat conversation includes the user message **"Bramuel and Udi are having dinner at Citi…"** which contains text referencing **account number 4565789845** — a financial identifier that the Synisense Shield is supposed to detect and redact.

Beneath the AI message, the inline audit panel — instead of rendering any audit/detection summary — shows the literal error string:

> **`AxiosError: Request failed with status code 404`**

No identifier list, no redaction count, no trust receipt, no model-call breakdown. The panel surface is broken end-to-end at the network boundary.

## Reproduction context

- **Account:** `bramuel@syni.ai`
- **Surface:** Akki Chat — inline audit panel attached to AI message bubbles
- **Trigger:** User clicks the audit-toggle on an AI message to expand the inline panel
- **Observed network response:** HTTP 404 from whichever endpoint the panel calls (frontend renders the AxiosError verbatim instead of a friendly empty-state)
- **Date observed:** 20 May 2026

## Why this matters for Chunk 9.5 Part 1

This screenshot is the primary evidence for **Symptom 1** of the Phase C audit regression. The 404 means either:
1. The endpoint route was renamed/removed by a subsequent refactor (most likely — Phase F.1 cleanup is a candidate)
2. The frontend axios call still points at a stale URL
3. The route exists but a path-param shape mismatch returns 404

Diagnostic must confirm which of the three before patching.
