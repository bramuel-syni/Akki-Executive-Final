# Track A Phase 3 — R3v3 plumbing fix + prompt all-tabs requirement

**Dispatch:** 2026-06-04T05:37:00Z
**Scope:** plumbing reorder + observability + autopicker spread correctness + prompt all-tabs contract + anomaly call-site fix.
No fence-parser touch. No Track B touch. No deterministic engine output schema changes (signal/forecast/anomaly Pydantic models untouched). No shield_invoke signature change. Bounded retry max 1.

---

## Problem (tester verdict, after R3v2 J19 re-run)

`/app/backend/routers/workbook_analysis.py` lines ~807-845:
`forecast_meta_for_prompt = None` then ONLY assigned **after**
`run_forecast()` succeeds inside `try/except (ValueError,
CitationUnverifiable): pass`. If `run_forecast` raised (and it was
— silently on the J19 workbook because the date column failed
`_to_ordinal` on every row → fewer than 3 (date, value) pairs),
the autopicker's decision was dropped before the prompt was built.
The prompt then had no `forecast_meta` to require `whats_likely_next`.

Plus `value_spread=0.00` in the autopicker stdout despite the
narration showing $115K spread → the 6-row sample preview hid the
real column range.

Plus narration was producing only 1 of 4 required tabs.

---

## Fixes

### 1. Move `forecast_meta_for_prompt` BEFORE the run_forecast try-block

**File:** `backend/routers/workbook_analysis.py` (synthesize_v2_endpoint,
around line 807).

```python
pick = autopick_forecast_columns(sheets=sheets)
forecast_meta_for_prompt: Optional[Dict[str, Any]] = None
if pick is not None:
    # Surface the autopicker choice for the prompt regardless of
    # whether `run_forecast` produces a deterministic vector.
    forecast_meta_for_prompt = {
        "date_col":      pick["date_column"],
        "value_col":     pick["value_column"],
        "picker_reason": pick.get("picker_reason", ""),
    }
    sheet_obj = next((s for s in sheets if s.name == pick["sheet"]), None)
    if sheet_obj:
        ...
        try:
            fc = run_forecast(...)
            resolver.resolve_many(fc.citations)
            wba.forecasts.append(fc)
        except (ValueError, CitationUnverifiable) as exc:
            logger.warning(
                "[run_forecast] swallowed exception on (%s, %s): %s",
                pick["date_column"], pick["value_column"], exc,
            )
```

The prompt now sees `forecast_meta` even when the deterministic
forecast vector is empty, and the prompt scaffolding requires
`whats_likely_next` based on "we attempted (date_col, value_col)".

### 2. Observability — `logger.warning` on swallowed exception

`logger = logging.getLogger("akki.workbook_analysis")` declared
once at module top. Inside the except block:

```python
logger.warning(
    "[run_forecast] swallowed exception on (%s, %s): %s",
    pick["date_column"], pick["value_column"], exc,
)
```

No raise — preserves graceful degradation. Just makes the failure
visible in `/var/log/supervisor/backend.*.log`.

Symmetric `[detect_anomalies] swallowed exception` added on the
companion anomaly call-site so future regressions surface.

### 3. `value_spread` regression — use minv/maxv not 6-sample preview

**File:** `backend/services/workbook_analyzer/forecaster.py` —
`autopick_forecast_columns`, the spread calculation.

The parser already pre-computes `minv` / `maxv` on the FULL
numeric column (see `services/workbook_analyzer/parser.py:120`).
The autopicker now uses those directly; sample-based spread is
the rare fallback when the parser couldn't compute the stats.

```python
if num_col.maxv is not None and num_col.minv is not None:
    spread = float(num_col.maxv) - float(num_col.minv)
else:
    # Fall back to sample-based spread for the rare case the parser
    # couldn't compute minv/maxv.
    samples = [
        float(v) for v in (num_col.sample_values or [])
        if isinstance(v, (int, float))
    ]
    spread = (max(samples) - min(samples)) if len(samples) >= 2 else 0.0
```

Verified live: `value_spread=5240.00` (was `0.00` in R3v2) for the
24-month CSV with three numeric columns.

### 4. Prompt requires ALL tabs whose deterministic block has data

**File:** `backend/services/solva_v2/analyze_narration.py` —
`_build_prompt` restructured to surface labeled blocks:

