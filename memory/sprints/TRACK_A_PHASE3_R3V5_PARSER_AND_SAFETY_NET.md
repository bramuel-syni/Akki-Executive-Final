# Track A Phase 3 — R3v5 parser widening + validator safety-net (A+B dispatch)

**Dispatch:** 2026-06-04T05:58:00Z
**Scope:** parser date-classifier widening (Fix A) + tightly-scoped validator safety-net for the forecast tab (Fix B).
**Hard nos honoured:** no forecaster.py touch, no deterministic engine threshold tuning, no Track B work, no shield_invoke signature change, no new env vars, no customer-facing copy changes (voice-lint stays clean).

---

## Problem (tester verdict on R3v4 J19 happy-path run)

R3v4 EMPTY-sentinel fix verified clean (zero `\bEMPTY\b` occurrences in J19 prose, McKinsey-tone headline). **BUT** J19 happy-path workbook (`Month,Sales` header, 16 ISO `YYYY-MM` rows like `2024-01..2025-04`) rendered as single-tab output with `observations=[ONE entry, tab="what_changed"]`, no `forecast_meta`, no `partial_*` flag — silent regression.

Tester's root-cause hypothesis matched the prior R3v3 fight class:

- The parser's `_coerce_value` (`parser.py:67`) does not recognise `YYYY-MM` as a date format. The `Month` column votes `text` → `_infer_column_kind` returns `text` → `autopick_forecast_columns` returns `None` → `forecast_meta_for_prompt` stays `None` → `forecast_attempted=False` in the validator → the validator silently treats "no forecast block ran" as "forecast tab not required" → no missing-tab flag fires.

Net effect: a workbook the PM would call happy-path rendered as a single-tab "what_changed" output with zero diagnostic signal.

---

## Fix A — Parser date classifier widened (`parser.py:67`)

**File:** `backend/services/workbook_analyzer/parser.py` — `_coerce_value`.

**Before:**
```python
for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
    try:
        return datetime.strptime(s, fmt).date(), "date"
    except ValueError:
        continue
return s, "text"
```

**After (verbatim):**
```python
# Try ISO date.
# Track A Phase 3 R3v5 (2026-06-04) — added %Y-%m and %Y/%m so
# monthly series like "2024-01" classify as `kind="date"`.
# strptime defaults the missing day to 1, so the resulting
# `date(2024,1,1)` works with `_to_ordinal` untouched. Net
# effect: the J19 happy-path workbook (Month/Sales) now reaches
# the autopicker → run_forecast → forecast block → narration.
for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m", "%Y/%m"):
    try:
        return datetime.strptime(s, fmt).date(), "date"
    except ValueError:
        continue
return s, "text"
```

`strptime` defaults the missing day to `1`, so `"2024-01"` coerces to `date(2024,1,1)` — `_to_ordinal` works untouched, no forecaster touch needed.

**Unit test added** in `backend/tests/test_phase_p5_14_workbook_analyze.py`:

```python
def test_parser_classifies_yyyy_mm_strings_as_date():
    """Track A Phase 3 R3v5 (2026-06-04) — YYYY-MM + YYYY/MM
    strings classify as `kind="date"`. J19 shape: header
    `Month,Sales`, rows `2024-01..2025-04`."""
    # YYYY-MM variant
    csv_rows = ["Month,Sales"]
    for i in range(16):
        year = 2024 + (i // 12); month = (i % 12) + 1
        csv_rows.append(f"{year}-{month:02d},{100 + i * 10}")
    blob = ("\n".join(csv_rows) + "\n").encode("utf-8")
    sheets, _ = parse_workbook(blob=blob, file_format="csv")
    cols = {c.name: c for c in sheets[0].columns}
    assert cols["Month"].kind == "date"
    assert cols["Sales"].kind == "numeric"
    # YYYY/MM variant — same widening covers slash separator.
    csv_rows_slash = [...]
    assert cols_slash["Month"].kind == "date"
```

---

## Fix B — Validator safety-net for the forecast tab

**File:** `backend/services/solva_v2/analyze_narration.py` — `_validate_observation_completeness`.

