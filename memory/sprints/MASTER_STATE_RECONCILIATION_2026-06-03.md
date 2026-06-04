# MASTER_STATE.md Reconciliation — 2026-06-03

**Mode:** READ-ONLY on product code/tests/env. Files touched: `memory/MASTER_STATE.md` + this memo.
**Method:** Downloaded the three QA docs the user named, parsed every list-paragraph via python-docx, mapped each item against current code state + prior dispatch outcomes.

---

## 1 — What changed in the reconciliation

The previous Section 3 was a prior agent's 8-cluster aggregation of QA items (`C1 · Email infra`, `C2 · Auth/OAuth`, etc.) that paraphrased the source asks. Side-by-side comparison against the three actual QA docs surfaced two product-level divergences and several smaller alignment issues. The new Section 3 carries verbatim quotes from each doc and uses per-doc grouping (Doc 1 Onboarding · Doc 2 Task Manager · Doc 3 Google Login + Doc Reader + Calendar + Open Questions) as the primary structure. The 8-cluster tags are preserved as a cross-reference footer only.

The new totals are: **37 items across the 3 docs · ✅ 11 · 🟡 5 · ❌ 19 · 🚧 2 · ❔ 0.** Plus Bug #30 (Forecaster column-pair picker) which originated outside the 3 docs.

---

## 2 — The two onboarding-card divergences (previously claimed ✅, demoted to 🟡 `NEEDS_RE-DISPATCH`)

### O4 — "Create your first cycle"

- **What the QA doc literally says (Onboarding QA, item 4):** *"Why does 'Create your first cycle' option redirect the user to the page in figure 2? I think the user should be redirected to the Task Manager Module shown in figure 3"*
- **What the prior dispatch shipped:** Routes the card to `/app/cycle?wizard=1` (Cycle Setup Wizard).
- **Justification cited at the time:** "per spec G21 = Cycle Setup Wizard".
- **Divergence:** the QA doc explicitly cites Task Manager (Fig 3) as the expected destination. The Cycle Setup Wizard is a different surface.
- **Status:** flipped to **🟡 PARTIAL — NEEDS_RE-DISPATCH**.

### O6 — "Try the Demo"

- **What the QA doc literally says (Onboarding QA, item 6):** *"Why does 'Try the Demo' option redirect the user to the page in Figure 5 after going through the steps in figure 6? I think the user should land on the Home Page"*
- **What the prior dispatch shipped:** Routes the card to `/app/cycle` (Cycle Manager).
- **Justification cited at the time:** "per spec G22 = Cycle Manager `/app/cycle`".
- **Divergence:** the QA doc explicitly cites the Home Page as the expected destination. Cycle Manager is a different surface.
- **Status:** flipped to **🟡 PARTIAL — NEEDS_RE-DISPATCH**.

Both items map to the same prior-agent mistake: closing the QA item against an internal spec document (G21/G22) instead of against the verbatim QA expectation. Surfaced for re-dispatch as Track B Phase B1 additions.

---

## 3 — Other status adjustments

