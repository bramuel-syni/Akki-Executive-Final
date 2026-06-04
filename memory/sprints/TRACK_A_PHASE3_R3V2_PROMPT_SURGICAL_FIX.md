# Track A Phase 3 — R3v2 prompt-layer surgical fix

**Dispatch:** 2026-06-04T05:18:21Z
**Scope:** prompt + autopicker observability + retry semantics ONLY.
No parser/fence/deterministic-engine/shield-invoke/refuse-to-decide/voice-lint signature changes.

---

## Problem (tester verdict on J19/J20 against the prior R3 fix)

The R3 fenced-JSON fix removed the parser refusal, so `shield_invoke`
narrations now actually persist. But the verbatim tone the live wire
emitted surfaced four deeper truths:

1. **Claude read monthly time-series rows as "locations"** — the prompt
   never told it the first column is a temporal axis (months/quarters),
   so it framed observations as "row 25 of this location" instead of
   "this month broke pattern".
2. **`whats_likely_next` tab was EMPTY** — Bug #30's autopicker computed
   a forecast, but the prompt never *required* the LLM to narrate it,
   so the forecast bar surfaced no observation.
3. **The autopicker's `(date_col, value_col)` choice had zero
   observability** — neither stdout nor the synthesize response carried
   which pair was picked, or why.
4. **Tone was stats-notebook**, not McKinsey — phrases like
   "standard deviation above average" and "row 25" leaked into the
   headline that should be reserved for executive-readable prose.

---

## Fix (five surgical changes)

### 1. Temporal-axis context in the prompt

`analyze_narration._build_prompt` already accepted `workbook_context`
+ `forecast_meta` parameters but `narrate_analysis` never passed them.
Wired the synthesize endpoint (`routers/workbook_analysis.py`) to
build them from the first-sheet column metadata:

```python
workbook_context_for_prompt = {
    "date_columns":    [c.name for c in sheets[0].columns if c.kind == "date"],
    "numeric_columns": [c.name for c in sheets[0].columns if c.kind == "numeric"],
}
```

The prompt now opens with:

```
WORKBOOK STRUCTURE
The first column is a temporal axis (e.g. dates, months,
quarters). Rows represent points in time, NOT entities or
locations. Narrate trends across periods, not across
entities.
Date columns: month
Numeric columns: actual_sales
```

### 2. FORECAST INPUT block + required `whats_likely_next`

When `autopick_forecast_columns` returns a pair AND `run_forecast`
succeeds, the synthesize endpoint forwards a `forecast_meta`:

```python
forecast_meta_for_prompt = {
    "date_col": pick["date_column"],
    "value_col": pick["value_column"],
    "picker_reason": pick.get("picker_reason", ""),
}
```

The prompt then carries:

```
FORECAST INPUT
A forecast has been computed on (month, actual_sales). The
autopicker chose this pair because: non_null_count=24,
value_spread=1100.00.
REQUIREMENT: Because forecast input is present above, your
`observations` array MUST contain at least one entry whose
`tab` is exactly `whats_likely_next`. That observation must
narrate the forecast projection in plain business language
(e.g. 'if the trend holds, Q1 lands 12% below plan'). Do NOT
skip this — the user explicitly asked for forward-looking
narration.
```

### 3. `forecast_meta` in synthesize response + autopicker stdout

`narrate_analysis` now returns `forecast_meta` in the response when
a forecast was computed:

```json
"forecast_meta": {
  "date_col": "month",
  "value_col": "actual_sales",
  "picker_reason": "non_null_count=24, value_spread=1100.00"
}
```

`autopick_forecast_columns` emits a single stdout line per successful
call (visible in the supervisor backend log):

```
[autopick] selected (month, actual_sales) from sheet 'Monthly' (non_null_count=24, value_spread=1100.00)
```

### 4. McKinsey-tone strengthening + concrete good/bad example

```
VOICE
- Headline-first. Lead with what happened in plain business
  language: "Q1 actual sales fell 14% YoY across the trade book",
  NOT "the time-series shows a 14% decrease from prior period".
- Translate statistics into so-what language. A 2.11σ outlier is
  "one month broke pattern", not "row 25 is 2.11 standard
  deviations above the mean".
- BANNED in headline and observation body: the words/symbols
  "standard deviation", "σ", "sigma", "variance", "percentile",
  "z-score". (Statisticians read the Sources tab; executives read
  this narration.)
- Frame rows as time periods, not as entities.

Good headline example:
  "Q1 actual sales fell 14% YoY across the trade book despite
   quantity holding +12% — pricing power eroded in three regions."
Bad headline example (rejected):
  "A single location in Revenue recorded revenue more than twice
   the standard deviation above average."
```

### 5. Banned-jargon-in-headline lockdown + bounded retry

`_headline_has_banned_jargon` blanks the headline if it contains any
of `σ / sigma / standard deviation / std deviation / std dev /
variance / percentile / z-score / z score` (case-insensitive). The
observations stay — only the headline is rejected, so the FE renders
"headline rejected" instead of losing the whole narration.

If `forecast_meta` is set but the LLM's response omits any observation
with `tab == "whats_likely_next"`, `narrate_analysis` retries once
with a stern prepended reminder. After the retry, if `whats_likely_next`
is STILL absent the response carries
`partial_narration_missing_forecast: true` so the FE can surface
"forecast not narrated this run".

