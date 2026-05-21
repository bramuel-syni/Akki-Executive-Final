# READ_FIRST — Continuity entry-point

**Updated:** 2026-05-21 (autonomous overnight) · **Maintainer:** whichever agent last patched the system.

## Status (snapshot)

- Synisense rewrite **A → F.1 closed**.
- **78 chunk-pytest passing** (across chunks 9.5/10/11/12/13/14/15/16 + CI guard) · 0 failed.
  Full-suite baseline 743+ remains green; per-chunk regression run 78/78.
- **CI guard green** (`test_no_direct_llm_calls_outside_shield`).
- **Render-smoke green** — 11/11 routes + steps 4-18 hard-asserted/soft-skipped per scope.
- **QA 16-May progress:** Chunks 7 (6 P0s) · 8 (8 P1s) · 9 (5 P1/P2s) · 10 (1 P1 + 6 P2s) · 11 (3 P1 + 2 P2s) · 12 (1 P1 deep rewrite) · 15 (4 P2s) · 16 (2 P1 + 2 P2s, Work Studio Document Cards cluster) **DONE**. Remaining: ~8 P1 (overlay rewrite cluster + others) · ~0 P2 (all-closed barring deferrals) · 2 P3 · 2 CLR (PO).
- **Solva 20-May progress:** Chunks 9.5 (SV-01/02/03 + Phase C audit regression) · 13 (SV-04) · 14 (SV-05/06/07/08 PARTIAL — SV-07 overflow-y queued as C17-004) **DONE**. Solva QA Brief fully addressed; SV-07 cosmetic CSS gap in C17 cleanup.
- **Autonomous overnight sprint ACTIVE** — see `/app/memory/AUTONOMOUS_SPRINT_LOG.md`; Chunks 9.5 + 10 + 11 + 12 (PARTIAL) + 13 + 14 (PARTIAL) + 15 + 16 closed.
- **C17 cleanup queue** (`/app/memory/sprints/CHUNK_17_CLEANUP_QUEUE.md`): C17-001 EditGoalRow · C17-002 seed Exec for QA-049 · C17-003 cross-context Solva aggregate (optional) · C17-004 SV-07 overflow-y CSS fix.
- **PO routings queued (non-blocking):** `/app/memory/sprints/AWAITING_PO/CHUNK_11_QA_050_dual_role_interpretation.md`
- **Deploy verdict 🟢 READY** with **4 platform-side 🟡 confirmations** (see table below). No 🔴 blockers.

## Where to read next (priority order)

| # | File | Why open it |
|--:|------|-------------|
| 0 | `/app/memory/FORGETTING_MITIGATION.md` | **Read BEFORE acting.** Anti-ghost-ID + auto-compaction recovery protocol. |
| 0.5 | `/app/memory/qa_reports/QA_BACKLOG.md` | Master QA backlog — single source of truth for 16-May findings (51 + 2 CLR). |
| 1 | `/app/memory/REWRITE_DEPLOY_READY.md` | Ship / no-ship verdict (green / yellow / red list) |
| 2 | `/app/memory/sprints/POST_REWRITE_RAMP.md` | What to build next — Track 0 (platform confirms) → Track 1 (Chunk 7 QA resume) |
| 3 | `/app/memory/REWRITE_SPRINT_STATE.md` | Canonical sprint state — phase-status table + locked decisions |
| 4 | `/app/memory/SYSTEM_STATE.md` | Append-only patch ledger (§4 = newest-at-top closeout log) |
| 5 | `/app/memory/sprints/PROD_DEPLOY_CHECKLIST.md` | Deploy-day runbook — env vars, system packages, smoke-test path |
| 6 | `/app/memory/sprints/BANK_QA_EVIDENCE_PACK/README.md` | Bank-QA evidence index — 7 sections, sample PDF, standalone HMAC verifier |
| 7 | `/app/memory/sprints/PHASE_F1_CLOSEOUT.md` | Most recent phase closeout (Phase F.1 + cleanup verification) |
| 8 | `/app/backend/scripts/seed_chunks.py` | **Chunk seed script** (renamed from `seed_chunk8_overlay.py` 2026-05-18). Idempotent. Currently seeds Chunk 8 (overlay enrichment + Draft committee_pack) + Chunk 9 (cycle/agenda/team for Add-a-Contribution smoke). Re-run safe. |

