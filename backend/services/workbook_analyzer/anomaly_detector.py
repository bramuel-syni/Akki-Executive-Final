"""Phase P5.14 — Anomaly detector.

Two-rule detector (z-score and IQR) over each numeric column.
Rationale strings are observational and refuse-to-decide
validated. Causes that can be inferred from sibling columns are
deferred to the optional LLM commentary path in
`signal_extractor.narrate_anomaly` — the deterministic detector
itself emits a neutral observational rationale only.

Thresholds:
  * z-score > 3   → strong anomaly
  * |IQR distance| > 1.5 → moderate anomaly

The detector returns BOTH and the upstream router merges
overlaps (a row that fires both rules is reported once with
the higher of the two scores).
"""
from __future__ import annotations

from typing import Any, List

import numpy as np

from .schema import AnomalyRow, WorkbookCitation


def _to_float(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float("nan")


def detect_anomalies(
    *,
    sheet: str,
    column_name: str,
    column_letter: str,
    sheet_matrix: List[List[Any]],
    header_row_index: int,
    col_index_zero: int,
    z_threshold: float = 3.0,
    iqr_multiplier: float = 1.5,
) -> List[AnomalyRow]:
    """Returns one `AnomalyRow` per outlier in the column. Empty
    list if the column has < 4 non-null numeric values (z-score /
    IQR statistics are not robust below that)."""
    data_rows = sheet_matrix[header_row_index:]
    values: List[tuple[int, float]] = []  # (sheet_row_1idx, value)
    for i, r in enumerate(data_rows):
        if col_index_zero >= len(r):
            continue
        v = _to_float(r[col_index_zero])
        if np.isnan(v):
            continue
        values.append((header_row_index + i + 1, v))

    if len(values) < 4:
        return []

    arr = np.array([v for _, v in values], dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    anomalies: List[AnomalyRow] = []
    for (row_idx, v) in values:
        z = (v - mean) / std if std > 0 else 0.0
        if iqr > 0:
            if v > q3:
                iqr_dist = (v - q3) / iqr
            elif v < q1:
                iqr_dist = (v - q1) / iqr  # negative when below q1
            else:
                iqr_dist = 0.0
        else:
            iqr_dist = 0.0
        if abs(z) >= z_threshold or abs(iqr_dist) >= iqr_multiplier:
            direction = "above" if v > mean else "below"
            rationale = (
                f"The {column_name} value at row {row_idx} sits {abs(z):.2f}σ "
                f"{direction} the column mean of {mean:.2f}. The interquartile-"
                f"range distance is {iqr_dist:+.2f}× the IQR. Reviewers may want "
                f"to verify the cell or look for an explanation in the same row."
            )
            anomalies.append(AnomalyRow(
                sheet=sheet,
                column=column_name,
                row_index=row_idx,
                value=float(v),
                z_score=float(z),
                iqr_distance=float(iqr_dist),
                rationale=rationale,
                citations=[WorkbookCitation(
                    cell_range=f"{sheet}!{column_letter}{row_idx}",
                    excerpt=f"{column_name}={v}",
                )],
            ))

    return anomalies


__all__ = ["detect_anomalies"]