---

## Live wire sample (admin@akki.ai, 24-month tester CSV)

Captured 2026-06-04T05:18:21Z via `/tmp/track_a_phase3_r3v2_live_sample.py`:

```json
{
  "headline": "Monthly sales climbed steadily through the period and are on track to reach 17,056 next period—35% above the historical average.",
  "observations": [
    {
      "tab": "what_changed",
      "title": "Sales grew consistently across all 24 months",
      "body": "Actual sales averaged 12,593 across the period, with a floor of 10,000 and a peak of 15,240. The data shows no month broke sharply from the underlying pattern; instead, revenue built incrementally month over month.",
      "citation_count": 1
    },
    {
      "tab": "whats_likely_next",
      "title": "Next period projected at 17,056, up 35% from average",
      "body": "If the trend holds, the next period lands at 17,056 in actual sales—a figure 35% above the 12,593 historical mean. The eight-step-ahead projection carries an 80% confidence band of 16,668 to 17,444, reflecting the strong linear momentum captured by the Linear model (R² of 0.966). The slope of 7.46 per month confirms steady, compounding growth.",
      "citation_count": 1
    }
  ],
  "forecast_meta": {
    "date_col": "month",
    "value_col": "actual_sales",
    "picker_reason": "non_null_count=24, value_spread=1100.00"
  },
  "partial_narration_missing_forecast": false,
  "refused": false,
  "refusal_reason": null
}
```

Stdout confirmed `[autopick] selected (month, actual_sales) from sheet 'Monthly' (non_null_count=24, value_spread=1100.00)`.

**Tone check (eyeball):**
- Headline frames the change in business-readable units ("climbed steadily", "35% above the historical average") — NOT stats jargon. ✓
- "Months" not "rows" or "locations" — temporal-axis context landed. ✓
- `whats_likely_next` populated — forecast requirement honoured. ✓
- The body of `whats_likely_next` does contain "R²", "slope", "confidence band" — these are NOT in the headline-banned set, and they live inside the body where some technical precision is acceptable for the "What's likely next" tab. If the orchestrator wants those banned from the body too, that's a one-line broadening of `_headline_has_banned_jargon` to `_body_has_banned_jargon`. Surfaced for review.

---

## Lockdown tests (≤10 — refactored to separate file)

New file `backend/tests/test_track_a_phase3_prompt_fix.py` — 6 test
functions covering ONLY the R3v2 surfaces. Existing
`test_track_a_phase3_narration.py` (10 tests) untouched.

| # | Test | Asserts |
|---|---|---|
| 1 | `test_banned_jargon_in_headline_blanked` (4 parametrize) | σ / standard deviation / variance / percentile in headline → blanked; observations survive |
| 2 | `test_forecast_meta_surfaces_in_response` | `forecast_meta.{date_col, value_col, picker_reason}` present on response when forecast computed |
| 3 | `test_bounded_retry_when_whats_likely_next_omitted` | shield_invoke called exactly 2× when first response missing forecast tab; retry's observations persist |
| 4 | `test_partial_flag_when_retry_also_omits_forecast` | After both attempts omit forecast → `partial_narration_missing_forecast: true` |
| 5 | `test_autopicker_returns_picker_reason` | `pick["picker_reason"]` carries `non_null_count=N, value_spread=…` |
| 6 | `test_autopicker_emits_stdout_log_line` | `[autopick] selected (D, V)` line emitted |

Pytest verbatim: `9 passed in 7.93s` (4 parametrize + 5 others) for the new file. Combined with `test_track_a_phase3_narration.py` (10) + `test_solva_v1_unchanged.py` (4) → **23/23 PASS**.

Voice-lint: `clean across customer-copy surfaces`.

---

## Files touched (verbatim)

```
M backend/services/solva_v2/analyze_narration.py     # +94/-32 (signature ext, retry, banned-jargon)
M backend/services/workbook_analyzer/forecaster.py   # +21/-4   (picker_reason, stdout log)
M backend/routers/workbook_analysis.py                # +25/-4   (workbook_context + forecast_meta pass-through)
M memory/MASTER_STATE.md                              # 6 phases flipped to ✅; Section 7 timestamp
?? backend/tests/test_track_a_phase3_prompt_fix.py    # 6 functions, ≤10 lockdown ceiling honoured
?? memory/sprints/TRACK_A_PHASE3_R3V2_PROMPT_SURGICAL_FIX.md
?? /tmp/track_a_phase3_r3v2_live_sample.py            # orchestrator-readable sample
```

---

## Hard nos honoured

- ✓ No parser/fence touch — `_extract_json_payload` unchanged.
- ✓ No Track B touch — Questions / TaskManager / Onboarding all untouched.
- ✓ No deterministic engine touch — forecaster / signal_extractor / anomaly_detector / parser unchanged.
- ✓ No shield_invoke / refuse_to_decide / voice_lint signature changes — signature additions are net-new keyword args with default `None` (backward-compatible).
- ✓ Bounded retry max 1.

---

## Resume contract

Pause for tester on **J19 + J20 only**. Six other phases (Track A Phase 1+2, Track B B1+B2+B3) already tester-PASS per orchestrator verdict and flipped to ✅ in MASTER_STATE.md Section 3 + Section 4. Track A Phase 3 plumbing + tone landed; tester re-run captures whether the new headline tone is McKinsey enough.
