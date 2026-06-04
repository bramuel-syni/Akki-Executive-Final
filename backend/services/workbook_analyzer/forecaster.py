"""Phase P5.14 — Forecaster.

Pure-numpy linear regression on the slope/intercept of a value
column against the date column. The horizon `n` produces n future
projections. Each projection carries a 80% CI band derived from
the residual stddev. The MVP method is linear regression — the
schema field `method` exists so a future "arima" or "stl" baseline
can ship without a breaking change.

Citations: every projection cites the historical cell range from
which it was fit (`<sheet>!<date_col_letter><start_row>:<value_col_letter><end_row>`).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .schema import ForecastRun, NarrationBlock, WorkbookCitation


# Track A Phase 4 (2026-06-04) — tuning constants for autopicker
# density gate + low-R² safety-net flag. Named so they're greppable
# and the synthesize endpoint can import the R² threshold.
_AUTOPICK_MIN_NON_NULL_RATIO = 0.30   # column needs ≥30% non-null density
_AUTOPICK_MIN_NON_NULL_COUNT = 6      # absolute floor for fit-ability
_FORECAST_LOW_R2_THRESHOLD = 0.30     # below this → low_signal flag fires


def _to_ordinal(v: Any) -> Optional[float]:
    if isinstance(v, (datetime, date)):
        return float(v.toordinal())
    return None


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def run_forecast(
    *,
    sheet: str,
    date_column: str,
    value_column: str,
    sheet_matrix: List[List[Any]],
    header_row_index: int,
    date_col_index_zero: int,
    value_col_index_zero: int,
    horizon_periods: int = 8,
    narration: Optional[NarrationBlock] = None,
) -> ForecastRun:
    """Fit a linear regression and project `horizon_periods` ahead.

    `sheet_matrix` is the full 2D row list including the header
    row at position 0. `date_col_index_zero` and
    `value_col_index_zero` are 0-indexed column positions in that
    matrix. `header_row_index` is 1-indexed (so `matrix[header_row_index]`
    is the first data row).

    Citations point at the historical date+value cell ranges.
    """
    if horizon_periods < 1 or horizon_periods > 12:
        raise ValueError("horizon_periods must be in [1, 12]")

    rows = sheet_matrix[header_row_index:]
    pairs: List[Tuple[float, float]] = []
    first_data_row_1idx: Optional[int] = None
    last_data_row_1idx: Optional[int] = None
    for i, r in enumerate(rows):
        if date_col_index_zero >= len(r) or value_col_index_zero >= len(r):
            continue
        d_ord = _to_ordinal(r[date_col_index_zero])
        v_num = _to_float(r[value_col_index_zero])
        if d_ord is None or v_num is None:
            continue
        pairs.append((d_ord, v_num))
        sheet_row_1idx = header_row_index + i + 1
        if first_data_row_1idx is None:
            first_data_row_1idx = sheet_row_1idx
        last_data_row_1idx = sheet_row_1idx

    if len(pairs) < 3:
        raise ValueError(
            "workbook_analyze.forecaster: need at least 3 (date, value) pairs to fit"
        )

    xs = np.array([p[0] for p in pairs], dtype=float)
    ys = np.array([p[1] for p in pairs], dtype=float)

    # numpy.polyfit returns coefficients high-to-low — for degree=1, [slope, intercept].
    slope, intercept = np.polyfit(xs, ys, 1)
    fitted = slope * xs + intercept
    residuals = ys - fitted
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((ys - ys.mean()) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
    band_half = 1.282 * residual_std  # 80% CI under residual-normality

    # Average historical step (days between rows) — used to project forward.
    step_days = float(np.median(np.diff(xs))) if len(xs) > 1 else 30.0
    if step_days <= 0:
        step_days = 30.0

    last_x = float(xs[-1])
    projections: List[Dict[str, float]] = []
    for k in range(1, horizon_periods + 1):
        x_proj = last_x + k * step_days
        y_hat = float(slope * x_proj + intercept)
        projections.append({
            "period_index": int(k),
            "x_ordinal": float(x_proj),
            "value": y_hat,
            "ci_low": float(y_hat - band_half),
            "ci_high": float(y_hat + band_half),
        })

    # Build citations: one range across the historical date column,
    # one across the historical value column.
    def _letter(idx_zero: int) -> str:
        n = idx_zero + 1
        out = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            out = chr(65 + rem) + out
        return out

    date_letter = _letter(date_col_index_zero)
    value_letter = _letter(value_col_index_zero)
    cite_range = (
        f"{sheet}!{date_letter}{first_data_row_1idx}:{value_letter}{last_data_row_1idx}"
    )
    citations = [WorkbookCitation(
        cell_range=cite_range,
        excerpt=(
            f"Fitted on {len(pairs)} historical (date, value) pairs from "
            f"rows {first_data_row_1idx}-{last_data_row_1idx}."
        ),
    )]

    return ForecastRun(
        id="fc-" + uuid.uuid4().hex[:12],
        sheet=sheet,
        date_column=date_column,
        value_column=value_column,
        method="linear_regression",
        n_historical=len(pairs),
        horizon_periods=int(horizon_periods),
        slope=float(slope),
        intercept=float(intercept),
        r2=float(max(0.0, min(1.0, r2))),
        projections=projections,
        narration=narration,
        citations=citations,
    )


def autopick_forecast_columns(
    *,
    sheets: List[Any],
) -> Optional[Dict[str, Any]]:
    """Bug #30 fix (2026-06-04) — column-pair auto-picker.

    Returns `{sheet, date_column, value_column, picker_reason}` for
    the strongest signal pair OR None if no viable pair exists.

    Heuristic: find sheets with at least one `date` column AND one
    or more `numeric` columns. Pick the (date, numeric) pair with
    the HIGHEST non-null count on the numeric column. If two ties,
    prefer the numeric column with the larger variance — that's
    where the strongest forecastable signal usually lives.

    Returns None if no sheet has both a date and a numeric column.

    Track A Phase 3 R3v2 (2026-06-04) — `picker_reason` surfaces the
    pair's score so the synthesize endpoint can expose the choice to
    the user (observability requirement). Also emits a single
    `[autopick]` stdout line per call so the choice is logged when
    re-running in headless harnesses.
    """
    best: Optional[Dict[str, Any]] = None
    best_score: Tuple[int, float] = (0, 0.0)
    rejected_count = 0
    for sheet in sheets:
        cols = getattr(sheet, "columns", [])
        date_cols = [c for c in cols if c.kind == "date"]
        numeric_cols = [c for c in cols if c.kind == "numeric"]
        if not date_cols or not numeric_cols:
            continue
        # Track A Phase 4 (2026-06-04) — density gate. Total row count
        # for ratio math; columns with `<30% non-null OR <6 absolute
        # non-nulls` are excluded entirely. Prevents sparse columns
        # from winning the picker on spread alone (Phase 3 regression
        # discovered post-J19).
        total_rows = max(getattr(sheet, "n_rows", 0) or 0, 1)
        for date_col in date_cols:
            for num_col in numeric_cols:
                non_null = num_col.non_null_count or 0
                density = non_null / total_rows
                if non_null < _AUTOPICK_MIN_NON_NULL_COUNT or density < _AUTOPICK_MIN_NON_NULL_RATIO:
                    rejected_count += 1
                    print(
                        f"[autopick] rejected ({date_col.name}, {num_col.name}) "
                        f"in sheet {sheet.name!r} — density {density:.2f} "
                        f"(min {_AUTOPICK_MIN_NON_NULL_RATIO:.2f}), "
                        f"non_null {non_null} "
                        f"(min {_AUTOPICK_MIN_NON_NULL_COUNT})",
                        flush=True,
                    )
                    continue
                # Score: (non_null_count, value_spread) — descending.
                # Track A Phase 3 R3v3 (2026-06-04) — spread is now
                # computed from the parser's pre-computed minv/maxv on
                # the FULL column (not the truncated 6-sample preview).
                # Sample-based spread silently collapsed to 0.00 when
                # the first six previewed rows happened to look similar
                # or carried non-numeric types that filter dropped —
                # masking real-spread columns like monthly revenue.
                if num_col.maxv is not None and num_col.minv is not None:
                    spread = float(num_col.maxv) - float(num_col.minv)
                else:
                    # Fall back to sample-based spread for the (rare)
                    # case the parser couldn't compute minv/maxv.
                    samples = [
                        float(v) for v in (num_col.sample_values or [])
                        if isinstance(v, (int, float))
                    ]
                    spread = (max(samples) - min(samples)) if len(samples) >= 2 else 0.0
                score = (non_null, spread)
                if score > best_score:
                    best_score = score
                    best = {
                        "sheet": sheet.name,
                        "date_column": date_col.name,
                        "value_column": num_col.name,
                        "picker_reason": (
                            f"non_null_count={num_col.non_null_count}, "
                            f"value_spread={spread:.2f}"
                        ),
                    }
    if best is not None:
        # Observability requirement (Track A Phase 3 R3v2): single
        # stdout line per call so the chosen pair is visible in the
        # supervisor backend log.
        print(
            f"[autopick] selected ({best['date_column']}, "
            f"{best['value_column']}) from sheet {best['sheet']!r} "
            f"({best['picker_reason']})",
            flush=True,
        )
    return best


__all__ = ["run_forecast", "autopick_forecast_columns"]
