# AKKI — Product Features Audit (factual, function-level)

> **Purpose.** Stub. We populate the long-form description later. This file
> is the function-level truth on what works **right now** in `/app` against
> the running database, so we don't write marketing ahead of the code.
>
> **Date of audit:** 2026-05-05 · **Branch:** `main` · **DB:** `akki_dev`
>   (mongodb://localhost:27017) · **Backend:** FastAPI on `:8001` · `/api/health` 200 ·
>   `/api/docs` 200 · `/api/openapi.json` 200.
> **Public preview:** `https://akki-executive.preview.emergentagent.com`.
> **Method.** Direct DB inspection + endpoint probes + grep over
> `backend/routers/`, `backend/services/`, `frontend/src/`.
> The previous long-form doc is preserved at
> `docs/PRODUCT_FEATURES_legacy_2026-05-04.md`.

## Status legend
- **WORKS** — wired end-to-end; observable rows in DB or successful endpoint round-trip.
- **PARTIAL** — wired but degraded by an environment flag, mock, or missing key.
- **STUB** — endpoint or page exists but logic is canned/placeholder.
- **MISSING** — no implementation; only a holding page or comment.

## Audit table

| Feature | Status | Evidence (file / endpoint / DB observation) |
|---|---|---|
| **Solva v3** (4-tile picker: clarity, strategy, hypothesis, perspectives) | **WORKS** | `frontend/src/components/solva/SolvaLanding.jsx` renders the 4 cards. `backend/routers/solva_v2.py` carries the full session API. `db.solva_v2_sessions` = **323 rows** (`completed: 82, active: 72, abandoned: 105, blocked_hard: 64`). `db.solva_clusters` seeded with 12 canonical clusters. `submodule` field present on session docs (`seek_clarity` / `develop_strategy` / `simulate_hypothesis` / `get_perspective`). PDF + DOCX export endpoints registered (`GET /api/solva/v2/sessions/{sid}/export.{pdf,docx}`). |
| **Synisense Shield** (3-layer regex → Presidio → LLM, pre-LLM redaction) | **WORKS** | `backend/services/synisense/{pipeline,encryption,presidio_engine,regex_recognisers,llm_fallback}.py`. `db.synisense_runs` = **2,671 rows** across surfaces `chat (60), ingest (511), briefing (123), deck (16), report (8), solva_v2.* (1,953)` — i.e. it *does* run pre-LLM. Sample row carries `input_sha256`, `spans[]` with `entity_type`/`source`/`confidence` (presidio, regex). `SYNISENSE_MASTER_KEY` set in `backend/.env`. `db.synisense_shield_maps` index has `expires_at` TTL. **Caveat:** the Solva surface tag is still spelt `solve_v2.*` (legacy nomenclature) — purely a string label, the engine is v2. |
| **Work Studio** (block editor + sensitivity Public..Restricted) | **WORKS** | `backend/routers/studio_blocks.py` (CRUD + `submit-review`/`approve`/`send`/`upload-image`). `backend/studio_sensitivity.py` deterministic 0–100 → PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED. `db.studio_blocks` = **23 rows**. `db.documents` carries `sensitivity_band`: `internal: 26, confidential: 2, none: 126` (band populated where the scorer ran). |
| **Cycle Manager** (cycles, signals, minutes, Boardpacks) | **WORKS** | `backend/routers/{cycle,cycle_config,signals_ask,prepare}.py`. `db.reports`, `db.submissions`, `db.checklists`, `db.signals`, `db.cycle_configs` all present and non-empty. Frontend `pages/Cycle.jsx` + `pages/CycleSettings.jsx`. Reports under review = 3. Public reportee reply at `GET/POST /api/respond/{token}` registered. |
| **Boardpack** (aggregation + AI commentary) | **WORKS** | M.3 migration applied — legacy `db.briefings` collection has **0 rows**, `db.boardpacks` has **88 rows**, sample row has `commentary` populated. Endpoints: `GET /api/contexts/{cid}/boardpacks[/{bpid}]`, `POST /boardpacks/{bpid}/regenerate-commentary`. Frontend tab labelled "Boardpack" via `AppShell.jsx` nav. **Caveat:** the "/api/contexts/{cid}/briefings/*" URL paths are **kept** as deliberate URL-stable backwards compat; the underlying collection is `boardpacks`. |
| **Document Journal** (workspace listing + on-demand AI commentary) | **WORKS** | Workspace listing at `frontend/src/pages/Workspace.jsx` lists docs; row click opens viewer; "Open original" now opens an in-app modal (M.2 fix). `GET /api/contexts/{cid}/document-journal` and `POST /api/contexts/{cid}/documents/{did}/journal-commentary` are registered. **Phase 1 backfill complete (2026-05-05):** `journal_commentary` now populated on **154 / 154** docs (100 % — bar was ≥ 90 %); 0 failures, 0 skips, 3,790 s wall-clock at concurrency=4. `db.synisense_runs` shows **154 fresh rows with `surface="journal_commentary"`** (the live path's pre-Phase-1 mis-label of `surface="briefing"` was fixed in the new `backend/document_commentary_service.py` so live + backfill share one code path; `briefing` surface count stayed flat at 123 — no double-write). Superadmin can re-trigger via `POST /api/admin/journal/backfill`. |
| **Sandbox v2** (5 industry contexts, guided pre-auth flow) | **WORKS** | `db.sandbox_v2_sessions` = **298 rows**, distributed across `WELCOME (279)`, `STEP_1_SOLVA (17)`, `CLOSING (2)` — i.e. real users have walked the flow. `backend/sandbox_v2_corpus.py` (1,443 ll.) carries the 5 verbatim contexts. `frontend/src/pages/SandboxV2.jsx` mounts at `/sandbox`. `backend/sandbox_v2_strategic.py` adds the 14-doc strategic pack (Phase L). **Caveat:** Step 2 (Pulse) is intentionally deferred — reducer reserves the state but FORWARD map skips to Step 3. |
| **Daily Review** (batched approval queue) | **WORKS** | `backend/routers/daily_review.py` registered: `GET /api/me/review-queue[/counts]`, `POST /items/{kind}/{iid}/{approve,reject,edit}`. Frontend `pages/DailyReview.jsx`. Live feeders today: `db.reports{status:"in_review"}` = **3**. `db.solva_cycle_handoff_queue{status:"pending"}` = **0**, `db.inbound_queue{status: pending/new/awaiting_review}` = **0** — queue is empty in the dev DB but the surface returns. |
| **Chat** (multi-model, SHA-256 hash-chained audit, streaming) | **WORKS** | `backend/routers/chat.py`: `GET /chat/models` lists 5 models (Claude Sonnet/Haiku 4.5, GPT-5.2, Gemini 2.5 Pro/Flash). `POST /chats/{cid}/messages/stream` registered. `db.chat_audit_log` = **169 rows** with explicit `prev_hash` + `row_hash` fields; first row carries `prev_hash="GENESIS-AKKI-CHAT-AUDIT-2026"` — i.e. hash chain is real. Daily 03:30 UTC retention sweep registered in `server.py`. |
| **Akki Pulse** (cross-context aggregator) | **MISSING (placeholder confirmed)** | `frontend/src/pages/PulsePlaceholder.jsx` is the only Pulse surface. No `pulse_signals` collection (`db` does not contain it). No aggregator endpoint registered. Nav slot wired to `/app/pulse`. Phase 14 dependency. |
| **Privacy Wall** (metadata-only projection guard) | **MISSING (confirmed)** | No `privacy_wall` collection. No metadata-only projection guard in cross-context reads. The existing `GET /api/me/home/stream` aggregator is membership-based, not Privacy-Wall-safe. Phase 14 dependency. |
| **Email — Resend (outbound)** | **PARTIAL — TEST MODE** | `backend/email_service.py` returns `{ok, id, mode}` envelope where `mode ∈ {sent, noop, test_mode_restricted, error}`. `RESEND_API_KEY` is set in `backend/.env` but the key is in Resend test mode → only the registered test recipient is delivered to; everyone else gets `test_mode_restricted` and the UI shows a "session is saved — bookmark the resume link" notice. Invitation email path in `routers/contexts.py` is still a `[invite-email-stub]` log (does NOT call `send_email` — Phase 16 dependency). |
| **Email — Postmark (inbound)** | **WORKS — LIVE** | `POSTMARK_SERVER_TOKEN` set in `backend/.env`. Webhook at `POST /api/inbound/postmark`. Per-account inbound tokens populated on **2 / 492** accounts; per-context tokens on **0** contexts (allocated lazily on first call to `GET /api/inbound/address`). |
| **Stripe billing** | **DISABLED (confirmed)** | `BILLING_ENABLED=false` in `.env`; `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` are commented out. Endpoints are registered (`/api/billing/{plans,me,checkout,status/{sid}}`, `/api/webhook/stripe`) but the boot guard in `server.py` would refuse to start with `BILLING_ENABLED=true` and no key. `db.stripe_events` carries the idempotency `expires_at` TTL index. `db.payment_transactions` empty. Phase 16 boundary. |
| **ClamAV virus scan** | **PARTIAL — BYPASSED IN DEV** | `backend/services/clamav_service.py` is the live integration; `documents_service.virus_scan_stub` was retired. In production the scanner is a **hard precondition** (uploads return 503 if down). In this dev pod, supervisord shows `clamd: STOPPED` and `backend/.env` carries `ALLOW_UNSAFE_UPLOADS=true` to bypass; a stderr nag fires every 60s. Phase G dependency. |

## What's NOT in this stub (deliberately)
- Long-form prose for each feature — this lives in
  `docs/PRODUCT_FEATURES_legacy_2026-05-04.md` and will be re-written
  *after* M.3 / M.2 / M.1 sign-off, against the same evidence as above.
- Marketing copy. None of the wording above is for prospect-facing use.
- The full 49-router OpenAPI dump — accessible at runtime via
  `/api/docs` and `/api/openapi.json`.

## Re-run this audit
The audit was generated by running:
1. `curl -s http://localhost:8001/api/health` and `/api/docs` and `/api/openapi.json`
2. Direct `motor.AsyncIOMotorClient("mongodb://localhost:27017")["akki_dev"]` queries
3. `grep` over `backend/routers/` and `frontend/src/pages/`

To regenerate, run the inspection script that produced the row counts:
```bash
python3 -c "$(cat <<'PY'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
async def main():
    db = AsyncIOMotorClient("mongodb://localhost:27017")["akki_dev"]
    for c in ["accounts","contexts","documents","solva_v2_sessions","sandbox_v2_sessions",
              "boardpacks","briefings","decks","studio_blocks","chat_audit_log",
              "synisense_runs","reports","stripe_events","payment_transactions"]:
        print(f"{c}: {await db[c].count_documents({})}")
asyncio.run(main())
PY
)"
```
