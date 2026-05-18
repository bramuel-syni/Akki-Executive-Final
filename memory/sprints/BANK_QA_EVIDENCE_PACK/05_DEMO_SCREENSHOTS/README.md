# 05 — Demo Screenshots

Four key surfaces captured live from the preview deployment at https://akki-executive.preview.emergentagent.com on 2026-05-18.

| # | File | What it shows |
|---|---|---|
| 1 | `01_admin_observability_activity.jpeg` | **Admin → Synisense Observability → Activity tab.** Aggregate Shield invokes across all consumers. KPI tiles: total invokes, consumer count, re-identification partial rate, guardrail blocks. Per-consumer breakdown table with success / refusal / unavailable rates + average exposure-reduction and dilution scores. Top 10 purposes. Solva refusal-reason distribution. |
| 2 | `02_admin_observability_billing.jpeg` | **Admin → Synisense Observability → Billing estimate tab.** Amber disclaimer ("Estimated only — figures are illustrative, derived from the code-controlled pricing table at `services/synisense/pricing.py`. Not invoiced."). KPI tiles: total calls, estimated total USD, consumer count, pricing entry count. Per-consumer USD estimate table. Top purposes by estimated cost. |
| 3 | `03_solva_phase_d_trust_verified.jpeg` | **Solva Phase D session — framing screen.** Prominently displays the "TRUST VERIFIED BY SYNISENSE — Every reasoning step is governed and auditable" CTA banner. Below the banner: framing prompt + textarea + Attach (paperclip) button + Privacy provenance expander. The Attach button opens the mid-session document-attach modal (next image). |
| 4 | `04_solva_mid_session_attach_modal.jpeg` | **Mid-Solva-session document attach modal.** Two tabs: "Upload new" (drop-zone + file picker, supports PDF/DOCX/PPTX/XLSX/CSV/TXT/PNG/JPG/HEIC up to 25MB) and "From Document Journal" (searchable list of existing context-scoped docs). After attach succeeds, inline confirmation strip appears and the document's extracted text is wired into the session's reasoning context (Layer 0 evidence anchor). |

The two surfaces not captured (chat audit panel + Monitor "Update goal" assessment) require an authenticated executive account with seeded objectives and chat history. Both are exercised by the live test suite (`test_phase_e_polish.py`, `test_phase_f_engine_signals.py`) and verified by render-smoke; their UI shells render cleanly on the bramuel test account but the assessment expander needs real objectives + a fresh Akki call to populate.

For a live walk-through of those two surfaces, run:

```bash
# Chat audit panel:
POST /api/auth/login → bramuel@syni.ai
POST /api/chats → new chat
POST /api/chats/{id}/messages → send any message
# Then GET /api/chats/{id}/messages and inspect the embedded audit_panel
# field on the latest assistant turn.

# Monitor "Update goal":
POST /api/contexts/{cid}/monitor/objective → seed an objective
POST /api/contexts/{cid}/monitor/objective/{oid}/update-status
# Returns the full assessment payload including audit_id, rationale,
# supporting_signal_ids, supporting_doc_ids.
```

Both API paths are documented in `06_API_CONTRACTS.md`.
