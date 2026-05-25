# T5 Implementation Log

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (Ratified 24 May 2026).
Scope: T5 = "Cycle Manager redesign" — 8 surfaces:
1. C1 — Cycle Manager landing
2. C2 — Setup Wizard Step 1 (G4 ratified)
3. C3 — Setup Wizard Step 2 (G5 ratified)
4. C4 — Setup Wizard Step 3 + submit
5. C5 — Cycle Page (active view) + Compile downloads (G6 parity)
6. C6 — Draft Journal
7. C7 — Ready Journal
8. C8 — Completed cycles

**Hard rules:**
- All LLM calls go through `llm_router.invoke()` + `deidentifier.deidentify()`.
- No guardrail file changes.
- DOM-unconditional rule for every spec-required section.
- No J1–J4 onboarding work pulled forward.
- Verbatim spec copy on every toast, label, and button.

Scope-out → `/app/memory/sprints/POST_T5_BACKLOG.md`.

---

## Pre-tier hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-T5` → commit `d411485df7be0b457e74de0912fe10b8e75a066b` | 2026-05-25T07:34:00Z |
| Mongo dump | `/app/backup/pre_T5_20260525T073436Z/akki_dev/` (237 bson + metadata files, 63 MB) | 2026-05-25T07:34:36Z |

Note: tag local-only. `git push origin v-pre-T5` requires the user's "Save to Github" feature.

---

## Disk re-verification + implementation (per item)

(Populated below as each item is verified or implemented.)