**Verbatim added branch:**
```python
# Track A Phase 3 R3v5 (2026-06-04) — safety-net branch.
# When the autopicker rejected the workbook (`forecast_attempted=
# False`) but the LLM still produced ≥1 observation, the user
# has genuinely lost forward-looking commentary even though no
# deterministic forecast block was ever attempted. Surface a
# banner so the FE can render "forecast not attempted on this
# workbook" instead of a silent single-tab render.
#
# IMPORTANT — narrow scope. The safety-net only fires for
# `whats_likely_next` (the forecast tab's whole point is
# forward-looking). It does NOT auto-imply `whats_odd` missing:
# an anomalies block that ran and found zero records is a clean
# workbook, not a missing tab — firing a flag there would cry
# wolf on every clean spreadsheet.
if (
    not forecast_attempted
    and not any(b.kind == "forecast" for b in blocks)
    and len(observations) >= 1
    and "whats_likely_next" not in present
):
    flags["partial_narration_missing_whats_likely_next"] = True

# Backwards-compat alias for R3v2 consumers — fires whenever
# `whats_likely_next` is missing, by required-tab path OR by
# the safety-net path above.
if flags.get("partial_narration_missing_whats_likely_next"):
    flags["partial_narration_missing_forecast"] = True
return flags
```

**Tightening applied per orchestrator:** the `whats_odd` clause is NOT widened. Empty anomalies block stays a clean-workbook signal, not a missing-tab signal. The flag fires only when (a) the deterministic anomalies block produced ≥1 record AND (b) `whats_odd` is absent from the rendered observations.

---

## Live wire — three scenarios

Run: `cd /app/backend && python3 /tmp/track_a_phase3_r3v2_live_sample.py`

### Scenario 1 — J19 EXACT SHAPE (Fix A target, the failing case)

```
[autopick] selected (Month, Sales) from sheet 'Sheet1' (non_null_count=16, value_spread=182.00)
```

```json
{
  "headline": "Sales averaged 193 per month across sixteen periods, spanning a low of 100 to a high of 282, with no clear linear trend emerging.",
  "observations": [
    {"tab": "what_changed", "title": "Sales varied widely across the sixteen-month window", "body": "Over the sixteen months on record, sales averaged 193 per month. The range was substantial: the weakest month recorded 100 in sales while the strongest hit 282...", "citation_count": 1},
    {"tab": "whats_likely_next", "title": "No linear trend fits the data; volatility likely persists", "body": "The forecast engine could not fit a linear model to the monthly sales series, meaning neither growth nor decline follows a predictable path...", "citation_count": 1}
  ],
  "forecast_meta": {
    "date_col": "Month",
    "value_col": "Sales",
    "picker_reason": "non_null_count=16, value_spread=182.00"
  },
  "partial_flags": {},
  "EMPTY_token_leaked_in_prose": false,
  "refused": false
}
```

**Verification:**
- `forecast_meta` non-null ✓ (Fix A worked — parser now classified `Month` as `date`, autopicker selected the pair)
- Both required tabs populate naturally ✓
- `whats_odd` correctly absent — anomalies block was empty (clean workbook) ✓
- `partial_flags: {}` ✓ — safety-net (Fix B) correctly silent; not crying wolf on a happy path
- No `EMPTY` token leak ✓

### Scenario 2 — Happy path 24-month CSV (regression check)

Unchanged from R3v4 — all 3 tabs populate, no partial flags, no EMPTY leak. ✓

### Scenario 3 — EMPTY-vector branch (noisy date strings)

```json
{
  "headline": "Actual sales averaged 12,530 across 24 months with a stable range from 10,000 to 15,060—no major shifts in the baseline trend.",
  "observations": [],
  "forecast_meta": null,
  "partial_flags": {"partial_narration_missing_what_changed": true},
  "EMPTY_token_leaked_in_prose": false,
  "refused": false
}
```

- Validator fires `partial_narration_missing_what_changed: true` ✓
- Safety-net stays SILENT because `len(observations) >= 1` guard suppresses noise when Claude returns 0 observations ✓
- No EMPTY token leak ✓

---

## Lockdown tests (R4 ≤10 honoured)

`backend/tests/test_track_a_phase3_prompt_fix.py` — stays at **10 functions**. Test 4 (`test_post_shield_validator_sets_per_tab_missing_flags`) extended with **Path C** (safety-net branch):

```python
# ── Path C — R3v5 safety-net branch ──────────────────────────
# `forecast_attempted=False` (autopicker rejected the workbook —
# e.g. parser couldn't classify the date column) AND ≥1 obs
# rendered AND `whats_likely_next` absent → safety-net fires the
# forecast-missing flag + BC alias so the FE never silently
# swallows the missing forward-looking tab.
#
# The matching anomalies-empty branch is INTENTIONALLY NOT
# widened to fire `whats_odd` — an empty anomalies block is a
# clean workbook, not a missing tab. Path C asserts both
# invariants: forecast flag fires; whats_odd flag does NOT.
```

Three Path-C assertions:
- `result_c.get("partial_narration_missing_whats_likely_next") is True` ✓
- `result_c.get("partial_narration_missing_forecast") is True` (BC alias) ✓
- `"partial_narration_missing_whats_odd" not in result_c` (no wolf-crying on clean workbook) ✓

`tests/test_phase_p5_14_workbook_analyze.py` — **+1 parser unit test** (32 total in that file; outside the Phase-3 ≤10 budget per file ownership).

**Combined regression:**
- `test_track_a_phase3_prompt_fix.py`: 14 cases (10 functions, param fanout = +4)
- `test_track_a_phase3_narration.py`: 13 cases
- `test_solva_v1_unchanged.py`: 4 cases (v1 byte-identical guard intact)
- `test_phase_p5_14_workbook_analyze.py`: 32 cases (was 31, +1 R3v5)

**Total: 59/59 PASS in 9.41s.** Voice-lint clean.

---

## Files touched (verbatim diff stat)

```
M backend/services/workbook_analyzer/parser.py            # +9/-1 (date format list widened)
M backend/services/solva_v2/analyze_narration.py          # +24/-3 (safety-net branch in validator)
M backend/tests/test_phase_p5_14_workbook_analyze.py      # +37/-0 (parser YYYY-MM unit test)
M backend/tests/test_track_a_phase3_prompt_fix.py         # +56/-0 (Path C extension on test 4)
M memory/MASTER_STATE.md                                  # Section 6 + 7
M /tmp/track_a_phase3_r3v2_live_sample.py                 # J19 exact-shape scenario added
?? memory/sprints/TRACK_A_PHASE3_R3V5_PARSER_AND_SAFETY_NET.md
```

---

## Hard nos honoured

- ✓ No `forecaster.py` touch — autopicker scoring + `_to_ordinal` unchanged from R3v3.
- ✓ No deterministic engine threshold tuning — `signal_extractor`, `anomaly_detector`, `monte_carlo` untouched.
- ✓ No Track B work.
- ✓ No `shield_invoke` signature change.
- ✓ No new env vars.
- ✓ No customer-facing copy / voice-lint changes — voice-lint stays "clean across customer-copy surfaces".

---

## Resume contract

Pause for tester re-run of **J19 + J20 only**. MASTER_STATE.md Section 4 Track A Phase 3 stays 🟡 PARTIAL.

---

## Close-out — TESTER-VERIFIED 2026-06-04 (4/4 PASS)

The tester re-ran all four cases against the real `shield_invoke` endpoint and confirmed R3v5 lands green:

| # | Case | Verdict | Evidence |
|---|---|---|---|
| 1 | **J19** (happy path, ISO `YYYY-MM`) | ✅ PASS | HTTP 200 in 8.3s real Claude round-trip. `forecast_meta` non-null with `picker_reason: "non_null_count=16, value_spread=110.00"`. Both `what_changed` + `whats_likely_next` populated with McKinsey-tone prose. `whats_odd` correctly absent (clean workbook). Zero `partial_narration_missing_*` flags. No `\bEMPTY\b` token. **Fix A confirmed working in production.** |
| 2 | **J20** (noisy unparseable dates) | ✅ PASS | HTTP 200. `partial_narration_missing_whats_likely_next: true` + BC alias `partial_narration_missing_forecast: true` both fire correctly. `what_changed` rendered. No EMPTY leak. **Fix B safety-net confirmed.** |
| 3 | **J19-API** (curl sanity) | ✅ PASS | Identical behaviour to J19. |
| 4 | **J20-API** (curl sanity) | ✅ PASS | Identical behaviour to J20. |

**Real LLM round-trip confirmed** — varied stats and non-deterministic prose across runs prove the trace is not mocked. EMPTY-sentinel fix from R3v4 still holding clean across both paths.

**Status flips:**
- MASTER_STATE.md Section 4 Track A Phase 3 → ✅ COMPLETE.
- MASTER_STATE.md Section 3 Bug #30 → ✅ SHIPPED (folded into Phase 3 close-out).
- Lockdown still green: 59/59 PASS.
- v1 byte-identical guard intact.
- Voice-lint clean.

**Next:** paused pending user's separate document-review request scoping. Track B B4 + Track A Phase 4 NOT auto-started per orchestrator instruction.