```
WORKBOOK STRUCTURE
The first column is a temporal axis (e.g. dates, months,
quarters). Rows represent points in time, NOT entities or
locations. Narrate trends across periods, not across entities.
Date columns: month
Numeric columns: actual_sales, units, refunds

SIGNALS BLOCK
[0] Up — Run rate climbed.  (cite=Monthly!B2:B25)

FORECAST BLOCK
Autopicker chose (month, actual_sales); reason: non_null_count=24, value_spread=5240.00.
[1] Linear regression on (month, actual_sales) — slope 0.0250, R² 0.972; …

ANOMALIES BLOCK
[2] Row 19 of Monthly!D value=4050.00 (z=+5.10, IQR-distance=+3.22). …

REQUIREMENTS — your `observations` array MUST contain
`what_changed` (at least one entry; cite the SIGNALS BLOCK); AND
`whats_likely_next` (at least one entry; narrate the FORECAST BLOCK); AND
`whats_odd` (at least one entry; cite the ANOMALIES BLOCK).
Omitting a required tab when its block has data is a contract
violation. The bottom-line headline is mandatory regardless.
```

Empty blocks emit explicit "no X — OMIT `tab` tab" lines so Claude
doesn't fabricate.

### 5. Bounded retry on missing tabs + per-tab partial flags

Inside `narrate_analysis`:

```python
required_tabs = set()
if has_signals: required_tabs.add("what_changed")
if has_forecast_vector or forecast_attempted: required_tabs.add("whats_likely_next")
if has_anomalies: required_tabs.add("whats_odd")

missing = required_tabs - tabs_present(parsed)
if missing:
    retry_prompt = (
      "PREVIOUS ATTEMPT VIOLATED THE REQUIRED-TABS CONTRACT.\n"
      f"Your prior response was missing observations for: {sorted(missing)}. ..."
    ) + prompt
    retry_parsed = await _invoke_once(retry_prompt)
    if retry_parsed and len(tabs_present(retry_parsed) & required_tabs) > len(tabs_present(parsed) & required_tabs):
        parsed = retry_parsed
```

After voice-lint + banned-jargon + citation-resolver pass,
`final_missing = required_tabs - final_present` populates per-tab
flags `partial_narration_missing_what_changed`, `…_whats_likely_next`,
`…_whats_odd`. `partial_narration_missing_forecast` retained as a
backwards-compat alias for `whats_likely_next`.

Bounded retry is **max 1 per synthesize call total** — not per tab.

### 6. Anomaly call-site fix (router plumbing, not engine)

The synthesize_v2 endpoint was calling `detect_anomalies(sheet=<WorkbookSheet>, column=<col>, …)` with wrong kwarg names; the
engine expects `sheet: str, column_name, column_letter, header_row_index, col_index_zero`. Every call raised TypeError → swallowed →
`wba.anomalies` was always empty → `whats_odd` never had block data.

Fixed in-place; engine signature untouched.

---

## Live wire sample (24-month CSV with Date + 3 numerics)

Run: `cd /app/backend && python3 /tmp/track_a_phase3_r3v2_live_sample.py`

Captured 2026-06-04T05:37:17Z:

```
[autopick] selected (month, actual_sales) from sheet 'Monthly' (non_null_count=24, value_spread=5240.00)
```

```json
{
  "headline": "One month saw refunds spike to 17 times the typical level, while underlying sales climbed steadily toward a projected 36% gain over two years.",
  "observations": [
    {
      "tab": "what_changed",
      "title": "Sales grew consistently with units stable across two years",
      "body": "Actual sales averaged 12,590 per month across the 24-month period, ranging from 10,000 to 15,240. The steady climb reflects consistent momentum without dramatic swings. Refunds typically ran around 238 per month, staying within a narrow band except for one pronounced spike.",
      "citation_count": 2
    },
    {
      "tab": "whats_likely_next",
      "title": "Sales trajectory points to 17,056 in eight months",
      "body": "The sales trend line shows a monthly lift of roughly 7.5 units of revenue, with 97% of the variation explained by time alone. Extending that pattern eight months forward lands at 17,056 (range 16,668 to 17,444), representing a 36% increase from the current baseline. The tightness of the confidence interval reflects the reliability of the historical climb.",
      "citation_count": 1
    },
    {
      "tab": "whats_odd",
      "title": "Row 19 refunds hit 4,050—seventeen times normal monthly volume",
      "body": "In the month captured at row 19, refunds reached 4,050, dwarfing the typical 238 and sitting nearly five times further from the average than any other month. That single period accounts for roughly one-sixth of all refunds across the two-year window. Executives may want to trace whether a product recall, billing error, or one-time event drove the spike.",
      "citation_count": 2
    }
  ],
  "forecast_meta": {
    "date_col": "month",
    "value_col": "actual_sales",
    "picker_reason": "non_null_count=24, value_spread=5240.00"
  },
  "partial_narration_missing_forecast": false,
  "refused": false
}
```

