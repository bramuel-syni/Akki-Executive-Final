# Push Readiness — Onboarding Sprint Close

**Generated:** 2026-05-25 (immediately after J4 e1_tester 4/4 PASS).
**Audience:** the human operator who will trigger "Save to GitHub" from the Emergent chat input.
**Purpose:** give the operator a clean diff-ready view of everything that landed across the horizontal + onboarding sprints, so the GitHub push commit message and reviewer notes can be assembled without spelunking through the per-sprint logs.

This is documentation only — no code changes were made for this file. The push itself MUST be triggered by the operator via the "Save to Github" UI affordance (an agent can't push from inside the pod).

---

## 1. What's about to be pushed

Two consecutive sprints, both closed cleanly:

| Sprint | Chunks | Scope | Closure tag |
| --- | --- | --- | --- |
| Horizontal UI reshaping (T1–T5 + backlog-b + chunk-d skip-audit) | T1, T2, T2.3-fix, T3, T4, T5, backlog-b (b1/b2/b3 fixes), chunk-d | UI reshape against the four 24 May 2026 QA reports + 12 PO-ratified gaps G1–G12 + demo seeds + Trust Center methodology + skip-audit re-enables | `v-post-T5-horizontal-closed` + `v-post-backlog-b` + `v-post-d` |
| Onboarding vertical sprint (J1–J4) | J1, J2 (incl. two J2.3 fix-passes), J3, J4 | First-session onboarding stages 1–6 + 19 PO-ratified gaps G13–G31 | `v-post-j4` + `v-post-onboarding-sprint-closed` |

Both sprints honoured the same guardrail set throughout — zero modifications to `services/synisense/*`, `services/llm_router.py`, `services/clamav_service.py`, `routers/trust_center.py`, `services/trust_center.py`, `routers/admin_audit_invariant.py`.

---

## 2. Tag inventory (chronological)

All tags are local-only until the operator's GitHub push lands them on `origin`.

```
2026-05-25  v-pre-T1                          fbea67f   horizontal sprint open
2026-05-25  v-pre-T2                          a0f2f54
2026-05-25  v-pre-T3                          ff32d5c
2026-05-25  v-pre-T4                          b010ac2
2026-05-25  v-pre-T5                          d411485
2026-05-25  v-post-T5-horizontal-closed       dba8423   horizontal sprint close
2026-05-25  v-pre-backlog-b                   3378212   demo seeds + 3 production bug fixes
2026-05-25  v-post-backlog-b                  7b38d21
2026-05-25  v-pre-d                           43b8b61   Trust Center methodology + skip-audit
2026-05-25  v-post-d                          81f8c66
2026-05-25  v-pre-a                           e6ee36a   onboarding sprint open
2026-05-25  v-post-j1                         1e7b283
2026-05-25  v-post-j2                         43980f0
2026-05-25  v-post-j3                         d657926
2026-05-25  v-post-j4                         (NEW)     onboarding sprint close
2026-05-25  v-post-onboarding-sprint-closed   (NEW)     entire J1-J4 closed, spec v1.1
```

The two `(NEW)` tags get created immediately after this document lands (and before the operator triggers the push).

---

## 3. Commit count

| Range | Commits |
| --- | --- |
| Total commits on `HEAD` | **442** |
| Sprint scope (`v-pre-T1..HEAD`) | **20 user-prompted milestone commits** + auto-commits from the platform between them |
| Onboarding sprint only (`v-pre-a..HEAD`) | **10 user-prompted milestone commits** |

Diff totals across the full sprint scope (`v-pre-T1..HEAD`):

```
3165 files changed · 15853 insertions(+) · 365 deletions(-)
```

The file count is dominated by the demo-seed JSON fixtures and the cumulative test files (each chunk added 4-25 tests).

---

## 4. One-line summary per major chunk

Roughly the same flow as the orchestrator's chunk index, sorted by tag creation order:

### Horizontal sprint (T1–T5)

| Chunk | Summary | Verdict |
| --- | --- | --- |
| **T1** | Chat sticky + Context Switch + Generate Brief + "All documents" routing + Add to Cycle (G1) | 5/5 PASS |
| **T2** | Document Journal filter tabs + Pulse Resolved tab + Monitor drawer redesign + Strategic Goals filters (G11 + G12) | 4/4 PASS |
| **T2.3-fix** | False-green correction — Monitor drawer FileText crash + Update assessment routing | 2/2 PASS |
| **T3** | Add to Work Studio modal (G8) + Add to Cycle parity + Work Studio kind routing + Compile modal nested upload (G9) | 4/4 PASS |
| **T4** | W3 compiled doc toolbar + DOCX/PDF/PPTX (G6) + Refine failure (G7) + W5 committed + Enhance flow + W10 refine failure (G10) | 5/5 PASS |
| **T5** | Cycle Manager landing (C1) + Setup Wizard (C2 G4 + C3 G5 + C4) + Cycle Page Compile parity (C5 G6) + Draft Journal (C7) + Ready Journal (C8) | 4/4 PASS |

**Horizontal sprint cumulative: 22/22 surfaces verified, 12/12 gaps G1–G12 shipped.**

### Post-horizontal interludes

| Chunk | Summary | Verdict |
| --- | --- | --- |
| **backlog-b** | Demo seed packs (Board + Committee + Cycle compilation) + 3 production bug fixes exposed by the seeds — Work Studio titles, Cycle page G6 chips, Monitor drawer FileText crash | 3/3 fixes + seeds tested green |
| **b1/b2/b3-fix** | Companion fix-passes triggered by backlog-b test surface | All green |
| **chunk-d** | Trust Center session-deviation note + `TRUST_CENTER_METHODOLOGY.md` + Skip-Audit (500 skipped tests classified in `SKIP_LEDGER.md`; 10 guardrail-adjacent re-enabled) | doc-only + 10 guardrail tests now green |

### Onboarding sprint (J1–J4)

| Chunk | Summary | Verdict |
| --- | --- | --- |
| **J1** | Stages 1-2 — 3-question intake form + auth · Shield de-id on `top_of_mind` (G18) · b48ee23 onboarding-status cherry-pick (G19 + G20) | 4/4 PASS |
| **J2** | Stage 3 — 4-door layout (cycle · upload · solve · demo) · ALLOWED_DOORS pinned (G21) · demo-attach (G22) · cycle setup wizard prefill | 3/4 PASS first pass |
| **J2.3-fix-1** | Cycle-door behavior — false-green correction (missing query params + route guard) | 4/4 PASS |
| **J2.3-fix-2** | Frontend auth-refresh — stale AuthContext blocking navigate after door-take | 6/6 PASS |
| **J3** | Stages 4-5 — first-doc upload routing through ClamAV + Shield (G24 + G25 + G26) · Trust Center 3-stop intro tour (G27 + G28) | 4/4 PASS |
| **J4** | Stage 6 — first Akki Chat / Solva session · G30 starter prompt seeded from de-identified `intake.top_of_mind` · G29 Help tooltip verbatim copy · G31 DOM-unconditional refactor | 4/4 PASS |

**Onboarding sprint cumulative: 4/4 chunks PASS, 16/16 user-verified verdicts, 19/19 gaps G13–G31 shipped.**

---

## 5. Pytest at the close

```
1 failed · 1193 passed · 490 skipped · 86 warnings in 245.65s (4:05)
```

- The single failure is the pre-existing `test_real_requirements_file_is_clean` — parked in `POST_T5_BACKLOG.md`, predates this sprint pair, not blocking.
- The 490 skipped are classified in `/app/memory/sprints/SKIP_LEDGER.md` (chunk-d artifact). 84% are broken-masked tech debt that pre-dates this sprint; 10 were re-enabled during chunk-d.
- Net delta across both sprints: **+110 passing tests** vs the pre-`v-pre-T1` baseline. Zero regressions.

---

## 6. Suggested commit message for the operator's "Save to GitHub" push

```
Sprint close: horizontal UI reshape (T1-T5) + onboarding vertical (J1-J4)

T1-T5 horizontal sprint: 22/22 surfaces verified across five tiers against
the 24 May 2026 QA reports + 12 PO-ratified gaps G1-G12. Full closeout at
memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md.

J1-J4 onboarding sprint: 4/4 chunks PASS, 16 user-verified verdicts, 19/19
gaps G13-G31 shipped. Closeout §11 of the same file. Spec locked at
memory/AKKI_ONBOARDING_SPEC.md v1.1.

Interludes: backlog-b (demo seeds + 3 production bug fixes) and chunk-d
(Trust Center methodology + skip-audit). +110 passing tests, zero
regressions, zero guardrail file changes.

Tags created: v-pre-T1, v-pre-T2, v-pre-T3, v-pre-T4, v-pre-T5,
v-post-T5-horizontal-closed, v-pre-backlog-b, v-post-backlog-b, v-pre-d,
v-post-d, v-pre-a, v-post-j1, v-post-j2, v-post-j3, v-post-j4,
v-post-onboarding-sprint-closed.
```

---

## 7. Pre-push checklist (operator)

Before triggering "Save to GitHub":

- [ ] Read `memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` (full sprint summary, both sprints).
- [ ] Read `memory/sprints/A_LOG.md` (per-chunk onboarding implementation diary).
- [ ] Confirm tag inventory above matches `git tag -l | grep "^v-"` output.
- [ ] Run `cd /app/backend && pytest -q --no-header --tb=no` one final time and confirm `1193 passed · 1 failed (pre-existing)`.
- [ ] Trigger "Save to GitHub" from the Emergent chat input.

---

## 8. After the push lands

- Optional: re-fetch tags on the remote (`git fetch --tags origin`) and verify the 16 tags above are visible on the origin.
- Begin chunk (c) — Stripe "Billing — Coming Soon" UX (the agent has its own brief and a separate `v-pre-c` / `v-post-c` tag pair will be created at chunk boundaries).

---

**Status:** ready for the operator's GitHub push. Documentation only — no code changes for chunk (e).
