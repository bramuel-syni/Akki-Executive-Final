# AKKI Sandbox — Roadmap

> Prioritised backlog of remaining product work.
> See `/app/memory/SYSTEM_STATE.md` §7 for tech debt.

## P0 — Blocking deployment
1. **Deployment blockers (5)** — original audit items, not yet triaged.

## P1 — Next sprint candidates
1. **Streaming UX retrofit** — convert Solva / Cycle compilation / Work
   Studio Enhance endpoints to SSE streams emitting `phase` events; then
   adopt `StreamingShell` on those surfaces. Motion architecture is
   already shipped; only the wiring remains.
2. **Objectives & Projects — ExCo-member chips + KPI chips** —
   the Monitor v2 brief called for a second filter row above the R/A/G
   tabs. Implemented the R/A/G tabs; the ExCo/KPI chips are a follow-up.
3. **Real calendar integration on Home 1** — replace the empty-state
   calendar peek with real cycle + compilation cadence aggregation.
4. **7-insight cards — wire missing counts** — `cycles_closing_this_week`
   requires `expected_close_at` on cycle docs; `open_questions` requires
   the `cycle_questions.assignee_account_id` field. Both return 0
   gracefully today; wiring the fields lights up the cards.

## P2 — Polish and productisation
1. **Real news integration** for Home 1 — replace `mock_news.json`.
2. **Agent Cycle — real AI engine** — wizard Step 3 preview is
   deterministic; upgrading to an LLM-generated briefing is a future
   product decision.
3. **Real template library** for Compilation Wizard Step 1 — currently
   a single "Standard" template per artefact type.
4. **Unskip legacy test suites** — roughly 65 files quarantined in
   Patch 8; reintroduce them one at a time as their fixtures / schema
   are modernised.
5. **Marketing JS bundle code-split** — deferred.
6. **Pydantic v2 migration** — `.dict()` → `.model_dump()` sweep on
   new routers.
7. **Legacy Home components (`HomeExecutive/Ned/Dual`)** — delete
   after a full visual-parity audit against Home 2.

## P3 — 3rd-party integrations (PLANNED)
- Stripe
- Azure stack
- ClamAV