**Tone check:** headline frames change in business-readable units ("36% gain over two years", "17 times the typical level"). All three required tabs populated. `whats_odd` body says "five times further from the average than any other month" — translates z-score to so-what language. No σ/standard-deviation/variance/percentile/z-score in any visible surface.

---

## Lockdown tests (≤10 R4 ceiling honoured)

**File:** `backend/tests/test_track_a_phase3_prompt_fix.py` — 10 test
functions, 13 pytest cases (banned-jargon parametrize × 4 + 9 others).

| # | Test | Asserts |
|---|---|---|
| 1 | `test_banned_jargon_in_headline_blanked` (×4 param) | σ / standard deviation / variance / percentile in headline → blanked; observations survive |
| 2 | `test_forecast_meta_surfaces_in_response` | `forecast_meta.{date_col, value_col, picker_reason}` present on response when forecast computed |
| 3 | `test_bounded_retry_when_whats_likely_next_omitted` | shield_invoke called exactly 2× when first response missing required tab; retry's observations persist |
| 4 | `test_partial_flag_when_retry_also_omits_forecast` | After both attempts omit forecast → `partial_narration_missing_forecast: true` |
| 5 | `test_autopicker_returns_picker_reason` | `pick["picker_reason"]` carries `non_null_count=N, value_spread=…` |
| 6 | `test_autopicker_emits_stdout_log_line` | `[autopick] selected (D, V)` line emitted |
| 7 | `test_forecast_meta_passes_to_prompt_even_when_run_forecast_raises` | **R3v3 regression** — `forecast_meta` on response when `run_forecast` raises (autopicker decision flows past the try) |
| 8 | `test_logger_warning_on_swallowed_forecast_exception` | **R3v3 obs** — `[run_forecast] swallowed exception` WARNING line lands on `akki.workbook_analysis` logger |
| 9 | `test_all_three_tabs_persist_when_all_blocks_populated` | All three required tabs persist when all 3 blocks non-empty + no partial flags |
| 10 | `test_value_spread_uses_minv_maxv_not_truncated_samples` | **R3v3 regression** on `value_spread=0.00` — picker_reason uses minv/maxv not 6-sample preview |

Pytest verbatim: `27 passed in 8.34s` (10 prompt-fix + 13 narration + 4 v1 byte-identical).
Combined with `test_phase_p5_14_workbook_analyze.py`: **58/58 PASS in 9.53s**. Voice-lint `clean across customer-copy surfaces`.

---

## Files touched (verbatim)

```
M backend/routers/workbook_analysis.py            # forecast_meta reorder + logger + anomaly call-site fix
M backend/services/solva_v2/analyze_narration.py  # _build_prompt restructure + general retry + per-tab partial flags
M backend/services/workbook_analyzer/forecaster.py # value_spread uses minv/maxv
M backend/tests/test_track_a_phase3_narration.py  # idempotent test stub updated for R3v3 required-tabs
M backend/tests/test_track_a_phase3_prompt_fix.py # +4 R3v3 tests (7-10); ≤10-cap honoured
M memory/MASTER_STATE.md                          # Section 7 timestamp
?? memory/sprints/TRACK_A_PHASE3_R3V3_PLUMBING_AND_ALL_TABS.md
```

---

## Hard nos honoured

- ✓ No fence-parser touch — `_extract_json_payload` unchanged.
- ✓ No Track B touch.
- ✓ No deterministic engine output schema changes — Pydantic models for `WorkbookSignal`, `ForecastRun`, `AnomalyRow` untouched. The anomaly call-site fix is a router-layer correction (kwargs reshape, not engine signature).
- ✓ No shield_invoke signature change.
- ✓ Bounded retry max 1 per synthesize call total.

---

## Declined per orchestrator

- FE drawer "Forecast picked: (month, actual_sales) · spread 5240.00" chip suggestion from R3v2 enhancement. Phase 4 work. Parked.

---

## Resume contract

Pause for tester on **J19 + J20 only**. MASTER_STATE.md Section 4 Track A Phase 3 stays 🟡 PARTIAL.
