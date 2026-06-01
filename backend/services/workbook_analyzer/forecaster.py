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


__all__ = ["run_forecast"]
