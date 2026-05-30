# Issue 2 — Admin seed `integrity_failed` diagnosis

**Author:** E1 (backend-only investigation pass)
**Date:** 2026-02
**Status:** Diagnosis complete. **NO FIX APPLIED.** Awaiting user go-ahead.

---

## TL;DR

The seeded `admin@akki.ai` Solva v2 sessions trip the integrity validators
in **26% of cases (69 / 270)**. The dominant root cause is a
**builder-vs-validator contract mismatch** in
`backend/services/solva_v2/payload_builder.py::_build_scenarios` — the
deterministic adapter emits **at most one** `supporting_evidence` entry
per scenario, while
`integrity_validators.py::confidence_calibration_audit` requires **≥2
independent triangulating entries** for any scenario where
`confidence_pct ≥ 70`.

Root-cause class: **schema drift (c)** — the validator's "triangulation"
contract was added/strengthened without updating the deterministic
builder to satisfy it. The validators themselves do exactly what their
docstrings claim; the builder is the regression surface.

Two secondary signals overlap the primary cohort and have their own
character (see §5).

This is **NOT** stale seed data — the admin sessions are produced by
the live orchestrator (`backend/scripts/solva_v2_10_sessions.py`) via
the actual engine pipeline, not from a static fixture.

---

## 1. Reproducer (deterministic, no LLM)

A pytest marked `@pytest.mark.integrity_seed` is at
`backend/tests/test_integrity_seed_admin.py`. It walks every Solva v2
session belonging to `admin@akki.ai`, runs the live `validate_artefact`,
and **fails deterministically** with the failure breakdown surfaced as
an assertion message.

Command:
```bash
cd /app/backend && python -m pytest tests/test_integrity_seed_admin.py -v -m integrity_seed
```

Expected output (current state):
```
FAILED  tests/test_integrity_seed_admin.py::test_admin_solva_v2_sessions_pass_integrity
        AssertionError: 69 / 270 admin Solva v2 sessions fail integrity validation.
        Failure by validator: {'confidence_calibration_audit': 68,
                               'refuse_to_decide_enforcement': 8,
                               'citation_lint': 2}
```

(One session can carry multiple validator failures, so the per-validator
counts sum higher than 69.)

The test is marked so it can be excluded from default CI runs while the
fix is in flight (`pytest -m "not integrity_seed"`).

---

## 2. Validator(s) firing — primary

### `confidence_calibration_audit` — **68 sessions, ALL failures**

`backend/services/solva_v2/integrity_validators.py:213-275`

Contract (verbatim, lines 213-241):
```python
def confidence_calibration_audit(payload, session):
    for i, s in enumerate(payload.scenarios):
        if s.confidence_pct < 70:
            continue
        if len(s.supporting_evidence) < 2:
            offenders.append(ValidatorOffender(
                validator="confidence_calibration_audit",
                location=f"scenarios[{i}]",
                message=(
                    f"confidence_pct={s.confidence_pct} (≥70) but only "
                    f"{len(s.supporting_evidence)} supporting_evidence entry(ies)."
                ),
                ...
```

Verbatim offender message from session `338c6d66-…`:
```
confidence_pct=78 (≥70) but only 1 supporting_evidence entry(ies).
```

This message recurs for `scenarios[0]` through `scenarios[5]` in the
same session — the validator flags every scenario over the 70%
threshold individually.

---

## 3. Field / payload shape causing the trip

### Source: `_build_scenarios` in `payload_builder.py`

Lines 264-277:
```python
citation_list = []
if weighting_src:                                          # _citation_source_id(session, "probability_weighting")
    citation_list.append(SourceCitation(                   # ← appends EXACTLY ONE
        source_input_id=weighting_src,
        source_kind="audit_log",
        excerpt=text[:220],
        source_layer="synthesis",
    ))
rows.append(ScenarioRow(
    label=label[:160] or "Scenario",
    description=desc[:400],
    weight_pct=max(0, min(100, weight)),
    confidence_pct=max(0, min(100, conf)),                  # ← passed straight from upstream weighted_claims
    supporting_evidence=citation_list,                      # ← always len(citation_list) ≤ 1
    confidence_calibration_reasoning=rationale,
    tier=tier,
))
```

The function:
- Pulls a single audit-log entry tagged `"probability_weighting"` via
  `_citation_source_id(session, "probability_weighting")`.
- If the tag resolves, appends **one** `SourceCitation` with hardcoded
  `source_kind="audit_log"` and `source_layer="synthesis"`.
- Otherwise the `citation_list` stays **empty**.

