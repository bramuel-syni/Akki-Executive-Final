# Push Readiness — Full Session Close

**Generated:** 2026-05-25 (immediately after J4 e1_tester 4/4 PASS).
**Last updated:** 2026-05-25 (chunk (c) closed at 4/4 after (c.1)(c) surgical fix).
**Audience:** the human operator who will trigger "Save to GitHub" from the Emergent chat input.
**Purpose:** give the operator a clean diff-ready view of everything that landed across the horizontal + onboarding + Coming-Soon chunks, so the GitHub push commit message and reviewer notes can be assembled without spelunking through the per-sprint logs.

This is documentation only — no code changes were made for this file. The push itself MUST be triggered by the operator via the "Save to Github" UI affordance (an agent can't push from inside the pod).

---

## 1. What's about to be pushed

Two consecutive sprints + one Coming-Soon chunk, all closed cleanly:

| Sprint / chunk | Inner chunks | Scope | Closure tag |
| --- | --- | --- | --- |
| Horizontal UI reshaping | T1, T2 (incl. T2.3 fix-pass), T3, T4, T5 | UI reshape against the four 24 May 2026 QA reports + 12 PO-ratified gaps G1–G12 | `v-post-T5-horizontal-closed` |
| backlog-b + chunk-d (interludes) | backlog-b, b1/b2/b3 fix-passes, chunk-d | Demo seeds + 3 production bug fixes + Trust Center methodology + skip-audit re-enables | `v-post-backlog-b` + `v-post-d` |
| Onboarding vertical sprint | J1, J2 (incl. two J2.3 fix-passes), J3, J4 | First-session onboarding stages 1–6 + 19 PO-ratified gaps G13–G31 | `v-post-j4` + `v-post-onboarding-sprint-closed` |
| Stripe Coming-Soon chunk | chunk (c), chunk (c.1)(c) surgical fix | Replace §M4 Stripe checkout with honest Coming-Soon surface + `/notify-billing-launch` waitlist; zero-Stripe-SDK invariant pinned | `v-post-c` |

All sprints honoured the same guardrail set throughout — zero modifications to `services/synisense/*`, `services/llm_router.py`, `services/clamav_service.py`, `services/inbound_email.py`, `routers/trust_center.py`, `services/trust_center.py`, `routers/admin_audit_invariant.py`.

---

## 2. Tag inventory (chronological)

All tags are local-only until the operator's GitHub push lands them on `origin`.

```
2026-05-25  v-pre-T1                          horizontal sprint open
2026-05-25  v-pre-T2
2026-05-25  v-pre-T3
2026-05-25  v-pre-T4
2026-05-25  v-pre-T5
2026-05-25  v-post-T5-horizontal-closed       horizontal sprint close
2026-05-25  v-pre-backlog-b                   demo seeds + 3 production bug fixes
2026-05-25  v-post-backlog-b
2026-05-25  v-pre-d                           Trust Center methodology + skip-audit
2026-05-25  v-post-d
2026-05-25  v-pre-a                           onboarding sprint open
2026-05-25  v-post-j1
2026-05-25  v-post-j2
2026-05-25  v-post-j3
2026-05-25  v-post-j4
2026-05-25  v-pre-c                           Stripe Coming-Soon chunk open
2026-05-25  v-post-onboarding-sprint-closed   (annotated: "onboarding sprint J1-J4 closed, spec v1.1")
2026-05-25  v-post-c                          Stripe Coming-Soon chunk close (after c.1.c fix)
```

**18 tags total.**

---

## 3. Commit count

| Range | Commits |
| --- | --- |
| Total commits on `HEAD` | **444** |
| Sprint scope (`v-pre-T1..HEAD`) | **22 user-prompted milestone commits** + auto-commits from the platform between them |
| Onboarding sprint only (`v-pre-a..HEAD`) | **12 user-prompted milestone commits** |
| Coming-Soon chunk only (`v-pre-c..HEAD`) | **2 user-prompted milestone commits** (chunk (c) initial + (c.1)(c) surgical fix) |

Diff totals across the full sprint scope (`v-pre-T1..v-post-c`):

```
$ git diff --shortstat v-pre-T1..v-post-c
3165+ files changed · ~16000+ insertions · ~500 deletions
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
| **backlog-b** | Demo seed packs (Board + Committee + Cycle compilation) + 3 production bug fixes exposed by the seeds | 3/3 fixes + seeds tested green |
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

### Stripe Coming-Soon chunk (c)

| Chunk | Summary | Verdict |
| --- | --- | --- |
| **chunk (c)** | Stripe checkout REPLACED by Coming-Soon UX. `/api/billing/checkout` returns `{coming_soon: true}`; new `POST /api/notify-billing-launch` idempotent waitlist; `BillingTab.jsx` rewritten as Coming-Soon hero with notify-me CTA; `UpgradeModal.jsx` routes to `/app/settings/billing` | 3/4 PASS first pass |
| **chunk (c.1)(c) fix** | Zero-Stripe-SDK invariant — deleted dead `verify_and_parse_event` + `SignatureInvalid` in `services/stripe_webhook.py` (contained dead `import stripe`); added grep-based regression test `test_chunk_c_no_stripe_sdk_import.py` | 4/4 PASS re-verified |

**Coming-Soon chunk cumulative: 4/4 invariants verified.**

---

## 5. Pytest at the close

```
1 failed · 1208 passed · 490 skipped · 86 warnings in 263.70s (4:23)
```

- The single failure is the pre-existing `test_real_requirements_file_is_clean` — parked in `POST_T5_BACKLOG.md`, predates this sprint pair, not blocking.
- The 490 skipped are classified in `/app/memory/sprints/SKIP_LEDGER.md` (chunk-d artifact). 84% are broken-masked tech debt that pre-dates this sprint; 10 were re-enabled during chunk-d.
- Net delta across the entire session: **+125 passing tests** vs the pre-`v-pre-T1` baseline. Zero regressions.

---

## 6. Suggested commit message for the operator's "Save to GitHub" push

```
Session close: horizontal UI reshape (T1-T5) + onboarding vertical (J1-J4) +
Stripe Coming-Soon (c)

T1-T5 horizontal sprint: 22/22 surfaces verified across five tiers against
the 24 May 2026 QA reports + 12 PO-ratified gaps G1-G12. Full closeout at
memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md.

J1-J4 onboarding sprint: 4/4 chunks PASS, 16 user-verified verdicts, 19/19
gaps G13-G31 shipped. Closeout §11 of the same file. Spec locked at
memory/AKKI_ONBOARDING_SPEC.md v1.1.

Chunk (c) Stripe Coming-Soon: replaced §M4 Stripe checkout with an honest
Coming-Soon surface + idempotent /api/notify-billing-launch waitlist.
Zero-Stripe-SDK invariant pinned by source-grep regression test
(test_chunk_c_no_stripe_sdk_import.py). Closeout §12.

Interludes: backlog-b (demo seeds + 3 production bug fixes) and chunk-d
(Trust Center methodology + skip-audit + 10 guardrail re-enables).
+125 passing tests across the session, zero regressions, zero guardrail
file changes.

Tags: v-pre-T1, v-pre-T2, v-pre-T3, v-pre-T4, v-pre-T5,
v-post-T5-horizontal-closed, v-pre-backlog-b, v-post-backlog-b, v-pre-d,
v-post-d, v-pre-a, v-post-j1, v-post-j2, v-post-j3, v-post-j4, v-pre-c,
v-post-onboarding-sprint-closed, v-post-c.
```

---

## 7. Pre-push checklist (operator)

Before triggering "Save to GitHub":

- [ ] Read `memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` — full session summary (§11 onboarding + §12 full session close).
- [ ] Read `memory/sprints/A_LOG.md` — per-chunk onboarding + chunk-c implementation diary.
- [ ] Confirm tag inventory above matches `git tag -l | grep "^v-"` output (18 tags).
- [ ] Run `cd /app/backend && pytest -q --no-header --tb=no` one final time and confirm `1208 passed · 1 failed (pre-existing)`.
- [ ] Trigger "Save to GitHub" from the Emergent chat input.

---

## 8. After the push lands

- Optional: re-fetch tags on the remote (`git fetch --tags origin`) and verify the 18 tags above are visible on the origin.
- All implementation chunks are now complete. Begin the next sprint when ready — the P2/P3 backlog at `POST_T5_BACKLOG.md` is classified and ready to scope.

---

**Status:** ready for the operator's GitHub push. Documentation only — no code changes for chunk (e).

---

## Update — Production-hardening sprint added (2026-05-25)

After the chunk-(c) close above, the operator dispatched a 5-step production-hardening sprint. All 5 steps are now closed. The **6 new tags below are LOCAL-ONLY and require another "Save to GitHub" cycle** to land on origin.

### Hardening tags (added to the inventory in §2)

```
2026-05-25  v-pre-hardening                  hardening sprint open
2026-05-25  v-post-hardening-step-1          clamav prod-status endpoint
2026-05-25  v-post-hardening-step-2          false-green sweep + ESLint pin
2026-05-25  v-post-hardening-step-3          demo seeds auto-apply on boot
2026-05-25  v-post-hardening-step-4          coverage-loss test triage
2026-05-25  v-post-hardening-sprint-closed   hardening sprint close (annotated)
```

**24 total tags now in the local repo** (18 from session close + 6 from hardening). The previous "Save to GitHub" cycle (if completed for chunk-e) covered the 18; the next cycle needs to cover the 6 new hardening tags.

### Hardening chunk summary

| Step | Summary | Verdict |
| --- | --- | --- |
| **1** | `GET /api/healthz/clamav` — read-only daemon status probe (alive / unreachable / unknown). Caught the `clamd.ConnectionError` library-class mis-classification live in the preview env. | 3/3 PASS |
| **2** | Static-analysis sweep for 3 known false-green patterns (T2.3 DOM-unconditional · B3 undefined-symbol · J2.3 auth-staleness). 4 P0 sites fixed via surgical patches. ESLint `react/jsx-no-undef` + `no-undef` pinned in `craco.config.js` (lesson §5.10) — Phase C immediately caught 2 latent prod bugs the regex script missed. | 4/4 PASS |
| **3** | `@app.on_event("startup")` hook auto-applies the `DEMO_T5_BACKLOG` seed pack on pod boot. Idempotent (deterministic-id upserts), fail-soft (catch-all logs + pod keeps booting), `DISABLE_DEMO_SEED=1` env-flag for prod opt-out. | 4/4 PASS |
| **4** | 4 coverage-loss test files triaged. 3 rewritten as in-process companions (`test_iter{40,41,19}_*_in_process.py`, 19 new tests), 1 archived as obsolete (iter62, `/api/solve/*` namespace retired). All 4 unbacked tier verdicts (T1 D7 · T2.2 · T2.4 G11/G12 · T3.3 G8) now backed. | 4/4 PASS |
| **5** | `/app/memory/sprints/FRIENDLY_TESTER_ROLLOUT_CHECKLIST.md` — operator-readable, 159 lines, 7 sections. Closes the "never seen by real users" gap. | doc-only |

### Pytest at hardening close

```
1 failed · 1248 passed · 453 skipped · 89 warnings
```

- **+40 vs pre-hardening baseline** (1208 → 1248).
- **−37 vs pre-hardening skipped** (490 → 453). Coverage-loss families retired.
- The 1 failure is the pre-existing `test_real_requirements_file_is_clean` — parked P3 (`POST_T5_BACKLOG.md`).
- Zero regressions on the 1208 pre-hardening passing.

### Suggested commit message for the SECOND "Save to GitHub" push

```
Production-hardening sprint (5 steps) close

Step 1: GET /api/healthz/clamav — daemon-status probe.
Step 2: false-green pattern sweep — 4 surgical fixes + ESLint
        react/jsx-no-undef + no-undef pinned in craco config
        (lesson §5.10). Phase C immediately caught 2 latent prod
        bugs the regex audit missed.
Step 3: on_startup_demo_seed boot hook — idempotent + fail-soft
        + DISABLE_DEMO_SEED env-flag.
Step 4: coverage-loss test triage — 3 files rewritten as in-
        process companions (19 new tests), 1 archived as obsolete.
        All 4 unbacked tier verdicts now backed.
Step 5: friendly-tester rollout checklist (operator docs).

4 latent prod bugs caught + fixed before any tester invite:
clamd.ConnectionError mis-classification, Search lucide import,
WorkStudio navigate scope, 4 onboarding bootstrap-callback
staleness sites.

+40 passing tests (1208 → 1248), −37 skipped, 0 regressions,
0 guardrail file changes. New durable lesson banked (§5.10).

Tags: v-pre-hardening, v-post-hardening-step-{1,2,3,4},
v-post-hardening-sprint-closed.
```

### Updated pre-push checklist (operator)

Before triggering the SECOND "Save to GitHub":

- [ ] Read `memory/sprints/HARDENING_LOG.md` (full per-step diary).
- [ ] Read `memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` §13 (hardening sprint closeout).
- [ ] Confirm hardening tag inventory above matches `git tag -l | grep hardening` output.
- [ ] Run `cd /app/backend && pytest -q --no-header --tb=no` and confirm `1248 passed · 1 failed (pre-existing)`.
- [ ] Trigger "Save to GitHub" from the Emergent chat input.

### After the second push lands

- Optional: re-fetch tags on the remote and verify all 24 tags above are visible on the origin.
- Begin the friendly-tester rollout per `memory/sprints/FRIENDLY_TESTER_ROLLOUT_CHECKLIST.md`.

---

**Status (post-hardening):** ready for the operator's SECOND GitHub push + first friendly-tester batch invite. Pure documentation — no code changes for this update.
