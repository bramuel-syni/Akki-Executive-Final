# READ FIRST — Project status (2026-05-24, evening)

**Live on prod (https://akki.syni.ai):** H1 + H2.5 + H3 + H4 all shipped and
independently verified.

## What's live on prod
- **H1** — UI polish (tab title, pre-Shield-v1.x indicator, Trust Center footer copy)
- **H2.5** — Shield uniformity (canonical mint, vocabulary parity, admin invariant
  endpoint, envelope `audit_id` resolves, parametrized fail-closed, boot-time
  `warmup_or_warn`, `/api/healthz/shield`)
- **H3** — Trust Center v1 (`/app/trust-center` page, session/turn/plaintext/
  activity endpoints, 4-row evidence drill-down, standards-aligned footer,
  view-time redaction re-derivation)
- **H4** — Shield back-fill engine (admin endpoints, idempotent runner,
  separate `backfill_chain_v1`, Trust Center `backfilled` state + per-turn
  badges) — **code shipped, JOB not yet triggered on prod**

## Independent prod verification (3/4 PASS via `e1_tester`)
- `GET https://akki.syni.ai/api/healthz/shield` → 200, `ready:true`,
  `model_version:3.8.0`, warmup 29.3 s (cold-start tax noted in
  `H3_PROD_TRANSIENT_DIAGNOSIS.md`, P3 classification)
- `https://akki.syni.ai/app/trust-center` page renders, all 5 standards
  markers present
- End-to-end PAN redaction on prod streaming chat: audit
  `aud-78980b5ff03d4ec39d8f1098177d1403`, `by_category`
  `{PERSON:1, CREDIT_CARD:1, ORG:1}`, raw PAN absent from stream
- `GET /api/trust-center/session/{chat}` returns the documented shape
  (currently `pre_shield_v1` because the back-fill JOB hasn't run on prod yet)

## Open items (waiting on user)
1. **Onboarding scope decision** — agent sent the user a recommended journey
   (Stages 0–6, phased I1–I4, ~10–11 h dev). User is reviewing. Do NOT
   pre-build any I1/I2/I3/I4 work until the user replies with scope.
2. **Back-fill A/B**:
   - **(A)** User triggers `POST https://akki.syni.ai/api/admin/shield/backfill`
     via curl (recommended for explicit batch-size/sleep control).
   - **(B)** Agent triggers via `deployment_agent`.
3. **Cosmetic**: `/trust-center` → `/app/trust-center` redirect (the marketing
   site doesn't currently catch the bare path).

## Discipline rules to honour on next dispatch
- File-wins on prod vs session memory (this file IS the canonical state until
  the user dispatches something new).
- DO NOT run any more pre-deploy readiness checks — the bundle is already on prod.
- DO NOT touch code until the user dispatches a tight brief with scope.
- DO NOT trigger back-fill on prod without user authorization.

## Inventory cross-refs (read-only, already on disk)
- `/app/memory/PRD.md` — current product state
- `/app/memory/sprints/H2_5_FINAL_CLOSEOUT.md`
- `/app/memory/sprints/H3_PROD_TRANSIENT_DIAGNOSIS.md`
- `/app/memory/sprints/ONBOARDING_INVENTORY.md` — what exists today (Sandbox v2,
  First Session, role declaration, sandbox tutorial pattern unreused for real
  contexts)

**Agent state: idle until user dispatches.**