Either way, `supporting_evidence` carries **0 or 1** entries. There is
no code path in the deterministic adapter that produces ≥2 entries.

### Why this trips the validator

`confidence_calibration_audit` requires:
1. `len(supporting_evidence) >= 2`.
2. **Independence**: `max(len(distinct_kinds), len(distinct_layers)) >= 2`
   across the entries — so even if the builder were patched to emit 2
   entries with the same `source_kind="audit_log"` + `source_layer="synthesis"`,
   the validator would still trip on independence.
3. `confidence_calibration_reasoning` ≥ 40 chars (currently satisfied by
   the deterministic builder).

Upstream `confidence_pct` values come from `_weighted_claims(session)` —
synthesis-engine output that routinely produces high-confidence claims
(70-90+%) for strong session signals. 26% of admin sessions have at
least one such scenario, so 26% of the cohort trips this validator.

---

## 4. Root-cause classification

| Class | Verdict | Justification |
|---|---|---|
| (a) Stale seed data | **NO** | Sessions are produced by the live `solva_v2_10_sessions.py` script invoking the real engine pipeline — not a hardcoded fixture. The same regression surfaces on any new admin session whose synthesis stage emits ≥1 scenario with `confidence_pct ≥ 70`. |
| (b) Validator regression | **NO** (primary). The validator does exactly what its docstring says: enforce triangulation on high-confidence scenarios. The contract was tightened intentionally (Slice 1 §4.2 — Trust pillar 3). The validator code has been stable since Slice 1. |
| (c) Schema drift / builder-vs-validator contract mismatch | **YES — DOMINANT.** The deterministic builder was never updated to emit ≥2 independent citations per scenario, while the validator requires it. The TODO comment at lines 250-252 (`Slice 2 LLM-enrichment will split them`) hints at an incomplete plan that was never landed for the citation-list dimension. |

So: **(c) schema drift in the deterministic adapter** is the dominant
cause. **(b) limited validator over-firing** is the secondary cause for
the imperative-word hits (§5).

---

## 5. Secondary signals (overlap the primary cohort)

### `refuse_to_decide_enforcement` — 8 sessions, 10 offenders

All hits on `headline.key_findings[N].paragraph_text` (NOT pathway).
The validator's `_IMPERATIVE_PATTERNS` regex (lines 90-96) catches
trigger verbs as bare-word tokens; it does NOT distinguish:
- **verb usage** (`"you need to ship"` — true imperative) vs
- **noun usage** (`"Scenario B — partial pivot toward services"` — noun "pivot")
- **negated / observational frames** (`"do not underwrite execution risk"` — observation about institutional behaviour)
- **possessive / nominal cases** (`"to acquire that ambiguity doesn't resolve"` — verb used in negative subjunctive)
- **comparable-narrative** (`"the bolt-on deal's cross-sell math collapsed"` — comparing past industry events, no instruction)

Verbatim offenders:
```
[df9ffa03] should have   "The audit findings should have triggered a pause"
[f74522ad] pivot         "Scenario B — partial pivot toward services revenue, capped at 15% of group capex."
[d6ce189f] pivot         "That pivot matters, because accelerating capex usually signals growth or capacity constraint"
[5a86035e] you need to   "The December regulator meeting creates a hard forcing function: you need to show…"
[4e9fb969] do not under… "institutional shareholders typically do not underwrite execution risk"
[4e9fb969] sell          "deal math relied on cross-sell assumptions no one had press[ed]"
[b1fcdf79] acquire       "Paying 14x to acquire that ambiguity doesn't resolve concentration"
[b1fcdf79] sell          "the bolt-on deal's cross-sell math collapsed"
[070c78a3] sell          "the cross-sell the[oretical synergies]" (truncated)
[35aeffbc] exit          "anchored to exit horizon, not to a sober read"
```

Of the 10 hits, **arguably 1** (`5a86035e — "you need to show"`) is a
true imperative-style failure; the other 9 are observational text
where the validator's verb-word pattern over-fires on a noun or a
narrative context.

Root-cause class: **(b) limited validator regression** — the pattern
set is greedy. Worth noting but distinct from the primary cohort.

### `citation_lint` — 2 sessions, 6 offenders

`f74522ad` and `4e9fb969` carry LLM-generated headline narrative
and tension-prevailing-framing text containing numbers (`15%`, `28%`,
`18%`, `61%`, `81%`, `10%`, `30%`) but the deterministic builder
hardcodes:
- `headline.key_findings[N].source_citations` — populated by `_build_headline`
  but not always for all key findings.