- **G1 (signin redirect):** previously C2 row "Sign-in lands at `/` not `/signin`" → ❌ OPEN. Verbatim doc text now confirms the literal scope (the button-in-fig-20 routes to `/` rather than `/signin`). The literal-interpretation concern flagged earlier (that forcing all unauth `/` traffic to `/signin` would break the marketing funnel) is moot — the QA doc is about a specific button, not the `/` route policy. Still ❌ OPEN until fig 20 screenshot is available to identify the button.
- **G2 (Google signin + fig 22 post-redirect):** the doc treats this as ONE item ("Why can't the user sign in with google as shown in figure 21? User encounters the error in figure 22 after being redirected to the platform?"). The prior matrix had this split into THREE rows ("Google sign-in fails (Fig 21)", "Post-redirect error (Fig 22)", "Re-enter password toast (Fig 22)"). Reconciled to one item, status 🚧 USER-BLOCKED (needs GCP OAuth creds). The "Re-enter password toast" sub-issue → already SHIPPED via P0-C OAuth `last_activity_at` refresh; reconciliation does not split it back out.
- **G5 ("signals tab" terminology):** the prior matrix did not separately track this. Reconciliation status: ✅ SHIPPED (subsumed by G4 fix — the error string in fig 25.2 is gone post-P0-A).
- **G14 (drawer CTAs):** the prior matrix listed each CTA separately. Reconciliation keeps G14 as the "all four CTAs present" item (🟡 PARTIAL — Share missing) and G15-G18 as the per-CTA spec rows.
- **G20 (Open-until-confirmed):** the prior matrix did not have this row explicitly. Folds into G19 implementation. ❌ OPEN.
- **G22 (Response History preservation on reopen):** the prior matrix had "Response history" as a separate row; reconciliation keeps it with G19/G21 as part of the same C6 feature surface. ❌ OPEN.

---

## 4 — New items discovered (not in the prior 29-bug matrix)

- **G23 — Empty state of Your Questions Page.** Verbatim from doc 3, paragraph 26: *"The Empty state of the Your Questions Page to be 'You have not generated any questions yet. Go to a document to generate questions.' And the CTA button 'Go to Document' that redirects the user to the Document Journal"*. This was not represented in the prior matrix at all. Track B Phase B3.

The prior matrix had no other items absent from the QA docs except Bug #30 (Forecaster — outside the 3 docs, preserved for continuity).

---

## 5 — Section 4 Track B reshape

Track B phases preserved (no new phases invented per dispatch rule). Reshape:

- **B1 — small mechanical onboarding + signin (was: Sign-in + Post-redirect + Begin).** Now adds **O4** + **O6** (the two re-dispatch cards) as B1 work. The Begin button (O7) stays in B1 awaiting tester re-verification. G1 (signin redirect) stays in B1 awaiting fig 20 screenshot.
- **B2 — Task Manager lifecycle.** Items: TM1 (badges) + TM2 (Commission + Closure flow) + TM5 (View more → follow-up emails page).
- **B3 — Questions feature wiring.** Items: G13 + G14 + G17 + G19 + G20 + G21 + G22 + G23.
- **B4 — cross-feature surfacing.** Item: G11 (Open Question card → Your Questions wiring).
- **B5 — Document workflow + Calendar polish.** Items: G6 (Notes autosave) + G7 (Send Share) + G10 (Calendar text leakage).

---

## 6 — File-touched diff

```
M memory/MASTER_STATE.md                                       (Section 3 fully rebuilt; Section 4 Track B reshaped; Section 7 timestamp)
A memory/sprints/MASTER_STATE_RECONCILIATION_2026-06-03.md     (this memo)
```

ZERO product code touched. ZERO tests touched. ZERO env changes.

---

## 7 — Honest reckoning (R7)

- The two onboarding-card divergences were silent ✅-claims against an internal spec doc instead of against the verbatim QA expectation. This is exactly the failure mode R5/R7 were designed to catch; the rails fired too late (after the ship). Reconciliation surfaces both for re-dispatch.
- One item (G23) was missing entirely from the prior matrix.
- The G2 cluster-collapse (3 rows → 1) is a structural fix; the QA doc treats it as a single bug.
- The cross-reference at the end of Section 3 preserves the 8-cluster tags as P0/P1/P2 priority hints without making them authoritative — per-doc grouping is the canonical structure going forward.

---

## 8 — Pause point

Awaiting orchestrator's next Pre-Read. The two highest-leverage candidates per status counts:
1. **B1 re-dispatch on O4 + O6** — 2 small mechanical card-route changes. Likely <30 min implementation. Restores ✅ on both rows.
2. **B3 — Questions feature wiring** (8 items) — most-open phase, single feature surface, biggest matrix-flip per dispatch.

Not picking — orchestrator's call.