## Hard rules for next agent

- **Never invent IDs.** If a brief references a finding-ID and `grep -r '<ID>' /app/memory /app/backend /app/frontend` returns zero hits, STOP and ask. Never re-ask a blocker question if the user has uploaded the artefact since — resume from disk. See `FORGETTING_MITIGATION.md`.
- **DO NOT re-litigate the Synisense Shield gateway or the Solva 5-layer pipeline.** Phases A → F.1 are CLOSED. Architectural invariants are in force.
- **DO NOT add direct LLM SDK calls** (`import anthropic` / `from openai import` / `import google.generativeai`). All LLM traffic MUST route through `services.synisense.shield.client.invoke()`. The CI guard `tests/test_no_direct_llm_calls_outside_shield.py` fails the build if violated.
- **DO NOT use `mcp_screenshot_tool` for verification** — it times out on the auth path in this pod. Use `pytest` + `yarn render-smoke` instead; full-page screenshots only when the user explicitly asks.
- **APPEND to `SYSTEM_STATE.md` § 4 after every patch.** Newest-at-top. Closeout entry must reference its sprint doc.
- **Backend test floor: 662 passing.** Any drop is a regression. Skipped counts may shift but the passing count must not regress.
- **Frontend lint clean on touched files.** `yarn lint` on the changed paths.
- **One closeout doc per sprint dispatch** under `/app/memory/sprints/`.
- **Strict scope discipline.** If the user dispatched a tightly-scoped task, do NOT pull forward queued items even if they look related — list them and ask.

## Platform-side carry-overs (4 yellow items — NOT code-side; do NOT attempt to fix in code)

| Item | Why it matters | Owner | Graceful fallback in place? |
|------|----------------|-------|------------------------------|
| `tesseract-ocr` + `tesseract-ocr-eng` baked into the production Docker image | Preview pod `apt-get install` does NOT survive pod restarts — image must include it. OCR returns `status=failed` with a clean error string if absent. | ✅ **RESOLVED (2026-05-18)** — `Dockerfile.backend` runtime stage now installs `tesseract-ocr` + `tesseract-ocr-eng` alongside the other runtime apt deps. Effective on next build/deploy. | ✅ Yes — image uploads return graceful "no extractable text" hint, no 500 |
| Postmark inbound webhook URL pointed at `https://akki.syni.ai/api/inbound/postmark` | Code wired and verified; whether the Postmark dashboard actually POSTs to that URL is a deployment-config question. | User (Postmark dashboard) | ✅ Yes — webhook returns 401 to unauth, no crash; inbound email simply doesn't trigger |
| `SYNISENSE_MASTER_SECRET` set to a high-entropy random string in prod (NOT the dev fallback) | Trust receipts signed with the fallback are NOT verifiable by Bank QA; the standalone verification script returns FAIL. | User (Emergent Platform secrets) | 🟡 Partial — app boots and runs, but BANK-QA-VISIBLE warning every 60s + signatures are non-verifiable |
| `CLAMAV_HOST` / `CLAMAV_PORT` reachable from prod backend pod | Required by every document-upload path. | User / platform | ❌ No — document upload returns 503 ClamAVUnreachable. **Hard fail by design** (refuse to store unscanned files) |

## Architectural invariants (do not violate)

1. **No direct LLM calls outside `synisense.shield.llm_router`** — CI-enforced.
2. **Strict `tenant_id == account_id` binding** on every Shield surface. Admin overrides MUST explicitly check `is_superadmin`.
3. **Phase D is the only Solva engine.** Legacy `solva_v2` is read-only.
4. **Engine signals are deterministic** (no LLM). Every signal carries `derivation_source`.
5. **Pricing table code-controlled, NOT API-editable** (same governance as `ALLOWED_PURPOSES`).
6. **Trust receipts HMAC-SHA256** with per-tenant HKDF-derived keys.

## Deferred

- **Holistic product features & functionality review document** — deferred to end-of-work per user instruction 2026-05-18.