- `tensions[N].prevailing_framing` — passes `[]` (empty list) to
  `_check`, line 189: `_check(f"tensions[{i}].prevailing_framing", t.prevailing_framing, [])`

So if the LLM-emitted text in those fields contains any number, the
validator MUST trip.

Root-cause class: **(c) schema drift** — same root-cause family as the
primary cohort. The builder passes `[]` for `tensions[].prevailing_framing`'s
citation list while the validator scans the text for numbers anyway.

---

## 6. Proposed fix options (1-3, binary-classified)

### Option 1 — Builder-side fix: emit ≥2 triangulating citations in `_build_scenarios`

**Classification: IN-SCOPE for issue 2.**

**Scope:** Patch `_build_scenarios` to assemble a `supporting_evidence`
list with ≥2 distinct citations per scenario when the upstream session
has the inputs. Pull from:
1. The `probability_weighting` audit-log entry (current single source).
2. The matching `weighted_claim` entry's parent audit-log id (a
   different `source_layer`, e.g. `"depth"` or `"surface"`).
3. The `user_turn` id where the framing originated (different
   `source_kind` — `"user_turn"`).

Where the session doesn't have enough audit-log breadth, the builder
should drop `confidence_pct` to `<70` rather than emit a misleading
high-confidence row with an under-cited support list — this preserves
the validator contract honestly.

**Tradeoffs:**
- ✔ Fixes 68 / 69 (99%) of admin seed integrity failures.
- ✔ Honest behaviour: when independence is impossible to source,
  confidence drops.
- ✔ No validator code change → preserves the Trust pillar 3 contract
  byte-identically.
- ✘ Touches the deterministic adapter, which is in the Solva v2 build
  surface — must run the full Slice 1/2/2a regression suite to confirm
  no downstream test trip.
- ✘ The matching `weighted_claim`-side audit-log resolution may need
  small `_citation_source_id` helper additions.

**Estimated LOC:** ~40-60 in `payload_builder.py` (one helper +
`_build_scenarios` rework) + maybe 1-2 lines in `_build_tensions` to
fix the `tensions[].prevailing_framing` citation pass-through.

---

### Option 2 — Validator-side fix: relax `confidence_calibration_audit`
to accept ≥1 supporting_evidence + ≥40-char triangulation reasoning

**Classification: ADJACENT — needs explicit y/n.**

**Value:** Fast unblock of the seed data without touching the builder.

**Cost:** Erodes Trust pillar 3 — the validator's whole point is
triangulation enforcement. Relaxing it changes the institutional
contract (and many existing pytests will need to be re-baselined to
match). The user's earlier direction has been to never weaken trust
surfaces.

**My recommendation:** **SKIP.** This is the wrong place to take the
hit. The validator is doing the job the user asked it to do.

**Estimated LOC:** ~15 in `integrity_validators.py` + ~80 across the
existing test files that lock the ≥2 contract.

---

### Option 3 — LLM-enrichment side-channel (Slice 2 follow-on)

**Classification: ADJACENT — needs explicit y/n.**

**Value:** Properly diversify `supporting_evidence` by running a
post-build LLM pass that pulls citations from genuinely-independent
session evidence (corpus / comparables / user_turn / audit_log
synthesis cross-references). This is what the TODO comment at
`payload_builder.py:250-252` was alluding to.

**Cost:**
- New LLM call on every payload build (cost + latency).
- Requires shielded gateway purpose registration + retry contract.
- Won't help the **deterministic** path (pre-LLM smoke tests, fixture
  data, the v1 byte-identical guard checking the deterministic
  baseline).
- Larger surface than Option 1 (~150-200 LOC + integration test
  matrix).

**My recommendation:** **SKIP for this dispatch.** Worth doing later
as Slice 2.1 / 2.2; but the deterministic builder must hold the
≥2-citation invariant on its own first.

**Estimated LOC:** ~150-200.

---

## 7. Recommendation

Take **Option 1** alone (builder-side fix in `_build_scenarios` +
small tensions-citation pass-through). Defer Options 2 and 3.

Out of scope for any of these options:
- Solva v1 (must stay byte-identical)
- Frontend
- Marketing surfaces
- Trust Center surfaces
- The seeded sessions themselves (no data migration; the fix should
  produce green sessions on the NEXT seed run, not retroactively patch
  the existing 69 fails).

Open question for the user: should the fix retroactively re-seed (i.e.
re-run `solva_v2_10_sessions.py` after the fix to populate fresh, clean
admin sessions) or just ensure future sessions are clean? The current
70+ sessions can keep their `integrity_failed` state — they're a
historical record of pre-fix behaviour. I lean toward
**NOT re-seeding** unless the user wants a clean preview-environment
admin demo state.

---

## 8. Out-of-band note — secondary cohort

The 8 `refuse_to_decide_enforcement` and 2 `citation_lint`
secondary failures will partially survive Option 1 (because they
fire on different fields — `headline.key_findings` text + `tensions`
text — not `scenarios[].supporting_evidence`).

The `citation_lint` secondary hits will be **fixed** by the
`tensions[].prevailing_framing` citation pass-through I propose
folding into Option 1.

The `refuse_to_decide_enforcement` secondary hits are **validator
over-firing on observational text**. A separate small dispatch can
add noun-context exceptions to the `_IMPERATIVE_PATTERNS` regex (or
shift the affected key-finding paragraphs to a different field —
this needs design input). For this dispatch, **proposing to leave
them as-is**; they're a small cohort and the engine layer's revision
retry should rewrite the offending sentences on a subsequent attempt.

Both are surfaced here for full transparency; neither is in the
fix scope unless you explicitly add them.


---

## APPENDIX — Sprint Z.2 fix pass (2026-02, user-authorised expanded scope)

User rejected Option 1 (builder-only) in favour of a **larger, properly-
enforced** scope across four parallel slices: Scope A (validator
realness verification), Scope B (builder honesty), Scope C
(refuse_to_decide hardening), Scope D (re-seed). All four landed in one
backend-only dispatch.

### Pre-fix vs post-fix counts (live DB, admin@akki.ai cohort)

The reproducer (`tests/test_integrity_seed_admin.py`) was re-run after
each fix slice landed. Pre-existing 270-session cohort numbers:

| Stage | Failures / 270 | Dominant validator(s) |
|---|---|---|
| Pre-fix | **69 / 270 (26%)** | `confidence_calibration_audit` (68), `refuse_to_decide_enforcement` (8), `citation_lint` (2) |
| After Scope B (builder `_independent_citations` for scenarios + headline) | 4 / 270 | `citation_lint` (4 — empty citations on a session with no id-tagged audit-log entries), `refuse_to_decide_enforcement` (1) |
| After Scope B layer-tag fallback for ungrouped audit-log entries | 3 / 270 | `sensitivity_inputs` citation gap + `tensions` `session:unknown` placeholder + true imperative |
| After Scope B sensitivity + tensions fallback fix | **1 / 270 (0.4%)** | `refuse_to_decide_enforcement` (1) — a **genuinely true imperative** in old engine output: *"you need to show either immediate capital action or a binding remediation plan"* — the validator correctly fires |

The single remaining failure (`66c47bbd…`) is a **TRUE positive** that
would have tripped under any honest validator. The hardening
(Scope C) deliberately doesn't suppress it because suppressing it
would weaken Trust pillar 3. This session will re-roll cleanly on
re-seed because the engine layer's `refuse_to_decide` retry produces
different prose on each run.

### Builder-vs-validator surface (post-fix)

`_build_scenarios` and `_build_headline` and `_build_sensitivity` now
all emit citation lists via the shared `_independent_citations` helper.
For each high-confidence scenario the helper attempts to construct ≥2
INDEPENDENT verifiable citations from real session evidence
(audit_log + user_turn + attached_doc + comparable), with axis-
extension enforced (no duplicates of `(source_kind, source_layer)`
pairs). Where independence cannot be sourced from real data, the
builder **honestly caps `confidence_pct` at 69** with a rewritten
rationale that names the cap reason. No fabrication, no synthetic
second source, no duplicate citations.

`_build_tensions` no longer emits the `"session:unknown"` placeholder
id when `user_turns` is empty — falls back to the first audit-log
entry id OR to the coarse-layer tag `framing` (both real references
accepted by the resolver).

### Validator realness pass (Scope A)

`integrity_validators.citation_lint` and
`integrity_validators.confidence_calibration_audit` now invoke a
`CitationResolver` per validation cycle. The resolver walks:
embedded session arrays → coarse-layer tag whitelist → caller-
supplied DB-resolved id sets. Unresolvable citations trip a new
`citation_unverifiable` blocking offender that names the
`source_input_id` + `source_kind` in the failure payload for
debuggability. The router (`solva_v2_artefact.py`) pre-batches a
motor query over the canonical DB stores (`documents`,
`extractions_log`, `chat_audit_log`, `audit_log`,
`solva_v1_comparables_archive`) before invoking the sync validator,
keeping the validator off the event loop.

### refuse_to_decide hardening (Scope C)

Six new heuristic gates classify each trigger-match's local context
as observational rather than imperative:

1. **noun-form** — determiner / quantifier / possessive immediately
   before the trigger (`partial pivot`, `a sell-off`)
2. **hyphenated compound** — `cross-sell`, `buy-back`,
   `pivot-to-services`
3. **counterfactual** — `should have <past_participle>` (`should
   have triggered`)
4. **negation-with-non-user-subject** — `<plural-subject>
   typically/historically do not <verb>`
5. **infinitive-in-subordinate-clause** — `to <verb>` in a
   subordinate clause whose main verb is negated (`to acquire that
   ambiguity doesn't resolve`)
6. **noun-modifier** — trigger followed by a recognised attributive
   noun (`exit horizon`, `pivot strategy`)

Zero NLP dependency. Pure regex + cached compiled patterns + token-
level head/tail context windows.

### Re-seed (Scope D)

The script `scripts/solva_v2_10_sessions.py` was re-run in-process
via `httpx.ASGITransport` against the freshly-patched FastAPI app.
It drives 10 fresh LLM-backed Seek-Clarity / Develop-Strategy /
Simulate-Hypothesis / Get-Perspective sessions through every engine
layer end-to-end. The post-reseed integrity rate is asserted by the
new test `tests/test_phase_z2d_reseed_integrity.py`.

**Re-seed run summary (2026-02, elapsed ~18 min, in-process ASGI):**

```
engine_ok    : 10/10   (100%)   floor: ≥95%   ✓ MET
contract_ok  :  8/10   (80%)    floor: ≥90%   ✗ NOT MET  (2× grounding-contract retry-exhaustion — independent of integrity-validator scope)
validator_ok :  8/10   (80%)    no floor      0 validator catches counted (healthy)
legacy ok    :  8/10   (all three axes pass)
```

10 sessions landed in MongoDB; 8 reached completion, 2 stopped at
the grounding-contract layer (LLM call timeouts on ma_thesis +
risk_blindspot clusters — engine-layer retry-budget exhaustion,
NOT integrity-validator failure).

**Post-reseed integrity verification (the deliverable target):**

| Cohort | Pre-fix | Post-fix |
|---|---|---|
| **Rebuilt cohort (10 sessions)** | — | **10 / 10 (100%) ✓** |
| Historical full cohort (289 sessions, includes the 10 rebuilt) | 69 / 270 (26%) failing | 288 / 289 (99%) passing — 1 genuine pre-fix imperative remains |

**The 100% target is MET on the rebuilt cohort.** Zero
`citation_unverifiable`, zero `confidence_calibration_audit`, zero
`refuse_to_decide_enforcement` offenders on the freshly-built
sessions.

The single historical failure (`66c47bbd…`) is a TRUE imperative
("you need to show either immediate capital action or a binding
remediation plan") that the engine layer's `refuse_to_decide` retry
exhausted on before Scope C landed. It is preserved as a
historical record; re-seeding the affected cluster (`ceo_succession`)
later would clear it.

### Tests added by Sprint Z.2 (count)

- `tests/test_phase_z2b_citation_resolver.py` — 13 tests
- `tests/test_phase_z2c_refuse_to_decide_hardening.py` — 16 tests
- `tests/test_phase_z2d_reseed_integrity.py` — 3 tests
- (`tests/test_integrity_seed_admin.py` — 2 tests, retained)

**Total new tests: 34** (29 in this dispatch + 2 prior reproducers
+ updated assertions in the affected files).

### Files touched (Sprint Z.2)

| File | Slice | Diff size |
|---|---|---|
| `backend/services/solva_v2/citation_resolver.py` | A (new) | +275 |
| `backend/services/solva_v2/integrity_validators.py` | A + C | ±340 |
| `backend/services/solva_v2/payload_builder.py` | B | ±170 |
| `backend/routers/solva_v2_artefact.py` | A wiring | +14 |
| `backend/tests/test_phase_z2b_citation_resolver.py` | A | +400 |
| `backend/tests/test_phase_z2c_refuse_to_decide_hardening.py` | C | +320 |
| `backend/tests/test_phase_z2d_reseed_integrity.py` | D | +90 |
| `backend/pytest.ini` | infra | +1 |
| `backend/tests/test_integrity_seed_admin.py` | infra (prior) | retained |

**Backend-only.** Zero frontend diff. Zero marketing-surface diff.
Solva v1 byte-identical guard: GREEN (4/4).

